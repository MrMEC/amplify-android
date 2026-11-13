"""Build 599: Immersive View upright shows a visualizer in the cover's colour, centred between Play and
the bottom of the screen, clear of Play; moving while playing, settled when paused; never sideways.
Home's carousel shows an artist once however many of their songs were played.
At Mark's phone size (327 CSS px wide upright, dpr 3.3). Run: python3 tests/test_imm_viz.py"""
import sys as _nsys, os as _nos; _nsys.path.insert(0, _nos.path.dirname(_nos.path.abspath(__file__))); from notice_auto import AUTO_NOTICE
import asyncio, os, json
HERE = os.path.dirname(os.path.abspath(__file__))
src = open(os.path.join(HERE, 'test_cf_after_video.py')).read()
head = src[:src.index('fails = []')]
head = head.replace("'/tmp/claude-0/t/srv_cfv'", "'/tmp/claude-0/t/srv_viz'").replace('8848', '8852')
exec(head)
from playwright.async_api import async_playwright
fails = []
def check(c, m):
    print(('PASS ' if c else 'FAIL ') + m)
    if not c: fails.append(m)
SH = '/tmp/claude-0/t/shots'
BOX = """(()=>{ var c=document.getElementById('npImmViz'), r=c.getBoundingClientRect(), p=document.getElementById('npPlayBtn').getBoundingClientRect(), cs=getComputedStyle(c);
  var g=c.getContext('2d').getImageData(0,0,c.width,c.height).data, lit=0; for(var i=3;i<g.length;i+=16){ if(g[i]>40) lit++; }
  return {disp:cs.display, op:cs.opacity, top:Math.round(r.top), bot:Math.round(r.bottom), playB:Math.round(p.bottom), vh:innerHeight, lit:lit, sig: (function(){ var a=0; for(var i=0;i<g.length;i+=97) a+=g[i]; return a; })()}; })()"""
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
        for theme in ('dark', 'light'):
            ctx = await b.new_context(viewport={'width': 327, 'height': 680}, screen={'width': 327, 'height': 708}, device_scale_factor=3.3, is_mobile=True, has_touch=True, color_scheme=theme)
            await ctx.add_init_script(MOCK); await ctx.add_init_script(AUTO_NOTICE)
            await ctx.add_init_script("localStorage.setItem('radioPlayerTheme', '%s'); localStorage.setItem('radioPlayerCarousel', JSON.stringify({mode:'flow',size:'m',tilt:66,reflect:true,auto:false}))" % theme)
            pg = await ctx.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
            await pg.goto(f'http://127.0.0.1:{PORT}/index.html'); await pg.wait_for_timeout(2500)
            await pg.evaluate("""(function(){ var ov=document.getElementById('addMusicOverlay'); if(ov) ov.classList.add('open');
              var btn=document.getElementById('addMusicFolderBtn'); btn.disabled=false; btn.click(); })()""")
            for _ in range(60):
                await pg.wait_for_timeout(500)
                if await pg.evaluate("(js)=>window.__h.ev(js)", 'libraryTracks.length') >= len(files): break
            T = '[%s]' % theme
            # several songs by one artist -> one cover on Home
            await pg.evaluate("(js)=>window.__h.ev(js)", "runLibrarySection('songs'); 1"); await pg.wait_for_timeout(800)
            for i in range(3):
                await pg.evaluate("(i)=>{ var r=document.querySelectorAll('#stationsGrid .song-row:not(.shuffle-all-row)')[i]; r.click(); }", i); await pg.wait_for_timeout(900)
            hi = await pg.evaluate("(js)=>window.__h.ev(js)", "heroItems().map(function(t){ return (t.artist||'') + '|' + (t.name||t.title||''); })")
            arts = [x.split('|')[0] for x in hi if x.split('|')[0]]
            check(len(arts) == len(set(arts)) and len(arts) >= 1, T + ' Home carousel: each artist once %s' % hi)
            await pg.evaluate("document.querySelector('.mobile-nav-btn[data-nav=home]').click()"); await pg.wait_for_timeout(1200)
            await pg.screenshot(path=f'{SH}/viz-home-{theme}.png')
            # Immersive View upright
            await pg.evaluate("document.getElementById('playerNowTrigger').click()"); await pg.wait_for_timeout(1500)
            await pg.evaluate("document.getElementById('npArtWrap').click()"); await pg.wait_for_timeout(1500)
            v = await pg.evaluate(BOX)
            await pg.screenshot(path=f'{SH}/viz-playing-{theme}.png')
            room_mid = (v['playB'] + v['vh']) / 2; box_mid = (v['top'] + v['bot']) / 2
            check(v['disp'] == 'block' and v['op'] == '1' and v['lit'] > 50, T + ' visualizer shows while playing %s' % v)
            check(v['top'] >= v['playB'] + 20 and abs(box_mid - (v['playB'] + 28 + v['vh'] - 24) / 2) <= 2 and v['bot'] <= v['vh'], T + ' centred below Play, clear of it %s' % v)
            await pg.wait_for_timeout(300); v2 = await pg.evaluate(BOX)
            check(v2['sig'] != v['sig'], T + ' moving')
            await pg.evaluate("document.getElementById('npPlayBtn').click()"); await pg.wait_for_timeout(2500)
            p1 = await pg.evaluate(BOX); await pg.wait_for_timeout(400); p2 = await pg.evaluate(BOX)
            await pg.screenshot(path=f'{SH}/viz-paused-{theme}.png')
            check(abs(p1['sig'] - p2['sig']) <= max(1, p1['sig']) * .03 and p1['lit'] < v['lit'] * .3, T + ' settled and still when paused %s %s' % (p1['lit'], v['lit']))
            await pg.evaluate("document.getElementById('npPlayBtn').click()"); await pg.wait_for_timeout(800)
            # sideways: none
            await pg.set_viewport_size({'width': 678, 'height': 297}); await pg.wait_for_timeout(1500)
            sd = await pg.evaluate("getComputedStyle(document.getElementById('npImmViz')).display")
            check(sd == 'none', T + ' not sideways %s' % sd)
            await pg.set_viewport_size({'width': 327, 'height': 680}); await pg.wait_for_timeout(1500)
            v3 = await pg.evaluate(BOX)
            check(v3['disp'] == 'block' and v3['lit'] > 50, T + ' back upright, shows again')
            await pg.evaluate("document.getElementById('npArtWrap').click()"); await pg.wait_for_timeout(1200)
            v4 = await pg.evaluate("getComputedStyle(document.getElementById('npImmViz')).display")
            check(v4 == 'none', T + ' gone when Immersive View ends %s' % v4)
            check(not errs, T + ' no page errors %s' % errs[:2])
            await ctx.close()
        await b.close()
    print('ALL PASSED' if not fails else 'FAILED %s' % fails)
    raise SystemExit(1 if fails else 0)
asyncio.run(main())
