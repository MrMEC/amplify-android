"""Nothing ever points at music that has left the library: after a refresh finds songs gone,
their artist (if nothing else of theirs is left) leaves Top Artists and its play count, and the
songs, artist and album leave Favorites, Continue Listening and playlists. An artist or album
page whose subject is gone steps back instead of showing "no longer in your library".
Run: python3 tests/test_stale_refs.py (screenshots in /tmp/claude-0/t/shots)"""
import asyncio, os, json, threading, http.server, functools, shutil, subprocess
from playwright.async_api import async_playwright

PORT = 8793
root = '/tmp/claude-0/t/srv_stale'
shots = '/tmp/claude-0/t/shots'
os.makedirs(shots, exist_ok=True)
shutil.rmtree(root, ignore_errors=True)
os.makedirs(root)
HOOK = ("window.__t = { tracks: function(){ return libraryTracks.map(function(t){ return t.name; }); },"
        " stations: function(){ artistStations = [{ stationuuid: 'ex-zed', name: 'Exclusively Zed', url: 'http://radio.example/zed', favicon: '', tags: '' }];"
        "   artistStationsFailed = false; artistStationsPromise = Promise.resolve(artistStations); onArtistStationsChanged(); },"
        " seed: function(){ var T = function(n){ return libraryTracks.filter(function(t){ return t.name === n; })[0]; };"
        "   var plays = {}; [['Alpha', 8], ['Bravo', 9], ['Charlie', 7], ['Zed', 6]].forEach(function(a){ plays[artistMatchKey(a[0])] = { name: a[0], count: a[1], last: Date.now() }; });"
        "   saveArtistPlays(plays);"
        "   var bravoAlbum = buildAlbumIndex().filter(function(a){ return a.artist === 'Bravo'; })[0];"
        "   favorites = [T('Bravo 1'), artistFavRecord(findArtistEntry(artistMatchKey('Bravo'))), albumFavRecord(bravoAlbum), T('Alpha 1'), artistFavRecord(findArtistEntry(artistMatchKey('Alpha')))]; saveFavorites();"
        "   recentStations = [T('Bravo 2'), T('Alpha 1'), { stationuuid: 'st-1', name: 'Radio One', url: 'http://radio.example/one', favicon: '' }]; saveRecent();"
        "   stationPlaylists.push({ id: 'pl_x', label: 'Mix', stations: [T('Bravo 1'), T('Charlie 1'), { stationuuid: 'st-1', name: 'Radio One', url: 'http://radio.example/one', favicon: '' }] }); saveStationPlaylists();"
        "   renderFavoritesList(); renderRecentSection(); renderTopArtistsSection(); },"
        " state: function(){ var plays = loadArtistPlays(); return { favs: favorites.map(function(f){ return (f.type || 'x') + ':' + (f.name || ''); }),"
        "   recent: recentStations.map(function(s){ return s.name; }), pl: findStationPlaylistById('pl_x').stations.map(function(s){ return s.name; }),"
        "   plays: Object.keys(plays).sort(), top: topArtistList().map(function(e){ return e.name; }) }; },"
        " openTop: function(){ openHomeSectionPage('topArtists'); }, openArtist: function(n){ openArtistPage(artistMatchKey(n)); },"
        " openAlbum: function(a){ var al = buildAlbumIndex().filter(function(x){ return x.album === a; })[0]; openAlbumPage(al ? al.key : 'gone|' + a, null); },"
        " openAlbumKey: function(k){ openAlbumPage(k, null); },"
        " albumKey: function(a){ var al = buildAlbumIndex().filter(function(x){ return x.album === a; })[0]; return al && al.key; },"
        " view: function(){ return { artist: activeArtistKey, album: activeAlbumKey, home: activeHomeSection, lib: activeLibrarySection,"
        "   heading: document.getElementById('stationsHeading').textContent, text: document.getElementById('stationsGrid').textContent }; },"
        " key: function(n){ return artistMatchKey(n); }, refresh: function(){ refreshMusicLibrary(); } };\n")
