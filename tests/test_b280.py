"""Build 280 (Mark: Live TV's Add and Edit were clunky; build all four recommendations):
1. One Add: the header says "Add" (on a phone too); Add Channels opens on My Shows & Movies, where a
   show, all movies, a genre or a decade becomes a channel with one tap (+, a check once on Live TV,
   tapping the check takes it off after asking); Build a Custom Channel opens the editor.
2. A channel's options from its logo in the guide: Watch Now, Edit Channel (yours) / Rename (added),
   Favorite, Move, Remove from Live TV (asks first).
3. The ⋯ menu instead of Edit: Arrange Channels (drag; a drag makes the order Manual), Layout, Order.
4. An empty guide shows the two ways in as cards.
Also: the floating video can't be dragged under the header.
Run: python3 tests/test_b280.py (screenshots in /tmp/claude-0/t/shots)"""
import sys as _nsys, os as _nos; _nsys.path.insert(0, _nos.path.dirname(_nos.path.abspath(__file__)))
src = open(_nos.path.join(_nos.path.dirname(_nos.path.abspath(__file__)), 'test_live_channels_editor.py')).read()
src = src[:src.index('async def run2(')].replace('PORT = 8863', 'PORT = 8879').replace("srv-livech2'", "srv-b280'")
exec(src)
import json, sys

async def defs_(pg): return await pg.evaluate("JSON.parse(localStorage.getItem('radioPlayerLiveChannels') || 'null')")
async def guide_names(pg):
    return await pg.evaluate("Array.from(document.querySelectorAll('#stationsGrid .epg-row')).map(r => r.querySelector('.epg-ch').getAttribute('aria-label'))")
async def confirm_ok(pg):
    await pg.wait_for_timeout(300)
    t = await pg.evaluate("document.getElementById('confirmOverlay').classList.contains('open') ? document.getElementById('confirmTitle').textContent : null")
    if t: await pg.evaluate("document.getElementById('confirmOk').click()"); await pg.wait_for_timeout(500)
    return t

