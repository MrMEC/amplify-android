"""Build 309 (Mark), part 1: full screen holds into the next video; the show/hide-details arrow beside the list heading on a music video. Built on test_b307 / Build 307 (Mark): the picture beside a music video's title follows the video (shuffle, Next, a music video channel). Built on test_b303 / Build 303 (Mark): a music video shows its title and artist under it even with the guide's channel details hidden; a swipe left shows the queue; Previous / Next on the picture while there is a queue. Built on test_b301 / Build 301 (Mark): Watch > Music Videos: every music video on the phone by artist (artists with
videos but no songs included), Other Videos for the rest; an artist's page plays their videos.
Build 302: no Artist button, the name links to the artist page, the artist page heading links back, Recently Added shows the artist. Run: python3 tests/test_b301.py (screenshots in /tmp/claude-0/t/shots)"""
import os, sys, json
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
__file__ = os.path.join(HERE, 'test_daily_mixes.py')
src = open(os.path.join(HERE, 'test_daily_mixes.py')).read()
src = src[:src.index('async def run(theme):')]
src = src.replace('PORT = 8803', 'PORT = 8902').replace("srv_daily'", "srv_b309'")
src = src.replace('" stopPlay:', '''" mv301: { seed: function(files){ musicVideos.files = files.map(function(f, i){ return { uri: 'content://v/' + i, name: f[0].split('/').pop(), relPath: f[0], size: 1000 + i, lastModified: f[1], tree: 't' }; });"
  "     musicVideos.files.forEach(function(f, i){ videoInfo[f.uri] = { d: 200 + i * 10, w: 640, h: 360, t: 'data:image/svg+xml,%3Csvg xmlns=%22http://www.w3.org/2000/svg%22 width=%2216%22 height=%229%22%3E%3Crect width=%2216%22 height=%229%22 fill=%22%23' + (i + 1) + (i + 1) + '8%22/%3E%3C/svg%3E#still' + i }; }); saveMusicVideos(); mvCatalogCache = null; },"
  "   vidOn: function(){ npVideoOn = true; npVideoStream = true; nowPlayingScreen.classList.add('np-video-on', 'np-video-stream'); npVideoWrap.hidden = false; vctlSync(); renderNowPlayingScreen(); },"
  "   playOne: function(){ setQueue([window.__one], window.__one, 'x'); playQueue = []; queueIndex = -1; upNext = []; playStation(window.__one); openNowPlaying(window.__one, true); },"
  "   fullNext: function(locked){ if(npVideoFull){ npFullCarry = null; exitVideoFull(); npVideoNoAutoFull = false; } npVideoOn = true; npVideoStream = true; nowPlayingScreen.classList.add('np-video-on', 'np-video-stream'); npVideoWrap.hidden = false; enterVideoFull(locked);"
  "     var was = { full: npVideoFull, locked: npVideoFullLocked }; resetNpVideoUi(); var mid = { full: npVideoFull, carry: !!npFullCarry };"
  "     npVideoOn = true; nowPlayingScreen.classList.add('np-video-on'); npVideoWrap.hidden = false; var resumed = npResumeFull();"
  "     return { was: was, mid: mid, resumed: resumed, after: { full: npVideoFull, locked: npVideoFullLocked, body: document.body.classList.contains('np-video-full') } }; },"
  "   handExit: function(){ npVideoOn = true; npVideoWrap.hidden = false; enterVideoFull(true); npVideoFullBtn.click(); var a = npVideoFull; resetNpVideoUi(); npVideoOn = true; npVideoWrap.hidden = false; var r = npResumeFull(); return { afterHand: a, resumed: r, full: npVideoFull }; },"
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
        await pg.evaluate("__amplifyOpenMusicVideoArtist(__d.mv301.key('Prince'))"); await pg.wait_for_timeout(600)
        await pg.evaluate("document.querySelector('.mv-page-acts .mv-play').click()"); await pg.wait_for_timeout(2000)
        await pg.evaluate("__d.mv301.vidOn()"); await pg.wait_for_timeout(500)
        # the arrow beside the list heading
        TG = """(()=>{ const t = document.getElementById('npFootToggle'), h = document.getElementById('npCollectionHeading'), f = document.querySelector('#nowPlayingScreen .np-hero-foot');
          const tr = t.getBoundingClientRect(), hr = h.getBoundingClientRect();
          return { shown: getComputedStyle(t).display !== 'none', left: tr.right <= hr.left + 1, sameRow: Math.abs((tr.top + tr.bottom) / 2 - (hr.top + hr.bottom) / 2) < 6,
            arrow: t.dataset.arrow, label: t.getAttribute('aria-label'), head: h.textContent, foot: Math.round(f.getBoundingClientRect().height) }; })()"""
        t = await pg.evaluate(TG); print('toggle', t)
        check(t['shown'] and t['left'] and t['sameRow'] and t['head'] == 'More Videos by Prince', f'a show/hide arrow left of the first heading {t}')
        check(t['arrow'] == 'up' and t['foot'] > 30 and t['label'] == 'Hide details', f'details shown, the arrow points up {t}')
        await pg.screenshot(path=f'{shots}/b309-toggle-open.png')
        await pg.evaluate("document.getElementById('npFootToggle').click()"); await pg.wait_for_timeout(700)
        t2 = await pg.evaluate(TG)
        check(t2['arrow'] == 'down' and t2['foot'] == 0 and t2['label'] == 'Show details', f'a tap hides the details, the arrow points down {t2}')
        check(await pg.evaluate("localStorage.getItem('radioPlayerNpDetailsHidden')") == '1', "kept, and shared with the Live TV guide's corner")
        await pg.screenshot(path=f'{shots}/b309-toggle-closed.png')
        await pg.evaluate("document.getElementById('npFootToggle').click()"); await pg.wait_for_timeout(700)
        t3 = await pg.evaluate(TG)
        check(t3['arrow'] == 'up' and t3['foot'] > 30, f'and back {t3}')
        # full screen into the next video
        fn = await pg.evaluate("__d.mv301.fullNext(true)"); print('full next', fn)
        check(fn['was']['full'] and not fn['mid']['full'] and fn['mid']['carry'] and fn['resumed'] and fn['after']['full'] and fn['after']['locked'] and fn['after']['body'],
              f'full screen (by the button) comes back for the next video, still held sideways {fn}')
        fn2 = await pg.evaluate("__d.mv301.fullNext(false)")
        check(fn2['after']['full'] and not fn2['after']['locked'], f'and full screen from turning the phone comes back too {fn2}')
        he = await pg.evaluate("__d.mv301.handExit()")
        check(not he['afterHand'] and not he['resumed'] and not he['full'], f'leaving full screen by hand: the next video stays out {he}')
        check(not errs, f'no page errors {errs[:2]}')
        await b.close()
    print('ALL PASSED' if not fails else f'FAILED {len(fails)}')
asyncio.run(main())
