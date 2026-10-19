"""Build 263 (phase 2): your own channels are made and changed in Live TV's Edit. Edit lists Your
Channels (with New Channel) above Added Channels. The editor (a dialog): a name (blank = named
from what it plays), a picture, what it plays (Shows & Movies picked from the library with a
search, All Movies from the phone / Plex / both, a Genre, a Decade) and the order (In Order: the
shows take turns; Shuffle; Daily Shuffle: a new order each day from midnight). Save only when
there's something to play; Delete asks first. A channel of several shows names the show on each
program. Start from the Beginning on Now Playing; the channels go into Export.
Run: python3 tests/test_live_channels_editor.py (screenshots in /tmp/claude-0/t/shots)"""
import sys as _nsys, os as _nos; _nsys.path.insert(0, _nos.path.dirname(_nos.path.abspath(__file__))); from notice_auto import AUTO_NOTICE
import os, json, time, datetime, asyncio
HERE = os.path.dirname(os.path.abspath(__file__))
src = open(os.path.join(HERE, 'test_live_channels.py')).read()
head = src[:src.index('\nasync def run(')]
head = head.replace("'/tmp/claude-0/t/srv-livech'", "'/tmp/claude-0/t/srv-livech2'").replace('PORT = 8862', 'PORT = 8863')
# Export: the backup the page saves
head = head.replace("if(k==='videoState')", "if(k==='saveToDownloads') return function(a){ window.__saved = a; return Promise.resolve({ folder: 'Downloads', name: a.name }); };\n   if(k==='videoState')")
exec(head)

# Years and genres (Plex), as a sync with build 263 keeps them
YG = {'10': ('2005', ['Comedy']), '20': ('1995', ['Comedy']), '30': ('1989', ['Comedy']), '40': ('1994', ['Comedy', 'Romance'])}
for sh in SHOWS:
    sh['y'], sh['g'] = YG[sh['k']]
MOVIES[0]['g'] = ['Action']
SEED = """(function(){ if(!localStorage.getItem('__seeded')){ localStorage.setItem('__seeded','1');
  localStorage.setItem('radioPlayerPlexAccount', %s);
  var lib = JSON.parse(%s); lib.at = Date.now(); localStorage.setItem('radioPlayerPlexLib', JSON.stringify(lib));
  localStorage.setItem('radioPlayerVideoFiles', %s);
  localStorage.setItem('radioPlayerVideoInfo', %s);
  localStorage.setItem('radioPlayerVideoChannels', %s);
  localStorage.setItem('radioPlayerVideoTab', 'channels'); } })();""" % tuple(json.dumps(json.dumps(x)) for x in (ACCT, LIB, FILES, INFO, CHANNELS))

def fnv(s):
    h = 2166136261
    for ch in s.encode('utf-16-le')[::2]:   # ASCII ids: one char per code unit
        h ^= ch
        h = (h * 16777619) & 0xffffffff
    return h
def plex_id(k): return 'plex:' + SRV[:8] + ':' + k

ED = """(()=>{ var o=document.getElementById('liveChOverlay'); var g=function(id){ return document.getElementById(id); };
  var on=function(id){ return Array.from(g(id).querySelectorAll('.home-tab.active')).map(function(b){ return b.textContent; }).join(); };
  var r=g('liveChPanel').getBoundingClientRect();
  return { open: o.classList.contains('open'), title: g('liveChTitle').textContent, name: g('liveChName').value, ph: g('liveChName').placeholder,
    kind: on('liveChKind'), order: on('liveChOrder'), from: on('liveChFrom'), del: getComputedStyle(g('liveChDeleteBtn')).visibility !== 'hidden',
    save: !g('liveChSaveBtn').disabled, sum: g('liveChSummary').textContent, focused: document.activeElement && document.activeElement.tagName,
    rows: Array.from(g('liveChList').querySelectorAll('.artist-info-row')).filter(function(b){ return !g('liveChPanePick').hidden; }).map(function(b){ return [b.querySelector('.artist-info-name').textContent, b.getAttribute('aria-selected')]; }),
    genres: Array.from(g('liveChGenre').options).map(function(x){ return x.value; }), decades: Array.from(g('liveChDecade').options).map(function(x){ return x.value; }),
    panes: ['Pick','Movies','Genre','Decade'].filter(function(p){ return !g('liveChPane'+p).hidden; }),
    fits: r.left >= 0 && r.right <= innerWidth + .5 && r.top >= 0 && r.bottom <= innerHeight + .5 }; })()"""
