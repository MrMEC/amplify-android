"""Build 393: Settings > Appearance > Sizes & text. Cover sizes for cover rows, artist circles, music video
thumbnails, movie/TV posters and albums/stations (with their text size), and the most lines a title or a detail
line may run to. Also that the same kind of row has the same size and text size on every page (Profile's
favorites = Home's favorites; Library rows = Home rows). Reuses the phone mock and library of
test_artist_videos.py. Run: python3 tests/test_layout_sizes.py (screenshots in /tmp/claude-0/t/shots)"""
import asyncio, json, sys, os, re
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
__file__ = os.path.join(HERE, 'test_artist_videos.py')
_src = open(__file__).read().split("async def main():")[0].replace("PORT = 8802", "PORT = 8883").replace("srv_artvid", "srv_layout")
exec(_src)
BACKUP = json.load(open(os.path.join(HERE, 'fixtures', 'layout_backup.json')))
W = lambda pg, js: pg.evaluate(js)
async def home_sizes(pg):
    await pg.evaluate("document.querySelector('.mobile-nav-btn[data-nav=home]').click()"); await pg.wait_for_timeout(700)
    return await pg.evaluate("""(()=>{ function w(sel){ var e=document.querySelector(sel); return e? Math.round(e.getBoundingClientRect().width):null; }
      return { fav: w('#favoritesGrid .tile-art'), recent: w('#recentGrid .tile-art'), podcasts: w('#latestPodcastsGrid .tile-art'), playlists: w('#playlistsHomeGrid .tile-art'),
               topArtists: w('#topArtistsGrid .tile-art') }; })()""")
