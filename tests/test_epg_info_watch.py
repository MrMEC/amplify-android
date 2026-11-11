"""Build 585: on an Archive.org channel, a later show in the guide has Watch Now (the film itself); a Pluto one doesn't.
Run: python3 tests/test_epg_info_watch.py"""
import sys as _nsys, os as _nos; _nsys.path.insert(0, _nos.path.dirname(_nos.path.abspath(__file__))); from notice_auto import AUTO_NOTICE
import os
HERE = os.path.dirname(os.path.abspath(__file__))
src = open(os.path.join(HERE, 'test_epg_grid.py')).read()
head = src[:src.index('\nasync def run(')]
head = head.replace("'/tmp/claude-0/t/srv-epg'", "'/tmp/claude-0/t/srv-info'").replace('PORT = 8846', 'PORT = 8876')
exec(head)
ARCH = """try{ var l=JSON.parse(localStorage.getItem('radioPlayerVideoChannels')||'[]');
  l.push({id:'archive:m:dis', name:'Disney Shorts', url:'amplify-archive:m:dis', logo:'', cats:['archive.org'], src:'archive',
    archive:{ items:[{id:'disone', title:'Disney One', creator:'Walt', year:'1950', video:true},{id:'distwo', title:'Disney Two', creator:'Walt', year:'1951', video:true}], order:'inorder' }});
  localStorage.setItem('radioPlayerVideoChannels', JSON.stringify(l)); localStorage.setItem('radioPlayerLtvAuto','0'); }catch(e){}"""
def md(i): return {'metadata': {'title': i}, 'files': [{'name': i + '.mp4', 'format': 'MPEG4', 'length': '1500', 'size': '1000', 'source': 'original'}]}
async def route2(r):
    u = urlparse(r.request.url)
    if u.netloc == 'archive.org' and u.path.startswith('/metadata/'):
        return await r.fulfill(status=200, content_type='application/json', headers={'Access-Control-Allow-Origin': '*'}, body=json.dumps(md(u.path.rsplit('/', 1)[1])))
    return await route(r)

INFO = "(()=>{ var o=document.getElementById('epgInfoOverlay'), w=document.getElementById('epgInfoWatch'); var x=w.getBoundingClientRect(); return {open:o.classList.contains('open'), watch:!w.hidden && x.height>0, show:document.getElementById('epgInfoShow').textContent}; })()"
def future(url): return "(()=>{ var r=document.querySelector('.epg-row[data-ch-url=\"%s\"]'); var b=r && r.querySelector('.epg-prog.info'); if(!b) return false; b.click(); return true; })()" % url

async def main():
    from playwright.async_api import async_playwright
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
        ctx = await b.new_context(viewport={'width': 390, 'height': 844}, device_scale_factor=2, is_mobile=True, has_touch=True, locale='en-US', timezone_id='America/New_York')
        await ctx.add_init_script(MOCK); await ctx.add_init_script(AUTO_NOTICE); await ctx.add_init_script(SEED); await ctx.add_init_script(ARCH)
        pg = await ctx.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.route('**/*', route2)
        await pg.goto(f'http://127.0.0.1:{PORT}/index.html'); await pg.wait_for_timeout(2500)
        await pg.evaluate("document.querySelector('.mobile-nav-btn[data-nav=video]').click()"); await pg.wait_for_timeout(2500)
        # an Archive.org channel
        check(await pg.evaluate(future('amplify-archive:m:dis')), 'a later show on the Archive.org channel')
        await pg.wait_for_timeout(500)
        i2 = await pg.evaluate(INFO)
        check(i2['open'] and i2['watch'], f'its details have Watch Now {i2}')
        await pg.evaluate("document.getElementById('epgInfoWatch').click()"); await pg.wait_for_timeout(3000)
        np2 = await pg.evaluate("[document.getElementById('nowPlayingScreen').style.display, document.getElementById('nowPlayingScreen').className, (document.querySelector('.np-name')||{}).textContent]")
        check(np2[0] == 'flex' and 'np-tv' not in np2[1] and i2['show'] in (np2[2] or '') , f'Watch Now plays that film itself {np2} {i2["show"]}')
        # a Pluto channel's later show: no Watch Now (nothing to play on demand)
        await pg.evaluate("document.querySelector('.mobile-nav-btn[data-nav=video]').click()"); await pg.wait_for_timeout(1500)
        if await pg.evaluate("document.getElementById('nowPlayingScreen').style.display") == 'flex':
            await pg.evaluate("document.getElementById('npBackBtn').click()"); await pg.wait_for_timeout(1200)
        pl = await pg.evaluate("(Array.from(document.querySelectorAll('.epg-row')).map(function(r){return r.dataset.chUrl;}).filter(function(u){return u.indexOf('pluto')>=0;})[0])")
        if await pg.evaluate(future(pl)):
            await pg.wait_for_timeout(500); i3 = await pg.evaluate(INFO)
            check(i3['open'] and not i3['watch'], f'a Pluto channel later show: no Watch Now {i3}')
        check(not errs, f'no page errors {errs}')
        await b.close()
    print('FAILED' if fails else 'ALL PASSED', fails)
asyncio.run(main())
