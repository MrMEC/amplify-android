"""Build 562: the profile picture (top right) fades with Home's logo instead of sliding away.
Fades out at the logo's scroll position (past 8px), fades back in on a scroll up, on every page.
Run: python3 tests/test_avatar_fade.py (screenshots in /tmp/claude-0/t/shots)"""
import sys as _nsys, os as _nos; _nsys.path.insert(0, _nos.path.dirname(_nos.path.abspath(__file__))); from notice_auto import AUTO_NOTICE
import asyncio, os, json, threading, http.server, functools, shutil
from playwright.async_api import async_playwright
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = '/tmp/claude-0/t/srv-avfade'; SHOTS = '/tmp/claude-0/t/shots'; PORT = 8881
shutil.rmtree(ROOT, ignore_errors=True); os.makedirs(ROOT); os.makedirs(SHOTS, exist_ok=True)
shutil.copy(os.path.join(HERE, '..', 'www', 'index.html'), ROOT + '/index.html')
H = functools.partial(http.server.SimpleHTTPRequestHandler, directory=ROOT); H.log_message = lambda *a: None
srv = http.server.ThreadingHTTPServer(('127.0.0.1', PORT), H); threading.Thread(target=srv.serve_forever, daemon=True).start()
ST = [{'name': 'Station %d' % i, 'urlToResolve': 'http://x/%d' % i, 'favicon': '', 'tags': '80s', 'stationuuid': 'u%d' % i} for i in range(40)]
SEED = ("if(!sessionStorage.getItem('s')){ sessionStorage.setItem('s','1'); localStorage.setItem('radioPlayerFavorites', %s); }") % json.dumps(json.dumps(ST))
fails = []
def check(ok, msg):
    print(('PASS ' if ok else 'FAIL ') + msg)
    if not ok: fails.append(msg)
OP = "[+getComputedStyle(document.querySelector('#hbAvatar')).opacity, +getComputedStyle(document.querySelector('.sidebar-top .brand')).opacity, document.querySelector('#hbAvatar').getBoundingClientRect().top, window.scrollY]"
async def swipe(cdp, dy):
    # a scroll of dy px (negative = back up), fired as real wheel input on the page: Chromium's
    # synthesized touch drag does not move this page in headless mode (see /tmp debugging in build 562)
    await cdp.send('Input.dispatchMouseEvent', {'type': 'mouseWheel', 'x': 195, 'y': 600, 'deltaX': 0, 'deltaY': dy})
    await asyncio.sleep(0.6)
async def state(pg):
    return await pg.evaluate(OP)
async def page_cycle(pg, cdp, name):
    await pg.wait_for_timeout(500)
    s0 = await state(pg); top0 = s0[2]
    check(s0[0] == 1, f'[{name}] at the top the picture is showing {s0}')
    await pg.screenshot(path=f'{SHOTS}/avfade-{name}-1top.png', clip={'x': 0, 'y': 0, 'width': 390, 'height': 140})
    await swipe(cdp, 300); s1 = await state(pg)
    check(s1[3] > 8 and s1[0] == 0, f'[{name}] scrolled down: the picture has faded out {s1}')
    check(abs(s1[2] - top0) < 1, f'[{name}] it faded where it was, it did not slide ({top0} -> {s1[2]})')
    await pg.screenshot(path=f'{SHOTS}/avfade-{name}-2down.png', clip={'x': 0, 'y': 0, 'width': 390, 'height': 140})
    await swipe(cdp, -60); s2 = await state(pg)
    check(s2[3] > 8 and s2[0] == 1, f'[{name}] scrolled up a little: the picture fades back in {s2}')
    check(abs(s2[2] - top0) < 1, f'[{name}] and it did not slide down from the top ({top0} -> {s2[2]})')
    await pg.screenshot(path=f'{SHOTS}/avfade-{name}-3up.png', clip={'x': 0, 'y': 0, 'width': 390, 'height': 140})
    await swipe(cdp, 120); s3 = await state(pg)
    check(s3[0] == 0, f'[{name}] down again: faded out again {s3}')
    await pg.evaluate("window.scrollTo(0,0)"); await pg.wait_for_timeout(500); s4 = await state(pg)
    check(s4[0] == 1, f'[{name}] back at the top: showing {s4}')
async def run(B, theme):
    c = await B.new_context(viewport={'width': 390, 'height': 844}, device_scale_factor=2, is_mobile=True, has_touch=True, color_scheme=theme)
    await c.add_init_script(AUTO_NOTICE); await c.add_init_script(SEED)
    pg = await c.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
    cdp = await c.new_cdp_session(pg)
    await pg.goto(f'http://127.0.0.1:{PORT}/index.html'); await pg.wait_for_timeout(2500)
    # Home: the logo and the picture must change at the same scroll position
    await swipe(cdp, 4); s = await state(pg)
    check(s[3] <= 8 and s[0] == 1 and s[1] == 1, f'[{theme}] home, scrolled under 8px: picture and logo both still showing {s}')
    await pg.evaluate("window.scrollTo(0,0)"); await pg.wait_for_timeout(300)
    await swipe(cdp, 30); await pg.wait_for_timeout(300); s = await state(pg)
    check(s[3] > 8 and s[0] == 0 and s[1] == 0, f'[{theme}] home, scrolled past 8px: picture and logo both faded out together {s}')
    await pg.evaluate("window.scrollTo(0,0)"); await pg.wait_for_timeout(500)
    await page_cycle(pg, cdp, f'{theme}-home')
    for tab, label in (('library', 'Library'), ('podcasts', 'Podcasts'), ('watch', 'Watch')):
        btn = pg.locator('.mobile-nav-btn', has_text=label).first
        if await btn.count():
            await btn.tap(); await pg.wait_for_timeout(900)
            # these pages are short on an empty library: give the page height so it can scroll (the header logic is the same)
            await pg.evaluate("(function(){ var d = document.getElementById('avSpacer') || document.createElement('div'); d.id = 'avSpacer'; d.style.cssText = 'height:2600px;pointer-events:none'; document.getElementById('browseView').appendChild(d); window.scrollTo(0,0); })()"); await pg.wait_for_timeout(300)
            await page_cycle(pg, cdp, f'{theme}-{tab}')
    check(not errs, f'[{theme}] no page errors {errs[:2]}')
    await c.close()
async def main():
    async with async_playwright() as p:
        B = await p.chromium.launch()
        for th in ('dark', 'light'): await run(B, th)
        await B.close()
    print('FAILED: %d' % len(fails) if fails else 'ALL PASS')
    raise SystemExit(1 if fails else 0)
asyncio.run(main())
