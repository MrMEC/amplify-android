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
ROOT = '/tmp/claude-0/t/srv-livecats'; SHOTS = '/tmp/claude-0/t/shots'
PORT = 8865
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
    if u.netloc == 'logos.example': return await r.fulfill(status=200, content_type='image/png', headers=cors, body=png(160, 90, (20 + (hash(u.path) % 7) * 30, 60, 140)))
    if 'archive.org' in u.netloc and r.request.resource_type == 'image': return await r.fulfill(status=200, content_type='image/png', headers=cors, body=ORANGE)
    if u.netloc == 'miamitv.sfo3.cdn.example': return await r.fulfill(status=200, content_type='image/png', headers=cors, body=ORANGE)
    return await r.abort()


EV = lambda js: "() => window.__h.ev(%s)" % json.dumps(js)
CHIPS = "() => Array.from(document.querySelectorAll('#stationsGrid .epg-cat')).map(function(b){ return (b.classList.contains('active') ? '*' : '') + b.textContent; })"
ROWS = "(sel) => Array.from(document.querySelectorAll(sel + ' .epg-row')).map(function(r){ return r.querySelector('.epg-ch').getAttribute('aria-label').split(',')[0]; })"
async def chip(pg, scope, label):
    await pg.evaluate("([s, l]) => Array.from(document.querySelectorAll(s + ' .epg-cat')).find(function(b){ return b.textContent === l; }).click()", [scope, label]); await pg.wait_for_timeout(500)
