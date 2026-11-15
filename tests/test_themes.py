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
        c = await B.new_context(viewport={'width':327,'height':709}, device_scale_factor=3.3, is_mobile=True, has_touch=True)
        pg = await c.new_page(); errs=[]; pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.add_init_script(AUTO_NOTICE)
        await pg.goto(f'http://127.0.0.1:{PORT}/index.html'); await pg.wait_for_timeout(1800)
        await pg.evaluate("__t.set('appearance-theme')"); await pg.wait_for_timeout(500)
        print('title', await pg.evaluate("document.querySelector('[data-set-page=appearance-theme]').dataset.setTitle"))
        names = await pg.evaluate("Array.from(document.querySelectorAll('#themePresetGrid span:last-child')).map(s=>s.textContent)")
        check(len(names)==10, f'10 presets {names}')
        await pg.screenshot(path=f'{SHOTS}/th-top.png')
        for i,n in [(1,'neon'),(3,'paper'),(9,'terminal'),(8,'candy')]:
            await pg.click(f'#themePresetGrid .th-chip:nth-child({i})'); await pg.wait_for_timeout(500)
            on = await pg.evaluate("Array.from(document.querySelectorAll('#themePresetGrid [aria-pressed=true] span:last-child')).map(s=>s.textContent)")
            check(len(on)==1, f'{n} marked {on}')
            await pg.screenshot(path=f'{SHOTS}/th-{n}.png')
        want = {1:'flow,l,60,true',2:'edit,m,above',3:'none',4:'card,m',5:'slides,l',6:'edit,m,below',7:'card,l',8:'card,s',9:'none',10:'edit,s,above'}
        for i,w in want.items():
            await pg.click(f'#themePresetGrid .th-chip:nth-child({i})'); await pg.wait_for_timeout(400)
            got = await pg.evaluate("(function(){var c=JSON.parse(localStorage.getItem('radioPlayerCarousel'));return c.mode=='none'?'none':c.mode=='flow'?['flow',c.size,c.tilt,c.reflect].join(','):c.mode=='card'?'card,'+c.cardSize:c.mode=='edit'?'edit,'+c.cardSize+','+c.textPos:'slides,'+c.size})()")
            vis = await pg.evaluate("getComputedStyle(document.getElementById('npHero')).display")
            check(got==w, f'preset {i} carousel {got} (hero display {vis})')
            check(await pg.evaluate("document.querySelectorAll('#themePresetGrid [aria-pressed=true]').length")==1, f'preset {i} marked')
        await pg.click('#themePresetGrid .th-chip:nth-child(4)'); await pg.wait_for_timeout(300)
        await pg.evaluate("__t.set('home-carousel')"); await pg.wait_for_timeout(300); await pg.evaluate("document.querySelector('[data-carousel-opt=none]').click()"); await pg.wait_for_timeout(300)
        check(await pg.evaluate("document.querySelectorAll('#themePresetGrid [aria-pressed=true]').length")==0, 'changing the carousel clears the mark')
        await pg.evaluate("__t.set('appearance-theme')"); await pg.wait_for_timeout(400)
        await pg.evaluate("document.getElementById('themeSaveBtn').scrollIntoView({block:'center'})"); await pg.click('#themeSaveBtn'); await pg.fill('#thNameInput','Plain'); await pg.click('#thNameSave'); await pg.wait_for_timeout(400)
        await pg.click('#themePresetGrid .th-chip:nth-child(1)'); await pg.wait_for_timeout(300)
        await pg.click('#themeCustomList .th-use'); await pg.wait_for_timeout(500)
        check(await pg.evaluate("JSON.parse(localStorage.getItem('radioPlayerCarousel')).mode")=='none', 'saved theme restores carousel off')
        print('errs', errs)
        await B.close()
asyncio.run(main()); print('FAILS', fails)
