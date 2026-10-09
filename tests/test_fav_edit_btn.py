"""Build 176: the Favorites page's Edit button (#favPageEditBtn) shows only on the Favorites page.
Mark saw its pencil left on My Library and Watch after visiting Favorites (switching tabs didn't
clear it). Also checks Edit / Done still work on the Favorites page.
Run: python3 tests/test_fav_edit_btn.py"""
import asyncio, os, json, shutil, threading, http.server, functools
from playwright.async_api import async_playwright
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = '/tmp/claude-0/t/srv-favedit'; PORT = 8818
os.makedirs(ROOT, exist_ok=True)
shutil.copy(os.path.join(HERE, '..', 'www', 'index.html'), ROOT)
H = functools.partial(http.server.SimpleHTTPRequestHandler, directory=ROOT); H.log_message = lambda *a: None
srv = http.server.ThreadingHTTPServer(('127.0.0.1', PORT), H); threading.Thread(target=srv.serve_forever, daemon=True).start()
MOCK = """(function(){ var P=new Proxy({}, {get:function(t,k){ if(k==='then') return undefined;
 if(k==='addListener') return function(){ return Promise.resolve({remove:function(){}}); };
 return function(){ return Promise.resolve({}); }; }});
 window.Capacitor={isNativePlatform:function(){return true;},getPlatform:function(){return 'android';},Plugins:{AmplifyPlayer:P},convertFileSrc:function(u){return u;}}; })();"""
FAVS = [{'name': n, 'urlToResolve': f'https://s{i}.example/live', 'url_resolved': f'https://s{i}.example/live', 'stationuuid': f'u{i}', 'favicon': '', 'tags': 'jazz', 'country': 'US'}
        for i, n in enumerate(['One FM', 'Two FM', 'Three FM'])]
fails = []
def check(ok, msg):
    print(('PASS ' if ok else 'FAIL ') + msg)
    if not ok: fails.append(msg)
VIS = "(()=>{ var b=document.getElementById('favPageEditBtn'); return !!(b.offsetParent && getComputedStyle(b).display!=='none'); })()"

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
        ctx = await b.new_context(viewport={'width': 412, 'height': 900}, device_scale_factor=2, is_mobile=True, has_touch=True, color_scheme='dark')
        await ctx.add_init_script(MOCK)
        await ctx.add_init_script("if(!localStorage.getItem('radioPlayerFavorites')) localStorage.setItem('radioPlayerFavorites', %s);" % repr(json.dumps(FAVS)))
        pg = await ctx.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.route('**/*', lambda r: r.continue_() if '127.0.0.1' in r.request.url else r.abort())
        await pg.goto(f'http://127.0.0.1:{PORT}/index.html'); await pg.wait_for_timeout(2500)
        async def fav_page():
            await pg.evaluate("document.querySelector('.mobile-nav-btn[data-nav=home]').click()"); await pg.wait_for_timeout(700)
            await pg.evaluate("document.getElementById('favoritesHeading').click()"); await pg.wait_for_timeout(800)
        await fav_page()
        check(await pg.evaluate(VIS), 'the Favorites page shows Edit')
        await pg.evaluate("document.getElementById('favPageEditBtn').click()"); await pg.wait_for_timeout(500)
        st = await pg.evaluate("[document.getElementById('favPageEditBtn').textContent.trim(), document.querySelectorAll('#stationsGrid .row-drag-handle').length]")
        check(st[0] == 'Done' and st[1] == 3, f'Edit turns on editing (Done, grips) {st}')
        await pg.evaluate("document.getElementById('favPageEditBtn').click()"); await pg.wait_for_timeout(500)
        st = await pg.evaluate("document.getElementById('favPageEditBtn').textContent.trim()")
        check(st == 'Edit', f'Done ends it {st}')
        for tab in ['library', 'video', 'podcasts']:
            await fav_page()
            await pg.evaluate("document.querySelector('.mobile-nav-btn[data-nav=%s]').click()" % tab); await pg.wait_for_timeout(900)
            check(not await pg.evaluate(VIS), f'leaving Favorites for {tab}: no Edit pencil there')
        # left while editing: comes back not editing
        await fav_page()
        await pg.evaluate("document.getElementById('favPageEditBtn').click()"); await pg.wait_for_timeout(400)
        await pg.evaluate("document.querySelector('.mobile-nav-btn[data-nav=library]').click()"); await pg.wait_for_timeout(800)
        check(not await pg.evaluate(VIS), 'left while editing: gone from My Library')
        await fav_page()
        st = await pg.evaluate("[document.getElementById('favPageEditBtn').textContent.trim(), document.querySelectorAll('#stationsGrid .row-drag-handle').length]")
        check(st[0] == 'Edit' and st[1] == 0, f'and Favorites opens again not editing {st}')
        check(not errs, f'no page errors {errs[:3]}')
        await b.close()
    print('ALL PASSED' if not fails else f'FAILED {fails}')
asyncio.run(main())
