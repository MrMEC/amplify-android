"""Build 640: Theme Settings presets and saved themes.
Run: python3 tests/test_accent_presets.py (screenshots in /tmp/claude-0/t/shots)"""
import sys as _nsys, os as _nos; _nsys.path.insert(0, _nos.path.dirname(_nos.path.abspath(__file__))); from notice_auto import AUTO_NOTICE
import asyncio, os, json, threading, http.server, functools, shutil
from playwright.async_api import async_playwright
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = '/tmp/claude-0/t/srv-themes'; SHOTS = '/tmp/claude-0/t/shots'; PORT = 8877
shutil.rmtree(ROOT, ignore_errors=True); os.makedirs(ROOT); os.makedirs(SHOTS, exist_ok=True)
HOOK = "window.__t = { set: function(c){ openSettings(c); }, close: function(){ closeSettings(); }, ev: function(js){ return eval(js); } };\n"
src = open(os.path.join(HERE, '..', 'www', 'index.html')).read()
mark = '  var coverFlow = null;\n'
assert src.count(mark) == 1
open(ROOT + '/index.html', 'w').write(src.replace(mark, mark + HOOK))
H = functools.partial(http.server.SimpleHTTPRequestHandler, directory=ROOT); H.log_message = lambda *a: None
srv = http.server.ThreadingHTTPServer(('127.0.0.1', PORT), H); threading.Thread(target=srv.serve_forever, daemon=True).start()
fails = []
def check(ok, msg):
    print(('PASS ' if ok else 'FAIL ') + msg)
    if not ok: fails.append(msg)
def rgb(h): return 'rgb(%d, %d, %d)' % (int(h[1:3], 16), int(h[3:5], 16), int(h[5:7], 16))
async def accent(pg): return await pg.evaluate("getComputedStyle(document.documentElement).getPropertyValue('--accent').trim()")
async def active(pg): return await pg.evaluate("Array.prototype.map.call(document.querySelectorAll('.preset-chip[aria-pressed=true] span:last-child'), s => s.textContent)")
async def main():
    async with async_playwright() as p:
        B = await p.chromium.launch()
        c = await B.new_context(viewport={'width':327,'height':709}, device_scale_factor=3.3, is_mobile=True, has_touch=True, color_scheme='dark')
        pg = await c.new_page(); errs=[]; pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.add_init_script(AUTO_NOTICE)
        await pg.goto(f'http://127.0.0.1:{PORT}/index.html'); await pg.wait_for_timeout(1800)
        await pg.evaluate("__t.set('home-carousel')"); await pg.wait_for_timeout(600)
        await pg.screenshot(path=f'{SHOTS}/co-1.png')
        await pg.click('[data-carousel-opt=edit]'); await pg.wait_for_timeout(500); await pg.screenshot(path=f'{SHOTS}/co-3.png')
        await pg.evaluate("document.getElementById('carouselEditOpts').scrollIntoView()"); await pg.wait_for_timeout(300)
        await pg.screenshot(path=f'{SHOTS}/co-2.png')
        print('errs', errs); await B.close()
asyncio.run(main())
