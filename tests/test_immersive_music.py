"""Build 320, Immersive View moves with the music: the phone's audio meter ('meter' events, rows of
[ms until heard, level, band0..band8]) drives a glow where the artwork dissolves (swelling with the
bass, flaring on beats), sparks (burst on beats, rising with the highs) and a small beat kick on the
artwork; the artwork tilts in 3D with the gyroscope (deviceorientation) or the mouse, with a sheen.
Asked for only while Immersive View is up (setMeter on/off); pausing eases it down; nothing with
Remove animations; a calm breath without meter data.
Run: python3 tests/test_immersive_music.py (screenshots in /tmp/claude-0/t/shots)"""
import sys as _nsys, os as _nos; _nsys.path.insert(0, _nos.path.dirname(_nos.path.abspath(__file__))); from notice_auto import AUTO_NOTICE
import asyncio, os, re, sys
HERE = os.path.dirname(os.path.abspath(__file__))
src = open(os.path.join(HERE, 'test_immersive.py')).read()
pre = src[:src.rindex('\nasync def main()')]
pre = pre.replace("'/tmp/claude-0/t/srv_imm'", "'/tmp/claude-0/t/srv_immm'").replace("'PORT = 8796'", "'PORT = 8865'")
exec(pre)
MOCK = MOCK.replace('setVideoUi: function(o){', 'setMeter: function(o){ (window.__meter = window.__meter || []).push(!!o.on); return Promise.resolve({}); }, setVideoUi: function(o){')
MOCK = MOCK.replace(" function emit(n, ev){ (listeners[n] || []).forEach(function(f){ try{ f(ev); }catch(e){} }); }",
                    " function emit(n, ev){ (listeners[n] || []).forEach(function(f){ try{ f(ev); }catch(e){} }); } window.__emit = emit;")
assert '__meter' in MOCK and '__emit' in MOCK and PORT == 8865
from playwright.async_api import async_playwright
import subprocess

# A fake song at 120 bpm: every 500ms a bass hit, hi-hats in between. Rows are sent every 100ms,
# 23ms apart, each due 150ms+ after it arrives (like the phone, which measures ahead of the speaker).
MUSIC = """(function(loud){ clearInterval(window.__mus); var t0 = performance.now(), sent = 0;
  window.__mus = setInterval(function(){ var now = performance.now() - t0, rows = [];
    while(sent * 23 < now + 100){ var at = sent * 23, ph = (at % 500) / 500, hat = ((at + 250) % 250) / 250;
      var bass = loud ? (ph < .08 ? 92 : 58 - ph * 12) : 30, high = loud ? (hat < .1 ? 70 : 40) : 22;
      rows.push([Math.round(at - now + 150), loud ? 70 + (ph < .08 ? 15 : 0) : 25, bass, bass - 4, 55, 50, 48, 45, high, high - 5, high - 10]); sent++; }
    window.__emit('meter', { f: rows }); }, 100); })"""
FX = """(()=>{ var g = document.getElementById('npImmGlow'), c = document.getElementById('npImmSparks'), w = document.getElementById('npArtWrap'), sh = document.getElementById('npImmSheen');
  var gc = getComputedStyle(g);
  return { imm: document.body.classList.contains('np-immersive'), glowShown: gc.display, glowOp: +gc.opacity, glowT: g.style.transform,
    sparksShown: getComputedStyle(c).display, count: +c.dataset.count || 0, beats: +c.dataset.beats || 0,
    wrapT: w.style.transform, tilt: w.dataset.tilt || '', sheenOp: +getComputedStyle(sh).opacity, sheenX: sh.style.getPropertyValue('--sheen-x'),
    meter: window.__meter || [], H: innerHeight }; })()"""

def tilt_of(t):
    m = re.search(r'rotateX\(([-\d.]+)deg\) rotateY\(([-\d.]+)deg\) scale\(([-\d.]+)\)', t)
    return [float(v) for v in m.groups()] if m else None

