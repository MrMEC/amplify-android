"""Build 339: Add Channels > Archive.org. Mocked archive.org. Checks: the tab and its 18 categories (the
seven asked for first, spelled with archive.org's case-sensitive ids); a category opens to its top 20;
+ adds a channel to My Channels (Archive.org group); tuning it plays the first item and queues the rest;
Search everything drops the collection filter; a search result can be added as a channel.
Run: python3 tests/test_archive_channels.py (screenshots in /tmp/claude-0/t/shots)"""
import asyncio, json, os, shutil, threading, http.server, functools
from urllib.parse import urlparse, parse_qs
from playwright.async_api import async_playwright
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = '/tmp/claude-0/t/srv-archch'; SHOTS = '/tmp/claude-0/t/shots'
os.makedirs(ROOT, exist_ok=True); os.makedirs(SHOTS, exist_ok=True)
shutil.copy(os.path.join(HERE, '..', 'www', 'index.html'), ROOT)
H = functools.partial(http.server.SimpleHTTPRequestHandler, directory=ROOT); H.log_message = lambda *a: None
srv = http.server.ThreadingHTTPServer(('127.0.0.1', 8829), H); threading.Thread(target=srv.serve_forever, daemon=True).start()
fails = 0
def check(ok, msg):
    global fails
    print(('PASS ' if ok else 'FAIL ') + msg); fails += 0 if ok else 1
CORS = {'access-control-allow-origin': '*', 'access-control-allow-headers': '*', 'access-control-allow-methods': 'GET,OPTIONS'}
seen = {'q': [], 'meta': []}
TOP = [{'identifier': 'popeye%d' % i, 'title': 'Popeye Cartoon %d' % i, 'mediatype': 'movies', 'year': '195%d' % (i % 10), 'downloads': 1000000 - i * 1000} for i in range(1, 21)]
SEARCH = [{'identifier': 'zz_found', 'title': 'Some Found Thing', 'mediatype': 'audio', 'creator': 'Somebody', 'year': '2001', 'downloads': 12}]
def meta_for(i):
    return {'files': [{'name': i + '.mp4', 'format': 'h.264', 'size': '9000', 'length': '600'}]}
def jr(r, obj):
    return r.fulfill(status=200, content_type='application/json', headers=CORS, body=json.dumps(obj))
