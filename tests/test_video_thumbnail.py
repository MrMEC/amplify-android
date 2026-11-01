"""Build 380: Choose Thumbnail. Long-press a music video's tile and any frame can be its picture:
the frame shows at the slider's point (a quick frame while dragging, the exact one on letting
go), +/- 1s nudges it, Use This Frame saves it (the phone cuts it), and every tile of that video
shows it at once and after a reload; Use Automatic puts the original back. A plain tap still
plays; the long press doesn't. Phone, dark and light.
Run: python3 tests/test_video_thumbnail.py (screenshots in /tmp/claude-0/t/shots)"""
import os, sys, json, asyncio
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
_setup = open(os.path.join(HERE, 'test_music_videos.py')).read().split('fails = []')[0]
_setup = _setup.replace('PORT = 8814', 'PORT = 8883').replace("root = '/tmp/claude-0/t/srv_mv'", "root = '/tmp/claude-0/t/srv_tp'")
_setup = _setup.replace("os.path.dirname(__file__)", repr(HERE))
_setup = _setup.replace("   addListener: function(n, f)", """   videoFrame: function(o){ (window.__frames = window.__frames || []).push(o);
     if(window.__frameFail) return Promise.reject(new Error('setDataSource failed'));
     if(o.save) return Promise.resolve({ thumb: 'http://127.0.0.1:8883/still2.jpg', duration: 125000 });
     return new Promise(function(r){ setTimeout(function(){ r({ data: 'http://127.0.0.1:8883/still2.jpg?ms=' + o.ms, duration: 125000 }); }, 60); }); },
   videoFrameDone: function(){ window.__frameDone = (window.__frameDone || 0) + 1; return Promise.resolve({}); },
   addListener: function(n, f)""")
exec(_setup)
ff('-f', 'lavfi', '-i', 'color=c=orange:s=320x180', '-frames:v', '1', f'{root}/still2.jpg')
fails = []
def check(cond, msg):
    print(('PASS ' if cond else 'FAIL ') + msg)
    if not cond: fails.append(msg)
async def longpress(pg, sel, ms=650, idx=0):
    cdp = await pg.context.new_cdp_session(pg)
    r = await pg.evaluate("(a)=>{ var b = document.querySelectorAll(a[0])[a[1]].getBoundingClientRect(); return [b.left + b.width / 3, b.top + b.height / 2]; }", [sel, idx])
    pt = [{'x': r[0], 'y': r[1]}]
    await cdp.send('Input.dispatchTouchEvent', {'type': 'touchStart', 'touchPoints': pt})
    await pg.wait_for_timeout(ms)
    await cdp.send('Input.dispatchTouchEvent', {'type': 'touchEnd', 'touchPoints': []})
    await pg.wait_for_timeout(300)
