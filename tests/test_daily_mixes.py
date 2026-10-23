"""Build 219: Daily Mix 1-5, Discover, Hear It Again and Artist Videos rows on Home, under Top 100.
Each mix row shows 20 songs and its heading opens the whole list; Daily Mix features one of the most
played artists plus similar library artists (Deezer related, same genre) ; Discover/Hear It Again use
song play counts; Artist Videos is one artist's videos headed by their name. Lists stay the same all
day and are remade the next. Run: python3 tests/test_daily_mixes.py (screenshots in /tmp/claude-0/t/shots)"""
import sys as _nsys, os as _nos; _nsys.path.insert(0, _nos.path.dirname(_nos.path.abspath(__file__))); from notice_auto import AUTO_NOTICE
import asyncio, os, json, threading, http.server, functools, shutil, subprocess, sys
from playwright.async_api import async_playwright

PORT = 8803
root = '/tmp/claude-0/t/srv_daily'
shots = '/tmp/claude-0/t/shots'
os.makedirs(shots, exist_ok=True)
shutil.rmtree(root, ignore_errors=True)
os.makedirs(root)
HOOK = ("window.__d = { n: function(){ return libraryTracks.length; }, home: function(){ loadTopStations(); }, st: function(){ return window.__amplifyDaily(); },"
        " names: function(id){ var m = dailyMixFor(id); return m ? dailyMixSongs(m).map(function(t){ return t.artist + '|' + t.name; }) : null; },"
        " plays: function(){ var p = {}; ['Prince', 'Madonna', 'Kay', 'Earth, Wind & Fire', 'Rick James', 'Lee'].forEach(function(n, i){ p[artistMatchKey(n)] = { name: n, count: [40, 30, 20, 12, 6, 3][i], last: Date.now() - i * 1000 }; }); saveArtistPlays(p);"
        "   var sp = {}; libraryTracks.filter(function(t){ return /^Madonna 0[1-6]$/.test(t.name); }).forEach(function(t){ sp[favKey(t)] = [5, Date.now()]; });"
        "   localStorage.setItem('radioPlayerSongPlays', JSON.stringify(sp)); },"
        " vid: function(){ var k = artistMatchKey('Kay'); var fe = findArtistEntry(k); if(fe && !isFavorite(artistFavRecord(fe))) toggleFavorite(artistFavRecord(fe)); /* build 289: Artist Videos only from favourite artists */ ytStore[k] = { channels: ['UC' + 'k'.repeat(22)], chTs: Date.now(), ts: Date.now(), fv: YT_FV, mv: true,"
        "   videos: [{ id: 'kayVid00001', title: 'Kay - One (Official Video)', published: '2024-01-01' }, { id: 'kayVid00002', title: 'Kay - Two (Official Video)', published: '2023-01-01' }, { id: 'kayVid00003', title: 'Kay - Three (Official Video)', published: '2022-01-01' }] }; ytSave(); },"
        " yesterday: function(){ var s = JSON.parse(localStorage.getItem('radioPlayerDailyMixes')); s.day = '2000-1-1'; localStorage.setItem('radioPlayerDailyMixes', JSON.stringify(s)); dailyState = null; },"
        " closeNp: function(){ try{ closeNowPlaying(); }catch(e){} },"
        " mixOf: function(name){ var e = findArtistEntry(artistMatchKey(name)); return fetchSimilarArtists(e).then(function(names){ var m = buildOneDailyMix(e, 1, mfyDay(), names); return { rel: m.rel, songs: m.songs.map(function(id){ var t = libraryById[id]; return t.artist + '|' + t.name; }) }; }); },"
        " reset: function(){ localStorage.removeItem('radioPlayerDailyMixes'); dailyState = null; },"
        " q: function(){ return { label: queueLabel, n: playQueue.length, cur: currentStation && currentStation.name }; },"
        " note: function(name){ var t = libraryTracks.filter(function(x){ return x.name === name; })[0]; recordArtistPlay(t); return loadSongPlays()[favKey(t)]; },"
        " stopPlay: function(){ audio.play = function(){ return Promise.resolve(); }; } };\n")
