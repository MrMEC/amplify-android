"""Build 306 (Mark): a music video channel is one "Music Videos" block in the guide; grey edges on video stills; the day's artist on the Music Videos tab. Built on test_b305 / Build 305 (Mark): Add Channels tabs to the edge; music video channels; New Channel as a page; Music Videos page buttons. Built on test_b304 / Build 304 (Mark): grey rings on artist circles; three artists across on the Artists page; Back on artist pages goes to the page you came from; no favourite star on the Music Videos artists. Built on test_b301 / Build 301 (Mark): Watch > Music Videos: every music video on the phone by artist (artists with
videos but no songs included), Other Videos for the rest; an artist's page plays their videos.
Build 302: no Artist button, the name links to the artist page, the artist page heading links back, Recently Added shows the artist. Run: python3 tests/test_b301.py (screenshots in /tmp/claude-0/t/shots)"""
import os, sys, json
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
__file__ = os.path.join(HERE, 'test_daily_mixes.py')
src = open(os.path.join(HERE, 'test_daily_mixes.py')).read()
src = src[:src.index('async def run(theme):')]
src = src.replace('PORT = 8803', 'PORT = 8899').replace("srv_daily'", "srv_b306'")
src = src.replace('" stopPlay:', '''" mv301: { seed: function(files){ musicVideos.files = files.map(function(f, i){ return { uri: 'content://v/' + i, name: f[0].split('/').pop(), relPath: f[0], size: 1000 + i, lastModified: f[1], tree: 't' }; });"
  "     musicVideos.files.forEach(function(f, i){ videoInfo[f.uri] = { d: 200 + i * 10, w: 640, h: 360, t: '' }; }); saveMusicVideos(); mvCatalogCache = null; },"
  "   where: function(){ return { heading: stationsHeading.textContent, artist: activeArtistKey, sect: activeLibrarySection, home: document.body.classList.contains('home-view'), video: onVideoView, vdetail: onVideoDetailView, mv: (document.querySelector('.mv-hero-name') || {}).textContent || '', hist: viewHistory.map(function(v){ return v.label; }) }; },"
  "   back: function(){ var b = document.getElementById('detailBackBtn'); var vis = b && getComputedStyle(b).display !== 'none'; if(vis){ b.click(); return 'detailBack'; } return 'none'; },"
  "   key: function(n){ return artistMatchKey(n); },"
  "   np: function(){ var t = libraryTracks.filter(function(x){ return x.artist === 'Prince'; })[0]; audio.play = function(){ return Promise.resolve(); }; playEntity(t); setTimeout(function(){ openNowPlaying(currentStation); }, 500); },"
  "   daily: function(n){ ensureDailyLists(); dailyState.videoKey = artistMatchKey(n); },"
  "   home: function(){ document.querySelector('.mobile-nav-btn[data-nav=home]').click(); setTimeout(function(){ try{ renderDailyHome(); }catch(e){} }, 300); },"
  "   edit: function(id){ openLiveChEditor(id); },"
  "   defs: function(){ return JSON.parse(JSON.stringify(liveChDefs())); },"
  "   addCh: function(){ videoTab = 'channels'; addChannelsTab = 'mine'; pushView(); openAddChannelsPage(); },"
  "   liveTv: function(){ videoTab = 'channels'; pushView(); openVideoHome(); },"
  "   tune: function(id){ var ok = tuneLiveChannel('amplify-live:' + id, {}); return { ok: ok, cur: currentStation && { kind: currentStation.videoKind, liveTitle: currentStation.liveTitle, artist: currentStation.liveArtist, text: liveTrackText(currentStation), name: currentStation.name } }; },"
  "   guide: function(id){ var c = liveChannelByUrl('amplify-live:' + id); return c ? liveChItems(c).slice(0, 3).map(function(p){ return p.t + '|' + p.sub; }) : null; },"
  "   isFavArtist: function(n){ var e = findArtistEntry(artistMatchKey(n)); return e ? isFavorite(artistFavRecord(e)) : null; },"
  "   queue: function(){ return upNext.map(function(t){ return t.name; }); },"
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



BORDER = "(sel) => { const e = document.querySelector(sel); return e ? getComputedStyle(e).borderTopStyle + ' ' + getComputedStyle(e).borderTopColor : null; }"
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
        # 1) a music video channel in the guide: one block
        await pg.evaluate("__d.mv301.liveTv()"); await pg.wait_for_timeout(600)
        await pg.evaluate("__d.mv301.addCh()"); await pg.wait_for_timeout(900)
        await pg.evaluate("[...document.querySelectorAll('.ch-list .ch-row')].find(r => r.querySelector('.ch-name').textContent === 'All Music Videos').click()"); await pg.wait_for_timeout(400)
        await pg.evaluate("__d.mv301.liveTv()"); await pg.wait_for_timeout(1500)
        row = await pg.evaluate("""(()=>{ const r = [...document.querySelectorAll('#stationsGrid .epg-row')].find(x => (x.querySelector('.epg-ch').getAttribute('aria-label') || '').startsWith('Music Videos'));
          if(!r) return null; const bs = [...r.querySelectorAll('.epg-block, .epg-prog, [class*=epg-b]')].filter(x => !x.classList.contains('epg-ch'));
          return { n: bs.length, text: bs.map(x => x.innerText.replace(/\\s+/g, ' ').trim()), rows: document.querySelectorAll('#stationsGrid .epg-row').length }; })()""")
        print('guide row', row)
        check(row and row['n'] == 1 and row['text'][0].startswith('Music Videos'), f'the music video channel is one "Music Videos" block in the guide {row}')
        await pg.screenshot(path=f'{shots}/b306-guide.png')
        # 3) the day's artist on the Music Videos tab
        await pg.evaluate("__d.mv301.daily('Prince')")
        await pg.evaluate("__d.mv301.watch()"); await pg.wait_for_timeout(1000)
        order = await pg.evaluate("[...document.querySelectorAll('#stationsGrid > .grid-section-label, #stationsGrid > .mv-artists-head .grid-section-label')].map(e => e.textContent.trim())")
        print('sections', order)
        check(order[:3] == ['Prince', 'Recently Added', 'Artists'], f"the day's artist above Recently Added {order}")
        dt = await pg.evaluate("[...document.querySelectorAll('.mv-daily .yt-title')].map(e => e.textContent)")
        check(dt == ['Prince 01', 'Purple Rain'], f"their videos in a row {dt}")
        # 2) grey edges
        b1 = await pg.evaluate(f"({BORDER})('.mv-daily .yt-thumb')"); b2 = await pg.evaluate(f"({BORDER})('.mv-recent .yt-thumb')")
        check(b1 == 'solid rgb(58, 58, 62)' and b2 == 'solid rgb(58, 58, 62)', f'thin grey edge on the Music Videos tab stills {b1} {b2}')
        await pg.screenshot(path=f'{shots}/b306-mvtab.png')
        await pg.evaluate("document.querySelector('.mv-daily-label').click()"); await pg.wait_for_timeout(700)
        w = await pg.evaluate("(document.querySelector('.mv-hero-name') || {}).textContent")
        check(w == 'Prince', f"the heading opens their Music Videos page {w}")
        b3 = await pg.evaluate(f"({BORDER})('.mv-row .vep-thumb')")
        check(b3 == 'solid rgb(58, 58, 62)', f"and on the artist's Music Videos page {b3}")
        await pg.evaluate("__d.mv301.home()"); await pg.wait_for_timeout(1500)
        b4 = await pg.evaluate(f"({BORDER})('#dailyHomeSections .daily-home-section[data-daily=videos] .yt-thumb')")
        check(b4 == 'solid rgb(58, 58, 62)', f"and Home's daily videos {b4}")
        await pg.evaluate("(()=>{ const s = document.querySelector('#dailyHomeSections .daily-home-section[data-daily=videos]'); if(s) s.scrollIntoView(); })()"); await pg.wait_for_timeout(400)
        await pg.screenshot(path=f'{shots}/b306-home.png')
        check(not errs, f'no page errors {errs[:2]}')
        await b.close()
    print('ALL PASSED' if not fails else f'FAILED {len(fails)}')
asyncio.run(main())
