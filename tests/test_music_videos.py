"""Build 152: videos in the music folders (.mp4 with a picture, .avi, .mkv ...) are listed on their
artist's page under "Videos" -- by "Artist - Title" when that artist is in the library, else by
folder (named after the artist, or mostly their songs) -- and play as videos, one after another.
A sound-only .mp4 is still a song; an .mp4 video added as a song before is taken out of the songs.
Run: python3 tests/test_music_videos.py (screenshots in /tmp/claude-0/t/shots)"""
import asyncio, os, json, threading, http.server, functools, shutil, subprocess
from playwright.async_api import async_playwright

PORT = 8814
root = '/tmp/claude-0/t/srv_mv'
shots = '/tmp/claude-0/t/shots'
os.makedirs(shots, exist_ok=True)
shutil.rmtree(root, ignore_errors=True)
os.makedirs(root)
HOOK = ("window.__t = { tracks: function(){ return libraryTracks.map(function(t){ return t.name + '|' + t.artist; }); },"
        " openArtist: function(n){ openArtistPage(artistMatchKey(n)); },"
        " q: function(){ return { list: playQueue.map(function(s){ return s.name; }), idx: queueIndex, label: queueLabel, cur: currentStation && currentStation.name, type: currentStation && currentStation.type, kind: currentStation && currentStation.videoKind }; },"
        " mv: function(k){ return musicVideosFor(artistMatchKey(k)).map(function(v){ return v.name; }); },"
        " files: function(){ return musicVideos.files.map(function(f){ return f.name; }); },"
        " clearProbe: function(){ musicVideos.probed = {}; saveMusicVideos(); },"
        " scan: function(){ return scanMusicFolderVideos(); },"
        " next: function(){ return playNextInLine(); },"
        " ended: function(){ onLocalVideoEnded(); },"
        " npList: function(){ return { head: npCollectionHeading.textContent, rows: Array.from(npCollectionGrid.querySelectorAll('.vep-title')).map(function(e){ return e.textContent; }) }; } };\n")
_src = open(os.path.join(os.path.dirname(__file__), '..', 'www', 'index.html')).read()
_mark = '  var coverFlow = null;\n'
assert _src.count(_mark) == 1
open(root + '/index.html', 'w').write(_src.replace(_mark, _mark + HOOK))

def ff(*args):
    subprocess.run(['ffmpeg', '-loglevel', 'error', '-y'] + list(args), check=True)
M = root + '/Music'
songs = [('Ann', 'Ann/a1.mp3', 'Ann Song 1'), ('Bob', 'Bob/b1.mp3', 'Bob Song 1'), ('Bob', 'Bob/b2.mp3', 'Bob Song 2'), ('Bob', 'Bob/b3.mp3', 'Bob Song 3'),
         ('Carl', 'Mixed Folder/c1.mp3', 'Carl Song 1'), ('Carl', 'Mixed Folder/c2.mp3', 'Carl Song 2'), ('Carl', 'Mixed Folder/c3.mp3', 'Carl Song 3')]
for i, (a, rel, t) in enumerate(songs):
    os.makedirs(os.path.dirname(f'{M}/{rel}'), exist_ok=True)
    ff('-f', 'lavfi', '-i', f'sine=frequency={300 + i * 40}:duration=2', '-c:a', 'libmp3lame', '-b:a', '32k',
       '-metadata', f'title={t}', '-metadata', f'artist={a}', '-metadata', f'album={a} Album', f'{M}/{rel}')
os.makedirs(f'{M}/Videos', exist_ok=True); os.makedirs(f'{M}/Unknown', exist_ok=True)
# an .mp4 video named "Artist - Title", a plain-named .avi in Bob's folder, a .mkv by name in a Videos folder,
# an .mp4 in a folder of mostly Carl's songs, a sound-only .mp4 song, and one nobody's
vids = {'Bob/Bob - Great Song (Official Video).mp4': 640, 'Bob/Live at Wembley.avi': 640, 'Videos/Ann - Hello [HD].mkv': 640,
        'Mixed Folder/carl_backstage.mp4': 640, 'Unknown/Someone - Thing.mp4': 640}
for rel in vids:
    ff('-f', 'lavfi', '-i', 'testsrc2=s=160x90:d=2', '-f', 'lavfi', '-i', 'sine=frequency=500:duration=2', '-shortest', '-c:v', 'mpeg4', '-c:a', 'aac', '-f', 'mp4', f'{M}/{rel}')
