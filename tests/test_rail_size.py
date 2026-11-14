"""Build 614: bigger rail touch targets sideways. Run: python3 tests/test_rail_size.py"""
import os, asyncio
HERE = os.path.dirname(os.path.abspath(__file__))
src = open(os.path.join(HERE, 'test_cf_after_video.py')).read()
head = src[:src.index('fails = []')].replace("'/tmp/claude-0/t/srv_cfv'", "'/tmp/claude-0/t/srv_614'").replace('8848', '8862')
exec(head)
fails = []
def check(c, m):
    print(('PASS ' if c else 'FAIL ') + m)
    if not c: fails.append(m)
async def ev(pg, js): return await pg.evaluate('(js) => window.__h.ev(js)', js)
SH = '/tmp/claude-0/t/shots'
M = """(()=>{ var bs=[].slice.call(document.querySelectorAll('.mobile-nav .mobile-nav-btn')).filter(b=>b.offsetParent); var r=bs.map(b=>{var q=b.getBoundingClientRect(), s=b.querySelector('svg'); var sr=s?s.getBoundingClientRect():{width:0}; return [Math.round(q.left),Math.round(q.top),Math.round(q.width),Math.round(q.height),Math.round(sr.width)];}); var a=document.querySelector('.sidebar-top .hamburger-btn').getBoundingClientRect(); var n=document.getElementById('mobileNav').getBoundingClientRect(); return {btns:r, av:[Math.round(a.top),Math.round(a.bottom),Math.round(a.width)], rail:Math.round(n.width), lay:Math.round(document.querySelector('.layout').getBoundingClientRect().left)}; })()"""
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
        for theme in ('dark', 'light'):
            ctx = await b.new_context(viewport={'width': 678, 'height': 297}, screen={'width': 678, 'height': 297}, device_scale_factor=3.3, is_mobile=True, has_touch=True, color_scheme=theme)
            await ctx.add_init_script(MOCK); await ctx.add_init_script(AUTO_NOTICE)
            await ctx.add_init_script("localStorage.setItem('radioPlayerTheme','%s')" % theme)
            pg = await ctx.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
            await pg.goto(f'http://127.0.0.1:{PORT}/index.html'); await pg.wait_for_timeout(2500)
            T='[%s]'%theme
            for name, js in (('home', "1"), ('library', "runLibrarySection('artists'); 1")):
                await ev(pg, js); await pg.wait_for_timeout(800)
                m = await pg.evaluate(M); print(T, name, m)
                await pg.screenshot(path=f'{SH}/614-rail-{name}-{theme}.png')
                bt = m['btns']
                check(len(bt)==5 and all(x[3]>=44 and x[2]>=60 for x in bt), T+name+' buttons big %s' % bt)
                check(bt[-1][1]+bt[-1][3] <= m['av'][0]-4, T+name+' buttons clear of the profile picture')
                check(all(x[0]>=0 and x[0]+x[2]<=m['rail'] for x in bt), T+name+' buttons inside the rail')
            # portrait unaffected
            await pg.set_viewport_size({'width': 327, 'height': 700}); await pg.wait_for_timeout(1000)
            pm = await pg.evaluate("(()=>{var b=document.querySelector('.mobile-nav .mobile-nav-btn').getBoundingClientRect(); return [Math.round(b.width),Math.round(b.height)];})()")
            print(T,'portrait', pm)
            await pg.screenshot(path=f'{SH}/614-port-{theme}.png')
            check(not errs, T+' no errors %s'%errs[:2])
            await ctx.close()
        await b.close()
    print('ALL PASSED' if not fails else 'FAILED %s' % fails)
asyncio.run(main())
