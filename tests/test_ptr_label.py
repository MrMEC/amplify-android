"""Build 699 (Mark): after pulling down to refresh, the page name in the header must not land over the tabs.
Build 473 (Mark): the tabs of every Library, Podcasts and Watch page stay at the top while the
page scrolls (under the header, and up to the top of the screen when the header slides away).
Podcasts' date headings and Live TV's time bar stay sticky too, just under the tabs.
Phone, dark and light. Run: python3 tests/test_ptr_label.py (screenshots in /tmp/claude-0/t/shots)"""
import sys as _nsys, os as _nos; _nsys.path.insert(0, _nos.path.dirname(_nos.path.abspath(__file__))); from notice_auto import AUTO_NOTICE
import asyncio, os, json, threading, http.server, functools, shutil, subprocess
from playwright.async_api import async_playwright

PORT = 8897
root = '/tmp/claude-0/t/srv_ptr'
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

async def pull(pg, cdp, dist=260):
    x = 160
    await cdp.send('Input.dispatchTouchEvent', {'type': 'touchStart', 'touchPoints': [{'x': x, 'y': 150}]})
    for i in range(1, 16):
        await cdp.send('Input.dispatchTouchEvent', {'type': 'touchMove', 'touchPoints': [{'x': x, 'y': 150 + dist * i / 15}]})
        await pg.wait_for_timeout(12)
    await cdp.send('Input.dispatchTouchEvent', {'type': 'touchEnd', 'touchPoints': []})

LAB = """()=>{ var L = document.getElementById('hdrPageLabel'), H = document.getElementById('stationsHeading'), T = document.querySelector('#stationsGrid > .lib-tabs');
  var tr = function(e){ var g = document.createRange(); g.selectNodeContents(e); var b = g.getBoundingClientRect(); return { left: Math.round(b.left), top: Math.round(b.top), bottom: Math.round(b.bottom) }; };
  return { lab: tr(L), op: getComputedStyle(L).opacity, styleTop: L.style.top, head: tr(H), tabsTop: Math.round(T.getBoundingClientRect().top), y: Math.round(scrollY),
    hidden: document.body.classList.contains('hdr-hidden'), mainT: document.querySelector('main.main').style.transform }; }"""

async def run(b, scheme):
    T = f'[{scheme}]'
    ctx = await b.new_context(viewport={'width': 327, 'height': 700}, device_scale_factor=3.3, is_mobile=True, has_touch=True, color_scheme=scheme, locale='en-US')
    await ctx.add_init_script(MOCK); await ctx.add_init_script(AUTO_NOTICE)
    await ctx.add_init_script("try{ localStorage.setItem('radioPlayerTheme', %s); localStorage.setItem('radioPlayerTourDone','1'); }catch(e){}" % json.dumps(scheme))
    pg = await ctx.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
    cdp = await ctx.new_cdp_session(pg)
    await pg.route('**/*', lambda r: r.continue_() if '127.0.0.1' in r.request.url else r.fulfill(status=200, content_type='application/json', body='[]') if '/json/' in r.request.url else r.abort())
    await pg.goto(f'http://127.0.0.1:{PORT}/index.html'); await pg.wait_for_timeout(2500)
    await pg.evaluate("""(function(){ var ov=document.getElementById('addMusicOverlay'); if(ov) ov.classList.add('open');
      var btn=document.getElementById('addMusicFolderBtn'); btn.disabled=false; btn.click(); })()""")
    for _ in range(80):
        await pg.wait_for_timeout(500)
        if await pg.evaluate('__t.n()') >= N_SONGS: break
    await pg.wait_for_timeout(1500)
    await pg.evaluate("try{ document.getElementById('addMusicOverlay').classList.remove('open'); hideImportPanel(); }catch(e){}")
    await pg.evaluate("document.querySelector('.mobile-nav-btn[data-nav=library]').click()"); await pg.wait_for_timeout(1200)
    for tab in ['artists', 'songs']:
        await pg.evaluate("(t)=>document.querySelector('#stationsGrid > .lib-tabs [data-libtab='+t+']').click()", tab); await pg.wait_for_timeout(1200)
        await pg.evaluate("window.scrollTo(0, 0)"); await pg.wait_for_timeout(400)
        rest = await pg.evaluate(LAB)
        await pull(pg, cdp); await pg.wait_for_timeout(2200)
        after = await pg.evaluate(LAB)
        check(after['mainT'] in ('', 'none'), f'{T} {tab}: page back in place after the refresh ({after["mainT"]!r})')
        # down (header slides away), then a little back up (header back)
        for yy in range(100, 801, 100):
            await pg.evaluate("(y)=>window.scrollTo(0, y)", yy); await pg.wait_for_timeout(60)
        await pg.wait_for_timeout(500)
        down = await pg.evaluate(LAB)
        await pg.screenshot(path=f'{shots}/ptr-{scheme}-{tab}-down.png')
        await pg.evaluate("window.scrollTo(0, 740)"); await pg.wait_for_timeout(1500)
        up = await pg.evaluate(LAB)
        await pg.screenshot(path=f'{shots}/ptr-{scheme}-{tab}-up.png')
        await pg.evaluate("window.scrollTo(0, 0)"); await pg.wait_for_timeout(700)
        back0 = await pg.evaluate(LAB)
        check(back0['op'] == '0' and abs(back0['styleTop'].replace('px','') and int(back0['styleTop'][:-2]) - rest['head']['top'] - 3) <= 1 and abs(back0['head']['top'] - rest['head']['top']) <= 1, f'{T} {tab}: back at the top, the heading and the label position are as before the refresh ({back0})')
        print(T, tab, 'rest', rest, '\n  after', after, '\n  down', down, '\n  up', up)
        check(down['hidden'] and down['lab']['bottom'] <= 0, f'{T} {tab}: after the refresh, header away -> the page name goes with it (bottom {down["lab"]["bottom"]})')
        # Since build 570 the header stays away on a scroll back up (nothing returns until the top).
        check(up['lab']['bottom'] <= up['tabsTop'], f'{T} {tab}: the page name is above the tabs, not over them ({up["lab"]["bottom"]} vs tabs {up["tabsTop"]})')
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
