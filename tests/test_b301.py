"""Build 301 (Mark): Watch > Music Videos: every music video on the phone by artist (artists with
videos but no songs included), Other Videos for the rest; an artist's page plays their videos.
Run: python3 tests/test_b301.py (screenshots in /tmp/claude-0/t/shots)"""
import os, sys, json
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
__file__ = os.path.join(HERE, 'test_daily_mixes.py')
src = open(os.path.join(HERE, 'test_daily_mixes.py')).read()
src = src[:src.index('async def run(theme):')]
src = src.replace('PORT = 8803', 'PORT = 8895').replace("srv_daily'", "srv_b301'")
src = src.replace('" stopPlay:', '''" mv301: { seed: function(files){ musicVideos.files = files.map(function(f, i){ return { uri: 'content://v/' + i, name: f[0].split('/').pop(), relPath: f[0], size: 1000 + i, lastModified: f[1], tree: 't' }; });"
  "     musicVideos.files.forEach(function(f, i){ videoInfo[f.uri] = { d: 200 + i * 10, w: 640, h: 360, t: '' }; }); saveMusicVideos(); mvCatalogCache = null; },"
  "   key: function(n){ return artistMatchKey(n); },"
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
        await pg.evaluate("__d.mv301.watch()"); await pg.wait_for_timeout(1200)
        tabs = await pg.evaluate("[...document.querySelectorAll('.watch-tabs .home-tab')].map(b => b.textContent + (b.classList.contains('active') ? '*' : ''))")
        check(tabs == ['Live TV', 'Movies', 'TV Shows', 'Music Videos*', 'Continue'], f'a Music Videos tab between TV Shows and Continue {tabs}')
        summ = await pg.evaluate("document.querySelector('.mv-sum').textContent")
        check(summ == '8 videos · 4 artists', f'count of videos and artists {summ}')
        rec = await pg.evaluate("[...document.querySelectorAll('.mv-recent .yt-title')].map(e => e.textContent)")
        print('recent', rec)
        check(rec[:3] == ['Purple Rain', 'Rhythm Nation', 'Got Til Its Gone'], f'Recently Added, newest first {rec[:3]}')
        t = await pg.evaluate(TILES); print('artists', t)
        check(t == ['Janet Jackson|2 videos', 'Madonna|1 video', 'Prince|2 videos', 'Sade|1 video', 'Other Videos|2 videos'],
              f'artists A to Z with counts (Janet Jackson and Sade have videos but no songs), Other Videos last {t}')
        check(await pg.evaluate("!!document.querySelector('.az-rail, .az-index, [class*=az-rail]')"), 'the A to Z rail is there in A–Z order')
        await pg.screenshot(path=f'{shots}/b301-tab.png')
        await pg.evaluate("window.scrollTo(0, 400)"); await pg.wait_for_timeout(200)
        await pg.screenshot(path=f'{shots}/b301-tab-2.png')
        await pg.evaluate("document.querySelector('.mv-seg-btn[data-sort=most]').click()"); await pg.wait_for_timeout(500)
        t2 = await pg.evaluate(TILES)
        check([x.split('|')[0] for x in t2][:2] == ['Janet Jackson', 'Prince'], f'Most: the artists with the most videos first {t2}')
        await pg.evaluate("document.querySelector('.mv-seg-btn[data-sort=recent]').click()"); await pg.wait_for_timeout(500)
        t3 = await pg.evaluate(TILES)
        check([x.split('|')[0] for x in t3][:4] == ['Prince', 'Janet Jackson', 'Sade', 'Madonna'], f'Recent: by newest video {t3}')
        check(await pg.evaluate("JSON.parse(localStorage.getItem('radioPlayerMusicVideoSort'))") == 'recent', 'the order is remembered')
        await pg.evaluate("document.querySelector('.mv-seg-btn[data-sort=az]').click()"); await pg.wait_for_timeout(500)
        # an artist with songs
        await pg.evaluate("[...document.querySelectorAll('.tile.mv-artist')].find(t => t.querySelector('.tile-name').textContent === 'Prince').click()"); await pg.wait_for_timeout(900)
        pi = await pg.evaluate("""({ name: document.querySelector('.mv-hero-name').textContent, meta: document.querySelector('.mv-hero-meta').textContent,
          btns: [...document.querySelectorAll('.mv-page-acts button')].map(b => b.textContent.trim()),
          rows: [...document.querySelectorAll('.mv-row')].map(r => r.querySelector('.vep-title').textContent + '|' + r.querySelector('.vep-sub').textContent + '|' + ((r.querySelector('.mv-dur') || {}).textContent || '')) })""")
        print('prince', pi)
        check(pi['name'] == 'Prince' and pi['meta'].startswith('2 music videos'), f'the artist page: name and count {pi["meta"]}')
        check(pi['btns'] == ['Play All', 'Shuffle', 'Artist'], f'Play All, Shuffle, and Artist (has songs) {pi["btns"]}')
        check(pi['rows'][0].startswith('Prince 01|Prince Album') and pi['rows'][1].startswith('Purple Rain|'), f'videos A to Z; album from the song of the same name {pi["rows"]}')
        check(pi['rows'][0].endswith('3:20'), f'length on the still {pi["rows"][0]}')
        await pg.screenshot(path=f'{shots}/b301-artist.png')
        await pg.evaluate("document.querySelector('.mv-page-acts .vd-play').click()"); await pg.wait_for_timeout(900)
        q = await pg.evaluate("__d.mv301.q()"); print('queue', q)
        check(q['n'] == 2 and q['cur'] == 'Prince 01' and q['kind'] == 'music', f"Play All plays the artist's videos in order {q}")
        await pg.evaluate("document.getElementById('npBackBtn').click()"); await pg.wait_for_timeout(700)
        # an artist with videos only
        await pg.evaluate("__amplifyOpenMusicVideoArtist(__d.mv301.key('Janet Jackson'))"); await pg.wait_for_timeout(700)
        ji = await pg.evaluate("({ btns: [...document.querySelectorAll('.mv-page-acts button')].map(b => b.textContent.trim()), rows: [...document.querySelectorAll('.mv-row .vep-title')].map(e => e.textContent) })")
        check(ji['btns'] == ['Play All', 'Shuffle'] and ji['rows'] == ['Got Til Its Gone', 'Rhythm Nation'], f'a videos-only artist: their videos, no Artist button {ji}')
        await pg.evaluate("__amplifyOpenMusicVideoArtist(__d.mv301.key('Sade'))"); await pg.wait_for_timeout(500)
        si = await pg.evaluate("[...document.querySelectorAll('.mv-row .vep-title')].map(e => e.textContent)")
        check(si == ['Smooth Operator'], f'an artist from their folder name {si}')
        await pg.evaluate("__amplifyOpenMusicVideoArtist('__other__')"); await pg.wait_for_timeout(500)
        oi = await pg.evaluate("({ name: document.querySelector('.mv-hero-name').textContent, rows: [...document.querySelectorAll('.mv-row .vep-title')].map(e => e.textContent) })")
        check(oi['name'] == 'Other Videos' and sorted(oi['rows']) == sorted(['random clip', 'Something']), f'Other Videos: the ones with no artist {oi}')
        await pg.screenshot(path=f'{shots}/b301-other.png')
        # back to the tab: Play All across everything, Shuffle
        await pg.evaluate("__d.mv301.watch()"); await pg.wait_for_timeout(800)
        await pg.evaluate("document.querySelector('.mv-acts .vd-play').click()"); await pg.wait_for_timeout(800)
        q = await pg.evaluate("__d.mv301.q()")
        check(q['n'] == 8 and q['cur'] == 'Got Til Its Gone', f'Play All on the tab: every video, artists A to Z, Other Videos last {q}')
        await pg.evaluate("document.getElementById('npBackBtn').click()"); await pg.wait_for_timeout(700)
        # an empty phone
        await pg.evaluate("(f) => __d.mv301.seed(f)", []); await pg.evaluate("__d.mv301.watch()"); await pg.wait_for_timeout(600)
        check('No music videos yet' in await pg.evaluate("document.getElementById('stationsGrid').innerText"), 'with no videos: a short note on how they get there')
        check(not errs, f'no page errors {errs[:2]}')
        await b.close()
    print('ALL PASSED' if not fails else f'FAILED {len(fails)}')
asyncio.run(main())
