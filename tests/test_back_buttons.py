"""Build 204: one back button everywhere (the artist page's bare arrow, no label, no pill) and it always
goes back to the page you came from; My Stations has no "Saved Searches" label or count.
Run: python3 tests/test_back_buttons.py (screenshots in /tmp/claude-0/t/shots)"""
"""Artist and album pages slide in from the right on phones when opened (tapping a tile),
using only a transform; Back, and the system's Remove animations setting, open them in place.
Run: python3 tests/test_page_slide.py (screenshots in /tmp/claude-0/t/shots)"""
import asyncio, os, json, threading, http.server, functools, shutil, subprocess
from playwright.async_api import async_playwright

PORT = 8803
root = '/tmp/claude-0/t/srv_back'
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
        " artists: function(){ runLibrarySection('artists'); }, ev: function(js){ return eval(js); },"
        " status: function(){ var e = document.getElementById('statusLine') || document.querySelector('.status-line'); return e ? e.textContent : ''; } };\n")
_src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'www', 'index.html')).read()
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



BTN="""(()=>{var b=document.getElementById('detailBackBtn'); if(!b||getComputedStyle(b).display==='none') return null; var r=b.getBoundingClientRect(), c=getComputedStyle(b), l=document.getElementById('detailBackLabel');
 var x=document.createElement('span'); x.style.color='var(--text)'; b.parentNode.appendChild(x); var tc=getComputedStyle(x).color; x.remove();
 return {x:Math.round(r.left),w:Math.round(r.width),h:Math.round(r.height),bg:c.backgroundColor,border:c.borderTopWidth,fs:c.fontSize,color:c.color,text:tc,
  label:Math.round(l.getBoundingClientRect().width)};})()"""
HEAD="(()=>[document.getElementById('stationsHeading').textContent, document.body.classList.contains('album-open'), document.body.classList.contains('artist-open')])()"
async def look(pg, name, theme, plain=True, x=None):
    await pg.wait_for_timeout(700)
    r = await pg.evaluate(BTN)
    await pg.screenshot(path=f'{shots}/back-{theme}-{name}.png', clip={'x':0,'y':0,'width':390,'height':330})
    ok = r and r['w'] == 52 and r['h'] == 52 and r['bg'] == 'rgba(0, 0, 0, 0)' and r['border'] == '0px' and r['fs'] == '24px' and r['label'] <= 1
    if plain: ok = ok and r['color'] == r['text']
    if x is not None: ok = ok and r['x'] == x
    check(ok, f'{theme} {name}: bare 24px arrow on a 52px target, no pill, no label{", page text colour" if plain else ""}{", same place as the artist page" if x is not None else ""} {r}')
    return r
async def back(pg):
    await pg.evaluate("document.getElementById('detailBackBtn').click()"); await pg.wait_for_timeout(700)
    return await pg.evaluate(HEAD)
async def run(p, theme):
    b = await p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
    ctx = await b.new_context(viewport={'width': 390, 'height': 844}, device_scale_factor=2, is_mobile=True, has_touch=True, color_scheme='dark')
    await ctx.add_init_script(MOCK)
    await ctx.add_init_script("localStorage.setItem('radioPlayerTheme','%s'); localStorage.setItem('radioPlayerCustomSearches', JSON.stringify([{id:'cs1',label:'Smooth Jazz',mode:'tag',query:'smooth jazz'}]));" % theme)
    pg = await ctx.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
    await pg.route('**/*', lambda route: route.continue_() if '127.0.0.1' in route.request.url else route.abort())
    await pg.goto(f'http://127.0.0.1:{PORT}/index.html'); await pg.wait_for_timeout(2500)
    await pg.evaluate("""(function(){ var ov=document.getElementById('addMusicOverlay'); if(ov) ov.classList.add('open'); var btn=document.getElementById('addMusicFolderBtn'); btn.disabled=false; btn.click(); })()""")
    for _ in range(60):
        await pg.wait_for_timeout(500)
        if len(await pg.evaluate('__t.tracks()')) >= 4: break
    await pg.evaluate("__t.mk()")
    # My Library -> Artists -> Kay -> Big Album, then Back each step
    await pg.evaluate("document.querySelector('.mobile-nav-btn[data-nav=library]').click()"); await pg.wait_for_timeout(700)
    await pg.evaluate("Array.from(document.querySelectorAll('#stationsGrid .tile')).filter(function(t){ return /Artists/.test(t.textContent); })[0].click()")
    await look(pg, 'artists', theme)
    await pg.evaluate("Array.from(document.querySelectorAll('#stationsGrid .tile')).filter(function(t){ return /Kay/.test(t.textContent); })[0].click()")
    ar = await look(pg, 'artist', theme, plain=False)
    ax = ar and ar['x']
    await pg.evaluate("Array.from(document.querySelectorAll('.tile')).filter(function(t){ return /Big Album/.test(t.textContent) && t.offsetParent; })[0].click()")
    await look(pg, 'album', theme, plain=False, x=ax)
    # pages opened from the album page: My Stations, Playlists, a playlist
    await pg.evaluate("__t.ev('pushView(); openStationsHome()')")
    await look(pg, 'mystations', theme, x=ax)
    txt = await pg.evaluate("document.getElementById('stationsGrid').innerText")
    check('Saved Searches' not in txt and not await pg.evaluate("!!document.querySelector('#stationsGrid .grid-section-label, #stationsGrid .grid-section-count')") and 'Smooth Jazz' in txt,
          f'{theme}: My Stations lists the saved search with no "Saved Searches" label or count {txt[:60]!r}')
    await pg.evaluate("__t.ev('pushView(); openPlaylistsHome()')"); await look(pg, 'playlists', theme, x=ax)
    await pg.evaluate("__t.ev('pushView(); runStationPlaylist(stationPlaylists[0])')"); await look(pg, 'playlist', theme, x=ax)
    h = await back(pg); check(h[0] == 'Playlists', f'{theme}: Back from a playlist returns to Playlists {h}')
    h = await back(pg); check(h[0] == 'My Stations', f'{theme}: Back from Playlists returns to My Stations (not My Library) {h}')
    h = await back(pg); check(h[1], f'{theme}: Back from My Stations returns to the album {h}')
    h = await back(pg); check(h[2] and not h[1], f'{theme}: then the artist {h}')
    h = await back(pg); check(h[0] == 'Artists', f'{theme}: then Artists {h}')
    h = await back(pg); check(h[0] == 'Library' and not await pg.evaluate("getComputedStyle(document.getElementById('detailBackBtn')).display!=='none'"),
          f'{theme}: then My Library, which has no back button {h}')
    # Genres from My Library, a genre, Back twice
    await pg.evaluate("Array.from(document.querySelectorAll('#stationsGrid .tile')).filter(function(t){ return /Genres/.test(t.textContent); })[0].click()")
    await look(pg, 'genres', theme, x=ax)
    h = await back(pg); check(h[0] == 'Library', f'{theme}: Back from Genres returns to My Library {h}')
    check(not errs, f'{theme}: no page errors {errs[:3]}')
    await b.close()
async def main():
    async with async_playwright() as p:
        for t in ['dark', 'light']: await run(p, t)
    print('ALL PASSED' if not fails else f'FAILED {fails}')
asyncio.run(main())
