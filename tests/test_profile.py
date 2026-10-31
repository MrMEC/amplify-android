"""Build 360: on a phone the menu button opens the profile in place of the menu: name and
photo (Edit Profile, kept after a restart), the app's own numbers, shortcuts that go where
they say and close the profile, the first eight favorites with names, and Settings over it
(back returns to the profile). A wide screen keeps its side panel. Phone dark and light.
Run: python3 tests/test_profile.py (screenshots in /tmp/claude-0/t/shots)"""
import sys as _nsys, os as _nos; _nsys.path.insert(0, _nos.path.dirname(_nos.path.abspath(__file__))); from notice_auto import AUTO_NOTICE
import asyncio, os, json, threading, http.server, functools, shutil, subprocess
from playwright.async_api import async_playwright
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = '/tmp/claude-0/t/srv-profile'; SHOTS = '/tmp/claude-0/t/shots'; PORT = 8874
shutil.rmtree(ROOT, ignore_errors=True); os.makedirs(ROOT); os.makedirs(SHOTS, exist_ok=True)
HOOK = "window.__t = { ev: function(js){ return eval(js); } };\n"
src = open(os.path.join(HERE, '..', 'www', 'index.html')).read()
mark = '  var coverFlow = null;\n'; assert src.count(mark) == 1
open(ROOT + '/index.html', 'w').write(src.replace(mark, mark + HOOK))
subprocess.run(['ffmpeg', '-loglevel', 'error', '-y', '-f', 'lavfi', '-i', 'testsrc2=s=600x400:d=1', '-frames:v', '1', ROOT + '/me.jpg'], check=True)
H = functools.partial(http.server.SimpleHTTPRequestHandler, directory=ROOT); H.log_message = lambda *a: None
srv = http.server.ThreadingHTTPServer(('127.0.0.1', PORT), H); threading.Thread(target=srv.serve_forever, daemon=True).start()
ST = [{'name': n, 'urlToResolve': 'http://x/%d' % i, 'favicon': '', 'tags': '80s', 'stationuuid': 'u%d' % i} for i, n in enumerate(
    ["80's 80's", 'Motown Radio', 'Positively Radio', '80s80s Alternative', "80's Sitcom Flashback", '24 Hour Free Movies', 'ABC', '80s80s Bowie', 'Ninth Station'])]
SEED = ("if(!sessionStorage.getItem('s')){ sessionStorage.setItem('s','1'); localStorage.setItem('radioPlayerFavorites', %s);"
        " localStorage.setItem('radioPlayerArtistPlays', JSON.stringify({motown:{name:'The Supremes',count:42,last:1},b:{name:'Prince',count:9,last:1}}));"
        " localStorage.setItem('radioPlayerSongPlays', JSON.stringify({a:[30,1],b:[12,1]})); localStorage.setItem('radioPlayerArtistPlaysReset1', String(Date.UTC(2026,7,22))); }") % json.dumps(json.dumps(ST))
fails = []
def check(ok, msg):
    print(('PASS ' if ok else 'FAIL ') + msg)
    if not ok: fails.append(msg)
