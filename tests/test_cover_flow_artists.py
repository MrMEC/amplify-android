"""Cover Flow from My Library > Artists: turning the phone opens it with albums in artist order
(artist, then album title), on the first album of the artist at the top of the list; at the very
top of the list, on the first album. An artist found only on a compilation opens where their name
falls alphabetically, not on the compilation (which sorts under Various Artists). The Albums button on the landscape Now
Playing screen still opens it in album order.
Run: python3 tests/test_cover_flow_artists.py (screenshots in /tmp/claude-0/t/shots)"""
import asyncio, os, json, threading, http.server, functools, shutil, subprocess, colorsys
from playwright.async_api import async_playwright

PORT = 8789
root = '/tmp/claude-0/t/srv_cfa'
shots = '/tmp/claude-0/t/shots'
os.makedirs(shots, exist_ok=True)
shutil.rmtree(root, ignore_errors=True)
os.makedirs(root)
HOOK = ("window.__t = { cf: function(){ return coverFlow; }, runLibrarySection: runLibrarySection, tracks: function(){ return libraryTracks; },"
        " openNp: function(){ openNowPlaying(); }, hist: function(){ return viewHistory.map(function(v){ return v.label; }); },"
        " setArt: function(album, url){ var t = libraryTracks.filter(function(x){ return x.album === album; })[0]; return setCustomArtUrl('album:' + albumKeyFor(t), url); },"
        " clearArt: function(album){ var t = libraryTracks.filter(function(x){ return x.album === album; })[0]; return clearCustomArtUrl('album:' + albumKeyFor(t)); } };\n")
_src = open(os.path.join(os.path.dirname(__file__), '..', 'www', 'index.html')).read()
_mark = '  var coverFlow = null;\n'
assert _src.count(_mark) == 1
open(root + '/index.html', 'w').write(_src.replace(_mark, _mark + HOOK))

tone = f'{root}/tone.mp3'
subprocess.run(['ffmpeg', '-loglevel', 'error', '-y', '-f', 'lavfi', '-i', 'sine=frequency=440:duration=2',
                '-c:a', 'libmp3lame', '-b:a', '48k', tone], check=True)
M = root + '/Music'
n_art = [0]
def art(label):
    n_art[0] += 1
    r, g, b = colorsys.hsv_to_rgb((n_art[0] * 0.13) % 1, .6, .8)
    p = f'{root}/a{n_art[0]}.png'
    subprocess.run(['ffmpeg', '-loglevel', 'error', '-y', '-f', 'lavfi', '-i', 'color=c=0x%02x%02x%02x:s=400x400' % (int(r * 255), int(g * 255), int(b * 255)),
                    '-vf', f"drawtext=text='{label}':fontcolor=white:fontsize=90:x=(w-tw)/2:y=(h-th)/2", '-frames:v', '1', p], check=True)
    return p
def song(folder, n, title, artist, album, cover):
    p = f'{M}/{folder}/{n:02d}.mp3'
    os.makedirs(os.path.dirname(p), exist_ok=True)
    subprocess.run(['ffmpeg', '-loglevel', 'error', '-y', '-i', tone, '-i', cover, '-map', '0:a', '-map', '1:v', '-c:a', 'copy', '-c:v', 'png',
                    '-disposition:v', 'attached_pic', '-id3v2_version', '3', '-metadata', f'title={title}', '-metadata', f'artist={artist}',
                    '-metadata', f'album={album}', '-metadata', f'track={n}', p], check=True)

# Artist order differs from album order on purpose.
for artist, albums in [('Zed', ['Alpha', 'Mid']), ('Abba', ['Zulu', 'Beta']), ('Moby', ['Play']), ('Ivy', ['Green']), ('Jay', ['Jazz'])]:
    for al in albums:
        c = art(al[:4])
        song(f'{artist}/{al}', 1, f'{al} one', artist, al, c)
        song(f'{artist}/{al}', 2, f'{al} two', artist, al, c)
