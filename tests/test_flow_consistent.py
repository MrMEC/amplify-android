"""Build 603: Cover Flow takes Home's carousel settings (cover size, tilt, reflection); auto-advance gone;
Home's Flow words the size of Cover Flow's caption; the bottom shadow goes with the mini player.
At Mark's size (327x700 upright, 678x297 sideways, dpr 3.3). Run: python3 tests/test_flow_consistent.py"""
import os, asyncio, json
HERE = os.path.dirname(os.path.abspath(__file__))
src = open(os.path.join(HERE, 'test_cf_after_video.py')).read()
head = src[:src.index('fails = []')].replace("'/tmp/claude-0/t/srv_cfv'", "'/tmp/claude-0/t/srv_flc'").replace('8848', '8856')
exec(head)
fails = []
def check(c, m):
    print(('PASS ' if c else 'FAIL ') + m)
    if not c: fails.append(m)
async def ev(pg, js): return await pg.evaluate('(js) => window.__h.ev(js)', js)
SH = '/tmp/claude-0/t/shots'
HOMEC = "(()=>{ var c=document.querySelector('#npHero .nph-slide.flow-center') || Array.prototype.filter.call(document.querySelectorAll('#npHero .nph-slide'), function(e){ return getComputedStyle(e).zIndex === '1000'; })[0] || document.querySelector('#npHero .nph-slide'); var r=c.querySelector('.nph-art').getBoundingClientRect(); return Math.round(r.height); })()"
CFG = """(()=>{ var c0=document.querySelector('#npLandAlbums .cf-cover.cf-center'), r0=c0.getBoundingClientRect(), cap=document.querySelector('#npLandAlbums .cf-cap.on') || document.querySelector('#npLandAlbums .cf-cap'), capR=cap.getBoundingClientRect(), t=cap.querySelector('.cf-cap-artist').getBoundingClientRect();
  window.__blk=[Math.round(r0.top), Math.round(t.bottom), innerHeight]; })();
  (()=>{ var c=document.querySelector('#npLandAlbums .cf-cover.cf-center') || document.querySelector('#npLandAlbums .cf-cover'); var side=document.querySelector('#npLandAlbums .cf-cover:not(.cf-center)');
  var r=document.querySelector('#npLandAlbums .cf-refl'); return {S: c?Math.round(c.getBoundingClientRect().height):0, side: side?side.style.transform:'', refl: r?getComputedStyle(r).display:'', cap: getComputedStyle(document.querySelector('#npLandAlbums .cf-cap-title')).fontSize}; })()"""
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
        res = {}
        for name, cfg in (('m', {'mode':'flow','size':'m','tilt':66,'reflect':True}), ('s40', {'mode':'flow','size':'s','tilt':40,'reflect':False}), ('l', {'mode':'flow','size':'l','tilt':66,'reflect':True})):
            ctx = await b.new_context(viewport={'width': 327, 'height': 700}, screen={'width': 327, 'height': 708}, device_scale_factor=3.3, is_mobile=True, has_touch=True, color_scheme='dark')
            await ctx.add_init_script(MOCK); await ctx.add_init_script(AUTO_NOTICE)
            await ctx.add_init_script("localStorage.setItem('radioPlayerCarousel', %s)" % repr(json.dumps(cfg)))
            pg = await ctx.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
            await pg.goto(f'http://127.0.0.1:{PORT}/index.html'); await pg.wait_for_timeout(2500)
            await pg.evaluate("""(function(){ var ov=document.getElementById('addMusicOverlay'); if(ov) ov.classList.add('open'); var btn=document.getElementById('addMusicFolderBtn'); btn.disabled=false; btn.click(); })()""")
            for _ in range(60):
                await pg.wait_for_timeout(500)
                if await ev(pg, 'libraryTracks.length') >= len(files): break
            await ev(pg, "runLibrarySection('songs'); 1"); await pg.wait_for_timeout(600)
            await pg.evaluate("document.querySelector('#stationsGrid .song-row:not(.shuffle-all-row)').click()"); await pg.wait_for_timeout(900)
            await pg.evaluate("document.querySelector('.mobile-nav-btn[data-nav=home]').click()"); await pg.wait_for_timeout(1200)
            if name == 'm':
                fs = await pg.evaluate("[getComputedStyle(document.querySelector('.nph-flow-info .nph-title')).fontSize, getComputedStyle(document.querySelector('.nph-flow-info .nph-line')).fontSize]")
                check(fs[1] == '14px' and float(fs[0][:-2]) <= 18, 'Home Flow words: title %s, line %s' % tuple(fs))
                await pg.screenshot(path=f'{SH}/flc-home-port.png')
                # mini player hidden: the bottom shadow goes
                fd0 = await pg.evaluate("getComputedStyle(document.querySelector('.mobile-scroll-fade')).opacity")
                await pg.evaluate("document.querySelector('.mobile-nav-btn[data-nav=home]').click()"); await pg.wait_for_timeout(800)
                fd1 = await pg.evaluate("[document.body.classList.contains('mini-hidden'), getComputedStyle(document.querySelector('.mobile-scroll-fade')).opacity]")
                check(fd0 == '1' and fd1 == [True, '0'], 'bottom shadow hides with the mini player %s %s' % (fd0, fd1))
                await pg.set_viewport_size({'width': 678, 'height': 297}); await pg.wait_for_timeout(1500)
                await pg.screenshot(path=f'{SH}/flc-home-land.png')
                await pg.evaluate("document.querySelector('.mobile-nav-btn[data-nav=home]').click()"); await pg.wait_for_timeout(800)
                await pg.set_viewport_size({'width': 327, 'height': 700}); await pg.wait_for_timeout(1000)
                auto = await pg.evaluate("!document.getElementById('flowAutoSelect') && !document.getElementById('flowAutoLabel')")
                check(auto, 'auto-advance setting gone')
            await pg.set_viewport_size({'width': 678, 'height': 297}); await pg.wait_for_timeout(1500)
            await pg.evaluate("document.querySelector('.mobile-nav-btn[data-nav=library]').click()"); await pg.wait_for_timeout(300)
            await pg.evaluate("document.querySelector('.mobile-nav-btn[data-nav=home]').click()"); await pg.wait_for_timeout(1500)
            homeS = await pg.evaluate(HOMEC)
            await pg.screenshot(path=f'{SH}/flc-homeland-{name}.png')
            await pg.set_viewport_size({'width': 327, 'height': 700}); await pg.wait_for_timeout(800)
            await ev(pg, "runLibrarySection('albums'); 1"); await pg.wait_for_timeout(800)
            await pg.set_viewport_size({'width': 678, 'height': 297}); await pg.wait_for_timeout(1500)
            await pg.click('#cfOpenBtn'); await pg.wait_for_timeout(1300)
            res[name] = await pg.evaluate(CFG)
            res[name]['home'] = homeS
            res[name]['blk'] = await pg.evaluate("window.__blk")
            await pg.screenshot(path=f'{SH}/flc-cf-{name}.png')
            check(not errs, name + ' no page errors %s' % errs[:2])
            await ctx.close()
        print(res)
        for k in res:
            r = res[k]; top, bot, H = r['blk']
            check(abs(r['S'] - r['home']) <= 2 or (r['S'] < r['home'] and bot >= H - 10), k + ': Cover Flow cover the size of Home\'s (or as big as the screen allows) %s vs %s' % (r['S'], r['home']))
            check(abs((top + bot) / 2 - H / 2) <= 4, k + ': cover + caption centred top to bottom %s' % r['blk'])
        check(res['s40']['S'] < res['m']['S'] <= res['l']['S'], 'Cover Flow cover size follows the setting %s' % [res[k]['S'] for k in ('s40','m','l')])
        check(any(x in res['s40']['side'] for x in ('rotateY(-40deg)', 'rotateY(40deg)', 'rotateY(-40.00deg)', 'rotateY(40.00deg)')), 'tilt follows the setting %s' % res['s40']['side'])
        check(res['s40']['refl'] == 'none' and res['m']['refl'] != 'none', 'reflection follows the setting')
        check(res['m']['cap'] == '18px', 'caption title 18px like Home')
        await b.close()
    print('ALL PASSED' if not fails else 'FAILED %s' % fails)
    raise SystemExit(1 if fails else 0)
asyncio.run(main())
