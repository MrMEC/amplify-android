"""Build 336: the tour's welcome voice (www/tour-welcome.wav). It plays by itself, in the background,
when the tour opens on its first screen: no Now Playing screen, nothing in the app's player; it
stops when the tour moves on or closes; it does not play from a later screen; and where the browser
won't start sound without a touch, the first touch on the tour starts it.
Run: python3 tests/test_tour_voice.py (screenshots in /tmp/claude-0/t/shots)"""
import asyncio, os, json, shutil, threading, http.server, functools
from playwright.async_api import async_playwright
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = '/tmp/claude-0/t/srv-voice'; SHOTS = '/tmp/claude-0/t/shots'
shutil.rmtree(ROOT, ignore_errors=True); os.makedirs(ROOT); os.makedirs(SHOTS, exist_ok=True)
for f in ('index.html', 'tour-welcome.wav'): shutil.copy(os.path.join(HERE, '..', 'www', f), ROOT)
class Q(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a): pass
srv = http.server.ThreadingHTTPServer(('127.0.0.1', 8834), functools.partial(Q, directory=ROOT)); threading.Thread(target=srv.serve_forever, daemon=True).start()
fails = 0
def check(ok, msg):
    global fails
    print(('PASS ' if ok else 'FAIL ') + msg); fails += 0 if ok else 1
INIT = """localStorage.setItem('amplifyTourTest','1'); window.__auds=[]; var A=window.Audio;
window.Audio=function(s){ var a=new A(s); window.__auds.push(a); return a; }; window.Audio.prototype=A.prototype;"""
async def route(r):
    u = r.request.url
    if u.startswith('http://127.0.0.1'): return await r.continue_()
    if 'radio-browser' in u: return await r.fulfill(status=200, content_type='application/json', headers={'access-control-allow-origin': '*'}, body='[]')
    return await r.abort()
STATE = """(()=>{ var a=(window.__auds||[]).filter(function(x){return x.getAttribute('src')!==null;}); var l=window.__auds[window.__auds.length-1];
  var np=document.getElementById('nowPlayingScreen'), pb=document.getElementById('audio');
  return { n:(window.__auds||[]).length, playing: !!l && !l.paused && !l.ended && !!l.getAttribute('src'), src: l && l.getAttribute('src'), t: l ? l.currentTime : 0,
    step: window.__amplifyTour.step(), tourOpen: document.getElementById('tourOverlay').classList.contains('open'),
    npShown: !!np && getComputedStyle(np).display !== 'none', mainPaused: pb.paused, mainSrc: pb.getAttribute('src') }; })()"""
async def run(p, args, label):
    b = await p.chromium.launch(executable_path='/opt/pw-browsers/chromium', args=args)
    ctx = await b.new_context(viewport={'width': 390, 'height': 844}, device_scale_factor=2, is_mobile=True, has_touch=True, color_scheme='dark')
    await ctx.add_init_script(INIT)
    pg = await ctx.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e))); await pg.route('**/*', route)
    await pg.goto('http://127.0.0.1:8834/index.html'); await pg.wait_for_timeout(3500)
    return b, pg, errs
