"""Build 389 (Mark): an artist's page shows "On Archive.org", a sideways row of that artist's music
videos and concert films from archive.org (most downloaded first), under the YouTube row. Only the
artist's own items (a title that starts "Artist - ...", or an exact creator -- never a creator alone
for a short one-word name); covers/karaoke/etc. and unplayable items are left out; the answer is
kept (a cache) so the page doesn't ask again; off with archive.org in Sources. Tapping plays it.
Run: python3 tests/test_artist_archive.py (screenshots in /tmp/claude-0/t/shots)"""
import os, sys, json, asyncio
from urllib.parse import urlparse, parse_qs
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
# The library, folder mock and server of the YouTube row's test (everything above its BIO).
_src = open(os.path.join(HERE, 'test_artist_videos.py')).read().split('BIO = (')[0]
_src = (_src.replace('PORT = 8802', 'PORT = 8803').replace("srv_artvid", "srv_artarch")
        .replace('window.__v = {', 'window.__t = { ev: function(js){ return eval(js); } }; window.__v = {')
        .replace("os.path.dirname(__file__)", "%r" % HERE))
exec(_src)

fails = []
def check(cond, msg):
    print(('PASS ' if cond else 'FAIL ') + msg)
    if not cond: fails.append(msg)
async def route(r):
    u = urlparse(r.request.url); hdr = {'access-control-allow-origin': '*'}
    if '127.0.0.1' in u.netloc: return await r.continue_()
    if u.netloc == 'www.wikidata.org': return await r.fulfill(status=200, content_type='application/json', headers=hdr, body=json.dumps({'search': [], 'entities': {}}))
    if u.netloc.endswith('wikipedia.org'): return await r.fulfill(status=404, body='', headers=hdr)
    if u.netloc == 'i.ytimg.com': return await r.fulfill(status=200, content_type='image/jpeg', body=THUMB_BYTES)
    return await r.abort()
PLAYABLE = {'files': [{'name': 'a.mp4', 'format': 'h.264', 'size': '9'}]}
PRIVATE = {'files': [{'name': '__ia_thumb.jpg', 'format': 'Item Tile'}, {'name': 'a.mp4', 'format': 'MPEG4', 'private': 'true'}]}
LOCKED = {'a7'}
# What archive.org returns for "Alpha": [id, title, creator, year, downloads]
ALPHA = [
    ['a1', 'Alpha - Song One (Official Video)', 'Alpha Records', '2008', 90000],
    ['a2', 'Alpha Live in Paris 1999', '', '1999', 50000],
    ['a3', 'Alpha - Song Two (cover by some kid)', '', '2011', 40000],            # a cover: out
    ['a4', 'Alphabet Soup - Hey', 'Alpha', '2001', 30000],                         # creator is just "Alpha" (one word) with no music cue in the title: out
    ['a5', 'Alpha Centauri documentary', 'Some Studio', '2015', 20000],            # not by the artist: out
    ['a6', 'Greatest Hits - Alpha', '', '1995', 10000],                            # "... - Alpha": kept
    ['a7', 'Alpha - Locked Video', '', '2003', 9000],                              # archive.org keeps its files private: out
    ['a8', 'Karaoke: Alpha - Song Three', '', '2009', 8000],                       # karaoke: out
]
BRAVO = [['b1', 'Bravo - Hello', 'Bravo', '2010', 500]]
DELTA = [['d1', 'Delta Airlines safety video', 'Delta', '2012', 700], ['d2', 'Delta - Live Wire', '', '2013', 600]]
asked = {'search': [], 'meta': []}
def docs(rows):
    return {'response': {'numFound': len(rows), 'docs': [{'identifier': i, 'title': t, 'creator': c, 'year': y, 'downloads': d, 'mediatype': 'movies'} for i, t, c, y, d in rows]}}
