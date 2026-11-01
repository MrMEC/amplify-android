"""Build 392: Settings > Appearance > Color presets (accent pairs for dark and light) and AMOLED black.
Run: python3 tests/test_accent_presets.py (screenshots in /tmp/claude-0/t/shots)"""
import sys as _nsys, os as _nos; _nsys.path.insert(0, _nos.path.dirname(_nos.path.abspath(__file__))); from notice_auto import AUTO_NOTICE
import asyncio, os, json, threading, http.server, functools, shutil
from playwright.async_api import async_playwright
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = '/tmp/claude-0/t/srv-presets'; SHOTS = '/tmp/claude-0/t/shots'; PORT = 8874
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
async def run(B, w, h, mobile, theme):
    T = f'[{theme} {w}]'
    c = await B.new_context(viewport={'width': w, 'height': h}, device_scale_factor=2 if mobile else 1, is_mobile=mobile, has_touch=mobile, color_scheme=theme)
    pg = await c.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
    await pg.add_init_script(AUTO_NOTICE)
    await pg.goto(f'http://127.0.0.1:{PORT}/index.html'); await pg.wait_for_timeout(1800)
    await pg.evaluate("__t.ev(\"setTheme('%s')\")" % theme)
    await pg.evaluate("__t.set('appearance-theme')"); await pg.wait_for_timeout(400)
    names = await pg.evaluate("Array.prototype.map.call(document.querySelectorAll('.preset-chip span:last-child'), s => s.textContent)")
    check(names == ['Classic', 'Ruby', 'Rose', 'Sunset', 'Forest', 'Teal', 'Ocean', 'Violet'], f'{T} presets {names}')
    check(await active(pg) == ['Classic'], f'{T} Classic is active to begin with')
    base = await accent(pg)
    await pg.click('.preset-chip:nth-child(2)'); await pg.wait_for_timeout(300)
    want = {'dark': '#ff5a5f', 'light': '#c62833'}[theme]
    check((await accent(pg)).lower() == want, f'{T} Ruby sets the accent {await accent(pg)}')
    check(await active(pg) == ['Ruby'], f'{T} and is marked')
    stored = await pg.evaluate("JSON.parse(localStorage.getItem('radioPlayerCustomAccent'))")
    check(stored == {'dark': '#ff5a5f', 'light': '#c62833'}, f'{T} both themes saved {stored}')
    await pg.screenshot(path=f'{SHOTS}/presets_ruby_{theme}_{w}.png')
    other = 'light' if theme == 'dark' else 'dark'
    await pg.evaluate("__t.ev(\"setTheme('%s')\")" % other); await pg.wait_for_timeout(300)
    want2 = {'dark': '#ff5a5f', 'light': '#c62833'}[other]
    check((await accent(pg)).lower() == want2 and await active(pg) == ['Ruby'], f'{T} the other theme has Ruby\'s shade for it ({await accent(pg)})')
    await pg.screenshot(path=f'{SHOTS}/presets_ruby_{other}_{w}.png')
    await pg.evaluate("__t.ev(\"setTheme('%s')\")" % theme); await pg.wait_for_timeout(200)
    await pg.click('.preset-chip:nth-child(7)'); await pg.wait_for_timeout(200)
    check(await active(pg) == ['Ocean'], f'{T} choosing another moves the mark')
    await pg.reload(); await pg.wait_for_timeout(1500)
    await pg.evaluate("__t.set('appearance-theme')"); await pg.wait_for_timeout(300)
    check(await active(pg) == ['Ocean'], f'{T} kept after a restart')
    await pg.evaluate("__t.ev(\"saveCustomAccent(currentTheme, '#123456'); restoreAccentForTheme(currentTheme)\")")
    check(await active(pg) == [], f'{T} a custom colour clears the mark')
    await pg.click('.preset-chip:nth-child(1)'); await pg.wait_for_timeout(200)
    check(await active(pg) == ['Classic'] and await pg.evaluate("localStorage.getItem('radioPlayerCustomAccent')") in ('{}', None), f'{T} Classic puts the default back')
    check((await accent(pg)).lower() == base.lower(), f'{T} accent is the default again')
    # AMOLED
    check(await pg.evaluate("document.getElementById('amoledSelect').value") == 'off' and not await pg.evaluate("document.documentElement.hasAttribute('data-amoled')"), f'{T} AMOLED is off to begin with')
    bg0 = await pg.evaluate("getComputedStyle(document.documentElement).getPropertyValue('--panel').trim()")
    await pg.click('#amoledSelectSwitch'); await pg.wait_for_timeout(300)
    panel = await pg.evaluate("getComputedStyle(document.documentElement).getPropertyValue('--panel').trim()")
    sidebar = await pg.evaluate("getComputedStyle(document.documentElement).getPropertyValue('--bg').trim()")
    if theme == 'dark':
        check(panel == '#050506' and sidebar == '#000000', f'{T} AMOLED on: panels {panel}, background {sidebar} (was {bg0})')
    else:
        check(panel == bg0 and sidebar != '#000000', f'{T} AMOLED on does nothing to the light theme ({panel})')
    check(await pg.evaluate("localStorage.getItem('radioPlayerAmoled')") == 'on', f'{T} stored')
    await pg.screenshot(path=f'{SHOTS}/amoled_settings_{theme}_{w}.png')
    await pg.evaluate("__t.close()"); await pg.wait_for_timeout(500)
    await pg.screenshot(path=f'{SHOTS}/amoled_home_{theme}_{w}.png')
    await pg.reload(); await pg.wait_for_timeout(1500)
    check(await pg.evaluate("document.documentElement.hasAttribute('data-amoled')") and await pg.evaluate("document.getElementById('amoledSelect').value") == 'on', f'{T} AMOLED kept after a restart')
    await pg.click('.drawer-tab, body') if False else None
    check('radioPlayerAmoled' in await pg.evaluate("window.__amplifyKvKeys || []"), f'{T} in backups')
    await pg.evaluate("__t.set('appearance-theme')"); await pg.wait_for_timeout(300)
    await pg.click('#amoledSelectSwitch'); await pg.wait_for_timeout(200)
    check(not await pg.evaluate("document.documentElement.hasAttribute('data-amoled')"), f'{T} off again')
    check(not errs, f'{T} no page errors {errs[:3]}')
    await c.close()
async def main():
    async with async_playwright() as p:
        B = await p.chromium.launch()
        await run(B, 390, 844, True, 'dark')
        await run(B, 390, 844, True, 'light')
        await run(B, 1280, 860, False, 'dark')
        await B.close()
    print('FAILED %s' % fails if fails else 'ALL PASSED')
asyncio.run(main())
