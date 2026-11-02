"""Build 429: leaving a genre page before its late podcast list arrives must not repaint it
over the Library (the Library tabs went missing). Run: python3 tests/test_genre_leave.py [base]"""
import asyncio, os, shutil, sys, subprocess, threading, http.server, functools
from playwright.async_api import async_playwright
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = '/tmp/claude-0/t/srv-gl'; SHOTS = '/tmp/claude-0/t/shots'
shutil.rmtree(ROOT, ignore_errors=True); os.makedirs(ROOT); os.makedirs(SHOTS, exist_ok=True)
html = subprocess.check_output(['git', 'show', 'HEAD:www/index.html'], cwd=HERE).decode() if (len(sys.argv) > 1 and sys.argv[1] == 'base') else open(os.path.join(HERE, '..', 'www', 'index.html')).read()
mark = '  function searchByTag(tag){'
html = html.replace(mark, """  window.__gl = { open: function(t){ searchByTag(t); }, lib: function(){ openMyLibraryHome(); },
    stub: function(){ apiFetch = function(){ return Promise.resolve([]); }; window.__late = null; itunesSearchPodcasts = function(){ return new Promise(function(r){ window.__late = function(){ r([{ collectionId: 1, collectionName: 'Disney Pod', artistName: 'Disney', artworkUrl600: '' }]); }; }); }; },
    late: function(){ window.__late && window.__late(); } };
""" + mark, 1)
open(ROOT + '/index.html', 'w').write(html)
H = functools.partial(http.server.SimpleHTTPRequestHandler, directory=ROOT); H.log_message = lambda *a: None
srv = http.server.ThreadingHTTPServer(('127.0.0.1', 8844), H); threading.Thread(target=srv.serve_forever, daemon=True).start()
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
        ctx = await b.new_context(viewport={'width': 390, 'height': 844}, device_scale_factor=2, is_mobile=True, has_touch=True, color_scheme='dark')
        await ctx.add_init_script("localStorage.setItem('radioPlayerTourSeen','1')")
        pg = await ctx.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.route('**/*', lambda r: r.continue_() if r.request.url.startswith('http://127.0.0.1') else r.abort())
        await pg.goto('http://127.0.0.1:8844/index.html'); await pg.wait_for_timeout(2500)
        await pg.evaluate("window.__gl.stub(); window.__gl.open('Disney')"); await pg.wait_for_timeout(500)
        await pg.evaluate("window.__gl.lib()"); await pg.wait_for_timeout(800)
        await pg.evaluate("window.__gl.late()"); await pg.wait_for_timeout(800)
        st = await pg.evaluate("({ tabs: !!document.querySelector('.lib-tabs'), on: document.body.classList.contains('lib-tabs-on'), genre: document.body.classList.contains('genre-open'), gp: !!document.querySelector('.gp-hero') })")
        await pg.screenshot(path=f'{SHOTS}/genre-leave.png')
        ok = st['tabs'] and st['on'] and not st['genre'] and not st['gp'] and not errs
        print(('PASS' if ok else 'FAIL'), 'the Library keeps its tabs after a late genre result', st, errs[:1])
        await b.close(); raise SystemExit(0 if ok else 1)
asyncio.run(main())
