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

        # 1. Add or Manage Channels on the Live TV page
        has_btn = await pg.evaluate("!!document.querySelector('#stationsGrid > .epg-manage #ltvManageChannels')")
        check(has_btn, f'[{TAG}] Add or Manage Channels is under the guide on the Live TV page')
        if has_btn:
            await pg.evaluate("document.getElementById('ltvManageChannels').scrollIntoView({block:'center'})"); await pg.wait_for_timeout(400)
            await pg.screenshot(path=f'{SHOTS}/lms-{TAG}-2-manage-btn.png')
            await pg.evaluate("document.getElementById('ltvManageChannels').click()"); await pg.wait_for_timeout(700)
            items = await pg.evaluate("Array.from(document.querySelectorAll('#ltvManageSheet .np-menu-item')).map(function(b){ return b.textContent.trim(); })")
            check(items[:3] == ['Add Channels', 'Build a Custom Channel', 'Arrange Channels'], f'[{TAG}] the menu: Add Channels, Build a Custom Channel, Arrange Channels {items}')
            await pg.screenshot(path=f'{SHOTS}/lms-{TAG}-3-sheet.png')
            await pg.evaluate("document.querySelector('.ltv-manage-scrim').click()"); await pg.wait_for_timeout(500)

        # 2. Add Channels > My Shows & Movies has no Build a Custom Channel card
        await pg.evaluate("document.getElementById('videoReorderHeaderBtn').click()"); await pg.wait_for_timeout(500)
        hdr_items = await pg.evaluate("Array.from(document.querySelectorAll('#guideMenu .np-menu-item')).map(function(b){ return b.textContent.trim(); })")
        check('Build a Custom Channel' in hdr_items, f'[{TAG}] the header Edit menu has Build a Custom Channel {hdr_items}')
        await pg.evaluate("document.querySelector('#guideMenu .np-menu-item').click()"); await pg.wait_for_timeout(1500)
        await pg.evaluate("(function(){ var t = Array.from(document.querySelectorAll('.ch-tools .home-tab')).filter(function(x){ return /Shows/.test(x.textContent); })[0]; if(t) t.click(); })()"); await pg.wait_for_timeout(900)
        card = await pg.evaluate("!!document.getElementById('chCustomBtn')")
        check(not card, f'[{TAG}] Add Channels > My Shows & Movies no longer has the Build a Custom Channel card')
        await pg.screenshot(path=f'{SHOTS}/lms-{TAG}-4-addchannels.png')
        await pg.evaluate("document.getElementById('detailBackBtn').click()"); await pg.wait_for_timeout(1100)

        # 3. Arrange Channels: scroll by swiping over the rows
        await pg.evaluate("(function(){ var b = document.getElementById('videoReorderHeaderBtn'); b.click(); })()"); await pg.wait_for_timeout(400)
        await pg.evaluate("Array.from(document.querySelectorAll('#guideMenu .np-menu-item')).filter(function(b){ return /Arrange/.test(b.textContent); })[0].click()"); await pg.wait_for_timeout(900)
        rows = await pg.evaluate("document.querySelectorAll('.ch-edit-list > .tile').length")
        check(rows == 9 + 14, f'[{TAG}] Arrange lists all 23 channels {rows}')
        await pg.evaluate("window.scrollTo(0,0)"); await pg.wait_for_timeout(300)
        await pg.screenshot(path=f'{SHOTS}/lms-{TAG}-5-arrange.png')
        y0 = await pg.evaluate("window.scrollY")
        # swipe with the finger on a row (x on the name text, y mid-screen)
        await scroll_swipe(cdp, 150, 520, 300); await pg.wait_for_timeout(600)
        y1 = await pg.evaluate("window.scrollY")
        check(y1 - y0 > 120, f'[{TAG}] a finger swipe over the rows scrolls the Edit list ({y0} -> {y1})')
        await scroll_swipe(cdp, 150, 520, 300); await pg.wait_for_timeout(600)
        y2 = await pg.evaluate("window.scrollY")
        check(y2 > y1, f'[{TAG}] and again ({y1} -> {y2})')
        await pg.screenshot(path=f'{SHOTS}/lms-{TAG}-6-arrange-scrolled.png')
        if TAG != 'new':
            await b.close(); return
        # press-hold-drag still reorders (hold 600ms then move)
        await pg.evaluate("window.scrollTo(0,0)"); await pg.wait_for_timeout(300)
        order0 = await pg.evaluate("Array.from(document.querySelectorAll('.ch-added-list > .tile .tile-name')).map(function(e){ return e.textContent; })")
        from syn_drag import syn_drag
        await syn_drag(pg, '.ch-added-list > .tile', order0[0], order0[2], before=False)
        order1 = await pg.evaluate("Array.from(document.querySelectorAll('.ch-added-list > .tile .tile-name')).map(function(e){ return e.textContent; })")
        check(order1[:3] == [order0[1], order0[2], order0[0]], f'[{TAG}] press, hold and drag still reorders {order1[:3]}')

        # 4. Select
        await pg.evaluate("window.scrollTo(0,0)"); await pg.wait_for_timeout(300)
        await pg.evaluate("document.getElementById('chSelectBtn').click()"); await pg.wait_for_timeout(500)
        await pg.screenshot(path=f'{SHOTS}/lms-{TAG}-7-select.png')
        checks = await pg.evaluate("document.querySelectorAll('.ch-edit-list > .tile .ch-check').length")
        check(checks == 23, f'[{TAG}] every row has a checkbox in Select {checks}')
        # tap three rows with real taps: one of your own, two added
        names = ['Friends Marathon', 'Batman', 'Cartoons']
        for n in names:
            await pg.evaluate("(function(n){ var t = Array.from(document.querySelectorAll('.ch-edit-list > .tile')).filter(function(e){ return e.querySelector('.tile-name').textContent === n; })[0]; t.scrollIntoView({block:'center'}); })(%s)" % json.dumps(n))
            await pg.wait_for_timeout(250)
            box = await pg.evaluate("(function(n){ var t = Array.from(document.querySelectorAll('.ch-edit-list > .tile')).filter(function(e){ return e.querySelector('.tile-name').textContent === n; })[0]; var r = t.querySelector('.tile-name').getBoundingClientRect(); return [r.left + 10, r.top + r.height / 2]; })(%s)" % json.dumps(n))
            await pg.touchscreen.tap(box[0], box[1]); await pg.wait_for_timeout(250)
        btn = await pg.evaluate("(function(){ var b = document.getElementById('chSelDeleteBtn'); var r = b.getBoundingClientRect(); return { t: b.textContent, dis: b.disabled, vis: r.top >= 0 && r.bottom <= innerHeight }; })()")
        check(btn['t'] == 'Remove 3 Channels' and not btn['dis'] and btn['vis'], f'[{TAG}] three ticked: the Remove button says so and is on screen {btn}')
        await pg.screenshot(path=f'{SHOTS}/lms-{TAG}-8-selected.png')
        # Select None / Select All toggle
        await pg.evaluate("document.getElementById('chSelAllBtn') && 0")
        await pg.evaluate("document.getElementById('chSelDeleteBtn').click()"); await pg.wait_for_timeout(500)
        dlg = await pg.evaluate("(function(){ var o = document.getElementById('confirmOverlay'); return { open: o.classList.contains('open'), t: document.getElementById('confirmTitle').textContent, m: document.getElementById('confirmMsg').textContent, ok: document.getElementById('confirmOk').textContent }; })()")
        check(dlg['open'] and dlg['t'] == 'Remove 3 channels from Live TV?', f'[{TAG}] Remove asks first {dlg}')
        await pg.screenshot(path=f'{SHOTS}/lms-{TAG}-9-confirm.png')
        await pg.evaluate("document.getElementById('confirmCancel').click()"); await pg.wait_for_timeout(300)
        n_after_cancel = await pg.evaluate("document.querySelectorAll('.ch-edit-list > .tile').length")
        check(n_after_cancel == 23, f'[{TAG}] Cancel removes nothing {n_after_cancel}')
        await pg.evaluate("document.getElementById('chSelDeleteBtn').click()"); await pg.wait_for_timeout(400)
        await pg.evaluate("document.getElementById('confirmOk').click()"); await pg.wait_for_timeout(900)
        left = await pg.evaluate("Array.from(document.querySelectorAll('.ch-edit-list > .tile .tile-name')).map(function(e){ return e.textContent; })")
        check(len(left) == 20 and 'Batman' not in left and 'Cartoons' not in left and 'Friends Marathon' not in left, f'[{TAG}] the three are gone, 20 left {len(left)}')
        defs = await pg.evaluate("JSON.parse(localStorage.getItem('radioPlayerLiveChannels')).map(function(d){ return d.id; })")
        vc = await pg.evaluate("JSON.parse(localStorage.getItem('radioPlayerVideoChannels')).map(function(d){ return d.name; })")
        check('x1' not in defs and 'Batman' not in vc and 'Cartoons' not in vc and len(vc) == 12, f'[{TAG}] saved: your channel and two added ones removed {defs} {len(vc)}')
        sel_off = await pg.evaluate("!document.getElementById('chSelDeleteBtn') && !!document.getElementById('chSelectBtn')")
        check(sel_off, f'[{TAG}] back to Edit (Select button, no Remove bar)')
        await pg.screenshot(path=f'{SHOTS}/lms-{TAG}-10-after-remove.png')
        # Select All / Select None
        await pg.evaluate("document.getElementById('chSelectBtn').click()"); await pg.wait_for_timeout(300)
        await pg.evaluate("document.getElementById('chSelAllBtn').click()"); await pg.wait_for_timeout(200)
        t_all = await pg.evaluate("document.getElementById('chSelDeleteBtn').textContent + '|' + document.getElementById('chSelAllBtn').textContent")
        check(t_all == 'Remove 20 Channels|Select None', f'[{TAG}] Select All ticks everything {t_all}')
        await pg.evaluate("document.getElementById('chSelAllBtn').click()"); await pg.wait_for_timeout(200)
        t_none = await pg.evaluate("document.getElementById('chSelDeleteBtn').disabled")
        check(t_none, f'[{TAG}] Select None unticks (Remove disabled)')
        await pg.evaluate("document.getElementById('chSelCancelBtn').click()"); await pg.wait_for_timeout(300)

        # 5. Custom channel with archive.org videos + a library show
        await pg.evaluate("document.getElementById('videoReorderHeaderBtn').click()"); await pg.wait_for_timeout(500)
        await pg.evaluate("Array.from(document.querySelectorAll('#guideMenu .np-menu-item, #ltvManageSheet .np-menu-item')).filter(function(b){ return /Build a Custom/.test(b.textContent); })[0].click()"); await pg.wait_for_timeout(900)
        pills = await pg.evaluate("Array.from(document.querySelectorAll('#liveChPickWhere .home-tab')).map(function(b){ return b.textContent; })")
        check(pills == ['My Library', 'Archive.org'], f'[{TAG}] the editor picks from My Library or Archive.org {pills}')
        await pg.screenshot(path=f'{SHOTS}/lms-{TAG}-11-editor.png')
        await pg.evaluate("(function(){ Array.from(document.querySelectorAll('#liveChList .artist-info-row')).filter(function(x){ return x.querySelector('.artist-info-name').textContent === 'Seinfeld'; })[0].click(); })()"); await pg.wait_for_timeout(250)
        await pg.evaluate("Array.from(document.querySelectorAll('#liveChPickWhere .home-tab'))[1].click()"); await pg.wait_for_timeout(300)
        await pg.fill('#liveChIaSearch', 'fleischer'); await pg.wait_for_timeout(1800)
        rows = await pg.evaluate("Array.from(document.querySelectorAll('#liveChIaList .artist-info-name')).map(function(e){ return e.textContent; })")
        check(len(rows) == 3 and 'mediatype:(movies)' in IA_Q[-1], f'[{TAG}] archive.org video search shows 3 results, video only {rows} {IA_Q[-1:]}')
        await pg.screenshot(path=f'{SHOTS}/lms-{TAG}-12-ia-results.png')
        for n in ('Superman: The Mechanical Monsters', 'Betty Boop: Snow-White'):
            await pg.evaluate("(function(n){ Array.from(document.querySelectorAll('#liveChIaList .artist-info-row')).filter(function(x){ return x.querySelector('.artist-info-name').textContent === n; })[0].click(); })(%s)" % json.dumps(n))
            await pg.wait_for_timeout(250)
        await pg.wait_for_timeout(1200)
        st = await pg.evaluate("({ save: !document.getElementById('liveChSaveBtn').disabled, sum: document.getElementById('liveChSummary').textContent, tab: document.querySelectorAll('#liveChPickWhere .home-tab')[1].textContent, hdr: Array.from(document.querySelectorAll('#liveChIaList .lc-ia-head')).map(function(e){ return e.textContent; }) })")
        check(st['save'] and '1 show' in st['sum'] and '2 archive.org videos' in st['sum'], f'[{TAG}] summary counts the show and two archive.org videos {st}')
        check(st['tab'] == 'Archive.org (2)', f'[{TAG}] the Archive.org tab counts what is added {st}')
        # the Archive.org list now leads with what is in the channel (shown when the list is drawn again)
        await pg.evaluate("Array.from(document.querySelectorAll('#liveChPickWhere .home-tab'))[0].click()"); await pg.wait_for_timeout(250)
        await pg.evaluate("Array.from(document.querySelectorAll('#liveChPickWhere .home-tab'))[1].click()"); await pg.wait_for_timeout(300)
        hdr = await pg.evaluate("Array.from(document.querySelectorAll('#liveChIaList .lc-ia-head')).map(function(e){ return e.textContent; })")
        check(hdr == ['In this channel'] or hdr[:1] == ['In this channel'], f'[{TAG}] the Archive.org list leads with what is in the channel {hdr}')
        await pg.screenshot(path=f'{SHOTS}/lms-{TAG}-13-ia-added.png')
        await pg.fill('#liveChName', 'Cartoons & Seinfeld')
        await pg.evaluate("document.getElementById('liveChSaveBtn').click()"); await pg.wait_for_timeout(1500)
        d = await pg.evaluate("JSON.parse(localStorage.getItem('radioPlayerLiveChannels')).filter(function(x){ return x.name === 'Cartoons & Seinfeld'; })[0]")
        check(d and d['src']['shows'] == ['Seinfeld'] and [a['id'] for a in d['src']['archive']] == ['cartoon_one', 'cartoon_three'], f'[{TAG}] saved with the show and both videos {d and d["src"]}')
        # guide shows archive programs for the channel
        await pg.evaluate("window.scrollTo(0,0)"); await pg.wait_for_timeout(600)
        g = await grid(pg)
        row = [r for r in g['rows'] if r['name'] == 'Cartoons & Seinfeld']
        titles = [bl['t'] for bl in row[0]['blocks']] if row else []
        check(row and any('Superman' in t or 'Betty Boop' in t for t in titles) and any('Seinfeld' in t for t in titles), f'[{TAG}] the guide schedules the archive videos and the show {titles[:6]}')
        await pg.screenshot(path=f'{SHOTS}/lms-{TAG}-14-guide.png')
        # tuning in plays an archive file when one is on
        await pg.evaluate("window.__loads.length = 0")
        ok = await pg.evaluate("""(function(){ var r = Array.from(document.querySelectorAll('#stationsGrid .epg-row')).filter(function(x){ return /Cartoons/.test(x.querySelector('.epg-ch').textContent); })[0]; r.querySelector('.epg-prog.now').click(); return true; })()""")
        await pg.wait_for_timeout(1500)
        loads = await pg.evaluate("window.__loads.map(function(a){ return a.url || a.uri || ''; })")
        check(len(loads) >= 1, f'[{TAG}] tuning in the channel plays something {loads[-1:]}')
        check(not errs, f'[{TAG}] no page errors {errs[:2]}')
        await b.close()

asyncio.run(main())
print('FAILS:', len(fails))
for f in fails: print(' -', f)
sys.exit(1 if fails else 0)
