"""Build 135: artist portraits (Wikipedia) fill in on the Artists list by themselves, even for artists
whose songs carry their own cover art, and stay after a restart without asking again.
Run: python3 tests/test_artist_portraits.py (screenshots in /tmp/claude-0/t/shots)"""
import asyncio, os, json, threading, http.server, functools, shutil, subprocess, sys
from urllib.parse import urlparse, unquote
from playwright.async_api import async_playwright

PORT = 8805
root = '/tmp/claude-0/t/srv_portraits'
shots = '/tmp/claude-0/t/shots'
os.makedirs(shots, exist_ok=True)
shutil.rmtree(root, ignore_errors=True)
os.makedirs(root)
HOOK = ("window.__p = { tracks: function(){ return libraryTracks.length; },"
        " hide: function(){ try{ hideImportPanel(); setStatus('', false); }catch(e){} },"
        " artists: function(){ runLibrarySection('artists'); }, lib: function(){ openMyLibraryHome(); },"
        " open: function(n){ openArtistPage(findArtistEntry(artistMatchKey(n)).key); },"
        " fav: function(n){ var e = findArtistEntry(artistMatchKey(n)); toggleFavorite(artistFavRecord(e)); },"
        " age: function(days){ Object.keys(artistMeta).forEach(function(k){ var r = artistMeta[k]; r.ts = Date.now() - days * 864e5; saveArtistMeta(r); }); },"
        " sizes: function(sel){ var o = {}; document.querySelectorAll(sel || '#stationsGrid .tile[data-entity=\"artist\"]').forEach(function(t){"
        "   var n = t.querySelector('.tile-name, .row-name'), i = t.querySelector('.tile-art img, .row-thumb img'); o[n ? n.textContent.trim() : t.dataset.key] = i && i.complete ? i.naturalWidth : 0; }); return o; } };\n")
_src = open(os.path.join(os.path.dirname(__file__), '..', 'www', 'index.html')).read()
_mark = '  var coverFlow = null;\n'
assert _src.count(_mark) == 1
open(root + '/index.html', 'w').write(_src.replace(_mark, _mark + HOOK))

M = root + '/Music'
os.makedirs(M, exist_ok=True)
COVER = root + '/cover.jpg'   # 64px: the songs' own art
subprocess.run(['ffmpeg', '-loglevel', 'error', '-y', '-f', 'lavfi', '-i', 'color=c=green:s=64x64', '-frames:v', '1', COVER], check=True)
# Alpha and Charlie songs carry their own cover; Bravo's don't.
SONGS = [('A1', 'Alpha', 'Alpha Album', True), ('B1', 'Bravo', 'Bravo Album', False), ('C1', 'Charlie', 'Charlie Album', True),
         ('D1', 'Delta', 'Delta Album', True)]
for i, (t, a, al, art) in enumerate(SONGS):
    out = f'{M}/{i + 1:02d}.mp3'
    cmd = ['ffmpeg', '-loglevel', 'error', '-y', '-f', 'lavfi', '-i', f'sine=frequency={300 + i * 60}:duration=3']
    if art:
        cmd += ['-i', COVER, '-map', '0:a', '-map', '1:v', '-c:v', 'copy', '-id3v2_version', '3',
                '-metadata:s:v', 'title=Album cover', '-metadata:s:v', 'comment=Cover (front)']
    cmd += ['-c:a', 'libmp3lame', '-b:a', '32k', '-metadata', f'title={t}', '-metadata', f'artist={a}', '-metadata', f'album={al}', out]
    subprocess.run(cmd, check=True)
PORTRAITS = {}
for name, colour, size in [('alpha', 'red', 200), ('bravo', 'blue', 210), ('delta', 'yellow', 220)]:
    f = f'{root}/{name}.jpg'
    subprocess.run(['ffmpeg', '-loglevel', 'error', '-y', '-f', 'lavfi', '-i', f'color=c={colour}:s={size}x{size}', '-frames:v', '1', f], check=True)
    PORTRAITS[name] = open(f, 'rb').read()


