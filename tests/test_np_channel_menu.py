"""Build 191: under a playing channel, the More menu is readable on the light theme (it was the
dark panel with the white screen's dark text on it), and the More button sits level with the
channel name. Pluto channel and a link channel; light and dark themes; text 1.35x at 412 and 360.
Run: python3 tests/test_np_channel_menu.py (screenshots in /tmp/claude-0/t/shots)"""
import os, json, asyncio
HERE = os.path.dirname(os.path.abspath(__file__))
src = open(os.path.join(HERE, 'test_pluto.py')).read()
exec(src.split('async def main')[0].replace('8807', '8822').replace('srv-pluto', 'srv-npmenu'))
URL = f'https://{HOST1}/stitch/hls/channel/5421f71da6af422839419cb3/master.m3u8'
CH = [{'id': 'pluto:5421f71da6af422839419cb3', 'name': "Three's Company", 'url': URL, 'logo': '', 'country': '', 'cats': ['Comedy'], 'catNames': ['Comedy'], 'src': 'pluto', 'addedAt': 1},
      {'id': 'link:1', 'name': 'Alpha TV', 'url': 'http://a.example/l.m3u8', 'logo': '', 'country': '', 'cats': [], 'catNames': [], 'src': 'link', 'addedAt': 2}]
def lum(rgb):
    v = [int(x) for x in rgb[rgb.index('(') + 1:rgb.index(')')].split(',')[:3]]
    return 0.2126 * v[0] + 0.7152 * v[1] + 0.0722 * v[2]
async def run(p, theme, w, big):
    b = await p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
    ctx = await b.new_context(viewport={'width': w, 'height': 900}, device_scale_factor=2, is_mobile=True, has_touch=True, color_scheme=theme)
    await ctx.add_init_script(MOCK)
    await ctx.add_init_script("localStorage.setItem('radioPlayerVideoChannels', %s); localStorage.setItem('radioPlayerTheme','%s');" % (repr(json.dumps(CH)), theme))
    pg = await ctx.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
    await pg.route('**/*', route)
    await pg.goto('http://127.0.0.1:8822/index.html'); await pg.wait_for_timeout(2500)
    if big: await pg.add_style_tag(content='.np-name,.np-menu-item,.tile-name{font-size:calc(1em*1.35) !important}')
    tag = f'{theme}-{w}' + ('-big' if big else '')
    for name in ["Three's Company", 'Alpha TV']:
        await pg.evaluate("document.querySelector('.mobile-nav-btn[data-nav=video]').click()"); await pg.wait_for_timeout(800)
        await pg.evaluate("(n)=>Array.prototype.find.call(document.querySelectorAll('#stationsGrid .tile-row'), function(r){ return r.textContent.indexOf(n) !== -1; }).click()", name); await pg.wait_for_timeout(2000)
        g = await pg.evaluate("""(()=>{ var n=document.getElementById('npName').getBoundingClientRect(), b=document.getElementById('npMenuBtn').getBoundingClientRect(); return [(n.top+n.bottom)/2, (b.top+b.bottom)/2]; })()""")
        check(abs(g[0] - g[1]) <= 2, f'{tag} {name}: More is level with the name ({g[0]:.1f} vs {g[1]:.1f})')
        await pg.evaluate("document.getElementById('npMenuBtn').click()"); await pg.wait_for_timeout(500)
        c = await pg.evaluate("""(()=>{ var m=document.getElementById('npMenu'); var items=Array.prototype.filter.call(m.querySelectorAll('.np-menu-item'), function(i){ return i.offsetParent; });
          var r=m.getBoundingClientRect(); return {bg:getComputedStyle(m).backgroundColor, items:items.map(function(i){ return [i.textContent.trim(), getComputedStyle(i).color, i.classList.contains('danger')]; }), right:r.right, w:innerWidth}; })()""")
        bgl = lum(c['bg'])
        bad = [i for i in c['items'] if abs(lum(i[1]) - bgl) < (60 if i[2] else 110)]
        check(not bad and c['right'] <= c['w'], f'{tag} {name}: every menu item readable on the menu ({c["bg"]}) {bad}')
        await pg.screenshot(path=f'{SHOTS}/npmenu-{tag}-{name[:5].replace(" ", "")}.png')
        await pg.evaluate("document.body.click()"); await pg.wait_for_timeout(300)
        await pg.evaluate("document.getElementById('npBackBtn') && document.getElementById('npBackBtn').click()"); await pg.wait_for_timeout(800)
    check(not errs, f'{tag}: no page errors {errs[:3]}')
    await b.close()
async def main():
    async with async_playwright() as p:
        await run(p, 'light', 412, False)
        await run(p, 'dark', 412, False)
        await run(p, 'light', 412, True)
        await run(p, 'light', 360, True)
    print('ALL PASSED' if not fails else f'FAILED {fails}')
asyncio.run(main())
