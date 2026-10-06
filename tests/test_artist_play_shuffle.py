"""Build 149 (Radio since build 150): Play on an artist page with no station of their own plays all of the artist's songs
shuffled (the queue is just their songs, in a random order); with a station, Play still starts it.
Run: python3 tests/test_artist_play_shuffle.py"""
import asyncio, os
HERE = os.path.dirname(os.path.abspath(__file__))
src = open(os.path.join(HERE, 'test_station_skip.py')).read()
head = src[:src.index('async def main()')]
head = head.replace("'/tmp/claude-0/t/srv_skip'", "'/tmp/claude-0/t/srv_aps'").replace('PORT = 8794', 'PORT = 8812')
head = head.replace("for i, (t, a) in enumerate([('Song 1', 'Ann'), ('Song 2', 'Bob'), ('Song 3', 'Bob')]):",
                    "for i, (t, a) in enumerate([('Song 1', 'Ann'), ('Song 2', 'Bob'), ('Song 3', 'Bob'), ('Song 4', 'Bob'), ('Song 5', 'Bob'), ('Song 6', 'Bob')]):")
head = head.replace('" skip: function(){', '" noStations: function(){ artistStations = []; artistStationsFailed = false; artistStationsPromise = Promise.resolve(artistStations); }, skip: function(){')
assert 'Song 6' in head and 'noStations' in head
exec(head)
from playwright.async_api import async_playwright

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
            if len(await pg.evaluate('__t.tracks()')) >= 6: break
        await pg.evaluate('__t.noStations()')
        q = lambda: pg.evaluate('__t.q()')
        orders = set()
        for i in range(6):
            await pg.evaluate("__t.openArtist('Bob')"); await pg.wait_for_timeout(700)
            if i == 0:
                vis = await pg.evaluate("getComputedStyle(document.getElementById('artistPlayBtn')).display")
                check(vis != 'none', 'Play shows on an artist page with songs and no station')
            await pg.click('#artistPlayBtn'); await pg.wait_for_timeout(500)
            s = await q()
            check(sorted(s['list']) == ['Song 2', 'Song 3', 'Song 4', 'Song 5', 'Song 6'] and s['cur'] == s['list'][0] and s['idx'] == 0 and s['label'] == 'Bob Radio',
                  f'try {i}: all of Bob songs, and only his, queued with the first playing {s}')
            orders.add(tuple(s['list']))
            await pg.evaluate("__t.openArtist('Ann')"); await pg.wait_for_timeout(600)
            await pg.click('#artistPlayBtn'); await pg.wait_for_timeout(400)
        check(len(orders) >= 3, f'shuffled: a different order each time ({len(orders)} different orders in 6 tries)')
        # Ann has one song and no station: Play plays it
        s = await q()
        check(s['cur'] == 'Song 1', f'an artist with one song and no station: Play plays it {s}')
        # With a station: Play still starts the station
        await pg.evaluate('__t.setup()')
        await pg.evaluate("__t.openArtist('Bob')"); await pg.wait_for_timeout(900)
        await pg.click('#artistPlayBtn'); await pg.wait_for_timeout(500)
        s = await q()
        check(s['cur'] == 'Exclusively Bob', f'an artist with a station: Play starts the station {s}')
        check(not errs, f'no page errors {errs[:3]}')
        await b.close()
    print('ALL PASSED' if not fails else f'FAILED {fails}')

asyncio.run(main())
