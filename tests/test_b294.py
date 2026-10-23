"""Build 294 (Mark): Now Playing's progress bar gets a Samsung-style flowing wave in the cover's
colour over the played part, which stops (eases flat) when nothing plays; the dot has a white ring.
Run: python3 tests/test_b294.py (screenshots in /tmp/claude-0/t/shots)"""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
__file__ = os.path.join(HERE, 'test_daily_mixes.py')
src = open(os.path.join(HERE, 'test_daily_mixes.py')).read()
src = src[:src.index('async def run(theme):')]
src = src.replace('PORT = 8803', 'PORT = 8892').replace("srv_daily'", "srv_b294'")
src = src.replace('" stopPlay:', '''" w294: { play: function(){ var t = libraryTracks.filter(function(x){ return x.artist === 'Prince'; })[0]; audio.play = function(){ return Promise.resolve(); };"
  "     playEntity(t); setTimeout(function(){ Object.defineProperty(audio, 'duration', { configurable: true, get: function(){ return 200; } });"
  "     Object.defineProperty(audio, 'currentTime', { configurable: true, get: function(){ return 130; }, set: function(){} }); Object.defineProperty(audio, 'paused', { configurable: true, get: function(){ return !uiIsPlaying; } });"
  "     openNowPlaying(currentStation); setPlayingUI(true); syncSeekBar(); }, 600); },"
  "   pause: function(){ setPlayingUI(false); }, resume: function(){ setPlayingUI(true); },"
  "   px: function(){ var c = document.getElementById('npSeekWave'); var ctx = c.getContext('2d'); var d = ctx.getImageData(0, 0, c.width, c.height).data; var n = 0, sum = 0; for(var i = 3; i < d.length; i += 4){ if(d[i] > 8) n++; sum = (sum * 31 + d[i]) % 1000003; } return { lit: n, sig: sum, w: c.width, h: c.height }; },"
  "   colH: function(cssX){ var c = document.getElementById('npSeekWave'), dpr = c.width / c.clientWidth, x = Math.round(cssX * dpr); var d = c.getContext('2d').getImageData(x, 0, 1, c.height).data; for(var y = 0; y < c.height; y++) if(d[y * 4 + 3] > 8) return (c.height - y) / dpr; return 0; },"
  "   dotX: function(){ var c = document.getElementById('npSeekWave'), r = document.getElementById('npSeekRange'); return 8 + (r.value / 1000) * (c.clientWidth - 16); },"
  "   gap: function(){ var a = document.getElementById('npSeek').getBoundingClientRect(), t = document.querySelector('.np-seek-range').getBoundingClientRect(), u = document.getElementById('npUpNext').getBoundingClientRect(); return { below: Math.round(u.top - t.bottom) }; },"
  "   litRight: function(){ var c = document.getElementById('npSeekWave'); var d = c.getContext('2d').getImageData(Math.round(c.width * 0.8), 0, Math.round(c.width * 0.2), c.height).data; var n = 0; for(var i = 3; i < d.length; i += 4) if(d[i] > 8) n++; return n; },"
  "   thumb: function(){ var cs = getComputedStyle(document.getElementById('npSeekRange'), '::-webkit-slider-thumb'); return { border: cs.borderTopWidth + ' ' + cs.borderTopStyle + ' ' + cs.borderTopColor, w: cs.width }; },"
  "   vivid: function(){ return getComputedStyle(nowPlayingScreen).getPropertyValue('--np-vivid').trim(); } },"
  " stopPlay:''')
