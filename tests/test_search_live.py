"""Search revised (build 117): tapping the box opens the results page at once, results update
as letters are typed (directories asked once typing pauses), a Top Results tab leads with the
closest matches of every kind (artists, songs, albums, playlists, stations, TV channels,
podcasts), Channels and Playlists tabs, recent searches on an empty box, Back returns to the
same results without searching again, and a pasted link offers to play it.
Run: python3 tests/test_search_live.py (screenshots in /tmp/claude-0/t/shots)"""
import asyncio, os, json, threading, http.server, functools, shutil, subprocess
from playwright.async_api import async_playwright

PORT = 8798
root = '/tmp/claude-0/t/srv_srch'
shots = '/tmp/claude-0/t/shots'
os.makedirs(shots, exist_ok=True)
shutil.rmtree(root, ignore_errors=True)
os.makedirs(root)
HOOK = ("window.videoChannelsAdd = function(c){ addVideoChannel(c); };"
        "window.__t = { tracks: function(){ return libraryTracks.map(function(t){ return t.name; }); },"
        " mk: function(){ stationPlaylists.push({ id: 'pl_mix', label: 'Mix', stations: [{ stationuuid: 'st-1', name: 'Radio One', url: 'http://radio.example/one', urlToResolve: 'http://radio.example/one', favicon: '' }] });"
        "   stationPlaylists.push({ id: 'pl_empty', label: 'Empty', stations: [] }); saveStationPlaylists(); renderStationPlaylistList(); },"
        " pl: function(label){ var p = stationPlaylists.filter(function(x){ return x.label === label; })[0]; return p ? p.stations.map(function(s){ return s.name; }) : null; },"
        " stored: function(label){ var p = JSON.parse(localStorage.getItem('radioPlayerStationPlaylists')).filter(function(x){ return x.label === label; })[0]; return p ? p.stations.map(function(s){ return s.name; }) : null; },"
        " openAlbum: function(a){ var al = buildAlbumIndex().filter(function(x){ return x.album === a; })[0]; openAlbumPage(al.key, null); },"
        " status: function(){ var e = document.getElementById('statusLine') || document.querySelector('.status-line'); return e ? e.textContent : ''; } };\n")
_src = open(os.path.join(os.path.dirname(__file__), '..', 'www', 'index.html')).read()
_mark = '  var coverFlow = null;\n'
assert _src.count(_mark) == 1
open(root + '/index.html', 'w').write(_src.replace(_mark, _mark + HOOK))

M = root + '/Music'
os.makedirs(M, exist_ok=True)
SONGS = [('Ray of Light', 'Madonna', 'Ray of Light', 1), ('Escapism', 'Raye', 'My 21st Century Blues', 1), ('Black Mascara', 'Raye', 'My 21st Century Blues', 2), ('Lone', 'Lee', 'Other', 1)]
for i, (t, a, al, n) in enumerate(SONGS):
    subprocess.run(['ffmpeg', '-loglevel', 'error', '-y', '-f', 'lavfi', '-i', f'sine=frequency={300 + i * 60}:duration=3',
                    '-c:a', 'libmp3lame', '-b:a', '32k', '-metadata', f'title={t}', '-metadata', f'artist={a}',
                    '-metadata', f'album={al}', '-metadata', f'track={n}', f'{M}/{i + 1:02d}.mp3'], check=True)


class Q(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a): pass
H = functools.partial(Q, directory=root)
srv = http.server.ThreadingHTTPServer(('127.0.0.1', PORT), H)
threading.Thread(target=srv.serve_forever, daemon=True).start()
files = [{'uri': f'http://127.0.0.1:{PORT}/Music/{f}', 'name': f, 'relPath': f'Music/{f}', 'type': 'audio/mpeg',
          'size': os.path.getsize(f'{M}/{f}'), 'lastModified': 1700000000000} for f in sorted(os.listdir(M))]
