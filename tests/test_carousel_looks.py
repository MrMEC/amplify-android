"""Build 643: Card and Editorial carousels + Show heading, at 327 x 709 (dpr 3.3).
Run: python3 tests/test_carousel_looks.py (screenshots in /tmp/claude-0/t/shots)"""
import sys as _nsys, os as _nos; _nsys.path.insert(0, _nos.path.dirname(_nos.path.abspath(__file__))); from notice_auto import AUTO_NOTICE
import asyncio, os, json, io, threading, http.server, functools, shutil
from playwright.async_api import async_playwright
from PIL import Image
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = '/tmp/claude-0/t/srv-looks'; SHOTS = '/tmp/claude-0/t/shots'; PORT = 8878
shutil.rmtree(ROOT, ignore_errors=True); os.makedirs(ROOT); os.makedirs(SHOTS, exist_ok=True)
shutil.copy(os.path.join(HERE, '..', 'www', 'index.html'), ROOT + '/index.html')
H = functools.partial(http.server.SimpleHTTPRequestHandler, directory=ROOT); H.log_message = lambda *a: None
srv = http.server.ThreadingHTTPServer(('127.0.0.1', PORT), H); threading.Thread(target=srv.serve_forever, daemon=True).start()
fails = []
def check(ok, msg):
    print(('PASS ' if ok else 'FAIL ') + msg)
    if not ok: fails.append(msg)
def art(c1, c2):
    im = Image.new('RGB', (300, 300))
    px = im.load()
    for y in range(300):
        t = y / 299
        for x in range(300): px[x, y] = tuple(int(c1[i] * (1 - t) + c2[i] * t) for i in range(3))
    b = io.BytesIO(); im.save(b, 'PNG'); return b.getvalue()
def logo():
    im = Image.new('RGBA', (300, 120), (0, 0, 0, 0)); px = im.load()
    for y in range(30, 90):
        for x in range(20, 280): px[x, y] = (255, 255, 255, 255)
    b = io.BytesIO(); im.save(b, 'PNG'); return b.getvalue()
ARTS = {'e': logo(), 'a': art((20, 160, 150), (30, 120, 190)), 'b': art((240, 120, 40), (190, 30, 80)), 'c': art((230, 220, 180), (245, 240, 225)), 'd': art((60, 40, 120), (20, 10, 50))}
NAMES = [('a', 'R&B Now', 'Apple Music R&B'), ('b', 'Sunset Boulevard Mix Extended Edition', 'Daily Mix'), ('c', 'Tchaikovsky Undiscovered', 'Classical'), ('d', 'Midnight Drive', 'The Night Owls'), ('e', 'Lucha Plus', 'Live TV')]
async def route(r):
    u = r.request.url
    if u.startswith(f'http://127.0.0.1:{PORT}'): return await r.continue_()
    if 'archive.org/services/img/' in u:
        k = u.rsplit('/', 1)[1][:1]
        return await r.fulfill(status=200, content_type='image/png', headers={'access-control-allow-origin': '*'}, body=ARTS.get(k, ARTS['a']))
    return await r.fulfill(status=200, body='{}', content_type='application/json')
HIST = [{'k': 'video:%s.mp4' % k, 'r': 'item', 'it': {'type': 'video', 'id': '%s.mp4' % k, 'uri': 'https://archive.org/download/%s/%s.mp4' % (k, k), 'videoKind': 'archive', 'archive': True, 'name': n, 'favicon': 'https://archive.org/services/img/' + k, 'duration': 3000, 'artist': s}} for k, n, s in NAMES]
SEED = "(function(){ if(!localStorage.getItem('__s')){ localStorage.setItem('__s','1'); localStorage.setItem('radioPlayerPlayedHistory', %s); } })();" % json.dumps(json.dumps(HIST))
async def main():
    async with async_playwright() as p:
        B = await p.chromium.launch()
        c = await B.new_context(viewport={'width': 327, 'height': 709}, device_scale_factor=3.3, is_mobile=True, has_touch=True, color_scheme='dark')
        await c.add_init_script(AUTO_NOTICE); await c.add_init_script(SEED)
        pg = await c.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.route('**/*', route)
        await pg.goto(f'http://127.0.0.1:{PORT}/index.html'); await pg.wait_for_timeout(2500)
        print('slides', await pg.evaluate("document.querySelectorAll('#npHeroTrack > .nph-slide').length"))
        async def look(name, cfg, scroll=0):
            await pg.evaluate("window.ampCarouselSet(%s)" % json.dumps(cfg)); await pg.wait_for_timeout(900)
            if scroll:
                await pg.evaluate("(function(){var t=document.getElementById('npHeroTrack');var sl=t.children[%d];t.scrollTo({left:sl.offsetLeft,behavior:'instant'});})()" % scroll); await pg.wait_for_timeout(700)
            await pg.screenshot(path=f'{SHOTS}/cl-{name}.png')
        for sz in ('l', 'm', 's'):
            await look('card-' + sz, {'mode': 'card', 'size': sz, 'heading': True})
            await look('edit-' + sz, {'mode': 'edit', 'size': sz, 'textPos': 'below', 'heading': True})
        await look('card-logo', {'mode': 'card', 'size': 'm'}, 4)
        await look('edit-above-m', {'mode': 'edit', 'size': 'm', 'textPos': 'above', 'heading': True})
        r = await pg.evaluate("(function(){var h=document.getElementById('npHero').getBoundingClientRect(); var t=document.querySelector('.home-tabs,.featured-home'); return [Math.round(h.height), Math.round(Array.from(document.querySelectorAll('#npHeroTrack > .nph-slide')).reduce(function(m,s){return Math.max(m,s.getBoundingClientRect().height)},0))]})()")
        print('hero/slide heights (edit above, m)', r)
        print('play btn visible', await pg.evaluate("getComputedStyle(document.querySelector('.nph-play')).display"))
        await pg.evaluate("window.ampCarouselSet({mode:'slides',heading:false})")
        await pg.evaluate("__s.open()") if False else None
        print('errs', errs); await B.close()
asyncio.run(main()); print('FAILS', fails)
