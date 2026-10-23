"""Build 288 (Mark: show times unreadable; widen them, especially sideways): a half hour is about 1.75
of the space across a phone held upright (was a fixed 124px) and 2.25 sideways; the guide redraws at
the new width when the phone turns. Run: python3 tests/test_b288.py (screenshots in /tmp/claude-0/t/shots)"""
import sys as _nsys, os as _nos; _nsys.path.insert(0, _nos.path.dirname(_nos.path.abspath(__file__)))
src = open(_nos.path.join(_nos.path.dirname(_nos.path.abspath(__file__)), 'test_live_channels_editor.py')).read()
src = src[:src.index('async def run2(')].replace('PORT = 8863', 'PORT = 8887').replace("srv-livech2'", "srv-b288'")
exec(src)
import sys
M = """(()=>{ const g = document.querySelector('#stationsGrid .epg'); const labels = Array.from(g.querySelectorAll('.epg-head-times span')).slice(0, 2).map(e => e.getBoundingClientRect().left);
  const row = Array.from(g.querySelectorAll('.epg-row')).find(r => r.dataset.chUrl === 'amplify-live:office'); const bl = Array.from(row.querySelectorAll('.epg-prog')).slice(1, 3);
  const t = bl[0].querySelector('.epg-t'), sub = bl[0].querySelector('.epg-s');
  return { slot: Math.round(labels[1] - labels[0]), ep: bl.map(b => Math.round(b.getBoundingClientRect().width)), title: t.textContent, titleFits: t.scrollWidth <= t.clientWidth + 1, subFits: sub.scrollWidth <= sub.clientWidth + 1,
    land: document.body.classList.contains('epg-land'), vw: innerWidth }; })()"""
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
        ctx = await b.new_context(viewport={'width': 390, 'height': 844}, device_scale_factor=3, is_mobile=True, has_touch=True, color_scheme='dark', timezone_id='America/New_York')
        await ctx.add_init_script(MOCK); await ctx.add_init_script(AUTO_NOTICE); await ctx.add_init_script(SEED)
        pg = await ctx.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.route('**/*', route)
        await pg.goto(f'http://127.0.0.1:{PORT}/index.html'); await pg.wait_for_timeout(2500)
        await pg.evaluate("document.querySelector('.mobile-nav-btn[data-nav=video]').click()"); await pg.wait_for_timeout(1500)
        m = await pg.evaluate(M); print('upright', m)
        check(m['slot'] == round((390 - 80) / 1.75) and m['ep'][0] >= 120, f'[upright] a half hour {m["slot"]}px (was 124), a 22-minute episode {m["ep"]}px (was 87)')
        check(m['titleFits'] and m['subFits'], f'[upright] "{m["title"]}" and its code read in full {m}')
        await pg.screenshot(path=f'{SHOTS}/b288-upright.png')
        # turn the phone
        await pg.set_viewport_size({'width': 844, 'height': 390}); await pg.wait_for_timeout(1500)
        m2 = await pg.evaluate(M); print('sideways', m2)
        check(m2['slot'] == round((844 - 80) / 2.25) and m2['ep'][0] >= 240, f'[sideways] redrawn wider: a half hour {m2["slot"]}px, a 22-minute episode {m2["ep"]}px')
        check(m2['titleFits'] and m2['subFits'], f'[sideways] titles read in full {m2}')
        await pg.screenshot(path=f'{SHOTS}/b288-sideways.png')
        await pg.set_viewport_size({'width': 390, 'height': 844}); await pg.wait_for_timeout(1500)
        m3 = await pg.evaluate(M)
        check(m3['slot'] == m['slot'], f'[upright again] back to {m3["slot"]}px')
        # the now line sits where the time says
        nl = await pg.evaluate("""(()=>{ const g = document.querySelector('#stationsGrid .epg'), t0 = +g.dataset.t0, line = g.querySelector('.epg-now'); const want = 80 + (Date.now() - t0) / 1800000 * %d - 1;
          return [parseFloat(line.style.left), want]; })()""" % m3['slot'])
        check(abs(nl[0] - nl[1]) < 3, f'the now line matches the wider half hours {nl}')
        check(not errs, f'no page errors {errs[:2]}')
        await b.close()
    print('ALL PASSED' if not fails else f'{fails} FAILED')
    sys.exit(1 if fails else 0)
asyncio.run(main())
