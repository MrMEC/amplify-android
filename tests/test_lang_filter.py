"""Build 437 (Mark): Settings > Radio > Station languages: All / Only / Exclude with a drop-down of
tick boxes. Every station list from the directory follows it; the Disney genre's own Spanish rule is gone.
Run: python3 tests/test_lang_filter.py (screenshots in /tmp/claude-0/t/shots)"""
import asyncio, os, json, shutil, threading, http.server, functools
from playwright.async_api import async_playwright
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = '/tmp/claude-0/t/srv-lang'; SHOTS = '/tmp/claude-0/t/shots'
shutil.rmtree(ROOT, ignore_errors=True); os.makedirs(ROOT); os.makedirs(SHOTS, exist_ok=True)
html = open(os.path.join(HERE, '..', 'www', 'index.html')).read()
mark = '  var coverFlow = null;\n'
html = html.replace(mark, mark + "window.__lf = { ev: function(j){ return eval(j); } };\n", 1)
open(ROOT + '/index.html', 'w').write(html)
H = functools.partial(http.server.SimpleHTTPRequestHandler, directory=ROOT); H.log_message = lambda *a: None
srv = http.server.ThreadingHTTPServer(('127.0.0.1', 8848), H); threading.Thread(target=srv.serve_forever, daemon=True).start()
def st(n, uid, **kw):
    d = {'name': n, 'url_resolved': 'http://s/' + uid, 'stationuuid': uid, 'tags': 'kids', 'favicon': '', 'language': '', 'languagecodes': '', 'countrycode': ''}; d.update(kw); return d
STATIONS = [st('Disney Hits Radio', 'a1', language='english', countrycode='US'),
            st('XHPOP-FM 99.3 Radio Disney', 'a2', countrycode='MX'),
            st('Radio Disney Argentina', 'a3', language='spanish'),
            st('Radio Disney Brasil', 'a4', language='portuguese', countrycode='BR'),
            st('Disney Junior Paris', 'a5', languagecodes='fr'),
            st('Disney Mystery Stream', 'a6'),
            st('Disney Classics', 'a7', countrycode='US')]
fails = []
def check(c, m):
    print(('PASS ' if c else 'FAIL ') + m)
    if not c: fails.append(m)
async def route(r):
    u = r.request.url
    if u.startswith('http://127.0.0.1'): return await r.continue_()
    if '/json/stations' in u: return await r.fulfill(status=200, content_type='application/json', body=json.dumps(STATIONS))
    if '/json/' in u: return await r.fulfill(status=200, content_type='application/json', body='[]')
    return await r.abort()
