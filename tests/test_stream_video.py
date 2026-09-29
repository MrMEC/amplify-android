"""Stream video on Now Playing.

App mode (mocked Capacitor): paste a stream URL, the native player reports video, and the page
must tell the native side where the video box is -- and hide it when Now Playing closes, a
menu covers it, or the stream has no picture.
Browser mode: a real video stream (webm) pasted into search shows its picture in the box.

Run: python3 tests/test_stream_video.py  (needs ffmpeg-made files in /tmp/claude-0/t/vid)
Screenshots go to /tmp/claude-0/t/shots.
"""
import asyncio, json, os, shutil, threading, http.server, functools
from playwright.async_api import async_playwright

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = '/tmp/claude-0/t/srv-video'
SHOTS = '/tmp/claude-0/t/shots'
os.makedirs(ROOT, exist_ok=True); os.makedirs(SHOTS, exist_ok=True)
shutil.copy(os.path.join(HERE, '..', 'www', 'index.html'), ROOT)
for f in ('test.webm', 'audio.webm'):
    shutil.copy('/tmp/claude-0/t/vid/' + f, ROOT)
H = functools.partial(http.server.SimpleHTTPRequestHandler, directory=ROOT)
H.log_message = lambda *a: None
srv = http.server.ThreadingHTTPServer(('127.0.0.1', 8771), H)
threading.Thread(target=srv.serve_forever, daemon=True).start()
BASE = 'http://127.0.0.1:8771/'

MOCK = """
(function(){
 window.__calls=[]; window.__L={};
 function emit(t,ev){ (window.__L[t]||[]).forEach(function(f){ f(ev); }); }
 window.__emit=emit;
 var P=new Proxy({}, {get:function(t,k){
   if(k==='then') return undefined;
   if(k==='addListener') return function(n,f){ (window.__L[n]=window.__L[n]||[]).push(f); return Promise.resolve({remove:function(){}}); };
   if(k==='load') return function(a){ window.__calls.push(['load',a]); window.__cur=a.id;
       setTimeout(function(){ emit('state',{id:a.id,state:'ready',isPlaying:true,playWhenReady:true,position:0,duration:-1,live:true}); },50);
       return Promise.resolve({}); };
   if(k==='setVideoView') return function(a){ window.__calls.push(['view',a]); window.__view=a; return Promise.resolve(); };
   if(k==='videoState') return function(){ return Promise.resolve({id:null,hasVideo:false}); };
   return function(a){ window.__calls.push([k,a]); return Promise.resolve({}); };
 }});
 window.Capacitor={isNativePlatform:function(){return true;},getPlatform:function(){return 'android';},Plugins:{AmplifyPlayer:P},convertFileSrc:function(u){return u;}};
})();
"""

# Draws where the native picture would be, so the screenshot shows the real result.
STANDIN = """
(function(){
  var v=window.__view, d=document.getElementById('__standin');
  if(!d){ d=document.createElement('div'); d.id='__standin'; d.style.cssText='position:fixed;z-index:2147483647;pointer-events:none;background:repeating-linear-gradient(45deg,#2a6,#2a6 12px,#184 12px,#184 24px);color:#fff;font:600 14px sans-serif;display:flex;align-items:center;justify-content:center;'; d.textContent='native video'; document.body.appendChild(d); }
  if(!v || !v.show){ d.style.display='none'; return; }
  d.style.display='flex'; d.style.left=v.x+'px'; d.style.top=v.y+'px'; d.style.width=v.width+'px'; d.style.height=v.height+'px';
})()
"""

def check(ok, msg):
    print(('PASS ' if ok else 'FAIL ') + msg)
    if not ok: check.failed += 1
check.failed = 0

async def paste(pg, url):
    await pg.evaluate("""(u)=>{ var i=document.getElementById('searchInput'); i.value=u;
        document.getElementById('searchBtn').click(); }""", url)