async def run(p, width, theme='dark'):
    T = f'[{theme} {width}]'
    b = await p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
    ctx = await b.new_context(viewport={'width': width, 'height': 860}, device_scale_factor=3, is_mobile=True, has_touch=True, color_scheme=theme, locale='en-US', timezone_id='America/New_York')
    await ctx.add_init_script(MOCK); await ctx.add_init_script(AUTO_NOTICE); await ctx.add_init_script(SEED)
    await ctx.add_init_script("try{ localStorage.setItem('radioPlayerTheme', '%s'); }catch(e){}" % theme)
    pg = await ctx.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e) + ' ' + (e.stack or '')[:300]))
    await pg.route('**/*', route)
    await pg.goto(f'http://127.0.0.1:{PORT}/index.html'); await pg.wait_for_timeout(3000)
    await pg.evaluate("document.querySelector('.mobile-nav-btn[data-nav=video]').click()"); await pg.wait_for_timeout(1500)

    # header: "Add" with its word, and ⋯
    h = await pg.evaluate("""(()=>{ const a = document.getElementById('videoAddHeaderBtn'), m = document.getElementById('videoReorderHeaderBtn');
      const t = a.querySelector('.btn-text'); return { add: t.textContent, shown: getComputedStyle(t).display !== 'none', menu: m.textContent.trim(), menuTitle: m.title,
      ra: a.getBoundingClientRect().right, lm: m.getBoundingClientRect().left, vw: innerWidth, rm: m.getBoundingClientRect().right }; })()""")
    check(h['add'] == 'Add' and h['shown'] and h['menu'] == '⋯' and h['rm'] <= h['vw'], f'{T} header: "Add" with its word and ⋯ {h}')
    await pg.screenshot(path=f'{SHOTS}/b280-guide-{theme}-{width}.png')

    # 3) the ⋯ menu
    await pg.evaluate("document.getElementById('videoReorderHeaderBtn').click()"); await pg.wait_for_timeout(400)
    mi = await pg.evaluate("Array.from(document.querySelectorAll('#guideMenu .np-menu-item, #guideMenu .ch-menu-label')).map(e => e.textContent.trim())")
    check(mi == ['Arrange Channels', 'Layout', 'Your Channels First', 'Mix All Channels', 'Order', 'A to Z', 'Manual'], f'{T} ⋯: Arrange Channels, Layout, Order {mi}')
    on = await pg.evaluate("Array.from(document.querySelectorAll('#guideMenu .np-menu-item.on')).map(e => e.textContent.trim())")
    check(on == ['Your Channels First', 'Manual'], f'{T} the current layout and order are ticked {on}')
    await pg.screenshot(path=f'{SHOTS}/b280-menu-{theme}-{width}.png')
    await pg.evaluate("Array.from(document.querySelectorAll('#guideMenu .np-menu-item')).find(e => e.textContent.trim() === 'Mix All Channels').click()"); await pg.wait_for_timeout(500)
    lay = await pg.evaluate("localStorage.getItem('radioPlayerChannelLayout')")
    check(lay == 'mixed' and not await pg.evaluate("!!document.getElementById('guideMenu')"), f'{T} Mix All Channels is kept, the menu closes {lay}')
    await pg.evaluate("document.getElementById('videoReorderHeaderBtn').click()"); await pg.wait_for_timeout(300)
    await pg.evaluate("Array.from(document.querySelectorAll('#guideMenu .np-menu-item')).find(e => e.textContent.trim() === 'A to Z').click()"); await pg.wait_for_timeout(500)
    g = await guide_names(pg)
    check(g == sorted(g, key=lambda x: x.lower()), f'{T} Mix + A to Z: the guide in A to Z {g}')
    await pg.evaluate("document.getElementById('videoReorderHeaderBtn').click()"); await pg.wait_for_timeout(300)
    await pg.evaluate("Array.from(document.querySelectorAll('#guideMenu .np-menu-item')).find(e => e.textContent.trim() === 'Your Channels First').click()"); await pg.wait_for_timeout(400)
    await pg.evaluate("document.getElementById('videoReorderHeaderBtn').click()"); await pg.wait_for_timeout(300)
    await pg.evaluate("Array.from(document.querySelectorAll('#guideMenu .np-menu-item')).find(e => e.textContent.trim() === 'Manual').click()"); await pg.wait_for_timeout(400)
    # outside tap closes it
    await pg.evaluate("document.getElementById('videoReorderHeaderBtn').click()"); await pg.wait_for_timeout(300)
    await pg.mouse.click(30, 500); await pg.wait_for_timeout(300)
    check(not await pg.evaluate("!!document.getElementById('guideMenu')"), f'{T} a tap elsewhere closes the menu')

    # Arrange Channels
    await pg.evaluate("document.getElementById('videoReorderHeaderBtn').click()"); await pg.wait_for_timeout(300)
    await pg.evaluate("Array.from(document.querySelectorAll('#guideMenu .np-menu-item')).find(e => e.textContent.trim() === 'Arrange Channels').click()"); await pg.wait_for_timeout(600)
    ar = await pg.evaluate("""(()=>({ heads: Array.from(document.querySelectorAll('#stationsGrid .ch-group-head')).map(e => e.textContent), grips: document.querySelectorAll('#stationsGrid .ch-grip, #stationsGrid [class*=grip]').length,
      rows: document.querySelectorAll('#stationsGrid .ch-item').length, opts: document.querySelectorAll('#stationsGrid .ch-sort-opts').length, newBtn: !!document.getElementById('liveChNewBtn'),
      done: document.getElementById('videoReorderHeaderBtn').title }))()""")
    check(ar['heads'] == ['Your Channels', 'Added Channels'] and ar['grips'] >= ar['rows'] > 0 and not ar['opts'] and not ar['newBtn'] and ar['done'] == 'Done',
          f'{T} Arrange: the two lists to drag, no options or New Channel, header says Done {ar}')
    await pg.screenshot(path=f'{SHOTS}/b280-arrange-{theme}-{width}.png')
    await pg.evaluate("document.getElementById('videoReorderHeaderBtn').click()"); await pg.wait_for_timeout(600)
    check(len(await guide_names(pg)) >= 4 and (await pg.evaluate("document.getElementById('videoReorderHeaderBtn').textContent.trim()")) == '⋯', f'{T} Done: back to the guide')

    # 1) Add: My Shows & Movies first
    await pg.evaluate("document.getElementById('videoAddHeaderBtn').click()"); await pg.wait_for_timeout(1200)
    tabs = await pg.evaluate("Array.from(document.querySelectorAll('#stationsGrid .ch-tools .home-tab')).map(e => [e.textContent, e.classList.contains('active')])")
    check(tabs[0] == ['My Shows & Movies', True], f'{T} Add Channels opens on My Shows & Movies {tabs[:3]}')
    rows = await pg.evaluate("Array.from(document.querySelectorAll('.ch-row.ch-mine')).map(r => ({ n: r.querySelector('.ch-name').textContent, s: r.querySelector('.ch-sub').textContent, on: r.querySelector('.ch-add').classList.contains('added') }))")
    print(T, rows)
    names = [r['n'] for r in rows]; on = {r['n']: r['on'] for r in rows}
    check({'Friends', 'MADtv', 'Seinfeld', 'The Office (US)'} <= set(names), f'{T} each show is listed {names}')
    check(on.get('The Office (US)') and on.get('Seinfeld') and not on.get('Friends'), f'{T} shows already on Live TV have a check, the rest a + {on}')
    check(on.get('All Movies on the Phone') and 'Comedy' in names and any(n.startswith('The 19') for n in names), f'{T} collections: all movies (checked), genres, decades {names}')
    heads = await pg.evaluate("Array.from(document.querySelectorAll('.ch-mine-head')).map(e => e.textContent)")
    check(heads == ['Shows', 'Collections'] and await pg.evaluate("!!document.getElementById('chCustomBtn')"), f'{T} Build a Custom Channel, Shows, Collections {heads}')
    await pg.screenshot(path=f'{SHOTS}/b280-mine-{theme}-{width}.png')
    d0 = await defs_(pg)
    await pg.evaluate("Array.from(document.querySelectorAll('.ch-row.ch-mine')).find(r => r.querySelector('.ch-name').textContent === 'Friends').querySelector('.ch-add').click()"); await pg.wait_for_timeout(400)
    d1 = await defs_(pg)
    new = [d for d in d1 if d not in d0]
    check(len(new) == 1 and new[0]['src'] == {'kind': 'pick', 'shows': ['Friends'], 'movies': []} and new[0]['order'] == 'sequence', f'{T} + on Friends makes its channel {new}')
    fr = await pg.evaluate("(()=>{ const r = Array.from(document.querySelectorAll('.ch-row.ch-mine')).find(r => r.querySelector('.ch-name').textContent === 'Friends'); return [r.querySelector('.ch-add').classList.contains('added'), r.querySelector('.ch-sub').textContent]; })()")
    check(fr[0] and fr[1].endswith('On Live TV'), f'{T} and it shows a check at once {fr}')
    # a genre: tap the row
    await pg.evaluate("Array.from(document.querySelectorAll('.ch-row.ch-mine')).find(r => r.querySelector('.ch-name').textContent === 'Comedy').click()"); await pg.wait_for_timeout(400)
    d2 = await defs_(pg)
    check(any(d['src'] == {'kind': 'genre', 'genre': 'Comedy'} and d['order'] == 'shuffle' for d in d2), f'{T} a tap on Comedy makes a shuffled genre channel')
    # search
    await pg.fill('.ch-tools input[type=search]', 'sein'); await pg.wait_for_timeout(500)
    srch = await pg.evaluate("Array.from(document.querySelectorAll('.ch-row.ch-mine .ch-name')).map(e => e.textContent)")
    check(srch == ['Seinfeld'], f'{T} search narrows the list {srch}')
    await pg.fill('.ch-tools input[type=search]', ''); await pg.wait_for_timeout(500)
    # taking one off asks first
    await pg.evaluate("Array.from(document.querySelectorAll('.ch-row.ch-mine')).find(r => r.querySelector('.ch-name').textContent === 'Comedy').querySelector('.ch-add').click()")
    t = await confirm_ok(pg)
    d3 = await defs_(pg)
    check(t and 'Comedy' in t and not any(d['src'].get('genre') == 'Comedy' for d in d3), f'{T} the check takes it off, after asking ({t})')
    # Build a Custom Channel
    await pg.evaluate("document.getElementById('chCustomBtn').click()"); await pg.wait_for_timeout(500)
    # build 305: the editor is a page; Back leaves it
    ed = await pg.evaluate("[document.getElementById('liveChPanel').parentNode.id === 'stationsGrid', document.getElementById('stationsHeading').textContent]")
    check(ed == [True, 'New Channel'], f'{T} Build a Custom Channel opens the editor (a page since build 305) {ed}')
    await pg.evaluate("document.getElementById('detailBackBtn').click()"); await pg.wait_for_timeout(500)
    # back: Friends is in the guide
    await pg.evaluate("document.getElementById('detailBackBtn').click()"); await pg.wait_for_timeout(1200)
    g = await guide_names(pg)
    check(any(x.startswith('Friends') for x in g), f'{T} back in the guide, Friends is there {g}')

    # 2) a channel's options from its logo
    await pg.evaluate("Array.from(document.querySelectorAll('#stationsGrid .epg-ch')).find(c => c.getAttribute('aria-label').startsWith('Seinfeld')).click()"); await pg.wait_for_timeout(500)
    sh = await pg.evaluate("""(()=>({ open: document.getElementById('chSheetOverlay').classList.contains('open'), name: document.getElementById('chSheetName').textContent,
      items: Array.from(document.querySelectorAll('#chSheetItems .ch-sheet-item')).map(e => e.textContent), playing: !!window.__cur }))()""")
    check(sh['open'] and sh['name'].startswith('Seinfeld') and 'Your channel' in sh['name'] and sh['items'] == ['Watch Now', 'Edit Channel', 'Add to Favorites', 'Move', 'Remove from Live TV'],
          f'{T} Seinfeld\'s logo opens its options {sh}')
    await pg.screenshot(path=f'{SHOTS}/b280-sheet-{theme}-{width}.png')
    await pg.evaluate("Array.from(document.querySelectorAll('#chSheetItems .ch-sheet-item')).find(e => e.textContent === 'Edit Channel').click()"); await pg.wait_for_timeout(500)
    ed = await pg.evaluate("[document.getElementById('liveChPanel').parentNode.id === 'stationsGrid', document.getElementById('stationsHeading').textContent, document.getElementById('chSheetOverlay').classList.contains('open')]")
    check(ed == [True, 'Edit Channel', False], f'{T} Edit Channel opens its editor (a page since build 305) {ed}')
    await pg.evaluate("document.getElementById('detailBackBtn').click()"); await pg.wait_for_timeout(800)
    # favourite
    await pg.evaluate("Array.from(document.querySelectorAll('#stationsGrid .epg-ch')).find(c => c.getAttribute('aria-label').startsWith('Seinfeld')).click()"); await pg.wait_for_timeout(400)
    await pg.evaluate("Array.from(document.querySelectorAll('#chSheetItems .ch-sheet-item')).find(e => e.textContent === 'Add to Favorites').click()"); await pg.wait_for_timeout(600)
    fav = await pg.evaluate("JSON.parse(localStorage.getItem('radioPlayerFavorites') || '[]').some(f => f.liveCh && /seinfeld/.test(f.liveCh))")
    heart = await pg.evaluate("!!Array.from(document.querySelectorAll('#stationsGrid .epg-ch')).find(c => c.getAttribute('aria-label').startsWith('Seinfeld')).querySelector('.epg-heart')")
    check(fav and heart, f'{T} Add to Favorites: saved, heart in the guide')
    # watch now
    await pg.evaluate("Array.from(document.querySelectorAll('#stationsGrid .epg-ch')).find(c => c.getAttribute('aria-label').startsWith('Seinfeld')).click()"); await pg.wait_for_timeout(400)
    items = await pg.evaluate("Array.from(document.querySelectorAll('#chSheetItems .ch-sheet-item')).map(e => e.textContent)")
    check('Remove from Favorites' in items, f'{T} then it offers Remove from Favorites {items}')
    await pg.mouse.click(width // 2, 120); await pg.wait_for_timeout(300)
    check(not await pg.evaluate("document.getElementById('chSheetOverlay').classList.contains('open')"), f'{T} a tap above the sheet closes it')
    # an added channel: Rename, Remove asks, then it's gone
    await pg.evaluate("Array.from(document.querySelectorAll('#stationsGrid .epg-ch')).find(c => c.getAttribute('aria-label').startsWith('Buzzr')).click()"); await pg.wait_for_timeout(400)
    items = await pg.evaluate("Array.from(document.querySelectorAll('#chSheetItems .ch-sheet-item')).map(e => e.textContent)")
    check(items == ['Watch Now', 'Rename', 'Add to Favorites', 'Move', 'Remove from Live TV'], f'{T} an added channel: Rename instead of Edit {items}')
    await pg.evaluate("Array.from(document.querySelectorAll('#chSheetItems .ch-sheet-item')).find(e => e.textContent === 'Remove from Live TV').click()")
    t = await confirm_ok(pg)
    g = await guide_names(pg)
    check(t and 'Buzzr' in t and not any(x.startswith('Buzzr') for x in g), f'{T} Remove asks, then Buzzr is gone ({t}) {g}')
    # Move opens Arrange
    await pg.evaluate("document.querySelector('#stationsGrid .epg-ch').click()"); await pg.wait_for_timeout(400)
    await pg.evaluate("Array.from(document.querySelectorAll('#chSheetItems .ch-sheet-item')).find(e => e.textContent === 'Move').click()"); await pg.wait_for_timeout(500)
    check(await pg.evaluate("document.getElementById('videoReorderHeaderBtn').title") == 'Done', f'{T} Move opens Arrange Channels')
    await pg.evaluate("document.getElementById('videoReorderHeaderBtn').click()"); await pg.wait_for_timeout(500)

    # floating video can't go under the header
    await pg.evaluate("(()=>{ const v = document.getElementById('videoMini'); v.hidden = false; v.style.left = '100px'; v.style.top = '400px'; v.style.right='auto'; v.style.bottom='auto'; })()")
    bar = await pg.evaluate("(()=>{ const r = document.getElementById('videoMiniBar').getBoundingClientRect(); return [r.left + 60, r.top + 15]; })()")
    await pg.mouse.move(bar[0], bar[1]); await pg.mouse.down(); 
    for y in range(int(bar[1]), -40, -40): await pg.mouse.move(bar[0], y)
    await pg.mouse.up(); await pg.wait_for_timeout(300)
    pos = await pg.evaluate("[document.getElementById('videoMini').getBoundingClientRect().top, document.querySelector('.sidebar-top').getBoundingClientRect().bottom]")
    check(pos[0] >= 0, f'{T} the floating video stays on screen (above everything since build 282) {pos}')
    await pg.evaluate("document.getElementById('videoMini').hidden = true")
    check(not errs, f'{T} no page errors {errs[:2]}')
    await b.close()

    # 4) an empty guide
    b = await p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
    ctx = await b.new_context(viewport={'width': width, 'height': 860}, device_scale_factor=3, is_mobile=True, has_touch=True, color_scheme=theme, locale='en-US', timezone_id='America/New_York')
    await ctx.add_init_script(MOCK); await ctx.add_init_script(AUTO_NOTICE); await ctx.add_init_script(SEED)
    await ctx.add_init_script("if(!localStorage.getItem('__e')){ localStorage.setItem('__e','1'); localStorage.setItem('radioPlayerLiveChannels', '[]'); localStorage.setItem('radioPlayerVideoChannels', '[]'); }")
    pg = await ctx.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
    await pg.route('**/*', route)
    await pg.goto(f'http://127.0.0.1:{PORT}/index.html'); await pg.wait_for_timeout(3000)
    await pg.evaluate("document.querySelector('.mobile-nav-btn[data-nav=video]').click()"); await pg.wait_for_timeout(1200)
    cards = await pg.evaluate("Array.from(document.querySelectorAll('.ch-start-card .ch-name')).map(e => e.textContent)")
    check(cards == ['From My Shows & Movies', 'Free Live TV'], f'{T} empty guide: the two ways in {cards}')
    await pg.screenshot(path=f'{SHOTS}/b280-empty-{theme}-{width}.png')
    await pg.evaluate("document.querySelector('.ch-start-card.free').click()"); await pg.wait_for_timeout(1000)
    act = await pg.evaluate("(document.querySelector('#stationsGrid .ch-tools .home-tab.active') || {}).textContent")
    check(act == 'Recommended', f'{T} Free Live TV opens the free channels {act}')
    await pg.evaluate("document.getElementById('detailBackBtn').click()"); await pg.wait_for_timeout(800)
    await pg.evaluate("document.querySelector('.ch-start-card.mine').click()"); await pg.wait_for_timeout(1000)
    act = await pg.evaluate("(document.querySelector('#stationsGrid .ch-tools .home-tab.active') || {}).textContent")
    check(act == 'My Shows & Movies', f'{T} From My Shows & Movies opens that tab {act}')
    check(not errs, f'{T} no page errors {errs[:2]}')
    await b.close()

async def main():
    async with async_playwright() as p:
        await run(p, 390)
        await run(p, 360, 'light')
    print('ALL PASSED' if not fails else f'{fails} FAILED')
    sys.exit(1 if fails else 0)
asyncio.run(main())
