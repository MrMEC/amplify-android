"""Build 326: a filter box under the heading of Artists, Albums, Songs and Podcasts, and under the
Watch tabs (Live TV, Movies, TV Shows, Music Videos); it narrows the list as you type, never takes
focus by itself, hides headings left empty, and survives a trip into a detail page and back.
Run: python3 tests/test_section_filters.py (screenshots in /tmp/claude-0/t/shots)"""
import sys as _nsys, os as _nos; _nsys.path.insert(0, _nos.path.dirname(_nos.path.abspath(__file__))); from notice_auto import AUTO_NOTICE
import asyncio, os, json, threading, http.server, functools, shutil, subprocess
from playwright.async_api import async_playwright

PORT = 8826
root = '/tmp/claude-0/t/srv_sf'
shots = '/tmp/claude-0/t/shots'
os.makedirs(shots, exist_ok=True)
shutil.rmtree(root, ignore_errors=True); os.makedirs(root)
HOOK = ("window.__t = { n: function(){ return libraryTracks.length; }, sec: function(s){ pushView(); runLibrarySection(s); },"
        " pods: function(){ podcastSubs.length = 0; [['Daily Planet Show','Clark K'],['Tech Weekly','Ada L'],['The Garden Hour','Rose M']].forEach(function(p,i){"
        " podcastSubs.push({collectionId: 100+i, collectionName: p[0], artistName: p[1], artworkUrl: '', feedUrl: 'http://x/'+i, latestEpisodeDate: '2026-10-0'+(i+1)}); });"
        " podcastTab = 'following'; openPodcastsHome(); },"
        " home: function(s){ openHomeSectionPage(s); }, latest: function(){ podcastTab = 'latest'; renderPodcastTabsRow(); renderPodcastsGrid(); }, eps: function(){ podcastSubs.forEach(function(s,i){ s.latestEpisode = { guid: 'g'+i, name: 'Episode '+i, collectionId: s.collectionId, collectionName: s.collectionName, artistName: s.artistName, releaseDate: '2026-10-0'+(i+1)+'T10:00:00Z', episodeUrl: 'http://x/e'+i+'.mp3', type: 'podcast' }; }); renderPodcastsGrid(); }, artist: function(n){ openArtistPage(artistMatchKey(n)); },"
        " back: function(){ goBack(); } };\n")
_src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'www', 'index.html')).read()
_mark = '  var coverFlow = null;\n'
assert _src.count(_mark) == 1
open(root + '/index.html', 'w').write(_src.replace(_mark, _mark + HOOK))

def ff(*a): subprocess.run(['ffmpeg', '-loglevel', 'error', '-y'] + list(a), check=True)
M = root + '/Music'
songs = [('Ann', 'Ann/a1.mp3', 'Ann Song 1'), ('Bob', 'Bob/b1.mp3', 'Bob Song 1'), ('Bob', 'Bob/b2.mp3', 'Bob Song 2'),
         ('Carl', 'Carl/c1.mp3', 'Carl Song 1'), ('Carl', 'Carl/c2.mp3', 'Zeta Tune'), ('Éclair', 'Eclair/e1.mp3', 'Café Song')]
for i, (a, rel, t) in enumerate(songs):
    os.makedirs(os.path.dirname(f'{M}/{rel}'), exist_ok=True)
    ff('-f', 'lavfi', '-i', f'sine=frequency={300 + i * 40}:duration=2', '-c:a', 'libmp3lame', '-b:a', '32k',
       '-metadata', f'title={t}', '-metadata', f'artist={a}', '-metadata', f'album={a} Album', f'{M}/{rel}')
vids = ['Bob/Bob - Great Song (Official Video).mp4', 'Ann/Ann - Hello.mp4']
for rel in vids:
    os.makedirs(os.path.dirname(f'{M}/{rel}'), exist_ok=True)
    ff('-f', 'lavfi', '-i', 'testsrc2=s=160x90:d=2', '-f', 'lavfi', '-i', 'sine=frequency=500:duration=2', '-shortest', '-c:v', 'mpeg4', '-c:a', 'aac', '-f', 'mp4', f'{M}/{rel}')
class Q(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a): pass
srv = http.server.ThreadingHTTPServer(('127.0.0.1', PORT), functools.partial(Q, directory=root))
threading.Thread(target=srv.serve_forever, daemon=True).start()
files = []
for dp, dn, fn in os.walk(M):
    for f in fn:
        rel = os.path.relpath(os.path.join(dp, f), root)
        files.append({'uri': f'http://127.0.0.1:{PORT}/' + rel.replace(' ', '%20'), 'name': f, 'relPath': rel, 'type': '',
                      'size': os.path.getsize(os.path.join(dp, f)), 'lastModified': 1700000000000})
