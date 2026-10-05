"""Build 135: Recent Searches on the search page: tight rows aligned with the heading (no
indent, small gaps), more room under the heading, and an X on each row to delete that search.
Run: python3 tests/test_recent_searches.py (screenshots in /tmp/claude-0/t/shots)"""
import asyncio, os, json
HERE = os.path.dirname(os.path.abspath(__file__))
src = open(os.path.join(HERE, 'test_video_channels.py')).read()
head = src[:src.index('async def rows(pg)')]
head = head.replace("'/tmp/claude-0/t/srv-ch'", "'/tmp/claude-0/t/srv-recent'").replace('8777', '8805')
exec(head)
from playwright.async_api import async_playwright
RS = ['Twilight zone', 'Ben', 'Mariah', 'Sting', 'Lady gag', 'Dua lipa', 'Whitney']
SEED = "if(!localStorage.getItem('radioPlayerRecentSearches')) localStorage.setItem('radioPlayerRecentSearches', %s);" % repr(json.dumps(RS))
async def vroute(r):
    u = r.request.url
    if 'radio-browser' in u or 'api.radio' in u: return await r.fulfill(status=200, content_type='application/json', body='[]')
    if 'itunes.apple.com' in u: return await r.abort()
    return await route(r)
GEO = """(()=>{var h=document.querySelector('.recent-searches-head'), hs=h.querySelector('span').getBoundingClientRect();
  var rows=Array.prototype.map.call(document.querySelectorAll('.recent-search-row'),function(r){var b=r.getBoundingClientRect(),i=r.querySelector('.song-row-art'),ib=i.getBoundingClientRect(),
    t=r.querySelector('.song-row-title').getBoundingClientRect(), x=r.querySelector('.recent-search-del');
    return {top:Math.round(b.top),h:Math.round(b.height),iconL:Math.round(ib.left),iconW:Math.round(ib.width),textL:Math.round(t.left),title:r.querySelector('.song-row-title').textContent,
      del: x ? [Math.round(x.getBoundingClientRect().width), Math.round(x.querySelector('svg').getBoundingClientRect().right)] : null};});
  var c=document.querySelector('.recent-searches-clear');
  return {clearR: c ? Math.round(c.getBoundingClientRect().right - parseFloat(getComputedStyle(c).paddingRight)) : 0, vw: window.innerWidth, headL:Math.round(hs.left), headBottom:Math.round(h.getBoundingClientRect().bottom), rows:rows, gridR:Math.round(document.getElementById('stationsGrid').getBoundingClientRect().right)};})()"""
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
        ctx = await b.new_context(viewport={'width': 390, 'height': 844}, device_scale_factor=2, is_mobile=True, has_touch=True, color_scheme='dark', locale='en-US')
        await ctx.add_init_script(MOCK); await ctx.add_init_script(SEED)
        pg = await ctx.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.route('**/*', vroute)
        await pg.goto('http://127.0.0.1:8805/index.html'); await pg.wait_for_timeout(2500)
        await pg.evaluate("document.querySelector('.mobile-nav-btn[data-nav=search]').click()"); await pg.wait_for_timeout(400)
        await pg.tap('#searchSheetInput'); await pg.wait_for_timeout(500)
        g = await pg.evaluate(GEO)
        print(json.dumps(g))
        await pg.screenshot(path=f'{SHOTS}/recent-searches.png')
        r = g['rows']
        check([x['title'] for x in r] == RS, f'all recent searches listed {[x["title"] for x in r]}')
        check(abs(r[0]['iconL'] - g['headL']) <= 2, f'icons line up with the heading, no indent (icon {r[0]["iconL"]}, heading {g["headL"]})')
        check(r[0]['textL'] - r[0]['iconL'] <= 34, f'text close to the icon ({r[0]["textL"] - r[0]["iconL"]}px)')
        pitch = r[1]['top'] - r[0]['top']
        check(44 <= pitch <= 52, f'rows close together ({pitch}px apart)')
        gap = r[0]['top'] - g['headBottom']
        check(12 <= gap <= 22, f'more room under the heading ({gap}px)')
        check(all(x['del'] and x['del'][0] >= 36 and abs(x['del'][1] - g['clearR']) <= 2 for x in r), f'an X on every row, lined up under Clear {[x["del"] for x in r][:2]} {g["clearR"]}')
        # delete one
        await pg.evaluate("document.querySelectorAll('.recent-search-row')[1].querySelector('.recent-search-del').click()"); await pg.wait_for_timeout(300)
        left = await pg.evaluate("Array.prototype.map.call(document.querySelectorAll('.recent-search-row .song-row-title'),function(t){return t.textContent;})")
        saved = await pg.evaluate("JSON.parse(localStorage.getItem('radioPlayerRecentSearches'))")
        val = await pg.evaluate("document.getElementById('searchSheetInput').value")
        check(left == [x for x in RS if x != 'Ben'] and saved == left and val == '', f'X deletes just that search, without running it {left} {saved} {val!r}')
        await pg.screenshot(path=f'{SHOTS}/recent-searches-deleted.png')
        # tapping a row still runs it
        await pg.evaluate("document.querySelectorAll('.recent-search-row')[1].click()"); await pg.wait_for_timeout(600)
        val = await pg.evaluate("document.getElementById('searchSheetInput').value")
        check(val == 'Mariah', f'tapping a row runs it ({val})')
        # deleting the last one leaves the empty message
        await pg.fill('#searchSheetInput', ''); await pg.wait_for_timeout(500)
        for i in range(6):
            await pg.evaluate("document.querySelector('.recent-search-row .recent-search-del').click()"); await pg.wait_for_timeout(150)
        n = await pg.evaluate("document.querySelectorAll('.recent-search-row').length")
        emp = await pg.evaluate("(document.querySelector('#stationsGrid .empty-state')||{}).textContent||''")
        check(n == 0 and 'Search for' in emp, f'none left: the empty message ({n}, {emp[:30]})')
        # bigger text at 360 wide
        await pg.evaluate("localStorage.setItem('radioPlayerRecentSearches', JSON.stringify(['A very long search that will not fit on one line at all','Sting']))")
        await pg.reload(); await pg.wait_for_timeout(2000)
        await pg.set_viewport_size({'width': 360, 'height': 780})
        await pg.add_style_tag(content='.recent-search-row .song-row-title, .recent-searches-head{ font-size:20px !important; }')
        await pg.evaluate("document.querySelector('.mobile-nav-btn[data-nav=search]').click()"); await pg.wait_for_timeout(400)
        await pg.tap('#searchSheetInput'); await pg.wait_for_timeout(500)
        g = await pg.evaluate(GEO)
        check(all(x['del'] and x['del'][1] <= g['vw'] - 16 for x in g['rows']) and g['rows'][0]['h'] <= 70, f'big text: the X stays on screen {g["rows"]}')
        await pg.screenshot(path=f'{SHOTS}/recent-searches-big.png')
        check(not errs, f'no page errors {errs[:3]}')
        await b.close()
    print('ALL PASSED' if not fails else f'FAILED {fails}')
asyncio.run(main())
