"""Build 227: a playlist can be added to Favorites (the heart on its page, or on its cover in Home's
Playlists row). Tapped in Favorites it plays at once, shuffled, and never runs out (like an artist's
Radio); its name follows renames and it goes when the playlist is deleted. Android Auto lists it as a
playable row that shuffles the playlist. Run: python3 tests/test_playlist_fav.py"""
import sys as _nsys, os as _nos; _nsys.path.insert(0, _nos.path.dirname(_nos.path.abspath(__file__))); from notice_auto import AUTO_NOTICE
import os, sys
_here = os.path.dirname(os.path.abspath(__file__))
_src = open(os.path.join(_here, 'test_home_playlists.py')).read()
_head = _src[:_src.index('async def main():')]
_head = _head.replace("PORT = 8801", "PORT = 8818").replace("srv_homepl", "srv_plfav")
FHOOK = r"""window.__f = { favs: function(){ return favorites.map(function(f){ return [f.type, f.name, favKey(f)]; }); },
 q: function(){ return { label: queueLabel, n: playQueue.length, names: playQueue.map(function(t){ return t.name; }), radio: radioCtx && radioCtx.kind, cur: currentStation && currentStation.name }; },
 topUp: function(){ queueIndex = playQueue.length - 1; topUpArtistRadio(); return playQueue.length; },
 open: function(id){ pushView(); runStationPlaylist(findStationPlaylistById(id)); },
 stub: function(){ audio.play = function(){ return Promise.resolve(); }; },
 mk: function(){ var songs = libraryTracks.slice(); stationPlaylists.push({ id: 'pl_road', label: 'Road', stations: songs.concat([{ stationuuid: 'st-1', name: 'Radio One', url: 'http://radio.example/one', urlToResolve: 'http://radio.example/one', favicon: '' }]) }); saveStationPlaylists(); renderStationPlaylistList(); return stationPlaylists[0].stations.length; } };
"""
_head = _head.replace("open(root + '/index.html', 'w').write(_src.replace(_mark, _mark + HOOK))", "open(root + '/index.html', 'w').write(_src.replace(_mark, _mark + HOOK + FHOOK))")
__file__ = os.path.join(_here, 'test_home_playlists.py')
exec(_head)

