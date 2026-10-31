"""Build 356: Library Cleanup (Settings > Library). A library of real MP3s: tagged songs with a
large cover, an album with a 300px cover, an album with no cover and no year/genre, and two
untagged files. Cleanup lists each in its group, tapping opens the right fix (Info & Tags, album
Info & Tags, the album cover dialog with suggestions), back steps Cleanup > Library > Settings.
Phone, dark and light. Run: python3 tests/test_library_cleanup.py (screenshots in /tmp/claude-0/t/shots)"""
import sys as _nsys, os as _nos; _nsys.path.insert(0, _nos.path.dirname(_nos.path.abspath(__file__))); from notice_auto import AUTO_NOTICE
import asyncio, os, json, threading, http.server, functools, shutil, subprocess
from playwright.async_api import async_playwright

PORT = 8872
root = '/tmp/claude-0/t/srv_cleanup'
shots = '/tmp/claude-0/t/shots'
os.makedirs(shots, exist_ok=True)
shutil.rmtree(root, ignore_errors=True); os.makedirs(root)
HOOK = "window.__t = { n: function(){ return libraryTracks.length; }, set: function(c){ openSettings(c); } };\n"
_src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'www', 'index.html')).read()
_mark = '  var coverFlow = null;\n'
assert _src.count(_mark) == 1
open(root + '/index.html', 'w').write(_src.replace(_mark, _mark + HOOK))

def ff(*a): subprocess.run(['ffmpeg', '-loglevel', 'error', '-y'] + list(a), check=True)
M = root + '/Music'
os.makedirs(M, exist_ok=True)
ff('-f', 'lavfi', '-i', 'testsrc2=s=800x800:d=1', '-frames:v', '1', root + '/big.jpg')
ff('-f', 'lavfi', '-i', 'testsrc2=s=300x300:d=1', '-frames:v', '1', root + '/small.jpg')
# (folder, file, title, artist, album, year, genre, cover)
SONGS = [('Good', 'g1.mp3', 'Good One', 'Ann', 'Good Album', '1999', 'Rock', 'big'),
         ('Good', 'g2.mp3', 'Good Two', 'Ann', 'Good Album', '1999', 'Rock', 'big'),
         ('Small', 's1.mp3', 'Small One', 'Bob', 'Small Cover', '2001', 'Pop', 'small'),
         ('Bare', 'b1.mp3', 'Bare One', 'Cat', 'Bare Album', '', '', None),
         ('Loose', 'Some Artist - Untitled Thing.mp3', None, None, None, '', '', None),
         ('Loose', 'track07.mp3', None, None, None, '', '', None)]
for i, (d, f, t, a, al, y, g, cov) in enumerate(SONGS):
    os.makedirs(f'{M}/{d}', exist_ok=True)
    args = ['-f', 'lavfi', '-i', f'sine=frequency={300 + i * 40}:duration=2']
    if cov: args += ['-i', f'{root}/{cov}.jpg', '-map', '0:a', '-map', '1:v', '-c:v', 'mjpeg', '-disposition:v', 'attached_pic', '-id3v2_version', '3']
    args += ['-c:a', 'libmp3lame', '-b:a', '32k']
    for k, v in (('title', t), ('artist', a), ('album', al), ('date', y), ('genre', g)):
        if v: args += ['-metadata', f'{k}={v}']
    if not t: args += ['-map_metadata', '-1']
    ff(*args, f'{M}/{d}/{f}')

class Q(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a): pass
srv = http.server.ThreadingHTTPServer(('127.0.0.1', PORT), functools.partial(Q, directory=root))
threading.Thread(target=srv.serve_forever, daemon=True).start()
files = []
for dp, dn, fn in os.walk(M):
    for f in fn:
        rel = os.path.relpath(os.path.join(dp, f), root)
        files.append({'uri': f'http://127.0.0.1:{PORT}/' + rel.replace(' ', '%20'), 'name': f, 'relPath': rel, 'type': '',
                      'size': os.path.getsize(os.path.join(dp, f)), 'lastModified': 1700000000000})
