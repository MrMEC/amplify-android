"""Build 184: on movie/TV pages (and album/artist pages, whose menu button floats) the header
slides up while scrolling down and comes back on the first scroll up; it always shows near the
top of the page. The Play/Resume pill has white text.
Run: python3 tests/test_header_autohide.py (screenshots in /tmp/claude-0/t/shots)"""
import asyncio, os, json
HERE = os.path.dirname(os.path.abspath(__file__))
src = open(os.path.join(HERE, 'test_video_library.py')).read()
head = src[:src.index('async def main()')]
head = head.replace("'/tmp/claude-0/t/srv-vlib'", "'/tmp/claude-0/t/srv-hdr'").replace('8780', '8819')
exec(head)
HDR = """(()=>{ var h=document.querySelector('.sidebar-top'), r=h.getBoundingClientRect();
  return {bottom:Math.round(r.bottom), hidden:document.body.classList.contains('hdr-hidden'), y:Math.round(scrollY)}; })()"""

async def scroll_to(pg, y, step):
    cur = await pg.evaluate('scrollY')
    while (step > 0 and cur < y) or (step < 0 and cur > y):
        cur += step
        await pg.evaluate(f'window.scrollTo(0, {cur})'); await pg.wait_for_timeout(30)
    await pg.wait_for_timeout(400)

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
        ctx = await b.new_context(viewport={'width': 390, 'height': 700}, device_scale_factor=2, is_mobile=True, has_touch=True, color_scheme='dark', locale='en-US')
        await ctx.add_init_script(MOCK); await ctx.add_init_script(EXT)
        pg = await ctx.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.route('**/*', route)
        await pg.goto('http://127.0.0.1:8819/index.html'); await pg.wait_for_timeout(2500)
        await pg.evaluate("document.querySelector('.mobile-nav-btn[data-nav=video]').click()"); await pg.wait_for_timeout(600)
        await tab(pg, 'movies')
        await pg.evaluate("document.getElementById('videoAddHeaderBtn').click()"); await pg.wait_for_timeout(2500)
        await tab(pg, 'shows')
        await pg.evaluate("Array.prototype.find.call(document.querySelectorAll('#stationsGrid .tile.vposter'),function(x){return x.querySelector('.tile-name').textContent==='Breaking Bad';}).click()"); await pg.wait_for_timeout(1000)
        # make the page long enough to scroll
        await pg.evaluate("(()=>{var d=document.createElement('div'); d.style.height='1500px'; d.style.gridColumn='1/-1'; document.getElementById('stationsGrid').appendChild(d);})()")
        col = await pg.evaluate("getComputedStyle(document.querySelector('.vd-play')).color")
        check(col == 'rgb(255, 255, 255)', f'Play/Resume pill text is white ({col})')
        h = await pg.evaluate(HDR)
        check(not h['hidden'] and h['bottom'] == 60, f'at the top the header shows {h}')
        await scroll_to(pg, 50, 10)
        h = await pg.evaluate(HDR)
        check(not h['hidden'], f'a little scroll near the top keeps it {h}')
        await scroll_to(pg, 400, 15)
        h = await pg.evaluate(HDR)
        check(h['hidden'] and h['bottom'] <= 0, f'scrolling down slides it out of view {h}')
        await pg.screenshot(path=f'{SHOTS}/hdr-hidden.png')
        await scroll_to(pg, 385, -5)
        h = await pg.evaluate(HDR)
        check(not h['hidden'] and h['bottom'] == 60, f'the first scroll up brings it back {h}')
        await pg.screenshot(path=f'{SHOTS}/hdr-back.png')
        await scroll_to(pg, 700, 15)
        check((await pg.evaluate(HDR))['hidden'], 'down again hides it again')
        # another page (Watch home) never hides it
        await pg.evaluate("document.querySelector('.mobile-nav-btn[data-nav=video]').click()"); await pg.wait_for_timeout(600)
        h = await pg.evaluate(HDR)
        check(not h['hidden'] and h['bottom'] == 60, f'leaving the page shows the header {h}')
        await pg.evaluate("(()=>{var d=document.createElement('div'); d.style.height='2000px'; d.style.gridColumn='1/-1'; document.getElementById('stationsGrid').appendChild(d);})()")
        await scroll_to(pg, 500, 15)
        h = await pg.evaluate(HDR)
        check(not h['hidden'] and h['bottom'] == 60, f'other pages keep the header while scrolling {h}')
        check(not errs, f'no page errors {errs[:3]}')
        await b.close()
    print('ALL PASSED' if not fails else f'FAILED {fails}')

asyncio.run(main())
