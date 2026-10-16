"""Cover art in song files and an album's Info & Tags (build 232). One song: the sheet shows the
cover in the file, Edit offers Change / Remove, Save writes the picture as the front cover (ID3
APIC, FLAC PICTURE) and Amplify shows it. An album: the album menu's Info & Tags reads every
song, shows the shared tags (a field that differs says so and is left alone), and Save writes
the changes and the cover into every MP3 and FLAC (an M4A is left alone); a renamed album keeps
its page and custom cover. Edit Album Cover: "Also save in the album's song files". The mocked
plugin hands writes to this server, which applies them like TagWriter.java; mutagen checks the
files. Both themes; 360 wide with larger text.
Run: python3 tests/test_tag_covers.py (screenshots in /tmp/claude-0/t/shots)"""
import asyncio, os, json, threading, http.server, functools, shutil, subprocess, base64, zlib, hashlib
from playwright.async_api import async_playwright
from mutagen.id3 import ID3
from mutagen.flac import FLAC

PORT = 8830
root = '/tmp/claude-0/t/srv_covers'
shots = '/tmp/claude-0/t/shots'
os.makedirs(shots, exist_ok=True)
shutil.rmtree(root, ignore_errors=True)
os.makedirs(root)
HOOK = ("window.__t = { tracks: function(){ return libraryTracks; }, runLibrarySection: runLibrarySection,"
        " albumKey: function(name){ var t = libraryTracks.filter(function(x){ return x.album === name; })[0]; return t ? albumKeyFor(t) : null; },"
        " openAlbum: function(name){ var t = libraryTracks.filter(function(x){ return x.album === name; })[0]; openAlbumPage(albumKeyFor(t), null); },"
        " heading: function(){ return document.getElementById('albumHeroName') ? document.getElementById('albumHeroName').textContent : ''; },"
        " albumOpen: function(){ return document.body.classList.contains('album-open') && activeAlbumKey; },"
        " setArt: function(k, u){ setCustomArtUrl(k, u); }, getArt: function(k){ return getCustomArtUrl(k) || ''; },"
        " art: function(title){ var t = libraryTracks.filter(function(x){ return x.name === title; })[0]; return idbDo([LIB_STORE_ART], 'readonly', function(tx){ return tx.objectStore(LIB_STORE_ART).get(favKey(t)); }).then(function(b){ return { has: t.hasArt, size: b ? b.size : 0 }; }); },"
        " playSong: function(title){ var t = libraryTracks.filter(function(x){ return x.name === title; })[0]; playEntity(t); },"
        " openNp: function(){ openNowPlaying(); }, refresh: function(){ refreshMusicLibrary(); },"
        " cur: function(){ return currentStation && currentStation.name; },"
        " playerName: function(){ return document.getElementById('playerName').textContent; } };\n")
_src = open(os.path.join(os.path.dirname(__file__), '..', 'www', 'index.html')).read()
_mark = '  var coverFlow = null;\n'
assert _src.count(_mark) == 1
open(root + '/index.html', 'w').write(_src.replace(_mark, _mark + HOOK))


def ff(*args):
    subprocess.run(['ffmpeg', '-loglevel', 'error', '-y'] + list(args), check=True)


ff('-f', 'lavfi', '-i', 'color=c=orange:s=240x240', '-frames:v', '1', f'{root}/cover.jpg')
M = root + '/Music'
meta = lambda **k: sum([['-metadata', f'{a}={b}'] for a, b in k.items()], [])