NAMES = "Array.prototype.map.call(document.querySelectorAll('.gp-row .tile-name, .gp-grid .tile-name'), x => x.textContent)"
async def run(b, scheme, w):
    T = f'[{scheme} {w}]'
    ctx = await b.new_context(viewport={'width': w, 'height': 844}, device_scale_factor=2, is_mobile=True, has_touch=True, color_scheme=scheme)
    await ctx.add_init_script("localStorage.setItem('radioPlayerTourSeen','1'); localStorage.setItem('radioPlayerTheme', %s)" % json.dumps(scheme))
    pg = await ctx.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
    await pg.route('**/*', route)
    await pg.goto('http://127.0.0.1:8848/index.html'); await pg.wait_for_timeout(2500)
    async def disney():
        await pg.evaluate("__lf.ev(\"searchByTag('Disney'); 0\")"); await pg.wait_for_timeout(1200)
        return await pg.evaluate(NAMES)
    n0 = await disney()
    check(len(n0) == 7, f'{T} with All, the Disney genre keeps every station, Spanish ones too (the old Disney-only rule is gone) {n0}')
    await pg.evaluate("__lf.ev(\"openSettings('radio'); 0\")"); await pg.wait_for_timeout(600)
    r = await pg.evaluate("({ mode: document.getElementById('langModeSelect').value, pick: getComputedStyle(document.getElementById('langPickRow')).display })")
    check(r['mode'] == 'all' and r['pick'] == 'none', f'{T} Station languages starts on All, the picker hidden {r}')
    await pg.select_option('#langModeSelect', 'hide'); await pg.wait_for_timeout(400)
    r = await pg.evaluate("({ pick: getComputedStyle(document.getElementById('langPickRow')).display, open: !document.getElementById('langPickMenu').hidden, n: document.querySelectorAll('.lang-opt').length })")
    check(r['pick'] != 'none' and r['open'] and r['n'] >= 50, f'{T} Exclude shows the picker and opens it {r}')
    await pg.fill('#langPickFind', 'span'); await pg.wait_for_timeout(200)
    vis = await pg.evaluate("Array.prototype.filter.call(document.querySelectorAll('.lang-opt'), o => !o.hidden).map(o => o.textContent)")
    check(vis == ['Spanish'], f'{T} typing narrows the list {vis}')
    await pg.click('.lang-opt[data-lang=spanish]'); await pg.fill('#langPickFind', ''); await pg.wait_for_timeout(200)
    await pg.screenshot(path=f'{SHOTS}/lang-menu-{scheme}.png')
    await pg.click('#langPickDone'); await pg.wait_for_timeout(300)
    r = await pg.evaluate("({ txt: document.getElementById('langPickText').textContent, saved: JSON.parse(localStorage.getItem('radioPlayerLangFilter')), open: !document.getElementById('langPickMenu').hidden })")
    check(r['txt'] == 'Spanish' and r['saved'] == {'mode': 'hide', 'langs': ['spanish'], 'unknown': 'show'} and not r['open'], f'{T} the button names the choice and it is saved {r}')
    await pg.screenshot(path=f'{SHOTS}/lang-settings-{scheme}.png')
    await pg.keyboard.press('Escape'); await pg.wait_for_timeout(300)
    n1 = await disney()
    check(sorted(n1) == sorted(['Disney Hits Radio', 'Radio Disney Brasil', 'Disney Junior Paris', 'Disney Mystery Stream', 'Disney Classics']), f'{T} Exclude Spanish hides labelled, Mexican and Spanish-named stations {n1}')
    # Only English (+ French), unknown hidden
    await pg.evaluate("__lf.ev(\"langFilter.mode='only'; langFilter.langs=['english','french']; langFilter.unknown='hide'; saveLangFilter(); genreStationCache = {}; __langPick.sync(); 0\")")
    n2 = await disney()
    check(sorted(n2) == sorted(['Disney Hits Radio', 'Disney Junior Paris', 'Disney Classics']), f'{T} Only English and French, no-language hidden {n2}')
    await pg.evaluate("__lf.ev(\"langFilter.unknown='show'; saveLangFilter(); genreStationCache = {}; 0\")")
    n3 = await disney()
    check('Disney Mystery Stream' in n3 and len(n3) == 4, f'{T} and with no-language shown {n3}')
    await pg.evaluate("__lf.ev(\"openSettings('radio'); 0\")"); await pg.wait_for_timeout(500)
    r = await pg.evaluate("({ txt: document.getElementById('langPickText').textContent, unk: getComputedStyle(document.getElementById('langUnknownRow')).display, sw: document.documentElement.scrollWidth, vw: innerWidth })")
    check(r['txt'] == 'English, French' and r['unk'] != 'none' and r['sw'] <= r['vw'], f'{T} Only shows the No language listed row; nothing sideways {r}')
    await pg.screenshot(path=f'{SHOTS}/lang-settings-only-{scheme}.png')
    await pg.select_option('#langModeSelect', 'all'); await pg.wait_for_timeout(300)
    await pg.evaluate("document.getElementById('langPickDone') && (!document.getElementById('langPickMenu').hidden) && document.getElementById('langPickDone').click()")
    await pg.keyboard.press('Escape'); await pg.wait_for_timeout(300)
    n4 = await disney()
    check(len(n4) == 7, f'{T} back on All, every station returns ({len(n4)})')
    check(not errs, f'{T} no page errors {errs[:2]}')
    await ctx.close()
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
        await run(b, 'dark', 390); await run(b, 'light', 360)
        await b.close()
    print('FAILS:', fails)
asyncio.run(main())
