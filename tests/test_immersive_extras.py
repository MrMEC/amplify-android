"""Build 146, Immersive View (glow behind Play removed in build 147): the cover's reflection under the
controls (moving with the artwork, mirrored), and soft orbs of light rising at random sizes and
places in the lower half and fading out. All follow play/pause and go when Immersive View ends.
Run: python3 tests/test_immersive_extras.py (screenshots in /tmp/claude-0/t/shots)"""
import asyncio, os, io, re
HERE = os.path.dirname(os.path.abspath(__file__))
src = open(os.path.join(HERE, 'test_immersive.py')).read()
pre = src[:src.rindex('\nasync def main()')]
pre = pre.replace("'/tmp/claude-0/t/srv_imm'", "'/tmp/claude-0/t/srv_immx'").replace("'PORT = 8796'", "'PORT = 8811'")
exec(pre)
from playwright.async_api import async_playwright
from PIL import Image
import subprocess

STATE = """(()=>{ function anims(el){ return el.getAnimations(); }
  var p = document.getElementById('npPlayBtn'), cv = document.getElementById('npImmReflectCv'),
      rf = document.getElementById('npImmReflect'), ctl = document.querySelector('#nowPlayingScreen .np-controls'), art = document.getElementById('npArt');
  var pr = p.getBoundingClientRect();
  var orbs = Array.from(document.querySelectorAll('#npImmOrbs .np-imm-orb')).map(function(o){ var a = o.getAnimations()[0], k = a ? a.effect.getKeyframes() : [];
      return { w: o.offsetWidth, l: o.offsetLeft, t: o.offsetTop, rate: a ? a.playbackRate : null, o0: k.length ? +k[0].opacity : null, o2: k.length ? +k[k.length - 1].opacity : null,
        peak: k.length ? +k[1].opacity : null, endT: k.length ? k[k.length - 1].transform : '' }; });
  var artA = anims(art).filter(function(a){ return a.effect.getKeyframes().some(function(k){ return k.transform; }); })[0];
  var rA = anims(cv).filter(function(a){ return a.effect.getKeyframes().some(function(k){ return k.transform; }); })[0];
  return { glowEl: !!document.getElementById('npPlayGlow') || !!document.querySelector('.np-play-glow'), pc: [pr.left + pr.width / 2, pr.top + pr.height / 2],
    reflTop: rf.getBoundingClientRect().top, reflShown: getComputedStyle(rf).display, ctlBottom: ctl.getBoundingClientRect().bottom, drawn: +cv.dataset.drawn || 0,
    artKf: artA ? artA.effect.getKeyframes().map(function(k){ return k.transform; }) : null, rKf: rA ? rA.effect.getKeyframes().map(function(k){ return k.transform; }) : null,
    artTime: artA ? artA.currentTime : null, rTime: rA ? rA.currentTime : null, rRate: rA ? rA.playbackRate : null,
    orbs: orbs, box: document.getElementById('npImmOrbs').getBoundingClientRect().top, H: innerHeight }; })()"""

