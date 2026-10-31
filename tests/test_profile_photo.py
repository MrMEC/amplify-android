"""Build 364: the profile photo can be moved and zoomed before it's saved. A 600x400 picture,
red on the left and blue on the right: it opens centred in a round frame; a one-finger drag
moves it (real touch events), a two-finger pinch zooms it, the slider zooms it; Save cuts what's
in the circle (the saved picture shows the side that was dragged into view); opening Edit
Profile again puts the picture back where it was left. Phone, dark and light.
Run: python3 tests/test_profile_photo.py (screenshots in /tmp/claude-0/t/shots)"""
import sys as _nsys, os as _nos; _nsys.path.insert(0, _nos.path.dirname(_nos.path.abspath(__file__))); from notice_auto import AUTO_NOTICE
import asyncio, os, threading, http.server, functools, shutil, subprocess
from playwright.async_api import async_playwright
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = '/tmp/claude-0/t/srv-pfphoto'; SHOTS = '/tmp/claude-0/t/shots'; PORT = 8875
shutil.rmtree(ROOT, ignore_errors=True); os.makedirs(ROOT); os.makedirs(SHOTS, exist_ok=True)
HOOK = "window.__t = { ev: function(js){ return eval(js); } };\n"
src = open(os.path.join(HERE, '..', 'www', 'index.html')).read()
mark = '  var coverFlow = null;\n'; assert src.count(mark) == 1
open(ROOT + '/index.html', 'w').write(src.replace(mark, mark + HOOK))
subprocess.run(['ffmpeg', '-loglevel', 'error', '-y', '-f', 'lavfi', '-i', 'color=c=red:s=300x400', '-f', 'lavfi', '-i', 'color=c=blue:s=300x400',
                '-filter_complex', '[0][1]hstack', '-frames:v', '1', ROOT + '/rb.png'], check=True)
H = functools.partial(http.server.SimpleHTTPRequestHandler, directory=ROOT); H.log_message = lambda *a: None
srv = http.server.ThreadingHTTPServer(('127.0.0.1', PORT), H); threading.Thread(target=srv.serve_forever, daemon=True).start()
fails = []
def check(ok, msg):
    print(('PASS ' if ok else 'FAIL ') + msg)
    if not ok: fails.append(msg)
CENTER = """(()=>new Promise(function(res){ var p = JSON.parse(localStorage.getItem('radioPlayerProfile') || '{}'); var i = new Image();
  i.onload = function(){ var c = document.createElement('canvas'); c.width = i.width; c.height = i.height; var g = c.getContext('2d'); g.drawImage(i, 0, 0);
    function px(x, y){ var d = g.getImageData(x, y, 1, 1).data; return d[0] > 150 && d[2] < 100 ? 'red' : d[2] > 150 && d[0] < 100 ? 'blue' : 'mix'; }
    res([i.width, px(Math.round(i.width/2), Math.round(i.height/2)), px(3, Math.round(i.height/2)), px(i.width-4, Math.round(i.height/2))]); };
  i.src = p.photo; }))()"""
async def touch(cdp, kind, pts):
    await cdp.send('Input.dispatchTouchEvent', {'type': kind, 'touchPoints': [{'x': x, 'y': y, 'id': i} for i, (x, y) in enumerate(pts)]})
