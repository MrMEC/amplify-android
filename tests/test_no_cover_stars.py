"""Build 421: no star (favorite) button sits on top of a cover anywhere.
Run: python3 tests/test_no_cover_stars.py"""
import asyncio, json, os, functools, http.server, threading
from playwright.async_api import async_playwright
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.join(HERE, '..', 'www')
H = functools.partial(http.server.SimpleHTTPRequestHandler, directory=ROOT); H.log_message = lambda *a: None
srv = http.server.ThreadingHTTPServer(('127.0.0.1', 8842), H); threading.Thread(target=srv.serve_forever, daemon=True).start()
FAV = [{'name': f'Station {i}', 'homepage': '', 'urlToResolve': f'https://s{i}.example/live', 'stationuuid': f's{i}', 'favicon': '', 'tags': 'pop'} for i in range(6)]
SCAN = """() => { var out = []; document.querySelectorAll('.tile-fav, .row-fav, .fa-heart').forEach(function(b){
  var el = b.closest('button') || b; var cs = getComputedStyle(el); var r = el.getBoundingClientRect();
  if(cs.display === 'none' || cs.visibility === 'hidden' || r.width < 2 || r.height < 2) return;
  var host = el.closest('.tile, .fav-card');
  if(!host || host.classList.contains('song-row')) return;
  var art = host.querySelector('.tile-art, .art, img, [class*=art]'); if(!art) return;
  var a = art.getBoundingClientRect();
  if(r.left < a.right && r.right > a.left && r.top < a.bottom && r.bottom > a.top) out.push(host.className + ' > ' + el.className);
}); return out; }"""
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
        ctx = await b.new_context(viewport={'width': 390, 'height': 844}, device_scale_factor=2, is_mobile=True, has_touch=True, color_scheme='dark')
        await ctx.add_init_script("if(!localStorage.getItem('__s')){ localStorage.setItem('__s','1'); localStorage.setItem('radioPlayerTourSeen','1'); localStorage.setItem('radioPlayerFavorites', %s); }" % repr(json.dumps(FAV)))
        pg = await ctx.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.route('**/*', lambda r: r.continue_() if r.request.url.startswith('http://127.0.0.1') else r.abort())
        await pg.goto('http://127.0.0.1:8842/index.html'); await pg.wait_for_timeout(3000)
        n = await pg.evaluate("document.querySelectorAll('.tile:not(.song-row)').length")
        syn = await pg.evaluate("""() => { var d = document.createElement('div'); d.id='syn'; d.style.cssText='position:fixed;top:100px;left:0;z-index:9999;width:300px;background:#222';
          d.innerHTML = '<div class="tile station-tile"><div class="tile-art" style="width:120px;height:120px"></div><button class="tile-fav"><i class="fa-regular fa-heart"></i></button></div>'
           + '<div class="tile fav-card"><div class="tile-art" style="width:120px;height:120px"></div><button class="tile-fav on"><i class="fa-solid fa-heart"></i></button></div>'
           + '<div class="tile song-row"><div class="song-row-art"></div><button class="tile-fav"><i class="fa-regular fa-heart"></i></button></div>'
           + '<div class="tile station-tile"><div class="tile-art" style="width:120px;height:120px"></div><button class="tile-fav tile-more"><i class="fa-solid fa-ellipsis-vertical"></i></button></div>';
          document.body.appendChild(d); var q = d.querySelectorAll('.tile-fav'); return Array.prototype.map.call(q, function(x){ return getComputedStyle(x).display; }); }""")
        print(('PASS' if syn == ['none','none','flex','flex'] else 'FAIL'), 'tile stars hidden; song-row star and More buttons kept', syn)
        if syn != ['none','none','flex','flex']: raise SystemExit(1)
        await pg.evaluate("document.getElementById('syn').remove()")
        hits = await pg.evaluate(SCAN)
        await pg.screenshot(path='/tmp/claude-0/t/shots/nostars-home.png')
        print(('PASS' if not hits else 'FAIL'), f'no star over a cover on Home ({n} tiles) {hits[:3]}')
        print(('PASS' if not errs else 'FAIL'), 'no page errors', errs[:2])
        await b.close()
        raise SystemExit(1 if hits or errs else 0)
asyncio.run(main())
