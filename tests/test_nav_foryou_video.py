"""Home For You row (called My Stations since build 120), Video tab (Stations removed), true back links for saved searches and
podcast pages. Run: python3 tests/test_nav_foryou_video.py (screenshots in /tmp/claude-0/t/shots)"""
import asyncio, json, os, shutil, threading, http.server, functools
from playwright.async_api import async_playwright
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = '/tmp/claude-0/t/srv-nav'; SHOTS = '/tmp/claude-0/t/shots'
os.makedirs(ROOT, exist_ok=True); os.makedirs(SHOTS, exist_ok=True)
shutil.copy(os.path.join(HERE, '..', 'www', 'index.html'), ROOT)
H = functools.partial(http.server.SimpleHTTPRequestHandler, directory=ROOT); H.log_message = lambda *a: None
srv = http.server.ThreadingHTTPServer(('127.0.0.1', 8774), H); threading.Thread(target=srv.serve_forever, daemon=True).start()
SEED = {'radioPlayerCustomSearches': [{'id': 's1', 'label': 'Smooth Jazz', 'query': 'smooth jazz'}, {'id': 's2', 'label': 'News Talk', 'query': 'news'}],
        'radioPlayerRecent': [{'name': 'Rock 1', 'urlToResolve': 'http://rock/s', 'stationuuid': 'u2'}]}
STATIONS = [{'name': 'Station %d' % i, 'url_resolved': 'http://s/%d' % i, 'stationuuid': 'x%d' % i, 'favicon': '', 'tags': 'news', 'codec': 'MP3', 'country': 'US'} for i in range(6)]
SHOW = {'wrapperType': 'track', 'kind': 'podcast', 'collectionId': 777, 'collectionName': 'News Pod', 'artistName': 'NP', 'artworkUrl600': '', 'feedUrl': 'http://f', 'trackCount': 3}
fails = 0
def check(ok, msg):
    global fails
    print(('PASS ' if ok else 'FAIL ') + msg); fails += 0 if ok else 1

async def route(r):
    u = r.request.url
    if 'radio-browser' in u: return await r.fulfill(status=200, content_type='application/json', body=json.dumps(STATIONS))
    if 'itunes.apple.com/' in u:
        # JSONP: the page asks for callback=<name> and loads it as a script.
        from urllib.parse import urlparse, parse_qs
        cb = (parse_qs(urlparse(u).query).get('callback') or [''])[0]
        body = json.dumps({'resultCount': 1, 'results': [SHOW]})
        return await r.fulfill(status=200, content_type='application/javascript' if cb else 'application/json', body=(cb + '(' + body + ');') if cb else body)
    return await r.continue_()

async def info(pg):
    return await pg.evaluate("""(()=>{var b=document.getElementById('detailBackBtn');
      var act=document.querySelector('.mobile-nav-btn.active');
      return {heading:document.getElementById('stationsHeading').textContent, back: b.style.display==='none'?null:document.getElementById('detailBackLabel').textContent,
              nav: act?act.dataset.nav:null, home: document.body.classList.contains('home-stacked')};})()""")