MOCK = """
(function(){
 var picked = %s, listeners = {};
 var impl = {
   pickMusicFolder: function(){ return Promise.resolve({folder:'Music', files:picked, truncated:false}); },
   addListener: function(n, f){ (listeners[n] = listeners[n] || []).push(f); return Promise.resolve({remove:function(){}}); }
 };
 var P = new Proxy({}, {get:function(t,k){
   if(k==='then') return undefined;
   if(k==='setCarLibraryPart') return undefined;
   if(impl[k]) return impl[k];
   return function(){ return Promise.resolve({}); };
 }});
 window.Capacitor = { isNativePlatform:function(){return true;}, getPlatform:function(){return 'android';},
   registerPlugin:function(){ return P; }, Plugins:{AmplifyPlayer:P}, convertFileSrc:function(u){return u;} };
})();
""" % json.dumps(files)

from urllib.parse import urlparse, parse_qs
fails = []
def check(cond, msg):
    print(('PASS ' if cond else 'FAIL ') + msg)
    if not cond: fails.append(msg)
calls = {'name': [], 'pod': []}
SEED = """localStorage.setItem('radioPlayerVideoChannels', JSON.stringify([{id:'link:raytv', name:'Ray TV News', url:'http://tv.example/ray.m3u8', logo:'', cats:['news'], catNames:['News'], src:'link'}]));
localStorage.setItem('radioPlayerStationPlaylists', JSON.stringify([{id:'pl_r', label:'Ray Mix', stations:[]}]));"""

async def route(r):
    u = r.request.url
    if '127.0.0.1' in u: return await r.continue_()
    q = parse_qs(urlparse(u).query)
    if 'radio-browser' in u and 'name' in q:
        word = q['name'][0]; calls['name'].append(word)
        return await r.fulfill(status=200, content_type='application/json', body=json.dumps(
            [{'name': '%s FM %d' % (word.title(), i), 'url_resolved': 'http://s/%s%d' % (word, i), 'stationuuid': '%s%d' % (word, i), 'favicon': '', 'tags': 'x', 'codec': 'MP3', 'country': 'UK'} for i in range(3)]))
    if 'itunes.apple.com/' in u and 'term' in q:
        cb = (q.get('callback') or [''])[0]; term = q['term'][0]; calls['pod'].append(term)
        body_ = json.dumps({'resultCount': 1, 'results': [{'wrapperType': 'track', 'kind': 'podcast', 'collectionId': 5, 'collectionName': term.title() + ' Talks', 'artistName': 'Pod Co', 'artworkUrl600': ''}]})
        return await r.fulfill(status=200, content_type='application/javascript', body=cb + '(' + body_ + ');')
    return await r.abort()

STATE = """(()=>{ var tabs = Array.from(document.querySelectorAll('#searchTabs .home-tab')).map(function(b){ return b.textContent; });
  var act = document.querySelector('#searchTabs .home-tab.active');
  return { heading: document.getElementById('stationsHeading').textContent, tabs: tabs, active: act ? act.textContent : null,
    tabsShown: getComputedStyle(document.getElementById('searchTabs')).display !== 'none',
    rows: Array.from(document.querySelectorAll('#stationsGrid .top-result-row')).map(function(r){
      return [r.dataset.kind, r.querySelector('.song-row-title').textContent, r.querySelector('.song-row-sub').textContent, !!r.querySelector('.top-result-chev'), !!r.querySelector('.row-more-btn')]; }),
    names: Array.from(document.querySelectorAll('#stationsGrid .tile-name')).map(function(n){ return n.textContent; }),
    focused: document.activeElement && document.activeElement.id }; })()"""


