"""Build 134: Search finds Movies & TV (phone folders and Plex), with its own tab and in Top
Results; Video's Movies and TV Shows tabs get the A to Z rail (a letter in Recently Added
switches to A to Z first, then jumps).
Run: python3 tests/test_video_search.py (screenshots in /tmp/claude-0/t/shots)"""
import asyncio, os, json
HERE = os.path.dirname(os.path.abspath(__file__))
src = open(os.path.join(HERE, 'test_plex.py')).read()
head = src[:src.index('async def main():')]
head = head.replace("'/tmp/claude-0/t/srv-plex'", "'/tmp/claude-0/t/srv-vsearch'").replace('8803', '8804')
exec(head)
from playwright.async_api import async_playwright

# more Plex movies, so the rail has enough to index
for i, t in enumerate(['Zodiac', 'Babe', 'Casablanca', 'Gladiator', 'Jaws', 'Memento', 'Rocky', 'Up', 'Vertigo', 'Psycho', '12 Angry Men', 'Notorious']):
    MOVIES.append({'ratingKey': str(700 + i), 'title': t, 'year': 1950 + i, 'thumb': '/library/metadata/%d/thumb/1' % (700 + i),
                   'duration': 6000000, 'addedAt': NOW - 20000 - i * 100, 'Media': part(700 + i)})
ACCT = {'token': 'TOKEN1', 'user': 'Mark', 'servers': [{'id': 'srvabcdef123', 'name': 'Home Server', 'token': 'SRVTOKEN', 'owned': True,
        'conns': [{'uri': LOCAL, 'local': True, 'relay': False}, {'uri': REMOTE, 'local': False, 'relay': False}]}], 'serverId': 'srvabcdef123', 'base': REMOTE}
SEED = "if(!localStorage.getItem('radioPlayerPlexAccount')) localStorage.setItem('radioPlayerPlexAccount', %s);" % repr(json.dumps(ACCT))

