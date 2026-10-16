"""Notices (build 234): every message is a modal in the delete dialog's style instead of a line
at the top of the page; the library's progress is a modal too (Stop, Hide, then the outcome with
OK); "Copied!" / "Added!" tips and the library storage box are notices. Both themes at 412 wide,
plus 360 wide with larger text.
Run: python3 tests/test_notices.py (screenshots in /tmp/claude-0/t/shots)"""
import asyncio, os, json, threading, http.server, functools, shutil, subprocess
from playwright.async_api import async_playwright

PORT = 8831
root = '/tmp/claude-0/t/srv_notices'
shots = '/tmp/claude-0/t/shots'
os.makedirs(shots, exist_ok=True)
shutil.rmtree(root, ignore_errors=True)
os.makedirs(root)
ST = lambda n: ("{ stationuuid: 'st-" + n + "', name: '" + n + "', url: 'http://radio.example/" + n.replace(' ', '')
                + "', urlToResolve: 'http://radio.example/" + n.replace(' ', '') + "', favicon: '', tags: '' }")
HOOK = ("window.__t = { tracks: function(){ return libraryTracks.length; },"
        " setup: function(){ stationPlaylists.push({ id: 'pl_mix', label: 'Mix', stations: [" + ST('Radio A') + "] }); saveStationPlaylists(); },"
        " playStation: function(){ playStation(" + ST('Radio B') + "); },"
        " openNp: function(){ openNowPlaying(); }, closeNp: function(){ closeNowPlaying(); },"
        " addToMix: function(){ addItemsToPlaylist('pl_mix', [" + ST('Radio C') + "]); },"
        " storageError: function(){ runLibrarySection('songs'); libraryStorageError = 'The database is locked.'; refreshLibraryView(); },"
        " storageFixed: function(){ libraryStorageError = ''; },"
        " status: setStatus, importPanel: showImportPanel };\n")
_src = open(os.path.join(os.path.dirname(__file__), '..', 'www', 'index.html')).read()
_mark = '  var coverFlow = null;\n'
assert _src.count(_mark) == 1
open(root + '/index.html', 'w').write(_src.replace(_mark, _mark + HOOK))

M = root + '/Music'
os.makedirs(M, exist_ok=True)
for i in range(8):
    subprocess.run(['ffmpeg', '-loglevel', 'error', '-y', '-f', 'lavfi', '-i', f'sine=frequency={300 + i * 40}:duration=2',
                    '-c:a', 'libmp3lame', '-b:a', '32k', '-metadata', f'title=Song {i + 1}', '-metadata', 'artist=Ann',
                    '-metadata', 'album=Ann Album', '-metadata', f'track={i + 1}', f'{M}/{i + 1:02d}.mp3'], check=True)


class Q(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a): pass
srv = http.server.ThreadingHTTPServer(('127.0.0.1', PORT), functools.partial(Q, directory=root))
threading.Thread(target=srv.serve_forever, daemon=True).start()
files = [{'uri': f'http://127.0.0.1:{PORT}/Music/{f}', 'name': f, 'relPath': f'Music/{f}', 'type': 'audio/mpeg',
          'size': os.path.getsize(f'{M}/{f}'), 'lastModified': 1700000000000} for f in sorted(os.listdir(M))]
# nativeFileFromEntry is slowed down (window.__slow ms per song) so the progress can be seen.
MOCK = """
(function(){
 var picked = %s, listeners = {}, cur = null;
 function emit(n, ev){ (listeners[n] || []).forEach(function(f){ try{ f(ev); }catch(e){} }); }
 var impl = {
   pickMusicFolder: function(){ return Promise.resolve({folder:'Music', files:picked, truncated:false}); },
   cacheCheck: function(){ return Promise.resolve({ url: 'file:///cache/x.mp3' }); },
   load: function(o){ cur = o.id; setTimeout(function(){ emit('state', { id: cur, state: 'ready', isPlaying: true, playWhenReady: true, position: 0, duration: 0 }); }, 20); return Promise.resolve({}); },
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
 var realFetch = window.fetch;
 window.fetch = function(u, o){
   var d = window.__slow || 0;
   if(d && /\\/Music\\//.test(String(u))) return new Promise(function(r){ setTimeout(r, d); }).then(function(){ return realFetch(u, o); });
   return realFetch(u, o);
 };
})();
""" % json.dumps(files)

