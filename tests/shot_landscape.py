"""Screenshots of every main screen in phone landscape (and portrait), for the side rail work.
Run: python3 tests/shot_landscape.py [tag]  -> /tmp/claude-0/t/land/<tag>-*.png"""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
src = open(os.path.join(HERE, 'test_live_channels.py')).read()
head = src[:src.index('\nasync def run(')]
head = head.replace("'/tmp/claude-0/t/srv-livech'", "'/tmp/claude-0/t/srv-land'").replace('PORT = 8862', 'PORT = 8878')
exec(head)
TAG = sys.argv[1] if len(sys.argv) > 1 else 'now'
OUT = '/tmp/claude-0/t/land'
GEO = """(()=>{ var q=function(s){var e=document.querySelector(s); if(!e) return null; var r=e.getBoundingClientRect(), cs=getComputedStyle(e); return (cs.display==='none'||cs.visibility==='hidden'||!r.width)?null:[Math.round(r.left),Math.round(r.top),Math.round(r.width),Math.round(r.height)];};
  return {nav:q('.mobile-nav'), top:q('.sidebar-top'), head:q('#sectionHeadingRow'), tabs:q('#stationsGrid > .watch-tabs, #stationsGrid > .lib-tabs'), grid:q('#stationsGrid'), bar:q('.player-bar'), main:q('.main, main, .content'), sw:document.documentElement.scrollWidth, vw:innerWidth}; })()"""