class Q(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a): pass
srv = http.server.ThreadingHTTPServer(('127.0.0.1', PORT), functools.partial(Q, directory=root))
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

BIOS = {'Alpha': 'American rock band', 'Bravo': 'American singer', 'Delta': 'English band'}
log = {'summary': [], 'photo': []}
state = {'offline': False}
fails = []


def check(cond, msg):
    print(('PASS ' if cond else 'FAIL ') + msg)
    if not cond: fails.append(msg)


async def route(r):
    u = urlparse(r.request.url)
    if '127.0.0.1' in u.netloc:
        return await r.continue_()
    hdr = {'access-control-allow-origin': '*'}
    if state['offline']:
        return await r.abort()
    if u.netloc == 'en.wikipedia.org' and u.path.startswith('/api/rest_v1/page/summary/'):
        t = unquote(u.path.split('/summary/')[1])
        log['summary'].append(t)
        if t in BIOS:
            return await r.fulfill(status=200, content_type='application/json', headers=hdr, body=json.dumps({
                'type': 'standard', 'title': t, 'description': BIOS[t],
                'extract': f'{t} is an {BIOS[t]}. They make music and release albums.',
                'thumbnail': {'source': f'https://upload.wikimedia.org/x/{t.lower()}.jpg'},
                'content_urls': {'desktop': {'page': f'https://en.wikipedia.org/wiki/{t}'}}}))
        return await r.fulfill(status=404, body='', headers=hdr)
    if u.netloc == 'upload.wikimedia.org':
        n = u.path.rsplit('/', 1)[1].split('.')[0]
        log['photo'].append(n)
        if n in PORTRAITS:
            return await r.fulfill(status=200, content_type='image/jpeg', headers=hdr, body=PORTRAITS[n])
        return await r.fulfill(status=404, body='', headers=hdr)
    if u.netloc == 'www.wikidata.org':
        return await r.fulfill(status=200, content_type='application/json', headers=hdr, body=json.dumps({'search': []}))
    return await r.abort()


WANT = {'Alpha': 200, 'Bravo': 210, 'Charlie': 64, 'Delta': 220}


