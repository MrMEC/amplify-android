"""Build 602 (Mark: the rail kept going missing sideways, taking Cover Flow with it): a video left loaded
behind a closed Now Playing must not go full screen when the phone turns. The rail, the player bar and
the Cover Flow button stay; Now Playing open sideways still goes full screen; closing it ends full screen.
At Mark's size (327 wide upright / 678x297 sideways, dpr 3.3). Run: python3 tests/test_rail_video_behind.py"""
import os, asyncio
HERE = os.path.dirname(os.path.abspath(__file__))
src = open(os.path.join(HERE, 'test_cf_after_video.py')).read()
head = src[:src.index('fails = []')].replace("'/tmp/claude-0/t/srv_cfv'", "'/tmp/claude-0/t/srv_rvb'").replace('8848', '8855')
exec(head)
fails = []
def check(c, m):
    print(('PASS ' if c else 'FAIL ') + m)
    if not c: fails.append(m)
async def ev(pg, js): return await pg.evaluate('(js) => window.__h.ev(js)', js)
P = """(()=>{ var B=document.body.classList, nav=document.getElementById('mobileNav'), l=document.elementFromPoint(30, innerHeight/2), pb=document.querySelector('.player-bar'), cf=document.getElementById('cfOpenBtn');
  return {full:B.contains('np-video-full'), videoOn:document.getElementById('nowPlayingScreen').classList.contains('np-video-on'), npShown:document.getElementById('nowPlayingScreen').style.display==='flex',
    rail:!!(nav&&nav.contains(l)), bar:getComputedStyle(pb).display!=='none', cf:getComputedStyle(cf).display!=='none'}; })()"""
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
        ctx = await b.new_context(viewport={'width': 327, 'height': 700}, screen={'width': 327, 'height': 708}, device_scale_factor=3.3, is_mobile=True, has_touch=True, color_scheme='dark')
        await ctx.add_init_script(MOCK); await ctx.add_init_script(AUTO_NOTICE)
        await ctx.add_init_script("if(!localStorage.getItem('radioPlayerVideoChannels')) localStorage.setItem('radioPlayerVideoChannels', %s)" % repr(json.dumps(CH)))
        pg = await ctx.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.goto(f'http://127.0.0.1:{PORT}/index.html'); await pg.wait_for_timeout(2500)
        await pg.evaluate("""(function(){ var ov=document.getElementById('addMusicOverlay'); if(ov) ov.classList.add('open'); var btn=document.getElementById('addMusicFolderBtn'); btn.disabled=false; btn.click(); })()""")
        for _ in range(60):
            await pg.wait_for_timeout(500)
            if await ev(pg, 'libraryTracks.length') >= len(files): break
        # a channel with its picture, upright
        await ev(pg, "playChannel(findVideoChannel('http://ch1.example/l.m3u8')); 1"); await pg.wait_for_timeout(700)
        cur = await pg.evaluate("window.__cur")
        await pg.evaluate("(id)=>window.__emit('video',{id:id,hasVideo:true,width:1280,height:720})", cur); await pg.wait_for_timeout(800)
        s = await pg.evaluate(P); check(s['videoOn'] and s['npShown'], 'video showing upright %s' % s)
        # close Now Playing (the video stays loaded), go to Albums, turn sideways
        await pg.evaluate("document.getElementById('npBackBtn').click()"); await pg.wait_for_timeout(900)
        await ev(pg, "runLibrarySection('albums'); 1"); await pg.wait_for_timeout(800)
        for i in range(3):
            await pg.set_viewport_size({'width': 678, 'height': 297}); await pg.wait_for_timeout(1300)
            s = await pg.evaluate(P)
            await pg.screenshot(path='/tmp/claude-0/t/shots/rvb-albums-%d.png' % i)
            check(not s['full'] and s['rail'] and s['bar'] and s['cf'], 'turn %d: video behind a closed Now Playing stays put; rail, player bar, Cover Flow button %s' % (i, s))
            await pg.set_viewport_size({'width': 327, 'height': 700}); await pg.wait_for_timeout(1000)
        await pg.set_viewport_size({'width': 678, 'height': 297}); await pg.wait_for_timeout(1300)
        await pg.click('#cfOpenBtn'); await pg.wait_for_timeout(1000)
        cfo = await pg.evaluate("document.getElementById('nowPlayingScreen').classList.contains('la-open') && document.querySelectorAll('#npLandAlbums .cf-cover, #npLandAlbums img').length > 0")
        await pg.screenshot(path='/tmp/claude-0/t/shots/rvb-cf.png')
        check(cfo, 'Cover Flow opens')
        await pg.click('#cfCloseBtn'); await pg.wait_for_timeout(800)
        # Now Playing opened sideways with a video still goes full screen; closing it ends it
        await pg.set_viewport_size({'width': 327, 'height': 700}); await pg.wait_for_timeout(1000)
        await pg.evaluate("document.getElementById('playerNowTrigger').click()"); await pg.wait_for_timeout(1200)
        await pg.evaluate("(id)=>window.__emit('video',{id:id,hasVideo:true,width:1280,height:720})", cur); await pg.wait_for_timeout(800)
        await pg.set_viewport_size({'width': 678, 'height': 297}); await pg.wait_for_timeout(1300)
        await ev(pg, "enterVideoFull(false); 1"); await pg.wait_for_timeout(500)   # (a My Channels channel is Live TV: full screen by its button)
        s = await pg.evaluate(P); check(s['full'], 'Now Playing showing: full screen %s' % s)
        await ev(pg, "closeNowPlaying(false); 1"); await pg.wait_for_timeout(1200)
        s = await pg.evaluate(P)
        await pg.screenshot(path='/tmp/claude-0/t/shots/rvb-after-close.png')
        check(not s['full'] and s['rail'] and s['bar'], 'closing Now Playing ends full screen; rail back %s' % s)
        check(not errs, 'no page errors %s' % errs[:2])
        await b.close()
    print('ALL PASSED' if not fails else 'FAILED %s' % fails)
    raise SystemExit(1 if fails else 0)
asyncio.run(main())
