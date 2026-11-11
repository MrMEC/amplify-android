"""Build 583: Add or Manage Channels under the Live TV guide on the video screen.
Run: python3 tests/test_ltv_manage.py"""
import sys as _nsys, os as _nos; _nsys.path.insert(0, _nos.path.dirname(_nos.path.abspath(__file__))); from notice_auto import AUTO_NOTICE
import os
HERE = os.path.dirname(os.path.abspath(__file__))
src = open(os.path.join(HERE, 'test_epg_grid.py')).read()
head = src[:src.index('\nasync def run(')]
head = head.replace("'/tmp/claude-0/t/srv-epg'", "'/tmp/claude-0/t/srv-manage'").replace('PORT = 8846', 'PORT = 8875')
exec(head)

async def go(p, vw, vh, theme, label):
    T = f'[{label} {theme}]'
    b = await p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
    ctx = await b.new_context(viewport={'width': vw, 'height': vh}, device_scale_factor=2, is_mobile=True, has_touch=True, color_scheme=theme, locale='en-US', timezone_id='America/New_York')
    await ctx.add_init_script(MOCK); await ctx.add_init_script(AUTO_NOTICE); await ctx.add_init_script(SEED)
    await ctx.add_init_script("try{ localStorage.setItem('radioPlayerLtvAuto','1'); localStorage.setItem('radioPlayerTheme','%s'); }catch(e){}" % theme)
    pg = await ctx.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
    await pg.route('**/*', route)
    await pg.goto(f'http://127.0.0.1:{PORT}/index.html'); await pg.wait_for_timeout(2500)
    await pg.evaluate("document.querySelector('.mobile-nav-btn[data-nav=video]').click()"); await pg.wait_for_timeout(3000)
    await pg.evaluate("document.getElementById('npManageChannels').scrollIntoView({block:'end'})"); await pg.wait_for_timeout(500)
    r = await pg.evaluate("""(()=>{ var b=document.getElementById('npManageChannels'); if(!b) return null; var x=b.getBoundingClientRect(), g=document.querySelector('#npCollection .epg').getBoundingClientRect();
      var nav=document.querySelector('.mobile-nav'), nb=nav&&nav.getBoundingClientRect(), nt=(nav&&getComputedStyle(nav).display!=='none'&&nb.height<120)?nb.top:innerHeight;
      var hit=document.elementFromPoint(x.left+x.width/2, x.top+x.height/2);
      return {t:Math.round(x.top), b:Math.round(x.bottom), w:Math.round(x.width), h:Math.round(x.height), gb:Math.round(g.bottom), nt:Math.round(nt), text:b.textContent, hit: !!(hit && b.contains(hit))}; })()""")
    check(r and r['text'] == 'Add or Manage Channels' and r['h'] >= 44 and r['t'] >= r['gb'] and r['b'] <= r['nt'] + 1 and r['hit'], f'{T} the button sits under the guide, on screen and tappable {r}')
    await pg.screenshot(path=f'{SHOTS}/ltv-manage-{label}-{theme}.png')
    await pg.evaluate("document.getElementById('npManageChannels').click()"); await pg.wait_for_timeout(400)
    await pg.wait_for_timeout(400)
    m = await pg.evaluate("""(()=>{ var m=document.getElementById('ltvManageSheet'); if(!m || !m.classList.contains('open')) return null; var x=m.getBoundingClientRect(); var items=Array.from(m.querySelectorAll('.np-menu-item')).map(function(e){return e.textContent;});
      var hit=document.elementFromPoint(x.left+x.width/2, x.top+30); return {t:Math.round(x.top), b:Math.round(x.bottom), l:Math.round(x.left), r:Math.round(x.right), items:items, title:m.querySelector('.artist-menu-title').textContent, top: !!(hit && m.contains(hit))}; })()""")
    check(m and m['items'][:2] == ['Add Channels', 'Arrange Channels'] and m['top'] and m['l'] == 0 and m['r'] == vw and abs(m['b'] - vh) <= 1 and m['t'] >= 0, f'{T} the sheet slides up full width from the bottom, on top {m}')
    await pg.screenshot(path=f'{SHOTS}/ltv-manage-menu-{label}-{theme}.png')
    await pg.evaluate("Array.from(document.querySelectorAll('#ltvManageSheet .np-menu-item')).find(function(e){return e.textContent==='Add Channels';}).click()"); await pg.wait_for_timeout(1500)
    a = await pg.evaluate("[document.getElementById('nowPlayingScreen').style.display, document.body.classList.contains('ltv-dock'), (document.getElementById('stationsHeading')||{}).textContent]")
    check(a[0] != 'flex' and not a[1] and a[2] == 'Add Channels', f'{T} Add Channels opens its page {a}')
    await pg.screenshot(path=f'{SHOTS}/ltv-manage-add-{label}-{theme}.png')
    # a logo in the guide under the video opens that channel's menu
    await pg.reload(); await pg.wait_for_timeout(2500)
    await pg.evaluate("document.querySelector('.mobile-nav-btn[data-nav=video]').click()"); await pg.wait_for_timeout(3000)
    before = await pg.evaluate("(document.querySelector('#npCollection .epg-ch.playing')||{closest:function(){return {dataset:{}};}}).closest('.epg-row').dataset.chUrl")
    await pg.evaluate("document.querySelectorAll('#npCollection .epg-ch')[2].click()"); await pg.wait_for_timeout(600)
    sh = await pg.evaluate("(()=>{ var o=document.getElementById('chSheetOverlay'); var items=Array.from(document.querySelectorAll('#chSheetItems .ch-sheet-item')).map(function(e){return e.textContent;}); var it=document.querySelector('#chSheetItems .ch-sheet-item'); var x=it?it.getBoundingClientRect():null; var hit=x?document.elementFromPoint(x.left+x.width/2,x.top+x.height/2):null; return {open:o.classList.contains('open'), items:items, top:!!(hit&&it.contains(hit)), name:document.getElementById('chSheetName').textContent}; })()")
    after = await pg.evaluate("(document.querySelector('#npCollection .epg-ch.playing')||{closest:function(){return {dataset:{}};}}).closest('.epg-row').dataset.chUrl")
    check(sh['open'] and sh['top'] and 'Watch Now' in sh['items'] and 'Remove from Live TV' in sh['items'] and before == after, f'{T} tapping a logo opens its menu (and doesn\'t change channel) {sh} {before} {after}')
    await pg.screenshot(path=f'{SHOTS}/ltv-chsheet-{label}-{theme}.png')
    await pg.evaluate("Array.from(document.querySelectorAll('#chSheetItems .ch-sheet-item')).find(function(e){return e.textContent==='Watch Now';}).click()"); await pg.wait_for_timeout(1500)
    now = await pg.evaluate("(document.querySelector('#npCollection .epg-ch.playing')||{closest:function(){return {dataset:{}};}}).closest('.epg-row').dataset.chUrl")
    want = await pg.evaluate("document.querySelectorAll('#npCollection .epg-row')[2].dataset.chUrl")
    check(now == want and await pg.evaluate("document.body.classList.contains('ltv-dock')"), f'{T} Watch Now plays it, still on Live TV {now} {want}')
    check(not errs, f'{T} no page errors {errs}')
    await b.close()

async def main():
    from playwright.async_api import async_playwright
    async with async_playwright() as p:
        for th in ('dark', 'light'):
            await go(p, 390, 844, th, 'portrait')
            await go(p, 844, 390, th, 'landscape')
    print('FAILED' if fails else 'ALL PASSED', fails)
asyncio.run(main())