async def setrange(pg, k, v):
    await pg.evaluate("([k,v])=>{ var r=document.getElementById('sz-'+k); r.value=String(v); r.dispatchEvent(new Event('input')); r.dispatchEvent(new Event('change')); }", [k, v])
    await pg.wait_for_timeout(250)
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
        ctx = await b.new_context(viewport={'width': 390, 'height': 844}, device_scale_factor=2, is_mobile=True, has_touch=True, color_scheme='dark')
        await ctx.add_init_script(MOCK); await ctx.add_init_script(AUTO_NOTICE)
        pg = await ctx.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.route('**/*', route)
        await pg.goto(f'http://127.0.0.1:{PORT}/index.html'); await pg.wait_for_timeout(2500)
        await pg.evaluate("""(function(){ var ov=document.getElementById('addMusicOverlay'); if(ov) ov.classList.add('open');
          var btn=document.getElementById('addMusicFolderBtn'); btn.disabled=false; btn.click(); })()""")
        for _ in range(60):
            await pg.wait_for_timeout(500)
            if await pg.evaluate('__v.tracks()') >= 5: break
        await pg.evaluate("document.getElementById('addMusicOverlay').classList.remove('open')")
        await pg.wait_for_timeout(300); await pg.evaluate('__v.hide()')
        await pg.evaluate("(d)=>{ __t.ev('importBackupData')(d, 'merge'); }", BACKUP); await pg.wait_for_timeout(2000)
        await pg.evaluate("document.querySelectorAll('button').forEach(x=>{ if(x.textContent.trim()==='OK' && x.offsetParent) x.click(); })"); await pg.wait_for_timeout(400)
        # ---- defaults: same kind of row, same size and text ----
        s0 = await home_sizes(pg)
        check(s0['fav'] == s0['recent'] == s0['podcasts'] == s0['playlists'] == 132, f'Home: favorites and every cover row are 132px {s0}')
        txt = await pg.evaluate("""(()=>{ var o={}; document.querySelectorAll('.tile:not(.tile-row):not(.song-row) .tile-name').forEach(function(e){ if(e.offsetParent) o[Math.round(parseFloat(getComputedStyle(e).fontSize)*10)/10]=1; }); return Object.keys(o); })()""")
        check(txt == ['13'], f'Home: all cover names are one size {txt}')
        await pg.evaluate("__t.ev('openMyLibraryHome()')"); await pg.wait_for_timeout(800)
        lib = await pg.evaluate("""(()=>{ var o={}; document.querySelectorAll('.cl-row .tile .tile-name').forEach(function(e){ o[Math.round(parseFloat(getComputedStyle(e).fontSize)*10)/10]=1; });
           var a=document.querySelector('.cl-row .tile-art'); return { names: Object.keys(o), w: a? Math.round(a.getBoundingClientRect().width):null }; })()""")
        check(lib['names'] == ['13'] and lib['w'] == 132, f'Library rows match Home rows (cover and text) {lib}')
        sub = await pg.evaluate("""(()=>{ var e=document.querySelector('.cl-row .tile-sub'); return e? parseFloat(getComputedStyle(e).fontSize):null; })()""")
        check(sub == 11.5, f'Library detail text is Home\'s ({sub})')
        await pg.evaluate("__t.ev('openAlbumsPlaceholder') ") if False else None
        # ---- the settings ----
        await pg.evaluate("__t.ev('openSettings(\"appearance-sizes\")')"); await pg.wait_for_timeout(500)
        labels = await pg.evaluate("Array.from(document.querySelectorAll('#szRows .settings-label')).map(e=>e.textContent)")
        check(labels == ['Cover rows', 'Artist circles', 'Music video thumbnails', 'Movies & TV shows', 'Albums & stations', 'Albums & stations text', 'Title lines', 'Detail lines', 'Reset sizes and lines'], f'settings rows {labels}')
        check(await pg.evaluate("document.getElementById('sz-titleLines').value") == '3' and await pg.evaluate("document.getElementById('sz-subLines').value") == '2', 'lines default to 3 for titles and 2 for details')
        await pg.screenshot(path=f'{shots}/layout-settings-top.png')
        await pg.evaluate("document.getElementById('szRows').scrollIntoView({block:'start'})"); await pg.wait_for_timeout(300)
        await pg.screenshot(path=f'{shots}/layout-settings.png')
        # cover rows 150%
        await setrange(pg, 'cover', 150)
        await pg.evaluate("__t.ev('closeSettings()')"); await pg.wait_for_timeout(500)
        s1 = await home_sizes(pg)
        check(s1['fav'] == s1['recent'] == s1['podcasts'] == s1['playlists'] == 198, f'cover rows 150%: favorites and all cover rows 198px {s1}')
        check(s1['topArtists'] == s0['topArtists'], f'artist circles unchanged {s1["topArtists"]}')
        await pg.screenshot(path=f'{shots}/layout-cover150.png')
        pf = await pg.evaluate("__t.ev('openProfile()'); new Promise(r=>setTimeout(()=>{ var e=document.querySelector('#pfFavs .shortcut'); r(e? Math.round(e.getBoundingClientRect().width):null); },500))")
        check(pf == 198, f'Profile favorites match Home favorites (150%): {pf}')
        await pg.screenshot(path=f'{shots}/layout-profile150.png')
        await pg.evaluate("__t.ev('closeProfile ? closeProfile() : 0')"); await pg.wait_for_timeout(300)
        await pg.evaluate("__t.ev('openSettings(\"appearance-sizes\")')"); await pg.wait_for_timeout(400)
        await setrange(pg, 'cover', 70)
        await pg.evaluate("__t.ev('closeSettings()')"); await pg.wait_for_timeout(400)
        s2 = await home_sizes(pg)
        check(s2['fav'] == s2['recent'] == 92 or abs(s2['fav'] - 92) <= 1, f'cover rows 70%: {s2}')
        await pg.screenshot(path=f'{shots}/layout-cover70.png')
        await pg.evaluate("__t.ev('openSettings(\"appearance-sizes\")')"); await pg.wait_for_timeout(400)
        await setrange(pg, 'cover', 100)
        # artists
        await setrange(pg, 'artist', 130)
        await pg.evaluate("__t.ev('closeSettings()')"); await pg.wait_for_timeout(400)
        s3 = await home_sizes(pg)
        ta = await pg.evaluate("(()=>{ var e=document.querySelector('#topArtistsGrid .tile'); return e? Math.round(e.getBoundingClientRect().width):null; })()")
        base_ta = await pg.evaluate("1")
        check(s3['fav'] == 132 and (ta is None or ta >= 100), f'artist circles 130%: covers unchanged, circles bigger ({ta})')
        await pg.evaluate("__t.ev('openMyLibraryHome()')"); await pg.wait_for_timeout(700)
        fa = await pg.evaluate("(()=>{ var e=document.querySelector('.fav-artist-thumb'); return e? Math.round(e.getBoundingClientRect().width):null; })()")
        check(fa == 73, f'Favorite Artists in Library follow artist size (56 x 1.3): {fa}')
        await pg.screenshot(path=f'{shots}/layout-artists130.png')
        await pg.evaluate("__t.ev('openSettings(\"appearance-sizes\")')"); await pg.wait_for_timeout(400)
        await setrange(pg, 'artist', 100)
        # albums: phone = covers across
        await setrange(pg, 'album', 60)
        cols = await pg.evaluate("getComputedStyle(document.documentElement).getPropertyValue('--album-cols').trim()")
        check(cols == '3', f'albums 60%: three across on a phone ({cols})')
        await pg.evaluate("__t.ev('closeSettings()')"); await pg.wait_for_timeout(300)
        await pg.evaluate("__t.ev('openMyLibraryHome()')"); await pg.wait_for_timeout(500)
        await pg.evaluate("(()=>{ var t=Array.from(document.querySelectorAll('.tile[data-entity=library-section]')).find(x=>x.querySelector('.tile-name').textContent==='Albums'); t&&t.click(); })()"); await pg.wait_for_timeout(900)
        aw = await pg.evaluate("(()=>{ var e=document.querySelector('.tile[data-entity=album] .tile-art'); return e? Math.round(e.getBoundingClientRect().width):null; })()")
        check(aw is not None and aw < 120, f'Albums page: three across ({aw}px)')
        await pg.screenshot(path=f'{shots}/layout-albums60.png')
        await pg.evaluate("__t.ev('openSettings(\"appearance-sizes\")')"); await pg.wait_for_timeout(400)
        await setrange(pg, 'album', 100); await setrange(pg, 'albumfs', 130)
        await pg.evaluate("__t.ev('closeSettings()')"); await pg.wait_for_timeout(500)
        fs = await pg.evaluate("(()=>{ var e=document.querySelector('.tile[data-entity=album] .tile-name'); return e? parseFloat(getComputedStyle(e).fontSize):null; })()")
        check(fs == 16.9, f'albums text 130%: names {fs}px')
        await pg.screenshot(path=f'{shots}/layout-albums-font130.png')
        await pg.evaluate("__t.ev('openSettings(\"appearance-sizes\")')"); await pg.wait_for_timeout(400)
        await setrange(pg, 'albumfs', 100)
        # lines
        await pg.evaluate("""(()=>{ var s=document.getElementById('sz-titleLines'); s.value='1'; s.dispatchEvent(new Event('change')); })()"""); await pg.wait_for_timeout(200)
        await pg.evaluate("__t.ev('closeSettings()')"); await pg.wait_for_timeout(300)
        await pg.evaluate("__t.ev('openPodcastsHome()')"); await pg.wait_for_timeout(900)
        lc = await pg.evaluate("(()=>{ var e=document.querySelector('.song-row-title'); var cs=getComputedStyle(e); return [cs.webkitLineClamp, cs.display]; })()")
        check(lc[0] == '1', f'title lines 1: {lc}')
        await pg.screenshot(path=f'{shots}/layout-lines1.png')
        await pg.evaluate("__t.ev('openSettings(\"appearance-sizes\")')"); await pg.wait_for_timeout(400)
        await pg.evaluate("""(()=>{ var s=document.getElementById('sz-titleLines'); s.value='0'; s.dispatchEvent(new Event('change')); var d=document.getElementById('sz-subLines'); d.value='3'; d.dispatchEvent(new Event('change')); })()"""); await pg.wait_for_timeout(200)
        await pg.evaluate("__t.ev('closeSettings()')"); await pg.wait_for_timeout(400)
        lc = await pg.evaluate("(()=>{ var e=document.querySelector('.song-row-title'); var cs=getComputedStyle(e); var cut=Array.from(document.querySelectorAll('.song-row-title')).filter(x=>x.scrollHeight>x.clientHeight+1).length; return [cs.webkitLineClamp, cut]; })()")
        check(lc[0] == 'none' and lc[1] == 0, f'title lines: no limit, nothing cut off {lc}')
        await pg.screenshot(path=f'{shots}/layout-lines-none.png')
        # persistence, backups, reset
        st = await pg.evaluate("JSON.parse(localStorage.getItem('radioPlayerLayout'))")
        check(st['titleLines'] == 0 and st['subLines'] == 3, f'stored {st}')
        await pg.reload(); await pg.wait_for_timeout(2500)
        v = await pg.evaluate("getComputedStyle(document.documentElement).getPropertyValue('--lines-title').trim()")
        check(v == 'none', f'kept after a restart ({v})')
        check('radioPlayerLayout' in await pg.evaluate("window.__amplifyKvKeys || []"), 'in backups')
        await pg.evaluate("__t.ev('openSettings(\"appearance-sizes\")')"); await pg.wait_for_timeout(400)
        await pg.click('#szResetBtn'); await pg.wait_for_timeout(300)
        check(await pg.evaluate("document.getElementById('sz-titleLines').value") == '3' and await pg.evaluate("document.getElementById('sz-cover').value") == '100', 'Reset puts everything back')
        # ---- the rows and grids this data didn't fill: built here, sized by the same rules ----
        await pg.evaluate("document.querySelector('.mobile-nav-btn[data-nav=home]').click()"); await pg.wait_for_timeout(500)
        PROBE = """(()=>{ var h=document.getElementById('homeProbe'); if(h) h.remove(); h=document.createElement('div'); h.id='homeProbe';
          h.innerHTML='<div class="home-row"><div class="tile-grid" id="topArtistsGrid"><div class="tile" data-entity="artist"><div class="tile-art"></div><div class="tile-name">A</div></div></div></div>'
           +'<div class="artist-yt-row"><span class="yt-tile"><span class="yt-thumb"></span><span class="yt-title">T</span></span></div>'
           +'<div class="tile-grid" id="posterProbe">'+'<div class="tile vposter"><div class="tile-art vposter-art"></div><div class="tile-name">P</div></div>'.repeat(6)+'</div>';
          document.getElementById('browseView') ? document.body.appendChild(h) : document.body.appendChild(h);
          function w(sel){ var e=document.querySelector('#homeProbe '+sel); return e? Math.round(e.getBoundingClientRect().width):null; }
          return { ta: w('#topArtistsGrid > .tile'), yt: w('.yt-tile'), cols: getComputedStyle(document.getElementById('posterProbe')).gridTemplateColumns.split(' ').length }; })()"""
        base = await pg.evaluate(PROBE)
        check(base['ta'] == 73 and base['yt'] == 235 and base['cols'] == 2, f'standard sizes on a 390px phone: Top Artists 73, video thumbnails 235, posters 2 across {base}')
        await pg.evaluate("__t.ev('openSettings(\"appearance-sizes\")')"); await pg.wait_for_timeout(400)
        await setrange(pg, 'artist', 120); await setrange(pg, 'video', 80); await setrange(pg, 'poster', 60)
        await pg.evaluate("__t.ev('closeSettings()')"); await pg.wait_for_timeout(300)
        big = await pg.evaluate(PROBE)
        check(big['ta'] == 87 and big['yt'] == 188 and big['cols'] == 3, f'artist 120% -> 87, video 80% -> 188, posters 60% -> 3 across {big}')
        await pg.screenshot(path=f'{shots}/layout-probe.png')
        await pg.evaluate("document.getElementById('homeProbe').remove()")
        check(not errs, f'no page errors {errs[:3]}')
        await b.close()
    print('FAILED %s' % fails if fails else 'ALL PASSED')
asyncio.run(main())