def make_library():
    shutil.rmtree(M, ignore_errors=True)
    os.makedirs(f'{M}/Cover Album', exist_ok=True)
    # MP3 ID3v2.4 with an orange front cover
    ff('-f', 'lavfi', '-i', 'sine=frequency=440:duration=6', '-i', f'{root}/cover.jpg', '-map', '0:a', '-map', '1:v',
       '-c:a', 'libmp3lame', '-b:a', '64k', '-c:v', 'copy', '-disposition:v', 'attached_pic', '-id3v2_version', '4',
       *meta(title='Ann One', artist='Ann', album='Cover Album', track='1', genre='Pop', date='2001'), f'{M}/Cover Album/01 One.mp3')
    # MP3 ID3v2.3, no cover
    ff('-f', 'lavfi', '-i', 'sine=frequency=330:duration=6', '-c:a', 'libmp3lame', '-b:a', '64k', '-id3v2_version', '3',
       *meta(title='Ann Two', artist='Ann', album='Cover Album', track='2', genre='Pop', date='2002'), f'{M}/Cover Album/02 Two.mp3')
    # FLAC with the orange picture
    ff('-f', 'lavfi', '-i', 'sine=frequency=660:duration=6', '-i', f'{root}/cover.jpg', '-map', '0:a', '-map', '1:v',
       '-c:a', 'flac', '-c:v', 'copy', '-disposition:v', 'attached_pic',
       *meta(title='Ann Three', artist='Ann', album='Cover Album', track='3', genre='Pop', date='2002'), f'{M}/Cover Album/03 Three.flac')
    # M4A on the same album: read-only, left alone
    ff('-f', 'lavfi', '-i', 'sine=frequency=770:duration=6', '-c:a', 'aac', '-b:a', '64k',
       *meta(title='Ann Four', artist='Ann', album='Cover Album', track='4', genre='Pop', date='2002'), f'{M}/Cover Album/04 Four.m4a')


ff('-f', 'lavfi', '-i', 'color=c=blue:s=300x200', '-frames:v', '1', f'{root}/blue.png')
ff('-f', 'lavfi', '-i', 'color=c=green:s=500x500', '-frames:v', '1', f'{root}/green.png')
ff('-f', 'lavfi', '-i', 'color=c=red:s=600x600', '-frames:v', '1', '-q:v', '2', f'{root}/red.jpg')
make_library()


def audio_md5(p):
    r = subprocess.run(['ffmpeg', '-loglevel', 'error', '-i', p, '-map', '0:a', '-c', 'copy', '-f', 'md5', '-'],
                       capture_output=True, text=True, check=True)
    return r.stdout.strip()


def decodes_clean(p):
    r = subprocess.run(['ffmpeg', '-v', 'error', '-i', p, '-f', 'null', '-'], capture_output=True, text=True)
    return r.returncode == 0 and not r.stderr.strip()


writes = []


class H(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **k):
        super().__init__(*a, directory=root, **k)

    def log_message(self, *a):
        pass

    def end_headers(self):
        self.send_header('Cache-Control', 'no-store')
        super().end_headers()

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        rel = body['uri'].split(f':{PORT}/', 1)[1].replace('%20', ' ')
        path = os.path.join(root, rel)
        data = open(path, 'rb').read()
        head = base64.b64decode(body['data'])
        n = body['replace']
        if len(data) != body['size'] or zlib.crc32(data[:n]) != body['crc']:
            out = {'error': 'CHANGED'}
        else:
            open(path, 'wb').write(head + data[n:])
            st = os.stat(path)
            writes.append({'name': os.path.basename(path), 'replace': n, 'head': len(head), 'inPlace': len(head) == n})
            out = {'size': st.st_size, 'lastModified': int(st.st_mtime * 1000)}
        b = json.dumps(out).encode()
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(b)))
        self.end_headers()
        self.wfile.write(b)


srv = http.server.ThreadingHTTPServer(('127.0.0.1', PORT), H)
threading.Thread(target=srv.serve_forever, daemon=True).start()


def listing():
    files = []
    for dp, _, fs in os.walk(M):
        for f in sorted(fs):
            p = os.path.join(dp, f); rel = os.path.relpath(p, root); st = os.stat(p)
            files.append({'uri': f'http://127.0.0.1:{PORT}/' + rel.replace(' ', '%20'), 'name': f, 'relPath': rel,
                          'type': 'audio/mpeg', 'size': st.st_size, 'lastModified': int(st.st_mtime * 1000)})
    return files