async def app_mode(b, w, h, tag):
    ctx = await b.new_context(viewport={'width': w, 'height': h}, device_scale_factor=2, is_mobile=True, has_touch=True)
    pg = await ctx.new_page()
    errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
    await pg.add_init_script(MOCK)
    await pg.goto(BASE + 'index.html'); await pg.wait_for_timeout(2500)

    await paste(pg, 'http://iptv.example/live/channel1.m3u8')
    await pg.wait_for_timeout(600)
    cur = await pg.evaluate('window.__cur')
    check(bool(cur), f'[{tag}] pasted stream loaded natively')
    await pg.evaluate("document.getElementById('playerNowTrigger').click()")
    await pg.wait_for_timeout(900)
    view = await pg.evaluate('window.__view')
    check(not view or not view.get('show'), f'[{tag}] no video shown before the stream reports a picture')
    hidden = await pg.evaluate("document.getElementById('npVideo').hidden")
    check(hidden, f'[{tag}] video box hidden for a stream without video')

    await pg.evaluate("(id)=>window.__emit('video',{id:id,hasVideo:true,width:1280,height:720,fullscreen:false})", cur)
    await pg.wait_for_timeout(500)
    view = await pg.evaluate('window.__view')
    check(view and view.get('show'), f'[{tag}] native told to show video: {view}')
    box = await pg.evaluate("(()=>{var r=document.getElementById('npVideo').getBoundingClientRect();return {x:r.left,y:r.top,w:r.width,h:r.height};})()")
    back = await pg.evaluate("(()=>{var r=document.getElementById('npBackBtn').getBoundingClientRect();return {b:r.bottom};})()")
    name = await pg.evaluate("(()=>{var r=document.getElementById('npName').getBoundingClientRect();return {t:r.top};})()")
    check(view and abs(view['x']-box['x'])<1 and abs(view['y']-box['y'])<1 and abs(view['width']-box['w'])<1, f'[{tag}] rect matches the box {box}')
    check(box['y'] >= back['b'], f'[{tag}] box starts below the minimize button ({box["y"]:.0f} >= {back["b"]:.0f})')
    check(box['y'] + box['h'] <= name['t'] - 8, f'[{tag}] box ends above the title ({box["y"]+box["h"]:.0f} < {name["t"]:.0f})')
    check(abs(box['w'] / box['h'] - 16/9) < 0.02 or box['w'] < w - 1, f'[{tag}] box keeps the 16:9 shape (or is narrower than the screen)')
    await pg.evaluate(STANDIN)
    await pg.screenshot(path=f'{SHOTS}/{tag}-np-video.png')

    # A menu over the box hides the picture; closing it brings it back.
    await pg.evaluate("document.getElementById('npMenuBtn').click()")
    await pg.wait_for_timeout(300)
    menu_open = await pg.evaluate("getComputedStyle(document.getElementById('npMenu')).display!=='none' && document.getElementById('npMenu').getBoundingClientRect().height>0")
    view_menu = await pg.evaluate('window.__view')
    mr = await pg.evaluate("(()=>{var r=document.getElementById('npMenu').getBoundingClientRect();return {t:r.top,b:r.bottom};})()")
    overlaps = mr['t'] < box['y'] + box['h'] and mr['b'] > box['y']
    if overlaps:
        check(not view_menu.get('show'), f'[{tag}] menu covering the box hides the picture')
    else:
        check(view_menu.get('show'), f'[{tag}] menu clear of the box keeps the picture (menu {mr})')
    await pg.evaluate(STANDIN)
    await pg.screenshot(path=f'{SHOTS}/{tag}-np-menu.png')
    await pg.mouse.click(5, h - 5)
    await pg.keyboard.press('Escape')
    await pg.wait_for_timeout(300)

    # Scrolling moves the picture with the box.
    await pg.evaluate("document.getElementById('nowPlayingScreen').scrollTop=60")
    await pg.wait_for_timeout(300)
    v2 = await pg.evaluate('window.__view')
    b2 = await pg.evaluate("document.getElementById('npVideo').getBoundingClientRect().top")
    check(v2.get('show') is False or abs(v2['y'] - b2) < 1, f'[{tag}] picture follows scrolling (y {v2.get("y")} vs box {b2:.0f})')
    await pg.evaluate("document.getElementById('nowPlayingScreen').scrollTop=0")
    await pg.wait_for_timeout(300)

    # Closing Now Playing hides it.
    await pg.evaluate("document.getElementById('npBackBtn').click()")
    await pg.wait_for_timeout(900)
    v3 = await pg.evaluate('window.__view')
    check(not v3.get('show'), f'[{tag}] closing Now Playing hides the picture')
    await pg.evaluate(STANDIN)
    await pg.screenshot(path=f'{SHOTS}/{tag}-closed.png')

    # Reopen; then the stream loses video -> hidden, box gone.
    await pg.evaluate("document.getElementById('playerNowTrigger').click()")
    await pg.wait_for_timeout(900)
    check((await pg.evaluate('window.__view')).get('show'), f'[{tag}] reopening shows it again')
    await pg.evaluate("(id)=>window.__emit('video',{id:id,hasVideo:false,width:0,height:0})", cur)
    await pg.wait_for_timeout(400)
    check(not (await pg.evaluate('window.__view')).get('show') and await pg.evaluate("document.getElementById('npVideo').hidden"), f'[{tag}] no picture -> box hidden')
    check(not errs, f'[{tag}] no page errors {errs[:3]}')
    await ctx.close()