async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
        ctx = await b.new_context(viewport={'width': 390, 'height': 844}, device_scale_factor=2, is_mobile=True, has_touch=True, color_scheme='dark')
        await ctx.add_init_script(MOCK)
        await ctx.add_init_script("if(!sessionStorage.getItem('seeded')){ sessionStorage.setItem('seeded','1'); " + SEED + " }")
        pg = await ctx.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.route('**/*', route)
        await pg.goto(f'http://127.0.0.1:{PORT}/index.html'); await pg.wait_for_timeout(2500)
        await pg.evaluate("""(function(){ var ov=document.getElementById('addMusicOverlay'); if(ov) ov.classList.add('open');
          var btn=document.getElementById('addMusicFolderBtn'); btn.disabled=false; btn.click(); })()""")
        for _ in range(60):
            await pg.wait_for_timeout(500)
            if len(await pg.evaluate('__t.tracks()')) >= 4: break
        await pg.evaluate("document.getElementById('addMusicOverlay') && document.getElementById('addMusicOverlay').classList.remove('open')")

        # the Search tab opens the box without the keyboard; tapping the box opens the results page at once
        await pg.evaluate("document.querySelector('.mobile-nav-btn[data-nav=home]').click()"); await pg.wait_for_timeout(600)
        await pg.evaluate("document.querySelector('.mobile-nav-btn[data-nav=search]').click()"); await pg.wait_for_timeout(400)
        s0 = await pg.evaluate(STATE)
        check(s0['heading'] != 'Search' and s0['focused'] != 'searchSheetInput', f"Search tab: box open, no keyboard, page unchanged ({s0['heading']})")
        await pg.tap('#searchSheetInput'); await pg.wait_for_timeout(150)
        s1 = await pg.evaluate(STATE)
        check(s1['heading'] == 'Search' and s1['focused'] == 'searchSheetInput', f"tapping the box opens the results page straight away {s1['heading']}")
        check(not s1['tabsShown'], 'an empty box: no tabs yet')
        check(await pg.evaluate("getComputedStyle(document.getElementById('sectionHeadingRow')).display") == 'none', 'and no heading row on the search page')
        await pg.screenshot(path=f'{shots}/search-open.png')

        # typing updates the page letter by letter
        await pg.keyboard.type('r', delay=0); await pg.wait_for_timeout(200)
        sr = await pg.evaluate(STATE)
        check(sr['heading'] == 'Results for "r"', f"one letter typed: results already ({sr['heading']})")
        await pg.keyboard.type('ay', delay=70); await pg.wait_for_timeout(200)
        sa = await pg.evaluate(STATE)
        check(sa['heading'] == 'Results for "ray"', f"each letter updates the page without pressing Enter ({sa['heading']})")
        check(sa['focused'] == 'searchSheetInput', 'the box keeps the keyboard while results change')
        local_kinds = set(r[0] for r in sa['rows'])
        check({'artists', 'songs', 'channels', 'playlists'} <= local_kinds, f'your own matches show at once, before the directories answer {sorted(local_kinds)}')
        await pg.wait_for_timeout(1200)
        check(len(calls['name']) <= 2 and calls['name'][-1:] == ['ray'], f"the directories are asked once typing pauses, not per letter {calls['name']}")
        s2 = await pg.evaluate(STATE)
        print(s2['tabs']); [print('  ', r) for r in s2['rows']]
        check(s2['tabs'][0] == 'Top Results' and s2['active'] == 'Top Results', f"Top Results is the first tab and open {s2['tabs'][:2]}")
        for lab in ('Stations', 'Artists', 'Albums', 'Songs', 'Podcasts', 'Channels', 'Playlists'):
            check(any(t.startswith(lab) for t in s2['tabs']), f'{lab} tab offered')
        kinds = [r[0] for r in s2['rows']]
        check({'artists', 'songs', 'albums', 'playlists', 'stations', 'channels', 'podcasts'} <= set(kinds), f'Top Results mixes every kind {kinds}')
        check(len(s2['rows']) <= 12, f'at most a dozen ({len(s2["rows"])})')
        subs = {r[0]: r[2] for r in s2['rows']}
        check(subs.get('songs', '').startswith('Song · ') and subs.get('artists') == 'Artist' and subs.get('albums', '').startswith('Album · Raye')
              and subs.get('stations', '').startswith('Station') and subs.get('channels', '').startswith('TV Channel') and subs.get('podcasts', '').startswith('Podcast · '),
              f'each row says what it is {subs}')
        nav = {r[0]: (r[3], r[4]) for r in s2['rows']}
        check(nav['artists'] == (True, False) and nav['albums'] == (True, False) and nav['songs'] == (False, True) and nav['stations'] == (False, True),
              f'places to go get a chevron, things to play a More button, never both {nav}')
        titles = [r[1] for r in s2['rows']]
        check(titles.index('Ray of Light') < titles.index('Raye'), 'closest names first: "Ray of Light" (starts with ray) above Raye (contains it)')
        await pg.screenshot(path=f'{shots}/search-top.png')
        # the tabs stay fixed under the header as the results scroll
        t0 = await pg.evaluate("document.getElementById('searchTabs').getBoundingClientRect().top")
        await pg.evaluate("window.scrollTo(0, 500)"); await pg.wait_for_timeout(300)
        tb = await pg.evaluate("""(()=>{ var t = document.getElementById('searchTabs').getBoundingClientRect();
          var el = document.elementFromPoint(200, t.top + t.height / 2); return { top: t.top, y: window.scrollY, onTop: !!(el && el.closest('#searchTabs')) }; })()""")
        check(tb['y'] > 100 and 58 <= tb['top'] <= 72 and tb['onTop'], f'tabs stay fixed under the header while scrolling (was {t0}, now {tb})')
        await pg.screenshot(path=f'{shots}/search-sticky.png')
        await pg.evaluate("window.scrollTo(0, 0)"); await pg.wait_for_timeout(200)
        # no heading row above the tabs (no "Results for", count, save or clear icons)
        hr = await pg.evaluate("""(()=>{ var r = document.getElementById('sectionHeadingRow');
          return { shown: getComputedStyle(r).display !== 'none' && r.getBoundingClientRect().height > 0,
                   tabsTop: document.getElementById('searchTabs').getBoundingClientRect().top,
                   save: !!document.getElementById('searchSaveBtn') }; })()""")
        check(not hr['shown'], f'no heading, count or icons above the tabs {hr}')
        check(not hr['save'], 'no Save Search on Top Results')
        # Save Search: on the Stations tab, far right, above the results, text only
        await pg.evaluate("Array.from(document.querySelectorAll('#searchTabs .home-tab')).filter(function(b){ return /^Stations/.test(b.textContent); })[0].click()"); await pg.wait_for_timeout(300)
        sv = await pg.evaluate("""(()=>{ var b = document.getElementById('searchSaveBtn'); if(!b) return null;
          var r = b.getBoundingClientRect(), g = document.getElementById('stationsGrid').getBoundingClientRect();
          var first = document.querySelector('#stationsGrid .tile:not(.search-tab-actions)');
          return { text: b.textContent.trim(), icon: !!b.querySelector('i, svg'), mid: Math.round((r.left + r.right) / 2), gridMid: Math.round((g.left + g.right) / 2),
                   above: first ? r.bottom <= first.getBoundingClientRect().top + 1 : null, shownText: getComputedStyle(b).textTransform }; })()""")
        print('save', sv)
        check(sv and sv['text'] == 'Save as Custom Station' and not sv['icon'], f'Stations tab has a "Save as Custom Station" button with no icon {sv}')
        check(sv and abs(sv['mid'] - sv['gridMid']) <= 2 and sv['above'], f'centred, above the results {sv}')
        await pg.screenshot(path=f'{shots}/search-stations-save.png')
        await pg.evaluate("document.getElementById('searchSaveBtn').click()"); await pg.wait_for_timeout(300)
        md = await pg.evaluate("[document.getElementById('customSearchOverlay').classList.contains('open'), document.getElementById('customSearchQueryInput').value]")
        check(md == [True, 'ray'], f'it opens Save Search with the query filled in {md}')
        await pg.evaluate("document.getElementById('customSearchOverlay').classList.remove('open')")
        await pg.evaluate("Array.from(document.querySelectorAll('#searchTabs .home-tab'))[0].click()"); await pg.wait_for_timeout(300)

        # Channels tab
        await pg.evaluate("Array.from(document.querySelectorAll('#searchTabs .home-tab')).filter(function(b){ return /^Channels/.test(b.textContent); })[0].click()"); await pg.wait_for_timeout(300)
        ch = await pg.evaluate(STATE)
        check('Ray TV News' in ch['names'] and 'Search all TV channels' in ch['names'], f"Channels tab: your channel, and a way to search the whole directory {ch['names']}")
        # more channels, to check the rows' spacing: add three to My Channels and search again
        await pg.evaluate("""(()=>{ ['Ray One','Ray Two','Ray Three'].forEach(function(n, i){ videoChannelsAdd({ id: 'link:r' + i, name: n, url: 'http://tv.example/r' + i + '.m3u8', logo: '', cats: [], src: 'link' }); }); })()""")
        await pg.fill('#searchSheetInput', 'ray '); await pg.wait_for_timeout(300); await pg.fill('#searchSheetInput', 'ray'); await pg.wait_for_timeout(1200)
        await pg.evaluate("Array.from(document.querySelectorAll('#searchTabs .home-tab')).filter(function(b){ return /^Channels/.test(b.textContent); })[0].click()"); await pg.wait_for_timeout(300)
        rows = await pg.evaluate("Array.from(document.querySelectorAll('#stationsGrid .ch-item')).map(function(r){ var b = r.getBoundingClientRect(), a = r.querySelector('.tile-art').getBoundingClientRect(); return [Math.round(b.top), Math.round(b.bottom), Math.round(a.top), Math.round(a.bottom)]; })")
        print('channel rows', rows)
        check(len(rows) == 4 and all(rows[i + 1][0] >= rows[i][1] - 1 for i in range(len(rows) - 1)), f'channel rows stack without overlapping {rows}')
        check(all(r[2] >= r[0] and r[3] <= r[1] for r in rows) and all(r[1] - r[0] >= 50 for r in rows), 'each logo sits inside its own row, with room around it')
        await pg.screenshot(path=f'{shots}/search-channels.png')
        await pg.screenshot(path=f'{shots}/search-channels.png')
        await pg.evaluate("Array.from(document.querySelectorAll('#searchTabs .home-tab'))[0].click()"); await pg.wait_for_timeout(300)

        # open an artist from Top Results, then Back: same results, no new request
        n0 = len(calls['name'])
        await pg.evaluate("Array.from(document.querySelectorAll('.top-result-row')).filter(function(r){ return r.dataset.kind === 'artists'; })[0].click()")
        await pg.wait_for_timeout(700)
        check(await pg.evaluate("document.body.classList.contains('artist-open') && /Raye/.test(document.getElementById('artistHeroName').textContent)"), 'the artist row opens the artist page')
        await pg.evaluate("document.getElementById('detailBackBtn').click()"); await pg.wait_for_timeout(700)
        sb = await pg.evaluate(STATE)
        check(sb['heading'] == 'Results for "ray"' and sb['active'] == 'Top Results' and len(sb['rows']) == len(s2['rows']), f"Back returns to the same results ({sb['heading']}, {sb['active']})")
        check(len(calls['name']) == n0, f'...without asking the directory again ({len(calls["name"]) - n0} requests)')
        check(await pg.evaluate("document.getElementById('searchSheetInput').value") == 'ray', 'the box still says ray')

        # empty the box: recent searches
        await pg.tap('#searchSheetInput')
        for _ in range(3): await pg.keyboard.press('Backspace')
        await pg.wait_for_timeout(300)
        se = await pg.evaluate(STATE)
        check(se['heading'] == 'Search' and 'ray' in se['names'] and not se['tabsShown'], f"an emptied box shows recent searches {se['names']}")
        await pg.screenshot(path=f'{shots}/search-recents.png')
        await pg.evaluate("Array.from(document.querySelectorAll('.recent-search-row')).filter(function(r){ return r.textContent.trim() === 'ray'; })[0].click()")
        await pg.wait_for_timeout(500)
        check((await pg.evaluate(STATE))['heading'] == 'Results for "ray"' and await pg.evaluate("document.getElementById('searchSheetInput').value") == 'ray', 'tapping a recent search runs it')

        # a pasted link offers to play it
        await pg.fill('#searchSheetInput', 'http://example.com/live.mp3'); await pg.wait_for_timeout(300)
        sl = await pg.evaluate(STATE)
        check('Play this stream' in sl['names'], f"a stream link offers to play it {sl['names']}")

        # Enter still works, and searches straight away
        await pg.fill('#searchSheetInput', 'madonna'); await pg.keyboard.press('Enter'); await pg.wait_for_timeout(500)
        check(calls['name'][-1] == 'madonna', f"Enter asks the directory at once {calls['name'][-2:]}")
        check((await pg.evaluate(STATE))['heading'] == 'Results for "madonna"', 'Enter shows the results')
        check(not errs, f'no page errors {errs[:3]}')
        await b.close()
    print('ALL PASSED' if not fails else f'FAILED {fails}')

asyncio.run(main())