async def run(b, theme):
    T = f'[{theme}]'
    ctx = await b.new_context(viewport={'width': 390, 'height': 844}, device_scale_factor=2, is_mobile=True, has_touch=True, color_scheme=theme)
    await ctx.add_init_script(MOCK); await ctx.add_init_script(AUTO_NOTICE)
    pg = await ctx.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
    await pg.route('**/*', lambda route: route.continue_() if '127.0.0.1' in route.request.url else route.abort())
    await pg.goto(f'http://127.0.0.1:{PORT}/index.html'); await pg.wait_for_timeout(2500)
    await pg.evaluate("""(function(){ var ov=document.getElementById('addMusicOverlay'); if(ov) ov.classList.add('open');
      var btn=document.getElementById('addMusicFolderBtn'); btn.disabled=false; btn.click(); })()""")
    for _ in range(60):
        await pg.wait_for_timeout(500)
        if len(await pg.evaluate('__t.tracks()')) >= 8: break
    await pg.wait_for_timeout(1500)
    await pg.evaluate("__t.openArtist('Bob')"); await pg.wait_for_timeout(1500)
    await pg.evaluate("document.getElementById('importOverlay').classList.remove('open'); document.querySelector('#stationsGrid .mv-tile').scrollIntoView({block:'center'})"); await pg.wait_for_timeout(300)
    # a long press opens Choose Thumbnail; nothing plays
    await longpress(pg, '#stationsGrid .mv-tile')
    st = await pg.evaluate("[!!document.getElementById('thumbPickOverlay') && document.getElementById('thumbPickOverlay').classList.contains('open'), document.getElementById('tpName') && document.getElementById('tpName').textContent, window.__loaded ? 1 : 0]")
    check(st[0] and st[1] == 'Great Song · Bob' and st[2] == 0, f'{T} long press: Choose Thumbnail for that video, and it does not play {st}')
    await pg.wait_for_timeout(300)
    f0 = await pg.evaluate("[window.__frames.map(function(f){ return [f.ms, !!f.exact]; }), document.getElementById('tpImg').src, document.getElementById('tpTime').textContent, document.getElementById('tpAuto').hidden, document.getElementById('tpFrame').classList.contains('loading')]")
    check(f0[0] == [[20833, False], [20833, True]] and 'ms=20833' in f0[1] and f0[2] == '0:20.8 / 2:05' and f0[3] and not f0[4], f'{T} opens on the automatic point (a sixth in): a quick frame, then the exact one; the spinner stops {f0}')
    one = await pg.evaluate("(function(){ var t = document.getElementById('tpTime'); return t.getBoundingClientRect().height < 26; })()")
    check(one, f'{T} the time stays on one line')
    await pg.screenshot(path=f'{SHOTS_DIR}/tp-{theme}-open.png')
    # dragging: quick frames, only the latest asked for while one is coming; letting go: exact
    await pg.evaluate("""(function(){ var s = document.getElementById('tpSlider'); window.__frames = [];
      [30000, 40000, 50000, 60000].forEach(function(v){ s.value = v; s.dispatchEvent(new Event('input')); });
      s.value = 61200; s.dispatchEvent(new Event('change')); })()""")
    await pg.wait_for_timeout(500)
    fr = await pg.evaluate("window.__frames.map(function(f){ return [f.ms, !!f.exact]; })")
    check(fr[0] == [30000, False] and fr[-1] == [61200, True] and len(fr) <= 3, f'{T} dragging asks for quick frames, only the latest while one is coming; letting go the exact one {fr}')
    await pg.click('#tpFwd'); await pg.wait_for_timeout(300)
    t = await pg.evaluate("[document.getElementById('tpTime').textContent, window.__frames[window.__frames.length - 1].ms]")
    check(t == ['1:02.2 / 2:05', 62200], f'{T} + 1s nudges it {t}')
    await pg.screenshot(path=f'{SHOTS_DIR}/tp-{theme}-moved.png')
    # save
    await pg.click('#tpSave'); await pg.wait_for_timeout(500)
    sv = await pg.evaluate("""(function(){ var f = window.__frames[window.__frames.length - 1]; var t = document.querySelector('#stationsGrid .mv-tile img');
      return [f.save, f.ms, document.getElementById('thumbPickOverlay').classList.contains('open'), t && t.getAttribute('src'), window.__frameDone || 0]; })()""")
    check(sv[0] and sv[1] == 62200 and not sv[2] and sv[3] and 'still2.jpg' in sv[3] and sv[4] >= 1, f'{T} Use This Frame: saved at that point, the tile shows it, the reader is let go {sv}')
    await pg.screenshot(path=f'{SHOTS_DIR}/tp-{theme}-saved.png')
    # it stays after a reload, and the Watch tiles show it too
    await pg.reload(); await pg.wait_for_timeout(3000)
    await pg.evaluate("__t.openArtist('Bob')"); await pg.wait_for_timeout(1200)
    src = await pg.evaluate("(document.querySelector('#stationsGrid .mv-tile img') || {}).src || ''")
    check('still2.jpg' in src, f'{T} kept after a reload {src}')
    # Use Automatic puts the original back
    await pg.evaluate("document.querySelector('#stationsGrid .mv-tile').scrollIntoView({block:'center'})"); await pg.wait_for_timeout(200)
    await longpress(pg, '#stationsGrid .mv-tile'); await pg.wait_for_timeout(300)
    auto = await pg.evaluate("document.getElementById('tpAuto').hidden")
    await pg.click('#tpAuto'); await pg.wait_for_timeout(500)
    src = await pg.evaluate("(document.querySelector('#stationsGrid .mv-tile img') || {}).src || ''")
    check(auto is False and src.endswith('/still.jpg'), f'{T} Use Automatic shows with a chosen still, and puts the original back {auto} {src}')
    # a frame that can't be read: said so, and the spinner stops
    await longpress(pg, '#stationsGrid .mv-tile'); await pg.wait_for_timeout(300)
    await pg.evaluate("window.__frameFail = true; var s = document.getElementById('tpSlider'); s.value = 90000; s.dispatchEvent(new Event('change'))"); await pg.wait_for_timeout(400)
    er = await pg.evaluate("[document.getElementById('tpMsg').hidden, document.getElementById('tpMsg').textContent, document.getElementById('tpFrame').classList.contains('loading')]")
    check(er[0] is False and 'setDataSource failed' in er[1] and not er[2], f'{T} a frame that fails says why, and the spinner stops {er}')
    await pg.screenshot(path=f'{SHOTS_DIR}/tp-{theme}-error.png')
    await pg.evaluate("window.__frameFail = false"); await pg.click('#tpFwd'); await pg.wait_for_timeout(300)
    check(await pg.evaluate("document.getElementById('tpMsg').hidden"), f'{T} and the message goes once a frame comes')
    await pg.click('#tpCancel'); await pg.wait_for_timeout(200)
    # the Music Videos page: the row's menu has Choose Thumbnail, and a long press on a row works too
    await pg.evaluate("__t.mvPage('Bob')"); await pg.wait_for_timeout(1000)
    await pg.evaluate("document.querySelector('.mv-row .row-more-btn').click()"); await pg.wait_for_timeout(300)
    mi = await pg.evaluate("getComputedStyle(document.getElementById('rowMenuThumb')).display")
    await pg.screenshot(path=f'{SHOTS_DIR}/tp-{theme}-rowmenu.png')
    await pg.evaluate("document.getElementById('rowMenuThumb').click()"); await pg.wait_for_timeout(400)
    op = await pg.evaluate("[document.getElementById('thumbPickOverlay').classList.contains('open'), document.getElementById('tpName').textContent]")
    check(mi != 'none' and op[0] and op[1].startswith('Great Song'), f'{T} Music Videos page: the row menu has Choose Thumbnail, and it opens the picker {mi} {op}')
    await pg.click('#tpSave'); await pg.wait_for_timeout(500)
    rs = await pg.evaluate("(document.querySelector('.mv-row .vep-thumb img') || {}).src || ''")
    check('still2.jpg' in rs, f'{T} the row shows the new picture {rs}')
    await pg.evaluate("document.querySelectorAll('.mv-row')[1].scrollIntoView({block:'center'})"); await pg.wait_for_timeout(200)
    await longpress(pg, '.mv-row', idx=1)
    op = await pg.evaluate("[document.getElementById('thumbPickOverlay').classList.contains('open'), document.getElementById('tpName').textContent, window.__loaded ? 1 : 0]")
    check(op[0] and op[1].startswith('Live at Wembley') and op[2] == 0, f'{T} a long press on a row opens it too, without playing {op}')
    await pg.click('#tpCancel'); await pg.wait_for_timeout(200)
    # a plain tap still plays
    await pg.tap('.mv-row'); await pg.wait_for_timeout(1000)
    check(await pg.evaluate("!!window.__loaded"), f'{T} a tap still plays the video')
    check(not errs, f'{T} no page errors {errs}')
    await ctx.close()
SHOTS_DIR = shots
async def main2():
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
        for th in ('dark', 'light'): await run(b, th)
        await b.close()
    print('ALL PASSED' if not fails else f'FAILS {len(fails)}')
asyncio.run(main2())
