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
ROOT = '/tmp/claude-0/t/srv-multicat2'; SHOTS = '/tmp/claude-0/t/shots'
PORT = 8879
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
DEF = [{'id': 'aewch', 'name': 'AEW', 'order': 'sequence', 'src': {'kind': 'pick', 'shows': [], 'movies': [], 'archive': [{'id': 'aew-dyn', 'title': 'AEW Friday Night Dynamite', 'creator': '', 'year': '2021'}]}}]
async def run(p, theme, W=327, H=675):
    T = '[%s]' % theme
    D = DEF + [{'id': 'seinfeld', 'name': '', 'order': 'sequence', 'src': {'kind': 'pick', 'shows': ['Seinfeld'], 'movies': []}}]
    b = await p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
    ctx = await b.new_context(viewport={'width': W, 'height': H}, device_scale_factor=3.3, is_mobile=True, has_touch=True, color_scheme=theme, locale='en-US')
    await ctx.add_init_script(MOCK); await ctx.add_init_script(SEED)
    # Mark's state: AEW was given Wrestling (one category) before build 696
    await ctx.add_init_script("try{ localStorage.setItem('radioPlayerTheme', '%s'); localStorage.setItem('radioPlayerLtvAuto', '0'); localStorage.setItem('radioPlayerLiveChannels', %s); localStorage.setItem('radioPlayerChannelCats', JSON.stringify({'amplify-live:aewch': 'Wrestling'})); }catch(e){}" % (theme, json.dumps(json.dumps(D))))
    pg = await ctx.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
    await pg.route('**/*', route)
    await pg.goto('http://127.0.0.1:%d/index.html' % PORT); await pg.wait_for_timeout(2000)
    await pg.evaluate("() => document.getElementById('noticeOverlay').classList.remove('open')")
    await pg.evaluate(EV("archiveFilesAll()['aew-dyn'] = { t: Date.now(), units: [{ id: 'aew-dyn/a.mp4', url: 'https://archive.org/download/aew-dyn/a.mp4', dur: 6180, title: 'AEW', video: true }] }; liveChCache = null; 1"))
    U = 'amplify-live:aewch'
    cats = await pg.evaluate(EV("chCategories({ url: '%s', name: 'AEW' })" % U))
    check(cats == ['My Channels', 'Wrestling'], '%s AEW (Wrestling set before 696): My Channels and Wrestling %s' % (T, cats))
    await pg.evaluate(EV("openLiveChEditor('aewch'); 1")); await pg.wait_for_timeout(1200)
    ed = await pg.evaluate("() => Array.from(document.querySelectorAll('#liveChCats .home-tab.active')).map(function(b){ return b.textContent.trim(); })")
    check(ed == ['My Channels', 'Wrestling'], '%s Edit Channel shows both highlighted %s' % (T, ed))
    await pg.evaluate("() => document.getElementById('liveChCats').scrollIntoView({block:'center'})"); await pg.wait_for_timeout(300)
    await pg.screenshot(path=SHOTS + '/multicat697-editor-%s.png' % theme)
    # Seinfeld channel: its shows' Plex genres (Comedy) give the category
    sf = await pg.evaluate(EV("""(function(){ var o = liveChSources; liveChSources = function(def, lib){ if(def && def.id === 'seinfeld') return { shows: [{ key: 'seinfeld', title: 'Seinfeld', genres: ['Comedy', 'Sitcom'] }], movies: [], mvs: [], archive: [] }; return o(def, lib); };
      chCatMemo = {}; var r = chCategories({ url: 'amplify-live:seinfeld', name: 'Seinfeld' }); liveChSources = o; return r; })()"""))
    check(sf == ['My Channels', 'Comedy'], '%s a channel of shows takes its Plex genre: Seinfeld -> My Channels, Comedy %s' % (T, sf))
    check(not errs, '%s no page errors %s' % (T, errs[:3]))
    await b.close()
async def main():
    async with async_playwright() as p:
        await run(p, 'dark')
        await run(p, 'light')
    print('ALL PASSED' if not fails else 'FAILS %d' % len(fails))
asyncio.run(main())