MK = "__f.mk()"

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
        for theme in ('dark', 'light'):
            ctx = await b.new_context(viewport={'width': 412, 'height': 900}, device_scale_factor=2, is_mobile=True, has_touch=True, color_scheme=theme)
            await ctx.add_init_script(MOCK); await ctx.add_init_script(AUTO_NOTICE)
            await ctx.add_init_script("try{ localStorage.setItem('radioPlayerTheme', '%s'); }catch(e){}" % theme)
            pg = await ctx.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
            await pg.route('**/*', lambda route: route.continue_() if '127.0.0.1' in route.request.url else route.abort())
            await pg.goto(f'http://127.0.0.1:{PORT}/index.html'); await pg.wait_for_timeout(2500)
            await pg.evaluate("""(function(){ var ov=document.getElementById('addMusicOverlay'); if(ov) ov.classList.add('open');
              var btn=document.getElementById('addMusicFolderBtn'); btn.disabled=false; btn.click(); })()""")
            for _ in range(40):
                await pg.wait_for_timeout(500)
                if len(await pg.evaluate('__t.tracks()')) >= 4: break
            await pg.evaluate("document.getElementById('addMusicOverlay').classList.remove('open')")
            n = await pg.evaluate(MK)
            check(n == 5, f'[{theme}] (playlist Road: 4 songs and a station)')
            # the heart on the playlist's page
            await pg.evaluate("__f.open('pl_road')"); await pg.wait_for_timeout(600)
            hb = await pg.evaluate("(()=>{ var b = document.getElementById('playlistFavBtn'); return { shown: b.offsetParent !== null, on: b.classList.contains('on'), label: b.getAttribute('aria-label') }; })()")
            check(hb['shown'] and not hb['on'] and hb['label'] == 'Add to Favorites', f'[{theme}] a playlist page has a heart {hb}')
            await pg.screenshot(path=f'{shots}/plfav-page-{theme}.png')
            await pg.evaluate("document.getElementById('playlistFavBtn').click()"); await pg.wait_for_timeout(300)
            check(await pg.evaluate("document.getElementById('playlistFavBtn').classList.contains('on')"), f'[{theme}] tapping it fills it')
            favs = await pg.evaluate('__f.favs()')
            check(['playlistRadio', 'Road', 'playlistradio:pl_road'] in favs, f'[{theme}] and the playlist is a favourite {favs}')
            # editing hides the heart
            await pg.evaluate("document.getElementById('editActiveCustomSearchBtn').click()"); await pg.wait_for_timeout(300)
            check(not await pg.evaluate("document.getElementById('playlistFavBtn').offsetParent !== null"), f'[{theme}] (hidden while editing)')
            await pg.evaluate("document.getElementById('editActiveCustomSearchBtn').click()"); await pg.wait_for_timeout(300)
            # Home's Favorites row: tap plays it shuffled at once
            await pg.evaluate('__h.home()'); await pg.wait_for_timeout(800)
            card = await pg.evaluate("(()=>{ var t = Array.from(document.querySelectorAll('#favoritesGrid .tile')).filter(function(x){ return /Road/.test(x.textContent); })[0]; return t ? { name: t.textContent.trim(), img: !!t.querySelector('.tile-art') } : null; })()")
            check(card is not None, f'[{theme}] it shows in Favorites on Home {card}')
            await pg.evaluate("document.getElementById('favoritesSection').scrollIntoView({ block: 'center' })"); await pg.wait_for_timeout(300)
            await pg.screenshot(path=f'{shots}/plfav-home-{theme}.png')
            await pg.evaluate('__f.stub()')
            await pg.evaluate("Array.from(document.querySelectorAll('#favoritesGrid .tile')).filter(function(x){ return /Road/.test(x.textContent); })[0].click()"); await pg.wait_for_timeout(1000)
            q = await pg.evaluate('__f.q()'); print(q)
            check(q['label'] == 'Road' and q['radio'] == 'playlist' and q['n'] >= 5 and sorted(q['names'][:5]) == sorted(['Kay 1', 'Kay 2', 'Kay 3', 'Lone', 'Radio One']), f'[{theme}] tapping it plays the whole playlist shuffled at once')
            check(q['cur'] == q['names'][0], f'[{theme}] starting with the first of the shuffle ({q["cur"]})')
            orders = set()
            for _ in range(4):
                await pg.evaluate("Array.from(document.querySelectorAll('#favoritesGrid .tile')).filter(function(x){ return /Road/.test(x.textContent); })[0].click()"); await pg.wait_for_timeout(300)
                orders.add(tuple((await pg.evaluate('__f.q()'))['names'][:5]))
            check(len(orders) > 1, f'[{theme}] a different order each time ({len(orders)} orders in 4)')
            before = (await pg.evaluate('__f.q()'))['n']
            grown = await pg.evaluate('__f.topUp()')
            check(grown > before, f'[{theme}] and it never runs out: near the end another shuffle is added ({grown})')
            # the Home Playlists row cover has a heart too, already on
            hrow = await pg.evaluate("(()=>{ var t = Array.from(document.querySelectorAll('#playlistsHomeGrid .tile')).filter(function(x){ return /Road/.test(x.textContent); })[0]; var h = t && t.querySelector('.tile-fav'); return h ? h.classList.contains('on') : null; })()")
            check(hrow is True, f'[{theme}] its cover in Home\'s Playlists row has a filled heart')
            # rename follows; delete removes
            await pg.evaluate("__h.rename('pl_road', 'Road Trip')"); await pg.wait_for_timeout(300)
            check(['playlistRadio', 'Road Trip', 'playlistradio:pl_road'] in await pg.evaluate('__f.favs()'), f'[{theme}] renaming the playlist renames the favourite')
            await pg.evaluate("Array.from(document.querySelectorAll('#playlistsHomeGrid .tile')).filter(function(x){ return /Road/.test(x.textContent); })[0].querySelector('.tile-fav').click()"); await pg.wait_for_timeout(300)
            check(not any(f[0] == 'playlistRadio' for f in await pg.evaluate('__f.favs()')), f'[{theme}] the cover\'s heart takes it out of Favorites again')
            await pg.evaluate("Array.from(document.querySelectorAll('#playlistsHomeGrid .tile')).filter(function(x){ return /Road/.test(x.textContent); })[0].querySelector('.tile-fav').click()"); await pg.wait_for_timeout(300)
            check(any(f[0] == 'playlistRadio' for f in await pg.evaluate('__f.favs()')), f'[{theme}] and puts it back')
            await pg.evaluate("__h.del('pl_road')"); await pg.wait_for_timeout(300)
            check(not any(f[0] == 'playlistRadio' for f in await pg.evaluate('__f.favs()')), f'[{theme}] deleting the playlist removes the favourite')
            check(not errs, f'[{theme}] no page errors {errs[:3]}')
            await ctx.close()
        await b.close()
    print('ALL PASSED' if not fails else f'FAILED {fails}')
    sys.exit(1 if fails else 0)

asyncio.run(main())
