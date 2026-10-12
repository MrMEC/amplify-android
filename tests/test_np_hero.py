"""Builds 220-225: the Home hero (225: removals from Continue Listening/Watching leave the slides; Top 100 plays recorded) (222: swipeable through the last 50 played; 223: progress bar, station tap plays, last song line, opened files) follows playback (artist portrait + bio for a library song with a
shuffle Play and a tap to the artist page; a channel logo; a podcast or video cover with details).
(Harness from build 219: Daily Mix 1-5, Discover, Hear It Again and Artist Videos rows on Home, under Top 100.
Each mix row shows 20 songs and its heading opens the whole list; Daily Mix features one of the most
played artists plus similar library artists (Deezer related, same genre) ; Discover/Hear It Again use
song play counts; Artist Videos is one artist's videos headed by their name. Lists stay the same all
day and are remade the next. Run: python3 tests/test_daily_mixes.py (screenshots in /tmp/claude-0/t/shots)"""
import asyncio, os, json, threading, http.server, functools, shutil, subprocess, sys
from playwright.async_api import async_playwright

PORT = 8804
root = '/tmp/claude-0/t/srv_hero'
shots = '/tmp/claude-0/t/shots'
os.makedirs(shots, exist_ok=True)
shutil.rmtree(root, ignore_errors=True)
os.makedirs(root)
HOOK = ("window.__h = { stub: function(){ var on = false; try{ Object.defineProperty(audio, 'paused', { configurable: true, get: function(){ return !on; } }); }catch(e){} audio.play = function(){ on = true; return Promise.resolve(); }; audio.pause = function(){ on = false; window.__tp = (window.__tp || 0) + 1; }; },"
        " cover: function(name, url){ var t = libraryTracks.filter(function(x){ return x.name === name; })[0]; setCustomArtUrl('album:' + albumKeyFor(t), url); },"
        " meta: function(n, bio){ var e = findArtistEntry(artistMatchKey(n)); artistMeta[e.key] = { key: e.key, query: n, ok: true, manual: true, name: n, bio: bio, photoUrl: 'https://covers.example/portrait.jpg', description: 'American musician', ts: Date.now() }; delete artistArtResolved[e.key]; },"
        " play: function(name){ __h.stub(); var t = libraryTracks.filter(function(x){ return x.name === name; })[0]; playTrackInList([t], t, 'Test'); },"
        " fake: function(st){ __h.stub(); audio.play(); currentStation = st; noteHeroPlayed(st); updatePlayerMeta(st, ''); setPlayingUI(true); },"
        " playing: function(v){ setPlayingUI(v); },"
        " el: function(sel){ return heroSlides[heroIndex()].querySelector(sel); }, idx: function(){ return heroIndex(); }, n: function(){ return heroSlides.length; }, gaps: function(){ return heroSlides.slice(0, 4).map(function(sl){ return Math.round(document.getElementById('npHeroProgress').getBoundingClientRect().top - sl.querySelector('.nph-play').getBoundingClientRect().bottom); }); },"
        " titles: function(){ return heroSlides.map(function(x){ return x.querySelector('.nph-title').textContent; }); },"
        " rmRecent: function(name){ var r = recentStations.filter(function(x){ return x.name === name; })[0]; removeFromRecent(r || { name: name, url: 'https://radio.example/kiss', urlToResolve: 'https://radio.example/kiss', stationuuid: 'kiss-1' }); },"
        " rmChannel: function(url){ removeFromContinueWatching({ kind: 'channel', ch: { url: url } }); },"
        " chartPreview: function(it){ __h.stub(); audio.play(); currentStation = it; onPlaybackSuccess(it); },"
        " chartVideo: function(it, id){ noteChartVideo(it, { id: id }); },"
        " recents: function(){ return recentStations.map(function(x){ return x.name; }); },"
        " cw: function(){ return Array.from(document.querySelectorAll('#continueWatchingHomeGrid .vw-tile')).map(function(t){ var i = t.querySelector('img'); return [t.querySelector('.tile-name').textContent, i ? (i.getAttribute('src') || i.dataset.src || '') : '']; }); },"
        " rmChart: function(it){ removeFromContinueWatching({ kind: 'chart', item: it }); },"
        " clearStatus: function(){ setStatus('', false); },"
        " bar: function(){ var b = document.getElementById('npHeroProgress'), f = b.firstChild, r = b.getBoundingClientRect(); return { w: Math.round(r.width), h: Math.round(r.height), fill: f.getBoundingClientRect().width / r.width, shown: getComputedStyle(b).display !== 'none', knobs: b.querySelectorAll('*').length, bg: getComputedStyle(b).backgroundColor, fc: getComputedStyle(f).backgroundColor }; },"
        " onair: function(t, a){ window.dispatchEvent(new CustomEvent('amplify-onair', { detail: { id: 'x', title: t, artist: a } })); },"
        " slideLine: function(title){ var sl = heroSlides.filter(function(x){ return x.querySelector('.nph-title').textContent === title; })[0]; return sl ? sl.querySelector('.nph-line').textContent : null; },"
        " cur: function(){ return currentStation ? (currentStation.name || '') : ''; }, inLib: function(){ return libraryTracks.length; },"
        " npOpen: function(){ return document.body.classList.contains('np-open'); }, curArt: function(){ return currentStation ? (libraryArtUrls[favKey(currentStation)] || '') : ''; },"
        " tapSlide: function(title){ var sl = heroSlides.filter(function(x){ return x.querySelector('.nph-title').textContent === title; })[0]; sl.querySelector('.nph-media').click(); },"
        " go: function(i){ var t = document.getElementById('npHeroTrack'); t.scrollLeft = i * t.clientWidth; },"
        " hero: function(){ var h = document.getElementById('npHero'); var sl = heroSlides[heroIndex()] || h; var r = h.getBoundingClientRect(); var d = sl.querySelector('.nph-desc') || h;"
        "   var img = sl.querySelector('.nph-art img'); var lh = parseFloat(getComputedStyle(d).lineHeight); var pb = sl.querySelector('.nph-play') || h; var ti = sl.querySelector('.nph-title') || h;"
        "   return { shown: getComputedStyle(h).display !== 'none' && r.height > 0, top: Math.round(r.top), left: Math.round(r.left), right: Math.round(r.right), vw: innerWidth,"
        "     kicker: (sl.querySelector('.nph-kicker') || h).textContent, title: ti.textContent, line: (sl.querySelector('.nph-line') || h).textContent,"
        "     desc: d.textContent, descLines: d.textContent ? Math.round(d.getBoundingClientRect().height / lh) : 0, img: img ? img.src : '', imgW: img ? Math.round(img.getBoundingClientRect().width) : 0, imgTop: img ? Math.round(img.getBoundingClientRect().top - h.getBoundingClientRect().top) : -1, objPos: img ? getComputedStyle(img).objectPosition : '', mediaH: sl.querySelector('.nph-media') ? Math.round(sl.querySelector('.nph-media').getBoundingClientRect().height) : 0, gap: (function(){ var n = h.nextElementSibling; while(n && (getComputedStyle(n).display === 'none' || !n.getBoundingClientRect().height)) n = n.nextElementSibling; return n ? Math.round(n.getBoundingClientRect().top - r.bottom) : null; })(), headFs: (function(){ var x = document.querySelector('#favoritesSection .home-section-head h2'); return x ? parseFloat(getComputedStyle(x).fontSize) : 0; })(), titleFs: parseFloat(getComputedStyle(ti).fontSize),"
        "     play: pb.dataset.state, first: (function(){ var n = h.nextElementSibling; while(n && getComputedStyle(n).display === 'none') n = n.nextElementSibling; return n ? n.id || n.className : ''; })(),"
        "     playRight: Math.round(pb.getBoundingClientRect().right), playBottom: Math.round(pb.getBoundingClientRect().bottom), bottom: Math.round(sl.getBoundingClientRect ? sl.getBoundingClientRect().bottom : r.bottom) }; } };"
        "window.__d = { n: function(){ return libraryTracks.length; }, home: function(){ loadTopStations(); }, st: function(){ return window.__amplifyDaily(); },"
        " names: function(id){ var m = dailyMixFor(id); return m ? dailyMixSongs(m).map(function(t){ return t.artist + '|' + t.name; }) : null; },"
        " plays: function(){ var p = {}; ['Prince', 'Madonna', 'Kay', 'Earth, Wind & Fire', 'Rick James', 'Lee'].forEach(function(n, i){ p[artistMatchKey(n)] = { name: n, count: [40, 30, 20, 12, 6, 3][i], last: Date.now() - i * 1000 }; }); saveArtistPlays(p);"
        "   var sp = {}; libraryTracks.filter(function(t){ return /^Madonna 0[1-6]$/.test(t.name); }).forEach(function(t){ sp[favKey(t)] = [5, Date.now()]; });"
        "   localStorage.setItem('radioPlayerSongPlays', JSON.stringify(sp)); },"
        " vid: function(){ var k = artistMatchKey('Kay'); ytStore[k] = { channels: ['UC' + 'k'.repeat(22)], chTs: Date.now(), ts: Date.now(), fv: YT_FV, mv: true,"
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
 window.__fireOpen = function(info){ window.__opened = info; (listeners.openfile || []).forEach(function(f){ f({}); }); };
 function dz(u){
   window.__dz.push(u);
   if(/search\\/artist/.test(u)){ return /q=Prince$/.test(u) ? { data: [{ id: 77, name: 'Prince' }] } : { data: [] }; }
   if(/artist\\/77\\/related/.test(u)) return { data: [{ name: 'Rick James' }, { name: 'Madonna' }, { name: 'Nobody Here' }] };
   return { data: [] };
 }
 var impl = {
   pickMusicFolder: function(){ return Promise.resolve({folder:'Music', files:picked, truncated:false}); },
   fetchText: function(o){ if(/api\\.deezer\\.com/.test(o.url)) return Promise.resolve({ text: JSON.stringify(dz(o.url)) }); return Promise.reject(new Error('offline')); },
   takeOpenedFile: function(){ var o = window.__opened || {}; window.__opened = null; return Promise.resolve(o); },
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



from urllib.parse import urlparse
PORTRAIT = root + '/portrait.jpg'
subprocess.run(['ffmpeg', '-loglevel', 'error', '-y', '-f', 'lavfi', '-i', 'testsrc2=size=600x800:rate=1', '-frames:v', '1', PORTRAIT], check=True)
LOGO = root + '/logo.png'
subprocess.run(['ffmpeg', '-loglevel', 'error', '-y', '-f', 'lavfi', '-i', 'color=c=0x2266cc:size=400x220,drawbox=x=40:y=40:w=320:h=140:color=white@0.9:t=fill', '-frames:v', '1', LOGO], check=True)
COVER = root + '/cover.jpg'
subprocess.run(['ffmpeg', '-loglevel', 'error', '-y', '-f', 'lavfi', '-i', 'mandelbrot=size=600x600:rate=1', '-frames:v', '1', COVER], check=True)
BIO = ('Prince Rogers Nelson was an American singer, songwriter, musician and record producer. Known for his flamboyant stage presence '
       'and wide vocal range, he is regarded as one of the greatest musicians of his generation, and sold over 150 million records.')
CHANNEL = {'name': 'Ray TV News', 'url': 'https://tv.example/ray.m3u8', 'urlToResolve': 'https://tv.example/ray.m3u8', 'favicon': 'https://covers.example/logo.png', 'videoChannel': True}
PODCAST = {'type': 'podcast', 'guid': 'ep-1', 'name': 'Episode 12: The Purple Years', 'collectionName': 'Funk History Hour', 'artistName': 'Radio Co',
           'favicon': 'https://covers.example/cover.jpg', 'episodeUrl': 'https://pod.example/ep12.mp3',
           'description': '<p>We look back at <b>1984</b> and the making of a classic album.</p><p>Plus listener mail, a deep cut and what came next for the band.</p><p>Third paragraph that should be cut off by the two line limit on a phone.</p>'}
MOVIE = {'type': 'video', 'videoKind': 'movie', 'id': 'v:heat', 'name': 'Heat', 'title': 'Heat', 'year': '1995', 'duration': 10200, 'uri': 'https://v.example/heat.mkv',
         'favicon': 'https://covers.example/cover.jpg', 'summary': 'A group of high-end professional thieves start to feel the heat from the LAPD when they unknowingly leave a clue at their latest heist. A long second sentence to fill a third line.'}

async def files_route(route):
    u = urlparse(route.request.url)
    if u.hostname == '127.0.0.1': return await route.continue_()
    if u.hostname == 'i.ytimg.com':
        return await route.fulfill(path=root + '/cover.jpg', headers={'Access-Control-Allow-Origin': '*'})
    if u.hostname == 'covers.example':
        f = root + u.path
        if os.path.exists(f):
            return await route.fulfill(path=f, headers={'Access-Control-Allow-Origin': '*'})
    return await route.abort()

async def run(theme, b):
    ctx = await b.new_context(viewport={'width': 412, 'height': 900}, device_scale_factor=2, is_mobile=True, has_touch=True, color_scheme=theme)
    await ctx.add_init_script(MOCK)
    await ctx.add_init_script("try{ localStorage.setItem('radioPlayerTheme', %s); }catch(e){}" % json.dumps(theme))
    pg = await ctx.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
    await pg.route('**/*', files_route)
    await pg.goto(f'http://127.0.0.1:{PORT}/index.html'); await pg.wait_for_timeout(2500)
    await pg.evaluate("""(function(){ var ov=document.getElementById('addMusicOverlay'); if(ov) ov.classList.add('open');
      var btn=document.getElementById('addMusicFolderBtn'); btn.disabled=false; btn.click(); })()""")
    for _ in range(90):
        await pg.wait_for_timeout(500)
        if await pg.evaluate("__d.n()") >= len(SONGS): break
    await pg.evaluate("document.getElementById('addMusicOverlay').classList.remove('open')")
    await pg.evaluate("try{ document.getElementById('statusLineDismiss').click(); }catch(e){}")
    await pg.evaluate('__d.home()'); await pg.wait_for_timeout(600)
    h = await pg.evaluate('__h.hero()')
    check(not h['shown'], f'[{theme}] nothing ever played: no hero')
    # a library song
    await pg.evaluate(f"__h.meta('Prince', {json.dumps(BIO)})")
    await pg.evaluate("__h.cover('Prince 03', 'https://covers.example/portrait.jpg')")
    await pg.evaluate("__h.play('Prince 03')"); await pg.wait_for_timeout(1500)
    await pg.evaluate('__d.home()'); await pg.wait_for_timeout(1200)
    h = await pg.evaluate('__h.hero()'); print(h)
    check(h['shown'] and h['left'] == 0 and h['right'] == h['vw'], f'[{theme}] the hero runs edge to edge across the top of Home')
    await pg.evaluate('__h.clearStatus()'); await pg.wait_for_timeout(600)
    gap = await pg.evaluate("(()=>{ var s = document.getElementById('statusLine'); if(s.classList.contains('has-message')) return null; return Math.round(document.getElementById('npHero').getBoundingClientRect().top - document.querySelector('.sidebar-top').getBoundingClientRect().bottom); })()")
    check(gap is None or gap == 0, f'[{theme}] and starts right under the header (gap {gap}px)')
    check(h['first'] in ('favoritesSection', 'recentSection') or 'section' in h['first'], f'[{theme}] above the Home rows (next: {h["first"]})')
    check(h['kicker'] == 'Artist' and h['title'] == 'Prince', f'[{theme}] a library song shows the artist ({h["kicker"]} / {h["title"]})')
    check(h['desc'].startswith('Prince Rogers Nelson') and h['descLines'] == 2, f'[{theme}] with two lines of the bio ({h["descLines"]} lines)')
    check('portrait.jpg' in h['img'], f'[{theme}] and the song\'s own cover (build 221) {h["img"][:60]}')
    check(h['imgW'] == h['vw'] and h['imgTop'] == 0 and h['objPos'].endswith('0%'), f'[{theme}] the cover runs full width from the top {h["imgW"]} {h["imgTop"]} {h["objPos"]}')
    check(h['mediaH'] <= 330, f'[{theme}] half the old height ({h["mediaH"]}px; was {round(min(412 * 1.12, 500))})')
    check(h['gap'] is not None and h['gap'] >= 40, f'[{theme}] with room below it ({h["gap"]}px)')
    check(h['headFs'] == 19 and h['titleFs'] >= 32, f'[{theme}] Home headings are smaller ({h["headFs"]}px) than the hero title ({h["titleFs"]}px)')
    check(h['playRight'] > h['vw'] - 60 and h['bottom'] - h['playBottom'] < 40, f'[{theme}] the Play button sits at the bottom right')
    await pg.evaluate("window.scrollTo(0,0)"); await pg.wait_for_timeout(300)
    await pg.screenshot(path=f'{shots}/hero-artist-{theme}.png')
    # Play: every Prince song shuffled, starting with this one, which keeps playing
    await pg.evaluate("__h.el('.nph-play').click()"); await pg.wait_for_timeout(800)
    q = await pg.evaluate('__d.q()')
    order = await pg.evaluate("playQueue.map(function(t){ return t.name; })") if False else None
    check(q['label'] == 'Prince Shuffle' and q['n'] == 20 and q['cur'] == 'Prince 03', f'[{theme}] Play starts a shuffle of all 20 Prince songs from the current one {q}')
    h = await pg.evaluate('__h.hero()')
    check(h['play'] == 'pause', f'[{theme}] and the button then shows Pause')
    await pg.evaluate("__h.el('.nph-play').click()"); await pg.wait_for_timeout(400)
    check((await pg.evaluate('__h.hero()'))['play'] == 'play', f'[{theme}] which pauses it')
    await pg.evaluate("__h.el('.nph-play').click()"); await pg.wait_for_timeout(400)
    # anywhere else opens the artist
    await pg.evaluate("__h.el('.nph-desc').click()"); await pg.wait_for_timeout(900)
    check(await pg.evaluate("document.body.classList.contains('artist-open') && document.getElementById('artistHeroName').textContent") == 'Prince', f'[{theme}] tapping the hero opens the artist page')
    check(not (await pg.evaluate('__h.hero()'))['shown'], f'[{theme}] the hero shows on Home only')
    await pg.evaluate("document.getElementById('detailBackBtn').click()"); await pg.wait_for_timeout(800)
    check((await pg.evaluate('__h.hero()'))['shown'], f'[{theme}] back on Home it is there')
    # follows playback: a channel
    await pg.evaluate(f"__h.fake({json.dumps(CHANNEL)})"); await pg.wait_for_timeout(1200)
    h = await pg.evaluate('__h.hero()'); print(h)
    check(h['kicker'] == 'Live TV' and h['title'] == 'Ray TV News' and 'logo.png' in h['img'] and h['imgW'] == h['vw'], f'[{theme}] a channel shows its logo, full width, and name')
    check(h['play'] == 'pause', f'[{theme}] its button follows playback')
    await pg.evaluate("window.scrollTo(0,0)"); await pg.wait_for_timeout(300)
    await pg.screenshot(path=f'{shots}/hero-channel-{theme}.png')
    await pg.evaluate("__h.playing(false)"); await pg.wait_for_timeout(200)
    check((await pg.evaluate('__h.hero()'))['play'] == 'play', f'[{theme}] Play when it is paused')
    # a podcast
    await pg.evaluate(f"__h.fake({json.dumps(PODCAST)})"); await pg.wait_for_timeout(1200)
    h = await pg.evaluate('__h.hero()'); print(h)
    check(h['kicker'] == 'Podcast' and h['title'] == 'Funk History Hour' and h['line'] == 'Episode 12: The Purple Years', f'[{theme}] a podcast shows the show and the episode')
    check(h['desc'].startswith('We look back at 1984') and '<' not in h['desc'] and h['descLines'] == 2, f'[{theme}] with two lines of its notes, tags removed')
    await pg.evaluate("window.scrollTo(0,0)"); await pg.wait_for_timeout(300)
    await pg.screenshot(path=f'{shots}/hero-podcast-{theme}.png')
    # Play on a playing podcast pauses (resume = the same item, togglePlayPause)
    await pg.evaluate("window.__tp = 0")
    await pg.evaluate("__h.el('.nph-play').click()"); await pg.wait_for_timeout(300)
    check(await pg.evaluate('window.__tp') == 1 and (await pg.evaluate('__h.hero()'))['play'] == 'play', f'[{theme}] the podcast\'s button pauses and resumes it')
    # a movie
    await pg.evaluate(f"__h.fake({json.dumps(MOVIE)})"); await pg.wait_for_timeout(1200)
    h = await pg.evaluate('__h.hero()'); print(h)
    check(h['kicker'] == 'Movie' and h['title'] == 'Heat' and h['line'].startswith('1995') and h['descLines'] == 2, f'[{theme}] a movie shows its name, year and details')
    await pg.evaluate("window.scrollTo(0,0)"); await pg.wait_for_timeout(300)
    await pg.screenshot(path=f'{shots}/hero-movie-{theme}.png')
    # tapping a non-song hero doesn't navigate
    await pg.evaluate("__h.el('.nph-title').click()"); await pg.wait_for_timeout(400)
    check((await pg.evaluate('__h.hero()'))['shown'], f'[{theme}] tapping a movie hero stays on Home')
    # build 222: swipe through what was played
    t = await pg.evaluate('__h.titles()'); print(t)
    check(t[:4] == ['Heat', 'Funk History Hour', 'Ray TV News', 'Prince'] and await pg.evaluate('__h.idx()') == 0, f'[{theme}] the slides are what is playing, then what was played, newest first {t[:5]}')
    d = await pg.evaluate('__h.bar()')
    n = len(t)
    check(d['shown'] and d['w'] == 78 and d['h'] == 6 and d['knobs'] == 1 and abs(d['fill'] - 1 / n) < .02, f'[{theme}] a thin 78x6 progress bar (where the dots were), no knob, filled 1/{n} {d}')
    await pg.evaluate('__h.go(2)'); await pg.wait_for_timeout(600)
    h = await pg.evaluate('__h.hero()')
    check(await pg.evaluate('__h.idx()') == 2 and h['title'] == 'Ray TV News' and 'logo.png' in h['img'] and abs((await pg.evaluate('__h.bar()'))['fill'] - 3 / n) < .02,
          f'[{theme}] swiping shows the next one, picture and all {h["title"]}')
    await pg.screenshot(path=f'{shots}/hero-swipe-{theme}.png')
    gaps = await pg.evaluate("__h.gaps()")
    check(max(gaps) - min(gaps) <= 2 and max(gaps) < 40, f'[{theme}] every slide\'s Play button sits the same short way above the bar {gaps}')
    # a drag (mouse) pages one slide on
    box = await pg.evaluate("(()=>{ var r = document.getElementById('npHeroTrack').getBoundingClientRect(); return [r.left + r.width * .7, r.top + 80]; })()")
    await pg.mouse.move(box[0], box[1]); await pg.mouse.down(); await pg.mouse.move(box[0] - 150, box[1], steps=8); await pg.mouse.up(); await pg.wait_for_timeout(900)
    check(await pg.evaluate('__h.idx()') == 3 and (await pg.evaluate('__h.hero()'))['title'] == 'Prince', f'[{theme}] a drag pages to the next slide ({await pg.evaluate("__h.idx()")})')
    check(not await pg.evaluate("document.body.classList.contains('artist-open')"), f'[{theme}] and the drag doesn\'t count as a tap')
    # something new plays while looking back: the slide stays put
    await pg.evaluate("__h.fake({ name: 'KISS FM', url: 'https://radio.example/kiss', urlToResolve: 'https://radio.example/kiss', favicon: 'https://covers.example/logo.png', stationuuid: 'kiss-1' })"); await pg.wait_for_timeout(700)
    tt = await pg.evaluate('__h.titles()')
    # (the test's movie isn't in a real video library, so it drops out of the history)
    check((await pg.evaluate('__h.hero()'))['title'] == 'Prince' and await pg.evaluate('__h.idx()') == tt.index('Prince') and tt[0] == 'KISS FM',
          f'[{theme}] a new track while looking back leaves that slide on screen (the new one goes first)')
    # on the first slide, the new track shows
    await pg.evaluate('__h.go(0)'); await pg.wait_for_timeout(600)
    await pg.evaluate("__h.fake({ name: 'Jazz 24', url: 'https://radio.example/jazz', urlToResolve: 'https://radio.example/jazz', favicon: 'https://covers.example/cover.jpg', stationuuid: 'jazz-1' })"); await pg.wait_for_timeout(700)
    h = await pg.evaluate('__h.hero()')
    check(h['title'] == 'Jazz 24' and h['kicker'] == 'Station' and await pg.evaluate('__h.idx()') == 0, f'[{theme}] on the first slide, the new track takes its place')
    # build 223: the song a station names shows under its name, and stays once it's gone
    check(h['line'] == '', f'[{theme}] a station that hasn\'t named a song has no song line')
    await pg.evaluate("__h.onair('Take Five', 'Dave Brubeck')"); await pg.wait_for_timeout(300)
    check((await pg.evaluate('__h.hero()'))['line'] == 'Take Five \u00b7 Dave Brubeck', f'[{theme}] the song on air shows under the station name')
    await pg.screenshot(path=f'{shots}/hero-station-song-{theme}.png')
    await pg.evaluate("__h.onair('Blue Rondo', 'Dave Brubeck')"); await pg.wait_for_timeout(300)
    await pg.evaluate("__h.fake({ name: 'KISS FM', url: 'https://radio.example/kiss', urlToResolve: 'https://radio.example/kiss', favicon: 'https://covers.example/logo.png', stationuuid: 'kiss-1' })"); await pg.wait_for_timeout(700)
    check(await pg.evaluate("__h.slideLine('Jazz 24')") == 'Blue Rondo \u00b7 Dave Brubeck', f'[{theme}] and the latest one stays on its slide after switching away')
    # tapping a station's cover plays it
    await pg.evaluate("__h.tapSlide('Jazz 24')"); await pg.wait_for_timeout(900)
    check(await pg.evaluate('__h.cur()') == 'Jazz 24', f'[{theme}] tapping a station\'s cover plays it ({await pg.evaluate("__h.cur()")})')
    check(not await pg.evaluate("document.body.classList.contains('artist-open')"), f'[{theme}] (and goes nowhere)')
    await pg.evaluate('__h.go(0)'); await pg.wait_for_timeout(400)
    # Play on an older song slide: the artist shuffle from that song
    ti = await pg.evaluate('__h.titles()'); pi = ti.index('Prince')
    await pg.evaluate(f'__h.go({pi})'); await pg.wait_for_timeout(600)
    await pg.evaluate("__h.el('.nph-play').click()"); await pg.wait_for_timeout(1000)
    q = await pg.evaluate('__d.q()')
    check(q['label'] == 'Prince Shuffle' and q['cur'] == 'Prince 03', f'[{theme}] Play on an older song starts the artist shuffle from that song {q}')
    check(await pg.evaluate('__h.idx()') == 0 and (await pg.evaluate('__h.hero()'))['title'] == 'Prince', f'[{theme}] and it is now the first slide, still on screen')
    n_before = await pg.evaluate('__h.n()')
    await pg.reload(); await pg.wait_for_timeout(3000)
    await pg.evaluate('__d.home()'); await pg.wait_for_timeout(800)
    check(await pg.evaluate('__h.n()') == n_before and (await pg.evaluate('__h.titles()'))[0] == 'Prince', f'[{theme}] the slides come back after a restart')
    check(await pg.evaluate("__h.slideLine('Jazz 24')") == 'Blue Rondo \u00b7 Dave Brubeck', f'[{theme}] with each station\'s last song')
    # build 223: a music file opened from another app
    libn = await pg.evaluate('__h.inLib()')
    await pg.evaluate('__h.stub()')
    await pg.evaluate(f"""__fireOpen({{ url: 'http://127.0.0.1:{PORT}/Music/001.mp3', name: 'My Download.mp3', title: 'Opened Song', artist: 'Some Band', album: 'Loose Files', duration: 1, size: 9999, seq: 1, art: '/data/user/0/x/cache/opened/a1.img' }})""")
    await pg.wait_for_timeout(1500)
    check(await pg.evaluate('__h.cur()') == 'Opened Song' and await pg.evaluate('__h.npOpen()'), f'[{theme}] an opened music file plays with its own tags, Now Playing open ({await pg.evaluate("__h.cur()")})')
    check(await pg.evaluate('__h.inLib()') == libn, f'[{theme}] without joining the library')
    check('a1.img' in await pg.evaluate('__h.curArt()'), f'[{theme}] its embedded cover is used')
    await pg.evaluate("__d.closeNp()")
    await pg.evaluate(f"""__fireOpen({{ url: 'http://127.0.0.1:{PORT}/Music/002.mp3', name: 'Artist Two - Untagged Tune.mp3', size: 8888, seq: 2 }})""")
    await pg.wait_for_timeout(1500)
    check(await pg.evaluate('__h.cur()') == 'Untagged Tune', f'[{theme}] an untagged file is named from its file name ({await pg.evaluate("__h.cur()")})')
    await pg.evaluate("__fireOpen({ error: \"Couldn't open that file.\", name: 'bad.mp3' })"); await pg.wait_for_timeout(400)
    check(await pg.evaluate('__h.cur()') == 'Untagged Tune', f'[{theme}] a file that couldn\'t be read leaves playback alone')
    await pg.evaluate("__d.closeNp()"); await pg.evaluate('__d.home()'); await pg.wait_for_timeout(500)
    # build 225: removing from Continue Listening / Continue Watching takes it off the slides
    t0 = await pg.evaluate('__h.titles()'); print(t0)
    check('KISS FM' in t0 and 'Ray TV News' in t0, f'[{theme}] (KISS FM and Ray TV News are slides)')
    await pg.evaluate("__h.rmRecent('KISS FM')"); await pg.wait_for_timeout(300)
    check('KISS FM' not in await pg.evaluate('__h.titles()'), f'[{theme}] removed from Continue Listening: gone from the slides')
    await pg.evaluate("__h.rmChannel('https://tv.example/ray.m3u8')"); await pg.wait_for_timeout(300)
    check('Ray TV News' not in await pg.evaluate('__h.titles()'), f'[{theme}] removed from Continue Watching: gone from the slides')
    await pg.reload(); await pg.wait_for_timeout(3000); await pg.evaluate('__d.home()'); await pg.wait_for_timeout(600)
    tr = await pg.evaluate('__h.titles()')
    check('KISS FM' not in tr and 'Ray TV News' not in tr, f'[{theme}] and they stay gone after a restart')
    # Top 100: a preview goes to Continue Listening and the slides; a music video to Continue Watching and the slides
    CH1 = {'type': 'chartsong', 'name': 'Golden Hour', 'artist': 'JVKE', 'songKey': 'jvke|golden hour', 'rank': 7, 'chartDate': '2026-10-10', 'favicon': 'https://covers.example/cover.jpg'}
    CH2 = {'type': 'chartsong', 'name': 'Flowers', 'artist': 'Miley Cyrus', 'songKey': 'miley cyrus|flowers', 'rank': 3, 'chartDate': '2026-10-10'}
    await pg.evaluate(f"__h.chartPreview({json.dumps(CH1)})"); await pg.wait_for_timeout(700)
    h = await pg.evaluate('__h.hero()')
    check('Golden Hour' in await pg.evaluate('__h.recents()'), f'[{theme}] a Top 100 preview is kept in Continue Listening')
    check(h['title'] == 'Golden Hour' and h['kicker'] == 'Top 100' and h['line'] == 'JVKE', f'[{theme}] and is the first slide {h["kicker"]} {h["title"]}')
    await pg.evaluate(f"__h.chartVideo({json.dumps(CH2)}, 'flwrsVid001')"); await pg.wait_for_timeout(500)
    cw = await pg.evaluate('__h.cw()'); print(cw)
    await pg.evaluate("document.getElementById('continueWatchingHomeSection').scrollIntoView({block:'center'})"); await pg.wait_for_timeout(500)
    await pg.screenshot(path=f'{shots}/cw-chart-{theme}.png')
    check(any(n == 'Flowers' and 'flwrsVid001' in src for n, src in cw), f'[{theme}] a Top 100 music video is kept in Continue Watching with its video still')
    check('Flowers' in await pg.evaluate('__h.titles()'), f'[{theme}] and among the slides')
    await pg.evaluate(f"__h.rmChart({json.dumps(CH2)})"); await pg.wait_for_timeout(300)
    check(not any(n == 'Flowers' for n, _ in await pg.evaluate('__h.cw()')) and 'Flowers' not in await pg.evaluate('__h.titles()'), f'[{theme}] removing it from Continue Watching takes it off both')
    await pg.evaluate("__h.rmRecent('Golden Hour')"); await pg.wait_for_timeout(300)
    check('Golden Hour' not in await pg.evaluate('__h.recents()') and (await pg.evaluate('__h.titles()')).count('Golden Hour') <= 1,
          f'[{theme}] removing the preview from Continue Listening leaves only the now-playing slide')
    # bigger text at 360 wide still fits
    await pg.set_viewport_size({'width': 360, 'height': 800})
    await pg.evaluate(f"__h.meta('Prince', {json.dumps(BIO)})")
    await pg.evaluate("__h.play('Prince 05')"); await pg.wait_for_timeout(1200)
    await pg.evaluate("""(()=>{ var st = document.createElement('style'); st.textContent = '.nph-title{ font-size:calc(1.3 * clamp(28px, 8vw, 40px)) !important } .nph-desc{ font-size:18.2px !important } .nph-kicker{ font-size:15px !important }'; document.head.appendChild(st); window.scrollTo(0,0); })()""")
    await pg.wait_for_timeout(400)
    h = await pg.evaluate('__h.hero()')
    check(h['descLines'] == 2 and h['playRight'] <= 360, f'[{theme}] with 30% larger text at 360 wide: two lines of bio, button on screen')
    await pg.screenshot(path=f'{shots}/hero-artist-big-{theme}.png')
    check(not errs, f'[{theme}] no page errors {errs[:3]}')
    await ctx.close()

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
        for theme in ('dark', 'light'):
            await run(theme, b)
        await b.close()
    print('ALL PASSED' if not fails else f'FAILED {fails}')
    sys.exit(1 if fails else 0)

asyncio.run(main())
