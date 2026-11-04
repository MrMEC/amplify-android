"""Build 473 (Mark): the tabs of every Library, Podcasts and Watch page stay at the top while the
page scrolls (under the header, and up to the top of the screen when the header slides away).
Podcasts' date headings and Live TV's time bar stay sticky too, just under the tabs.
Phone, dark and light. Run: python3 tests/test_sticky_tabs.py (screenshots in /tmp/claude-0/t/shots)"""
import sys as _nsys, os as _nos; _nsys.path.insert(0, _nos.path.dirname(_nos.path.abspath(__file__))); from notice_auto import AUTO_NOTICE
import asyncio, os, json, threading, http.server, functools, shutil, subprocess
from playwright.async_api import async_playwright

PORT = 8893
root = '/tmp/claude-0/t/srv_sticky'
shots = '/tmp/claude-0/t/shots'
os.makedirs(shots, exist_ok=True)
shutil.rmtree(root, ignore_errors=True); os.makedirs(root)
HOOK = "window.__t = { n: function(){ return libraryTracks.length; }, ev: function(js){ return eval(js); } };\n"
_src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'www', 'index.html')).read()
_mark = '  var coverFlow = null;\n'
assert _src.count(_mark) == 1
open(root + '/index.html', 'w').write(_src.replace(_mark, _mark + HOOK))
M = root + '/Music'; os.makedirs(M)
N_SONGS = 48
NATO = ['Alpha', 'Bravo', 'Charlie', 'Delta', 'Echo', 'Foxtrot', 'Golf', 'Hotel', 'India', 'Juliet', 'Kilo', 'Lima', 'Mike', 'November',
        'Oscar', 'Papa', 'Quebec', 'Romeo', 'Sierra', 'Tango', 'Uniform', 'Victor', 'Whiskey', 'Xray']