async def wait_sizes(pg, want, ms=12000, sel=None):
    got = None
    for _ in range(ms // 250):
        got = await pg.evaluate('__p.sizes(%s)' % json.dumps(sel) if sel else '__p.sizes()')
        if all(got.get(k) == v for k, v in want.items()):
            return got
        await pg.wait_for_timeout(250)
    return got


async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
        ctx = await b.new_context(viewport={'width': 412, 'height': 900}, device_scale_factor=2, is_mobile=True, has_touch=True, color_scheme='dark')
        await ctx.add_init_script(MOCK)
        pg = await ctx.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.route('**/*', route)
        await pg.goto(f'http://127.0.0.1:{PORT}/index.html'); await pg.wait_for_timeout(2500)
        await pg.evaluate("""(function(){ var ov=document.getElementById('addMusicOverlay'); if(ov) ov.classList.add('open');
          var btn=document.getElementById('addMusicFolderBtn'); btn.disabled=false; btn.click(); })()""")
        for _ in range(60):
            await pg.wait_for_timeout(500)
            if await pg.evaluate('__p.tracks()') >= 4: break
        await pg.evaluate("document.getElementById('addMusicOverlay').classList.remove('open')")
        await pg.wait_for_timeout(300); await pg.evaluate('__p.hide()')

        # ---- Favorite Artists on My Library: a portrait arriving while the row is shown repaints it ----
        await pg.evaluate("__p.fav('Alpha')"); await pg.evaluate("__p.fav('Charlie')")
        await pg.evaluate('__p.lib()')
        FAV = '.fav-artists-list .fav-artist-row'
        got = await wait_sizes(pg, {'Alpha': 200, 'Charlie': 64}, 8000, FAV)
        print('favorite artists', got)
        check(got.get('Alpha') == 200 and got.get('Charlie') == 64, f'Favorite Artists rows update to the portrait by themselves {got}')
        await pg.screenshot(path=f'{shots}/portraits-favs.png')

        # ---- the Artists list fills in by itself, cover-art artists included ----
        await pg.evaluate('__p.artists()')
        got = await wait_sizes(pg, WANT)
        print('list', got)
        check(got.get('Alpha') == 200, f'Alpha (songs have their own cover) shows the portrait without opening the page {got}')
        check(got.get('Bravo') == 210, f'Bravo (no cover) shows the portrait {got}')
        check(got.get('Delta') == 220, f'Delta shows the portrait {got}')
        check(got.get('Charlie') == 64, f'Charlie (no article) keeps the songs\' cover {got}')
        await pg.wait_for_timeout(1500); await pg.screenshot(path=f'{shots}/portraits-list.png')
        px = (await pg.evaluate("""Array.from(document.querySelectorAll('#stationsGrid .tile[data-entity=artist]')).map(function(t){ var i = t.querySelector('img'); var c = document.createElement('canvas'); c.width = 4; c.height = 4; var x = c.getContext('2d'); x.drawImage(i, 0, 0, 4, 4); var d = x.getImageData(1,1,1,1).data; var r = i.getBoundingClientRect(); return t.textContent.trim() + ' ' + i.naturalWidth + ' ' + d[0]+','+d[1]+','+d[2] + ' ' + getComputedStyle(i).opacity + ' ' + Math.round(r.width); })"""))
        print('pixels', px)
        check(px[0].startswith('Alpha 200 25') and px[3].startswith('Delta 220 25'), f'the portraits are what is drawn {px}')

        # ---- opening a page and coming back keeps it ----
        await pg.evaluate("__p.open('Alpha')"); await pg.wait_for_timeout(1200)
        hero = await pg.evaluate("(()=>{ var i = document.querySelector('#artistHeroArt img'); return i ? i.naturalWidth : 0; })()")
        check(hero == 200, f'the artist page shows the same portrait ({hero})')
        await pg.evaluate('__p.artists()')
        got = await wait_sizes(pg, WANT, 3000)
        check(got == WANT, f'back on the list: unchanged {got}')


        # ---- after a restart: painted from what was saved, nothing asked again ----
        n_sum, n_photo = len(log['summary']), len(log['photo'])
        await pg.reload(); await pg.wait_for_timeout(2500)
        await pg.evaluate('__p.hide()'); await pg.evaluate('__p.artists()')
        got = await wait_sizes(pg, WANT, 6000)
        print('after restart', got)
        check(got == WANT, f'after a restart the portraits are still there {got}')
        print('asked after restart', log['summary'][n_sum:], log['photo'][n_photo:])
        check(len(log['summary']) == n_sum and len(log['photo']) == n_photo,
              f"after a restart nothing is asked again ({len(log['summary']) - n_sum} summaries, {len(log['photo']) - n_photo} photos)")
        await pg.screenshot(path=f'{shots}/portraits-restart.png')
        await pg.evaluate('__p.lib()')
        got = await wait_sizes(pg, {'Alpha': 200, 'Charlie': 64}, 4000, '.fav-artists-list .fav-artist-row')
        check(got.get('Alpha') == 200, f'Favorite Artists after a restart {got}')

        # ---- after a restart with no connection: still there ----
        state['offline'] = True
        await pg.evaluate('__p.age(40)')   # past the month: a refresh is due, but there is no signal
        await pg.wait_for_timeout(500)
        await pg.reload(); await pg.wait_for_timeout(2500)
        await pg.evaluate('__p.hide()'); await pg.evaluate('__p.artists()')
        await pg.wait_for_timeout(4000)
        got = await wait_sizes(pg, WANT, 3000)
        print('offline restart', got)
        check(got == WANT, f'offline, with the saved info due a refresh: portraits kept {got}')
        state['offline'] = False

        check(not errs, f'no page errors {errs[:3]}')
        await b.close()
    srv.shutdown()
    print('FAILS:', len(fails))
    sys.exit(1 if fails else 0)

asyncio.run(main())
