"""A stream added by its link: titled from the link at first, then by the stream's own name
(icy-name) once it plays, and renameable from Now Playing's More menu. Also: the Podcasts
date headings are small grey capitals under bold section labels (build 164).
Run: python3 tests/test_stream_rename.py (screenshots in /tmp/claude-0/t/shots)"""
import asyncio, os, json
HERE = os.path.dirname(os.path.abspath(__file__))
src = open(os.path.join(HERE, 'test_video_channels.py')).read()
head = src[:src.index('async def rows(pg)')]
head = head.replace("'/tmp/claude-0/t/srv-ch'", "'/tmp/claude-0/t/srv-ren'").replace('8777', '8784')
exec(head)
from playwright.async_api import async_playwright

URL = 'https://radio.wanderingsheep.net:8000/jazzcafe'
OLD = 'https://old.example:8000/stream'
RECENT = [{'name': 'KEXP', 'urlToResolve': 'https://kexp.example/s', 'url_resolved': 'https://kexp.example/s', 'stationuuid': 'k1', 'tags': '', 'country': '', 'favicon': None},
          {'name': OLD, 'urlToResolve': OLD, 'favicon': None, 'tags': '', 'country': '', 'codec': '', 'bitrate': '', 'stationuuid': None}]

async def np_name(pg):
    return await pg.evaluate("document.getElementById('npName').textContent")
async def recent_names(pg):
    return await pg.evaluate("JSON.parse(localStorage.getItem('radioPlayerRecent')||'[]').map(function(r){return r.name;})")
async def icy(pg, name):
    await pg.evaluate("(n)=>window.__emit('streamname',{id:window.__cur,name:n})", name); await pg.wait_for_timeout(300)
async def open_np(pg):
    await pg.evaluate("document.getElementById('playerBar').querySelector('.name').click()"); await pg.wait_for_timeout(700)

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
        ctx = await b.new_context(viewport={'width': 390, 'height': 844}, device_scale_factor=2, is_mobile=True, has_touch=True, color_scheme='dark', locale='en-US')
        await ctx.add_init_script(MOCK)
        await ctx.add_init_script("if(!localStorage.getItem('radioPlayerRecent')) localStorage.setItem('radioPlayerRecent', %s);" % repr(json.dumps(RECENT)))
        pg = await ctx.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e) + ' @ ' + (e.stack or '')[:300]))
        answers = []
        async def on_dialog(d):
            await d.accept(answers.pop(0) if answers else '')
        pg.on('dialog', lambda d: asyncio.ensure_future(on_dialog(d)))
        await pg.route('**/*', route)
        await pg.goto('http://127.0.0.1:8784/index.html'); await pg.wait_for_timeout(2500)

        # paste the link
        await pg.evaluate("(u)=>{var i=document.getElementById('searchInput'); i.value=u; document.getElementById('searchBtn').click();}", URL)
        await pg.wait_for_timeout(1200)
        pn = await pg.evaluate("document.getElementById('playerName').textContent")
        check(pn == 'Jazzcafe', f'titled from the link, not the whole link ({pn!r})')
        await open_np(pg)
        # the stream says its name
        await icy(pg, 'Jazz Cafe Radio')
        n = await np_name(pg); pn = await pg.evaluate("document.getElementById('playerName').textContent")
        rec = await recent_names(pg)
        check(n == 'Jazz Cafe Radio' and pn == 'Jazz Cafe Radio' and rec[0] == 'Jazz Cafe Radio', f'the stream\'s own name replaces it ({n!r}, {pn!r}, {rec})')
        await pg.screenshot(path=f'{SHOTS}/ren-icy.png')
        # rename from the More menu
        await pg.evaluate("document.getElementById('npMenuBtn').click()"); await pg.wait_for_timeout(300)
        vis = await pg.evaluate("getComputedStyle(document.getElementById('npRenameBtn')).display")
        check(vis != 'none', f'Rename is in the More menu ({vis})')
        await pg.screenshot(path=f'{SHOTS}/ren-menu.png')
        answers.append('Wandering Sheep Jazz')
        await pg.evaluate("document.getElementById('npRenameBtn').click()"); await pg.wait_for_timeout(500)
        n = await np_name(pg); rec = await recent_names(pg)
        check(n == 'Wandering Sheep Jazz' and rec[0] == 'Wandering Sheep Jazz', f'renamed everywhere ({n!r}, {rec})')
        # a name you chose stays, even when the stream announces its own again
        await icy(pg, 'Jazz Cafe Radio')
        n = await np_name(pg)
        check(n == 'Wandering Sheep Jazz', f'your name is kept ({n!r})')
        await pg.screenshot(path=f'{SHOTS}/ren-renamed.png')
        await pg.evaluate("document.getElementById('npBackBtn').click()"); await pg.wait_for_timeout(500)
        # an older stream saved with the whole link as its name gets fixed when it plays
        await pg.evaluate("document.querySelector('.mobile-nav-btn[data-nav=home]').click()"); await pg.wait_for_timeout(700)
        await pg.evaluate("(u)=>{ var t=Array.prototype.find.call(document.querySelectorAll('#recentGrid .tile, .tile'),function(x){return x.dataset.key===u;}); t.click(); }", OLD)
        await pg.wait_for_timeout(1000)
        await icy(pg, 'Old Station FM')
        rec = await recent_names(pg)
        check('Old Station FM' in rec and OLD not in rec, f'an older link-named stream takes its real name {rec}')
        # a radio-browser station has no Rename
        await pg.evaluate("document.querySelector('.mobile-nav-btn[data-nav=home]').click()"); await pg.wait_for_timeout(700)
        await pg.evaluate("Array.prototype.find.call(document.querySelectorAll('.tile'),function(x){return x.dataset.key==='k1';}).click()"); await pg.wait_for_timeout(1000)
        await open_np(pg)
        vis = await pg.evaluate("getComputedStyle(document.getElementById('npRenameBtn')).display")
        check(vis == 'none', f'no Rename for a directory station ({vis})')
        await icy(pg, 'Something Else')
        check(await np_name(pg) == 'KEXP', 'a directory station keeps its name')
        await pg.evaluate("document.getElementById('npBackBtn').click()"); await pg.wait_for_timeout(500)

        # Podcasts date headings: small grey capitals; section labels larger and bolder (build 164)
        st = await pg.evaluate("""(()=>{var g=document.getElementById('stationsGrid');
          var a=document.createElement('div'); a.className='podcast-date-heading'; a.textContent='Today';
          var b=document.createElement('div'); b.className='grid-section-label'; b.textContent='Continue Watching';
          g.appendChild(a); g.appendChild(b);
          var f=function(e){var c=getComputedStyle(e);return [parseFloat(c.fontSize),c.fontWeight,c.color,c.textTransform];};
          var r=[f(a),f(b)]; a.remove(); b.remove(); return r;})()""")
        check(st[0][3] == 'uppercase' and st[0][0] < 15 and st[1][0] >= 18 and st[1][1] == '800' and st[0][2] != st[1][2],
              f'date headings are small grey capitals, section labels big and bold {st}')
        check(not errs, f'no page errors {errs[:3]}')
        await b.close()
    print('ALL PASSED' if not fails else f'FAILED {fails}')
asyncio.run(main())
