"""Build 589: Settings > Theme & color > Background -- default, a colour (presets, Accent tint, the
picker) and a gradient (style, position, intensity, size, first and second colour), per theme.
Run: python3 tests/test_background.py (screenshots in /tmp/claude-0/t/shots)"""
import sys as _nsys, os as _nos; _nsys.path.insert(0, _nos.path.dirname(_nos.path.abspath(__file__))); from notice_auto import AUTO_NOTICE
import asyncio, os, json, threading, http.server, functools, shutil
from playwright.async_api import async_playwright
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = '/tmp/claude-0/t/srv-bg'; SHOTS = '/tmp/claude-0/t/shots'; PORT = 8882
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
BODY = "(()=>{ var cs=getComputedStyle(document.body); return {img:cs.backgroundImage, att:cs.backgroundAttachment, col:cs.backgroundColor, fill:getComputedStyle(document.documentElement).getPropertyValue('--main-fill').trim(), mainbg:getComputedStyle(document.documentElement).getPropertyValue('--main-bg').trim(), text:getComputedStyle(document.documentElement).getPropertyValue('--text').trim(), cls:document.body.className}; })()"
async def run(B, w, h, theme):
    T = f'[{theme} {w}x{h}]'
    c = await B.new_context(viewport={'width': w, 'height': h}, device_scale_factor=2, is_mobile=True, has_touch=True, color_scheme=theme)
    pg = await c.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
    await pg.add_init_script(AUTO_NOTICE)
    await pg.add_init_script("try{ localStorage.setItem('radioPlayerLandscape', JSON.stringify({np:false,cf:true})); }catch(e){}")
    await pg.goto(f'http://127.0.0.1:{PORT}/index.html'); await pg.wait_for_timeout(1800)
    await pg.evaluate("__t.ev(\"setTheme('%s')\")" % theme)
    b0 = await pg.evaluate(BODY)
    check(b0['img'] == 'none' and not b0['fill'], f'{T} default: plain page {b0["img"][:40]}')
    await pg.evaluate("__t.set('appearance-theme')"); await pg.wait_for_timeout(400)
    vis = await pg.evaluate("[document.getElementById('bgSolidRows').hidden, document.getElementById('bgGradRows').hidden, Array.from(document.querySelectorAll('#bgModeSwitch .theme-opt.active')).map(function(b){return b.textContent;})]")
    check(vis == [True, True, ['Default']], f'{T} Default chosen, nothing else showing {vis}')
    await pg.evaluate("document.querySelector('#bgModeSwitch [data-bg-mode=gradient]').scrollIntoView({block:'start'})"); await pg.wait_for_timeout(200)
    # gradient
    await pg.click('#bgModeSwitch [data-bg-mode=gradient]'); await pg.wait_for_timeout(300)
    g = await pg.evaluate(BODY)
    check('radial-gradient' in g['img'] and g['att'] == 'fixed' and 'bg-grad' in g['cls'], f'{T} Gradient: a radial gradient, fixed to the screen {g["img"][:80]} {g["att"]}')
    acc = await pg.evaluate("getComputedStyle(document.documentElement).getPropertyValue('--accent').trim()")
    await pg.screenshot(path=f'{SHOTS}/bg-grad-settings-{theme}-{w}.png')
    for st, needle in [('vertical', 'linear-gradient'), ('horizontal', 'linear-gradient'), ('diagonal', 'linear-gradient'), ('sweep', 'conic-gradient'), ('radial', 'radial-gradient')]:
        await pg.click(f'#bgStyleChips [data-style={st}]'); await pg.wait_for_timeout(150)
        gi = await pg.evaluate(BODY)
        en = await pg.evaluate("Array.from(document.querySelectorAll('#bgPosGrid .bg-pos-btn')).filter(function(b){return !b.disabled;}).map(function(b){return b.dataset.pos;})")
        check(needle in gi['img'], f'{T} style {st}: {needle} (positions {en})')
    await pg.click('#bgPosGrid [data-pos=br]'); await pg.wait_for_timeout(150)
    check('100% 100%' in (await pg.evaluate(BODY))['img'], f'{T} position bottom right')
    await pg.fill('#bgIntRange', '80'); await pg.dispatch_event('#bgIntRange', 'input'); await pg.wait_for_timeout(150)
    await pg.fill('#bgSizeRange', '40'); await pg.dispatch_event('#bgSizeRange', 'input'); await pg.wait_for_timeout(150)
    gi = await pg.evaluate(BODY)
    check('0.8)' in gi['img'] and '40%' in gi['img'], f'{T} intensity 80% and size 40% reach the gradient {gi["img"][:120]}')
    # colours through the picker
    await pg.click('#bgC1Btn'); await pg.wait_for_timeout(300)
    t1 = await pg.evaluate("document.getElementById('accentTitle').textContent")
    await pg.click('#accentSwatches .accent-sw:nth-child(9)'); await pg.click('#accentSetBtn'); await pg.wait_for_timeout(200)
    gi = await pg.evaluate(BODY)
    acc2 = await pg.evaluate("getComputedStyle(document.documentElement).getPropertyValue('--accent').trim()")
    check(t1 == 'First Color' and 'rgba(0, 122, 255' in gi['img'] and acc2 == acc, f'{T} first colour from the picker (title {t1}), accent untouched {gi["img"][:90]}')
    await pg.click('#bgC2Btn'); await pg.wait_for_timeout(300)
    await pg.click('#accentSwatches .accent-sw:nth-child(11)'); await pg.click('#accentSetBtn'); await pg.wait_for_timeout(200)
    gi = await pg.evaluate(BODY)
    check('rgba(175, 82, 222' in gi['img'], f'{T} second colour {gi["img"][:120]}')
    await pg.evaluate("document.getElementById('bgResetBtn').scrollIntoView({block:'end'})"); await pg.wait_for_timeout(300)
    await pg.screenshot(path=f'{SHOTS}/bg-grad-controls-{theme}-{w}.png')
    await pg.evaluate("__t.close()"); await pg.wait_for_timeout(500)
    await pg.screenshot(path=f'{SHOTS}/bg-grad-home-{theme}-{w}.png')
    await pg.evaluate("document.querySelector('.mobile-nav-btn[data-nav=library]').click()"); await pg.wait_for_timeout(800)
    await pg.evaluate("window.scrollTo(0, 300)"); await pg.wait_for_timeout(400)
    await pg.screenshot(path=f'{SHOTS}/bg-grad-library-{theme}-{w}.png')
    # back to accent / none, then a reload keeps it
    await pg.evaluate("__t.set('appearance-theme')"); await pg.wait_for_timeout(400)
    await pg.click('#bgC1Reset'); await pg.click('#bgC2Reset'); await pg.wait_for_timeout(200)
    gi = await pg.evaluate(BODY)
    check('rgba(175, 82, 222' not in gi['img'] and 'rgba(0, 122, 255' not in gi['img'], f'{T} Use accent / None put the colours back')
    await pg.reload(); await pg.wait_for_timeout(1800)
    gr = await pg.evaluate(BODY)
    check('radial-gradient' in gr['img'] and '100% 100%' in gr['img'], f'{T} kept after a restart')
    # the other theme is separate
    other = 'light' if theme == 'dark' else 'dark'
    await pg.evaluate("__t.ev(\"setTheme('%s')\")" % other); await pg.wait_for_timeout(300)
    check((await pg.evaluate(BODY))['img'] == 'none', f'{T} the {other} theme keeps its own (default) background')
    await pg.evaluate("__t.ev(\"setTheme('%s')\")" % theme); await pg.wait_for_timeout(300)
    # solid colours
    await pg.evaluate("__t.set('appearance-theme')"); await pg.wait_for_timeout(400)
    await pg.click('#bgModeSwitch [data-bg-mode=solid]'); await pg.wait_for_timeout(200)
    s1 = await pg.evaluate(BODY)
    check(s1['img'] == 'none' and 'bg-solid' in s1['cls'] and s1['mainbg'].startswith('#'), f'{T} Color: Accent tint to begin with {s1["mainbg"]}')
    await pg.click('#bgSolidSwatches .bg-sw:nth-child(4)'); await pg.wait_for_timeout(200)
    s2 = await pg.evaluate(BODY)
    want = {'dark': '#0b1020', 'light': '#eef2f6'}[theme]
    check(s2['mainbg'] == want, f'{T} a preset colour {s2["mainbg"]}')
    await pg.evaluate("document.getElementById('bgResetBtn').scrollIntoView({block:'end'})"); await pg.wait_for_timeout(300)
    await pg.screenshot(path=f'{SHOTS}/bg-solid-settings-{theme}-{w}.png')
    await pg.click('#bgSolidSwatches .bg-sw-custom'); await pg.wait_for_timeout(300)
    await pg.click('#accentSwatches .accent-sw:nth-child(5)'); await pg.click('#accentSetBtn'); await pg.wait_for_timeout(200)
    s3 = await pg.evaluate(BODY)
    check(s3['mainbg'] == '#ffcc00' and s3['text'] in ('#201d17',) , f'{T} a picked colour (yellow): dark text on it {s3["mainbg"]} {s3["text"]}')
    await pg.evaluate("__t.close()"); await pg.wait_for_timeout(400)
    await pg.screenshot(path=f'{SHOTS}/bg-solid-home-{theme}-{w}.png')
    await pg.evaluate("__t.set('appearance-theme')"); await pg.wait_for_timeout(400)
    await pg.click('#bgResetBtn'); await pg.wait_for_timeout(200)
    s4 = await pg.evaluate(BODY)
    check(s4['img'] == 'none' and 'bg-solid' not in s4['cls'] and not s4['text'] in ('#201d17',) or theme == 'light', f'{T} Reset: the theme\'s own background')
    check(not errs, f'{T} no page errors {errs}')
    await c.close()
async def main():
    async with async_playwright() as p:
        B = await p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
        for theme in ('dark', 'light'):
            await run(B, 390, 844, theme)
        await run(B, 892, 373, 'dark')
        await B.close()
    print('FAILED' if fails else 'ALL PASSED', fails)
asyncio.run(main())