async def vroute(r):
    u = r.request.url
    if 'radio-browser' in u or 'api.radio' in u:
        return await r.fulfill(status=200, content_type='application/json', headers=CORS, body='[]')
    if 'itunes.apple.com' in u:
        return await r.abort()
    return await proute(r)

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
        ctx = await b.new_context(viewport={'width': 390, 'height': 844}, device_scale_factor=2, is_mobile=True, has_touch=True, color_scheme='dark', locale='en-US')
        await ctx.add_init_script(MOCK)
        await ctx.add_init_script(EXT)
        await ctx.add_init_script(OPEN)
        await ctx.add_init_script(SEED)
        pg = await ctx.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e) + ' @ ' + (e.stack or '')[:300]))
        await pg.route('**/*', vroute)
        await pg.goto('http://127.0.0.1:8804/index.html'); await pg.wait_for_timeout(2500)
        await pg.evaluate("document.querySelector('.mobile-nav-btn[data-nav=video]').click()"); await pg.wait_for_timeout(500)
        await tab(pg, 'movies')
        await pg.evaluate("document.getElementById('videoAddHeaderBtn').click()"); await pg.wait_for_timeout(2500)
        await tab(pg, 'shows'); await tab(pg, 'movies')
        mv = await names(pg, '#stationsGrid .tile.vposter .tile-name')
        check(len(mv) == 19, f'phone and Plex movies ({len(mv)})')

        # A to Z rail, Recently Added: a letter switches to A to Z and jumps
        rail = await pg.evaluate("""(()=>{var r=document.getElementById('azRail');return [getComputedStyle(r).display, r.children.length,
            Array.prototype.filter.call(r.children,function(b){return !b.classList.contains('az-empty');}).map(function(b){return b.dataset.letter;}).join('')];})()""")
        check(rail[0] != 'none' and rail[1] == 27 and rail[2] == '#ABCDGHIJMNPRTUVZ', f'Movies shows the A to Z rail with the letters it has {rail}')
        await pg.screenshot(path=f'{SHOTS}/vsearch-rail-recent.png')
        await pg.evaluate("document.querySelector('#azRail .az-letter[data-letter=R]').click()"); await pg.wait_for_timeout(900)
        sort = await pg.evaluate("JSON.parse(localStorage.getItem('radioPlayerVideoSort')).movies")
        mv = await names(pg, '#stationsGrid .tile.vposter .tile-name')
        top = await pg.evaluate("""(()=>{var t=Array.prototype.find.call(document.querySelectorAll('#stationsGrid .tile.vposter'),function(x){return x.querySelector('.tile-name').textContent==='Rocky';});
            return Math.round(t.getBoundingClientRect().top);})()""")
        check(sort == 'az' and mv[:3] == ['12 Angry Men', 'Alien', 'Arrival'] and 40 < top < 200, f'R switched to A to Z and jumped to Rocky (top {top}) {mv[:3]}')
        await pg.screenshot(path=f'{SHOTS}/vsearch-rail-r.png')
        await pg.evaluate("window.scrollTo(0,0)"); await pg.wait_for_timeout(300)
        await pg.evaluate("document.querySelector('#azRail .az-letter[data-letter=G]').click()"); await pg.wait_for_timeout(900)
        top = await pg.evaluate("""(()=>{var t=Array.prototype.find.call(document.querySelectorAll('#stationsGrid .tile.vposter'),function(x){return x.querySelector('.tile-name').textContent==='Gladiator';});
            return Math.round(t.getBoundingClientRect().top);})()""")
        check(40 < top < 200, f'in A to Z a letter jumps straight there (Gladiator top {top})')
        # a short list (TV Shows: 5) gets no rail
        await tab(pg, 'shows')
        disp = await pg.evaluate("getComputedStyle(document.getElementById('azRail')).display")
        check(disp == 'none', f'TV Shows with only a few shows has no rail ({disp})')
        # the rail goes away off the Video page
        await pg.evaluate("document.querySelector('.mobile-nav-btn[data-nav=home]').click()"); await pg.wait_for_timeout(500)
        disp = await pg.evaluate("getComputedStyle(document.getElementById('azRail')).display")
        check(disp == 'none', f'no rail on Home ({disp})')

        # Search: Movies & TV
        await pg.evaluate("document.querySelector('.mobile-nav-btn[data-nav=search]').click()"); await pg.wait_for_timeout(400)
        await pg.tap('#searchSheetInput'); await pg.wait_for_timeout(200)
        await pg.fill('#searchSheetInput', 'breaking'); await pg.wait_for_timeout(1200)
        tabs = await names(pg, '#searchTabs .home-tab')
        check(any(x.startswith('Movies & TV') for x in tabs), f'a Movies & TV tab {tabs}')
        top = await pg.evaluate("Array.prototype.map.call(document.querySelectorAll('#stationsGrid .top-result-row'),function(r){return r.querySelector('.song-row-title').textContent+'|'+r.querySelector('.song-row-sub').textContent;})")
        check(top and top[0] == 'Breaking Bad|TV Show · 3 seasons', f'Top Results has the show first {top}')
        await pg.screenshot(path=f'{SHOTS}/vsearch-top.png')
        await pg.evaluate("Array.prototype.find.call(document.querySelectorAll('#searchTabs .home-tab'),function(b){return b.textContent.indexOf('Movies & TV')===0;}).click()"); await pg.wait_for_timeout(400)
        rows = await names(pg, '#stationsGrid .video-result-row .song-row-title')
        check(rows == ['Breaking Bad'], f'Movies & TV tab {rows}')
        await pg.evaluate("document.querySelector('#stationsGrid .video-result-row').click()"); await pg.wait_for_timeout(700)
        t = await pg.evaluate("document.querySelector('.vd-title') && document.querySelector('.vd-title').textContent")
        check(t == 'Breaking Bad', f'a show result opens the show page {t}')
        await pg.evaluate("document.getElementById('detailBackBtn').click()"); await pg.wait_for_timeout(700)
        rows = await names(pg, '#stationsGrid .video-result-row .song-row-title')
        check(rows == ['Breaking Bad'], f'Back returns to the results {rows}')

        # a Plex movie (Dune), a phone movie (Matrix), an episode title (Half Loop), a year
        async def search(q):
            await pg.fill('#searchSheetInput', q); await pg.wait_for_timeout(1000)
            await pg.evaluate("(()=>{var b=Array.prototype.find.call(document.querySelectorAll('#searchTabs .home-tab'),function(b){return b.textContent.indexOf('Movies & TV')===0;}); if(b) b.click();})()"); await pg.wait_for_timeout(400)
            return await pg.evaluate("Array.prototype.map.call(document.querySelectorAll('#stationsGrid .video-result-row'),function(r){return r.querySelector('.song-row-title').textContent+'|'+r.querySelector('.song-row-sub').textContent;})")
        r = await search('dune')
        check(r == ['Dune|Movie · 2021 · Plex'], f'a Plex movie {r}')
        img = await pg.evaluate("(document.querySelector('#stationsGrid .video-result-row img')||{}).src||''")
        check(img.startswith(REMOTE + '/photo/'), f'with its Plex poster {img[:60]}')
        await pg.screenshot(path=f'{SHOTS}/vsearch-dune.png')
        r = await search('matrix')
        check(r == ['The Matrix|Movie · 1999'], f'a phone movie {r}')
        r = await search('half loop')
        check(r == ['Half Loop|Episode · Severance S1 E2'], f'an episode by its title {r}')
        n0 = await pg.evaluate("window.__loadArgs.length")
        await pg.evaluate("document.querySelector('#stationsGrid .video-result-row').click()"); await pg.wait_for_timeout(1500)
        la = await pg.evaluate("(n)=>window.__loadArgs.slice(n).map(function(a){return a.url;})", n0)
        check(la and '/library/parts/22/' in la[-1], f'an episode result plays it {la}')
        await pg.evaluate("document.getElementById('npBackBtn').click()"); await pg.wait_for_timeout(500)
        r = await search('1999')
        check('The Matrix|Movie · 1999' in r, f'a year finds the movie {r}')
        # Home Movies switched off stays out of search
        await pg.evaluate("""(()=>{var a=JSON.parse(localStorage.getItem('radioPlayerPlexAccount')); a.excluded={'srvabcdef123':{'1':true}}; localStorage.setItem('radioPlayerPlexAccount', JSON.stringify(a));})()""")
        await pg.reload(); await pg.wait_for_timeout(2500)
        await pg.evaluate("document.querySelector('.mobile-nav-btn[data-nav=search]').click()"); await pg.wait_for_timeout(400)
        await pg.tap('#searchSheetInput'); await pg.wait_for_timeout(200)
        r = await search('dune')
        check(r == [], f'a Plex library switched off is left out of search {r}')
        # big text at 360: rows don't overflow
        await pg.set_viewport_size({'width': 360, 'height': 780})
        r = await search('matrix')
        over = await pg.evaluate("Array.prototype.some.call(document.querySelectorAll('#stationsGrid .video-result-row'),function(r){return r.scrollWidth>r.clientWidth+1;})")
        check(not over, 'rows fit at 360 wide')
        check(not errs, f'no page errors {errs[:3]}')
        await b.close()
    print('ALL PASSED' if not fails else f'FAILED {fails}')
asyncio.run(main())
