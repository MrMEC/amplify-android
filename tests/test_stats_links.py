"""Build 377: everything on the profile's numbers and in Listening Stats goes somewhere.
Profile: Artists -> the Artists page, This month -> Listening Stats, Top artist -> Top Artists.
Listening Stats: Music/Radio/Podcasts/Video & TV -> Library, My Stations, Podcasts, Watch; the
Podcasts heading -> Podcasts; a top artist -> that artist's page; a top song or station plays
(and is marked); a followed top show -> its page. Phone, dark and light.
Run: python3 tests/test_stats_links.py (screenshots in /tmp/claude-0/t/shots)"""
import sys as _nsys, os as _nos; _nsys.path.insert(0, _nos.path.dirname(_nos.path.abspath(__file__))); from notice_auto import AUTO_NOTICE
import asyncio, os, json, threading, http.server, functools, shutil, datetime
from playwright.async_api import async_playwright
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = '/tmp/claude-0/t/srv-statslinks'; SHOTS = '/tmp/claude-0/t/shots'; PORT = 8880
shutil.rmtree(ROOT, ignore_errors=True); os.makedirs(ROOT); os.makedirs(SHOTS, exist_ok=True)
HOOK = ("window.__t = { ev: function(js){ return eval(js); }, played: [],"
        " lib: function(ts){ libraryTracks = ts; libraryById = {}; ts.forEach(function(t){ libraryById[favKey(t)] = t; }); artistIndexSig = ''; artistIndexBurst = null; } };\n"
        "  var __origPlayStation = null;\n")
src = open(os.path.join(HERE, '..', 'www', 'index.html')).read()
mark = '  var coverFlow = null;\n'; assert src.count(mark) == 1
open(ROOT + '/index.html', 'w').write(src.replace(mark, mark + HOOK))
H = functools.partial(http.server.SimpleHTTPRequestHandler, directory=ROOT); H.log_message = lambda *a: None
srv = http.server.ThreadingHTTPServer(('127.0.0.1', PORT), H); threading.Thread(target=srv.serve_forever, daemon=True).start()
today = datetime.date.today()
days = {today.isoformat(): {'t': 9000, 'm': 4000, 'r': 3000, 'p': 1500, 'v': 500}}
MOTOWN = {'name': 'Motown Radio', 'urlToResolve': 'http://127.0.0.1:1/motown', 'favicon': '', 'stationuuid': 'motown-uuid'}
LS = {'v': 1, 'start': 1, 'days': days, 'hours': [0] * 24,
      'items': {'MOTOWNKEY': {'n': 'Motown Radio', 'k': 'r', 's': 25000, 'st': MOTOWN},
                'p:1': {'n': 'Episode 12', 'a': 'Talk Is Jericho', 'c': 4242, 'k': 'p', 's': 5000}},
      'artists': {}}
SUBS = [{'collectionId': 4242, 'collectionName': 'Talk Is Jericho', 'artworkUrl600': '', 'feedUrl': 'http://127.0.0.1:1/feed'}]
SEED = ("if(!sessionStorage.getItem('s')){ sessionStorage.setItem('s','1'); localStorage.setItem('radioPlayerListening', %s);"
        " localStorage.setItem('radioPlayerPodcastSubs', %s);"
        " }") % (json.dumps(json.dumps(LS)), json.dumps(json.dumps(SUBS)))
TRACKS = [{'id': 'local:1', 'type': 'local', 'name': 'Stop! In the Name of Love', 'artist': 'The Supremes', 'album': 'More Hits', 'url': 'http://127.0.0.1:1/a.mp3', 'fileName': 'a.mp3'},
          {'id': 'local:2', 'type': 'local', 'name': 'Kiss', 'artist': 'Prince', 'album': 'Parade', 'url': 'http://127.0.0.1:1/b.mp3', 'fileName': 'b.mp3'}]
fails = []
def check(ok, msg):
    print(('PASS ' if ok else 'FAIL ') + msg)
    if not ok: fails.append(msg)
