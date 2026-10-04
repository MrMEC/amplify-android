"""Made for You (build 122): a Home row (and page, and car list) of stations for the artists in
the library, stations from the listener's genres, and library albums to rediscover, each saying
why it's there. Run: python3 tests/test_made_for_you.py (screenshots in /tmp/claude-0/t/shots)"""
import asyncio, os, json, threading, http.server, functools, shutil, subprocess
from playwright.async_api import async_playwright

PORT = 8800
root = '/tmp/claude-0/t/srv_mfy'
shots = '/tmp/claude-0/t/shots'
os.makedirs(shots, exist_ok=True)
shutil.rmtree(root, ignore_errors=True)
os.makedirs(root)
HOOK = ("window.__m = { mfy: function(){ var m = madeForYou(); function s(x){ return [x.kind, x.kind === 'album' ? x.item.album : x.item.name, x.why]; } return { artists: m.artists.map(s), genres: m.genres.map(s), rediscover: m.rediscover.map(s), mix: m.mix.map(s) }; },"
        " reset: function(){ mfyMemo = null; }, setup: function(){ var e = findArtistEntry(artistMatchKey('Charlie')); toggleFavorite(artistFavRecord(e));"
        "   var m = {}; buildAlbumIndex().forEach(function(a){ if(a.album === 'Alpha One') m[a.key] = Date.now(); if(a.album === 'Bravo Blue') m[a.key] = Date.now() - 92 * 864e5; });"
        "   localStorage.setItem('radioPlayerAlbumPlayed', JSON.stringify(m)); },"
        " cur: function(){ return currentStation && currentStation.name; }, home: function(){ loadTopStations(); }, genres: function(){ return mfyTopGenres(4); } };"
        "window.__t = { tracks: function(){ return libraryTracks.map(function(t){ return t.name; }); },"
        " mk: function(){ stationPlaylists.push({ id: 'pl_mix', label: 'Mix', stations: [{ stationuuid: 'st-1', name: 'Radio One', url: 'http://radio.example/one', urlToResolve: 'http://radio.example/one', favicon: '' }] });"
        "   stationPlaylists.push({ id: 'pl_empty', label: 'Empty', stations: [] }); saveStationPlaylists(); renderStationPlaylistList(); },"
        " pl: function(label){ var p = stationPlaylists.filter(function(x){ return x.label === label; })[0]; return p ? p.stations.map(function(s){ return s.name; }) : null; },"
        " stored: function(label){ var p = JSON.parse(localStorage.getItem('radioPlayerStationPlaylists')).filter(function(x){ return x.label === label; })[0]; return p ? p.stations.map(function(s){ return s.name; }) : null; },"
        " openAlbum: function(a){ var al = buildAlbumIndex().filter(function(x){ return x.album === a; })[0]; openAlbumPage(al.key, null); },"
        " status: function(){ var e = document.getElementById('statusLine') || document.querySelector('.status-line'); return e ? e.textContent : ''; } };\n")
_src = open(os.path.join(os.path.dirname(__file__), '..', 'www', 'index.html')).read()
_mark = '  var coverFlow = null;\n'
assert _src.count(_mark) == 1
open(root + '/index.html', 'w').write(_src.replace(_mark, _mark + HOOK))

M = root + '/Music'
os.makedirs(M, exist_ok=True)
SONGS = [('A1', 'Alpha', 'Alpha One', 1, 'Rock'), ('A2', 'Alpha', 'Alpha One', 2, 'Rock'), ('A3', 'Alpha', 'Alpha Two', 1, 'Rock'),
         ('B1', 'Bravo', 'Bravo Blue', 1, 'Jazz'), ('B2', 'Bravo', 'Bravo Blue', 2, 'Jazz'), ('C1', 'Charlie', 'Charlie C', 1, 'Rock/Pop'),
         ('D1', 'Delta', 'Delta D', 1, '')]
