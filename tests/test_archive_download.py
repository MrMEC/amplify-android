"""Build 379: Download to Library for archive.org items. An audio item's songs and its cover
are saved into the music folder at Archive.org/<Creator - Title>/ (asking for permission to add
files there first, when needed), with a progress window that can be hidden or cancelled and a
percentage on the item's button; the songs go straight into the library, and tags a file lacks
are filled from archive.org. A film goes into the video folder as Archive.org/<Title (Year)>.mp4.
With two music folders the person picks one once; with none they're asked to add one. Now
Playing's menu offers it for an archive.org item playing. Phone, dark and light.
Run: python3 tests/test_archive_download.py (screenshots in /tmp/claude-0/t/shots)"""
import sys as _nsys, os as _nos; _nsys.path.insert(0, _nos.path.dirname(_nos.path.abspath(__file__)))
import asyncio, os, json, threading, http.server, functools, shutil, subprocess
from playwright.async_api import async_playwright
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = '/tmp/claude-0/t/srv-iadl'; SHOTS = '/tmp/claude-0/t/shots'; PORT = 8881
shutil.rmtree(ROOT, ignore_errors=True); os.makedirs(ROOT + '/files'); os.makedirs(SHOTS, exist_ok=True)
HOOK = "window.__t = { ev: function(js){ return eval(js); } };\n"
src = open(os.path.join(HERE, '..', 'www', 'index.html')).read()
mark = '  var coverFlow = null;\n'; assert src.count(mark) == 1
open(ROOT + '/index.html', 'w').write(src.replace(mark, mark + HOOK))
# The "downloaded" files: song one fully tagged, song two with no tags at all.
def mp3(path, freq, tags):
    cmd = ['ffmpeg', '-loglevel', 'error', '-y', '-f', 'lavfi', '-i', f'sine=frequency={freq}:duration=2', '-c:a', 'libmp3lame', '-b:a', '32k']
    for k, v in tags.items(): cmd += ['-metadata', f'{k}={v}']
    if not tags: cmd += ['-write_id3v2', '0', '-write_xing', '0']
    else: cmd += ['-id3v2_version', '3']
    subprocess.run(cmd + [path], check=True)
mp3(ROOT + '/files/01 - Song One.mp3', 440, {'title': 'Song One', 'artist': 'The Band', 'album': 'Live at the Fillmore', 'track': '1', 'date': '1970'})
mp3(ROOT + '/files/02 - Song Two.mp3', 550, {})
subprocess.run(['ffmpeg', '-loglevel', 'error', '-y', '-f', 'lavfi', '-i', 'color=c=purple:s=300x300', '-frames:v', '1', ROOT + '/files/cover.jpg'], check=True)
H = functools.partial(http.server.SimpleHTTPRequestHandler, directory=ROOT); H.log_message = lambda *a: None
srv = http.server.ThreadingHTTPServer(('127.0.0.1', PORT), H); threading.Thread(target=srv.serve_forever, daemon=True).start()
SIZES = {n: os.path.getsize(ROOT + '/files/' + n) for n in os.listdir(ROOT + '/files')}
META_AUDIO = {'metadata': {'title': 'Live at the Fillmore', 'creator': 'The Band', 'year': '1970'},
  'files': [{'name': '01 - Song One.mp3', 'format': 'VBR MP3', 'title': 'Song One', 'track': '1', 'size': str(SIZES['01 - Song One.mp3']), 'length': '2.0'},
            {'name': '02 - Song Two.mp3', 'format': 'VBR MP3', 'title': 'Song Two', 'track': '2', 'size': str(SIZES['02 - Song Two.mp3']), 'length': '2.0'},
            {'name': '01 - Song One.flac', 'format': 'Flac', 'size': '99999'},
            {'name': 'cover.jpg', 'format': 'JPEG', 'size': str(SIZES['cover.jpg'])},
            {'name': 'band1970_thumb.jpg', 'format': 'JPEG Thumb', 'size': '900'}]}
META_FILM = {'metadata': {'title': 'Night of the Living Dead', 'year': '1968'},
  'files': [{'name': 'night.mp4', 'format': 'h.264', 'size': '5000000', 'length': '5760'}, {'name': 'night.ogv', 'format': 'Ogg Video', 'size': '400'}]}
