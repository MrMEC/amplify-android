"""Build 284 (Mark): every heart is a star (filled when a favourite, outlined when not).
Run: python3 tests/test_b284.py (screenshots in /tmp/claude-0/t/shots)"""
import sys as _nsys, os as _nos; _nsys.path.insert(0, _nos.path.dirname(_nos.path.abspath(__file__)))
src = open(_nos.path.join(_nos.path.dirname(_nos.path.abspath(__file__)), 'test_live_channels_editor.py')).read()
src = src[:src.index('async def run2(')].replace('PORT = 8863', 'PORT = 8883').replace("srv-livech2'", "srv-b284'")
exec(src)
import sys
ICONS = """Array.from(document.querySelectorAll('.fa-heart')).filter(e => e.offsetParent).map(e => { const b = getComputedStyle(e, '::before');
  return { cls: e.className, content: b.content, mask: (b.webkitMaskImage || b.maskImage || '').indexOf('svg') >= 0, filled: (b.webkitMaskImage || b.maskImage || '').indexOf("fill='%23000'") >= 0 || (b.webkitMaskImage || '').indexOf('fill%3D') >= 0,
    w: Math.round(e.getBoundingClientRect().width) }; })"""
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
            # favourite Seinfeld from its options, then look at the guide's mark and the sheet
            await pg.evaluate("Array.from(document.querySelectorAll('#stationsGrid .epg-ch')).find(c => c.getAttribute('aria-label').startsWith('Seinfeld')).click()"); await pg.wait_for_timeout(400)
            await pg.screenshot(path=f'{SHOTS}/b284-sheet-{theme}.png')
            ic = await pg.evaluate(ICONS); print(T, ic)
            check(ic and all(i['content'] in ('""', 'none', "''") and i['mask'] for i in ic), f'{T} the sheet\'s Add to Favorites shows a star, no heart glyph {ic}')
            await pg.evaluate("Array.from(document.querySelectorAll('#chSheetItems .ch-sheet-item')).find(e => e.textContent === 'Add to Favorites').click()"); await pg.wait_for_timeout(700)
            ic = await pg.evaluate(ICONS)
            check(any('epg-heart' in i['cls'] and i['mask'] for i in ic), f'{T} the guide marks a favourite with a star {ic}')
            await pg.screenshot(path=f'{SHOTS}/b284-guide-{theme}.png')
            # Now Playing for a channel: its favourite button and the menu
            await pg.evaluate("Array.from(document.querySelectorAll('#stationsGrid .epg-row')).find(r => r.textContent.indexOf('Buzzr') >= 0).querySelector('.epg-prog').click()"); await pg.wait_for_timeout(1500)
            await pg.evaluate("(document.getElementById('npMenuBtn') || {click(){}}).click()"); await pg.wait_for_timeout(500)
            ic = await pg.evaluate(ICONS); print(T, 'np', ic)
            check(ic and all(i['mask'] for i in ic), f'{T} Now Playing: stars only {ic}')
            await pg.screenshot(path=f'{SHOTS}/b284-np-{theme}.png')
            # nothing left anywhere in the page draws the heart glyph
            left = await pg.evaluate("""Array.from(document.querySelectorAll('*')).filter(e => { const c = getComputedStyle(e, '::before').content; return c && c.indexOf('\\uf004') >= 0; }).length""")
            check(left == 0, f'{T} no heart glyph anywhere ({left})')
            check(not errs, f'{T} no page errors {errs[:2]}')
            await b.close()
    print('ALL PASSED' if not fails else f'{fails} FAILED')
    sys.exit(1 if fails else 0)
asyncio.run(main())
