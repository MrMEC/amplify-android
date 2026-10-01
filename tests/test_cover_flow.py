"""Cover Flow on the landscape Albums page: layout in 3D with reflections, drag + fling with a
spring settle, taps on side covers and the edges, the tracklist flip, the caption crossfade, the
recycled pool, opening on the playing album, and opening straight from My Library > Albums on
rotate. Builds its own library of 30 albums (ffmpeg).
Run: python3 tests/test_cover_flow.py (screenshots in /tmp/claude-0/t/shots)"""
import asyncio, os, json, threading, http.server, functools, shutil, subprocess, colorsys
from playwright.async_api import async_playwright

PORT = 8788
root = '/tmp/claude-0/t/srv_cf'
shots = '/tmp/claude-0/t/shots'
os.makedirs(shots, exist_ok=True)
shutil.rmtree(root, ignore_errors=True)
os.makedirs(root)
HOOK = ("window.__t = { cf: function(){ return coverFlow; }, runLibrarySection: runLibrarySection,"
        " tracks: function(){ return libraryTracks; }, cur: function(){ return currentStation && currentStation.name; } };\n")
_src = open(os.path.join(os.path.dirname(__file__), '..', 'www', 'index.html')).read()
_mark = '  var coverFlow = null;\n'
assert _src.count(_mark) == 1
open(root + '/index.html', 'w').write(_src.replace(_mark, _mark + HOOK))

N = 30
M = root + '/Music'
tone = f'{root}/tone.mp3'
subprocess.run(['ffmpeg', '-loglevel', 'error', '-y', '-f', 'lavfi', '-i', 'sine=frequency=440:duration=2',
                '-c:a', 'libmp3lame', '-b:a', '48k', tone], check=True)
for i in range(N):
    r, g, b = colorsys.hsv_to_rgb(i / N, .65, .85)
    col = '0x%02x%02x%02x' % (int(r * 255), int(g * 255), int(b * 255))
    art = f'{root}/c{i}.png'
    subprocess.run(['ffmpeg', '-loglevel', 'error', '-y', '-f', 'lavfi', '-i', f'color=c={col}:s=600x600',
                    '-vf', f"drawtext=text='{i:02d}':fontcolor=white:fontsize=260:x=(w-tw)/2:y=(h-th)/2",
                    '-frames:v', '1', art], check=True)
    name = f'Album {i:02d}'
    for t in range(4 if i == 0 else 2):
        p = f'{M}/{name}/{t + 1:02d}.mp3'
        os.makedirs(os.path.dirname(p), exist_ok=True)
        # No art on track 2 of odd albums: it borrows the album's cover.
        with_art = not (i % 2 and t == 1)
        cmd = ['ffmpeg', '-loglevel', 'error', '-y', '-i', tone]
        if with_art:
            cmd += ['-i', art, '-map', '0:a', '-map', '1:v', '-c:v', 'png', '-disposition:v', 'attached_pic']
        cmd += ['-c:a', 'copy', '-id3v2_version', '3', '-metadata', f'title=Song {t + 1} of {i:02d}',
                '-metadata', f'artist=Artist {i:02d}', '-metadata', f'album={name}', '-metadata', f'track={t + 1}', p]
        subprocess.run(cmd, check=True)

H = functools.partial(http.server.SimpleHTTPRequestHandler, directory=root)
H.log_message = lambda *a: None
srv = http.server.ThreadingHTTPServer(('127.0.0.1', PORT), H)
threading.Thread(target=srv.serve_forever, daemon=True).start()
files = []
for dp, _, fs in os.walk(M):
    for f in sorted(fs):
        p = os.path.join(dp, f); rel = os.path.relpath(p, root)
        files.append({'uri': f'http://127.0.0.1:{PORT}/' + rel.replace(' ', '%20'), 'name': f, 'relPath': rel,
                      'type': 'audio/mpeg', 'size': os.path.getsize(p), 'lastModified': 1700000000000})
