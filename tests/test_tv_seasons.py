"""TV show pages: the season tabs scroll sideways, show and episode titles get two lines;
channel logos sit on dark gray instead of a generated colour wash (build 155).
Run: python3 tests/test_tv_seasons.py (screenshots in /tmp/claude-0/t/shots)"""
import asyncio, os, json
HERE = os.path.dirname(os.path.abspath(__file__))
src = open(os.path.join(HERE, 'test_video_library.py')).read()
head = src[:src.index('async def main()')]
head = head.replace("'/tmp/claude-0/t/srv-vlib'", "'/tmp/claude-0/t/srv-tvs'").replace('8780', '8816')
LONG = 'The Marvelous Adventures of the Extraordinarily Long Titled Show'
extra = []
for sn in range(1, 13):
    extra.append("f('Videos/TV/%s/Season %d/%s.S%02dE01.The.Beginning.of.a.Rather.Long.Episode.Name.That.Goes.On.mkv', lm=7)" % (LONG, sn, LONG.replace(' ', '.'), sn))
head = head.replace("FILES = [", "FILES = [\n  " + ",\n  ".join(extra) + ",")
exec(head)
CH = [{'id': 'iptv:ABCNews.us', 'name': 'ABC News Live', 'url': 'https://abc.example/live1080.m3u8', 'logo': '', 'country': 'US', 'cats': ['news'], 'catNames': ['News'], 'src': 'iptv', 'addedAt': 1}]

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
        ctx = await b.new_context(viewport={'width': 390, 'height': 844}, device_scale_factor=2, is_mobile=True, has_touch=True, color_scheme='dark', locale='en-US')
        await ctx.add_init_script(MOCK)
        await ctx.add_init_script(EXT)
        await ctx.add_init_script("localStorage.setItem('radioPlayerVideoChannels', %s)" % repr(json.dumps(CH)))
        pg = await ctx.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.route('**/*', route)
        await pg.goto('http://127.0.0.1:8816/index.html'); await pg.wait_for_timeout(2500)
        await pg.evaluate("document.querySelector('.mobile-nav-btn[data-nav=video]').click()"); await pg.wait_for_timeout(700)
        bg = await pg.evaluate("""Array.prototype.map.call(document.querySelectorAll('#stationsGrid .tile.ch-item .tile-art'), function(a){
            return [a.classList.contains('channel-art'), getComputedStyle(a).backgroundImage, getComputedStyle(a).backgroundColor];})""")
        check(bg and all(x[0] and x[1] == 'none' and x[2] == 'rgb(43, 44, 49)' for x in bg), f'channel logos sit on dark gray {bg}')
        await pg.screenshot(path=f'{SHOTS}/tvs-channels.png')
        await tab(pg, 'movies')
        await pg.evaluate("document.getElementById('videoAddHeaderBtn').click()"); await pg.wait_for_timeout(2500)
        await tab(pg, 'shows')
        nm = await pg.evaluate("""(t)=>{var n=Array.prototype.find.call(document.querySelectorAll('#stationsGrid .tile.vposter .tile-name'),function(x){return x.textContent===t;});
            var lh=parseFloat(getComputedStyle(n).lineHeight); return [Math.round(n.getBoundingClientRect().height/lh), getComputedStyle(n).whiteSpace];}""", LONG)
        check(nm[0] == 2 and nm[1] == 'normal', f'a long show name takes two lines in the grid {nm}')
        await pg.screenshot(path=f'{SHOTS}/tvs-grid.png')
        await pg.evaluate("(t)=>Array.prototype.find.call(document.querySelectorAll('#stationsGrid .tile.vposter'),function(x){return x.querySelector('.tile-name').textContent===t;}).click()", LONG); await pg.wait_for_timeout(800)
        tb = await pg.evaluate("""(()=>{var t=document.querySelector('.vd-seasons'); var r=t.getBoundingClientRect();
            return {n:t.children.length, sw:t.scrollWidth, cw:t.clientWidth, right:Math.round(r.right), ox:getComputedStyle(t).overflowX};})()""")
        check(tb['n'] == 12 and tb['sw'] > tb['cw'] and tb['ox'] == 'auto' and tb['right'] <= 390, f'season tabs overflow inside a scroller {tb}')
        # a finger swipe moves them
        box = await pg.evaluate("(()=>{var r=document.querySelector('.vd-seasons').getBoundingClientRect(); return [r.left+r.width*0.8, r.top+r.height/2];})()")
        cdp = await ctx.new_cdp_session(pg)
        x, y = box
        await cdp.send('Input.dispatchTouchEvent', {'type': 'touchStart', 'touchPoints': [{'x': x, 'y': y}]})
        for i in range(1, 11):
            await cdp.send('Input.dispatchTouchEvent', {'type': 'touchMove', 'touchPoints': [{'x': x - i * 25, 'y': y}]})
            await pg.wait_for_timeout(16)
        await cdp.send('Input.dispatchTouchEvent', {'type': 'touchEnd', 'touchPoints': []})
        await pg.wait_for_timeout(500)
        sl = await pg.evaluate("document.querySelector('.vd-seasons').scrollLeft")
        check(sl > 50, f'swiping scrolls the season tabs ({sl})')
        await pg.evaluate("Array.prototype.find.call(document.querySelectorAll('.vd-seasons .home-tab'),function(b){return b.textContent==='Season 11';}).click()"); await pg.wait_for_timeout(500)
        act = await pg.evaluate("[document.querySelector('.vd-seasons .home-tab.active').textContent, document.querySelector('.vd-seasons').scrollLeft]")
        check(act[0] == 'Season 11' and act[1] > 200, f'a far season can be picked and stays in view {act}')
        await pg.screenshot(path=f'{SHOTS}/tvs-show.png')
        ttl = await pg.evaluate("(()=>{var n=document.querySelector('.vd-title'); return Math.round(n.getBoundingClientRect().height/parseFloat(getComputedStyle(n).lineHeight));})()")
        check(ttl <= 3, f'the page title is at most three lines ({ttl})')
        ep = await pg.evaluate("(()=>{var n=document.querySelector('.vep-title'); return Math.round(n.getBoundingClientRect().height/parseFloat(getComputedStyle(n).lineHeight));})()")
        check(ep in (2, 3), f'a long episode title wraps, up to three lines ({ep})')
        check(not errs, f'no page errors {errs}')
        await b.close()
    print('ALL PASSED' if not fails else f'FAILED {fails}')

asyncio.run(main())