fails = []
def check(cond, msg):
    print(('PASS ' if cond else 'FAIL ') + msg)
    if not cond: fails.append(msg)

NOTICE = """() => { var ov = document.getElementById('noticeOverlay'), p = document.getElementById('noticePanel');
  var t = document.getElementById('noticeTitle'), m = document.getElementById('noticeMsg');
  var r = p.getBoundingClientRect(), ic = document.getElementById('noticeIcon').getBoundingClientRect();
  return { open: ov.classList.contains('open') && getComputedStyle(ov).display !== 'none',
    kind: ['info','done','error','working'].filter(function(k){ return p.classList.contains(k); })[0] || '',
    title: t.hidden ? '' : t.textContent, msg: m.textContent,
    btns: Array.from(document.querySelectorAll('#noticeActions button')).map(function(b){ return b.textContent; }),
    inView: r.left >= 0 && r.right <= innerWidth && r.top >= 0 && r.bottom <= innerHeight, icon: ic.width > 10,
    z: +getComputedStyle(ov).zIndex }; }"""
IMPORT = """() => { var ov = document.getElementById('importOverlay'), p = document.getElementById('importPanel');
  var r = p.getBoundingClientRect();
  return { open: ov.classList.contains('open') && getComputedStyle(ov).display !== 'none' && r.height > 0,
    title: document.getElementById('importPanelTitle').textContent, count: document.getElementById('importPanelCount').textContent,
    pct: document.getElementById('importPanelPct').textContent, detail: document.getElementById('importPanelDetail').textContent,
    fill: document.getElementById('importPanelFill').style.width,
    btns: Array.from(p.querySelectorAll('.import-panel-actions button')).filter(function(b){ return getComputedStyle(b).display !== 'none'; }).map(function(b){ return b.textContent; }),
    inView: r.left >= 0 && r.right <= innerWidth && r.top >= 0 && r.bottom <= innerHeight }; }"""
LINE = "(() => { var s = document.getElementById('statusLine'); return getComputedStyle(s).display === 'none' || s.getBoundingClientRect().height === 0; })()"