async def click_back(pg):
    await pg.evaluate("document.getElementById('detailBackBtn').click()"); await pg.wait_for_timeout(700)

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
        ctx = await b.new_context(viewport={'width': 390, 'height': 844}, device_scale_factor=2, is_mobile=True, has_touch=True)
        await ctx.add_init_script('(function(){var s=%s;for(var k in s)localStorage.setItem(k,JSON.stringify(s[k]));})()' % json.dumps(SEED))
        pg = await ctx.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.route('**/*', route)
        await pg.goto('http://127.0.0.1:8774/index.html'); await pg.wait_for_timeout(3000)

        navs = await pg.evaluate("Array.prototype.map.call(document.querySelectorAll('.mobile-nav-btn'),function(b){return b.dataset.nav+':'+b.textContent.trim();})")
        check(navs == ['home:Home', 'library:Library', 'podcasts:Podcasts', 'video:Video', 'search:Search'], f'bottom nav {navs}')
        order = await pg.evaluate("""(()=>{var ids=['recentSection','forYouSection','homeTopHeading'];
          return ids.map(function(i){var e=document.getElementById(i);return e&&e.offsetParent?Math.round(e.getBoundingClientRect().top+scrollY):null;});})()""")
        check(order[0] is not None and order[1] is not None and order[0] < order[1] < order[2], f'For You sits under Continue Listening, above Top Stations {order}')
        tiles = await pg.evaluate("Array.prototype.map.call(document.querySelectorAll('#forYouGrid .tile-name'),function(n){return n.textContent;})")
        check(tiles == ['Smooth Jazz', 'News Talk'], f'For You row tiles {tiles}')
        await pg.evaluate("document.getElementById('forYouSection').scrollIntoView({block:'center'})"); await pg.wait_for_timeout(300)
        await pg.screenshot(path=f'{SHOTS}/nav-home-foryou.png')

        # Home -> saved search -> back to Home
        await pg.evaluate("document.querySelector('#forYouGrid .tile').click()"); await pg.wait_for_timeout(900)
        i = await info(pg)
        check(i['heading'] == 'Smooth Jazz' and i['back'] == 'Home' and i['nav'] == 'home', f'saved search from Home: back says Home {i}')
        await click_back(pg)
        check((await info(pg))['home'], 'back returns to Home')

        # Home -> For You page -> saved search -> back to For You -> back to Home
        await pg.evaluate("document.getElementById('forYouHomeHeading').click()"); await pg.wait_for_timeout(700)
        i = await info(pg)
        check(i['heading'] == 'My Stations' and i['back'] == 'Home', f'For You page has a back link to Home {i}')
        add = await pg.evaluate("getComputedStyle(document.getElementById('forYouAddHeaderBtn')).display!=='none'")
        check(add, 'For You page keeps Add Search')
        await pg.screenshot(path=f'{SHOTS}/nav-foryou-page.png')
        await pg.evaluate("document.querySelector('#stationsGrid .tile').click()"); await pg.wait_for_timeout(900)
        i = await info(pg)
        check(i['back'] == 'My Stations', f'saved search from the For You page: back says For You {i}')
        await click_back(pg)
        check((await info(pg))['heading'] == 'My Stations', 'back returns to the For You page')
        await click_back(pg)
        check((await info(pg))['home'], '...and then Home')

        # Video tab, and a saved search opened from the drawer while on Video comes back to Video
        await pg.evaluate("document.querySelector('.mobile-nav-btn[data-nav=video]').click()"); await pg.wait_for_timeout(700)
        i = await info(pg)
        grid = await pg.evaluate("(document.querySelector('#stationsGrid .grid-section-label')||{}).textContent||''")
        check(i['heading'] == 'Video' and i['back'] is None and i['nav'] == 'video' and grid.startswith('My Channels'), f'Video page: My Channels, tab active {i} {grid}')
        await pg.screenshot(path=f'{SHOTS}/nav-video.png')
        await pg.evaluate("document.querySelector('#customSearchList .cs-row, #customSearchList [class*=cs]').click()"); await pg.wait_for_timeout(900)
        i = await info(pg)
        check(i['back'] == 'Video', f'saved search opened while on Video: back says Video {i}')
        await click_back(pg)
        check((await info(pg))['heading'] == 'Video', 'back returns to Video')

        # Search -> Podcasts tab -> show page -> back to the results on the Podcasts tab
        await pg.evaluate("(()=>{var i=document.getElementById('searchInput');i.value='news';document.getElementById('searchBtn').click();})()"); await pg.wait_for_timeout(1500)
        await pg.evaluate("Array.prototype.find.call(document.querySelectorAll('#searchTabs .home-tab, .search-tabs .home-tab'),function(b){return /podcast/i.test(b.textContent);}).click()"); await pg.wait_for_timeout(500)
        await pg.evaluate("document.querySelector('#stationsGrid .tile').click()"); await pg.wait_for_timeout(1500)
        i = await info(pg)
        check(i['back'] == 'Results' and i['nav'] == 'podcasts', f'podcast from search: back says Results, not Podcasts {i}')
        await pg.screenshot(path=f'{SHOTS}/nav-podcast-from-search.png')
        await click_back(pg); await pg.wait_for_timeout(800)
        tab = await pg.evaluate("(()=>{var a=document.querySelector('#searchTabs .home-tab.active, .search-tabs .home-tab.active');return a?a.textContent:null;})()")
        check(tab and 'odcast' in tab, f'back lands on the search results, Podcasts tab ({tab})')

        # Podcasts page -> show -> back to Podcasts
        await pg.evaluate("document.querySelector('.mobile-nav-btn[data-nav=podcasts]').click()"); await pg.wait_for_timeout(800)
        check((await info(pg))['nav'] == 'podcasts', 'Podcasts tab opens')
        # drawer: For You + Video entries, no Stations
        side = await pg.evaluate("Array.prototype.map.call(document.querySelectorAll('.sidebar-row-link .sidebar-row-label'),function(e){return e.textContent.trim();})")
        check('Stations' not in side and 'My Stations' in side and 'Video' in side, f'sidebar/drawer entries {side}')
        await pg.evaluate("document.getElementById('hamburgerBtn').click()"); await pg.wait_for_timeout(500)
        await pg.screenshot(path=f'{SHOTS}/nav-drawer.png')
        check(not errs, f'no page errors {errs[:3]}')
        await b.close()
    print('ALL PASSED' if not fails else f'FAILED {fails}')
asyncio.run(main())
