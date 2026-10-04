"""Search results mark stations that carry video with a camera to the right of the name.

Directory codecs ("AAC,H.264") mark a station; so does the app having found video in it.
Run: python3 tests/test_station_video_icon.py  (screenshots in /tmp/claude-0/t/shots)
"""
import asyncio, json, os, shutil, threading, http.server, functools
from playwright.async_api import async_playwright
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = '/tmp/claude-0/t/srv-icon'; SHOTS = '/tmp/claude-0/t/shots'
os.makedirs(ROOT, exist_ok=True); os.makedirs(SHOTS, exist_ok=True)
shutil.copy(os.path.join(HERE, '..', 'www', 'index.html'), ROOT)
H = functools.partial(http.server.SimpleHTTPRequestHandler, directory=ROOT); H.log_message = lambda *a: None
srv = http.server.ThreadingHTTPServer(('127.0.0.1', 8773), H); threading.Thread(target=srv.serve_forever, daemon=True).start()

def st(n, codec, uuid, name=None):
    return {'name': name or n, 'url_resolved': 'http://s/' + uuid, 'stationuuid': uuid, 'favicon': '', 'tags': 'news', 'codec': codec, 'bitrate': 0, 'country': 'US'}
RESULTS = [st('News 24 TV', 'AAC,H.264', 'v1'), st('Classic Rock FM', 'MP3', 'a1'),
           st('Music Video Channel With A Very Long Name Indeed', 'AAC+,H.265', 'v2'),
           st('Jazz Radio', 'AAC+', 'a2'), st('Sports HD', 'UNKNOWN', 'l1'), st('Talk', 'OGG', 'a3')]
MOCK = """
(function(){
 window.__L={}; window.__emit=function(t,ev){ (window.__L[t]||[]).forEach(function(f){ f(ev); }); };
 var P=new Proxy({}, {get:function(t,k){
   if(k==='then') return undefined;
   if(k==='addListener') return function(n,f){ (window.__L[n]=window.__L[n]||[]).push(f); return Promise.resolve({remove:function(){}}); };
   if(k==='load') return function(a){ window.__cur=a.id; setTimeout(function(){ window.__emit('state',{id:a.id,state:'ready',isPlaying:true,playWhenReady:true,position:0,duration:-1,live:true}); },50); return Promise.resolve({}); };
   if(k==='videoState') return function(){ return Promise.resolve({id:null,hasVideo:false}); };
   return function(){ return Promise.resolve({}); };
 }});
 window.Capacitor={isNativePlatform:function(){return true;},getPlatform:function(){return 'android';},Plugins:{AmplifyPlayer:P},convertFileSrc:function(u){return u;}};
})();
"""
fails = 0
def check(ok, msg):
    global fails
    print(('PASS ' if ok else 'FAIL ') + msg); fails += 0 if ok else 1

async def marks(pg):
    return await pg.evaluate("""Array.prototype.map.call(document.querySelectorAll('#stationsGrid .tile'), function(t){
      var n=t.querySelector('.tile-name'), v=t.querySelector('.tile-video');
      var r=n.getBoundingClientRect(), a=t.querySelector('.tile-art').getBoundingClientRect(), vr=v&&v.getBoundingClientRect();
      return {name:n.textContent, video:!!v, right: vr ? vr.left >= r.right - 1 : null, below: vr ? vr.top >= a.bottom : null,
              level: vr ? Math.abs(vr.top - r.top) < 8 : null, inTile: vr ? vr.right <= t.getBoundingClientRect().right + 1 : null};
    })""")

async def run(b, w, h, tag):
    ctx = await b.new_context(viewport={'width': w, 'height': h}, device_scale_factor=2, is_mobile=w < 700, has_touch=w < 700)
    pg = await ctx.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
    await pg.route('**/*radio-browser*/**', lambda r: r.fulfill(status=200, content_type='application/json', body=json.dumps(RESULTS)))
    await pg.add_init_script(MOCK)
    await pg.goto('http://127.0.0.1:8773/index.html'); await pg.wait_for_timeout(2500)
    await pg.evaluate("(()=>{var i=document.getElementById('searchInput');i.value='news';document.getElementById('searchBtn').click();})()")
    await pg.wait_for_timeout(1500)
    # Top Results leads since build 117; the video marks are on the Stations tab's tiles.
    await pg.evaluate("Array.from(document.querySelectorAll('#searchTabs .home-tab')).filter(function(b){ return /^Stations/.test(b.textContent); })[0].click()")
    await pg.wait_for_timeout(400)
    m = await marks(pg)
    byname = {x['name']: x for x in m}
    check(len(m) == 6, f'[{tag}] six results ({len(m)})')
    check(byname.get('News 24 TV', {}).get('video') and byname['Music Video Channel With A Very Long Name Indeed']['video'], f'[{tag}] H.264 / H.265 stations marked')
    check(not any(byname[n]['video'] for n in ('Classic Rock FM', 'Jazz Radio', 'Sports HD', 'Talk')), f'[{tag}] audio stations not marked')
    marked = [x for x in m if x['video']]
    check(all(x['right'] and x['below'] and x['level'] and x['inTile'] for x in marked), f'[{tag}] icon below the art, right of the name, level with it, inside the tile {marked}')
    await pg.screenshot(path=f'{SHOTS}/icon-{tag}.png')
    # Learned: play 'Sports HD' (codec UNKNOWN), native reports video -> marked from then on.
    await pg.evaluate("Array.prototype.find.call(document.querySelectorAll('#stationsGrid .tile'),function(t){return t.querySelector('.tile-name').textContent==='Sports HD';}).click()")
    await pg.wait_for_timeout(600)
    cur = await pg.evaluate('window.__cur')
    await pg.evaluate("(id)=>window.__emit('video',{id:id,hasVideo:true,width:1280,height:720})", cur)
    await pg.wait_for_timeout(300)
    check({x['name']: x for x in await marks(pg)}['Sports HD']['video'], f'[{tag}] station found to have video is marked right away')
    await pg.reload(); await pg.wait_for_timeout(2500)
    await pg.evaluate("(()=>{var i=document.getElementById('searchInput');i.value='news';document.getElementById('searchBtn').click();})()")
    await pg.wait_for_timeout(1500)
    check({x['name']: x for x in await marks(pg)}['Sports HD']['video'], f'[{tag}] ...and still marked after a restart')
    check(not errs, f'[{tag}] no page errors {errs[:3]}')
    await ctx.close()

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
        await run(b, 390, 844, 'phone'); await run(b, 1400, 900, 'desktop')
        await b.close()
    print('ALL PASSED' if not fails else f'FAILED {fails}')
asyncio.run(main())
