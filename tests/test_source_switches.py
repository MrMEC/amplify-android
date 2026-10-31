"""Build 351: Settings > Sources can turn off Pluto TV and archive.org. Off, the source's channels
leave Live TV (and are kept, coming back when it is turned on), its Add Channels tab goes, and
with archive.org off Search asks archive.org nothing. Phone, light and dark.
Run: python3 tests/test_source_switches.py (screenshots in /tmp/claude-0/t/shots)"""
import sys as _nsys, os as _nos; _nsys.path.insert(0, _nos.path.dirname(_nos.path.abspath(__file__))); from notice_auto import AUTO_NOTICE
import asyncio, os, json, threading, http.server, functools, shutil
from playwright.async_api import async_playwright
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = '/tmp/claude-0/t/srv-sources'; SHOTS = '/tmp/claude-0/t/shots'
PORT = 8871
shutil.rmtree(ROOT, ignore_errors=True); os.makedirs(ROOT); os.makedirs(SHOTS, exist_ok=True)
HOOK = ("window.__t = { watch: function(){ openVideoHome(); videoTab = 'channels'; renderVideoHome(); },"
        " add: function(){ openAddChannelsPage(); }, set: function(c){ openSettings(c); }, close: function(){ closeSettings(); }, vis: function(){ return visibleVideoChannels().map(function(c){ return c.name; }); },"
        " search: function(q){ runSearch(q); return searchState.archivePending; } };\n")
src = open(os.path.join(HERE, '..', 'www', 'index.html')).read()
mark = '  var coverFlow = null;\n'
assert src.count(mark) == 1
open(ROOT + '/index.html', 'w').write(src.replace(mark, mark + HOOK))
H = functools.partial(http.server.SimpleHTTPRequestHandler, directory=ROOT); H.log_message = lambda *a: None
srv = http.server.ThreadingHTTPServer(('127.0.0.1', PORT), H); threading.Thread(target=srv.serve_forever, daemon=True).start()
CH = [{'id': 'p1', 'name': 'Pluto Westerns', 'url': 'https://cfd-v4-service-channel-stitcher-use1-1.prd.pluto.tv/stitch/hls/channel/abc123/master.m3u8', 'src': 'pluto', 'logo': '', 'cats': ['Movies'], 'catNames': ['Movies'], 'country': '', 'addedAt': 1},
      {'id': 'a1', 'name': 'Sci-Fi & Horror', 'url': 'amplify-archive:c:SciFi_Horror', 'src': 'archive', 'logo': '', 'cats': ['archive.org'], 'catNames': ['archive.org'], 'country': '', 'addedAt': 2, 'archive': {'collection': 'SciFi_Horror'}},
      {'id': 'n1', 'name': 'ABC News Live', 'url': 'https://x.example/abc.m3u8', 'src': 'iptv', 'logo': '', 'cats': ['news'], 'catNames': ['News'], 'country': 'US', 'addedAt': 3}]
SEED = "try{ localStorage.setItem('radioPlayerVideoChannels', %s); }catch(e){}" % json.dumps(json.dumps(CH))
fails = []
def check(ok, msg):
    print(('PASS ' if ok else 'FAIL ') + msg)
    if not ok: fails.append(msg)
async def run(B, theme):
    T = f'[{theme}]'
    c = await B.new_context(viewport={'width': 390, 'height': 844}, device_scale_factor=2, is_mobile=True, has_touch=True, color_scheme=theme)
    pg = await c.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
    await pg.add_init_script(AUTO_NOTICE)
    pg_first = True
    await c.add_init_script("if(!sessionStorage.getItem('seeded')){ sessionStorage.setItem('seeded','1'); " + SEED + " }")
    await pg.goto(f'http://127.0.0.1:{PORT}/index.html'); await pg.wait_for_timeout(1800)
    vis = await pg.evaluate('__t.vis()')
    check(set(vis) == {'Pluto Westerns', 'Sci-Fi & Horror', 'ABC News Live'}, f'{T} all three channels to start {vis}')
    # Settings > Sources
    await pg.evaluate("__t.set('sources')"); await pg.wait_for_timeout(300)
    await pg.screenshot(path=f'{SHOTS}/sources_{theme}.png')
    sub = await pg.evaluate("document.querySelector('.set-cat[data-set-cat=sources] .set-cat-sub').textContent")
    check('Pluto' in sub and 'archive' in sub, f'{T} category line names them {sub!r}')
    await pg.select_option('#plutoSourceSelect', 'off'); await pg.wait_for_timeout(200)
    vis = await pg.evaluate('__t.vis()')
    check(vis == ['ABC News Live', 'Sci-Fi & Horror'] or set(vis) == {'ABC News Live', 'Sci-Fi & Horror'}, f'{T} Pluto off: its channel leaves Live TV {vis}')
    await pg.select_option('#archiveSourceSelect', 'off'); await pg.wait_for_timeout(200)
    vis = await pg.evaluate('__t.vis()')
    check(vis == ['ABC News Live'], f'{T} archive.org off too: only the other channel {vis}')
    stored = await pg.evaluate("JSON.parse(localStorage.getItem('radioPlayerVideoChannels')).length")
    check(stored == 3, f'{T} the channels are kept ({stored})')
    await pg.evaluate("__t.close()")
    await pg.evaluate('__t.add()'); await pg.wait_for_timeout(500)
    tabs = await pg.evaluate("Array.prototype.map.call(document.querySelectorAll('.ch-tools .home-tab'), function(b){ return b.textContent; })")
    check('Pluto' not in tabs and 'Archive.org' not in tabs, f'{T} Add Channels has no Pluto or Archive.org tab {tabs}')
    await pg.screenshot(path=f'{SHOTS}/sources_addch_off_{theme}.png')
    pending = await pg.evaluate("__t.search('night')")
    check(pending is False, f'{T} Search asks archive.org nothing ({pending})')
    # after a restart it stays off
    await pg.reload(); await pg.wait_for_timeout(1500)
    vis = await pg.evaluate('__t.vis()')
    check(vis == ['ABC News Live'], f'{T} still off after a restart {vis}')
    sel = await pg.evaluate("[document.getElementById('plutoSourceSelect').value, document.getElementById('archiveSourceSelect').value]")
    check(sel == ['off', 'off'], f'{T} Settings shows Off {sel}')
    # back on
    await pg.evaluate("__t.set('sources')"); await pg.wait_for_timeout(200)
    await pg.select_option('#plutoSourceSelect', 'on'); await pg.select_option('#archiveSourceSelect', 'on'); await pg.wait_for_timeout(200)
    vis = await pg.evaluate('__t.vis()')
    check(len(vis) == 3, f'{T} back on: all three again {vis}')
    await pg.evaluate("__t.close()"); await pg.evaluate('__t.add()'); await pg.wait_for_timeout(400)
    tabs = await pg.evaluate("Array.prototype.map.call(document.querySelectorAll('.ch-tools .home-tab'), function(b){ return b.textContent; })")
    check('Pluto' in tabs and 'Archive.org' in tabs, f'{T} tabs back {tabs}')
    check(not errs, f'{T} no page errors {errs}')
    await c.close()
async def main():
    async with async_playwright() as p:
        B = await p.chromium.launch()
        for th in ('dark', 'light'): await run(B, th)
        await B.close()
    print('ALL PASSED' if not fails else f'FAILS {len(fails)}')
asyncio.run(main())
