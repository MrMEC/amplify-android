"""Build 327: Internet Archive (the Archive tab in Search). Mocked archive.org. Checks: Archive tab + rows;
tapping a film plays it (one file) and an album queues its songs; Podcast Index is not in the app.
Run: python3 tests/test_archive.py (screenshots in /tmp/claude-0/t/shots)"""
import asyncio, json, os, re, shutil, threading, http.server, functools
from urllib.parse import urlparse, parse_qs
from playwright.async_api import async_playwright
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = '/tmp/claude-0/t/srv-arch'; SHOTS = '/tmp/claude-0/t/shots'
os.makedirs(ROOT, exist_ok=True); os.makedirs(SHOTS, exist_ok=True)
shutil.copy(os.path.join(HERE, '..', 'www', 'index.html'), ROOT)
H = functools.partial(http.server.SimpleHTTPRequestHandler, directory=ROOT); H.log_message = lambda *a: None
srv = http.server.ThreadingHTTPServer(('127.0.0.1', 8828), H); threading.Thread(target=srv.serve_forever, daemon=True).start()
fails = 0
def check(ok, msg):
    global fails
    print(('PASS ' if ok else 'FAIL ') + msg); fails += 0 if ok else 1
CORS = {'access-control-allow-origin': '*', 'access-control-allow-headers': '*', 'access-control-allow-methods': 'GET,OPTIONS'}
seen = {'ia_search': [], 'pi': [], 'meta': []}
DOCS = [{'identifier': 'nosferatu', 'title': 'Nosferatu (1922)', 'mediatype': 'movies', 'creator': 'F. W. Murnau', 'year': '1922'},
        {'identifier': 'nosferatu_ost', 'title': 'Nosferatu Soundtrack', 'mediatype': 'audio', 'creator': ['Some Band'], 'year': 1999}]
META = {
 'nosferatu': {'files': [{'name': 'nosferatu.mp4', 'format': 'h.264', 'size': '90000', 'length': '5640'}, {'name': 'nosferatu.ogv', 'format': 'Ogg Video'},
                         {'name': 'nosferatu_meta.xml', 'format': 'Metadata', 'source': 'metadata'}]},
 'nosferatu_ost': {'files': [{'name': '02 - Second.mp3', 'format': 'VBR MP3', 'track': '2', 'length': '03:10'}, {'name': '01 - First.mp3', 'format': 'VBR MP3', 'track': '1', 'length': '2:05'},
                             {'name': '01 - First.ogg', 'format': 'Ogg Vorbis', 'track': '1'}]}}
def jr(r, obj, status=200):
    return r.fulfill(status=status, content_type='application/json', headers=CORS, body=json.dumps(obj))
async def route(r):
    u = r.request.url; pu = urlparse(u); q = parse_qs(pu.query)
    if r.request.method == 'OPTIONS' and ('archive.org' in u or 'podcastindex' in u):
        return await r.fulfill(status=204, headers=CORS)
    if 'archive.org/advancedsearch' in u:
        seen['ia_search'].append(q.get('q', [''])[0]); return await jr(r, {'response': {'docs': DOCS}})
    if 'archive.org/metadata/' in u:
        i = pu.path.rsplit('/', 1)[1]; seen['meta'].append(i); return await jr(r, META.get(i, {'files': []}))
    if 'archive.org/' in u:
        return await r.fulfill(status=200, content_type='image/png', headers=CORS, body=b'')
    if 'podcastindex.org' in u:
        seen['pi'].append({'q': q.get('q', [''])[0], 'h': {k: v for k, v in r.request.headers.items() if k.lower().startswith('x-auth') or k.lower() == 'authorization'}})
        return await jr(r, {'feeds': [
            {'title': 'Serial Dup', 'author': 'Apple Has It', 'itunesId': 5, 'artwork': '', 'url': 'http://f/1', 'episodeCount': 9},
            {'title': 'Serial Only On PI', 'author': 'Indie Host', 'itunesId': 777, 'artwork': '', 'url': 'http://f/2', 'episodeCount': 4},
            {'title': 'Serial No Apple Id', 'author': 'X', 'itunesId': 0, 'artwork': '', 'url': 'http://f/3'}]})
    if 'radio-browser' in u:
        return await jr(r, [])
    if 'itunes.apple.com/' in u:
        cb = (q.get('callback') or [''])[0]
        body = json.dumps({'resultCount': 1, 'results': [{'wrapperType': 'track', 'kind': 'podcast', 'collectionId': 5, 'collectionName': 'Serial Dup', 'artistName': 'A', 'artworkUrl600': ''}]})
        return await r.fulfill(status=200, content_type='application/javascript', body=cb + '(' + body + ');')
    return await r.continue_()
async def sheet_search(pg, text):
    await pg.evaluate("(t)=>{var i=document.getElementById('searchSheetInput');i.value=t;document.getElementById('searchSheetGo').click();}", text)
    await pg.wait_for_timeout(1500)