AUDIO = {'id': 'band1970', 'title': 'Live at the Fillmore', 'creator': 'The Band', 'year': '1970', 'video': False}
FILM = {'id': 'night1968', 'title': 'Night of the Living Dead', 'creator': '', 'year': '1968', 'video': True}
MOCK = """
(function(){
  window.__calls = []; window.__writes = 0; window.__noWrite = %s; window.__grants = 0; window.__slow = 0;
  var listeners = {};
  function emit(n, ev){ (listeners[n] || []).forEach(function(f){ f(ev); }); }
  var impl = {
    downloadToFolder: function(o){
      window.__calls.push(o);
      if(window.__noWrite){ var e = new Error('no'); e.code = 'NO_WRITE'; return Promise.reject(e); }
      var root = o.tree.indexOf('Video') >= 0 ? 'Videos' : 'Music';
      return new Promise(function(res, rej){
        var i = 0, files = [];
        function next(){
          if(window.__cancel){ window.__cancel = false; var e = new Error('Cancelled'); e.code = 'CANCELLED'; rej(e); return; }
          if(i >= o.files.length){ res({ files: files, failed: [], folder: root + '/' + o.path.join('/') }); return; }
          var f = o.files[i];
          emit('folderDownload', { id: o.id, index: i, count: o.files.length, name: f.name, done: Math.round((f.size || 1000) / 2), total: f.size || 1000 });
          setTimeout(function(){
            emit('folderDownload', { id: o.id, index: i, count: o.files.length, name: f.name, done: f.size || 1000, total: f.size || 1000 });
            files.push({ uri: o.tree + '/document/' + encodeURIComponent(o.path.concat([f.name]).join('/')), name: f.name,
              relPath: root + '/' + o.path.join('/') + '/' + f.name, type: /\\.mp3$/.test(f.name) ? 'audio/mpeg' : /\\.jpg$/.test(f.name) ? 'image/jpeg' : 'video/mp4',
              size: f.size || 1000, lastModified: 1700000000000 + i, skipped: false });
            i++; next();
          }, window.__slow || 60);
        }
        next();
      });
    },
    cancelDownload: function(o){ window.__cancel = true; return Promise.resolve(); },
    grantFolderWrite: function(o){ window.__grants++; window.__noWrite = false; return Promise.resolve({ ok: true, matches: true }); },
    writeFileHead: function(o){ window.__writes++; (window.__wl = window.__wl || []).push(decodeURIComponent(o.uri).split('/').pop()); return Promise.resolve({ size: 1, lastModified: 1 }); },
    rescanVideoFolder: function(){ window.__videoRescans = (window.__videoRescans || 0) + 1; return Promise.resolve({ files: [] }); },
    rescanMusicFolder: function(){ return Promise.resolve({ files: [] }); },
    addListener: function(n, f){ (listeners[n] = listeners[n] || []).push(f); return Promise.resolve({ remove: function(){} }); }
  };
  var P = new Proxy({}, { get: function(t, k){ if(k === 'then') return undefined; if(k === 'setCarLibraryPart' || k === 'kvSet' || k === 'kvGetAll') return undefined; if(impl[k]) return impl[k]; return function(){ return Promise.resolve({}); }; } });
  window.Capacitor = { isNativePlatform: function(){ return true; }, getPlatform: function(){ return 'android'; }, registerPlugin: function(){ return P; }, Plugins: { AmplifyPlayer: P },
    convertFileSrc: function(u){ var n = decodeURIComponent(u.split('/document/')[1] || '').split('/').pop(); return 'http://127.0.0.1:%d/files/' + encodeURIComponent(n); } };
})();
"""
fails = []
def check(ok, msg):
    print(('PASS ' if ok else 'FAIL ') + msg)
    if not ok: fails.append(msg)
async def page(B, theme, folders, video_folders=None, no_write=False):
    c = await B.new_context(viewport={'width': 390, 'height': 844}, device_scale_factor=2, is_mobile=True, has_touch=True, color_scheme=theme)
    await c.add_init_script(MOCK % ('true' if no_write else 'false', PORT))
    await c.add_init_script("if(!sessionStorage.getItem('s')){ sessionStorage.setItem('s','1'); localStorage.setItem('radioPlayerMusicFolders', %s); localStorage.setItem('radioPlayerVideoFolders', %s); localStorage.setItem('radioPlayerTourDone', '1'); }"
                            % (json.dumps(json.dumps(folders)), json.dumps(json.dumps(video_folders or []))))
    async def meta(route):
        u = route.request.url
        await route.fulfill(status=200, content_type='application/json', headers={'Access-Control-Allow-Origin': '*'}, body=json.dumps(META_FILM if 'night1968' in u else META_AUDIO))
    await c.route('https://archive.org/**', lambda r: r.fulfill(status=200, body=b''))
    await c.route('https://archive.org/metadata/**', meta)
    pg = await c.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
    await pg.goto(f'http://127.0.0.1:{PORT}/index.html'); await pg.wait_for_timeout(2500)
    # close anything that came up at start (offline messages)
    await pg.evaluate("document.getElementById('noticeOverlay').classList.remove('open')")
    # two result rows on the page, as Search shows them
    await pg.evaluate("(its)=>{ var g = document.getElementById('stationsGrid'); g.innerHTML = ''; its.forEach(function(it){ g.appendChild(__t.ev('buildArchiveResultRow')(it)); }); }", [AUDIO, FILM])
    return c, pg, errs
