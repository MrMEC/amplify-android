"""(replaced below)
Build 315: the Live TV guide. Picking a channel in the guide under the player keeps the guide where it was
scrolled (it used to jump back to the top of the channel list); a cover set with Custom Cover Art shows in the
guide's channel column (MiamiTV); the channel column is dark grey in light mode so white logos show.
Phone viewport with touch; both themes.
Run: python3 tests/test_epg_keep.py (screenshots in /tmp/claude-0/t/shots)"""
import sys as _nsys, os as _nos; _nsys.path.insert(0, _nos.path.dirname(_nos.path.abspath(__file__))); from notice_auto import AUTO_NOTICE
import asyncio, json, os, shutil, threading, http.server, functools, zlib, struct
from urllib.parse import urlparse
from playwright.async_api import async_playwright

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = '/tmp/claude-0/t/srv-guide688'; SHOTS = '/tmp/claude-0/t/shots'
PORT = 8870
shutil.rmtree(ROOT, ignore_errors=True); os.makedirs(ROOT, exist_ok=True); os.makedirs(SHOTS, exist_ok=True)
src = open(os.path.join(HERE, '..', 'www', 'index.html')).read()
mark = '  var coverFlow = null;\n'
assert src.count(mark) == 1
HOOK = "window.__h = { ev: function(js){ return eval(js); } };\n"
open(ROOT + '/index.html', 'w').write(src.replace(mark, mark + HOOK))
H = functools.partial(http.server.SimpleHTTPRequestHandler, directory=ROOT); H.log_message = lambda *a: None
srv = http.server.ThreadingHTTPServer(('127.0.0.1', PORT), H); threading.Thread(target=srv.serve_forever, daemon=True).start()

def png(w, h, rgb):
    raw = b''.join(b'\x00' + bytes(rgb) * w for _ in range(h))
    ch = lambda t, d: struct.pack('>I', len(d)) + t + d + struct.pack('>I', zlib.crc32(t + d) & 0xffffffff)
    return b'\x89PNG\r\n\x1a\n' + ch(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, 2, 0, 0, 0)) + ch(b'IDAT', zlib.compress(raw)) + ch(b'IEND', b'')
WHITE = png(120, 60, (255, 255, 255))
ORANGE = png(120, 120, (255, 160, 0))

def C(i, name, cats, src='pluto', url=None, **kw):
    d = {'id': 'x:%d' % i, 'name': name, 'url': url or 'http://tv%02d.example/live.m3u8' % i, 'logo': 'https://logos.example/l%02d.png' % i, 'cats': [c.lower() for c in cats], 'catNames': cats, 'src': src}
    d.update(kw); return d
for _d in []: pass
LOGOS = {('/l%02d.png' % i): open('/tmp/mock3/%s.png' % n, 'rb').read() for i, n in [(1, 'aew'), (2, 'lh'), (3, 'mtv'), (4, 'tc'), (5, 'tmz')]}
CHANNELS = [
  C(1, 'AEW Rampage Episode 3 (2021)', [], 'archive', url='amplify-archive:i:aew-rampage-ep3', archive={'id': 'aew-rampage-ep3', 'title': 'AEW Rampage Episode 3', 'video': True}),
  C(2, 'Little House on the Prairie', ['Classic TV']), C(3, 'MTV Music Videos', [], 'link'), C(4, "Three's Company", ['Classic TV']),
  C(5, 'TMZ', ['Entertainment']), C(6, 'CBS News', ['News'], 'starter'), C(7, 'Reuters TV', ['News'], 'starter'),
  C(8, 'WeatherNation', ['Weather'], 'starter'), C(9, 'Stadium', ['Sports']), C(10, 'Pluto TV Westerns', ['Westerns']),
  C(11, 'MST3K', ['Comedy']), C(12, 'Kids Animation', ['Kids']), C(13, 'Beach TV Key West', ['Live Cams'], 'starter'),
  C(14, 'Window TV', ['Live Cams'], 'starter'), C(15, 'NASA TV', ['Space'], 'starter'), C(16, 'Docurama', ['Documentary'], 'starter'),
  C(17, 'Retro TV', ['Classic TV'], 'starter'), C(18, 'Unsolved Mysteries', ['True Crime']), C(19, 'Bob Ross', ['Lifestyle + DIY']),
  C(20, 'Pluto TV Comedy Central', ['Comedy'])]
