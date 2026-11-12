"""Rotation sequences: after every step, is the rail what's at the left edge, and what covers the middle?"""
import os, sys, json
HERE = os.path.dirname(os.path.abspath(__file__))
src = open(os.path.join(HERE, 'test_live_channels.py')).read()
head = src[:src.index('\nasync def run(')]
head = head.replace("'/tmp/claude-0/t/srv-livech'", "'/tmp/claude-0/t/srv-prot'").replace('PORT = 8862', 'PORT = 8880')
exec(head)
OUT = '/tmp/claude-0/t/prot'; os.makedirs(OUT, exist_ok=True)
NP = os.environ.get('NP', 'on')
PROBE = """(()=>{ function d(el){ if(!el) return 'none'; var s=el.tagName.toLowerCase()+(el.id?'#'+el.id:''); if(typeof el.className==='string'&&el.className) s+='.'+el.className.split(' ')[0]; return s; }
 var land = innerWidth>innerHeight; var l=document.elementFromPoint(30, innerHeight/2), m=document.elementFromPoint(innerWidth*0.6, innerHeight/2);
 var nav=document.getElementById('mobileNav'); var railOk = !!(nav && nav.contains(l));
 var np=document.getElementById('nowPlayingScreen');
 var cls=document.body.className.split(' ').filter(function(c){return /rotate|land|np-|ltv|cf-|video|home-view|album|artist/.test(c);}).join(' ');
 return {land:land, rail:railOk, left:d(l), mid:d(m), cls:cls, npDisp:np.style.display, npCls:np.className.replace('now-playing-screen','').trim().slice(0,80)}; })()"""
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
        ctx = await b.new_context(viewport={'width': 390, 'height': 844}, device_scale_factor=2, is_mobile=True, has_touch=True, locale='en-US', timezone_id='America/New_York', color_scheme='dark')
        await ctx.add_init_script(MOCK); await ctx.add_init_script(AUTO_NOTICE); await ctx.add_init_script(SEED)
        lp = '{"np":true,"cf":true}' if NP == 'on' else '{"np":false,"cf":true}'
        await ctx.add_init_script("try{ if(!sessionStorage.getItem('x')){ sessionStorage.setItem('x','1'); localStorage.setItem('radioPlayerLtvAuto','1'); if(window.__FLOW!==0) localStorage.setItem('radioPlayerCarousel', JSON.stringify({mode:'flow',size:'m',tilt:66,reflect:true,auto:false})); localStorage.setItem('radioPlayerLandscape', '" + lp + "'); } }catch(e){}")
        pg = await ctx.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.route('**/*', route)
        await pg.goto(f'http://127.0.0.1:{PORT}/index.html'); await pg.wait_for_timeout(3000)
        n = [0]
        async def snap(label):
            n[0] += 1
            r = await pg.evaluate(PROBE)
            bad = r['land'] and not r['rail']
            print(('BAD ' if bad else '    ') + f"{n[0]:02d} {label}: {json.dumps(r)}")
            await pg.screenshot(path=f'{OUT}/{NP}-{n[0]:02d}.png')
        async def land(): await pg.set_viewport_size({'width': 892, 'height': 373}); await pg.wait_for_timeout(1500)
        async def port(): await pg.set_viewport_size({'width': 390, 'height': 844}); await pg.wait_for_timeout(1500)
        async def nav(x): await pg.evaluate(f"document.querySelector('.mobile-nav-btn[data-nav={x}]').click()"); await pg.wait_for_timeout(1500)
        async def vtab(t): await pg.evaluate(f"document.querySelector('#stationsGrid > .watch-tabs .home-tab[data-vtab={t}]').click()"); await pg.wait_for_timeout(2500)
        await land(); await snap('home land')
        await port(); await land(); await snap('home land again')
        await nav('video'); await vtab('channels'); await snap('live tv land')
        await nav('home'); await snap('-> home (land)')
        await port(); await snap('home port'); await land(); await snap('home land after ltv')
        await nav('video'); await snap('watch land'); await port(); await snap('watch port'); await land(); await snap('watch land2')
        await nav('library'); await snap('library land')
        await port(); await nav('home'); await land(); await snap('home land 3')
        await nav('video'); await vtab('movies'); await snap('movies land'); await nav('home'); await snap('home from movies')
        print('errors', errs)
        await b.close()
asyncio.run(main())