MOCK = """
(function(){
 var picked = %s;
 window.__loads = [];
 var listeners = {};
 function proxy(){ return new Proxy({}, {get:function(t,k){
   if(k==='then') return undefined;
   if(k==='pickMusicFolder') return function(){ return Promise.resolve({folder:'Music', files:picked, truncated:false}); };
   if(k==='setCarLibraryPart') return undefined;
   if(k==='load') return function(o){ window.__loads.push(o); setTimeout(function(){ (listeners.state||[]).forEach(function(f){ f({state:'playing', playing:true}); }); }, 50); return Promise.resolve({}); };
   if(k==='addListener') return function(n, f){ (listeners[n] = listeners[n] || []).push(f); return Promise.resolve({remove:function(){}}); };
   return function(){ return Promise.resolve({}); };
 }}); }
 var P = proxy();
 window.Capacitor = { isNativePlatform:function(){return true;}, getPlatform:function(){return 'android';},
   registerPlugin:function(){ return P; }, Plugins:{AmplifyPlayer:P}, convertFileSrc:function(u){return u;} };
})();
""" % json.dumps(files)

fails = []
def check(cond, msg):
    print(('PASS ' if cond else 'FAIL ') + msg)
    if not cond:
        fails.append(msg)

ST = "__t.cf()._state()"
COVERS = """(function(){ return Array.from(document.querySelectorAll('#npLandAlbums .cf-cover')).map(function(e){
  var m = new DOMMatrix(getComputedStyle(e).transform); var r = e.getBoundingClientRect();
  var rot = Math.round(Math.atan2(-m.m13, m.m11) * 180 / Math.PI);
  return { i:+e.dataset.i, rot:rot, z:Math.round(m.m43), x:Math.round(m.m41), l:Math.round(r.left), w:Math.round(r.width), t:Math.round(r.top), b:Math.round(r.bottom),
           zi:+e.style.zIndex, shade:+e.querySelector('.cf-shade').style.opacity, img:!!e.querySelector('img') }; }).sort(function(a,b){return a.i-b.i;}); })()"""


async def settle(pg, ms=1200):
    await pg.wait_for_timeout(ms)