MOCK = """
(function(){
 window.__noWrite = true; window.__grants = 0;
 var listeners = {}, cur = null;
 function emit(n, ev){ (listeners[n] || []).forEach(function(f){ try{ f(ev); }catch(e){} }); }
 function state(playing){ if(cur) setTimeout(function(){ emit('state', { id: cur, state: 'ready', isPlaying: playing, playWhenReady: playing, position: 0, duration: 8 }); }, 20); }
 function err(msg, code){ var e = new Error(msg); e.code = code; return e; }
 var impl = {
   pickMusicFolder: function(){ return Promise.resolve({folder:'Music', treeUri: 'http://127.0.0.1:%d/Music', files: window.__listing, truncated:false}); },
   rescanMusicFolder: function(){ return fetch('/__listing.json', {cache:'no-store'}).then(function(r){ return r.json(); }).then(function(f){ return {folder:'Music', files: f}; }); },
   cacheCheck: function(){ return Promise.resolve({ url: 'file:///cache/x.mp3' }); },
   load: function(o){ cur = o.id; state(!!o.play); return Promise.resolve({}); },
   play: function(){ state(true); return Promise.resolve({}); },
   pause: function(){ state(false); return Promise.resolve({}); },
   writeFileHead: function(o){
     if(window.__noWrite) return Promise.reject(err('no', 'NO_WRITE'));
     return fetch('/__write', { method: 'POST', body: JSON.stringify(o) }).then(function(r){ return r.json(); }).then(function(j){
       if(j.error) throw err('changed', j.error);
       return j;
     });
   },
   grantFolderWrite: function(o){ window.__grants++; window.__grantTree = o.treeUri; window.__noWrite = false; return Promise.resolve({ treeUri: o.treeUri, matches: true, canWrite: true }); },
   addListener: function(n, f){ (listeners[n] = listeners[n] || []).push(f); return Promise.resolve({remove:function(){}}); }
 };
 var P = new Proxy({}, {get:function(t,k){
   if(k==='then') return undefined;
   if(k==='setCarLibraryPart') return undefined;
   if(impl[k]) return impl[k];
   return function(){ return Promise.resolve({}); };
 }});
 window.Capacitor = { isNativePlatform:function(){return true;}, getPlatform:function(){return 'android';},
   registerPlugin:function(){ return P; }, Plugins:{AmplifyPlayer:P, CapacitorHttp: window.__noNativeHttp ? undefined : { request: function(o){
     window.__httpAsked = (window.__httpAsked || []).concat([o.url]);
     var path = '/' + String(o.url).split('/').pop();
     return fetch(path).then(function(r){ return r.blob().then(function(b){ return new Promise(function(res){
       var fr = new FileReader(); fr.onload = function(){ res({ status: r.status, data: String(fr.result).replace(/^data:[^,]*,/, '') }); }; fr.readAsDataURL(b); }); }); });
   } } }, convertFileSrc:function(u){return u;} };
})();
""" % PORT

fails = []
def check(cond, msg):
    print(('PASS ' if cond else 'FAIL ') + msg)
    if not cond: fails.append(msg)


from mutagen.id3 import ID3
from mutagen.flac import FLAC
from mutagen.mp4 import MP4
from PIL import Image
import io

F = lambda n: f'{M}/Cover Album/{n}'


def id3_pics(n):
    return [(f.type, f.mime, Image.open(io.BytesIO(f.data)).size, Image.open(io.BytesIO(f.data)).convert('RGB').getpixel((5, 5))) for f in ID3(F(n)).getall('APIC')]


def flac_pics(n):
    return [(p.type, p.mime, (p.width, p.height), Image.open(io.BytesIO(p.data)).convert('RGB').getpixel((5, 5))) for p in FLAC(F(n)).pictures]


def blueish(px): return px[2] > 180 and px[0] < 80 and px[1] < 80
def greenish(px): return px[1] > 90 and px[0] < 80 and px[2] < 80


SHEET = """(function(){ var o=document.getElementById('tagOverlay'); if(!o.classList.contains('open')) return null;
  var secs=Array.from(document.querySelectorAll('#tagBody .tag-sec')), out={};
  secs.forEach(function(s){ out[s.querySelector('.tag-sec-title').textContent]=Array.from(s.querySelectorAll('.tag-row')).map(function(r){
    var k=r.querySelector('.tag-k'), v=r.querySelector('.tag-v'), i=r.querySelector('.tag-in');
    return { k: k.firstChild ? k.firstChild.textContent : k.textContent, v: i ? i.value : (v ? v.textContent : ''), ph: i ? i.placeholder : '',
      img: !!r.querySelector('img.tag-pic'), btns: Array.from(r.querySelectorAll('.tag-cover-btn')).map(function(b){ return b.textContent; }) }; }); });
  var b=document.getElementById('tagEditBtn');
  return { title: (document.querySelector('.tag-head-title')||{}).textContent, fmt: (document.querySelector('.tag-head-fmt')||{}).textContent, secs: out,
    btn: b.hidden ? null : b.textContent, disabled: b.disabled,
    note: document.getElementById('tagNote').hidden ? '' : document.getElementById('tagNote').textContent,
    editing: document.getElementById('tagPanel').classList.contains('editing') }; })()"""