def nums(t):
    m = re.findall(r'translate3d\(([-\d.]+)%, ([-\d.]+)%, 0px\) rotate\(([-\d.]+)deg\) scale\(([-\d.]+)\)', t)[0]
    return [float(v) for v in m]

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
        ctx = await b.new_context(viewport={'width': 390, 'height': 844}, device_scale_factor=2, is_mobile=True, has_touch=True, color_scheme='dark')
        await ctx.add_init_script(MOCK)
        pg = await ctx.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.route('**/*', lambda route: route.continue_() if '127.0.0.1' in route.request.url else route.abort())
        subprocess.run(['ffmpeg', '-loglevel', 'error', '-y', '-f', 'lavfi', '-i', 'testsrc2=s=300x300', '-frames:v', '1', f'{root}/cov1.png'], check=True)
        async def covers(route):
            await route.fulfill(status=200, content_type='image/png', body=open(f'{root}/' + route.request.url.rsplit('/', 1)[1], 'rb').read())
        await pg.route('https://covers.example/**', covers)
        await pg.goto(f'http://127.0.0.1:{PORT}/index.html'); await pg.wait_for_timeout(2500)
        await pg.evaluate("__t.play({ stationuuid: 'st-c1', name: 'Cover One', url: 'http://radio.example/c1', urlToResolve: 'http://radio.example/c1', favicon: 'http://covers.example/cov1.png', tags: '' })")
        await pg.wait_for_timeout(800)
        await pg.evaluate('__t.openNp()'); await pg.wait_for_timeout(900)
        await pg.evaluate('__t.ui(true)')
        s0 = await pg.evaluate(STATE)
        check(not s0['glowEl'] and s0['reflShown'] == 'none' and not s0['orbs'], f'nothing extra outside Immersive View {s0["reflShown"]}')
        box = await pg.locator('#npArtWrap').bounding_box()
        await pg.touchscreen.tap(box['x'] + box['width'] / 2, box['y'] + box['height'] * .35)
        await pg.wait_for_timeout(3500)
        await pg.screenshot(path=f'{shots}/immx-1.png')
        await pg.wait_for_timeout(5000)
        s1 = await pg.evaluate(STATE)
        print({k: v for k, v in s1.items() if k not in ('orbs', 'artKf', 'rKf')})
        # no glow (removed in build 147)
        check(not s1['glowEl'], 'no glow behind Play')
        on_top = await pg.evaluate("document.elementFromPoint(%d, %d).closest('#npPlayBtn') !== null" % (s1['pc'][0], s1['pc'][1]))
        check(on_top, 'Play is on top and tappable')
        img = Image.open(io.BytesIO(await pg.screenshot())).convert('RGB')
        pcol = img.getpixel((int(s1['pc'][0] * 2) - 40, int(s1['pc'][1] * 2) - 40))
        viv = await pg.evaluate("(function(){ var d=document.createElement('div'); d.style.color=getComputedStyle(document.body).getPropertyValue('--np-vivid'); document.body.appendChild(d); var c=getComputedStyle(d).color; d.remove(); return c.match(/\\d+/g).slice(0,3).map(Number); })()")
        check(max(abs(pcol[k] - viv[k]) for k in range(3)) <= 6, f'Play keeps its own solid colour {pcol} vs {viv}')
        # reflection
        check(s1['reflShown'] == 'block' and s1['drawn'] >= 1 and s1['ctlBottom'] <= s1['reflTop'] <= s1['ctlBottom'] + 20, f'the reflection is drawn and starts just under the controls {s1["reflTop"]} {s1["ctlBottom"]}')
        check(s1['artKf'] and s1['rKf'] and len(s1['artKf']) == len(s1['rKf']), 'the reflection has its own motion alongside the artwork')
        ok = True
        for a, r in zip(s1['artKf'], s1['rKf']):
            A, Rr = nums(a), nums(r)
            ok = ok and abs(A[0] - Rr[0]) < .01 and abs(A[1] + Rr[1]) < .01 and abs(A[2] + Rr[2]) < .01 and abs(A[3] - Rr[3]) < .01
        check(ok, f'mirrored: same zoom and sideways drift, opposite vertical drift and turn {s1["artKf"]} {s1["rKf"]}')
        check(abs(s1['artTime'] - s1['rTime']) < 50 and s1['rRate'] == 1, f'in step with the artwork {s1["artTime"]} {s1["rTime"]}')
        # orbs
        orbs = s1['orbs']
        print(orbs)
        check(2 <= len(orbs) <= 7, f'a few orbs are floating ({len(orbs)})')
        check(len(set(o['w'] for o in orbs)) >= 2 and len(set(o['l'] for o in orbs)) >= 2, f'at random sizes and places {[(o["w"], o["l"], o["t"]) for o in orbs]}')
        check(all(o['o0'] == 0 and o['o2'] == 0 and 0.3 <= o['peak'] <= .73 for o in orbs), 'each fades in, then gradually out')
        check(all(float(re.findall(r'translate3d\(([-\d.]+)px, ([-\d.]+)px', o['endT'])[0][1]) < 0 for o in orbs), 'each rises')
        check(s1['box'] >= s1['H'] * .44, f'all in the lower half (from {s1["box"]})')
        await pg.screenshot(path=f'{shots}/immx-2.png')
        await pg.wait_for_timeout(6000)
        s15 = await pg.evaluate(STATE)
        check(len(s15['orbs']) <= 7 and len(s15['orbs']) >= 2, f'they keep coming, never too many ({len(s15["orbs"])})')
        await pg.screenshot(path=f'{shots}/immx-3.png')
        # pause holds everything
        await pg.evaluate('__t.ui(false)'); await pg.wait_for_timeout(3600)
        s2 = await pg.evaluate(STATE)
        n2 = len(s2['orbs'])
        await pg.wait_for_timeout(4000)
        s3 = await pg.evaluate(STATE)
        check(s2['rRate'] == 0 and all(o['rate'] == 0 for o in s2['orbs']), f'paused: reflection and orbs hold still {s2["rRate"]}')
        check(len(s3['orbs']) == n2, f'and no new orbs while paused ({n2} -> {len(s3["orbs"])})')
        await pg.evaluate('__t.ui(true)'); await pg.wait_for_timeout(2200)
        s4 = await pg.evaluate(STATE)
        check(s4['rRate'] == 1 and all(o['rate'] == 1 for o in s4['orbs']), 'playing again: back to speed')
        # leaving takes it all away
        await pg.touchscreen.tap(box['x'] + box['width'] / 2, box['y'] + box['height'] * .35)
        await pg.wait_for_timeout(800)
        s5 = await pg.evaluate(STATE)
        check(not s5['orbs'] and s5['reflShown'] == 'none' and s5['rKf'] is None, 'leaving Immersive View removes the orbs and the reflection')
        check(not errs, f'no page errors {errs[:3]}')
        await b.close()
    print('ALL PASSED' if not fails else f'FAILED {fails}')

asyncio.run(main())
