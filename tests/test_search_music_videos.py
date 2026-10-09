"""Build 177: Search finds music videos -- your own (music folders, matched to artists) and the
YouTube music videos Amplify knows for your artists -- in a Music Videos tab (after Songs) and in
Top Results; a search naming one of your artists looks their YouTube videos up. Your own play as
videos with the artist's videos as the queue; YouTube ones open the YouTube player.
Run: python3 tests/test_search_music_videos.py (screenshots in /tmp/claude-0/t/shots)"""
import asyncio, os, json, time
HERE = os.path.dirname(os.path.abspath(__file__))
src = open(os.path.join(HERE, 'test_music_videos.py')).read()
head = src[:src.index('async def main():')]
head = head.replace('PORT = 8814', 'PORT = 8819').replace("'/tmp/claude-0/t/srv_mv'", "'/tmp/claude-0/t/srv_smv'")
head = head.replace('" scan: function(){', '" search: function(q){ searchByName(q, false, false); }, ytKey: function(n){ return artistMatchKey(n); }, scan: function(){')
__file__ = os.path.join(HERE, 'test_music_videos.py')
exec(head)
from playwright.async_api import async_playwright

ROWS = """(()=>{ return Array.from(document.querySelectorAll('#stationsGrid .mv-result-row')).map(function(r){
  return { t: r.querySelector('.song-row-title').textContent, s: r.querySelector('.song-row-sub').textContent, src: r.dataset.src, img: !!r.querySelector('img') }; }); })()"""