async def run(p, theme, full):
    make_library()
    open(f'{root}/__listing.json', 'w').write(json.dumps(listing()))
    writes.clear()
    audio_before = {n: audio_md5(F(n)) for n in os.listdir(f'{M}/Cover Album')}
    b = await p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
    ctx = await b.new_context(viewport={'width': 412, 'height': 900}, device_scale_factor=2, is_mobile=True, has_touch=True, color_scheme=theme)
    await ctx.add_init_script(MOCK)
    await ctx.add_init_script('window.__listing = %s;' % json.dumps(listing()))
    await ctx.add_init_script("try{ localStorage.setItem('radioPlayerTheme', %s); }catch(e){}" % json.dumps(theme))
    pg = await ctx.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
    # Like Discogs: the picture is served to an ordinary <img> (the preview), but a page asking
    # to read its pixels (a CORS request) gets nothing it may use.
    async def image_site(route):
        if (route.request.headers.get('sec-fetch-mode') == 'cors') or route.request.headers.get('origin'):
            await route.abort()
        else:
            await route.fulfill(path=f'{root}/red.jpg', content_type='image/jpeg')
    await pg.route('https://i.images.example/**', image_site)
    await pg.goto(f'http://127.0.0.1:{PORT}/index.html'); await pg.wait_for_timeout(2500)
    await pg.evaluate("""(function(){ var ov=document.getElementById('addMusicOverlay'); if(ov) ov.classList.add('open');
      var btn=document.getElementById('addMusicFolderBtn'); btn.disabled=false; btn.click(); })()""")
    for _ in range(60):
        await pg.wait_for_timeout(500)
        if await pg.evaluate('__t.tracks().length') >= 4: break
    await pg.evaluate("(function(){ var ov=document.getElementById('addMusicOverlay'); if(ov) ov.classList.remove('open'); try{ hideImportPanel(); }catch(e){} })()")
    check(await pg.evaluate('__t.tracks().length') == 4, f'[{theme}] library imported')
    sheet = lambda: pg.evaluate(SHEET)
    T = f'[{theme}]'

    # ---------- one song: the cover row, Change, Save ----------
    await pg.evaluate("__t.playSong('Ann One')"); await pg.wait_for_timeout(500)
    await pg.evaluate('__t.openNp()'); await pg.wait_for_timeout(700)
    await pg.evaluate("document.getElementById('npMenuBtn').click()"); await pg.wait_for_timeout(200)
    await pg.evaluate("document.getElementById('npTagsBtn').click()"); await pg.wait_for_timeout(1200)
    s = await sheet()
    cov = [r for r in s['secs']['Tags'] if r['k'] == 'Cover']
    check(cov and cov[0]['img'] and not cov[0]['btns'], f'{T} a song shows the cover in its file {cov}')
    art0 = await pg.evaluate("__t.art('Ann One')")
    await pg.evaluate("document.getElementById('tagEditBtn').click()"); await pg.wait_for_timeout(300)
    s = await sheet()
    cov = [r for r in s['secs']['Tags'] if r['k'] == 'Cover'][0]
    check(cov['btns'] == ['Change', 'Remove'], f'{T} Edit offers Change and Remove {cov["btns"]}')
    await pg.set_input_files('#tagCoverInput', f'{root}/blue.png'); await pg.wait_for_timeout(1200)
    s = await sheet()
    cov = [r for r in s['secs']['Tags'] if r['k'] == 'Cover'][0]
    check(cov['img'] and 'New cover' in cov['v'] and 'Undo' in cov['btns'], f'{T} the new picture shows, waiting for Save {cov}')
    await pg.evaluate("document.querySelector('.tag-body').scrollTop = 0"); await pg.wait_for_timeout(200)
    await pg.screenshot(path=f'{shots}/covers-song-edit-{theme}.png')
    await pg.evaluate("document.getElementById('tagEditBtn').click()"); await pg.wait_for_timeout(1200)
    s = await sheet()
    check('permission' in s['note'], f'{T} first save asks for the folder ({s["note"][:60]})')
    await pg.evaluate("document.querySelector('#tagNote .tag-note-btn').click()"); await pg.wait_for_timeout(2500)
    s = await sheet()
    check(s['note'] == 'Saved to the file.' and not s['editing'], f'{T} saved ({s["note"]})')
    pics = id3_pics('01 One.mp3')
    check(len(pics) == 1 and pics[0][0] == 3 and pics[0][1] == 'image/jpeg' and pics[0][2] == (300, 200) and blueish(pics[0][3]),
          f'{T} the MP3 now has the new front cover, and only it {pics}')
    check(audio_md5(F('01 One.mp3')) == audio_before['01 One.mp3'] and decodes_clean(F('01 One.mp3')), f'{T} audio untouched')
    check(ID3(F('01 One.mp3'))['TIT2'].text[0] == 'Ann One' and ID3(F('01 One.mp3')).version[1] == 4, f'{T} other tags and the v2.4 tag kept')
    art1 = await pg.evaluate("__t.art('Ann One')")
    check(art1['has'] and art1['size'] and art1['size'] != art0['size'], f'{T} Amplify shows the new cover ({art0} -> {art1})')
    # Remove
    await pg.evaluate("document.getElementById('tagEditBtn').click()"); await pg.wait_for_timeout(300)
    await pg.evaluate("Array.from(document.querySelectorAll('.tag-cover-btn')).filter(function(b){ return b.textContent === 'Remove'; })[0].click()"); await pg.wait_for_timeout(300)
    await pg.evaluate("document.getElementById('tagEditBtn').click()"); await pg.wait_for_timeout(2000)
    check(id3_pics('01 One.mp3') == [] and audio_md5(F('01 One.mp3')) == audio_before['01 One.mp3'], f'{T} Remove takes the cover out of the file')
    art2 = await pg.evaluate("__t.art('Ann One')")
    check(not art2['has'] and not art2['size'], f'{T} and Amplify no longer shows it {art2}')
    s = await sheet()
    cov = [r for r in s['secs']['Tags'] if r['k'] == 'Cover'][0]
    check(cov['v'] == 'None' and not cov['img'], f'{T} the sheet says None {cov}')
    await pg.evaluate("document.getElementById('tagCloseBtn').click()"); await pg.wait_for_timeout(300)
    await pg.evaluate("__t.closeNp ? __t.closeNp() : document.querySelector('.np-float .np-back') && document.querySelector('.np-float .np-back').click()"); await pg.wait_for_timeout(500)

    # ---------- the album ----------
    old_key = await pg.evaluate("__t.albumKey('Cover Album')")
    await pg.evaluate(f"__t.setArt('album:{old_key}', 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==')")
    await pg.evaluate("__t.openAlbum('Cover Album')"); await pg.wait_for_timeout(900)
    await pg.evaluate("document.getElementById('albumMenuBtn').click()"); await pg.wait_for_timeout(250)
    vis = await pg.evaluate("!document.getElementById('albumTagsBtn').hidden && getComputedStyle(document.getElementById('albumTagsBtn')).display !== 'none'")
    check(vis, f'{T} the album menu has Info & Tags')
    await pg.screenshot(path=f'{shots}/covers-album-menu-{theme}.png')
    await pg.evaluate("document.getElementById('albumTagsBtn').click()"); await pg.wait_for_timeout(2500)
    s = await sheet()
    rows = {r['k']: r for r in s['secs'].get('Every Song on the Album', [])}
    check(rows.get('Album', {}).get('v') == 'Cover Album' and rows.get('Artist', {}).get('v') == 'Ann' and rows.get('Genre', {}).get('v') == 'Pop',
          f'{T} the album sheet shows the shared tags {[(k, r["v"]) for k, r in rows.items()]}')
    check(rows.get('Year', {}).get('v') == 'Different on each song', f'{T} a field that differs says so ({rows.get("Year")})')
    check(rows.get('Cover', {}).get('img') and 'In 1 of 4 songs' in rows['Cover']['v'], f'{T} the cover row says how many songs have one ({rows.get("Cover")})')
    check(len(s['secs'].get('Songs', [])) == 4 and s['btn'] == 'Edit' and not s['disabled'], f'{T} the songs are listed, Edit offered')
    await pg.screenshot(path=f'{shots}/covers-album-view-{theme}.png')
    await pg.evaluate("document.getElementById('tagEditBtn').click()"); await pg.wait_for_timeout(300)
    s = await sheet()
    rows = {r['k']: r for r in s['secs']['Every Song on the Album']}
    check(rows['Year']['ph'] == 'Varies by song' and rows['Year']['v'] == '', f'{T} in Edit the mixed field is empty with a hint')
    check(rows['Cover']['btns'] == ['Change', 'Use Amplify’s Cover', 'Remove'], f'{T} cover buttons for an album {rows["Cover"]["btns"]}')
    await pg.screenshot(path=f'{shots}/covers-album-edit-{theme}.png')
    if full:
        await pg.fill('.tag-in[data-key="album"]', 'Cover Album Deluxe')
        await pg.fill('.tag-in[data-key="genre"]', 'Soul')
        await pg.set_input_files('#tagCoverInput', f'{root}/green.png'); await pg.wait_for_timeout(1200)
        m4a_before = open(F('04 Four.m4a'), 'rb').read()
        await pg.evaluate("window.__notes = []; new MutationObserver(function(){ window.__notes.push(document.getElementById('tagNote').textContent); }).observe(document.getElementById('tagNote'), { childList: true, subtree: true, characterData: true })")
        await pg.evaluate("document.getElementById('tagEditBtn').click()")
        saw = ''
        for _ in range(40):
            await pg.wait_for_timeout(250)
            s = await sheet()
            if 'Saving' in s['note']: saw = s['note']
            if not s['editing'] and s['btn'] == 'Edit': break
        await pg.wait_for_timeout(800)
        s = await sheet()
        saw = saw or next((x for x in await pg.evaluate('window.__notes') if x.startswith('Saving')), '')
        check(saw.startswith('Saving'), f'{T} saving shows its progress ({saw})')
        check('Changes saved in 3 song files' in s['note'] and '1 song was left' in s['note'], f'{T} the summary ({s["note"]})')
        for n in ('01 One.mp3', '02 Two.mp3'):
            t = ID3(F(n), translate=False)
            pics = id3_pics(n)
            check(t['TALB'].text[0] == 'Cover Album Deluxe' and t['TCON'].text[0] == 'Soul', f'{T} {n}: album and genre written')
            check(len(pics) == 1 and pics[0][0] == 3 and greenish(pics[0][3]) and pics[0][2] == (500, 500), f'{T} {n}: the new front cover {pics}')
            check(audio_md5(F(n)) == audio_before[n] and decodes_clean(F(n)), f'{T} {n}: audio untouched')
        years = [str(ID3(F('01 One.mp3'), translate=False).get('TDRC').text[0]), str(ID3(F('02 Two.mp3'), translate=False).get('TYER').text[0])]
        check(years == ['2001', '2002'], f'{T} the year that differed was left alone {years}')
        fl = FLAC(F('03 Three.flac'))
        fp = flac_pics('03 Three.flac')
        check(fl['album'] == ['Cover Album Deluxe'] and fl['genre'] == ['Soul'] and len(fp) == 1 and fp[0][0] == 3 and greenish(fp[0][3]) and fp[0][2] == (500, 500),
              f'{T} the FLAC: tags and a single new front picture {fp}')
        check(audio_md5(F('03 Three.flac')) == audio_before['03 Three.flac'] and decodes_clean(F('03 Three.flac')), f'{T} the FLAC audio untouched')
        check(open(F('04 Four.m4a'), 'rb').read() == m4a_before, f'{T} the M4A was left alone')
        new_key = await pg.evaluate("__t.albumKey('Cover Album Deluxe')")
        check(await pg.evaluate('__t.albumOpen()') == new_key and await pg.evaluate('__t.heading()') == 'Cover Album Deluxe',
              f'{T} the open album page follows the new name ({await pg.evaluate("__t.heading()")})')
        check(await pg.evaluate(f"__t.getArt('album:{new_key}')") != '' and await pg.evaluate(f"__t.getArt('album:{old_key}')") != '',
              f'{T} the album\'s custom cover goes with it (and stays for the M4A left behind)')
        check(s['title'] == 'Cover Album Deluxe', f'{T} the sheet shows the new name ({s["title"]})')
        await pg.screenshot(path=f'{shots}/covers-album-saved-{theme}.png')
    await pg.evaluate("document.getElementById('tagCloseBtn').click()"); await pg.wait_for_timeout(200)
    await pg.evaluate("document.getElementById('tagCloseBtn').click()"); await pg.wait_for_timeout(300)

    # ---------- Edit Album Cover: Also save in the album's song files ----------
    await pg.evaluate("document.getElementById('albumMenuBtn').click()"); await pg.wait_for_timeout(250)
    await pg.evaluate("document.getElementById('albumArtEditBtn').click()"); await pg.wait_for_timeout(500)
    row = await pg.evaluate("(function(){ var r=document.getElementById('artToFilesRow'); return { shown: !r.hidden && r.getBoundingClientRect().height > 0, text: r.textContent.trim(), on: document.getElementById('artToFilesChk').checked }; })()")
    check(row['shown'] and row['text'] == 'Also save in the album’s song files' and not row['on'], f'{T} the cover dialog offers saving in the files, off at first {row}')
    await pg.set_input_files('#artUrlFileInput', f'{root}/blue.png'); await pg.wait_for_timeout(900)
    await pg.evaluate("document.getElementById('artToFilesChk').click()"); await pg.wait_for_timeout(200)
    await pg.screenshot(path=f'{shots}/covers-dialog-{theme}.png')
    if full:
        await pg.evaluate("window.__an = []; new MutationObserver(function(){ window.__an.push(document.getElementById('artFilesNote').textContent); }).observe(document.getElementById('artFilesNote'), { childList: true, subtree: true, characterData: true })")
        await pg.evaluate("document.getElementById('artUrlSaveBtn').click()")
        saw = ''
        for _ in range(40):
            await pg.wait_for_timeout(250)
            n = await pg.evaluate("document.getElementById('artFilesNote').hidden ? '' : document.getElementById('artFilesNote').textContent")
            if 'Saving' in n: saw = n
            if not await pg.evaluate("document.getElementById('artUrlOverlay').classList.contains('open')"): break
        saw = saw or next((x for x in await pg.evaluate('window.__an') if 'Saving' in x), '')
        check('Saving in the song files' in saw, f'{T} the dialog shows the files being saved ({saw})')
        check(not await pg.evaluate("document.getElementById('artUrlOverlay').classList.contains('open')"), f'{T} and closes when done')
        st = await pg.evaluate("document.getElementById('statusLineText').textContent")
        check('Cover saved in 3 song files' in st, f'{T} the status says what happened ({st.strip()})')
        for n in ('01 One.mp3', '02 Two.mp3'):
            pics = id3_pics(n)
            check(len(pics) == 1 and blueish(pics[0][3]) and pics[0][2] == (300, 200), f'{T} {n}: cover from the dialog {pics}')
        fp = flac_pics('03 Three.flac')
        check(len(fp) == 1 and blueish(fp[0][3]), f'{T} the FLAC too {fp}')
        check(await pg.evaluate("localStorage.getItem('radioPlayerArtToFiles')") == '1', f'{T} the choice is remembered')

        # Build 233 (Mark's Discogs picture): a pasted web address on a site that doesn't let pages
        # copy its pictures. The phone fetches it itself, so it still goes into the files.
        await pg.evaluate("document.getElementById('albumMenuBtn').click()"); await pg.wait_for_timeout(250)
        await pg.evaluate("document.getElementById('albumArtEditBtn').click()"); await pg.wait_for_timeout(500)
        await pg.fill('#artUrlInput', 'https://i.images.example/kY0/red.jpg'); await pg.wait_for_timeout(800)
        prev = await pg.evaluate("document.getElementById('artUrlPreviewImg').naturalWidth")
        check(prev == 600, f'{T} the web picture shows in the preview ({prev})')
        check(await pg.evaluate("document.getElementById('artToFilesChk').checked"), f'{T} saving in the files is still on')
        await pg.evaluate("document.getElementById('artUrlSaveBtn').click()")
        for _ in range(120):
            await pg.wait_for_timeout(250)
            if not await pg.evaluate("document.getElementById('artUrlOverlay').classList.contains('open')"): break
        note = await pg.evaluate("document.getElementById('artFilesNote').hidden ? '' : document.getElementById('artFilesNote').textContent")
        check(not await pg.evaluate("document.getElementById('artUrlOverlay').classList.contains('open')") and not note,
              f'{T} no "couldn\'t be loaded" error; the dialog closes ({note})')
        asked = await pg.evaluate('window.__httpAsked || []')
        check(any('i.images.example' in u for u in asked), f'{T} the phone fetched the picture itself {asked[-1:]}')
        for n in ('01 One.mp3', '02 Two.mp3'):
            pics = id3_pics(n)
            px = pics[0][3] if pics else (0, 0, 0)
            check(len(pics) == 1 and px[0] > 180 and px[1] < 80 and px[2] < 80 and pics[0][2] == (600, 600), f'{T} {n}: the web picture is the cover {pics}')
        fp = flac_pics('03 Three.flac')
        check(len(fp) == 1 and fp[0][3][0] > 180 and fp[0][2] == (600, 600), f'{T} the FLAC too {fp}')
    else:
        await pg.evaluate("document.getElementById('artUrlCloseBtn').click()")
    check(not errs, f'{T} no page errors {errs[:3]}')
    await b.close()