ff('-f', 'lavfi', '-i', 'sine=frequency=700:duration=2', '-c:a', 'aac', '-metadata', 'title=Ann Song 2', '-metadata', 'artist=Ann', '-f', 'mp4', f'{M}/Ann/a2.mp4')
vids['Ann/a2.mp4'] = 0
ff('-f', 'lavfi', '-i', 'testsrc2=s=320x180:d=1', '-frames:v', '1', f'{root}/still.jpg')

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
widths = {f['uri']: vids.get(f['relPath'][len('Music/'):], None) for f in files}
MOCK = """
(function(){
 var picked = %s, widths = %s, listeners = {}, cur = null;
 window.__forceVideo = {};
 function emit(n, ev){ (listeners[n] || []).forEach(function(f){ try{ f(ev); }catch(e){} }); }
 var impl = {
   pickMusicFolder: function(){ return Promise.resolve({ folder: 'Music', treeUri: 'tree:music', files: picked, truncated: false }); },
   rescanMusicFolder: function(){ return Promise.resolve({ folder: 'Music', treeUri: 'tree:music', files: picked, truncated: false }); },
   videoInfo: function(o){ window.__probes = (window.__probes || 0) + 1; var w = window.__forceVideo[o.uri] != null ? window.__forceVideo[o.uri] : (widths[o.uri] || 0);
     return Promise.resolve({ duration: 125000, width: w, height: w ? 360 : 0, thumb: w && o.thumb !== false ? 'http://127.0.0.1:%d/still.jpg' : '' }); },
   cacheCheck: function(){ return Promise.resolve({ url: 'file:///cache/x.mp3' }); },
   load: function(o){ cur = o.id; window.__loaded = o; setTimeout(function(){ emit('state', { id: cur, state: 'ready', isPlaying: true, playWhenReady: true, position: 0, duration: 0 }); }, 20); return Promise.resolve({}); },
   addListener: function(n, f){ (listeners[n] = listeners[n] || []).push(f); return Promise.resolve({remove:function(){}}); }
 };
 var P = new Proxy({}, {get:function(t,k){ if(k==='then') return undefined; if(k==='setCarLibraryPart') return undefined; if(impl[k]) return impl[k]; return function(){ return Promise.resolve({}); }; }});
 window.Capacitor = { isNativePlatform:function(){return true;}, getPlatform:function(){return 'android';},
   registerPlugin:function(){ return P; }, Plugins:{AmplifyPlayer:P}, convertFileSrc:function(u){return u;} };
})();
""" % (json.dumps(files), json.dumps(widths), PORT)

