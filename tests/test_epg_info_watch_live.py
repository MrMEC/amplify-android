"""Build 585: a later show on a channel of your own (The Office from Plex) has Watch Now, which plays
that episode itself (not the channel). Run: python3 tests/test_epg_info_watch_live.py"""
import os
HERE = os.path.dirname(os.path.abspath(__file__))
src = open(os.path.join(HERE, 'test_live_channels.py')).read()
head = src[:src.index('\nasync def run(')]
head = head.replace("'/tmp/claude-0/t/srv-livech'", "'/tmp/claude-0/t/srv-infolive'").replace('PORT = 8862', 'PORT = 8877')
exec(head)

INFO = "(()=>{ var o=document.getElementById('epgInfoOverlay'), w=document.getElementById('epgInfoWatch'); var x=w.getBoundingClientRect(); return {open:o.classList.contains('open'), watch:!w.hidden && x.height>0, show:document.getElementById('epgInfoShow').textContent, ep:document.getElementById('epgInfoEp').textContent}; })()"

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
        ctx = await b.new_context(viewport={'width': 390, 'height': 860}, device_scale_factor=2, is_mobile=True, has_touch=True, locale='en-US', timezone_id='America/New_York')
        await ctx.add_init_script(MOCK); await ctx.add_init_script(AUTO_NOTICE); await ctx.add_init_script(SEED)
        await ctx.add_init_script("try{ localStorage.setItem('radioPlayerLtvAuto','0'); }catch(e){}")
        pg = await ctx.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.route('**/*', route)
        await pg.goto(f'http://127.0.0.1:{PORT}/index.html'); await pg.wait_for_timeout(3000)
        await pg.evaluate("document.querySelector('.mobile-nav-btn[data-nav=video]').click()"); await pg.wait_for_timeout(1500)
        ok = await pg.evaluate("(()=>{ var r=document.querySelector('.epg-row[data-ch-url=\"amplify-live:office\"]'); var b=r && r.querySelectorAll('.epg-prog.info')[1]; if(!b) return false; b.click(); return true; })()")
        check(ok, 'a later Office episode in the guide')
        await pg.wait_for_timeout(500)
        i1 = await pg.evaluate(INFO)
        check(i1['open'] and i1['watch'], f'its details have Watch Now {i1}')
        await pg.screenshot(path=f'{SHOTS}/epg-info-watch-office.png')
        await pg.evaluate("document.getElementById('epgInfoWatch').click()"); await pg.wait_for_timeout(2500)
        np = await pg.evaluate("[document.getElementById('nowPlayingScreen').style.display, document.getElementById('nowPlayingScreen').className, document.getElementById('nowPlayingScreen').innerText.slice(0,400)]")
        check(np[0] == 'flex' and 'np-tv' not in np[1] and i1['show'] in np[2], f'Watch Now plays that episode itself, not the channel {np[1]} | {np[2][:160]!r} | {i1["show"]}')
        await pg.screenshot(path=f'{SHOTS}/epg-info-watch-office-np.png')
        check(not errs, f'no page errors {errs}')
        await b.close()
    print('FAILED' if fails else 'ALL PASSED', fails)
asyncio.run(main())
