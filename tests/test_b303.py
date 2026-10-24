"""Build 303 (Mark): a music video shows its title and artist under it even with the guide's channel details hidden; a swipe left shows the queue; Previous / Next on the picture while there is a queue. Built on test_b301 / Build 301 (Mark): Watch > Music Videos: every music video on the phone by artist (artists with
videos but no songs included), Other Videos for the rest; an artist's page plays their videos.
Build 302: no Artist button, the name links to the artist page, the artist page heading links back, Recently Added shows the artist. Run: python3 tests/test_b301.py (screenshots in /tmp/claude-0/t/shots)"""
import os, sys, json
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
__file__ = os.path.join(HERE, 'test_daily_mixes.py')
src = open(os.path.join(HERE, 'test_daily_mixes.py')).read()
src = src[:src.index('async def run(theme):')]
src = src.replace('PORT = 8803', 'PORT = 8896').replace("srv_daily'", "srv_b303'")
src = src.replace('" stopPlay:', '''" mv301: { seed: function(files){ musicVideos.files = files.map(function(f, i){ return { uri: 'content://v/' + i, name: f[0].split('/').pop(), relPath: f[0], size: 1000 + i, lastModified: f[1], tree: 't' }; });"
  "     musicVideos.files.forEach(function(f, i){ videoInfo[f.uri] = { d: 200 + i * 10, w: 640, h: 360, t: '' }; }); saveMusicVideos(); mvCatalogCache = null; },"
  "   vidOn: function(){ npVideoOn = true; npVideoStream = true; nowPlayingScreen.classList.add('np-video-on', 'np-video-stream'); npVideoWrap.hidden = false; vctlSync(); renderNowPlayingScreen(); },"
  "   playOne: function(){ setQueue([window.__one], window.__one, 'x'); playQueue = []; queueIndex = -1; upNext = []; playStation(window.__one); openNowPlaying(window.__one, true); },"
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

SWIPE = """((el, dx) => { const r = el.getBoundingClientRect(); const x0 = r.left + r.width * (dx < 0 ? 0.8 : 0.2), y = r.top + Math.min(r.height * 0.7, 600);
  const mk = (x) => new Touch({ identifier: 1, target: el, clientX: x, clientY: y });
  el.dispatchEvent(new TouchEvent('touchstart', { touches: [mk(x0)], changedTouches: [mk(x0)], bubbles: true, cancelable: true }));
  for(let i = 1; i <= 8; i++){ const t = mk(x0 + dx * i / 8); el.dispatchEvent(new TouchEvent('touchmove', { touches: [t], changedTouches: [t], bubbles: true, cancelable: true })); }
  el.dispatchEvent(new TouchEvent('touchend', { touches: [], changedTouches: [mk(x0 + dx)], bubbles: true, cancelable: true })); })"""
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
        # the Live TV guide's "hide channel details" left on
        await pg.evaluate("localStorage.setItem('radioPlayerNpDetailsHidden', '1'); document.getElementById('nowPlayingScreen').classList.add('np-foot-collapsed')")
        await pg.evaluate("__d.mv301.watch()"); await pg.wait_for_timeout(1000)
        await pg.evaluate("__amplifyOpenMusicVideoArtist(__d.mv301.key('Prince'))"); await pg.wait_for_timeout(600)
        await pg.evaluate("document.querySelector('.mv-page-acts .vd-play').click()"); await pg.wait_for_timeout(2000)
        await pg.evaluate("__d.mv301.vidOn()"); await pg.wait_for_timeout(600)
        foot = await pg.evaluate("""(()=>{ const f = document.querySelector('#nowPlayingScreen .np-hero-foot'); const r = f.getBoundingClientRect(); const n = document.getElementById('npName');
          return { h: r.height, vis: getComputedStyle(f).visibility, name: n.textContent, sub: (document.querySelector('#nowPlayingScreen .np-sub') || {}).textContent,
            cls: document.getElementById('nowPlayingScreen').className }; })()""")
        print('foot', foot)
        check(foot['h'] > 30 and foot['vis'] == 'visible' and foot['name'] == 'Prince 01' and 'Prince' in foot['sub'],
              f'title and artist under the video, even with the guide\'s channel details hidden {foot}')
        check('np-tv' not in foot['cls'], 'a video of your own is not treated as a TV channel')
        # Previous / Next on the picture
        await pg.evaluate("(()=>{ const v = document.getElementById('vctl'); if(!v.classList.contains('show')) v.click(); })()"); await pg.wait_for_timeout(300)
        st = await pg.evaluate("""(()=>{ const v = document.getElementById('vctl'), p = document.getElementById('vctlPrev'), n = document.getElementById('vctlNext');
          return { steps: v.classList.contains('steps'), show: v.classList.contains('show'), prevDis: p.disabled, nextDis: n.disabled,
            prevVis: getComputedStyle(p).visibility, pr: p.getBoundingClientRect().left, pl: document.getElementById('vctlPlay').getBoundingClientRect().left, nr: n.getBoundingClientRect().left }; })()""")
        print('steps', st)
        check(st['steps'] and not st['nextDis'] and st['prevDis'], f'Previous / Next on the picture (first of the queue: Previous greyed) {st}')
        check(st['pr'] < st['pl'] < st['nr'], 'either side of Play')
        await pg.screenshot(path=f'{shots}/b303-controls.png')
        await pg.evaluate("document.getElementById('vctlNext').click()"); await pg.wait_for_timeout(1500)
        q = await pg.evaluate("__d.mv301.q()")
        check(q['cur'] == 'Purple Rain', f'Next plays the next video {q}')
        await pg.evaluate("__d.mv301.vidOn()"); await pg.wait_for_timeout(300)
        st2 = await pg.evaluate("({ prevDis: document.getElementById('vctlPrev').disabled, nextDis: document.getElementById('vctlNext').disabled, name: document.getElementById('npName').textContent })")
        check(not st2['prevDis'] and st2['nextDis'] and st2['name'] == 'Purple Rain', f'now Previous works, Next greyed at the end, the title follows {st2}')
        await pg.evaluate("document.getElementById('vctlPrev').click()"); await pg.wait_for_timeout(1500)
        q = await pg.evaluate("__d.mv301.q()")
        check(q['cur'] == 'Prince 01', f'Previous goes back {q}')
        # swipe left: the queue
        await pg.evaluate(f"({SWIPE})(document.getElementById('nowPlayingScreen'), -260)"); await pg.wait_for_timeout(800)
        qo = await pg.evaluate("({ open: document.getElementById('queuePanel').classList.contains('open'), rows: [...document.querySelectorAll('#queuePanel .queue-row-title')].map(e => e.textContent), subs: [...document.querySelectorAll('#queuePanel .queue-row-sub')].map(e => e.textContent) })")
        check(qo['subs'] and all(x == 'Prince' for x in qo['subs']), f'each video in the queue shows its artist {qo.get("subs")}')
        print('queue', qo)
        check(qo['open'] and 'Prince 01' in qo['rows'] and 'Purple Rain' in qo['rows'], f'a swipe left shows the queue {qo}')
        await pg.screenshot(path=f'{shots}/b303-queue.png')
        await pg.evaluate(f"({SWIPE})(document.getElementById('queuePanel'), 260)"); await pg.wait_for_timeout(600)
        # a single video (no queue): no Previous / Next
        await pg.evaluate("(()=>{ const v = __amplifyMusicVideoCatalog().other[0]; window.__one = v; })()")
        await pg.evaluate("__d.mv301.playOne()"); await pg.wait_for_timeout(1500)
        await pg.evaluate("__d.mv301.vidOn()"); await pg.wait_for_timeout(300)
        check(not await pg.evaluate("document.getElementById('vctl').classList.contains('steps')"), 'one video on its own: no Previous / Next')
        check(not errs, f'no page errors {errs[:2]}')
        await b.close()
    print('ALL PASSED' if not fails else f'FAILED {len(fails)}')
asyncio.run(main())