async def run(p, w, h, dpr, scheme, tag, full):
    ctx = await p.new_context(viewport={'width': w, 'height': h}, device_scale_factor=dpr, is_mobile=True, has_touch=True, color_scheme=scheme)
    await ctx.add_init_script(MOCK); await ctx.add_init_script(AUTO_NOTICE)
    pg = await ctx.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
    await pg.route('**/*', lambda route: route.continue_() if '127.0.0.1' in route.request.url else route.abort())
    for name, src in (('cova.png', 'testsrc2=s=400x400'), ('covb.png', 'color=c=0x2050c0:s=400x400')):
        if not os.path.exists(f'{root}/{name}'):
            subprocess.run(['ffmpeg', '-loglevel', 'error', '-y', '-f', 'lavfi', '-i', src, '-frames:v', '1', f'{root}/{name}'], check=True)
    async def covers(route):
        await route.fulfill(status=200, content_type='image/png', body=open(f'{root}/' + route.request.url.rsplit('/', 1)[1], 'rb').read())
    await pg.route('https://covers.example/**', covers)
    await pg.goto(f'http://127.0.0.1:{PORT}/index.html'); await pg.wait_for_timeout(2500)
    cov = 'cova' if full else 'covb'
    await pg.evaluate("__t.play({ stationuuid: 'st-m1', name: 'Music One', url: 'http://radio.example/m1', urlToResolve: 'http://radio.example/m1', favicon: 'http://covers.example/%s.png', tags: '' })" % cov)
    await pg.wait_for_timeout(800)
    await pg.evaluate('__t.openNp()'); await pg.wait_for_timeout(900)
    await pg.evaluate('__t.ui(true)')
    s0 = await pg.evaluate(FX)
    check(s0['glowShown'] == 'none' and s0['sparksShown'] == 'none' and not s0['wrapT'] and not s0['meter'], f'{tag}: nothing outside Immersive View {s0}')
    box = await pg.locator('#npArtWrap').bounding_box()
    await pg.touchscreen.tap(box['x'] + box['width'] / 2, box['y'] + box['height'] * .35)
    await pg.wait_for_timeout(1500)
    s1 = await pg.evaluate(FX)
    check(s1['imm'] and s1['meter'] == [True], f'{tag}: the meter is asked for on entering {s1["meter"]}')
    check(s1['glowShown'] == 'block' and s1['sparksShown'] == 'block', f'{tag}: glow and sparks shown')
    # no meter data yet: a calm breath, no beats
    await pg.wait_for_timeout(2500)
    s2 = await pg.evaluate(FX)
    check(0.1 < s2['glowOp'] < 0.75 and s2['beats'] == 0, f'{tag}: without meter data the glow breathes, no beats ({s2["glowOp"]:.2f}, {s2["beats"]})')
    if not full:
        await pg.evaluate(MUSIC + '(true)'); await pg.wait_for_timeout(4000)
        await pg.screenshot(path=f'{shots}/immm-{tag}.png')
        await pg.evaluate('clearInterval(window.__mus)')
        await ctx.close(); return errs
    # loud music with beats
    await pg.evaluate(MUSIC + '(true)')
    await pg.wait_for_timeout(3000)
    ops, scs = [], []
    for i in range(30):
        f = await pg.evaluate(FX); ops.append(f['glowOp']); t = tilt_of(f['wrapT']); scs.append(t[2] if t else 0)
        await pg.wait_for_timeout(33)
    s3 = await pg.evaluate(FX)
    print(tag, 'glow', round(min(ops), 2), round(max(ops), 2), 'kick', min(scs), max(scs), 'sparks', s3['count'], 'beats', s3['beats'])
    check(s3['beats'] >= 7, f'{tag}: beats found at 120 bpm ({s3["beats"]} in ~4s)')
    check(max(ops) - min(ops) > .15 and max(ops) > .6, f'{tag}: the glow flares with the beat ({min(ops):.2f}..{max(ops):.2f})')
    check(max(scs) - min(scs) > .008, f'{tag}: the artwork kicks on the beat ({min(scs)}..{max(scs)})')
    check(s3['count'] >= 20, f'{tag}: sparks are flying ({s3["count"]})')
    # a screenshot right on a beat
    await pg.wait_for_function("(function(){ var g = document.getElementById('npImmGlow'); return +g.style.opacity > .75; })()", timeout=3000)
    await pg.wait_for_timeout(60)
    await pg.screenshot(path=f'{shots}/immm-{tag}-beat.png')
    on_top = await pg.evaluate("(function(){ var b = document.getElementById('npPlayBtn').getBoundingClientRect(); return document.elementFromPoint(b.left + b.width/2, b.top + b.height/2).closest('#npPlayBtn') !== null; })()")
    check(on_top, f'{tag}: Play still takes taps through the sparks')
    # quiet passage: no new beats, fewer sparks
    await pg.evaluate(MUSIC + '(false)'); await pg.wait_for_timeout(2500)
    b0 = (await pg.evaluate(FX))['beats']; await pg.wait_for_timeout(2000)
    s4 = await pg.evaluate(FX)
    check(s4['beats'] == b0 and s4['count'] < s3['count'], f'{tag}: a quiet passage has no beats and fewer sparks ({s4["count"]} vs {s3["count"]})')
    await pg.evaluate(MUSIC + '(true)')
    # gyroscope: level, then tipped right and forward
    await pg.evaluate("window.dispatchEvent(Object.assign(new Event('deviceorientation'), { alpha: 0, beta: 40, gamma: 0 }))")
    await pg.wait_for_timeout(100)
    for i in range(8):
        await pg.evaluate("window.dispatchEvent(Object.assign(new Event('deviceorientation'), { alpha: 0, beta: 52, gamma: 16 }))")
        await pg.wait_for_timeout(60)
    await pg.wait_for_timeout(400)
    s5 = await pg.evaluate(FX); t5 = tilt_of(s5['wrapT'])
    print(tag, 'gyro tilt', t5, s5['sheenOp'], s5['sheenX'])
    check(t5 and 4 < t5[1] <= 7 and -7 <= t5[0] < -3, f'{tag}: tipping the phone tilts the artwork ({t5})')
    check(s5['sheenOp'] > .6 and s5['sheenX'].startswith('-'), f'{tag}: the sheen brightens and slides ({s5["sheenOp"]}, {s5["sheenX"]})')
    await pg.screenshot(path=f'{shots}/immm-{tag}-tilt.png')
    # held still at that angle: slowly levels out again
    for i in range(60):
        await pg.evaluate("window.dispatchEvent(Object.assign(new Event('deviceorientation'), { alpha: 0, beta: 52, gamma: 16 }))")
        await pg.wait_for_timeout(50)
    t6 = tilt_of((await pg.evaluate(FX))['wrapT'])
    check(abs(t6[1]) < abs(t5[1]) * .6, f'{tag}: held at an angle, it re-centres ({t6})')
    # the mouse
    await pg.mouse.move(box['x'] + box['width'] - 5, box['y'] + box['height'] / 2)
    await pg.wait_for_timeout(700)
    t7 = tilt_of((await pg.evaluate(FX))['wrapT'])
    check(t7 and t7[1] > 6 and abs(t7[0]) < 1.5, f'{tag}: the mouse at the right edge turns it right ({t7})')
    # taps still toggle (the click lands on the tilted artwork)
    # pause: everything eases down
    await pg.evaluate('__t.ui(false)'); await pg.wait_for_timeout(3800)
    b1 = (await pg.evaluate(FX))['beats']; await pg.wait_for_timeout(1500)
    s8 = await pg.evaluate(FX)
    check(s8['glowOp'] < .05 and s8['beats'] == b1, f'{tag}: paused, the glow fades and beats stop ({s8["glowOp"]})')
    await pg.wait_for_timeout(3500)
    check((await pg.evaluate(FX))['count'] == 0, f'{tag}: paused, the sparks die away')
    await pg.evaluate('__t.ui(true)'); await pg.wait_for_timeout(2500)
    s9 = await pg.evaluate(FX)
    check(s9['glowOp'] > .2 and s9['count'] > 5, f'{tag}: playing again brings it back ({s9["glowOp"]}, {s9["count"]})')
    # leaving
    await pg.evaluate('clearInterval(window.__mus)')
    await pg.touchscreen.tap(box['x'] + box['width'] / 2, box['y'] + box['height'] * .35)
    await pg.wait_for_timeout(800)
    s10 = await pg.evaluate(FX)
    check(not s10['imm'] and s10['meter'][-1] is False and not s10['wrapT'] and s10['glowShown'] == 'none' and s10['count'] == 0,
          f'{tag}: leaving turns the meter off and clears everything {s10}')
    await pg.screenshot(path=f'{shots}/immm-{tag}-normal.png')
    await ctx.close()
    return errs

