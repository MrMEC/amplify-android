"""Build 661 (Mark): Add Channels has no Show More / More Results buttons. Channel lists (All etc.)
and Add Channels > Archive.org load more as the end of the list comes into view, added under the
rows already there (the page stays where it is). Phone size (327 wide, dpr 3.3), dark and light.
Run: python3 tests/test_addch_scroll.py (screenshots in /tmp/claude-0/t/shots)"""
import os, sys, json, asyncio, urllib.parse
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
src = open(os.path.join(HERE, 'test_archive_download.py')).read().split('async def notice(pg):')[0]
src = src.replace('PORT = 8881', 'PORT = 8862').replace("ROOT = '/tmp/claude-0/t/srv-iadl'", "ROOT = '/tmp/claude-0/t/srv-addscroll'")
src = src.replace("HERE = os.path.dirname(os.path.abspath(__file__))", "HERE = %r" % HERE)
exec(src)
TOTAL = 75
def docs_for(url):
    qs = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
    page = int(qs.get('page', ['1'])[0]); rows = int(qs.get('rows', ['30'])[0]); start = (page - 1) * rows
    docs = [{'identifier': f'item{i:03d}', 'title': f'Fillmore East Late Show, March 1971, Reel {i:03d}', 'creator': 'The Allman Brothers Band', 'year': '1971', 'mediatype': 'movies', 'downloads': 1000 - i}
            for i in range(start, min(TOTAL, start + rows))]
    return {'response': {'numFound': TOTAL, 'start': start, 'docs': docs}}
CH = [{'id': f'Ch{i}.us', 'name': f'Channel {i:03d} ' + ('Classic Movies and Westerns Around the Clock' if i % 7 == 0 else 'News'), 'country': 'US', 'cats': ['news'], 'url': f'https://example.com/{i}.m3u8', 'logo': '', 'src': 'iptv'} for i in range(400)]
fails = []
def check(ok, msg):
    print(('PASS ' if ok else 'FAIL ') + msg)
    if not ok: fails.append(msg)
async def run(B, theme):
    T = f'[{theme}]'
    c, pg, errs = await page(B, theme, [{'treeUri': 'content://tree/Music', 'name': 'Music'}])
    await pg.set_viewport_size({'width': 327, 'height': 700})
    async def adv(r):
        await r.fulfill(status=200, content_type='application/json', headers={'Access-Control-Allow-Origin': '*'}, body=json.dumps(docs_for(r.request.url)))
    await c.route('https://archive.org/advancedsearch.php**', adv)
    # --- All tab: 400 channels
    await pg.evaluate("__t.ev('iptvIndex = { at: Date.now(), list: %s, cats: {news: \"News\"}, countries: {US: \"United States\"} }; addChannelsTab = \"all\"; addChannelsState.country = \"\"; openAddChannelsPage()')" % json.dumps(json.dumps(CH))[1:-1].replace("'", "\\'"))
    await pg.wait_for_timeout(1500)
    await pg.evaluate("document.getElementById('noticeOverlay').classList.remove('open')")
    st = lambda: pg.evaluate("[document.querySelectorAll('.ch-list .ch-row').length, document.querySelectorAll('.lc-more-sentinel').length, document.querySelectorAll('.ch-more').length, Math.round(scrollY)]")
    s = await st()
    check(s[0] == 60 and s[1] == 1 and s[2] == 0, f'{T} All: 60 channels, a Loading line, no Show More button {s}')
    await pg.evaluate("window.scrollTo(0, 0)"); await pg.wait_for_timeout(150)
    await pg.screenshot(path=f'{SHOTS}/addscroll-{theme}-top.png')
    for k in range(12):
        await pg.evaluate("window.scrollTo(0, document.documentElement.scrollHeight)"); await pg.wait_for_timeout(350)
    s = await st()
    names = await pg.evaluate("Array.prototype.map.call(document.querySelectorAll('.ch-list .ch-row .ch-name'), function(e){ return e.textContent; })")
    check(s[0] == 400 and s[1] == 0 and len(set(names)) == 400, f'{T} All: scrolling loads every channel once, then the Loading line goes {s[:3]} {len(set(names))}')
    # partway: scroll so the 60th is near, check no jump
    await pg.evaluate("__t.ev('addChannelsState.shown = 60; renderAddChannels(true)')"); await pg.wait_for_timeout(500)
    await pg.evaluate("document.querySelectorAll('.ch-list .ch-row')[50].scrollIntoView({block:'start'})"); await pg.wait_for_timeout(100)
    top0 = await pg.evaluate("[Math.round(document.querySelectorAll('.ch-list .ch-row')[50].getBoundingClientRect().top), document.querySelectorAll('.ch-list .ch-row').length]")
    await pg.wait_for_timeout(800)
    top1 = await pg.evaluate("[Math.round(document.querySelectorAll('.ch-list .ch-row')[50].getBoundingClientRect().top), document.querySelectorAll('.ch-list .ch-row').length]")
    check(top1[1] > 60 and abs(top1[0] - top0[0]) <= 1, f'{T} All: the next rows come in under the list and nothing moves {top0} {top1}')
    await pg.evaluate("document.querySelectorAll('.ch-list .ch-row')[55].scrollIntoView({block:'center'})"); await pg.wait_for_timeout(200)
    await pg.screenshot(path=f'{SHOTS}/addscroll-{theme}-mid.png')
    # sentinel visible while loading (block the load by checking the last screen after the 400)
    await pg.evaluate("window.scrollTo(0, document.documentElement.scrollHeight)"); await pg.wait_for_timeout(300)
    await pg.screenshot(path=f'{SHOTS}/addscroll-{theme}-end.png')
    # --- Archive.org tab
    await pg.evaluate("window.scrollTo(0,0); __t.ev('addChannelsState.archiveQ = \"fillmore\"; addChannelsTab = \"archive\"; openAddChannelsPage()')"); await pg.wait_for_timeout(1500)
    await pg.evaluate("document.getElementById('noticeOverlay').classList.remove('open')")
    ia = lambda: pg.evaluate("[document.querySelectorAll('.ia-item').length, document.querySelectorAll('.lc-more-sentinel').length, document.querySelectorAll('.ia-more').length]")
    s = await ia()
    check(s[0] >= 30 and s[2] == 0, f'{T} Archive.org: results, no More Results button {s}')
    await pg.evaluate("document.querySelectorAll('.ia-item')[26].scrollIntoView({block:'center'})"); await pg.wait_for_timeout(200)
    await pg.screenshot(path=f'{SHOTS}/addscroll-{theme}-ia.png')
    for k in range(8):
        await pg.evaluate("window.scrollTo(0, document.documentElement.scrollHeight)"); await pg.wait_for_timeout(500)
    s = await ia()
    ids = await pg.evaluate("Array.prototype.map.call(document.querySelectorAll('.ia-item'), function(e){ return e.textContent; })")
    last = await pg.evaluate("(function(){ var b=document.querySelector('.ia-item:last-of-type'); var n=b.parentNode.lastElementChild; return n.className; })()")
    check(s[0] == 75 and s[1] == 0 and len(set(ids)) == 75, f'{T} Archive.org: scrolling loads all 75 in order, then stops {s} {len(set(ids))} last={last}')
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