async def run(B, theme):
    T = f'[{theme}]'
    c = await B.new_context(viewport={'width': 390, 'height': 844}, device_scale_factor=2, is_mobile=True, has_touch=True, color_scheme=theme)
    await c.add_init_script(AUTO_NOTICE)
    pg = await c.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
    cdp = await c.new_cdp_session(pg)
    await pg.goto(f'http://127.0.0.1:{PORT}/index.html'); await pg.wait_for_timeout(2000)
    await pg.tap('#hamburgerBtn'); await pg.wait_for_timeout(300)
    await pg.tap('#pfAvatarBtn'); await pg.wait_for_timeout(300)
    check(await pg.evaluate("document.getElementById('pfCrop').hidden"), f'{T} no photo yet: no frame')
    await pg.set_input_files('#pfPhotoInput', ROOT + '/rb.png'); await pg.wait_for_timeout(700)
    st = await pg.evaluate("[!document.getElementById('pfCrop').hidden, document.getElementById('pfZoom').value, getComputedStyle(document.getElementById('pfCropStage')).borderRadius]")
    check(st[0] and st[1] == '1', f'{T} a chosen photo opens in the round frame at no zoom {st}')
    await pg.screenshot(path=f'{SHOTS}/pfphoto-{theme}-frame.png')
    box = await pg.evaluate("(()=>{ var r = document.getElementById('pfCropStage').getBoundingClientRect(); return [r.left, r.top, r.width]; })()")
    cx, cy = box[0] + box[2] / 2, box[1] + box[2] / 2
    # one finger: drag right by 100px (more of the red left side comes into view)
    await touch(cdp, 'touchStart', [(cx, cy)])
    for i in range(1, 11): await touch(cdp, 'touchMove', [(cx + i * 10, cy)])
    await touch(cdp, 'touchEnd', [])
    await pg.wait_for_timeout(200)
    tr = await pg.evaluate("document.getElementById('pfCropImg').style.transform")
    check('translate(0px' in tr, f'{T} the drag moved the picture (stopped at its left edge) {tr}')
    await pg.screenshot(path=f'{SHOTS}/pfphoto-{theme}-dragged.png')
    await pg.tap('#pfEditSave'); await pg.wait_for_timeout(500)
    r = await pg.evaluate(CENTER)
    check(r[0] == 320 and r[2] == 'red' and r[1] == 'red', f'{T} saved: a 320px picture, red at its middle (dragged to the left side) {r}')
    # reopen: placement remembered; pinch to zoom
    await pg.tap('#pfAvatarBtn'); await pg.wait_for_timeout(600)
    tr2 = await pg.evaluate("document.getElementById('pfCropImg').style.transform")
    check('translate(0px' in tr2, f'{T} Edit Profile again: the picture is where it was left {tr2}')
    await touch(cdp, 'touchStart', [(cx - 20, cy), (cx + 20, cy)])
    for i in range(1, 11): await touch(cdp, 'touchMove', [(cx - 20 - i * 5, cy), (cx + 20 + i * 5, cy)])
    await touch(cdp, 'touchEnd', [])
    await pg.wait_for_timeout(200)
    z = float(await pg.evaluate("document.getElementById('pfZoom').value"))
    check(2.2 < z < 3.8, f'{T} a two-finger pinch zooms in (and the slider follows) {z}')
    await pg.screenshot(path=f'{SHOTS}/pfphoto-{theme}-pinched.png')
    # slider back to 1, then to the far right side by dragging left
    await pg.evaluate("var z = document.getElementById('pfZoom'); z.value = '1'; z.dispatchEvent(new Event('input'))")
    await touch(cdp, 'touchStart', [(cx, cy)])
    for i in range(1, 21): await touch(cdp, 'touchMove', [(cx - i * 10, cy)])
    await touch(cdp, 'touchEnd', [])
    await pg.evaluate("var z = document.getElementById('pfZoom'); z.value = '1.5'; z.dispatchEvent(new Event('input'))")
    await pg.wait_for_timeout(600)   # a person reaching for Save after a quick drag
    await pg.tap('#pfEditSave'); await pg.wait_for_timeout(500)
    r = await pg.evaluate(CENTER)
    check(r[0] == 320 and r[1] == 'blue' and r[3] == 'blue', f'{T} dragged to the right side and zoomed with the slider: blue in the middle and at the right {r}')
    p = await pg.evaluate("JSON.parse(localStorage.getItem('radioPlayerProfile'))")
    check(p.get('photoSrc', '').startswith('data:image/jpeg') and abs(p['crop']['z'] - 1.5) < 0.01, f'{T} the original and its placement are kept {p.get("crop")}')
    check(await pg.evaluate("!!document.querySelector('#hbAvatar img') && !!document.querySelector('#pfAvatar img')"), f'{T} the header and the profile show the new picture')
    # Remove
    await pg.tap('#pfAvatarBtn'); await pg.wait_for_timeout(400)
    await pg.tap('#pfPhotoRemove'); await pg.wait_for_timeout(100)
    await pg.tap('#pfEditSave'); await pg.wait_for_timeout(300)
    p = await pg.evaluate("JSON.parse(localStorage.getItem('radioPlayerProfile'))")
    check(not p.get('photo') and not p.get('photoSrc'), f'{T} Remove takes the photo away')
    check(not errs, f'{T} no page errors {errs}')
    await c.close()
async def main():
    async with async_playwright() as p:
        B = await p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
        for th in ('dark', 'light'): await run(B, th)
        await B.close()
    print('ALL PASSED' if not fails else f'FAILS {len(fails)}')
asyncio.run(main())
