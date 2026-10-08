"""Build 155: leaving Now Playing while a video is on keeps it playing in a small floating
window above the mini player; opening Now Playing again puts the same picture back without a
reload. Covers a video podcast (the page's own <video>, moved, never reloaded) here; native
pictures (channels, local videos) are covered in test_stream_video.py.
Run: python3 tests/test_video_mini.py (needs /tmp/claude-0/t/vid/test.webm, see test_stream_video.py)"""
import asyncio, os, json
HERE = os.path.dirname(os.path.abspath(__file__))
src = open(os.path.join(HERE, 'test_stream_video.py')).read()
head = src[:src.index('async def paste(pg, url)')]
head = head.replace("'/tmp/claude-0/t/srv-video'", "'/tmp/claude-0/t/srv-vmini'").replace('8771', '8817')
exec(head)

EP = {'type': 'podcast', 'name': 'Episode With Video', 'url': BASE + 'test.webm', 'episodeUrl': BASE + 'test.webm', 'isVideo': True,
      'guid': 'ep-v-1', 'podcastName': 'Video Show', 'feedUrl': 'https://feed.example/rss', 'favicon': '', 'duration': 20}

async def mini_state(pg):
    return await pg.evaluate("""(()=>{var m=document.getElementById('videoMini'), v=document.getElementById('npVideo');
      return {hidden:m.hidden, inMini:v.parentNode.id==='videoMiniBox', inNp:v.parentNode.id==='npVideoWrap', paused:v.paused, t:v.currentTime,
        src:v.currentSrc, np:document.getElementById('nowPlayingScreen').style.display, shown: !m.hidden && getComputedStyle(m).display!=='none'};})()""")

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path='/opt/pw-browsers/chromium', args=['--autoplay-policy=no-user-gesture-required'])
        ctx = await b.new_context(viewport={'width': 390, 'height': 844}, device_scale_factor=2, is_mobile=True, has_touch=True, color_scheme='dark')
        await ctx.add_init_script(MOCK)
        await ctx.add_init_script("localStorage.setItem('radioPlayerRecent', %s)" % repr(json.dumps([EP])))
        pg = await ctx.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.goto(BASE + 'index.html'); await pg.wait_for_timeout(2500)
        await pg.evaluate("document.querySelector('#recentSection .tile[data-key]').click()"); await pg.wait_for_timeout(800)
        await pg.evaluate("document.getElementById('playerNowTrigger').click()"); await pg.wait_for_timeout(900)
        tog = await pg.evaluate("document.getElementById('npVideoToggle').hidden")
        check(not tog, 'the episode offers Turn On Video')
        await pg.evaluate("document.getElementById('npVideoToggle').click()"); await pg.wait_for_timeout(2500)
        s0 = await mini_state(pg)
        check(s0['inNp'] and not s0['paused'] and s0['t'] > 0.3 and s0['hidden'], f'video plays in Now Playing, no floating window {s0}')
        src0 = s0['src']
        await pg.evaluate("document.getElementById('npBackBtn').click()"); await pg.wait_for_timeout(1200)
        s1 = await mini_state(pg)
        check(s1['shown'] and s1['inMini'] and not s1['paused'] and s1['src'] == src0 and s1['t'] >= s0['t'], f'leaving Now Playing floats the same video, still playing {s1}')
        await pg.wait_for_timeout(1000)
        s1b = await mini_state(pg)
        check(s1b['t'] > s1['t'] + 0.5, f'it keeps playing in the window ({s1["t"]} -> {s1b["t"]})')
        box = await pg.evaluate("""(()=>{var m=document.getElementById('videoMini').getBoundingClientRect(), p=document.getElementById('playerBar').getBoundingClientRect();
          return {bottom:Math.round(m.bottom), barTop:Math.round(p.top), right:Math.round(m.right), w:innerWidth};})()""")
        check(box['bottom'] <= box['barTop'] and box['right'] >= box['w'] - 14, f'it sits above the mini player, on the right {box}')
        await pg.screenshot(path=f'{SHOTS}/vmini-home.png')
        # browse somewhere else: it stays
        await pg.evaluate("document.querySelector('.mobile-nav-btn[data-nav=library]').click()"); await pg.wait_for_timeout(800)
        s2 = await mini_state(pg)
        check(s2['shown'] and not s2['paused'], f'it stays while browsing the Library {s2}')
        # pause / play from the window
        await pg.evaluate("document.getElementById('videoMiniPlay').click()"); await pg.wait_for_timeout(400)
        pz = await pg.evaluate("[document.getElementById('npVideo').paused, document.getElementById('videoMiniPlay').getAttribute('aria-label')]")
        check(pz[0] and pz[1] == 'Play', f'its pause button pauses {pz}')
        await pg.evaluate("document.getElementById('videoMiniPlay').click()"); await pg.wait_for_timeout(600)
        pz = await pg.evaluate("[document.getElementById('npVideo').paused, document.getElementById('videoMiniPlay').getAttribute('aria-label')]")
        check(not pz[0] and pz[1] == 'Pause', f'and plays again {pz}')
        # drag it anywhere: it stays exactly where it is let go (build 158)
        r0 = await pg.evaluate("(()=>{var r=document.getElementById('videoMini').getBoundingClientRect(); return [r.left, r.top];})()")
        bar = await pg.evaluate("(()=>{var r=document.getElementById('videoMiniTitle').getBoundingClientRect(); return [r.left+r.width/2, r.top+r.height/2];})()")
        await pg.mouse.move(bar[0], bar[1]); await pg.mouse.down()
        for i in range(1, 9): await pg.mouse.move(bar[0] - i * 12, bar[1] - i * 40)
        await pg.mouse.up(); await pg.wait_for_timeout(900)
        r1 = await pg.evaluate("(()=>{var r=document.getElementById('videoMini').getBoundingClientRect(); return [r.left, r.top];})()")
        check(abs(r1[0] - (r0[0] - 96)) <= 2 and abs(r1[1] - (r0[1] - 320)) <= 2, f'dragged, it stays where it was let go, not snapped to a side {r0} -> {r1}')
        await pg.screenshot(path=f'{SHOTS}/vmini-moved.png')
        saved = await pg.evaluate("localStorage.getItem('radioPlayerVideoMiniPos')")
        check(saved and json.loads(saved)['x'] == r1[0], f'the spot is remembered ({saved})')
        # dragged past the edge: kept on screen
        bar = await pg.evaluate("(()=>{var r=document.getElementById('videoMiniTitle').getBoundingClientRect(); return [r.left+r.width/2, r.top+r.height/2];})()")
        await pg.mouse.move(bar[0], bar[1]); await pg.mouse.down()
        for i in range(1, 9): await pg.mouse.move(bar[0] - i * 80, bar[1])
        await pg.mouse.up(); await pg.wait_for_timeout(500)
        r2 = await pg.evaluate("(()=>{var r=document.getElementById('videoMini').getBoundingClientRect(); return [Math.round(r.left), Math.round(r.top)];})()")
        check(r2[0] == 4 and abs(r2[1] - r1[1]) <= 2, f'pushed past the edge it stays on screen {r2}')
        # back to Now Playing: same element, still playing
        t_before = (await mini_state(pg))['t']
        await pg.evaluate("document.getElementById('videoMiniBox').click()"); await pg.wait_for_timeout(1000)
        s3 = await mini_state(pg)
        check(s3['np'] == 'flex' and s3['inNp'] and s3['hidden'] and not s3['paused'] and s3['src'] == src0 and s3['t'] >= t_before,
              f'tapping it opens Now Playing with the video back in place, uninterrupted {s3}')
        await pg.screenshot(path=f'{SHOTS}/vmini-np.png')
        # close from the window: pauses, window goes
        await pg.evaluate("document.getElementById('npBackBtn').click()"); await pg.wait_for_timeout(900)
        await pg.evaluate("document.getElementById('videoMiniClose').click()"); await pg.wait_for_timeout(500)
        s4 = await mini_state(pg)
        check(not s4['shown'] and s4['paused'], f'closing the window pauses and hides it {s4}')
        await pg.evaluate("document.getElementById('playPauseBtn').click()"); await pg.wait_for_timeout(800)
        s5 = await mini_state(pg)
        check(s5['shown'] and not s5['paused'], f'playing again from the mini player brings it back {s5}')
        check(not errs, f'no page errors {errs}')
        await b.close()
    print('ALL PASSED' if not check.failed else f'FAILED {check.failed}')
asyncio.run(main())
