"""Playlists: a playlist opened from the Playlists page lists its entries as stacked rows
(songs as song rows, stations as station rows), and Edit lets you remove entries and drag them
into a new order (with a finger or a mouse), which is saved.
Run: python3 tests/test_playlists.py (screenshots in /tmp/claude-0/t/shots)"""
import asyncio, os, json, threading, http.server, functools, shutil, subprocess
from playwright.async_api import async_playwright

PORT = 8792
root = '/tmp/claude-0/t/srv_pl'
shots = '/tmp/claude-0/t/shots'
os.makedirs(shots, exist_ok=True)
shutil.rmtree(root, ignore_errors=True)
os.makedirs(root)
HOOK = ("window.__t = { tracks: function(){ return libraryTracks; },"
        " makePl: function(name, titles){ var items = titles.map(function(t){ return t.indexOf('http') === 0"
        "   ? { stationuuid: 'st-' + t.length, name: 'Radio ' + t.slice(-3), url: t, favicon: '' }"
        "   : libraryTracks.filter(function(x){ return x.name === t; })[0]; });"
        "   var p = { id: makeStationPlaylistId(), label: name, stations: items }; stationPlaylists.push(p); saveStationPlaylists(); return p.id; },"
        " pl: function(id){ return findStationPlaylistById(id).stations.map(function(s){ return s.name; }); },"
        " stored: function(id){ return JSON.parse(localStorage.getItem('radioPlayerStationPlaylists')).filter(function(p){ return p.id === id; })[0].stations.map(function(s){ return s.name; }); },"
        " openPlaylists: function(){ openPlaylistsHome(); },"
        " openArtist: function(n){ artistStations = [{ stationuuid: 'ex-ann', name: 'Exclusively Ann', url: 'http://radio.example/ann', favicon: '', tags: '' }]; artistStationsPromise = Promise.resolve(artistStations); openArtistPage(artistMatchKey(n)); }, cur: function(){ return currentStation && currentStation.name; },"
        " queue: function(){ return (typeof playQueue !== 'undefined' && playQueue) ? playQueue.map(function(s){ return s.name; }) : null; } };\n")
_src = open(os.path.join(os.path.dirname(__file__), '..', 'www', 'index.html')).read()
_mark = '  var coverFlow = null;\n'
assert _src.count(_mark) == 1
open(root + '/index.html', 'w').write(_src.replace(_mark, _mark + HOOK))

M = root + '/Music'
os.makedirs(M, exist_ok=True)
SONGS = [('Amber', 'Ann'), ('Blue', 'Bob'), ('Coral', 'Cat'), ('Dusk', 'Dan'), ('Ember', 'Eve')]
for i, (t, a) in enumerate(SONGS):
    subprocess.run(['ffmpeg', '-loglevel', 'error', '-y', '-f', 'lavfi', '-i', f'sine=frequency={300 + i * 50}:duration=3',
                    '-c:a', 'libmp3lame', '-b:a', '32k', '-metadata', f'title={t}', '-metadata', f'artist={a}',
                    '-metadata', f'album={a} Album', f'{M}/{i + 1:02d}.mp3'], check=True)
class Q(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a): pass
H = functools.partial(Q, directory=root)
srv = http.server.ThreadingHTTPServer(('127.0.0.1', PORT), H)
threading.Thread(target=srv.serve_forever, daemon=True).start()
files = []
for f in sorted(os.listdir(M)):
    p = os.path.join(M, f)
    files.append({'uri': f'http://127.0.0.1:{PORT}/Music/{f}', 'name': f, 'relPath': f'Music/{f}', 'type': 'audio/mpeg',
                  'size': os.path.getsize(p), 'lastModified': 1700000000000})
