"""Build 582: an Archive.org channel playing has its outline in the guide like any other channel.
Run: python3 tests/test_epg_archive_outline.py"""
import sys as _nsys, os as _nos; _nsys.path.insert(0, _nos.path.dirname(_nos.path.abspath(__file__))); from notice_auto import AUTO_NOTICE
import os
HERE = os.path.dirname(os.path.abspath(__file__))
src = open(os.path.join(HERE, 'test_epg_grid.py')).read()
head = src[:src.index('\nasync def run(')]
head = head.replace("'/tmp/claude-0/t/srv-epg'", "'/tmp/claude-0/t/srv-arch'").replace('PORT = 8846', 'PORT = 8874')
exec(head)

ARCH = """try{ var l=JSON.parse(localStorage.getItem('radioPlayerVideoChannels')||'[]');
  l.push({id:'archive:m:dis', name:'Disney Shorts', url:'amplify-archive:m:dis', logo:'', cats:['archive.org'], src:'archive',
    archive:{ items:[{id:'disone', title:'Disney One', creator:'Walt', year:'1950', video:true}], order:'inorder' }});
  localStorage.setItem('radioPlayerVideoChannels', JSON.stringify(l)); localStorage.setItem('radioPlayerLtvAuto','0'); }catch(e){}"""
MD = {'metadata': {'title': 'Disney One', 'mediatype': 'movies'}, 'files': [{'name': 'one.mp4', 'format': 'MPEG4', 'length': '1500', 'size': '1000', 'source': 'original'}]}
async def route2(r):
    u = urlparse(r.request.url)
    if u.netloc == 'archive.org' and u.path.startswith('/metadata/'):
        return await r.fulfill(status=200, content_type='application/json', headers={'Access-Control-Allow-Origin': '*'}, body=json.dumps(MD))
    return await route(r)

OUT = """(()=>{ return Array.from(document.querySelectorAll('%s .epg-ch.playing')).map(function(c){ return c.closest('.epg-row').dataset.chUrl; }); })()"""

async def main():
    from playwright.async_api import async_playwright
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
        ctx = await b.new_context(viewport={'width': 390, 'height': 844}, device_scale_factor=2, is_mobile=True, has_touch=True, locale='en-US', timezone_id='America/New_York')
        await ctx.add_init_script(MOCK); await ctx.add_init_script(AUTO_NOTICE); await ctx.add_init_script(SEED); await ctx.add_init_script(ARCH)
        pg = await ctx.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.route('**/*', route2)
        await pg.goto(f'http://127.0.0.1:{PORT}/index.html'); await pg.wait_for_timeout(2500)
        await pg.evaluate("document.querySelector('.mobile-nav-btn[data-nav=video]').click()"); await pg.wait_for_timeout(2000)
        ok = await pg.evaluate("(()=>{ var r=document.querySelector('.epg-row[data-ch-url=\"amplify-archive:m:dis\"]'); if(!r) return false; var p=r.querySelector('.epg-prog')||r.querySelector('.epg-block'); (p||r.querySelector('.epg-ch')).click(); return !!p; })()")
        check(ok, 'the archive channel is in the guide')
        await pg.wait_for_timeout(3000)
        got = await pg.evaluate(OUT % '#npCollection')
        check(got == ['amplify-archive:m:dis'], f'the playing archive channel has the outline under the video {got}')
        await pg.screenshot(path=f'{SHOTS}/epg-archive-outline.png')
        check(not errs, f'no page errors {errs}')
        await b.close()
    print('FAILED' if fails else 'ALL PASSED', fails)
asyncio.run(main())