# A compilation; Aaron (first in the Artists list) and Kim appear only on it.
c = art('Now')
song('Comp/Now 1', 1, 'Kim song', 'Kim', 'Now 1', c)
song('Comp/Now 1', 2, 'Aaron song', 'Aaron', 'Now 1', c)
# Enough other artists to make the Artists list scroll.
for i in range(30):
    c = art(f'F{i:02d}')
    song(f'Filler/F{i:02d}', 1, f'Filler song {i:02d}', f'Ofiller {i:02d}', f'Record F{i:02d}', c)

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
 function proxy(){ return new Proxy({}, {get:function(t,k){
   if(k==='then') return undefined;
   if(k==='pickMusicFolder') return function(){ return Promise.resolve({folder:'Music', files:picked, truncated:false}); };
   if(k==='setCarLibraryPart') return undefined;
   if(k==='addListener') return function(){ return Promise.resolve({remove:function(){}}); };
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
    if not cond: fails.append(msg)

TOP = """(function(){ var ts=document.querySelectorAll(".tile[data-entity='artist']");
  for(var i=0;i<ts.length;i++){ var r=ts[i].getBoundingClientRect(); if(r.bottom>60) return ts[i].querySelector('.tile-name').textContent; } })()"""

async def scroll_to_artist(pg, name):
    await pg.evaluate(f"""(function(){{ var t=Array.prototype.find.call(document.querySelectorAll(".tile[data-entity='artist']"), function(x){{ return x.querySelector('.tile-name').textContent==={json.dumps(name)}; }});
      window.scrollTo(0, t.getBoundingClientRect().top + scrollY - 80); }})()""")
    await pg.wait_for_timeout(400)

async def rotate(pg, landscape):
    await pg.set_viewport_size({'width': 844, 'height': 390} if landscape else {'width': 390, 'height': 844})
    await pg.wait_for_timeout(1400)

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
            if await pg.evaluate('__t.tracks().length') >= len(files): break
        check(await pg.evaluate('__t.tracks().length') == len(files), f'library imported ({len(files)} songs)')
        await pg.wait_for_timeout(1500)

        # Artists list, top of the list: Abba.
        await pg.evaluate("__t.runLibrarySection('artists')"); await pg.wait_for_timeout(900)
        await pg.evaluate("window.scrollTo(0,0)"); await pg.wait_for_timeout(300)
        top = await pg.evaluate(TOP)
        await rotate(pg, True)
        st = await pg.evaluate("__t.cf()._state(true)")
        is_open = await pg.evaluate("document.getElementById('nowPlayingScreen').classList.contains('la-open')")
        check(is_open and st['order'] == 'artist', f'rotating on Artists opens Cover Flow in artist order ({top}, {st["order"]})')
        lst = st['list']
        head = lst[:2]; tail = lst[-6:]
        check(head == ['Beta / Abba', 'Zulu / Abba'], f'albums run by artist, then album title {head}')
        check(tail[-4:] == ['Record F29 / Ofiller 29', 'Now 1 / Various Artists', 'Alpha / Zed', 'Mid / Zed'] and lst.index('Green / Ivy') < lst.index('Play / Moby') < lst.index('Record F00 / Ofiller 00'),
              f'...through to the last artist {tail}')
        check(top == 'Aaron' and int(st['pos']) == 0 and lst[0] == 'Beta / Abba', f'at the top of the list it opens on the first album, not the top artist\'s compilation ({top} -> {lst[int(st["pos"])]})')
        cap = await pg.evaluate("document.querySelector('.cf-cap.on').innerText")
        check(cap == 'Beta\nAbba', f'caption {cap!r}')
        await pg.screenshot(path=f'{shots}/cfa-abba.png')
        await rotate(pg, False)
        back = await pg.evaluate("[document.body.classList.contains('np-open'), document.querySelectorAll(\".tile[data-entity='artist']\").length > 0]")
        check(not back[0] and back[1], f'turning back returns to the Artists list {back}')

        # An artist only on a compilation opens where their name falls (Kim -> Moby's album).
        await scroll_to_artist(pg, 'Kim')
        top = await pg.evaluate(TOP)
        await rotate(pg, True)
        st = await pg.evaluate("__t.cf()._state(true)")
        check(top == 'Kim' and st['list'][int(st['pos'])] == 'Play / Moby', f'compilation-only artist opens in alphabetical place ({top} -> {st["list"][int(st["pos"])]})')
        await pg.screenshot(path=f'{shots}/cfa-kim.png')
        await rotate(pg, False)

        # Scrolled down, then away and back to Artists (list drawn again, at its top): opens at
        # the start, not where the old scroll was.
        await scroll_to_artist(pg, 'Ofiller 20')
        await pg.evaluate("__t.runLibrarySection('albums')"); await pg.wait_for_timeout(700)
        await pg.evaluate("__t.runLibrarySection('artists')"); await pg.wait_for_timeout(900)
        top = await pg.evaluate(TOP)
        await rotate(pg, True)
        st = await pg.evaluate("__t.cf()._state(true)")
        check(top == 'Aaron' and int(st['pos']) == 0, f'a fresh visit to Artists opens at the start ({top} -> {st["list"][int(st["pos"])]})')
        await pg.screenshot(path=f'{shots}/cfa-fresh.png')
        await rotate(pg, False)

        # A filler artist part way down.
        await scroll_to_artist(pg, 'Ofiller 12')
        top = await pg.evaluate(TOP)
        await rotate(pg, True)
        st = await pg.evaluate("__t.cf()._state(true)")
        n = int(top.split()[-1])
        check(top.startswith('Ofiller') and st['list'][int(st['pos'])] == f'Record F{n:02d} / {top}', f'opens on the artist at the top of the list ({top} -> {st["list"][int(st["pos"])]})')
        # Scrolling keeps artist order.
        for k in range(3):
            await pg.evaluate("document.querySelector('.cf').dispatchEvent(new KeyboardEvent('keydown',{key:'ArrowRight'}))"); await pg.wait_for_timeout(80)
        await pg.wait_for_timeout(900)
        st = await pg.evaluate("__t.cf()._state(true)")
        want = f'Record F{n + 3:02d} / Ofiller {n + 3:02d}'
        check(st['list'][int(st['pos'])] == want, f'steps through artists in order ({st["list"][int(st["pos"])]})')
        await pg.screenshot(path=f'{shots}/cfa-filler.png')

        # Back to Now Playing, then the Albums button: album order again.
        await pg.evaluate("document.getElementById('npLandAlbumsBtn').click()"); await pg.wait_for_timeout(700)
        await pg.evaluate("document.getElementById('npLandAlbumsBtn').click()"); await pg.wait_for_timeout(900)
        st = await pg.evaluate("__t.cf()._state(true)")
        titles = [x.split(' / ')[0] for x in st['list']]
        check(st['order'] == 'album' and titles[:5] == ['Alpha', 'Beta', 'Green', 'Jazz', 'Mid'], f'Albums button opens in album order {titles[:4]}')
        check(st['list'][int(st['pos'])] == want, f'...on the same album it was showing ({st["list"][int(st["pos"])]})')
        await rotate(pg, False)

        # Turning an album over opens its page behind Cover Flow; a second one replaces it;
        # upright again, the page is showing and Back returns to the Artists list.
        await pg.evaluate("__t.runLibrarySection('artists')"); await pg.wait_for_timeout(800)
        await pg.evaluate("window.scrollTo(0,0)"); await pg.wait_for_timeout(300)
        await rotate(pg, True)
        key = lambda k: pg.evaluate("document.querySelector('.cf').dispatchEvent(new KeyboardEvent('keydown',{key:'" + k + "'}))")
        NPSTATE = "[document.body.classList.contains('np-open'), document.body.classList.contains('np-sheet'), document.getElementById('nowPlayingScreen').style.display]"
        before = await pg.evaluate(NPSTATE)
        await key('Enter'); await pg.wait_for_timeout(800)
        after_np = await pg.evaluate(NPSTATE)
        vis = await pg.evaluate("getComputedStyle(document.getElementById('nowPlayingScreen')).display")
        land = await pg.evaluate("[document.body.classList.contains('rotate-lock'), document.getElementById('nowPlayingScreen').classList.contains('la-open'), document.body.classList.contains('album-open'), document.getElementById('albumHeroName').textContent, !!document.querySelector('.cf-panel.open')]")
        check(land[:3] == [True, True, True] and land[3] == 'Beta' and land[4] and after_np == before and vis == 'flex',
              f'tapping the centre album opens its page behind Cover Flow, which stays up {land} {before} -> {after_np}')
        await pg.screenshot(path=f'{shots}/cfa-flip-behind.png')
        await key('Escape'); await pg.wait_for_timeout(500)
        await key('ArrowRight'); await pg.wait_for_timeout(700)
        await key('Enter'); await pg.wait_for_timeout(800)
        name = await pg.evaluate("document.getElementById('albumHeroName').textContent")
        hist = await pg.evaluate("__t.hist()")
        check(name == 'Zulu' and hist.count('Beta') == 0, f'a second album replaces the first, not stacked behind it ({name}, history {hist})')
        await rotate(pg, False)
        up = await pg.evaluate("[document.body.classList.contains('np-open'), document.body.classList.contains('album-open'), document.getElementById('albumHeroName').textContent, Math.round(document.getElementById('albumHero').getBoundingClientRect().height), window.scrollY, document.querySelectorAll('.song-row').length]")
        check(not up[0] and up[1] and up[2] == 'Zulu' and up[3] > 100 and up[5] == 2, f'upright, the album page is showing {up}')
        await pg.screenshot(path=f'{shots}/cfa-upright-album.png')
        back = await pg.evaluate("document.getElementById('detailBackLabel') ? document.getElementById('detailBackLabel').textContent : ''")
        await pg.evaluate("document.getElementById('detailBackBtn').click()"); await pg.wait_for_timeout(900)
        after = await pg.evaluate("[document.body.classList.contains('album-open'), document.querySelectorAll(\".tile[data-entity='artist']\").length]")
        check(back == 'Artists' and not after[0] and after[1] > 30, f'Back ({back!r}) returns to the Artists list {after}')

        # Now Playing opened by hand before turning: upright again after an album was turned
        # over, the album page shows rather than Now Playing.
        await pg.evaluate("__t.openNp()"); await pg.wait_for_timeout(700)
        await rotate(pg, True)
        await pg.evaluate("document.getElementById('npLandAlbumsBtn').click()"); await pg.wait_for_timeout(900)
        await key('Enter'); await pg.wait_for_timeout(800)
        await rotate(pg, False)
        up = await pg.evaluate("[document.body.classList.contains('np-open'), document.body.classList.contains('album-open')]")
        check(up == [False, True], f'album page shows even when Now Playing had been opened by hand {up}')

        # Just looking (no album turned over) still returns to the list as before.
        await pg.evaluate("__t.runLibrarySection('artists')"); await pg.wait_for_timeout(800)
        await rotate(pg, True)
        await key('ArrowRight'); await pg.wait_for_timeout(600)
        await rotate(pg, False)
        up = await pg.evaluate("[document.body.classList.contains('np-open'), document.body.classList.contains('album-open'), document.querySelectorAll(\".tile[data-entity='artist']\").length > 0]")
        check(up == [False, False, True], f'browsing without turning an album over returns to the list {up}')

        # Changing an album's cover shows in Cover Flow: while it's open, and when reopened.
        import base64, zlib, struct
        def png(r, g, b):
            raw = b''.join(b'\x00' + bytes([r, g, b]) * 16 for _ in range(16))
            ch = lambda t, d: struct.pack('>I', len(d)) + t + d + struct.pack('>I', zlib.crc32(t + d) & 0xffffffff)
            return 'data:image/png;base64,' + base64.b64encode(b'\x89PNG\r\n\x1a\n' + ch(b'IHDR', struct.pack('>IIBBBBB', 16, 16, 8, 2, 0, 0, 0)) + ch(b'IDAT', zlib.compress(raw)) + ch(b'IEND', b'')).decode()
        CENTRE = """(function(){ var c=document.querySelector('#npLandAlbums .cf-cover.cf-center'); if(!c) return null;
          var f=c.querySelector('.cf-face img'), r=c.querySelector('.cf-refl-img img');
          function px(img){ if(!img || !img.complete) return null; var cv=document.createElement('canvas'); cv.width=cv.height=4; var g=cv.getContext('2d'); g.drawImage(img,0,0,4,4); return Array.from(g.getImageData(1,1,1,1).data).slice(0,3); }
          return { face: px(f), refl: px(r), n: c.querySelectorAll('.cf-face img').length }; })()"""
        await pg.evaluate("__t.runLibrarySection('artists')"); await pg.wait_for_timeout(800)
        await pg.evaluate("window.scrollTo(0,0)"); await pg.wait_for_timeout(300)
        await rotate(pg, True)
        await pg.wait_for_timeout(1500)
        before = await pg.evaluate(CENTRE)
        await pg.evaluate(f"__t.setArt('Beta', {json.dumps(png(220, 20, 30))})"); await pg.wait_for_timeout(1500)
        after = await pg.evaluate(CENTRE)
        red = lambda p: p and p[0] > 180 and p[1] < 60 and p[2] < 70
        check(before and not red(before['face']) and red(after['face']) and red(after['refl']) and after['n'] == 1,
              f'a new cover shows at once while Cover Flow is open, on the cover and its reflection ({before} -> {after})')
        await pg.screenshot(path=f'{shots}/cfa-new-art.png')
        await rotate(pg, False)
        await pg.evaluate(f"__t.setArt('Beta', {json.dumps(png(20, 40, 230))})"); await pg.wait_for_timeout(300)
        await pg.evaluate("__t.runLibrarySection('artists')"); await pg.wait_for_timeout(800)
        await pg.evaluate("window.scrollTo(0,0)"); await pg.wait_for_timeout(300)
        await rotate(pg, True); await pg.wait_for_timeout(1500)
        blue = await pg.evaluate(CENTRE)
        check(blue and blue['face'] and blue['face'][2] > 180 and blue['face'][0] < 60, f'a cover changed while Cover Flow was closed shows when it opens ({blue})')
        await pg.evaluate("__t.clearArt('Beta')"); await pg.wait_for_timeout(1500)
        orig = await pg.evaluate(CENTRE)
        check(orig and orig['face'] == before['face'], f'removing the custom cover brings the original back ({orig} vs {before})')
        await rotate(pg, False)

        # My Library > Albums still opens in album order.
        await pg.evaluate("__t.runLibrarySection('albums')"); await pg.wait_for_timeout(800)
        await pg.evaluate("window.scrollTo(0,0)"); await pg.wait_for_timeout(300)
        await rotate(pg, True)
        st = await pg.evaluate("__t.cf()._state(true)")
        check(st['order'] == 'album' and st['list'][int(st['pos'])].startswith('Alpha'), f'Albums list still opens in album order ({st["order"]}, {st["list"][int(st["pos"])]})')
        check(not errs, f'no page errors {errs[:3]}')
        await b.close()
    print('ALL PASSED' if not fails else f'FAILED {fails}')

asyncio.run(main())