async def reduced(p):
    ctx = await p.new_context(viewport={'width': 412, 'height': 915}, device_scale_factor=2, is_mobile=True, has_touch=True, reduced_motion='reduce')
    await ctx.add_init_script(MOCK); await ctx.add_init_script(AUTO_NOTICE)
    pg = await ctx.new_page()
    await pg.route('**/*', lambda route: route.continue_() if '127.0.0.1' in route.request.url else route.abort())
    await pg.goto(f'http://127.0.0.1:{PORT}/index.html'); await pg.wait_for_timeout(2500)
    await pg.evaluate("__t.play({ stationuuid: 'st-m2', name: 'Still', url: 'http://radio.example/m2', urlToResolve: 'http://radio.example/m2', favicon: '', tags: '' })")
    await pg.wait_for_timeout(800); await pg.evaluate('__t.openNp()'); await pg.wait_for_timeout(900); await pg.evaluate('__t.ui(true)')
    box = await pg.locator('#npArtWrap').bounding_box()
    await pg.touchscreen.tap(box['x'] + box['width'] / 2, box['y'] + box['height'] * .35); await pg.wait_for_timeout(1200)
    s = await pg.evaluate(FX)
    check(s['imm'] and not s['meter'] and not s['wrapT'] and s['count'] == 0, f'reduced motion: no meter, tilt or sparks {s}')
    await ctx.close()

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
        errs = await run(b, 412, 915, 2.6, 'dark', 'p412', True)
        errs += await run(b, 360, 780, 3, 'light', 'p360', False)
        await reduced(b)
        check(not errs, f'no page errors {errs}')
        await b.close()
    srv.shutdown()
    print('ALL PASSED' if not fails else f'{len(fails)} FAILED')
    sys.exit(1 if fails else 0)

asyncio.run(main())