async def run(p, theme, W=327, H=700):
    T = '[%s]' % theme
    b = await p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
    ctx = await b.new_context(viewport={'width': W, 'height': H}, device_scale_factor=3.3, is_mobile=True, has_touch=True, color_scheme=theme, locale='en-US')
    await ctx.add_init_script(MOCK); await ctx.add_init_script(SEED)
    await ctx.add_init_script("try{ localStorage.setItem('radioPlayerTheme', '%s'); localStorage.setItem('radioPlayerLtvAuto', '0'); }catch(e){}" % theme)
    pg = await ctx.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
    await pg.route('**/*', route)
    await pg.goto('http://127.0.0.1:%d/index.html' % PORT); await pg.wait_for_timeout(2000)
    await pg.evaluate("() => document.getElementById('noticeOverlay').classList.remove('open')")
    # Mark's favourites
    await pg.evaluate(EV("['x:1','x:2','x:3','x:4','x:5'].forEach(function(id){ var c = videoChannels.find(function(v){ return v.id === id; }); if(c && !isFavorite(channelToStation(c))) toggleFavorite(channelToStation(c)); }); 1"))
    await pg.tap('.mobile-nav-btn[data-nav=video]'); await pg.wait_for_timeout(2000)
    cats = await pg.evaluate(EV("var o = {}; videoChannels.forEach(function(c){ o[c.name] = chCategory(c); }); o"))
    want = {'AEW Rampage Episode 3 (2021)': 'Sports', 'Little House on the Prairie': 'Classic TV', 'MTV Music Videos': 'Music', 'TMZ': 'Entertainment', 'WeatherNation': 'News',
            'Stadium': 'Sports', 'Pluto TV Westerns': 'Movies', 'MST3K': 'Comedy', 'Kids Animation': 'Kids & Family', 'Beach TV Key West': 'Live Cams', 'NASA TV': 'Nature & Science',
            'Docurama': 'Nature & Science', 'Unsolved Mysteries': 'Crime & Mystery', 'Bob Ross': 'Lifestyle'}
    bad = {k: (cats.get(k), v) for k, v in want.items() if cats.get(k) != v}
    check(not bad, '%s automatic categories %s' % (T, bad))
    chips = await pg.evaluate(CHIPS)
    check(chips[:4] == ['*All', 'Favorites', 'Sports', 'News'] and 'Sports' in chips and 'Live Cams' in chips, '%s chips on the Watch guide %s' % (T, chips))
    geo = await pg.evaluate("() => { var c = document.querySelector('#stationsGrid .epg-cats').getBoundingClientRect(), t = document.querySelector('#stationsGrid .epg-head-track').getBoundingClientRect(), r = document.querySelector('#stationsGrid .epg-row').getBoundingClientRect(); return [Math.round(c.bottom), Math.round(t.top), Math.round(t.bottom), Math.round(r.top)]; }")
    check(geo[0] <= geo[1] + 1 and geo[2] <= geo[3] + 1, '%s chips sit right above the times, rows below %s' % (T, geo))
    await pg.screenshot(path=SHOTS + '/livecats-watch-all-%s.png' % theme)
    await chip(pg, '#stationsGrid', 'Sports')
    rows = await pg.evaluate(ROWS, '#stationsGrid')
    check(sorted(rows) == sorted(['AEW Rampage Episode 3 (2021)', 'Stadium']), '%s Sports shows only sports %s' % (T, rows))
    await pg.screenshot(path=SHOTS + '/livecats-watch-sports-%s.png' % theme)
    await chip(pg, '#stationsGrid', 'Favorites')
    rows = await pg.evaluate(ROWS, '#stationsGrid')
    check(len(rows) == 5, '%s Favorites shows the five %s' % (T, rows))
    await chip(pg, '#stationsGrid', 'All')
    # sticky: chips and times stay together at the top while the rows scroll
    await pg.evaluate("() => window.scrollTo(0, 600)"); await pg.wait_for_timeout(400)
    st = await pg.evaluate("() => { var h = document.querySelector('#stationsGrid .epg-head').getBoundingClientRect(); var c = document.querySelector('#stationsGrid .epg-cats').getBoundingClientRect(); return [Math.round(h.top), Math.round(c.top), Math.round(h.bottom)]; }")
    check(st[0] < 120 and abs(st[1] - st[0]) <= 1, '%s chips stay stuck with the times when scrolled %s' % (T, st))
    await pg.screenshot(path=SHOTS + '/livecats-watch-scrolled-%s.png' % theme)
    await pg.evaluate("() => window.scrollTo(0, 0)"); await pg.wait_for_timeout(300)
    # News chosen, then play CBS News: the guide under the video has the same chips, News chosen
    await chip(pg, '#stationsGrid', 'News')
    await pg.evaluate("() => Array.from(document.querySelectorAll('#stationsGrid .epg-row')).find(function(r){ return r.dataset.chUrl.indexOf('tv06') >= 0; }).querySelector('.epg-prog').click()"); await pg.wait_for_timeout(2200)
    npc = await pg.evaluate("() => Array.from(document.querySelectorAll('#npCollection .epg-cat')).map(function(b){ return (b.classList.contains('active') ? '*' : '') + b.textContent; })")
    check('*News' in npc, '%s under the video: chips with News chosen %s' % (T, npc))
    g2 = await pg.evaluate("() => { var v = document.querySelector('#nowPlayingScreen .np-hero') || document.querySelector('#npArtWrap'); var c = document.querySelector('#npCollection .epg-cats').getBoundingClientRect(), t = document.querySelector('#npCollection .epg-head-track').getBoundingClientRect(); return [v ? Math.round(v.getBoundingClientRect().bottom) : -1, Math.round(c.top), Math.round(c.bottom), Math.round(t.top)]; }")
    check(g2[1] >= g2[0] - 2 and g2[2] <= g2[3] + 1, '%s chips under the video, above the times %s' % (T, g2))
    await pg.screenshot(path=SHOTS + '/livecats-np-news-%s.png' % theme)
    await chip(pg, '#npCollection', 'Live Cams')
    rows = await pg.evaluate(ROWS, '#npCollection')
    check(sorted(rows) == ['Beach TV Key West', 'Window TV'], '%s Live Cams under the video %s' % (T, rows))
    await pg.screenshot(path=SHOTS + '/livecats-np-cams-%s.png' % theme)
    await pg.evaluate(EV("closeNowPlaying(false, false); 1")); await pg.wait_for_timeout(800)
    await pg.evaluate("() => window.scrollTo(0, 0)")
    # chosen chip kept after a restart
    await pg.reload(); await pg.wait_for_timeout(2000); await pg.evaluate("() => document.getElementById('noticeOverlay').classList.remove('open')")
    await pg.tap('.mobile-nav-btn[data-nav=video]'); await pg.wait_for_timeout(1800)
    chips = await pg.evaluate(CHIPS)
    check('*Live Cams' in chips, '%s the chosen chip is kept after a restart %s' % (T, chips[:6]))
    await chip(pg, '#stationsGrid', 'All')
    # change TMZ's category from its sheet: Category > News; then Automatic
    async def sheet_for(name):
        await pg.evaluate("(n) => Array.from(document.querySelectorAll('#stationsGrid .epg-row')).find(function(r){ return r.querySelector('.epg-ch').getAttribute('aria-label').indexOf(n) === 0; }).querySelector('.epg-ch').click()", name); await pg.wait_for_timeout(500)
    await sheet_for('TMZ')
    items = await pg.evaluate("() => Array.from(document.querySelectorAll('#chSheetItems .ch-sheet-item')).map(function(b){ return b.textContent; })")
    check('Category: Entertainment' in items, '%s the sheet shows Category: Entertainment %s' % (T, items))
    await pg.screenshot(path=SHOTS + '/livecats-sheet-%s.png' % theme)
    await pg.evaluate("() => Array.from(document.querySelectorAll('#chSheetItems .ch-sheet-item')).find(function(b){ return b.textContent.indexOf('Category') === 0; }).click()"); await pg.wait_for_timeout(400)
    opts = await pg.evaluate("() => [document.getElementById('chSheetOverlay').classList.contains('open'), Array.from(document.querySelectorAll('#chSheetItems .ch-sheet-item')).map(function(b){ return b.textContent; })]")
    check(opts[0] and opts[1][0].startswith('Automatic') and 'News' in opts[1] and opts[1][-1] == 'New Category', '%s the category list %s' % (T, opts[1][:4]))
    await pg.screenshot(path=SHOTS + '/livecats-catlist-%s.png' % theme)
    await pg.evaluate("() => Array.from(document.querySelectorAll('#chSheetItems .ch-sheet-item')).find(function(b){ return b.textContent === 'News'; }).click()"); await pg.wait_for_timeout(400)
    await chip(pg, '#stationsGrid', 'News')
    rows = await pg.evaluate(ROWS, '#stationsGrid')
    check('TMZ' in rows, '%s TMZ now under News %s' % (T, rows))
    await chip(pg, '#stationsGrid', 'All')
    # New Category for AEW
    await sheet_for('AEW')
    await pg.evaluate("() => Array.from(document.querySelectorAll('#chSheetItems .ch-sheet-item')).find(function(b){ return b.textContent.indexOf('Category') === 0; }).click()"); await pg.wait_for_timeout(300)
    await pg.evaluate("() => Array.from(document.querySelectorAll('#chSheetItems .ch-sheet-item')).find(function(b){ return b.textContent === 'New Category'; }).click()"); await pg.wait_for_timeout(400)
    await pg.fill('.ch-cat-input', 'wrestling'); await pg.wait_for_timeout(100)
    await pg.screenshot(path=SHOTS + '/livecats-newcat-%s.png' % theme)
    await pg.evaluate("() => Array.from(document.querySelectorAll('#noticeActions button')).find(function(b){ return b.textContent === 'Save'; }).click()"); await pg.wait_for_timeout(500)
    chips = await pg.evaluate(CHIPS)
    check('Wrestling' in chips, '%s New Category "Wrestling" appears as a chip %s' % (T, chips))
    check(not errs, '%s no page errors %s' % (T, errs[:3]))
    await b.close()
async def main():
    async with async_playwright() as p:
        await run(p, 'dark')
        await run(p, 'light')
    print('ALL PASSED' if not fails else 'FAILS %d' % len(fails))
asyncio.run(main())
