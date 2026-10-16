"""Build 235: a custom station (My Stations) can be a favourite: a heart on its Home cover and on its
page. In Home's Favorites row it plays one of its stations at random, with Previous/Next going
through the rest; it follows a rename and goes when the custom station is deleted. Android Auto's
Favorites lists it as a playable row that plays its stations shuffled ("shuffle:fy:<id>"), and the
car's Favorites hold only what Home's row does. Both themes at 412.
Run: python3 tests/test_custom_station_fav.py (screenshots in /tmp/claude-0/t/shots)"""
import sys as _nsys, os as _nos; _nsys.path.insert(0, _nos.path.dirname(_nos.path.abspath(__file__))); from notice_auto import AUTO_NOTICE
import os, sys, json
from urllib.parse import urlparse, parse_qs
_here = os.path.dirname(os.path.abspath(__file__))
_src = open(os.path.join(_here, 'test_home_playlists.py')).read()
_head = _src[:_src.index('async def main():')]
_head = _head.replace("PORT = 8801", "PORT = 8833").replace("srv_homepl", "srv_csfav")
CHOOK = r"""window.__c = {
 seed: function(){
   customSearches = [{ id: 'cs_soul', label: 'Soul Mix', query: 'soul' }, { id: 'cs_jazz', label: 'Late Jazz', query: 'jazz' }];
   saveCustomSearches(); renderForYouHomeSection(); renderCustomSearchList();
   favorites = [libraryTracks[0], { type: 'artist', artistKey: artistMatchKey('Kay'), name: 'Kay' },
     { stationuuid: 'st-kiss', name: 'KISS FM', url: 'http://radio.example/kiss', urlToResolve: 'http://radio.example/kiss', favicon: '', tags: 'pop' }];
   saveFavorites(); renderFavoritesSection();
 },
 homeTileHeart: function(id){ var t = document.querySelector('[data-key="foryou-home-' + id + '"] .tile-fav'); if(!t) return null; t.click(); return t.classList.contains('on'); },
 favs: function(){ return favorites.map(function(f){ return [f.type || 'station', f.name]; }); },
 row: function(){ return Array.from(document.querySelectorAll('#favoritesGrid .tile')).map(function(t){ var n = t.querySelector('.tile-name'); return n ? n.textContent : ''; }); },
 tapRow: function(name){ var t = Array.from(document.querySelectorAll('#favoritesGrid .tile')).filter(function(x){ var n = x.querySelector('.tile-name'); return n && n.textContent === name; })[0]; if(t) t.click(); return !!t; },
 q: function(){ return { label: queueLabel, list: playQueue.map(function(s){ return s.name; }), idx: queueIndex, cur: currentStation && currentStation.name }; },
 openPage: function(id){ pushView(); runCustomSearch(findCustomSearchById(id)); },
 pageHeart: function(){ var b = document.getElementById('playlistFavBtn'); return { shown: getComputedStyle(b).display !== 'none' && b.getBoundingClientRect().width > 0, on: b.classList.contains('on') }; },
 clickPageHeart: function(){ document.getElementById('playlistFavBtn').click(); },
 rename: function(id, l){ findCustomSearchById(id).label = l; saveCustomSearches(); renderForYouHomeSection(); renderFavoritesSection(); },
 del: function(id){ deleteCustomSearch(id); renderFavoritesSection(); },
 home: function(){ loadTopStations(); },
 car: function(){ if(window.AmplifyPublishCarMenu) window.AmplifyPublishCarMenu(); }
};
"""
_head = _head.replace("open(root + '/index.html', 'w').write(_src.replace(_mark, _mark + HOOK))", "open(root + '/index.html', 'w').write(_src.replace(_mark, _mark + HOOK + CHOOK))")
_head = _head.replace("   addListener:", "   setCarCatalog: function(o){ window.__cat = JSON.parse(o.json); return Promise.resolve({}); },\n   addListener:", 1)
__file__ = os.path.join(_here, 'test_home_playlists.py')
exec(_head)
assert 'setCarCatalog' in MOCK