async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
        ctx = await b.new_context(viewport={'width': 390, 'height': 844}, device_scale_factor=2, is_mobile=True, has_touch=True, color_scheme='dark')
        await ctx.add_init_script(MOCK)
        pg = await ctx.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.goto(f'http://127.0.0.1:{PORT}/index.html'); await pg.wait_for_timeout(2500)
        await pg.evaluate("""(function(){ var ov=document.getElementById('addMusicOverlay'); if(ov) ov.classList.add('open');
          var btn=document.getElementById('addMusicFolderBtn'); btn.disabled=false; btn.click(); })()""")
        for _ in range(120):
            await pg.wait_for_timeout(500)
            if await pg.evaluate('__t.tracks().length') >= len(files):
                break
        check(await pg.evaluate('__t.tracks().length') == len(files), f'library imported ({len(files)} songs)')
        await pg.wait_for_timeout(1500)

        # --- From My Library > Albums, turning the phone opens Cover Flow on the album in view.
        await pg.evaluate("__t.runLibrarySection('albums')"); await pg.wait_for_timeout(800)
        await pg.evaluate("""(function(){ var t=document.querySelectorAll(".tile[data-entity='album']")[12]; window.scrollTo(0, t.getBoundingClientRect().top + scrollY - 80); })()""")
        await pg.wait_for_timeout(400)
        in_view = await pg.evaluate("""(function(){ var ts=document.querySelectorAll(".tile[data-entity='album']");
          for(var i=0;i<ts.length;i++){ var r=ts[i].getBoundingClientRect(); if(r.bottom>60) return ts[i].querySelector('.tile-name').textContent; } })()""")
        await pg.set_viewport_size({'width': 844, 'height': 390}); await pg.wait_for_timeout(1500)
        open_ = await pg.evaluate("document.getElementById('nowPlayingScreen').classList.contains('la-open')")
        st = await pg.evaluate(ST)
        check(open_ and st['center'] == in_view, f'rotating on Albums opens Cover Flow on the album in view ({in_view} / {st["center"]})')
        await pg.screenshot(path=f'{shots}/cf-from-library.png')
        await pg.set_viewport_size({'width': 390, 'height': 844}); await pg.wait_for_timeout(900)
        back = await pg.evaluate("[document.body.classList.contains('np-open'), document.querySelectorAll(\".tile[data-entity='album']\").length]")
        check(not back[0] and back[1] == N, f'turning back returns to the Albums list {back}')

        # --- From landscape Now Playing: play a song from Album 05, open Albums.
        await pg.evaluate("""(function(){ var t=__t.tracks().filter(function(x){return x.album==='Album 05';})[0];
           document.querySelectorAll('.tile')[0]; })()""")
        await pg.evaluate("__t.runLibrarySection('songs')"); await pg.wait_for_timeout(600)
        await pg.evaluate("""Array.prototype.find.call(document.querySelectorAll('.song-row'), function(r){ return /Song 1 of 05/.test(r.textContent); }).click()""")
        await pg.wait_for_timeout(800)
        await pg.set_viewport_size({'width': 844, 'height': 390}); await pg.wait_for_timeout(1000)
        await pg.evaluate("document.getElementById('npLandAlbumsBtn').click()"); await settle(pg)
        st = await pg.evaluate(ST)
        check(st['center'] == 'Album 05', f'opens on the playing album ({st["center"]})')
        check(st['live'] < st['n'], f'only nearby covers exist ({st["live"]} of {st["n"]})')
        await pg.wait_for_timeout(1200)
        cv = await pg.evaluate(COVERS)
        c = [x for x in cv if x['i'] == 5][0]
        left = [x for x in cv if x['i'] < 5]; right = [x for x in cv if x['i'] > 5]
        check(c['rot'] == 0 and c['z'] == 0 and c['shade'] == 0, f'centre faces forward, full size, undimmed {c}')
        check(all(60 <= x['rot'] <= 70 for x in left) and all(-70 <= x['rot'] <= -60 for x in right), f'sides turned in ({[x["rot"] for x in left]}, {[x["rot"] for x in right]})')
        check(all(x['z'] < 0 for x in left + right), 'sides pushed back')
        gaps = [right[k + 1]['x'] - right[k]['x'] for k in range(len(right) - 1)]
        check(len(set(gaps)) <= 2 and gaps and gaps[0] > 0, f'sides evenly stacked {gaps}')
        sh = [x['shade'] for x in right]
        check(all(sh[k] <= sh[k + 1] for k in range(len(sh) - 1)) and sh[0] > 0, f'darker further out {sh}')
        check(c['zi'] > max(x['zi'] for x in left + right), 'centre on top')
        refl = await pg.evaluate("getComputedStyle(document.querySelector('#npLandAlbums .cf-face')).webkitBoxReflect")
        check(refl.startswith('below 1px'), f'reflection 1px below ({refl[:40]})')
        cap = await pg.evaluate("Array.from(document.querySelectorAll('.cf-cap.on')).map(function(e){return e.innerText;})")
        check(cap == ['Album 05\nArtist 05'], f'caption names the centre album {cap}')
        capbox = await pg.evaluate("document.querySelector('.cf-cap.on').getBoundingClientRect().top")
        check(capbox > c['b'] + c['w'] * 0.2, f'caption under the reflection ({capbox} vs cover bottom {c["b"]})')
        check(all(x['img'] for x in cv if abs(x['i'] - 5) <= 3), 'nearby covers have their art')
        await pg.screenshot(path=f'{shots}/cf-open.png')

        # --- Drag left by about two covers, slowly, and let go: settles on a whole album.
        frames = []
        await pg.mouse.move(600, 150); await pg.mouse.down()
        for k in range(1, 25):
            await pg.mouse.move(600 - k * 7, 150); await pg.wait_for_timeout(25)
            if k % 6 == 0: frames.append((await pg.evaluate(ST))['pos'])
        await pg.wait_for_timeout(150)
        await pg.mouse.up()
        check(all(frames[k] < frames[k + 1] for k in range(len(frames) - 1)) and frames[-1] > 5.5, f'covers follow the finger {[round(f, 2) for f in frames]}')
        await pg.screenshot(path=f'{shots}/cf-dragging.png')
        await settle(pg)
        st = await pg.evaluate(ST)
        check(st['pos'] == st['target'] and st['pos'] == int(st['pos']), f'settles exactly on an album ({st["pos"]})')
        slow_end = st['pos']

        # --- A quick fling travels further and glides (in-between frames, no jump).
        await pg.mouse.move(600, 150); await pg.mouse.down()
        for k in range(1, 6):
            await pg.mouse.move(600 - k * 40, 150); await pg.wait_for_timeout(12)
        await pg.mouse.up()
        glide = await pg.evaluate("new Promise(function(res){var o=[];var t0=performance.now();(function f(){o.push(__t.cf()._state().pos);if(performance.now()-t0<700)requestAnimationFrame(f);else res(o);})();})")
        await settle(pg)
        st = await pg.evaluate(ST)
        steps = [abs(glide[k + 1] - glide[k]) for k in range(len(glide) - 1)]
        check(st['pos'] - slow_end >= 4, f'fling carries momentum ({slow_end} -> {st["pos"]})')
        check(max(steps) < 1.2 and len([s for s in steps if s > 0.001]) > 8, f'glides smoothly (largest frame step {max(steps):.2f})')
        check(st['pos'] == int(st['pos']), 'snaps to an album after a fling')

        # --- Dragging past the end bands back.
        await pg.evaluate("__t.cf()._state()")
        await pg.mouse.move(150, 150); await pg.mouse.down()
        for k in range(1, 40):
            await pg.mouse.move(150 + k * 30, 150); await pg.wait_for_timeout(8)
        await pg.mouse.up()
        await settle(pg, 1500)
        await pg.mouse.move(150, 150); await pg.mouse.down()
        for k in range(1, 12):
            await pg.mouse.move(150 + k * 30, 150); await pg.wait_for_timeout(20)
        over = (await pg.evaluate(ST))['pos']
        await pg.mouse.up(); await settle(pg)
        st = await pg.evaluate(ST)
        check(-1.6 < over < 0 and st['pos'] == 0, f'rubber-bands past the first album ({over:.2f} -> {st["pos"]})')

        # --- Tap a side cover: it comes to the centre.
        cv = await pg.evaluate(COVERS)
        r2 = [x for x in cv if x['i'] == 2][0]
        # Only the outer sliver of a side cover is showing; that is where a finger lands on it.
        hx, hy = r2['l'] + r2['w'] - 6, (r2['t'] + r2['b']) // 2
        await pg.mouse.click(hx, hy); await settle(pg)
        check((await pg.evaluate(ST))['pos'] == 2, f'tapping a side cover brings it to the centre ({(await pg.evaluate(ST))["pos"]}, tapped {r2})')
        # --- Edge taps step one at a time.
        await pg.mouse.click(835, 120); await settle(pg, 300)
        await pg.mouse.click(835, 120); await settle(pg)
        check((await pg.evaluate(ST))['pos'] == 4, 'right edge taps step forward')
        await pg.mouse.click(8, 120); await settle(pg)
        check((await pg.evaluate(ST))['pos'] == 3, 'left edge tap steps back')

        # --- Caption crossfades when the centre changes.
        await pg.evaluate("__t.cf()._state()")
        fade = await pg.evaluate("""new Promise(function(res){ var o=[]; var t0=performance.now();
          document.querySelector('.cf').dispatchEvent(new KeyboardEvent('keydown',{key:'ArrowRight'}));
          (function f(){ o.push(Array.from(document.querySelectorAll('.cf-cap')).map(function(e){return +getComputedStyle(e).opacity;})); if(performance.now()-t0<450) requestAnimationFrame(f); else res(o); })(); })""")
        mixed = [f for f in fade if 0.05 < f[0] < 0.95 and 0.05 < f[1] < 0.95]
        check(len(mixed) >= 2, f'caption crossfades ({len(mixed)} mixed frames)')
        await settle(pg)

        # --- Tap the centre: the tracklist turns over; tap a song to play it.
        await pg.evaluate("__t.cf()")
        await pg.mouse.click(422, 120); await pg.wait_for_timeout(700)
        st = await pg.evaluate(ST)
        panel = await pg.evaluate("(function(){var p=document.querySelector('.cf-panel');var r=p.getBoundingClientRect();return {open:p.classList.contains('open'),w:Math.round(r.width),h:Math.round(r.height),title:p.querySelector('.cf-panel-title').textContent,rows:p.querySelectorAll('.cf-track').length,first:p.querySelector('.cf-track').innerText};})()")
        check(st['flipped'] == 4 and panel['open'] and panel['title'] == 'Album 04' and panel['rows'] == 2, f'centre tap shows the tracklist {panel}')
        await pg.screenshot(path=f'{shots}/cf-tracklist.png')
        await pg.evaluate("document.querySelectorAll('.cf-track')[1].click()"); await pg.wait_for_timeout(800)
        loads = await pg.evaluate("window.__loads.length")
        playing = await pg.evaluate("Array.from(document.querySelectorAll('.cf-track')).map(function(b){return b.classList.contains('playing');})")
        np = await pg.evaluate("document.getElementById('npName').textContent")
        check(playing == [False, True] and 'Song 2 of 04' in np, f'tapping a song plays it and marks it ({np!r}, {playing})')
        await pg.screenshot(path=f'{shots}/cf-tracklist-playing.png')
        await pg.evaluate("document.querySelector('.cf-panel-head').click()"); await pg.wait_for_timeout(700)
        st = await pg.evaluate(ST)
        vis = await pg.evaluate("getComputedStyle(document.querySelector('.cf-cover.cf-center')).visibility")
        check(st['flipped'] is None and vis == 'visible', 'tapping the header turns it back')

        # --- Favourites row open: Cover Flow shrinks to fit above it (none here, so check sizing on resize).
        s_before = (await pg.evaluate(ST))['S']
        await pg.set_viewport_size({'width': 800, 'height': 360}); await pg.wait_for_timeout(600)
        s_after = (await pg.evaluate(ST))['S']
        check(s_after < s_before, f'resizes with the screen ({s_before} -> {s_after})')
        await pg.set_viewport_size({'width': 844, 'height': 390}); await pg.wait_for_timeout(600)

        # --- Many albums, few layers: thumbnails capped, pool bounded while sweeping the whole list.
        for k in range(29):
            await pg.evaluate("document.querySelector('.cf').dispatchEvent(new KeyboardEvent('keydown',{key:'ArrowRight'}))")
            await pg.wait_for_timeout(40)
        await settle(pg, 1500)
        st = await pg.evaluate(ST)
        nodes = await pg.evaluate("document.querySelectorAll('#npLandAlbums .cf-cover').length")
        check(st['pos'] == N - 1 and nodes == st['live'] and nodes <= 16, f'pool stays small at the far end ({nodes} covers, pos {st["pos"]})')
        await pg.screenshot(path=f'{shots}/cf-end.png')

        # --- Back to Now Playing and round again: remembers nothing odd.
        await pg.evaluate("document.getElementById('npLandAlbumsBtn').click()"); await pg.wait_for_timeout(700)
        check(not await pg.evaluate("document.getElementById('nowPlayingScreen').classList.contains('la-open')"), 'Now Playing button closes Cover Flow')
        check(not errs, f'no page errors {errs[:3]}')
        await b.close()
    print('ALL PASSED' if not fails else f'FAILED {fails}')

asyncio.run(main())
