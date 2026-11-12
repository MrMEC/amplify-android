"""Rotate portrait -> landscape -> portrait with the default landscape settings (Horizontal Now Playing on).
Run: python3 tests/shot_rotate.py [tag]"""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
src = open(os.path.join(HERE, 'test_live_channels.py')).read()
head = src[:src.index('\nasync def run(')]
head = head.replace("'/tmp/claude-0/t/srv-livech'", "'/tmp/claude-0/t/srv-rot'").replace('PORT = 8862', 'PORT = 8879')
exec(head)
TAG = sys.argv[1] if len(sys.argv) > 1 else 'now'
OUT = '/tmp/claude-0/t/rot'; os.makedirs(OUT, exist_ok=True)
GEO = """(()=>{ var q=function(s){var e=document.querySelector(s); if(!e) return null; var r=e.getBoundingClientRect(), cs=getComputedStyle(e); return (cs.display==='none'||cs.visibility==='hidden'||!r.width)?null:[Math.round(r.left),Math.round(r.top),Math.round(r.width),Math.round(r.height), cs.opacity, cs.zIndex];};
  var np=document.getElementById('nowPlayingScreen');
  return {cls:document.body.className, nav:q('.mobile-nav'), np:q('#nowPlayingScreen'), npDisp:np.style.display, hero:q('.np-hero'), la:q('.np-land-albums')}; })()"""
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
        ctx = await b.new_context(viewport={'width': 390, 'height': 844}, device_scale_factor=2, is_mobile=True, has_touch=True, locale='en-US', timezone_id='America/New_York', color_scheme='dark')
        await ctx.add_init_script(MOCK); await ctx.add_init_script(AUTO_NOTICE); await ctx.add_init_script(SEED)
        await ctx.add_init_script("try{ localStorage.setItem('radioPlayerLtvAuto','0'); }catch(e){}")
        pg = await ctx.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.route('**/*', route)
        await pg.goto(f'http://127.0.0.1:{PORT}/index.html'); await pg.wait_for_timeout(3000)
        async def step(name, w, h, wait=1500):
            await pg.set_viewport_size({'width': w, 'height': h}); await pg.wait_for_timeout(wait)
            await pg.screenshot(path=f'{OUT}/{TAG}-{name}.png'); print(name, await pg.evaluate(GEO))
        await step('0-port-idle', 390, 844, 300)
        await step('1-land-idle', 892, 373)
        await step('2-port-idle', 390, 844)
        # play something from Home
        await pg.evaluate("(()=>{ var t=document.querySelector('#stationsGrid .tile, .tile'); if(t) t.click(); })()"); await pg.wait_for_timeout(1500)
        await pg.evaluate("var b=document.getElementById('npBackBtn'); if(document.body.classList.contains('np-open')&&b) b.click()"); await pg.wait_for_timeout(800)
        await step('3-port-playing', 390, 844, 300)
        await step('4-land-playing', 892, 373)
        await step('5-port-playing', 390, 844)
        await step('6-land-again', 892, 373)
        for n in ['library','video','home']:
            await pg.evaluate(f"var b=document.querySelector('.mobile-nav-btn[data-nav={n}]'); if(b) b.click()"); await pg.wait_for_timeout(800)
            await step('7-port-'+n, 390, 844, 300); await step('8-land-'+n, 892, 373)
        print('errors', errs)
        await b.close()
asyncio.run(main())
