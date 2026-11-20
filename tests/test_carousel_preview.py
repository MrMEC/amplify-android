"""Build 702 (Mark): Cover Flow 'covers only' (Details on Home / Details in Albums), a live sticky
preview on Settings > Carousel, compact controls. Run: python3 tests/test_carousel_preview.py"""
import sys, os, json, asyncio, base64, threading, http.server, functools, shutil
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE); from notice_auto import AUTO_NOTICE
from playwright.async_api import async_playwright
ROOT = '/tmp/claude-0/t/srv-carprev'; PORT = 8902; SH = '/tmp/claude-0/t/shots'
shutil.rmtree(ROOT, ignore_errors=True); os.makedirs(ROOT); os.makedirs(SH, exist_ok=True)
HOOK = "window.__t = { set: function(c){ openSettings(c); }, back: function(){ settingsBack(); }, close: function(){ closeSettings(); }, ev: function(js){ return eval(js); } };\n"
src = open(os.path.join(HERE, '..', 'www', 'index.html')).read(); mark = '  var coverFlow = null;\n'; assert src.count(mark) == 1
open(ROOT + '/index.html', 'w').write(src.replace(mark, mark + HOOK))
H = functools.partial(http.server.SimpleHTTPRequestHandler, directory=ROOT); H.log_message = lambda *a: None
srv = http.server.ThreadingHTTPServer(('127.0.0.1', PORT), H); threading.Thread(target=srv.serve_forever, daemon=True).start()
def D(f, t='png'): return f'data:image/{t};base64,' + base64.b64encode(open('/tmp/t/logos/' + f, 'rb').read()).decode()
REC = [{'name': 'Chill Out Radio', 'url': 'https://radio.example/chill', 'favicon': D('photo1.jpg', 'jpeg'), 'stationuuid': 'st-chill'},
       {'name': '2 - WXYZ 7 Springfield', 'url': 'https://tv.example/wxyz.m3u8', 'videoChannel': True, 'favicon': D('logo1.png'), 'stationuuid': 'ch-wxyz'},
       {'name': 'NEWS Now', 'url': 'https://tv.example/news.m3u8', 'videoChannel': True, 'favicon': D('logo3.png'), 'stationuuid': 'ch-news'}]
fails = []
def check(ok, m):
    print(('PASS ' if ok else 'FAIL ') + m)
    if not ok: fails.append(m)