async def browser_mode(b):
    ctx = await b.new_context(viewport={'width': 390, 'height': 844}, device_scale_factor=2, is_mobile=True, has_touch=True)
    pg = await ctx.new_page()
    errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
    await pg.goto(BASE + 'index.html'); await pg.wait_for_timeout(2500)
    await paste(pg, BASE + 'test.webm')
    await pg.wait_for_timeout(2500)
    await pg.evaluate("document.getElementById('playerNowTrigger').click()")
    await pg.wait_for_timeout(1500)
    st = await pg.evaluate("(()=>{var a=document.getElementById('audio');return {vw:a.videoWidth,inBox:a.parentNode&&a.parentNode.id,paused:a.paused,t:a.currentTime,hidden:document.getElementById('npVideo').hidden};})()")
    check(st['vw'] == 640 and st['inBox'] == 'npVideo' and not st['hidden'], f'[browser] video plays in the box {st}')
    await pg.screenshot(path=f'{SHOTS}/browser-np-video.png')
    await pg.evaluate("document.getElementById('npBackBtn').click()")
    await pg.wait_for_timeout(800)
    st2 = await pg.evaluate("(()=>{var a=document.getElementById('audio');return {parent:a.parentNode===document.body,paused:a.paused,t:a.currentTime};})()")
    check(st2['parent'] and not st2['paused'], f'[browser] leaving Now Playing keeps playing, element back out of the layout {st2}')
    await paste(pg, BASE + 'audio.webm')
    await pg.wait_for_timeout(2000)
    await pg.evaluate("document.getElementById('playerNowTrigger').click()")
    await pg.wait_for_timeout(1200)
    st3 = await pg.evaluate("(()=>{var a=document.getElementById('audio');return {vw:a.videoWidth,parent:a.parentNode===document.body,paused:a.paused,hidden:document.getElementById('npVideo').hidden};})()")
    check(st3['vw'] == 0 and st3['parent'] and st3['hidden'] and not st3['paused'], f'[browser] audio-only stream: no box, plays as before {st3}')
    await pg.screenshot(path=f'{SHOTS}/browser-np-audio.png')
    check(not errs, f'[browser] no page errors {errs[:3]}')
    await ctx.close()

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path='/opt/pw-browsers/chromium',
                                    args=['--autoplay-policy=no-user-gesture-required'])
        await app_mode(b, 390, 844, 'phone')
        await app_mode(b, 360, 740, 'small')
        await browser_mode(b)
        await b.close()
    print('FAILED' if check.failed else 'ALL PASSED', check.failed)

asyncio.run(main())