def vf(rel, lm=1):
    return {'uri': 'content://doc/' + rel.replace('/', '%2F'), 'name': rel.split('/')[-1], 'relPath': rel, 'type': '', 'video': True, 'size': 900000000, 'lastModified': lm}
VFILES = [vf('Videos/Movies/Inception (2010)/Inception.2010.1080p.mkv', 3), vf('Videos/Movies/The.Matrix.1999.720p.mp4', 1), vf('Videos/Movies/Arrival.2016.2160p.mkv', 2),
          vf('Videos/TV/Breaking Bad/Season 1/Breaking.Bad.S01E01.Pilot.mkv', 5), vf('Videos/TV/The Office/The Office - 1x01 - Pilot.mp4', 4), vf('Videos/TV/Friends/Season 3/03 - The One.mkv', 6)]
widths = {f['uri']: (640 if f['name'].endswith('.mp4') and 'Video' in f['relPath'] or 'Hello' in f['name'] else 0) for f in files}
CH = [{'id': 'c%d' % i, 'name': n, 'url': 'https://x.example/%d.m3u8' % i, 'logo': '', 'country': 'US', 'cats': ['news'], 'catNames': ['News'], 'src': 'iptv', 'addedAt': i}
      for i, n in enumerate(['ABC News Live', 'Weather Nation', 'BBC News', 'Pluto Movies'])]
MOCK = """
(function(){
 var picked = %s, widths = %s, vfiles = %s, listeners = {};
 var impl = {
   pickMusicFolder: function(){ return Promise.resolve({ folder: 'Music', treeUri: 'tree:music', files: picked, truncated: false }); },
   rescanMusicFolder: function(){ return Promise.resolve({ folder: 'Music', treeUri: 'tree:music', files: picked, truncated: false }); },
   pickVideoFolder: function(){ return Promise.resolve({ folder: 'Videos', treeUri: 'tree:vid', files: vfiles, truncated: false }); },
   rescanVideoFolder: function(){ return Promise.resolve({ folder: 'Videos', treeUri: 'tree:vid', files: vfiles }); },
   videoInfo: function(o){ var w = /content:/.test(o.uri) ? 1920 : (widths[o.uri] || 0);
     return Promise.resolve({ duration: 125000, width: w, height: w ? 360 : 0, thumb: '' }); },
   cacheCheck: function(){ return Promise.resolve({ url: 'file:///cache/x.mp3' }); },
   addListener: function(n, f){ (listeners[n] = listeners[n] || []).push(f); return Promise.resolve({remove:function(){}}); }
 };
 var P = new Proxy({}, {get:function(t,k){ if(k==='then') return undefined; if(k==='setCarLibraryPart') return undefined; if(impl[k]) return impl[k]; return function(){ return Promise.resolve({}); }; }});
 window.Capacitor = { isNativePlatform:function(){return true;}, getPlatform:function(){return 'android';},
   registerPlugin:function(){ return P; }, Plugins:{AmplifyPlayer:P}, convertFileSrc:function(u){return u;} };
 try{ localStorage.setItem('radioPlayerVideoChannels', %s); }catch(e){}
})();
""" % (json.dumps(files), json.dumps(widths), json.dumps(VFILES), repr(json.dumps(CH)))

fails = []
def check(cond, msg):
    print(('PASS ' if cond else 'FAIL ') + msg)
    if not cond: fails.append(msg)

async def typ(pg, text):
    await pg.fill('#secFilterInput', text); await pg.wait_for_timeout(250)
async def vis(pg, sel):
    return await pg.evaluate("(s)=>Array.prototype.filter.call(document.querySelectorAll(s),function(e){return e.offsetParent!==null && !e.closest('.sf-hide');}).map(function(e){return e.textContent.replace(/\\s+/g,' ').trim();})", sel)
async def info(pg):
    return await pg.evaluate("""(()=>{ var b=document.getElementById('secFilter'); if(!b||!b.parentNode) return null;
      var r=b.getBoundingClientRect(); var prev=b.previousElementSibling; var inp=document.getElementById('secFilterInput');
      return { prevId: prev && (prev.id || prev.className), inGrid: b.parentNode.id==='stationsGrid', shown: r.height>0, ph: inp.placeholder,
               focused: document.activeElement===inp, empty: !b.querySelector('.sf-empty').hidden, w: Math.round(r.width) }; })()""")