_src = open(os.path.join(os.path.dirname(__file__), '..', 'www', 'index.html')).read()
_mark = '  var coverFlow = null;\n'
assert _src.count(_mark) == 1
open(root + '/index.html', 'w').write(_src.replace(_mark, _mark + HOOK))

M = root + '/Music'
os.makedirs(M, exist_ok=True)
LIB = [('Prince', 'Funk', 20), ('Rick James', 'Funk', 10), ('Morris Day', 'Funk/R&B', 8), ('Madonna', 'Pop', 10),
       ('Kay', 'Rock', 6), ('Lee', 'Pop', 6), ('Earth, Wind & Fire', 'Funk', 5)]
SONGS = []
for a, g, n in LIB:
    for i in range(n):
        SONGS.append((f'{a} {i + 1:02d}', a, f'{a} Album', i + 1, g))
for i, (t, a, al, n, g) in enumerate(SONGS):
    subprocess.run(['ffmpeg', '-loglevel', 'error', '-y', '-f', 'lavfi', '-i', f'sine=frequency={200 + i * 7}:duration=1',
                    '-c:a', 'libmp3lame', '-b:a', '32k', '-metadata', f'title={t}', '-metadata', f'artist={a}',
                    '-metadata', f'album={al}', '-metadata', f'track={n}', '-metadata', f'genre={g}', f'{M}/{i + 1:03d}.mp3'], check=True)


class Q(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a): pass
H = functools.partial(Q, directory=root)
srv = http.server.ThreadingHTTPServer(('127.0.0.1', PORT), H)
threading.Thread(target=srv.serve_forever, daemon=True).start()
files = [{'uri': f'http://127.0.0.1:{PORT}/Music/{f}', 'name': f, 'relPath': f'Music/{f}', 'type': 'audio/mpeg',
          'size': os.path.getsize(f'{M}/{f}'), 'lastModified': 1700000000000} for f in sorted(os.listdir(M))]
