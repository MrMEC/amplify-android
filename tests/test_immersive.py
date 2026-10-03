"""Immersive View: on a phone, tapping the artwork on Now Playing slides the corner buttons
(close, menu) up off the screen and the mini player and tab bar down off it, and Now Playing
takes the whole screen; tapping again brings them back. Works for songs, stations and podcast
episodes, not for channels; closing Now Playing leaves it. Also checks the mobile search
placeholder ("Search or add stream").
Run: python3 tests/test_immersive.py (screenshots in /tmp/claude-0/t/shots)"""
import asyncio, os
HERE = os.path.dirname(os.path.abspath(__file__))
src = open(os.path.join(HERE, 'test_station_skip.py')).read()
head = src[:src.index('async def main()')]
head = head.replace("'/tmp/claude-0/t/srv_skip'", "'/tmp/claude-0/t/srv_imm'").replace('PORT = 8794', 'PORT = 8796')
head = head.replace('" skip: function(){', '" closeNp: function(){ closeNowPlaying(false, false); }, play: function(x){ playStation(x); }, skip: function(){')
head = head.replace('skip: function(){ return window.__skip; }', 'ui: function(b){ setPlayingUI(b); }, skip: function(){ return window.__skip; }')
head = head.replace("setSkip: function(o){", "setVideoUi: function(o){ (window.__vui = window.__vui || []).push(o); return Promise.resolve({}); }, setSkip: function(o){")
assert 'closeNp' in head and '__vui' in head and 'setPlayingUI' in head
exec(head)
from playwright.async_api import async_playwright

STATE = """(()=>{ var H = innerHeight;
  function r(el){ if(!el) return null; var b = el.getBoundingClientRect(), c = getComputedStyle(el); return { top: Math.round(b.top), bottom: Math.round(b.bottom), op: parseFloat(c.opacity), pe: c.pointerEvents, shown: c.display !== 'none' }; }
  return { imm: document.body.classList.contains('np-immersive'), H: H,
    back: r(document.getElementById('npBackBtn')), menu: r(document.getElementById('hamburgerBtn')),
    bar: r(document.getElementById('playerBar')), nav: r(document.getElementById('mobileNav')),
    screen: r(document.getElementById('nowPlayingScreen')) }; })()"""