async def run(B, theme):
    T = f'[{theme}]'
    c = await B.new_context(viewport={'width': 390, 'height': 844}, device_scale_factor=2, is_mobile=True, has_touch=True, color_scheme=theme)
    await c.add_init_script(AUTO_NOTICE); await c.add_init_script(SEED)
    pg = await c.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
    await pg.goto(f'http://127.0.0.1:{PORT}/index.html'); await pg.wait_for_timeout(2200)
    await pg.tap('#hamburgerBtn'); await pg.wait_for_timeout(400)
    st = await pg.evaluate("[document.getElementById('profileOverlay').classList.contains('open'), document.querySelector('.sidebar-scroll').classList.contains('open'), getComputedStyle(document.getElementById('profileOverlay')).zIndex]")
    check(st[0] and not st[1], f'{T} the menu button opens the profile, not the old menu {st}')
    info = await pg.evaluate("""[document.getElementById('pfName').textContent, document.getElementById('pfSince').textContent,
      Array.prototype.map.call(document.querySelectorAll('.pf-stat'), function(s){ return s.textContent; }),
      Array.prototype.map.call(document.querySelectorAll('.pf-fav-name'), function(s){ return s.textContent; })]""")
    check(info[0] == 'Add your name', f'{T} no name yet: "Add your name" {info[0]!r}')
    check(info[1] == 'Listening since August 2026', f'{T} listening since the first counted play {info[1]!r}')
    check(info[2] == ['—Artists', '42Songs played', 'The SupremesTop artist'], f'{T} numbers from the app {info[2]}')
    check(len(info[3]) == 8 and info[3][0] == "80's 80's", f'{T} first eight favorites, named {info[3]}')
    fit = await pg.evaluate("Array.prototype.every.call(document.querySelectorAll('.pf-stat-v'), function(v){ return v.scrollWidth <= v.clientWidth + 1; })")
    check(fit, f'{T} no number is cut off (a long top artist shrinks)')
    await pg.screenshot(path=f'{SHOTS}/profile-{theme}-top.png')
    await pg.evaluate("document.getElementById('pfSettingsBtn').scrollIntoView({block:'end'})"); await pg.wait_for_timeout(200)
    await pg.screenshot(path=f'{SHOTS}/profile-{theme}-bottom.png')
    # Edit Profile
    await pg.evaluate("document.getElementById('profilePage').scrollTop = 0"); await pg.wait_for_timeout(100)
    await pg.tap('#pfEditBtn'); await pg.wait_for_timeout(300)
    await pg.fill('#pfNameInput', 'Mark')
    await pg.set_input_files('#pfPhotoInput', ROOT + '/me.jpg'); await pg.wait_for_timeout(600)
    await pg.screenshot(path=f'{SHOTS}/profile-{theme}-edit.png')
    await pg.tap('#pfEditSave'); await pg.wait_for_timeout(300)
    av = await pg.evaluate("[document.getElementById('pfName').textContent, !!document.querySelector('#pfAvatar img'), document.querySelector('#pfAvatar img') && document.querySelector('#pfAvatar img').naturalWidth]")
    check(av[0] == 'Mark' and av[1] and av[2] == 320, f'{T} name and a 320px square photo saved {av}')
    await pg.screenshot(path=f'{SHOTS}/profile-{theme}-named.png')
    # Settings over it, back returns to the profile
    await pg.tap('#pfSettingsBtn'); await pg.wait_for_timeout(300)
    check(await pg.evaluate("document.getElementById('settingsOverlay').classList.contains('open')"), f'{T} Settings opens over the profile')
    await pg.tap('#settingsCloseBtn'); await pg.wait_for_timeout(300)
    check(await pg.evaluate("document.getElementById('profileOverlay').classList.contains('open') && !document.getElementById('settingsOverlay').classList.contains('open')"), f'{T} back from Settings: the profile again')
    # a shortcut goes there and closes the profile
    await pg.tap('.pf-link[data-pf-go=stations]'); await pg.wait_for_timeout(500)
    r = await pg.evaluate("[document.getElementById('profileOverlay').classList.contains('open'), document.getElementById('stationsHeading').textContent]")
    check(r == [False, 'My Stations'], f'{T} My Stations shortcut {r}')
    await pg.tap('#hamburgerBtn'); await pg.wait_for_timeout(300)
    await pg.tap('#pfFavAll'); await pg.wait_for_timeout(500)
    r = await pg.evaluate("[document.getElementById('profileOverlay').classList.contains('open'), document.getElementById('stationsHeading').textContent]")
    check(r == [False, 'Favorites'], f'{T} See all opens Favorites {r}')
    await pg.tap('#hamburgerBtn'); await pg.wait_for_timeout(300)
    await pg.tap('#profileCloseBtn'); await pg.wait_for_timeout(200)
    check(not await pg.evaluate("document.getElementById('profileOverlay').classList.contains('open')"), f'{T} the close button puts it away')
    await pg.reload(); await pg.wait_for_timeout(1800)
    await pg.tap('#hamburgerBtn'); await pg.wait_for_timeout(300)
    check(await pg.evaluate("document.getElementById('pfName').textContent") == 'Mark' and await pg.evaluate("!!document.querySelector('#pfAvatar img')"), f'{T} name and photo kept after a restart')
    check(not errs, f'{T} no page errors {errs}')
    await c.close()
async def wide(B):
    c = await B.new_context(viewport={'width': 1400, 'height': 900})
    await c.add_init_script(AUTO_NOTICE)
    pg = await c.new_page()
    await pg.goto(f'http://127.0.0.1:{PORT}/index.html'); await pg.wait_for_timeout(1800)
    vis = await pg.evaluate("getComputedStyle(document.querySelector('.sidebar-scroll')).display !== 'none' && !document.getElementById('profileOverlay').classList.contains('open')")
    check(vis, '[wide] the side panel stays on a wide screen')
    await c.close()
async def main():
    async with async_playwright() as p:
        B = await p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
        for th in ('dark', 'light'): await run(B, th)
        await wide(B)
        await B.close()
    print('ALL PASSED' if not fails else f'FAILS {len(fails)}')
asyncio.run(main())