# Deezer: Prince's related artists are Rick James (Funk, in), Madonna (Pop: different genre, out)
# and someone not in the library. Every other artist is unknown to Deezer.
MOCK = """
(function(){
 var picked = %s, listeners = {};
 window.__dz = [];
 function dz(u){
   window.__dz.push(u);
   if(/search\\/artist/.test(u)){ return /q=Prince$/.test(u) ? { data: [{ id: 77, name: 'Prince' }] } : { data: [] }; }
   if(/artist\\/77\\/related/.test(u)) return { data: [{ name: 'Rick James' }, { name: 'Madonna' }, { name: 'Nobody Here' }] };
   return { data: [] };
 }
 var impl = {
   pickMusicFolder: function(){ return Promise.resolve({folder:'Music', files:picked, truncated:false}); },
   fetchText: function(o){ if(/api\\.deezer\\.com/.test(o.url)) return Promise.resolve({ text: JSON.stringify(dz(o.url)) }); return Promise.reject(new Error('offline')); },
   setCarCatalog: function(o){ window.__cat = JSON.parse(o.json); window.__catN = (window.__catN || 0) + 1; return Promise.resolve({}); },
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

fails = []
def check(cond, msg):
    print(('PASS ' if cond else 'FAIL ') + msg)
    if not cond: fails.append(msg)
ROWS = """(()=>{ var c = document.getElementById('dailyHomeSections');
  var secs = Array.from(c.querySelectorAll('.daily-home-section')).filter(function(s){ return s.style.display !== 'none'; });
  return { shown: getComputedStyle(c).display !== 'none', after: c.previousElementSibling && c.previousElementSibling.id,
    rows: secs.map(function(s){ var g = s.querySelector('.tile-grid'); var r = g.getBoundingClientRect();
      var kids = Array.from(g.children);
      return { full: s.dataset.daily === 'videos' ? 0 : (__d.names(s.dataset.daily) || []).length, id: s.dataset.daily, title: s.querySelector('h2').textContent.trim(), n: kids.length,
        tops: Array.from(new Set(kids.map(function(k){ return Math.round(k.getBoundingClientRect().top); }))).length,
        inRow: g.parentElement.classList.contains('home-row'), scrolls: g.scrollWidth > g.clientWidth + 4,
        left: Math.round(r.left), right: Math.round(r.right), vw: innerWidth,
        kinds: kids.map(function(k){ return k.classList.contains('yt-tile') ? 'yt' : (k.dataset.entity || '?'); }),
        w0: kids[0] ? Math.round(kids[0].getBoundingClientRect().width) : 0,
        th: kids[0] && kids[0].querySelector('.yt-thumb') ? Math.round(kids[0].querySelector('.yt-thumb').getBoundingClientRect().height) : 0,
        subs: kids.map(function(k){ var x = k.querySelector('.tile-sub'); return x ? x.textContent : ''; }) }; }) }; })()"""


async def run(theme):
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
        ctx = await b.new_context(viewport={'width': 412, 'height': 900}, device_scale_factor=2, is_mobile=True, has_touch=True, color_scheme=theme)
        await ctx.add_init_script(MOCK); await ctx.add_init_script(AUTO_NOTICE)
        await ctx.add_init_script("try{ localStorage.setItem('radioPlayerTheme', %s); }catch(e){}" % json.dumps(theme))
        pg = await ctx.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.route('**/*', lambda route: route.continue_() if '127.0.0.1' in route.request.url else route.abort())
        await pg.goto(f'http://127.0.0.1:{PORT}/index.html'); await pg.wait_for_timeout(2500)
        await pg.evaluate("""(function(){ var ov=document.getElementById('addMusicOverlay'); if(ov) ov.classList.add('open');
          var btn=document.getElementById('addMusicFolderBtn'); btn.disabled=false; btn.click(); })()""")
        n = 0
        for _ in range(90):
            await pg.wait_for_timeout(500)
            n = await pg.evaluate("__d.n()")
            if n >= len(SONGS): break
        await pg.evaluate("document.getElementById('addMusicOverlay').classList.remove('open')")
        check(n == len(SONGS), f'[{theme}] library imported ({n})')
        await pg.evaluate('__d.plays(); __d.vid(); __d.reset();')
        await pg.evaluate("try{ hideImportPanel(); setStatus('', false); }catch(e){}")
        await pg.evaluate('__d.home()'); await pg.wait_for_timeout(1500)
        r = await pg.evaluate(ROWS)
        ids = [x['id'] for x in r['rows']]
        titles = [x['title'] for x in r['rows']]
        print(titles)
        check(r['shown'] and r['after'] == 'top100Section', f'[{theme}] the rows sit right under Top 100 (after {r["after"]})')
        check(len([t for t in titles[:5] if t.startswith('Daily Mix: ')]) == 5,
              f'[{theme}] five Daily Mixes, one per top artist {titles[:5]}')
        check(len(set(titles)) == len(titles), f'[{theme}] no artist gets two mixes {titles}')
        check(titles[5:7] == ['Discover', 'Hear It Again'], f'[{theme}] then Discover and Hear It Again {titles[5:7]}')
        check(titles[-1] == 'Kay' and ids[-1] == 'videos', f'[{theme}] then Artist Videos, headed by the artist ({titles[-1]})')
        for x in [y for y in r['rows'] if y['id'] != 'videos']:
            check(x['n'] == min(20, x['full']) and x['tops'] == 1 and x['inRow'] and x['scrolls'] and set(x['kinds']) == {'song'},
                  f'[{theme}] {x["title"]}: one sideways row of 20 songs ({x["n"]}, {x["tops"]} lines)')
        vrow = r['rows'][-1]
        check(vrow['n'] == 3 and vrow['kinds'] == ['yt'] * 3 and abs(vrow['th'] * 16 / 9 - vrow['w0']) < 3, f'[{theme}] videos row: 3 16:9 video tiles ({vrow["w0"]}x{vrow["th"]})')
        check(all(x['left'] == 0 and x['right'] == x['vw'] for x in r['rows']), f'[{theme}] every row runs to both screen edges {[(x["left"], x["right"]) for x in r["rows"]]}')
        # Prince's mix: mostly Prince, the rest Rick James (Deezer, Funk) and Morris Day / EWF (same genre), never Pop/Rock
        await pg.wait_for_timeout(1500)
        pm = await pg.evaluate("__d.mixOf('Prince')")
        prince = pm['songs']
        arts = [x.split('|')[0] for x in prince]
        print({a: arts.count(a) for a in set(arts)})
        check(arts.count('Prince') == 20 and arts.count('Prince') > len(arts) / 2, f'[{theme}] Daily Mix: Prince is mostly Prince ({arts.count("Prince")} of {len(arts)})')
        check('Rick James' in arts and len(set(arts) & {'Morris Day', 'Earth, Wind & Fire'}) >= 1, f'[{theme}] with similar artists from the library (Deezer related + same genre)')
        check('Madonna' not in arts and 'Kay' not in arts and 'Lee' not in arts, f'[{theme}] and none from other genres (Madonna is related on Deezer but Pop)')
        check(len(set(prince)) == len(prince) and len(prince) <= 100, f'[{theme}] no repeats, at most 100 ({len(prince)})')
        same = sum(1 for i in range(1, len(arts)) if arts[i] == arts[i - 1])
        check(same < arts.count('Prince'), f'[{theme}] the artists are spread through it ({same} neighbours)')
        dz = await pg.evaluate('window.__dz')
        check(any('related' in u for u in dz), f'[{theme}] Deezer asked for related artists')
        check(pm['rel'] is True, f'[{theme}] the mix was made with Deezer\'s related artists')
        st = await pg.evaluate('__d.st()')
        dm = [m for m in st['mixes'] if m['id'].startswith('mix:dm')]
        check(len(dm) == 5 and all(len(m['songs']) >= 10 for m in dm), f'[{theme}] five mixes long enough to show (a Rock artist with no Rock company is passed over) {[m["title"] for m in dm]}')
        mad = [x.split('|')[0] for x in (await pg.evaluate("__d.mixOf('Madonna')"))['songs']]
        mad = [x.split('|')[0] for x in await pg.evaluate("__d.names('mix:dm2')")]
        check(set(mad) <= {'Madonna', 'Lee'} and 'Lee' in mad, f'[{theme}] Madonna\'s mix adds Pop artists from the library {sorted(set(mad))}')
        disc = await pg.evaluate("__d.names('mix:discover')")
        again = await pg.evaluate("__d.names('mix:again')")
        played = {f'Madonna|Madonna {i:02d}' for i in range(1, 7)}
        check(not (played & set(disc)), f'[{theme}] Discover leaves out the most played songs')
        check(played <= set(again), f'[{theme}] Hear It Again has every song played 5 times')
        check(len(again) >= 20 and all(a.split('|')[0] in ('Madonna', 'Prince', 'Kay', 'Earth, Wind & Fire', 'Rick James', 'Lee') for a in again),
              f'[{theme}] and is filled from the most played artists ({len(again)})')
        # Build 231: the same lists in Android Auto (Home > Daily Mixes), each a folder of songs
        await pg.wait_for_timeout(1500)
        cat = await pg.evaluate('window.__cat || null')
        shown = [m for m in (await pg.evaluate('__d.st()'))['mixes'] if len(m['songs']) >= 10]
        check(cat and [m['id'] for m in cat.get('mixes', [])] == [m['id'] for m in shown]
              and [m['title'] for m in cat['mixes']] == [m['title'] for m in shown],
              f'[{theme}] the car gets every list shown on Home, in order {[m["title"] for m in shown]} {[m["title"] for m in (cat or {}).get("mixes", [])]}')
        if cat:
            ok = all(len(cat['lists'].get(m['id'], [])) == len(m['songs']) and all(e.get('t') == 'song' for e in cat['lists'][m['id']]) for m in shown)
            check(ok, f'[{theme}] each car list holds the whole mix as songs')
            subs = {m['id']: m.get('sub') for m in cat['mixes']}
            check(subs.get('mix:discover') == 'Songs you rarely play' and subs.get('mix:again') == 'Your most played songs'
                  and subs.get('mix:dm1', '').endswith(' and similar artists'), f'[{theme}] each car list says what it is {subs}')
        java = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'android/app/src/main/java/com/markcoleman/amplify/CarLibrary.java')).read()
        home = java[java.index('"tab:home",\n'):java.index('"tab:library",\n')]
        check('"home:mixes"' in home and home.index('"home:mixes"') < home.index('"home:madeforyou"') and 'put("home:mixes", "Daily Mixes")' in java,
              f'[{theme}] CarLibrary: Daily Mixes under Home, before Made for You')
        check('str.startsWith(MIX_PREFIX)\n                  || "lib:songs"' in java.replace('\r', '') or 'str.startsWith(MIX_PREFIX)' in java[java.index('arrayList.add(0, shuffleItem(str))') - 400:java.index('arrayList.add(0, shuffleItem(str))')],
              f'[{theme}] CarLibrary: a mix opens with a Shuffle row')
        # tap a tile: plays through that mix
        await pg.evaluate('__d.stopPlay()')
        dm1 = await pg.evaluate("__d.names('mix:dm1')"); t1 = st['mixes'][0]['title']
        await pg.evaluate("document.querySelector('[data-daily=\"mix:dm1\"] .tile-grid .tile').click()"); await pg.wait_for_timeout(500)
        q = await pg.evaluate('__d.q()')
        check(q['label'] == t1 and q['n'] == len(dm1), f'[{theme}] a tile plays through the whole mix {q}')
        await pg.evaluate("__d.closeNp()"); await pg.wait_for_timeout(400)
        await pg.evaluate("document.querySelector('[data-daily=\"mix:dm1\"]').scrollIntoView({block:'start'}); window.scrollBy(0, -70)"); await pg.wait_for_timeout(400)
        await pg.screenshot(path=f'{shots}/daily-home-{theme}.png')
        await pg.evaluate("document.querySelector('[data-daily=\"mix:again\"]').scrollIntoView({block:'start'}); window.scrollBy(0, -70)"); await pg.wait_for_timeout(400)
        await pg.screenshot(path=f'{shots}/daily-home2-{theme}.png')
        # heading opens the page with the whole mix
        await pg.evaluate("document.querySelector('[data-daily=\"mix:dm1\"] h2').click()"); await pg.wait_for_timeout(700)
        pgr = await pg.evaluate("""(()=>({ h: document.getElementById('stationsHeading').textContent,
          rows: document.querySelectorAll('#stationsGrid .song-row').length, back: document.getElementById('detailBackLabel').textContent,
          shuffle: getComputedStyle(document.getElementById('libraryShuffleBtn')).display !== 'none',
          count: (document.getElementById('resultCount').style.display !== 'none') && document.getElementById('resultCount').textContent }))()""")
        check(pgr['h'] == t1 and pgr['rows'] == len(dm1) and pgr['back'] == 'Home', f'[{theme}] the heading opens a page with the whole mix {pgr}')
        check(pgr['shuffle'] and not pgr['count'], f'[{theme}] with Shuffle and no count')
        await pg.screenshot(path=f'{shots}/daily-page-{theme}.png')
        await pg.evaluate("document.getElementById('libraryShuffleBtn').click()"); await pg.wait_for_timeout(500)
        q = await pg.evaluate('__d.q()')
        check(q['label'] == t1 and q['n'] == len(dm1), f'[{theme}] Shuffle plays the mix shuffled {q}')
        await pg.evaluate("__d.closeNp()"); await pg.wait_for_timeout(300)
        await pg.evaluate("document.querySelector('#stationsGrid .song-row').click()"); await pg.wait_for_timeout(500)
        q = await pg.evaluate('__d.q()')
        check(q['label'] == t1, f'[{theme}] a row on the page plays in the mix {q}')
        await pg.evaluate("__d.closeNp()"); await pg.wait_for_timeout(300)
        await pg.evaluate("document.getElementById('detailBackBtn').click()"); await pg.wait_for_timeout(700)
        check((await pg.evaluate(ROWS))['shown'], f'[{theme}] Back returns Home')
        # Discover page
        await pg.evaluate("document.querySelector('[data-daily=\"mix:discover\"] h2').click()"); await pg.wait_for_timeout(700)
        check(await pg.evaluate("document.getElementById('stationsHeading').textContent") == 'Discover'
              and await pg.evaluate("document.querySelectorAll('#stationsGrid .song-row').length") == len(disc), f'[{theme}] Discover opens its page')
        await pg.evaluate("document.getElementById('detailBackBtn').click()"); await pg.wait_for_timeout(700)
        # the video artist heading opens the artist
        await pg.evaluate("document.querySelector('[data-daily=\"videos\"] h2').click()"); await pg.wait_for_timeout(900)
        check(await pg.evaluate("document.body.classList.contains('artist-open') && document.getElementById('artistHeroName').textContent") == 'Kay', f'[{theme}] the Artist Videos heading opens the artist page')
        await pg.evaluate("document.getElementById('detailBackBtn').click()"); await pg.wait_for_timeout(700)
        # the same all day: a reload keeps every list
        before = await pg.evaluate("JSON.stringify(__d.st().mixes)")
        await pg.reload(); await pg.wait_for_timeout(3000)
        await pg.evaluate('__d.home()'); await pg.wait_for_timeout(800)
        after = await pg.evaluate("JSON.stringify(__d.st().mixes)")
        check(before == after, f'[{theme}] the lists stay the same through the day (reload)')
        # a new day remakes them
        await pg.evaluate("__d.yesterday()")
        await pg.evaluate('__d.home()'); await pg.wait_for_timeout(800)
        st2 = await pg.evaluate('__d.st()')
        check(st2['day'] != '2000-1-1' and json.dumps(st2['mixes']) != after, f'[{theme}] a new day makes new lists')
        await pg.wait_for_timeout(1500)
        cat2 = await pg.evaluate('window.__cat || null')
        want = [m['id'] for m in st2['mixes'] if len(m['songs']) >= 10]
        check(cat2 and [m['id'] for m in cat2['mixes']] == want
              and all(len(cat2['lists'][m['id']]) == len(m['songs']) for m in st2['mixes'] if m['id'] in want)
              and json.dumps([cat2['lists'][i] for i in want]) != json.dumps([(cat or {}).get('lists', {}).get(i) for i in want]),
              f'[{theme}] and the car gets the new day\'s lists')
        # song plays are counted
        c1 = await pg.evaluate("__d.note('Lee 01')")
        c2 = await pg.evaluate("__d.note('Lee 01')")
        check(c1[0] == 1 and c2[0] == 2, f'[{theme}] each counted play of a song is recorded ({c1}, {c2})')
        check(not errs, f'[{theme}] no page errors {errs[:3]}')
        await b.close()


async def main():
    for theme in ('dark', 'light'):
        await run(theme)
    print('ALL PASSED' if not fails else f'FAILED {fails}')
    sys.exit(1 if fails else 0)

asyncio.run(main())