MOCK = """
(function(){
 var picked = %s, listeners = {};
 var impl = {
   pickMusicFolder: function(){ return Promise.resolve({ folder: 'Music', treeUri: 'tree:music', files: picked, truncated: false }); },
   rescanMusicFolder: function(){ return Promise.resolve({ folder: 'Music', treeUri: 'tree:music', files: picked, truncated: false }); },
   cacheCheck: function(){ return Promise.resolve({ url: 'file:///cache/x.mp3' }); },
   addListener: function(n, f){ (listeners[n] = listeners[n] || []).push(f); return Promise.resolve({remove:function(){}}); }
 };
 var P = new Proxy({}, {get:function(t,k){ if(k==='then') return undefined; if(k==='setCarLibraryPart') return undefined; if(impl[k]) return impl[k]; return function(){ return Promise.resolve({}); }; }});
 window.Capacitor = { isNativePlatform:function(){return true;}, getPlatform:function(){return 'android';},
   registerPlugin:function(){ return P; }, Plugins:{AmplifyPlayer:P}, convertFileSrc:function(u){return u;} };
})();
""" % json.dumps(files)

fails = []
def check(cond, msg):
    print(('PASS ' if cond else 'FAIL ') + msg)
    if not cond: fails.append(msg)

CATS = "Array.prototype.map.call(document.querySelectorAll('#cleanupCats .cl-cat'), function(b){ return [b.dataset.clGroup, (b.querySelector('.cl-count')||{}).textContent || '', b.querySelector('.set-cat-sub').textContent, b.disabled]; })"
ITEMS = "Array.prototype.map.call(document.querySelectorAll('#cleanupList .cl-item'), function(b){ return [b.querySelector('.cl-name').textContent, b.querySelector('.cl-sub').textContent]; })"

