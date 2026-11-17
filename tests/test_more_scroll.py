import os, sys, json, asyncio, urllib.parse
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
src = open(os.path.join(HERE, 'test_archive_download.py')).read().split('async def notice(pg):')[0]
src = src.replace('PORT = 8881', 'PORT = 8863').replace("ROOT = '/tmp/claude-0/t/srv-iadl'", "ROOT = '/tmp/claude-0/t/srv-morescroll'")
src = src.replace("HERE = os.path.dirname(os.path.abspath(__file__))", "HERE = %r" % HERE)
exec(src)
TOTAL = 75
def docs_for(url):
    qs = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
    page = int(qs.get('page', ['1'])[0]); rows = int(qs.get('rows', ['30'])[0]); start = (page - 1) * rows
    docs = [{'identifier': f'item{i:03d}', 'title': f'Fillmore Show {i:03d} and a Long Title', 'creator': 'Mark Twain', 'year': '1971', 'mediatype': 'audio', 'downloads': 1000 - i, 'runtime': '3:00:00'}
            for i in range(start, min(TOTAL, start + rows))]
    return {'response': {'numFound': TOTAL, 'start': start, 'docs': docs}}
fails = []
def check(ok, msg):
    print(('PASS ' if ok else 'FAIL ') + msg)
    if not ok: fails.append(msg)
async def scroll_all(pg, n=10):
    for k in range(n):
        await pg.evaluate("window.scrollTo(0, document.documentElement.scrollHeight)"); await pg.wait_for_timeout(600)
async def run(B, theme):
    T = f'[{theme}]'
    c, pg, errs = await page(B, theme, [{'treeUri': 'content://tree/Music', 'name': 'Music'}])
    await pg.set_viewport_size({'width': 327, 'height': 700})
    async def adv(r):
        if 'page=1' not in r.request.url and 'page=' in r.request.url: await asyncio.sleep(0.8)
        await r.fulfill(status=200, content_type='application/json', headers={'Access-Control-Allow-Origin': '*'}, body=json.dumps(docs_for(r.request.url)))
    await c.route('https://archive.org/advancedsearch.php**', adv)
    # Search > Archive.org
    await pg.evaluate("document.getElementById('stationsGrid').innerHTML = ''; __t.ev('searchByName(\"fillmore\")')"); await pg.wait_for_timeout(2500)
    await pg.evaluate("document.getElementById('noticeOverlay').classList.remove('open'); __t.ev('searchState.tab = \"archive\"; applySearchResults()')"); await pg.wait_for_timeout(600)
    st = lambda sel: pg.evaluate(f"[document.querySelectorAll('{sel}').length, document.querySelectorAll('.ia-more-wrap').length, document.querySelectorAll('button.ia-more').length]")
    s = await st('.archive-result-row')
    check(s[0] >= 30 and s[2] == 0, f'{T} Search Archive: results, no button {s}')
    await pg.evaluate("document.querySelectorAll('.archive-result-row')[20].scrollIntoView({block:'start'})"); await pg.wait_for_timeout(100)
    await pg.wait_for_timeout(700)
    M = "[Math.round(document.querySelectorAll('.archive-result-row')[20].getBoundingClientRect().top), document.querySelectorAll('.archive-result-row').length, Math.round(scrollY)]"
    y0 = await pg.evaluate(M); y0n = y0[1]
    await pg.evaluate("document.querySelector('.ia-more-wrap').scrollIntoView({block:'end'})"); await pg.wait_for_timeout(700)
    await pg.evaluate("document.querySelectorAll('.archive-result-row')[20].scrollIntoView({block:'start'})"); await pg.wait_for_timeout(700)
    y0 = await pg.evaluate(M)
    await pg.wait_for_timeout(1500)
    y1 = await pg.evaluate(M)
    y0, y1 = y0[0], y1[0]
    check(abs(y1 - y0) <= 2, f'{T} Search Archive: loading more doesn’t move the list {y0} {y1}')
    await pg.evaluate("document.getElementById('noticeOverlay').classList.remove('open'); window.scrollTo(0, document.documentElement.scrollHeight)"); await pg.wait_for_timeout(120)
    await pg.screenshot(path=f'{SHOTS}/morescroll-{theme}-search.png')
    await scroll_all(pg)
    s = await st('.archive-result-row')
    names = await pg.evaluate("Array.prototype.map.call(document.querySelectorAll('.archive-result-row .song-row-title'), function(e){ return e.textContent; })")
    check(s[0] == 75 and s[1] == 0 and len(set(names)) == 75, f'{T} Search Archive: all 75 by scrolling, then no loading line {s}')
    # Audiobooks category
    await pg.evaluate("window.scrollTo(0,0); __t.ev('openAudiobookCategory(\"Adventure\", \"adventure\")')"); await pg.wait_for_timeout(2000)
    s = await st('.ab-row, #stationsGrid .song-row')
    check(s[0] >= 30 and s[2] == 0, f'{T} Audiobooks: books, no button {s}')
    await pg.evaluate("document.getElementById('noticeOverlay').classList.remove('open'); window.scrollTo(0, document.documentElement.scrollHeight)"); await pg.wait_for_timeout(120)
    await pg.screenshot(path=f'{SHOTS}/morescroll-{theme}-ab.png')
    await scroll_all(pg)
    s = await st('#stationsGrid .song-row')
    check(s[0] == 75 and s[1] == 0, f'{T} Audiobooks: all 75 by scrolling, line gone {s}')
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
