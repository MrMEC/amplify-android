"""Volume leveling setting (build 231): Settings > Volume leveling (On/Off) in the Android app, read
from and sent to the native player (setLeveling); hidden in a browser. Both themes at 412 wide.
Run: python3 tests/test_leveling.py (screenshots in /tmp/claude-0/t/shots)"""
import sys as _nsys, os as _nos; _nsys.path.insert(0, _nos.path.dirname(_nos.path.abspath(__file__))); from notice_auto import AUTO_NOTICE
import asyncio, os, threading, http.server, functools, shutil
from playwright.async_api import async_playwright

PORT = 8829
root = '/tmp/claude-0/t/srv_leveling'
shots = '/tmp/claude-0/t/shots'
os.makedirs(shots, exist_ok=True)
shutil.rmtree(root, ignore_errors=True)
os.makedirs(root)
HOOK = "window.__t = { settings: function(){ openSettings('playback'); } };\n"
_src = open(os.path.join(os.path.dirname(__file__), '..', 'www', 'index.html')).read()
_mark = '  var coverFlow = null;\n'
assert _src.count(_mark) == 1
open(root + '/index.html', 'w').write(_src.replace(_mark, _mark + HOOK))


class Q(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a): pass
srv = http.server.ThreadingHTTPServer(('127.0.0.1', PORT), functools.partial(Q, directory=root))
threading.Thread(target=srv.serve_forever, daemon=True).start()

# The native side starts with leveling off, so the page must show what the player says.
MOCK = """
(function(){
 var on = false, listeners = {};
 window.__lev = [];
 var impl = {
   setLeveling: function(o){ window.__lev.push(o); if(typeof o.on === 'boolean') on = o.on; return Promise.resolve({ on: on }); },
   addListener: function(n, f){ (listeners[n] = listeners[n] || []).push(f); return Promise.resolve({remove:function(){}}); }
 };
 var P = new Proxy({}, {get:function(t,k){
   if(k==='then') return undefined;
   if(k==='setCarLibraryPart') return undefined;
   if(impl[k]) return impl[k];
   return function(){ return Promise.resolve({}); };
 }});
 window.Capacitor = { isNativePlatform:function(){return true;}, getPlatform:function(){return 'android';},
   registerPlugin:function(){ return P; }, Plugins:{AmplifyPlayer:P}, convertFileSrc:function(u){return u;} };
})();
"""

fails = []
def check(cond, msg):
    print(('PASS ' if cond else 'FAIL ') + msg)
    if not cond: fails.append(msg)

ROW = """() => { var r = document.getElementById('levelingRow'), s = document.getElementById('levelingSelect');
  var b = r.getBoundingClientRect(), l = r.querySelector('.settings-label');
  return { shown: getComputedStyle(r).display !== 'none' && b.height > 0, value: s.value,
    label: l.textContent, oneLine: l.getBoundingClientRect().height < 26, inView: b.right <= innerWidth && b.left >= 0 }; }"""


async def run(p, scheme):
    b = await p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
    ctx = await b.new_context(viewport={'width': 412, 'height': 900}, device_scale_factor=2, is_mobile=True, has_touch=True, color_scheme=scheme)
    await ctx.add_init_script(MOCK); await ctx.add_init_script(AUTO_NOTICE)
    await ctx.add_init_script("try{ localStorage.setItem('radioPlayerTheme', '%s'); }catch(e){}" % scheme)
    pg = await ctx.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
    await pg.route('**/*', lambda route: route.continue_() if '127.0.0.1' in route.request.url else route.abort())
    await pg.goto(f'http://127.0.0.1:{PORT}/index.html'); await pg.wait_for_timeout(2500)
    await pg.evaluate('__t.settings()'); await pg.wait_for_timeout(800)
    r = await pg.evaluate(ROW)
    check(r['shown'] and r['label'] == 'Volume leveling' and r['oneLine'] and r['inView'], f'[{scheme}] Settings shows Volume leveling {r}')
    check(r['value'] == 'off', f'[{scheme}] it shows what the player says (off here) {r["value"]}')
    await pg.evaluate("document.getElementById('levelingRow').scrollIntoView({block:'center'})"); await pg.wait_for_timeout(300)
    await pg.screenshot(path=f'{shots}/leveling-settings-{scheme}.png')
    await pg.select_option('#levelingSelect', 'on'); await pg.wait_for_timeout(300)
    lev = await pg.evaluate('window.__lev')
    check(lev and lev[-1] == {'on': True}, f'[{scheme}] choosing On turns it on in the player {lev[-1:]}')
    await pg.select_option('#levelingSelect', 'off'); await pg.wait_for_timeout(300)
    lev = await pg.evaluate('window.__lev')
    check(lev[-1] == {'on': False}, f'[{scheme}] choosing Off turns it off {lev[-1:]}')
    check(not errs, f'[{scheme}] no page errors {errs[:3]}')
    await b.close()


async def browser(p):
    b = await p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
    ctx = await b.new_context(viewport={'width': 1280, 'height': 900})
    pg = await ctx.new_page()
    await pg.route('**/*', lambda route: route.continue_() if '127.0.0.1' in route.request.url else route.abort())
    await pg.goto(f'http://127.0.0.1:{PORT}/index.html'); await pg.wait_for_timeout(2000)
    await pg.evaluate('__t.settings()'); await pg.wait_for_timeout(500)
    check(not (await pg.evaluate(ROW))['shown'], '[browser] no Volume leveling row without the Android player')
    await b.close()


async def main():
    async with async_playwright() as p:
        for scheme in ('dark', 'light'):
            await run(p, scheme)
        await browser(p)
    print('ALL PASSED' if not fails else f'FAILED {fails}')

asyncio.run(main())
