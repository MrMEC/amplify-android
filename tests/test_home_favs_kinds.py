"""Build 235: the Favorites row at the top of Home shows only stations, artist radio and favourite
playlists. Artists, albums, songs, podcast episodes, Live TV channels, movies and TV episodes stay
off the row (they're still on the Favorites page, which the heading opens). Both themes at 412.
Run: python3 tests/test_home_favs_kinds.py (screenshots in /tmp/claude-0/t/shots)"""
import sys as _nsys, os as _nos; _nsys.path.insert(0, _nos.path.dirname(_nos.path.abspath(__file__))); from notice_auto import AUTO_NOTICE
import os, sys
_here = os.path.dirname(os.path.abspath(__file__))
_src = open(os.path.join(_here, 'test_home_playlists.py')).read()
_head = _src[:_src.index('async def main():')]
_head = _head.replace("PORT = 8801", "PORT = 8832").replace("srv_homepl", "srv_homefavkinds")
KHOOK = r"""window.__k = {
 seed: function(){
   var song = libraryTracks[0];
   var entry = buildArtistIndex().filter(function(e){ return e.tracks && e.tracks.length; })[0];
   stationPlaylists.push({ id: 'pl_road', label: 'Road Trip', stations: [song] });
   saveStationPlaylists();
   favorites = [
     { stationuuid: 'st-kiss', name: 'KISS FM', url: 'http://radio.example/kiss', urlToResolve: 'http://radio.example/kiss', favicon: '', tags: 'pop' },
     { type: 'artist', artistKey: entry.key, name: entry.name },
     artistRadioRecord(entry),
     { type: 'album', albumKey: albumKeyFor(song), name: song.album || 'Album' },
     song,
     { type: 'podcast', guid: 'ep-1', name: 'Episode One', collectionName: 'Some Show', collectionId: 99, episodeUrl: 'http://pod.example/1.mp3' },
     { stationuuid: 'ch-news', name: 'Ray TV News', url: 'http://tv.example/news.m3u8', urlToResolve: 'http://tv.example/news.m3u8', videoChannel: true, favicon: '' },
     { type: 'video', id: 'mv-1', videoKind: 'movie', name: 'Big Movie', year: 1999 },
     { type: 'video', id: 'ep-9', videoKind: 'episode', name: 'Pilot', show: 'Some Series', season: 1, episode: 1 },
     playlistRadioRecord(findStationPlaylistById('pl_road')),
     { stationuuid: 'st-jazz', name: 'Smooth Jazz 24', url: 'http://radio.example/jazz', urlToResolve: 'http://radio.example/jazz', favicon: '', tags: 'jazz' }
   ];
   saveFavorites();
   renderFavoritesSection();
   return { artist: entry.name, song: song.name, album: song.album };
 },
 row: function(){ return Array.from(document.querySelectorAll('#favoritesGrid .tile')).map(function(t){ var n = t.querySelector('.tile-name'); return n ? n.textContent : ''; }); },
 empty: function(){ var e = document.querySelector('#favoritesGrid .empty-state'); return e ? e.textContent : ''; },
 onlyOthers: function(){ favorites = favorites.filter(function(f){ return !isHomeFavorite(f); }); saveFavorites(); renderFavoritesSection(); },
 page: function(){ openHomeSectionPage('favorites'); },
 pageNames: function(){ return Array.from(document.querySelectorAll('#stationsGrid .tile-name, #stationsGrid .song-row-title, #stationsGrid .row-name, #stationsGrid .fav-artist-name')).map(function(e){ return e.textContent; }); },
 count: function(){ return favorites.length; }
};
"""
_head = _head.replace("open(root + '/index.html', 'w').write(_src.replace(_mark, _mark + HOOK))", "open(root + '/index.html', 'w').write(_src.replace(_mark, _mark + HOOK + KHOOK))")
__file__ = os.path.join(_here, 'test_home_playlists.py')
exec(_head)


async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
        for theme in ('dark', 'light'):
            T = f'[{theme}]'
            ctx = await b.new_context(viewport={'width': 412, 'height': 900}, device_scale_factor=2, is_mobile=True, has_touch=True, color_scheme=theme)
            await ctx.add_init_script(MOCK); await ctx.add_init_script(AUTO_NOTICE)
            await ctx.add_init_script("try{ localStorage.setItem('radioPlayerTheme', '%s'); }catch(e){}" % theme)
            pg = await ctx.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
            await pg.route('**/*', lambda route: route.continue_() if '127.0.0.1' in route.request.url else route.abort())
            await pg.goto(f'http://127.0.0.1:{PORT}/index.html'); await pg.wait_for_timeout(2500)
            await pg.evaluate("""(function(){ var ov=document.getElementById('addMusicOverlay'); if(ov) ov.classList.add('open');
              var btn=document.getElementById('addMusicFolderBtn'); btn.disabled=false; btn.click(); })()""")
            for _ in range(60):
                await pg.wait_for_timeout(500)
                if len(await pg.evaluate('__t.tracks()')) >= 4: break
            await pg.evaluate("(function(){ var ov=document.getElementById('addMusicOverlay'); if(ov) ov.classList.remove('open'); })()")
            await pg.evaluate('__h.home()'); await pg.wait_for_timeout(800)
            info = await pg.evaluate('__k.seed()')
            await pg.evaluate("window.scrollTo(0, 0)"); await pg.wait_for_timeout(500)
            row = await pg.evaluate('__k.row()')
            want = ['KISS FM', info['artist'] + ' Radio', 'Road Trip', 'Smooth Jazz 24']
            check(row == want, f'{T} the row has only stations, artist radio and the playlist, in favourites order {row}')
            for name in [info['artist'], info['song'], 'Episode One', 'Ray TV News', 'Big Movie', 'Pilot']:
                check(name not in row, f'{T} {name!r} is not in the row')
            check(await pg.evaluate('__k.count()') == 11, f'{T} nothing was taken out of favourites')
            await pg.evaluate("document.getElementById('favoritesSection').scrollIntoView({block:'start'}); window.scrollBy(0, -70)"); await pg.wait_for_timeout(500)
            await pg.screenshot(path=f'{shots}/home-favs-kinds-{theme}.png')
            # the Favorites page still has everything
            await pg.evaluate('__k.page()'); await pg.wait_for_timeout(900)
            names = await pg.evaluate('__k.pageNames()')
            check(all(x in names for x in ['KISS FM', 'Ray TV News', 'Big Movie', 'Episode One', info['song']]), f'{T} the Favorites page still lists them all {names}')
            await pg.evaluate("document.getElementById('detailBackBtn').click()"); await pg.wait_for_timeout(700)
            # only other kinds: the row says how to add one
            await pg.evaluate('__k.onlyOthers()'); await pg.wait_for_timeout(300)
            check(await pg.evaluate('__k.row()') == [] and await pg.evaluate('__k.empty()') == 'Tap the heart on any station to save it here.',
                  f'{T} with no stations among them the row shows how to add one')
            check(not errs, f'{T} no page errors {errs[:3]}')
            await ctx.close()
        await b.close()
    print('ALL PASSED' if not fails else f'FAILED {fails}')

asyncio.run(main())