async def run(b, scheme):
    T = f'[{scheme}]'
    car = {'mode': 'flow', 'size': 's', 'tilt': 66, 'reflect': True, 'textPos': 'below', 'heading': True, 'cardSize': 's'}
    seed = "localStorage.setItem('radioPlayerRecent', %s); localStorage.setItem('radioPlayerCarousel', %s); localStorage.setItem('radioPlayerTheme', %s);" % (json.dumps(json.dumps(REC)), json.dumps(json.dumps(car)), json.dumps(scheme))
    ctx = await b.new_context(viewport={'width': 327, 'height': 700}, device_scale_factor=3.3, is_mobile=True, has_touch=True, color_scheme=scheme)
    await ctx.add_init_script(AUTO_NOTICE); await ctx.add_init_script("try{ localStorage.setItem('radioPlayerTourDone','1'); %s }catch(e){}" % seed)
    pg = await ctx.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
    await pg.route('**/*', lambda r: r.continue_() if '127.0.0.1' in r.request.url else r.fulfill(status=200, content_type='application/json', body='[]') if '/json/' in r.request.url else r.abort())
    await pg.goto(f'http://127.0.0.1:{PORT}/index.html'); await pg.wait_for_timeout(2500)
    homeParent = await pg.evaluate("__t.ev('npHero.parentElement.className')")
    await pg.evaluate("__t.set('home-carousel')"); await pg.wait_for_timeout(1000)
    st = await pg.evaluate("""()=>{ var h = __t.ev('npHero'), p = document.getElementById('carPreview'); var r = p.getBoundingClientRect(), hr = h.getBoundingClientRect();
        return { inPrev: p.contains(h), shown: getComputedStyle(h).display, ph: Math.round(r.height), hTop: Math.round(hr.top), hBot: Math.round(hr.bottom), pBot: Math.round(r.bottom), info: getComputedStyle(h.querySelector('.nph-flow-info')).display }; }""")
    print(T, st)
    check(st['inPrev'] and st['shown'] != 'none' and st['hBot'] <= st['pBot'] + 1, f'{T} the carousel shows in the preview, whole')
    check(st['ph'] <= 0.36 * 700 + 20, f'{T} the preview takes about a third of the screen ({st["ph"]}px)')
    edge = await pg.evaluate("""()=>{ var p = document.getElementById('carPreview').getBoundingClientRect(), i = document.getElementById('carPreviewIn').getBoundingClientRect(); return [Math.round(p.left), Math.round(p.right), Math.round(i.left), Math.round(i.right)]; }""")
    check(edge[0] == 0 and edge[1] == 327 and abs(edge[2]) <= 1 and abs(edge[3] - 327) <= 1, f'{T} the preview runs the full width, no side gaps (build 703) {edge}')
    # build 703: tilt 0-90
    await pg.evaluate("(()=>{ var r = document.getElementById('flowTiltRange'); r.value = '0'; r.dispatchEvent(new Event('input', { bubbles: true })); })()"); await pg.wait_for_timeout(300)
    t0 = await pg.evaluate("[document.getElementById('flowTiltRange').min, document.getElementById('flowTiltRange').max, JSON.parse(localStorage.getItem('radioPlayerCarousel')).tilt]")
    check(t0 == ['0', '90', 0], f'{T} tilt goes from 0 to 90 degrees, and 0 is kept {t0}')
    await pg.evaluate("(()=>{ var r = document.getElementById('flowTiltRange'); r.value = '66'; r.dispatchEvent(new Event('input', { bubbles: true })); })()"); await pg.wait_for_timeout(300)
    # sticky while scrolling
    await pg.evaluate("document.getElementById('settingsPanel').scrollTop = 500"); await pg.wait_for_timeout(400)
    top = await pg.evaluate("Math.round(document.getElementById('carPreview').getBoundingClientRect().top)")
    check(55 <= top <= 58, f'{T} the preview stays at the top under the back button when scrolled ({top})')
    await pg.screenshot(path=f'{SH}/carprev-{scheme}-flow-scrolled.png')
    # Details on Home off: no words under the cover, live
    await pg.evaluate("document.getElementById('flowInfoSelectSwitch').click()"); await pg.wait_for_timeout(500)
    st2 = await pg.evaluate("""()=>{ var h = __t.ev('npHero'); return { info: getComputedStyle(h.querySelector('.nph-flow-info')).display, cfg: JSON.parse(localStorage.getItem('radioPlayerCarousel')).flowInfo, ph: Math.round(document.getElementById('carPreview').getBoundingClientRect().height) }; }""")
    check(st2['info'] == 'none' and st2['cfg'] is False, f'{T} Details on Home off: covers only, in the preview at once {st2}')
    check(st2['ph'] <= st['ph'], f'{T} and the preview still fits ({st["ph"]} -> {st2["ph"]})')
    await pg.screenshot(path=f'{SH}/carprev-{scheme}-flow-noinfo.png')
    # Details in Albums off: landscape Cover Flow caption gone
    await pg.evaluate("document.getElementById('cfInfoSelectSwitch').click()"); await pg.wait_for_timeout(300)
    cfi = await pg.evaluate("JSON.parse(localStorage.getItem('radioPlayerCarousel')).cfInfo")
    check(cfi is False, f'{T} Details in Albums is saved separately')
    cap = await pg.evaluate("""__t.ev("(function(){ var host = document.createElement('div'); host.style.cssText = 'position:fixed;left:0;top:0;width:700px;height:320px'; document.body.appendChild(host); var cf = createCoverFlow(host, {}); cf.open(null, {}); var r = host.querySelector('.cf'); var c = host.querySelector('.cf-caption'); var out = { cls: r.className, cap: getComputedStyle(c).display }; return JSON.stringify(out); })()")""")
    print(T, 'cf', cap)
    check('cf-nocap' in cap and '"cap":"none"' in cap, f'{T} Cover Flow (Albums) shows covers only {cap}')
    # Editorial segmented choice live
    await pg.evaluate("document.querySelector('[data-carousel-opt=edit]').click()"); await pg.wait_for_timeout(600)
    await pg.evaluate("document.querySelector('#carouselTextPosSelect + .car-seg button[data-v=above]').click()"); await pg.wait_for_timeout(600)
    ab = await pg.evaluate("[__t.ev('npHero').classList.contains('nph-above'), document.querySelector('#carouselTextPosSelect + .car-seg button[data-v=above]').getAttribute('aria-pressed')]")
    check(ab == [True, 'true'], f'{T} Text: Above (segmented) applies live {ab}')
    await pg.evaluate("document.getElementById('settingsPanel').scrollTop = 0"); await pg.wait_for_timeout(300)
    await pg.screenshot(path=f'{SH}/carprev-{scheme}-edit-above.png')
    # a tap in the preview does not play
    await pg.evaluate("__t.ev('npHero').querySelector('.nph-slide').click()"); await pg.wait_for_timeout(500)
    playing = await pg.evaluate("__t.ev('!!(currentStation && !audio.paused)')")
    check(not playing, f'{T} a tap in the preview plays nothing')
    # None
    await pg.evaluate("document.querySelector('[data-carousel-opt=none]').click()"); await pg.wait_for_timeout(500)
    nn = await pg.evaluate("[!document.getElementById('carPreviewEmpty').hidden, document.getElementById('carPreviewEmpty').textContent]")
    check(nn[0] and 'No carousel' in nn[1], f'{T} None: the preview says there is no carousel {nn}')
    await pg.evaluate("document.querySelector('[data-carousel-opt=flow]').click()"); await pg.wait_for_timeout(500)
    # leaving puts it back on Home
    await pg.evaluate("__t.back()"); await pg.wait_for_timeout(500)
    back = await pg.evaluate("__t.ev('npHero.parentElement.className')")
    check(back == homeParent, f'{T} leaving the page puts the carousel back on Home ({back})')
    await pg.evaluate("__t.set('home-carousel')"); await pg.wait_for_timeout(500)
    await pg.evaluate("__t.close()"); await pg.wait_for_timeout(800)
    hb = await pg.evaluate("[__t.ev('npHero.parentElement.className'), getComputedStyle(__t.ev('npHero')).display]")
    check(hb[0] == homeParent and hb[1] != 'none', f'{T} closing Settings: the carousel is back on Home and showing {hb}')
    await pg.screenshot(path=f'{SH}/carprev-{scheme}-home-after.png')
    check(not errs, f'{T} no page errors {errs[:2]}')
    await ctx.close()
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
        for s in ('light', 'dark'): await run(b, s)
        await b.close()
asyncio.run(main())
print('FAILED: %d' % len(fails) if fails else 'ALL PASS')
raise SystemExit(1 if fails else 0)
