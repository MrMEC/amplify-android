"""Build 610: Zen sideways beside the rail; favourite artists sideways the same size as upright.
At Mark's size (678x297 / 327x700, dpr 3.3). Run: python3 tests/test_land_610.py"""
import os, asyncio
HERE = os.path.dirname(os.path.abspath(__file__))
src = open(os.path.join(HERE, 'test_cf_after_video.py')).read()
head = src[:src.index('fails = []')].replace("'/tmp/claude-0/t/srv_cfv'", "'/tmp/claude-0/t/srv_610'").replace('8848', '8860')
exec(head)
fails = []
def check(c, m):
    print(('PASS ' if c else 'FAIL ') + m)
    if not c: fails.append(m)
async def ev(pg, js): return await pg.evaluate('(js) => window.__h.ev(js)', js)
SH = '/tmp/claude-0/t/shots'
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
        for theme in ('dark', 'light'):
            ctx = await b.new_context(viewport={'width': 327, 'height': 700}, screen={'width': 327, 'height': 708}, device_scale_factor=3.3, is_mobile=True, has_touch=True, color_scheme=theme)
            await ctx.add_init_script(MOCK); await ctx.add_init_script(AUTO_NOTICE)
            await ctx.add_init_script("localStorage.setItem('radioPlayerTheme','%s')" % theme)
            pg = await ctx.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
            await pg.goto(f'http://127.0.0.1:{PORT}/index.html'); await pg.wait_for_timeout(2500)
            await pg.evaluate("""(function(){ var ov=document.getElementById('addMusicOverlay'); if(ov) ov.classList.add('open'); var btn=document.getElementById('addMusicFolderBtn'); btn.disabled=false; btn.click(); })()""")
            for _ in range(60):
                await pg.wait_for_timeout(500)
                if await ev(pg, 'libraryTracks.length') >= len(files): break
            T = '[%s]' % theme
            # favourite artists (several with long names)
            await ev(pg, """(function(){ var es = libraryArtistIndex ? 0 : 0; var keys = Object.keys(artistIndex || {}); return 1; })()""") if False else None
            await ev(pg, """(function(){ var n=0; document.querySelectorAll('#stationsGrid') ; runLibrarySection('artists'); return 1; })()"""); await pg.wait_for_timeout(700)
            await ev(pg, """(function(){ Array.prototype.forEach.call(document.querySelectorAll('#stationsGrid [data-entity=artist]'), function(t){ var k=t.dataset.key||t.dataset.artistKey; }); return 1; })()""")
            await ev(pg, """(function(){ var seen={}; libraryTracks.forEach(function(t){ var k=artistMatchKey(t.artist); if(k && !seen[k]){ seen[k]=1; favorites.push({type:'artist', artistKey:k, name:t.artist, url:'artist:'+k}); } }); try{ saveFavorites(); }catch(e){} runLibrarySection('artists'); return 1; })()"""); await pg.wait_for_timeout(900)
            portW = await pg.evaluate("(()=>{ var t=document.querySelector('.lib-fav-row > .tile, .fav-artists-row > .tile'); return t?Math.round(t.getBoundingClientRect().width):0; })()")
            await pg.set_viewport_size({'width': 678, 'height': 297}); await pg.wait_for_timeout(1300)
            landW = await pg.evaluate("(()=>{ var t=document.querySelector('.lib-fav-row > .tile, .fav-artists-row > .tile'); return t?Math.round(t.getBoundingClientRect().width):0; })()")
            await pg.evaluate("var r=document.querySelector('.lib-fav-row, .fav-artists-row'); window.scrollTo(0, r.getBoundingClientRect().top + scrollY - 60)"); await pg.wait_for_timeout(400)
            await pg.screenshot(path=f'{SH}/610-favs-{theme}.png')
            check(landW >= portW and landW >= 80, T + ' favourite artists sideways %spx (upright %spx)' % (landW, portW))
            # Zen
            await ev(pg, "zenOpenScreen(null, false); 1"); await pg.wait_for_timeout(1000)
            z = await pg.evaluate("(()=>{ var z=document.getElementById('zenScreen').getBoundingClientRect(), b=document.getElementById('zenClose').getBoundingClientRect(), n=document.getElementById('mobileNav').getBoundingClientRect(); var e=document.elementFromPoint(b.left+b.width/2, b.top+b.height/2); return {zl:Math.round(z.left), zr:Math.round(z.right), back:[Math.round(b.left),Math.round(b.top)], rail:Math.round(n.right), hit: !!(e && e.closest('#zenClose'))}; })()")
            await pg.screenshot(path=f'{SH}/610-zen-{theme}.png')
            av = await pg.evaluate("(()=>{ var h=document.querySelector('.sidebar-top .hamburger-btn'); var r=h.getBoundingClientRect(); var e=document.elementFromPoint(r.left+r.width/2, r.top+r.height/2); var o=1, n=h; while(n && n!==document.body){ o*=parseFloat(getComputedStyle(n).opacity); n=n.parentElement; } return {top: !!(e && e.closest('.sidebar-top')), op:o, w:Math.round(r.width), vis:getComputedStyle(h).visibility}; })()")
            check(av['top'] and av['op'] > 0.95 and av['w'] > 20 and av['vis']=='visible', T + ' profile picture at rail foot visible and on top over Zen %s' % av)
            await ev(pg, "document.querySelector('.sidebar-top .hamburger-btn').click(); 1"); await pg.wait_for_timeout(700)
            await pg.screenshot(path=f'{SH}/613-zen-profile-{theme}.png')
            pm = await pg.evaluate("(()=>{ var o=document.querySelector('.profile-overlay.open, .drawer-open'); return !!o || document.body.classList.contains('drawer-open'); })()")
            check(pm, T + ' tapping it opens the profile menu over Zen')
            await pg.keyboard.press('Escape'); await ev(pg, "try{ closeDrawer && closeDrawer(); }catch(e){} document.querySelectorAll('.profile-overlay.open').forEach(function(o){o.classList.remove('open')}); 1"); await pg.wait_for_timeout(500)
            check(z['zl'] >= z['rail'] - 1 and z['zr'] == 678 and z['hit'], T + ' Zen beside the rail, back arrow visible and tappable %s' % z)
            await ev(pg, "zenEl.classList.remove('open'); zenOpen=false; 1"); await pg.wait_for_timeout(600)
            await pg.set_viewport_size({'width': 327, 'height': 700}); await pg.wait_for_timeout(1000)
            await ev(pg, "zenOpenScreen(null, false); 1"); await pg.wait_for_timeout(1000)
            zp = await pg.evaluate("Math.round(document.getElementById('zenScreen').getBoundingClientRect().left)")
            await pg.screenshot(path=f'{SH}/610-zen-port-{theme}.png')
            check(zp == 0, T + ' Zen upright unchanged (left %s)' % zp)
            check(not errs, T + ' no page errors %s' % errs[:2])
            await ctx.close()
        await b.close()
    print('ALL PASSED' if not fails else 'FAILED %s' % fails)
    raise SystemExit(1 if fails else 0)
asyncio.run(main())
