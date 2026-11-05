"""Build 453 (Mark): Podcasts gets the count Library's tabs have in the row under the filter box: "N shows" on
Latest, a group, A-Z and Popular; "N episodes" on Continue. And a count follows the filter box: while it
narrows the list, the count is of what is listed (Library: the artists/albums/songs left, each once;
Podcasts' Latest: the shows whose episodes are left), and clearing the box brings the total back.
Phone, dark and light. Run: python3 tests/test_counts.py (screenshots in /tmp/claude-0/t/shots)"""
import os, sys, json, asyncio
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
src = open(os.path.join(HERE, 'test_section_filters.py')).read().split('async def run(')[0]
src = src.replace("os.path.dirname(os.path.abspath(__file__))", repr(HERE)).replace('PORT = 8826', 'PORT = 8898').replace("srv_sf'", "srv_counts'")
src = src.replace('" back: function(){ goBack(); } };', '" back: function(){ goBack(); }, tab: function(t){ podcastTab = t; renderPodcastTabsRow(); renderPodcastsGrid(); }, ev: function(js){ return eval(js); } };')
assert 'tab: function(t)' in src
exec(src)

COUNT = "(()=>{ var e = document.getElementById('resultCount'); if(!e || getComputedStyle(e).display === 'none' || !e.offsetParent) return null; return e.textContent; })()"
ROWBOX = """(()=>{ var e = document.getElementById('resultCount'), b = document.getElementById('secFilter');
  if(!e || !e.offsetParent) return null; var r = e.getBoundingClientRect(), f = b && b.getBoundingClientRect();
  var btns = Array.from(document.querySelectorAll('button')).filter(function(x){ var q = x.getBoundingClientRect(); return x.offsetParent && Math.abs((q.top + q.bottom) / 2 - (r.top + r.bottom) / 2) < 20 && q.left > r.right; });
  return { below: f ? Math.round(r.top - f.bottom) : null, left: Math.round(r.left), onButtonsRow: btns.length > 0, nowrap: e.scrollWidth <= e.clientWidth + 1 }; })()"""

async def run2(vw, vh, scheme):
    tag = f'{scheme} {vw}'
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
        ctx = await b.new_context(viewport={'width': vw, 'height': vh}, device_scale_factor=2, is_mobile=True, has_touch=True, color_scheme=scheme, locale='en-US')
        await ctx.add_init_script(MOCK); await ctx.add_init_script(AUTO_NOTICE)
        await ctx.add_init_script("try{ localStorage.setItem('radioPlayerTheme', %s); }catch(e){}" % json.dumps(scheme))
        pg = await ctx.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.route('**/*', lambda route: route.continue_() if '127.0.0.1' in route.request.url else route.abort())
        await pg.goto(f'http://127.0.0.1:{PORT}/index.html'); await pg.wait_for_timeout(2500)
        await pg.evaluate("""(function(){ var ov=document.getElementById('addMusicOverlay'); if(ov) ov.classList.add('open');
          var btn=document.getElementById('addMusicFolderBtn'); btn.disabled=false; btn.click(); })()""")
        for _ in range(60):
            await pg.wait_for_timeout(500)
            if await pg.evaluate("__t.n()") >= 6: break
        await pg.wait_for_timeout(1500)
        await pg.evaluate("document.getElementById('importPanelClose') && document.getElementById('importPanelClose').click()")

        # ---- Library (build 489): no count on Artists, Albums and Songs -- the sort menu is in its place,
        # filtered or not ----
        SORT = "(()=>{ var b = document.getElementById('libSortBtn'); return b && b.offsetParent ? b.querySelector('.lib-sort-cur').textContent : null; })()"
        for sec, q in (('artists', 'bo'), ('songs', 'carl'), ('albums', 'bob')):
            await pg.evaluate(f"__t.sec('{sec}')"); await pg.wait_for_timeout(1200)
            check(await pg.evaluate(COUNT) is None and await pg.evaluate(SORT) == 'A-Z', f'[{tag}] {sec}: the sort menu, no count {await pg.evaluate(SORT)!r}')
            await typ(pg, q)
            check(await pg.evaluate(COUNT) is None and await pg.evaluate(SORT) == 'A-Z', f'[{tag}] {sec} filtered: still no count')
            await pg.click('#secFilter .sf-clear'); await pg.wait_for_timeout(300)

        # ---- Podcasts ----
        await pg.evaluate("__t.pods()"); await pg.wait_for_timeout(800)
        await pg.evaluate("__t.latest()"); await pg.evaluate("__t.eps()"); await pg.wait_for_timeout(800)
        c = await pg.evaluate(COUNT); box = await pg.evaluate(ROWBOX)
        check(c == '3 shows', f'[{tag}] Latest: "3 shows" (the shows followed) {c!r}')
        check(box and box['onButtonsRow'] and box['below'] is not None and box['below'] >= 0 and box['nowrap'], f'[{tag}] in the row under the filter box, beside its buttons, on one line {box}')
        await pg.screenshot(path=f'{shots}/count-{tag.replace(" ", "-")}-latest.png')
        await typ(pg, 'garden')
        c = await pg.evaluate(COUNT)
        check(c == '1 show', f'[{tag}] Latest filtered: the shows whose episodes are left, "1 show" {c!r}')
        await pg.screenshot(path=f'{shots}/count-{tag.replace(" ", "-")}-latest-filtered.png')
        await pg.click('#secFilter .sf-clear'); await pg.wait_for_timeout(300)
        check(await pg.evaluate(COUNT) == '3 shows', f'[{tag}] cleared: "3 shows" again')
        await pg.evaluate("__t.tab('following')"); await pg.wait_for_timeout(600)
        check(await pg.evaluate(COUNT) == '3 shows', f'[{tag}] A-Z: "3 shows"')
        await typ(pg, 'tech')
        check(await pg.evaluate(COUNT) == '1 show', f'[{tag}] A-Z filtered: "1 show"')
        await pg.click('#secFilter .sf-clear'); await pg.wait_for_timeout(300)
        # a group
        await pg.evaluate("__t.ev(\"podcastCategories.push({ id: 'g1', name: 'Morning', showIds: [100, 102] })\")")
        await pg.evaluate("__t.tab('cat:g1')"); await pg.wait_for_timeout(600)
        c = await pg.evaluate(COUNT)
        check(c == '2 shows', f'[{tag}] a group: the shows in it, "2 shows" {c!r}')
        # Continue: none in progress -> no count
        await pg.evaluate("__t.tab('continue')"); await pg.wait_for_timeout(1200)
        c = await pg.evaluate(COUNT)
        check(c is None, f'[{tag}] Continue with nothing in progress: no count {c!r}')
        # no shows followed: no count
        await pg.evaluate("__t.ev('podcastSubs.length = 0'); __t.tab('latest')"); await pg.wait_for_timeout(600)
        check(await pg.evaluate(COUNT) is None, f'[{tag}] following nothing: no count')
        check(not errs, f'[{tag}] no page errors {errs[:2]}')
        await b.close()

async def main2():
    await run2(390, 844, 'dark')
    await run2(360, 780, 'light')
    print('\nFAILS:', len(fails))
    for f in fails: print(' -', f)
    sys.exit(1 if fails else 0)
asyncio.run(main2())