async def run(p, scheme):
    b = await p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
    ctx = await b.new_context(viewport={'width': 412, 'height': 900}, device_scale_factor=2, is_mobile=True, has_touch=True, color_scheme=scheme)
    await ctx.add_init_script(MOCK)
    await ctx.add_init_script("try{ localStorage.setItem('radioPlayerTheme', '%s'); }catch(e){}" % scheme)
    pg = await ctx.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
    await pg.route('**/*', lambda route: route.continue_() if '127.0.0.1' in route.request.url else route.abort())
    await pg.goto(f'http://127.0.0.1:{PORT}/index.html'); await pg.wait_for_timeout(2500)
    T = f'[{scheme}]'
    notice = lambda: pg.evaluate(NOTICE)
    imp = lambda: pg.evaluate(IMPORT)
    await pg.evaluate('__t.status("")'); await pg.wait_for_timeout(200)

    # ---- the library's progress: a modal with the bar, Stop and Hide, then the outcome ----
    await pg.evaluate('window.__slow = 1200')
    await pg.evaluate("""(function(){ var ov=document.getElementById('addMusicOverlay'); if(ov) ov.classList.add('open');
      var btn=document.getElementById('addMusicFolderBtn'); btn.disabled=false; btn.click(); })()""")
    seen = None
    for _ in range(40):
        await pg.wait_for_timeout(150)
        i = await imp()
        if i['open'] and i['title'] == 'Adding music' and i['count'] not in ('', '0 of 8'):
            seen = i; break
    check(seen and seen['btns'] == ['Stop', 'Hide'] and seen['inView'] and '%' in seen['pct'] and seen['fill'] not in ('', '0%'),
          f'{T} the library\'s progress is a modal with the bar, count, Stop and Hide {seen}')
    n = await notice()
    check(not n['open'], f'{T} no notice on top of it ({n["msg"]})')
    check(await pg.evaluate(LINE), f'{T} nothing at the top of the page')
    await pg.screenshot(path=f'{shots}/notice-import-working-{scheme}.png')
    await pg.evaluate("document.getElementById('importPanelClose').click()"); await pg.wait_for_timeout(500)
    i = await imp()
    check(not i['open'], f'{T} Hide puts it away while it runs')
    await pg.wait_for_timeout(1200)
    check(not (await imp())['open'], f'{T} and it stays away while the import goes on')
    for _ in range(60):
        await pg.wait_for_timeout(200)
        i = await imp()
        if i['open'] and i['title'] != 'Adding music': break
    check(i['open'] and i['title'] == 'Library updated' and i['count'] == '8 tracks added' and i['btns'] == ['OK'] and i['inView'],
          f'{T} the outcome opens again with OK {i}')
    check(not (await notice())['open'], f'{T} with no second message on top')
    await pg.screenshot(path=f'{shots}/notice-import-done-{scheme}.png')
    await pg.evaluate("document.getElementById('importPanelClose').click()"); await pg.wait_for_timeout(300)
    check(not (await imp())['open'], f'{T} OK closes it')
    await pg.evaluate("(function(){ var ov=document.getElementById('addMusicOverlay'); if(ov) ov.classList.remove('open'); })()")
    await pg.evaluate('window.__slow = 0')

    # ---- an ordinary message: an info notice that closes itself ----
    await pg.evaluate('__t.setup()')
    await pg.evaluate("__t.status('“Song 1” will play next.')"); await pg.wait_for_timeout(300)
    n = await notice()
    check(n['open'] and n['kind'] == 'info' and n['msg'] == '“Song 1” will play next.' and n['btns'] == ['OK'] and n['inView'] and n['icon'],
          f'{T} a message is a notice with an icon and OK {n}')
    check(n['z'] > 5000, f'{T} above every other dialog (z {n["z"]})')
    check(await pg.evaluate(LINE), f'{T} the old line at the top stays hidden')
    await pg.screenshot(path=f'{shots}/notice-info-{scheme}.png')
    await pg.wait_for_timeout(6500)
    check(not (await notice())['open'], f'{T} it closes by itself after a few seconds')

    # ---- an error waits for OK; a tap outside also closes it ----
    await pg.evaluate("__t.status('There is no music in your library to shuffle yet.', true)"); await pg.wait_for_timeout(300)
    n = await notice()
    check(n['open'] and n['kind'] == 'error' and n['btns'] == ['OK'], f'{T} an error notice {n}')
    await pg.screenshot(path=f'{shots}/notice-error-{scheme}.png')
    await pg.wait_for_timeout(7000)
    check((await notice())['open'], f'{T} an error stays until OK')
    await pg.evaluate("document.querySelector('#noticeActions button').click()"); await pg.wait_for_timeout(300)
    check(not (await notice())['open'], f'{T} OK closes it')
    await pg.evaluate("__t.status('Couldn’t set the sleep timer', true)"); await pg.wait_for_timeout(300)
    await pg.mouse.click(10, 10); await pg.wait_for_timeout(300)
    check(not (await notice())['open'], f'{T} a tap outside closes a notice')

    # ---- something in progress: a spinner and Hide, replaced by the outcome ----
    await pg.evaluate("__t.status('Checking your music folders…', false, true)"); await pg.wait_for_timeout(300)
    n = await notice()
    check(n['open'] and n['kind'] == 'working' and n['btns'] == ['Hide'], f'{T} work in progress has a spinner and Hide {n}')
    await pg.screenshot(path=f'{shots}/notice-working-{scheme}.png')
    await pg.wait_for_timeout(7000)
    check((await notice())['open'], f'{T} and doesn\'t close by itself')
    await pg.evaluate("__t.status('Everything is up to date.')"); await pg.wait_for_timeout(300)
    n = await notice()
    check(n['kind'] == 'info' and n['msg'] == 'Everything is up to date.', f'{T} the outcome replaces it {n["msg"]}')
    await pg.evaluate("__t.status('')"); await pg.wait_for_timeout(200)
    check(not (await notice())['open'], f'{T} an empty message closes it')

    # ---- Add to Playlist: a notice with a tick (was a small "Added!" tip) ----
    await pg.evaluate('__t.addToMix()'); await pg.wait_for_timeout(300)
    n = await notice()
    check(n['open'] and n['kind'] == 'done' and n['msg'] == '“Radio C” was added to “Mix”.', f'{T} Add to Playlist says so in a notice {n}')
    await pg.screenshot(path=f'{shots}/notice-done-{scheme}.png')
    check(await pg.evaluate("!document.getElementById('npPlaylistTip')"), f'{T} the old tip is gone')
    await pg.evaluate("document.querySelector('#noticeActions button').click()"); await pg.wait_for_timeout(200)

    # ---- Copy stream URL: a notice (was "Copied!" on the menu item) ----
    await ctx.grant_permissions(['clipboard-read', 'clipboard-write'], origin=f'http://127.0.0.1:{PORT}')
    await pg.evaluate('__t.playStation()'); await pg.wait_for_timeout(600)
    await pg.evaluate('__t.openNp()'); await pg.wait_for_timeout(700)
    await pg.evaluate("document.getElementById('npMenuBtn').click()"); await pg.wait_for_timeout(200)
    await pg.evaluate("document.getElementById('npCopyBtn').click()"); await pg.wait_for_timeout(500)
    n = await notice()
    menu = await pg.evaluate("document.getElementById('npMenu').classList.contains('open')")
    check(n['open'] and n['kind'] == 'done' and n['msg'] == 'Stream URL copied.' and not menu, f'{T} copying says so in a notice and closes the menu {n}')
    await pg.screenshot(path=f'{shots}/notice-copied-{scheme}.png')
    await pg.evaluate("document.querySelector('#noticeActions button').click()"); await pg.wait_for_timeout(200)
    await pg.evaluate('__t.closeNp()'); await pg.wait_for_timeout(400)

    # ---- the library can't be read: a notice with a title and Retry, once ----
    await pg.evaluate('__t.storageError()'); await pg.wait_for_timeout(600)
    n = await notice()
    check(n['open'] and n['kind'] == 'error' and n['title'] == 'Your music isn’t showing' and 'The database is locked.' in n['msg']
          and n['btns'] == ['Close', 'Retry'], f'{T} the storage problem is a notice with Retry {n}')
    box = await pg.evaluate("(function(){ var b = document.getElementById('libraryNotice'); return !b || getComputedStyle(b).display === 'none'; })()")
    check(box, f'{T} not a box on the page')
    await pg.screenshot(path=f'{shots}/notice-library-{scheme}.png')
    await pg.evaluate("document.querySelector('#noticeActions button').click()"); await pg.wait_for_timeout(200)
    await pg.evaluate("runLibrarySection('albums')") if False else None
    await pg.evaluate("__t.storageError()"); await pg.wait_for_timeout(400)
    check(not (await notice())['open'], f'{T} not shown again for the same problem')
    await pg.evaluate('__t.storageFixed()')

    check(not errs, f'{T} no page errors {errs[:3]}')
    await b.close()


