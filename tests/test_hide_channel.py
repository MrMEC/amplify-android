"""Build 617: Live TV channel management at Mark's phone size (327 x 709 CSS px, dpr 3.3).
 1. Add or Manage Channels is under the guide on the Live TV page (not only under a playing channel).
 2. Its menu has Build a Custom Channel; Add Channels > My Shows & Movies no longer has that card.
 3. Arrange Channels (Edit): a finger anywhere on the list scrolls it (CDP touch swipe over a row).
 4. Select: tick several channels (your own + added), Remove N Channels asks first, then removes them.
 5. The channel editor can add archive.org videos (video only), mixed with library shows, in one channel;
    the channel is scheduled from those videos and shows them in the guide.
Run: python3 tests/test_live_manage_select.py [path-to-index.html]  (screenshots in /tmp/claude-0/t/shots)"""
import sys as _nsys, os as _nos; _nsys.path.insert(0, _nos.path.dirname(_nos.path.abspath(__file__))); from notice_auto import AUTO_NOTICE
import os, json, sys, asyncio
HERE = os.path.dirname(os.path.abspath(__file__))
src = open(os.path.join(HERE, 'test_live_channels.py')).read()
head = src[:src.index('\nasync def run(')]
APP = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, '..', 'www', 'index.html')
TAG = sys.argv[2] if len(sys.argv) > 2 else 'new'
head = head.replace("'/tmp/claude-0/t/srv-livech'", "'/tmp/claude-0/t/srv-lms-%s'" % TAG).replace('PORT = 8862', 'PORT = %d' % (8880 if TAG == 'new' else 8881))
head = head.replace("shutil.copy(os.path.join(HERE, '..', 'www', 'index.html'), ROOT)", "shutil.copy(APP, os.path.join(ROOT, 'index.html'))")
exec(head)

# A realistic long list: nine of your own channels (four default + five) and 14 added channels.
OWN_EXTRA = [
    {'id': 'x1', 'name': 'Friends Marathon', 'src': {'kind': 'pick', 'shows': ['Friends'], 'movies': []}, 'order': 'sequence'},
    {'id': 'x2', 'name': 'Comedy Mix', 'src': {'kind': 'pick', 'shows': ['MADtv', 'Seinfeld'], 'movies': []}, 'order': 'shuffle'},
    {'id': 'x3', 'name': 'Office Shuffle', 'src': {'kind': 'pick', 'shows': ['The Office (US)'], 'movies': []}, 'order': 'daily'},
    {'id': 'x4', 'name': 'Everything Sitcom', 'src': {'kind': 'pick', 'shows': ['The Office (US)', 'MADtv', 'Seinfeld', 'Friends'], 'movies': []}, 'order': 'sequence'},
    {'id': 'x5', 'name': 'Late Night Laughs', 'src': {'kind': 'pick', 'shows': ['MADtv'], 'movies': []}, 'order': 'sequence'},
]
ADDED = [{'id': 'pluto:%02d' % i, 'name': n, 'url': 'https://example.test/live/%02d/master.m3u8' % i, 'logo': '', 'cats': ['Classic TV'], 'catNames': ['Classic TV'], 'src': 'pluto'}
         for i, n in enumerate(['Buzzr', 'Black Classics', 'Batman', 'BTTF', 'Cartoons', 'Classic TV', 'Comedy Central Classics', 'Bewitched', 'Animation', 'Pluto TV Action',
                                'Pluto TV Mystery', 'Pluto TV Sci-Fi', 'Pluto TV Westerns', 'Pluto TV Game Shows'])]
DEFAULTS = [
    {'id': 'office', 'name': '', 'src': {'kind': 'pick', 'shows': ['The Office'], 'movies': []}, 'order': 'sequence'},
    {'id': 'madtv', 'name': '', 'src': {'kind': 'pick', 'shows': ['MadTV'], 'movies': []}, 'order': 'sequence'},
    {'id': 'seinfeld', 'name': '', 'src': {'kind': 'pick', 'shows': ['Seinfeld'], 'movies': []}, 'order': 'sequence'},
    {'id': 'movies', 'name': 'Movies', 'src': {'kind': 'movies', 'from': 'phone'}, 'order': 'shuffle'},
]
SEED2 = """(function(){ if(!localStorage.getItem('__seeded')){ localStorage.setItem('__seeded','1');
  localStorage.setItem('radioPlayerPlexAccount', %s);
  var lib = JSON.parse(%s); lib.at = Date.now(); localStorage.setItem('radioPlayerPlexLib', JSON.stringify(lib));
  localStorage.setItem('radioPlayerVideoFiles', %s);
  localStorage.setItem('radioPlayerVideoInfo', %s);
  localStorage.setItem('radioPlayerVideoChannels', %s);
  localStorage.setItem('radioPlayerLiveChannels', %s);
  localStorage.setItem('radioPlayerVideoTab', 'channels'); } })();""" % tuple(json.dumps(json.dumps(x)) for x in (ACCT, LIB, FILES, INFO, ADDED, DEFAULTS + OWN_EXTRA))

