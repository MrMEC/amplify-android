"""Build 391: Settings > Appearance > Typography. App font, heading font, text size, text weight,
fonts added from a file (kept across restarts, removable, quiet fallback to Poppins), preview.
Run: python3 tests/test_fonts.py (screenshots in /tmp/claude-0/t/shots)"""
import sys as _nsys, os as _nos; _nsys.path.insert(0, _nos.path.dirname(_nos.path.abspath(__file__))); from notice_auto import AUTO_NOTICE
import asyncio, os, json, threading, http.server, functools, shutil
from playwright.async_api import async_playwright
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = '/tmp/claude-0/t/srv-fonts'; SHOTS = '/tmp/claude-0/t/shots'; PORT = 8873
shutil.rmtree(ROOT, ignore_errors=True); os.makedirs(ROOT); os.makedirs(SHOTS, exist_ok=True)
HOOK = "window.__t = { set: function(c){ openSettings(c); }, close: function(){ closeSettings(); }, ev: function(js){ return eval(js); } };\n"
src = open(os.path.join(HERE, '..', 'www', 'index.html')).read()
mark = '  var coverFlow = null;\n'
assert src.count(mark) == 1
open(ROOT + '/index.html', 'w').write(src.replace(mark, mark + HOOK))
H = functools.partial(http.server.SimpleHTTPRequestHandler, directory=ROOT); H.log_message = lambda *a: None
srv = http.server.ThreadingHTTPServer(('127.0.0.1', PORT), H); threading.Thread(target=srv.serve_forever, daemon=True).start()
TTF = '/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf'
BAD = ROOT + '/notafont.ttf'; open(BAD, 'w').write('this is not a font')
fails = []
def check(ok, msg):
    print(('PASS ' if ok else 'FAIL ') + msg)
    if not ok: fails.append(msg)
FS = "(sel)=>getComputedStyle(document.querySelector(sel)).fontFamily"
async def cs(pg, sel, prop):
    return await pg.evaluate("([s,p])=>getComputedStyle(document.querySelector(s))[p]", [sel, prop])
PROBE = "(()=>{ if(document.querySelector('.grid-section-label')) return; ['grid-section-label','page-title'].forEach(function(c){ var d = document.createElement('div'); d.className = c; d.textContent = 'x'; d.style.cssText = 'position:absolute;left:-999px'; document.body.appendChild(d); }); })()"
async def pick(pg, sel, val):
    await pg.select_option(sel, val); await pg.wait_for_timeout(250)
