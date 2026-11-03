"""Build 388: archive.org results only show items Amplify can play. Each result's file list is
looked at (an item whose files archive.org keeps private, like the Funny or Die videos, is left
out); a page that is all unplayable is skipped for the next; the answers are kept, so a second
search doesn't ask again; an item that can't be checked is kept. Search and Add Channels.
Run: python3 tests/test_archive_playable.py"""
import os, sys, json, asyncio, urllib.parse
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
src = open(os.path.join(HERE, 'test_archive_download.py')).read().split('async def notice(pg):')[0]
src = src.replace('PORT = 8881', 'PORT = 8887').replace("ROOT = '/tmp/claude-0/t/srv-iadl'", "ROOT = '/tmp/claude-0/t/srv-iaplay'").replace("HERE = os.path.dirname(os.path.abspath(__file__))", "HERE = %r" % HERE)
exec(src)
TOTAL = 90
LOCKED = set(f'item{i:03d}' for i in list(range(0, 30)) + [31, 33, 35])   # page 1 all locked; three on page 2
FAILS_NET = {'item040'}
PLAYABLE = {'files': [{'name': 'a.mp4', 'format': 'h.264', 'size': '9'}]}
PRIVATE = {'files': [{'name': '__ia_thumb.jpg', 'format': 'Item Tile'}, {'name': 'a.mp4', 'format': 'MPEG4', 'private': 'true'}, {'name': 'a.ogv', 'format': 'Ogg Video', 'private': 'true'}]}
def docs_for(url):
    qs = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
    page = int(qs.get('page', ['1'])[0]); rows = int(qs.get('rows', ['30'])[0]); start = (page - 1) * rows
    return {'response': {'numFound': TOTAL, 'docs': [{'identifier': f'item{i:03d}', 'title': f'Funny Video {i:03d}', 'creator': 'Funny or Die', 'year': '2008', 'mediatype': 'movies'} for i in range(start, min(TOTAL, start + rows))]}}
fails = []
def check(ok, msg):
    print(('PASS ' if ok else 'FAIL ') + msg)
    if not ok: fails.append(msg)
async def main():
    from playwright.async_api import async_playwright
    async with async_playwright() as p:
        B = await p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
        c, pg, errs = await page(B, 'dark', [{'treeUri': 'content://tree/Music', 'name': 'Music'}])
        asked = {'search': [], 'meta': []}
        async def adv(r):
            asked['search'].append(r.request.url)
            await r.fulfill(status=200, content_type='application/json', headers={'Access-Control-Allow-Origin': '*'}, body=json.dumps(docs_for(r.request.url)))
        async def meta(r):
            id_ = r.request.url.rstrip('/').split('/')[-1]
            asked['meta'].append(id_)
            if id_ in FAILS_NET: return await r.abort()
            await r.fulfill(status=200, content_type='application/json', headers={'Access-Control-Allow-Origin': '*'}, body=json.dumps(PRIVATE if id_ in LOCKED else PLAYABLE))
        await c.route('https://archive.org/advancedsearch.php**', adv)
        await c.route('https://archive.org/metadata/**', meta)
        await pg.evaluate("document.getElementById('stationsGrid').innerHTML = ''; __t.ev('searchByName(\"funny\")')"); await pg.wait_for_timeout(3500)
        await pg.evaluate("document.getElementById('noticeOverlay').classList.remove('open'); __t.ev('searchState.tab = \"archive\"; applySearchResults()')"); await pg.wait_for_timeout(600)
        names = await pg.evaluate("Array.prototype.map.call(document.querySelectorAll('.archive-result-row .song-row-title'), function(e){ return e.textContent; })")
        pages = [urllib.parse.parse_qs(urllib.parse.urlparse(u).query)['page'][0] for u in asked['search'] if 'audio_bookspoetry' not in urllib.parse.unquote(u)]   # build 444: Search's Audiobooks tab asks too
        check(pages == ['1', '2'], f'page 1 was all unplayable, so page 2 was asked for {pages}')
        check(len(names) == 27 and 'Funny Video 031' not in names and 'Funny Video 030' in names and not any(n.endswith(('000', '029')) for n in names), f'only playable items: page 2 less its three locked ones {len(names)} {names[:3]}')
        check('Funny Video 040' in names, 'an item that couldn’t be checked is kept')
        more = await pg.evaluate("!!document.querySelector('.ia-more')")
        check(more, 'More Results still offered (90 found)')
        await pg.click('.ia-more'); await pg.wait_for_timeout(1500)
        pages = [urllib.parse.parse_qs(urllib.parse.urlparse(u).query)['page'][0] for u in asked['search'] if 'audio_bookspoetry' not in urllib.parse.unquote(u)]   # build 444: Search's Audiobooks tab asks too
        n2 = await pg.evaluate("[document.querySelectorAll('.archive-result-row').length, !!document.querySelector('.ia-more')]")
        check(pages[-1] == '3' and n2 == [57, False], f'More Results goes on from the page reached (3): 27 + 30, and that’s all {pages} {n2}')
        # the answers are kept: the same search again asks archive.org's search, not each item
        kept = await pg.evaluate("Object.keys(JSON.parse(localStorage.getItem('amplifyArchivePlayable') || '{}')).length")
        check(kept >= 89, f'answers kept on the phone ({kept})')
        asked['meta'].clear()
        await pg.evaluate("__t.ev('addChannelsState.archiveQ = \"funny\"; addChannelsTab = \"archive\"; openAddChannelsPage()')"); await pg.wait_for_timeout(2000)
        n3 = await pg.evaluate("document.querySelectorAll('.ia-item').length")
        check(n3 == 27 and asked['meta'] == ['item040'], f'Add Channels: the same 27, only the unchecked one asked about again {n3} {asked["meta"]}')
        check(not errs, f'no page errors {errs}')
        await B.close()
    print('ALL PASSED' if not fails else f'FAILS {len(fails)}')
asyncio.run(main())