for i, (t, a, al, n, g) in enumerate(SONGS):
    subprocess.run(['ffmpeg', '-loglevel', 'error', '-y', '-f', 'lavfi', '-i', f'sine=frequency={300 + i * 60}:duration=3',
                    '-c:a', 'libmp3lame', '-b:a', '32k', '-metadata', f'title={t}', '-metadata', f'artist={a}',
                    '-metadata', f'album={al}', '-metadata', f'track={n}', '-metadata', f'genre={g}', f'{M}/{i + 1:02d}.mp3'], check=True)


class Q(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a): pass
H = functools.partial(Q, directory=root)
srv = http.server.ThreadingHTTPServer(('127.0.0.1', PORT), H)
threading.Thread(target=srv.serve_forever, daemon=True).start()
files = [{'uri': f'http://127.0.0.1:{PORT}/Music/{f}', 'name': f, 'relPath': f'Music/{f}', 'type': 'audio/mpeg',
          'size': os.path.getsize(f'{M}/{f}'), 'lastModified': 1700000000000} for f in sorted(os.listdir(M))]
MOCK = """
(function(){
 var picked = %s, listeners = {};
 var impl = {
   pickMusicFolder: function(){ return Promise.resolve({folder:'Music', files:picked, truncated:false}); },
   setCarCatalog: function(o){ window.__cat = JSON.parse(o.json); return Promise.resolve({}); },
   addListener: function(n, f){ (listeners[n] = listeners[n] || []).push(f); return Promise.resolve({remove:function(){}}); }
 };
 var P = new Proxy({}, {get:function(t,k){
   if(k==='then') return undefined;
   if(k==='setCarLibraryPart') return undefined;
   if(impl[k]) return impl[k];
   return function(){ return Promise.resolve({}); };
 }});
 window.Capacitor = { isNativePlatform:function(){return true;}, getPlatform:function(){return 'android';},
   registerPlugin:function(){ return P; }, Plugins:{AmplifyPlayer:P}, convertFileSrc:function(u){return u;} };
})();
""" % json.dumps(files)

from urllib.parse import urlparse, parse_qs
fails = []
def check(cond, msg):
    print(('PASS ' if cond else 'FAIL ') + msg)
    if not cond: fails.append(msg)
calls = {'tag': []}
NOW_MS = None
EXCL = [{'name': 'Exclusively ' + a, 'url_resolved': 'http://s/ex-' + a, 'stationuuid': 'ex-' + a, 'favicon': '', 'tags': 'rock', 'codec': 'MP3'} for a in ('Alpha', 'Bravo', 'Charlie', 'Zed')]
offline = {'on': False}
async def route(r):
    u = r.request.url
    if '127.0.0.1' in u: return await r.continue_()
    q = parse_qs(urlparse(u).query)
    if '/json/stations/search' in u and not offline['on']:
        if q.get('name', [''])[0] == 'exclusively':
            return await r.fulfill(status=200, content_type='application/json', body=json.dumps(EXCL))
        if 'tag' in q:
            tag = q['tag'][0]; calls['tag'].append(tag)
            return await r.fulfill(status=200, content_type='application/json', body=json.dumps(
                [{'name': '%s Station %d' % (tag.title(), i), 'url_resolved': 'http://s/%s%d' % (tag, i), 'stationuuid': '%s-%d' % (tag, i), 'favicon': '', 'tags': tag, 'codec': 'MP3'} for i in range(6)]))
        return await r.fulfill(status=200, content_type='application/json', body='[]')
    return await r.abort()

SEED = """localStorage.setItem('radioPlayerArtistPlaysReset1', '1');
localStorage.setItem('radioPlayerArtistPlays', JSON.stringify({ alpha: { name: 'Alpha', count: 12, last: Date.now() }, bravo: { name: 'Bravo', count: 3, last: Date.now() - 1000 } }));"""


