"""Artist and album pages slide in from the right on phones when opened (tapping a tile),
using only a transform; Back, and the system's Remove animations setting, open them in place.
Run: python3 tests/test_page_slide.py (screenshots in /tmp/claude-0/t/shots)"""
import asyncio, os, json, threading, http.server, functools, shutil, subprocess
from playwright.async_api import async_playwright

PORT = 8797
root = '/tmp/claude-0/t/srv_slide'
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
        " artists: function(){ runLibrarySection('artists'); },"
        " status: function(){ var e = document.getElementById('statusLine') || document.querySelector('.status-line'); return e ? e.textContent : ''; } };\n")
_src = open(os.path.join(os.path.dirname(__file__), '..', 'www', 'index.html')).read()
_mark = '  var coverFlow = null;\n'
assert _src.count(_mark) == 1
open(root + '/index.html', 'w').write(_src.replace(_mark, _mark + HOOK))

M = root + '/Music'
os.makedirs(M, exist_ok=True)
SONGS = [('Kay 1', 'Kay', 'Big Album', 1), ('Kay 2', 'Kay', 'Big Album', 2), ('Kay 3', 'Kay', 'Second', 1), ('Lone', 'Lee', 'Other', 1)]
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

# Samples the browse view's horizontal offset every frame for ms after running js.
SAMPLE = """([js, ms]) => new Promise(function(res){ var bv = document.getElementById('browseView'), out = [], t0 = performance.now();
  eval(js);
  (function f(now){ var m = new DOMMatrix(getComputedStyle(bv).transform); out.push([Math.round(now - t0), Math.round(m.m41)]);
    if(now - t0 < ms) requestAnimationFrame(f); else res(out); })(performance.now()); })"""


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
        await pg.evaluate("__t.artists()"); await pg.wait_for_timeout(600)

        # tap Kay on the Artists list
        tap_artist = "Array.from(document.querySelectorAll('#stationsGrid .tile')).filter(function(t){ return /Kay/.test(t.textContent); })[0].click()"
        fr = await pg.evaluate(SAMPLE, [tap_artist, 700])
        print(fr)
        xs = [x for _, x in fr]
        check(await pg.evaluate("document.body.classList.contains('artist-open')"), 'the artist page opened')
        left = await pg.evaluate("document.getElementById('browseView').getBoundingClientRect().left")
        check(left + xs[0] >= 390, f'it starts fully off the right edge (column left {left} + {xs[0]}px)')
        check(any(40 < x < 300 for x in xs), 'and passes through in-between positions (it slides, not jumps)')
        check(all(xs[i + 1] <= xs[i] for i in range(len(xs) - 1)), 'moving steadily left, never back')
        check(xs[-1] == 0, f'it lands in place ({xs[-1]})')
        lands = next(t for t, x in fr if x == 0)
        check(250 <= lands <= 520, f'in about a third of a second ({lands}ms)')
        check(not await pg.evaluate("document.body.classList.contains('page-sliding')"), 'the slide clean-up ran')
        # a frame mid-slide
        await pg.evaluate("__t.artists()"); await pg.wait_for_timeout(500)
        await pg.evaluate(tap_artist); await pg.wait_for_timeout(110)
        await pg.screenshot(path=f'{shots}/slide-mid.png'); await pg.wait_for_timeout(600)
        await pg.screenshot(path=f'{shots}/slide-artist.png')
        overflow = await pg.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
        check(overflow, 'the page never scrolls sideways')

        # tap an album on the artist page
        tap_album = "Array.from(document.querySelectorAll('.tile')).filter(function(t){ return /Big Album/.test(t.textContent) && t.offsetParent; })[0].click()"
        fr2 = await pg.evaluate(SAMPLE, [tap_album, 600])
        xs2 = [x for _, x in fr2]
        check(await pg.evaluate("document.body.classList.contains('album-open')"), 'the album page opened')
        check(xs2[0] >= 300 and any(40 < x < 300 for x in xs2) and xs2[-1] == 0, f'the album page slides in too {xs2[:4]}...{xs2[-2:]}')
        await pg.screenshot(path=f'{shots}/slide-album.png')

        # Back: no slide
        fr3 = await pg.evaluate(SAMPLE, ["document.getElementById('detailBackBtn').click()", 300])
        check(await pg.evaluate("document.body.classList.contains('artist-open') && !document.body.classList.contains('album-open')"), 'Back returns to the artist page')
        check(all(x == 0 for _, x in fr3), f'Back does not slide {[x for _, x in fr3][:5]}')

        # opened from Now Playing etc. by code: same slide (it is the open itself that slides)
        fr4 = await pg.evaluate(SAMPLE, ["__t.openAlbum('Other')", 500])
        check(fr4[0][1] >= 300 and fr4[-1][1] == 0, 'an album opened from anywhere else slides in too')

        # Remove animations
        await pg.emulate_media(reduced_motion='reduce')
        fr5 = await pg.evaluate(SAMPLE, ["__t.openAlbum('Second')", 300])
        check(all(x == 0 for _, x in fr5), 'with Remove animations on, pages open in place')
        await pg.emulate_media(reduced_motion='no-preference')

        # desktop width: in place
        await pg.set_viewport_size({'width': 1280, 'height': 800}); await pg.wait_for_timeout(400)
        fr6 = await pg.evaluate(SAMPLE, ["__t.openAlbum('Big Album')", 300])
        check(all(x == 0 for _, x in fr6), 'on a wide screen, pages open in place')
        check(not errs, f'no page errors {errs[:3]}')
        await b.close()
    print('ALL PASSED' if not fails else f'FAILED {fails}')

asyncio.run(main())