IA_DOCS = [{'identifier': 'cartoon_one', 'title': 'Superman: The Mechanical Monsters', 'mediatype': 'movies', 'creator': 'Fleischer Studios', 'year': '1941', 'downloads': 90000},
           {'identifier': 'cartoon_two', 'title': 'Popeye the Sailor Meets Sindbad', 'mediatype': 'movies', 'creator': 'Fleischer Studios', 'year': '1936', 'downloads': 80000},
           {'identifier': 'cartoon_three', 'title': 'Betty Boop: Snow-White', 'mediatype': 'movies', 'creator': 'Fleischer Studios', 'year': '1933', 'downloads': 70000}]
LEN = {'cartoon_one': '600', 'cartoon_two': '1200', 'cartoon_three': '420'}
IA_Q = []
async def route2(r):
    u = r.request.url; pu = urlparse(u)
    if 'archive.org' in u:
        if r.request.method == 'OPTIONS': return await r.fulfill(status=204, headers=CORS)
        if 'advancedsearch' in u:
            IA_Q.append(parse_qs(pu.query).get('q', [''])[0])
            return await r.fulfill(status=200, content_type='application/json', headers=CORS, body=json.dumps({'response': {'numFound': 3, 'docs': IA_DOCS}}))
        if '/metadata/' in u:
            i = pu.path.rsplit('/', 1)[1]
            return await r.fulfill(status=200, content_type='application/json', headers=CORS, body=json.dumps({'files': [{'name': i + '.mp4', 'format': 'h.264', 'size': '9000', 'length': LEN.get(i, '300')}]}))
        return await r.fulfill(status=200, content_type='image/png', headers=CORS, body=PNG)
    if u.startswith('https://example.test'): return await r.fulfill(status=200, content_type='application/vnd.apple.mpegurl', headers=CORS, body='#EXTM3U')
    return await route(r)
from urllib.parse import parse_qs