async def notice(pg):
    return await pg.evaluate("[document.getElementById('noticeOverlay').classList.contains('open'), document.getElementById('noticeTitle').textContent, document.getElementById('noticeMsg').textContent, Array.prototype.map.call(document.querySelectorAll('#noticeActions button'), function(b){ return b.textContent; })]")
async def act(pg, label):
    await pg.evaluate("(l)=>Array.prototype.filter.call(document.querySelectorAll('#noticeActions button'), function(b){ return b.textContent === l; })[0].click()", label)
async def run(B, theme):
    T = f'[{theme}]'
    MUS = [{'treeUri': 'content://tree/Music', 'name': 'Music'}]
    c, pg, errs = await page(B, theme, MUS, [{'treeUri': 'content://tree/Videos', 'name': 'Videos'}], no_write=True)
    await pg.evaluate("document.querySelector('.archive-result-row .ia-more-btn').click()"); await pg.wait_for_timeout(200)
    btns = await pg.evaluate("Array.prototype.map.call(document.querySelectorAll('.ia-row-menu .np-menu-item'), function(b){ return b.textContent; })")
    badge = await pg.evaluate("getComputedStyle(document.querySelector('.archive-result-row .ia-dl-badge')).display")
    check(btns == ['Play Next', 'Add to Queue', 'Download'] and badge == 'none', f'{T} each archive.org result has a More menu: Play Next, Add to Queue, Download (no arrow until it downloads) {btns} {badge}')
    await pg.screenshot(path=f'{SHOTS}/iadl-{theme}-menu.png')
    await pg.evaluate("document.body.click()"); await pg.wait_for_timeout(150)
    await pg.screenshot(path=f'{SHOTS}/iadl-{theme}-rows.png', clip={'x': 0, 'y': 0, 'width': 390, 'height': 360})
    # no permission to add files yet: asked, then it goes ahead
    await pg.evaluate("window.__slow = 250; document.querySelector('.archive-result-row .ia-more-btn').click(); document.getElementById('iaMenuDl').click()"); await pg.wait_for_timeout(500)
    n = await notice(pg)
    check(n[1] == 'Allow Amplify to save here' and n[3] == ['Not Now', 'Allow'], f'{T} without permission it asks for it {n[1]!r} {n[3]}')
    await act(pg, 'Allow'); await pg.wait_for_timeout(350)
    n = await notice(pg)
    pct = await pg.evaluate("document.querySelector('.archive-result-row .ia-dl').textContent")
    check(n[1] == 'Downloading to your library' and 'Live at the Fillmore' in n[2] and n[3] == ['Cancel', 'Hide'] and pct.endswith('%'), f'{T} then downloads, with progress, Cancel and Hide; the button counts {n[1]!r} {n[2]!r} {pct!r}')
    await pg.screenshot(path=f'{SHOTS}/iadl-{theme}-progress.png')
    await act(pg, 'Hide'); await pg.wait_for_timeout(2500)
    call = await pg.evaluate("window.__calls[window.__calls.length - 1]")
    check(call['tree'] == 'content://tree/Music' and call['path'] == ['Archive.org', 'The Band - Live at the Fillmore'], f'{T} into Music/Archive.org/The Band - Live at the Fillmore {call["path"]}')
    names = [f['name'] for f in call['files']]
    check(names == ['01 - Song One.mp3', '02 - Song Two.mp3', 'cover.jpg'] and call['files'][0]['url'].endswith('/download/band1970/01%20-%20Song%20One.mp3'), f'{T} the songs (one format) and the cover, sizes known {names}')
    lib = await pg.evaluate("__t.ev('libraryTracks').map(function(t){ return [t.name, t.artist, t.album, !!t.srcUri]; })")
    check(len(lib) == 2 and ['Song One', 'The Band', 'Live at the Fillmore', True] in lib, f'{T} both songs are in the library now {lib}')
    w = await pg.evaluate("window.__writes")
    check(w == 1, f'{T} the untagged song gets its tags from archive.org, the tagged one is left alone ({w} written)')
    st = await pg.evaluate("[document.querySelector('.archive-result-row .ia-dl').classList.contains('done'), document.querySelector('.archive-result-row .ia-dl').getAttribute('aria-label')]")
    check(st == [True, 'Downloaded to your library'], f'{T} the button shows it is done {st}')
    await pg.evaluate("document.getElementById('noticeOverlay').classList.remove('open'); document.getElementById('importOverlay').classList.remove('open')")
    await pg.screenshot(path=f'{SHOTS}/iadl-{theme}-done.png', clip={'x': 0, 'y': 0, 'width': 390, 'height': 360})
    # a film goes into the video folder, named as a movie
    await pg.evaluate("document.querySelectorAll('.archive-result-row .ia-more-btn')[1].click(); document.getElementById('iaMenuDl').click()"); await pg.wait_for_timeout(1200)
    call = await pg.evaluate("window.__calls[window.__calls.length - 1]")
    check(call['tree'] == 'content://tree/Videos' and call['path'] == ['Archive.org'] and [f['name'] for f in call['files']] == ['Night of the Living Dead (1968).mp4'], f'{T} a film -> Videos/Archive.org/Night of the Living Dead (1968).mp4 {call["path"]} {[f["name"] for f in call["files"]]}')
    await pg.wait_for_timeout(600)
    n = await notice(pg); vr = await pg.evaluate("window.__videoRescans || 0")
    check(n[1] == 'Downloaded' and 'Watch' in n[2] and vr >= 1, f'{T} and Watch looks again {n[1]!r} {n[2]!r} rescans={vr}')
    # cancel
    await pg.evaluate("__t.ev('delete archiveDl.band1970'); window.__slow = 400; document.querySelector('.archive-result-row .ia-more-btn').click(); document.getElementById('iaMenuDl').click()"); await pg.wait_for_timeout(500)
    await act(pg, 'Cancel'); await pg.wait_for_timeout(1200)
    n = await notice(pg); lbl = await pg.evaluate("document.querySelector('.archive-result-row .ia-dl').getAttribute('aria-label')")
    check('cancelled' in n[2] and lbl == 'Download to Library', f'{T} Cancel stops it and the button resets {n[2]!r} {lbl!r}')
    # Now Playing's menu offers it for an archive.org item
    await pg.evaluate("__t.ev('currentStation = { type: \"podcast\", guid: \"ia:band1970/01 - Song One.mp3\", name: \"Song One\", collectionName: \"Live at the Fillmore\", artistName: \"The Band\", episodeUrl: \"x\" }; toggleNpMenu()')")
    vis = await pg.evaluate("getComputedStyle(document.getElementById('npArchiveDlBtn')).display")
    await pg.evaluate("__t.ev('closeNpMenu(); currentStation = { name: \"Jazz FM\", urlToResolve: \"http://x\" }; toggleNpMenu()')")
    vis2 = await pg.evaluate("getComputedStyle(document.getElementById('npArchiveDlBtn')).display")
    check(vis != 'none' and vis2 == 'none', f'{T} Now Playing menu: Download to Library only for an archive.org item {vis} {vis2}')
    check(not errs, f'{T} no page errors {errs}')
    await c.close()
    # two music folders: picked once, then kept
    c, pg, errs = await page(B, theme, MUS + [{'treeUri': 'content://tree/Phone%20Music', 'name': 'Phone Music'}])
    await pg.evaluate("document.querySelector('.archive-result-row .ia-more-btn').click(); document.getElementById('iaMenuDl').click()"); await pg.wait_for_timeout(500)
    n = await notice(pg); opts = await pg.evaluate("Array.prototype.map.call(document.querySelectorAll('#noticeMsg .bk-file-name'), function(e){ return e.textContent; })")
    check(n[1] == 'Download to' and opts == ['Music', 'Phone Music'], f'{T} two music folders: which one? {opts}')
    await pg.screenshot(path=f'{SHOTS}/iadl-{theme}-pick.png')
    await pg.evaluate("document.querySelectorAll('#noticeMsg .bk-file')[1].click()"); await pg.wait_for_timeout(1500)
    call = await pg.evaluate("window.__calls[0]"); kept = await pg.evaluate("JSON.parse(localStorage.getItem('radioPlayerArchiveDownloads'))")
    check(call['tree'] == 'content://tree/Phone%20Music' and kept.get('music') == 'content://tree/Phone%20Music', f'{T} goes there, and it is kept {kept}')
    await c.close()
    # no music folder: asked to add one
    c, pg, errs = await page(B, theme, [])
    await pg.evaluate("document.querySelector('.archive-result-row .ia-more-btn').click(); document.getElementById('iaMenuDl').click()"); await pg.wait_for_timeout(500)
    n = await notice(pg)
    check(n[1] == 'Add a music folder first' and n[3] == ['Not Now', 'Add Music Folder'], f'{T} no music folder: add one first {n[1]!r} {n[3]}')
    await c.close()
async def main():
    async with async_playwright() as p:
        B = await p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
        for th in ('dark', 'light'): await run(B, th)
        await B.close()
    print('ALL PASSED' if not fails else f'FAILS {len(fails)}')
asyncio.run(main())
