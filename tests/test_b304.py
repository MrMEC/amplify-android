"""Build 304 (Mark): grey rings on artist circles; three artists across on the Artists page; Back on artist pages goes to the page you came from; no favourite star on the Music Videos artists. Built on test_b301 / Build 301 (Mark): Watch > Music Videos: every music video on the phone by artist (artists with
videos but no songs included), Other Videos for the rest; an artist's page plays their videos.
Build 302: no Artist button, the name links to the artist page, the artist page heading links back, Recently Added shows the artist. Run: python3 tests/test_b301.py (screenshots in /tmp/claude-0/t/shots)"""
import os, sys, json
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
__file__ = os.path.join(HERE, 'test_daily_mixes.py')
src = open(os.path.join(HERE, 'test_daily_mixes.py')).read()
src = src[:src.index('async def run(theme):')]
src = src.replace('PORT = 8803', 'PORT = 8897').replace("srv_daily'", "srv_b304'")
src = src.replace('" stopPlay:', '''" mv301: { seed: function(files){ musicVideos.files = files.map(function(f, i){ return { uri: 'content://v/' + i, name: f[0].split('/').pop(), relPath: f[0], size: 1000 + i, lastModified: f[1], tree: 't' }; });"
  "     musicVideos.files.forEach(function(f, i){ videoInfo[f.uri] = { d: 200 + i * 10, w: 640, h: 360, t: '' }; }); saveMusicVideos(); mvCatalogCache = null; },"
  "   where: function(){ return { heading: stationsHeading.textContent, artist: activeArtistKey, sect: activeLibrarySection, home: document.body.classList.contains('home-view'), video: onVideoView, vdetail: onVideoDetailView, mv: (document.querySelector('.mv-hero-name') || {}).textContent || '', hist: viewHistory.map(function(v){ return v.label; }) }; },"
  "   back: function(){ var b = document.getElementById('detailBackBtn'); var vis = b && getComputedStyle(b).display !== 'none'; if(vis){ b.click(); return 'detailBack'; } return 'none'; },"
  "   key: function(n){ return artistMatchKey(n); },"
  "   np: function(){ var t = libraryTracks.filter(function(x){ return x.artist === 'Prince'; })[0]; audio.play = function(){ return Promise.resolve(); }; playEntity(t); setTimeout(function(){ openNowPlaying(currentStation); }, 500); },"
  "   watch: function(){ videoTab = 'music'; pushView(); openVideoHome(); },"
  "   q: function(){ return { n: playQueue.length, cur: currentStation && currentStation.name, kind: currentStation && currentStation.videoKind, label: queueLabel }; } },"
  " stopPlay:''')
