"""Build 178: a genre's page is titled with the genre alone ("Rock", not "Rock Stations"); its
songs and stations are on tabs of their own, Songs first, each naming its own count; no tabs when
the genre has only one kind; the Songs tab starts with Shuffle All, which plays every song in it.
Run: python3 tests/test_genre_tabs.py (screenshots in /tmp/claude-0/t/shots)"""
import asyncio, os, json, threading, http.server, functools, shutil, subprocess
from urllib.parse import urlparse, parse_qs
from playwright.async_api import async_playwright

PORT = 8820
root = '/tmp/claude-0/t/srv_genre'
shots = '/tmp/claude-0/t/shots'
os.makedirs(shots, exist_ok=True)
shutil.rmtree(root, ignore_errors=True); os.makedirs(root)
HOOK = ("window.__t = { tracks: function(){ return libraryTracks.map(function(t){ return t.name; }); },"
        " genre: function(g){ searchByTag(g); },"
        " q: function(){ return { list: playQueue.map(function(s){ return s.name; }), label: queueLabel, cur: currentStation && currentStation.name }; } };\n")
_src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'www', 'index.html')).read()
_mark = '  var coverFlow = null;\n'
assert _src.count(_mark) == 1
open(root + '/index.html', 'w').write(_src.replace(_mark, _mark + HOOK))
M = root + '/Music'; os.makedirs(M)
SONGS = [('Rock One', 'Ann', 'Rock'), ('Rock Two', 'Ann', 'Rock'), ('Rock Three', 'Bob', 'Rock'), ('Jazz Tune', 'Cal', 'Jazz')]
for i, (t, a, g) in enumerate(SONGS):
    subprocess.run(['ffmpeg', '-loglevel', 'error', '-y', '-f', 'lavfi', '-i', f'sine=frequency={300 + i * 50}:duration=3', '-c:a', 'libmp3lame', '-b:a', '32k',
                    '-metadata', f'title={t}', '-metadata', f'artist={a}', '-metadata', f'album={a} LP', '-metadata', f'genre={g}', f'{M}/{i:02d}.mp3'], check=True)
class Q(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a): pass
srv = http.server.ThreadingHTTPServer(('127.0.0.1', PORT), functools.partial(Q, directory=root))
threading.Thread(target=srv.serve_forever, daemon=True).start()
files = [{'uri': f'http://127.0.0.1:{PORT}/Music/{f}', 'name': f, 'relPath': f'Music/{f}', 'type': 'audio/mpeg',
          'size': os.path.getsize(f'{M}/{f}'), 'lastModified': 1700000000000} for f in sorted(os.listdir(M))]
MOCK = """(function(){ var picked = %s, listeners = {}, cur = null;
 function emit(n, ev){ (listeners[n] || []).forEach(function(f){ try{ f(ev); }catch(e){} }); }
 var impl = { pickMusicFolder: function(){ return Promise.resolve({folder:'Music', files:picked, truncated:false}); },
   cacheCheck: function(){ return Promise.resolve({ url: 'file:///cache/x.mp3' }); },
   load: function(o){ cur = o.id; setTimeout(function(){ emit('state', { id: cur, state: 'ready', isPlaying: true, playWhenReady: true, position: 0, duration: 3 }); }, 20); return Promise.resolve({}); },
   addListener: function(n, f){ (listeners[n] = listeners[n] || []).push(f); return Promise.resolve({remove:function(){}}); } };
 var P = new Proxy({}, {get:function(t,k){ if(k==='then') return undefined; if(k==='setCarLibraryPart') return undefined; if(impl[k]) return impl[k]; return function(){ return Promise.resolve({}); }; }});
 window.Capacitor = { isNativePlatform:function(){return true;}, getPlatform:function(){return 'android';}, registerPlugin:function(){ return P; }, Plugins:{AmplifyPlayer:P}, convertFileSrc:function(u){return u;} };
})();""" % json.dumps(files)
fails = []
def check(cond, msg):
    print(('PASS ' if cond else 'FAIL ') + msg)
    if not cond: fails.append(msg)
STATIONS = {'rock': 5, 'jazz': 0, 'blues': 3, 'polka': 0}
delay = {'ms': 0}
async def route(r):
    u = r.request.url
    if '127.0.0.1' in u: return await r.continue_()
    q = parse_qs(urlparse(u).query)
    if '/json/stations/search' in u and 'tag' in q:
        tag = q['tag'][0]
        if delay['ms']: await asyncio.sleep(delay['ms'] / 1000)
        return await r.fulfill(status=200, content_type='application/json', body=json.dumps(
            [{'name': '%s Station %d' % (tag.title(), i), 'url_resolved': 'http://s/%s%d' % (tag, i), 'stationuuid': '%s-%d' % (tag, i), 'favicon': '', 'tags': tag, 'codec': 'MP3'} for i in range(STATIONS.get(tag, 0))]))
    if '/json/' in u: return await r.fulfill(status=200, content_type='application/json', body='[]')
    return await r.abort()