fails = []
def check(cond, msg):
    print(('PASS ' if cond else 'FAIL ') + msg)
    if not cond: fails.append(msg)

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
        ctx = await b.new_context(viewport={'width': 390, 'height': 844}, device_scale_factor=2, is_mobile=True, has_touch=True, color_scheme='dark')
        await ctx.add_init_script(MOCK)
        pg = await ctx.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.route('**/*', lambda route: route.continue_() if '127.0.0.1' in route.request.url else route.abort())
        await pg.goto(f'http://127.0.0.1:{PORT}/index.html'); await pg.wait_for_timeout(2500)
        await pg.evaluate("""(function(){ var ov=document.getElementById('addMusicOverlay'); if(ov) ov.classList.add('open');
          var btn=document.getElementById('addMusicFolderBtn'); btn.disabled=false; btn.click(); })()""")
        for _ in range(60):
            await pg.wait_for_timeout(500)
            if len(await pg.evaluate('__t.tracks()')) >= 8: break
        await pg.wait_for_timeout(1500)
        tr = sorted(await pg.evaluate('__t.tracks()')); print(tr)
        check(len(tr) == 8 and 'Ann Song 2|Ann' in tr and not any('Great Song' in x or 'Wembley' in x or 'backstage' in x.lower() for x in tr),
              f'the songs are imported (the sound-only .mp4 too), the videos are not {tr}')
        fl = sorted(await pg.evaluate('__t.files()'))
        check(len(fl) == 5 and 'a2.mp4' not in fl, f'five videos noted, not the sound-only .mp4 {fl}')
        mb = await pg.evaluate("__t.mv('Bob')"); check(mb == ['Great Song', 'Live at Wembley'], f"Bob: by name (title tidied) and by folder {mb}")
        ma = await pg.evaluate("__t.mv('Ann')"); check(ma == ['Hello'], f"Ann: by name, from a Videos folder {ma}")
        mc = await pg.evaluate("__t.mv('Carl')"); check(mc == ['carl backstage'], f"Carl: a folder that is mostly his songs {mc}")
        # Bob's page
        await pg.evaluate("__t.openArtist('Bob')"); await pg.wait_for_timeout(1500)
        page = await pg.evaluate("""(()=>{ var labels = Array.from(document.querySelectorAll('#stationsGrid .grid-section-label')).map(function(e){ return e.firstChild.textContent; });
          var tiles = Array.from(document.querySelectorAll('#stationsGrid .mv-tile')).map(function(t){ return { title: t.querySelector('.yt-title').textContent, dur: t.querySelector('.yt-date').textContent, img: !!t.querySelector('img') }; });
          return { labels: labels, tiles: tiles }; })()""")
        print(page)
        check(page['labels'] and page['labels'][0] == 'Music Videos' and 'Videos' not in page['labels'], f'one Music Videos row, at the top {page["labels"]}')
        check([t['title'] for t in page['tiles']] == ['Great Song', 'Live at Wembley'] and all(t['img'] and t['dur'] == '2:05' for t in page['tiles']),
              f'two tiles with a still and length {page["tiles"]}')
        await pg.screenshot(path=f'{shots}/mv-artist.png')
        await pg.evaluate("document.getElementById('importPanelClose') && document.getElementById('importPanelClose').click(); document.querySelector('.artist-videos-label').scrollIntoView({block:'center'})"); await pg.wait_for_timeout(600)
        await pg.screenshot(path=f'{shots}/mv-artist-row.png')
        # play the first: it plays as a video, Now Playing opens, the queue is Bob's videos
        await pg.click('#stationsGrid .mv-tile'); await pg.wait_for_timeout(1200)
        s = await pg.evaluate('__t.q()'); print(s)
        loaded = await pg.evaluate('window.__loaded || {}')
        check(s['type'] == 'video' and s['kind'] == 'music' and s['cur'] == 'Great Song' and s['list'] == ['Great Song', 'Live at Wembley'] and s['label'] == 'Bob Videos',
              f'plays as a video, with Bob’s videos as the queue {s}')
        check('Great%20Song' in (loaded.get('url') or loaded.get('src') or json.dumps(loaded)), f'the file is what is loaded {loaded}')
        np = await pg.evaluate("[document.getElementById('nowPlayingScreen').style.display, (document.getElementById('npSub') || {}).textContent]")
        check(np[0] == 'flex' and 'Bob' in (np[1] or ''), f'Now Playing opens, naming Bob {np}')
        nl = await pg.evaluate('__t.npList()')
        check(nl['head'] == 'More Videos by Bob' and nl['rows'] == ['Live at Wembley'], f'Now Playing lists Bob’s other videos {nl}')
        await pg.screenshot(path=f'{shots}/mv-np.png')
        await pg.evaluate('__t.ended()'); await pg.wait_for_timeout(800)
        s = await pg.evaluate('__t.q()')
        check(s['cur'] == 'Live at Wembley', f'at the end it goes on to the next video {s}')
        # an .mp4 video added as a song before build 152 leaves the songs on the next look
        await pg.evaluate("__t.clearProbe()")
        await pg.evaluate("window.__forceVideo[%s] = 0" % json.dumps([f['uri'] for f in files if f['relPath'].endswith('Ann/a2.mp4')][0]))
        n = await pg.evaluate('__t.scan()')
        check(n == 0 and 'Ann Song 2|Ann' in await pg.evaluate('__t.tracks()'), 'a sound-only .mp4 stays a song')
        await pg.evaluate("window.__forceVideo[%s] = 640" % json.dumps([f['uri'] for f in files if f['relPath'].endswith('Ann/a2.mp4')][0]))
        await pg.evaluate("__t.clearProbe()")
        n = await pg.evaluate('__t.scan()')
        tr2 = await pg.evaluate('__t.tracks()')
        check(n == 1 and 'Ann Song 2|Ann' not in tr2 and 'a2' in await pg.evaluate("__t.mv('Ann')"), f'an .mp4 found to be a video leaves the songs and joins Ann’s videos ({n}) {await pg.evaluate("__t.mv(\'Ann\')")}')
        check(not errs, f'no page errors {errs[:3]}')
        await b.close()
    print('ALL PASSED' if not fails else f'FAILED {fails}')

asyncio.run(main())
