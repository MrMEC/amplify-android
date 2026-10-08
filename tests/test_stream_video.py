"""Live stream video on Now Playing (uses the podcast video feature from build 45).

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
   if(k==='videoTracks') return function(){ return Promise.resolve({textOff:false, audio:[], text:[{group:3,track:0,label:'CC1',selected:true}]}); };
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

async def state(pg):
    return await pg.evaluate("""(()=>{var w=document.getElementById('npVideoWrap'),v=document.getElementById('npVideo'),
      t=document.getElementById('npVideoToggle'),r=v.getBoundingClientRect();
      return {wrapHidden:w.hidden,toggleHidden:t.hidden,label:document.getElementById('npVideoToggleLabel').textContent,
        full:document.body.classList.contains('np-video-full'),x:r.left,y:r.top,w:r.width,h:r.height,view:window.__view||null};})()""")

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
    st = await state(pg)
    check(st['wrapHidden'] and st['toggleHidden'] and not (st['view'] or {}).get('show'), f'[{tag}] no video UI before the stream reports a picture')

    await pg.evaluate("(id)=>window.__emit('video',{id:id,hasVideo:true,width:1280,height:720})", cur)
    await pg.wait_for_timeout(500)
    st = await state(pg); v = st['view'] or {}
    check(not st['wrapHidden'] and not st['toggleHidden'] and st['label'] == 'Turn Off Video', f'[{tag}] video comes on by itself, pill says Turn Off Video ({st["label"]})')
    check(v.get('show') and abs(v['x']-st['x'])<1 and abs(v['y']-st['y'])<1 and abs(v['width']-st['w'])<1 and abs(v['height']-st['h'])<1, f'[{tag}] native picture placed on the video box {v}')
    back = await pg.evaluate("(()=>{var b=document.querySelector('.np-float, #npBackBtn');if(!b)return null;var r=b.getBoundingClientRect();return {b:r.bottom};})()")
    name = await pg.evaluate("document.getElementById('npName').getBoundingClientRect().top")
    check(st['y'] + st['h'] <= name, f'[{tag}] picture ends above the title ({st["y"]+st["h"]:.0f} <= {name:.0f})')
    await pg.evaluate(STANDIN); await pg.screenshot(path=f'{SHOTS}/{tag}-np-video.png')

    # The ⋮ menu: hides the picture only if it overlaps it.
    await pg.evaluate("document.getElementById('npMenuBtn').click()")
    await pg.wait_for_timeout(300)
    mr = await pg.evaluate("(()=>{var r=document.getElementById('npMenu').getBoundingClientRect();return {t:r.top,b:r.bottom,l:r.left,r:r.right};})()")
    vm = await pg.evaluate('window.__view')
    overlaps = mr['t'] < st['y'] + st['h'] and mr['b'] > st['y'] and mr['r'] > st['x'] and mr['l'] < st['x'] + st['w']
    check((not vm.get('show')) if overlaps else vm.get('show'), f'[{tag}] menu {"over" if overlaps else "clear of"} the picture -> shown={vm.get("show")}')
    await pg.evaluate(STANDIN); await pg.screenshot(path=f'{SHOTS}/{tag}-np-menu.png')
    await pg.keyboard.press('Escape'); await pg.wait_for_timeout(300)
    if (await pg.evaluate("getComputedStyle(document.getElementById('npMenu')).display")) != 'none':
        await pg.evaluate("document.getElementById('npMenuBtn').click()"); await pg.wait_for_timeout(300)
    check((await pg.evaluate('window.__view')).get('show'), f'[{tag}] picture back once the menu closes')

    # A tap on the picture (native) -> full screen; the picture covers the whole screen.
    await pg.evaluate("(id)=>window.__emit('videotap',{id:id})", cur)
    await pg.wait_for_timeout(400)
    st = await state(pg); v = st['view'] or {}
    check(st['full'] and v.get('show') and v['width'] >= w - 1 and v['height'] >= h - 1, f'[{tag}] tap -> full screen, picture fills the screen {v}')
    ui = await pg.evaluate("window.__calls.filter(function(c){return c[0]==='setVideoUi';}).slice(-1)[0]")
    check(ui and ui[1].get('fullscreen'), f'[{tag}] system bars hidden via setVideoUi {ui}')
    await pg.evaluate(STANDIN); await pg.screenshot(path=f'{SHOTS}/{tag}-full.png')
    await pg.evaluate("(id)=>window.__emit('videotap',{id:id})", cur)
    await pg.wait_for_timeout(400)
    st = await state(pg)
    check(not st['full'] and st['view'].get('show') and st['view']['height'] < h / 2, f'[{tag}] tap again -> back to the box')

    # Pill: off by hand, then on.
    await pg.evaluate("document.getElementById('npVideoToggle').click()")
    await pg.wait_for_timeout(300)
    st = await state(pg)
    check(st['wrapHidden'] and not st['view'].get('show') and st['label'] == 'Turn On Video' and not st['toggleHidden'], f'[{tag}] Turn Off Video hides it, pill offers Turn On Video')
    await pg.evaluate("(id)=>window.__emit('video',{id:id,hasVideo:true,width:1280,height:720})", cur)
    await pg.wait_for_timeout(300)
    check((await state(pg))['wrapHidden'], f'[{tag}] stays off after turning it off by hand')
    await pg.evaluate("document.getElementById('npVideoToggle').click()")
    await pg.wait_for_timeout(300)
    check((await state(pg))['view'].get('show'), f'[{tag}] Turn On Video brings it back')

    # Closing Now Playing hides the picture; reopening shows it again.
    await pg.evaluate("document.getElementById('npBackBtn').click()")
    await pg.wait_for_timeout(900)
    # Build 155: the picture carries on in the floating window instead.
    mini = await pg.evaluate("""(()=>{var m=document.getElementById('videoMini'),b=document.getElementById('videoMiniBox').getBoundingClientRect();
      return {hidden:m.hidden, x:Math.round(b.left), y:Math.round(b.top), w:Math.round(b.width), h:Math.round(b.height), view:window.__view, calls:window.__calls.filter(function(c){return c[0]==='pause'||c[0]==='stop';}).length};})()""")
    v = mini['view'] or {}
    check(not mini['hidden'] and v.get('show') and v.get('x') == mini['x'] and v.get('y') == mini['y'] and v.get('width') == mini['w'],
          f'[{tag}] closing Now Playing moves the picture into the floating window {mini}')
    await pg.evaluate(STANDIN); await pg.screenshot(path=f'{SHOTS}/stream-video-mini-{tag}.png')
    # the app reports a finger dragging its picture (build 161): the window follows, the picture with it
    m0 = await pg.evaluate("(()=>{var r=document.getElementById('videoMini').getBoundingClientRect(); return [r.left, r.top];})()")
    await pg.evaluate("window.__emit('videodrag',{phase:'start',dx:0,dy:0})")
    for i in range(1, 6):
        await pg.evaluate("(d)=>window.__emit('videodrag',{phase:'move',dx:-d*10,dy:-d*30})", i); await pg.wait_for_timeout(30)
    await pg.evaluate("window.__emit('videodrag',{phase:'end',dx:-50,dy:-150})"); await pg.wait_for_timeout(300)
    m1 = await pg.evaluate("(()=>{var r=document.getElementById('videoMini').getBoundingClientRect(), b=document.getElementById('videoMiniBox').getBoundingClientRect(); return [r.left, r.top, Math.round(b.left), Math.round(b.top), window.__view];})()")
    check(abs(m1[0] - (m0[0] - 50)) <= 2 and abs(m1[1] - (m0[1] - 150)) <= 2 and m1[4].get('x') == m1[2] and m1[4].get('y') == m1[3],
          f'[{tag}] dragging the app-drawn picture moves the window and the picture with it {m0} -> {m1}')
    await pg.evaluate("document.getElementById('videoMiniBox').click()")
    await pg.wait_for_timeout(900)
    back = await state(pg)
    check(back['view'].get('show') and abs(back['view']['y'] - round(back['y'])) <= 1 and await pg.evaluate("document.getElementById('videoMini').hidden"),
          f'[{tag}] tapping it reopens Now Playing with the picture back in place {back}')

    # Captions (build 162): the menu offers them for a channel; off is kept for the next channel.
    cc = await pg.evaluate("[getComputedStyle(document.getElementById('npTracksBtn')).display, document.getElementById('npTracksBtn').textContent.trim()]")
    check(cc[0] != 'none' and cc[1] == 'Captions', f'[{tag}] a channel has a Captions item in its menu {cc}')
    await pg.evaluate("document.getElementById('npTracksBtn').click()"); await pg.wait_for_timeout(400)
    opts = await pg.evaluate("[document.querySelector('.v-tracks-menu .v-menu-head').textContent, Array.from(document.querySelectorAll('.v-tracks-menu .np-menu-item')).map(function(b){return b.textContent.trim()+(b.classList.contains('on')?'*':'');})]")
    check(opts[0] == 'Captions' and opts[1] == ['Off', 'On*'], f'[{tag}] Captions: Off / On (on now) {opts}')
    await pg.evaluate("document.querySelectorAll('.v-tracks-menu .np-menu-item')[0].click()"); await pg.wait_for_timeout(300)
    sel = await pg.evaluate("[window.__calls.filter(function(c){return c[0]==='selectVideoTrack';}).slice(-1)[0], localStorage.getItem('radioPlayerChannelCaptionsOff')]")
    check(sel[0] and sel[0][1].get('off') is True and sel[1] == 'true', f'[{tag}] Off turns them off and is remembered {sel}')

    # Another channel: video resets, then comes on for the new one when it reports a picture.
    await paste(pg, 'http://iptv.example/live/channel2.m3u8')
    await pg.wait_for_timeout(400)
    la = await pg.evaluate("window.__calls.filter(function(c){return c[0]==='load';}).slice(-1)[0][1]")
    check(la.get('textOff') is True, f'[{tag}] the next channel starts with captions off {la}')
    await pg.wait_for_timeout(600)
    cur2 = await pg.evaluate('window.__cur')
    await pg.evaluate("document.getElementById('playerNowTrigger').click()")
    await pg.wait_for_timeout(900)
    st = await state(pg)
    check(cur2 != cur and st['wrapHidden'] and not st['view'].get('show'), f'[{tag}] new channel starts without the old picture')
    await pg.evaluate("(id)=>window.__emit('video',{id:id,hasVideo:true,width:1920,height:1080})", cur2)
    await pg.wait_for_timeout(500)
    check((await state(pg))['view'].get('show'), f'[{tag}] new channel shows its picture')
    await pg.evaluate("(id)=>window.__emit('video',{id:id,hasVideo:false})", cur2)
    await pg.wait_for_timeout(400)
    st = await state(pg)
    check(st['wrapHidden'] and st['toggleHidden'] and not st['view'].get('show'), f'[{tag}] picture gone -> no video UI')
    check(not errs, f'[{tag}] no page errors {errs[:3]}')
    await ctx.close()

async def browser_mode(b):
    ctx = await b.new_context(viewport={'width': 390, 'height': 844}, device_scale_factor=2, is_mobile=True, has_touch=True)
    pg = await ctx.new_page()
    errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
    await pg.goto(BASE + 'index.html'); await pg.wait_for_timeout(2500)
    await paste(pg, BASE + 'audio.webm')
    await pg.wait_for_timeout(2000)
    await pg.evaluate("document.getElementById('playerNowTrigger').click()")
    await pg.wait_for_timeout(1200)
    st = await pg.evaluate("(()=>{var a=document.getElementById('audio');return {paused:a.paused,t:a.currentTime,wrap:document.getElementById('npVideoWrap').hidden};})()")
    check(not st['paused'] and st['t'] > 0 and st['wrap'], f'[browser] streams play as before, no video UI {st}')
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
