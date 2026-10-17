"""Build 240: Settings > Equalizer (Android app): the presets, the player's saved choice shown,
a change sent to the player (setEq), the player's own list used; hidden in a browser. Both
themes at 412 (and 360 with larger text). Based on test_leveling.py.
Run: python3 tests/test_eq_presets.py (screenshots in /tmp/claude-0/t/shots)"""
import sys as _nsys, os as _nos; _nsys.path.insert(0, _nos.path.dirname(_nos.path.abspath(__file__))); from notice_auto import AUTO_NOTICE
import os
_here = os.path.dirname(os.path.abspath(__file__))
_src = open(os.path.join(_here, 'test_leveling.py')).read()
_head = _src[:_src.index('ROW = """')]
_head = _head.replace("PORT = 8829", "PORT = 8843").replace("srv_leveling", "srv_eq")
_head = _head.replace("""   setLeveling: function(o){""", """   setEq: function(o){ window.__eq = (window.__eq || []).concat([o]); if(o.preset) window.__eqNow = o.preset; return Promise.resolve({ preset: window.__eqNow || 'Rock', presets: ['Off','Bass Boost','Treble Boost','Vocal','Rock','Pop','Jazz','Classical','Dance','Late Night'] }); },
   setLeveling: function(o){""")
__file__ = os.path.join(_here, 'test_leveling.py')
exec(_head)

ROW = """() => { var r = document.getElementById('eqRow'), s = document.getElementById('eqSelect');
  var b = r.getBoundingClientRect(), l = r.querySelector('.settings-label'), sb = s.getBoundingClientRect();
  return { shown: getComputedStyle(r).display !== 'none' && b.height > 0, value: s.value, options: Array.from(s.options).map(o => o.value),
    label: l.textContent, oneLine: l.getBoundingClientRect().height < 30, inView: b.right <= innerWidth && b.left >= 0 && sb.right <= innerWidth,
    nextToLeveling: !!(document.getElementById('levelingRow').compareDocumentPosition(r) & Node.DOCUMENT_POSITION_FOLLOWING) }; }"""


async def run(p, scheme, width, big):
    b = await p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
    ctx = await b.new_context(viewport={'width': width, 'height': 900}, device_scale_factor=2, is_mobile=True, has_touch=True, color_scheme=scheme)
    await ctx.add_init_script(MOCK); await ctx.add_init_script(AUTO_NOTICE)
    await ctx.add_init_script("try{ localStorage.setItem('radioPlayerTheme', '%s'); }catch(e){}" % scheme)
    pg = await ctx.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
    await pg.route('**/*', lambda route: route.continue_() if '127.0.0.1' in route.request.url else route.abort())
    await pg.goto(f'http://127.0.0.1:{PORT}/index.html'); await pg.wait_for_timeout(2500)
    if big:
        await pg.add_style_tag(content='.settings-label{font-size:20px !important} .settings-select{font-size:19px !important}')
    T = f'[{scheme} {width}{" big" if big else ""}]'
    await pg.evaluate('__t.settings()'); await pg.wait_for_timeout(800)
    r = await pg.evaluate(ROW)
    check(r['shown'] and r['label'] == 'Equalizer' and r['oneLine'] and r['inView'] and r['nextToLeveling'], f'{T} Settings shows Equalizer, after Volume leveling {r}')
    check(r['value'] == 'Rock', f'{T} it shows the player\'s saved preset (Rock) {r["value"]}')
    check(len(r['options']) == 10 and r['options'][0] == 'Off' and 'Bass Boost' in r['options'] and 'Late Night' in r['options'], f'{T} the presets {r["options"]}')
    await pg.evaluate("document.getElementById('eqRow').scrollIntoView({block:'center'})"); await pg.wait_for_timeout(300)
    await pg.screenshot(path=f'{shots}/eq-settings-{scheme}-{width}{"-big" if big else ""}.png')
    await pg.select_option('#eqSelect', 'Bass Boost'); await pg.wait_for_timeout(300)
    eq = await pg.evaluate('window.__eq')
    check(eq[-1] == {'preset': 'Bass Boost'} and (await pg.evaluate(ROW))['value'] == 'Bass Boost', f'{T} choosing Bass Boost sends it to the player {eq[-1:]}')
    await pg.select_option('#eqSelect', 'Off'); await pg.wait_for_timeout(300)
    check((await pg.evaluate('window.__eq'))[-1] == {'preset': 'Off'}, f'{T} and Off turns it off')
    check(not errs, f'{T} no page errors {errs[:3]}')
    await b.close()


async def browser(p):
    b = await p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
    ctx = await b.new_context(viewport={'width': 1280, 'height': 900})
    pg = await ctx.new_page()
    await pg.route('**/*', lambda route: route.continue_() if '127.0.0.1' in route.request.url else route.abort())
    await pg.goto(f'http://127.0.0.1:{PORT}/index.html'); await pg.wait_for_timeout(2000)
    await pg.evaluate('__t.settings()'); await pg.wait_for_timeout(500)
    check(not (await pg.evaluate(ROW))['shown'], '[browser] no Equalizer row without the Android player')
    await b.close()


async def main():
    async with async_playwright() as p:
        await run(p, 'dark', 412, False)
        await run(p, 'light', 412, False)
        await run(p, 'light', 360, True)
        await browser(p)
    print('ALL PASSED' if not fails else f'FAILED {fails}')

asyncio.run(main())
