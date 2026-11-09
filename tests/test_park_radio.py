"""Build 452: Park radio row on the Disney page.
Run: python3 tests/test_disney_genre.py (screenshots in /tmp/claude-0/t/shots)"""
import asyncio, json, os, shutil, threading, http.server, functools
from playwright.async_api import async_playwright
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = '/tmp/claude-0/t/srv-pk'; SHOTS = '/tmp/claude-0/t/shots'
shutil.rmtree(ROOT, ignore_errors=True); os.makedirs(ROOT); os.makedirs(SHOTS, exist_ok=True)
html = open(os.path.join(HERE, '..', 'www', 'index.html')).read()
mark = '  function searchByTag(tag){'
assert html.count(mark) == 1
hook = """  window.__dz = {
    open: function(t){ searchByTag(t); },
    setLib: function(tracks){ libraryTracks.length = 0; tracks.forEach(function(t){ libraryTracks.push(t); }); },
    stub: function(){
      apiFetch = function(u){ if(/name=exclusively/.test(u)) return Promise.resolve([]); var d = /name=disney/.test(u) ? [{ name: 'Disney Hits Radio', url_resolved: 'http://s/dz1', stationuuid: 'dz1', tags: 'kids', favicon: '' }, { name: 'Disney Classics', url_resolved: 'http://s/dz3', stationuuid: 'dz3', tags: 'kids', favicon: '' }] : [{ name: 'Magic Mix', url_resolved: 'http://s/dz2', stationuuid: 'dz2', tags: 'disney,pop', favicon: '' }]; return Promise.resolve(d); };
      itunesSearchPodcasts = function(){ return Promise.resolve([{ collectionId: 1, collectionName: 'Disney Dreamlight Podcast', artistName: 'Disney', artworkUrl600: '', feedUrl: '' }, { collectionId: 2, collectionName: 'Unrelated Show', artistName: 'Someone' }]); };
      var lib = { movies: [{ id: 'm1', kind: 'movie', title: 'The Lion King', year: 1994, duration: 5300, relPath: 'Movies/The Lion King (1994).mp4', fileName: 'The Lion King (1994).mp4', poster: '', uri: 'x1' }, { id: 'm2', kind: 'movie', title: 'Alien', year: 1979, duration: 7000, relPath: 'Movies/Alien.mp4', fileName: 'Alien.mp4', poster: '', uri: 'x2' }],
        shows: [{ key: 'ducktales', title: 'DuckTales', episodes: [{ relPath: 'TV/DuckTales/s01e01.mp4', season: 1, episode: 1, uri: 'e1', id: 'e1' }], seasons: [1], poster: '', backdrop: '', seasonPosters: {} }, { key: 'seinfeld', title: 'Seinfeld', episodes: [{ relPath: 'TV/Seinfeld/s01e01.mp4', season: 1, episode: 1, uri: 'e2', id: 'e2' }], seasons: [1], poster: '', backdrop: '', seasonPosters: {} }], byId: {}, showsByKey: {} };
      vlib = function(){ return lib; };
    },
    songs: function(){ return localTracksWithTag('Disney').map(function(t){ return t.name; }); },
    many: function(){ var a = []; for(var i = 0; i < 14; i++) a.push({ name: 'Disney Radio ' + i, url_resolved: 'http://s/m' + i, stationuuid: 'm' + i, tags: 'kids', favicon: '' }); var old = apiFetch; apiFetch = function(u){ return /name=disney/.test(u) ? Promise.resolve(a) : Promise.resolve([]); }; },
    setSt: function(f, pl){ favorites.length = 0; f.forEach(function(x){ favorites.push(x); }); stationPlaylists.length = 0; pl.forEach(function(x){ stationPlaylists.push(x); }); },
    home: function(){ openGenresHome(); },
    genres: function(){ return genreOrder.slice(); }
  };
"""
html = html.replace(mark, hook + mark, 1)
open(ROOT + '/index.html', 'w').write(html)
H = functools.partial(http.server.SimpleHTTPRequestHandler, directory=ROOT); H.log_message = lambda *a: None
srv = http.server.ThreadingHTTPServer(('127.0.0.1', 8871), H); threading.Thread(target=srv.serve_forever, daemon=True).start()
fails = []
def check(ok, msg):
    print(('PASS ' if ok else 'FAIL ') + msg)
    if not ok: fails.append(msg)