MOCK = """
(function(){
 window.__calls=[]; window.__L={}; window.__emit=function(t,ev){ (window.__L[t]||[]).forEach(function(f){ f(ev); }); };
 var P=new Proxy({}, {get:function(t,k){
   if(k==='then') return undefined;
   if(k==='addListener') return function(n,f){ (window.__L[n]=window.__L[n]||[]).push(f); return Promise.resolve({remove:function(){}}); };
   if(k==='load') return function(a){ window.__calls.push(['load',a.url]);
      setTimeout(function(){ window.__emit('state',{id:a.id,state:'ready',isPlaying:true,playWhenReady:true,position:0,duration:-1,live:true}); },60);
      return Promise.resolve({}); };
   if(k==='videoState') return function(){ return Promise.resolve({id:null,hasVideo:false}); };
   return function(){ return Promise.resolve({}); };
 }});
 window.Capacitor={isNativePlatform:function(){return true;},getPlatform:function(){return 'android';},Plugins:{AmplifyPlayer:P},convertFileSrc:function(u){return u;}};
})();
"""
SEED = """(function(){ if(!localStorage.getItem('__seeded')){ localStorage.setItem('__seeded','1');
  localStorage.setItem('radioPlayerVideoChannels', %s);
  localStorage.setItem('radioPlayerVideoTab', 'channels'); localStorage.setItem('radioPlayerTourDone', '1'); localStorage.setItem('radioPlayerStarterPack', '1'); localStorage.setItem('radioPlayerLiveChannels', '[]'); } })();""" % json.dumps(json.dumps(CHANNELS))

fails = []
def check(ok, msg):
    print(('PASS ' if ok else 'FAIL ') + msg)
    if not ok: fails.append(msg)

async def route(r):
    u = urlparse(r.request.url)
    cors = {'Access-Control-Allow-Origin': '*'}
    if '127.0.0.1' in u.netloc: return await r.continue_()
    if u.netloc == 'logos.example' and u.path in LOGOS: return await r.fulfill(status=200, content_type='image/png', headers=cors, body=LOGOS[u.path])
    if u.netloc == 'logos.example': return await r.fulfill(status=200, content_type='image/png', headers=cors, body=png(160, 90, (20 + (hash(u.path) % 7) * 30, 60, 140)))
    if 'archive.org' in u.netloc and r.request.resource_type == 'image': return await r.fulfill(status=200, content_type='image/png', headers=cors, body=ORANGE)
    if u.netloc == 'miamitv.sfo3.cdn.example': return await r.fulfill(status=200, content_type='image/png', headers=cors, body=ORANGE)
    return await r.abort()


EV = lambda js: "() => window.__h.ev(%s)" % json.dumps(js)
CHIPS = "() => Array.from(document.querySelectorAll('#stationsGrid .epg-cat')).map(function(b){ return (b.classList.contains('active') ? '*' : '') + b.textContent; })"
ROWS = "(sel) => Array.from(document.querySelectorAll(sel + ' .epg-row')).map(function(r){ return r.querySelector('.epg-ch').getAttribute('aria-label').split(',')[0]; })"
async def chip(pg, scope, label):
    await pg.evaluate("([s, l]) => Array.from(document.querySelectorAll(s + ' .epg-cat')).find(function(b){ return b.textContent === l; }).click()", [scope, label]); await pg.wait_for_timeout(500)
for _d in CHANNELS: _d['src'] = 'link'
SCHED = r"""(function(){
  var H = 30 * 60000, t0 = Math.floor(Date.now() / H) * H;
  var S = {
    'AEW Rampage Episode 3 (2021)': [[-40, 40, 'AEW Friday Night Dynamite 04-06-2021', '2021']],
    'Little House on the Prairie': [[-35, 30, 'Little House on the Prairie', 'Money Crop'], [30, 90, 'Little House on the Prairie', 'Survival']],
    'MTV Music Videos': [[-60, 120, 'Music Videos', '']],
    "Three's Company": [[-8, 30, "Three's Company", "Critic's Choice"], [30, 60, "Three's Company", 'In Like Larry']],
    'TMZ': [[-10, 30, 'TMZ LIVE', ''], [30, 60, 'TMZ LIVE', '']],
    'CBS News': [[-30, 30, 'CBS News 24/7', 'Top stories'], [30, 60, 'CBS Evening News', '']],
    'Reuters TV': [[-20, 30, 'Reuters Now', 'World news'], [30, 60, 'Reuters Weekly', '']], 'Docurama': [[-15, 30, 'Rivers of Life', 'The Amazon'], [30, 75, 'Planet Ice', '']]
  };
  var og = guideSource; guideSource = function(ch){ return og(ch) || (ch && S[ch.name] ? { key: 'test:' + ch.url } : null); };
  guideNeedsFetch = function(){ return false; }; guideRefresh = function(){};
  var orig = guideItemsFor;
  guideItemsFor = function(ch){ var a = S[ch && ch.name]; if(!a) return orig(ch); return a.map(function(x){ return { s: t0 + x[0] * 60000, e: t0 + x[1] * 60000, t: x[2], sub: x[3] }; }); };
  return 1; })()"""