async def big_text(p):
    """Mark's phone: 360 wide, text 35% larger. The album sheet's rows and cover buttons fit."""
    make_library()
    open(f'{root}/__listing.json', 'w').write(json.dumps(listing()))
    b = await p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
    ctx = await b.new_context(viewport={'width': 360, 'height': 780}, device_scale_factor=2, is_mobile=True, has_touch=True, color_scheme='dark')
    await ctx.add_init_script(MOCK)
    await ctx.add_init_script('window.__listing = %s;' % json.dumps(listing()))
    pg = await ctx.new_page()
    await pg.goto(f'http://127.0.0.1:{PORT}/index.html'); await pg.wait_for_timeout(2500)
    await pg.evaluate("""(function(){ var ov=document.getElementById('addMusicOverlay'); if(ov) ov.classList.add('open');
      var btn=document.getElementById('addMusicFolderBtn'); btn.disabled=false; btn.click(); })()""")
    for _ in range(60):
        await pg.wait_for_timeout(500)
        if await pg.evaluate('__t.tracks().length') >= 4: break
    await pg.evaluate("(function(){ var ov=document.getElementById('addMusicOverlay'); if(ov) ov.classList.remove('open'); try{ hideImportPanel(); }catch(e){} })()")
    await pg.evaluate("__t.openAlbum('Cover Album')"); await pg.wait_for_timeout(900)
    await pg.add_style_tag(content='.tag-k{font-size:16.9px !important} .tag-v,.tag-cover-text{font-size:18.2px !important} .tag-in{font-size:18.9px !important} .tag-cover-btn{font-size:16.9px !important} .tag-head-title{font-size:20.3px !important} .tag-head-sub{font-size:17.6px !important}')
    await pg.evaluate("document.getElementById('albumTagsBtn').click()"); await pg.wait_for_timeout(2500)
    await pg.evaluate("document.getElementById('tagEditBtn').click()"); await pg.wait_for_timeout(300)
    fit = await pg.evaluate("""(function(){ var w = document.getElementById('tagPanel').getBoundingClientRect();
      var bad = Array.from(document.querySelectorAll('#tagBody .tag-cover-btn, #tagBody .tag-in')).filter(function(e){ var r = e.getBoundingClientRect(); return r.right > w.right + 1 || r.left < w.left - 1 || (e.classList.contains('tag-cover-btn') && r.height > 44); }).length;
      return { bad: bad, panelRight: w.right }; })()""")
    check(fit['bad'] == 0 and fit['panelRight'] <= 360, f'[big text 360] the album sheet fits {fit}')
    await pg.screenshot(path=f'{shots}/covers-album-bigtext.png')
    await b.close()


async def main():
    async with async_playwright() as p:
        await run(p, 'dark', True)
        await run(p, 'light', False)
        await big_text(p)
    print('ALL PASSED' if not fails else f'FAILED {fails}')

asyncio.run(main())