async def run(scheme):
    T = f'[{scheme}]'
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
        ctx = await b.new_context(viewport={'width': 412, 'height': 860}, device_scale_factor=2, is_mobile=True, has_touch=True, color_scheme=scheme)
        await ctx.add_init_script(MOCK); await ctx.add_init_script(AUTO_NOTICE)
        pg = await ctx.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.route('**/*', lambda route: route.continue_() if '127.0.0.1' in route.request.url else route.abort())
        await pg.goto(f'http://127.0.0.1:{PORT}/index.html'); await pg.wait_for_timeout(2500)
        await pg.evaluate("""(function(){ var ov=document.getElementById('addMusicOverlay'); if(ov) ov.classList.add('open');
          var btn=document.getElementById('addMusicFolderBtn'); btn.disabled=false; btn.click(); })()""")
        for _ in range(60):
            await pg.wait_for_timeout(500)
            if await pg.evaluate("__t.n()") >= 6: break
        await pg.wait_for_timeout(1500)
        await pg.evaluate("document.getElementById('importPanelClose') && document.getElementById('importPanelClose').click()")
        check(await pg.evaluate("__t.n()") == 6, f'{T} six songs imported')

        await pg.evaluate("__t.set('library')"); await pg.wait_for_timeout(300)
        await pg.screenshot(path=f'{shots}/cleanup-{scheme}-library.png')
        await pg.tap('#cleanupOpenBtn'); await pg.wait_for_timeout(300)
        check(await pg.evaluate("document.getElementById('settingsTitle').textContent") == 'Library Cleanup', f'{T} the Cleanup page opens')
        for _ in range(20):
            await pg.wait_for_timeout(300)
            cats = await pg.evaluate(CATS)
            if cats and cats[3][2] != 'Checking covers…': break
        await pg.screenshot(path=f'{shots}/cleanup-{scheme}-cats.png')
        d = {c[0]: c for c in cats}
        check(d['songs'][1] == '2', f'{T} two songs missing details {d["songs"]}')
        check(d['albums'][1] == '1', f'{T} one album missing year or genre (songs with no album aren\'t an album) {d["albums"]}')
        check(d['noart'][1] == '1', f'{T} one album with no cover {d["noart"]}')
        check(d['lowart'][1] == '1', f'{T} one low-res cover {d["lowart"]}')

        await pg.tap('.cl-cat[data-cl-group=lowart]'); await pg.wait_for_timeout(300)
        items = await pg.evaluate(ITEMS)
        check(items == [['Small Cover', 'Bob · 300 × 300']], f'{T} low-res list names the album and its size {items}')
        await pg.screenshot(path=f'{shots}/cleanup-{scheme}-lowart.png')
        await pg.tap('#cleanupList .cl-item'); await pg.wait_for_timeout(500)
        dlg = await pg.evaluate("[document.getElementById('artUrlOverlay').classList.contains('open'), document.getElementById('artUrlTitle').textContent, !document.getElementById('artSuggestBtn').hidden, !document.getElementById('artToFilesRow').hidden && document.getElementById('artToFilesChk').checked, parseInt(getComputedStyle(document.getElementById('artUrlOverlay')).zIndex)]")
        check(dlg[0] and dlg[1] == 'Album Cover' and dlg[2] and dlg[3] and dlg[4] > 1500, f'{T} tapping it opens the album cover dialog above Settings, with suggestions and save-in-files ticked {dlg}')
        await pg.screenshot(path=f'{shots}/cleanup-{scheme}-coverdlg.png')
        await pg.evaluate("document.getElementById('artUrlCloseBtn').click()"); await pg.wait_for_timeout(700)

        await pg.tap('#settingsCloseBtn'); await pg.wait_for_timeout(300)
        check(await pg.evaluate("document.getElementById('settingsTitle').textContent") == 'Library Cleanup', f'{T} back goes to Cleanup')
        await pg.tap('.cl-cat[data-cl-group=songs]'); await pg.wait_for_timeout(300)
        items = await pg.evaluate(ITEMS)
        check(len(items) == 2 and all('Loose' in x[1] for x in items), f'{T} the untagged songs are listed with their file paths {items}')
        await pg.screenshot(path=f'{shots}/cleanup-{scheme}-songs.png')
        await pg.tap('#cleanupList .cl-item'); await pg.wait_for_timeout(800)
        tag = await pg.evaluate("[document.getElementById('tagOverlay').classList.contains('open'), parseInt(getComputedStyle(document.getElementById('tagOverlay')).zIndex)]")
        check(tag[0] and tag[1] > 1500, f'{T} a song opens its Info & Tags above Settings {tag}')
        await pg.screenshot(path=f'{shots}/cleanup-{scheme}-tagsheet.png')
        await pg.evaluate("document.getElementById('tagCloseBtn').click()"); await pg.wait_for_timeout(700)

        await pg.tap('#settingsCloseBtn'); await pg.wait_for_timeout(200)
        await pg.tap('.cl-cat[data-cl-group=albums]'); await pg.wait_for_timeout(300)
        items = await pg.evaluate(ITEMS)
        check(['Bare Album', 'Cat · No year or genre'] in items, f'{T} Bare Album listed as missing year and genre {items}')
        await pg.tap('#cleanupList .cl-item'); await pg.wait_for_timeout(800)
        check(await pg.evaluate("document.getElementById('tagOverlay').classList.contains('open')"), f'{T} an album opens its album Info & Tags')
        await pg.evaluate("document.getElementById('tagCloseBtn').click()"); await pg.wait_for_timeout(700)

        await pg.tap('#settingsCloseBtn'); await pg.wait_for_timeout(200)
        await pg.tap('#settingsCloseBtn'); await pg.wait_for_timeout(200)
        check(await pg.evaluate("document.getElementById('settingsTitle').textContent") == 'Library', f'{T} back from Cleanup goes to Library')
        await pg.tap('#settingsCloseBtn'); await pg.wait_for_timeout(200)
        check(await pg.evaluate("document.getElementById('settingsTitle').textContent") == 'Settings', f'{T} then to Settings')
        check(not errs, f'{T} no page errors {errs}')
        await b.close()

async def main():
    for s in ('dark', 'light'): await run(s)
    print('ALL PASSED' if not fails else f'FAILS {len(fails)}')
asyncio.run(main())
