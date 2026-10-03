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
assert 'closeNp' in head
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
