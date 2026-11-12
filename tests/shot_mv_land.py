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
            await ctx.add_init_script("try{ localStorage.setItem('radioPlayerLandscape', JSON.stringify({np:false,cf:true})); localStorage.setItem('radioPlayerLtvAuto','0'); var f=[]; ['Ann','Bob','Carl','Dee','Eve','Fay','Gus','Hal','Ivy'].forEach(function(n){ f.push({type:'artist', artistKey:n.toLowerCase(), name:n}); }); localStorage.setItem('radioPlayerFavorites', JSON.stringify(f)); }catch(e){}")
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
            for tab in ['artists', 'albums']:
                await pg.evaluate("document.querySelector('.mobile-nav-btn[data-nav=library]').click()"); await pg.wait_for_timeout(1000)
                await pg.evaluate(f"var b=document.querySelector('#stationsGrid > .lib-tabs [data-ltab={tab}], #stationsGrid > .lib-tabs [data-tab={tab}]')||Array.from(document.querySelectorAll('#stationsGrid > .lib-tabs button')).find(function(x){{return x.textContent.trim().toLowerCase()=='{tab}';}}); b.click()"); await pg.wait_for_timeout(1200)
                await pg.screenshot(path=f'/tmp/claude-0/t/land/lib-{tab}-{pre}.png')
                if tab == 'artists': print('FAVDOM', await pg.evaluate("(()=>{ var b=document.querySelector('.fav-artists-block'); if(!b) return null; var t=b.querySelector('.tile, .row-item, [class*=fav]'); var out=[]; var e=t; for(var i=0;i<4&&e;i++){ out.push(e.tagName+'.'+e.className+' w='+Math.round(e.getBoundingClientRect().width)+' fb='+getComputedStyle(e).flexBasis); e=e.parentElement; } return out; })()"))
                print(pre, tab, await pg.evaluate("(()=>{ var t=document.querySelector('.fav-artists-row > .tile, .tile[data-entity=album]'); var g=document.getElementById('stationsGrid').getBoundingClientRect(); return t? [Math.round(t.getBoundingClientRect().width), Math.round(g.width)] : null; })()"))
            await pg.evaluate("window.scrollTo(0, 400)"); await pg.wait_for_timeout(600)
            await pg.evaluate("(()=>{ var a=document.querySelector('.az-rail'); if(!a) return; document.body.classList.add('az-on'); a.style.opacity='1'; a.style.display='flex'; if(!a.children.length){ '#ABCDEFGHIJKLMNOPQRSTUVWXYZ'.split('').forEach(function(c){ var b=document.createElement('button'); b.className='az-letter'; b.textContent=c; a.appendChild(b); }); } })()")
            print(pre, 'az', await pg.evaluate("(()=>{ var a=document.querySelector('.az-rail'); if(!a) return null; var r=a.getBoundingClientRect(); return [Math.round(r.top), Math.round(r.height), getComputedStyle(a).opacity]; })()"))
            await pg.screenshot(path=f'/tmp/claude-0/t/land/lib-az-{pre}.png')
            await pg.evaluate("(()=>{ var st=document.createElement('style'); st.textContent='.az-letter{font-size:10.5px !important}'; document.head.appendChild(st); })()")
            print(pre, 'az-big', await pg.evaluate("(()=>{ var L=Array.from(document.querySelectorAll('.az-rail .az-letter')); var bad=0; for(var i=1;i<L.length;i++){ var a=L[i-1].getBoundingClientRect(), b=L[i].getBoundingClientRect(); var ha=a.top+(a.height-L[i-1].scrollHeight)/2+L[i-1].scrollHeight; } var r=L[0].getBoundingClientRect(); var s=document.createElement('span'); s.textContent='W'; s.style.cssText='font-size:10.5px;font-weight:800;line-height:1'; document.body.appendChild(s); var gh=s.getBoundingClientRect().height; s.remove(); return {slot:r.height, glyph:gh, fits: r.height >= gh}; })()"))
            await pg.screenshot(path=f'/tmp/claude-0/t/land/lib-az-big-{pre}.png')
            print(pre, 'errors', errs)
            await ctx.close()
        await b.close()
asyncio.run(main())
