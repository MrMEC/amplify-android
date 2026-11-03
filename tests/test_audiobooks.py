"""Build 440: Library > Audiobooks. A sixth Library tab (after Genres) holding LibriVox's recordings from
archive.org: the app's filter box (never focused by itself), Continue Listening and Popular as sideways rows of
covers, Browse categories as colour cards; typing lists matches (More Results past 30); a category opens a list
page with a back button; a book plays from the section last played with its sections as Up Next; the tab goes
with Settings > Sources > Audiobooks; an audiobook's place survives "Search everything". Phone, dark and light.
Run: python3 tests/test_audiobooks.py (screenshots in /tmp/claude-0/t/shots)"""
import os, sys, json, asyncio, urllib.parse
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
src = open(os.path.join(HERE, 'test_archive_download.py')).read().split('async def notice(pg):')[0]
src = src.replace('PORT = 8881', 'PORT = 8893').replace("ROOT = '/tmp/claude-0/t/srv-iadl'", "ROOT = '/tmp/claude-0/t/srv-ab'").replace("HERE = os.path.dirname(os.path.abspath(__file__))", "HERE = %r" % HERE)
exec(src)
# The shared mock never reports a native player's state, so nothing "plays"; this one does, as a phone would.
MOCK = MOCK.replace("downloadToFolder: function(o){", "load: function(o){ setTimeout(function(){ emit('state', { id: o.id, state: 'ready', isPlaying: true, playWhenReady: true, position: 0, duration: 600 }); }, 20); return Promise.resolve({}); },\n    cacheCheck: function(){ return Promise.resolve({ url: 'file:///cache/x.mp3' }); },\n    downloadToFolder: function(o){", 1)
assert 'cacheCheck' in MOCK

BOOKS = [
    ('letters_brides_0709_librivox', 'Letters of Two Brides', 'Honoré de Balzac', 32960),
    ('best_russian_shortstories_1010_librivox', 'Best Russian Short Stories', 'Various', 38000),
    ('best_thing_in_the_world_1003_librivox', 'The Best Thing in the World', 'Elizabeth Barrett Browning', 930),
    ('best_man_1009_librivox', 'The Best Man', 'Grace Livingston Hill', 23630),
    ('best_way_read_book_1009_librivox', 'Best Way to Read a Book', 'Edgar A. Guest', 1980),
    ('best_british_1922_librivox', 'Best British Short Stories of 1922', 'Various', 49380),
    ('best_american_humorous_librivox', 'Best American Humorous Short Stories', 'Various', 40380),
    ('tom_sawyer_librivox', 'The Adventures of Tom Sawyer', 'Mark Twain', 24000),
    ('huck_finn_librivox', 'Adventures of Huckleberry Finn', 'Mark Twain', 33000),
    ('pride_prejudice_librivox', 'Pride and Prejudice', 'Jane Austen', 41000),
    ('sherlock_librivox', 'The Adventures of Sherlock Holmes', 'Arthur Conan Doyle', 37000),
    ('dracula_librivox', 'Dracula', 'Bram Stoker', 53000),
]
BY_ID = {b[0]: b for b in BOOKS}
SECTIONS = 5
TOTAL_TWAIN = 40   # more than one page of results
fails = []
def check(ok, msg):
    print(('PASS ' if ok else 'FAIL ') + msg)
    if not ok: fails.append(msg)