async def route(r):
    u = r.request.url; pu = urlparse(u); q = parse_qs(pu.query)
    if r.request.method == 'OPTIONS' and 'archive.org' in u:
        return await r.fulfill(status=204, headers=CORS)
    if 'archive.org/advancedsearch' in u:
        qq = q.get('q', [''])[0]; seen['q'].append(qq)
        return await jr(r, {'response': {'docs': TOP if qq.startswith('collection:(') else SEARCH}})
    if 'archive.org/metadata/' in u:
        i = pu.path.rsplit('/', 1)[1]; seen['meta'].append(i); return await jr(r, meta_for(i))
    if 'archive.org/' in u:
        return await r.fulfill(status=200, content_type='image/png', headers=CORS, body=b'')
    if 'radio-browser' in u:
        return await jr(r, [])
    return await r.continue_()
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
        ctx = await b.new_context(viewport={'width': 390, 'height': 844}, device_scale_factor=2, is_mobile=True, has_touch=True, color_scheme='dark')
        pg = await ctx.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.route('**/*', route)
        await pg.goto('http://127.0.0.1:8829/index.html'); await pg.wait_for_timeout(2500)
        await pg.evaluate("document.querySelector('.mobile-nav-btn[data-nav=video]').click()"); await pg.wait_for_timeout(500)
        await pg.evaluate("document.getElementById('videoAddHeaderBtn').click()"); await pg.wait_for_timeout(1500)
        tabs = await pg.evaluate("Array.prototype.map.call(document.querySelectorAll('.ch-tools .home-tab'),function(t){return t.textContent.trim();})")
        check('Archive.org' in tabs, f'Archive.org tab in Add Channels {tabs}')
        await pg.evaluate("Array.prototype.find.call(document.querySelectorAll('.ch-tools .home-tab'),function(t){return t.textContent.trim()==='Archive.org';}).click()"); await pg.wait_for_timeout(600)
        names = await pg.evaluate("Array.prototype.map.call(document.querySelectorAll('.ia-cat > .ch-row .ch-name'),function(n){return n.textContent;})")
        want = ['Classic TV', 'Film Noir', 'Silent Films', 'Sci-Fi & Horror', 'Classic Cartoons', 'Old-Time Radio', 'Live Concerts']
        check(names[:7] == want and len(names) == 18, f'seven asked-for categories first, 18 in all {len(names)} {names[:7]}')
        await pg.screenshot(path=f'{SHOTS}/archch-tab.png')
        # open a category: its top 20, asked for with the collection id as archive.org spells it
        await pg.evaluate("document.querySelectorAll('.ia-cat > .ch-row')[3].click()"); await pg.wait_for_timeout(900)
        n = await pg.evaluate("document.querySelectorAll('.ia-cat.open .ia-item').length")
        check(n == 20, f'category opens to 20 items {n}')
        check(any('collection:(SciFi_Horror)' in q for q in seen['q']), f'asked for SciFi_Horror with its exact id {seen["q"][-1:]}')
        await pg.screenshot(path=f'{SHOTS}/archch-open.png')
        # + adds the category as a channel
        await pg.evaluate("document.querySelectorAll('.ia-cat > .ch-row .ch-add')[3].click()"); await pg.wait_for_timeout(300)
        chs = await pg.evaluate("JSON.parse(localStorage.getItem('radioPlayerVideoChannels')||'[]')")
        check(len(chs) == 1 and chs[0]['url'] == 'amplify-archive:c:SciFi_Horror' and chs[0]['name'] == 'Sci-Fi & Horror', f'channel added {[c["url"] for c in chs]}')
        check(chs[0].get('catNames') == ['Archive.org'], f'grouped as Archive.org {chs[0].get("catNames")}')
        # tune it: first item plays at once, the others are lined up
        seen['meta'].clear()
        await pg.evaluate("document.getElementById('npBackBtn') && document.getElementById('npBackBtn').click()")
        await pg.evaluate("document.querySelector('.mobile-nav-btn[data-nav=video]').click()"); await pg.wait_for_timeout(600)
        await pg.screenshot(path=f'{SHOTS}/archch-mine.png', full_page=True)
        await pg.evaluate("document.querySelector('#stationsGrid .epg-prog.now').click()"); await pg.wait_for_timeout(2500)
        cur = await pg.evaluate("({n: document.getElementById('playerName').textContent.trim()})")
        check(cur['n'] == 'Popeye Cartoon 1', f'plays item 1 {cur}')
        await pg.screenshot(path=f'{SHOTS}/archch-playing.png')
        lay = await pg.evaluate("({ch: document.getElementById('nowPlayingScreen').classList.contains('np-channel'), tg: getComputedStyle(document.getElementById('npVideoToggle')).display})")
        check(lay['ch'] and lay['tg'] == 'none', f'an archive video uses the video screen, no Turn On Video pill {lay}')
        # Next steps along the channel's items
        await pg.evaluate("document.getElementById('npNextBtn') && document.getElementById('npNextBtn').click()"); await pg.wait_for_timeout(800)
        cur2 = await pg.evaluate("({n: document.getElementById('playerName').textContent.trim()})")
        check(cur2['n'] == 'Popeye Cartoon 2', f'Next goes to item 2 {cur2}')
        check(len(seen['meta']) == 20, f'file lists asked for all 20 items {len(seen["meta"])}')
        # tuned from elsewhere (a favourite / the guide), the channel station tunes in too
        # search: off = collections only; on = everything
        await pg.evaluate("document.getElementById('npBackBtn') && document.getElementById('npBackBtn').click()"); await pg.wait_for_timeout(300)
        await pg.evaluate("document.querySelector('.mobile-nav-btn[data-nav=video]').click()"); await pg.wait_for_timeout(400)
        await pg.evaluate("document.getElementById('videoAddHeaderBtn').click()"); await pg.wait_for_timeout(800)
        await pg.evaluate("Array.prototype.find.call(document.querySelectorAll('.ch-tools .home-tab'),function(t){return t.textContent.trim()==='Archive.org';}).click()"); await pg.wait_for_timeout(500)
        async def search(text):
            await pg.evaluate("(t)=>{var i=document.querySelector('.ch-tools input[type=search]');i.value=t;i.dispatchEvent(new Event('input',{bubbles:true}));}", text)
            await pg.wait_for_timeout(1400)
        seen['q'].clear(); await search('found thing')
        q1 = seen['q'][-1] if seen['q'] else ''
        check('collection:(' in q1 and 'classic_tv' in q1, f'switch off: restricted to the collections {q1[:90]}')
        rows = await pg.evaluate("document.querySelectorAll('.ia-item').length")
        check(rows == 1, f'search shows its result {rows}')
        await pg.evaluate("var c=document.querySelector('.ia-switch input');c.checked=true;c.dispatchEvent(new Event('change',{bubbles:true}));"); await pg.wait_for_timeout(1000)
        q2 = seen['q'][-1]
        check('collection:' not in q2 and 'mediatype:(movies OR audio OR etree)' in q2, f'switch on: all of archive.org {q2}')
        check(await pg.evaluate("localStorage.getItem('radioPlayerArchiveAll')") == '1', 'switch kept')
        await pg.screenshot(path=f'{SHOTS}/archch-search.png')
        await pg.evaluate("document.querySelector('.ia-item .ch-add:not(.ia-combine)').click()"); await pg.wait_for_timeout(300)
        urls = await pg.evaluate("JSON.parse(localStorage.getItem('radioPlayerVideoChannels')).map(function(c){return c.url;})")
        check('amplify-archive:i:zz_found' in urls, f'a search result is added as a channel {urls}')
        # --- custom channel: name it, put several items in it, play it
        await pg.evaluate("document.querySelector('.ia-item .ia-combine').click()"); await pg.wait_for_timeout(300)
        check(await pg.evaluate("!!document.querySelector('.ia-sheet')"), 'picker sheet opens')
        await pg.evaluate("var i=document.querySelector('.ia-sheet .ia-new input');i.value='Disney';document.querySelector('.ia-new-go').click();"); await pg.wait_for_timeout(300)
        await pg.screenshot(path=f'{SHOTS}/archch-picker.png')
        await pg.evaluate("document.querySelector('.ia-sheet-done').click()"); await pg.wait_for_timeout(300)
        # a second item into the same channel, from a category's top 20
        await pg.evaluate("var i=document.querySelector('.ch-tools input[type=search]');i.value='';i.dispatchEvent(new Event('input',{bubbles:true}));"); await pg.wait_for_timeout(900)
        await pg.evaluate("document.querySelectorAll('.ia-cat:not(.ia-custom) > .ch-row')[4].click()"); await pg.wait_for_timeout(900)
        await pg.evaluate("document.querySelectorAll('.ia-cat.open .ia-item .ia-combine')[1].click()"); await pg.wait_for_timeout(300)
        await pg.evaluate("document.querySelector('.ia-pick').click()"); await pg.wait_for_timeout(200)
        await pg.evaluate("document.querySelector('.ia-sheet-done').click()"); await pg.wait_for_timeout(400)
        cust = await pg.evaluate("JSON.parse(localStorage.getItem('radioPlayerVideoChannels')).filter(function(c){return c.url.indexOf('amplify-archive:m:')===0;})")
        check(len(cust) == 1 and cust[0]['name'] == 'Disney' and [x['id'] for x in cust[0]['archive']['items']] == ['zz_found', 'popeye2'], f'custom channel holds both items {[x["id"] for x in cust[0]["archive"]["items"]] if cust else cust}')
        await pg.screenshot(path=f'{SHOTS}/archch-custom.png', full_page=True)
        # open it in the tab, remove an item, shuffle on
        await pg.evaluate("document.querySelector('.ia-custom > .ch-row').click()"); await pg.wait_for_timeout(300)
        await pg.screenshot(path=f'{SHOTS}/archch-custom-open.png')
        await pg.evaluate("document.querySelector('.ia-custom .ia-remove').click()"); await pg.wait_for_timeout(200)
        await pg.evaluate("var c=document.querySelector('.ia-custom .ia-switch input');c.checked=true;c.dispatchEvent(new Event('change',{bubbles:true}));"); await pg.wait_for_timeout(200)
        cust = await pg.evaluate("JSON.parse(localStorage.getItem('radioPlayerVideoChannels')).filter(function(c){return c.url.indexOf('amplify-archive:m:')===0;})")
        check([x['id'] for x in cust[0]['archive']['items']] == ['popeye2'] and cust[0]['archive']['order'] == 'shuffle', 'item removed, shuffle kept')
        # Live TV: it plays its item
        seen['meta'].clear()
        await pg.evaluate("document.getElementById('npBackBtn') && document.getElementById('npBackBtn').click()")
        await pg.evaluate("document.querySelector('.mobile-nav-btn[data-nav=video]').click()"); await pg.wait_for_timeout(600)
        await pg.evaluate("Array.prototype.find.call(document.querySelectorAll('#stationsGrid .epg-row'),function(r){return r.textContent.indexOf('Disney')>=0;}).querySelector('.epg-prog.now').click()"); await pg.wait_for_timeout(1500)
        nm = await pg.evaluate("document.getElementById('playerName').textContent.trim()")
        check(nm == 'Popeye Cartoon 2', f'the custom channel plays {nm}')
        check(not errs, f'no page errors {errs[:3]}')
        await b.close()
    print('FAILS', fails); raise SystemExit(1 if fails else 0)
asyncio.run(main())