TRACKS = [{'name': 'Let It Go', 'artist': 'Idina Menzel', 'album': 'Frozen (Soundtrack)', 'uri': 'content://t/1', 'type': 'local', 'localTrack': True, 'tags': ''},
          {'name': 'Circle of Life', 'artist': 'Carmen Twillie', 'album': 'The Lion King', 'uri': 'content://t/2', 'type': 'local', 'localTrack': True, 'tags': ''},
          {'name': 'Zip-a-Dee-Doo-Dah', 'artist': 'Various', 'album': 'Greatest Hits', 'relPath': 'Music/Disney Classics/Zip.mp3', 'uri': 'content://t/3', 'type': 'local', 'localTrack': True, 'tags': ''},
          {'name': 'Purple Rain', 'artist': 'Prince', 'album': 'Live at the Aladdin, Las Vegas', 'uri': 'content://t/5', 'type': 'local', 'localTrack': True, 'tags': ''},
          {'name': 'Slow Me Down', 'artist': 'Emmy Rossum', 'album': 'Inside Out', 'uri': 'content://t/6', 'type': 'local', 'localTrack': True, 'tags': ''},
          {'name': 'S1', 'artist': 'Disney Kids', 'album': 'A', 'uri': 'content://t/7', 'type': 'local', 'localTrack': True, 'tags': ''},
          {'name': 'S2', 'artist': 'Disney Kids', 'album': 'A', 'uri': 'content://t/8', 'type': 'local', 'localTrack': True, 'tags': ''},
          {'name': 'S3', 'artist': 'Disney Kids', 'album': 'A', 'uri': 'content://t/9', 'type': 'local', 'localTrack': True, 'tags': ''},
          {'name': 'Bohemian Rhapsody', 'artist': 'Queen', 'album': 'A Night at the Opera', 'uri': 'content://t/4', 'type': 'local', 'localTrack': True, 'tags': 'rock'}]
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
        for scheme in ('dark', 'light'):
            ctx = await b.new_context(viewport={'width': 390, 'height': 844}, device_scale_factor=2, is_mobile=True, has_touch=True, color_scheme=scheme)
            await ctx.add_init_script("localStorage.setItem('radioPlayerTourSeen','1');")
            pg = await ctx.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
            await pg.route('**/*', lambda r: r.continue_() if r.request.url.startswith('http://127.0.0.1') else r.abort())
            await pg.goto('http://127.0.0.1:8871/index.html'); await pg.wait_for_timeout(2500)
            await pg.evaluate("""() => {
              window.__dz.setLib(%s); window.__dz.stub();
              var mk = (n, u, tags) => ({ name: n, urlToResolve: u, favicon: '', homepage: '', tags: tags || '', country: '', codec: 'MP3', bitrate: 128, stationuuid: null });
              var F = [mk('DMagicWorld', 'http://p/dmw', 'disney,theme park'), mk('Smooth Jazz', 'http://p/jazz', 'jazz')];
              var PL = [{ id: 'pl_x', label: 'Disney Parks Radio', stations: [mk('Sorcerer Radio', 'http://p/sr', 'disney,theme park'), mk("Sorcerer Radio: Loop'd", 'http://p/loopd', 'disney,theme park'), mk('DParkRadio Main', 'http://s/dz1', 'disney,theme park'), mk('DMagicWorld', 'http://p/dmw', 'disney,theme park'), mk('Chill FM', 'http://p/chill', 'chill')] }];
              window.__dz.setSt(F, PL); window.__dz.open('Disney');
            }""" % json.dumps(TRACKS))
            await pg.wait_for_timeout(1500)
            info = await pg.evaluate("""() => ({ heads: Array.prototype.map.call(document.querySelectorAll('.gp-head'), h => h.textContent),
              park: Array.prototype.map.call(document.querySelectorAll('.gp-park-radio .tile-name'), x => x.textContent),
              top: Array.prototype.map.call(document.querySelectorAll('.gp-row:not(.gp-park-radio) .tile-name'), x => x.textContent),
              noX: document.documentElement.scrollWidth <= window.innerWidth })""")
            await pg.screenshot(path=f'{SHOTS}/park-{scheme}.png')
            await pg.evaluate("window.scrollTo(0, document.querySelector('.gp-park-radio').getBoundingClientRect().top + window.scrollY - 520)"); await pg.wait_for_timeout(300)
            await pg.screenshot(path=f'{SHOTS}/park-row-{scheme}.png')
            await pg.evaluate("window.scrollTo(0,0)"); await pg.wait_for_timeout(200)
            check(info['heads'][:2] == ['Top stations', 'Park radio'], f"{scheme}: Park radio sits right below Top stations {info['heads']}")
            check(info['park'] == ['DMagicWorld', 'Sorcerer Radio', "Sorcerer Radio: Loop'd", 'DParkRadio Main'], f"{scheme}: park stations only, no duplicates {info['park']}")
            check('Smooth Jazz' not in info['park'] and 'Chill FM' not in info['park'], f'{scheme}: other stations stay out')
            check(info['noX'], f'{scheme}: no sideways page scroll')
            check('Disney Hits Radio' not in info['top'], f"{scheme}: a park station the directory also lists is not repeated {info['top'][:3]}")
            async def hold(name):
                await pg.evaluate("(n)=>{ var tl=Array.prototype.filter.call(document.querySelectorAll('.gp-park-radio .tile'), x=>x.querySelector('.tile-name').textContent===n)[0]; tl.scrollIntoView({block:'center', inline:'center'}); var r=tl.getBoundingClientRect(); var tc=new Touch({identifier:1,target:tl,clientX:r.left+20,clientY:r.top+20}); tl.dispatchEvent(new TouchEvent('touchstart',{touches:[tc],targetTouches:[tc],changedTouches:[tc],bubbles:true,cancelable:true})); window.__held=tl; window.__tc=tc; }", name)
                await pg.wait_for_timeout(650)
            async def release():
                await pg.evaluate("window.__held.dispatchEvent(new TouchEvent('touchend',{touches:[],changedTouches:[window.__tc],bubbles:true,cancelable:true}))")
            async def pick(label):
                await pg.evaluate("(l)=>Array.prototype.filter.call(document.querySelectorAll('#genreStMenu .np-menu-item'), b=>b.textContent.indexOf(l)>=0)[0].click()", label)
                await pg.wait_for_timeout(400)
            park = lambda: pg.evaluate("Array.prototype.map.call(document.querySelectorAll('.gp-park-radio .tile-name'), x=>x.textContent)")
            await pg.evaluate("window.scrollTo(0,0)"); await pg.wait_for_timeout(300)
            await hold('DMagicWorld')
            items = await pg.evaluate("Array.prototype.map.call(document.querySelectorAll('#genreStMenu .np-menu-item'), b=>b.textContent.trim())")
            check(items == ['Remove from Disney'], f'{scheme}: long-press on the first park station opens the menu {items}')
            await release(); await pick('Move Down')
            o = await park()
            check(o[:2] == ['Sorcerer Radio', 'DMagicWorld'], f'{scheme}: Move Down {o}')
            await hold('DParkRadio Main')
            items = await pg.evaluate("Array.prototype.map.call(document.querySelectorAll('#genreStMenu .np-menu-item'), b=>b.textContent.trim())")
            await pg.screenshot(path=f'{SHOTS}/park-menu-{scheme}.png')
            check(items == ['Move to Top', 'Move Up', 'Remove from Disney'], f'{scheme}: last station menu {items}')
            await release(); await pick('Move to Top')
            o = await park()
            check(o == ['DParkRadio Main', 'Sorcerer Radio', 'DMagicWorld', "Sorcerer Radio: Loop'd"], f'{scheme}: Move to Top {o}')
            await pg.evaluate("window.__dz.open('Disney')"); await pg.wait_for_timeout(900)
            o2 = await park()
            check(o2 == o, f'{scheme}: order survives reopening {o2}')
            saved = await pg.evaluate("JSON.parse(localStorage.getItem('radioPlayerGenreStations')).disney")
            check(saved.get('parkOrder') and not saved.get('order'), f"{scheme}: saved apart from the directory stations' order {saved}")
            await hold("Sorcerer Radio: Loop'd")
            await release(); await pick('Remove from')
            dlg = await pg.evaluate("document.getElementById('confirmOk') && getComputedStyle(document.getElementById('confirmOk')).display !== 'none' && document.getElementById('confirmOk').offsetParent !== null")
            check(bool(dlg), f'{scheme}: removing asks first')
            await pg.screenshot(path=f'{SHOTS}/park-confirm-{scheme}.png')
            await pg.evaluate("document.getElementById('confirmOk').click()"); await pg.wait_for_timeout(400)
            o3 = await park()
            check("Sorcerer Radio: Loop'd" not in o3 and len(o3) == 3, f'{scheme}: removed from the row {o3}')
            top = await pg.evaluate("Array.prototype.map.call(document.querySelectorAll('.gp-row:not(.gp-park-radio) .tile-name, .gp-grid .tile-name'), x=>x.textContent)")
            check("Sorcerer Radio: Loop'd" not in top, f'{scheme}: and does not drop into the other station rows')
            rest = await pg.evaluate("(Array.prototype.filter.call(document.querySelectorAll('.gp-more'), b=>b.textContent.indexOf('Restore')>=0)[0]||{}).textContent")
            check(rest == 'Restore 1 removed station', f'{scheme}: Restore at the bottom ({rest})')
            await hold('DParkRadio Main'); await release(); await pick('Remove from')
            await pg.evaluate("document.getElementById('confirmOk').click()"); await pg.wait_for_timeout(400)
            top = await pg.evaluate("Array.prototype.map.call(document.querySelectorAll('.gp-row:not(.gp-park-radio) .tile-name, .gp-grid .tile-name'), x=>x.textContent)")
            check('Disney Hits Radio' not in top, f'{scheme}: a removed park station the directory also lists stays out of Top stations {top[:3]}')
            await pg.evaluate("Array.prototype.filter.call(document.querySelectorAll('.gp-more'), b=>b.textContent.indexOf('Restore')>=0)[0].click()"); await pg.wait_for_timeout(400)
            o4 = await park()
            check(len(o4) == 4, f'{scheme}: Restore brings them back {o4}')
            await pg.evaluate("window.scrollTo(0,0)"); await pg.wait_for_timeout(300)
            await pg.screenshot(path=f'{SHOTS}/park-after-{scheme}.png')
            await pg.evaluate("window.__dz.open('Jazz')"); await pg.wait_for_timeout(800)
            h2 = await pg.evaluate("Array.prototype.map.call(document.querySelectorAll('.gp-head'), h => h.textContent)")
            check('Park radio' not in h2, f'{scheme}: other genres have no Park radio row {h2}')
            check(not errs, f'{scheme}: no page errors {errs}')
            await ctx.close()
        await b.close()
asyncio.run(main())
print('FAILS', len(fails)); raise SystemExit(1 if fails else 0)