async def shots(pg, prefix):
    res = {}
    async def nav(n):
        await pg.evaluate(f"document.querySelector('.mobile-nav-btn[data-nav={n}]').click()"); await pg.wait_for_timeout(1300)
        await pg.evaluate("window.scrollTo(0,0)"); await pg.wait_for_timeout(200)
    for n in ['home', 'library', 'podcasts', 'search']:
        await nav(n); await pg.screenshot(path=f'{OUT}/{TAG}-{prefix}-{n}.png'); res[n] = await pg.evaluate(GEO)
    await nav('video')
    for t in ['movies', 'shows', 'music', 'continue', 'channels']:
        await pg.evaluate(f"document.querySelector('#stationsGrid > .watch-tabs .home-tab[data-vtab={t}]').click()"); await pg.wait_for_timeout(1500)
        await pg.screenshot(path=f'{OUT}/{TAG}-{prefix}-watch-{t}.png'); res['watch-' + t] = await pg.evaluate(GEO)
        if t == 'movies':
            await pg.evaluate("document.getElementById('wlFilterBtn').click()"); await pg.wait_for_timeout(300)
            await pg.keyboard.type('he'); await pg.wait_for_timeout(600)
            await pg.screenshot(path=f'{OUT}/{TAG}-{prefix}-watch-movies-filter.png')
            res['filter'] = await pg.evaluate("[document.body.classList.contains('wl-filter'), document.querySelectorAll('#stationsGrid > .tile.vposter:not(.sf-hide)').length, (document.getElementById('secFilterInput')||{}).value]")
            await pg.evaluate("document.getElementById('wlFilterBtn').click()"); await pg.wait_for_timeout(400)
            res['filter-closed'] = await pg.evaluate("[document.body.classList.contains('wl-filter'), (document.getElementById('secFilterInput')||{}).value]")
            await pg.evaluate("window.scrollTo(0, 600)"); await pg.wait_for_timeout(500)
            await pg.screenshot(path=f'{OUT}/{TAG}-{prefix}-watch-movies-scrolled.png'); await pg.evaluate("window.scrollTo(0,0)")
    # the menu (profile picture), then a station's Now Playing
    await pg.evaluate("document.querySelector('.mobile-nav-btn[data-nav=home]').click()"); await pg.wait_for_timeout(1200)
    res['playbtn'] = await pg.evaluate("(()=>{ var b=Array.from(document.querySelectorAll('button')).filter(function(b){ var r=b.getBoundingClientRect(); return b.offsetParent && r.top>40 && r.top<200 && /play/i.test((b.getAttribute('aria-label')||'')+b.className); })[0]; if(b){ b.click(); return b.className; } return null; })()"); await pg.wait_for_timeout(2000)
    await pg.screenshot(path=f'{OUT}/{TAG}-{prefix}-playing.png')
    await pg.evaluate("var pb=document.querySelector('.player-bar .player-info, .player-bar'); if(pb) pb.click()"); await pg.wait_for_timeout(1500)
    await pg.screenshot(path=f'{OUT}/{TAG}-{prefix}-np.png'); res['np'] = await pg.evaluate("[document.getElementById('nowPlayingScreen').style.display, document.body.className]")
    await pg.evaluate("var b=document.getElementById('npBackBtn'); if(b) b.click()"); await pg.wait_for_timeout(1000)
    await pg.evaluate("document.querySelector('.mobile-nav-btn[data-nav=video]').click()"); await pg.wait_for_timeout(1200)
    # Live TV with the video (docked), and a film's Now Playing
    await pg.evaluate("try{ localStorage.setItem('radioPlayerLtvAuto','1'); }catch(e){}")
    await pg.evaluate("document.querySelector('#stationsGrid > .watch-tabs .home-tab[data-vtab=movies]').click()"); await pg.wait_for_timeout(800)
    await pg.evaluate("document.querySelector('#stationsGrid > .watch-tabs .home-tab[data-vtab=channels]').click()"); await pg.wait_for_timeout(3000)
    await pg.evaluate("document.body.classList.add('cast-avail')")
    await pg.screenshot(path=f'{OUT}/{TAG}-{prefix}-ltv-docked.png'); res['ltv-docked'] = await pg.evaluate(GEO)
    await pg.evaluate("document.getElementById('vctlMute').click()"); await pg.wait_for_timeout(300)
    await pg.evaluate("document.querySelector('.mobile-nav-btn[data-nav=library]').click()"); await pg.wait_for_timeout(1500)
    await pg.screenshot(path=f'{OUT}/{TAG}-{prefix}-after-ltv-library.png'); res['after-ltv'] = await pg.evaluate(GEO)
    await pg.evaluate("document.getElementById('playerNowTrigger').click()"); await pg.wait_for_timeout(1500)
    await pg.screenshot(path=f'{OUT}/{TAG}-{prefix}-np2.png'); res['np2'] = await pg.evaluate("[document.getElementById('nowPlayingScreen').style.display, document.body.className]")
    await pg.evaluate("document.getElementById('hamburgerBtn').click()"); await pg.wait_for_timeout(700)
    await pg.screenshot(path=f'{OUT}/{TAG}-{prefix}-drawer.png')
    res['drawer'] = await pg.evaluate("document.body.classList.contains('drawer-open')")
    await pg.evaluate("var c=Array.from(document.querySelectorAll('button[aria-label]')).filter(function(b){return /close/i.test(b.getAttribute('aria-label')) && b.offsetParent;})[0]; if(c) c.click()"); await pg.wait_for_timeout(800)
    res['profile-closed'] = await pg.evaluate("document.body.classList.contains('profile-open')")
    return res
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
        for (w, h, pre) in [(892, 373, 'land'), (390, 844, 'port')]:
            ctx = await b.new_context(viewport={'width': w, 'height': h}, device_scale_factor=2, is_mobile=True, has_touch=True, locale='en-US', timezone_id='America/New_York', color_scheme=os.environ.get('THEME','dark'))
            await ctx.add_init_script(MOCK); await ctx.add_init_script(AUTO_NOTICE); await ctx.add_init_script(SEED)
            await ctx.add_init_script("try{ localStorage.setItem('radioPlayerLtvAuto','0'); localStorage.setItem('radioPlayerTheme', '" + os.environ.get('THEME','dark') + "'); localStorage.setItem('radioPlayerLandscape', JSON.stringify({np:false,cf:true})); localStorage.setItem('radioPlayerVideoProgress', JSON.stringify({'plex:srv1abcd:10203':{pos:600,dur:1320,at:Date.now()-60000},'plex:srv1abcd:900':{pos:1500,dur:6000,at:Date.now()-120000}})); }catch(e){}")
            pg = await ctx.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
            await pg.route('**/*', route)
            await pg.goto(f'http://127.0.0.1:{PORT}/index.html'); await pg.wait_for_timeout(3000)
            r = await shots(pg, pre)
            for k, v in r.items(): print(pre, k, v)
            print(pre, 'errors', errs)
            await ctx.close()
        await b.close()
asyncio.run(main())
