"""Build 444: audiobooks from more places. The Audiobooks find box and main Search's new Audiobooks tab both
search archive.org's Audio Books & Poetry collection (LibriVox and the rest) and Project Gutenberg's audiobooks
(gutendex.com), archive.org first, a Gutenberg copy of a book already listed left out. A Gutenberg book plays
from the MP3s its gutenberg.org page links (or the MP3 folder an older book keeps), in part order, as Up
Next; it is remembered in Continue Listening and its cover can be changed like any book's. A non-LibriVox
archive.org book is remembered as a book once played. Either library failing leaves the other's books.
Phone, dark and light. Run: python3 tests/test_audiobook_sources.py (screenshots in /tmp/claude-0/t/shots)"""
import os, sys, json, asyncio, urllib.parse
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
src = open(os.path.join(HERE, 'test_audiobooks.py')).read().split('async def run(B, theme):')[0]
src = src.replace("HERE = os.path.dirname(os.path.abspath(__file__))", "HERE = %r" % HERE).replace('PORT = 8893', 'PORT = 8894')
exec(src)

GB_BOOKS = {
    # a Gutenberg copy of a book archive.org already lists: left out
    '7000': {'id': 7000, 'title': 'Twain Book 00', 'authors': [{'name': 'Twain, Mark'}], 'formats': {}},
    '9999': {'id': 9999, 'title': 'The Prince and the Pauper', 'authors': [{'name': 'Twain, Mark'}], 'formats': {'audio/mpeg': 'http://www.gutenberg.org/files/9999/mp3/9999-01.mp3'}},
    '8888': {'id': 8888, 'title': 'Life on the Mississippi', 'authors': [{'name': 'Twain, Mark (Samuel Clemens)'}], 'formats': {}},
    '5555': {'id': 5555, 'title': 'Roughing It', 'authors': [{'name': 'Twain, Mark'}], 'formats': {}},
}
gb_asked = []
gb_down = {'on': False}
gb_delay = {'s': 1.5}   # Gutendex is slow live
ia_down = {'on': False}