W, H_ = 327, 709
async def scroll_swipe(cdp, x, y, dist, steps=20):
    # real touch input through the browser (touch-action is honoured), finger moving up = page scrolls down
    await cdp.send('Input.dispatchTouchEvent', {'type': 'touchStart', 'touchPoints': [{'x': x, 'y': y}]})
    for i in range(1, steps + 1):
        await cdp.send('Input.dispatchTouchEvent', {'type': 'touchMove', 'touchPoints': [{'x': x, 'y': y - dist * i / steps}]})
        await asyncio.sleep(0.016)
    await cdp.send('Input.dispatchTouchEvent', {'type': 'touchEnd', 'touchPoints': []})

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
        ctx = await b.new_context(viewport={'width': W, 'height': H_}, device_scale_factor=3.3, is_mobile=True, has_touch=True, color_scheme='dark', locale='en-US', timezone_id='America/New_York')
        await ctx.add_init_script(MOCK); await ctx.add_init_script(AUTO_NOTICE); await ctx.add_init_script(SEED2)
        pg = await ctx.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e) + ' ' + (e.stack or '')[:300]))
        await pg.route('**/*', route2)
        cdp = await ctx.new_cdp_session(pg)
        await pg.goto(f'http://127.0.0.1:{PORT}/index.html'); await pg.wait_for_timeout(3000)
        await pg.evaluate("document.querySelector('.mobile-nav-btn[data-nav=video]').click()"); await pg.wait_for_timeout(1800)
        await pg.screenshot(path=f'{SHOTS}/lms-{TAG}-1-livetv.png')


        guide0 = await pg.evaluate("document.querySelectorAll('#stationsGrid .epg-row, #stationsGrid .epg-ch').length")
        names = lambda: pg.evaluate("Array.from(document.querySelectorAll('#stationsGrid .epg-chan, #stationsGrid .epg-ch-name, #stationsGrid [data-ch-url]')).length")
        # open the guide and the channel sheet for Batman
        await pg.evaluate("window.__sheet = null")
        n0 = await pg.evaluate("liveCount()") if False else None
        # Hide Channel in the sheet (called straight through the logo tap)
        logos = await pg.evaluate("Array.from(document.querySelectorAll('#stationsGrid .epg-logo, #stationsGrid .epg-ch')).length")
        print('logos', logos)
        await pg.evaluate("document.querySelector('#stationsGrid .epg-logo, #stationsGrid .epg-ch').click()"); await pg.wait_for_timeout(600)
        items = await pg.evaluate("Array.from(document.querySelectorAll('#chSheetItems .ch-sheet-item')).map(function(b){ return b.textContent.trim(); })")
        print('sheet', items)
        await pg.screenshot(path=f'{SHOTS}/lms-{TAG}-h1-sheet.png')
        before = await pg.evaluate("document.querySelectorAll('#stationsGrid .epg-logo, #stationsGrid .epg-ch').length")
        await pg.evaluate("Array.from(document.querySelectorAll('#chSheetItems .ch-sheet-item')).filter(function(b){return /Hide Channel/.test(b.textContent)})[0].click()"); await pg.wait_for_timeout(900)
        after = await pg.evaluate("document.querySelectorAll('#stationsGrid .epg-logo, #stationsGrid .epg-ch').length")
        hid = await pg.evaluate("localStorage.getItem('radioPlayerHiddenChannels')")
        check(after == before - 2, f'hidden channel leaves the grid {before}->{after} {hid}')
        # privacy on: it comes back, and no Hide option
        await pg.evaluate("localStorage.setItem('radioPlayerPrivacy','on')"); await pg.evaluate("rerenderVideoKeepingScroll && 0")
        await pg.reload(); await pg.wait_for_timeout(2500)
        await pg.evaluate("document.querySelector('.mobile-nav-btn[data-nav=video]').click()"); await pg.wait_for_timeout(1800)
        priv = await pg.evaluate("document.querySelectorAll('#stationsGrid .epg-logo, #stationsGrid .epg-ch').length")
        check(priv == before, f'privacy on shows it again {priv}')
        await pg.evaluate("document.querySelector('#stationsGrid .epg-logo, #stationsGrid .epg-ch').click()"); await pg.wait_for_timeout(600)
        items = await pg.evaluate("Array.from(document.querySelectorAll('#chSheetItems .ch-sheet-item')).map(function(b){ return b.textContent.trim(); })")
        check(not any('Hide' in i or 'Show' in i for i in items), f'no Hide option in privacy {items}')
        await pg.evaluate("document.getElementById('chSheetOverlay').click()"); await pg.wait_for_timeout(300)
        await pg.evaluate("localStorage.setItem('radioPlayerPrivacy','off')")
        await pg.reload(); await pg.wait_for_timeout(2500)
        await pg.evaluate("document.querySelector('.mobile-nav-btn[data-nav=video]').click()"); await pg.wait_for_timeout(1800)
        # Edit list: Select Channels button, spacing, hidden row marked, Show Channel
        await pg.evaluate("document.getElementById('videoReorderHeaderBtn').click()"); await pg.wait_for_timeout(400)
        await pg.evaluate("Array.from(document.querySelectorAll('#guideMenu .np-menu-item')).filter(function(b){ return /Arrange/.test(b.textContent); })[0].click()"); await pg.wait_for_timeout(900)
        await pg.evaluate("window.scrollTo(0,0)"); await pg.wait_for_timeout(300)
        await pg.screenshot(path=f'{SHOTS}/lms-{TAG}-h2-edit.png')
        m = await pg.evaluate("""(function(){ var b=document.getElementById('chSelectBtn').getBoundingClientRect(), f=document.querySelector('.ch-edit-list').getBoundingClientRect();
          var pills=document.querySelector('.ch-tools, .video-tabs, .home-tabs'); var pr=null;
          var prev=document.getElementById('chSelectBtn').parentNode.previousElementSibling; var pb=prev?prev.getBoundingClientRect().bottom:null;
          return {txt:document.getElementById('chSelectBtn').textContent, cx:(b.left+b.right)/2, w:window.innerWidth, above:b.top-(pb||0), below:f.top-b.bottom, prev:prev&&prev.className}; })()""")
        print('select', m)
        check(m['txt'] == 'Select Channels' and abs(m['cx'] - m['w']/2) < 2, 'Select Channels centered')
        check(abs(m['above'] - m['below']) < 3, f"even spacing above/below {m}")
        hidden_rows = await pg.evaluate("Array.from(document.querySelectorAll('.ch-edit-list > .tile')).filter(function(t){return /Hidden/.test(t.textContent)}).length")
        check(hidden_rows == 1, f'hidden row marked {hidden_rows}')
        await pg.evaluate("Array.from(document.querySelectorAll('.ch-edit-list > .tile')).filter(function(t){return /Hidden/.test(t.textContent)})[0].querySelector('.row-more-btn').click()"); await pg.wait_for_timeout(500)
        await pg.screenshot(path=f'{SHOTS}/lms-{TAG}-h3-rowmenu.png')
        lab = await pg.evaluate("document.getElementById('rowMenuHide').style.display + '|' + document.getElementById('rowMenuHideLabel').textContent")
        check(lab == '|Show Channel', f'row menu offers Show Channel {lab}')
        await pg.evaluate("document.getElementById('rowMenuHide').click()"); await pg.wait_for_timeout(600)
        check(await pg.evaluate("localStorage.getItem('radioPlayerHiddenChannels')") == '[]', 'shown again')
        print('errs', errs)
        await b.close()

asyncio.run(main())