exec(src)
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
        ctx = await b.new_context(viewport={'width': 390, 'height': 844}, device_scale_factor=3, is_mobile=True, has_touch=True, color_scheme='dark')
        await ctx.add_init_script(MOCK); await ctx.add_init_script(AUTO_NOTICE)
        pg = await ctx.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.route('**/*', lambda route: route.continue_() if '127.0.0.1' in route.request.url else route.abort())
        await pg.goto(f'http://127.0.0.1:{PORT}/index.html'); await pg.wait_for_timeout(2500)
        await pg.evaluate("""(function(){ var ov=document.getElementById('addMusicOverlay'); if(ov) ov.classList.add('open');
          var btn=document.getElementById('addMusicFolderBtn'); btn.disabled=false; btn.click(); })()""")
        for _ in range(90):
            await pg.wait_for_timeout(500)
            if await pg.evaluate("__d.n()") >= len(SONGS): break
        await pg.evaluate("document.getElementById('addMusicOverlay').classList.remove('open'); try{ hideImportPanel(); setStatus('', false); }catch(e){}")
        await pg.evaluate("__d.w294.play()"); await pg.wait_for_timeout(2500)
        a = await pg.evaluate("__d.w294.px()"); await pg.wait_for_timeout(400); b2 = await pg.evaluate("__d.w294.px()")
        print('playing', a, b2, await pg.evaluate("__d.w294.vivid()"))
        check(a['lit'] > 500 and b2['lit'] > 500, f'playing: a wave is drawn over the bar {a["lit"]}')
        check(a['sig'] != b2['sig'], 'and it moves')
        await pg.wait_for_timeout(300)
        dx = await pg.evaluate("__d.w294.dotX()")
        hs = [await pg.evaluate(f"__d.w294.colH({dx + o})") for o in (2, -2, -60, -120)]
        print('heights at dot+2, dot-2, dot-60, dot-120:', hs)
        check(hs[0] == 0 and hs[1] < 4, f'the wave springs from the dot: nothing past it, flat right at it {hs[:2]}')
        check(max(hs[2], hs[3]) > 8, f'and it rises away from the dot {hs[2:]}')
        print('gap from bar to Next card:', await pg.evaluate("__d.w294.gap()"))
        check(await pg.evaluate("__d.w294.litRight()") == 0, 'only over the played part (65%): nothing past it')
        t = await pg.evaluate("__d.w294.thumb()"); print(t)
        print('ring checked in the screenshot (the thumb pseudo-element isn\'t readable)')
        el = await pg.query_selector('#npSeek')
        await el.screenshot(path=f'{shots}/b294-wave-1.png'); await pg.wait_for_timeout(300); await el.screenshot(path=f'{shots}/b294-wave-2.png')
        await pg.screenshot(path=f'{shots}/b294-np.png')
        bx = await pg.evaluate("(()=>{ const r = document.getElementById('npSeek').getBoundingClientRect(); return [r.left, r.top - 40, r.width, r.height + 40]; })()")
        await pg.screenshot(path=f'{shots}/b294-zoom-1.png', clip={'x': bx[0], 'y': bx[1], 'width': bx[2], 'height': bx[3]})
        await pg.wait_for_timeout(500)
        await pg.screenshot(path=f'{shots}/b294-zoom-2.png', clip={'x': bx[0], 'y': bx[1], 'width': bx[2], 'height': bx[3]})
        await pg.evaluate("__d.w294.pause()"); await pg.wait_for_timeout(1500)
        c1 = await pg.evaluate("__d.w294.px()"); await pg.wait_for_timeout(500); c2 = await pg.evaluate("__d.w294.px()")
        raf = await pg.evaluate("(()=>{ let n = 0; return new Promise(r => { const t0 = performance.now(); (function f(){ n++; if(performance.now() - t0 < 300) requestAnimationFrame(f); else r(n); })(); }); })()")
        print('paused', c1, c2)
        check(c1['lit'] < 50 and c1['sig'] == c2['sig'], f'paused: the wave flattens out and stops {c1["lit"]}')
        await el.screenshot(path=f'{shots}/b294-paused.png')
        await pg.evaluate("__d.w294.resume()"); await pg.wait_for_timeout(1200)
        d = await pg.evaluate("__d.w294.px()")
        check(d['lit'] > 500, f'playing again: the wave comes back {d["lit"]}')
        await pg.evaluate("closeNowPlaying && closeNowPlaying()") if False else None
        check(not errs, f'no page errors {errs[:2]}')
        await b.close()
    print('ALL PASSED' if not fails else f'{len(fails)} FAILED')
    sys.exit(1 if fails else 0)
asyncio.run(main())
