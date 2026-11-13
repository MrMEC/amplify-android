"""Build 612: Cover Flow's words open the artist (from Artists) or album (from Albums) page; Zen sideways
has no profile photo (upright keeps it). At Mark's size. Run: python3 tests/test_cf_caption.py"""
import os, asyncio
HERE = os.path.dirname(os.path.abspath(__file__))
src = open(os.path.join(HERE, 'test_cf_after_video.py')).read()
head = src[:src.index('fails = []')].replace("'/tmp/claude-0/t/srv_cfv'", "'/tmp/claude-0/t/srv_cfc'").replace('8848', '8862')
exec(head)
fails = []
def check(c, m):
    print(('PASS ' if c else 'FAIL ') + m)
    if not c: fails.append(m)
async def ev(pg, js): return await pg.evaluate('(js) => window.__h.ev(js)', js)
SH = '/tmp/claude-0/t/shots'
ST = "window.__h.ev(\"[document.body.className.split(' ').filter(function(c){return /artist-open|album-open|rotate-lock|cf-btn/.test(c);}).join(' '), activeArtistKey, activeAlbumKey, (document.querySelector('#npLandAlbums .cf-cap.on .cf-cap-title')||{}).textContent, (document.querySelector('#npLandAlbums .cf-cap.on .cf-cap-artist')||{}).textContent]\")"
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
        ctx = await b.new_context(viewport={'width': 327, 'height': 700}, screen={'width': 327, 'height': 708}, device_scale_factor=3.3, is_mobile=True, has_touch=True)
        await ctx.add_init_script(MOCK); await ctx.add_init_script(AUTO_NOTICE)
        pg = await ctx.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.goto(f'http://127.0.0.1:{PORT}/index.html'); await pg.wait_for_timeout(2500)
        await pg.evaluate("""(function(){ var ov=document.getElementById('addMusicOverlay'); if(ov) ov.classList.add('open'); var btn=document.getElementById('addMusicFolderBtn'); btn.disabled=false; btn.click(); })()""")
        for _ in range(60):
            await pg.wait_for_timeout(500)
            if await ev(pg, 'libraryTracks.length') >= len(files): break
        await pg.set_viewport_size({'width': 678, 'height': 297}); await pg.wait_for_timeout(1200)
        for sec in ('albums', 'artists'):
            await ev(pg, "runLibrarySection('%s'); 1" % sec); await pg.wait_for_timeout(800)
            await pg.click('#cfOpenBtn'); await pg.wait_for_timeout(1200)
            s0 = await pg.evaluate(ST)
            await pg.click('#npLandAlbums .cf-caption'); await pg.wait_for_timeout(1400)
            s1 = await pg.evaluate(ST)
            await pg.screenshot(path=f'{SH}/cfc-{sec}.png')
            if sec == 'albums':
                check('album-open' in s1[0] and 'rotate-lock' not in s1[0] and s1[2], 'Albums: tapping "%s" opens its album page %s' % (s0[3], s1))
            else:
                check('artist-open' in s1[0] and 'album-open' not in s1[0] and 'rotate-lock' not in s1[0] and s1[1] == await ev(pg, "artistMatchKey(%r)" % s0[4]), 'Artists: tapping "%s / %s" opens the artist page %s' % (s0[3], s0[4], s1))
        await ev(pg, "zenOpenScreen(null, false); 1"); await pg.wait_for_timeout(1000)
        z = await pg.evaluate("getComputedStyle(document.getElementById('zenAvatar')).display")
        await pg.screenshot(path=f'{SH}/cfc-zen-land.png')
        check(z == 'none', 'Zen sideways: no profile photo (%s)' % z)
        await pg.set_viewport_size({'width': 327, 'height': 700}); await pg.wait_for_timeout(1000)
        z = await pg.evaluate("getComputedStyle(document.getElementById('zenAvatar')).display")
        check(z != 'none', 'Zen upright keeps its profile photo (%s)' % z)
        check(not errs, 'no page errors %s' % errs[:2])
        await b.close()
    print('ALL PASSED' if not fails else 'FAILED %s' % fails)
    raise SystemExit(1 if fails else 0)
asyncio.run(main())