async def route2(r):
    url = r.request.url; u = urlparse(url)
    hdr = {'Access-Control-Allow-Origin': '*'}
    if u.netloc == 'archive.org' and u.path == '/advancedsearch.php':
        q = parse_qs(u.query)['q'][0]; asked['search'].append(q)
        rows = ALPHA if 'Alpha' in q else BRAVO if 'Bravo' in q else DELTA if 'Delta' in q else []
        return await r.fulfill(status=200, content_type='application/json', headers=hdr, body=json.dumps(docs(rows)))
    if u.netloc == 'archive.org' and u.path.startswith('/metadata/'):
        i = u.path.rstrip('/').split('/')[-1]; asked['meta'].append(i)
        return await r.fulfill(status=200, content_type='application/json', headers=hdr, body=json.dumps(PRIVATE if i in LOCKED else PLAYABLE))
    if u.netloc == 'archive.org' and u.path.startswith('/services/img/'):
        return await r.fulfill(status=200, content_type='image/jpeg', body=THUMB_BYTES)
    return await route(r)

ROW2 = """(()=>{ var g = document.getElementById('stationsGrid'); var kids = Array.from(g.children);
  var lab = g.querySelector('.artist-archive-label'), row = g.querySelector('.artist-archive-row'), al = g.querySelector('.artist-albums');
  return { label: lab ? lab.firstChild.textContent : null, labelIdx: kids.indexOf(lab), rowIdx: kids.indexOf(row), albumsIdx: kids.indexOf(al),
    ids: row ? Array.from(row.querySelectorAll('.yt-tile')).map(function(t){ return t.dataset.iaid; }) : null,
    titles: row ? Array.from(row.querySelectorAll('.yt-title')).map(function(t){ return t.textContent; }) : null,
    subs: row ? Array.from(row.querySelectorAll('.yt-date')).map(function(t){ return t.textContent; }) : null,
    img: row && row.querySelector('img') ? row.querySelector('img').getAttribute('src') : null,
    sw: row ? row.scrollWidth : 0, cw: row ? row.clientWidth : 0,
    labelPad: lab ? getComputedStyle(lab).paddingTop : null }; })()"""

