"""Build 699 (Mark): starting Amplify showed the video view (black box) for a radio station.
A station's picture now comes on only once a picture of real size arrives; TV channels as before.
Item ids are unique per launch. Run: python3 tests/test_stream_video_wait.py"""
import sys as _nsys, os as _nos; _nsys.path.insert(0, _nos.path.dirname(_nos.path.abspath(__file__))); from notice_auto import AUTO_NOTICE
import asyncio, os, json, threading, http.server, functools, shutil
from playwright.async_api import async_playwright
PORT = 8898
root = '/tmp/claude-0/t/srv_svw'; shots = '/tmp/claude-0/t/shots'; os.makedirs(shots, exist_ok=True)
shutil.rmtree(root, ignore_errors=True); os.makedirs(root)
HOOK = "window.__t = { ev: function(js){ return eval(js); } };\n"
_src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'www', 'index.html')).read()
_mark = '  var coverFlow = null;\n'; assert _src.count(_mark) == 1
open(root + '/index.html', 'w').write(_src.replace(_mark, _mark + HOOK))
class Q(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a): pass
srv = http.server.ThreadingHTTPServer(('127.0.0.1', PORT), functools.partial(Q, directory=root))
threading.Thread(target=srv.serve_forever, daemon=True).start()
ST = {'name': 'Christmas FM Non-stop!', 'url': 'http://radio.example/xmas', 'urlToResolve': 'http://radio.example/xmas', 'stationuuid': 'xmas-1', 'favicon': ''}
MOCK = """(function(){ var listeners = {}; window.__L = listeners;
 var impl = { addListener: function(n, f){ (listeners[n] = listeners[n] || []).push(f); return Promise.resolve({remove:function(){}}); },
   videoState: function(){ return Promise.resolve({ id: 'm1', hasVideo: true, width: 0, height: 0 }); } };
 var P = new Proxy({}, {get:function(t,k){ if(k==='then') return undefined; if(k==='setCarLibraryPart') return undefined; if(impl[k]) return impl[k]; return function(){ return Promise.resolve({}); }; }});
 window.Capacitor = { isNativePlatform:function(){return true;}, getPlatform:function(){return 'android';}, registerPlugin:function(){ return P; }, Plugins:{AmplifyPlayer:P}, convertFileSrc:function(u){return u;} };
 try{ localStorage.setItem('radioPlayerRecent', %s); }catch(e){}
})();""" % json.dumps(json.dumps([ST]))
fails = []
def check(c, m):
    print(('PASS ' if c else 'FAIL ') + m)
    if not c: fails.append(m)
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
        ctx = await b.new_context(viewport={'width': 327, 'height': 700}, device_scale_factor=3.3, is_mobile=True, has_touch=True, color_scheme='dark')
        await ctx.add_init_script(MOCK); await ctx.add_init_script(AUTO_NOTICE)
        await ctx.add_init_script("try{ localStorage.setItem('radioPlayerTourDone','1'); }catch(e){}")
        pg = await ctx.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.route('**/*', lambda r: r.continue_() if '127.0.0.1' in r.request.url else r.fulfill(status=200, content_type='application/json', body='[]') if '/json/' in r.request.url else r.abort())
        await pg.goto(f'http://127.0.0.1:{PORT}/index.html'); await pg.wait_for_timeout(2500)
        await pg.evaluate("__t.ev(\"playStation(recentStations[0])\")"); await pg.wait_for_timeout(800)
        st = await pg.evaluate("__t.ev('JSON.stringify({id: audio._id, name: currentStation && currentStation.name})')")
        print(st); st = json.loads(st)
        check(st['id'] and st['id'] != 'm1' and st['id'].startswith('m') and '.' in st['id'], f'item id is unique to this launch ({st["id"]})')
        await pg.evaluate("__t.ev(\"openNowPlaying(currentStation)\")"); await pg.wait_for_timeout(800)
        on = lambda: pg.evaluate("document.getElementById('nowPlayingScreen').classList.contains('np-video-on')")
        fire = lambda w, h: pg.evaluate("([w,h])=>{ (window.__L.video||[]).forEach(f=>f({ id: __t.ev('audio._id'), hasVideo: true, width: w, height: h })); }", [w, h])
        stale = await pg.evaluate("()=>{ (window.__L.video||[]).forEach(f=>f({ id: 'm1', hasVideo: true, width: 640, height: 360 })); return document.getElementById('nowPlayingScreen').classList.contains('np-video-on'); }")
        check(not stale, 'a picture from the previous launch\'s item (id m1) is ignored')
        await fire(0, 0); await pg.wait_for_timeout(300)
        check(not await on(), 'radio station: a video track with no picture does not bring up the video view')
        await pg.screenshot(path=f'{shots}/svw-station-nopic.png')
        pill = await pg.evaluate("!document.getElementById('npVideoToggle').hidden")
        check(not pill, 'and no Turn On Video button on the station')
        pip = await pg.evaluate("__t.ev('streamPicReady(currentStation)')")
        check(not pip, 'nor picture-in-picture on leaving the app')
        rem = await pg.evaluate("__t.ev('stationHasVideo(currentStation)')")
        check(not rem, 'and the station is not remembered as carrying video')
        await fire(640, 360); await pg.wait_for_timeout(300)
        check(await on(), 'a real picture still brings it up (video streams keep working)')
        # TV channel: straight away
        await pg.evaluate("__t.ev(\"resetNpVideoUi(); currentStation.videoChannel = true;\")")
        await fire(0, 0); await pg.wait_for_timeout(300)
        check(await on(), 'a TV channel puts the picture box up straight away, as before')
        check(not errs, f'no page errors {errs[:3]}')
        await b.close()
asyncio.run(main())
print('FAILED: %d' % len(fails) if fails else 'ALL PASS')
raise SystemExit(1 if fails else 0)