async def big_text(p):
    b = await p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
    ctx = await b.new_context(viewport={'width': 360, 'height': 740}, device_scale_factor=2, is_mobile=True, has_touch=True, color_scheme='dark')
    await ctx.add_init_script(MOCK)
    pg = await ctx.new_page()
    await pg.route('**/*', lambda route: route.continue_() if '127.0.0.1' in route.request.url else route.abort())
    await pg.goto(f'http://127.0.0.1:{PORT}/index.html'); await pg.wait_for_timeout(2500)
    await pg.add_style_tag(content='.notice-msg{font-size:20.3px !important} .notice-title{font-size:24.3px !important} #noticeActions button, .import-panel-actions button{font-size:18.9px !important} .import-panel-title{font-size:24.3px !important} .import-panel-meta{font-size:17.6px !important} .import-panel-detail{font-size:16.9px !important}')
    await pg.evaluate("__t.status('A music folder could not be opened. Add it again with the + button.', true)"); await pg.wait_for_timeout(300)
    n = await pg.evaluate(NOTICE)
    check(n['open'] and n['inView'], f'[big text 360] a long message fits {n["inView"]}')
    await pg.screenshot(path=f'{shots}/notice-bigtext.png')
    await pg.evaluate("document.querySelector('#noticeActions button').click()")
    await pg.evaluate("__t.importPanel('working', { done: 3, total: 120, detail: 'A very long file name for a song that goes on and on.mp3' })"); await pg.wait_for_timeout(300)
    i = await pg.evaluate(IMPORT)
    fit = await pg.evaluate("Array.from(document.querySelectorAll('.import-panel-actions button')).every(function(b){ return b.scrollWidth <= b.clientWidth + 1; })")
    check(i['open'] and i['inView'] and fit, f'[big text 360] the progress modal fits {i}')
    await pg.screenshot(path=f'{shots}/notice-import-bigtext.png')
    await b.close()


async def main():
    async with async_playwright() as p:
        for scheme in ('dark', 'light'):
            await run(p, scheme)
        await big_text(p)
    print('ALL PASSED' if not fails else f'FAILED {fails}')

asyncio.run(main())
