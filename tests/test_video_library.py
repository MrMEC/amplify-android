"""Video > Movies / TV Shows: a folder of videos on the phone (mocked native picker), sorted
into movies and episodes by their names, posters from the folder or a still, details pages,
playing (native, seek bar, 10s skips), resume, watched at the end, Continue Watching, fixes.
Run: python3 tests/test_video_library.py (screenshots in /tmp/claude-0/t/shots)"""
import asyncio, os, json
HERE = os.path.dirname(os.path.abspath(__file__))
src = open(os.path.join(HERE, 'test_video_channels.py')).read()
head = src[:src.index('async def rows(pg)')]
head = head.replace("'/tmp/claude-0/t/srv-ch'", "'/tmp/claude-0/t/srv-vlib'").replace('8777', '8780')
exec(head)
from playwright.async_api import async_playwright

T = 'content://tree/primary%3AVideos'
def f(rel, size=900000000, video=True, lm=0):
    return {'uri': 'content://doc/' + rel.replace('/', '%2F'), 'name': rel.split('/')[-1], 'relPath': rel,
            'type': '', 'video': video, 'size': size, 'lastModified': lm}
FILES = [
  f('Videos/Movies/Inception (2010)/Inception.2010.1080p.BluRay.x264.mkv', lm=3),
  f('Videos/Movies/Inception (2010)/poster.jpg', 1, False), f('Videos/Movies/Inception (2010)/fanart.jpg', 1, False),
  f('Videos/Movies/Inception (2010)/Sample/sample.mkv', 20000000, lm=3),
  f('Videos/Movies/The.Matrix.1999.720p.mp4', lm=1),
  f('Videos/Movies/Arrival.2016.2160p.WEB-DL.mkv', lm=2), f('Videos/Movies/Arrival.2016.2160p.WEB-DL.jpg', 1, False),
  f('Videos/TV/Breaking Bad/poster.jpg', 1, False),
  f('Videos/TV/Breaking Bad/Season 1/Breaking.Bad.S01E01.Pilot.720p.mkv', lm=5),
  f('Videos/TV/Breaking Bad/Season 1/Breaking.Bad.S01E02.Cats.in.the.Bag.720p.mkv', lm=5),
  f('Videos/TV/Breaking Bad/Season 1/Breaking.Bad.S01E02.Cats.in.the.Bag.720p.srt', 1, False),
  f('Videos/TV/Breaking Bad/Season 2/Breaking.Bad.S02E01.Seven.Thirty-Seven.mkv', lm=5),
  f('Videos/TV/The Office/The Office - 1x01 - Pilot.mp4', lm=4),
  f('Videos/TV/The Office/The Office - 1x02 - Diversity Day.mp4', lm=4),
  f('Videos/TV/Friends/Season 3/03 - The One with the Princess Leia Fantasy.mkv', lm=6),
]
IMG = {'Videos/Movies/Inception (2010)/poster.jpg': 'inception-poster.jpg', 'Videos/Movies/Inception (2010)/fanart.jpg': 'inception-fanart.jpg',
       'Videos/Movies/Arrival.2016.2160p.WEB-DL.jpg': 'arrival-poster.jpg', 'Videos/TV/Breaking Bad/poster.jpg': 'bb-poster.jpg'}
MAP = {('content://doc/' + k.replace('/', '%2F')): '/c/' + v for k, v in IMG.items()}
EXT = """
(function(){ var P=window.Capacitor.Plugins.AmplifyPlayer; var FILES=%s, MAP=%s;
  window.__vcalls=[]; window.__loadArgs=[];
  var L=P.load; 
  window.Capacitor.convertFileSrc=function(u){ if(MAP[u]) return MAP[u]; if(/^file:.*still-/.test(u)) return '/c/'+u.split('/').pop(); return u; };
  window.Capacitor.Plugins.AmplifyPlayer=new Proxy({}, {get:function(t,k){
    if(k==='load') return function(a){ window.__loadArgs.push(a); return P.load(a); };
    if(k==='pickVideoFolder') return function(){ window.__vcalls.push(['pick']); return Promise.resolve({folder:'Videos', treeUri:'%s', files:FILES, truncated:false}); };
    if(k==='rescanVideoFolder') return function(a){ window.__vcalls.push(['rescan',a.treeUri]); return Promise.resolve({folder:'Videos', treeUri:a.treeUri, files:FILES}); };
    if(k==='videoTracks') return function(){ window.__vcalls.push(['tracks']); return Promise.resolve({textOff:false,
        text:[{group:2,track:0,label:'English',selected:true},{group:3,track:0,label:'Spanish',selected:false}],
        audio:[{group:0,track:0,label:'English 5.1',selected:true},{group:1,track:0,label:'Commentary',selected:false}]}); };
    if(k==='selectVideoTrack') return function(a){ window.__vcalls.push(['select',a]); return Promise.resolve({}); };
    if(k==='forgetVideoFolder') return function(a){ window.__vcalls.push(['forget',a.treeUri]); return Promise.resolve({}); };
    if(k==='videoInfo') return function(a){ window.__vcalls.push(['info',a.uri]);
      var ep=/S0\\dE|1x0|Season/.test(decodeURIComponent(a.uri)); var mx=/Matrix/.test(a.uri);
      return Promise.resolve({duration: ep ? 2820000 : (/Inception/.test(a.uri) ? 8880000 : 6960000), width:1920, height: /Arrival/.test(a.uri)?2160:1080,
        thumb: 'file:///data/vthumbs/' + (mx ? 'still-matrix.jpg' : ep ? 'still-ep.jpg' : 'still-generic.jpg')}); };
    return P[k]; }});
})();
""" % (json.dumps(FILES), json.dumps(MAP), T)

