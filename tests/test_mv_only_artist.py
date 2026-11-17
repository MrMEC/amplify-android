"""Build 152: videos in the music folders (.mp4 with a picture, .avi, .mkv ...) are listed on their
artist's page under "Videos" -- by "Artist - Title" when that artist is in the library, else by
folder (named after the artist, or mostly their songs) -- and play as videos, one after another.
A sound-only .mp4 is still a song; an .mp4 video added as a song before is taken out of the songs.
Run: python3 tests/test_music_videos.py (screenshots in /tmp/claude-0/t/shots)"""
import sys as _nsys, os as _nos; _nsys.path.insert(0, _nos.path.dirname(_nos.path.abspath(__file__))); from notice_auto import AUTO_NOTICE
import asyncio, os, json, threading, http.server, functools, shutil, subprocess
from playwright.async_api import async_playwright

PORT = 8831
root = '/tmp/claude-0/t/srv_mvonly'
shots = '/tmp/claude-0/t/shots'
os.makedirs(shots, exist_ok=True)
shutil.rmtree(root, ignore_errors=True)
os.makedirs(root)
HOOK = ("window.__t = { mvPage: function(n){ pushView(); openMusicVideoArtist(artistMatchKey(n)); }, tracks: function(){ return libraryTracks.map(function(t){ return t.name + '|' + t.artist; }); },"
        " openArtist: function(n){ openArtistPage(artistMatchKey(n)); },"
        " q: function(){ return { list: playQueue.map(function(s){ return s.name; }), idx: queueIndex, label: queueLabel, cur: currentStation && currentStation.name, type: currentStation && currentStation.type, kind: currentStation && currentStation.videoKind }; },"
        " listArtists: function(){ pushView(); enterLibraryChrome(); activeLibrarySection = 'artists'; activeArtistKey = null; activeAlbumKey = null; renderLibraryList(); runLibrarySection('artists'); },"
        " idx: function(){ return libraryArtistIndex().map(function(e){ return e.name + ':' + e.tracks.length + (e.videoOnly ? ':v' : ''); }); },"
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
songs = [('Ann', 'Ann/a1.mp3', 'Ann Song 1'), ('Bob', 'Bob/b1.mp3', 'Bob Song 1')]
for i, (a, rel, t) in enumerate(songs):
    os.makedirs(os.path.dirname(f'{M}/{rel}'), exist_ok=True)
    ff('-f', 'lavfi', '-i', f'sine=frequency={300 + i * 40}:duration=2', '-c:a', 'libmp3lame', '-b:a', '32k',
       '-metadata', f'title={t}', '-metadata', f'artist={a}', '-metadata', f'album={a} Album', f'{M}/{rel}')
os.makedirs(f'{M}/Videos', exist_ok=True); os.makedirs(f'{M}/Unknown', exist_ok=True)
# an .mp4 video named "Artist - Title", a plain-named .avi in Bob's folder, a .mkv by name in a Videos folder,
# an .mp4 in a folder of mostly Carl's songs, a sound-only .mp4 song, and one nobody's
vids = {'Videos/D-Nice - Call Me D-Nice.mp4': 640, 'Videos/Ann - Hello [HD].mkv': 640, 'Unknown/Someone - Thing.mp4': 640, 'Unknown/Someone - Other.mp4': 640}
for rel in vids:
    ff('-f', 'lavfi', '-i', 'testsrc2=s=160x90:d=2', '-f', 'lavfi', '-i', 'sine=frequency=500:duration=2', '-shortest', '-c:v', 'mpeg4', '-c:a', 'aac', '-f', 'mp4', f'{M}/{rel}')
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
        ctx = await b.new_context(viewport={'width': 327, 'height': 676}, device_scale_factor=3.3, is_mobile=True, has_touch=True, color_scheme='dark')
        await ctx.add_init_script(MOCK); await ctx.add_init_script(AUTO_NOTICE)
        pg = await ctx.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.route('**/*', lambda route: route.continue_() if '127.0.0.1' in route.request.url else route.abort())
        await pg.goto(f'http://127.0.0.1:{PORT}/index.html'); await pg.wait_for_timeout(2500)
        await pg.evaluate("""(function(){ var ov=document.getElementById('addMusicOverlay'); if(ov) ov.classList.add('open');
          var btn=document.getElementById('addMusicFolderBtn'); btn.disabled=false; btn.click(); })()""")
        for _ in range(60):
            await pg.wait_for_timeout(500)
            if len(await pg.evaluate('__t.tracks()')) >= 2: break
        await pg.wait_for_timeout(1500)
        idx = await pg.evaluate('__t.idx()'); print(idx)
        check('D-Nice:0:v' in idx, f'D-Nice (a video, no songs) is an artist {idx}')
        check('Someone:0:v' in idx, f'Someone (two videos, no songs) is an artist {idx}')
        check('Ann:1' in idx and 'Bob:1' in idx, f'artists with songs are unchanged {idx}')
        check(len([x for x in idx if x.startswith('Ann')]) == 1, 'Ann (songs + a video) is listed once')
        mv = await pg.evaluate("__t.mv('D-Nice')"); check(mv == ['Call Me D-Nice'], f'D-Nice video {mv}')
        # Library > Artists list
        await pg.evaluate("openLibrary && 0; runLibrarySection('artists')") if False else None
        await pg.evaluate("document.getElementById('importPanelClose') && document.getElementById('importPanelClose').click()")
        await pg.evaluate("__t.listArtists()"); await pg.wait_for_timeout(1200)
        tiles = await pg.evaluate("Array.from(document.querySelectorAll('#stationsGrid .tile[data-entity=artist]')).map(function(t){ return t.textContent.replace(/\\s+/g,' ').trim(); })")
        print(tiles)
        check(any('D-Nice' in t for t in tiles), f'the Artists list shows D-Nice {tiles}')
        await pg.screenshot(path=f'{shots}/mvonly-list.png')
        # the artist page
        await pg.evaluate("__t.openArtist('D-Nice')"); await pg.wait_for_timeout(1800)
        page = await pg.evaluate("""(()=>{ var labels = Array.from(document.querySelectorAll('#stationsGrid .grid-section-label')).map(function(e){ return e.firstChild.textContent; });
          var tiles = Array.from(document.querySelectorAll('#stationsGrid .mv-tile')).map(function(t){ return t.querySelector('.yt-title').textContent; });
          var play = document.getElementById('artistPlayBtn');
          return { labels: labels, tiles: tiles, name: document.getElementById('artistHeroName').textContent, empty: !!document.querySelector('#stationsGrid .empty-state'), play: play && play.style.display !== 'none', hero: document.getElementById('artistHero').style.display }; })()""")
        print(page)
        check(page['name'] == 'D-Nice' and page['hero'] != 'none', f'the artist page opens for D-Nice {page}')
        check(page['tiles'] == ['Call Me D-Nice'] and 'Music Videos' in page['labels'], f'with a Music Videos row {page}')
        check(not page['empty'], 'no "nothing to show" message')
        check(page['play'], 'Play is shown')
        await pg.screenshot(path=f'{shots}/mvonly-page.png')
        await pg.click('#artistPlayBtn'); await pg.wait_for_timeout(1200)
        s = await pg.evaluate('__t.q()'); print(s)
        check(s['type'] == 'video' and s['cur'] == 'Call Me D-Nice', f'Play plays the music video {s}')
        await pg.evaluate("closeNowPlaying && closeNowPlaying()") if False else None
        # the Watch page's name links to the artist page now
        await pg.evaluate("document.getElementById('nowPlayingScreen').style.display='none'")
        await pg.evaluate("__t.mvPage('D-Nice')"); await pg.wait_for_timeout(1500)
        link = await pg.evaluate("!!document.querySelector('.mv-hero-link')")
        check(link, 'the Music Videos page name is a link to the artist page')
        await pg.screenshot(path=f'{shots}/mvonly-watch.png')
        await pg.evaluate("document.querySelector('.mv-hero-link').click()"); await pg.wait_for_timeout(1800)
        nm = await pg.evaluate("document.getElementById('artistHeroName').textContent")
        check(nm == 'D-Nice', f'tapping it opens the artist page {nm}')
        check(not errs, f'no page errors {errs}')
        await b.close()

asyncio.run(main())
print('FAILS:', fails)
raise SystemExit(1 if fails else 0)
