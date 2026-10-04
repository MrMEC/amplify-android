"""Build 120: the A logo's dark version on the dark theme and light one on the light theme;
My Library's Favorite Artists as stacked rows with Edit (a word, far right) for dragging rows
into order and removing artists; For You renamed My Stations (Home, its page, the save button,
Android Auto). Build 129: A to Z by default, Order A to Z / Manual in Edit, grips only in Manual. Run: python3 tests/test_fav_artists.py (screenshots in /tmp/claude-0/t/shots)"""
import asyncio, os, json, threading, http.server, functools, shutil, subprocess
from playwright.async_api import async_playwright

PORT = 8799
root = '/tmp/claude-0/t/srv_favart'
shots = '/tmp/claude-0/t/shots'
os.makedirs(shots, exist_ok=True)
shutil.rmtree(root, ignore_errors=True)
os.makedirs(root)
HOOK = ("window.__f = { fav: function(n){ var e = findArtistEntry(artistMatchKey(n)); toggleFavorite(artistFavRecord(e)); },"
        " order: function(){ return favorites.filter(isArtistFav).map(function(f){ return f.name; }); },"
        " library: function(){ openMyLibraryHome(); }, stations: function(){ openStationsHome(); } };"
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
SONGS = [('A1', 'Alpha', 'Al', 1), ('B1', 'Bravo', 'Br', 1), ('C1', 'Charlie', 'Ch', 1), ('D1', 'Delta', 'De', 1)]
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

ROWS = """Array.from(document.querySelectorAll('.fav-artists-list .fav-artist-row')).map(function(r){ var b = r.getBoundingClientRect();
  return { name: r.querySelector('.row-name').textContent, top: Math.round(b.top), bottom: Math.round(b.bottom), left: Math.round(b.left),
    grip: !!r.querySelector('.row-drag-handle'), trash: !!r.querySelector('.fav-remove-btn'),
    round: getComputedStyle(r.querySelector('.row-thumb')).borderRadius }; })"""


async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
        ctx = await b.new_context(viewport={'width': 390, 'height': 844}, device_scale_factor=2, is_mobile=True, has_touch=True, color_scheme='dark')
        await ctx.add_init_script(MOCK)
        pg = await ctx.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.route('**/*', lambda route: route.continue_() if '127.0.0.1' in route.request.url else route.abort())
        await pg.goto(f'http://127.0.0.1:{PORT}/index.html'); await pg.wait_for_timeout(2500)

        # ---- the logo ----
        g = await pg.evaluate("getComputedStyle(document.documentElement).getPropertyValue('--logo-grad-start').trim()")
        check(g.lower() in ('#000000', '#000'), f'dark theme: the dark A ({g})')
        await pg.screenshot(path=f'{shots}/logo-dark.png', clip={'x': 0, 'y': 0, 'width': 390, 'height': 64})
        await pg.evaluate("document.documentElement.setAttribute('data-theme', 'light')"); await pg.wait_for_timeout(200)
        g2 = await pg.evaluate("getComputedStyle(document.documentElement).getPropertyValue('--logo-grad-start').trim()")
        check(g2.lower() in ('#ffffff', '#fff'), f'light theme: the light A ({g2})')
        await pg.screenshot(path=f'{shots}/logo-light.png', clip={'x': 0, 'y': 0, 'width': 390, 'height': 64})
        await pg.evaluate("document.documentElement.setAttribute('data-theme', 'dark')")

        # ---- My Stations ----
        home_h = await pg.evaluate("document.getElementById('forYouHomeHeading').textContent.trim()")
        drawer_h = await pg.evaluate("document.getElementById('forYouHeading').textContent.trim()")
        check(home_h == 'My Stations' and drawer_h == 'My Stations', f'Home row and menu say My Stations ({home_h!r}, {drawer_h!r})')
        await pg.evaluate('__f.stations()'); await pg.wait_for_timeout(400)
        check(await pg.evaluate("document.getElementById('stationsHeading').textContent") == 'My Stations', 'its page is headed My Stations')
        check('My Stations' in await pg.evaluate("document.getElementById('searchSaveBtn') ? '' : document.getElementById('saveSearchBtn').title"), 'saving a search says it goes to My Stations')
        java = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'android/app/src/main/java/com/markcoleman/amplify/CarLibrary.java')).read()
        check('"st:foryou", "My Stations"' in java and '"For You"' not in java, 'Android Auto calls it My Stations')
        txt = await pg.evaluate("document.body.innerText")
        check('For You' not in txt, 'no "For You" left anywhere on screen')

        # ---- Favorite Artists ----
        await pg.evaluate("""(function(){ var ov=document.getElementById('addMusicOverlay'); if(ov) ov.classList.add('open');
          var btn=document.getElementById('addMusicFolderBtn'); btn.disabled=false; btn.click(); })()""")
        for _ in range(60):
            await pg.wait_for_timeout(500)
            if len(await pg.evaluate('__t.tracks()')) >= 4: break
        await pg.evaluate("document.getElementById('addMusicOverlay').classList.remove('open')")
        # favourited out of alphabetical order
        for n in ('Delta', 'Bravo', 'Alpha', 'Charlie'): await pg.evaluate(f"__f.fav('{n}')")
        await pg.evaluate('__f.library()'); await pg.wait_for_timeout(700)
        rows = await pg.evaluate(ROWS)
        print(rows)
        check([r['name'] for r in rows] == ['Alpha', 'Bravo', 'Charlie', 'Delta'], 'Favorite Artists listed A to Z by default (build 129)')
        check(all(rows[i + 1]['top'] >= rows[i]['bottom'] - 1 and rows[i + 1]['left'] == rows[0]['left'] for i in range(3)), 'stacked as rows, one under another')
        check(all(r['round'] == '50%' and not r['grip'] and not r['trash'] for r in rows), 'round portraits; no grips or remove buttons until Edit')
        check(not await pg.evaluate("!!document.querySelector('.fav-artists-order')"), 'no order options until Edit')
        ed = await pg.evaluate("""(()=>{ var b = document.querySelector('.fav-artists-edit'), g = document.getElementById('stationsGrid').getBoundingClientRect(), r = b.getBoundingClientRect();
          return { text: b.textContent, icon: !!b.querySelector('i, svg'), right: Math.round(g.right - r.right) }; })()""")
        check(ed['text'] == 'Edit' and not ed['icon'] and ed['right'] <= 4, f'"Edit" as a word, on the far right {ed}')
        await pg.screenshot(path=f'{shots}/favart-rows.png')
        await pg.evaluate("document.querySelectorAll('.fav-artist-row')[1].click()"); await pg.wait_for_timeout(600)
        check(await pg.evaluate("document.body.classList.contains('artist-open') && /Bravo/.test(document.getElementById('artistHeroName').textContent)"), 'a row opens the artist')
        await pg.evaluate('__f.library()'); await pg.wait_for_timeout(700)

        OPTS = "Array.from(document.querySelectorAll('.fav-artists-order .home-tab')).map(function(b){ return b.textContent + (b.classList.contains('active') ? '*' : ''); })"
        # Edit in A to Z: order options, remove buttons, no grips
        await pg.evaluate("document.querySelector('.fav-artists-edit').click()"); await pg.wait_for_timeout(300)
        check(await pg.evaluate(OPTS) == ['A to Z*', 'Manual'], 'Edit shows Order: A to Z (chosen) / Manual')
        rows = await pg.evaluate(ROWS)
        check([r['name'] for r in rows] == ['Alpha', 'Bravo', 'Charlie', 'Delta'] and all(r['trash'] and not r['grip'] for r in rows), 'A to Z: remove buttons but no grips')
        check(await pg.evaluate("document.querySelector('.fav-artists-edit').textContent") == 'Done', 'the button now says Done')
        geo = await pg.evaluate("""(()=>{ var h = document.querySelector('.fav-artists-head').getBoundingClientRect(), o = document.querySelector('.fav-artists-order').getBoundingClientRect(), r = document.querySelector('.fav-artist-row').getBoundingClientRect();
          return { below: o.top >= h.bottom - 1, above: o.bottom <= r.top + 1 }; })()""")
        check(geo['below'] and geo['above'], 'the options sit between the heading and the rows')
        await pg.screenshot(path=f'{shots}/favart-edit-az.png')
        # Manual: the favourites' own order, with grips
        await pg.evaluate("document.querySelector('.fav-artists-order .home-tab[data-opt=manual]').click()"); await pg.wait_for_timeout(300)
        check(await pg.evaluate(OPTS) == ['A to Z', 'Manual*'], 'Manual chosen')
        rows = await pg.evaluate(ROWS)
        check([r['name'] for r in rows] == ['Delta', 'Bravo', 'Alpha', 'Charlie'] and all(r['grip'] and r['trash'] for r in rows), f'Manual: favourite order, with grips {[r["name"] for r in rows]}')
        check(await pg.evaluate("document.querySelector('.fav-artists-edit').textContent") == 'Done', 'still editing')
        await pg.screenshot(path=f'{shots}/favart-edit.png')
        # finger drag Charlie (4th) to the top
        await pg.evaluate("""([i, yTo]) => new Promise(function(res){
              var rows = document.querySelectorAll('.fav-artist-row');
              var h = rows[i].querySelector('.row-drag-handle'), r = h.getBoundingClientRect();
              var x = r.left + r.width / 2, y = r.top + r.height / 2;
              function ev(t, yy, el){ (el || document).dispatchEvent(new PointerEvent(t, { pointerId: 7, pointerType: 'touch', clientX: x, clientY: yy, bubbles: true, cancelable: true })); }
              ev('pointerdown', y, h);
              var steps = 12, k = 0;
              (function step(){ k++; ev('pointermove', y + (yTo - y) * k / steps);
                if(k < steps) setTimeout(step, 16); else { ev('pointerup', yTo); res(); } })();
            })""", [3, rows[0]['top'] + 8])
        await pg.wait_for_timeout(300)
        names = [r['name'] for r in await pg.evaluate(ROWS)]
        check(names == ['Charlie', 'Delta', 'Bravo', 'Alpha'], f'a finger on the grip drags a row into place {names}')
        check(await pg.evaluate('__f.order()') == names, 'the new order is saved')
        # tapping a row in Edit doesn't navigate
        await pg.evaluate("document.querySelectorAll('.fav-artist-row')[0].click()"); await pg.wait_for_timeout(300)
        check(not await pg.evaluate("document.body.classList.contains('artist-open')"), 'in Edit, tapping a row does not open the artist')
        # back to A to Z and to Manual again: the manual order is kept
        await pg.evaluate("document.querySelector('.fav-artists-order .home-tab[data-opt=az]').click()"); await pg.wait_for_timeout(300)
        rows = await pg.evaluate(ROWS)
        check([r['name'] for r in rows] == ['Alpha', 'Bravo', 'Charlie', 'Delta'] and not any(r['grip'] for r in rows), 'A to Z again: alphabetical, grips gone')
        await pg.evaluate("document.querySelector('.fav-artists-order .home-tab[data-opt=manual]').click()"); await pg.wait_for_timeout(300)
        check([r['name'] for r in await pg.evaluate(ROWS)] == ['Charlie', 'Delta', 'Bravo', 'Alpha'], 'Manual again: the dragged order is still there')
        # remove Bravo
        await pg.evaluate("Array.from(document.querySelectorAll('.fav-artist-row')).filter(function(r){ return /Bravo/.test(r.textContent); })[0].querySelector('.fav-remove-btn').click()")
        await pg.wait_for_timeout(300)
        rows = await pg.evaluate(ROWS)
        check([r['name'] for r in rows] == ['Charlie', 'Delta', 'Alpha'] and all(r['grip'] for r in rows), f'remove takes the artist off the list, still in Edit {[r["name"] for r in rows]}')
        check(await pg.evaluate('__f.order()') == ['Charlie', 'Delta', 'Alpha'], 'and out of favourites')
        await pg.evaluate("document.querySelector('.fav-artists-edit').click()"); await pg.wait_for_timeout(300)
        rows = await pg.evaluate(ROWS)
        check(not any(r['grip'] or r['trash'] for r in rows) and await pg.evaluate("document.querySelector('.fav-artists-edit').textContent") == 'Edit'
              and not await pg.evaluate("!!document.querySelector('.fav-artists-order')"), 'Done: plain rows again, options hidden')
        check([r['name'] for r in rows] == ['Charlie', 'Delta', 'Alpha'], 'Manual order shown outside Edit too')
        # restart keeps order and the Manual choice
        await pg.reload(); await pg.wait_for_timeout(2500)
        await pg.evaluate('__f.library()'); await pg.wait_for_timeout(900)
        check([r['name'] for r in await pg.evaluate(ROWS)] == ['Charlie', 'Delta', 'Alpha'], 'order, Manual and removal kept after a restart')
        # removing every artist removes the section
        await pg.evaluate("document.querySelector('.fav-artists-edit').click()"); await pg.wait_for_timeout(200)
        for _ in range(3):
            await pg.evaluate("document.querySelector('.fav-artist-row .fav-remove-btn').click()"); await pg.wait_for_timeout(200)
        check(await pg.evaluate("!document.querySelector('.fav-artists-block')"), 'the section goes once the last artist is removed')
        check(not errs, f'no page errors {errs[:3]}')
        await b.close()
    print('ALL PASSED' if not fails else f'FAILED {fails}')

asyncio.run(main())
