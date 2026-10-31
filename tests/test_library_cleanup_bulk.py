"""Build 358: Library Cleanup finds fixes online for a whole list, shows them for review, and
writes the kept ones into the files. MusicBrainz and the Cover Art Archive are stood in for.
Covers: an untagged "Artist - Title" file gets title/artist/album/year/track; an album gets its
missing year and genre; an album with no cover and one with a 300px cover get an 800px cover.
A song with nothing to look up shows "No match found". Saving asks first, asks for folder access
once, and the files really change (read back with mutagen). Phone, dark.
Run: python3 tests/test_library_cleanup_bulk.py (screenshots in /tmp/claude-0/t/shots)"""
import sys as _nsys, os as _nos; _nsys.path.insert(0, _nos.path.dirname(_nos.path.abspath(__file__)))
import asyncio, os, json, threading, http.server, shutil, subprocess, base64, zlib, re
from urllib.parse import urlparse, parse_qs, unquote
from playwright.async_api import async_playwright
from mutagen.id3 import ID3

PORT = 8873
root = '/tmp/claude-0/t/srv_cleanup_bulk'
shots = '/tmp/claude-0/t/shots'
os.makedirs(shots, exist_ok=True)
HOOK = "window.__t = { n: function(){ return libraryTracks.length; }, ev: function(js){ return eval(js); }, set: function(c){ openSettings(c); }, rv: function(){ return cleanupReview ? { g: cleanupReview.group, found: cleanupReview.found.size, picked: cleanupReview.picked.size, looked: cleanupReview.looked.size } : null; } };\n"
_src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'www', 'index.html')).read()
_mark = '  var coverFlow = null;\n'
assert _src.count(_mark) == 1
M = root + '/Music'

def ff(*a): subprocess.run(['ffmpeg', '-loglevel', 'error', '-y'] + list(a), check=True)
SONGS = [('Loose', 'Some Artist - Untitled Thing.mp3', None, None, None, '', '', None),
         ('Loose', 'track07.mp3', None, None, None, '', '', None),
         ('Bare', 'b1.mp3', 'Bare One', 'Cat', 'Bare Album', '', '', 'big'),
         ('Bare', 'b2.mp3', 'Bare Two', 'Cat', 'Bare Album', '', '', 'big'),
         ('Plain', 'p1.mp3', 'Plain One', 'Dan', 'Plain Album', '2003', 'Jazz', None),
         ('Small', 's1.mp3', 'Small One', 'Bob', 'Small Cover', '2001', 'Pop', 'small')]
def make_library():
    shutil.rmtree(root, ignore_errors=True); os.makedirs(M)
    open(root + '/index.html', 'w').write(_src.replace(_mark, _mark + HOOK))
    ff('-f', 'lavfi', '-i', 'color=c=0x2050d0:s=800x800:d=1', '-frames:v', '1', root + '/big.jpg')
    ff('-f', 'lavfi', '-i', 'color=c=0x30a040:s=300x300:d=1', '-frames:v', '1', root + '/small.jpg')
    ff('-f', 'lavfi', '-i', 'color=c=0x2050d0:s=250x250:d=1', '-frames:v', '1', root + '/thumb.jpg')
    for i, (d, f, t, a, al, y, g, cov) in enumerate(SONGS):
        os.makedirs(f'{M}/{d}', exist_ok=True)
        args = ['-f', 'lavfi', '-i', f'sine=frequency={300 + i * 40}:duration=2']
        if cov: args += ['-i', f'{root}/{cov}.jpg', '-map', '0:a', '-map', '1:v', '-c:v', 'mjpeg', '-disposition:v', 'attached_pic']
        args += ['-c:a', 'libmp3lame', '-b:a', '32k', '-id3v2_version', '3']
        for k, v in (('title', t), ('artist', a), ('album', al), ('date', y), ('genre', g)):
            if v: args += ['-metadata', f'{k}={v}']
        if not t: args += ['-map_metadata', '-1']
        ff(*args, f'{M}/{d}/{f}')