SOUL = [{'name': 'Soul %d' % i, 'url_resolved': 'http://s/soul%d' % i, 'stationuuid': 'soul-%d' % i, 'favicon': '', 'tags': 'soul', 'codec': 'MP3'} for i in range(8)]
JAZZ = [{'name': 'Jazz %d' % i, 'url_resolved': 'http://s/jazz%d' % i, 'stationuuid': 'jazz-%d' % i, 'favicon': '', 'tags': 'jazz', 'codec': 'MP3'} for i in range(3)]


async def directory(r):
    u = r.request.url
    if '127.0.0.1' in u: return await r.continue_()
    q = parse_qs(urlparse(u).query)
    if '/json/stations/search' in u:
        name = q.get('name', [''])[0]
        body = SOUL if name == 'soul' else JAZZ if name == 'jazz' else []
        return await r.fulfill(status=200, content_type='application/json', body=json.dumps(body))
    return await r.abort()


async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
        for theme in ('dark', 'light'):
            T = f'[{theme}]'
            ctx = await b.new_context(viewport={'width': 412, 'height': 900}, device_scale_factor=2, is_mobile=True, has_touch=True, color_scheme=theme)
            await ctx.add_init_script(MOCK); await ctx.add_init_script(AUTO_NOTICE)
            await ctx.add_init_script("try{ localStorage.setItem('radioPlayerTheme', '%s'); }catch(e){}" % theme)
            pg = await ctx.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
            await pg.route('**/*', directory)
            await pg.goto(f'http://127.0.0.1:{PORT}/index.html'); await pg.wait_for_timeout(2500)
            await pg.evaluate("""(function(){ var ov=document.getElementById('addMusicOverlay'); if(ov) ov.classList.add('open');
              var btn=document.getElementById('addMusicFolderBtn'); btn.disabled=false; btn.click(); })()""")
            for _ in range(60):
                await pg.wait_for_timeout(500)
                if len(await pg.evaluate('__t.tracks()')) >= 4: break
            await pg.evaluate("(function(){ var ov=document.getElementById('addMusicOverlay'); if(ov) ov.classList.remove('open'); })()")
            await pg.evaluate('__c.home()'); await pg.wait_for_timeout(800)
            await pg.evaluate('__c.seed()'); await pg.wait_for_timeout(300)

            # ---- the heart on the My Stations cover ----
            on = await pg.evaluate("__c.homeTileHeart('cs_soul')")
            check(on is True, f'{T} the heart on a My Stations cover favourites it ({on})')
            favs = await pg.evaluate('__c.favs()')
            check(['customStation', 'Soul Mix'] in favs, f'{T} it is in favourites {favs}')
            await pg.evaluate('__c.home()'); await pg.wait_for_timeout(700)
            row = await pg.evaluate('__c.row()')
            check(row == ['KISS FM', 'Soul Mix'], f'{T} Home\'s row has it (and only stations etc.) {row}')
            await pg.evaluate("document.getElementById('favoritesSection').scrollIntoView({block:'start'}); window.scrollBy(0, -70)"); await pg.wait_for_timeout(500)
            await pg.screenshot(path=f'{shots}/csfav-row-{theme}.png')

            # ---- playing it: a random station, the rest to skip through ----
            firsts = set(); orders = set()
            for i in range(4):
                await pg.evaluate("__c.tapRow('Soul Mix')"); await pg.wait_for_timeout(700)
                q = await pg.evaluate('__c.q()')
                firsts.add(q['cur']); orders.add(tuple(q['list']))
            check(q['label'] == 'Soul Mix' and sorted(q['list']) == sorted('Soul %d' % i for i in range(8)) and q['idx'] == 0 and q['cur'] == q['list'][0],
                  f'{T} it plays one of its stations, all 8 queued {q}')
            check(len(orders) > 1, f'{T} in a different order each time ({len(orders)} orders, firsts {sorted(firsts)})')
            await pg.evaluate('__t.openNp ? __t.openNp() : openNowPlaying()') if False else None
            await pg.evaluate("document.getElementById('barNextBtn').click()"); await pg.wait_for_timeout(700)
            q2 = await pg.evaluate('__c.q()')
            check(q2['idx'] == 1 and q2['cur'] == q['list'][1], f'{T} Next plays the next of its stations {q2["cur"]}')
            await pg.evaluate("document.getElementById('barPrevBtn').click()"); await pg.wait_for_timeout(700)
            q3 = await pg.evaluate('__c.q()')
            check(q3['idx'] == 0 and q3['cur'] == q['list'][0], f'{T} Previous goes back {q3["cur"]}')
            await pg.screenshot(path=f'{shots}/csfav-playing-{theme}.png')

            # ---- the heart on the custom station's own page ----
            await pg.evaluate("__c.openPage('cs_jazz')"); await pg.wait_for_timeout(900)
            h = await pg.evaluate('__c.pageHeart()')
            check(h['shown'] and not h['on'], f'{T} its page has a heart, not filled yet {h}')
            await pg.evaluate('__c.clickPageHeart()'); await pg.wait_for_timeout(300)
            h = await pg.evaluate('__c.pageHeart()')
            check(h['on'] and ['customStation', 'Late Jazz'] in await pg.evaluate('__c.favs()'), f'{T} tapping it favourites the custom station {h}')
            await pg.screenshot(path=f'{shots}/csfav-page-{theme}.png')
            await pg.evaluate('__c.clickPageHeart()'); await pg.wait_for_timeout(300)
            check(not (await pg.evaluate('__c.pageHeart()'))['on'] and ['customStation', 'Late Jazz'] not in await pg.evaluate('__c.favs()'), f'{T} and again takes it out')
            await pg.evaluate('__c.clickPageHeart()'); await pg.wait_for_timeout(300)

            # ---- Android Auto ----
            await pg.evaluate('__c.car()'); await pg.wait_for_timeout(1500)
            cat = await pg.evaluate('window.__cat')
            cf = (cat or {}).get('lists', {}).get('favorites', [])
            kinds = [(e.get('t'), e.get('title')) for e in cf]
            check(('radio', 'Soul Mix') in kinds and ('radio', 'Late Jazz') in kinds, f'{T} the car\'s Favorites list the custom stations {kinds}')
            check(all(e.get('t') in ('station', 'radio') for e in cf) and len(cf) == 3, f'{T} and only stations, radio rows (no song or artist) {kinds}')
            soul = [e for e in cf if e.get('title') == 'Soul Mix'][0]
            check(soul.get('fyid') == 'cs_soul' and len(cat['lists'].get('fy:cs_soul', [])) == 8, f'{T} the row names its list, which holds its 8 stations')
            java = open(os.path.join(_here, '..', 'android/app/src/main/java/com/markcoleman/amplify/CarLibrary.java')).read()
            check('SHUFFLE_PREFIX + "fy:" + fyid' in java and '"Custom Station"' in java, f'{T} CarLibrary plays it as "shuffle:fy:<id>" (shuffled, skippable)')

            # ---- rename and delete ----
            await pg.evaluate("__c.rename('cs_soul', 'Soul Radio')"); await pg.wait_for_timeout(300)
            check(['customStation', 'Soul Radio'] in await pg.evaluate('__c.favs()') and 'Soul Radio' in await pg.evaluate('__c.row()'), f'{T} a rename follows')
            await pg.evaluate("__c.del('cs_soul')"); await pg.wait_for_timeout(300)
            check(all(f[1] != 'Soul Radio' for f in await pg.evaluate('__c.favs()')) and 'Soul Radio' not in await pg.evaluate('__c.row()'), f'{T} deleting it takes it out of favourites')
            check(not errs, f'{T} no page errors {errs[:3]}')
            await ctx.close()
        await b.close()
    print('ALL PASSED' if not fails else f'FAILED {fails}')

asyncio.run(main())