async def run(b, theme, w=390, h=844, tag=''):
    T = f'[{theme}{tag}]'
    ctx = await b.new_context(viewport={'width': w, 'height': h}, device_scale_factor=2, is_mobile=(w < 900), has_touch=(w < 900), color_scheme=theme)
    await ctx.add_init_script(MOCK); await ctx.add_init_script(AUTO_NOTICE)
    pg = await ctx.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
    await pg.route('**/*', route2)
    await pg.goto(f'http://127.0.0.1:{PORT}/index.html'); await pg.wait_for_timeout(2500)
    await pg.evaluate("""(function(){ var ov=document.getElementById('addMusicOverlay'); if(ov) ov.classList.add('open');
      var btn=document.getElementById('addMusicFolderBtn'); btn.disabled=false; btn.click(); })()""")
    for _ in range(60):
        await pg.wait_for_timeout(500)
        if await pg.evaluate('__v.tracks()') >= 5: break
    await pg.evaluate("document.getElementById('addMusicOverlay').classList.remove('open')")
    await pg.wait_for_timeout(300); await pg.evaluate('__v.hide()')

    # ---- who counts as the artist's own ----
    m = await pg.evaluate("""__t.ev(`(()=>{ var f = function(n, t, c){ return aaMatches(n, { title: t, creator: c || '' }); };
      return [f('Prince', 'Prince - Purple Rain (Live)'), f('Prince', 'Prince of Persia: Warrior Within'), f('Prince', 'Prince Albert Piercing'),
        f('KEM', 'Welcome To YTPMV', 'KEM'), f('KEM', 'KEM - Love Calls'), f('The Jacksons', 'Jacksons - Can You Feel It'),
        f('Earth Wind & Fire', 'Earth, Wind & Fire - September'), f('Bjork', 'Bj\\\\u00f6rk - Army of Me'), f('Coldplay', 'Viva La Vida', 'Coldplay'), f('Seal', 'Crazy (Official Video)', 'Seal'),
        f('Alpha', 'Alpha - Song (karaoke version)'), f('Alpha', 'Alpha - Song (tribute)'), f('Madonna', 'Madonna - Vogue (Official Video)')]; })()`)""")
    check(m == [True, False, False, False, True, True, True, True, False, True, False, False, True], f'{T} who counts as the artist: Prince - ... yes, Prince of Persia no; KEM only by title; accents, & and "The" forgiven; covers/karaoke out {m}')

    # ---- Alpha: the row ----
    await pg.evaluate("__v.open('Alpha')"); await pg.wait_for_timeout(2500)
    r = await pg.evaluate(ROW2)
    check(r['label'] == 'On Archive.org', f'{T} heading "On Archive.org" {r["label"]}')
    check(r['ids'] == ['a1', 'a2', 'a6'], f'{T} their own, playable items, most downloaded first (cover, other act, one-word creator alone, karaoke and the locked one out) {r["ids"]}')
    check(r['titles'][0] == 'Song One' and r['titles'][1].startswith('Alpha Live'), f'{T} titles tidied like the YouTube row {r["titles"]}')
    check(r['subs'] == ['Video · 2008', 'Live · 1999', 'Video · 1995'], f'{T} each says Live or Video and the year {r["subs"]}')
    check(r['img'] == 'https://archive.org/services/img/a1', f'{T} thumbnail is archive.org’s own {r["img"]}')
    check(r['labelIdx'] == 0 and r['rowIdx'] == 1 and (r['albumsIdx'] == -1 or r['albumsIdx'] > 1), f'{T} at the top (no YouTube row), above Albums {r["labelIdx"]} {r["rowIdx"]} {r["albumsIdx"]}')
    check(r['labelPad'] == '22px', f'{T} room under the bio like the YouTube row {r["labelPad"]}')
    check(r['sw'] > r['cw'], f'{T} sideways row, cut off at the edge to show it scrolls {r["sw"]} {r["cw"]}')
    await pg.screenshot(path=f'{shots}/artarch-{theme}{tag}-alpha.png')
    await pg.evaluate("document.querySelector('.artist-archive-label').scrollIntoView({ block: 'center' })"); await pg.wait_for_timeout(500)
    await pg.screenshot(path=f'{shots}/artarch-{theme}{tag}-row.png')
    n1 = len(asked['search'])

    # ---- the order: Music Videos (phone), On YouTube, On Archive.org -- whichever arrives first ----
    ORDER = """__t.ev(`(()=>{ var e = findArtistEntry(artistMatchKey('Alpha')), g = document.getElementById('stationsGrid');
      clearArtistVideos(); clearArtistYouTube(); clearArtistArchive();
      var order = arguments[0] || [];
      var fakeLocal = function(){ var l = document.createElement('div'); l.className = 'grid-section-label artist-videos-label'; l.textContent = 'Music Videos';
        var w = document.createElement('div'); w.className = 'artist-videos'; w.innerHTML = '<div class="yt-tile"></div>'; placeArtistSection(0, l, w); };
      var yt = function(){ paintArtistYouTube(e, { videos: [{ id: 'yt000000001', title: 'Alpha - X (Official Video)', published: '2024-01-01' }] }, false); };
      var ia = function(){ paintArtistArchive(e, aaMap()[e.key]); };
      return { fakeLocal: fakeLocal, yt: yt, ia: ia }; })()`)"""
    for seq in (['ia', 'yt', 'local'], ['local', 'ia', 'yt'], ['yt', 'local', 'ia']):
        o = await pg.evaluate("""(seq)=>{ var h = %s; seq.forEach(function(k){ (k === 'local' ? h.fakeLocal : h[k])(); });
          return Array.from(document.getElementById('stationsGrid').children).slice(0, 6).map(function(e){ return e.className.split(' ').filter(function(c){ return /artist-/.test(c); })[0]; }); }""" % ORDER, seq)
        check(o == ['artist-videos-label', 'artist-videos', 'artist-yt-label', 'artist-yt-row', 'artist-archive-label', 'artist-archive-row'], f'{T} order Music Videos, On YouTube, On Archive.org when they arrive as {seq} {o}')
    await pg.evaluate("document.querySelector('.artist-yt-label').scrollIntoView({ block: 'start' })"); await pg.wait_for_timeout(500)
    await pg.screenshot(path=f'{shots}/artarch-{theme}{tag}-three.png')
    await pg.evaluate("__v.open('Alpha')"); await pg.wait_for_timeout(800)

    # ---- kept: opening again doesn't ask archive.org again ----
    await pg.evaluate("__v.open('Bravo')"); await pg.wait_for_timeout(1800)
    rb = await pg.evaluate(ROW2)
    check(rb['ids'] == ['b1'], f'{T} Bravo has its own {rb["ids"]}')
    await pg.evaluate("__v.open('Alpha')"); await pg.wait_for_timeout(1200)
    r2 = await pg.evaluate(ROW2)
    check(r2['ids'] == ['a1', 'a2', 'a6'] and len(asked['search']) == n1 + 1, f'{T} Alpha again: shown at once, archive.org not asked again (searches {len(asked["search"]) - n1} since)')
    kept = await pg.evaluate("Object.keys(JSON.parse(localStorage.getItem('amplifyFallback:amplifyArtistArchive') || '{}')).length")
    check(kept >= 2, f'{T} answers kept ({kept})')
    check(await pg.evaluate("window.__amplifyIsCache('amplifyFallback:amplifyArtistArchive')"), f'{T} a cache entry, so backups skip it')

    # ---- an artist with nothing of their own: no row, no empty heading ----
    await pg.evaluate("__v.open('Charlie')"); await pg.wait_for_timeout(1800)
    rc = await pg.evaluate(ROW2)
    check(rc['label'] is None and rc['rowIdx'] == -1, f'{T} nothing found: no row, no heading')
    await pg.evaluate("__v.open('Delta')"); await pg.wait_for_timeout(1800)
    rd = await pg.evaluate(ROW2)
    check(rd['ids'] == ['d2'], f'{T} Delta: the airline video is left out, the band’s kept {rd["ids"]}')

    # ---- tap plays it ----
    await pg.evaluate("__v.open('Alpha')"); await pg.wait_for_timeout(1200)
    asked['meta'].clear()
    await pg.evaluate("document.querySelector('.artist-archive-row .yt-tile').click()"); await pg.wait_for_timeout(1500)
    check('a1' in asked['meta'], f'{T} tapping a tile opens that item (its file list asked for) {asked["meta"]}')

    # ---- off with archive.org in Settings > Sources: the real switch, the artist page open behind it ----
    await pg.evaluate("__v.open('Alpha')"); await pg.wait_for_timeout(800)
    check(await pg.evaluate("document.getElementById('archiveSourceSelect').value") == 'on' and (await pg.evaluate(ROW2))['label'] == 'On Archive.org', f'{T} archive.org on in Sources, and the row is showing')
    await pg.evaluate("(()=>{ var s = document.getElementById('archiveSourceSelect'); s.value = 'off'; s.dispatchEvent(new Event('change')); })()"); await pg.wait_for_timeout(400)
    ro = await pg.evaluate(ROW2)
    check(ro['label'] is None and ro['rowIdx'] == -1, f'{T} archive.org turned off in Settings: the On Archive.org row goes from the page behind it')
    n_s = len(asked['search'])
    await pg.evaluate("__v.open('Bravo')"); await pg.wait_for_timeout(1200)
    await pg.evaluate("__v.open('Alpha')"); await pg.wait_for_timeout(800)
    ro2 = await pg.evaluate(ROW2)
    check(ro2['label'] is None and len(asked['search']) == n_s, f'{T} and stays off on other artists\' pages, archive.org not asked ({len(asked["search"]) - n_s} searches)')
    await pg.evaluate("(()=>{ var s = document.getElementById('archiveSourceSelect'); s.value = 'on'; s.dispatchEvent(new Event('change')); })()"); await pg.wait_for_timeout(800)
    check((await pg.evaluate(ROW2))['ids'] == ['a1', 'a2', 'a6'], f'{T} turned on again: the row is back')
    check(not errs, f'{T} no page errors {errs}')
    await ctx.close()

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
        for theme in ('dark', 'light'):
            asked['search'].clear(); asked['meta'].clear()
            await run(b, theme)
        asked['search'].clear(); asked['meta'].clear()
        await run(b, 'dark', 1400, 900, '-desktop')
        await b.close()
    print('ALL PASSED' if not fails else f'FAILS {len(fails)}')
    sys.exit(1 if fails else 0)
asyncio.run(main())