async def ed(pg): return await pg.evaluate(ED)
async def pill(pg, box, label):
    await pg.evaluate("(function(b,l){ Array.from(document.querySelectorAll('#'+b+' .home-tab')).filter(function(x){ return x.textContent===l; })[0].click(); })(%s,%s)" % (json.dumps(box), json.dumps(label)))
    await pg.wait_for_timeout(250)
async def pick(pg, name):
    await pg.evaluate("(function(n){ Array.from(document.querySelectorAll('#liveChList .artist-info-row')).filter(function(x){ return x.querySelector('.artist-info-name').textContent===n; })[0].click(); })(%s)" % json.dumps(name))
    await pg.wait_for_timeout(200)
async def defs(pg): return await pg.evaluate("JSON.parse(localStorage.getItem('radioPlayerLiveChannels') || 'null')")
EDITLIST = """(()=>{ return Array.from(document.querySelectorAll('#stationsGrid > *, #stationsGrid > .ch-edit-list > *')).map(function(e){
  if(e.classList.contains('ch-group-head')) return 'H:' + e.textContent;
  if(e.id === 'liveChNewBtn') return 'NEW';
  if(e.classList.contains('lc-row')) return 'L:' + e.querySelector('.tile-name').textContent + '|' + ((e.querySelector('.tile-sub')||{}).textContent||'');
  if(e.classList.contains('ch-item')) return 'C:' + e.querySelector('.tile-name').textContent;
  return ''; }).filter(Boolean); })()"""


