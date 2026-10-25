"""Build 315: the Live TV guide. Picking a channel in the guide under the player keeps the guide where it was
scrolled (it used to jump back to the top of the channel list); a cover set with Custom Cover Art shows in the
guide's channel column (MiamiTV); the channel column is dark grey in light mode so white logos show.
Phone viewport with touch; both themes.
Run: python3 tests/test_epg_keep.py (screenshots in /tmp/claude-0/t/shots)"""
import sys as _nsys, os as _nos; _nsys.path.insert(0, _nos.path.dirname(_nos.path.abspath(__file__))); from notice_auto import AUTO_NOTICE
import asyncio, json, os, shutil, threading, http.server, functools, zlib, struct
from urllib.parse import urlparse
from playwright.async_api import async_playwright

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = '/tmp/claude-0/t/srv-epgkeep'; SHOTS = '/tmp/claude-0/t/shots'
PORT = 8847
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

CHANNELS = [{'id': 'link:%02d' % i, 'name': 'Channel %02d' % i, 'url': 'http://tv%02d.example/live.m3u8' % i,
             'logo': ('https://logos.example/white%02d.png' % i) if i % 3 == 0 else '', 'cats': [], 'catNames': [], 'src': 'link'} for i in range(1, 23)]
CHANNELS.append({'id': 'link:miami', 'name': 'MiamiTV', 'url': 'http://miami.example/live.m3u8', 'logo': '', 'cats': [], 'catNames': [], 'src': 'link'})

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
  localStorage.setItem('radioPlayerVideoTab', 'channels'); } })();""" % json.dumps(json.dumps(CHANNELS))

fails = []
def check(ok, msg):
    print(('PASS ' if ok else 'FAIL ') + msg)
    if not ok: fails.append(msg)

async def route(r):
    u = urlparse(r.request.url)
    cors = {'Access-Control-Allow-Origin': '*'}
    if '127.0.0.1' in u.netloc: return await r.continue_()
    if u.netloc == 'logos.example': return await r.fulfill(status=200, content_type='image/png', headers=cors, body=WHITE)
    if u.netloc == 'miamitv.sfo3.cdn.example': return await r.fulfill(status=200, content_type='image/png', headers=cors, body=ORANGE)
    return await r.abort()

ROW = """(name) => { var r = Array.from(document.querySelectorAll('#npCollection .epg-row')).find(function(x){ return x.querySelector('.epg-ch').getAttribute('aria-label').indexOf(name) === 0; });
  if(!r) return null; var b = r.getBoundingClientRect(); return { top: Math.round(b.top), bottom: Math.round(b.bottom) }; }"""

async def run(p, theme):
    T = '[%s]' % theme
    b = await p.chromium.launch()
    ctx = await b.new_context(viewport={'width': 412, 'height': 900}, device_scale_factor=2, is_mobile=True, has_touch=True, color_scheme=theme, locale='en-US')
    await ctx.add_init_script(MOCK); await ctx.add_init_script(AUTO_NOTICE); await ctx.add_init_script(SEED)
    await ctx.add_init_script("try{ localStorage.setItem('radioPlayerTheme', '%s'); }catch(e){}" % theme)
    pg = await ctx.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
    await pg.route('**/*', route)
    await pg.goto('http://127.0.0.1:%d/index.html' % PORT); await pg.wait_for_timeout(2000)
    # MiamiTV's own cover, as set with Custom Cover Art.
    await pg.evaluate("() => window.__h.ev(\"var c = findVideoChannel('http://miami.example/live.m3u8'); setCustomArtUrl(favKey(channelToStation(c)), 'https://miamitv.sfo3.cdn.example/logo.png'); 1\")")
    await pg.tap('.mobile-nav-btn[data-nav=video]'); await pg.wait_for_timeout(2000)

    # Channel column colour and logos on the Watch page.
    col = await pg.evaluate("""() => { var c = document.querySelector('#stationsGrid .epg-ch'); var bg = getComputedStyle(c, '::before').backgroundColor;
      var m = Array.from(document.querySelectorAll('#stationsGrid .epg-row')).find(function(r){ return r.dataset.chUrl.indexOf('miami') >= 0; });
      var img = m && m.querySelector('.epg-logo img');
      return { bg: bg, miami: !!img && img.naturalWidth > 0, miamiSrc: img ? img.src : '', names: m ? m.querySelectorAll('.epg-logo-name').length : -1 }; }""")
    want = 'rgb(43, 44, 49)' if theme == 'light' else 'rgb(0, 0, 0)'
    check(col['bg'] == want, '%s channel column background %s' % (T, col['bg']))
    check(col['miami'] and col['names'] == 0, '%s MiamiTV shows its custom cover in the guide %s' % (T, col))
    await pg.evaluate("() => { var m = Array.from(document.querySelectorAll('#stationsGrid .epg-row')).find(function(r){ return r.dataset.chUrl.indexOf('miami') >= 0; }); m.scrollIntoView({ block: 'center' }); }")
    await pg.wait_for_timeout(500)
    await pg.screenshot(path=SHOTS + '/epgkeep-watch-%s.png' % theme)

    # Watch Channel 02 from the guide: Now Playing with the guide under it.
    await pg.evaluate("() => window.scrollTo(0, 0)"); await pg.wait_for_timeout(300)
    await pg.tap('#stationsGrid .epg-row:nth-of-type(2) .epg-prog'); await pg.wait_for_timeout(1800)
    name = await pg.evaluate("() => document.getElementById('npName').textContent")
    check(name == 'Channel 02', '%s playing Channel 02 (%s)' % (T, name))
    # Scroll the guide under the player well down, to Channel 18.
    await pg.evaluate("""() => { var r = Array.from(document.querySelectorAll('#npCollection .epg-row')).find(function(x){ return x.dataset.chUrl.indexOf('tv18') >= 0; });
      r.scrollIntoView({ block: 'center' }); }""")
    await pg.wait_for_timeout(600)
    before = await pg.evaluate(ROW, 'Channel 18')
    sx = await pg.evaluate("() => { var s = document.querySelector('#npCollection .epg-scroll'); s.scrollLeft = 150; return s.scrollLeft; }")
    await pg.wait_for_timeout(200)
    await pg.screenshot(path=SHOTS + '/epgkeep-np-before-%s.png' % theme)
    # Pick Channel 18 with a finger.
    box = await pg.evaluate("""() => { var r = Array.from(document.querySelectorAll('#npCollection .epg-row')).find(function(x){ return x.dataset.chUrl.indexOf('tv18') >= 0; });
      var b = r.querySelector('.epg-prog').getBoundingClientRect(); return [Math.max(b.left + 20, 140), b.top + b.height / 2]; }""")
    await pg.touchscreen.tap(box[0], box[1]); await pg.wait_for_timeout(1800)
    name = await pg.evaluate("() => document.getElementById('npName').textContent")
    after = await pg.evaluate(ROW, 'Channel 18')
    sx2 = await pg.evaluate("() => document.querySelector('#npCollection .epg-scroll').scrollLeft")
    check(name == 'Channel 18', '%s picking Channel 18 plays it (%s)' % (T, name))
    check(before and after and abs(after['top'] - before['top']) <= 2, '%s the guide stays where it was (row top %s -> %s)' % (T, before, after))
    check(after and 0 <= after['top'] < 900, '%s Channel 18 still on screen' % T)
    check(abs(sx2 - sx) <= 2, '%s and keeps its sideways place (%d -> %d)' % (T, sx, sx2))
    playing = await pg.evaluate("() => { var r = Array.from(document.querySelectorAll('#npCollection .epg-row')).find(function(x){ return x.dataset.chUrl.indexOf('tv18') >= 0; }); return r.querySelector('.epg-ch').classList.contains('playing'); }")
    check(playing, '%s Channel 18 marked playing in the guide' % T)
    await pg.screenshot(path=SHOTS + '/epgkeep-np-after-%s.png' % theme)
    # Once more, further down (MiamiTV): still in place, and its cover shows under the player too.
    await pg.evaluate("""() => { var r = Array.from(document.querySelectorAll('#npCollection .epg-row')).find(function(x){ return x.dataset.chUrl.indexOf('miami') >= 0; });
      r.scrollIntoView({ block: 'center' }); }""")
    await pg.wait_for_timeout(500)
    b2 = await pg.evaluate(ROW, 'MiamiTV')
    box = await pg.evaluate("""() => { var r = Array.from(document.querySelectorAll('#npCollection .epg-row')).find(function(x){ return x.dataset.chUrl.indexOf('miami') >= 0; });
      var b = r.querySelector('.epg-prog').getBoundingClientRect(); return [Math.max(b.left + 20, 140), b.top + b.height / 2]; }""")
    await pg.touchscreen.tap(box[0], box[1]); await pg.wait_for_timeout(1800)
    a2 = await pg.evaluate(ROW, 'MiamiTV')
    mi = await pg.evaluate("() => { var r = Array.from(document.querySelectorAll('#npCollection .epg-row')).find(function(x){ return x.dataset.chUrl.indexOf('miami') >= 0; }); var i = r.querySelector('.epg-logo img'); return !!i && i.naturalWidth > 0; }")
    check(b2 and a2 and abs(a2['top'] - b2['top']) <= 2, '%s MiamiTV: guide stays put (%s -> %s)' % (T, b2, a2))
    check(mi, '%s MiamiTV cover under the player' % T)
    await pg.screenshot(path=SHOTS + '/epgkeep-np-miami-%s.png' % theme)
    check(not errs, '%s no page errors %s' % (T, errs[:3]))
    await b.close()

async def main():
    async with async_playwright() as p:
        await run(p, 'light')
        await run(p, 'dark')
    print('ALL PASSED' if not fails else 'FAILED %s' % fails)
    raise SystemExit(1 if fails else 0)
asyncio.run(main())
