"""Music Videos sideways (build 586): screenshots. Run: python3 tests/shot_mv_land.py"""
import os
HERE = os.path.dirname(os.path.abspath(__file__))
src = open(os.path.join(HERE, 'test_music_videos.py')).read()
head = src[:src.index('\nasync def main(')]
head = head.replace("'/tmp/claude-0/t/srv_mv'", "'/tmp/claude-0/t/srv_mvland'").replace('PORT = 8814', 'PORT = 8880')
exec(head)
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
        for (w, h, pre) in [(892, 373, 'land'), (390, 844, 'port')]:
            ctx = await b.new_context(viewport={'width': w, 'height': h}, device_scale_factor=2, is_mobile=True, has_touch=True, color_scheme='dark')
            await ctx.add_init_script(MOCK); await ctx.add_init_script(AUTO_NOTICE)
            await ctx.add_init_script("try{ localStorage.setItem('radioPlayerLandscape', JSON.stringify({np:false,cf:true})); localStorage.setItem('radioPlayerLtvAuto','0'); }catch(e){}")
            pg = await ctx.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
            await pg.route('**/*', lambda route: route.continue_() if '127.0.0.1' in route.request.url else route.abort())
            await pg.goto(f'http://127.0.0.1:{PORT}/index.html'); await pg.wait_for_timeout(2500)
            await pg.evaluate("""(function(){ var ov=document.getElementById('addMusicOverlay'); if(ov) ov.classList.add('open');
              var btn=document.getElementById('addMusicFolderBtn'); btn.disabled=false; btn.click(); })()""")
            for _ in range(60):
                await pg.wait_for_timeout(500)
                if len(await pg.evaluate('__t.tracks()')) >= 8: break
            await pg.wait_for_timeout(2500)
            await pg.evaluate("var o=document.getElementById('addMusicOverlay'); if(o) o.classList.remove('open')")
            await pg.evaluate("document.querySelector('.mobile-nav-btn[data-nav=video]').click()"); await pg.wait_for_timeout(1200)
            await pg.evaluate("document.querySelector('#stationsGrid > .watch-tabs .home-tab[data-vtab=music]').click()"); await pg.wait_for_timeout(1500)
            await pg.screenshot(path=f'/tmp/claude-0/t/land/mv-{pre}.png')
            print(pre, await pg.evaluate("Array.from(document.querySelectorAll('#stationsGrid > *')).slice(0,8).map(function(e){var r=e.getBoundingClientRect(); return e.className+' '+[Math.round(r.left),Math.round(r.top),Math.round(r.width),Math.round(r.height)].join(',');})"))
            print(pre, 'errors', errs)
            await ctx.close()
        await b.close()
asyncio.run(main())
