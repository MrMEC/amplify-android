"""Build 319: sideways Now Playing for a song: the progress bar's wave clears the artist / album line, the
controls sit below it, all on screen; Play / Pause is a circle. 844x390 and 780x360 touch, both themes.
Run: python3 tests/test_land_np_spacing.py (screenshots in /tmp/claude-0/t/shots)"""
import sys as _nsys, os as _nos; _nsys.path.insert(0, _nos.path.dirname(_nos.path.abspath(__file__))); from notice_auto import AUTO_NOTICE
import asyncio, os, json
HERE = os.path.dirname(os.path.abspath(__file__))
src = open(os.path.join(HERE, 'test_cf_after_video.py')).read()
head = src[:src.index('fails = []')]
head = head.replace("'/tmp/claude-0/t/srv_cfv'", "'/tmp/claude-0/t/srv_lnp'").replace('8848', '8849')
exec(head)
from playwright.async_api import async_playwright
fails = []
def check(c, m):
    print(('PASS ' if c else 'FAIL ') + m)
    if not c: fails.append(m)
GEO = """(()=>{ function r(id){ var e = document.getElementById(id); var b = e.getBoundingClientRect(); return { t: b.top, b: b.bottom, l: b.left, r: b.right, w: b.width, h: b.height }; }
  var sub = document.querySelector('#nowPlayingScreen .np-sub');
  var sb = sub.getBoundingClientRect(); var wave = r('npSeekWave'), seek = r('npSeek'), play = r('npPlayBtn');
  var pcs = getComputedStyle(document.getElementById('npPlayBtn'));
  return { subB: sb.bottom, waveT: wave.t, seekT: seek.t, seekB: seek.b, playT: play.t, playB: play.b, playW: play.w, playH: play.h,
    radius: pcs.borderTopLeftRadius, vh: innerHeight, rot: document.body.classList.contains('rotate-lock') }; })()"""
async def main():
    async with async_playwright() as p:
        for theme, size in (('dark', (844, 390)), ('light', (780, 360))):
            b = await p.chromium.launch()
            ctx = await b.new_context(viewport={'width': 390, 'height': 844}, device_scale_factor=2, is_mobile=True, has_touch=True, color_scheme=theme)
            await ctx.add_init_script(MOCK); await ctx.add_init_script(AUTO_NOTICE)
            await ctx.add_init_script("localStorage.setItem('radioPlayerTheme', '%s')" % theme)
            pg = await ctx.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
            await pg.goto(f'http://127.0.0.1:{PORT}/index.html'); await pg.wait_for_timeout(2500)
            await pg.evaluate("""(function(){ var ov=document.getElementById('addMusicOverlay'); if(ov) ov.classList.add('open');
              var btn=document.getElementById('addMusicFolderBtn'); btn.disabled=false; btn.click(); })()""")
            for _ in range(60):
                await pg.wait_for_timeout(500)
                if await pg.evaluate("(js)=>window.__h.ev(js)", 'libraryTracks.length') >= len(files): break
            await pg.evaluate("(js)=>window.__h.ev(js)", "runLibrarySection('songs'); 1"); await pg.wait_for_timeout(800)
            await pg.tap('#stationsGrid .song-row:not(.shuffle-all-row)'); await pg.wait_for_timeout(1200)
            await pg.set_viewport_size({'width': size[0], 'height': size[1]}); await pg.wait_for_timeout(1500)
            g = await pg.evaluate(GEO)
            T = '[%s %dx%d]' % (theme, size[0], size[1])
            check(g['rot'], T + ' sideways Now Playing')
            check(g['waveT'] >= g['subB'] + 2, T + ' the wave clears the artist / album line (%.1f below %.1f)' % (g['waveT'], g['subB']))
            check(g['playT'] >= g['seekB'] and g['playB'] <= g['vh'] - 4, T + ' controls below the bar and on screen (%.1f..%.1f of %d)' % (g['playT'], g['playB'], g['vh']))
            check(g['radius'] in ('50%',) or abs(float(g['radius'].replace('px', '') or 0) - g['playW'] / 2) < 1, T + ' Play / Pause is a circle (%s, %.0fx%.0f)' % (g['radius'], g['playW'], g['playH']))
            await pg.screenshot(path='%s/land-np-spacing-%s.png' % (shots, theme))
            check(not errs, T + ' no page errors %s' % errs[:2])
            await b.close()
    print('ALL PASSED' if not fails else 'FAILED %s' % fails)
    raise SystemExit(1 if fails else 0)
asyncio.run(main())
