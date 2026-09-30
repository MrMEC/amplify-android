"""Landscape Now Playing: an arrow at the bottom right opens a full-width row of favourite
covers (no labels); the player above shrinks to make room, nothing scrolls, closed by default.
Run: python3 tests/test_land_favs.py (screenshots in /tmp/claude-0/t/shots)"""
import asyncio, os, json
HERE = os.path.dirname(os.path.abspath(__file__))
src = open(os.path.join(HERE, 'test_video_channels.py')).read()
head = src[:src.index('async def rows(pg)')]
head = head.replace("'/tmp/claude-0/t/srv-ch'", "'/tmp/claude-0/t/srv-lf'").replace('8777', '8785')
exec(head)
from playwright.async_api import async_playwright

COLORS = ['c0392b', '2980b9', '27ae60', '8e44ad', 'f39c12', '16a085', 'd35400', '2c3e50', 'e84393', '00b894']
FAVS = [{'name': f'Station {i}', 'urlToResolve': f'https://s{i}.example/live', 'url_resolved': f'https://s{i}.example/live', 'stationuuid': f'u{i}',
         'favicon': f'https://img.example/{c}.png', 'tags': 'jazz', 'country': 'US'} for i, c in enumerate(COLORS)]
FAVS.append({'type': 'artist', 'name': 'Some Artist', 'artistKey': 'some artist'})
PNG = {}
def png(color):
    import zlib, struct
    r, g, b = int(color[0:2], 16), int(color[2:4], 16), int(color[4:6], 16)
    raw = b''.join(b'\x00' + bytes([r, g, b]) * 8 for _ in range(8))
    def ch(t, d): return struct.pack('>I', len(d)) + t + d + struct.pack('>I', zlib.crc32(t + d) & 0xffffffff)
    return b'\x89PNG\r\n\x1a\n' + ch(b'IHDR', struct.pack('>IIBBBBB', 8, 8, 8, 2, 0, 0, 0)) + ch(b'IDAT', zlib.compress(raw)) + ch(b'IEND', b'')

async def route2(r):
    u = r.request.url
    if 'img.example/' in u:
        return await r.fulfill(status=200, content_type='image/png', headers={'Access-Control-Allow-Origin': '*'}, body=png(u.rsplit('/', 1)[-1][:6]))
    return await route(r)

