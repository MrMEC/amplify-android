"""Albums with several artists in one folder, sharing a name and cover, group as Various Artists."""
import asyncio, os, json, threading, http.server, functools, shutil, subprocess
from playwright.async_api import async_playwright

PORT = 8786
root = '/tmp/claude-0/t/srv_comp'
shots = '/tmp/claude-0/t/shots'
os.makedirs(shots, exist_ok=True)
shutil.rmtree(root, ignore_errors=True)
os.makedirs(root)
# The page keeps everything inside its own scope, so the served copy gets a small hook into it.
HOOK = ("window.__t = { tracks: function(){ return libraryTracks; }, bump: function(){ compilationVersion++; },"
        " runLibrarySection: runLibrarySection, openArtistPage: openArtistPage, artistMatchKey: artistMatchKey,"
        " renderLibraryList: function(){ renderLibraryList(); }, backfillArtSigs: backfillArtSigs, idbDo: idbDo,"
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


def song(path, title, artist, album, track, art):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    subprocess.run(['ffmpeg', '-loglevel', 'error', '-y', '-f', 'lavfi', '-i', 'sine=frequency=440:duration=2',
                    '-i', art, '-map', '0:a', '-map', '1:v', '-c:a', 'libmp3lame', '-b:a', '64k', '-c:v', 'png',
                    '-id3v2_version', '3', '-disposition:v', 'attached_pic',
                    '-metadata', f'title={title}', '-metadata', f'artist={artist}', '-metadata', f'album={album}',
                    '-metadata', f'track={track}', path], check=True)


red, blue, green, gold = cover('red', 'red'), cover('blue', 'blue'), cover('green', 'green'), cover('gold', 'gold')
M = root + '/Music'
# A compilation: three artists, one folder, one cover.
song(f'{M}/Now 50/01.mp3', 'Opening', 'Alpha Band', 'Now 50', 1, red)
song(f'{M}/Now 50/02.mp3', 'Middle', 'Beta Singer', 'Now 50', 2, red)
song(f'{M}/Now 50/03.mp3', 'Closing', 'Gamma Crew', 'Now 50', 3, red)
# Same name in another folder: a different record, kept apart.
song(f'{M}/Other/01.mp3', 'Elsewhere', 'Delta', 'Now 50', 1, gold)
# Two artists, same folder and name, different covers: not a compilation.
song(f'{M}/Split/01.mp3', 'Left', 'Echo', 'Split', 1, green)
song(f'{M}/Split/02.mp3', 'Right', 'Foxtrot', 'Split', 2, blue)
# An ordinary one-artist album.
song(f'{M}/Band/01.mp3', 'One', 'Alpha Band', 'Solo Record', 1, blue)
song(f'{M}/Band/02.mp3', 'Two', 'Alpha Band', 'Solo Record', 2, blue)

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

ALBUMS = """(function(){ return Array.from(document.querySelectorAll(".tile[data-entity='album']")).map(function(t){
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
        await pg.add_init_script(MOCK)
        await pg.goto(f'http://127.0.0.1:{PORT}/index.html'); await pg.wait_for_timeout(2500)
        await pg.evaluate("""(function(){ var ov=document.getElementById('addMusicOverlay'); if(ov) ov.classList.add('open');
          var btn=document.getElementById('addMusicFolderBtn'); btn.disabled=false; btn.click(); })()""")
        for _ in range(60):
            await pg.wait_for_timeout(500)
            if await pg.evaluate('__t.tracks().length') >= len(files):
                break
        check(await pg.evaluate('__t.tracks().length') == len(files), 'all songs imported')
        check(await pg.evaluate("__t.tracks().every(function(t){ return !!t.artSig; })"), 'covers fingerprinted on import')

        await open_albums(pg)
        albums = await pg.evaluate(ALBUMS)
        print(albums)
        check('Now 50 / Various Artists · 3 songs' in albums, 'compilation listed once as Various Artists')
        check(sum(1 for a in albums if a.startswith('Now 50')) == 2, 'same name in another folder kept apart')
        check('Now 50 / Delta · 1 song' in albums, 'other-folder album keeps its artist')
        check('Split / Echo · 1 song' in albums and 'Split / Foxtrot · 1 song' in albums, 'different covers stay split')
        check('Solo Record / Alpha Band · 2 songs' in albums, 'ordinary album unchanged')
        await pg.screenshot(path=shots + '/comp_albums.png')

        # Album page: Various Artists as plain text, each song shows its own artist.
        await pg.evaluate("""(function(){ var t=Array.from(document.querySelectorAll(".tile[data-entity='album']"))
          .filter(function(t){ return /Various/.test(t.textContent); })[0]; t.click(); })()""")
        await pg.wait_for_timeout(800)
        hero = await pg.evaluate("document.getElementById('albumHeroArtist').textContent + '|' + document.getElementById('albumHeroArtist').tagName")
        check(hero == 'Various Artists|DIV', 'album page names Various Artists, not a link')
        subs = await pg.evaluate("Array.from(document.querySelectorAll('.song-row .song-row-sub')).map(function(e){return e.textContent;})")
        check(subs == ['Alpha Band', 'Beta Singer', 'Gamma Crew'], 'each song row shows its artist: %r' % subs)
        await pg.screenshot(path=shots + '/comp_album_page.png')

        # Artist page for one of its artists lists the compilation.
        await pg.evaluate("__t.openArtistPage(__t.artistMatchKey('Beta Singer'))")
        await pg.wait_for_timeout(800)
        on_artist = await pg.evaluate(ALBUMS)
        check(any(a.startswith('Now 50 /') for a in on_artist), 'artist page shows the compilation: %r' % on_artist)

        # Android Auto: one album, listed under each of its artists.
        await pg.evaluate("__t.renderLibraryList()"); await pg.wait_for_timeout(4000)
        car = await pg.evaluate("window.__car ? (typeof window.__car === 'string' ? window.__car : JSON.stringify(window.__car)) : ''")
        check(bool(car), 'car library published')
        if car:
            lib = json.loads(car)
            va = [al for al in lib['albums'] if al['artist'] == 'Various Artists']
            check(len(va) == 1 and len(va[0]['tracks']) == 3, 'car library has one Various Artists album')
            for name in ('Alpha Band', 'Beta Singer', 'Gamma Crew'):
                ar = [x for x in lib['artists'] if x['name'] == name][0]
                check(va[0]['key'] in ar['albums'], 'car lists the compilation under ' + name)

        # Songs imported before fingerprints: the background pass fills them in and regroups.
        await pg.evaluate("__t.tracks().forEach(function(t){ delete t.artSig; }); __t.bump();")
        await open_albums(pg)
        before = await pg.evaluate(ALBUMS)
        check(any(a.startswith('Split / Various Artists') for a in before), 'unfingerprinted covers count as matching')
        await pg.evaluate("__t.backfillArtSigs()")
        await pg.wait_for_timeout(2500)
        after = await pg.evaluate(ALBUMS)
        check('Split / Echo · 1 song' in after and 'Now 50 / Various Artists · 3 songs' in after,
              'background pass regroups by cover: %r' % after)
        stored = await pg.evaluate("""__t.idbDo([__t.store()],'readonly',function(tx){ return tx.objectStore(__t.store()).getAll(); })
          .then(function(r){ return r.filter(function(t){ return t.artSig; }).length; })""")
        check(stored == len(files), 'fingerprints saved back')

        # A favourite saved against an old per-artist key still opens the album.
        fav = await pg.evaluate("__t.albumEntryForFav({albumKey: __t.legacyAlbumKeyFor(__t.tracks().filter(function(t){return t.artist==='Beta Singer';})[0])}).tracks.length")
        check(fav == 3, 'old album key resolves to the compilation')

        # Reload: grouping holds from storage alone.
        await pg.reload(); await pg.wait_for_timeout(3000)
        await open_albums(pg)
        check('Now 50 / Various Artists · 3 songs' in await pg.evaluate(ALBUMS), 'grouping survives a reload')
        check(not errs, 'no page errors %r' % errs[:3])
        await b.close()

asyncio.run(main())
