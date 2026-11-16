"""Build 653: the channel editor redesign, at Mark's phone size (327 x 709, dpr 3.3).
 - one page that scrolls (no list box with its own scrollbar), Order / Commercials / Guide text first, Content last
 - Commercials and Guide text notes are short; Guide text is a single line
 - Save sits on a sticky bar above the bottom tabs, always on screen
 - archive.org results load by themselves as the end comes into view, added under the rows already there (place kept)
Run: python3 tests/test_live_editor_redesign.py   (shots in /tmp/claude-0/t/shots)"""
import os, sys, json, asyncio
HERE = os.path.dirname(os.path.abspath(__file__))
src = open(os.path.join(HERE, 'test_live_manage_select.py')).read()
head = src[:src.index('\nasync def main():')]
exec(head)
TOTAL = 95
def docs(page):
    lo = (page - 1) * 30
    return [{'identifier': 'sesame%d' % i, 'title': 'Sesame Street - Season %d' % i, 'mediatype': 'movies', 'creator': 'Sesame Workshop', 'year': '2008', 'downloads': 1000 - i} for i in range(lo, min(lo + 30, TOTAL))]
PAGES = []
async def route3(r):
    u = r.request.url; pu = urlparse(u)
    if 'archive.org' in u and 'advancedsearch' in u:
        q = parse_qs(pu.query); pgn = int(q.get('page', ['1'])[0]); PAGES.append(pgn)
        return await r.fulfill(status=200, content_type='application/json', headers=CORS, body=json.dumps({'response': {'numFound': TOTAL, 'docs': docs(pgn)}}))
    return await route2(r)
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
        ctx = await b.new_context(viewport={'width': W, 'height': H_}, device_scale_factor=3.3, is_mobile=True, has_touch=True, color_scheme='dark', locale='en-US', timezone_id='America/New_York')
        await ctx.add_init_script(MOCK); await ctx.add_init_script(AUTO_NOTICE); await ctx.add_init_script(SEED2)
        pg = await ctx.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.route('**/*', route3)
        await pg.goto(f'http://127.0.0.1:{PORT}/index.html'); await pg.wait_for_timeout(3000)
        await pg.evaluate("document.querySelector('.mobile-nav-btn[data-nav=video]').click()"); await pg.wait_for_timeout(1500)
        await pg.evaluate("document.getElementById('videoReorderHeaderBtn').click()"); await pg.wait_for_timeout(500)
        await pg.evaluate("Array.from(document.querySelectorAll('#guideMenu .np-menu-item, #ltvManageSheet .np-menu-item')).filter(function(b){ return /Build a Custom/.test(b.textContent); })[0].click()"); await pg.wait_for_timeout(900)
        await pg.screenshot(path=f'{SHOTS}/red-1-top.png')
        L = await pg.evaluate("""(function(){ function q(s){ return document.querySelector(s); }
          var ids = ['liveChKind','liveChOrder','liveChAds','liveChDesc','liveChPanePick'].map(function(i){ return Math.round(q('#'+i).getBoundingClientRect().top + scrollY); });
          var nest = Array.from(document.querySelectorAll('#liveChPanel *')).filter(function(e){ var o = getComputedStyle(e).overflowY; return (o === 'auto' || o === 'scroll') && e.scrollHeight > e.clientHeight + 2 && e.clientHeight > 60; }).map(function(e){ return e.id || e.className; });
          return { ids: ids, nest: nest, descTag: q('#liveChDesc').tagName, adsNote: q('#liveChAdsNote').textContent.length }; })()""")
        check(L['ids'] == sorted(L['ids']), f'order of sections: Plays, Order, Commercials, Guide text, then the picker {L["ids"]}')
        check(not L['nest'] and L['descTag'] == 'INPUT' and L['adsNote'] < 80, f'no scrolling box inside the page, guide text is one line, short ads note {L}')
        await pg.evaluate("Array.from(document.querySelectorAll('#liveChPickWhere .home-tab'))[1].click()"); await pg.wait_for_timeout(300)
        await pg.fill('#liveChIaSearch', 'sesame'); await pg.wait_for_timeout(2000)
        n1 = await pg.evaluate("document.querySelectorAll('#liveChIaList .artist-info-row').length")
        check(n1 == 30, f'first page: 30 results {n1}')
        bar = await pg.evaluate("(function(){ var r = document.querySelector('.lc-bar').getBoundingClientRect(), n = document.getElementById('mobileNav').getBoundingClientRect(); return { bottom: Math.round(r.bottom), navTop: Math.round(innerHeight - 58), h: innerHeight, save: Math.round(document.getElementById('liveChSaveBtn').getBoundingClientRect().height) }; })()")
        check(bar['bottom'] <= bar['navTop'] and bar['bottom'] > bar['navTop'] - 16 and bar['save'] > 30, f'Save bar sits just above the bottom tabs {bar}')
        # scroll down in steps: pages 2 and 3 arrive by themselves
        PAGES.clear()
        mark = None
        for i in range(14):
            await pg.evaluate("window.scrollBy(0, 700)"); await pg.wait_for_timeout(500)
            if i == 3:
                mark = await pg.evaluate("(function(){ var r = document.querySelector('#liveChIaList .artist-info-row[data-ia-id=sesame20]'); return r ? Math.round(r.getBoundingClientRect().top) : null; })()")
        n2 = await pg.evaluate("document.querySelectorAll('#liveChIaList .artist-info-row').length")
        check(n2 == TOTAL and 2 in PAGES and 3 in PAGES, f'scrolling loads the rest by itself {n2} pages {PAGES}')
        await pg.screenshot(path=f'{SHOTS}/red-2-bottom.png')
        sent = await pg.evaluate("!!document.querySelector('.lc-more-sentinel')")
        check(not sent, 'no loader left when everything is in')
        # place kept: scroll to a row, pick it, scroll back up a little: rows above did not move or get rebuilt
        same = await pg.evaluate("(function(){ var r = document.querySelector('#liveChIaList .artist-info-row[data-ia-id=sesame20]'); return !!r && r.isConnected; })()")
        check(same, 'rows already on the page stay (nothing redrawn)')
        await pg.evaluate("document.querySelector('#liveChIaList .artist-info-row[data-ia-id=sesame33]').scrollIntoView({block:'center'}); document.querySelector('#liveChIaList .artist-info-row[data-ia-id=sesame33]').click()"); await pg.wait_for_timeout(500)
        ok = await pg.evaluate("document.querySelector('#liveChIaList .artist-info-row[data-ia-id=sesame33]').getAttribute('aria-selected')")
        sv = await pg.evaluate("(function(){ var r = document.getElementById('liveChSaveBtn').getBoundingClientRect(); return [Math.round(r.top), Math.round(r.bottom), innerHeight, document.getElementById('liveChSummary').textContent]; })()")
        check(ok == 'true' and sv[1] < sv[2], f'a picked row ticks and Save is still on screen {sv}')
        await pg.screenshot(path=f'{SHOTS}/red-3-picked.png')
        # the sticky search stays at the top while scrolled
        st = await pg.evaluate("Math.round(document.getElementById('liveChIaSearch').getBoundingClientRect().top)")
        check(0 <= st < 120, f'the archive search stays at the top while scrolling {st}')
        check(not errs, f'no page errors {errs[:2]}')
        await b.close()
asyncio.run(main())
print('FAILS:', len(fails))
for f in fails: print(' -', f)
sys.exit(1 if fails else 0)