PAGE = """(()=>{ var g = document.getElementById('stationsGrid');
  return { title: document.getElementById('stationsHeading').textContent,
    tabs: Array.from(g.querySelectorAll('.genre-tab')).map(function(b){ return { tab: b.dataset.gtab, name: b.textContent, active: b.classList.contains('active') }; }),
    shuffle: !!g.querySelector('.shuffle-all-row'), shuffleSub: (g.querySelector('.shuffle-all-row .song-row-sub') || {}).textContent || '',
    songs: Array.from(g.querySelectorAll('.song-row:not(.shuffle-all-row) .song-row-title')).map(function(e){ return e.textContent; }),
    stations: Array.from(g.querySelectorAll('.tile:not(.song-row) .tile-name')).map(function(e){ return e.textContent; }),
    count: (document.getElementById('resultCount') || {}).textContent || '', spinner: !!g.querySelector('.loading-state') }; })()"""

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
        ctx = await b.new_context(viewport={'width': 412, 'height': 900}, device_scale_factor=2, is_mobile=True, has_touch=True, color_scheme='dark')
        await ctx.add_init_script(MOCK)
        pg = await ctx.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.route('**/*', route)
        await pg.goto(f'http://127.0.0.1:{PORT}/index.html'); await pg.wait_for_timeout(2500)
        await pg.evaluate("""(function(){ var ov=document.getElementById('addMusicOverlay'); if(ov) ov.classList.add('open');
          var btn=document.getElementById('addMusicFolderBtn'); btn.disabled=false; btn.click(); })()""")
        for _ in range(60):
            await pg.wait_for_timeout(500)
            if len(await pg.evaluate('__t.tracks()')) >= 4: break
        await pg.wait_for_timeout(1200)
        # Rock: both kinds
        await pg.evaluate("__t.genre('Rock')"); await pg.wait_for_timeout(1500)
        r = await pg.evaluate(PAGE); print(r)
        check(r['title'] == 'Rock', f'titled with the genre alone {r["title"]!r}')
        check([t['tab'] for t in r['tabs']] == ['songs', 'stations'] and r['tabs'][0]['active'], f'Songs and Stations tabs, Songs first and open {r["tabs"]}')
        check([t['name'] for t in r['tabs']] == ['Songs', 'Stations'], f'the tabs carry their names only, no counts (build 179) {r["tabs"]}')
        check(r['count'] == '3 songs', f'the count is shown once, at the top {r["count"]!r}')
        check(r['songs'] == ['Rock One', 'Rock Three', 'Rock Two'] and not r['stations'], f'the Songs tab lists the songs, A to Z, and no stations {r["songs"]} {r["stations"]}')
        check(r['shuffle'] and r['shuffleSub'] == '', f'Shuffle All heads the songs, with no count under it {r["shuffleSub"]!r}')
        page_text = await pg.evaluate("document.getElementById('browseView').innerText")
        check(page_text.count('3 songs') == 1, f'"3 songs" appears once on the page ({page_text.count("3 songs")})')
        await pg.screenshot(path=f'{shots}/genre-songs.png')
        await pg.evaluate("document.querySelector('.genre-tab[data-gtab=stations]').click()"); await pg.wait_for_timeout(500)
        r2 = await pg.evaluate(PAGE)
        check(len(r2['stations']) == 5 and not r2['songs'] and not r2['shuffle'] and r2['tabs'][1]['active'], f'the Stations tab lists the stations {r2["stations"]}')
        check('5 stations' in r2['count'], f'the count follows the tab {r2["count"]}')
        await pg.screenshot(path=f'{shots}/genre-stations.png')
        await pg.evaluate("document.querySelector('.genre-tab[data-gtab=songs]').click()"); await pg.wait_for_timeout(500)
        check('3 songs' in (await pg.evaluate(PAGE))['count'], 'and back on Songs')
        # Shuffle All plays every song of the genre
        await pg.evaluate("document.querySelector('.shuffle-all-row').click()"); await pg.wait_for_timeout(1200)
        s = await pg.evaluate('__t.q()'); print(s)
        check(sorted(s['list']) == ['Rock One', 'Rock Three', 'Rock Two'] and s['label'] == 'Rock' and s['cur'] in s['list'], f'Shuffle All plays every Rock song {s}')
        # Jazz: songs only, no tabs
        await pg.evaluate("document.getElementById('npBackBtn') && document.getElementById('npBackBtn').click()"); await pg.wait_for_timeout(500)
        await pg.evaluate("__t.genre('Jazz')"); await pg.wait_for_timeout(1500)
        j = await pg.evaluate(PAGE); print(j)
        check(j['title'] == 'Jazz' and not j['tabs'] and j['songs'] == ['Jazz Tune'] and not j['spinner'], f'songs only: just the songs, no tabs {j}')
        # Blues: stations only, no tabs
        await pg.evaluate("__t.genre('Blues')"); await pg.wait_for_timeout(1500)
        bl = await pg.evaluate(PAGE); print(bl)
        check(bl['title'] == 'Blues' and not bl['tabs'] and len(bl['stations']) == 3 and '3 stations' in bl['count'], f'stations only: just the stations, no tabs {bl}')
        await pg.screenshot(path=f'{shots}/genre-stations-only.png')
        # Polka: nothing
        await pg.evaluate("__t.genre('Polka')"); await pg.wait_for_timeout(1500)
        po = await pg.evaluate("document.getElementById('stationsGrid').textContent")
        check('No songs or stations' in po, f'nothing at all says so {po}')
        # stations slow to arrive: the songs show at once, the tabs appear when the stations do
        delay['ms'] = 1500
        await pg.evaluate("__t.genre('Rock')"); await pg.wait_for_timeout(400)
        e = await pg.evaluate(PAGE)
        check(not e['tabs'] and len(e['songs']) == 3 and e['spinner'], f'songs at once while the stations load {e}')
        await pg.wait_for_timeout(2000)
        e2 = await pg.evaluate(PAGE)
        check(len(e2['tabs']) == 2 and e2['tabs'][0]['active'] and not e2['spinner'], f'then the tabs, still on Songs {e2["tabs"]}')
        delay['ms'] = 0
        check(not errs, f'no page errors {errs[:3]}')
        await b.close()
    print('ALL PASSED' if not fails else f'FAILED {fails}')
asyncio.run(main())
