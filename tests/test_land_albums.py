"""Landscape Now Playing: an Albums button (the My Library Albums icon) sits just left of the
favourites arrow. It switches the screen to a blank Albums page: the favourites row slides shut,
the player fades out and the background fades to black, while the arrow stays put and the button
turns into the Now Playing bars (moving while music plays) that lead back.
Run: python3 tests/test_land_albums.py (screenshots in /tmp/claude-0/t/shots)"""
import asyncio, os, json
HERE = os.path.dirname(os.path.abspath(__file__))
src = open(os.path.join(HERE, 'test_land_favs.py')).read()
head = src[:src.index('async def main()')]
head = head.replace("'/tmp/claude-0/t/srv-lf'", "'/tmp/claude-0/t/srv-la'").replace('8785', '8787')
exec(head)
from playwright.async_api import async_playwright

BOX = """(function(s){var e=document.querySelector(s);if(!e)return null;var r=e.getBoundingClientRect();var c=getComputedStyle(e);
  return {t:Math.round(r.top),b:Math.round(r.bottom),l:Math.round(r.left),r:Math.round(r.right),w:Math.round(r.width),h:Math.round(r.height),
          d:c.display,o:c.opacity,v:c.visibility};})"""
BG = "getComputedStyle(document.getElementById('nowPlayingScreen')).backgroundColor"
ANIM = "getComputedStyle(document.querySelector('.la-ico-np span')).animationName"
TINT = "(function(){var e=document.createElement('div');e.style.color=getComputedStyle(document.getElementById('nowPlayingScreen')).getPropertyValue('--np-tint')||'#1c1d22';document.body.appendChild(e);var c=getComputedStyle(e).color;e.remove();return c;})()"


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
          var a=document.querySelector('#npLandAlbumsBtn .la-ico-albums').innerHTML.replace(/\\s+/g,'');
          var b=document.querySelector('.drawer-lib-link[data-lib="albums"] svg').innerHTML.replace(/\\s+/g,'');
          return a===b; })()""")
        check(same, 'same icon as Albums in My Library')
        check((await box('.la-ico-albums'))['o'] == '1' and (await box('.la-ico-np'))['o'] == '0', 'shows the Albums icon on Now Playing')
        tint = await pg.evaluate(BG)
        await pg.screenshot(path=f'{SHOTS}/la-closed.png')

        # open the favourites row, then go to Albums: the row slides shut on the way
        await pg.evaluate("document.getElementById('npLandToggle').click()"); await pg.wait_for_timeout(700)
        await pg.screenshot(path=f'{SHOTS}/la-favs-open.png')
        frames = await pg.evaluate("""new Promise(function(res){var o=[];document.getElementById('npLandAlbumsBtn').click();var t0=performance.now();
          (function f(){var sc=document.getElementById('nowPlayingScreen');
            o.push([Math.round(performance.now()-t0),Math.round(document.getElementById('npLandFavs').getBoundingClientRect().height),
              getComputedStyle(sc).backgroundColor,getComputedStyle(document.querySelector('.np-hero')).opacity]);
            if(performance.now()-t0<520)requestAnimationFrame(f);else res(o);})();})""")
        mid_rows = [f for f in frames if 0 < f[1] < 74]
        check(len(mid_rows) >= 3, f'favourites row animates closed {[f[1] for f in frames][::3]}')
        mid_bg = [f for f in frames if f[2] not in (tint, 'rgb(0, 0, 0)')]
        check(len(mid_bg) >= 3, f'background fades rather than snapping ({len(mid_bg)} in-between frames)')
        mid_op = [f for f in frames if 0 < float(f[3]) < 1]
        check(len(mid_op) >= 3, f'player fades out ({len(mid_op)} in-between frames)')
        await pg.wait_for_timeout(400)

        check(await pg.evaluate(BG) == 'rgb(0, 0, 0)', 'Albums page is black')
        hero = await box('.np-hero')
        check(hero['v'] == 'hidden' and hero['o'] == '0', f'player hidden on Albums {hero}')
        tog2, al2 = await box('#npLandToggle'), await box('#npLandAlbumsBtn')
        check(tog2['d'] == 'flex' and tog2['b'] >= 390 - 20 and tog2['r'] >= 844 - 20, f'arrow stays, back at the bottom right {tog2}')
        check(al2['t'] == tog2['t'] and al2['l'] == al['l'], f'Now Playing button where the Albums button was {al2}')
        check((await box('.la-ico-albums'))['o'] == '0' and (await box('.la-ico-np'))['o'] == '1', 'button shows the Now Playing bars')
        lbl = await pg.evaluate("document.getElementById('npLandAlbumsBtn').getAttribute('aria-label')")
        check(lbl == 'Back to Now Playing', f'labelled as the way back ({lbl})')
        txt = await pg.evaluate("document.getElementById('npLandAlbums').innerText.trim()")
        vis_text = await pg.evaluate("""(function(){var sc=document.getElementById('nowPlayingScreen');var w=document.createTreeWalker(sc,NodeFilter.SHOW_TEXT);var out=[];
          while(w.nextNode()){var n=w.currentNode;if(!n.textContent.trim())continue;var e=n.parentElement;var c=getComputedStyle(e);
            var r=e.getBoundingClientRect();if(c.visibility!=='hidden'&&r.width>0&&r.height>0){var op=1;for(var x=e;x;x=x.parentElement){op*=parseFloat(getComputedStyle(x).opacity);}if(op>0.01)out.push(n.textContent.trim());}}
          return out;})()""")
        check(vis_text == ['No albums in your library yet'], f'with no albums, Cover Flow says so and nothing else ({vis_text[:5]})')
        await pg.screenshot(path=f'{SHOTS}/la-page.png')

        # bars move while playing, stand still when paused
        check(await pg.evaluate(ANIM) == 'la-bars', 'bars animate while music plays')
        await pg.evaluate("document.getElementById('playPauseBtn').click()"); await pg.wait_for_timeout(500)
        playing = await pg.evaluate("document.body.classList.contains('ui-playing')")
        check(not playing and await pg.evaluate(ANIM) == 'none', 'bars still when paused')
        await pg.screenshot(path=f'{SHOTS}/la-page-paused.png')
        await pg.evaluate("document.getElementById('playPauseBtn').click()"); await pg.wait_for_timeout(500)
        check(await pg.evaluate(ANIM) == 'la-bars', 'bars move again on play')

        # the arrow still works on the Albums page
        await pg.evaluate("document.getElementById('npLandToggle').click()"); await pg.wait_for_timeout(700)
        row = await box('#npLandFavs')
        check(row['h'] >= 52, f'arrow opens the favourites row on Albums {row}')
        await pg.screenshot(path=f'{SHOTS}/la-page-favs.png')
        await pg.evaluate("document.getElementById('npLandToggle').click()"); await pg.wait_for_timeout(700)

        # back to Now Playing: background fades back to the station tint
        frames = await pg.evaluate("""new Promise(function(res){var o=[];document.getElementById('npLandAlbumsBtn').click();var t0=performance.now();
          (function f(){o.push(getComputedStyle(document.getElementById('nowPlayingScreen')).backgroundColor);
            if(performance.now()-t0<520)requestAnimationFrame(f);else res(o);})();})""")
        check(len([c for c in frames if c not in (tint, 'rgb(0, 0, 0)')]) >= 3, 'background fades back')
        await pg.wait_for_timeout(400)
        check(await pg.evaluate(BG) == tint, f'back to the Now Playing colour ({await pg.evaluate(BG)} vs {tint})')
        hero = await box('.np-hero')
        check(hero['v'] == 'visible' and hero['o'] == '1', 'player back')
        check((await box('.la-ico-albums'))['o'] == '1', 'Albums icon back')
        nm = await pg.evaluate("document.getElementById('npName').textContent")
        check(nm == 'Station 2', f'still on the same station ({nm!r})')
        await pg.screenshot(path=f'{SHOTS}/la-back.png')

        # turning the phone resets it
        await pg.evaluate("document.getElementById('npLandAlbumsBtn').click()"); await pg.wait_for_timeout(300)
        await pg.set_viewport_size({'width': 390, 'height': 844}); await pg.wait_for_timeout(600)
        await pg.set_viewport_size({'width': 844, 'height': 390}); await pg.wait_for_timeout(900)
        check(not await pg.evaluate("document.getElementById('nowPlayingScreen').classList.contains('la-open')"), 'closed again after turning the phone back')
        check(not errs, f'no page errors {errs[:3]}')
        await b.close()
    print('ALL PASSED' if not fails else f'FAILED {fails}')
asyncio.run(main())
