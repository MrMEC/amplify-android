"""Build 297 (Mark): Next card evenly centred. Built on test_b294 / Build 294 (Mark): Now Playing's progress bar gets a Samsung-style flowing wave in the cover's
colour over the played part, which stops (eases flat) when nothing plays; the dot has a white ring.
Run: python3 tests/test_b294.py (screenshots in /tmp/claude-0/t/shots)"""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
__file__ = os.path.join(HERE, 'test_daily_mixes.py')
src = open(os.path.join(HERE, 'test_daily_mixes.py')).read()
src = src[:src.index('async def run(theme):')]
src = src.replace('PORT = 8803', 'PORT = 8893').replace("srv_daily'", "srv_b297'")
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

GAPS = """(()=>{ const vis = e => e && e.offsetParent !== null && getComputedStyle(e).display !== 'none';
  const u = document.getElementById('npUpNext').getBoundingClientRect();
  const seek = document.getElementById('npSeek'); const ctl = document.getElementById('npPlayBtn').getBoundingClientRect();
  const above = vis(seek) ? document.querySelector('.np-seek-times').getBoundingClientRect().bottom : ctl.bottom;
  const h = [...document.querySelectorAll('.np-below .np-related')].filter(vis)[0];
  const hh = h && h.querySelector('.np-related-heading').getBoundingClientRect();
  return { above: Math.round(u.top - above), below: hh ? Math.round(hh.top - u.bottom) : null, which: h && h.id }; })()"""
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
        g = await pg.evaluate(GAPS); print('track', g)
        check(g['below'] is not None and abs(g['above'] - g['below']) <= 2, f'track: the Next card sits evenly between the bar and the heading {g}')
        await pg.screenshot(path=f'{shots}/b297-track.png')
        # a stream has no progress bar: the same layout with it hidden
        await pg.evaluate("document.getElementById('npSeek').style.display = 'none'")
        await pg.wait_for_timeout(400)
        g2 = await pg.evaluate(GAPS); print('station', g2)
        if g2['below'] is not None and await pg.evaluate("getComputedStyle(document.getElementById('npUpNext')).display") != 'none':
            check(abs(g2['above'] - g2['below']) <= 2, f'station: evenly between the controls and the heading {g2}')
        await pg.screenshot(path=f'{shots}/b297-station.png')
        check(not errs, f'no page errors {errs[:2]}')
        await b.close()
    print('ALL PASSED' if not fails else f'FAILED {len(fails)}')
asyncio.run(main())