_src = open(os.path.join(os.path.dirname(__file__), '..', 'www', 'index.html')).read()
_mark = '  var coverFlow = null;\n'
assert _src.count(_mark) == 1
open(root + '/index.html', 'w').write(_src.replace(_mark, _mark + HOOK))

M = root + '/Music/document'   # laid out like an Android tree URI: <tree>/document/<file>
for artist in ['Alpha', 'Bravo', 'Charlie']:
    os.makedirs(f'{M}/{artist}', exist_ok=True)
    for n in (1, 2):
        subprocess.run(['ffmpeg', '-loglevel', 'error', '-y', '-f', 'lavfi', '-i', f'sine=frequency={200 + n * 100}:duration=2',
                        '-c:a', 'libmp3lame', '-b:a', '32k', '-metadata', f'title={artist} {n}', '-metadata', f'artist={artist}',
                        '-metadata', f'album={artist} Album', '-metadata', f'track={n}', f'{M}/{artist}/{n:02d}.mp3'], check=True)


class Q(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a): pass
    def end_headers(self):
        self.send_header('Cache-Control', 'no-store'); super().end_headers()
H = functools.partial(Q, directory=root)
srv = http.server.ThreadingHTTPServer(('127.0.0.1', PORT), H)
threading.Thread(target=srv.serve_forever, daemon=True).start()


def listing():
    out = []
    for dp, _, fs in os.walk(M):
        for f in sorted(fs):
            p = os.path.join(dp, f); rel = os.path.relpath(p, M)
            out.append({'uri': f'http://127.0.0.1:{PORT}/Music/document/' + rel, 'name': f, 'relPath': 'Music/' + rel, 'type': 'audio/mpeg',
                        'size': os.path.getsize(p), 'lastModified': 1700000000000})
    return out


MOCK = """
(function(){
 var listeners = {};
 var impl = {
   pickMusicFolder: function(){ return Promise.resolve({folder:'Music', treeUri: 'http://127.0.0.1:%d/Music', files: window.__listing, truncated:false}); },
   rescanMusicFolder: function(){ return fetch('/__listing.json', {cache:'no-store'}).then(function(r){ return r.json(); }).then(function(f){ return {folder:'Music', files: f}; }); },
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
""" % PORT

fails = []
def check(cond, msg):
    print(('PASS ' if cond else 'FAIL ') + msg)
    if not cond: fails.append(msg)


