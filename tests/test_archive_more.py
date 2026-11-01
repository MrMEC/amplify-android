"""Build 385-386: archive.org search results come 30 at a time. With more than 30, a More Results
button under them loads the next 30, again and again until there are no more -- in Search's
Archive tab and in Add Channels > Archive.org. Phone, dark and light.
Run: python3 tests/test_archive_more.py (screenshots in /tmp/claude-0/t/shots)"""
import os, sys, json, asyncio, urllib.parse
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
src = open(os.path.join(HERE, 'test_archive_download.py')).read().split('async def notice(pg):')[0]
src = src.replace('PORT = 8881', 'PORT = 8884').replace("ROOT = '/tmp/claude-0/t/srv-iadl'", "ROOT = '/tmp/claude-0/t/srv-iamore'")
src = src.replace("HERE = os.path.dirname(os.path.abspath(__file__))", "HERE = %r" % HERE)
exec(src)
TOTAL = 75
def docs_for(url):
    qs = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
    page = int(qs.get('page', ['1'])[0]); rows = int(qs.get('rows', ['30'])[0])
    start = (page - 1) * rows
    q = qs.get('q', [''])[0]
    kind = 'movies' if 'mediatype:(movies)' in q else 'audio'
    docs = [{'identifier': f'item{i:03d}', 'title': (f'Fillmore Show {i:03d}' if i else 'Fillmore Show 000, the complete late show at the Fillmore East, New York City, March 1971'), 'creator': 'The Band', 'year': '1970', 'mediatype': kind, 'downloads': 1000 - i}
            for i in range(start, min(TOTAL, start + rows))]
    return {'response': {'numFound': TOTAL, 'start': start, 'docs': docs}}
fails = []
def check(ok, msg):
    print(('PASS ' if ok else 'FAIL ') + msg)
    if not ok: fails.append(msg)
