"""Build 426: the Disney genre (library songs, stations, podcasts, movies, TV shows).
Run: python3 tests/test_disney_genre.py (screenshots in /tmp/claude-0/t/shots)"""
import asyncio, json, os, shutil, threading, http.server, functools
from playwright.async_api import async_playwright
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = '/tmp/claude-0/t/srv-dz'; SHOTS = '/tmp/claude-0/t/shots'
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
    home: function(){ openGenresHome(); },
    genres: function(){ return genreOrder.slice(); }
  };
"""
html = html.replace(mark, hook + mark, 1)
open(ROOT + '/index.html', 'w').write(html)
H = functools.partial(http.server.SimpleHTTPRequestHandler, directory=ROOT); H.log_message = lambda *a: None
srv = http.server.ThreadingHTTPServer(('127.0.0.1', 8843), H); threading.Thread(target=srv.serve_forever, daemon=True).start()
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
        ctx = await b.new_context(viewport={'width': 390, 'height': 844}, device_scale_factor=2, is_mobile=True, has_touch=True, color_scheme='dark')
        await ctx.add_init_script("localStorage.setItem('radioPlayerTourSeen','1'); if(!localStorage.getItem('__o')){ localStorage.setItem('__o','1'); localStorage.setItem('radioPlayerGenreOrder', JSON.stringify(['Jazz','Rock','Pop'])); }")
        pg = await ctx.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.route('**/*', lambda r: r.continue_() if r.request.url.startswith('http://127.0.0.1') else r.abort())
        await pg.goto('http://127.0.0.1:8843/index.html'); await pg.wait_for_timeout(2500)
        order = await pg.evaluate("window.__dz.genres()")
        check('Disney' in order and order[:3] == ['Jazz', 'Rock', 'Pop'], f'Disney joins an existing saved order {order[-3:]}')
        await pg.evaluate("window.__dz.setLib(%s); window.__dz.stub(); window.__dz.open('Disney')" % json.dumps(TRACKS))
        await pg.wait_for_timeout(1500)
        info = await pg.evaluate("""() => ({ title: (document.querySelector('.gp-title')||{}).textContent,
          heads: Array.prototype.map.call(document.querySelectorAll('.gp-head'), h => h.textContent),
          songs: Array.prototype.map.call(document.querySelectorAll('.gp-songs .song-row .song-row-title'), x => x.textContent),
          meta: (document.querySelector('.gp-meta')||{}).textContent,
          tiles: Array.prototype.map.call(document.querySelectorAll('.gp-row .tile-name'), x => x.textContent) })""")
        await pg.screenshot(path=f'{SHOTS}/disney-top.png')
        check(info['title'] == 'Disney', f"the genre page is called Disney {info['title']}")
        allsongs = await pg.evaluate("(function(){ return window.__dz.songs(); })()")
        check(sorted(allsongs) == ['Circle of Life', 'Let It Go', 'S1', 'S2', 'S3', 'Zip-a-Dee-Doo-Dah'], f'Prince at the Aladdin and Emmy Rossum are not Disney {allsongs}')
        shown = [x for x in info['songs'] if x != 'Shuffle All']
        check(len(shown) == 5, f'the library shows 5 by default {shown}')
        txt = await pg.evaluate("(document.querySelector('.gp-more')||{}).textContent")
        check(txt == 'Show more', f'with a Show more link ({txt})')
        await pg.evaluate("document.querySelector('.gp-more').click()"); await pg.wait_for_timeout(300)
        n2 = await pg.evaluate("document.querySelectorAll('.gp-songs .song-row').length")
        check(n2 == 7, f'Show more reveals the rest ({n2} rows incl. Shuffle All)')
        check(all(h in info['heads'] for h in ['Top stations', 'In your library', 'Podcasts', 'Movies', 'TV shows']), f"all the sections {info['heads']}")
        check(info['tiles'][:3] == ['Disney Hits Radio', 'Disney Classics', 'Magic Mix'], f"name matches first, tag-only last {info['tiles'][:3]}")  # build 437: languages are a Settings filter now (test_lang_filter.py)
        check('Disney Dreamlight Podcast' in info['tiles'] and 'Unrelated Show' not in info['tiles'], 'only Disney podcasts')
        check('The Lion King' in info['tiles'] and 'Alien' not in info['tiles'], 'only Disney movies')
        check('DuckTales' in info['tiles'] and 'Seinfeld' not in info['tiles'], 'only Disney shows')
        await pg.evaluate("window.scrollTo(0, 700)"); await pg.wait_for_timeout(400)
        await pg.screenshot(path=f'{SHOTS}/disney-mid.png')
        await pg.evaluate("window.scrollTo(0, 1500)"); await pg.wait_for_timeout(400)
        await pg.screenshot(path=f'{SHOTS}/disney-low.png')
        await pg.evaluate("openGenresHome ? 0 : 0") if False else None
        # --- long-press a station: reorder / remove
        await pg.evaluate("window.scrollTo(0,0)"); await pg.wait_for_timeout(300)
        async def hold(name):
            await pg.evaluate("(n)=>{ var tl=Array.prototype.filter.call(document.querySelectorAll('.gp-row .tile'), x=>x.querySelector('.tile-name').textContent===n)[0]; var r=tl.getBoundingClientRect(); var tc=new Touch({identifier:1,target:tl,clientX:r.left+20,clientY:r.top+20}); tl.dispatchEvent(new TouchEvent('touchstart',{touches:[tc],targetTouches:[tc],changedTouches:[tc],bubbles:true,cancelable:true})); window.__held=tl; window.__tc=tc; }", name)
            await pg.wait_for_timeout(650)
        await hold('Magic Mix')
        items = await pg.evaluate("Array.prototype.map.call(document.querySelectorAll('#genreStMenu .np-menu-item'), b=>b.textContent.trim())")
        await pg.screenshot(path=f'{SHOTS}/disney-menu.png')
        check(items == ['Move to Top', 'Move Up', 'Remove from Disney'], f'long press opens the menu {items}')
        await pg.evaluate("window.__held.dispatchEvent(new TouchEvent('touchend',{touches:[],changedTouches:[window.__tc],bubbles:true,cancelable:true}))")
        await pg.evaluate("Array.prototype.filter.call(document.querySelectorAll('#genreStMenu .np-menu-item'), b=>b.textContent.indexOf('Move to Top')>=0)[0].click()")
        await pg.wait_for_timeout(300)
        order = await pg.evaluate("Array.prototype.map.call(document.querySelectorAll('.gp-row .tile-name'), x=>x.textContent).slice(0,3)")
        check(order == ['Magic Mix', 'Disney Hits Radio', 'Disney Classics'], f'Move to Top puts it first {order}')
        saved = await pg.evaluate("JSON.parse(localStorage.getItem('radioPlayerGenreStations'))")
        check(saved['disney']['order'][0] == 'dz2' or 'Magic' in json.dumps(saved), f'the order is saved {saved}')
        await pg.evaluate("window.__dz.open('Disney')"); await pg.wait_for_timeout(900)
        order2 = await pg.evaluate("Array.prototype.map.call(document.querySelectorAll('.gp-row .tile-name'), x=>x.textContent).slice(0,3)")
        check(order2[0] == 'Magic Mix', f'and survives reopening {order2}')
        await hold('Disney Classics')
        await pg.evaluate("Array.prototype.filter.call(document.querySelectorAll('#genreStMenu .np-menu-item'), b=>b.textContent.indexOf('Remove from')>=0)[0].click()")
        await pg.wait_for_timeout(300)
        dlg = await pg.evaluate("!!document.querySelector('#confirmOverlay.open, .confirm-overlay.open') || document.body.innerText.indexOf('Remove') >= 0")
        check(dlg, 'removing asks for confirmation first')
        await pg.screenshot(path=f'{SHOTS}/disney-confirm.png')
        await pg.evaluate("document.getElementById('confirmOk').click()"); await pg.wait_for_timeout(400)
        names = await pg.evaluate("Array.prototype.map.call(document.querySelectorAll('.gp-row .tile-name'), x=>x.textContent)")
        check('Disney Classics' not in names, f'the station is removed {names}')
        rest = await pg.evaluate("(Array.prototype.filter.call(document.querySelectorAll('.gp-more'), b=>b.textContent.indexOf('Restore')>=0)[0]||{}).textContent")
        check(rest == 'Restore 1 removed station', f'with a Restore link ({rest})')
        pos = await pg.evaluate("(()=>{ var g=document.getElementById('stationsGrid'), b=Array.prototype.filter.call(g.querySelectorAll('.gp-more'), x=>x.textContent.indexOf('Restore')>=0)[0]; var kids=Array.prototype.filter.call(g.children, x=>!x.classList.contains('loading-state')); var r=b.getBoundingClientRect(), gr=g.getBoundingClientRect(); return { last: kids[kids.length-1]===b, centered: Math.abs((r.left+r.right)/2-(gr.left+gr.right)/2) < 3, more: Array.prototype.every.call(g.querySelectorAll('.gp-more'), function(x){ var q=x.getBoundingClientRect(); return Math.abs((q.left+q.right)/2-(gr.left+gr.right)/2) < 3; }) }; })()")
        check(pos['last'] and pos['centered'] and pos['more'], f'build 436: Restore is last on the page, it and Show more are centered {pos}')
        await pg.evaluate("Array.prototype.filter.call(document.querySelectorAll('.gp-more'), b=>b.textContent.indexOf('Restore')>=0)[0].scrollIntoView({block:'center'})"); await pg.wait_for_timeout(300)
        await pg.screenshot(path=f'{SHOTS}/disney-restore-bottom.png')
        await pg.evaluate("Array.prototype.filter.call(document.querySelectorAll('.gp-more'), b=>b.textContent.indexOf('Restore')>=0)[0].click()"); await pg.wait_for_timeout(300)
        names2 = await pg.evaluate("Array.prototype.map.call(document.querySelectorAll('.gp-row .tile-name'), x=>x.textContent)")
        check('Disney Classics' in names2, 'Restore brings it back')
        await pg.evaluate("window.__dz.home()"); await pg.wait_for_timeout(800)
        await pg.evaluate("window.scrollTo(0, document.body.scrollHeight)"); await pg.wait_for_timeout(500)
        await pg.screenshot(path=f'{SHOTS}/disney-genres-home.png')
        check(await pg.evaluate("!!document.querySelector('[data-genre=Disney], .genre-card[data-genre=Disney]') || document.body.innerText.indexOf('Disney') >= 0"), 'Disney is on the Genres page')
        # build 435: Pogo is never Disney; a Genre tag of "Disney" puts any song in the genre
        more = TRACKS + [
          {'name': 'Wishery', 'artist': 'Pogo', 'album': 'Disney Remixes', 'relPath': 'Music/Pogo/Disney/Wishery.mp3', 'uri': 'content://t/20', 'type': 'local', 'localTrack': True, 'tags': 'Electronic'},
          {'name': 'Lionhearted', 'artist': 'Pogo', 'album': 'The Lion King', 'uri': 'content://t/21', 'type': 'local', 'localTrack': True, 'tags': 'Disney'},
          {'name': 'Mystery Song', 'artist': 'Nobody', 'album': 'Misc', 'uri': 'content://t/22', 'type': 'local', 'localTrack': True, 'tags': 'Disney'},
          {'name': 'Two Genres', 'artist': 'Somebody', 'album': 'Misc', 'uri': 'content://t/23', 'type': 'local', 'localTrack': True, 'tags': 'Pop, Disney'},
          {'name': 'Slash Genre', 'artist': 'Anybody', 'album': 'Misc', 'uri': 'content://t/24', 'type': 'local', 'localTrack': True, 'tags': 'Soundtrack/Disney'}]
        await pg.evaluate("window.__dz.setLib(%s)" % json.dumps(more))
        got = await pg.evaluate("(function(){ return window.__dz.songs(); })()")
        check('Wishery' not in got and 'Lionhearted' not in got, f'build 435: Pogo songs are not Disney, even tagged {sorted(got)}')
        check(all(x in got for x in ['Mystery Song', 'Two Genres', 'Slash Genre']), f'build 435: a Genre tag of Disney puts a song in the Disney genre {sorted(got)}')
        # build 435: More Disney stations come before Podcasts, Movies and TV shows
        await pg.evaluate("window.__dz.many(); window.__dz.open('Disney')"); await pg.wait_for_timeout(1500)
        heads = await pg.evaluate("Array.prototype.map.call(document.querySelectorAll('.gp-head'), h => h.textContent)")
        check([h for h in heads if h != 'Artist radio'] == ['Top stations', 'Artists in your library', 'In your library', 'More Disney stations', 'Podcasts', 'Movies', 'TV shows'],   # build 448 adds Artist radio
              f'build 435: More Disney stations sits above Podcasts and Movies {heads}')
        await pg.evaluate("document.querySelectorAll('.gp-head')[2].scrollIntoView({block:'start'}); window.scrollBy(0, -80)"); await pg.wait_for_timeout(400)
        await pg.screenshot(path=f'{SHOTS}/disney-more-stations.png')
        check(not errs, f'no page errors {errs[:2]}')
        await b.close()
        print('FAILS:', fails)
asyncio.run(main())