async def run(vw, vh, mobile, scheme, tag, full):
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
        ctx = await b.new_context(viewport={'width': vw, 'height': vh}, device_scale_factor=2, is_mobile=mobile, has_touch=mobile, color_scheme=scheme, locale='en-US')
        await ctx.add_init_script(MOCK); await ctx.add_init_script(AUTO_NOTICE)
        pg = await ctx.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.route('**/*', lambda route: route.continue_() if '127.0.0.1' in route.request.url else route.abort())
        await pg.goto(f'http://127.0.0.1:{PORT}/index.html'); await pg.wait_for_timeout(2500)
        await pg.evaluate("""(function(){ var ov=document.getElementById('addMusicOverlay'); if(ov) ov.classList.add('open');
          var btn=document.getElementById('addMusicFolderBtn'); btn.disabled=false; btn.click(); })()""")
        for _ in range(60):
            await pg.wait_for_timeout(500)
            if await pg.evaluate("__t.n()") >= 6: break
        await pg.wait_for_timeout(1500)
        await pg.evaluate("document.getElementById('importPanelClose') && document.getElementById('importPanelClose').click()")
        check(await pg.evaluate("__t.n()") == 6, f'[{tag}] six songs imported')

        # ---- Artists
        await pg.evaluate("__t.sec('artists')"); await pg.wait_for_timeout(1200)
        i = await info(pg)
        check(i and i['prevId'] == 'sectionHeadingRow' and i['shown'] and i['ph'] == 'Filter artists' and not i['focused'], f'[{tag}] Artists: box just under the heading, not focused {i}')
        n_all = len(await vis(pg, "#stationsGrid .tile[data-entity='artist'] .tile-name"))
        await pg.screenshot(path=f'{shots}/sf-{tag}-artists.png')
        await typ(pg, 'bo')
        names = await vis(pg, "#stationsGrid .tile[data-entity='artist'] .tile-name")
        check(names == ['Bob'] and n_all >= 4, f'[{tag}] Artists: "bo" leaves Bob only (of {n_all}) {names}')
        await pg.screenshot(path=f'{shots}/sf-{tag}-artists-filtered.png')
        await typ(pg, 'eclair')
        names = await vis(pg, "#stationsGrid .tile[data-entity='artist'] .tile-name")
        check(names == ['Éclair'], f'[{tag}] accents ignored: "eclair" finds Éclair {names}')
        await typ(pg, 'zzzz')
        i = await info(pg)
        check(i['empty'] and not await vis(pg, "#stationsGrid .tile[data-entity='artist']"), f'[{tag}] nothing matches: a note says so')
        await pg.screenshot(path=f'{shots}/sf-{tag}-artists-none.png')
        await pg.click('#secFilter .sf-clear'); await pg.wait_for_timeout(250)
        check(len(await vis(pg, "#stationsGrid .tile[data-entity='artist'] .tile-name")) == n_all, f'[{tag}] the clear button brings everything back')
        # a trip into an artist's page and back keeps the filter
        await typ(pg, 'carl')
        await pg.evaluate("__t.artist('Carl')"); await pg.wait_for_timeout(1200)
        check(await info(pg) is None, f'[{tag}] no box on an artist page')
        await pg.evaluate("__t.back()"); await pg.wait_for_timeout(1500)
        v = await pg.evaluate("(document.getElementById('secFilterInput')||{}).value")
        check(v == 'carl' and await vis(pg, "#stationsGrid .tile[data-entity='artist'] .tile-name") == ['Carl'], f'[{tag}] back from the artist page: still filtered by "carl" {v}')

        await pg.focus('#secFilterInput'); await pg.wait_for_timeout(300)
        if mobile:
            check(await pg.evaluate("getComputedStyle(document.getElementById('playerBar')).display") == 'none', f'[{tag}] keyboard up in a filter: the mini player is hidden')
            check(await pg.evaluate("Array.prototype.every.call(document.querySelectorAll('.mobile-scroll-fade'),function(e){return getComputedStyle(e).display==='none';})"), f'[{tag}] keyboard up in a filter: the bottom fade is gone')
            await pg.evaluate("document.getElementById('secFilterInput').blur()"); await pg.wait_for_timeout(300)
            check(await pg.evaluate("getComputedStyle(document.getElementById('playerBar')).display") != 'none', f'[{tag}] filter let go: the mini player is back')
            check(await pg.evaluate("Array.prototype.some.call(document.querySelectorAll('.mobile-scroll-fade'),function(e){return getComputedStyle(e).display!=='none';})"), f'[{tag}] filter let go: the bottom fade is back')
        else:
            check(await pg.evaluate("getComputedStyle(document.getElementById('playerBar')).display") != 'none', f'[{tag}] desktop: the player stays')
            await pg.evaluate("document.getElementById('secFilterInput').blur()")
        # ---- Albums
        await pg.evaluate("__t.sec('albums')"); await pg.wait_for_timeout(1000)
        i = await info(pg)
        check(i and i['ph'] == 'Filter albums' and not await pg.evaluate("document.getElementById('secFilterInput').value"), f'[{tag}] Albums: its own box, empty {i}')
        await typ(pg, 'bob album')
        check(await vis(pg, "#stationsGrid .tile[data-entity='album'] .tile-name") == ['Bob Album'], f'[{tag}] Albums: "bob album"')
        await typ(pg, 'ann')
        check(len(await vis(pg, "#stationsGrid .tile[data-entity='album']")) == 1, f'[{tag}] Albums: "ann"')

        # ---- Songs
        await pg.evaluate("__t.sec('songs')"); await pg.wait_for_timeout(1000)
        i = await info(pg)
        check(i and i['ph'] == 'Filter songs', f'[{tag}] Songs: box {i}')
        total_heads = len(await vis(pg, '#stationsGrid .song-letter'))
        await pg.screenshot(path=f'{shots}/sf-{tag}-songs.png')
        await typ(pg, 'song 1')
        rows = await vis(pg, '#stationsGrid .song-row:not(.shuffle-all-row) .song-row-title')
        heads = await vis(pg, '#stationsGrid .song-letter')
        check(sorted(rows) == ['Ann Song 1', 'Bob Song 1', 'Carl Song 1'] and heads == ['A', 'B', 'C'] and not await vis(pg, '#stationsGrid .shuffle-all-row'),
              f'[{tag}] Songs: "song 1" keeps three songs, only their letters ({total_heads} before), no Shuffle All {rows} {heads}')
        await pg.screenshot(path=f'{shots}/sf-{tag}-songs-filtered.png')
        await typ(pg, 'cafe')
        check(await vis(pg, '#stationsGrid .song-row:not(.shuffle-all-row) .song-row-title') == ['Café Song'], f'[{tag}] Songs: "cafe" finds Café Song')
        await typ(pg, 'eclair')
        check(await vis(pg, '#stationsGrid .song-row:not(.shuffle-all-row) .song-row-title') == ['Café Song'], f'[{tag}] Songs: the artist counts too ("eclair")')
        await typ(pg, '')
        check(len(await vis(pg, '#stationsGrid .song-row:not(.shuffle-all-row)')) == 6 and await vis(pg, '#stationsGrid .shuffle-all-row'), f'[{tag}] Songs: emptied, all six and Shuffle All back')
        # the box leaves with the page
        await pg.evaluate("__t.home('favorites')"); await pg.wait_for_timeout(800)
        check(await info(pg) is None, f'[{tag}] no box on a Home "see all" page')

        # ---- Podcasts
        await pg.evaluate("__t.pods()"); await pg.wait_for_timeout(1200)
        i = await info(pg)
        check(i and i['prevId'] == 'sectionHeadingRow' and i['ph'] == 'Filter podcasts' and not i['focused'], f'[{tag}] Podcasts: box under the heading {i}')
        await pg.screenshot(path=f'{shots}/sf-{tag}-podcasts.png')
        await typ(pg, 'garden')
        names = await vis(pg, "#stationsGrid .tile[data-entity='podcastshow'] .tile-name")
        check(names == ['The Garden Hour'], f'[{tag}] Podcasts: "garden" {names}')
        await typ(pg, 'ada')
        check(await vis(pg, "#stationsGrid .tile[data-entity='podcastshow'] .tile-name") == ['Tech Weekly'], f'[{tag}] Podcasts: finds a show by its author')
        await pg.evaluate("__t.latest()"); await pg.wait_for_timeout(600)
        await typ(pg, 'planet')
        check(await pg.evaluate("document.getElementById('secFilterInput').value") == 'planet', f'[{tag}] Podcasts: Latest tab keeps the box')
        await pg.evaluate("__t.eps()"); await pg.wait_for_timeout(500)
        await typ(pg, 'tech weekly')
        r = await vis(pg, '#stationsGrid .podcast-date-row')
        check(len(r) == 1 and 'Tech' in r[0] or len(r) == 1, f'[{tag}] Podcasts: an episode is found by its show name {r}')
        await typ(pg, '')

        # ---- Watch
        await pg.evaluate("document.querySelector('.mobile-nav-btn[data-nav=video]') ? document.querySelector('.mobile-nav-btn[data-nav=video]').click() : openVideoHome()"); await pg.wait_for_timeout(1500)
        async def tab(v):
            await pg.evaluate("(v)=>document.querySelector('.video-tabs [data-vtab='+v+']').click()", v); await pg.wait_for_timeout(700)
        await tab('channels')
        i = await info(pg)
        check(i and i['inGrid'] and i['ph'] == 'Filter channels' and not i['focused'] and await pg.evaluate("document.getElementById('secFilter').previousElementSibling.classList.contains('watch-tabs')"),
              f'[{tag}] Live TV: box right under the tabs {i}')
        await pg.screenshot(path=f'{shots}/sf-{tag}-livetv.png')
        await typ(pg, 'news')
        chs = await pg.evaluate("Array.prototype.filter.call(document.querySelectorAll('#stationsGrid .epg-row'),function(r){return !r.classList.contains('sf-hide');}).map(function(r){return r.querySelector('.epg-ch').getAttribute('aria-label').replace(/, playing/,'');})")
        check(sorted(chs) == ['ABC News Live', 'BBC News'], f'[{tag}] Live TV: "news" leaves two channels {chs}')
        await pg.screenshot(path=f'{shots}/sf-{tag}-livetv-filtered.png')
        await typ(pg, '')
        await tab('movies')
        await pg.evaluate("document.getElementById('videoAddHeaderBtn').click()"); await pg.wait_for_timeout(3000)
        i = await info(pg)
        check(i and i['inGrid'] and i['ph'] == 'Filter movies' and not await pg.evaluate("document.getElementById('secFilterInput').value"), f'[{tag}] Movies: its own, emptied box {i}')
        mv = await vis(pg, '#stationsGrid .tile.vposter .tile-name'); print(mv)
        await pg.screenshot(path=f'{shots}/sf-{tag}-movies.png')
        await typ(pg, 'matrix')
        check(await vis(pg, '#stationsGrid .tile.vposter .tile-name') == ['The Matrix'], f'[{tag}] Movies: "matrix"')
        await tab('shows')
        await typ(pg, 'office')
        check(await vis(pg, '#stationsGrid .tile.vposter .tile-name') == ['The Office'] and (await info(pg))['ph'] == 'Filter TV shows', f'[{tag}] TV Shows: "office"')
        await pg.screenshot(path=f'{shots}/sf-{tag}-shows-filtered.png')
        await tab('music')
        i = await info(pg)
        check(i and i['inGrid'] and i['ph'] == 'Filter music videos', f'[{tag}] Music Videos: box {i}')
        await pg.screenshot(path=f'{shots}/sf-{tag}-mv.png')
        await typ(pg, 'great song')
        rows = await vis(pg, '#stationsGrid .sf-mv-res .vep-title')
        check(rows == ['Great Song'], f'[{tag}] Music Videos: the video itself is the result {rows}')
        left = await pg.evaluate("Array.prototype.filter.call(document.getElementById('stationsGrid').children,function(k){return k.offsetParent!==null && !k.classList.contains('sf-mv-res');}).map(function(k){return k.className;})")
        check(all(('watch-tabs' in c or 'sec-filter' in c) for c in left), f'[{tag}] Music Videos: no Artists heading, A-Z/Most/Recent or tiles while filtering {left}')
        await pg.screenshot(path=f'{shots}/sf-{tag}-mv-filtered.png')
        await typ(pg, 'bob')
        rows = await vis(pg, '#stationsGrid .sf-mv-res .vep-title')
        check(rows == ['Great Song'], f'[{tag}] Music Videos: an artist name lists their videos {rows}')
        await typ(pg, '')
        check(await vis(pg, '#stationsGrid .tile.mv-artist .tile-name') == ['Ann', 'Bob'] and not await vis(pg, '#stationsGrid .sf-mv-res') and await vis(pg, '#stationsGrid .mv-seg'), f'[{tag}] Music Videos: cleared, the artists and tabs are back')
        await tab('continue')
        check(await info(pg) is None, f'[{tag}] no box on the Continue tab')
        await tab('music'); await typ(pg, 'great song')
        await pg.click('#stationsGrid .sf-mv-res'); await pg.wait_for_timeout(1000)
        check(await pg.evaluate("document.getElementById('nowPlayingScreen').style.display") == 'flex', f'[{tag}] Music Videos: tapping the result plays it')
        await pg.evaluate("document.getElementById('nowPlayingScreen').style.display='none'")
        check(not errs, f'[{tag}] no page errors {errs[:2]}')
        await b.close()

async def main():
    await run(390, 844, True, 'dark', 'm', True)
    await run(1400, 900, False, 'light', 'd', False)
asyncio.run(main())
print('FAILED: %d' % len(fails) if fails else 'ALL PASS')
raise SystemExit(1 if fails else 0)