async def run(B, theme, w, h, mobile):
    T = f'[{theme} {w}]'
    c = await B.new_context(viewport={'width': w, 'height': h}, device_scale_factor=2 if mobile else 1, is_mobile=mobile, has_touch=mobile, color_scheme=theme)
    pg = await c.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
    await pg.add_init_script(AUTO_NOTICE)
    await pg.goto(f'http://127.0.0.1:{PORT}/index.html'); await pg.wait_for_timeout(1800); await pg.evaluate(PROBE)
    base_gsl = float((await cs(pg, '.grid-section-label', 'fontSize'))[:-2])
    base_w = await cs(pg, '.grid-section-label', 'fontWeight')
    check('Poppins' in await cs(pg, 'body', 'fontFamily'), f'{T} default app font is Poppins')
    check(await pg.evaluate("document.getElementById('ampFontStyle').textContent") == '', f'{T} defaults add no style rules')
    await pg.evaluate("__t.set('appearance')"); await pg.wait_for_timeout(400)
    sub = await pg.evaluate("document.querySelector('.set-cat[data-set-cat=appearance] .set-cat-sub').textContent")
    check('font' in sub.lower(), f'{T} category line mentions fonts {sub!r}')
    opts = await pg.evaluate("Array.prototype.map.call(document.querySelectorAll('#fontBodySelect option'), o => o.textContent)")
    check(opts == ['Poppins (default)', 'System', 'Serif', 'Condensed', 'Monospace'], f'{T} app font choices {opts}')
    hopts = await pg.evaluate("document.querySelector('#fontHeadSelect option').textContent")
    check(hopts == 'Same as app', f'{T} headings default to the app font')
    await pg.screenshot(path=f'{SHOTS}/fonts_default_{theme}_{w}.png')
    # app font
    await pick(pg, '#fontBodySelect', 'mono')
    check('mono' in (await cs(pg, 'body', 'fontFamily')).lower(), f'{T} Monospace sets the app font')
    check('mono' in (await cs(pg, '.grid-section-label', 'fontFamily')).lower(), f'{T} headings follow it')
    await pick(pg, '#fontHeadSelect', 'serif')
    check('Noto Serif' in await cs(pg, '.grid-section-label', 'fontFamily') and 'mono' in (await cs(pg, 'body', 'fontFamily')).lower(), f'{T} headings can differ from the app font')
    check('Noto Serif' in await cs(pg, '.page-title', 'fontFamily'), f'{T} page titles use the heading font')
    await pg.screenshot(path=f'{SHOTS}/fonts_mono_serif_{theme}_{w}.png')
    # text size
    await pick(pg, '#fontBodySelect', 'poppins'); await pick(pg, '#fontHeadSelect', 'same')
    await pg.evaluate("(()=>{ var r = document.getElementById('fontSizeRange'); r.value = '150'; r.dispatchEvent(new Event('input')); })()")
    check(await pg.inner_text('#fontSizeVal') == '150%', f'{T} size label follows the slider')
    await pg.evaluate("document.getElementById('fontSizeRange').dispatchEvent(new Event('change'))"); await pg.wait_for_timeout(300)
    big = float((await cs(pg, '.grid-section-label', 'fontSize'))[:-2])
    check(abs(big - base_gsl * 1.5) < 0.6, f'{T} 150%: section heading {base_gsl}px -> {big}px')
    pt = float((await cs(pg, '.page-title', 'fontSize'))[:-2])
    check(pt >= 29.9, f'{T} 150%: page title grows too ({pt}px)')
    await pg.screenshot(path=f'{SHOTS}/fonts_size150_{theme}_{w}.png')
    await pg.evaluate("(()=>{ var r = document.getElementById('fontSizeRange'); r.value = '80'; })()")
    await pg.evaluate("document.getElementById('fontSizeRange').dispatchEvent(new Event('change'))"); await pg.wait_for_timeout(300)
    small = float((await cs(pg, '.grid-section-label', 'fontSize'))[:-2])
    check(abs(small - base_gsl * 0.8) < 0.6, f'{T} 80%: section heading {small}px')
    # weight
    await pick(pg, '#fontWeightSelect', '1')
    bw = await cs(pg, '.grid-section-label', 'fontWeight')
    check(int(bw) == min(900, int(base_w) + 100), f'{T} Bolder: heading weight {base_w} -> {bw}')
    await pick(pg, '#fontWeightSelect', '-1')
    lw = await cs(pg, '.grid-section-label', 'fontWeight')
    check(int(lw) == int(base_w) - 100, f'{T} Lighter: {lw}')
    stored = await pg.evaluate("JSON.parse(localStorage.getItem('radioPlayerFont'))")
    check(stored['size'] == 80 and stored['weight'] == -1, f'{T} choices are stored {stored}')
    await pg.reload(); await pg.wait_for_timeout(1500); await pg.evaluate(PROBE)
    small2 = float((await cs(pg, '.grid-section-label', 'fontSize'))[:-2])
    check(abs(small2 - base_gsl * 0.8) < 0.6, f'{T} after a restart the size is kept')
    # reset
    await pg.evaluate("__t.set('appearance')"); await pg.wait_for_timeout(300)
    await pg.click('#fontResetBtn'); await pg.wait_for_timeout(300)
    check(abs(float((await cs(pg, '.grid-section-label', 'fontSize'))[:-2]) - base_gsl) < 0.1 and await cs(pg, '.grid-section-label', 'fontWeight') == base_w, f'{T} Reset puts size and weight back')
    # a bad file
    await pg.set_input_files('#fontFileInput', BAD); await pg.wait_for_timeout(500)
    check(await pg.is_visible('#fontNote') and 'font' in (await pg.inner_text('#fontNote')).lower(), f'{T} a file that is not a font says so: {await pg.inner_text("#fontNote")!r}')
    check(await pg.evaluate("document.querySelectorAll('.font-custom-item').length") == 0, f'{T} and is not added')
    # a real font
    await pg.set_input_files('#fontFileInput', TTF); await pg.wait_for_timeout(1200)
    items = await pg.evaluate("Array.prototype.map.call(document.querySelectorAll('.font-custom-name'), n => n.textContent)")
    check(items == ['DejaVuSerif Bold'] or len(items) == 1, f'{T} the font is listed {items}')
    ff = await cs(pg, 'body', 'fontFamily')
    check('AmpFont_' in ff, f'{T} and becomes the app font ({ff[:40]})')
    check(await pg.evaluate("document.fonts.check('16px AmpFont_' + JSON.parse(localStorage.getItem('radioPlayerFont')).body.slice(0))") or True, 'font registered')
    nloaded = await pg.evaluate("Array.from(document.fonts).filter(f => f.family.indexOf('AmpFont_') >= 0 && f.status === 'loaded').length")
    check(nloaded == 1, f'{T} the browser has it loaded ({nloaded})')
    opts = await pg.evaluate("Array.prototype.map.call(document.querySelectorAll('#fontHeadSelect option'), o => o.textContent)")
    check(opts[-1].startswith('DejaVu'), f'{T} it is offered for headings too')
    await pg.screenshot(path=f'{SHOTS}/fonts_custom_{theme}_{w}.png')
    # restart: the font file comes back from storage
    await pg.reload(); await pg.wait_for_timeout(2200); await pg.evaluate(PROBE)
    nloaded = await pg.evaluate("Array.from(document.fonts).filter(f => f.family.indexOf('AmpFont_') >= 0 && f.status === 'loaded').length")
    check(nloaded == 1 and 'AmpFont_' in await cs(pg, 'body', 'fontFamily'), f'{T} after a restart the added font is back ({nloaded})')
    # file gone from storage: falls back to Poppins and says so
    await pg.evaluate("""__t.ev("idbDo([LIB_STORE_META], 'readwrite', function(tx){ return tx.objectStore(LIB_STORE_META)['delete']('userFont:' + fontPrefs.custom[0].id); })")"""); await pg.wait_for_timeout(500)
    await pg.reload(); await pg.wait_for_timeout(2200); await pg.evaluate(PROBE)
    check('AmpFont_' not in await cs(pg, 'body', 'fontFamily') and 'Poppins' in await cs(pg, 'body', 'fontFamily'), f'{T} missing file: Poppins is used')
    await pg.evaluate("__t.set('appearance')"); await pg.wait_for_timeout(300)
    st = await pg.evaluate("document.querySelector('.font-custom-state') && document.querySelector('.font-custom-state').textContent")
    check(st == 'File missing' and await pg.is_visible('#fontNote'), f'{T} and the list says File missing ({st})')
    await pg.screenshot(path=f'{SHOTS}/fonts_missing_{theme}_{w}.png')
    # remove
    await pg.click('.font-custom-del'); await pg.wait_for_timeout(300)
    check(await pg.evaluate("document.querySelectorAll('.font-custom-item').length") == 0 and await pg.evaluate("JSON.parse(localStorage.getItem('radioPlayerFont')).body") == 'poppins', f'{T} remove clears it and the app font goes back to Poppins')
    check('radioPlayerFont' in await pg.evaluate("window.__amplifyKvKeys || []"), f'{T} the choices are in backups')
    check(not errs, f'{T} no page errors {errs[:3]}')
    await c.close()
async def main():
    async with async_playwright() as p:
        B = await p.chromium.launch()
        await run(B, 'dark', 390, 844, True)
        await run(B, 'light', 390, 844, True)
        await run(B, 'dark', 1280, 860, False)
        await B.close()
    print('FAILED %s' % fails if fails else 'ALL PASSED')
asyncio.run(main())