async def main():
    open(f'{root}/__listing.json', 'w').write(json.dumps(listing()))
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
        ctx = await b.new_context(viewport={'width': 390, 'height': 844}, device_scale_factor=2, is_mobile=True, has_touch=True, color_scheme='dark')
        await ctx.add_init_script(MOCK)
        await ctx.add_init_script('window.__listing = %s;' % json.dumps(listing()))
        pg = await ctx.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.route('**/*', lambda route: route.continue_() if '127.0.0.1' in route.request.url else route.abort())
        await pg.goto(f'http://127.0.0.1:{PORT}/index.html'); await pg.wait_for_timeout(2500)
        await pg.evaluate("""(function(){ var ov=document.getElementById('addMusicOverlay'); if(ov) ov.classList.add('open');
          var btn=document.getElementById('addMusicFolderBtn'); btn.disabled=false; btn.click(); })()""")
        for _ in range(60):
            await pg.wait_for_timeout(500)
            if len(await pg.evaluate('__t.tracks()')) >= 6: break
        await pg.evaluate('__t.stations()'); await pg.wait_for_timeout(300)
        await pg.evaluate('__t.seed()'); await pg.wait_for_timeout(300)
        st = await pg.evaluate('__t.state()')
        print(st)
        check('Bravo' in st['top'] and 'Zed' in st['top'], f"before: Bravo and Zed in Top Artists {st['top']}")
        bravo_album = await pg.evaluate("__t.albumKey('Bravo Album')")

        # On Bravo's page (opened from Top Artists) when the refresh finds Bravo's songs gone
        await pg.evaluate('__t.openTop()'); await pg.wait_for_timeout(500)
        await pg.evaluate("__t.openArtist('Bravo')"); await pg.wait_for_timeout(600)
        check((await pg.evaluate('__t.view()'))['artist'] == await pg.evaluate("__t.key('Bravo')"), 'on Bravo\'s page')
        shutil.rmtree(f'{M}/Bravo')
        open(f'{root}/__listing.json', 'w').write(json.dumps(listing()))
        await pg.evaluate('__t.refresh()'); await pg.wait_for_timeout(3000)
        check(sorted(await pg.evaluate('__t.tracks()')) == ['Alpha 1', 'Alpha 2', 'Charlie 1', 'Charlie 2'], 'refresh removed Bravo\'s songs')
        v = await pg.evaluate('__t.view()')
        check(v['home'] == 'topArtists' and not v['artist'] and 'no longer' not in v['text'], f'Bravo\'s page stepped back to Top Artists {v["home"]} {v["heading"]!r}')
        check('Bravo' not in v['text'] and 'Alpha' in v['text'] and 'Zed' in v['text'], f'Top Artists page has no Bravo ({v["text"][:120]})')
        await pg.screenshot(path=f'{shots}/stale-top-artists.png')
        st = await pg.evaluate('__t.state()')
        print(st)
        bk, ak, ck, zk = [await pg.evaluate(f"__t.key('{n}')") for n in ('Bravo', 'Alpha', 'Charlie', 'Zed')]
        check(bk not in st['plays'] and {ak, ck, zk} <= set(st['plays']), f"Bravo's play count gone, others (incl. station artist Zed) kept {st['plays']}")
        check(st['top'] == ['Alpha', 'Charlie', 'Zed'], f"Top Artists {st['top']}")
        check(st['favs'] == ['local:Alpha 1', 'artist:Alpha'], f"Favorites lost Bravo's song, artist and album {st['favs']}")
        check(st['recent'] == ['Alpha 1', 'Radio One'], f"Continue Listening lost Bravo {st['recent']}")
        check(st['pl'] == ['Charlie 1', 'Radio One'], f"playlist lost Bravo, kept the rest {st['pl']}")

        # A page for something gone (old link / history) steps back instead of saying so
        await pg.evaluate("__t.openTop()"); await pg.wait_for_timeout(400)
        await pg.evaluate("__t.openArtist('Bravo')"); await pg.wait_for_timeout(600)
        v = await pg.evaluate('__t.view()')
        check(v['home'] == 'topArtists' and 'no longer' not in v['text'], f'opening a gone artist goes back to where it came from ({v["home"]}, {v["heading"]!r})')
        await pg.evaluate("__t.openTop()"); await pg.wait_for_timeout(400)
        await pg.evaluate(f"__t.openAlbumKey({json.dumps(bravo_album)})"); await pg.wait_for_timeout(600)
        v = await pg.evaluate('__t.view()')
        check(not v['album'] and 'no longer' not in v['text'], f'opening a gone album goes back too ({v["home"]}, {v["heading"]!r})')
        # Station-only artist still opens
        await pg.evaluate("__t.openArtist('Zed')"); await pg.wait_for_timeout(600)
        v = await pg.evaluate('__t.view()')
        check(v['artist'] == zk, 'a station-only artist still opens normally')

        # Restart: still gone; nothing pruned before the library is read
        await pg.reload(); await pg.wait_for_timeout(3000)
        await pg.evaluate('__t.stations()'); await pg.wait_for_timeout(500)
        st = await pg.evaluate('__t.state()')
        check(st['top'] == ['Alpha', 'Charlie', 'Zed'] and st['favs'] == ['local:Alpha 1', 'artist:Alpha'], f'after a restart {st}')
        check(not errs, f'no page errors {errs[:3]}')
        await b.close()
    print('ALL PASSED' if not fails else f'FAILED {fails}')

asyncio.run(main())