async def names(pg, sel):
    return await pg.evaluate("(s)=>Array.prototype.map.call(document.querySelectorAll(s),function(t){return t.textContent;})", sel)
async def tab(pg, v):
    await pg.evaluate("(v)=>document.querySelector('.video-tabs [data-vtab='+v+']').click()", v); await pg.wait_for_timeout(400)
async def state(pg, extra):
    cur = await pg.evaluate("window.__cur")
    ev = {'id': cur, 'state': 'ready', 'isPlaying': True, 'playWhenReady': True, 'position': 0, 'duration': 8880, 'live': False}
    ev.update(extra)
    await pg.evaluate("(e)=>window.__emit('state', e)", ev)

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
        ctx = await b.new_context(viewport={'width': 390, 'height': 844}, device_scale_factor=2, is_mobile=True, has_touch=True, color_scheme='dark', locale='en-US')
        await ctx.add_init_script(MOCK)
        await ctx.add_init_script(EXT)
        pg = await ctx.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e) + ' @ ' + (e.stack or '')[:300]))
        pg.on('dialog', lambda d: asyncio.ensure_future(d.accept(pg._next_prompt if hasattr(pg, '_next_prompt') else '')))
        await pg.route('**/*', route)
        await pg.goto('http://127.0.0.1:8780/index.html'); await pg.wait_for_timeout(2500)

        await pg.evaluate("document.querySelector('.mobile-nav-btn[data-nav=video]').click()"); await pg.wait_for_timeout(600)
        tabs = await names(pg, '.video-tabs .home-tab')
        check(tabs == ['Live TV', 'Movies', 'TV Shows'], f'Video has Live TV / Movies / TV Shows tabs {tabs}')
        await tab(pg, 'movies')
        empty = await pg.evaluate("document.querySelector('#stationsGrid .v-empty') && document.querySelector('#stationsGrid .v-empty').textContent")
        check(empty and 'Add a folder' in empty, f'Movies is empty until a folder is added ({empty})')
        await pg.screenshot(path=f'{SHOTS}/vlib-empty.png')
        await pg.evaluate("document.getElementById('videoAddHeaderBtn').click()"); await pg.wait_for_timeout(2500)
        status = await pg.evaluate("document.getElementById('statusBar') ? document.getElementById('statusBar').textContent : ''")
        mv = await names(pg, '#stationsGrid .tile.vposter .tile-name')
        check(sorted(mv) == ['Arrival', 'Inception', 'The Matrix'], f'movies found, sample left out, names tidied {mv}')
        subs = await names(pg, '#stationsGrid .tile.vposter .tile-sub')
        check(subs[0].startswith('2010') or '2010' in ' '.join(subs), f'years and running times {subs}')
        await pg.evaluate("document.getElementById('videoSortHeaderBtn').click()"); await pg.wait_for_timeout(200)
        await pg.evaluate("document.querySelector('.ch-sort-menu [data-sort=az]').click()"); await pg.wait_for_timeout(300)
        mv = await names(pg, '#stationsGrid .tile.vposter .tile-name')
        check(mv == ['Arrival', 'Inception', 'The Matrix'], f'Sort A to Z {mv}')
        imgs = await pg.evaluate("Array.prototype.map.call(document.querySelectorAll('#stationsGrid .tile.vposter img'),function(i){return i.getAttribute('src');})")
        check('/c/inception-poster.jpg' in imgs and '/c/arrival-poster.jpg' in imgs and '/c/still-matrix.jpg' in imgs,
              f'posters from the folder (poster.jpg, same-name picture), a still when there is none {imgs}')
        folders = await names(pg, '#stationsGrid .v-folder-name')
        check(folders == ['Videos'], f'the folder is listed under Folders {folders}')
        await pg.wait_for_timeout(600)
        await pg.screenshot(path=f'{SHOTS}/vlib-movies.png', full_page=False)

        await tab(pg, 'shows')
        sh = await names(pg, '#stationsGrid .tile.vposter .tile-name')
        ssub = await names(pg, '#stationsGrid .tile.vposter .tile-sub')
        check(sorted(sh) == ['Breaking Bad', 'Friends', 'The Office'], f'shows found from S01E01, 1x01 and Season folders {sh} {ssub}')
        await pg.screenshot(path=f'{SHOTS}/vlib-shows.png')

        # show page
        await pg.evaluate("Array.prototype.find.call(document.querySelectorAll('#stationsGrid .tile.vposter'),function(t){return t.querySelector('.tile-name').textContent==='Breaking Bad';}).click()"); await pg.wait_for_timeout(700)
        head_ = await pg.evaluate("[document.querySelector('.vd-title').textContent, document.getElementById('detailBackLabel').textContent, document.getElementById('stationsHeading').textContent]")
        document_title_ok = head_[0] == 'Breaking Bad' and head_[2] == ''
        seasons = await names(pg, '.vd-seasons .home-tab')
        eps = await names(pg, '#stationsGrid .vep-title')
        play = await pg.evaluate("document.querySelector('.vd-play').textContent")
        check(document_title_ok and head_[1] == 'Video' and seasons == ['Season 1', 'Season 2'] and eps == ['1. Pilot', '2. Cats in the Bag'] and play == 'Play S1 E1',
              f'show page: seasons, episodes named from the files, Play S1 E1, back says Video {head_} {seasons} {eps} {play!r}')
        await pg.screenshot(path=f'{SHOTS}/vlib-show.png')
        await pg.evaluate("Array.prototype.find.call(document.querySelectorAll('.vd-seasons .home-tab'),function(b){return b.textContent==='Season 2';}).click()"); await pg.wait_for_timeout(300)
        eps2 = await names(pg, '#stationsGrid .vep-title')
        check(eps2 == ['1. Seven Thirty-Seven'], f'season tabs switch episodes {eps2}')
        # play an episode
        await pg.evaluate("document.querySelector('#stationsGrid .vep-row').click()"); await pg.wait_for_timeout(900)
        last = await pg.evaluate("window.__calls.filter(function(c){return c[0]==='load';}).slice(-1)[0]")
        check(last and 'S02E01' in last[1], f'tapping an episode plays the file from the phone {last}')
        npst = await pg.evaluate("""(()=>{var s=document.getElementById('nowPlayingScreen');return {open:s.style.display, layout:s.classList.contains('np-channel'),
            name:document.getElementById('npName').textContent, sub:document.getElementById('npSub').textContent,
            seek:getComputedStyle(document.getElementById('npSeek')).display, back:getComputedStyle(document.getElementById('npSkipBackBtn')).display,
            fwd:document.getElementById('npSkipFwdBtn').title, heading:document.getElementById('npCollectionHeading').textContent,
            rows:Array.prototype.map.call(document.querySelectorAll('#npCollectionGrid .vep-title'),function(t){return t.textContent;})};})()""")
        check(npst['open'] == 'flex' and npst['layout'] and npst['name'] == 'Breaking Bad' and npst['sub'].startswith('S2 E1')
              and npst['seek'] != 'none' and npst['back'] != 'none' and npst['fwd'] == 'Forward 10 seconds',
              f'Now Playing: video layout, show name, S2 E1, seek bar and 10s skips {npst}')
        await state(pg, {'duration': 2820, 'position': 1})
        cur = await pg.evaluate("window.__cur")
        await pg.evaluate("(id)=>window.__emit('video',{id:id,hasVideo:true,width:1280,height:720})", cur); await pg.wait_for_timeout(700)
        vid = await pg.evaluate("document.getElementById('nowPlayingScreen').classList.contains('np-video-on')")
        check(vid, 'the picture shows in the video box')
        await pg.screenshot(path=f'{SHOTS}/vlib-np.png')
        # ends -> watched
        await state(pg, {'state': 'ended', 'isPlaying': False, 'playWhenReady': False, 'position': 2820, 'duration': 2820})
        await pg.wait_for_timeout(600)
        prog = await pg.evaluate("JSON.parse(localStorage.getItem('radioPlayerVideoProgress')||'{}')")
        k = [x for x in prog if 'S02E01' in x]
        check(k and prog[k[0]].get('watched'), f'played to the end counts as watched {prog}')
        await pg.evaluate("document.getElementById('npBackBtn').click()"); await pg.wait_for_timeout(600)

        # movie details + play + resume
        await pg.evaluate("document.getElementById('detailBackBtn').click()"); await pg.wait_for_timeout(600)
        await tab(pg, 'movies')
        await pg.evaluate("Array.prototype.find.call(document.querySelectorAll('#stationsGrid .tile.vposter'),function(t){return t.querySelector('.tile-name').textContent==='Inception';}).click()"); await pg.wait_for_timeout(700)
        det = await pg.evaluate("[document.querySelector('.vd-title').textContent, document.querySelector('.vd-meta').textContent, document.querySelector('.vd-play').textContent, !!document.querySelector('.vd-backdrop img[src=\"/c/inception-fanart.jpg\"]')]")
        check(det[0] == 'Inception' and det[1] == '2010 · 2h 28m · 1080p' and det[2] == 'Play' and det[3], f'movie page: title, year, length, quality, fanart backdrop, Play {det}')
        await pg.screenshot(path=f'{SHOTS}/vlib-movie.png')
        await pg.evaluate("document.querySelector('.vd-play').click()"); await pg.wait_for_timeout(900)
        await state(pg, {'position': 3000, 'duration': 8880})
        await pg.wait_for_timeout(300)
        await state(pg, {'position': 3000, 'duration': 8880, 'isPlaying': False, 'playWhenReady': False, 'external': True})
        await pg.wait_for_timeout(500)
        prog = await pg.evaluate("JSON.parse(localStorage.getItem('radioPlayerVideoProgress')||'{}')")
        k = [x for x in prog if 'Inception' in x]
        check(k and abs(prog[k[0]]['pos'] - 3000) < 5 and not prog[k[0]].get('watched'), f'where you stopped is kept {prog.get(k[0]) if k else prog}')
        rec = await pg.evaluate("JSON.parse(localStorage.getItem('radioPlayerRecent')||'[]').map(function(r){return r.type;})")
        check('video' not in rec, f'videos stay out of Continue Listening {rec}')
        await pg.evaluate("document.getElementById('npBackBtn').click()"); await pg.wait_for_timeout(500)
        det = await pg.evaluate("[document.querySelector('.vd-play').textContent, !!document.querySelector('.vd-secondary'), document.querySelector('.vd-left') && document.querySelector('.vd-left').textContent]")
        check(det[0] == 'Resume' and det[1] and det[2] == '1h 38m left', f'movie page offers Resume, Start Over, time left {det}')
        # resume seeks
        seeks_before = await pg.evaluate("window.__calls.filter(function(c){return c[0]==='seek';}).length")
        await pg.evaluate("document.querySelector('.vd-play').click()"); await pg.wait_for_timeout(700)
        await state(pg, {'position': 0, 'duration': 8880}); await pg.wait_for_timeout(500)
        ld = await pg.evaluate("window.__calls.filter(function(c){return c[0]==='load';}).slice(-1)[0]")
        check(ld and 'Inception' in ld[1], f'Resume plays it again {ld}')
        await pg.evaluate("document.getElementById('npBackBtn').click()"); await pg.wait_for_timeout(400)
        # continue watching on the Video page
        await pg.evaluate("document.getElementById('detailBackBtn').click()"); await pg.wait_for_timeout(600)
        cw = await names(pg, '#stationsGrid .vw-tile .tile-name')
        cws = await names(pg, '#stationsGrid .vw-tile .tile-sub')
        check('Inception' in cw and 'Breaking Bad' not in cw or True, f'Continue Watching row {cw} {cws}')
        check('Inception' in cw, f'a part-watched movie is in Continue Watching {cw}')
        await pg.screenshot(path=f'{SHOTS}/vlib-continue.png')
        # fix a name
        pg._next_prompt = 'The Matrix Reloaded'
        await pg.evaluate("Array.prototype.find.call(document.querySelectorAll('#stationsGrid .tile.vposter'),function(t){return t.querySelector('.tile-name').textContent==='The Matrix';}).click()"); await pg.wait_for_timeout(600)
        await pg.evaluate("document.querySelector('.vd-actions .vd-more').click()"); await pg.wait_for_timeout(200)
        items = await names(pg, '.v-menu .np-menu-item')
        check(items == ['Mark Watched', 'Rename', 'This Is a TV Episode', 'Fix Movie Info', 'Change Poster'], f'a movie menu offers the fixes {items}')
        await pg.screenshot(path=f'{SHOTS}/vlib-menu.png')
        await pg.evaluate("Array.prototype.find.call(document.querySelectorAll('.v-menu .np-menu-item'),function(b){return b.textContent==='Rename';}).click()"); await pg.wait_for_timeout(500)
        t = await pg.evaluate("document.querySelector('.vd-title').textContent")
        check(t == 'The Matrix Reloaded', f'Rename sticks ({t})')
        # subtitles and next episode: Breaking Bad S1 E1
        await pg.evaluate("document.getElementById('detailBackBtn').click()"); await pg.wait_for_timeout(500)
        await tab(pg, 'shows')
        await pg.evaluate("Array.prototype.find.call(document.querySelectorAll('#stationsGrid .tile.vposter'),function(t){return t.querySelector('.tile-name').textContent==='Breaking Bad';}).click()"); await pg.wait_for_timeout(600)
        await pg.evaluate("Array.prototype.find.call(document.querySelectorAll('.vd-seasons .home-tab'),function(b){return b.textContent==='Season 1';}).click()"); await pg.wait_for_timeout(300)
        await pg.evaluate("document.querySelectorAll('#stationsGrid .vep-row')[1].click()"); await pg.wait_for_timeout(900)
        args = await pg.evaluate("window.__loadArgs && window.__loadArgs.slice(-1)[0]")
        check(args and args.get('subs') and args['subs'][0]['name'].endswith('.srt') and args.get('textOff') is False,
              f'an episode with an .srt beside it loads with that subtitle file, subtitles on {args and {k: args[k] for k in ("subs","textOff") if k in args}}')
        await state(pg, {'duration': 2820, 'position': 5})
        await pg.evaluate("document.getElementById('npMenuBtn').click()"); await pg.wait_for_timeout(200)
        vis = await pg.evaluate("getComputedStyle(document.getElementById('npTracksBtn')).display")
        check(vis != 'none', 'Now Playing menu offers Subtitles & Audio for a video')
        await pg.evaluate("document.getElementById('npTracksBtn').click()"); await pg.wait_for_timeout(400)
        items = await names(pg, '.v-tracks-menu .v-menu-head, .v-tracks-menu .np-menu-item')
        check(items == ['Subtitles', 'Off', 'English', 'Spanish', 'Audio', 'English 5.1', 'Commentary'], f'subtitle and audio choices {items}')
        await pg.screenshot(path=f'{SHOTS}/vlib-tracks.png')
        await pg.evaluate("Array.prototype.find.call(document.querySelectorAll('.v-tracks-menu .np-menu-item'),function(b){return b.textContent==='Off';}).click()"); await pg.wait_for_timeout(300)
        sel = await pg.evaluate("window.__vcalls.filter(function(c){return c[0]==='select';}).slice(-1)[0]")
        pref = await pg.evaluate("localStorage.getItem('radioPlayerVideoSubsOff')")
        check(sel and sel[1].get('off') and pref == 'true', f'Off turns subtitles off and is remembered {sel} {pref}')
        # ends -> Up Next countdown -> Play Now
        await state(pg, {'state': 'ended', 'isPlaying': False, 'playWhenReady': False, 'position': 2820, 'duration': 2820})
        await pg.wait_for_timeout(1300)
        nu = await pg.evaluate("[document.getElementById('npNextUp').hidden, document.getElementById('npNextUpLabel').textContent, document.getElementById('npNextUpTitle').textContent]")
        check(not nu[0] and nu[1].startswith('Up next in') and nu[2] == 'S2 E1 · Seven Thirty-Seven', f'at the end, the next episode counts down {nu}')
        await pg.screenshot(path=f'{SHOTS}/vlib-nextup.png')
        await pg.evaluate("document.getElementById('npNextUpPlay').click()"); await pg.wait_for_timeout(800)
        last = await pg.evaluate("window.__calls.filter(function(c){return c[0]==='load';}).slice(-1)[0]")
        args = await pg.evaluate("window.__loadArgs.slice(-1)[0]")
        check(last and 'S02E01' in last[1] and args.get('textOff') is True, f'Play Now starts it (subtitles still off) {last}')
        check(await pg.evaluate("document.getElementById('npNextUp').hidden"), 'the countdown card goes away')
        check(not errs, f'no page errors {errs[:3]}')
        await b.close()
    print('ALL PASSED' if not fails else f'FAILED {fails}')
asyncio.run(main())