async def run2(p, theme, width):
    T = f'[{theme} {width}]'
    b = await p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
    ctx = await b.new_context(viewport={'width': width, 'height': 860}, device_scale_factor=2, is_mobile=True, has_touch=True, color_scheme=theme, locale='en-US', timezone_id='America/New_York')
    await ctx.add_init_script(MOCK); await ctx.add_init_script(AUTO_NOTICE); await ctx.add_init_script(SEED)
    await ctx.add_init_script("try{ localStorage.setItem('radioPlayerTheme', '%s'); }catch(e){}" % theme)
    pg = await ctx.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e) + ' ' + (e.stack or '')[:300]))
    await pg.route('**/*', route)
    await pg.goto(f'http://127.0.0.1:{PORT}/index.html'); await pg.wait_for_timeout(3000)
    await pg.evaluate("document.querySelector('.mobile-nav-btn[data-nav=video]').click()"); await pg.wait_for_timeout(1500)
    d0 = await defs(pg)
    check(d0 and [x['id'] for x in d0] == ['office', 'madtv', 'seinfeld', 'movies'], f'{T} phase 1’s four channels are saved as your channels {d0 and [x["id"] for x in d0]}')
    g = await grid(pg)
    check([r['url'] for r in g['rows']][:4] == ['amplify-live:office', 'amplify-live:madtv', 'amplify-live:seinfeld', 'amplify-live:movies'], f'{T} the guide is as before')

    # Edit: Your Channels (New Channel, the four) above Added Channels
    await pg.evaluate("document.getElementById('videoReorderHeaderBtn').click()"); await pg.wait_for_timeout(700)
    el = await pg.evaluate(EDITLIST)
    check(el[:3] == ['H:Your Channels', 'NEW', 'L:The Office (US)|Shows & movies · In order'] and 'L:Movies|All movies on the phone · Shuffled' in el
          and el.index('H:Added Channels') > el.index('L:Movies|All movies on the phone · Shuffled') and el[-1] == 'C:Buzzr', f'{T} Edit: Your Channels with New Channel, then Added Channels {el}')
    await pg.evaluate("window.scrollTo(0,0)"); await pg.wait_for_timeout(200)
    await pg.screenshot(path=f'{SHOTS}/livech2-edit-{theme}-{width}.png')

    # New Channel: nothing focused, Save not ready, no Delete
    await pg.evaluate("document.getElementById('liveChNewBtn').click()"); await pg.wait_for_timeout(600)
    e = await ed(pg)
    check(e['open'] and e['title'] == 'New Channel' and not e['del'] and not e['save'] and e['focused'] not in ('INPUT', 'SELECT') and e['kind'] == 'Shows & Movies' and e['order'] == 'In Order',
          f'{T} New Channel: Shows & Movies, In Order, nothing to save yet, no Delete, no field focused {e["focused"]}')
    names = [r[0] for r in e['rows']]
    check(names == ['Friends', 'MADtv', 'Seinfeld', 'The Office (US)', 'Alien', 'Broken', 'Heat', 'Plex Only Movie', 'Up'], f'{T} the list: the library’s shows then movies, A to Z {names}')
    check(e['fits'], f'{T} the dialog fits the screen')
    await pg.fill('#liveChSearch', 'fri'); await pg.wait_for_timeout(300)
    e = await ed(pg)
    check([r[0] for r in e['rows']] == ['Friends'], f'{T} the search narrows the list {e["rows"]}')
    await pick(pg, 'Friends')
    await pg.fill('#liveChSearch', ''); await pg.wait_for_timeout(300)
    await pick(pg, 'Seinfeld')
    e = await ed(pg)
    sel = [r[0] for r in e['rows'] if r[1] == 'true']
    check(sel == ['Friends', 'Seinfeld'] and e['save'] and e['ph'] == 'Friends & Seinfeld' and e['sum'].startswith('2 shows, about 3 hours'),
          f'{T} picking: ticked, Save ready, named from them, how long before it repeats {sel} {e["ph"]!r} {e["sum"]!r}')
    await pill(pg, 'liveChOrder', 'Daily Shuffle')
    await pg.fill('#liveChName', 'Sitcoms')
    await pg.screenshot(path=f'{SHOTS}/livech2-editor-{theme}-{width}.png')
    await pg.evaluate("document.getElementById('liveChSaveBtn').click()"); await pg.wait_for_timeout(700)
    d1 = await defs(pg)
    new = d1[-1] if d1 else {}
    check(len(d1) == 5 and new.get('name') == 'Sitcoms' and new.get('order') == 'daily' and new['src'] == {'kind': 'pick', 'shows': ['Friends', 'Seinfeld'], 'movies': []},
          f'{T} Save keeps the channel {new}')
    el = await pg.evaluate(EDITLIST)
    check('L:Sitcoms|Shows & movies · Daily shuffle' in el and not (await ed(pg))['open'], f'{T} the dialog closes and Edit lists it {el[:8]}')

    # The guide: after the others, the show named on each program; the day's own shuffle from midnight
    await pg.evaluate("document.getElementById('videoReorderHeaderBtn').click()"); await pg.wait_for_timeout(700)
    g = await grid(pg)
    urls = [r['url'] for r in g['rows']]
    url = 'amplify-live:' + new['id']
    check(urls.index(url) == 4 and urls[5] == CHANNELS[0]['url'], f'{T} it joins the top of the guide, after the others {urls}')
    row = g['rows'][4]
    eps = [x for x in EPS if x['gk'] in ('40', '30') and x['sn'] > 0]
    day = datetime.datetime.now(ZoneInfo('America/New_York')).strftime('%Y-%m-%d')
    seed = new['id'] + '|' + day
    eps.sort(key=lambda x: (fnv(plex_id(x['k']) + '|' + seed), plex_id(x['k'])))
    midnight = datetime.datetime.now(ZoneInfo('America/New_York')).replace(hour=0, minute=0, second=0, microsecond=0).timestamp()
    total = sum(x['d'] for x in eps)
    off = (time.time() - midnight) % total
    acc = 0
    for x in eps:
        if acc <= off < acc + x['d']: cur = x; break
        acc += x['d']
    nowb = [x for x in row['blocks'] if x['now']]
    want_t = cur['st']; want_s = 'S%d E%d · %s' % (cur['sn'], cur['en'], cur['t'])
    check(len(nowb) == 1 and nowb[0]['t'] == want_t and nowb[0]['s'] == want_s, f'{T} daily shuffle: what’s on is the day’s order from midnight, the show named {[(x["t"], x["s"]) for x in nowb]} vs {(want_t, want_s)}')
    check(all(x['t'] in ('Friends', 'Seinfeld') for x in row['blocks']), f'{T} every program names its show')
    await pg.evaluate("window.scrollTo(0,0)"); await pg.wait_for_timeout(200)
    await pg.screenshot(path=f'{SHOTS}/livech2-guide-{theme}-{width}.png')

    # Edit it: Genre (from Plex) -> Romance: just Friends, its episodes titled again
    await pg.evaluate("document.getElementById('videoReorderHeaderBtn').click()"); await pg.wait_for_timeout(700)
    await pg.evaluate("(function(id){ document.querySelector('.lc-row[data-live-id=\"'+id+'\"]').click(); })(%s)" % json.dumps(new['id'])); await pg.wait_for_timeout(600)
    e = await ed(pg)
    check(e['title'] == 'Edit Channel' and e['name'] == 'Sitcoms' and e['del'] and e['order'] == 'Daily Shuffle' and [r[0] for r in e['rows'] if r[1] == 'true'] == ['Friends', 'Seinfeld'],
          f'{T} Edit Channel opens with it as saved, Delete there')
    await pill(pg, 'liveChKind', 'Genre')
    e = await ed(pg)
    check(e['panes'] == ['Genre'] and e['genres'] == ['Action', 'Comedy', 'Romance'], f'{T} Genre lists the library’s genres {e["genres"]}')
    await pg.select_option('#liveChGenre', 'Romance'); await pg.wait_for_timeout(300)
    await pill(pg, 'liveChOrder', 'In Order')
    e = await ed(pg)
    check(e['sum'].startswith('1 show,') and e['save'], f'{T} Romance: one show {e["sum"]!r}')
    await pg.screenshot(path=f'{SHOTS}/livech2-genre-{theme}-{width}.png')
    await pg.evaluate("document.getElementById('liveChSaveBtn').click()"); await pg.wait_for_timeout(700)
    await pg.evaluate("document.getElementById('videoReorderHeaderBtn').click()"); await pg.wait_for_timeout(700)
    g = await grid(pg)
    row = [r for r in g['rows'] if r['url'] == url][0]
    check(all(x['t'].startswith('Friends ') and x['s'].startswith('S1 E') for x in row['blocks']), f'{T} one show: programs titled by episode again {[(x["t"], x["s"]) for x in row["blocks"][:3]]}')

    # A Decade channel (the 1990s: MADtv, Friends, Heat), In Order: the shows and the movie take turns
    await pg.evaluate("document.getElementById('videoReorderHeaderBtn').click()"); await pg.wait_for_timeout(700)
    await pg.evaluate("document.getElementById('liveChNewBtn').click()"); await pg.wait_for_timeout(500)
    await pill(pg, 'liveChKind', 'Decade')
    e = await ed(pg)
    check(e['decades'] == ['1970', '1980', '1990', '2000', '2010'], f'{T} Decade lists the decades the library has {e["decades"]}')
    await pg.select_option('#liveChDecade', '1990'); await pg.wait_for_timeout(300)
    e = await ed(pg)
    check(e['ph'] == '1990s' and e['sum'].startswith('2 shows and 1 movie'), f'{T} the 1990s: two shows and a movie {e["ph"]!r} {e["sum"]!r}')
    await pg.evaluate("document.getElementById('liveChSaveBtn').click()"); await pg.wait_for_timeout(700)
    d2 = await defs(pg)
    dec = d2[-1]
    await pg.evaluate("document.getElementById('videoReorderHeaderBtn').click()"); await pg.wait_for_timeout(700)
    g = await grid(pg)
    row = [r for r in g['rows'] if r['url'] == 'amplify-live:' + dec['id']][0]
    seq = [x['t'] for x in row['blocks']]
    # turns: MADtv (4 eps), Friends (3), Heat (1): M F H M F M F M, then again
    cyc = ['MADtv', 'Friends', 'Heat', 'MADtv', 'Friends', 'MADtv', 'Friends', 'MADtv'] * 4
    inside = any(cyc[i:i + len(seq)] == seq for i in range(8))
    check(row['name'] == '1990s' and len(seq) >= 6 and inside,
          f'{T} In Order: the shows and the movie take turns {seq[:8]}')

    # All Movies from Both: the phone's and Plex's
    await pg.evaluate("document.getElementById('videoReorderHeaderBtn').click()"); await pg.wait_for_timeout(700)
    await pg.evaluate("document.getElementById('liveChNewBtn').click()"); await pg.wait_for_timeout(500)
    await pill(pg, 'liveChKind', 'All Movies')
    e = await ed(pg)
    check(e['panes'] == ['Movies'] and e['from'] == 'Phone' and e['sum'].startswith('3 movies'), f'{T} All Movies: the phone’s by default {e["sum"]!r}')
    await pill(pg, 'liveChFrom', 'Both')
    e = await ed(pg)
    check(e['sum'].startswith('4 movies'), f'{T} Both adds Plex’s {e["sum"]!r}')
    # Picture: the cover dialog opens over it
    await pg.evaluate("document.getElementById('liveChArtChange').click()"); await pg.wait_for_timeout(500)
    art = await pg.evaluate("[document.getElementById('artUrlOverlay').classList.contains('open'), getComputedStyle(document.getElementById('artUrlOverlay')).zIndex]")
    check(art[0] and int(art[1]) > 500, f'{T} Change opens the picture dialog on top {art}')
    await pg.evaluate("document.querySelector('#artUrlOverlay .settings-close').click()"); await pg.wait_for_timeout(300)
    # Close without saving: nothing added
    await pg.evaluate("document.getElementById('liveChCloseBtn').click()"); await pg.wait_for_timeout(400)
    check(len(await defs(pg)) == len(d2), f'{T} closing without Save adds nothing')

    # Delete asks first: Cancel keeps it, Delete removes it (and its place in the guide)
    await pg.evaluate("(function(id){ document.querySelector('.lc-row[data-live-id=\"'+id+'\"]').click(); })(%s)" % json.dumps(new['id'])); await pg.wait_for_timeout(500)
    await pg.evaluate("document.getElementById('liveChDeleteBtn').click()"); await pg.wait_for_timeout(400)
    cf = await pg.evaluate("[document.getElementById('confirmOverlay').classList.contains('open'), document.getElementById('confirmTitle').textContent, document.getElementById('confirmOk').textContent]")
    check(cf[0] and cf[1] == 'Delete “Sitcoms”?' and cf[2] == 'Delete', f'{T} Delete asks first {cf}')
    await pg.screenshot(path=f'{SHOTS}/livech2-delete-{theme}-{width}.png')
    await pg.evaluate("document.getElementById('confirmCancel').click()"); await pg.wait_for_timeout(300)
    check(any(x['id'] == new['id'] for x in await defs(pg)) and (await ed(pg))['open'], f'{T} Cancel keeps it')
    await pg.evaluate("document.getElementById('liveChDeleteBtn').click()"); await pg.wait_for_timeout(300)
    await pg.evaluate("document.getElementById('confirmOk').click()"); await pg.wait_for_timeout(700)
    el = await pg.evaluate(EDITLIST)
    check(not any(x['id'] == new['id'] for x in await defs(pg)) and not any(x.startswith('L:Sitcoms') for x in el) and not (await ed(pg))['open'], f'{T} Delete removes it')

    # Start from the Beginning, on Now Playing's menu
    await pg.evaluate("document.getElementById('videoReorderHeaderBtn').click()"); await pg.wait_for_timeout(700)
    await tap_now(pg, 'amplify-live:office'); await pg.wait_for_timeout(2500)
    await pg.evaluate("window.__seeks=[]")
    vis = await pg.evaluate("getComputedStyle(document.getElementById('npLiveRestartBtn')).display")
    await pg.evaluate("document.getElementById('npLiveRestartBtn').click()"); await pg.wait_for_timeout(500)
    sk = await pg.evaluate("window.__seeks")
    check(vis != 'none' and sk and sk[-1] == 0, f'{T} Start from the Beginning: the episode from its start {vis} {sk}')

    # Export carries the channels
    await pg.evaluate("document.getElementById('exportFavBtn').click()"); await pg.wait_for_timeout(800)
    saved = await pg.evaluate("window.__saved ? JSON.parse(window.__saved.text).liveChannels : null")
    check(saved and [x['id'] for x in saved] == [x['id'] for x in await defs(pg)], f'{T} Export includes your channels {saved and len(saved)}')
    check(not errs, f'{T} no page errors {errs[:3]}')
    await b.close()


async def main():
    async with async_playwright() as p:
        await run2(p, 'dark', 412)
        await run2(p, 'light', 360)
    print('ALL PASSED' if not fails else f'FAILED {len(fails)}: {fails}')

asyncio.run(main())
