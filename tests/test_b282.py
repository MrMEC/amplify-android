"""Build 282 (Mark): the floating video, its title bar and close button above everything, the header
and the tab bar included (build 280 kept it below the header; it could still be cut off at the bottom).
Run: python3 tests/test_b282.py (screenshots in /tmp/claude-0/t/shots)"""
import sys as _nsys, os as _nos; _nsys.path.insert(0, _nos.path.dirname(_nos.path.abspath(__file__)))
src = open(_nos.path.join(_nos.path.dirname(_nos.path.abspath(__file__)), 'test_live_channels_editor.py')).read()
src = src[:src.index('async def run2(')].replace('PORT = 8863', 'PORT = 8880').replace("srv-livech2'", "srv-b282'")
exec(src)
import sys
HIT = """(()=>{ const v = document.getElementById('videoMini'), r = v.getBoundingClientRect(), c = document.getElementById('videoMiniClose').getBoundingClientRect();
  const pts = [[r.left + r.width/2, r.top + 5], [r.left + r.width/2, r.top + r.height/2], [c.left + c.width/2, c.top + c.height/2], [r.left + 20, r.bottom - 5]];
  return { top: Math.round(r.top), bottom: Math.round(r.bottom), vh: innerHeight, hits: pts.map(p => v.contains(document.elementFromPoint(p[0], p[1]))),
    hdr: Math.round(document.querySelector('.sidebar-top').getBoundingClientRect().bottom), nav: Math.round(document.getElementById('mobileNav').getBoundingClientRect().top) }; })()"""
async def drag(pg, dy):
    bar = await pg.evaluate("(()=>{ const r = document.getElementById('videoMiniTitle').getBoundingClientRect(); return [r.left + 10, r.top + r.height/2]; })()")
    await pg.mouse.move(bar[0], bar[1]); await pg.mouse.down()
    steps = 12
    for i in range(1, steps + 1): await pg.mouse.move(bar[0], bar[1] + dy * i / steps)
    await pg.mouse.up(); await pg.wait_for_timeout(300)
async def main():
    async with async_playwright() as p:
        for width in (390, 360):
            T = f'[{width}]'
            b = await p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
            ctx = await b.new_context(viewport={'width': width, 'height': 844}, device_scale_factor=3, is_mobile=True, has_touch=True, color_scheme='dark')
            await ctx.add_init_script(MOCK); await ctx.add_init_script(AUTO_NOTICE); await ctx.add_init_script(SEED)
            pg = await ctx.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
            await pg.route('**/*', route)
            await pg.goto(f'http://127.0.0.1:{PORT}/index.html'); await pg.wait_for_timeout(2500)
            await pg.evaluate("document.querySelector('.mobile-nav-btn[data-nav=podcasts]').click()"); await pg.wait_for_timeout(800)
            await pg.evaluate("(()=>{ const v = document.getElementById('videoMini'); v.hidden = false; v.style.width='240px'; v.style.left = '60px'; v.style.top = '400px'; v.style.right='auto'; v.style.bottom='auto'; document.getElementById('videoMiniTitle').textContent = 'ABC'; })()")
            await drag(pg, -600)
            h = await pg.evaluate(HIT); print(T, 'top', h)
            check(h['top'] < h['hdr'] and all(h['hits']), f'{T} dragged up over the header: all of it on top, the header under it {h}')
            await pg.screenshot(path=f'{SHOTS}/b282-top-{width}.png')
            await drag(pg, 900)
            h = await pg.evaluate(HIT); print(T, 'bottom', h)
            check(h['bottom'] > h['nav'] and h['bottom'] <= h['vh'] and all(h['hits']), f'{T} dragged down over the tab bar: title bar and close button on top, still on screen {h}')
            await pg.screenshot(path=f'{SHOTS}/b282-bottom-{width}.png')
            # a dialog still covers it
            z = await pg.evaluate("[+getComputedStyle(document.getElementById('videoMini')).zIndex, +getComputedStyle(document.getElementById('confirmOverlay')).zIndex]")
            check(z[0] < z[1], f'{T} dialogs still open over it {z}')
            check(not errs, f'{T} no page errors {errs[:2]}')
            await b.close()
    print('ALL PASSED' if not fails else f'{fails} FAILED')
    sys.exit(1 if fails else 0)
asyncio.run(main())
