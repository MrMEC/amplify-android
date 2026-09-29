"""The yellow search button always opens the results page, on the last search, until a new
search replaces it (also across a restart). Run: python3 tests/test_last_search.py"""
import asyncio, json, os, shutil, threading, http.server, functools
from urllib.parse import urlparse, parse_qs
from playwright.async_api import async_playwright
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = '/tmp/claude-0/t/srv-last'; SHOTS = '/tmp/claude-0/t/shots'
os.makedirs(ROOT, exist_ok=True); os.makedirs(SHOTS, exist_ok=True)
shutil.copy(os.path.join(HERE, '..', 'www', 'index.html'), ROOT)
H = functools.partial(http.server.SimpleHTTPRequestHandler, directory=ROOT); H.log_message = lambda *a: None
srv = http.server.ThreadingHTTPServer(('127.0.0.1', 8776), H); threading.Thread(target=srv.serve_forever, daemon=True).start()
fails = 0
def check(ok, msg):
    global fails
    print(('PASS ' if ok else 'FAIL ') + msg); fails += 0 if ok else 1
calls = {'name': 0}
async def route(r):
    u = r.request.url; q = parse_qs(urlparse(u).query)
    if 'radio-browser' in u:
        if 'name' in q: calls['name'] += 1
        word = (q.get('name') or q.get('tag') or ['top'])[0]
        return await r.fulfill(status=200, content_type='application/json', body=json.dumps(
            [{'name': '%s station %d' % (word, i), 'url_resolved': 'http://s/%s%d' % (word, i), 'stationuuid': '%s%d' % (word, i), 'favicon': '', 'tags': 'x', 'codec': 'MP3'} for i in range(4)]))
    if 'itunes.apple.com/' in u:
        cb = (q.get('callback') or [''])[0]; term = (q.get('term') or ['x'])[0]
        body = json.dumps({'resultCount': 1, 'results': [{'wrapperType': 'track', 'kind': 'podcast', 'collectionId': 5, 'collectionName': term + ' pod', 'artistName': 'A', 'artworkUrl600': ''}]})
        return await r.fulfill(status=200, content_type='application/javascript', body=cb + '(' + body + ');')
    return await r.continue_()

async def results(pg):
    return await pg.evaluate("""(()=>{var a=document.querySelector('#searchTabs .home-tab.active');
      return {heading:document.getElementById('stationsHeading').textContent, tab:a?a.textContent:null,
        names:Array.prototype.map.call(document.querySelectorAll('#stationsGrid .tile-name'),function(n){return n.textContent;}).slice(0,2)};})()""")
async def sheet_search(pg, text):
    await pg.evaluate("(t)=>{var i=document.getElementById('searchSheetInput');i.value=t;document.getElementById('searchSheetGo').click();}", text)
    await pg.wait_for_timeout(1200)
async def go_home(pg):
    await pg.evaluate("document.getElementById('searchSheetClose').click()"); await pg.wait_for_timeout(200)
    await pg.evaluate("document.querySelector('.mobile-nav-btn[data-nav=home]').click()"); await pg.wait_for_timeout(700)
async def yellow(pg, text=''):
    await pg.evaluate("document.querySelector('.mobile-nav-btn[data-nav=search]').click()"); await pg.wait_for_timeout(300)
    await pg.evaluate("(t)=>{document.getElementById('searchSheetInput').value=t;document.getElementById('searchSheetGo').click();}", text)
    await pg.wait_for_timeout(900)

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
        ctx = await b.new_context(viewport={'width': 390, 'height': 844}, device_scale_factor=2, is_mobile=True, has_touch=True, color_scheme='dark')
        pg = await ctx.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.route('**/*', route)
        await pg.goto('http://127.0.0.1:8776/index.html'); await pg.wait_for_timeout(2500)

        await yellow(pg, '')
        r = await results(pg)
        check(r['heading'] == 'Search' and not r['names'], f'no search yet: yellow opens an empty results page {r}')

        await sheet_search(pg, 'news')
        r = await results(pg)
        check(r['heading'] == 'Results for "news"' and r['names'][0].startswith('news'), f'search runs {r}')
        n0 = calls['name']
        await pg.evaluate("Array.prototype.find.call(document.querySelectorAll('#searchTabs .home-tab'),function(b){return /podcast/i.test(b.textContent);}).click()"); await pg.wait_for_timeout(400)
        await go_home(pg)
        check(await pg.evaluate("document.body.classList.contains('home-stacked')"), 'navigated away (Home)')
        await yellow(pg, '')
        r = await results(pg)
        check(r['heading'] == 'Results for "news"' and r['tab'] and 'odcast' in r['tab'], f'empty box + yellow: last results, same tab {r}')
        check(calls['name'] == n0, f'...without searching again ({calls["name"]-n0} extra requests)')
        await pg.screenshot(path=f'{SHOTS}/last-search-back.png')
        await go_home(pg)
        await yellow(pg, 'news')
        check((await results(pg))['heading'] == 'Results for "news"' and calls['name'] == n0, 'same words + yellow: same results, no new request')

        # Pasting a stream link is not a search.
        await go_home(pg)
        await yellow(pg, 'http://example.com/live.mp3'); await pg.wait_for_timeout(400)
        await go_home(pg)
        await yellow(pg, '')
        check((await results(pg))['heading'] == 'Results for "news"', 'a pasted stream link leaves the last search alone')

        # Restart: still there.
        await pg.reload(); await pg.wait_for_timeout(2500)
        await yellow(pg, '')
        r = await results(pg)
        check(r['heading'] == 'Results for "news"' and r['names'] and r['tab'] and 'odcast' in r['tab'], f'after a restart: same results and tab {r}')
        check(calls['name'] == n0, 'restored without searching again')

        # A new search replaces it.
        await sheet_search(pg, 'jazz')
        await go_home(pg)
        await yellow(pg, '')
        r = await results(pg)
        check(r['heading'] == 'Results for "jazz"', f'a new search replaces the kept one {r}')
        await pg.evaluate("document.querySelector('.mobile-nav-btn[data-nav=search]').click()")
        check(not errs, f'no page errors {errs[:3]}')
        await b.close()
    print('ALL PASSED' if not fails else f'FAILED {fails}')
asyncio.run(main())