async def run(B, theme):
    T = f'[{theme}]'
    c, pg, errs = await page(B, theme, [{'treeUri': 'content://tree/Music', 'name': 'Music'}])
    asked = []
    async def adv(r):
        asked.append(r.request.url)
        await r.fulfill(status=200, content_type='application/json', headers={'Access-Control-Allow-Origin': '*'}, body=json.dumps(docs_for(r.request.url)))
    await c.route('https://archive.org/advancedsearch.php**', adv)
    await pg.evaluate("document.getElementById('stationsGrid').innerHTML = ''; __t.ev('searchByName(\"fillmore\")')"); await pg.wait_for_timeout(2500)
    await pg.evaluate("document.getElementById('noticeOverlay').classList.remove('open'); __t.ev('searchState.tab = \"archive\"; applySearchResults()')"); await pg.wait_for_timeout(600)
    def state(sel):
        return pg.evaluate(f"[document.querySelectorAll('{sel}').length, !!document.querySelector('.ia-more'), (document.getElementById('resultCount') || {{}}).textContent]")
    s = await state('.archive-result-row')
    check(s[0] == 30 and s[1], f'{T} Search: 30 results, then More Results {s}')
    await pg.evaluate("document.querySelector('.ia-more').scrollIntoView({block:'center'})"); await pg.wait_for_timeout(200)
    await pg.screenshot(path=f'{SHOTS}/iamore-{theme}-search.png')
    y0 = await pg.evaluate("window.scrollY")
    await pg.click('.ia-more'); await pg.wait_for_timeout(800)
    s = await state('.archive-result-row'); y1 = await pg.evaluate("window.scrollY")
    names = await pg.evaluate("Array.prototype.map.call(document.querySelectorAll('.archive-result-row .song-row-title'), function(e){ return e.textContent; })")
    check(s[0] == 60 and s[1] and names[30] == 'Fillmore Show 030' and len(set(names)) == 60, f'{T} More Results adds the next 30, after the first, and offers more {s} {names[29:31]}')
    check(abs(y1 - y0) < 5, f'{T} the page stays where it was {y0} {y1}')
    await pg.click('.ia-more'); await pg.wait_for_timeout(800)
    s = await state('.archive-result-row')
    check(s[0] == 75 and not s[1], f'{T} the last 15, and no More Results once there are no more {s}')
    pages = [urllib.parse.parse_qs(urllib.parse.urlparse(u).query).get('page', ['?'])[0] for u in asked]
    check(pages[-3:] == ['1', '2', '3'], f'{T} pages 1, 2, 3 asked for {pages}')
    # Build 386: titles take two lines
    h = await pg.evaluate("(function(){ var t = document.querySelector('.archive-result-row .song-row-title'); return [Math.round(t.getBoundingClientRect().height), parseFloat(getComputedStyle(t).fontSize)]; })()")
    check(h[0] > h[1] * 2 and h[0] < h[1] * 3, f'{T} a long title takes two lines {h}')
    await pg.evaluate("window.scrollTo(0, 0)"); await pg.wait_for_timeout(100)
    await pg.screenshot(path=f'{SHOTS}/iamore-{theme}-top.png')
    # the filter: All by default; Video Only asks archive.org for videos, and is kept
    seg = await pg.evaluate("Array.prototype.map.call(document.querySelectorAll('.ia-kind .mv-seg-btn'), function(b){ return b.textContent + (b.classList.contains('on') ? '*' : ''); })")
    check(seg == ['All*', 'Audio Only', 'Video Only'], f'{T} All / Audio Only / Video Only, All to start {seg}')
    asked.clear()
    await pg.click('.ia-kind .mv-seg-btn[data-kind=video]'); await pg.wait_for_timeout(900)
    q = urllib.parse.parse_qs(urllib.parse.urlparse(asked[-1]).query)['q'][0] if asked else ''
    s = await state('.archive-result-row')
    subs = await pg.evaluate("Array.prototype.map.call(document.querySelectorAll('.archive-result-row .song-row-sub'), function(e){ return e.textContent.split(' ')[0]; }).slice(0, 3)")
    check('mediatype:(movies)' in q and 'mediatype:(audio' not in q and s[0] == 30 and s[1] and subs == ['Video'] * 3, f'{T} Video Only: archive.org is asked for videos only, 30 again with More Results {s} {subs}')
    await pg.screenshot(path=f'{SHOTS}/iamore-{theme}-video.png')
    await pg.reload(); await pg.wait_for_timeout(2500)
    await pg.evaluate("document.getElementById('stationsGrid').innerHTML = ''; __t.ev('searchByName(\"fillmore\")')"); await pg.wait_for_timeout(2000)
    await pg.evaluate("document.getElementById('noticeOverlay').classList.remove('open'); __t.ev('searchState.tab = \"archive\"; applySearchResults()')"); await pg.wait_for_timeout(600)
    on = await pg.evaluate("(document.querySelector('.ia-kind .mv-seg-btn.on') || {}).textContent")
    q = urllib.parse.parse_qs(urllib.parse.urlparse(asked[-1]).query)['q'][0]
    check(on == 'Video Only' and 'mediatype:(movies)' in q, f'{T} after the app is closed and opened, still Video Only {on}')
    await pg.click('.ia-kind .mv-seg-btn[data-kind=audio]'); await pg.wait_for_timeout(900)
    q = urllib.parse.parse_qs(urllib.parse.urlparse(asked[-1]).query)['q'][0]
    check('mediatype:(audio OR etree)' in q, f'{T} Audio Only asks for audio {q[-40:]}')
    await pg.click('.ia-kind .mv-seg-btn[data-kind=all]'); await pg.wait_for_timeout(900)
    # the More menu: Play Next and Add to Queue put the item's files in Up Next
    await pg.evaluate("document.querySelector('.archive-result-row .ia-more-btn').click()"); await pg.wait_for_timeout(200)
    await pg.evaluate("document.getElementById('iaMenuNext').click()"); await pg.wait_for_timeout(800)
    un = await pg.evaluate("__t.ev('upNext').map(function(t){ return t.name; })")
    check(un == ['Song One', 'Song Two'], f'{T} Play Next puts the item\u2019s songs next {un}')
    await pg.evaluate("document.querySelectorAll('.archive-result-row .ia-more-btn')[1].click()"); await pg.wait_for_timeout(200)
    await pg.evaluate("document.getElementById('iaMenuQueue').click()"); await pg.wait_for_timeout(800)
    un2 = await pg.evaluate("__t.ev('upNext').length")
    check(un2 >= 2, f'{T} Add to Queue adds at the end {un2}')
    # Add Channels > Archive.org
    asked.clear()
    await pg.evaluate("__t.ev('addChannelsState.archiveQ = \"fillmore\"; addChannelsTab = \"archive\"; openAddChannelsPage()')"); await pg.wait_for_timeout(1500)
    await pg.evaluate("document.getElementById('noticeOverlay').classList.remove('open')")
    s = await state('.ia-item')
    check(s[0] == 30 and s[1], f'{T} Add Channels: 30, then More Results {s}')
    seg = await pg.evaluate("Array.prototype.map.call(document.querySelectorAll('.ia-kind .mv-seg-btn'), function(b){ return b.textContent + (b.classList.contains('on') ? '*' : ''); })")
    check(seg == ['All*', 'Audio Only', 'Video Only'], f'{T} Add Channels has the same filter {seg}')
    await pg.evaluate("document.querySelector('.ia-more').scrollIntoView({block:'center'})"); await pg.wait_for_timeout(200)
    await pg.screenshot(path=f'{SHOTS}/iamore-{theme}-addch.png')
    await pg.click('.ia-more'); await pg.wait_for_timeout(800)
    s = await state('.ia-item')
    check(s[0] == 60 and s[1], f'{T} Add Channels: 60 and More Results again {s}')
    await pg.click('.ia-more'); await pg.wait_for_timeout(800)
    s = await state('.ia-item')
    check(s[0] == 75 and not s[1], f'{T} Add Channels: all 75, no button {s}')
    # 30 or fewer: no button
    global TOTAL
    TOTAL = 12
    await pg.evaluate("__t.ev('addChannelsState.archiveQ = \"band\"; renderAddChannels(true)')"); await pg.wait_for_timeout(1200)
    s = await state('.ia-item')
    check(s[0] == 12 and not s[1], f'{T} 12 results: no More Results {s}')
    TOTAL = 75
    check(not errs, f'{T} no page errors {errs}')
    await c.close()
async def main():
    from playwright.async_api import async_playwright
    async with async_playwright() as p:
        B = await p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
        for th in ('dark', 'light'): await run(B, th)
        await B.close()
    print('ALL PASSED' if not fails else f'FAILS {len(fails)}')
asyncio.run(main())
