"""Landscape Now Playing: an Albums button (the My Library Albums icon) sits just left of the
favourites arrow and opens a blank Albums page whose only content is a button at the bottom right
back to Now Playing.
Run: python3 tests/test_land_albums.py (screenshots in /tmp/claude-0/t/shots)"""
import asyncio, os, json
HERE = os.path.dirname(os.path.abspath(__file__))
src = open(os.path.join(HERE, 'test_land_favs.py')).read()
head = src[:src.index('async def main()')]
head = head.replace("'/tmp/claude-0/t/srv-lf'", "'/tmp/claude-0/t/srv-la'").replace('8785', '8787')
exec(head)
from playwright.async_api import async_playwright

BOX = """(function(s){var e=document.querySelector(s);if(!e)return null;var r=e.getBoundingClientRect();
  return {t:Math.round(r.top),b:Math.round(r.bottom),l:Math.round(r.left),r:Math.round(r.right),w:Math.round(r.width),h:Math.round(r.height),
          d:getComputedStyle(e).display};})"""


async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
        ctx = await b.new_context(viewport={'width': 844, 'height': 390}, device_scale_factor=2, is_mobile=True, has_touch=True, color_scheme='dark', locale='en-US')
        await ctx.add_init_script(MOCK)
        await ctx.add_init_script("if(!localStorage.getItem('radioPlayerFavorites')) localStorage.setItem('radioPlayerFavorites', %s);" % repr(json.dumps(FAVS)))
        pg = await ctx.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.route('**/*', route2)
        await pg.goto('http://127.0.0.1:8787/index.html'); await pg.wait_for_timeout(2500)
        await pg.set_viewport_size({'width': 390, 'height': 844}); await pg.wait_for_timeout(600)
        await pg.evaluate("document.querySelector('.mobile-nav-btn[data-nav=home]').click()"); await pg.wait_for_timeout(600)
        await pg.evaluate("Array.prototype.find.call(document.querySelectorAll('.tile'),function(x){return x.dataset.key==='u2';}).click()"); await pg.wait_for_timeout(1000)
        box = lambda s: pg.evaluate(BOX + "('" + s + "')")
        check((await box('#npLandAlbumsBtn'))['d'] == 'none', 'no Albums button in portrait')
        await pg.set_viewport_size({'width': 844, 'height': 390}); await pg.wait_for_timeout(900)

        al, tog = await box('#npLandAlbumsBtn'), await box('#npLandToggle')
        check(al['d'] == 'flex' and al['w'] == 44, f'Albums button shown in landscape {al}')
        check(al['r'] <= tog['l'] and tog['l'] - al['r'] <= 16 and al['t'] == tog['t'], f'just left of the arrow, same row {al} {tog}')
        same = await pg.evaluate("""(function(){
          var a=document.querySelector('#npLandAlbumsBtn svg').innerHTML.replace(/\\s+/g,'');
          var b=document.querySelector('.drawer-lib-link[data-lib="albums"] svg').innerHTML.replace(/\\s+/g,'');
          return a===b; })()""")
        check(same, 'same icon as Albums in My Library')
        await pg.screenshot(path=f'{SHOTS}/la-closed.png')

        # rides up with the favourites row
        await pg.evaluate("document.getElementById('npLandToggle').click()"); await pg.wait_for_timeout(700)
        al2, tog2 = await box('#npLandAlbumsBtn'), await box('#npLandToggle')
        check(al2['t'] == tog2['t'] and al2['t'] < al['t'], f'moves up with the arrow when the row opens {al2} {tog2}')
        await pg.screenshot(path=f'{SHOTS}/la-favs-open.png')
        await pg.evaluate("document.getElementById('npLandToggle').click()"); await pg.wait_for_timeout(700)

        # open the Albums page
        await pg.evaluate("document.getElementById('npLandAlbumsBtn').click()"); await pg.wait_for_timeout(400)
        page, back = await box('#npLandAlbums'), await box('#npLandAlbumsBack')
        check(page['d'] == 'block' and page['l'] == 0 and page['t'] == 0 and page['w'] == 844 and page['h'] == 390, f'Albums page covers the screen {page}')
        check(back['r'] >= 844 - 20 and back['b'] >= 390 - 20 and back['w'] == 44, f'back button at the bottom right {back}')
        txt = await pg.evaluate("document.getElementById('npLandAlbums').innerText.trim()")
        kids = await pg.evaluate("document.getElementById('npLandAlbums').children.length")
        check(txt == '' and kids == 1, f'blank: no labels, only the button ({txt!r}, {kids})')
        top = await pg.evaluate("(function(){var e=document.elementFromPoint(300,150);return e.id||e.className;})()")
        check(top == 'npLandAlbums', f'nothing of the player shows through ({top})')
        await pg.screenshot(path=f'{SHOTS}/la-page.png')

        # back to Now Playing
        await pg.evaluate("document.getElementById('npLandAlbumsBack').click()"); await pg.wait_for_timeout(400)
        check((await box('#npLandAlbums'))['d'] == 'none', 'back button returns to Now Playing')
        nm = await pg.evaluate("document.getElementById('npName').textContent")
        check(nm == 'Station 2', f'still on the same station ({nm!r})')

        # turning the phone resets it
        await pg.evaluate("document.getElementById('npLandAlbumsBtn').click()"); await pg.wait_for_timeout(300)
        await pg.set_viewport_size({'width': 390, 'height': 844}); await pg.wait_for_timeout(600)
        await pg.set_viewport_size({'width': 844, 'height': 390}); await pg.wait_for_timeout(700)
        check((await box('#npLandAlbums'))['d'] == 'none', 'closed again after turning the phone back')
        check(not errs, f'no page errors {errs[:3]}')
        await b.close()
    print('ALL PASSED' if not fails else f'FAILED {fails}')
asyncio.run(main())
