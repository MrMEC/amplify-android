"""Build 395: Appearance split into sub-pages; Shape & density (corner radius, density, artist portrait shape).
Run: python3 tests/test_shape_density.py (screenshots in /tmp/claude-0/t/shots)"""
import asyncio, json, sys, os
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
__file__ = os.path.join(HERE, 'test_artist_videos.py')
_src = open(__file__).read().split("async def main():")[0].replace("PORT = 8802", "PORT = 8884").replace("srv_artvid", "srv_shape")
exec(_src)
BACKUP = json.load(open(os.path.join(HERE, 'fixtures', 'layout_backup.json')))
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
        for scheme in ('dark', 'light'):
            ctx = await b.new_context(viewport={'width': 390, 'height': 844}, device_scale_factor=2, is_mobile=True, has_touch=True, color_scheme=scheme)
            await ctx.add_init_script(MOCK); await ctx.add_init_script(AUTO_NOTICE)
            pg = await ctx.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
            await pg.route('**/*', route)
            await pg.goto(f'http://127.0.0.1:{PORT}/index.html'); await pg.wait_for_timeout(2500)
            await pg.evaluate("(d)=>{ __t.ev('importBackupData')(d, 'merge'); }", BACKUP); await pg.wait_for_timeout(2000)
            await pg.evaluate("document.querySelectorAll('button').forEach(x=>{ if(x.textContent.trim()==='OK' && x.offsetParent) x.click(); })"); await pg.wait_for_timeout(400)
            await pg.evaluate("document.querySelector('.mobile-nav-btn[data-nav=home]').click()"); await pg.wait_for_timeout(700)
            probe = """(()=>{ var t=document.querySelector('#latestPodcastsGrid .tile-art, #recentGrid .tile-art'), a=document.querySelector('.tile[data-entity=artist]:not(.fav-card) .tile-art');
              return { tile: t&&getComputedStyle(t).borderTopLeftRadius, tw: t&&Math.round(t.getBoundingClientRect().width), artist: a?getComputedStyle(a).borderTopLeftRadius:'none' }; })()"""
            d0 = await pg.evaluate(probe)
            check(d0['tile'] == '8.5px' and d0['artist'] in ('50%', 'none'), f'defaults unchanged {d0}')
            await pg.screenshot(path=f'{shots}/shape-home-default-{scheme}.png')
            # hub
            await pg.evaluate("__t.ev('openSettings(\"appearance\")')"); await pg.wait_for_timeout(500)
            names = await pg.evaluate("Array.from(document.querySelectorAll('.set-subcats .set-cat-name')).map(e=>e.textContent)")
            check(names == ['Theme & color', 'Sizes & text', 'Typography', 'Shape & density'], f'hub lists four groups {names}')
            await pg.screenshot(path=f'{shots}/shape-hub-{scheme}.png')
            await pg.click('.set-subcats .set-cat[data-set-cat=appearance-shape]'); await pg.wait_for_timeout(400)
            title = await pg.evaluate("document.getElementById('settingsTitle').textContent")
            check(title == 'Shape & density', f'sub-page title {title}')
            await pg.screenshot(path=f'{shots}/shape-page-{scheme}.png')
            await pg.click('#settingsCloseBtn'); await pg.wait_for_timeout(300)
            check(await pg.evaluate("document.getElementById('settingsTitle').textContent") == 'Appearance', 'back goes to the Appearance list')
            # build 402: with the biggest text on a narrow phone the preview stays inside its box and nothing scrolls sideways
            await pg.set_viewport_size({'width': 360, 'height': 780}); await pg.wait_for_timeout(200)
            await pg.evaluate("(()=>{ var r=document.getElementById('fontSizeRange'); r.value='150'; r.dispatchEvent(new Event('input')); r.dispatchEvent(new Event('change')); })()"); await pg.wait_for_timeout(500)
            await pg.evaluate("__t.ev('openSettings(\"appearance-shape\")')"); await pg.wait_for_timeout(400)
            ov = await pg.evaluate("""(()=>{ var p=document.getElementById('settingsPanel'), b=document.getElementById('shapePreview').getBoundingClientRect();
              var kids=Array.from(document.querySelectorAll('#shapePreview > *')).map(e=>e.getBoundingClientRect());
              return { sw: p.scrollWidth, cw: p.clientWidth, doc: document.documentElement.scrollWidth, vw: innerWidth, boxR: Math.round(b.right), kidsR: Math.round(Math.max.apply(null, kids.map(k=>k.right))), kidsB: Math.round(Math.max.apply(null, kids.map(k=>k.bottom))), boxB: Math.round(b.bottom) }; })()""")
            check(ov['sw'] <= ov['cw'] and ov['doc'] <= ov['vw'] and ov['kidsR'] <= ov['boxR'] and ov['kidsB'] <= ov['boxB'], f'[{scheme}] text 150% at 360px: the preview fits, no sideways scroll {ov}')
            await pg.screenshot(path=f'{shots}/shape-preview-big-{scheme}.png')
            await pg.evaluate("(()=>{ var r=document.getElementById('fontSizeRange'); r.value='100'; r.dispatchEvent(new Event('input')); r.dispatchEvent(new Event('change')); })()"); await pg.wait_for_timeout(300)
            await pg.set_viewport_size({'width': 390, 'height': 844}); await pg.wait_for_timeout(200)
            # build 400: the previews are first on their pages and stay at the top while scrolling (a short screen, so the pages scroll)
            await pg.set_viewport_size({'width': 390, 'height': 480}); await pg.wait_for_timeout(300)
            for cat, pid in (('appearance-type', 'fontPreview'), ('appearance-shape', 'shapePreview')):
                await pg.evaluate("(c)=>__t.ev('openSettings(\"' + c + '\")')", cat); await pg.wait_for_timeout(300)
                first = await pg.evaluate(f"(()=>{{ var pg=document.querySelector('.set-page[data-set-page={cat}]'); return pg.firstElementChild.contains(document.getElementById('{pid}')); }})()")
                await pg.evaluate("document.getElementById('settingsPanel').scrollTop = 99999"); await pg.wait_for_timeout(300)
                st = await pg.evaluate(f"""(()=>{{ var r=document.getElementById('{pid}').getBoundingClientRect(), p=document.getElementById('settingsPanel');
                  var hit=document.elementFromPoint(r.left+r.width/2, r.top+r.height/2); return {{ top: Math.round(r.top), h: Math.round(r.height), scrolled: p.scrollTop, hit: !!hit && document.getElementById('{pid}').contains(hit) || (hit && hit.closest && !!hit.closest('#{pid}')) }}; }})()""")
                check(first and st['scrolled'] > 0 and st['top'] >= 56 and st['top'] <= 64 and st['hit'], f'[{scheme}] {pid} is first and stays at the top while scrolling {st}')
                await pg.screenshot(path=f'{shots}/sticky-{cat}-{scheme}.png')
                await pg.evaluate("document.getElementById('settingsPanel').scrollTop = 0")
            await pg.set_viewport_size({'width': 390, 'height': 844}); await pg.wait_for_timeout(300)
            await pg.evaluate("__t.ev('openSettings(\"appearance\")')"); await pg.wait_for_timeout(300)
            for cat, ttl in (('appearance-theme', 'Theme & color'), ('appearance-sizes', 'Sizes & text'), ('appearance-type', 'Typography')):
                await pg.click(f'.set-subcats .set-cat[data-set-cat={cat}]'); await pg.wait_for_timeout(300)
                check(await pg.evaluate("document.getElementById('settingsTitle').textContent") == ttl, f'opens {ttl}')
                await pg.screenshot(path=f'{shots}/shape-{cat}-{scheme}.png')
                await pg.click('#settingsCloseBtn'); await pg.wait_for_timeout(250)
            if scheme == 'dark':
                async def setsel(i, v):
                    await pg.evaluate("([i,v])=>{ var s=document.getElementById(i); s.value=v; s.dispatchEvent(new Event('change')); }", [i, v]); await pg.wait_for_timeout(200)
                await pg.click('.set-subcats .set-cat[data-set-cat=appearance-shape]'); await pg.wait_for_timeout(300)
                await setsel('shapeRadiusSelect', 'square'); await setsel('shapeArtistSelect', 'square'); await setsel('shapeDensitySelect', 'compact')
                await pg.screenshot(path=f'{shots}/shape-page-square.png')
                await pg.evaluate("__t.ev('closeSettings()')"); await pg.wait_for_timeout(500)
                d1 = await pg.evaluate(probe); await pg.screenshot(path=f'{shots}/shape-home-square.png')
                check(d1['tile'] == '0px' and d1['artist'] in ('0px','none') and d1['tw'] < d0['tw'], f'square + compact applied {d1}')
                await pg.evaluate("__t.ev('openSettings(\"appearance-shape\")')"); await pg.wait_for_timeout(300)
                await setsel('shapeRadiusSelect', 'round'); await setsel('shapeArtistSelect', 'rounded'); await setsel('shapeDensitySelect', 'roomy')
                await pg.evaluate("__t.ev('closeSettings()')"); await pg.wait_for_timeout(500)
                d2 = await pg.evaluate(probe); await pg.screenshot(path=f'{shots}/shape-home-round.png')
                check(d2['tile'] == '18px' and d2['artist'] != '50%' and d2['tw'] > d0['tw'], f'round + roomy applied {d2}')
                await pg.reload(); await pg.wait_for_timeout(2500)
                await pg.evaluate("document.querySelector('.mobile-nav-btn[data-nav=home]').click()"); await pg.wait_for_timeout(700)
                check((await pg.evaluate(probe))['tile'] == '18px', 'choice survives reload')
                check('radioPlayerShape' in await pg.evaluate("window.__amplifyKvKeys"), 'saved in backups')
                await pg.evaluate("__t.ev('openSettings(\"appearance-shape\")')"); await pg.wait_for_timeout(300)
                await pg.click('#shapeResetBtn'); await pg.wait_for_timeout(200)
                await pg.evaluate("__t.ev('closeSettings()')"); await pg.wait_for_timeout(400)
                check((await pg.evaluate(probe))['tile'] == '8.5px', 'reset restores defaults')
                # ---- build 401: the Home carousel follows Corner radius; Play button shape on carousel, Now Playing, artist page ----
                await pg.evaluate("""(function(){ var ov=document.getElementById('addMusicOverlay'); if(ov) ov.classList.add('open');
                  var btn=document.getElementById('addMusicFolderBtn'); btn.disabled=false; btn.click(); })()""")
                for _ in range(60):
                    await pg.wait_for_timeout(500)
                    if await pg.evaluate('__v.tracks()') >= 5: break
                await pg.evaluate("document.getElementById('addMusicOverlay').classList.remove('open')"); await pg.wait_for_timeout(300); await pg.evaluate('__v.hide()')
                R = """(()=>{ function r(sel){ var e=document.querySelector(sel); return e && e.offsetParent ? getComputedStyle(e).borderTopLeftRadius : null; }
                  return { hero: r('.nph-track'), heroPlay: r('.nph-play'), np: r('.now-playing-screen .np-play-btn'), artist: r('#artistPlayBtn') }; })()"""
                async def home():
                    await pg.evaluate("__t.ev('closeSettings()')"); await pg.wait_for_timeout(300)
                    await pg.evaluate("document.querySelector('.mobile-nav-btn[data-nav=home]').click()"); await pg.wait_for_timeout(900)
                await pg.evaluate("__t.ev('openSettings(\"appearance-shape\")')"); await pg.wait_for_timeout(300)
                names = await pg.evaluate("Array.from(document.querySelectorAll('[data-set-page=appearance-shape] .settings-label')).map(e=>e.textContent)")
                check('Play button' in names, f'Shape & density has a Play button setting {names}')
                check(await pg.evaluate("document.getElementById('shapePlaySelect').value") == 'circle', 'play buttons default to circular')
                await home(); d = await pg.evaluate(R)
                check(d['hero'] == '22px' and d['heroPlay'] == '999px', f'defaults: carousel corners 22px, round play button {d}')
                for rad, play, hero, pr in (('round', 'square', '32px', '0px'), ('square', 'rounded', '0px', '16px')):
                    await pg.evaluate("__t.ev('openSettings(\"appearance-shape\")')"); await pg.wait_for_timeout(300)
                    await setsel('shapeRadiusSelect', rad); await setsel('shapePlaySelect', play)
                    await pg.screenshot(path=f'{shots}/play-shape-settings-{play}.png')
                    await home(); a = await pg.evaluate(R); await pg.screenshot(path=f'{shots}/play-shape-home-{play}.png')
                    check(a['hero'] == hero and a['heroPlay'] == pr, f'{rad} corners + {play} play: carousel {a["hero"]}, its play button {a["heroPlay"]}')
                    await pg.evaluate("__v.open('Alpha')"); await pg.wait_for_timeout(1500)
                    a = await pg.evaluate(R); await pg.screenshot(path=f'{shots}/play-shape-artist-{play}.png')
                    check(a['artist'] == pr, f'{play}: artist page Play button {a["artist"]}')
                    await pg.evaluate("__v.play()"); await pg.evaluate("__t.ev('openNowPlaying(currentStation, false)')"); await pg.wait_for_timeout(900)
                    a = await pg.evaluate(R); await pg.screenshot(path=f'{shots}/play-shape-np-{play}.png')
                    check(a['np'] == pr, f'{play}: Now Playing play button {a["np"]}')
                    await pg.evaluate("__t.ev('closeNowPlaying()')"); await pg.wait_for_timeout(500)
                await pg.evaluate("__t.ev('openSettings(\"appearance-shape\")')"); await pg.wait_for_timeout(300)
                await pg.click('#shapeResetBtn'); await pg.wait_for_timeout(200)
                check(await pg.evaluate("document.getElementById('shapePlaySelect').value") == 'circle', 'Reset puts the play button back to circular')
            check(not errs, f'no page errors {errs[:3]}')
            await ctx.close()
        await b.close()
    print('FAILED %s' % fails if fails else 'ALL PASSED')
asyncio.run(main())
