"""Build 415: "Find better cover" (station More menus -> the picture picker, sharpest first, each with
its size; choosing one saves it) and the song on air as a station's cover when it has no real logo.
Run: python3 tests/test_find_cover.py (screenshots in /tmp/claude-0/t/shots)"""
import asyncio, json, os, re, shutil, threading, http.server, functools, subprocess
from playwright.async_api import async_playwright
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = '/tmp/claude-0/t/srv-fc'; SHOTS = '/tmp/claude-0/t/shots'
shutil.rmtree(ROOT, ignore_errors=True); os.makedirs(ROOT); os.makedirs(SHOTS, exist_ok=True)
html = open(os.path.join(HERE, '..', 'www', 'index.html')).read()
mark = '  function renderStationArt(container, station){'
assert html.count(mark) == 1
html = html.replace(mark, "  window.__fc = { open: openFindBetterCover, rowMenu: function(a, t){ openRowMenu(a, t, {}); }, findable: isFindableStation, setCur: function(s){ currentStation = s; }, onAir: setOnAir, art: function(){ return onAirArt; }, np: function(){ toggleNpMenu(); return [document.getElementById('npFindCoverBtn').style.display, JSON.stringify(npTarget() && npTarget().name)]; } };\n" + mark, 1)
open(ROOT + '/index.html', 'w').write(html)
H = functools.partial(http.server.SimpleHTTPRequestHandler, directory=ROOT); H.log_message = lambda *a: None
srv = http.server.ThreadingHTTPServer(('127.0.0.1', 8841), H); threading.Thread(target=srv.serve_forever, daemon=True).start()
def tpng(name, w, h):
    path = f'{ROOT}/{name}'
    subprocess.run(['ffmpeg', '-loglevel', 'error', '-y', '-f', 'lavfi', '-i', f'testsrc2=size={w}x{h}', '-frames:v', '1', path], check=True)
    return open(path, 'rb').read()
PNGS = {'fav48.png': tpng('fav48.png', 48, 48), 'touch180.png': tpng('touch180.png', 180, 180), 'icon512.png': tpng('icon512.png', 512, 512),
        'banner.png': tpng('banner.png', 1200, 630), 'cover.png': tpng('cover.png', 500, 500)}
HOME = '<html><head><link rel="apple-touch-icon" sizes="180x180" href="/touch180.png"><link rel="manifest" href="/site.webmanifest"><meta property="og:image" content="/banner.png"></head></html>'
MANI = json.dumps({'icons': [{'src': '/icon512.png', 'sizes': '512x512'}]})
CORS = {'access-control-allow-origin': '*'}
DEEZER = json.dumps({'data': [{'title': 'Blue Skies', 'artist': {'name': 'Ella Vale'}, 'album': {'title': 'Blue Skies', 'cover_big': 'https://cdn.example/cover.png'}}]})
fails = []
def check(ok, msg):
    print(('PASS ' if ok else 'FAIL ') + msg)
    if not ok: fails.append(msg)
