"""Build 236: Edit Favorites splits its rows into "Home row" (what Home's Favorites row shows) and
"Other favorites", each dragged only within itself; a group's new order keeps its own places in
the saved list. On Home, long-pressing a Favorites cover lifts it and dragging moves it (touch and
mouse); letting go saves the order, which Edit Favorites and the car's Favorites then show. A quick
swipe still scrolls and a tap still plays. In A to Z, a drag switches to Manual. Both themes at 412.
Run: python3 tests/test_home_fav_drag.py (screenshots in /tmp/claude-0/t/shots)"""
import sys as _nsys, os as _nos; _nsys.path.insert(0, _nos.path.dirname(_nos.path.abspath(__file__))); from notice_auto import AUTO_NOTICE
import os, sys, json
_here = os.path.dirname(os.path.abspath(__file__))
_src = open(os.path.join(_here, 'test_home_playlists.py')).read()
_head = _src[:_src.index('async def main():')]
_head = _head.replace("PORT = 8801", "PORT = 8834").replace("srv_homepl", "srv_favdrag")
DHOOK = r"""window.__d = {
 seed: function(){
   var song = libraryTracks[0];
   function st(n){ return { stationuuid: 'st-' + n, name: n, url: 'http://radio.example/' + n, urlToResolve: 'http://radio.example/' + n, favicon: '', tags: 'pop' }; }
   favorites = [st('Alpha'), song, st('Bravo'), { type: 'artist', artistKey: artistMatchKey('Kay'), name: 'Kay' }, st('Charlie'), st('Delta'), st('Echo')];
   saveFavorites(); renderFavoritesSection();
   return song.name;
 },
 names: function(){ return favorites.map(function(f){ return f.name; }); },
 row: function(){ return Array.from(document.querySelectorAll('#favoritesGrid > .tile')).map(function(t){ var n = t.querySelector('.tile-name'); return n ? n.textContent : ''; }); },
 rect: function(name){ var t = Array.from(document.querySelectorAll('#favoritesGrid > .tile')).filter(function(x){ var n = x.querySelector('.tile-name'); return n && n.textContent === name; })[0];
   if(!t) return null; t.scrollIntoView({block:'nearest', inline:'nearest'}); var r = t.getBoundingClientRect(); return { x: r.left + r.width / 2, y: r.top + r.height * 0.35, w: r.width }; },
 lifted: function(){ var t = document.querySelector('#favoritesGrid > .tile.fav-dragging'); return t ? t.querySelector('.tile-name').textContent : null; },
 scrollLeft: function(){ return document.getElementById('favoritesGrid').scrollLeft; },
 cur: function(){ return currentStation && currentStation.name; },
 order: function(){ return favOrder; },
 setOrder: function(v){ setFavOrder(v); },
 edit: function(){ openHomeSectionPage('favorites'); favPageEditing = true; syncFavPageEditBtn(); renderFavoritesPage(); },
 groups: function(){ var out = [], cur = null; Array.from(stationsGrid.children).forEach(function(el){
   if(el.classList.contains('fav-group-head')){ cur = { title: el.querySelector('.fav-group-title').textContent, note: (el.querySelector('.fav-group-note') || {}).textContent || '', rows: [] }; out.push(cur); }
   else if(el.classList.contains('fav-edit-row') && cur){ cur.rows.push(el.querySelector('.row-name').textContent); } }); return out; },
 handle: function(name){ var r = Array.from(stationsGrid.querySelectorAll('.fav-edit-row')).filter(function(x){ return x.querySelector('.row-name').textContent === name; })[0];
   var h = r.querySelector('.row-drag-handle').getBoundingClientRect(); return { x: h.left + h.width / 2, y: h.top + h.height / 2 }; },
 rowRect: function(name){ var r = Array.from(stationsGrid.querySelectorAll('.fav-edit-row')).filter(function(x){ return x.querySelector('.row-name').textContent === name; })[0].getBoundingClientRect(); return { x: r.left + r.width / 2, y: r.top + r.height / 2, h: r.height }; },
 done: function(){ document.getElementById('favPageEditBtn').click(); },
 home: function(){ loadTopStations(); },
 car: function(){ if(window.AmplifyPublishCarMenu) window.AmplifyPublishCarMenu(); }
};
"""
_head = _head.replace("open(root + '/index.html', 'w').write(_src.replace(_mark, _mark + HOOK))", "open(root + '/index.html', 'w').write(_src.replace(_mark, _mark + HOOK + DHOOK))")
_head = _head.replace("   addListener:", "   setCarCatalog: function(o){ window.__cat = JSON.parse(o.json); return Promise.resolve({}); },\n   addListener:", 1)
__file__ = os.path.join(_here, 'test_home_playlists.py')
exec(_head)


