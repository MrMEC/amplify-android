"""Build 571: tapping the active tab-bar icon slides the mini player away / back instead of reloading the page;
it stays hidden from page to page; playing brings it back; Watch starts hidden and its active tab shows it.
Run: python3 tests/test_mini_toggle.py (screenshots in /tmp/claude-0/t/shots)"""
import sys as _nsys, os as _nos; _nsys.path.insert(0, _nos.path.dirname(_nos.path.abspath(__file__))); from notice_auto import AUTO_NOTICE
import asyncio, os, json, threading, http.server, functools, shutil
from playwright.async_api import async_playwright
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = '/tmp/claude-0/t/srv-mini'; SHOTS = '/tmp/claude-0/t/shots'; PORT = 8883
shutil.rmtree(ROOT, ignore_errors=True); os.makedirs(ROOT); os.makedirs(SHOTS, exist_ok=True)
src = open(os.path.join(HERE, '..', 'www', 'index.html')).read()
mark = '  var coverFlow = null;\n'; assert src.count(mark) == 1
open(ROOT + '/index.html', 'w').write(src.replace(mark, mark + "window.__t = { ev: function(js){ return eval(js); } };\n"))
H = functools.partial(http.server.SimpleHTTPRequestHandler, directory=ROOT); H.log_message = lambda *a: None
srv = http.server.ThreadingHTTPServer(('127.0.0.1', PORT), H); threading.Thread(target=srv.serve_forever, daemon=True).start()
ST = [{'name': 'Station %d' % i, 'urlToResolve': 'http://x/%d' % i, 'favicon': '', 'tags': '80s', 'stationuuid': 'u%d' % i} for i in range(6)]
SEED = ("if(!sessionStorage.getItem('s')){ sessionStorage.setItem('s','1'); localStorage.setItem('radioPlayerFavorites', %s); }") % json.dumps(json.dumps(ST))
fails = []
def check(ok, msg):
    print(('PASS ' if ok else 'FAIL ') + msg)
    if not ok: fails.append(msg)
BAR = "(function(){ var b = document.getElementById('playerBar'), r = b.getBoundingClientRect(), cs = getComputedStyle(b); return { top: Math.round(r.top), vh: innerHeight, op: +cs.opacity, hidden: document.body.classList.contains('mini-hidden') }; })()"
async def bar(pg): await pg.wait_for_timeout(600); return await pg.evaluate(BAR)
def shown(b): return (not b['hidden']) and b['op'] == 1 and b['top'] < b['vh'] - 60
def gone(b): return b['hidden'] and b['op'] == 0 and b['top'] >= b['vh']
async def tab(pg, label):
    await pg.locator('.mobile-nav-btn', has_text=label).first.tap(); await pg.wait_for_timeout(500)
async def run(B, theme):
    T = f'[{theme}]'
    c = await B.new_context(viewport={'width': 390, 'height': 844}, device_scale_factor=2, is_mobile=True, has_touch=True, color_scheme=theme)
    await c.add_init_script(AUTO_NOTICE); await c.add_init_script(SEED)
    pg = await c.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
    await pg.goto(f'http://127.0.0.1:{PORT}/index.html'); await pg.wait_for_timeout(2500)
    ev = lambda js: pg.evaluate("window.__t.ev(%s)" % json.dumps(js))
    await ev("playStation(JSON.parse(localStorage.getItem('radioPlayerFavorites'))[0])"); await pg.wait_for_timeout(800)
    b = await bar(pg); check(shown(b), f'{T} home: the mini player shows {b}')
    await pg.evaluate("window.scrollTo(0, 0)")
    await tab(pg, 'Home'); b = await bar(pg)
    check(gone(b), f'{T} tapping the active Home icon slides the mini player away {b}')
    check(await pg.evaluate("document.body.classList.contains('home-view')"), f'{T} and Home was not reloaded away')
    await pg.screenshot(path=f'{SHOTS}/mini-{theme}-hidden.png')
    await tab(pg, 'Library'); b = await bar(pg)
    check(gone(b), f'{T} going to Library: it stays hidden {b}')
    await tab(pg, 'Podcasts'); b = await bar(pg)
    check(gone(b), f'{T} Podcasts: still hidden {b}')
    await tab(pg, 'Podcasts'); b = await bar(pg)
    check(shown(b), f'{T} tapping the active Podcasts icon shows it again {b}')
    await tab(pg, 'Podcasts'); b = await bar(pg); check(gone(b), f'{T} and hides it again {b}')
    await ev("playStation(JSON.parse(localStorage.getItem('radioPlayerFavorites'))[1])"); b = await bar(pg)
    check(shown(b), f'{T} playing something brings it back {b}')
    await tab(pg, 'Home'); b = await bar(pg)
    check(shown(b), f'{T} going Home with it showing: stays showing {b}')
    await tab(pg, 'Watch'); b = await bar(pg)
    check(gone(b), f'{T} Watch: hidden by default {b}')
    await pg.screenshot(path=f'{SHOTS}/mini-{theme}-watch-default.png')
    await tab(pg, 'Watch'); b = await bar(pg)
    check(shown(b), f'{T} Watch: tapping its active icon shows it {b}')
    await pg.screenshot(path=f'{SHOTS}/mini-{theme}-watch-shown.png')
    await tab(pg, 'Library'); b = await bar(pg); check(shown(b), f'{T} leaving Watch: the bar follows the normal state (showing) {b}')
    await tab(pg, 'Watch'); b = await bar(pg); check(gone(b), f'{T} entering Watch again: hidden again {b}')
    await tab(pg, 'Home'); await tab(pg, 'Home'); b = await bar(pg); check(gone(b), f'{T} hide at Home after Watch {b}')
    await ev("audio.dispatchEvent(new Event('ended')); playStation(JSON.parse(localStorage.getItem('radioPlayerFavorites'))[2])"); b = await bar(pg)
    check(gone(b), f'{T} a track that starts by itself when one ends does not bring it back {b}')
    check(not errs, f'{T} no page errors {errs[:2]}')
    await c.close()
async def main():
    async with async_playwright() as p:
        B = await p.chromium.launch()
        for th in ('dark', 'light'): await run(B, th)
        await B.close()
    print('FAILED: %d' % len(fails) if fails else 'ALL PASS')
    raise SystemExit(1 if fails else 0)
asyncio.run(main())
