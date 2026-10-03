"""Skipping through a list: a station (or song) tapped in a playlist, Favorites, an artist page
section or Now Playing's "More from" list plays through that list, so Next/Previous on Now
Playing, the player bar and the media session (lock screen, Android Auto) step along it.
Songs tapped while browsing the library still play on through the library.
Run: python3 tests/test_station_skip.py (screenshots in /tmp/claude-0/t/shots)"""
import asyncio, os, json, threading, http.server, functools, shutil, subprocess
from playwright.async_api import async_playwright

PORT = 8794
root = '/tmp/claude-0/t/srv_skip'
shots = '/tmp/claude-0/t/shots'
os.makedirs(shots, exist_ok=True)
shutil.rmtree(root, ignore_errors=True)
os.makedirs(root)
ST = lambda n: ("{ stationuuid: 'st-" + n + "', name: '" + n + "', url: 'http://radio.example/" + n.replace(' ', '')
                + "', urlToResolve: 'http://radio.example/" + n.replace(' ', '') + "', favicon: '', tags: '' }")
HOOK = ("window.__t = { tracks: function(){ return libraryTracks.map(function(t){ return t.name; }); },"
        " T: function(n){ return libraryTracks.filter(function(t){ return t.name === n; })[0]; },"
        " setup: function(){ var T = window.__t.T;"
        "   artistStations = [" + ST('Exclusively Ann') + ", " + ST('Exclusively Bob') + ", " + ST('Exclusively Bob Hits').replace("name: 'Exclusively Bob Hits'", "name: 'Exclusively Bob'") + "]; artistStationsFailed = false; artistStationsPromise = Promise.resolve(artistStations);"
        "   stationPlaylists.push({ id: 'pl_mix', label: 'Mix', stations: [" + ST('Radio A') + ", T('Song 1'), " + ST('Radio B') + ", " + ST('Radio C') + "] });"
        "   stationPlaylists.push({ id: 'pl_ann', label: 'Ann', stations: [" + ST('Ann Hits') + ", " + ST('Exclusively Ann') + ", " + ST('Ann Live') + "] });"
        "   saveStationPlaylists(); favorites = [" + ST('Fav One') + ", " + ST('Fav Two') + ", T('Song 2'), " + ST('Fav Three') + "]; saveFavorites(); },"
        " q: function(){ return { list: playQueue.map(function(s){ return s.name; }), idx: queueIndex, label: queueLabel, cur: currentStation && currentStation.name }; },"
        " openPl: function(id){ runStationPlaylist(findStationPlaylistById(id)); }, openFavs: function(){ openHomeSectionPage('favorites'); },"
        " openArtist: function(n){ openArtistPage(artistMatchKey(n)); }, openNp: function(){ openNowPlaying(); },"
        " songs: function(){ runLibrarySection('songs'); },"
        " skip: function(){ return window.__skip; } };\n")
_src = open(os.path.join(os.path.dirname(__file__), '..', 'www', 'index.html')).read()
_mark = '  var coverFlow = null;\n'
assert _src.count(_mark) == 1
open(root + '/index.html', 'w').write(_src.replace(_mark, _mark + HOOK))

M = root + '/Music'
os.makedirs(M, exist_ok=True)
for i, (t, a) in enumerate([('Song 1', 'Ann'), ('Song 2', 'Bob'), ('Song 3', 'Bob')]):
    subprocess.run(['ffmpeg', '-loglevel', 'error', '-y', '-f', 'lavfi', '-i', f'sine=frequency={300 + i * 60}:duration=3',
                    '-c:a', 'libmp3lame', '-b:a', '32k', '-metadata', f'title={t}', '-metadata', f'artist={a}',
                    '-metadata', f'album={a} Album', '-metadata', f'track={i + 1}', f'{M}/{i + 1:02d}.mp3'], check=True)


class Q(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a): pass
H = functools.partial(Q, directory=root)
srv = http.server.ThreadingHTTPServer(('127.0.0.1', PORT), H)
threading.Thread(target=srv.serve_forever, daemon=True).start()
files = [{'uri': f'http://127.0.0.1:{PORT}/Music/{f}', 'name': f, 'relPath': f'Music/{f}', 'type': 'audio/mpeg',
          'size': os.path.getsize(f'{M}/{f}'), 'lastModified': 1700000000000} for f in sorted(os.listdir(M))]
