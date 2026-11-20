"""Build 700 (Mark): 1) his "Amplify" theme is the app's default (fresh install) and the first preset,
so anyone can get back to it. 2) Live TV logos on the Home carousel (Slides): no blurred repeats of
the logo. Run: python3 tests/test_default_theme_logo_hero.py [tag]"""
import sys as _nsys, os as _nos; _nsys.path.insert(0, _nos.path.dirname(_nos.path.abspath(__file__))); from notice_auto import AUTO_NOTICE
import asyncio, os, json, threading, http.server, functools, shutil, sys
from playwright.async_api import async_playwright
TAG = sys.argv[1] if len(sys.argv) > 1 else 'new'
PORT = 8899
root = '/tmp/claude-0/t/srv_dth'; shots = '/tmp/claude-0/t/shots'; os.makedirs(shots, exist_ok=True)
shutil.rmtree(root, ignore_errors=True); os.makedirs(root)
HOOK = "window.__t = { ev: function(js){ return eval(js); } };\n"
_src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'www', 'index.html')).read()
_mark = '  var coverFlow = null;\n'; assert _src.count(_mark) == 1
open(root + '/index.html', 'w').write(_src.replace(_mark, _mark + HOOK))
for f in ('logo1.png', 'logo2.png'):
    if os.path.exists('/tmp/t/logos/' + f): shutil.copy('/tmp/t/logos/' + f, root + '/' + f)
class Q(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a): pass
srv = http.server.ThreadingHTTPServer(('127.0.0.1', PORT), functools.partial(Q, directory=root))
threading.Thread(target=srv.serve_forever, daemon=True).start()
B = f'http://127.0.0.1:{PORT}/'
import base64
LOGO = lambda f: 'data:image/png;base64,' + base64.b64encode(open('/tmp/t/logos/' + f, 'rb').read()).decode()
CH = [{'name': '7 - WXYZ 7 Springfield', 'url': 'https://tv.example/wxyz.m3u8', 'videoChannel': True, 'favicon': LOGO('logo1.png'), 'stationuuid': 'ch-wxyz'},
      {'name': 'MORNING All Day', 'url': 'https://tv.example/morning.m3u8', 'videoChannel': True, 'favicon': LOGO('logo2.png'), 'stationuuid': 'ch-morn'},
      {'name': 'NEWS Now', 'url': 'https://tv.example/news.m3u8', 'videoChannel': True, 'favicon': LOGO('logo3.png'), 'stationuuid': 'ch-news'}]
fails = []
def check(c, m):
    print(('PASS ' if c else 'FAIL ') + m)
    if not c: fails.append(m)
