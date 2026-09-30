"""Movies and TV shows get a poster and a description from Wikipedia (mocked): the right
article (same title, a film / a TV series, the year), a folder poster still wins, and a wrong
match is fixed with the article picker.
Run: python3 tests/test_video_wiki.py (screenshots in /tmp/claude-0/t/shots)"""
import asyncio, os, json, urllib.parse
HERE = os.path.dirname(os.path.abspath(__file__))
src = open(os.path.join(HERE, 'test_video_library.py')).read()
head = src[:src.index('async def names(pg, sel)')]
head = head.replace("'/tmp/claude-0/t/srv-vlib'", "'/tmp/claude-0/t/srv-vlib'").replace('8780', '8782')
exec(head)
from playwright.async_api import async_playwright

def page(i, title, desc, img=None, extract=''):
    p = {'pageid': 100 + i, 'ns': 0, 'title': title, 'index': i + 1, 'description': desc, 'extract': extract}
    if img: p['thumbnail'] = {'source': 'https://upload.wikimedia.org/' + img, 'width': 400, 'height': 600}
    return p
SEARCH = {
 'The Matrix 1999 film': [page(0, 'The Matrix Reloaded', '2003 film', 'wiki-inception.jpg'),
                          page(1, 'The Matrix', '1999 film by the Wachowskis', 'wiki-matrix.jpg', 'The Matrix is a 1999 science fiction action film.\nIt stars Keanu Reeves.')],
 'Inception 2010 film': [page(0, 'Inception', '2010 film by Christopher Nolan', 'wiki-inception.jpg', 'Inception is a 2010 science fiction action film.')],
 'Arrival 2016 film': [page(0, 'Arrival (album)', 'album by ABBA', 'wiki-inception.jpg'), page(1, 'Arrival (film)', '2016 film by Denis Villeneuve', None, 'Arrival is a 2016 American science fiction film.')],
 'The Office TV series': [page(0, 'The Office (American TV series)', 'American mockumentary sitcom', 'wiki-office.jpg', 'The Office is an American mockumentary sitcom.')],
 'Friends TV series': [page(0, 'Friends (song)', 'song by Marshmello', 'wiki-inception.jpg'), page(1, 'Friends', 'American television sitcom (1994-2004)', 'wiki-friends.jpg', 'Friends is an American television sitcom.')],
 'Breaking Bad TV series': [page(0, 'Breaking Bad', 'American crime drama television series', 'wiki-inception.jpg', 'Breaking Bad is an American crime drama television series.')],
 'Arrival film': [page(0, 'Arrival (film)', '2016 film by Denis Villeneuve', 'wiki-matrix.jpg', 'Arrival is a 2016 film.'), page(1, 'Arrival (album)', 'album by ABBA', None)],
}
TITLES = {'Arrival (film)': page(0, 'Arrival (film)', '2016 film by Denis Villeneuve', 'wiki-matrix.jpg', 'Arrival is a 2016 American science fiction film directed by Denis Villeneuve.')}

