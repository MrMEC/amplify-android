"""Build 285 (Mark): Live TV guide, dark mode: channel and show blocks solid black; the grid around
them as before; light mode unchanged. Run: python3 tests/test_b285.py (screenshots in /tmp/claude-0/t/shots)"""
import sys as _nsys, os as _nos; _nsys.path.insert(0, _nos.path.dirname(_nos.path.abspath(__file__)))
src = open(_nos.path.join(_nos.path.dirname(_nos.path.abspath(__file__)), 'test_live_channels_editor.py')).read()
src = src[:src.index('async def run2(')].replace('PORT = 8863', 'PORT = 8884').replace("srv-livech2'", "srv-b285'")
exec(src)
import sys
COL = """(()=>{ const ch = document.querySelector('#stationsGrid .epg-ch'), pr = document.querySelector('#stationsGrid .epg-prog:not(.now)'), now = document.querySelector('#stationsGrid .epg-prog.now');
  return { grid: getComputedStyle(document.querySelector('#stationsGrid .epg')).backgroundColor, chCell: getComputedStyle(ch, '::before').backgroundColor, chOuter: getComputedStyle(ch).backgroundColor,
    prog: getComputedStyle(pr).backgroundColor, now: now ? getComputedStyle(now).backgroundColor : null, text: getComputedStyle(pr.querySelector('.epg-t')).color }; })()"""
async def main():
    async with async_playwright() as p:
        for theme in ('dark', 'light'):
            T = f'[{theme}]'
            b = await p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
            ctx = await b.new_context(viewport={'width': 390, 'height': 844}, device_scale_factor=3, is_mobile=True, has_touch=True, color_scheme=theme, timezone_id='America/New_York')
            await ctx.add_init_script(MOCK); await ctx.add_init_script(AUTO_NOTICE); await ctx.add_init_script(SEED)
            await ctx.add_init_script("try{ localStorage.setItem('radioPlayerTheme', '%s'); }catch(e){}" % theme)
            pg = await ctx.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
            await pg.route('**/*', route)
            await pg.goto(f'http://127.0.0.1:{PORT}/index.html'); await pg.wait_for_timeout(2500)
            await pg.evaluate("document.querySelector('.mobile-nav-btn[data-nav=video]').click()"); await pg.wait_for_timeout(1200)
            c = await pg.evaluate(COL); print(T, c)
            if theme == 'dark':
                check(c['chCell'] == 'rgb(0, 0, 0)' and c['prog'] == 'rgb(0, 0, 0)' and c['now'] == 'rgb(0, 0, 0)', f'{T} channel and show blocks solid black {c}')
                check(c['grid'] == 'rgb(27, 28, 32)' and c['chOuter'] == 'rgb(27, 28, 32)', f'{T} the grid around them unchanged {c}')
            else:
                check(c['chCell'] == 'rgb(255, 255, 255)' and c['prog'] == 'rgb(255, 255, 255)' and c['grid'] == 'rgb(236, 238, 242)', f'{T} light mode unchanged {c}')
            await pg.screenshot(path=f'{SHOTS}/b285-guide-{theme}.png')
            # under a playing channel too
            await pg.evaluate("document.querySelector('#stationsGrid .epg-prog.now').click()"); await pg.wait_for_timeout(1500)
            np = await pg.evaluate("(()=>{ const e = document.querySelector('.now-playing-screen .epg-prog'); return e ? getComputedStyle(e).backgroundColor : null; })()")
            check(np == ('rgb(0, 0, 0)' if theme == 'dark' else 'rgb(255, 255, 255)'), f'{T} the guide under a playing channel matches {np}')
            await pg.screenshot(path=f'{SHOTS}/b285-np-{theme}.png')
            check(not errs, f'{T} no page errors {errs[:2]}')
            await b.close()
    print('ALL PASSED' if not fails else f'{fails} FAILED')
    sys.exit(1 if fails else 0)
asyncio.run(main())
