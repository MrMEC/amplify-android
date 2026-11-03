"""An album tagged Various Artists stays one album, whatever the folders and covers, including for songs imported before the tag was kept."""
import sys as _nsys, os as _nos; _nsys.path.insert(0, _nos.path.dirname(_nos.path.abspath(__file__))); from notice_auto import AUTO_NOTICE
import asyncio, os, json, threading, http.server, functools, shutil, subprocess
from playwright.async_api import async_playwright

PORT = 8788
root = '/tmp/claude-0/t/srv_vatag'
shots = '/tmp/claude-0/t/shots'
os.makedirs(shots, exist_ok=True)
shutil.rmtree(root, ignore_errors=True)
os.makedirs(root)
# The page keeps everything inside its own scope, so the served copy gets a small hook into it.
HOOK = ("window.__t = { tracks: function(){ return libraryTracks; }, bump: function(){ compilationVersion++; },"
        " runLibrarySection: runLibrarySection, openArtistPage: openArtistPage, artistMatchKey: artistMatchKey,"
        " renderLibraryList: function(){ renderLibraryList(); }, backfillArtSigs: backfillArtSigs, backfillAlbumArtists: backfillAlbumArtists, idbDo: idbDo,"
        " store: function(){ return LIB_STORE_TRACKS; }, albumEntryForFav: albumEntryForFav, legacyAlbumKeyFor: legacyAlbumKeyFor };\n")
_src = open(os.path.join(os.path.dirname(__file__), '..', 'www', 'index.html')).read()
_mark = '  function buildAlbumIndex(tracks){'
assert _src.count(_mark) == 1
open(root + '/index.html', 'w').write(_src.replace(_mark, HOOK + _mark))


def cover(name, color):
    p = f'{root}/{name}.png'
    subprocess.run(['ffmpeg', '-loglevel', 'error', '-y', '-f', 'lavfi', '-i', f'color=c={color}:s=300x300',
                    '-frames:v', '1', p], check=True)
    return p


def song(path, title, artist, album, track, art, aa=None):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    subprocess.run(['ffmpeg', '-loglevel', 'error', '-y', '-f', 'lavfi', '-i', 'sine=frequency=440:duration=2',
                    '-i', art, '-map', '0:a', '-map', '1:v', '-c:a', 'libmp3lame', '-b:a', '64k', '-c:v', 'png',
                    '-id3v2_version', '3', '-disposition:v', 'attached_pic',
                    '-metadata', f'title={title}', '-metadata', f'artist={artist}', '-metadata', f'album={album}',
                    '-metadata', f'track={track}'] + (['-metadata', f'album_artist={aa}'] if aa else []) + [path], check=True)


colors = {c: cover(c, c) for c in ('red', 'blue', 'green', 'gold', 'purple', 'orange')}
M = root + '/Music'
# Mark's case: every song a different artist, a different cover, split over two folders.
VA = 'Various Artists'
song(f'{M}/Lego Rock Band/01.mp3', 'Song A', 'Bangles', 'Lego Rock Band', 1, colors['red'], VA)
song(f'{M}/Lego Rock Band/02.mp3', 'Song B', 'Blink-182', 'Lego Rock Band', 2, colors['blue'], VA)
song(f'{M}/Lego Rock Band/03.mp3', 'Song C', 'Blondie', 'Lego Rock Band', 3, colors['green'], VA)
song(f'{M}/Lego Rock Band Extra/04.mp3', 'Song D', 'Blur', 'Lego Rock Band', 4, colors['gold'], VA)
# Another spelling of the tag.
song(f'{M}/Now 60/01.mp3', 'One', 'Alpha', 'Now 60', 1, colors['purple'], 'Various')
song(f'{M}/Now 60/02.mp3', 'Two', 'Beta', 'Now 60', 2, colors['orange'], 'Various')
# Not tagged as various: one-song albums by different artists sharing a name stay apart.
song(f'{M}/X/01.mp3', 'Left', 'Echo', 'Split', 1, colors['green'], 'Echo')
song(f'{M}/Y/01.mp3', 'Right', 'Foxtrot', 'Split', 1, colors['blue'], 'Foxtrot')
# An ordinary one-artist album.
song(f'{M}/Band/01.mp3', 'One', 'Alpha Band', 'Solo Record', 1, colors['blue'], 'Alpha Band')
song(f'{M}/Band/02.mp3', 'Two', 'Alpha Band', 'Solo Record', 2, colors['blue'], 'Alpha Band')