TABS = "Array.from(document.querySelectorAll('#searchTabs .home-tab')).map(function(b){ return b.textContent; })"

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
        ctx = await b.new_context(viewport={'width': 390, 'height': 844}, device_scale_factor=2, is_mobile=True, has_touch=True, color_scheme='dark')
        await ctx.add_init_script(MOCK)
        pg = await ctx.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
        feeds = []
        async def route(r):
            u = r.request.url
            if '127.0.0.1' in u: return await r.continue_()
            if 'ytimg.com' in u: return await r.fulfill(status=200, content_type='image/jpeg', body=open(f'{root}/still.jpg', 'rb').read())
            if 'youtube.com/feeds' in u or 'wikidata' in u or 'wikipedia' in u:
                feeds.append(u)
            return await r.abort()
        await pg.route('**/*', route)
        await pg.goto(f'http://127.0.0.1:{PORT}/index.html'); await pg.wait_for_timeout(2500)
        await pg.evaluate("""(function(){ var ov=document.getElementById('addMusicOverlay'); if(ov) ov.classList.add('open');
          var btn=document.getElementById('addMusicFolderBtn'); btn.disabled=false; btn.click(); })()""")
        for _ in range(60):
            await pg.wait_for_timeout(500)
            if len(await pg.evaluate('__t.tracks()')) >= 8: break
        await pg.wait_for_timeout(1500)
        # Bob's YouTube videos, as an artist page would have stored them
        bk = await pg.evaluate("__t.ytKey('Bob')")
        now = int(time.time() * 1000)
        store = {bk: {'channels': ['UCbob'], 'chTs': now, 'ts': now, 'fv': 2, 'mv': True,
                      'videos': [{'id': 'aaaaaaaaaaa', 'title': 'Bob - Night Drive (Official Video)', 'published': '2021-05-01'},
                                 {'id': 'bbbbbbbbbbb', 'title': 'Bob - Great Song (Live)', 'published': '2019-02-01'}]}}
        await pg.evaluate("(s)=>{ localStorage.setItem('amplifyFallback:artistVideos', s); }", json.dumps(store))
        pfx = await pg.evaluate("Object.keys(localStorage).filter(function(k){ return /artistVideos/.test(k); })")
        print('store keys', pfx)
        await pg.reload(); await pg.wait_for_timeout(3000)
        # "great song": Bob's own video and the YouTube live one
        await pg.evaluate("__t.search('great song')"); await pg.wait_for_timeout(1200)
        tabs = await pg.evaluate(TABS); print(tabs)
        check(any(t.startswith('Music Videos') for t in tabs), f'a Music Videos tab {tabs}')
        si = [i for i, t in enumerate(tabs) if t.startswith('Songs')]; mi = [i for i, t in enumerate(tabs) if t.startswith('Music Videos')]
        check(not si or (mi and mi[0] == si[0] + 1), f'right after Songs {tabs}')
        await pg.evaluate("Array.from(document.querySelectorAll('#searchTabs .home-tab')).filter(function(b){ return /^Music Videos/.test(b.textContent); })[0].click()"); await pg.wait_for_timeout(1200)
        rows = await pg.evaluate(ROWS); print(rows)
        check([r['t'] for r in rows] == ['Great Song', 'Great Song (Live)'] and rows[0]['src'] == 'local' and rows[1]['src'] == 'yt',
              f'yours first, then YouTube {rows}')
        check(rows[0]['s'].startswith('Music Video · Bob') and '2:05' in rows[0]['s'] and rows[1]['s'] == 'Music Video · Bob · YouTube', f'labelled {rows}')
        check(all(r['img'] for r in rows), f'each with a picture {rows}')
        await pg.screenshot(path=f'{shots}/search-mv.png')
        # by artist: every video of theirs
        await pg.evaluate("__t.search('bob')"); await pg.wait_for_timeout(1200)
        await pg.evaluate("Array.from(document.querySelectorAll('#searchTabs .home-tab')).filter(function(b){ return /^Music Videos/.test(b.textContent); })[0].click()"); await pg.wait_for_timeout(800)
        names = sorted(r['t'] for r in await pg.evaluate(ROWS))
        check(names == sorted(['Great Song', 'Live at Wembley', 'Night Drive', 'Great Song (Live)']), f"searching the artist lists all of Bob's videos {names}")
        # Top Results carries them too
        await pg.evaluate("__t.search('night drive')"); await pg.wait_for_timeout(1200)
        top = await pg.evaluate("Array.from(document.querySelectorAll('#stationsGrid .top-result-row')).map(function(r){ return r.dataset.kind + ':' + r.querySelector('.song-row-title').textContent; })")
        check('musicVideos:Night Drive' in top, f'in Top Results {top}')
        # playing your own from search
        await pg.evaluate("__t.search('wembley')"); await pg.wait_for_timeout(1200)
        await pg.evaluate("document.querySelector('#stationsGrid .mv-result-row').click()"); await pg.wait_for_timeout(1200)
        s = await pg.evaluate('__t.q()'); print(s)
        check(s['type'] == 'video' and s['kind'] == 'music' and s['cur'] == 'Live at Wembley' and s['label'] == 'Bob Videos', f"plays as a video with Bob's videos queued {s}")
        await pg.evaluate("closeNowPlaying && closeNowPlaying()") if False else None
        # a YouTube one opens the YouTube player
        await pg.evaluate("document.getElementById('npBackBtn').click()"); await pg.wait_for_timeout(700)
        await pg.evaluate("__t.search('night drive')"); await pg.wait_for_timeout(1200)
        await pg.evaluate("document.querySelector('#stationsGrid .mv-result-row[data-src=yt]').click()"); await pg.wait_for_timeout(800)
        yt = await pg.evaluate("[document.body.classList.contains('yt-open'), (document.querySelector('#ytOvFrame iframe') || {}).src || '', document.getElementById('ytOvTitle').textContent]")
        check(yt[0] and 'aaaaaaaaaaa' in yt[1] and yt[2] == 'Night Drive', f'a YouTube video opens the YouTube player {yt}')
        await pg.evaluate("document.querySelector('.yt-ov-close, #ytOvClose') && document.querySelector('.yt-ov-close, #ytOvClose').click()")
        # an artist you have with nothing stored: their videos are looked up
        feeds.clear()
        await pg.evaluate("__t.search('carl')"); await pg.wait_for_timeout(2500)
        print('feeds', feeds[:3])
        check(any('Carl' in f for f in feeds), f"searching one of your artists starts the lookup of their YouTube videos {feeds[:3]}")
        feeds.clear()
        await pg.evaluate("__t.search('bob')"); await pg.wait_for_timeout(1500)
        check(not any('Bob' in f for f in feeds), f'not for an artist whose videos are already known {feeds[:3]}')
        check(not errs, f'no page errors {errs[:3]}')
        await b.close()
    print('ALL PASSED' if not fails else f'FAILED {fails}')
asyncio.run(main())
