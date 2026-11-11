"""Build 580: the channel playing is on screen when the Live TV guide comes up (many channels,
the remembered one far down the list), upright and sideways.
Run: python3 tests/test_live_tv_reveal.py"""
import sys as _nsys, os as _nos; _nsys.path.insert(0, _nos.path.dirname(_nos.path.abspath(__file__))); from notice_auto import AUTO_NOTICE
import os
HERE = os.path.dirname(os.path.abspath(__file__))
src = open(os.path.join(HERE, 'test_epg_grid.py')).read()
head = src[:src.index('\nasync def run(')]
head = head.replace("'/tmp/claude-0/t/srv-epg'", "'/tmp/claude-0/t/srv-reveal'").replace('PORT = 8846', 'PORT = 8873')
exec(head)

MORE = """try{ var l=JSON.parse(localStorage.getItem('radioPlayerVideoChannels')||'[]');
  for(var i=1;i<=30;i++) l.push({id:'x'+i,name:'Extra '+i,url:'http://extra.example/'+i+'.m3u8',logo:'',cats:[],src:'link'});
  localStorage.setItem('radioPlayerVideoChannels', JSON.stringify(l));
  localStorage.setItem('radioPlayerLtvLastCh', 'http://extra.example/25.m3u8'); localStorage.setItem('radioPlayerLtvAuto','1'); }catch(e){}"""
VIS = """(()=>{ var c=document.querySelector('#npCollection .epg-ch.playing'); if(!c) return {none:true};
  var r=c.closest('.epg-row').getBoundingClientRect(), h=document.querySelector('#npCollection .epg-head').getBoundingClientRect(), n=document.querySelector('.mobile-nav');
  var nb = n && getComputedStyle(n).display!=='none' && n.offsetParent ? n.getBoundingClientRect().top : innerHeight;
  return {url:c.closest('.epg-row').dataset.chUrl, top:Math.round(r.top), bottom:Math.round(r.bottom), headBottom:Math.round(h.bottom), limit:Math.round(Math.min(nb, innerHeight))}; })()"""

async def go(p, vw, vh, label):
    b = await p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
    ctx = await b.new_context(viewport={'width': vw, 'height': vh}, device_scale_factor=2, is_mobile=True, has_touch=True, locale='en-US', timezone_id='America/New_York')
    await ctx.add_init_script(MOCK); await ctx.add_init_script(AUTO_NOTICE); await ctx.add_init_script(SEED); await ctx.add_init_script(MORE)
    pg = await ctx.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
    await pg.route('**/*', route)
    await pg.goto(f'http://127.0.0.1:{PORT}/index.html'); await pg.wait_for_timeout(2500)
    await pg.evaluate("document.querySelector('.mobile-nav-btn[data-nav=video]') ? document.querySelector('.mobile-nav-btn[data-nav=video]').click() : (window.showVideoPage && showVideoPage())"); await pg.wait_for_timeout(3000)
    v = await pg.evaluate(VIS)
    check(v.get('url') == 'http://extra.example/25.m3u8', f'{label}: the remembered channel plays {v}')
    check(not v.get('none') and v['top'] >= v['headBottom'] - 1 and v['bottom'] <= v['limit'] + 1, f'{label}: its row is on screen {v}')
    await pg.wait_for_timeout(800); await pg.screenshot(path=f'{SHOTS}/ltv-reveal-{label}.png')
    check(not errs, f'{label}: no page errors {errs}')
    await b.close()

async def main():
    from playwright.async_api import async_playwright
    async with async_playwright() as p:
        await go(p, 390, 844, 'portrait')
        await go(p, 844, 390, 'landscape')
    print('FAILED' if fails else 'ALL PASSED', fails)
asyncio.run(main())