H = functools.partial(http.server.SimpleHTTPRequestHandler, directory=root)
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
   if(k==='setCarLibrary') return function(o){ window.__car = o.json; return Promise.resolve({}); };
   if(k==='addListener') return function(){ return Promise.resolve({remove:function(){}}); };
   return function(){ return Promise.resolve({}); };
 }}); }
 var P = proxy();
 window.Capacitor = { isNativePlatform:function(){return true;}, getPlatform:function(){return 'android';},
   registerPlugin:function(){ return P; }, Plugins:{AmplifyPlayer:P}, convertFileSrc:function(u){return u;} };
})();
""" % json.dumps(files)

ALBUMS = """(function(){ return Array.from(document.querySelectorAll("#stationsGrid .tile[data-entity='album']")).map(function(t){
  return t.querySelector('.tile-name').textContent + ' / ' + (t.querySelector('.tile-sub')||{}).textContent; }); })()"""


def check(cond, msg):
    print(('PASS ' if cond else 'FAIL ') + msg)
    if not cond:
        raise SystemExit(1)


async def open_albums(pg):
    await pg.evaluate("__t.runLibrarySection('albums')")
    await pg.wait_for_timeout(600)


async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
        pg = await b.new_page(viewport={'width': 412, 'height': 900})
        errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.add_init_script(MOCK); await pg.add_init_script(AUTO_NOTICE)
        await pg.goto(f'http://127.0.0.1:{PORT}/index.html'); await pg.wait_for_timeout(2500)
        await pg.evaluate("""(function(){ var ov=document.getElementById('addMusicOverlay'); if(ov) ov.classList.add('open');
          var btn=document.getElementById('addMusicFolderBtn'); btn.disabled=false; btn.click(); })()""")
        for _ in range(60):
            await pg.wait_for_timeout(500)
            if await pg.evaluate('__t.tracks().length') >= len(files):
                break
        check(await pg.evaluate('__t.tracks().length') == len(files), 'all songs imported')
        check(await pg.evaluate("__t.tracks().filter(function(t){return t.albumArtist==='Various Artists';}).length") == 4,
              'album-artist tag kept on the song records')

        await open_albums(pg)
        albums = await pg.evaluate(ALBUMS)
        print(albums)
        check('Lego Rock Band / Various Artists · 4 songs' in albums, 'tagged album is one album, across folders and covers')
        check(sum(1 for a in albums if a.startswith('Lego Rock Band')) == 1, 'no per-artist Lego Rock Band albums remain')
        check('Now 60 / Various Artists · 2 songs' in albums, '"Various" spelling groups too')
        check('Split / Echo · 1 song' in albums and 'Split / Foxtrot · 1 song' in albums, 'untagged same-name albums stay apart')
        check('Solo Record / Alpha Band · 2 songs' in albums, 'ordinary album unchanged')
        await pg.screenshot(path=shots + '/vatag_albums.png')

        # Search lists it once too.
        await pg.evaluate("__t.runLibrarySection('albums')")

        # Album page.
        await pg.evaluate("""(function(){ var t=Array.from(document.querySelectorAll(".tile[data-entity='album']"))
          .filter(function(t){ return /Lego Rock Band/.test(t.textContent); })[0]; t.click(); })()""")
        await pg.wait_for_timeout(800)
        hero = await pg.evaluate("document.getElementById('albumHeroArtist').textContent")
        check(hero == 'Various Artists', 'album page names Various Artists')
        subs = await pg.evaluate("Array.from(document.querySelectorAll('#stationsGrid .song-row .song-row-sub')).map(function(e){return e.textContent;})")
        check(sorted(subs) == ['Bangles', 'Blink-182', 'Blondie', 'Blur'], 'each song row shows its own artist: %r' % subs)
        await pg.screenshot(path=shots + '/vatag_album_page.png')

        # Songs imported before the tag was kept: split until the background pass reads it.
        await pg.evaluate("__t.tracks().forEach(function(t){ delete t.albumArtist; delete t.aaRead; }); __t.bump();")
        await open_albums(pg)
        before = await pg.evaluate(ALBUMS)
        check(sum(1 for a in before if a.startswith('Lego Rock Band')) == 4, 'untagged records split like before: %r' % before)
        await pg.evaluate("__t.backfillAlbumArtists()")
        await pg.wait_for_timeout(3000)
        after = await pg.evaluate(ALBUMS)
        check('Lego Rock Band / Various Artists · 4 songs' in after and 'Now 60 / Various Artists · 2 songs' in after,
              'background pass regroups from the file tags: %r' % after)
        # Only songs on an album name several artists share are read: Solo Record (one artist) is not.
        read = await pg.evaluate("__t.tracks().filter(function(t){ return t.aaRead; }).map(function(t){ return t.album; }).sort()")
        check(len(read) == 8 and 'Solo Record' not in read, 'only shared-name albums were read: %r' % read)

        # Reload: grouping holds from storage alone.
        await pg.reload(); await pg.wait_for_timeout(3000)
        await open_albums(pg)
        check('Lego Rock Band / Various Artists · 4 songs' in await pg.evaluate(ALBUMS), 'grouping survives a reload')
        check(not errs, 'no page errors %r' % errs[:3])
        await b.close()

asyncio.run(main())