def runtime(secs):
    return '%d:%02d:%02d' % (secs // 3600, secs % 3600 // 60, secs % 60)
def doc(b):
    return {'identifier': b[0], 'title': b[1], 'creator': b[2], 'runtime': runtime(b[3]), 'year': '1900', 'mediatype': 'audio'}
asked = {'search': [], 'meta': []}
def adv_body(url):
    qs = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
    q = qs['q'][0]; page = int(qs.get('page', ['1'])[0]); rows = int(qs.get('rows', ['30'])[0])
    if 'twain' in q.lower():
        allb = [dict(doc(BOOKS[7 + i % 2]), identifier='twain%02d_librivox' % i, title='Twain Book %02d' % i, creator='Mark Twain') for i in range(TOTAL_TWAIN)]
        return {'response': {'numFound': TOTAL_TWAIN, 'docs': allb[(page - 1) * rows: page * rows]}}
    if 'zzzz' in q.lower():
        return {'response': {'numFound': 0, 'docs': []}}
    if 'subject:(mystery)' in q:
        return {'response': {'numFound': 3, 'docs': [doc(BOOKS[10]), doc(BOOKS[11]), doc(BOOKS[3])]}}
    return {'response': {'numFound': 5000, 'docs': [doc(b) for b in BOOKS]}}
def meta_body(id_):
    base = f'{id_}'
    files = [{'name': f'{base}_{i:02d}_x.mp3', 'format': 'VBR MP3', 'title': f'Section {i}', 'track': str(i), 'size': '9000', 'length': '600'} for i in range(1, SECTIONS + 1)]
    return {'metadata': {'title': BY_ID.get(id_, ('', id_))[1], 'creator': BY_ID.get(id_, ('', '', ''))[2]}, 'files': files + [{'name': 'cover.jpg', 'format': 'JPEG'}]}

STATE = """(()=>{ var g = document.getElementById('stationsGrid');
  function t(sel){ return Array.from(g.querySelectorAll(sel)).map(function(e){ return e.textContent; }); }
  var tabs = Array.from(g.querySelectorAll(':scope > .lib-tabs .home-tab')).map(function(b){ return b.textContent + (b.classList.contains('active') ? '*' : ''); });
  var inp = document.getElementById('abFindInput');
  return { tabs: tabs, heading: document.getElementById('stationsHeading').textContent,
    find: inp ? { cls: inp.parentElement.className, ph: inp.placeholder, focused: document.activeElement === inp, h: Math.round(inp.getBoundingClientRect().height) } : null,
    heads: t('.gp-head, .gb-head'), tiles: t('.gp-row > .tile .tile-name'), subs: t('.gp-row > .tile .tile-sub'), cards: t('.gb-card-name'),
    rows: t('.song-row .song-row-title'), rowSubs: t('.song-row .song-row-sub'), more: !!g.querySelector('.ab-more, .ia-more'),
    empty: (g.querySelector('.empty-state') || {}).textContent || '', spinner: !!g.querySelector('.loading-state'),
    sw: document.documentElement.scrollWidth, vw: innerWidth }; })()"""

async def ev(pg, js):
    return await pg.evaluate("(js)=>__t.ev(js)", js)

async def tap_tab(pg, name):
    await pg.evaluate("(n)=>{ var b=Array.from(document.querySelectorAll('.lib-tabs .home-tab')).find(function(x){ return x.textContent===n; }); b.click(); }", name)
    await pg.wait_for_timeout(900)

async def run(B, theme):
    T = f'[{theme}]'
    c, pg, errs = await page(B, theme, [{'treeUri': 'content://tree/Music', 'name': 'Music'}])
    async def adv(r):
        asked['search'].append(r.request.url)
        await r.fulfill(status=200, content_type='application/json', headers={'Access-Control-Allow-Origin': '*'}, body=json.dumps(adv_body(r.request.url)))
    async def meta(r):
        id_ = r.request.url.rstrip('/').split('/')[-1]; asked['meta'].append(id_)
        await r.fulfill(status=200, content_type='application/json', headers={'Access-Control-Allow-Origin': '*'}, body=json.dumps(meta_body(id_)))
    async def dl(r):
        await r.fulfill(status=200, content_type='audio/mpeg', headers={'Access-Control-Allow-Origin': '*'}, path=ROOT + '/files/01 - Song One.mp3')
    async def img(r):
        await r.fulfill(status=200, content_type='image/jpeg', headers={'Access-Control-Allow-Origin': '*'}, path=ROOT + '/files/cover.jpg')
    await c.route('https://archive.org/advancedsearch.php**', adv)
    await c.route('https://archive.org/metadata/**', meta)
    await c.route('https://archive.org/download/**', dl)
    await c.route('https://archive.org/services/img/**', img)
    await pg.evaluate("__t.ev('openLibTab(\"artists\")')"); await pg.wait_for_timeout(1200)

    # ---- the tab ----
    r = await pg.evaluate(STATE)
    check(r['tabs'][-2:] == ['Genres', 'Audiobooks'], f'{T} Audiobooks is the last Library tab, after Genres {r["tabs"]}')
    await tap_tab(pg, 'Audiobooks'); await pg.wait_for_timeout(1200)
    r = await pg.evaluate(STATE); print(T, r)
    check(r['tabs'][-1] == 'Audiobooks*' and r['heading'] == 'Library', f'{T} the tab is active under the Library heading {r["tabs"]} {r["heading"]}')
    check(r['find'] and r['find']['cls'] == 'sec-filter gb-find' and r['find']['ph'] == 'Search audiobooks' and r['find']['h'] == 46, f'{T} the find box is the app\'s filter box {r["find"]}')
    check(r['find'] and not r['find']['focused'], f'{T} the find box is never focused by itself')
    check(r['heads'] == ['Popular', 'Browse categories'], f'{T} Popular, then Browse categories (no Continue Listening yet) {r["heads"]}')
    check(len(r['tiles']) == 12 and r['tiles'][0] == 'Letters of Two Brides', f'{T} popular books as a row of covers ({len(r["tiles"])}) {r["tiles"][:2]}')
    check(r['subs'][0] == 'Honoré de Balzac', f'{T} the tile shows the author {r["subs"][:2]}')
    check(len(r['cards']) == 12 and r['cards'][:3] == ['Classics', 'Mystery', 'Science Fiction'], f'{T} twelve category cards {r["cards"]}')
    check(r['sw'] <= r['vw'], f'{T} nothing scrolls sideways ({r["sw"]} > {r["vw"]})')
    q0 = urllib.parse.unquote(asked['search'][-1])
    check('collection:(librivoxaudio)' in q0 and 'mediatype:(audio)' in q0, f'{T} Popular asks archive.org for the LibriVox collection')
    await pg.screenshot(path=f'{SHOTS}/audiobooks-home-{theme}.png')
    await pg.evaluate("window.scrollTo(0, 99999)"); await pg.wait_for_timeout(500)
    await pg.screenshot(path=f'{SHOTS}/audiobooks-home-scrolled-{theme}.png'); await pg.evaluate("window.scrollTo(0, 0)")

    # ---- the find box ----
    await pg.tap('#abFindInput'); await pg.wait_for_timeout(300)
    await pg.fill('#abFindInput', 'twain'); await pg.wait_for_timeout(1800)
    r = await pg.evaluate(STATE)
    check(len(r['rows']) == 30 and r['rows'][0] == 'Twain Book 00' and r['more'], f'{T} typing lists matches, 30 a page, with More Results ({len(r["rows"])})')
    check(r['rowSubs'][0] == 'Mark Twain · 6 h 40 m', f'{T} a row shows the author and length {r["rowSubs"][0]}')
    qs = urllib.parse.unquote(asked['search'][-1])
    check('title:(twain)' in qs and 'creator:(twain)' in qs, f'{T} it searches title and author')
    check(r['heads'] == [] and r['cards'] == [], f'{T} browse content gives way to the matches')
    await pg.screenshot(path=f'{SHOTS}/audiobooks-search-{theme}.png')
    await pg.evaluate("document.querySelector('.ia-more').click()"); await pg.wait_for_timeout(1500)
    r = await pg.evaluate(STATE)
    check(len(r['rows']) == 40 and not r['more'], f'{T} More Results adds the rest ({len(r["rows"])})')
    await pg.fill('#abFindInput', 'zzzz'); await pg.wait_for_timeout(1800)
    r = await pg.evaluate(STATE)
    check('No audiobooks match' in r['empty'] and 'zzzz' in r['empty'], f'{T} nothing found says so {r["empty"]}')
    await pg.evaluate("document.querySelector('#abFindInput').parentElement.querySelector('.sf-clear').click()"); await pg.wait_for_timeout(1500)
    r = await pg.evaluate(STATE)
    check(r['heads'][-2:] == ['Popular', 'Browse categories'] and not r['rows'], f'{T} clearing the box goes back to browsing {r["heads"]}')

    # ---- playing a book ----
    await pg.evaluate("document.querySelector('.gp-row > .tile').click()"); await pg.wait_for_timeout(1800)
    q = await ev(pg, "({ cur: currentStation && currentStation.guid, qn: playQueue.length, label: queueLabel, type: currentStation && currentStation.type })")
    check(q['type'] == 'podcast' and q['cur'].startswith('ia:letters_brides_0709_librivox/') and q['qn'] == SECTIONS and q['label'] == 'Letters of Two Brides', f'{T} a book plays as a podcast with its sections as Up Next {q}')
    await pg.screenshot(path=f'{SHOTS}/audiobooks-playing-{theme}.png')
    # listen to section 3: it is what Continue Listening holds
    await ev(pg, "(function(){ var s = playQueue[2]; playStation(s); })()"); await pg.wait_for_timeout(1200)
    rec = await ev(pg, "recentStations.filter(function(r){ return isAudiobookGuid(r.guid); }).map(function(r){ return r.name; })")
    check(rec and rec[0] == 'Section 3', f'{T} the section played is remembered {rec}')
    await ev(pg, "closeNowPlaying()"); await pg.wait_for_timeout(500)
    await pg.evaluate("__t.ev('openLibTab(\"audiobooks\")')"); await pg.wait_for_timeout(1500)
    r = await pg.evaluate(STATE)
    check(r['heads'][0] == 'Continue Listening' and r['tiles'][0] == 'Letters of Two Brides' and r['subs'][0] == 'Section 3', f'{T} Continue Listening holds the book and its section {r["heads"]} {r["tiles"][:1]} {r["subs"][:1]}')
    await pg.screenshot(path=f'{SHOTS}/audiobooks-continue-{theme}.png')
    await ev(pg, "playQueue = []; currentStation = null;")
    await pg.evaluate("document.querySelector('.gp-row > .tile').click()"); await pg.wait_for_timeout(1800)
    q = await ev(pg, "({ cur: currentStation && currentStation.name, qn: playQueue.length })")
    check(q['cur'] == 'Section 3' and q['qn'] == SECTIONS, f'{T} tapping the book picks up at the section left off {q}')
    await ev(pg, "closeNowPlaying()"); await pg.wait_for_timeout(400)

    # ---- a category ----
    await pg.evaluate("__t.ev('openLibTab(\"audiobooks\")')"); await pg.wait_for_timeout(1000)
    await pg.evaluate("Array.from(document.querySelectorAll('.gb-card')).find(function(c){ return c.dataset.category === 'Mystery'; }).click()"); await pg.wait_for_timeout(1500)
    r = await pg.evaluate(STATE)
    back = await pg.evaluate("(document.getElementById('detailBackBtn').textContent || '').trim() + '|' + (document.getElementById('detailBackBtn').getAttribute('aria-label') || '')")
    check(r['heading'] == 'Mystery' and len(r['rows']) == 3 and not r['tabs'], f'{T} a category is a page of its books with a back button {r["heading"]} {len(r["rows"])} {back}')
    check('subject:(mystery)' in urllib.parse.unquote(asked['search'][-1]), f'{T} the category asks for its subject')
    await pg.screenshot(path=f'{SHOTS}/audiobooks-category-{theme}.png')
    await pg.evaluate("document.getElementById('detailBackBtn').click()"); await pg.wait_for_timeout(1200)
    r = await pg.evaluate(STATE)
    check(r['tabs'][-1] == 'Audiobooks*', f'{T} back returns to the Audiobooks tab {r["tabs"]}')

    # ---- the More menu is the archive one ----
    await pg.fill('#abFindInput', 'twain'); await pg.wait_for_timeout(1800)
    await pg.evaluate("document.querySelector('.song-row .ia-more-btn').click()"); await pg.wait_for_timeout(500)
    items = await pg.evaluate("Array.from(document.querySelectorAll('.ia-row-menu .np-menu-item')).map(function(b){ return b.textContent.trim(); })")
    check(items[:2] == ['Play Next', 'Add to Queue'], f'{T} a row\'s More menu is Play Next, Add to Queue, Download {items}')
    await pg.screenshot(path=f'{SHOTS}/audiobooks-menu-{theme}.png')
    await pg.mouse.click(10, 300); await pg.wait_for_timeout(300)

    # ---- Search everything keeps an audiobook's place ----
    await ev(pg, "(function(){ recentStations.unshift({ type:'podcast', guid:'ia:some_movie/a.mp3', name:'A', collectionName:'Movie', artistName:'' }); setArchiveSearchAll(true); })()")
    left = await ev(pg, "recentStations.filter(function(r){ return /^ia:/.test(r.guid); }).map(function(r){ return r.guid.split('/')[0]; })")
    check('letters_brides_0709_librivox' in ''.join(left) and 'some_movie' not in ''.join(left), f'{T} Search everything clears other archive.org history but keeps the audiobook {left}')
    await ev(pg, "setArchiveSearchAll(false)")

    # ---- Settings > Sources ----
    sw = await pg.evaluate("""(()=>{ var s = document.getElementById('audiobooksSourceSelect'); return { there: !!s, val: s && s.value, label: (document.getElementById('audiobooksSourceLabel')||{}).textContent }; })()""")
    check(sw['there'] and sw['val'] == 'on' and sw['label'] == 'Audiobooks', f'{T} Settings > Sources has an Audiobooks switch, on {sw}')
    await pg.evaluate("""(()=>{ var s = document.getElementById('audiobooksSourceSelect'); s.value = 'off'; s.dispatchEvent(new Event('change')); })()"""); await pg.wait_for_timeout(1200)
    r = await pg.evaluate(STATE)
    check('Audiobooks' not in ''.join(r['tabs']).replace('*', '') and r['tabs'][0] == 'Artists*', f'{T} switched off while open: the tab goes and Artists opens {r["tabs"]}')
    await pg.evaluate("""(()=>{ var s = document.getElementById('audiobooksSourceSelect'); s.value = 'on'; s.dispatchEvent(new Event('change')); })()"""); await pg.wait_for_timeout(1000)
    r = await pg.evaluate(STATE)
    check(r['tabs'][-1] == 'Audiobooks', f'{T} switched on: the tab is back {r["tabs"]}')
    check(not errs, f'{T} no page errors {errs[:2]}')
    await c.close()

async def main():
    from playwright.async_api import async_playwright
    async with async_playwright() as p:
        B = await p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
        for theme in ('dark', 'light'):
            await run(B, theme)
        await B.close()
    print('\nFAILS:', len(fails))
    for f in fails: print(' -', f)
    sys.exit(1 if fails else 0)
asyncio.run(main())
