"""Info & Tags: the Now Playing menu shows it for library songs only; the sheet lists every tag
in the file; Edit/Save writes the changed tags into the file itself (only the tag area at the
front, the audio untouched), and the library, Now Playing and a later refresh all follow.
The mocked native plugin hands writes to this test's server, which applies them exactly like
TagWriter.java does (CRC check of the old tag, then replace the first N bytes).
Run: python3 tests/test_tag_editor.py (screenshots in /tmp/claude-0/t/shots)"""
import asyncio, os, json, threading, http.server, functools, shutil, subprocess, base64, zlib, hashlib
from playwright.async_api import async_playwright
from mutagen.id3 import ID3
from mutagen.flac import FLAC

PORT = 8791
root = '/tmp/claude-0/t/srv_tags'
shots = '/tmp/claude-0/t/shots'
os.makedirs(shots, exist_ok=True)
shutil.rmtree(root, ignore_errors=True)
os.makedirs(root)
HOOK = ("window.__t = { tracks: function(){ return libraryTracks; }, runLibrarySection: runLibrarySection,"
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
os.makedirs(f'{M}/Album', exist_ok=True)
meta = lambda **k: sum([['-metadata', f'{a}={b}'] for a, b in k.items()], [])
# MP3 with ID3v2.4, a comment and an embedded cover
ff('-f', 'lavfi', '-i', 'sine=frequency=440:duration=8', '-i', f'{root}/cover.jpg', '-map', '0:a', '-map', '1:v',
   '-c:a', 'libmp3lame', '-b:a', '64k', '-c:v', 'copy', '-disposition:v', 'attached_pic', '-id3v2_version', '4',
   *meta(title='Alpha Song', artist='Old Artist', album='First Album', track='1/9', genre='Rock', comment='hello', date='1999'),
   f'{M}/Album/01 Alpha.mp3')
# MP3 with ID3v2.3
ff('-f', 'lavfi', '-i', 'sine=frequency=330:duration=8', '-c:a', 'libmp3lame', '-b:a', '64k', '-id3v2_version', '3',
   *meta(title='Bravo Song', artist='Bravo', album='First Album', track='2'), f'{M}/Album/02 Bravo.mp3')
# MP3 with no tag at all
ff('-f', 'lavfi', '-i', 'sine=frequency=550:duration=8', '-c:a', 'libmp3lame', '-b:a', '64k', '-id3v2_version', '0',
   '-map_metadata', '-1', f'{M}/Album/03 Charlie.mp3')
# FLAC with Vorbis comments and a picture
ff('-f', 'lavfi', '-i', 'sine=frequency=660:duration=8', '-i', f'{root}/cover.jpg', '-map', '0:a', '-map', '1:v',
   '-c:a', 'flac', '-c:v', 'copy', '-disposition:v', 'attached_pic',
   *meta(title='Delta Song', artist='Delta', album='Flac Album', track='4', genre='Jazz', ISRC='USX123'), f'{M}/Album/04 Delta.flac')
# M4A: read-only
ff('-f', 'lavfi', '-i', 'sine=frequency=770:duration=8', '-c:a', 'aac', '-b:a', '64k',
   *meta(title='Echo Song', artist='Echo', album='M4A Album'), f'{M}/Album/05 Echo.m4a')


def audio_md5(p):
    r = subprocess.run(['ffmpeg', '-loglevel', 'error', '-i', p, '-map', '0:a', '-c', 'copy', '-f', 'md5', '-'],
                       capture_output=True, text=True, check=True)
    return r.stdout.strip()


def decodes_clean(p):
    r = subprocess.run(['ffmpeg', '-v', 'error', '-i', p, '-f', 'null', '-'], capture_output=True, text=True)
    return r.returncode == 0 and not r.stderr.strip()


AUDIO_BEFORE = {n: audio_md5(f'{M}/Album/{n}') for n in os.listdir(f'{M}/Album')}
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
   registerPlugin:function(){ return P; }, Plugins:{AmplifyPlayer:P}, convertFileSrc:function(u){return u;} };
})();
""" % PORT

fails = []
def check(cond, msg):
    print(('PASS ' if cond else 'FAIL ') + msg)
    if not cond: fails.append(msg)


SHEET = """(function(){ var o=document.getElementById('tagOverlay'); if(!o.classList.contains('open')) return null;
  function rows(sec){ return Array.from(sec.querySelectorAll('.tag-row')).map(function(r){
    var k=r.querySelector('.tag-k'), v=r.querySelector('.tag-v'), i=r.querySelector('.tag-in');
    return [k.firstChild ? k.firstChild.textContent : k.textContent, i ? i.value : (v ? v.textContent : ''), r.querySelector('.tag-id') ? r.querySelector('.tag-id').textContent : '', !!r.querySelector('img.tag-pic')]; }); }
  var secs=Array.from(document.querySelectorAll('#tagBody .tag-sec')), out={};
  secs.forEach(function(s){ out[s.querySelector('.tag-sec-title').textContent]=rows(s); });
  var b=document.getElementById('tagEditBtn');
  return { fmt: (document.querySelector('.tag-head-fmt')||{}).textContent, secs: out, btn: b.hidden ? null : b.textContent,
    btnDisabled: b.disabled, note: document.getElementById('tagNote').hidden ? '' : document.getElementById('tagNote').textContent,
    editing: document.getElementById('tagPanel').classList.contains('editing') }; })()"""


async def main():
    open(f'{root}/__listing.json', 'w').write(json.dumps(listing()))
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
        ctx = await b.new_context(viewport={'width': 390, 'height': 844}, device_scale_factor=2, is_mobile=True, has_touch=True, color_scheme='dark')
        await ctx.add_init_script(MOCK)
        await ctx.add_init_script('window.__listing = %s;' % json.dumps(listing()))
        pg = await ctx.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e))); pg.on('console', lambda m: print('CONSOLE', m.text) if m.type in ('error','warning') else None)
        await pg.goto(f'http://127.0.0.1:{PORT}/index.html'); await pg.wait_for_timeout(2500)
        await pg.evaluate("""(function(){ var ov=document.getElementById('addMusicOverlay'); if(ov) ov.classList.add('open');
          var btn=document.getElementById('addMusicFolderBtn'); btn.disabled=false; btn.click(); })()""")
        for _ in range(60):
            await pg.wait_for_timeout(500)
            if await pg.evaluate('__t.tracks().length') >= 5: break
        names = sorted(await pg.evaluate('__t.tracks().map(function(t){ return t.name; })'))
        check(len(names) == 5, f'library imported {names}')
        sheet = lambda: pg.evaluate(SHEET)

        async def open_np(title):
            await pg.evaluate(f"__t.playSong({json.dumps(title)})"); await pg.wait_for_timeout(500)
            await pg.evaluate('__t.openNp()'); await pg.wait_for_timeout(700)

        async def open_tags():
            await pg.evaluate("document.getElementById('npMenuBtn').click()"); await pg.wait_for_timeout(200)
            vis = await pg.evaluate("getComputedStyle(document.getElementById('npTagsBtn')).display !== 'none'")
            if vis:
                await pg.evaluate("document.getElementById('npTagsBtn').click()")
                await pg.wait_for_timeout(900)
            return vis

        # ---- MP3, ID3v2.4: view everything ----
        await open_np('Alpha Song')
        check(await open_tags(), 'Info & Tags is in the Now Playing menu for a library song')
        s = await sheet()
        print(json.dumps(s, indent=1)[:2500])
        check(s and s['fmt'] == 'MP3 · ID3v2.4', f"format shown {s and s['fmt']}")
        tags = dict((r[0], r[1]) for r in s['secs']['Tags'])
        check(tags['Title'] == 'Alpha Song' and tags['Artist'] == 'Old Artist' and tags['Album'] == 'First Album'
              and tags['Track'] == '1/9' and tags['Genre'] == 'Rock' and tags['Year'] == '1999',
              f'common fields read from the file {tags}')
        allrows = s['secs']['Everything in the file']
        ids = [r[2] or r[0] for r in allrows]
        check({'TIT2', 'TPE1', 'TALB', 'TRCK', 'TCON', 'TDRC', 'TSSE'} <= set(ids), f'every frame listed with its ID {ids}')
        check(any(r[3] for r in allrows), 'embedded picture shown as an image')
        check(s['btn'] == 'Edit' and not s['btnDisabled'], 'Edit button top right')
        check('File' in s['secs'] and any(r[0] == 'Bitrate' for r in s['secs']['File']), 'file details listed')
        await pg.screenshot(path=f'{shots}/tags-view.png')
        hdr = await pg.evaluate("""(function(){ var b=document.getElementById('tagEditBtn').getBoundingClientRect(), p=document.getElementById('tagPanel').getBoundingClientRect();
          return {right: Math.round(p.right-b.right), top: Math.round(b.top-p.top)}; })()""")
        check(hdr['right'] <= 20 and hdr['top'] <= 24, f'Edit sits at the top right of the sheet {hdr}')

        # ---- edit and save: first attempt asks for folder permission ----
        await pg.evaluate("document.getElementById('tagEditBtn').click()"); await pg.wait_for_timeout(300)
        s = await sheet()
        check(s['editing'] and s['btn'] == 'Save', 'Edit turns into Save with fields to type in')
        check(await pg.evaluate("document.querySelectorAll('#tagBody .tag-in').length") == 11, 'all 11 fields editable')
        await pg.screenshot(path=f'{shots}/tags-edit.png')

        async def set_field(key, val):
            await pg.evaluate(f"(function(){{ var i=document.querySelector('#tagBody .tag-in[data-key={key}]'); i.value={json.dumps(val)}; i.dispatchEvent(new Event('input')); }})()")
        await set_field('title', 'Alpha Song (Remastered)')
        await set_field('artist', 'Néw Ärtist 新')
        await set_field('track', '3 / 12')
        await set_field('composer', 'Someone')
        await set_field('comment', '')
        await pg.evaluate("document.getElementById('tagEditBtn').click()"); await pg.wait_for_timeout(800)
        s = await sheet()
        check('permission' in s['note'] and s['editing'], f'first save asks for permission to change the folder ({s["note"]})')
        check(not writes, 'nothing written without permission')
        await pg.screenshot(path=f'{shots}/tags-permission.png')
        await pg.evaluate("document.querySelector('#tagNote .tag-note-btn').click()"); await pg.wait_for_timeout(1500)
        check(await pg.evaluate('window.__grants') == 1 and await pg.evaluate('window.__grantTree') == f'http://127.0.0.1:{PORT}/Music',
              'Allow asks Android for that folder')
        s = await sheet()
        check(not s['editing'] and 'Saved' in s['note'], f'saved after permission given ({s["note"]})')
        check(len(writes) == 1 and writes[0]['name'] == '01 Alpha.mp3', f'one write to the file {writes}')
        check(not writes[0]['inPlace'] and writes[0]['head'] >= writes[0]['replace'] + 2048,
              f'first save outgrows the unpadded tag: file rewritten with room to spare {writes}')
        f = f'{M}/Album/01 Alpha.mp3'
        t = ID3(f)
        check(t.version[1] == 4, f'still ID3v2.4 {t.version}')
        check(str(t['TIT2']) == 'Alpha Song (Remastered)' and str(t['TPE1']) == 'Néw Ärtist 新' and str(t['TRCK']) == '3/12'
              and str(t['TCOM']) == 'Someone', f"file has the new tags {t.pprint()[:400]}")
        check(not t.getall('COMM::eng') and not [c for c in t.getall('COMM') if not c.desc], 'emptied comment removed')
        check(str(t['TALB']) == 'First Album' and t.getall('APIC') and str(t['TCON']) == 'Rock', 'untouched tags kept, picture too')
        check(audio_md5(f) == AUDIO_BEFORE['01 Alpha.mp3'] and decodes_clean(f), 'audio identical and decodes cleanly')
        tags = dict((r[0], r[1]) for r in s['secs']['Tags'])
        check(tags['Title'] == 'Alpha Song (Remastered)' and tags['Comment'] == '—', f'sheet shows what was saved {tags}')
        await pg.screenshot(path=f'{shots}/tags-saved.png')

        # The library, the player bar and Now Playing follow
        tr = await pg.evaluate("__t.tracks().filter(function(t){ return /Alpha/.test(t.name); }).map(function(t){ return [t.name, t.artist, t.trackNo, t.localId, t.diskSize]; })")
        check(len(tr) == 1 and tr[0][0] == 'Alpha Song (Remastered)' and tr[0][1] == 'Néw Ärtist 新' and tr[0][2] == 3, f'library song updated {tr}')
        check(await pg.evaluate('__t.playerName()') == 'Alpha Song (Remastered)', 'player bar shows the new title')
        np_name = await pg.evaluate("document.getElementById('npName').textContent")
        check('Remastered' in np_name, f'Now Playing shows the new title ({np_name})')
        # A second edit fits the room left last time: only the tag bytes are rewritten.
        await pg.evaluate("document.getElementById('tagEditBtn').click()"); await pg.wait_for_timeout(200)
        await set_field('genre', 'Alternative')
        await pg.evaluate("document.getElementById('tagEditBtn').click()"); await pg.wait_for_timeout(1500)
        check(len(writes) == 2 and writes[1]['inPlace'] and str(ID3(f)['TCON']) == 'Alternative', f'second save written in place {writes}')
        check(audio_md5(f) == AUDIO_BEFORE['01 Alpha.mp3'] and decodes_clean(f), 'audio still identical')
        await pg.evaluate("document.getElementById('tagCloseBtn').click()"); await pg.wait_for_timeout(300)
        check(await sheet() is None, 'close shuts the sheet')

        # ---- MP3 v2.3: grows past its space, so the file is rewritten ----
        await open_np('Bravo Song'); await open_tags()
        s = await sheet()
        check(s['fmt'] == 'MP3 · ID3v2.3', f"v2.3 shown {s['fmt']}")
        await pg.evaluate("document.getElementById('tagEditBtn').click()"); await pg.wait_for_timeout(200)
        await set_field('lyrics', 'Line one\nLine two\n' + 'la ' * 900)
        await set_field('album', 'Second Album')
        await pg.evaluate("document.getElementById('tagEditBtn').click()"); await pg.wait_for_timeout(1500)
        f = f'{M}/Album/02 Bravo.mp3'
        t = ID3(f)
        check(t.version[1] == 3 and str(t['TALB']) == 'Second Album' and t.getall('USLT') and t.getall('USLT')[0].text.startswith('Line one\nLine two'),
              'v2.3 saved with lyrics and new album')
        check(writes[-1]['name'] == '02 Bravo.mp3' and not writes[-1]['inPlace'], f'bigger tag: file rewritten {writes[-1]}')
        check(audio_md5(f) == AUDIO_BEFORE['02 Bravo.mp3'] and decodes_clean(f), 'audio identical after rewrite')
        # cancel discards edits
        await pg.evaluate("document.getElementById('tagEditBtn').click()"); await pg.wait_for_timeout(200)
        await set_field('title', 'Should Not Save')
        await pg.evaluate("document.getElementById('tagOverlay').click()"); await pg.wait_for_timeout(200)
        check((await sheet())['editing'], 'a tap outside while editing does not close or lose edits')
        await pg.evaluate("document.getElementById('tagCloseBtn').click()"); await pg.wait_for_timeout(200)
        s = await sheet()
        check(s and not s['editing'] and dict((r[0], r[1]) for r in s['secs']['Tags'])['Title'] == 'Bravo Song', 'X while editing cancels the edits')
        n = len(writes)
        await pg.evaluate("document.getElementById('tagEditBtn').click()"); await pg.wait_for_timeout(200)
        await set_field('track', 'two')
        await pg.evaluate("document.getElementById('tagEditBtn').click()"); await pg.wait_for_timeout(300)
        s = await sheet()
        check(s['editing'] and 'number' in s['note'] and len(writes) == n, f'bad track number is caught ({s["note"]})')
        await pg.evaluate("document.getElementById('tagCloseBtn').click()"); await pg.wait_for_timeout(100)
        await pg.evaluate("document.getElementById('tagCloseBtn').click()"); await pg.wait_for_timeout(200)

        # ---- MP3 with no tag: a new ID3v2.3 tag is added ----
        await open_np('Charlie'); await open_tags()
        s = await sheet()
        check(s['fmt'] == 'MP3 · no ID3v2 tag' and s['btn'] == 'Edit', f"untagged MP3 can be tagged {s['fmt']}")
        await pg.evaluate("document.getElementById('tagEditBtn').click()"); await pg.wait_for_timeout(200)
        await set_field('title', 'Charlie Song'); await set_field('artist', 'Chärlie 新'); await set_field('year', '2024'); await set_field('comment', 'Ünïcode — comment')
        await pg.evaluate("document.getElementById('tagEditBtn').click()"); await pg.wait_for_timeout(1500)
        f = f'{M}/Album/03 Charlie.mp3'
        t = ID3(f, translate=False)
        check(t.version[1] == 3 and str(t['TIT2']) == 'Charlie Song' and str(t['TYER']) == '2024' and str(t['TPE1']) == 'Chärlie 新' and str(t.getall('COMM')[0]) == 'Ünïcode — comment', f'new tag written {t.pprint()}')
        check(audio_md5(f) == AUDIO_BEFORE['03 Charlie.mp3'] and decodes_clean(f), 'audio identical after adding a tag')
        await pg.evaluate("document.getElementById('tagCloseBtn').click()"); await pg.wait_for_timeout(200)

        # ---- FLAC ----
        await open_np('Delta Song'); await open_tags()
        s = await sheet()
        check(s['fmt'] == 'FLAC · Vorbis comments', f"FLAC shown {s['fmt']}")
        allrows = s['secs']['Everything in the file']
        check(any(r[2] == 'ISRC' or r[0] == 'ISRC' for r in allrows) and any(r[3] for r in allrows), f'all comments and the picture listed {allrows}')
        check(any(r[0] == 'Audio' and 'Hz' in r[1] for r in s['secs']['File']), 'FLAC audio details listed')
        await pg.evaluate("document.getElementById('tagEditBtn').click()"); await pg.wait_for_timeout(200)
        await set_field('artist', 'Delta Quartet'); await set_field('track', '4/10'); await set_field('genre', '')
        await pg.evaluate("document.getElementById('tagEditBtn').click()"); await pg.wait_for_timeout(1500)
        f = f'{M}/Album/04 Delta.flac'
        fl = FLAC(f)
        check(fl['artist'] == ['Delta Quartet'] and fl['tracknumber'] == ['4'] and fl['tracktotal'] == ['10'] and 'genre' not in fl
              and fl['isrc'] == ['USX123'] and len(fl.pictures) == 1, f'FLAC saved {dict(fl)}')
        check(audio_md5(f) == AUDIO_BEFORE['04 Delta.flac'] and decodes_clean(f), 'FLAC audio identical')
        check(writes[-1]['inPlace'], f'FLAC padding used: written in place {writes[-1]}')
        await pg.evaluate("document.getElementById('tagCloseBtn').click()"); await pg.wait_for_timeout(200)

        # ---- M4A: view only ----
        await open_np('Echo Song'); await open_tags()
        s = await sheet()
        tags = dict((r[0], r[1]) for r in s['secs']['Tags'])
        check(s['fmt'].startswith('M4A') and s['btnDisabled'] and 'MP3 and FLAC' in s['note'] and tags['Title'] == 'Echo Song',
              f"M4A shown read-only {s['fmt']} {s['note']}")
        await pg.screenshot(path=f'{shots}/tags-m4a.png')
        await pg.evaluate("document.getElementById('tagCloseBtn').click()"); await pg.wait_for_timeout(200)

        # ---- a file changed meanwhile is never overwritten ----
        await open_np('Bravo Song'); await open_tags()
        await pg.evaluate("document.getElementById('tagEditBtn').click()"); await pg.wait_for_timeout(200)
        f = f'{M}/Album/02 Bravo.mp3'
        data = open(f, 'rb').read(); before = hashlib.md5(data).hexdigest()
        open(f, 'wb').write(data[:20] + b'X' + data[21:])
        await set_field('title', 'Clobber')
        await pg.evaluate("document.getElementById('tagEditBtn').click()"); await pg.wait_for_timeout(1200)
        s = await sheet()
        check('changed' in s['note'] and hashlib.md5(open(f, 'rb').read()).hexdigest() != before and b'Clobber' not in open(f, 'rb').read(),
              f'changed file left alone ({s["note"]})')
        open(f, 'wb').write(data)
        await pg.evaluate("document.getElementById('tagCloseBtn').click()"); await pg.wait_for_timeout(100)
        await pg.evaluate("document.getElementById('tagCloseBtn').click()"); await pg.wait_for_timeout(200)

        # ---- refresh keeps the edited songs as they are (no duplicates) ----
        open(f'{root}/__listing.json', 'w').write(json.dumps(listing()))
        await pg.evaluate('__t.refresh()'); await pg.wait_for_timeout(4000)
        names = sorted(await pg.evaluate('__t.tracks().map(function(t){ return t.name; })'))
        check(names == ['Alpha Song (Remastered)', 'Bravo Song', 'Charlie Song', 'Delta Song', 'Echo Song'], f'refresh adds no duplicates {names}')
        check(not errs, f'no page errors {errs[:3]}')
        await b.close()
    print('ALL PASSED' if not fails else f'FAILED {fails}')

asyncio.run(main())