MOCK = """
(function(){
 var picked = %s, listeners = {}, cur = null;
 function emit(n, ev){ (listeners[n] || []).forEach(function(f){ try{ f(ev); }catch(e){} }); }
 var impl = {
   pickMusicFolder: function(){ return Promise.resolve({folder:'Music', files:picked, truncated:false}); },
   cacheCheck: function(){ return Promise.resolve({ url: 'file:///cache/x.mp3' }); },
   load: function(o){ cur = o.id; setTimeout(function(){ emit('state', { id: cur, state: 'ready', isPlaying: true, playWhenReady: true, position: 0, duration: 0 }); }, 20); return Promise.resolve({}); },
   setSkip: function(o){ window.__skip = o; return Promise.resolve({}); },
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

fails = []
def check(cond, msg):
    print(('PASS ' if cond else 'FAIL ') + msg)
    if not cond: fails.append(msg)

CLICK = """(name) => { var el = Array.from(document.querySelectorAll('#stationsGrid .tile, #stationsGrid .row-item')).filter(function(e){
  var n = e.querySelector('.tile-name, .song-row-title, .row-name'); return n && n.textContent === name; })[0]; el.click(); return !!el; }"""


async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
        ctx = await b.new_context(viewport={'width': 390, 'height': 844}, device_scale_factor=2, is_mobile=True, has_touch=True, color_scheme='dark')
        await ctx.add_init_script(MOCK)
        pg = await ctx.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.route('**/*', lambda route: route.continue_() if '127.0.0.1' in route.request.url else route.abort())
        await pg.goto(f'http://127.0.0.1:{PORT}/index.html'); await pg.wait_for_timeout(2500)
        await pg.evaluate("""(function(){ var ov=document.getElementById('addMusicOverlay'); if(ov) ov.classList.add('open');
          var btn=document.getElementById('addMusicFolderBtn'); btn.disabled=false; btn.click(); })()""")
        for _ in range(60):
            await pg.wait_for_timeout(500)
            if len(await pg.evaluate('__t.tracks()')) >= 3: break
        await pg.evaluate('__t.setup()')
        q = lambda: pg.evaluate('__t.q()')
        steps = lambda: pg.evaluate("""(function(){ function s(id){ var b=document.getElementById(id); return { shown: getComputedStyle(b).display !== 'none', on: !b.disabled }; }
          return { prev: s('npPrevBtn'), next: s('npNextBtn'), barPrev: s('barPrevBtn'), barNext: s('barNextBtn') }; })()""")

        # ---- a playlist: tap a station, skip along the playlist (songs included) ----
        await pg.evaluate("__t.openPl('pl_mix')"); await pg.wait_for_timeout(600)
        check(await pg.evaluate(CLICK, 'Radio B'), 'tapped Radio B in the playlist')
        await pg.wait_for_timeout(500)
        st = await q()
        check(st['list'] == ['Radio A', 'Song 1', 'Radio B', 'Radio C'] and st['idx'] == 2 and st['label'] == 'Mix', f'the playlist is the queue {st}')
        await pg.evaluate('__t.openNp()'); await pg.wait_for_timeout(700)
        s = await steps()
        check(s['prev']['shown'] and s['next']['shown'] and s['prev']['on'] and s['next']['on'], f'Now Playing shows Previous and Next for the station {s}')
        await pg.screenshot(path=f'{shots}/skip-np-station.png')
        sk = await pg.evaluate('__t.skip()')
        check(sk and sk.get('next') and sk.get('prev'), f'lock screen / Android Auto get Next and Previous {sk}')
        await pg.evaluate("document.getElementById('npNextBtn').click()"); await pg.wait_for_timeout(600)
        st = await q()
        check(st['cur'] == 'Radio C' and st['idx'] == 3, f'Next plays Radio C {st}')
        s = await steps()
        check(s['next']['shown'] and not s['next']['on'] and s['prev']['on'], f'at the end Next is off, Previous on {s}')
        await pg.evaluate("document.getElementById('npPrevBtn').click()"); await pg.wait_for_timeout(600)
        await pg.evaluate("document.getElementById('npPrevBtn').click()"); await pg.wait_for_timeout(800)
        st = await q()
        check(st['cur'] == 'Song 1' and st['idx'] == 1, f'Previous twice reaches the song in the playlist {st}')
        await pg.evaluate("document.getElementById('npPrevBtn').click()"); await pg.wait_for_timeout(600)
        st = await q()
        check(st['cur'] == 'Radio A' and st['idx'] == 0, f'and on back to Radio A {st}')
        s = await steps()
        check(not s['prev']['on'] and s['next']['on'], f'at the start Previous is off {s}')
        # the player bar's buttons step too
        await pg.evaluate("document.getElementById('npBackBtn') && document.getElementById('npBackBtn').click()")
        await pg.evaluate("document.getElementById('barNextBtn').click()"); await pg.wait_for_timeout(800)
        check((await q())['cur'] == 'Song 1', 'the player bar Next steps too')

        # ---- Now Playing's "More from <playlist>": tapping one plays through the whole playlist ----
        await pg.evaluate("__t.openPl('pl_mix')"); await pg.wait_for_timeout(500)
        await pg.evaluate(CLICK, 'Radio A'); await pg.wait_for_timeout(500)
        await pg.evaluate('__t.openNp()'); await pg.wait_for_timeout(700)
        more = await pg.evaluate("Array.from(document.querySelectorAll('#npCollectionGrid .tile-name, #npCollectionGrid .song-row-title')).map(function(e){ return e.textContent; })")
        check(more == ['Song 1', 'Radio B', 'Radio C'], f'"More from Mix" lists the rest {more}')
        await pg.evaluate("Array.from(document.querySelectorAll('#npCollectionGrid .tile')).filter(function(t){ return /Radio B/.test(t.textContent); })[0].click()")
        await pg.wait_for_timeout(700)
        st = await q()
        check(st['list'] == ['Radio A', 'Song 1', 'Radio B', 'Radio C'] and st['cur'] == 'Radio B' and st['idx'] == 2, f'tapping in "More from" plays through the whole playlist {st}')

        # ---- Favorites page ----
        await pg.evaluate('__t.openFavs()'); await pg.wait_for_timeout(600)
        await pg.evaluate(CLICK, 'Fav Two'); await pg.wait_for_timeout(600)
        st = await q()
        check(st['list'] == ['Fav One', 'Fav Two', 'Song 2', 'Fav Three'] and st['idx'] == 1, f'Favorites is the queue {st}')
        await pg.evaluate("document.getElementById('barNextBtn').click()"); await pg.wait_for_timeout(800)
        check((await q())['cur'] == 'Song 2', 'Next from Fav Two plays the favourite song after it')

        # ---- artist page: "Featuring" (the case in Mark's screenshot) ----
        await pg.evaluate("__t.openArtist('Ann')"); await pg.wait_for_timeout(900)
        secs = await pg.evaluate("Array.from(document.querySelectorAll('#stationsGrid .grid-section-label')).map(function(e){ return e.firstChild.textContent; })")
        await pg.evaluate(CLICK, 'Ann'); await pg.wait_for_timeout(600)  # shown without "Exclusively"
        st = await q()
        check(st['list'] == ['Ann Hits', 'Exclusively Ann', 'Ann Live'] and st['idx'] == 1 and st['label'] == 'Featuring Ann',
              f'tapping the artist\'s station under Featuring queues Featuring {secs} {st}')
        await pg.evaluate('__t.openNp()'); await pg.wait_for_timeout(700)
        await pg.screenshot(path=f'{shots}/skip-np-featuring.png')
        await pg.evaluate("document.getElementById('npNextBtn').click()"); await pg.wait_for_timeout(700)
        check((await q())['cur'] == 'Ann Live', 'Next goes to the next station under Featuring')
        await pg.evaluate("document.getElementById('npBackBtn') && document.getElementById('npBackBtn').click()")

        # ---- the artist page's Play button: Featuring (or their stations) becomes the queue ----
        # (something else playing first; with one of theirs playing, Play is Pause)
        await pg.evaluate("__t.openPl('pl_mix')"); await pg.wait_for_timeout(500)
        await pg.evaluate(CLICK, 'Radio C'); await pg.wait_for_timeout(500)
        await pg.evaluate("__t.openArtist('Ann')"); await pg.wait_for_timeout(900)
        await pg.evaluate("document.getElementById('artistPlayBtn').click()"); await pg.wait_for_timeout(700)
        st = await q()
        check(st['cur'] == 'Ann Hits' and st['list'] == ['Ann Hits', 'Exclusively Ann', 'Ann Live'] and st['idx'] == 0,
              f'Play on the artist page plays the Featuring list from the top {st}')
        check(await pg.evaluate("document.getElementById('artistPlayBtn').dataset.state") == 'pause', 'the Play pill turns into Pause for a Featuring entry')
        await pg.evaluate('__t.openNp()'); await pg.wait_for_timeout(700)
        s = await steps()
        check(s['prev']['shown'] and s['next']['shown'] and not s['prev']['on'] and s['next']['on'], f'skip buttons shown after Play {s}')
        await pg.evaluate("document.getElementById('npNextBtn').click()"); await pg.wait_for_timeout(600)
        await pg.evaluate("document.getElementById('npNextBtn').click()"); await pg.wait_for_timeout(600)
        st = await q()
        check(st['cur'] == 'Ann Live' and st['idx'] == 2, f'Next twice reaches every entry, to the last {st}')
        await pg.evaluate("document.getElementById('npBackBtn') && document.getElementById('npBackBtn').click()")
        await pg.evaluate("__t.openArtist('Bob')"); await pg.wait_for_timeout(900)
        await pg.evaluate("document.getElementById('artistPlayBtn').click()"); await pg.wait_for_timeout(700)
        st = await q()
        check(st['cur'] == 'Exclusively Bob' and len(st['list']) == 2 and st['idx'] == 0, f'Play with two stations queues both {st}')
        await pg.evaluate("document.getElementById('barNextBtn').click()"); await pg.wait_for_timeout(700)
        check((await q())['idx'] == 1, 'Next goes to their other station')
        await pg.evaluate("__t.openArtist('Ann')"); await pg.wait_for_timeout(900)

        # ---- library browsing keeps the library order for songs ----
        await pg.evaluate('__t.songs()'); await pg.wait_for_timeout(700)
        await pg.evaluate("""Array.from(document.querySelectorAll('#stationsGrid .song-row')).filter(function(e){ return /Song 2/.test(e.textContent); })[0].click()""")
        await pg.wait_for_timeout(700)
        st = await q()
        check(st['label'] == 'Library' and st['cur'] == 'Song 2', f'a song from the Songs list still plays through the library {st}')
        check(not errs, f'no page errors {errs[:3]}')
        await b.close()
    print('ALL PASSED' if not fails else f'FAILED {fails}')

asyncio.run(main())