async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
        ctx = await b.new_context(viewport={'width': 390, 'height': 844}, device_scale_factor=2, is_mobile=True, has_touch=True, color_scheme='dark')
        await ctx.add_init_script(MOCK)
        pg = await ctx.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.route('**/*', lambda route: route.continue_() if '127.0.0.1' in route.request.url else route.abort())
        await pg.goto(f'http://127.0.0.1:{PORT}/index.html'); await pg.wait_for_timeout(2500)

        # 1) the mobile search placeholder
        ph = await pg.evaluate("[document.getElementById('searchSheetInput').placeholder, document.getElementById('searchInput').placeholder]")
        check(ph == ['Search or add stream', 'Search or add stream'], f'mobile search placeholder {ph}')

        await pg.evaluate("""(function(){ var ov=document.getElementById('addMusicOverlay'); if(ov) ov.classList.add('open');
          var btn=document.getElementById('addMusicFolderBtn'); btn.disabled=false; btn.click(); })()""")
        for _ in range(60):
            await pg.wait_for_timeout(500)
            if len(await pg.evaluate('__t.tracks()')) >= 3: break
        await pg.evaluate('__t.setup()')
        st = lambda: pg.evaluate(STATE)

        async def tap_art():
            box = await pg.locator('#npArtWrap').bounding_box()
            await pg.touchscreen.tap(box['x'] + box['width'] / 2, box['y'] + box['height'] * 0.35)

        async def run(kind, start_js):
            await pg.evaluate(start_js); await pg.wait_for_timeout(600)
            await pg.evaluate('__t.openNp()'); await pg.wait_for_timeout(900)
            s0 = await st()
            check(not s0['imm'] and s0['nav']['top'] < s0['H'] and s0['bar']['bottom'] < s0['H'] and s0['back']['top'] >= 0 and s0['menu']['top'] >= 0,
                  f'{kind}: normal view shows corner buttons, mini player and tab bar {s0}')
            await pg.screenshot(path=f'{shots}/immersive-{kind}-off.png')
            await tap_art()
            mid = []
            for _ in range(6):
                await pg.wait_for_timeout(45)
                s = await st()
                mid.append((s['nav']['top'], s['back']['top']))
            await pg.wait_for_timeout(500)
            s1 = await st()
            H = s1['H']
            check(s1['imm'], f'{kind}: tapping the artwork turns Immersive View on')
            check(s1['back']['bottom'] <= 0 and s1['back']['pe'] == 'none', f"{kind}: close button slid up off the screen {s1['back']}")
            check(s1['menu']['bottom'] <= 0 and s1['menu']['pe'] == 'none', f"{kind}: menu button slid up off the screen {s1['menu']}")
            check(s1['bar']['top'] >= H, f"{kind}: mini player slid down off the screen {s1['bar']}")
            check(s1['nav']['top'] >= H, f"{kind}: tab bar slid down off the screen {s1['nav']}")
            check(s1['screen']['bottom'] == H, f"{kind}: Now Playing fills the screen {s1['screen']}")
            inbetween = [m for m in mid if s0['nav']['top'] < m[0] < H]
            check(len(inbetween) >= 2, f'{kind}: the tab bar slides rather than jumping {mid}')
            await pg.screenshot(path=f'{shots}/immersive-{kind}-on.png')
            await tap_art(); await pg.wait_for_timeout(600)
            s2 = await st()
            check(not s2['imm'] and s2['nav']['top'] == s0['nav']['top'] and s2['bar']['top'] == s0['bar']['top'] and s2['back']['top'] == s0['back']['top'] and s2['menu']['top'] == s0['menu']['top'],
                  f'{kind}: tapping again brings everything back {s2}')

        await run('song', "__t.songs(); setTimeout(function(){ document.querySelector('#stationsGrid .song-row:not(.shuffle-all-row)').click(); }, 300)")
        await run('station', "__t.openPl('pl_mix'); setTimeout(function(){ Array.from(document.querySelectorAll('#stationsGrid .row-item')).filter(function(e){ return /Radio A/.test(e.textContent); })[0].click(); }, 300)")
        await run('podcast', "__t.play({ type: 'podcast', guid: 'ep-1', name: 'Episode One', url: 'http://pod.example/ep1.mp3', collectionName: 'The Show', artworkUrl: '' })")
        # a channel has its own full-screen layout: no Immersive View there


        # ---- movement in Immersive View ----
        import subprocess as _sp
        for name, col in (('cov1', 'orange'), ('cov2', 'teal')):
            src_ = 'testsrc2=s=300x300' if name == 'cov1' else f'color=c={col}:s=300x300'
            _sp.run(['ffmpeg', '-loglevel', 'error', '-y', '-f', 'lavfi', '-i', src_, '-frames:v', '1', f'{root}/{name}.png'], check=True)
        STN = lambda n, cov: ("{ stationuuid: 'st-" + n + "', name: '" + n + "', url: 'http://radio.example/" + n + "', urlToResolve: 'http://radio.example/" + n
                              + "', favicon: 'http://covers.example/" + cov + ".png', tags: '' }")
        async def covers(route):
            name = route.request.url.rsplit('/', 1)[1]
            await route.fulfill(status=200, content_type='image/png', body=open(f'{root}/{name}', 'rb').read())
        await pg.route('https://covers.example/**', covers)
        ANIMS = """(()=>{ var out = { art: 0, bg: 0, other: 0, composite: [], filters: [] }, rates = [];
          document.getAnimations().forEach(function(a){ var t = a.effect && a.effect.target; if(!t || a.playState === 'finished') return;
            var kf = a.effect.getKeyframes(); var moving = kf.some(function(k){ return k.transform; });
            if(!moving) return;
            if(t.id === 'npArt') out.art++; else if(t.closest('.np-imm-bg')) out.bg++; else out.other++;
            out.composite.push(a.effect.composite); out.filters.push(getComputedStyle(t).filter); rates.push(+a.playbackRate.toFixed(2)); });
          out.rates = rates;
          out.artT = getComputedStyle(document.getElementById('npArt')).transform;
          var c = document.querySelector('.np-imm-bg canvas'); out.bgT = c ? getComputedStyle(c).transform : null;
          out.canvases = document.querySelectorAll('.np-imm-bg').length;
          out.ghosts = document.querySelectorAll('.np-imm-ghost').length; out.vui = window.__vui || []; return out; })()"""
        await pg.evaluate("__t.play(" + STN('Cover One', 'cov1') + ")"); await pg.wait_for_timeout(900)
        await pg.evaluate("__t.ui(true)")
        await pg.screenshot(path=f'{shots}/immersive-wash-before.png')
        await tap_art(); await pg.wait_for_timeout(2200)
        await pg.screenshot(path=f'{shots}/immersive-wash-on.png')
        a1 = await pg.evaluate(ANIMS)
        print(a1)
        check(a1['art'] == 1 and a1['bg'] == 3 and a1['other'] == 0 and a1['canvases'] == 1, f"the artwork and the wash are moving, nothing else {a1}")
        check(all(c == 'replace' for c in a1['composite']) and all(f == 'none' for f in a1['filters']),
              f"only plain transforms on unfiltered layers, so the phone's compositor runs them {a1['composite']} {a1['filters']}")
        check(all(r == 1 for r in a1['rates']), f"at full speed while playing {a1['rates']}")
        check(a1['vui'] and a1['vui'][-1].get('awake') is True, f"screen kept on {a1['vui']}")
        await pg.wait_for_timeout(1500)
        a2 = await pg.evaluate(ANIMS)
        # the colours keep moving: the lower half of the screen (below the art) changes colour over time
        from PIL import Image as _I
        import io as _io
        async def lower_avg():
            im = _I.open(_io.BytesIO(await pg.screenshot())).convert('RGB').resize((39, 84))
            px = [im.getpixel((x, y)) for x in range(39) for y in range(60, 84)]
            return tuple(sum(p[k] for p in px) / len(px) for k in range(3))
        await pg.wait_for_timeout(1500)
        c1 = await lower_avg(); await pg.screenshot(path=f'{shots}/wash-t1.png'); await pg.wait_for_timeout(3500); c2 = await lower_avg(); await pg.screenshot(path=f'{shots}/wash-t2.png'); await pg.wait_for_timeout(3500); c3 = await lower_avg(); await pg.screenshot(path=f'{shots}/wash-t3.png')
        d = max(max(abs(c1[k] - c2[k]) for k in range(3)), max(abs(c2[k] - c3[k]) for k in range(3)))
        check(d > 6, f'the background colour keeps changing after the entrance ({c1} -> {c2} -> {c3}, max change {d:.1f})')
        check(a2['artT'] != a1['artT'] and a2['bgT'] != a1['bgT'], f"the art and the wash drift over time {a1['artT']} -> {a2['artT']}")
        # pause: eases to a stop
        await pg.evaluate("__t.ui(false)"); await pg.wait_for_timeout(500)
        mid = await pg.evaluate(ANIMS)
        check(all(0 < r < 1 for r in mid['rates']), f"pausing slows it down gradually {mid['rates']}")
        await pg.wait_for_timeout(1300)
        p1 = await pg.evaluate(ANIMS); await pg.wait_for_timeout(700); p2 = await pg.evaluate(ANIMS)
        check(all(r == 0 for r in p1['rates']) and p1['artT'] == p2['artT'] and p1['bgT'] == p2['bgT'], f"paused: everything holds still {p1['rates']}")
        await pg.evaluate("__t.ui(true)"); await pg.wait_for_timeout(2200)
        check(all(r == 1 for r in (await pg.evaluate(ANIMS))['rates']), 'playing again: back up to speed')
        # a new song dissolves in
        await pg.evaluate("__t.play(" + STN('Cover Two', 'cov2') + ")"); await pg.wait_for_timeout(500)
        g1 = await pg.evaluate(ANIMS)
        check(g1['ghosts'] == 1 and g1['canvases'] == 2, f"the old artwork and wash fade out over the new ({g1['ghosts']} art, {g1['canvases']} washes)")
        await pg.screenshot(path=f'{shots}/immersive-crossfade.png')
        await pg.wait_for_timeout(2000)
        g2 = await pg.evaluate(ANIMS)
        check(g2['ghosts'] == 0 and g2['canvases'] == 1 and g2['art'] == 1 and g2['bg'] == 3, f"and are gone once the new one is in; the new one moves {g2}")
        await pg.screenshot(path=f'{shots}/immersive-motion.png')
        # leaving stops it all and lets the screen sleep again
        await tap_art(); await pg.wait_for_timeout(500)
        a3 = await pg.evaluate(ANIMS)
        check(a3['art'] + a3['bg'] + a3['other'] == 0 and a3['canvases'] == 0 and not a3['vui'][-1].get('awake'), f"leaving Immersive View stops the motion and the keep-awake {a3}")
        # Remove animations: no motion
        await pg.emulate_media(reduced_motion='reduce')
        await tap_art(); await pg.wait_for_timeout(600)
        a4 = await pg.evaluate(ANIMS)
        check(a4['art'] + a4['bg'] == 0 and a4['canvases'] == 0 and (await st())['imm'], f"with Remove animations on, Immersive View still works but holds still {a4}")
        await tap_art(); await pg.wait_for_timeout(400)
        await pg.emulate_media(reduced_motion='no-preference')

        # closing Now Playing while immersive leaves it
        await tap_art(); await pg.wait_for_timeout(500)
        check((await st())['imm'], 'immersive again')
        await pg.evaluate("__t.closeNp()")
        await pg.wait_for_timeout(600)
        s = await st()
        check(not s['imm'] and s['nav']['top'] < s['H'], f'closing Now Playing ends Immersive View {s}')
        check(not errs, f'no page errors {errs[:3]}')
        await b.close()
    print('ALL PASSED' if not fails else f'FAILED {fails}')

asyncio.run(main())