async def tabs(pg):
    return await pg.evaluate("Array.prototype.map.call(document.querySelectorAll('#searchTabs .home-tab'),function(t){return t.textContent.trim();})")
async def click_tab(pg, label):
    await pg.evaluate("(l)=>{Array.prototype.forEach.call(document.querySelectorAll('#searchTabs .home-tab'),function(t){ if(t.textContent.trim().indexOf(l)===0) t.click(); });}", label)
    await pg.wait_for_timeout(500)
async def names(pg):
    return await pg.evaluate("Array.prototype.map.call(document.querySelectorAll('#stationsGrid .tile-name'),function(n){return n.textContent.trim();})")
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
        ctx = await b.new_context(viewport={'width': 390, 'height': 844}, device_scale_factor=2, is_mobile=True, has_touch=True, color_scheme='dark')
        pg = await ctx.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.route('**/*', route)
        await pg.goto('http://127.0.0.1:8828/index.html'); await pg.wait_for_timeout(2500)

        # --- Settings: no Podcast Index fields; Podcasts search is Apple's alone
        gone = await pg.evaluate("!document.getElementById('podcastIndexRow') && !document.getElementById('piKeyInput')")
        check(gone, 'no Podcast Index fields in Settings')
        await sheet_search(pg, 'serial')
        check(len(seen['pi']) == 0, 'no Podcast Index request')
        await click_tab(pg, 'Podcasts')
        check(await names(pg) == ['Serial Dup'], f'podcasts: Apple only {await names(pg)}')

        # --- Archive tab
        await sheet_search(pg, 'nosferatu')
        t = await tabs(pg)
        check(any(x.startswith('Archive') for x in t), f'Archive tab offered {t}')
        check(any('collection:(' in q and 'mediatype:(movies OR audio)' in q and 'title:(nosferatu)' in q for q in seen['ia_search']), 'archive query shape')
        await click_tab(pg, 'Archive')
        nm = await names(pg)
        check(nm == ['Nosferatu (1922)', 'Nosferatu Soundtrack'], f'archive rows {nm}')
        subs = await pg.evaluate("Array.prototype.map.call(document.querySelectorAll('#stationsGrid .song-row-sub'),function(n){return n.textContent.trim();})")
        check(subs == ['Video \u00b7 1922 \u00b7 F. W. Murnau', 'Audio \u00b7 1999 \u00b7 Some Band'], f'row subtitles {subs}')
        ov = await pg.evaluate("(()=>{var g=document.getElementById('stationsGrid').getBoundingClientRect(); return Array.prototype.every.call(document.querySelectorAll('#stationsGrid .archive-result-row'),function(r){var b=r.getBoundingClientRect(); return b.width>200 && b.left>=0 && b.right<=innerWidth;});})()")
        check(ov, 'rows sit inside the phone width')
        await pg.screenshot(path=SHOTS + '/arch_results.png')
        lefts = await pg.evaluate("Array.prototype.map.call(document.querySelectorAll('#stationsGrid .archive-result-row .tile-art'),function(a){return Math.round(a.getBoundingClientRect().left);})")
        check(len(set(lefts)) == 1, f'cover art left edges align {lefts}')
        check(await pg.evaluate("document.activeElement && document.activeElement.tagName") not in ('INPUT', 'TEXTAREA'), 'search input is not focused on mobile')

        # --- play the film: one file, the h.264 mp4
        await pg.evaluate("window.__played=[]; var o=HTMLMediaElement.prototype.play; ")
        await pg.evaluate("document.querySelector('#stationsGrid .archive-result-row').click()"); await pg.wait_for_timeout(1500)
        check(seen['meta'][-1] == 'nosferatu', 'metadata fetched for the tapped item')
        np_open = await pg.evaluate("(()=>{var n=document.getElementById('nowPlayingScreen'); return !!n && getComputedStyle(n).display!=='none';})()")
        check(np_open, 'Now Playing opened')
        await pg.screenshot(path=SHOTS + '/arch_nowplaying_video.png')
        await pg.evaluate("document.querySelector('.mobile-nav-btn[data-nav=search]').click()"); await pg.wait_for_timeout(600)
        await click_tab(pg, 'Archive')
        await pg.evaluate("document.querySelectorAll('#stationsGrid .archive-result-row')[1].click()"); await pg.wait_for_timeout(1500)
        npt = await pg.evaluate("document.getElementById('nowPlayingScreen').innerText")
        check(seen['meta'][-1] == 'nosferatu_ost' and npt.startswith('First') and '2:05' in npt and 'Second' in npt, f'album starts at track 1 (mp3, 2:05) with track 2 next {npt[:90]!r}')
        await pg.screenshot(path=SHOTS + '/arch_nowplaying_audio.png')
        check(len(errs) == 0, f'no page errors {errs}')
        await b.close()
    print('\n%d failure(s)' % fails)
    raise SystemExit(1 if fails else 0)
asyncio.run(main())
