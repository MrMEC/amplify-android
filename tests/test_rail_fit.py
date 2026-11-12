"""Build 588: the landscape rail never overlaps itself or the profile picture -- normal text, a big
Android text size (labels ~14px), with Cast showing, and on a shorter screen.
Run: python3 tests/test_rail_fit.py"""
import os
HERE = os.path.dirname(os.path.abspath(__file__))
src = open(os.path.join(HERE, 'test_live_channels.py')).read()
head = src[:src.index('\nasync def run(')]
head = head.replace("'/tmp/claude-0/t/srv-livech'", "'/tmp/claude-0/t/srv-railfit'").replace('PORT = 8862', 'PORT = 8881')
exec(head)
BIG = "(()=>{ var st=document.createElement('style'); st.textContent='.mobile-nav-btn{font-size:13.7px !important} .mobile-nav-btn svg{width:26px !important;height:26px !important}'; document.head.appendChild(st); })()"
CAST = "(()=>{ document.body.classList.add('cast-avail'); var c=document.querySelector('.sidebar-top .cast-btn'); if(c){ c.hidden=false; c.style.display='flex'; c.style.alignItems='center'; c.style.justifyContent='center'; c.style.borderRadius='50%'; } window.dispatchEvent(new Event('resize')); })()"
GEO = """(()=>{ var bs=Array.from(document.querySelectorAll('#mobileNav .mobile-nav-btn')).map(function(b){ var r=b.getBoundingClientRect(); var kids=Array.from(b.children).map(function(k){ var q=k.getBoundingClientRect(); return getComputedStyle(k).display==='none'?null:[q.top,q.bottom]; }).filter(Boolean); return {t:r.top,b:r.bottom,kids:kids, overflow: b.scrollHeight > b.clientHeight + 1}; });
  var ta=document.querySelector('.sidebar-top .top-actions').getBoundingClientRect();
  return {rf:document.documentElement.style.getPropertyValue('--rail-foot'), tah:ta.height, navpb:getComputedStyle(document.getElementById('mobileNav')).paddingBottom, btns:bs, foot:ta.top, footB:ta.bottom, vh:innerHeight, compact:document.body.classList.contains('rail-compact')}; })()"""
def ok(g):
    probs = []
    for i, b in enumerate(g['btns']):
        if b['overflow']: probs.append(f'button {i} content spills')
        for k in b['kids']:
            if k[0] < b['t'] - 0.5 or k[1] > b['b'] + 0.5: probs.append(f'button {i} content outside it')
        if i and b['t'] < g['btns'][i-1]['b'] - 0.5: probs.append(f'button {i} overlaps {i-1}')
    if g['btns'][-1]['b'] > g['foot'] - 2: probs.append('last button under the profile picture/Cast')
    if g['footB'] > g['vh'] + 0.5: probs.append('profile picture off screen')
    return probs
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
        for (h, big, cast) in [(373, False, False), (373, True, False), (373, True, True), (330, True, True), (300, True, True)]:
            label = f'h{h}{" big" if big else ""}{" cast" if cast else ""}'
            ctx = await b.new_context(viewport={'width': 892, 'height': h}, device_scale_factor=2, is_mobile=True, has_touch=True, color_scheme='dark')
            await ctx.add_init_script(MOCK); await ctx.add_init_script(AUTO_NOTICE); await ctx.add_init_script(SEED)
            await ctx.add_init_script("try{ localStorage.setItem('radioPlayerLtvAuto','0'); localStorage.setItem('radioPlayerLandscape', JSON.stringify({np:false,cf:true})); }catch(e){}")
            pg = await ctx.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
            await pg.route('**/*', route)
            await pg.goto(f'http://127.0.0.1:{PORT}/index.html'); await pg.wait_for_timeout(2500)
            if big: await pg.evaluate(BIG)
            if cast: await pg.evaluate(CAST)
            for nav in ['library', 'home', 'video']:
                await pg.evaluate(f"document.querySelector('.mobile-nav-btn[data-nav={nav}]').click()"); await pg.wait_for_timeout(1000)
                g = await pg.evaluate(GEO)
                pr = ok(g); print(label, nav, g['rf'], g['tah'], g['navpb'], g['foot'])
                check(not pr, f'[{label} {nav}] the rail fits, nothing on top of anything (compact={g["compact"]}) {pr}')
                if h >= 373: check(not g['compact'], f'[{label} {nav}] labels kept at a normal height')
                await pg.screenshot(path=f'{SHOTS}/rail-{label.replace(" ", "-")}-{nav}.png')
            check(not errs, f'[{label}] no page errors {errs}')
            await ctx.close()
        await b.close()
    print('FAILED' if fails else 'ALL PASSED', fails)
asyncio.run(main())
