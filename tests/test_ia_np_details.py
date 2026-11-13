"""Build 601: an archive.org video's Now Playing works like your own movies and episodes: its own picture
(never the last channel's), the show / hide details arrow beside the list heading, the same list rows.
At Mark's phone size (327 CSS px wide, dpr 3.3). Run: python3 tests/test_ia_np_details.py"""
import os, asyncio
HERE = os.path.dirname(os.path.abspath(__file__))
src = open(os.path.join(HERE, 'test_archive.py')).read()
head = src[:src.index('async def main():')].replace("'/tmp/claude-0/t/srv-arch'", "'/tmp/claude-0/t/srv-iad'").replace('8828', '8853')
exec(head)
DOCS[:] = [{'identifier': 'house1977', 'title': 'House (1977)', 'mediatype': 'movies', 'creator': 'Nobuhiko Obayashi', 'year': '1977'},
           {'identifier': 'houseilive', 'title': 'The House I Live In', 'mediatype': 'movies', 'creator': 'Eugene Jarecki', 'year': '2012'},
           {'identifier': 'houseilive45', 'title': 'The House I Live In', 'mediatype': 'movies', 'creator': 'Frank Ross, Mervyn LeRoy', 'year': '1945'}]
for d in DOCS: META[d['identifier']] = {'files': [{'name': d['identifier'] + '.mp4', 'format': 'h.264', 'size': '9000', 'length': '600'}]}
fails2 = []
def ck(ok, msg):
    print(('PASS ' if ok else 'FAIL ') + msg)
    if not ok: fails2.append(msg)
ST = """(()=>{ var n=document.getElementById('nowPlayingScreen'), th=document.getElementById('npEpThumb'), img=th.querySelector('img'), tg=document.getElementById('npFootToggle'), f=n.querySelector('.np-hero-foot');
  var rows=document.querySelectorAll('#npCollectionGrid > *');
  return {ia:n.classList.contains('np-ia'), ch:n.classList.contains('np-channel'), thumb:th.hidden?null:img.getAttribute('src'), toggle:getComputedStyle(tg).display, footH:Math.round(f.getBoundingClientRect().height),
    heading:document.getElementById('npCollectionHeading').textContent, rows:Array.prototype.map.call(rows,function(r){return r.className;}), name:document.getElementById('npName').textContent}; })()"""
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
        for theme in ('dark', 'light'):
            ctx = await b.new_context(viewport={'width': 327, 'height': 700}, device_scale_factor=3.3, is_mobile=True, has_touch=True, color_scheme=theme)
            await ctx.add_init_script("localStorage.setItem('radioPlayerTheme','%s'); localStorage.setItem('radioPlayerNpDetailsHidden','0')" % theme)
            pg = await ctx.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
            await pg.route('**/*', route)
            await pg.goto('http://127.0.0.1:8853/index.html'); await pg.wait_for_timeout(2500)
            T = '[%s]' % theme
            # the last channel's picture still in the details (as after watching a channel)
            await pg.evaluate("var th=document.getElementById('npEpThumb'); th.hidden=false; th.querySelector('img').src='https://example.com/pluto-logo.png';")
            await sheet_search(pg, 'house')
            await click_tab(pg, 'Archive')
            await pg.evaluate("document.querySelector('#stationsGrid .archive-result-row').click()"); await pg.wait_for_timeout(2000)
            s = await pg.evaluate(ST)
            await pg.screenshot(path=SHOTS + '/iad-open-%s.png' % theme)
            ck(s['ia'] and s['ch'] and s['name'].startswith('House'), T + ' archive video Now Playing %s' % s)
            ck(s['thumb'] == 'https://archive.org/services/img/house1977', T + ' its own picture, not the last channel\'s %s' % s['thumb'])
            ck(s['toggle'] == 'flex' and s['footH'] > 40, T + ' show/hide details arrow, details shown %s' % s)
            ck(s['heading'] == 'More Videos' and len(s['rows']) == 2 and all('vep-row' in r for r in s['rows']), T + ' rows like More Movies %s' % s['rows'])
            await pg.evaluate("document.getElementById('npFootToggle').click()"); await pg.wait_for_timeout(700)
            s2 = await pg.evaluate(ST)
            await pg.screenshot(path=SHOTS + '/iad-collapsed-%s.png' % theme)
            ck(s2['footH'] == 0, T + ' details collapse %s' % s2['footH'])
            await pg.evaluate("document.getElementById('npFootToggle').click()"); await pg.wait_for_timeout(700)
            s3 = await pg.evaluate(ST)
            ck(s3['footH'] == s['footH'], T + ' and come back %s' % s3['footH'])
            # next video from the list: its own picture
            await pg.evaluate("document.querySelector('#npCollectionGrid .vep-row').click()"); await pg.wait_for_timeout(2000)
            s4 = await pg.evaluate(ST)
            ck(s4['thumb'] == 'https://archive.org/services/img/houseilive', T + ' next video, its picture %s' % s4['thumb'])
            ck(not errs, T + ' no page errors %s' % errs[:2])
            await ctx.close()
        await b.close()
    print('ALL PASSED' if not fails2 else 'FAILED %s' % fails2)
    raise SystemExit(1 if fails2 else 0)
asyncio.run(main())
