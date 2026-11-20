"""Build 701 (Mark): Editorial carousel -- option A (above the cover: words line up, logos on a tile in
their own colours) and option C as a new Style setting (Framed card). Run: python3 tests/test_edit_above_framed.py [tag]"""
import sys as _nsys, os as _nos; _nsys.path.insert(0, _nos.path.dirname(_nos.path.abspath(__file__))); from notice_auto import AUTO_NOTICE
import asyncio, os, json, threading, http.server, functools, shutil, sys, base64
from playwright.async_api import async_playwright
TAG = sys.argv[1] if len(sys.argv) > 1 else 'new'
PORT = 8900
root = '/tmp/claude-0/t/srv_eaf'; shots = '/tmp/claude-0/t/shots'; os.makedirs(shots, exist_ok=True)
shutil.rmtree(root, ignore_errors=True); os.makedirs(root)
HOOK = "window.__t = { ev: function(js){ return eval(js); } };\n"
_src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'www', 'index.html')).read()
_mark = '  var coverFlow = null;\n'; assert _src.count(_mark) == 1
open(root + '/index.html', 'w').write(_src.replace(_mark, _mark + HOOK))
class Q(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a): pass
srv = http.server.ThreadingHTTPServer(('127.0.0.1', PORT), functools.partial(Q, directory=root))
threading.Thread(target=srv.serve_forever, daemon=True).start()
B = f'http://127.0.0.1:{PORT}/'
def D(f, t='png'): return f'data:image/{t};base64,' + base64.b64encode(open('/tmp/t/logos/' + f, 'rb').read()).decode()
REC = [{'name': '2 - WXYZ 7 Springfield', 'url': 'https://tv.example/wxyz.m3u8', 'videoChannel': True, 'favicon': D('logo1.png'), 'stationuuid': 'ch-wxyz'},
       {'name': '1. Parkland Theme Park Highlights', 'url': 'https://tv.example/park.m3u8', 'videoChannel': True, 'favicon': D('logo4.png'), 'stationuuid': 'ch-park'},
       {'name': 'Chill Out Radio', 'url': 'https://radio.example/chill', 'favicon': D('photo1.jpg', 'jpeg'), 'stationuuid': 'st-chill'},
       {'name': 'NEWS Now', 'url': 'https://tv.example/news.m3u8', 'videoChannel': True, 'favicon': D('logo3.png'), 'stationuuid': 'ch-news'}]
fails = []
def check(c, m):
    print(('PASS ' if c else 'FAIL ') + m)
    if not c: fails.append(m)
GEO = """()=>{ var sl = __t.ev('heroSlides'); return sl.slice(0, 3).map(function(s){ var r = function(q){ var e = s.querySelector(q); var b = e.getBoundingClientRect(); return Math.round(b.top); };
   var m = s.querySelector('.nph-media'); return { kicker: r('.nph-kicker'), media: r('.nph-media'), title: r('.nph-title'), logo: s.classList.contains('nph-logo'), solid: s.classList.contains('nph-logo-solid'),
     mbg: getComputedStyle(m).backgroundImage.slice(0, 20), sbg: getComputedStyle(s).backgroundColor, c: s.style.getPropertyValue('--nph-logo-c') }; }); }"""
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
        for scheme in ('light', 'dark'):
            for pos in ('above', 'below'):
                for frame in ((False, True) if TAG == 'new' else (False,)):
                    car = {'mode': 'edit', 'size': 's', 'tilt': 66, 'reflect': True, 'textPos': pos, 'heading': True, 'cardSize': 's', 'frame': frame}
                    seed = "localStorage.setItem('radioPlayerRecent', %s); localStorage.setItem('radioPlayerCarousel', %s); localStorage.setItem('radioPlayerTheme', %s); localStorage.setItem('radioPlayerCustomAccent', JSON.stringify({dark:'#4aa8ff', light:'#d10003'}));" % (json.dumps(json.dumps(REC)), json.dumps(json.dumps(car)), json.dumps(scheme))
                    ctx = await b.new_context(viewport={'width': 327, 'height': 700}, device_scale_factor=3.3, is_mobile=True, has_touch=True, color_scheme=scheme)
                    await ctx.add_init_script(AUTO_NOTICE)
                    await ctx.add_init_script("try{ localStorage.setItem('radioPlayerTourDone','1'); %s }catch(e){}" % seed)
                    pg = await ctx.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
                    await pg.route('**/*', lambda r: r.continue_() if '127.0.0.1' in r.request.url else r.fulfill(status=200, content_type='application/json', body='[]') if '/json/' in r.request.url else r.abort())
                    await pg.goto(B + 'index.html'); await pg.wait_for_timeout(3000)
                    tag = f'{TAG}-{scheme}-{pos}-{"framed" if frame else "plain"}'
                    await pg.screenshot(path=f'{shots}/eaf-{tag}.png', clip={'x': 0, 'y': 0, 'width': 327, 'height': 470})
                    await pg.evaluate("__t.ev('heroScrollTo(1, false)')"); await pg.wait_for_timeout(1200)
                    g = await pg.evaluate(GEO); print(tag, g)
                    await pg.evaluate("__t.ev('heroScrollTo(0, false)')"); await pg.wait_for_timeout(300)
                    if TAG == 'new':
                        T = f'[{scheme} {pos} {"framed" if frame else "plain"}]'
                        if pos == 'above':
                            check(len({x['kicker'] for x in g}) == 1 and len({x['media'] for x in g}) == 1, f'{T} labels and covers line up across slides {[(x["kicker"], x["media"]) for x in g]}')
                            check(g[0]['kicker'] - 0 < 140, f'{T} no big gap over the first slide (label at {g[0]["kicker"]})')
                        check(g[0]['logo'] and 'gradient' in g[0]['mbg'], f'{T} a channel logo sits on a tile in its own colours')
                        check(g[1]['solid'], f'{T} a logo that is a solid picture fills its tile')
                        if frame:
                            check(all(x['sbg'] not in ('rgba(0, 0, 0, 0)', '') for x in g) and all(x['c'].startswith('hsl(') for x in g), f'{T} every card is framed in its cover colour {[x["c"] for x in g]}')
                            chip = await pg.evaluate("__t.ev('thCarSig(thCarouselNow())')")
                            check(chip.endswith('framed,h'), f'{T} the style is part of a saved theme ({chip})')
                    check(not errs, f'no page errors {errs[:2]}')
                    await ctx.close()
        await b.close()
asyncio.run(main())
print('FAILED: %d' % len(fails) if fails else 'ALL PASS')
raise SystemExit(1 if fails else 0)