async def main():
    async with async_playwright() as p:
        # --- sound allowed: plays by itself on screen 1
        b, pg, errs = await run(p, ['--autoplay-policy=no-user-gesture-required'], 'auto')
        s = await pg.evaluate(STATE)
        check(s['tourOpen'] and s['step'] == 0, f'tour opened by itself on screen 1 {s["step"]}')
        check(s['playing'] and (s['src'] or '').startswith('blob:'), f'voice plays by itself {s}')
        check(not s['npShown'] and s['mainPaused'] and not s['mainSrc'], 'no Now Playing screen; the app\'s own player untouched')
        check(await pg.evaluate('window.__tourVoice.status()') == 'playing', 'status reads playing (Settings > Check storage)')
        await pg.screenshot(path=SHOTS + '/voice_screen1.png')
        await pg.wait_for_timeout(1000)
        s2 = await pg.evaluate(STATE); check(s2['t'] > s['t'], 'it keeps playing in the background')
        await pg.evaluate("document.getElementById('tourNext').click()"); await pg.wait_for_timeout(500)
        s = await pg.evaluate(STATE); check(s['step'] == 1 and not s['playing'], 'Start (next screen) stops the voice')
        await pg.evaluate("document.getElementById('tourBack').click()"); await pg.wait_for_timeout(500)
        s = await pg.evaluate(STATE); check(s['step'] == 0 and not s['playing'], 'going back does not replay it')
        await pg.evaluate("window.__amplifyTour.close(false)"); await pg.evaluate("window.__amplifyTour.open(0)"); await pg.wait_for_timeout(800)
        s = await pg.evaluate(STATE); check(s['playing'], 'reopening the tour on screen 1 plays it again')
        await pg.evaluate("window.__amplifyTour.close(false)"); await pg.wait_for_timeout(300)
        s = await pg.evaluate(STATE); check(not s['playing'] and not s['tourOpen'], 'closing the tour stops it')
        n = s['n']; await pg.evaluate("window.__amplifyTour.open(2)"); await pg.wait_for_timeout(500)
        s = await pg.evaluate(STATE); check(s['n'] == n and not s['playing'], 'opening on a later screen does not play it')
        await pg.evaluate("window.__amplifyTour.close(false); window.__amplifyTour.open(0)"); await pg.wait_for_timeout(9200)
        s = await pg.evaluate("(()=>{var l=window.__auds[window.__auds.length-1]; return {gone:!l.getAttribute('src'), paused:l.paused};})()")
        check(s['paused'], f'it ends by itself after its 8 seconds (1.2 s lead-in + 6.8 s voice) {s}')
        check(len(errs) == 0, f'no page errors {errs}')
        await b.close()
        # --- sound needs a touch: screen 1 waits for the first touch
        b, pg, errs = await run(p, [], 'gesture')
        s = await pg.evaluate(STATE)
        if s['playing']:
            print('NOTE autoplay allowed in this browser without a touch; touch fallback not exercised')
        else:
            await pg.evaluate("(()=>{var o=document.getElementById('tourOverlay'); o.dispatchEvent(new PointerEvent('pointerdown',{bubbles:true}));})()")
            await pg.wait_for_timeout(300)
            await pg.touchscreen.tap(200, 700); await pg.wait_for_timeout(800)
            s = await pg.evaluate(STATE)
            check(s['playing'], f'blocked at first: the first touch on the tour starts it {s}')
        await b.close()
        # --- on the phone: played by the app's own voice player; the web player stays unused
        for mode in ('ok', 'fail'):
            b = await p.chromium.launch(executable_path='/opt/pw-browsers/chromium', args=['--autoplay-policy=no-user-gesture-required'])
            ctx = await b.new_context(viewport={'width': 390, 'height': 844}, device_scale_factor=2, is_mobile=True, has_touch=True, color_scheme='dark')
            await ctx.add_init_script(INIT)
            await ctx.add_init_script("""(function(){ window.__nv=[]; window.__L={};
              var P=new Proxy({}, {get:function(t,k){ if(k==='then') return undefined;
                if(k==='addListener') return function(n,f){ (window.__L[n]=window.__L[n]||[]).push(f); return Promise.resolve({remove:function(){}}); };
                if(k==='playWelcomeVoice') return function(){ window.__nv.push('play'); return %s; };
                if(k==='stopWelcomeVoice') return function(){ window.__nv.push('stop'); return Promise.resolve({}); };
                return function(){ return Promise.resolve({}); }; }});
              window.Capacitor={isNativePlatform:function(){return true;},getPlatform:function(){return 'android';},Plugins:{AmplifyPlayer:P},convertFileSrc:function(u){return u;}}; })();""" % ("Promise.resolve({status:'playing'})" if mode == 'ok' else "Promise.reject(new Error('no sound'))"))
            pg = await ctx.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e))); await pg.route('**/*', route)
            await pg.goto('http://127.0.0.1:8834/index.html'); await pg.wait_for_timeout(3500)
            nv = await pg.evaluate('window.__nv'); st = await pg.evaluate('window.__tourVoice.status()'); s = await pg.evaluate(STATE)
            if mode == 'ok':
                check(nv[:1] == ['play'] and s['n'] == 0 and st == 'playing (phone player)' and not s['npShown'], f'phone: the app plays the voice, not the web player {nv} {st} audios={s["n"]}')
                await pg.evaluate("document.getElementById('tourNext').click()"); await pg.wait_for_timeout(400)
                check((await pg.evaluate('window.__nv'))[-1] == 'stop', 'phone: Start stops it')
                await pg.evaluate("window.__amplifyTour.close(false); window.__amplifyTour.open(0)"); await pg.wait_for_timeout(400)
                await pg.evaluate("window.__amplifyTour.close(false)"); await pg.wait_for_timeout(300)
                nv = await pg.evaluate('window.__nv'); check(nv[-1] == 'stop' and nv.count('play') == 2, f'phone: reopen plays again, close stops {nv}')
            else:
                check(nv[:1] == ['play'] and s['playing'] and (s['src'] or '').startswith('blob:'), f'phone player failed: falls back to the web player {nv} {st}')
            check(len(errs) == 0, f'no page errors ({mode}) {errs}')
            await b.close()
    print('\n%d failure(s)' % fails); raise SystemExit(1 if fails else 0)
asyncio.run(main())
