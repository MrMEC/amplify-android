"""Build 150: "<artist> Radio" for every artist with 3+ songs. It leads the Stations section of
the artist page (with a radio badge), plays all their songs shuffled and never runs out, goes in
Recent Stations, can be favourited (Home Favorites plays it), its cover can be set by hand, it
appears/disappears as songs are added/removed, the artist Play uses it, and the car gets it.
Run: python3 tests/test_artist_radio.py (screenshots in /tmp/claude-0/t/shots)"""
import asyncio, os, json, subprocess
HERE = os.path.dirname(os.path.abspath(__file__))
src = open(os.path.join(HERE, 'test_station_skip.py')).read()
head = src[:src.index('async def main()')]
head = head.replace("'/tmp/claude-0/t/srv_skip'", "'/tmp/claude-0/t/srv_radio'").replace('PORT = 8794', 'PORT = 8813')
head = head.replace("for i, (t, a) in enumerate([('Song 1', 'Ann'), ('Song 2', 'Bob'), ('Song 3', 'Bob')]):",
                    "for i, (t, a) in enumerate([('Song 1', 'Ann'), ('Song 2', 'Bob'), ('Song 3', 'Bob'), ('Song 4', 'Bob'), ('Song 5', 'Bob'), ('Song 6', 'Bob')]):")
HOOKS = ("noStations: function(){ artistStations = []; artistStationsFailed = false; artistStationsPromise = Promise.resolve(artistStations); },"
         " favs: function(){ return favorites.map(function(f){ return { type: f.type, key: favKey(f), name: f.name }; }); },"
         " recent: function(){ return recentStations.map(function(f){ return favKey(f); }); },"
         " next: function(){ return playNextInLine(); },"
         " home: function(){ loadTopStations(); },"
         " addAnn: function(n){ var t = libraryTracks.filter(function(x){ return x.artist === 'Ann'; })[0]; for(var i = 0; i < n; i++){ var c = Object.assign({}, t, { localId: t.localId + '-x' + i + Math.random(), name: 'Ann Extra ' + i }); libraryTracks.push(c); libraryById[favKey(c)] = c; } },"
         " dropBob: function(n){ for(var i = 0; i < n; i++){ var j = -1; libraryTracks.forEach(function(x, k){ if(x.artist === 'Bob') j = k; }); if(j >= 0){ delete libraryById[favKey(libraryTracks[j])]; libraryTracks.splice(j, 1); } } },"
         " prune: function(){ pruneStaleLibraryRefs(); },"
         " skip: function(){")
head = head.replace('" skip: function(){', '" ' + HOOKS)
head = head.replace("setSkip: function(o){", "setCarCatalog: function(o){ window.__car = o.json; return Promise.resolve({}); }, setSkip: function(o){")
assert 'Song 6' in head and 'dropBob' in head and '__car' in head
exec(head)
from playwright.async_api import async_playwright