for i in range(N_SONGS):
    a = NATO[i // 2]
    subprocess.run(['ffmpeg', '-loglevel', 'error', '-y', '-f', 'lavfi', '-i', f'sine=frequency={300 + i * 7}:duration=1', '-c:a', 'libmp3lame', '-b:a', '32k',
                    '-metadata', f'title={NATO[(i * 7) % 24]} Song {i:02d}', '-metadata', f'artist={a}', '-metadata', f'album={a} Album',
                    '-metadata', 'genre=Rock', f'{M}/{i:02d}.mp3'], check=True)
class Q(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a): pass
srv = http.server.ThreadingHTTPServer(('127.0.0.1', PORT), functools.partial(Q, directory=root))
threading.Thread(target=srv.serve_forever, daemon=True).start()
files = [{'uri': f'http://127.0.0.1:{PORT}/Music/{f}', 'name': f, 'relPath': f'Music/{f}', 'type': 'audio/mpeg',
          'size': os.path.getsize(f'{M}/{f}'), 'lastModified': 1700000000000} for f in sorted(os.listdir(M))]
def vf(rel, lm=1):
    return {'uri': 'content://doc/' + rel.replace('/', '%2F'), 'name': rel.split('/')[-1], 'relPath': rel, 'type': '', 'video': True, 'size': 900000000, 'lastModified': lm}
VFILES = [vf('Videos/Movies/Film Number %02d (19%02d).mkv' % (i, 60 + i), i) for i in range(30)] + \
         [vf('Videos/TV/Show %02d/Season 1/Show.%02d.S01E01.Pilot.mkv' % (i, i), 40 + i) for i in range(18)]
CH = [{'id': 'link:%d' % i, 'name': 'Channel %02d' % i, 'url': 'http://tv.example/%d.m3u8' % i, 'logo': '', 'country': 'US', 'cats': [], 'catNames': [], 'src': 'link', 'addedAt': i}
      for i in range(30)]
def ep(cid, show, title, date, dur):
    return {'type': 'podcast', 'guid': f'g-{cid}', 'name': title, 'collectionId': cid, 'collectionName': show,
            'releaseDate': date, 'duration': dur, 'episodeUrl': f'https://pod.example/{cid}.mp3', 'artworkUrl': ''}
SUBS = [{'collectionId': 100 + i, 'collectionName': 'Podcast Show %02d' % i, 'artistName': 'Host %d' % i, 'artworkUrl': '', 'feedUrl': 'https://pod.example/f%d' % i,
         'latestEpisodeDate': '2026-10-%02dT10:00:00Z' % (28 - i // 3),
         'latestEpisode': ep(100 + i, 'Podcast Show %02d' % i, 'Episode title number %d' % i, '2026-10-%02dT10:00:00Z' % (28 - i // 3), 1800 + i * 60)} for i in range(30)]
PLS = [{'id': 'pl_%d' % i, 'label': 'Playlist %02d' % i, 'stations': [{'name': 'St %d' % i, 'urlToResolve': 'http://s/%d' % i, 'stationuuid': 'u%d' % i}]} for i in range(24)]
MOCK = """(function(){ var picked = %s, vfiles = %s, listeners = {};
 var impl = { pickMusicFolder: function(){ return Promise.resolve({folder:'Music', treeUri:'tree:music', files:picked, truncated:false}); },
   rescanMusicFolder: function(){ return Promise.resolve({folder:'Music', treeUri:'tree:music', files:picked, truncated:false}); },
   pickVideoFolder: function(){ return Promise.resolve({ folder: 'Videos', treeUri: 'tree:vid', files: vfiles, truncated: false }); },
   rescanVideoFolder: function(){ return Promise.resolve({ folder: 'Videos', treeUri: 'tree:vid', files: vfiles }); },
   videoInfo: function(o){ return Promise.resolve({ duration: 5400000, width: 1920, height: 1080, thumb: '' }); },
   cacheCheck: function(){ return Promise.resolve({ url: 'file:///cache/x.mp3' }); },
   addListener: function(n, f){ (listeners[n] = listeners[n] || []).push(f); return Promise.resolve({remove:function(){}}); } };
 var P = new Proxy({}, {get:function(t,k){ if(k==='then') return undefined; if(k==='setCarLibraryPart') return undefined; if(impl[k]) return impl[k]; return function(){ return Promise.resolve({}); }; }});
 window.Capacitor = { isNativePlatform:function(){return true;}, getPlatform:function(){return 'android';}, registerPlugin:function(){ return P; }, Plugins:{AmplifyPlayer:P}, convertFileSrc:function(u){return u;} };
 try{ if(!localStorage.getItem('__seeded')){ localStorage.setItem('__seeded','1');
   localStorage.setItem('radioPlayerVideoChannels', %s); localStorage.setItem('radioPlayerPodcastSubs', %s); localStorage.setItem('radioPlayerStationPlaylists', %s); } }catch(e){}
})();""" % (json.dumps(files), json.dumps(VFILES), json.dumps(json.dumps(CH)), json.dumps(json.dumps(SUBS)), json.dumps(json.dumps(PLS)))

fails = []
def check(cond, msg):
    print(('PASS ' if cond else 'FAIL ') + msg)
    if not cond: fails.append(msg)

# Where the tab row and the thing that should sit under it are, after scrolling down (header slid
# away) and then a little back up (header back).
MEASURE = """(sel2)=>{ var t = document.querySelector('#stationsGrid > .lib-tabs') || document.querySelector('#stationsGrid > .watch-tabs') ||
    (document.getElementById('podcastTabs').offsetParent ? document.getElementById('podcastTabs') : null);
  if(!t) return null;
  var r = t.getBoundingClientRect(), o = { top: Math.round(r.top), bottom: Math.round(r.bottom), y: Math.round(scrollY),
    hidden: document.body.classList.contains('hdr-hidden'), bg: getComputedStyle(t).backgroundColor, pos: getComputedStyle(t).position, stuck: t.classList.contains('stab-stuck'),
    left: Math.round(r.left), right: Math.round(r.right), vw: innerWidth, sw: document.documentElement.scrollWidth };
  var hdr = document.querySelector('.sidebar-top'); o.hdrBottom = hdr ? Math.round(hdr.getBoundingClientRect().bottom) : null;
  // what is visible right under the tab row (the topmost thing, at the middle of the screen width)
  var x = innerWidth / 2, below = document.elementFromPoint(x, r.bottom + 2);
  var above = document.elementFromPoint(40, Math.max(1, r.top - 20)); o.aboveIsTabs = !!(above && (above === t || t.contains(above)));
  o.belowCls = below ? (below.className && below.className.baseVal === undefined ? String(below.className) : '') : '';
  if(sel2){
    var els = Array.prototype.filter.call(document.querySelectorAll(sel2), function(e){ var b = e.getBoundingClientRect(); return b.height && b.bottom > r.bottom - 1 && b.top < r.bottom + 400; });
    var e2 = els[0]; if(e2){ var b2 = e2.getBoundingClientRect(); o.second = { top: Math.round(b2.top), text: (e2.textContent || '').trim().slice(0, 30) }; }
  }
  return o; }"""

async def scroll_check(pg, T, name, sel2=None, need=900):
    maxy = await pg.evaluate("document.documentElement.scrollHeight - innerHeight")
    if maxy < need:
        check(False, f'{T} {name}: page long enough to scroll ({maxy})'); return
    await pg.evaluate("window.scrollTo(0, 0)"); await pg.wait_for_timeout(350)
    top0 = await pg.evaluate(MEASURE, sel2)
    for y in (20, 50):
        await pg.evaluate("(y)=>window.scrollTo(0, y)", y); await pg.wait_for_timeout(350)
        await pg.screenshot(path=f'{shots}/sticky-{T[1:-1].replace(" ", "-")}-{name}-y{y}.png')
    await pg.evaluate("window.scrollTo(0, 0)"); await pg.wait_for_timeout(350)
    jumps = []
    for y in range(100, need + 1, 100):
        await pg.evaluate("(y)=>window.scrollTo(0, y)", y); await pg.wait_for_timeout(60)
        got = await pg.evaluate("Math.round(scrollY)")
        if abs(got - y) > 2: jumps.append((y, got))
    await pg.wait_for_timeout(450)
    check(not jumps, f'{T} {name}: the page scrolls where it is asked, no jumps {jumps[:3]}')
    max2 = await pg.evaluate("document.documentElement.scrollHeight - innerHeight")
    check(max2 - maxy <= 4, f'{T} {name}: the page does not grow while scrolling ({maxy} -> {max2})')   # long lists may settle a little shorter as rows are drawn
    down = await pg.evaluate(MEASURE, sel2)
    await pg.screenshot(path=f'{shots}/sticky-{T[1:-1].replace(" ", "-")}-{name}-down.png')
    await pg.evaluate("(y)=>window.scrollTo(0, y)", need - 60); await pg.wait_for_timeout(450)
    up = await pg.evaluate(MEASURE, sel2)
    await pg.screenshot(path=f'{shots}/sticky-{T[1:-1].replace(" ", "-")}-{name}-up.png')
    print(T, name, 'start', top0, '\n   down', down, '\n   up', up)
    check(down and down['hidden'] and abs(down['top'] - 8) <= 1 and down['stuck'], f'{T} {name}: scrolled down, header away -> tabs 8px from the top of the screen, with their backdrop ({down and down["top"]}, {down and down["stuck"]})')
    check(not top0['stuck'], f'{T} {name}: at rest no backdrop (the heading above stays visible)')
    check(up and not up['hidden'] and up['stuck'] and abs(up['top'] - up['hdrBottom']) <= 2 if up and up['hdrBottom'] is not None else False,
          f'{T} {name}: header back -> tabs right under it ({up and up["top"]} vs header {up and up["hdrBottom"]})')
    check(up and up['bg'] not in ('rgba(0, 0, 0, 0)', 'transparent'), f'{T} {name}: tabs on the page colour so rows pass cleanly under ({up and up["bg"]})')
    check(up and up['left'] <= 0 and up['right'] >= up['vw'] and up['sw'] <= up['vw'], f'{T} {name}: edge to edge, no sideways scroll')
    if sel2:
        check(down.get('second') and abs(down['second']['top'] - down['bottom'] - 6) <= 2, f'{T} {name}: {sel2} sticks right under the tabs (header away) {down.get("second")} vs {down["bottom"]}')
        check(up.get('second') and abs(up['second']['top'] - up['bottom'] - 6) <= 2, f'{T} {name}: {sel2} sticks right under the tabs (header back) {up.get("second")} vs {up["bottom"]}')
    await pg.evaluate("window.scrollTo(0, 0)"); await pg.wait_for_timeout(400)
    back = await pg.evaluate(MEASURE, sel2)
    check(back and not back['stuck'], f'{T} {name}: back at the top, the backdrop is gone')
    check(back and abs(back['top'] - top0['top']) <= 1, f'{T} {name}: back at the top, the tabs sit where they always did ({top0["top"]} -> {back and back["top"]})')

async def run(b, scheme):
    T = f'[{scheme}]'
    ctx = await b.new_context(viewport={'width': 390, 'height': 844}, device_scale_factor=2, is_mobile=True, has_touch=True, color_scheme=scheme, locale='en-US')
    await ctx.add_init_script(MOCK); await ctx.add_init_script(AUTO_NOTICE)
    await ctx.add_init_script("try{ localStorage.setItem('radioPlayerTheme', %s); localStorage.setItem('radioPlayerTourDone','1'); }catch(e){}" % json.dumps(scheme))
    pg = await ctx.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
    await pg.route('**/*', lambda r: r.continue_() if '127.0.0.1' in r.request.url else r.fulfill(status=200, content_type='application/json', body='[]') if '/json/' in r.request.url else r.abort())
    await pg.goto(f'http://127.0.0.1:{PORT}/index.html'); await pg.wait_for_timeout(2500)
    await pg.evaluate("""(function(){ var ov=document.getElementById('addMusicOverlay'); if(ov) ov.classList.add('open');
      var btn=document.getElementById('addMusicFolderBtn'); btn.disabled=false; btn.click(); })()""")
    for _ in range(80):
        await pg.wait_for_timeout(500)
        if await pg.evaluate('__t.n()') >= N_SONGS: break
    await pg.wait_for_timeout(1500)
    await pg.evaluate("try{ document.getElementById('addMusicOverlay').classList.remove('open'); hideImportPanel(); }catch(e){}")
    check(await pg.evaluate('__t.n()') == N_SONGS, f'{T} {N_SONGS} songs in the library')
    # ---- Library
    await pg.evaluate("document.querySelector('.mobile-nav-btn[data-nav=library]').click()"); await pg.wait_for_timeout(1200)
    for tab in ['artists', 'albums', 'songs', 'playlists']:
        await pg.evaluate("(t)=>document.querySelector('#stationsGrid > .lib-tabs [data-libtab='+t+']').click()", tab); await pg.wait_for_timeout(1200)
        await scroll_check(pg, T, 'library-' + tab, need=900 if tab != 'playlists' else 600)
    for tab in ['artists', 'songs']:
        await pg.evaluate("(t)=>document.querySelector('#stationsGrid > .lib-tabs [data-libtab='+t+']').click()", tab); await pg.wait_for_timeout(1200)
        await pg.evaluate("window.scrollTo(0, 0)"); await pg.wait_for_timeout(300)
        await pg.evaluate("__t.ev(\"azScrollToLetter('K')\")"); await pg.wait_for_timeout(2600)
        az = await pg.evaluate("""()=>{ var t = document.querySelector('#stationsGrid > .lib-tabs').getBoundingClientRect(), el = __t.ev("azTargets['K']");
          var r = el.getBoundingClientRect(); return { tabsBottom: Math.round(t.bottom), letterTop: Math.round(r.top), text: (el.textContent||'').trim().slice(0, 20), y: Math.round(scrollY) }; }""")
        await pg.screenshot(path=f'{shots}/sticky-{T[1:-1]}-az-{tab}.png')
        check(az['y'] > 300 and az['tabsBottom'] + 6 <= az['letterTop'] <= az['tabsBottom'] + 24, f'{T} {tab}: A-Z jump to K lands just below the tabs, not under them {az}')
    await pg.evaluate("document.querySelector('#stationsGrid > .lib-tabs [data-libtab=genres]').click()"); await pg.wait_for_timeout(1200)
    await scroll_check(pg, T, 'library-genres', need=300)
    # ---- Podcasts (Latest: date headings stick under the tabs)
    await pg.evaluate("document.querySelector('.mobile-nav-btn[data-nav=podcasts]').click()"); await pg.wait_for_timeout(1500)
    await pg.evaluate("(()=>{ var b = Array.prototype.filter.call(document.querySelectorAll('#podcastTabs .home-tab'), x => /Latest/.test(x.textContent))[0]; if(b) b.click(); })()"); await pg.wait_for_timeout(1200)
    await scroll_check(pg, T, 'podcasts-latest', sel2='#stationsGrid > .podcast-date-heading', need=1200)
    await pg.evaluate("(()=>{ var b = Array.prototype.filter.call(document.querySelectorAll('#podcastTabs .home-tab'), x => /A-Z|Following/.test(x.textContent))[0]; if(b) b.click(); })()"); await pg.wait_for_timeout(1200)
    await scroll_check(pg, T, 'podcasts-az', need=900)
    # ---- Watch
    await pg.evaluate("document.querySelector('.mobile-nav-btn[data-nav=video]').click()"); await pg.wait_for_timeout(1500)
    async def vtab(v):
        await pg.evaluate("(v)=>document.querySelector('#stationsGrid > .watch-tabs [data-vtab='+v+']').click()", v); await pg.wait_for_timeout(1000)
    await vtab('movies')
    await pg.evaluate("document.getElementById('videoAddHeaderBtn').click()"); await pg.wait_for_timeout(3500)
    await vtab('channels')
    await scroll_check(pg, T, 'watch-livetv', sel2='#stationsGrid > .epg > .epg-head', need=1200)
    await vtab('movies')
    await scroll_check(pg, T, 'watch-movies', need=900)
    await vtab('shows')
    await scroll_check(pg, T, 'watch-shows', need=600)
    check(not errs, f'{T} no page errors {errs[:3]}')
    await ctx.close()

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
        for scheme in ('dark', 'light'):
            await run(b, scheme)
        await b.close()
asyncio.run(main())
print('FAILED: %d' % len(fails) if fails else 'ALL PASS')
raise SystemExit(1 if fails else 0)