exec(src)
FILES = [
  ('Music/Prince/Prince - Prince 01 (Official Video).mp4', 5000),
  ('Music/Prince/Prince - Purple Rain.mp4', 9000),
  ('Music/Madonna/Madonna - Vogue.mp4', 3000),
  ('Music/Videos/Janet Jackson - Rhythm Nation.mp4', 8000),
  ('Music/Videos/Janet Jackson feat. Q-Tip - Got Til Its Gone.mp4', 7000),
  ('Music/Sade/Smooth Operator.mp4', 6000),
  ('Music/Videos/random clip.mp4', 4000),
  ('Music/Videos/01 - Something.mp4', 1000),
]
TILES = "[...document.querySelectorAll('#stationsGrid .tile.mv-artist')].map(t => t.querySelector('.tile-name').textContent + '|' + (t.querySelector('.tile-sub') || {}).textContent)"

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
        ctx = await b.new_context(viewport={'width': 390, 'height': 844}, device_scale_factor=3, is_mobile=True, has_touch=True, color_scheme='dark')
        await ctx.add_init_script(MOCK); await ctx.add_init_script(AUTO_NOTICE)
        pg = await ctx.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.route('**/*', lambda route: route.continue_() if '127.0.0.1' in route.request.url else route.abort())
        await pg.goto(f'http://127.0.0.1:{PORT}/index.html'); await pg.wait_for_timeout(2500)
        await pg.evaluate("""(function(){ var ov=document.getElementById('addMusicOverlay'); if(ov) ov.classList.add('open');
          var btn=document.getElementById('addMusicFolderBtn'); btn.disabled=false; btn.click(); })()""")
        for _ in range(90):
            await pg.wait_for_timeout(500)
            if await pg.evaluate("__d.n()") >= len(SONGS): break
        await pg.evaluate("document.getElementById('addMusicOverlay').classList.remove('open'); try{ hideImportPanel(); setStatus('', false); }catch(e){}")
        await pg.evaluate("(f) => __d.mv301.seed(f)", [list(x) for x in FILES])
        # Library > Artists
        await pg.evaluate("document.querySelector('.mobile-nav-btn[data-nav=library]').click()"); await pg.wait_for_timeout(800)
        await pg.evaluate("[...document.querySelectorAll('#stationsGrid .tile, #stationsGrid button, #stationsGrid a, #stationsGrid [role=button]')].find(e => /^\\s*Artists/.test(e.textContent)).click()"); await pg.wait_for_timeout(1000)
        t = await pg.evaluate("(()=>{ const t = [...document.querySelectorAll('#stationsGrid .tile[data-entity=artist]')]; const tops = new Set(t.slice(0, 6).map(x => Math.round(x.getBoundingClientRect().top))); return { n: t.length, perRow: t.filter(x => Math.round(x.getBoundingClientRect().top) === Math.round(t[0].getBoundingClientRect().top)).length, font: getComputedStyle(t[0].querySelector('.tile-name')).fontSize, border: getComputedStyle(t[0].querySelector('.tile-art')).border }; })()")
        print('artists', t)
        check(t['perRow'] == 3, f'three artists per row on the Artists page {t}')
        check(t['font'] == '10px', f'artist names keep their size {t["font"]}')
        check(t['border'] .endswith('solid rgb(58, 58, 62)'), f'a thin solid grey ring, as in Top Artists {t["border"]}')
        await pg.screenshot(path=f'{shots}/b304-artists.png')
        # Library > Artists > artist > Back
        await pg.evaluate("[...document.querySelectorAll('#stationsGrid .tile[data-entity=artist]')].find(t => t.textContent.indexOf('Prince') !== -1).click()"); await pg.wait_for_timeout(1000)
        await pg.evaluate("__d.mv301.back()"); await pg.wait_for_timeout(800)
        w = await pg.evaluate("__d.mv301.where()")
        check(w['heading'] == 'Artists' and not w['artist'], f'from the Artists list, Back goes back to it {w}')
        # Music Videos > artist videos > name > artist page > Back
        await pg.evaluate("__d.mv301.watch()"); await pg.wait_for_timeout(800)
        mvt = await pg.evaluate("(()=>{ const t = [...document.querySelectorAll('.tile.mv-artist')]; return { favs: t.filter(x => x.querySelector('.tile-fav')).length, border: getComputedStyle(t[0].querySelector('.tile-art')).border }; })()")
        check(mvt['favs'] == 0, f'no favourite star on the Music Videos artists {mvt}')
        check(mvt['border'] .endswith('solid rgb(58, 58, 62)'), f'grey ring there too {mvt}')
        await pg.screenshot(path=f'{shots}/b304-mv.png')
        await pg.evaluate("[...document.querySelectorAll('.tile.mv-artist')].find(t => t.querySelector('.tile-name').textContent === 'Prince').click()"); await pg.wait_for_timeout(800)
        hb = await pg.evaluate("getComputedStyle(document.querySelector('.mv-hero-art')).border")
        check(hb .endswith('solid rgb(58, 58, 62)'), f'and on the artist\'s Music Videos page {hb}')
        await pg.evaluate("document.querySelector('.mv-hero-name').click()"); await pg.wait_for_timeout(1000)
        w = await pg.evaluate("__d.mv301.where()")
        check(w['artist'] == 'prince' and w['hist'][-1] == 'Prince' and len(w['hist']) == 2, f'artist page, with one step back to the videos page {w}')
        await pg.evaluate("__d.mv301.back()"); await pg.wait_for_timeout(800)
        w = await pg.evaluate("__d.mv301.where()")
        check(w['mv'] == 'Prince' and w['vdetail'], f'Back goes to Prince\'s Music Videos page, not Home {w}')
        await pg.evaluate("__d.mv301.back()"); await pg.wait_for_timeout(800)
        w = await pg.evaluate("__d.mv301.where()")
        check(w['video'] and not w['vdetail'], f'and Back again to Watch {w}')
        # Now Playing > artist name > Back: Now Playing again
        await pg.evaluate("__d.mv301.np()"); await pg.wait_for_timeout(1500)
        await pg.evaluate("[...document.querySelectorAll('#nowPlayingScreen .np-sub-link, #nowPlayingScreen .np-name-link')].find(b => b.textContent.indexOf('Prince') !== -1).click()"); await pg.wait_for_timeout(1000)
        w = await pg.evaluate("__d.mv301.where()")
        check(w['artist'] == 'prince' and w['hist'][-1] == 'Now Playing', f'from Now Playing to the artist page {w}')
        await pg.evaluate("__d.mv301.back()"); await pg.wait_for_timeout(1000)
        npOpen = await pg.evaluate("document.getElementById('nowPlayingScreen').style.display")
        check(npOpen == 'flex', f'Back brings Now Playing back {npOpen}')
        check(not errs, f'no page errors {errs[:2]}')
        await b.close()
    print('ALL PASSED' if not fails else f'FAILED {len(fails)}')
asyncio.run(main())