async def touch_drag(pg, cdp, x0, y0, x1, y1, hold=650, steps=14, y_end=None, dwell=120):
    pt = lambda x, y: [{'x': x, 'y': y, 'id': 1}]
    await cdp.send('Input.dispatchTouchEvent', {'type': 'touchStart', 'touchPoints': pt(x0, y0)})
    await pg.wait_for_timeout(hold)
    for i in range(1, steps + 1):
        x = x0 + (x1 - x0) * i / steps; y = y0 + ((y_end if y_end is not None else y1) - y0) * i / steps
        await cdp.send('Input.dispatchTouchEvent', {'type': 'touchMove', 'touchPoints': pt(x, y)})
        await pg.wait_for_timeout(30)
    await pg.wait_for_timeout(dwell)
    await cdp.send('Input.dispatchTouchEvent', {'type': 'touchEnd', 'touchPoints': []})
    await pg.wait_for_timeout(400)


async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
        for theme in ('dark', 'light'):
            T = f'[{theme}]'
            ctx = await b.new_context(viewport={'width': 412, 'height': 900}, device_scale_factor=2, is_mobile=True, has_touch=True, color_scheme=theme)
            await ctx.add_init_script(MOCK); await ctx.add_init_script(AUTO_NOTICE)
            await ctx.add_init_script("try{ localStorage.setItem('radioPlayerTheme', '%s'); }catch(e){}" % theme)
            pg = await ctx.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
            await pg.route('**/*', lambda route: route.continue_() if '127.0.0.1' in route.request.url else route.abort())
            cdp = await ctx.new_cdp_session(pg)
            await pg.goto(f'http://127.0.0.1:{PORT}/index.html'); await pg.wait_for_timeout(2500)
            await pg.evaluate("""(function(){ var ov=document.getElementById('addMusicOverlay'); if(ov) ov.classList.add('open');
              var btn=document.getElementById('addMusicFolderBtn'); btn.disabled=false; btn.click(); })()""")
            for _ in range(60):
                await pg.wait_for_timeout(500)
                if len(await pg.evaluate('__t.tracks()')) >= 4: break
            await pg.evaluate("(function(){ var ov=document.getElementById('addMusicOverlay'); if(ov) ov.classList.remove('open'); })()")
            await pg.evaluate('__d.home()'); await pg.wait_for_timeout(800)
            song = await pg.evaluate('__d.seed()'); await pg.wait_for_timeout(300)
            await pg.evaluate("document.getElementById('favoritesSection').scrollIntoView({block:'start'}); window.scrollBy(0, -70)"); await pg.wait_for_timeout(400)
            check(await pg.evaluate('__d.row()') == ['Alpha', 'Bravo', 'Charlie', 'Delta', 'Echo'], f'{T} the row starts in favourites order')

            # ---- Edit Favorites: two groups ----
            await pg.evaluate('__d.edit()'); await pg.wait_for_timeout(700)
            g = await pg.evaluate('__d.groups()')
            check([x['title'] for x in g] == ['Home row', 'Other favorites'], f'{T} Edit has a Home row group and an Other favorites group {[x["title"] for x in g]}')
            check(g[0]['rows'] == ['Alpha', 'Bravo', 'Charlie', 'Delta', 'Echo'] and g[1]['rows'] == [song, 'Kay'], f'{T} each holds its own favourites {g}')
            check('long-press' in g[0]['note'], f'{T} the Home row note mentions the long-press {g[0]["note"]!r}')
            await pg.evaluate('window.scrollTo(0,0)'); await pg.wait_for_timeout(300)
            await pg.screenshot(path=f'{shots}/favdrag-edit-{theme}.png')
            # drag Echo (home) to the top of its group with the grip
            h = await pg.evaluate("__d.handle('Echo')"); a = await pg.evaluate("__d.rowRect('Alpha')")
            await touch_drag(pg, cdp, h['x'], h['y'], h['x'], a['y'] - a['h'] * 0.3, hold=60, steps=16)
            # and try to drag Kay (other) up into the Home row group: it must stay in its own group
            h = await pg.evaluate("__d.handle('Kay')"); a = await pg.evaluate("__d.rowRect('Bravo')")
            await touch_drag(pg, cdp, h['x'], h['y'], h['x'], a['y'], hold=60, steps=16)
            g = await pg.evaluate('__d.groups()')
            check(g[0]['rows'] == ['Echo', 'Alpha', 'Bravo', 'Charlie', 'Delta'], f'{T} a grip drag reorders the Home row group {g[0]["rows"]}')
            check(g[1]['rows'][-1] == 'Kay' or g[1]['rows'] == ['Kay', song], f'{T} Other favorites can\'t be dragged into the Home row {g}')
            check(set(g[1]['rows']) == {song, 'Kay'} and 'Kay' not in g[0]['rows'], f'{T} the groups keep their members')
            names = await pg.evaluate('__d.names()')
            check(names[1] in (song, 'Kay') and names[3] in (song, 'Kay') and [n for n in names if n not in (song, 'Kay')] == ['Echo', 'Alpha', 'Bravo', 'Charlie', 'Delta'],
                  f'{T} saved: each group in its own places {names}')
            await pg.evaluate('__d.done()'); await pg.wait_for_timeout(300)

            # ---- Home: long-press and drag ----
            await pg.evaluate("document.getElementById('detailBackBtn').click()"); await pg.wait_for_timeout(900)
            await pg.evaluate("document.getElementById('favoritesSection').scrollIntoView({block:'start'}); window.scrollBy(0, -70)"); await pg.wait_for_timeout(400)
            check(await pg.evaluate('__d.row()') == ['Echo', 'Alpha', 'Bravo', 'Charlie', 'Delta'], f'{T} Home shows the order set in Edit {await pg.evaluate("__d.row()")}')
            r0 = await pg.evaluate("__d.rect('Echo')"); r1 = await pg.evaluate("__d.rect('Alpha')")
            # lift: hold, move a little, screenshot mid-drag
            await cdp.send('Input.dispatchTouchEvent', {'type': 'touchStart', 'touchPoints': [{'x': r0['x'], 'y': r0['y'], 'id': 1}]})
            await pg.wait_for_timeout(650)
            check(await pg.evaluate('__d.lifted()') == 'Echo', f'{T} a long press lifts the cover')
            for i in range(1, 13):
                await cdp.send('Input.dispatchTouchEvent', {'type': 'touchMove', 'touchPoints': [{'x': r0['x'] + (r1['x'] + 10 - r0['x']) * i / 12, 'y': r0['y'] + 6, 'id': 1}]})
                await pg.wait_for_timeout(30)
            await pg.wait_for_timeout(200)
            await pg.screenshot(path=f'{shots}/favdrag-lifted-{theme}.png')
            await cdp.send('Input.dispatchTouchEvent', {'type': 'touchEnd', 'touchPoints': []}); await pg.wait_for_timeout(500)
            row = await pg.evaluate('__d.row()')
            check(row == ['Alpha', 'Echo', 'Bravo', 'Charlie', 'Delta'], f'{T} dropping it moves it {row}')
            check(await pg.evaluate('__d.lifted()') is None and await pg.evaluate('__d.cur()') != 'Echo', f'{T} it settles and the press didn\'t play it')
            names = await pg.evaluate('__d.names()')
            check([n for n in names if n not in (song, 'Kay')] == ['Alpha', 'Echo', 'Bravo', 'Charlie', 'Delta'] and names[1] in (song, 'Kay') and names[3] in (song, 'Kay'),
                  f'{T} the new order is saved, others keep their places {names}')
            stored = await pg.evaluate("JSON.parse(localStorage.getItem('radioPlayerFavorites') || localStorage.getItem(FAVORITES_KEY) || '[]').map(function(f){ return f.name; })")
            check(stored == names, f'{T} and stored {stored}')
            # dragging toward the end scrolls the row on its own
            sl0 = await pg.evaluate('__d.scrollLeft()')
            r0 = await pg.evaluate("__d.rect('Alpha')")
            await touch_drag(pg, cdp, r0['x'], r0['y'], 404, r0['y'], hold=650, steps=10, dwell=1500)
            row = await pg.evaluate('__d.row()')
            check(row[-1] == 'Alpha' or row.index('Alpha') >= 3, f'{T} dragging to the edge carries it along the row {row} (scroll {sl0}->{await pg.evaluate("__d.scrollLeft()")})')
            # a quick swipe scrolls and doesn't reorder
            await pg.evaluate("document.getElementById('favoritesGrid').scrollLeft = 0"); await pg.wait_for_timeout(300)
            before = await pg.evaluate('__d.row()')
            r0 = await pg.evaluate("__d.rect('" + before[1] + "')")
            await touch_drag(pg, cdp, r0['x'], r0['y'], r0['x'] - 200, r0['y'], hold=20, steps=8)
            check(await pg.evaluate('__d.row()') == before and await pg.evaluate('__d.lifted()') is None, f'{T} a quick swipe doesn\'t move anything')
            # a tap still plays
            await pg.evaluate("document.getElementById('favoritesGrid').scrollLeft = 0"); await pg.wait_for_timeout(300)
            r0 = await pg.evaluate("__d.rect('" + before[0] + "')")
            await pg.touchscreen.tap(r0['x'], r0['y']); await pg.wait_for_timeout(700)
            check(await pg.evaluate('__d.cur()') == before[0], f'{T} a tap still plays {await pg.evaluate("__d.cur()")}')
            # mouse: press, hold, drag
            await pg.evaluate("document.getElementById('favoritesGrid').scrollLeft = 0"); await pg.wait_for_timeout(300)
            cur_row = await pg.evaluate('__d.row()')
            ra = await pg.evaluate("__d.rect('" + cur_row[0] + "')"); rb = await pg.evaluate("__d.rect('" + cur_row[1] + "')")
            await pg.mouse.move(ra['x'], ra['y']); await pg.mouse.down(); await pg.wait_for_timeout(650)
            await pg.mouse.move(rb['x'] + 15, ra['y'], steps=10); await pg.wait_for_timeout(150); await pg.mouse.up(); await pg.wait_for_timeout(500)
            check((await pg.evaluate('__d.row()'))[:2] == [cur_row[1], cur_row[0]], f'{T} with a mouse too {await pg.evaluate("__d.row()")}')

            # ---- Edit and the car show the new order ----
            want = await pg.evaluate('__d.row()')
            await pg.evaluate('__d.edit()'); await pg.wait_for_timeout(700)
            g = await pg.evaluate('__d.groups()')
            check(g[0]['rows'] == want, f'{T} Edit Favorites shows the dragged order {g[0]["rows"]} vs {want}')
            await pg.evaluate('__d.done()'); await pg.wait_for_timeout(200)
            await pg.evaluate('__d.car()'); await pg.wait_for_timeout(1500)
            cf = [e.get('title') for e in ((await pg.evaluate('window.__cat')) or {}).get('lists', {}).get('favorites', [])]
            check(cf == want, f'{T} and so do the car\'s Favorites {cf}')

            # ---- A to Z: a drag switches to Manual ----
            await pg.evaluate("__d.setOrder('az')"); await pg.evaluate("document.getElementById('detailBackBtn').click()"); await pg.wait_for_timeout(900)
            await pg.evaluate("document.getElementById('favoritesSection').scrollIntoView({block:'start'}); window.scrollBy(0, -70)"); await pg.wait_for_timeout(400)
            check(await pg.evaluate('__d.row()') == ['Alpha', 'Bravo', 'Charlie', 'Delta', 'Echo'], f'{T} A to Z shows the row sorted')
            ra = await pg.evaluate("__d.rect('Bravo')"); rb = await pg.evaluate("__d.rect('Alpha')")
            await touch_drag(pg, cdp, ra['x'], ra['y'], rb['x'] - 15, ra['y'], steps=10)
            check(await pg.evaluate('__d.row()') == ['Bravo', 'Alpha', 'Charlie', 'Delta', 'Echo'] and await pg.evaluate('__d.order()') in ('oldest', 'newest'),
                  f'{T} a drag in A to Z switches to Manual and keeps the new order {await pg.evaluate("__d.row()")} {await pg.evaluate("__d.order()")}')
            check(not errs, f'{T} no page errors {errs[:3]}')
            await ctx.close()
        await b.close()
    print('ALL PASSED' if not fails else f'FAILED {fails}')

asyncio.run(main())
