"""Build 241: the Daily Mix, Discover, Hear It Again and Artist Videos rows on Home keep their
scroll position. Swiped sideways (a finger, CDP touch) each row stays where it was left, also when
Home redraws its sections meanwhile (something played, a favourite changed, the mixes' related
artists arriving), and when the row's own contents haven't changed. 412 wide, both themes.
Run: python3 tests/test_daily_rows_scroll.py (screenshots in /tmp/claude-0/t/shots)"""
import sys as _nsys, os as _nos; _nsys.path.insert(0, _nos.path.dirname(_nos.path.abspath(__file__))); from notice_auto import AUTO_NOTICE
import os
_here = os.path.dirname(os.path.abspath(__file__))
_src = open(os.path.join(_here, 'test_daily_mixes.py')).read()
_head = _src[:_src.index('async def run(theme):')]
_head = _head.replace("PORT = 8803", "PORT = 8845").replace("srv_daily", "srv_dailyscroll")
_head = _head.replace('HOOK = ("window.__d = {', 'HOOK = ("window.__r = { redraw: function(){ renderRecentSection(); }, daily: function(){ renderDailyHome(); } };" "window.__d = {', 1)
__file__ = os.path.join(_here, 'test_daily_mixes.py')
exec(_head)

POS = """Array.from(document.querySelectorAll('.daily-home-section')).filter(s => s.style.display !== 'none').map(s => {
  var g = s.querySelector('.tile-grid'); return { id: s.dataset.daily, left: Math.round(g.scrollLeft), max: g.scrollWidth - g.clientWidth }; })"""


async def swipe(pg, cdp, sel):
    r = await pg.evaluate("(s)=>{ var g=document.querySelector(s); g.scrollIntoView({block:'center'}); var b=g.getBoundingClientRect(); return {x: b.left + b.width*0.8, y: b.top + b.height*0.4}; }", sel)
    await pg.wait_for_timeout(300)
    pt = lambda x: [{'x': x, 'y': r['y'], 'id': 1}]
    await cdp.send('Input.dispatchTouchEvent', {'type': 'touchStart', 'touchPoints': pt(r['x'])})
    for i in range(1, 11):
        await cdp.send('Input.dispatchTouchEvent', {'type': 'touchMove', 'touchPoints': pt(r['x'] - 25 * i)})
        await pg.wait_for_timeout(16)
    await cdp.send('Input.dispatchTouchEvent', {'type': 'touchEnd', 'touchPoints': []})
    await pg.wait_for_timeout(900)


async def run(theme):
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
        ctx = await b.new_context(viewport={'width': 412, 'height': 900}, device_scale_factor=2, is_mobile=True, has_touch=True, color_scheme=theme)
        await ctx.add_init_script(MOCK); await ctx.add_init_script(AUTO_NOTICE)
        await ctx.add_init_script("try{ localStorage.setItem('radioPlayerTheme', %s); }catch(e){}" % json.dumps(theme))
        pg = await ctx.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.route('**/*', lambda route: route.continue_() if '127.0.0.1' in route.request.url else route.abort())
        cdp = await ctx.new_cdp_session(pg)
        await pg.goto(f'http://127.0.0.1:{PORT}/index.html'); await pg.wait_for_timeout(2500)
        await pg.evaluate("""(function(){ var ov=document.getElementById('addMusicOverlay'); if(ov) ov.classList.add('open');
          var btn=document.getElementById('addMusicFolderBtn'); btn.disabled=false; btn.click(); })()""")
        for _ in range(90):
            await pg.wait_for_timeout(500)
            if await pg.evaluate("__d.n()") >= len(SONGS): break
        await pg.evaluate("document.getElementById('addMusicOverlay').classList.remove('open')")
        await pg.evaluate('__d.plays(); __d.vid(); __d.reset();')
        await pg.evaluate("try{ hideImportPanel(); setStatus('', false); }catch(e){}")
        await pg.evaluate('__d.home()'); await pg.wait_for_timeout(2500)
        T = f'[{theme}]'
        rows = await pg.evaluate(POS)
        check(len(rows) >= 7 and all(r['max'] > 50 for r in rows if r['id'] != 'videos'), f'{T} the rows scroll sideways {[(r["id"], r["max"]) for r in rows]}')
        for r in rows:
            if r['max'] < 50: continue
            sel = f'.daily-home-section[data-daily="{r["id"]}"] .tile-grid'
            await swipe(pg, cdp, sel)
            left = await pg.evaluate("(s)=>Math.round(document.querySelector(s).scrollLeft)", sel)
            check(left > 40, f'{T} {r["id"]}: a swipe moves the row ({left}px)')
            # Home redraws its sections (as when something plays) while the row is scrolled
            await pg.evaluate('__r.redraw()'); await pg.wait_for_timeout(300)
            await pg.evaluate('__r.daily()'); await pg.wait_for_timeout(300)
            left2 = await pg.evaluate("(s)=>Math.round(document.querySelector(s).scrollLeft)", sel)
            check(abs(left2 - left) <= 2, f'{T} {r["id"]}: it stays there when Home redraws ({left} -> {left2})')
        # every other sideways row on Home, too
        moved = await pg.evaluate("""(()=>{ var out=[]; document.querySelectorAll('.home-row > .tile-grid').forEach(function(g, i){
          var max = g.scrollWidth - g.clientWidth; if(max < 60 || !g.offsetParent) return; g.scrollTo({ left: Math.min(150, max), behavior: 'instant' }); g.dataset.t = i; out.push([i, Math.round(g.scrollLeft), (g.closest('[id]')||{}).id || g.id]); }); return out; })()""")
        await pg.evaluate('__r.redraw()'); await pg.wait_for_timeout(500)
        after = await pg.evaluate("(()=>{ var o={}; document.querySelectorAll('.home-row > .tile-grid[data-t]').forEach(function(g){ o[g.dataset.t] = Math.round(g.scrollLeft); }); return o; })()")
        lost = [(m[2], m[1], after.get(str(m[0]))) for m in moved if abs((after.get(str(m[0])) or 0) - m[1]) > 2]
        check(len(moved) >= 8 and not lost, f'{T} all {len(moved)} sideways rows on Home keep their place when it redraws {lost}')
        await pg.screenshot(path=f'{shots}/dailyscroll-{theme}.png')
        check(not errs, f'{T} no page errors {errs[:3]}')
        await b.close()


async def main():
    await run('dark')
    await run('light')
    print('ALL PASSED' if not fails else f'FAILED {fails}')

asyncio.run(main())