async def run(p, theme, W=327, H=675, land=False, accent='#ff1f1f'):
    T = '[%s%s %s]' % (theme, ' land' if land else '', accent)
    b = await p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
    ctx = await b.new_context(viewport={'width': W, 'height': H}, device_scale_factor=3.3, is_mobile=True, has_touch=True, color_scheme=theme, locale='en-US')
    await ctx.add_init_script(MOCK); await ctx.add_init_script(SEED)
    await ctx.add_init_script("try{ localStorage.setItem('radioPlayerTheme', '%s'); localStorage.setItem('radioPlayerLtvAuto', '0'); localStorage.setItem('radioPlayerCustomAccent', JSON.stringify({dark: '%s', light: '%s'})); localStorage.setItem('radioPlayerGuideCatOrder', JSON.stringify(['cat:My Channels','cat:Local','cat:Wrestling','fav'])); }catch(e){}" % (theme, accent, accent))
    pg = await ctx.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
    await pg.route('**/*', route)
    await pg.goto('http://127.0.0.1:%d/index.html' % PORT); await pg.wait_for_timeout(2000)
    await pg.evaluate("() => document.getElementById('noticeOverlay').classList.remove('open')")
    await pg.evaluate(EV("['x:1','x:2','x:3','x:4','x:5'].forEach(function(id){ var c = videoChannels.find(function(v){ return v.id === id; }); if(c && !isFavorite(channelToStation(c))) toggleFavorite(channelToStation(c)); }); 1"))
    await pg.evaluate(EV(SCHED))
    await pg.tap('.mobile-nav-btn[data-nav=video]'); await pg.wait_for_timeout(2200)
    if land:
        await pg.screenshot(path=SHOTS + '/g687-land-%s.png' % theme)
        check(not errs, '%s no page errors %s' % (T, errs[:3])); await b.close(); return
    g = await pg.evaluate("""() => { var w = document.querySelector('#stationsGrid .epg'); var r = w.querySelector('.epg-row'); var ch = r.querySelector('.epg-ch'), pr = r.querySelector('.epg-prog');
      var cb = getComputedStyle(ch, '::before'); var fi = document.querySelector('#secFilterInput'); var fr = fi.getBoundingClientRect();
      var bar = w.querySelector('.epg-now-bar'), cur = w.querySelector('.epg-time.cur');
      return { wl: Math.round(w.getBoundingClientRect().left), ww: Math.round(w.getBoundingClientRect().width), rowH: Math.round(r.getBoundingClientRect().height),
        chR: Math.round(ch.getBoundingClientRect().right), prL: Math.round(pr.getBoundingClientRect().left), cbRight: cb.right, cbBg: cb.backgroundColor, prBg: getComputedStyle(pr).backgroundColor,
        line: getComputedStyle(w.querySelector('.epg-now')).display, bar: bar ? [Math.round(bar.getBoundingClientRect().width), bar.firstChild.style.width] : null, cur: cur && cur.textContent,
        corner: w.querySelector('.epg-corner').textContent, fBg: getComputedStyle(fi).backgroundColor, fL: Math.round(fr.left), fR: Math.round(innerWidth - fr.right) }; }""")
    print(T, g)
    check(g['wl'] == 0 and g['ww'] == W, '%s guide edge to edge %s' % (T, (g['wl'], g['ww'])))
    check(g['rowH'] == 82, '%s rows 20px taller (82) %s' % (T, g['rowH']))
    check(g['cbRight'] == '-7px' and g['cbBg'] == g['prBg'], '%s logo cell runs into the listing, same colour %s' % (T, (g['cbBg'], g['prBg'])))
    check(g['line'] == 'none' and g['bar'] and g['cur'], '%s no line; progress bar under %s %s' % (T, g['cur'], g['bar']))
    check(g['corner'].split(' ')[0] in ('SUN','MON','TUE','WED','THU','FRI','SAT'), '%s date in the corner when nothing plays: %s' % (T, g['corner']))
    check(g['fBg'] in ('rgba(0, 0, 0, 0)', 'transparent') and abs(g['fL'] - g['fR']) <= 1, '%s filter box: no fill, centred %s' % (T, (g['fBg'], g['fL'], g['fR'])))
    await pg.screenshot(path=SHOTS + '/g687-watch-%s.png' % theme)
    # play CBS News: corner arrow under the video and on Watch
    await pg.evaluate("() => Array.from(document.querySelectorAll('#stationsGrid .epg-row')).find(function(r){ return r.dataset.chUrl.indexOf('tv06') >= 0; }).querySelector('.epg-prog.now, .epg-prog').click()"); await pg.wait_for_timeout(2500)
    npc = await pg.evaluate("() => { var c = document.querySelector('#npCollection .epg-corner'); return c ? [c.textContent, !!c.querySelector('svg'), c.disabled] : null; }")
    check(npc and npc[1] and not npc[0], '%s under the video: the arrow in the corner %s' % (T, npc))
    await pg.screenshot(path=SHOTS + '/g688-np-%s-%s.png' % (theme, accent[1:]))
    await pg.evaluate(EV("closeNowPlaying(false, false); 1")); await pg.wait_for_timeout(1000)
    wc = await pg.evaluate("() => { var c = document.querySelector('#stationsGrid .epg-corner'); return [c.textContent, !!c.querySelector('svg')]; }")
    check(wc[1] and not wc[0], '%s Watch while a channel plays: the arrow, not the date %s' % (T, wc))
    c = await pg.evaluate("""() => { var lum = function(c){ var m = c.match(/[\\d.]+/g).map(Number); return 0.2126*m[0] + 0.7152*m[1] + 0.0722*m[2]; };
      var rows = Array.from(document.querySelectorAll('#stationsGrid .epg-row')); var pr = rows.find(function(r){ return r.classList.contains('playing'); });
      var other = rows.find(function(r){ return !r.classList.contains('playing') && r.querySelector('.epg-prog.now') && r.querySelectorAll('.epg-prog').length > 1; });
      var bg = function(el, pse){ return getComputedStyle(el, pse || null).backgroundColor; };
      return { playing: pr ? pr.querySelector('.epg-ch').getAttribute('aria-label') : null, hlCh: pr && bg(pr.querySelector('.epg-ch'), '::before'), hlNow: pr && bg(pr.querySelector('.epg-prog.now')),
        now: bg(other.querySelector('.epg-prog.now')), later: bg(other.querySelector('.epg-prog:not(.now)')), gap: bg(document.querySelector('#stationsGrid .epg-scroll')),
        lNow: lum(bg(other.querySelector('.epg-prog.now'))), lLater: lum(bg(other.querySelector('.epg-prog:not(.now)'))) }; }""")
    print(T, c)
    check(c['playing'] and c['hlCh'] == c['hlNow'] and c['hlNow'] != c['now'], '%s playing row: logo and what\u2019s on tinted alike %s' % (T, (c['hlCh'], c['now'])))
    check(c['lNow'] > c['lLater'], '%s what\u2019s on now is lighter than later listings %s' % (T, (c['now'], c['later'])))
    check(c['gap'] in ('rgb(0, 0, 0)', 'rgb(195, 199, 207)'), '%s gaps: %s' % (T, c['gap']))
    await pg.evaluate("() => { var r = document.querySelector('#stationsGrid .epg-row.playing'); window.scrollTo(0, r.getBoundingClientRect().top + scrollY - 330); }"); await pg.wait_for_timeout(400)
    await pg.screenshot(path=SHOTS + '/g688-watch-playing-%s-%s.png' % (theme, accent[1:]))
    check(not errs, '%s no page errors %s' % (T, errs[:3]))
    await b.close()
async def main():
    async with async_playwright() as p:
        await run(p, 'dark')
        await run(p, 'light')
        await run(p, 'dark', accent='#f5b82e')
        await run(p, 'light', accent='#f5b82e')
    print('ALL PASSED' if not fails else 'FAILS %d' % len(fails))
asyncio.run(main())