MOCK = """
(function(){
 var picked = %s, listeners = {}, cur = null;
 function emit(n, ev){ (listeners[n] || []).forEach(function(f){ try{ f(ev); }catch(e){} }); }
 var impl = {
   pickMusicFolder: function(){ return Promise.resolve({folder:'Music', files:picked, truncated:false}); },
   cacheCheck: function(){ return Promise.resolve({ url: 'file:///cache/x.mp3' }); },
   load: function(o){ cur = o.id; setTimeout(function(){ emit('state', { id: cur, state: 'ready', isPlaying: true, playWhenReady: true, position: 0, duration: 3 }); }, 20); return Promise.resolve({}); },
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

ROWS = """Array.from(document.querySelectorAll('#stationsGrid > *')).map(function(r){ var b=r.getBoundingClientRect();
  var n=r.querySelector('.song-row-title, .row-name'); return { cls: r.className, name: n ? n.textContent : r.textContent.trim(),
  top: Math.round(b.top + scrollY), left: Math.round(b.left), w: Math.round(b.width),
  grip: !!r.querySelector('.row-drag-handle'), trash: !!r.querySelector('.fav-remove-btn'),
  sub: (r.querySelector('.song-row-sub, .row-sub')||{}).textContent || '' }; })"""


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
            if await pg.evaluate('__t.tracks().length') >= len(files): break
        pid = await pg.evaluate("__t.makePl('Road Trip', ['Coral', 'Amber', 'http://radio.example/abc', 'Ember', 'Blue', 'Dusk'])")
        await pg.evaluate('__t.openPlaylists()'); await pg.wait_for_timeout(600)
        await pg.evaluate("""Array.from(document.querySelectorAll('#stationsGrid .tile')).filter(function(t){ return /Road Trip/.test(t.textContent); })[0].click()""")
        await pg.wait_for_timeout(800)
        rows = await pg.evaluate(ROWS)
        print(rows)
        names = [r['name'] for r in rows]
        check(names == ['Coral', 'Amber', 'Radio abc', 'Ember', 'Blue', 'Dusk'], f'entries listed in playlist order {names}')
        check(all(r['w'] >= 330 and r['left'] <= 30 for r in rows), 'every entry is a full-width row')
        check(all(rows[i + 1]['top'] > rows[i]['top'] for i in range(len(rows) - 1)), 'rows stacked top to bottom')
        check('song-row' in rows[0]['cls'] and rows[0]['sub'].startswith('Cat'), f"songs show as song rows with artist {rows[0]}")
        check('row-item' in rows[2]['cls'], f"the station shows as a station row {rows[2]['cls']}")
        check(not any(r['grip'] or r['trash'] for r in rows), 'no grips or remove buttons outside Edit')
        await pg.screenshot(path=f'{shots}/playlist-rows.png')

        # Playing a song plays on through the playlist's songs
        await pg.evaluate("Array.from(document.querySelectorAll('#stationsGrid .song-row')).filter(function(r){ return /Amber/.test(r.textContent); })[0].click()")
        await pg.wait_for_timeout(800)
        check(await pg.evaluate('__t.cur()') == 'Amber', 'tapping a song plays it')

        # ---- Edit ----
        await pg.evaluate("document.getElementById('editActiveCustomSearchBtn').click()"); await pg.wait_for_timeout(500)
        rows = await pg.evaluate(ROWS)
        check([r['name'] for r in rows] == ['Coral', 'Amber', 'Radio abc', 'Ember', 'Blue', 'Dusk'] and all(r['grip'] and r['trash'] for r in rows),
              f'Edit: each row gets a grip and a remove button {[(r["name"], r["grip"], r["trash"]) for r in rows]}')
        check(rows[0]['sub'] == 'Cat - Cat Album', f"song rows keep artist and album in Edit ({rows[0]['sub']})")
        await pg.screenshot(path=f'{shots}/playlist-edit.png')
        # tapping a row in Edit doesn't play it
        await pg.evaluate("document.querySelectorAll('#stationsGrid .playlist-edit-row .row-name')[3].click()"); await pg.wait_for_timeout(400)
        check(await pg.evaluate('__t.cur()') == 'Amber', 'a tap on a row while editing plays nothing')

        # remove the station
        await pg.evaluate("document.querySelectorAll('#stationsGrid .playlist-edit-row')[2].querySelector('.fav-remove-btn').click()")
        await pg.wait_for_timeout(400)
        names = [r['name'] for r in await pg.evaluate(ROWS)]
        check(names == ['Coral', 'Amber', 'Ember', 'Blue', 'Dusk'], f'removed from the list {names}')
        check(await pg.evaluate(f'__t.stored({json.dumps(pid)})') == ['Coral', 'Amber', 'Ember', 'Blue', 'Dusk'], 'removal saved')

        # finger drag: Dusk (last) up to the top
        async def touch_drag(i_from, y_to):
            await pg.evaluate("""([i, yTo]) => new Promise(function(res){
              var rows = document.querySelectorAll('#stationsGrid .playlist-edit-row');
              var h = rows[i].querySelector('.row-drag-handle'), r = h.getBoundingClientRect();
              var x = r.left + r.width / 2, y = r.top + r.height / 2;
              function ev(t, yy, el){ (el || document).dispatchEvent(new PointerEvent(t, { pointerId: 7, pointerType: 'touch', clientX: x, clientY: yy, bubbles: true, cancelable: true })); }
              ev('pointerdown', y, h);
              var steps = 12, k = 0;
              (function step(){ k++; ev('pointermove', y + (yTo - y) * k / steps);
                if(k < steps) setTimeout(step, 16); else { ev('pointerup', yTo); res(); } })();
            })""", [i_from, y_to])
            await pg.wait_for_timeout(300)
        first_top = await pg.evaluate("document.querySelectorAll('#stationsGrid .playlist-edit-row')[0].getBoundingClientRect().top + 8")
        await touch_drag(4, first_top)
        names = [r['name'] for r in await pg.evaluate(ROWS)]
        check(names == ['Dusk', 'Coral', 'Amber', 'Ember', 'Blue'], f'a finger on the grip drags a row to a new place {names}')
        check(await pg.evaluate(f'__t.stored({json.dumps(pid)})') == names, 'new order saved straight away')
        # mouse drag: Coral below Ember
        src = pg.locator('#stationsGrid .playlist-edit-row').nth(1)
        dst = pg.locator('#stationsGrid .playlist-edit-row').nth(3)
        bb = await dst.bounding_box()
        await src.drag_to(dst, target_position={'x': 40, 'y': bb['height'] - 6})
        await pg.wait_for_timeout(400)
        names = [r['name'] for r in await pg.evaluate(ROWS)]
        check(names == ['Dusk', 'Amber', 'Ember', 'Coral', 'Blue'], f'mouse drag reorders too {names}')
        await pg.screenshot(path=f'{shots}/playlist-reordered.png')

        # Done (the check): rows back, in the new order
        await pg.evaluate("document.getElementById('editActiveCustomSearchBtn').click()"); await pg.wait_for_timeout(500)
        rows = await pg.evaluate(ROWS)
        check([r['name'] for r in rows] == ['Dusk', 'Amber', 'Ember', 'Coral', 'Blue'] and not any(r['grip'] for r in rows),
              f'after Done the playlist shows in its new order {[r["name"] for r in rows]}')
        check(await pg.evaluate(f'__t.stored({json.dumps(pid)})') == ['Dusk', 'Amber', 'Ember', 'Coral', 'Blue'], 'order kept in storage')
        # Reload: still in that order
        await pg.reload(); await pg.wait_for_timeout(2500)
        await pg.evaluate('__t.openPlaylists()'); await pg.wait_for_timeout(600)
        sub = await pg.evaluate("""Array.from(document.querySelectorAll('#stationsGrid .tile')).filter(function(t){ return /Road Trip/.test(t.textContent); })[0].textContent""")
        check('5 items' in sub, f'Playlists page counts the entries left ({sub})')
        await pg.evaluate("""Array.from(document.querySelectorAll('#stationsGrid .tile')).filter(function(t){ return /Road Trip/.test(t.textContent); })[0].click()""")
        await pg.wait_for_timeout(800)
        check([r['name'] for r in await pg.evaluate(ROWS)] == ['Dusk', 'Amber', 'Ember', 'Coral', 'Blue'], 'order survives a restart')
        # ---- an artist's own playlist sits right under their stations, as "Featuring <artist>" ----
        await pg.evaluate("__t.makePl('Ann', ['Blue', 'http://radio.example/zzz', 'Amber'])")
        await pg.evaluate("__t.openArtist('Ann')"); await pg.wait_for_timeout(1200)
        secs = await pg.evaluate("""Array.from(document.querySelectorAll('#stationsGrid .grid-section-label')).map(function(e){ return e.firstChild.textContent; })""")
        check(secs == ['Station', 'Featuring Ann', 'Albums'], f'artist page sections: Station, Featuring Ann, Albums {secs}')
        feat = await pg.evaluate("""(function(){ var out=[], on=false; Array.from(document.querySelectorAll('#stationsGrid > *')).forEach(function(e){
            if(e.classList.contains('grid-section-label')){ on = /Featuring/.test(e.textContent); return; }
            if(on){ var n=e.querySelector('.tile-name, .song-row-title, .row-name'); out.push(n ? n.textContent : ''); } }); return out; })()""")
        check(feat == ['Blue', 'Radio zzz', 'Amber'], f'Featuring lists the playlist entries {feat}')
        await pg.evaluate("document.querySelectorAll('#stationsGrid .grid-section-label')[0].scrollIntoView()"); await pg.wait_for_timeout(300)
        await pg.screenshot(path=f'{shots}/artist-featuring.png')
        no_more = await pg.evaluate("!/More from/.test(document.getElementById('stationsGrid').textContent)")
        check(no_more, 'no "More from" heading left')
        await pg.evaluate('__t.openPlaylists()'); await pg.wait_for_timeout(600)
        await pg.evaluate("""Array.from(document.querySelectorAll('#stationsGrid .tile')).filter(function(t){ return /Road Trip/.test(t.textContent); })[0].click()""")
        await pg.wait_for_timeout(800)

        # Remove everything: empty message
        await pg.evaluate("document.getElementById('editActiveCustomSearchBtn').click()"); await pg.wait_for_timeout(400)
        for _ in range(5):
            await pg.evaluate("document.querySelector('#stationsGrid .playlist-edit-row .fav-remove-btn').click()"); await pg.wait_for_timeout(200)
        txt = await pg.evaluate("document.getElementById('stationsGrid').textContent")
        check('empty' in txt, f'empty playlist says so ({txt})')
        check(not errs, f'no page errors {errs[:3]}')
        await b.close()
    print('ALL PASSED' if not fails else f'FAILED {fails}')

asyncio.run(main())
