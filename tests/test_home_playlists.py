"""Build 125: a sideways-scrolling Playlists row on Home, right under Latest Podcasts: a cover
per playlist with its item count; tapping one opens it, the heading opens the Playlists page;
it follows changes and hides with no playlists. Run: python3 tests/test_home_playlists.py"""
import asyncio, os, json, threading, http.server, functools, shutil, subprocess
from playwright.async_api import async_playwright

PORT = 8801
root = '/tmp/claude-0/t/srv_homepl'
shots = '/tmp/claude-0/t/shots'
os.makedirs(shots, exist_ok=True)
shutil.rmtree(root, ignore_errors=True)
os.makedirs(root)
HOOK = ("window.__h = { home: function(){ loadTopStations(); }, add: function(n){ for(var i = 0; i < n; i++) stationPlaylists.push({ id: 'pl_x' + i, label: 'Extra ' + i, stations: [] }); saveStationPlaylists(); },"
        " rename: function(id, l){ findStationPlaylistById(id).label = l; saveStationPlaylists(); }, del: function(id){ stationPlaylists = stationPlaylists.filter(function(p){ return p.id !== id; }); saveStationPlaylists(); },"
        " clear: function(){ stationPlaylists = []; saveStationPlaylists(); }, active: function(){ return activeStationPlaylistId; } };"
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
ROW = """(()=>{ var s = document.getElementById('playlistsHomeSection'), g = document.getElementById('playlistsHomeGrid');
  var tiles = Array.from(g.querySelectorAll('.tile'));
  var prev = s.previousElementSibling;
  return { shown: getComputedStyle(s).display !== 'none' && s.getBoundingClientRect().height > 0,
    heading: document.getElementById('playlistsHomeHeading').textContent.trim(),
    names: tiles.map(function(t){ return t.querySelector('.tile-name').textContent; }),
    subs: tiles.map(function(t){ var x = t.querySelector('.tile-sub'); return x ? x.textContent : ''; }),
    tops: tiles.map(function(t){ return Math.round(t.getBoundingClientRect().top); }),
    lefts: tiles.map(function(t){ return Math.round(t.getBoundingClientRect().left); }),
    overflow: getComputedStyle(g).overflowX, scrolls: g.scrollWidth > g.clientWidth + 4,
    inRow: !!(g.parentElement && g.parentElement.classList.contains('home-row')),
    after: prev ? prev.id : null }; })()"""


async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
        ctx = await b.new_context(viewport={'width': 412, 'height': 900}, device_scale_factor=2, is_mobile=True, has_touch=True, color_scheme='dark')
        await ctx.add_init_script(MOCK)
        pg = await ctx.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.route('**/*', lambda route: route.continue_() if '127.0.0.1' in route.request.url else route.abort())
        await pg.goto(f'http://127.0.0.1:{PORT}/index.html'); await pg.wait_for_timeout(2500)
        await pg.evaluate('__h.home()'); await pg.wait_for_timeout(600)
        r = await pg.evaluate(ROW)
        check(not r['shown'], 'no playlists: no Playlists row')
        await pg.evaluate('__t.mk()'); await pg.evaluate('__h.add(4)'); await pg.wait_for_timeout(300)
        await pg.evaluate('__h.home()'); await pg.wait_for_timeout(600)
        r = await pg.evaluate(ROW)
        print(r)
        check(r['shown'] and r['heading'] == 'Playlists', f'Home shows a Playlists row {r["heading"]}')
        check(r['after'] == 'latestPodcastsSection', f'right under Latest Podcasts (after {r["after"]})')
        check(r['names'] == ['Mix', 'Empty', 'Extra 0', 'Extra 1', 'Extra 2', 'Extra 3'], f'every playlist, in the Playlists page order {r["names"]}')
        check(r['subs'][:2] == ['1 item', '0 items'], f'each with how much is in it {r["subs"][:2]}')
        check(r['inRow'] and len(set(r['tops'])) == 1 and r['lefts'] == sorted(r['lefts']) and r['overflow'] in ('auto', 'scroll') and r['scrolls'],
              f'side by side in one row that scrolls sideways {r["tops"]} {r["overflow"]}')
        await pg.evaluate("document.getElementById('playlistsHomeSection').scrollIntoView()"); await pg.wait_for_timeout(300)
        await pg.screenshot(path=f'{shots}/home-playlists.png')
        await pg.evaluate("document.getElementById('playlistsHomeGrid').scrollBy({ left: 400 })"); await pg.wait_for_timeout(800)
        sl = await pg.evaluate("document.getElementById('playlistsHomeGrid').scrollLeft")
        check(sl > 100, f'it scrolls ({sl}px)')
        # open one
        await pg.evaluate("Array.from(document.querySelectorAll('#playlistsHomeGrid .tile')).filter(function(t){ return /Mix/.test(t.textContent); })[0].click()"); await pg.wait_for_timeout(600)
        check(await pg.evaluate('__h.active()') == 'pl_mix', 'a cover opens its playlist')
        check(await pg.evaluate("document.getElementById('detailBackLabel').textContent") == 'Home', 'with Back to Home')
        await pg.evaluate("document.getElementById('detailBackBtn').click()"); await pg.wait_for_timeout(600)
        check((await pg.evaluate(ROW))['shown'], 'Back returns Home')
        # heading opens the Playlists page
        await pg.evaluate("document.getElementById('playlistsHomeHeading').click()"); await pg.wait_for_timeout(600)
        check(await pg.evaluate("document.getElementById('stationsHeading').textContent") == 'Playlists', 'the heading opens the Playlists page')
        # from the Playlists page, a playlist's Back still says Playlists
        await pg.evaluate("Array.from(document.querySelectorAll('#stationsGrid .tile')).filter(function(t){ return /Mix/.test(t.textContent); })[0].click()"); await pg.wait_for_timeout(600)
        check(await pg.evaluate("document.getElementById('detailBackLabel').textContent") == 'Playlists', 'opened from the Playlists page, Back says Playlists')
        await pg.evaluate("document.getElementById('detailBackBtn').click()"); await pg.wait_for_timeout(600)
        check(await pg.evaluate("document.getElementById('stationsHeading').textContent") == 'Playlists', 'and goes back there')
        await pg.evaluate('__h.home()'); await pg.wait_for_timeout(600)
        # follows changes
        await pg.evaluate("__h.rename('pl_mix', 'Road Trip')"); await pg.evaluate("__h.del('pl_empty')"); await pg.wait_for_timeout(200)
        names = (await pg.evaluate(ROW))['names']
        check(names[0] == 'Road Trip' and 'Empty' not in names, f'renaming or deleting a playlist shows straight away {names}')
        await pg.evaluate('__h.clear()'); await pg.wait_for_timeout(200)
        check(not (await pg.evaluate(ROW))['shown'], 'and the row goes when the last playlist does')
        check(not errs, f'no page errors {errs[:3]}')
        await b.close()
    print('ALL PASSED' if not fails else f'FAILED {fails}')

asyncio.run(main())
