"""Build 228: every delete or remove asks first, in one shared dialog (confirmDelete): Cancel, a tap
outside or Escape keep it; Delete/Remove goes ahead. Run: python3 tests/test_confirm_delete.py"""
import os, sys, re
_here = os.path.dirname(os.path.abspath(__file__))
_fav = open(os.path.join(_here, 'test_playlist_fav.py')).read()
FHOOK = re.search(r'FHOOK = r"""(.*?)"""', _fav, re.S).group(1)
FHOOK = FHOOK.replace("stub: function(){", "playFirst: function(){ audio.play = function(){ return Promise.resolve(); }; playTrackInList([libraryTracks[0]], libraryTracks[0], 'Test'); }, recents: function(){ return recentStations.map(function(x){ return x.name; }); }, stub: function(){")
_src = open(os.path.join(_here, 'test_home_playlists.py')).read()
_head = _src[:_src.index('async def main():')]
_head = _head.replace("PORT = 8801", "PORT = 8819").replace("srv_homepl", "srv_confirm")
_head = _head.replace("open(root + '/index.html', 'w').write(_src.replace(_mark, _mark + HOOK))", "open(root + '/index.html', 'w').write(_src.replace(_mark, _mark + HOOK + FHOOK))")
__file__ = os.path.join(_here, 'test_home_playlists.py')
exec(_head)
DLG = "(()=>{ var o = document.getElementById('confirmOverlay'); return { open: o.classList.contains('open'), title: document.getElementById('confirmTitle').textContent, msg: document.getElementById('confirmMsg').textContent, ok: document.getElementById('confirmOk').textContent }; })()"
PL = "stationPlaylistsLabels"

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
        for theme in ('dark', 'light'):
            ctx = await b.new_context(viewport={'width': 412, 'height': 900}, device_scale_factor=2, is_mobile=True, has_touch=True, color_scheme=theme)
            await ctx.add_init_script(MOCK)
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
            await pg.evaluate('__f.mk()')
            pls = lambda: pg.evaluate("__t.pl('Road')")
            # deleting a playlist from its page
            await pg.evaluate("__f.open('pl_road')"); await pg.wait_for_timeout(500)
            await pg.evaluate("document.getElementById('deleteActiveCustomSearchBtn').click()"); await pg.wait_for_timeout(300)
            d = await pg.evaluate(DLG); print(d)
            check(d['open'] and d['title'] == 'Delete playlist “Road”?' and d['ok'] == 'Delete', f'[{theme}] deleting a playlist asks first {d}')
            await pg.screenshot(path=f'{shots}/confirm-{theme}.png')
            await pg.evaluate("document.getElementById('confirmCancel').click()"); await pg.wait_for_timeout(300)
            check(not (await pg.evaluate(DLG))['open'] and await pls() is not None, f'[{theme}] Cancel keeps it')
            await pg.evaluate("document.getElementById('deleteActiveCustomSearchBtn').click()"); await pg.wait_for_timeout(300)
            await pg.keyboard.press('Escape'); await pg.wait_for_timeout(300)
            check(not (await pg.evaluate(DLG))['open'] and await pls() is not None, f'[{theme}] Escape keeps it')
            await pg.evaluate("document.getElementById('deleteActiveCustomSearchBtn').click()"); await pg.wait_for_timeout(300)
            await pg.mouse.click(10, 10); await pg.wait_for_timeout(300)
            check(not (await pg.evaluate(DLG))['open'] and await pls() is not None, f'[{theme}] a tap outside keeps it')
            # removing one entry in Edit
            await pg.evaluate("document.getElementById('editActiveCustomSearchBtn').click()"); await pg.wait_for_timeout(400)
            await pg.evaluate("document.querySelector('.playlist-edit-row .fav-remove-btn, .playlist-edit-row button[aria-label^=\"Remove\"]').click()"); await pg.wait_for_timeout(300)
            d = await pg.evaluate(DLG)
            check(d['open'] and d['ok'] == 'Remove' and 'Road' in d['msg'], f'[{theme}] removing an entry from a playlist asks first {d}')
            await pg.evaluate("document.getElementById('confirmOk').click()"); await pg.wait_for_timeout(400)
            check(len(await pls()) == 4, f'[{theme}] and Remove takes it out ({len(await pls())} left)')
            await pg.evaluate("document.getElementById('editActiveCustomSearchBtn').click()"); await pg.wait_for_timeout(300)
            await pg.evaluate("document.getElementById('deleteActiveCustomSearchBtn').click()"); await pg.wait_for_timeout(300)
            await pg.evaluate("document.getElementById('confirmOk').click()"); await pg.wait_for_timeout(400)
            check(await pls() is None, f'[{theme}] Delete deletes the playlist')
            # Continue Listening: the More menu's Remove
            await pg.evaluate("__f.playFirst()"); await pg.wait_for_timeout(1200)
            await pg.evaluate('__h.home()'); await pg.wait_for_timeout(600)
            first = (await pg.evaluate('__f.recents()'))[0]
            await pg.evaluate("document.querySelector('#recentGrid .tile .tile-more').click()"); await pg.wait_for_timeout(300)
            await pg.evaluate("document.getElementById('rowMenuRemove') ? document.getElementById('rowMenuRemove').click() : 0"); await pg.wait_for_timeout(300)
            d = await pg.evaluate(DLG)
            check(d['open'] and d['ok'] == 'Remove' and first in d['title'], f'[{theme}] removing from Continue Listening asks first {d}')
            await pg.evaluate("document.getElementById('confirmCancel').click()"); await pg.wait_for_timeout(300)
            check(first in await pg.evaluate('__f.recents()'), f'[{theme}] (Cancel keeps it)')
            await pg.evaluate("document.querySelector('#recentGrid .tile .tile-more').click()"); await pg.wait_for_timeout(300)
            await pg.evaluate("document.getElementById('rowMenuRemove').click()"); await pg.wait_for_timeout(300)
            await pg.evaluate("document.getElementById('confirmOk').click()"); await pg.wait_for_timeout(300)
            check(first not in await pg.evaluate('__f.recents()'), f'[{theme}] Remove removes it')
            # Now Playing's Remove from library
            await pg.evaluate("__f.playFirst()"); await pg.wait_for_timeout(800)
            await pg.evaluate("openNowPlaying(currentStation, false)") if False else None
            await pg.evaluate("document.getElementById('npDeleteBtn').click()"); await pg.wait_for_timeout(300)
            d = await pg.evaluate(DLG)
            check(d['open'] and 'from your library' in d['title'] and d['msg'] == 'The file stays on your phone.', f'[{theme}] Remove from library asks first {d}')
            await pg.evaluate("document.getElementById('confirmCancel').click()"); await pg.wait_for_timeout(300)
            check(len(await pg.evaluate('__t.tracks()')) == 4, f'[{theme}] (Cancel keeps the song)')
            # clearing history
            await pg.evaluate("document.getElementById('recentStationsHeading').click()"); await pg.wait_for_timeout(500)
            await pg.evaluate("document.getElementById('clearHistoryBtn').click()"); await pg.wait_for_timeout(300)
            d = await pg.evaluate(DLG)
            check(d['open'] and d['title'] == 'Clear history?' and d['ok'] == 'Clear', f'[{theme}] Clear history asks first {d}')
            await pg.evaluate("document.getElementById('confirmCancel').click()"); await pg.wait_for_timeout(300)
            check(not errs, f'[{theme}] no page errors {errs[:3]}')
            await ctx.close()
        await b.close()
    print('ALL PASSED' if not fails else f'FAILED {fails}')
    sys.exit(1 if fails else 0)

asyncio.run(main())