async def main():
    subprocess.run(['ffmpeg', '-loglevel', 'error', '-y', '-f', 'lavfi', '-i', 'color=c=purple:s=200x200', '-frames:v', '1', f'{root}/cover.png'], check=True)
    import base64
    global COVER
    COVER = 'data:image/png;base64,' + base64.b64encode(open(f'{root}/cover.png', 'rb').read()).decode()
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
        ctx = await b.new_context(viewport={'width': 390, 'height': 844}, device_scale_factor=2, is_mobile=True, has_touch=True, color_scheme='dark')
        await ctx.add_init_script(MOCK)
        pg = await ctx.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.route('**/*', lambda route: route.continue_() if '127.0.0.1' in route.request.url else route.abort())
        await pg.goto(f'http://127.0.0.1:{PORT}/index.html'); await pg.wait_for_timeout(2500)
        await pg.evaluate("""(function(){ var ov=document.getElementById('addMusicOverlay'); if(ov) ov.classList.add('open');
          var btn=document.getElementById('addMusicFolderBtn'); btn.disabled=false; btn.click(); })()""")
        for _ in range(60):
            await pg.wait_for_timeout(500)
            if len(await pg.evaluate('__t.tracks()')) >= 6: break
        await pg.evaluate('__t.noStations()')
        q = lambda: pg.evaluate('__t.q()')
        PAGE = """(()=>{ var labels = Array.from(document.querySelectorAll('#stationsGrid .grid-section-label')).map(function(e){ return e.textContent; });
          var tiles = Array.from(document.querySelectorAll('#stationsGrid .tile')).map(function(t){ var a = t.querySelector('.tile-art'); return { key: t.dataset.key, name: (t.querySelector('.tile-name') || {}).textContent, badge: a ? a.classList.contains('art-radio') : false, img: a && a.querySelector('img') ? a.querySelector('img').src : '' }; });
          return { labels: labels, tiles: tiles }; })()"""
        # Bob: 5 songs -> Bob Radio; Ann: 1 song -> none
        await pg.evaluate("__t.openArtist('Bob')"); await pg.wait_for_timeout(900)
        pb = await pg.evaluate(PAGE); print(pb)
        check(pb['tiles'] and pb['tiles'][0]['key'].startswith('artistradio:') and pb['tiles'][0]['name'] == 'Bob Radio',
              f'Bob’s page leads with "Bob Radio" {pb["tiles"][:1]}')
        check(pb['labels'] and pb['labels'][0].startswith('Station'), f'under Stations {pb["labels"]}')
        check(pb['tiles'][0]['badge'], 'with a radio badge on its picture')
        await pg.screenshot(path=f'{shots}/radio-artist-page.png')
        await pg.evaluate("__t.openArtist('Ann')"); await pg.wait_for_timeout(700)
        pa = await pg.evaluate(PAGE)
        check(not any(t['key'].startswith('artistradio:') for t in pa['tiles']), f'Ann (1 song) has no Radio {pa}')
        # play Bob Radio from its tile
        await pg.evaluate("__t.openArtist('Bob')"); await pg.wait_for_timeout(800)
        await pg.click('#stationsGrid .tile[data-key^="artistradio:"]'); await pg.wait_for_timeout(600)
        s = await q(); print(s)
        bob = ['Song 2', 'Song 3', 'Song 4', 'Song 5', 'Song 6']
        check(sorted(s['list'][:5]) == bob and set(s['list']) == set(bob) and len(s['list']) >= 13 and s['cur'] == s['list'][0] and s['label'] == 'Bob Radio', f'plays all of Bob’s songs, shuffled, as "Bob Radio", a dozen songs ahead {s}')
        rk = pb['tiles'][0]['key']
        check((await pg.evaluate('__t.recent()'))[:2].count(rk) == 1, f'goes into Recent {await pg.evaluate("__t.recent()")}')
        # never runs out
        played = [s['cur']]
        for i in range(14):
            ok = await pg.evaluate('__t.next()'); await pg.wait_for_timeout(250)
            s2 = await q(); played.append(s2['cur'])
            if not ok: break
        print(played)
        check(len(played) == 15 and all(x in bob for x in played), f'keeps going past the end of the shuffle, only Bob’s songs ({len(played)} played)')
        check(all(played[i] != played[i + 1] for i in range(len(played) - 1)), 'never the same song twice in a row')
        check(set(played[:5]) == set(bob) and set(played[5:10]) == set(bob), 'each round plays every song once')
        # favourite it from the tile
        await pg.click('#stationsGrid .tile[data-key^="artistradio:"] .tile-fav'); await pg.wait_for_timeout(300)
        favs = await pg.evaluate('__t.favs()')
        check(any(f['key'] == rk and f['name'] == 'Bob Radio' for f in favs), f'favourited {favs}')
        # artist Play uses the radio
        await pg.click('#artistPlayBtn'); await pg.wait_for_timeout(300)  # pauses (already Bob's)
        await pg.evaluate("__t.openArtist('Ann')"); await pg.wait_for_timeout(500)
        await pg.click('#artistPlayBtn'); await pg.wait_for_timeout(500)
        await pg.evaluate("__t.openArtist('Bob')"); await pg.wait_for_timeout(700)
        await pg.click('#artistPlayBtn'); await pg.wait_for_timeout(500)
        s = await q()
        check(s['label'] == 'Bob Radio' and sorted(s['list'][:5]) == bob, f'Play on Bob’s page starts Bob Radio {s}')
        # custom cover
        await pg.click('#artistMenuBtn'); await pg.wait_for_timeout(300)
        vis = await pg.evaluate("getComputedStyle(document.getElementById('artistRadioArtBtn')).display")
        check(vis != 'none', 'the artist menu has "Edit radio cover"')
        await pg.click('#artistRadioArtBtn'); await pg.wait_for_timeout(400)
        await pg.fill('#artUrlInput', COVER)
        await pg.click('#artUrlSaveBtn'); await pg.wait_for_timeout(700)
        pb2 = await pg.evaluate(PAGE)
        t0 = [t for t in pb2['tiles'] if t['key'] == rk][0]
        check(t0['img'] == COVER, f'the Radio tile shows the new cover {t0}')
        hero = await pg.evaluate("(document.querySelector('#artistHeroArt img') || {}).src || ''")
        check(hero != COVER, f'the artist picture itself is unchanged {hero}')
        # Home favourites: the tile, with the cover, plays it
        await pg.evaluate('__t.home()'); await pg.wait_for_timeout(900)
        home = await pg.evaluate("""(()=>{ var t = document.querySelector('#favoritesGrid .tile[data-key^="artistradio:"]'); if(!t) return null; var i = t.querySelector('.tile-art img'); return { name: t.querySelector('.tile-name').textContent, img: i ? i.src : '' }; })()""")
        check(home and home['name'] == 'Bob Radio' and home['img'] == COVER, f'on Home Favorites with its cover {home}')
        await pg.screenshot(path=f'{shots}/radio-home.png')
        await pg.evaluate("__t.openArtist('Ann')"); await pg.wait_for_timeout(400); await pg.click('#artistPlayBtn'); await pg.wait_for_timeout(400)
        await pg.evaluate('__t.home()'); await pg.wait_for_timeout(700)
        await pg.click('#favoritesGrid .tile[data-key^="artistradio:"]'); await pg.wait_for_timeout(600)
        s = await q()
        check(s['label'] == 'Bob Radio' and s['cur'] in bob, f'tapping it on Home plays it {s}')
        # the car
        await pg.evaluate('window.AmplifyPublishCarMenu && window.AmplifyPublishCarMenu()'); await pg.wait_for_timeout(1500)
        car = await pg.evaluate('window.__car || ""')
        cat = json.loads(car) if car else {}
        cf = [e for e in (cat.get('lists', {}).get('favorites') or []) if e.get('t') == 'radio']
        check(cf and cf[0]['title'] == 'Bob Radio' and cf[0].get('key'), f'the car gets it as a Radio row {cf}')
        # appears automatically: Ann reaches 3 songs
        await pg.evaluate('__t.addAnn(2)')
        await pg.evaluate("__t.openArtist('Ann')"); await pg.wait_for_timeout(700)
        pa2 = await pg.evaluate(PAGE)
        check(pa2['tiles'] and pa2['tiles'][0]['name'] == 'Ann Radio', f'Ann gets a Radio once she has 3 songs {pa2["tiles"][:1]}')
        # goes when Bob drops below 3, and his favourite with it
        await pg.evaluate('__t.dropBob(3)'); await pg.evaluate('__t.prune()')
        await pg.evaluate("__t.openArtist('Bob')"); await pg.wait_for_timeout(700)
        pb3 = await pg.evaluate(PAGE)
        check(not any(t['key'].startswith('artistradio:') for t in pb3['tiles']), f'Bob (2 songs) loses his Radio {pb3}')
        check(not any(f['key'] == rk for f in await pg.evaluate('__t.favs()')), 'and it leaves Favorites')
        check(not errs, f'no page errors {errs[:3]}')
        await b.close()
    print('ALL PASSED' if not fails else f'FAILED {fails}')

asyncio.run(main())