async def geo(pg):
    return await pg.evaluate("""(()=>{var q=function(s){var e=document.querySelector(s);if(!e)return null;var r=e.getBoundingClientRect();return {t:Math.round(r.top),b:Math.round(r.bottom),l:Math.round(r.left),r:Math.round(r.right),h:Math.round(r.height),w:Math.round(r.width)};};
      var sc=document.getElementById('nowPlayingScreen');
      return {art:q('#npArtWrap'), row:q('#npLandFavs'), tog:q('#npLandToggle'), play:q('.np-play-btn'), seek:q('.np-seek'),
        open:sc.classList.contains('lf-open'), scroll:[sc.scrollHeight, sc.clientHeight, document.documentElement.scrollHeight, innerHeight],
        rot:getComputedStyle(document.querySelector('#npLandToggle svg')).transform,
        covers:document.querySelectorAll('#npLandFavsRow .np-land-fav').length,
        labels:document.querySelector('#npLandFavsRow').innerText.trim()};})()""")

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
        ctx = await b.new_context(viewport={'width': 844, 'height': 390}, device_scale_factor=2, is_mobile=True, has_touch=True, color_scheme='dark', locale='en-US')
        await ctx.add_init_script(MOCK)
        await ctx.add_init_script("if(!localStorage.getItem('radioPlayerFavorites')) localStorage.setItem('radioPlayerFavorites', %s);" % repr(json.dumps(FAVS)))
        pg = await ctx.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e) + ' @ ' + (e.stack or '')[:300]))
        await pg.route('**/*', route2)
        await pg.goto('http://127.0.0.1:8785/index.html'); await pg.wait_for_timeout(2500)
        # play the first favourite (portrait), then turn sideways
        await pg.set_viewport_size({'width': 390, 'height': 844}); await pg.wait_for_timeout(600)
        await pg.evaluate("document.querySelector('.mobile-nav-btn[data-nav=home]').click()"); await pg.wait_for_timeout(600)
        await pg.evaluate("Array.prototype.find.call(document.querySelectorAll('.tile'),function(x){return x.dataset.key==='u2';}).click()"); await pg.wait_for_timeout(1000)
        tvis = await pg.evaluate("getComputedStyle(document.getElementById('npLandToggle')).display")
        check(tvis == 'none', f'no arrow in portrait ({tvis})')
        await pg.set_viewport_size({'width': 844, 'height': 390}); await pg.wait_for_timeout(900)
        g0 = await geo(pg)
        bk = await pg.evaluate("getComputedStyle(document.getElementById('npBackBtn')).display")
        check(bk == 'none', f'no down arrow at the top left ({bk})')
        check(not g0['open'] and g0['row']['h'] == 0, f'closed by default {g0["row"]}')
        check(g0['tog']['r'] > 800 and g0['tog']['b'] > 350, f'arrow at the bottom right {g0["tog"]}')
        await pg.screenshot(path=f'{SHOTS}/lf-closed.png')
        # open, mid-animation, then settled
        hs = await pg.evaluate("new Promise(function(res){var o=[];document.getElementById('npLandToggle').click();var t0=performance.now();(function f(){o.push([Math.round(performance.now()-t0),Math.round(document.getElementById('npLandFavs').getBoundingClientRect().height),Math.round(document.getElementById('npArtWrap').getBoundingClientRect().height)]);if(performance.now()-t0<450)requestAnimationFrame(f);else res(o);})();})")
        mids = [h for h in hs if 0 < h[1] < 74]
        check(len(mids) >= 3, f'the row slides open and the player shrinks with it {hs[::3]}')
        await pg.screenshot(path=f'{SHOTS}/lf-opening.png')
        await pg.wait_for_timeout(600)
        g1 = await geo(pg)
        await pg.screenshot(path=f'{SHOTS}/lf-open.png')
        check(g1['open'] and g1['row']['h'] >= 52 and g1['row']['w'] == 844 and g1['row']['l'] == 0, f'the row opens across the whole screen {g1["row"]}')
        check(g1['covers'] == 10 and g1['labels'] == '', f'covers only, no labels, artists left out ({g1["covers"]}, {g1["labels"]!r})')
        check(g1['art']['h'] < g0['art']['h'] and g1['art']['b'] <= g1['row']['t'] and g1['row']['b'] <= 390, f'the player shrinks to fit ({g0["art"]["h"]} -> {g1["art"]["h"]}px)')
        check(g1['scroll'][0] <= g1['scroll'][1] and g1['scroll'][2] <= g1['scroll'][3], f'nothing scrolls {g1["scroll"]}')
        check(g1['play']['b'] <= g1['row']['t'] and g1['tog']['b'] <= g1['row']['t'], f'controls and arrow stay above the row {g1["play"]} {g1["tog"]}')
        check(g1['rot'] != g0['rot'] and g1['rot'] != 'none', f'the arrow turns to point down ({g0["rot"]} -> {g1["rot"]})')
        playing = await pg.evaluate("Array.prototype.map.call(document.querySelectorAll('#npLandFavsRow .np-land-fav.playing'),function(b){return b.dataset.key;})")
        check(playing == ['u2'], f'the playing one is marked {playing}')
        # tap a cover to play it
        await pg.evaluate("document.querySelector('#npLandFavsRow .np-land-fav[data-key=u5]').click()"); await pg.wait_for_timeout(900)
        nm = await pg.evaluate("document.getElementById('npName').textContent")
        playing = await pg.evaluate("Array.prototype.map.call(document.querySelectorAll('#npLandFavsRow .np-land-fav.playing'),function(b){return b.dataset.key;})")
        check(nm == 'Station 5' and playing == ['u5'], f'tapping a cover plays it ({nm!r}, {playing})')
        await pg.screenshot(path=f'{SHOTS}/lf-played.png')
        # close: back to full size
        await pg.evaluate("document.getElementById('npLandToggle').click()"); await pg.wait_for_timeout(700)
        g2 = await geo(pg)
        check(not g2['open'] and g2['row']['h'] == 0 and abs(g2['art']['h'] - g0['art']['h']) <= 1, f'closing restores the size ({g2["art"]["h"]}px)')
        # rotating back and forth starts closed again
        await pg.evaluate("document.getElementById('npLandToggle').click()"); await pg.wait_for_timeout(500)
        await pg.set_viewport_size({'width': 390, 'height': 844}); await pg.wait_for_timeout(600)
        await pg.set_viewport_size({'width': 844, 'height': 390}); await pg.wait_for_timeout(700)
        g3 = await geo(pg)
        check(not g3['open'], 'closed again after turning the phone back')
        # light theme look
        check(not errs, f'no page errors {errs[:3]}')
        await b.close()
    print('ALL PASSED' if not fails else f'FAILED {fails}')
asyncio.run(main())