async def run(B, theme):
    T = f'[{theme}]'
    c, pg, errs = await page(B, theme, [{'treeUri': 'content://tree/Music', 'name': 'Music'}])
    async def adv(r):
        if ia_down['on']: await r.abort(); return
        asked['search'].append(r.request.url)
        body = adv_body(r.request.url)
        q = urllib.parse.parse_qs(urllib.parse.urlparse(r.request.url).query)['q'][0]
        if 'pauper' in q.lower():
            body = {'response': {'numFound': 1, 'docs': [dict(doc(BOOKS[0]), identifier='prince_pauper_reading', title='The Prince and the Pauper (dramatic reading)', creator='Mark Twain')]}}
        await r.fulfill(status=200, content_type='application/json', headers={'Access-Control-Allow-Origin': '*'}, body=json.dumps(body))
    async def meta(r):
        id_ = r.request.url.rstrip('/').split('/')[-1]; asked['meta'].append(id_)
        await r.fulfill(status=200, content_type='application/json', headers={'Access-Control-Allow-Origin': '*'}, body=json.dumps(meta_body(id_)))
    async def audio(r):
        await r.fulfill(status=200, content_type='audio/mpeg', headers={'Access-Control-Allow-Origin': '*'}, path=ROOT + '/files/01 - Song One.mp3')
    async def img(r):
        await r.fulfill(status=200, content_type='image/jpeg', headers={'Access-Control-Allow-Origin': '*'}, path=ROOT + '/files/cover.jpg')
    async def gutendex(r):
        if gb_down['on']: await r.abort(); return
        gb_asked.append(r.request.url)
        await asyncio.sleep(gb_delay['s'])
        qs = urllib.parse.parse_qs(urllib.parse.urlparse(r.request.url).query)
        term = qs.get('search', [''])[0].lower(); pg_ = int(qs.get('page', ['1'])[0])
        res = []; nxt = None
        if 'twain' in term:
            res = [GB_BOOKS['7000'], GB_BOOKS['9999'], GB_BOOKS['8888']] if pg_ == 1 else [GB_BOOKS['5555']]
            nxt = 'https://gutendex.com/books/?mime_type=audio&page=2&search=twain' if pg_ == 1 else None
        elif 'pauper' in term:
            res = [GB_BOOKS['9999']]
        await r.fulfill(status=200, content_type='application/json', headers={'Access-Control-Allow-Origin': '*'},
                        body=json.dumps({'count': 4 if 'twain' in term else len(res), 'next': nxt, 'previous': None, 'results': res}))
    async def gbsite(r):
        u = r.request.url
        if u.endswith('/ebooks/9999'):   # a newer book: its page links every part (out of order, one twice)
            html = ''.join(f'<a href="/files/9999/mp3/9999-{n}.mp3">MP3 {n}</a>' for n in ('10', '01', '02', '01')) + '<a href="/files/9999/ogg/9999-01.ogg">ogg</a>'
        elif u.endswith('/ebooks/8888'):  # an older book: a folder of MP3s, linked from its files page
            html = '<a href="/files/8888/">More files</a>'
        elif u.endswith('/files/8888/'):
            html = '<a href="8888-readme.txt">readme</a><a href="8888-mp3/">8888-mp3/</a>'
        elif u.endswith('/files/8888/8888-mp3/'):
            html = '<a href="../">Parent</a><a href="8888-03.mp3">8888-03.mp3</a><a href="8888-01.mp3">8888-01.mp3</a><a href="8888-02.mp3">8888-02.mp3</a>'
        elif '/ebooks/5555' in u or '/files/5555/' in u:
            html = '<p>no audio here</p>'
        else:
            await r.fulfill(status=404, body=b''); return
        await r.fulfill(status=200, content_type='text/html', headers={'Access-Control-Allow-Origin': '*'}, body=html)
    await c.route('https://archive.org/advancedsearch.php**', adv)
    await c.route('https://archive.org/metadata/**', meta)
    await c.route('https://archive.org/download/**', audio)
    await c.route('https://archive.org/services/img/**', img)
    await c.route('https://gutendex.com/**', gutendex)
    await c.route('https://www.gutenberg.org/**', gbsite)
    await c.route('https://www.gutenberg.org/files/**/*.mp3', audio)
    await c.route('https://www.gutenberg.org/cache/**', img)
    await pg.evaluate("__t.ev('openLibTab(\"audiobooks\")')"); await pg.wait_for_timeout(1500)

    # ---- the find box reaches both libraries ----
    await pg.fill('#abFindInput', 'twain'); await pg.wait_for_timeout(1000)
    r = await pg.evaluate(STATE)
    late = await pg.evaluate("!!document.querySelector('#stationsGrid .ab-late')")
    check(len(r['rows']) == 30 and late and not r['more'], f'{T} archive.org\'s books show at once while Gutenberg is still answering, a spinner at the foot ({len(r["rows"])} rows, spinner {late}, more {r["more"]})')
    await pg.screenshot(path=f'{SHOTS}/absrc-find-early-{theme}.png')
    await pg.wait_for_timeout(1800)
    r = await pg.evaluate(STATE)
    late = await pg.evaluate("!!document.querySelector('#stationsGrid .ab-late')")
    check(not late, f'{T} the spinner goes once Gutenberg answers')
    qs = urllib.parse.unquote(asked['search'][-1])
    check('collection:(audio_bookspoetry)' in qs and 'collection:(librivoxaudio)' in qs, f'{T} the find box searches archive.org\'s Audio Books & Poetry collection, LibriVox included')
    check(gb_asked and 'mime_type=audio' in gb_asked[-1] and 'search=twain' in gb_asked[-1], f'{T} and Project Gutenberg\'s audiobooks {gb_asked[-1:]}')
    check(len(r['rows']) == 32 and r['rows'][30:] == ['The Prince and the Pauper', 'Life on the Mississippi'], f'{T} archive.org\'s books first, then Gutenberg\'s; its copy of a listed book is left out ({len(r["rows"])}) {r["rows"][29:]}')
    check(r['rowSubs'][30] == 'Mark Twain · Project Gutenberg' and r['rowSubs'][31] == 'Mark Twain · Project Gutenberg', f'{T} a Gutenberg row names the author (first name first) and the library {r["rowSubs"][30:]}')
    check(r['more'], f'{T} More Results while either library has more')
    await pg.screenshot(path=f'{SHOTS}/absrc-find-{theme}.png')
    await pg.evaluate("window.scrollTo(0, 99999)"); await pg.wait_for_timeout(400)
    await pg.screenshot(path=f'{SHOTS}/absrc-find-end-{theme}.png'); await pg.evaluate("window.scrollTo(0, 0)")
    await pg.evaluate("document.querySelector('.ia-more').click()"); await pg.wait_for_timeout(2800)
    r = await pg.evaluate(STATE)
    check(len(r['rows']) == 43 and r['rows'][-1] == 'Roughing It' and not r['more'], f'{T} More Results brings the rest of both ({len(r["rows"])}) {r["rows"][-2:]}')
    check('page=2' in gb_asked[-1], f'{T} Gutenberg\'s second page was asked for')

    # ---- a Gutenberg book plays ----
    await pg.evaluate("Array.from(document.querySelectorAll('.song-row')).find(function(x){ return x.querySelector('.song-row-title').textContent === 'The Prince and the Pauper'; }).click()"); await pg.wait_for_timeout(2000)
    q = await ev(pg, "({ cur: currentStation && currentStation.guid, q: playQueue.map(function(t){ return t.guid + '|' + t.name; }), label: queueLabel, url: currentStation && currentStation.episodeUrl, type: currentStation && currentStation.type, art: currentStation && currentStation.favicon })")
    check(q['type'] == 'podcast' and q['cur'] == 'gb:9999/9999-01.mp3', f'{T} a Gutenberg book plays from part one {q["cur"]}')
    check(q['q'] == ['gb:9999/9999-01.mp3|Part 1', 'gb:9999/9999-02.mp3|Part 2', 'gb:9999/9999-10.mp3|Part 3'] and q['label'] == 'The Prince and the Pauper', f'{T} its parts are Up Next in order, each once {q["q"]}')
    check(q['url'] == 'https://www.gutenberg.org/files/9999/mp3/9999-01.mp3', f'{T} straight from gutenberg.org {q["url"]}')
    check(q['art'] == 'https://www.gutenberg.org/cache/epub/9999/pg9999.cover.medium.jpg', f'{T} wearing Gutenberg\'s cover {q["art"]}')
    await pg.screenshot(path=f'{SHOTS}/absrc-gb-playing-{theme}.png')
    # its cover is the book's, like any other
    await pg.click('#npMenuBtn'); await pg.wait_for_timeout(400)
    await pg.click('#npArtEditBtn'); await pg.wait_for_timeout(500)
    ttl = await pg.evaluate("document.getElementById('artUrlTitle').textContent")
    check(ttl == 'Book Cover', f'{T} Edit cover art on a Gutenberg book edits the Book Cover {ttl!r}')
    await pg.set_input_files('#artUrlFileInput', '/tmp/claude-0/t/blue.png'); await pg.wait_for_timeout(1200)
    await pg.click('#artUrlSaveBtn'); await pg.wait_for_timeout(600)
    keys = await ev(pg, "Object.keys(loadCustomArtMap()).filter(function(k){ return k.indexOf('9999') >= 0; })")
    check(keys == ['audiobook:gutenberg-9999'], f'{T} saved as the book\'s cover {keys}')
    await ev(pg, "playStation(playQueue[1])"); await pg.wait_for_timeout(800)
    await ev(pg, "closeNowPlaying()"); await pg.wait_for_timeout(400)
    await pg.evaluate("__t.ev('openLibTab(\"audiobooks\")')"); await pg.wait_for_timeout(1500)
    r = await pg.evaluate(STATE)
    cl = await pg.evaluate("(function(){ var t = document.querySelector('.gp-row > .tile'); var ims = t.querySelectorAll('.tile-art img'); return { n: ims.length, src: ims[0] && ims[0].getAttribute('src').slice(0, 22) }; })()")
    check(r['heads'][0] == 'Continue Listening' and r['tiles'][0] == 'The Prince and the Pauper' and r['subs'][0] == 'Part 2', f'{T} Continue Listening holds the Gutenberg book at the part left off {r["tiles"][:1]} {r["subs"][:1]}')
    check(cl['n'] == 1 and cl['src'].startswith('data:image/'), f'{T} with its new cover, one picture in the box {cl}')
    await pg.screenshot(path=f'{SHOTS}/absrc-continue-{theme}.png')
    await ev(pg, "playQueue = []; currentStation = null;")
    await pg.evaluate("document.querySelector('.gp-row > .tile').click()"); await pg.wait_for_timeout(1800)
    q = await ev(pg, "({ cur: currentStation && currentStation.name, n: playQueue.length })")
    check(q == {'cur': 'Part 2', 'n': 3}, f'{T} tapping it picks up at Part 2 {q}')
    await ev(pg, "closeNowPlaying()"); await pg.wait_for_timeout(300)

    # ---- an older Gutenberg book keeps its MP3s in a folder ----
    await ev(pg, "playAudiobook({ id: 'gutenberg-8888', gbId: '8888', source: 'gutenberg', title: 'Life on the Mississippi', creator: 'Mark Twain', formats: {} })"); await pg.wait_for_timeout(2000)
    q = await ev(pg, "playQueue.map(function(t){ return t.guid; })")
    check(q == ['gb:8888/8888-01.mp3', 'gb:8888/8888-02.mp3', 'gb:8888/8888-03.mp3'], f'{T} an older book plays from its MP3 folder {q}')
    await ev(pg, "closeNowPlaying()"); await pg.wait_for_timeout(300)
    # a book with no audio says so
    await ev(pg, "playAudiobook({ id: 'gutenberg-5555', gbId: '5555', source: 'gutenberg', title: 'Roughing It', creator: 'Mark Twain', formats: {} })"); await pg.wait_for_timeout(1500)
    stt = await pg.evaluate("document.getElementById('statusLineText').textContent")
    check('no playable audio' in stt and 'Roughing It' in stt, f'{T} a book with no audio says so {stt!r}')

    # ---- a Gutenberg row's More menu ----
    await pg.evaluate("__t.ev('openLibTab(\"audiobooks\")')"); await pg.wait_for_timeout(1000)
    await pg.fill('#abFindInput', 'pauper'); await pg.wait_for_timeout(3000)
    r = await pg.evaluate(STATE)
    check(r['rows'] == ['The Prince and the Pauper (dramatic reading)', 'The Prince and the Pauper'], f'{T} a different recording of the same book is still listed {r["rows"]}')
    await pg.evaluate("document.querySelectorAll('.song-row .ia-more-btn')[1].click()"); await pg.wait_for_timeout(400)
    items = await pg.evaluate("Array.from(document.querySelectorAll('.ia-row-menu .np-menu-item')).map(function(b){ return b.textContent.trim(); })")
    check(items == ['Play Next', 'Add to Queue'], f'{T} a Gutenberg row\'s More menu: Play Next, Add to Queue (no archive.org download) {items}')
    await ev(pg, "upNext = []")
    await pg.evaluate("document.getElementById('iaMenuQueue').click()"); await pg.wait_for_timeout(1500)
    n = await ev(pg, "upNext.filter(function(t){ return /^gb:9999\\//.test(t.guid); }).length")
    check(n == 3, f'{T} Add to Queue adds its three parts ({n})')

    # ---- a non-LibriVox archive.org book is a book once played ----
    await pg.evaluate("document.querySelector('.song-row').click()"); await pg.wait_for_timeout(1800)
    book = await ev(pg, "({ ab: isAudiobookGuid(currentStation.guid), id: abIdFromGuid(currentStation.guid) })")
    check(book == {'ab': True, 'id': 'prince_pauper_reading'}, f'{T} a book from archive.org outside LibriVox counts as a book once played {book}')
    await ev(pg, "closeNowPlaying()"); await pg.wait_for_timeout(300)
    await pg.evaluate("__t.ev('openLibTab(\"audiobooks\")')"); await pg.wait_for_timeout(1500)
    r = await pg.evaluate(STATE)
    check(r['tiles'][:2] == ['The Prince and the Pauper (dramatic reading)', 'Life on the Mississippi'], f'{T} and is in Continue Listening {r["tiles"][:3]}')

    # ---- main Search: an Audiobooks tab ----
    await pg.evaluate("document.getElementById('stationsGrid').innerHTML = ''; __t.ev('searchByName(\"twain\")')"); await pg.wait_for_timeout(1200)
    await pg.evaluate("Array.from(document.querySelectorAll('#searchTabs .home-tab')).find(function(b){ return b.dataset.group === 'audiobooks'; }).click()"); await pg.wait_for_timeout(200)
    early = await pg.evaluate("[document.querySelectorAll('#stationsGrid .song-row').length, !!document.querySelector('#stationsGrid .ab-late')]")
    check(early == [30, True], f'{T} Search\'s tab too: archive.org\'s books at once, Gutenberg\'s on the way {early}')
    await pg.wait_for_timeout(2500)
    tabs = await pg.evaluate("Array.from(document.querySelectorAll('#searchTabs .home-tab')).map(function(b){ return b.textContent; })")
    ab = [t for t in tabs if t.startswith('Audiobooks')]
    check(ab == ['Audiobooks (32)'], f'{T} Search has an Audiobooks tab with its count {tabs}')
    check(not tabs or 'Podcasts' not in ''.join(tabs) or tabs.index(ab[0]) == [i for i, t in enumerate(tabs) if t.startswith('Podcasts')][0] + 1, f'{T} right after Podcasts {tabs}')
    await pg.evaluate("Array.from(document.querySelectorAll('#searchTabs .home-tab')).find(function(b){ return b.dataset.group === 'audiobooks'; }).click()"); await pg.wait_for_timeout(800)
    r = await pg.evaluate(STATE)
    check(len(r['rows']) == 32 and r['rows'][30] == 'The Prince and the Pauper' and r['more'], f'{T} the tab lists the same books, with More Results ({len(r["rows"])})')
    await pg.screenshot(path=f'{SHOTS}/absrc-search-tab-{theme}.png')
    await pg.evaluate("document.querySelector('.ia-more').click()"); await pg.wait_for_timeout(2800)
    r = await pg.evaluate(STATE)
    tabs = await pg.evaluate("Array.from(document.querySelectorAll('#searchTabs .home-tab')).map(function(b){ return b.textContent; })")
    check(len(r['rows']) == 43 and 'Audiobooks (43)' in tabs, f'{T} More Results there too ({len(r["rows"])}) {[t for t in tabs if "Audio" in t]}')
    await ev(pg, "playQueue = []; currentStation = null;")
    await pg.evaluate("Array.from(document.querySelectorAll('.song-row')).find(function(x){ return x.querySelector('.song-row-title').textContent === 'Life on the Mississippi'; }).click()"); await pg.wait_for_timeout(1800)
    q = await ev(pg, "({ cur: currentStation && currentStation.guid, n: playQueue.length })")
    check(q['cur'] == 'gb:8888/8888-01.mp3' and q['n'] == 3, f'{T} a book plays from Search {q}')
    await ev(pg, "closeNowPlaying()"); await pg.wait_for_timeout(300)
    top = await ev(pg, "topSearchResults().map(function(r){ return r.kind; })")
    check('audiobooks' not in top, f'{T} Top Results is not made of audiobooks {top}')

    # ---- a very slow Gutendex: archive.org's books still at once; Gutenberg given up after 12 s ----
    gb_delay['s'] = 20
    await pg.evaluate("__t.ev('openLibTab(\"audiobooks\")')"); await pg.wait_for_timeout(800)
    await pg.fill('#abFindInput', 'twain'); await pg.wait_for_timeout(1000)
    r = await pg.evaluate(STATE)
    check(len(r['rows']) == 30, f'{T} a very slow Gutenberg doesn\'t hold up archive.org\'s books ({len(r["rows"])})')
    await pg.wait_for_timeout(12500)
    r = await pg.evaluate(STATE)
    late = await pg.evaluate("!!document.querySelector('#stationsGrid .ab-late')")
    check(len(r['rows']) == 30 and not late and r['more'], f'{T} after 12 s it stops waiting for Gutenberg; More Results for archive.org\'s next page (spinner {late}, more {r["more"]})')
    gb_delay['s'] = 1.5
    # ---- one library down leaves the other's books ----
    gb_down['on'] = True
    await pg.evaluate("__t.ev('openLibTab(\"audiobooks\")')"); await pg.wait_for_timeout(1000)
    await pg.fill('#abFindInput', 'twain mark'); await pg.wait_for_timeout(2200)
    r = await pg.evaluate(STATE)
    check(len(r['rows']) == 30, f'{T} Gutenberg down: archive.org\'s books still listed ({len(r["rows"])})')
    ia_down['on'] = True
    await pg.fill('#abFindInput', 'mark twain'); await pg.wait_for_timeout(2200)
    r = await pg.evaluate(STATE)
    stt = await pg.evaluate("document.getElementById('statusLineText').textContent")
    check('No audiobooks match' in r['empty'] and 'Could not reach' in stt, f'{T} both down: says so {r["empty"]!r} {stt!r}')
    gb_down['on'] = False; ia_down['on'] = False

    # ---- Settings > Sources > Audiobooks off: no tab in Search ----
    await pg.evaluate("""(()=>{ var s = document.getElementById('audiobooksSourceSelect'); s.value = 'off'; s.dispatchEvent(new Event('change')); })()"""); await pg.wait_for_timeout(600)
    n0 = len(gb_asked)
    await pg.evaluate("document.getElementById('stationsGrid').innerHTML = ''; __t.ev('searchByName(\"twain\")')"); await pg.wait_for_timeout(2500)
    tabs = await pg.evaluate("Array.from(document.querySelectorAll('#searchTabs .home-tab')).map(function(b){ return b.dataset.group; })")
    check('audiobooks' not in tabs and len(gb_asked) == n0, f'{T} Audiobooks off: no tab, nothing asked {tabs}')
    await pg.evaluate("""(()=>{ var s = document.getElementById('audiobooksSourceSelect'); s.value = 'on'; s.dispatchEvent(new Event('change')); })()""")
    check(not errs, f'{T} no page errors {errs[:2]}')
    await c.close()

async def main():
    from playwright.async_api import async_playwright
    if not os.path.exists('/tmp/claude-0/t/blue.png'):
        from PIL import Image; Image.new('RGB', (300, 300), (20, 60, 230)).save('/tmp/claude-0/t/blue.png')
    async with async_playwright() as p:
        B = await p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
        for theme in ('dark', 'light'):
            await run(B, theme)
        await B.close()
    print('\nFAILS:', len(fails))
    for f in fails: print(' -', f)
    sys.exit(1 if fails else 0)

asyncio.run(main())
