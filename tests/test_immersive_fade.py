"""Build 143, Immersive View: a shade of the page's colour rises from the bottom of the screen
and hides "More from" (not outside Immersive View); the artwork zooms further, and each cycle
takes a random move (push, turn or sway) with a small rotation that never shows a corner.
Run: python3 tests/test_immersive_fade.py (screenshots in /tmp/claude-0/t/shots)"""
import asyncio, os, io, re, math
HERE = os.path.dirname(os.path.abspath(__file__))
src = open(os.path.join(HERE, 'test_immersive.py')).read()
pre = src[:src.rindex('\nasync def main()')]
pre = pre.replace("'/tmp/claude-0/t/srv_imm'", "'/tmp/claude-0/t/srv_immf'").replace("'PORT = 8796'", "'PORT = 8809'")
exec(pre)
PORT = 8809
from playwright.async_api import async_playwright
from PIL import Image

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
        ctx = await b.new_context(viewport={'width': 390, 'height': 844}, device_scale_factor=2, is_mobile=True, has_touch=True, color_scheme='dark')
        await ctx.add_init_script(MOCK)
        pg = await ctx.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.route('**/*', lambda route: route.continue_() if '127.0.0.1' in route.request.url else route.abort())
        await pg.goto(f'http://127.0.0.1:{PORT}/index.html'); await pg.wait_for_timeout(2500)
        await pg.evaluate("""(function(){ var ov=document.getElementById('addMusicOverlay'); if(ov) ov.classList.add('open');
          var btn=document.getElementById('addMusicFolderBtn'); btn.disabled=false; btn.click(); })()""")
        for _ in range(60):
            await pg.wait_for_timeout(500)
            if len(await pg.evaluate('__t.tracks()')) >= 3: break
        await pg.evaluate('__t.setup()')
        async def tap_art():
            box = await pg.locator('#npArtWrap').bounding_box()
            await pg.touchscreen.tap(box['x'] + box['width'] / 2, box['y'] + box['height'] * 0.35)
        await pg.evaluate("__t.songs(); setTimeout(function(){ document.querySelector('#stationsGrid .song-row:not(.shuffle-all-row)').click(); }, 300)")
        await pg.wait_for_timeout(700)
        await pg.evaluate('__t.openNp()'); await pg.wait_for_timeout(1200)
        await pg.evaluate("__t.ui(true)")

        INFO = """(()=>{ var f = document.querySelector('#nowPlayingScreen .np-imm-fade'), c = getComputedStyle(f), r = f.getBoundingClientRect();
          var hs = Array.from(document.querySelectorAll('#nowPlayingScreen .np-related')).filter(function(e){ return e.offsetParent; });
          var h = hs.length ? hs[0].querySelector('.np-related-heading') : null, hb = h ? h.getBoundingClientRect() : null;
          var play = document.querySelector('#nowPlayingScreen .np-controls').getBoundingClientRect();
          return { op: +c.opacity, vis: c.visibility, top: r.top, bottom: r.bottom, H: innerHeight, pe: c.pointerEvents,
            heading: h ? h.textContent : null, hTop: hb && hb.top, hBottom: hb && hb.bottom, hLeft: hb && hb.left, hRight: hb && hb.right,
            ctrlBottom: play.bottom, tint: getComputedStyle(document.getElementById('nowPlayingScreen')).getPropertyValue('--np-tint').trim() }; })()"""

        def region_contrast(png, box):
            im = Image.open(io.BytesIO(png)).convert('L')
            x0, y0, x1, y1 = [int(v * 2) for v in box]
            px = list(im.crop((x0, y0, x1, y1)).getdata())
            px.sort()
            return px[int(len(px) * .98)] - px[int(len(px) * .02)]

        SEAMOFF = "(function(o){ document.querySelector('#nowPlayingScreen .np-imm-fade').style.display = o ? 'none' : ''; document.querySelector('#nowPlayingScreen .np-below').style.visibility = o ? 'hidden' : ''; })"
        async def seam(tag):
            # with the motion held still: the fade over the page vs the page with no fade and no list
            a = Image.open(io.BytesIO(await pg.screenshot())).convert('RGB')
            await pg.evaluate(SEAMOFF + "(true)"); await pg.wait_for_timeout(150)
            bb = Image.open(io.BytesIO(await pg.screenshot())).convert('RGB')
            await pg.evaluate(SEAMOFF + "(false)")
            box = (0, int(844 * 2 * .80), 780, 844 * 2)
            pa, pb = list(a.crop(box).resize((39, 17)).getdata()), list(bb.crop(box).resize((39, 17)).getdata())
            d = sum(abs(pa[k][c] - pb[k][c]) for k in range(len(pa)) for c in range(3)) / (len(pa) * 3)
            return d
        n0 = await pg.evaluate(INFO)
        print(n0)
        check(n0['heading'] and n0['hTop'] is not None and n0['hTop'] < n0['H'], f"the 'More from' heading is on screen in normal view {n0}")
        check(n0['op'] == 0 and n0['vis'] == 'hidden', f'no shade outside Immersive View {n0}')
        hbox = (max(0, n0['hLeft']), n0['hTop'], min(390, n0['hLeft'] + 160), n0['hBottom'])
        png0 = await pg.screenshot(); await pg.screenshot(path=f'{shots}/imm-fade-off.png')
        c0 = region_contrast(png0, hbox)

        await tap_art(); await pg.wait_for_timeout(2500)
        n1 = await pg.evaluate(INFO)
        print(n1)
        check(n1['op'] == 1 and n1['vis'] == 'visible' and n1['pe'] == 'none', f'Immersive View: the shade is up and lets taps through {n1}')
        check(abs(n1['bottom'] - n1['H']) < 1 and n1['top'] < n1['hTop'], f'it runs from above the heading to the bottom of the screen {n1}')
        check(n1['top'] > n1['ctrlBottom'] - 90, f'and starts low enough to leave the controls clear {n1}')
        await pg.evaluate("document.querySelectorAll('#nowPlayingScreen .np-imm-fade')[0].style.transition='none'")
        png1 = await pg.screenshot(); await pg.screenshot(path=f'{shots}/imm-fade-on.png')
        c1 = region_contrast(png1, (hbox[0], n1['hTop'], hbox[2], n1['hBottom']))
        check(c0 > 60 and c1 < 6, f"'More from' is readable in normal view (contrast {c0}) and hidden in Immersive View (contrast {c1})")
        d = await seam('song')
        check(d < 4, f'the bottom of the screen matches the page behind it (no visible edge): mean difference {d:.1f}')

        # the artwork: a deeper zoom, random moves, small rotations that never show a corner
        PATH = """(()=>{ var a = document.getElementById('npArt').getAnimations().filter(function(a){ return a.effect.getKeyframes().some(function(k){ return k.transform; }); });
          if(a.length !== 1) return { n: a.length };
          var kf = a[0].effect.getKeyframes().map(function(k){ return k.transform; });
          return { n: 1, kind: document.getElementById('npArt').dataset.immPath, kf: kf, iters: a[0].effect.getTiming().iterations, dir: a[0].effect.getTiming().direction, dur: a[0].effect.getTiming().duration }; })()"""
        kinds, maxS, maxR, bad = set(), 0, 0, []
        first = await pg.evaluate(PATH)
        print(first)
        check(first['n'] == 1 and first['iters'] == 2 and first['dir'] == 'alternate', f'one animation, in and back out per cycle {first}')
        check(first['kf'][0] == 'translate3d(0%, 0%, 0px) rotate(0deg) scale(1)' or 'scale(1)' in first['kf'][0], f"each cycle starts and ends at rest {first['kf'][0]}")
        for i in range(14):
            pth = await pg.evaluate(PATH)
            check(pth['n'] == 1, f'cycle {i}: still exactly one art animation')
            kinds.add(pth['kind'])
            for t in pth['kf']:
                tx, ty = [float(v) for v in re.findall(r'translate3d\(([-\d.]+)%, ([-\d.]+)%', t)[0]]
                r = float(re.findall(r'rotate\(([-\d.]+)deg', t)[0]); s = float(re.findall(r'scale\(([-\d.]+)\)', t)[0])
                maxS = max(maxS, s); maxR = max(maxR, abs(r))
                need = math.cos(math.radians(abs(r))) + math.sin(math.radians(abs(r))) + 2 * max(abs(tx), abs(ty)) / 100
                if s + 1e-6 < need and not (s == 1 and r == 0 and tx == 0 and ty == 0): bad.append((t, need))
            # jump to the end of this cycle: the next one starts with a fresh random move
            await pg.evaluate("(function(){ var a = document.getElementById('npArt').getAnimations().filter(function(a){ return a.effect.getKeyframes().some(function(k){ return k.transform; }); })[0]; a.currentTime = 2 * a.effect.getTiming().duration - 5; })()")
            await pg.wait_for_timeout(120)
        print(kinds, maxS, maxR)
        check(len(kinds) >= 2 and kinds <= {'push', 'turn', 'sway'}, f'the moves change at random from cycle to cycle {kinds}')
        check(maxS >= 1.26, f'zooms further than before (1.16): up to {maxS}')
        check(1.5 <= maxR <= 4.01, f'subtle rotation, a few degrees at most: {maxR}')
        check(not bad, f'the cover always overfills its frame (no corner shows) {bad[:3]}')
        await pg.evaluate("__t.ui(true)")
        await pg.wait_for_timeout(5000)
        await pg.screenshot(path=f'{shots}/imm-fade-motion.png')

        # a station with artwork: the moving wash shows in the fade too
        import subprocess as _sp
        _sp.run(['ffmpeg', '-loglevel', 'error', '-y', '-f', 'lavfi', '-i', 'testsrc2=s=300x300', '-frames:v', '1', f'{root}/cov1.png'], check=True)
        async def covers(route):
            await route.fulfill(status=200, content_type='image/png', body=open(f'{root}/' + route.request.url.rsplit('/', 1)[1], 'rb').read())
        await pg.route('https://covers.example/**', covers)
        await pg.evaluate("__t.play({ stationuuid: 'st-c1', name: 'Cover One', url: 'http://radio.example/c1', urlToResolve: 'http://radio.example/c1', favicon: 'http://covers.example/cov1.png', tags: '' })")
        await pg.wait_for_timeout(900); await pg.evaluate("__t.ui(true)"); await pg.wait_for_timeout(4200)
        W = """(()=>{ var f = document.getElementById('npImmFadeWash'), c = document.querySelector('canvas.np-imm-bg');
          return { op: +getComputedStyle(f).opacity, ft: f.dataset.t, wt: c && c.dataset.t, fw: f.width, fh: f.height, cw: c && c.width, ch: c && c.height,
            fr: f.getBoundingClientRect().top, fb: f.getBoundingClientRect().bottom, cr: c && c.getBoundingClientRect().top, cb: c && c.getBoundingClientRect().bottom }; })()"""
        w1 = await pg.evaluate(W); print(w1)
        check(w1['wt'] is not None and w1['op'] == 1 and w1['ft'] == w1['wt'] and w1['fw'] == w1['cw'] and w1['fh'] == w1['ch'], f'the fade carries the wash, frame for frame {w1}')
        check(abs(w1['fr'] - w1['cr']) < 2 and abs(w1['fb'] - w1['cb']) < 2, f'lined up with the wash behind it {w1}')
        await pg.screenshot(path=f'{shots}/imm-fade-wash1.png')
        async def low():
            im = Image.open(io.BytesIO(await pg.screenshot())).convert('RGB').resize((39, 84))
            px = [im.getpixel((x, y)) for x in range(39) for y in range(72, 84)]
            return tuple(sum(p[q] for p in px) / len(px) for q in range(3))
        l1 = await low(); await pg.wait_for_timeout(3500); l2 = await low(); await pg.wait_for_timeout(3500); l3 = await low()
        await pg.screenshot(path=f'{shots}/imm-fade-wash2.png')
        dl = max(max(abs(l1[q] - l2[q]) for q in range(3)), max(abs(l2[q] - l3[q]) for q in range(3)))
        check(dl > 3, f'the colours at the very bottom keep shifting ({l1} -> {l2} -> {l3}, {dl:.1f})')
        w2 = await pg.evaluate(W)
        check(w2['ft'] != w1['ft'] and w2['ft'] == w2['wt'], f'and still in step with the wash {w2["ft"]} {w2["wt"]}')
        await pg.evaluate("__t.ui(false)"); await pg.wait_for_timeout(3600)
        d2 = await seam('wash')
        check(d2 < 4, f'with the wash, the fade matches the page behind it: mean difference {d2:.1f}')
        await pg.evaluate("__t.ui(true)")

        # leaving Immersive View takes the shade away again
        await tap_art(); await pg.wait_for_timeout(900)
        n2 = await pg.evaluate(INFO)
        check(n2['op'] == 0 and n2['vis'] == 'hidden', f'out of Immersive View the shade is gone {n2}')
        check(not errs, f'no page errors {errs[:3]}')
        await b.close()
    print('ALL PASSED' if not fails else f'FAILED {fails}')

asyncio.run(main())