async def wiki_route(r):
    u = r.request.url
    if 'wikipedia.org/w/api.php' in u:
        qs = urllib.parse.parse_qs(urllib.parse.urlparse(u).query)
        pages = []
        if 'gsrsearch' in qs: pages = SEARCH.get(qs['gsrsearch'][0], [])
        elif 'titles' in qs: pages = [TITLES[qs['titles'][0]]] if qs['titles'][0] in TITLES else []
        body = {'query': {'pages': {str(p['pageid']): p for p in pages}}} if pages else {}
        return await r.fulfill(status=200, content_type='application/json', headers={'Access-Control-Allow-Origin': '*'}, body=json.dumps(body))
    if 'upload.wikimedia.org/' in u:
        return await r.fulfill(status=200, content_type='image/jpeg', body=open('/tmp/claude-0/t/srv-vlib/c/' + u.rsplit('/', 1)[-1], 'rb').read())
    return await route(r)

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
        ctx = await b.new_context(viewport={'width': 390, 'height': 844}, device_scale_factor=2, is_mobile=True, has_touch=True, color_scheme='dark', locale='en-US')
        await ctx.add_init_script(MOCK)
        await ctx.add_init_script(EXT)
        pg = await ctx.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e) + ' @ ' + (e.stack or '')[:300]))
        await pg.route('**/*', wiki_route)
        await pg.goto('http://127.0.0.1:8782/index.html'); await pg.wait_for_timeout(2500)
        await pg.evaluate("document.querySelector('.mobile-nav-btn[data-nav=video]').click()"); await pg.wait_for_timeout(500)
        await pg.evaluate("document.querySelector('.video-tabs [data-vtab=movies]').click()"); await pg.wait_for_timeout(300)
        await pg.evaluate("document.getElementById('videoAddHeaderBtn').click()"); await pg.wait_for_timeout(6000)
        wiki = await pg.evaluate("JSON.parse(localStorage.getItem('radioPlayerVideoWiki')||'{}')")
        def rec(part):
            for k, v in wiki.items():
                if part in k: return v
            return None
        m = rec('Matrix')
        check(m and m.get('ok') and m['title'] == 'The Matrix' and 'wiki-matrix' in m['poster'] and m['extract'].startswith('The Matrix is'),
              f'The Matrix: the 1999 film, not Reloaded; poster and description {m and (m.get("title"), m.get("poster"))}')
        a = rec('Arrival')
        check(a and a.get('ok') and a['title'] == 'Arrival (film)', f'Arrival: the film, not the album {a and a.get("title")}')
        fr = rec('show:friends')
        check(fr and fr.get('ok') and fr['title'] == 'Friends', f'Friends: the sitcom, not the song {fr and fr.get("title")}')
        imgs = await pg.evaluate("Array.prototype.map.call(document.querySelectorAll('#stationsGrid .tile.vposter'),function(t){var i=t.querySelector('img');return t.querySelector('.tile-name').textContent+'='+(i?i.getAttribute('src'):'');})")
        check(any(x.startswith('The Matrix=') and 'wiki-matrix' in x for x in imgs) and any(x.startswith('Inception=/c/inception-poster') for x in imgs),
              f'posters: Wikipedia for The Matrix, the folder poster still wins for Inception {imgs}')
        await pg.screenshot(path=f'{SHOTS}/vwiki-movies.png')
        await pg.evaluate("document.querySelector('.video-tabs [data-vtab=shows]').click()"); await pg.wait_for_timeout(400)
        imgs = await pg.evaluate("Array.prototype.map.call(document.querySelectorAll('#stationsGrid .tile.vposter'),function(t){var i=t.querySelector('img');return t.querySelector('.tile-name').textContent+'='+(i?i.getAttribute('src'):'');})")
        check(any(x.startswith('Friends=') and 'wiki-friends' in x for x in imgs) and any(x.startswith('Breaking Bad=/c/bb-poster') for x in imgs),
              f'show posters from Wikipedia, folder poster first {imgs}')
        await pg.screenshot(path=f'{SHOTS}/vwiki-shows.png')
        # description on the show page
        await pg.evaluate("Array.prototype.find.call(document.querySelectorAll('#stationsGrid .tile.vposter'),function(t){return t.querySelector('.tile-name').textContent==='The Office';}).click()"); await pg.wait_for_timeout(500)
        ov = await pg.evaluate("[document.querySelector('.vd-overview-text') && document.querySelector('.vd-overview-text').textContent, document.querySelector('.vd-overview a') && document.querySelector('.vd-overview a').getAttribute('href')]")
        check(ov[0] and ov[0].startswith('The Office is') and 'wikipedia.org/wiki/The_Office' in (ov[1] or ''), f'show page: description with a Wikipedia link {ov}')
        await pg.screenshot(path=f'{SHOTS}/vwiki-show.png')
        await pg.evaluate("document.getElementById('detailBackBtn').click()"); await pg.wait_for_timeout(400)
        # fix a movie's info with the picker
        await pg.evaluate("document.querySelector('.video-tabs [data-vtab=movies]').click()"); await pg.wait_for_timeout(300)
        await pg.evaluate("Array.prototype.find.call(document.querySelectorAll('#stationsGrid .tile.vposter'),function(t){return t.querySelector('.tile-name').textContent==='Arrival';}).click()"); await pg.wait_for_timeout(500)
        ov = await pg.evaluate("document.querySelector('.vd-overview-text') && document.querySelector('.vd-overview-text').textContent")
        check(ov and ov.startswith('Arrival is a 2016'), f'movie page: description ({ov})')
        await pg.evaluate("document.querySelector('.vd-actions .vd-more').click()"); await pg.wait_for_timeout(200)
        items = await names(pg, '.v-menu .np-menu-item') if 'names' in globals() else await pg.evaluate("Array.prototype.map.call(document.querySelectorAll('.v-menu .np-menu-item'),function(b){return b.textContent;})")
        check('Fix Movie Info' in items, f'the movie menu has Fix Movie Info {items}')
        await pg.evaluate("Array.prototype.find.call(document.querySelectorAll('.v-menu .np-menu-item'),function(b){return b.textContent==='Fix Movie Info';}).click()"); await pg.wait_for_timeout(300)
        dlg = await pg.evaluate("[document.getElementById('artistInfoOverlay').classList.contains('open'), document.getElementById('artistInfoTitle').textContent, document.getElementById('artistInfoInput').value]")
        check(dlg[0] and dlg[1] == 'Movie info', f'the article picker opens for the movie {dlg}')
        await pg.evaluate("(()=>{var i=document.getElementById('artistInfoInput');i.value='Arrival film';i.dispatchEvent(new KeyboardEvent('keydown',{key:'Enter'}));})()"); await pg.wait_for_timeout(700)
        rows = await pg.evaluate("Array.prototype.map.call(document.querySelectorAll('#artistInfoList .artist-info-row .artist-info-name'),function(n){return n.textContent;})")
        check(rows and rows[0] == 'Arrival (film)', f'films listed first {rows}')
        await pg.screenshot(path=f'{SHOTS}/vwiki-picker.png')
        await pg.evaluate("document.querySelector('#artistInfoList .artist-info-row').click()"); await pg.wait_for_timeout(1500)
        ov = await pg.evaluate("[document.querySelector('.vd-overview-text') && document.querySelector('.vd-overview-text').textContent, document.querySelector('.vd-poster img') && document.querySelector('.vd-poster img').getAttribute('src')]")
        check(ov[0] and 'Villeneuve' in ov[0], f'choosing an article updates the page {ov}')
        await pg.screenshot(path=f'{SHOTS}/vwiki-movie.png')
        check(not errs, f'no page errors {errs[:3]}')
        await b.close()
    print('ALL PASSED' if not fails else f'FAILED {fails}')
asyncio.run(main())
