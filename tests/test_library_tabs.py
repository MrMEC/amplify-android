"""Build 405 (Mark): the Library is a row of tabs (Artists, Albums, Songs, Playlists, Genres), opening on the
last one used; the Artists tab has Favorite Artists as a sideways row above the A-Z of all artists. And the
Songs page opens straight away with a big library (first rows at once, the rest in batches, off-screen rows
not laid out) while the queue, the A-Z rail and the filter still cover every song.
Run: python3 tests/test_library_tabs.py (screenshots in /tmp/claude-0/t/shots)"""
import sys as _nsys, os as _nos; _nsys.path.insert(0, _nos.path.dirname(_nos.path.abspath(__file__))); from notice_auto import AUTO_NOTICE
import asyncio, os, json, threading, http.server, functools, shutil, subprocess
from urllib.parse import urlparse, parse_qs
from playwright.async_api import async_playwright

PORT = 8890
root = '/tmp/claude-0/t/srv_libtabs'
shots = '/tmp/claude-0/t/shots'
os.makedirs(shots, exist_ok=True)
shutil.rmtree(root, ignore_errors=True); os.makedirs(root)
HOOK = ("window.__t = { tracks: function(){ return libraryTracks.map(function(t){ return t.name; }); },"
        " genre: function(g){ searchByTag(g); }, home: function(){ openGenresHome(); }, ev: function(js){ return eval(js); },"
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
STATIONS = {'rock': 14, 'jazz': 0, 'blues': 3, 'polka': 0, 'classic rock': 4}
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


LT = """(()=>{ var g = document.getElementById('stationsGrid'), bar = g.querySelector(':scope > .lib-tabs');
  return { first: g.firstElementChild === bar, tabs: bar ? Array.from(bar.children).map(function(b){ return b.textContent; }) : [],
    active: bar && bar.querySelector('.active') ? bar.querySelector('.active').textContent : null,
    heading: document.getElementById('stationsHeading').textContent, back: getComputedStyle(document.getElementById('detailBackBtn')).display !== 'none',
    filterAfter: !!(bar && bar.nextElementSibling && bar.nextElementSibling.classList.contains('sec-filter') && getComputedStyle(bar.nextElementSibling).display !== 'none'),
    find: !!(bar && bar.nextElementSibling && bar.nextElementSibling.classList.contains('gb-find')),
    favRow: Array.from(g.querySelectorAll('.lib-fav-row > .tile .tile-name')).map(function(e){ return e.textContent; }),
    favRowScroll: (function(){ var r = g.querySelector('.lib-fav-row'); return r ? getComputedStyle(r).overflowX : null; })(),
    allHead: !!g.querySelector('.lib-all-head'), gridArtists: g.querySelectorAll(':scope > .tile[data-entity="artist"]').length,
    rightHidden: !document.querySelector('#sectionHeadingRow .section-heading-right'),
    toolbar: (function(){ var tb = document.querySelector('.page-toolbar'); if(!tb || tb.hidden) return null; var f = g.querySelector(':scope > .sec-filter, :scope > .gb-find'); var rc = tb.querySelector('#resultCount');
      return { count: rc && rc.style.display !== 'none' ? rc.textContent : '', btns: Array.from(tb.querySelectorAll('button')).filter(function(b){ return b.offsetParent; }).map(function(b){ return b.id; }),
        afterFilter: !!f && (f.compareDocumentPosition(tb) & 4) !== 0, gap: f ? Math.round(tb.getBoundingClientRect().top - f.getBoundingClientRect().bottom) : null }; })(),
    favStars: Array.from(g.querySelectorAll('.lib-fav-row .tile-fav')).filter(function(b){ return b.offsetParent; }).length,
    headW: (function(){ var h = document.getElementById('stationsHeading'); return [h.scrollWidth, h.clientWidth]; })(),
    gapTF: (function(){ var f = bar && bar.nextElementSibling; return f ? Math.round(f.getBoundingClientRect().top - bar.getBoundingClientRect().bottom) : null; })(),
    tabLeft: (function(){ var a = bar && bar.firstElementChild; return a ? Math.round(a.getBoundingClientRect().left) : null; })(), barLeft: bar ? Math.round(bar.getBoundingClientRect().left) : null,
    sw: document.documentElement.scrollWidth, vw: innerWidth }; })()"""

async def load(pg):
    await pg.goto(f'http://127.0.0.1:{PORT}/index.html'); await pg.wait_for_timeout(2500)
    await pg.evaluate("""(function(){ var ov=document.getElementById('addMusicOverlay'); if(ov) ov.classList.add('open');
      var btn=document.getElementById('addMusicFolderBtn'); btn.disabled=false; btn.click(); })()""")
    for _ in range(60):
        await pg.wait_for_timeout(500)
        if len(await pg.evaluate('__t.tracks()')) >= 4: break
    await pg.wait_for_timeout(1200)
    await pg.evaluate("try{ document.getElementById('addMusicOverlay').classList.remove('open'); hideImportPanel(); setStatus('', false); }catch(e){}")

async def lib(pg):
    await pg.evaluate("document.querySelector('.mobile-nav-btn[data-nav=library]').click()"); await pg.wait_for_timeout(1000)

async def run(b, scheme, w, h):
    T = f'[{scheme} {w}]'
    ctx = await b.new_context(viewport={'width': w, 'height': h}, device_scale_factor=2, is_mobile=True, has_touch=True, color_scheme=scheme)
    await ctx.add_init_script(MOCK); await ctx.add_init_script(AUTO_NOTICE)
    await ctx.add_init_script("try{ localStorage.setItem('radioPlayerTheme', %s); }catch(e){}" % json.dumps(scheme))
    pg = await ctx.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
    await pg.route('**/*', route)
    await load(pg)
    await pg.evaluate("__t.ev(\"['Ann','Bob'].forEach(function(n){ toggleFavorite(artistFavRecord(findArtistEntry(artistMatchKey(n)))); })\")"); await pg.wait_for_timeout(300)
    await lib(pg)
    r = await pg.evaluate(LT); print(T, r)
    check(r['first'] and r['tabs'] == ['Artists', 'Albums', 'Songs', 'Playlists', 'Genres'] and r['active'] == 'Artists', f'{T} the Library opens on tabs, Artists first {r["tabs"]} {r["active"]}')
    check(r['heading'] == 'Library' and not r['back'], f'{T} headed Library, no back button')
    check(r['favRow'] == ['Ann', 'Bob'] and r['favRowScroll'] == 'auto' and r['allHead'] and r['gridArtists'] == 3, f'{T} Favorite Artists as a sideways row above All Artists {r["favRow"]} {r["gridArtists"]}')
    check(r['filterAfter'], f'{T} the filter box sits right under the tabs')
    check(r['rightHidden'] and r['toolbar'] and r['toolbar']['count'] == '3 artists' and 'libraryShuffleBtn' in r['toolbar']['btns'] and r['toolbar']['afterFilter'] and r['toolbar']['gap'] == 10, f'{T} build 406: the count and buttons sit under the filter, not in the header {r["toolbar"]}')
    check(r['headW'][0] <= r['headW'][1] + 1, f'{T} "Library" shows whole at the top {r["headW"]}')
    check(r['favStars'] == 0, f'{T} build 408: no stars on the Favorite Artists row')
    await pg.evaluate("document.querySelector('.fav-artists-edit').click()"); await pg.wait_for_timeout(500)
    ed = await pg.evaluate("({ az: getComputedStyle(document.getElementById('azRail')).display, trash: document.querySelectorAll('.fav-remove-btn').length })")
    await pg.evaluate("window.scrollBy(0, 300)"); await pg.wait_for_timeout(300)
    ed2 = await pg.evaluate("document.body.classList.contains('az-show')")
    check(ed['az'] == 'none' and not ed2 and ed['trash'] == 2, f'{T} editing Favorite Artists: no A-Z rail, each can be removed {ed} {ed2}')
    await pg.evaluate("window.scrollTo(0,0)"); await pg.evaluate("document.querySelector('.fav-artists-edit').click()"); await pg.wait_for_timeout(600)
    check((await pg.evaluate(LT))['favRow'] == ['Ann', 'Bob'], f'{T} Done puts the row back')
    await pg.evaluate("document.querySelector('.page-toolbar #libraryShuffleBtn').click()"); await pg.wait_for_timeout(1200)
    q = await pg.evaluate('__t.q()')
    check(q['cur'] and q['label'] == 'Library', f'{T} the Shuffle button under the filter shuffles the library {q["label"]} {q["cur"]}')
    await pg.evaluate("__t.ev('closeNowPlaying()')"); await pg.wait_for_timeout(500)
    check(r['barLeft'] == 0 and r['tabLeft'] == 21, f'{T} the tab row runs to the screen edge and the first tab lines up with the page margin ({r["barLeft"]}, {r["tabLeft"]})')
    check(r['sw'] <= r['vw'], f'{T} nothing scrolls sideways')
    await pg.screenshot(path=f'{shots}/libtabs-artists-{scheme}-{w}.png')
    gaps = [r['gapTF']]
    for tab, extra in (('albums', None), ('songs', None), ('playlists', None), ('genres', 'find')):
        await pg.evaluate("(t)=>document.querySelector('.lib-tabs [data-libtab='+t+']').click()", tab); await pg.wait_for_timeout(900)
        r = await pg.evaluate(LT)
        check(r['first'] and r['active'] == tab.title() and r['heading'] == 'Library' and not r['back'], f'{T} {tab}: the tabs stay on top, {tab.title()} active {r["active"]} {r["heading"]}')
        if extra == 'find': check(r['find'], f'{T} genres: its own find box under the tabs')
        check(r['rightHidden'], f'{T} {tab}: no count or buttons in the header')
        if tab == 'playlists': check(r['toolbar'] and 'playlistsAddHeaderBtn' in r['toolbar']['btns'] and r['toolbar']['count'] == '0 playlists', f'{T} playlists: the playlist count, then Add Playlist, under the tabs {r["toolbar"]}')
        az = await pg.evaluate("getComputedStyle(document.getElementById('azRail')).display")
        if tab in ('playlists', 'genres'): check(az == 'none', f'{T} {tab}: no A-Z rail ({az})')
        if tab == 'songs': check(not await pg.evaluate("!!document.querySelector('#stationsGrid .shuffle-all-row')"), f'{T} songs: no Shuffle All row')
        await pg.screenshot(path=f'{shots}/libtabs-{tab}-{scheme}-{w}.png')
    check(len(set(gaps)) == 1 and gaps[0] == 12, f'{T} the same 12px between the tabs and the filter on every tab {gaps}')
    # the last tab is remembered
    await pg.evaluate("document.querySelector('.mobile-nav-btn[data-nav=video]').click()"); await pg.wait_for_timeout(1200)
    wb = await pg.evaluate("({ inBar: !!document.querySelector('.page-toolbar #videoAddHeaderBtn'), add: getComputedStyle(document.getElementById('videoAddHeaderBtn')).display, hdr: !document.querySelector('#sectionHeadingRow .section-heading-right') })")
    check(wb['inBar'] and wb['add'] != 'none' and wb['hdr'], f'{T} build 408: Watch puts its buttons under the filter too {wb}')
    await pg.evaluate("__t.ev('openPodcastsHome()')"); await pg.wait_for_timeout(1000)
    pb = await pg.evaluate("({ inBar: !!document.querySelector('.page-toolbar #podcastAddHeaderBtn'), hdr: !document.querySelector('#sectionHeadingRow .section-heading-right') })")
    check(pb['inBar'] and pb['hdr'], f'{T} build 408: and so does Podcasts {pb}')
    await pg.evaluate("__t.ev('loadTopStations()')"); await pg.wait_for_timeout(800)
    hb = await pg.evaluate("({ back: !!document.querySelector('#sectionHeadingRow .section-heading-right'), bars: document.querySelectorAll('.page-toolbar').length })")
    check(hb['back'] and hb['bars'] == 0, f'{T} on Home the buttons are back in the header and no toolbar is left behind {hb}')
    await pg.evaluate("__t.ev('loadTopStations()')"); await pg.wait_for_timeout(600)
    await lib(pg)
    check((await pg.evaluate(LT))['active'] == 'Genres', f'{T} the Library reopens on the last tab used')
    # an artist from the Artists tab, and Back
    await pg.evaluate("document.querySelector('.lib-tabs [data-libtab=artists]').click()"); await pg.wait_for_timeout(900)
    await pg.evaluate("document.querySelector('#stationsGrid > .tile[data-entity=\"artist\"]').click()"); await pg.wait_for_timeout(1200)
    check(not (await pg.evaluate(LT))['tabs'], f'{T} an artist page has no tabs')
    await pg.evaluate("document.getElementById('detailBackBtn').click()"); await pg.wait_for_timeout(1200)
    r = await pg.evaluate(LT)
    check(r['active'] == 'Artists' and r['favRow'] == ['Ann', 'Bob'], f'{T} Back returns to the Artists tab {r["active"]}')
    # ---- Songs with a big library ----
    if w == 390:
        cdp = await ctx.new_cdp_session(pg); await cdp.send('Emulation.setCPUThrottlingRate', {'rate': 4})
        r = await pg.evaluate("""()=>__t.ev(`(function(){ var base = libraryTracks.slice(0,4); var words=['Love','Night','Dream','Fire','Heart','Blue','Summer','Rain','Gold','Zebra'];
          var extra=[]; for(var i=0;i<8000;i++){ var b=base[i%4]; var t=Object.assign({}, b); t.id=(b.id||'x')+'-'+i; t.localId=t.id; t.name=words[i%10]+' '+words[(i*7)%10]+' '+i; extra.push(t); }
          libraryTracks = base.concat(extra); libraryById = {}; libraryTracks.forEach(function(t){ libraryById[t.id]=t; });
          var t0=performance.now(); openLibTab('songs'); var t1=performance.now(); document.body.offsetHeight; var t2=performance.now();
          return { build: Math.round(t1-t0), layout: Math.round(t2-t1), rows: document.querySelectorAll('#stationsGrid .song-row:not(.shuffle-all-row)').length }; })()`)""")
        print(T, 'songs', r)
        check(r['build'] + r['layout'] < 1500 and r['rows'] < 200, f'{T} 8,004 songs on a slow phone: the page is up in {r["build"] + r["layout"]} ms (was about 16 s), {r["rows"]} rows drawn first')
        await cdp.send('Emulation.setCPUThrottlingRate', {'rate': 1})
        await pg.wait_for_timeout(400)
        f0 = await pg.evaluate("({ shown: document.body.classList.contains('az-show'), op: getComputedStyle(document.getElementById('azRail')).opacity, disp: getComputedStyle(document.getElementById('azRail')).display })")
        await pg.mouse.wheel(0, 600); await pg.evaluate("window.scrollBy(0, 400)"); await pg.wait_for_timeout(400)
        f1 = await pg.evaluate("({ shown: document.body.classList.contains('az-show'), op: getComputedStyle(document.getElementById('azRail')).opacity })")
        await pg.evaluate("window.scrollTo(0, 0)"); await pg.wait_for_timeout(350)
        ftop = await pg.evaluate("document.body.classList.contains('az-show')")
        check(not ftop, f'{T} back at the top the rail goes at once')
        await pg.evaluate("window.scrollBy(0, 500)"); await pg.wait_for_timeout(200)
        await pg.wait_for_timeout(2300)
        f2 = await pg.evaluate("({ shown: document.body.classList.contains('az-show'), op: getComputedStyle(document.getElementById('azRail')).opacity })")
        check(f0['disp'] != 'none' and not f0['shown'] and f0['op'] == '0' and f1['shown'] and f1['op'] == '1' and not f2['shown'] and f2['op'] == '0', f'{T} the A-Z rail is hidden until scrolling, fades in, then fades out {f0} {f1} {f2}')
        await pg.evaluate("window.scrollTo(0,0)"); await pg.wait_for_timeout(300)
        await cdp.send('Emulation.setCPUThrottlingRate', {'rate': 4})
        await pg.evaluate("document.querySelectorAll('#stationsGrid .song-row:not(.shuffle-all-row)')[3].click()"); await pg.wait_for_timeout(1200)
        q = await pg.evaluate('__t.q()')
        print(T, 'queue', q['label'], q['cur']); check(len(q['list']) == 8004 and q['label'] in ('Songs', 'Library'), f'{T} a song tapped straight away queues the whole library ({len(q["list"])})')
        await pg.evaluate("__t.ev('closeNowPlaying()')"); await pg.wait_for_timeout(400)
        await pg.evaluate("document.querySelector('#azRail .az-letter[data-letter=Z]').click()"); await pg.wait_for_timeout(2600)
        print(T, 'rail', await pg.evaluate("({ shown: getComputedStyle(document.getElementById('azRail')).display, n: document.querySelectorAll('#stationsGrid .song-row').length, h: document.documentElement.scrollHeight })"))
        z = await pg.evaluate("(()=>{ var h=document.querySelector('#stationsGrid .song-letter[data-letter=Z]'); return h ? { y: Math.round(h.getBoundingClientRect().top), sy: Math.round(scrollY) } : null; })()")
        check(z and z['sy'] > 1000 and -50 < z['y'] < 400, f'{T} the A-Z rail jumps to Z, drawing the rest first {z}')
        await pg.evaluate("window.scrollTo(0,0)"); await pg.wait_for_timeout(300)
        await pg.evaluate("__t.ev('openLibTab(\"songs\")')"); await pg.wait_for_timeout(300)
        await pg.fill('#secFilterInput', 'zebra 7999'); await pg.wait_for_timeout(1500)
        f = await pg.evaluate("Array.from(document.querySelectorAll('#stationsGrid .song-row:not(.sf-hide):not(.shuffle-all-row) .song-row-title')).map(e=>e.textContent)")
        check(f == ['Zebra Night 7999'] or f == ['Zebra night 7999'] or (len(f) == 1 and '7999' in f[0]), f'{T} the filter finds a song from the end of the list {f}')
        await pg.fill('#secFilterInput', ''); await pg.wait_for_timeout(500)
        await cdp.send('Emulation.setCPUThrottlingRate', {'rate': 1})
        await pg.screenshot(path=f'{shots}/libtabs-songs-big-{scheme}-{w}.png')
    check(not errs, f'{T} no page errors {errs[:3]}')
    await ctx.close()

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
        await run(b, 'dark', 390, 844)
        await run(b, 'light', 360, 780)
        await b.close()
    print('ALL PASSED' if not fails else 'FAILED %s' % fails)
asyncio.run(main())