async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
        ctx = await b.new_context(viewport={'width': 390, 'height': 844}, device_scale_factor=2, is_mobile=True, has_touch=True, color_scheme='dark')
        await ctx.add_init_script(MOCK)
        await ctx.add_init_script("if(!sessionStorage.getItem('seeded')){ sessionStorage.setItem('seeded','1'); " + SEED + " }")
        pg = await ctx.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.route('**/*', route)
        await pg.goto(f'http://127.0.0.1:{PORT}/index.html'); await pg.wait_for_timeout(2500)
        await pg.evaluate("""(function(){ var ov=document.getElementById('addMusicOverlay'); if(ov) ov.classList.add('open');
          var btn=document.getElementById('addMusicFolderBtn'); btn.disabled=false; btn.click(); })()""")
        for _ in range(60):
            await pg.wait_for_timeout(500)
            if len(await pg.evaluate('__t.tracks()')) >= len(SONGS): break
        await pg.evaluate("document.getElementById('addMusicOverlay').classList.remove('open')")
        # Charlie is a favourite artist; Alpha One was played today, Bravo Blue three months ago.
        await pg.evaluate('__m.setup()')
        await pg.evaluate('__m.reset(); __m.home()'); await pg.wait_for_timeout(3500)
        m = await pg.evaluate('__m.mfy()')
        print(json.dumps(m, indent=1)[:1500])
        print('genres', await pg.evaluate('__m.genres()'))

        # 1. stations for the library's artists
        arts = {x[1]: x[2] for x in m['artists']}
        check(set(arts) == {'Alpha', 'Bravo', 'Charlie'}, f'artist stations for library artists only (not Zed) {list(arts)}')
        check([x[1] for x in m['artists']][0] == 'Alpha', 'the most-played artist first')
        check(arts.get('Alpha') == 'Because you play Alpha' and arts.get('Charlie') == 'A favorite artist', f'each says why {arts}')
        # 2. genre stations
        gen = await pg.evaluate('__m.genres()')
        check(gen[:2] == ['rock', 'jazz'], f'top genres from the library, weighted by plays {gen}')
        check(sorted(calls['tag']) == sorted(gen), f'one directory request per genre {calls["tag"]}')
        gs = m['genres']
        check(gs and gs[0][2] == 'Because you like Rock' and any(x[2] == 'Because you like Jazz' for x in gs), f'genre stations say which genre {[x[2] for x in gs][:4]}')
        check(len([x for x in gs if 'Rock' in x[2]]) <= 4, 'no more than four from one genre')
        # 3. rediscover
        rd = {x[1]: x[2] for x in m['rediscover']}
        check('Alpha One' not in rd, 'an album played today is not suggested')
        check(rd.get('Bravo Blue') == 'Not played in 3 months', f'an album not played for months says so {rd}')
        check(rd.get('Alpha Two') == 'Because you play Alpha', f'an unplayed album by a played artist {rd}')
        # the Home row
        check(m['mix'][:3] == [m['artists'][0], m['genres'][0], m['rediscover'][0]], 'the Home row takes turns: artist station, genre station, album')
        row = await pg.evaluate("""(()=>{ var s = document.getElementById('madeForYouSection'); var tiles = Array.from(document.querySelectorAll('#madeForYouGrid .tile'));
          return { shown: getComputedStyle(s).display !== 'none', heading: document.getElementById('madeForYouHeading').textContent.trim(),
            names: tiles.map(function(t){ return t.querySelector('.tile-name').textContent; }), subs: tiles.map(function(t){ var x = t.querySelector('.tile-sub'); return x ? x.textContent : null; }),
            after: (function(){ var a = document.getElementById('topArtistsSection'), b = s; return !!(a.compareDocumentPosition(b) & 4); })() }; })()""")
        check(row['shown'] and row['heading'] == 'Made for You', f'Home shows Made for You {row["heading"]}')
        check(len(row['names']) == len(m['mix']) and all(row['subs']), f'every tile has its reason under it {row["subs"][:4]}')
        await pg.evaluate("document.getElementById('madeForYouSection').scrollIntoView()"); await pg.wait_for_timeout(300)
        await pg.screenshot(path=f'{shots}/mfy-home.png')
        # play a station from the row, open an album from it
        await pg.evaluate("Array.from(document.querySelectorAll('#madeForYouGrid .tile')).filter(function(t){ return t.querySelector('.tile-name').textContent === 'Alpha'; })[0].click()"); await pg.wait_for_timeout(600)
        check(await pg.evaluate("__m.cur()") in ('Alpha', 'Exclusively Alpha'), f'a station tile plays it ({await pg.evaluate("__m.cur()")})')
        await pg.evaluate("Array.from(document.querySelectorAll('#madeForYouGrid .tile')).filter(function(t){ return /Alpha Two/.test(t.textContent); })[0].click()"); await pg.wait_for_timeout(700)
        check(await pg.evaluate("document.body.classList.contains('album-open') && /Alpha Two/.test(document.getElementById('albumHeroName').textContent)"), 'an album tile opens the album')
        # the page
        await pg.evaluate('__m.home()'); await pg.wait_for_timeout(800)
        await pg.evaluate("document.getElementById('madeForYouHeading').click()"); await pg.wait_for_timeout(600)
        pgv = await pg.evaluate("""(()=>({ heading: document.getElementById('stationsHeading').textContent,
          labels: Array.from(document.querySelectorAll('#stationsGrid .mfy-label')).map(function(l){ return l.textContent; }),
          rows: document.querySelectorAll('#stationsGrid .mfy-row').length, shuffle: getComputedStyle(document.getElementById('libraryShuffleBtn')).display, back: document.getElementById('detailBackLabel').textContent }))()""")
        check(pgv['heading'] == 'Made for You' and pgv['labels'] == ['Stations for Your Artists', 'From Your Genres', 'Rediscover'], f'the page groups them {pgv}')
        check(pgv['shuffle'] == 'none', 'no stray Shuffle button on the page')
        check(pgv['rows'] == len(m['artists']) + len(m['genres']) + len(m['rediscover']), 'with every item as a row')
        ov = await pg.evaluate("""Array.from(document.querySelectorAll('#stationsGrid .mfy-label')).map(function(l){
          var n = l.nextElementSibling, p = l.previousElementSibling; var r = l.getBoundingClientRect();
          return [Math.round(n.getBoundingClientRect().top - r.bottom), p ? Math.round(r.top - p.getBoundingClientRect().bottom) : null]; })""")
        check(all(a >= 2 and (b is None or b >= 12) for a, b in ov), f'headings sit clear of the rows above and below them {ov}')
        await pg.screenshot(path=f'{shots}/mfy-page.png')
        # the car
        await pg.wait_for_timeout(3000)
        cat = await pg.evaluate('window.__cat')
        lst = (cat or {}).get('lists', {}).get('madeForYou')
        check(lst and lst[0]['t'] == 'station' and lst[0].get('sub') == m['mix'][0][2] and any(x['t'] == 'album' for x in lst), f'Android Auto gets the same mix {lst and lst[:3]}')
        java = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'android/app/src/main/java/com/markcoleman/amplify/CarLibrary.java')).read()
        check('"home:madeforyou", "Made for You"' in java and '"home:madeforyou", "madeForYou"' in java, 'the car menu has a Made for You folder under Home')
        # stays the same all day; genre stations kept for offline
        n_tag = len(calls['tag'])
        offline['on'] = True
        await pg.reload(); await pg.wait_for_timeout(3500)
        await pg.evaluate('__m.reset()')
        m2 = await pg.evaluate('__m.mfy()')
        check(m2['genres'] == m['genres'] and len(calls['tag']) == n_tag, 'genre picks are kept for the day (and offline), not asked for again')
        check(m2['rediscover'] == m['rediscover'], 'the albums to rediscover stay the same all day')
        check(not errs, f'no page errors {errs[:3]}')
        await b.close()
    print('ALL PASSED' if not fails else f'FAILED {fails}')

asyncio.run(main())