STN = {'name': 'Alpha FM', 'homepage': 'https://a.radio.example/', 'urlToResolve': 'https://a.radio.example/live', 'stationuuid': 'alpha', 'favicon': 'https://a.radio.example/fav48.png', 'tags': 'pop'}
NOLOGO = {'name': 'Quiet Waves', 'homepage': '', 'urlToResolve': 'https://q.radio.example/live', 'stationuuid': 'quiet', 'favicon': '', 'tags': 'chill'}
LOCAL = {'name': 'Some Song', 'artist': 'X', 'album': 'Y', 'uri': 'content://x/1', 'type': 'local', 'localTrack': True, 'urlToResolve': ''}

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
        ctx = await b.new_context(viewport={'width': 390, 'height': 844}, device_scale_factor=2, is_mobile=True, has_touch=True, color_scheme='dark')
        await ctx.add_init_script("if(!localStorage.getItem('__seeded')){ localStorage.setItem('__seeded','1'); localStorage.setItem('radioPlayerTourSeen','1'); localStorage.setItem('radioPlayerFavorites', %s); }" % repr(json.dumps([STN, NOLOGO])))
        pg = await ctx.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
        async def route(r):
            u = r.request.url
            if u.startswith('http://127.0.0.1:8841'): await r.continue_(); return
            m = re.match(r'https://(a\.radio|cdn)\.example(/.*)?$', u)
            if m:
                path = m.group(2) or '/'; name = path.lstrip('/')
                if m.group(1) == 'a.radio' and path == '/': await r.fulfill(status=200, headers={**CORS, 'content-type': 'text/html'}, body=HOME); return
                if path == '/site.webmanifest': await r.fulfill(status=200, headers={**CORS, 'content-type': 'application/json'}, body=MANI); return
                if name in PNGS: await r.fulfill(status=200, headers={**CORS, 'content-type': 'image/png'}, body=PNGS[name]); return
                await r.fulfill(status=404, body='no'); return
            if 'api.deezer.com' in u: await r.fulfill(status=200, headers={**CORS, 'content-type': 'application/json'}, body=DEEZER); return
            await r.abort()
        await pg.route('**/*', route)
        await pg.goto('http://127.0.0.1:8841/index.html'); await pg.wait_for_timeout(2500)
        # which items are findable
        f = await pg.evaluate("(a)=>[window.__fc.findable(a[0]), window.__fc.findable(a[1]), window.__fc.findable(a[2]), window.__fc.findable({name:'Ch', urlToResolve:'http://x/l.m3u8', videoChannel:true})]", [STN, NOLOGO, LOCAL])
        check(f == [True, True, False, False], f'only directory stations offer Find better cover {f}')
        # the row menu
        await pg.evaluate("document.querySelector('.mobile-nav-btn[data-nav=home]').click()"); await pg.wait_for_timeout(900)
        await pg.evaluate("(t)=>{ var a=document.createElement('button'); a.id='anch'; a.textContent='more'; a.style.cssText='position:fixed;top:300px;right:20px;z-index:9;'; document.body.appendChild(a); window.__fc.rowMenu(a, [t]); }", STN)
        await pg.wait_for_timeout(300)
        vis = await pg.evaluate("getComputedStyle(document.getElementById('rowMenuCover')).display !== 'none'")
        check(vis, 'a station row menu shows Find better cover')
        await pg.screenshot(path=f'{SHOTS}/findcover-menu.png')
        await pg.evaluate("document.getElementById('rowMenuCover').click()")
        await pg.wait_for_timeout(5000)
        tiles = await pg.evaluate("Array.prototype.map.call(document.querySelectorAll('#artSuggestGrid .art-suggest-tile'), function(t){ return [t.hidden, (t.querySelector('.art-suggest-badge')||{}).textContent, t.title, t.querySelector('img').src.split('/').pop()]; })")
        print(tiles)
        shown = [t for t in tiles if not t[0]]
        sizes = [int(t[1].split()[0]) for t in shown if t[1].endswith(' px')]
        check(any('\u00d7' in t[1] for t in shown), 'a wide picture shows its real size')
        check(len(shown) >= 3 and sizes == sorted(sizes, reverse=True) and sizes[0] == 512, f'covers found, sharpest first, each with its size {sizes}')
        title = await pg.evaluate("document.getElementById('artUrlTitle').textContent")
        check(title == 'Better Covers', f'the picker is titled {title}')
        await pg.screenshot(path=f'{SHOTS}/findcover-grid.png')
        # choose the 512px one
        await pg.evaluate("document.querySelector('#artSuggestGrid .art-suggest-tile:not([hidden])').click()")
        await pg.wait_for_timeout(1500)
        saved = await pg.evaluate("JSON.parse(localStorage.getItem('radioPlayerCustomArt')||'{}')")
        check(any(str(v).endswith('icon512.png') for v in saved.values()), f'choosing a cover saves it {list(saved.values())[:1]}')
        # --- song on air for a station with no logo
        await pg.evaluate("(s)=>{ window.__fc.setCur(s); }", NOLOGO)
        await pg.evaluate("window.__fc.onAir({title:'Blue Skies', artist:'Ella Vale'})")
        await pg.wait_for_timeout(2500)
        art = await pg.evaluate("window.__fc.art()")
        check(art and art['url'].endswith('cover.png'), f'the song cover is found {art}')
        src = await pg.evaluate("(document.querySelector('#playerIcon img')||{}).src || ''")
        check(src.endswith('cover.png'), f'the player bar wears the song cover {src}')
        await pg.screenshot(path=f'{SHOTS}/findcover-song.png')
        # the next title names no artist: nothing is asked and the song cover goes
        await pg.evaluate("window.__fc.onAir({title:'Station Promo', artist:''})")
        await pg.wait_for_timeout(800)
        src2 = await pg.evaluate("(document.querySelector('#playerIcon img')||{}).src || ''")
        check(not src2.endswith('cover.png') and not await pg.evaluate("window.__fc.art()"), f'a title with no artist drops the song cover ({src2})')
        # the Now Playing menu offers it for a station, and not for a song
        npm = await pg.evaluate("window.__fc.np()")
        check(npm[0] == '', f'the Now Playing menu shows Find better cover for a station {npm}')
        await pg.evaluate("document.getElementById('npMenu').classList.remove('open')")
        # build 416: a station with a real logo shows the song cover too
        await pg.evaluate("(s)=>{ window.__fc.setCur(s); }", STN)
        await pg.evaluate("window.__fc.onAir({title:'Blue Skies', artist:'Ella Vale'})")
        await pg.wait_for_timeout(1500)
        check(bool(await pg.evaluate("window.__fc.art()")), 'a station with its own logo also shows the song cover')
        await pg.evaluate("window.__fc.onAir({title:'', artist:''})")
        await pg.wait_for_timeout(600)
        check(not await pg.evaluate("window.__fc.art()"), 'and falls back to the station cover when nothing is named')
        check(not errs, f'no page errors {errs[:3]}')
        await b.close()
    print('FAILS:', fails)
asyncio.run(main())
