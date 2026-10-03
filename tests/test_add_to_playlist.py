"""Adding albums and songs to playlists: an album page's menu has Add to Playlist (the whole
album, in track order), and every song row's More menu has it too (one song). The picker ticks
playlists that already hold everything, + New Playlist makes one and adds to it, and nothing is
added twice.
Run: python3 tests/test_add_to_playlist.py (screenshots in /tmp/claude-0/t/shots)"""
import asyncio, os, json, threading, http.server, functools, shutil, subprocess
from playwright.async_api import async_playwright

PORT = 8795
root = '/tmp/claude-0/t/srv_addpl'
shots = '/tmp/claude-0/t/shots'
os.makedirs(shots, exist_ok=True)
shutil.rmtree(root, ignore_errors=True)
os.makedirs(root)
HOOK = ("window.__t = { tracks: function(){ return libraryTracks.map(function(t){ return t.name; }); },"
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
SONGS = [('Kay 1', 'Kay', 'Big Album', 1), ('Kay 3', 'Kay', 'Big Album', 3), ('Kay 2', 'Kay', 'Big Album', 2), ('Lone', 'Lee', 'Other', 1)]
for i, (t, a, al, n) in enumerate(SONGS):
    subprocess.run(['ffmpeg', '-loglevel', 'error', '-y', '-f', 'lavfi', '-i', f'sine=frequency={300 + i * 60}:duration=3',
                    '-c:a', 'libmp3lame', '-b:a', '32k', '-metadata', f'title={t}', '-metadata', f'artist={a}',
                    '-metadata', f'album={al}', '-metadata', f'track={n}', f'{M}/{i + 1:02d}.mp3'], check=True)


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

PICKER = """Array.from(document.querySelectorAll('#addToPlaylistList .custom-search-item')).map(function(r){
  return r.querySelector('.cs-label').textContent + (r.querySelector('.fa-check') ? ' ✓' : ''); })"""


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
            if len(await pg.evaluate('__t.tracks()')) >= 4: break
        await pg.evaluate('__t.mk()')

        # ---- the album page menu: Add to Playlist adds the whole album in track order ----
        await pg.evaluate("__t.openAlbum('Big Album')"); await pg.wait_for_timeout(800)
        await pg.evaluate("document.getElementById('albumMenuBtn').click()"); await pg.wait_for_timeout(300)
        items = await pg.evaluate("Array.from(document.querySelectorAll('#albumMenu .np-menu-item')).filter(function(e){ return getComputedStyle(e).display !== 'none'; }).map(function(e){ return e.textContent.trim(); })")
        check('Add to Playlist' in items, f'album menu has Add to Playlist {items}')
        await pg.screenshot(path=f'{shots}/addpl-album-menu.png')
        await pg.evaluate("document.getElementById('albumAddPlaylistBtn').click()"); await pg.wait_for_timeout(400)
        check(await pg.evaluate("document.getElementById('addToPlaylistOverlay').classList.contains('open')"), 'the playlist picker opens')
        check(await pg.evaluate(PICKER) == ['Mix', 'Empty'], f'picker lists the playlists {await pg.evaluate(PICKER)}')
        await pg.screenshot(path=f'{shots}/addpl-picker.png')
        await pg.evaluate("Array.from(document.querySelectorAll('#addToPlaylistList .custom-search-item')).filter(function(r){ return /Mix/.test(r.textContent); })[0].click()")
        await pg.wait_for_timeout(400)
        mix = await pg.evaluate("__t.stored('Mix')")
        check(mix == ['Radio One', 'Kay 1', 'Kay 2', 'Kay 3'], f'album added after what was there, in track order {mix}')
        st = await pg.evaluate('__t.status()')
        check('Big Album' in st and 'Mix' in st, f'says what was added where ({st})')
        # again: ticked, and nothing doubled
        await pg.evaluate("document.getElementById('albumMenuBtn').click()"); await pg.wait_for_timeout(200)
        await pg.evaluate("document.getElementById('albumAddPlaylistBtn').click()"); await pg.wait_for_timeout(300)
        check(await pg.evaluate(PICKER) == ['Mix ✓', 'Empty'], f'Mix is ticked now {await pg.evaluate(PICKER)}')
        await pg.evaluate("Array.from(document.querySelectorAll('#addToPlaylistList .custom-search-item'))[0].click()"); await pg.wait_for_timeout(300)
        check(await pg.evaluate("__t.pl('Mix')") == ['Radio One', 'Kay 1', 'Kay 2', 'Kay 3'], 'adding again adds nothing twice')
        check('already' in await pg.evaluate('__t.status()'), 'and says it was already there')

        # ---- a song row on the album page: More > Add to Playlist adds just that song ----
        await pg.evaluate("""Array.from(document.querySelectorAll('#stationsGrid .song-row')).filter(function(r){ return /Kay 2/.test(r.textContent); })[0].querySelector('.row-more-btn').click()""")
        await pg.wait_for_timeout(300)
        rm = await pg.evaluate("Array.from(document.querySelectorAll('#rowMenu .np-menu-item')).filter(function(e){ return getComputedStyle(e).display !== 'none'; }).map(function(e){ return e.textContent.trim(); })")
        check('Add to Playlist' in rm, f"a song's More menu has Add to Playlist {rm}")
        await pg.screenshot(path=f'{shots}/addpl-row-menu.png')
        await pg.evaluate("document.getElementById('rowMenuAddPlaylist').click()"); await pg.wait_for_timeout(300)
        check(await pg.evaluate(PICKER) == ['Mix ✓', 'Empty'], 'picker ticks Mix, which already holds the song')
        await pg.evaluate("Array.from(document.querySelectorAll('#addToPlaylistList .custom-search-item')).filter(function(r){ return /Empty/.test(r.textContent); })[0].click()")
        await pg.wait_for_timeout(300)
        check(await pg.evaluate("__t.stored('Empty')") == ['Kay 2'], 'one song added to Empty')

        # ---- + New Playlist from the picker creates it with the song in it ----
        await pg.evaluate("""Array.from(document.querySelectorAll('#stationsGrid .song-row')).filter(function(r){ return /Kay 3/.test(r.textContent); })[0].querySelector('.row-more-btn').click()""")
        await pg.wait_for_timeout(200)
        await pg.evaluate("document.getElementById('rowMenuAddPlaylist').click()"); await pg.wait_for_timeout(300)
        await pg.evaluate("document.getElementById('addToPlaylistNewBtn').click()"); await pg.wait_for_timeout(300)
        await pg.fill('#playlistNameInput', 'Fresh')
        await pg.evaluate("document.getElementById('playlistSaveBtn').click()"); await pg.wait_for_timeout(400)
        fresh = await pg.evaluate("__t.stored('Fresh')")
        check(fresh == ['Kay 3'], f'new playlist made with the song {fresh}')
        check(await pg.evaluate("document.querySelector('#stationsGrid .song-row') !== null"), 'still on the album page')
        check(not errs, f'no page errors {errs[:3]}')
        await b.close()
    print('ALL PASSED' if not fails else f'FAILED {fails}')

asyncio.run(main())