writes = []
class H(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **k): super().__init__(*a, directory=root, **k)
    def log_message(self, *a): pass
    def end_headers(self):
        self.send_header('Cache-Control', 'no-store'); super().end_headers()
    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        rel = unquote(body['uri'].split(f':{PORT}/', 1)[1])
        path = os.path.join(root, rel)
        data = open(path, 'rb').read(); head = base64.b64decode(body['data']); n = body['replace']
        if len(data) != body['size'] or zlib.crc32(data[:n]) != body['crc']: out = {'error': 'CHANGED'}
        else:
            open(path, 'wb').write(head + data[n:]); st = os.stat(path)
            writes.append(os.path.basename(path))
            out = {'size': st.st_size, 'lastModified': int(st.st_mtime * 1000)}
        b = json.dumps(out).encode()
        self.send_response(200); self.send_header('Content-Type', 'application/json'); self.send_header('Content-Length', str(len(b))); self.end_headers(); self.wfile.write(b)
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
 var listeners = {};
 function err(msg, code){ var e = new Error(msg); e.code = code; return e; }
 var impl = {
   pickMusicFolder: function(){ return Promise.resolve({folder:'Music', treeUri: 'http://127.0.0.1:%d/Music', files: window.__listing, truncated:false}); },
   rescanMusicFolder: function(){ return Promise.resolve({folder:'Music', files: window.__listing}); },
   cacheCheck: function(){ return Promise.resolve({ url: 'file:///cache/x.mp3' }); },
   writeFileHead: function(o){
     if(window.__noWrite) return Promise.reject(err('no', 'NO_WRITE'));
     return fetch('/__write', { method: 'POST', body: JSON.stringify(o) }).then(function(r){ return r.json(); }).then(function(j){ if(j.error) throw err('changed', j.error); return j; });
   },
   grantFolderWrite: function(o){ window.__grants++; window.__noWrite = false; return Promise.resolve({ treeUri: o.treeUri, matches: true, canWrite: true }); },
   addListener: function(n, f){ (listeners[n] = listeners[n] || []).push(f); return Promise.resolve({remove:function(){}}); }
 };
 var P = new Proxy({}, {get:function(t,k){ if(k==='then') return undefined; if(k==='setCarLibraryPart') return undefined; if(impl[k]) return impl[k]; return function(){ return Promise.resolve({}); }; }});
 window.Capacitor = { isNativePlatform:function(){return true;}, getPlatform:function(){return 'android';},
   registerPlugin:function(){ return P; }, Plugins:{AmplifyPlayer:P, CapacitorHttp: { request: function(o){
     var path = '/' + String(o.url).split('/').pop();
     return fetch(path).then(function(r){ return r.blob().then(function(b){ return new Promise(function(res){
       var fr = new FileReader(); fr.onload = function(){ res({ status: r.status, data: String(fr.result).replace(/^data:[^,]*,/, '') }); }; fr.readAsDataURL(b); }); }); });
   } } }, convertFileSrc:function(u){return u;} };
})();
""" % PORT
# Notices: the library's own progress goes away at once; the rest stay, so the test can see them.
NOTICES = """document.addEventListener('DOMContentLoaded', function(){
  var o = document.getElementById('importOverlay');
  if(o) new MutationObserver(function(){ if(o.classList.contains('open')) setTimeout(function(){ o.classList.remove('open'); }, 0); }).observe(o, { attributes: true, attributeFilter: ['class'] });
  var n = document.getElementById('noticeOverlay');
  if(n) new MutationObserver(function(){ if(n.classList.contains('open') && !window.__keepNotices) setTimeout(function(){ n.classList.remove('open'); }, 0); }).observe(n, { attributes: true, attributeFilter: ['class'] });
});"""

mb_asked = []
def mb_answer(url):
    u = urlparse(url); q = parse_qs(u.query).get('query', [''])[0]; path = u.path
    mb_asked.append(path + ' ' + q)
    def ac(n): return [{'name': n, 'artist': {'name': n}}]
    if path.endswith('/recording/'):
        if 'Untitled Thing' in q and 'Some Artist' in q:
            return {'recordings': [{'score': 100, 'title': 'Untitled Thing', 'artist-credit': ac('Some Artist'), 'first-release-date': '1987-05-01',
                     'releases': [{'title': 'Greatest Hits', 'status': 'Official', 'date': '1995-01-01', 'release-group': {'primary-type': 'Album', 'secondary-types': ['Compilation']},
                                   'media': [{'track-count': 18, 'track': [{'number': '12'}]}]},
                                  {'title': 'Great Record', 'status': 'Official', 'date': '1987-05-01', 'release-group': {'primary-type': 'Album'},
                                   'media': [{'track-count': 10, 'track': [{'number': '3'}]}]}]}]}
        return {'recordings': []}
    if path.endswith('/release-group/'):
        for title, art, gid, date in (('Bare Album', 'Cat', 'rg-bare', '1994-02-02'), ('Plain Album', 'Dan', 'rg-plain', '2003'), ('Small Cover', 'Bob', 'rg-small', '2001')):
            if title in q:
                return {'release-groups': [{'id': gid, 'score': 100, 'title': title, 'artist-credit': ac(art), 'first-release-date': date, 'primary-type': 'Album'}]}
        return {'release-groups': []}
    if '/release-group/rg-bare' in path:
        return {'id': 'rg-bare', 'genres': [{'name': 'shoegaze', 'count': 1}, {'name': 'indie rock', 'count': 5}]}
    return {}

fails = []
def check(cond, msg):
    print(('PASS ' if cond else 'FAIL ') + msg)
    if not cond: fails.append(msg)
def tags_of(rel):
    t = ID3(f'{M}/{rel}')
    g = lambda k: str(t.get(k).text[0]) if t.get(k) else ''
    pics = [f for f in t.values() if f.FrameID == 'APIC']
    return {'title': g('TIT2'), 'artist': g('TPE1'), 'album': g('TALB'), 'year': g('TYER') or g('TDRC'), 'track': g('TRCK'), 'genre': g('TCON'), 'pic': len(pics[0].data) if pics else 0}
ITEMS = "Array.prototype.map.call(document.querySelectorAll('#cleanupList .cl-item'), function(b){ var c = b.querySelector('.cl-pick'); return [b.querySelector('.cl-name').textContent, (b.querySelector('.cl-new')||{}).textContent || '', c ? c.checked : null]; })"
CATS = "(function(){ var o = {}; Array.prototype.forEach.call(document.querySelectorAll('#cleanupCats .cl-cat'), function(b){ o[b.dataset.clGroup] = (b.querySelector('.cl-count')||{}).textContent || '0'; }); return o; })()"

async def find_and_save(pg, group, T, expect_items, shot):
    await pg.tap(f'.cl-cat[data-cl-group={group}]'); await pg.wait_for_timeout(300)
    check(await pg.evaluate("!!document.getElementById('cleanupFindBtn')"), f'{T} {group}: a Find button above the list')
    await pg.tap('#cleanupFindBtn')
    for _ in range(80):
        await pg.wait_for_timeout(250)
        if await pg.evaluate("__t.rv()"): break
    items = await pg.evaluate(ITEMS)
    check(items == expect_items, f'{T} {group}: review shows what was found {items}')
    bar = await pg.evaluate("[!document.getElementById('cleanupBar').hidden, document.getElementById('cleanupSaveBtn').textContent]")
    await pg.screenshot(path=f'{shots}/cleanupbulk-{shot}.png')
    return bar

async def confirm_and_wait(pg, T, allow):
    await pg.wait_for_timeout(300)
    conf = await pg.evaluate("[document.getElementById('confirmOverlay').classList.contains('open'), document.getElementById('confirmTitle').textContent, document.getElementById('confirmOk').classList.contains('confirm-ok-safe')]")
    check(conf[0] and conf[2], f'{T} Save asks first, with an ordinary (not red) Save button {conf}')
    await pg.screenshot(path=f'{shots}/cleanupbulk-confirm.png')
    await pg.tap('#confirmOk')
    if allow:
        for _ in range(40):
            await pg.wait_for_timeout(250)
            labels = await pg.evaluate("Array.prototype.map.call(document.querySelectorAll('#noticeActions button'), function(b){ return b.textContent; })")
            if 'Allow' in labels: break
        check('Allow' in labels, f'{T} first save asks for access to the music folder {labels}')
        await pg.screenshot(path=f'{shots}/cleanupbulk-allow.png')
        await pg.evaluate("Array.prototype.filter.call(document.querySelectorAll('#noticeActions button'), function(b){ return b.textContent === 'Allow'; })[0].click()")
    for _ in range(80):
        await pg.wait_for_timeout(250)
        t = await pg.evaluate("document.getElementById('noticeOverlay').classList.contains('open') ? document.getElementById('noticeTitle').textContent : ''")
        if t.endswith('saved'): break
    msg = await pg.evaluate("document.getElementById('noticeMsg').textContent")
    await pg.screenshot(path=f'{shots}/cleanupbulk-saved.png')
    await pg.evaluate("Array.prototype.forEach.call(document.querySelectorAll('#noticeActions button'), function(b){ b.click(); })")
    await pg.wait_for_timeout(600)
    return t, msg

async def run(scheme):
    T = f'[{scheme}]'
    make_library(); writes.clear(); mb_asked.clear()
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
        ctx = await b.new_context(viewport={'width': 412, 'height': 860}, device_scale_factor=2, is_mobile=True, has_touch=True, color_scheme=scheme)
        await ctx.add_init_script(MOCK); await ctx.add_init_script(NOTICES)
        await ctx.add_init_script('window.__listing = %s;' % json.dumps(listing()))
        pg = await ctx.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
        async def router(route):
            u = route.request.url
            if '127.0.0.1' in u: return await route.continue_()
            if 'musicbrainz.org/ws/2/' in u: return await route.fulfill(status=200, content_type='application/json', headers={'Access-Control-Allow-Origin': '*'}, body=json.dumps(mb_answer(u)))
            m = re.search(r'coverartarchive\.org/release-group/([^/?]+)(/front-250)?', u)
            if m:
                if m.group(2): return await route.fulfill(path=f'{root}/thumb.jpg', content_type='image/jpeg')
                return await route.fulfill(status=200, content_type='application/json', headers={'Access-Control-Allow-Origin': '*'},
                                           body=json.dumps({'images': [{'front': True, 'image': 'https://ia800.us.archive.org/x/big.jpg'}]}))
            if 'ia800.us.archive.org' in u: return await route.fulfill(path=f'{root}/big.jpg', content_type='image/jpeg', headers={'Access-Control-Allow-Origin': '*'})
            return await route.abort()
        await pg.route('**/*', router)
        await pg.goto(f'http://127.0.0.1:{PORT}/index.html'); await pg.wait_for_timeout(2500)
        await pg.evaluate("""(function(){ var ov=document.getElementById('addMusicOverlay'); if(ov) ov.classList.add('open');
          var btn=document.getElementById('addMusicFolderBtn'); btn.disabled=false; btn.click(); })()""")
        for _ in range(60):
            await pg.wait_for_timeout(500)
            if await pg.evaluate("__t.n()") >= 6: break
        await pg.wait_for_timeout(1500)
        check(await pg.evaluate("__t.n()") == 6, f'{T} six songs imported')
        await pg.evaluate("window.__keepNotices = true")
        await pg.evaluate("__t.set('library')"); await pg.wait_for_timeout(200)
        await pg.tap('#cleanupOpenBtn')
        for _ in range(20):
            await pg.wait_for_timeout(300)
            if 'Checking' not in await pg.evaluate("document.getElementById('cleanupCats').textContent"): break
        cats = await pg.evaluate(CATS)
        check(cats == {'songs': '2', 'albums': '1', 'noart': '1', 'lowart': '1'}, f'{T} before: {cats}')

        # Songs
        bar = await find_and_save(pg, 'songs', T, [['track07', 'No match found', None], ['Untitled Thing', 'Untitled Thing · Some Artist · Great Record (1987)', True]], 'songs')
        check(bar == [True, 'Save 1'], f'{T} songs: the bar offers Save 1 {bar}')
        await pg.tap('#cleanupSaveBtn')
        t, msg = await confirm_and_wait(pg, T, allow=True)
        check(t == 'Tags saved' and '1 song file' in msg, f'{T} songs saved: {t!r} {msg!r}')
        tg = tags_of('Loose/Some Artist - Untitled Thing.mp3')
        check(tg['title'] == 'Untitled Thing' and tg['artist'] == 'Some Artist' and tg['album'] == 'Great Record' and tg['year'].startswith('1987') and tg['track'] == '3/10', f'{T} the file has its tags (the original album, not the compilation) {tg}')
        items = await pg.evaluate(ITEMS)
        check([i[0] for i in items] == ['track07'], f'{T} the fixed song leaves the list {items}')
        await pg.tap('#settingsCloseBtn'); await pg.wait_for_timeout(300)

        # Albums: year and genre
        # (the song just fixed brought a new album, Great Record, which the stand-in MusicBrainz doesn't have)
        await find_and_save(pg, 'albums', T, [['Bare Album', '1994 · Indie Rock', True], ['Great Record', 'No match found', None]], 'albums')
        await pg.tap('#cleanupSaveBtn')
        t, msg = await confirm_and_wait(pg, T, allow=False)
        check(t == 'Tags saved' and '2 song files' in msg, f'{T} album saved in both songs: {t!r} {msg!r}')
        for rel in ('Bare/b1.mp3', 'Bare/b2.mp3'):
            tg = tags_of(rel)
            check(tg['year'].startswith('1994') and tg['genre'] == 'Indie Rock' and tg['title'].startswith('Bare'), f'{T} {rel} has year and genre, title kept {tg}')
        await pg.tap('#settingsCloseBtn'); await pg.wait_for_timeout(300)

        # No cover
        await find_and_save(pg, 'noart', T, [['Great Record', 'No match found', None], ['Plain Album', 'New cover · 800 × 800', True]], 'noart')
        thumbs = await pg.evaluate("document.querySelectorAll('#cleanupList img.cl-art-new').length")
        check(thumbs == 1, f'{T} the new cover is shown beside the album ({thumbs})')
        await pg.tap('#cleanupSaveBtn')
        t, msg = await confirm_and_wait(pg, T, allow=False)
        check(t == 'Covers saved', f'{T} cover saved: {t!r} {msg!r}')
        check(tags_of('Plain/p1.mp3')['pic'] > 1000, f'{T} Plain Album\'s file now has a cover')
        await pg.tap('#settingsCloseBtn'); await pg.wait_for_timeout(300)

        # Low-res: untick, nothing saved; then save
        await find_and_save(pg, 'lowart', T, [['Small Cover', 'New cover · 800 × 800', True]], 'lowart')
        await pg.tap('#cleanupList .cl-item:not(.cl-item-off)'); await pg.wait_for_timeout(200)
        bar = await pg.evaluate("[document.getElementById('cleanupSaveBtn').disabled, document.getElementById('cleanupSaveBtn').textContent]")
        check(bar == [True, 'Save'], f'{T} untick: Save turns off {bar}')
        await pg.tap('#cleanupList .cl-item:not(.cl-item-off)'); await pg.wait_for_timeout(200)
        before = tags_of('Small/s1.mp3')['pic']
        await pg.tap('#cleanupSaveBtn')
        t, msg = await confirm_and_wait(pg, T, allow=False)
        after = tags_of('Small/s1.mp3')['pic']
        check(t == 'Covers saved' and after and after != before, f'{T} the small cover is replaced ({before} -> {after})')
        await pg.tap('#settingsCloseBtn'); await pg.wait_for_timeout(500)
        for _ in range(20):
            await pg.wait_for_timeout(300)
            if 'Checking' not in await pg.evaluate("document.getElementById('cleanupCats').textContent"): break
        cats = await pg.evaluate(CATS)
        check(cats == {'songs': '1', 'albums': '1', 'noart': '1', 'lowart': '0'}, f'{T} after: only track07 and the new Great Record are left {cats}')
        await pg.screenshot(path=f'{shots}/cleanupbulk-after.png')
        check(await pg.evaluate("window.__grants") == 1, f'{T} folder access asked once')
        check(not errs, f'{T} no page errors {errs}')
        await b.close()

async def main():
    await run('dark')
    print('ALL PASSED' if not fails else f'FAILS {len(fails)}')
asyncio.run(main())