async def ctx_page(b, scheme, seed):
    ctx = await b.new_context(viewport={'width': 327, 'height': 700}, device_scale_factor=3.3, is_mobile=True, has_touch=True, color_scheme=scheme)
    await ctx.add_init_script(AUTO_NOTICE)
    await ctx.add_init_script("try{ localStorage.setItem('radioPlayerTourDone','1'); %s }catch(e){}" % seed)
    pg = await ctx.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
    await pg.route('**/*', lambda r: r.continue_() if '127.0.0.1' in r.request.url else r.fulfill(status=200, content_type='application/json', body='[]') if '/json/' in r.request.url else r.abort())
    await pg.goto(B + 'index.html'); await pg.wait_for_timeout(2500)
    return ctx, pg, errs
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
        # 1) fresh install
        ctx, pg, errs = await ctx_page(b, 'light', '')
        st = await pg.evaluate("""()=>({ amoled: localStorage.getItem('radioPlayerAmoled'), accent: localStorage.getItem('radioPlayerCustomAccent'), shape: localStorage.getItem('radioPlayerShape'),
            car: localStorage.getItem('radioPlayerCarousel'), font: localStorage.getItem('radioPlayerFont'), theme: localStorage.getItem('radioPlayerTheme'),
            acc: getComputedStyle(document.documentElement).getPropertyValue('--accent').trim() })""")
        print('fresh', st)
        if TAG == 'new':
            check(st['amoled'] == 'on' and '#d10003' in (st['accent'] or '') and '#4aa8ff' in (st['accent'] or ''), 'fresh install: AMOLED on, accent red (light) / blue (dark)')
            check('"density":"roomy"' in (st['shape'] or '') and '"play":"rounded"' in (st['shape'] or ''), 'fresh install: roomy, rounded play buttons')
            check('"mode":"slides"' in (st['car'] or '') and '"heading":true' in (st['car'] or ''), 'fresh install: Slides carousel with its heading')
            check(st['acc'].lower() == '#d10003', 'light theme accent is #d10003 (%s)' % st['acc'])
            chips = await pg.evaluate("[...document.querySelectorAll('#themePresetGrid .th-chip')].map(b=>b.textContent+':'+b.getAttribute('aria-pressed'))")
            print(chips[:3])
            check(chips and chips[0] == 'Amplify (Default):true', 'first preset is Amplify (Default), and it is the one in use')
            # change a setting, then go back
            await pg.evaluate("__t.ev(\"thApply(JSON.parse(JSON.stringify(THEME_PRESETS[2].s)))\")"); await pg.wait_for_timeout(300)
            off = await pg.evaluate("document.querySelector('#themePresetGrid .th-chip').getAttribute('aria-pressed')")
            await pg.evaluate("document.querySelector('#themePresetGrid .th-chip').click()"); await pg.wait_for_timeout(400)
            on = await pg.evaluate("document.querySelector('#themePresetGrid .th-chip').getAttribute('aria-pressed')")
            acc = await pg.evaluate("getComputedStyle(document.documentElement).getPropertyValue('--accent').trim()")
            check(off == 'false' and on == 'true' and acc.lower() == '#d10003', 'after another theme, Amplify (Default) brings the default back')
        check(not errs, 'no page errors %s' % errs[:2])
        await ctx.close()
        # 2) an existing user's settings are left alone
        if TAG == 'new':
            ctx, pg, errs = await ctx_page(b, 'dark', "localStorage.setItem('radioPlayerTheme','dark'); localStorage.setItem('radioPlayerCustomAccent', JSON.stringify({dark:'#00ff00'}));")
            st = await pg.evaluate("[localStorage.getItem('radioPlayerAmoled'), localStorage.getItem('radioPlayerCustomAccent')]")
            check(st[0] is None and '#00ff00' in st[1], 'existing settings are not replaced %s' % st)
            await ctx.close()
        # 3) logo hero
        for scheme in ('light', 'dark'):
            seed = "localStorage.setItem('radioPlayerRecent', %s);" % json.dumps(json.dumps(CH))
            ctx, pg, errs = await ctx_page(b, scheme, seed)
            await pg.wait_for_timeout(1500)
            for i in range(3):
                await pg.evaluate("(i)=>__t.ev('heroScrollTo('+i+', false)')", i); await pg.wait_for_timeout(900)
                await pg.screenshot(path=f'{shots}/dth-{TAG}-{scheme}-{i}.png', clip={'x': 0, 'y': 0, 'width': 327, 'height': 480})
            if TAG == 'new':
                r = await pg.evaluate("""()=>{ var s = __t.ev('heroSlides')[0]; var cs = getComputedStyle(s.querySelector('.nph-bg')), cm = getComputedStyle(s.querySelector('.nph-refl'));
                   var img = s.querySelector('.nph-art img'); return { logo: s.classList.contains('nph-logo'), bg: cs.display, mid: cm.display, fit: img && getComputedStyle(img).objectFit, c: s.style.getPropertyValue('--nph-logo-c') }; }""")
                print(scheme, r)
                check(r['logo'] and r['bg'] == 'none' and r['mid'] == 'none' and r['fit'] == 'contain', f'[{scheme}] a Live TV logo shows once, whole, with no blurred copies')
                check(r['c'].startswith('hsl('), f'[{scheme}] the card takes its colour from the logo ({r["c"]})')
                pale = await pg.evaluate("__t.ev('heroSlides').map(s=>s.classList.contains('nph-logo-pale'))")
                check(pale == [False, False, True], f'[{scheme}] only the white logo goes without the light glow {pale}')
            check(not errs, 'no page errors %s' % errs[:2])
            await ctx.close()
        await b.close()
asyncio.run(main())
print('FAILED: %d' % len(fails) if fails else 'ALL PASS')
raise SystemExit(1 if fails else 0)
