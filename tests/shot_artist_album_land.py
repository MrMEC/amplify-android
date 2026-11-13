"""Screenshots + geometry of the artist and album pages, sideways (678x297) and upright (327x700), dpr 3.3.
Run: python3 tests/shot_artist_album_land.py <tag>"""
import os, sys, asyncio, json
HERE = os.path.dirname(os.path.abspath(__file__))
src = open(os.path.join(HERE, 'test_cf_after_video.py')).read()
head = src[:src.index('fails = []')].replace("'/tmp/claude-0/t/srv_cfv'", "'/tmp/claude-0/t/srv_aal'").replace('8848', '8857')
exec(head)
TAG = sys.argv[1] if len(sys.argv) > 1 else 'x'
SH = '/tmp/claude-0/t/shots'
async def ev(pg, js): return await pg.evaluate('(js) => window.__h.ev(js)', js)
GEO = """(()=>{ function g(q){ var e=document.querySelector(q); if(!e) return null; var cs=getComputedStyle(e); if(cs.display==='none'||cs.visibility==='hidden') return null; var r=e.getBoundingClientRect(); if(!r.width) return null; return [Math.round(r.left),Math.round(r.top),Math.round(r.right),Math.round(r.bottom)]; }
 var o={}; ['#artistHeroName','#artistPlayBtn','#artistShuffleBtn','#artistMenuBtn','#artistHeroArt','#albumHeroName','#albumHeroArtist','#albumPlayPill','#albumShuffleBtn','#albumMenuBtn','#albumHeroArt','.player-bar','#mobileNav','#stationsGrid','#cfOpenBtn','#backBtn','.page-back-btn'].forEach(function(q){ o[q]=g(q); });
 o.play = ['#artistPlayBtn','#albumPlayPill'].map(function(q){ var e=document.querySelector(q); return e?getComputedStyle(e).backgroundColor:null; });
 var rows=Array.prototype.filter.call(document.querySelectorAll('#stationsGrid .song-row, #stationsGrid .tile'), function(e){ var r=e.getBoundingClientRect(); return r.width>0 && r.bottom>0 && r.top<innerHeight; });
 o.firstRow = rows[0] ? (function(r){ return [Math.round(r.left),Math.round(r.top),Math.round(r.right),Math.round(r.bottom)]; })(rows[0].getBoundingClientRect()) : null;
 o.cls = document.body.className; return o; })()"""
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
        out = {}
        for theme in ('dark', 'light'):
          for land in (True, False):
            ctx = await b.new_context(viewport={'width': 327, 'height': 700}, screen={'width': 327, 'height': 708}, device_scale_factor=3.3, is_mobile=True, has_touch=True, color_scheme=theme)
            await ctx.add_init_script(MOCK); await ctx.add_init_script(AUTO_NOTICE)
            await ctx.add_init_script("localStorage.setItem('radioPlayerTheme','%s')" % theme)
            pg = await ctx.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
            await pg.goto(f'http://127.0.0.1:{PORT}/index.html'); await pg.wait_for_timeout(2500)
            await pg.evaluate("""(function(){ var ov=document.getElementById('addMusicOverlay'); if(ov) ov.classList.add('open'); var btn=document.getElementById('addMusicFolderBtn'); btn.disabled=false; btn.click(); })()""")
            for _ in range(60):
                await pg.wait_for_timeout(500)
                if await ev(pg, 'libraryTracks.length') >= len(files): break
            await ev(pg, "runLibrarySection('songs'); 1"); await pg.wait_for_timeout(600)
            await pg.evaluate("document.querySelector('#stationsGrid .song-row:not(.shuffle-all-row)').click()"); await pg.wait_for_timeout(900)
            if land:
                await pg.set_viewport_size({'width': 678, 'height': 297}); await pg.wait_for_timeout(1200)
            for kind in ('artist', 'album'):
                if kind == 'artist':
                    await ev(pg, "runLibrarySection('artists'); 1"); await pg.wait_for_timeout(700)
                    await pg.evaluate("document.querySelector('#stationsGrid .tile[data-entity=artist], #stationsGrid [data-entity=artist]').click()")
                else:
                    await ev(pg, "runLibrarySection('albums'); 1"); await pg.wait_for_timeout(700)
                    await pg.evaluate("document.querySelector('#stationsGrid .tile[data-entity=album]').click()")
                await pg.wait_for_timeout(1500)
                k = '%s-%s-%s' % (kind, theme, 'land' if land else 'port')
                out[k] = await pg.evaluate(GEO)
                await pg.screenshot(path=f'{SH}/aal-{TAG}-{k}.png')
                await pg.evaluate("window.scrollTo(0, 400)"); await pg.wait_for_timeout(500)
                out[k]['scrolled'] = await pg.evaluate(GEO)
                await pg.screenshot(path=f'{SH}/aal-{TAG}-{k}-scrolled.png')
                await pg.evaluate("window.scrollTo(0, 0)"); await pg.wait_for_timeout(300)
            out['errs-%s-%s' % (theme, land)] = errs
            await ctx.close()
        json.dump(out, open(f'/tmp/claude-0/t/aal-{TAG}.json', 'w'), indent=1)
        await b.close()
asyncio.run(main())