async def run(B, theme):
    T = f'[{theme}]'
    c = await B.new_context(viewport={'width': 390, 'height': 844}, device_scale_factor=2, is_mobile=True, has_touch=True, color_scheme=theme)
    await c.add_init_script(AUTO_NOTICE); await c.add_init_script(SEED)
    pg = await c.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
    await pg.goto(f'http://127.0.0.1:{PORT}/index.html'); await pg.wait_for_timeout(2000)
    await pg.evaluate("(ts)=>__t.lib(ts)", TRACKS)
    await pg.evaluate("(function(){ var o = {}; o[__t.ev('artistMatchKey(\"The Supremes\")')] = {name:'The Supremes',count:42,last:2}; o[__t.ev('artistMatchKey(\"Prince\")')] = {name:'Prince',count:9,last:1}; localStorage.setItem('radioPlayerArtistPlays', JSON.stringify(o)); })()")
    # the song plays need the tracks' keys
    await pg.evaluate("localStorage.setItem('radioPlayerSongPlays', JSON.stringify((function(){ var o = {}; o[__t.ev('favKey(libraryTracks[0])')] = [30, 1]; o[__t.ev('favKey(libraryTracks[1])')] = [12, 1]; return o; })()))")
    # record what gets played instead of playing it
    await pg.evaluate("__t.ev('playStation = function(st){ if(st) window.__t.played.push(st.name); }; 0')")
    heading = "document.getElementById('stationsHeading').textContent"
    async def profile():
        await pg.evaluate("document.getElementById('statsOverlay').classList.remove('open'); __t.ev('closeProfile()')"); await pg.wait_for_timeout(50)
        await pg.tap('#hamburgerBtn'); await pg.wait_for_timeout(350)
    async def state():
        return await pg.evaluate(f"[document.getElementById('profileOverlay').classList.contains('open'), document.getElementById('statsOverlay').classList.contains('open'), {heading}]")
    # --- profile boxes
    await profile()
    tags = await pg.evaluate("Array.prototype.map.call(document.querySelectorAll('#pfStats .pf-stat'), function(b){ return b.tagName + ':' + b.dataset.pfGo; })")
    check(tags == ['BUTTON:artists', 'BUTTON:stats', 'BUTTON:topArtists'], f'{T} the three boxes are buttons {tags}')
    await pg.tap('#pfStats .pf-stat[data-pf-go=artists]'); await pg.wait_for_timeout(500)
    s = await state(); check(s[0] is False and s[2] == 'Artists', f'{T} Artists box -> Artists {s}')
    await profile()
    await pg.tap('#pfStats .pf-stat[data-pf-go=topArtists]'); await pg.wait_for_timeout(500)
    s = await state(); check(s[0] is False and s[2] == 'Top Artists', f'{T} Top artist box -> Top Artists {s}')
    await profile()
    await pg.tap('#pfStats .pf-stat[data-pf-go=stats]'); await pg.wait_for_timeout(500)
    s = await state(); check(s[1] is True, f'{T} This month box -> Listening Stats {s}')
    await pg.screenshot(path=f'{SHOTS}/statslinks-{theme}-top.png')
    await pg.evaluate("document.querySelector('#statsBody .st-legend').scrollIntoView({block:'start'})"); await pg.wait_for_timeout(150)
    await pg.screenshot(path=f'{SHOTS}/statslinks-{theme}-mid.png')
    # --- by type
    for name, want in [('Music', 'My Library'), ('Radio', 'My Stations'), ('Podcasts', 'Podcasts'), ('Video & TV', 'Watch')]:
        await pg.evaluate("(n)=>Array.prototype.filter.call(document.querySelectorAll('#statsBody .st-leg'), function(r){ return r.querySelector('.st-leg-n').textContent === n; })[0].click()", name)
        await pg.wait_for_timeout(500)
        s = await state()
        vis = await pg.evaluate("[document.body.className, document.getElementById('pageTitle') && document.getElementById('pageTitle').textContent]")
        check(s[0] is False and s[1] is False, f'{T} {name} closes stats and goes to {want} {s} {vis[1]!r}')
        print('   ', name, '->', repr(s[2]), repr(vis[1]))
        await profile(); await pg.tap('#pfStats .pf-stat[data-pf-go=stats]'); await pg.wait_for_timeout(400)
    # --- artists
    await pg.evaluate("Array.prototype.filter.call(document.querySelectorAll('#statsBody .st-row'), function(r){ return r.querySelector('.st-row-n').textContent === 'Prince'; })[0].click()"); await pg.wait_for_timeout(500)
    s = await state(); ak = await pg.evaluate("__t.ev('activeArtistKey === artistMatchKey(\"Prince\") && activeLibrarySection')")
    check(s[1] is False and ak == 'artists', f'{T} an artist -> its page {s} {ak}')
    await pg.screenshot(path=f'{SHOTS}/statslinks-{theme}-artist.png')
    await profile(); await pg.tap('#pfStats .pf-stat[data-pf-go=stats]'); await pg.wait_for_timeout(400)
    # --- songs and stations play, and stats stays
    await pg.evaluate("Array.prototype.filter.call(document.querySelectorAll('#statsBody .st-row'), function(r){ return r.querySelector('.st-row-n').textContent === 'Kiss'; })[0].click()"); await pg.wait_for_timeout(300)
    await pg.evaluate("Array.prototype.filter.call(document.querySelectorAll('#statsBody .st-row'), function(r){ return r.querySelector('.st-row-n').textContent === 'Motown Radio'; })[0].click()"); await pg.wait_for_timeout(300)
    p = await pg.evaluate("[window.__t.played, document.getElementById('statsOverlay').classList.contains('open'), Array.prototype.map.call(document.querySelectorAll('#statsBody .st-now .st-row-n'), function(e){ return e.textContent; })]")
    check(p[0] == ['Kiss', 'Motown Radio'] and p[1] and p[2] == ['Motown Radio'], f'{T} a song and a station play, marked {p}')
    await pg.evaluate("document.querySelector('#statsBody .st-now').scrollIntoView({block:'center'})"); await pg.wait_for_timeout(150)
    await pg.screenshot(path=f'{SHOTS}/statslinks-{theme}-lists.png')
    # --- podcasts heading, top show
    await pg.evaluate("document.querySelector('#statsBody .st-h2-link').click()"); await pg.wait_for_timeout(500)
    s = await state(); check(s[1] is False and s[2] == 'Podcasts', f'{T} Podcasts heading -> Podcasts {s}')
    await profile(); await pg.tap('#pfStats .pf-stat[data-pf-go=stats]'); await pg.wait_for_timeout(400)
    await pg.evaluate("Array.prototype.filter.call(document.querySelectorAll('#statsBody .st-row'), function(r){ return r.querySelector('.st-row-n').textContent === 'Talk Is Jericho'; })[0].click()"); await pg.wait_for_timeout(500)
    sh = await pg.evaluate("__t.ev('activeShowCollectionId')")
    check(str(sh) == '4242', f'{T} a followed show -> its page {sh}')
    # --- Back (build 378): from wherever a link went, Back returns to the screen it was tapped on
    async def back():
        await pg.evaluate("document.getElementById('detailBackBtn').click()"); await pg.wait_for_timeout(500)
    async def where():
        return await pg.evaluate("[document.getElementById('profileOverlay').classList.contains('open'), document.getElementById('statsOverlay').classList.contains('open'), document.getElementById('statsPage').scrollTop, document.getElementById('profilePage').scrollTop]")
    async def stats_row(name):
        await profile(); await pg.tap('#pfStats .pf-stat[data-pf-go=stats]'); await pg.wait_for_timeout(400)
        await pg.evaluate("(n)=>{ var r = Array.prototype.filter.call(document.querySelectorAll('#statsBody .st-row, #statsBody .st-leg'), function(r){ var e = r.querySelector('.st-row-n, .st-leg-n'); return e && e.textContent === n; })[0]; r.scrollIntoView({block:'center'}); window.__y = document.getElementById('statsPage').scrollTop; r.click(); }", name)
        await pg.wait_for_timeout(500)
    await stats_row('Prince')
    lab = await pg.evaluate("[getComputedStyle(document.getElementById('detailBackBtn')).display, document.getElementById('detailBackLabel').textContent]")
    await back(); w = await where(); y = await pg.evaluate("window.__y")
    check(lab[0] != 'none' and w[0] and w[1] and abs(w[2] - y) < 3, f'{T} artist page, Back -> Listening Stats where it was (over the profile) {lab} {w} y={y}')
    await pg.screenshot(path=f'{SHOTS}/statslinks-{theme}-back.png')
    for name, want in [('Music', 'Library'), ('Podcasts', 'Podcasts'), ('Video & TV', 'Watch'), ('Radio', 'My Stations')]:
        await stats_row(name)
        lab = await pg.evaluate("[getComputedStyle(document.getElementById('detailBackBtn')).display, document.getElementById('detailBackLabel').textContent, getComputedStyle(document.getElementById('sectionHeadingRow')).display]")
        if name == 'Music': await pg.screenshot(path=f'{SHOTS}/statslinks-{theme}-library-back.png')
        await back(); w = await where()
        check(lab[0] != 'none' and lab[1] == 'Listening Stats' and w[1], f'{T} {want} (from {name}) has Back, and it returns to Listening Stats {lab} {w}')
    # roots keep it while on them, and lose it when you move on
    await stats_row('Music')
    await pg.evaluate("__t.ev('openMyLibraryHome()')"); await pg.wait_for_timeout(200)
    k = await pg.evaluate("getComputedStyle(document.getElementById('detailBackBtn')).display")
    await pg.evaluate("document.querySelector('.mobile-nav-btn[data-nav=video]').click()"); await pg.wait_for_timeout(400)
    k2 = await pg.evaluate("[getComputedStyle(document.getElementById('detailBackBtn')).display, document.getElementById('detailBackLabel').textContent]")
    check(k != 'none' and k2[0] == 'none', f'{T} Library keeps its Back while it re-renders; Watch from the tab bar is a top page again (no Back) {k} {k2}')
    # the profile: Top Artists, a shortcut, Favorites -> Back -> the profile
    for sel, nm in [('#pfStats .pf-stat[data-pf-go=topArtists]', 'Top Artists'), ('#pfStats .pf-stat[data-pf-go=artists]', 'Artists'), ('.pf-link[data-pf-go=stations]', 'My Stations'), ('#pfFavAll', 'Favorites')]:
        await profile()
        await pg.evaluate("document.getElementById('profilePage').scrollTop = 120")
        await pg.evaluate("(s)=>document.querySelector(s).click()", sel); await pg.wait_for_timeout(500)
        lab = await pg.evaluate("document.getElementById('detailBackLabel').textContent")
        await back(); w = await where()
        check(lab == 'Profile' and w[0] and not w[1], f'{T} {nm} from the profile, Back -> the profile {lab} {w}')
    # closed with X, nothing is recorded: Back from a page opened later goes where it should
    await profile(); await pg.tap('#profileCloseBtn'); await pg.wait_for_timeout(200)
    await pg.evaluate("__t.ev('openHomeSectionPage(\"favorites\")')"); await pg.wait_for_timeout(300)
    lab = await pg.evaluate("document.getElementById('detailBackLabel').textContent")
    check(lab != 'Profile', f'{T} closing the profile with X leaves no trail {lab}')
    # --- a station played now keeps enough to play it again
    await pg.evaluate("__t.ev('listenCredit({name:\"Jazz FM\", urlToResolve:\"http://x/jazz\", stationuuid:\"j1\", favicon:\"\"}, 120)')")
    L = await pg.evaluate("JSON.parse(localStorage.getItem('radioPlayerListening')).items")
    jz = [v for v in L.values() if v.get('n') == 'Jazz FM']
    check(jz and jz[0].get('st', {}).get('urlToResolve') == 'http://x/jazz', f'{T} a station listened to now is kept playable {jz}')
    check(not errs, f'{T} no page errors {errs}')
    await c.close()
async def main():
    async with async_playwright() as p:
        B = await p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
        for th in ('dark', 'light'): await run(B, th)
        await B.close()
    print('ALL PASSED' if not fails else f'FAILS {len(fails)}')
asyncio.run(main())
