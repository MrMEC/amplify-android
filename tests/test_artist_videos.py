"""Build 126: a favourite artist's page shows a sideways row of YouTube music videos under the
albums (channel from Wikidata P2397, videos from YouTube's public feed fetched natively), and tapping one plays it in a full-screen overlay. Artist bio previews are
left-aligned. Run: python3 tests/test_artist_videos.py (screenshots in /tmp/claude-0/t/shots)"""
import asyncio, os, json, threading, http.server, functools, shutil, subprocess, re
from urllib.parse import urlparse, parse_qs, unquote
from playwright.async_api import async_playwright

PORT = 8802
root = '/tmp/claude-0/t/srv_artvid'
shots = '/tmp/claude-0/t/shots'
os.makedirs(shots, exist_ok=True)
shutil.rmtree(root, ignore_errors=True)
os.makedirs(root)
HOOK = ("window.__v = { fav: function(n){ var e = findArtistEntry(artistMatchKey(n)); toggleFavorite(artistFavRecord(e)); },"
        " open: function(n){ openArtistPage(findArtistEntry(artistMatchKey(n)).key); },"
        " tracks: function(){ return libraryTracks.length; }, hide: function(){ try{ hideImportPanel(); setStatus('', false); }catch(e){} },"
        " play: function(){ currentStation = libraryTracks[0]; audio.play = function(){ return Promise.resolve(); }; audio.pause = function(){}; setPlayingUI(true); },"
        " playing: function(){ return uiIsPlaying; },"
        " paused: [] };\n")
_src = open(os.path.join(os.path.dirname(__file__), '..', 'www', 'index.html')).read()
_mark = '  var coverFlow = null;\n'
assert _src.count(_mark) == 1
open(root + '/index.html', 'w').write(_src.replace(_mark, _mark + HOOK))

M = root + '/Music'
os.makedirs(M, exist_ok=True)
SONGS = [('A1', 'Alpha', 'Alpha Album', 1), ('A2', 'Alpha', 'Alpha Two', 1), ('B1', 'Bravo', 'Bravo Album', 1),
         ('C1', 'Charlie', 'Charlie Album', 1), ('D1', 'Delta', 'Delta Album', 1)]
for i, (t, a, al, n) in enumerate(SONGS):
    subprocess.run(['ffmpeg', '-loglevel', 'error', '-y', '-f', 'lavfi', '-i', f'sine=frequency={300 + i * 60}:duration=3',
                    '-c:a', 'libmp3lame', '-b:a', '32k', '-metadata', f'title={t}', '-metadata', f'artist={a}',
                    '-metadata', f'album={al}', '-metadata', f'track={n}', f'{M}/{i + 1:02d}.mp3'], check=True)
THUMB = root + '/thumb.jpg'
subprocess.run(['ffmpeg', '-loglevel', 'error', '-y', '-f', 'lavfi', '-i', 'testsrc=size=320x180:rate=1', '-frames:v', '1', THUMB], check=True)
THUMB_BYTES = open(THUMB, 'rb').read()


class Q(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a): pass
H = functools.partial(Q, directory=root)
srv = http.server.ThreadingHTTPServer(('127.0.0.1', PORT), H)
threading.Thread(target=srv.serve_forever, daemon=True).start()
files = [{'uri': f'http://127.0.0.1:{PORT}/Music/{f}', 'name': f, 'relPath': f'Music/{f}', 'type': 'audio/mpeg',
          'size': os.path.getsize(f'{M}/{f}'), 'lastModified': 1700000000000} for f in sorted(os.listdir(M))]

CH_A1 = 'UC' + 'a' * 22   # Alpha's own channel: no "videos only" list, plain feed
CH_A2 = 'UC' + 'b' * 22   # Alpha's VEVO channel
CH_AX = 'UC' + 'x' * 22   # deprecated, never asked
CH_B = 'UC' + 'c' * 22
CH_D = 'UC' + 'd' * 22


def entry(vid, title, date, shorts=False):
    href = f'https://www.youtube.com/{"shorts/" + vid if shorts else "watch?v=" + vid}'
    return (f'<entry><id>yt:video:{vid}</id><yt:videoId>{vid}</yt:videoId><title>{title}</title>'
            f'<link rel="alternate" href="{href}"/><published>{date}T10:00:00+00:00</published>'
            f'<media:group><media:title>{title}</media:title></media:group></entry>')


def feed(entries):
    return ('<?xml version="1.0" encoding="UTF-8"?><feed xmlns:yt="http://www.youtube.com/xml/schemas/2015" '
            'xmlns:media="http://search.yahoo.com/mrss/" xmlns="http://www.w3.org/2005/Atom"><title>ch</title>'
            + ''.join(entries) + '</feed>')


FEEDS = {
    'channel_id=' + CH_A1: feed([
        entry('alphaVid001', 'Alpha - Sunrise (Official Music Video)', '2025-06-01'),
        entry('alphaShrt01', 'Sunrise #shorts', '2025-06-03', shorts=True),
        entry('alphaLyric1', 'Alpha - Sunrise (Official Lyric Video)', '2025-05-20'),
        entry('alphaIntv01', 'Alpha interview at the festival', '2025-05-10'),
        entry('alphaVid002', 'Alpha - Midnight Drive [Official Video]', '2023-03-04'),
    ]),
    'playlist_id=UULF' + CH_A2[2:]: feed([
        entry('alphaVevo01', 'Alpha - A Very Long Song Title That Goes On And On Well Past Two Lines Of Text (Official Music Video)', '2024-11-11'),
        entry('alphaVid001', 'Alpha - Sunrise (Official Music Video)', '2025-06-01'),
        entry('alphaVevo02', 'Alpha - Old Hit (Official HD Video)', '2015-02-02'),
    ]),
    'playlist_id=UULF' + CH_B[2:]: feed([entry('bravoVid001', 'Bravo - Glow (Official Video)', '2022-01-01')]),
    'playlist_id=UULF' + CH_D[2:]: feed([entry('deltaTalk01', 'Delta on tour, part 1', '2024-01-01'),
                                         entry('deltaTalk02', 'Delta studio diary', '2023-01-01')]),
}

MOCK = """
(function(){
 var picked = %s, feeds = %s, listeners = {};
 window.__http = [];
 var impl = {
   pickMusicFolder: function(){ return Promise.resolve({folder:'Music', files:picked, truncated:false}); },
   addListener: function(n, f){ (listeners[n] = listeners[n] || []).push(f); return Promise.resolve({remove:function(){}}); },
   fetchText: function(o){ window.__http.push(o.url); var q = o.url.split('?')[1] || '';
     return new Promise(function(res, rej){ setTimeout(function(){
       if(o.url.indexOf('https://www.youtube.com/feeds/videos.xml?') === 0 && feeds[q]) res({ text: feeds[q], url: o.url });
       else rej(new Error('HTTP 404')); }, 120); }); }
 };
 var P = new Proxy({}, {get:function(t,k){
   if(k==='then') return undefined;
   if(k==='setCarLibraryPart') return undefined;
   if(impl[k]) return impl[k];
   return function(){ return Promise.resolve({}); };
 }});
 var Http = { get: function(o){
   window.__http.push(o.url);
   var q = o.url.split('?')[1] || '';
   return new Promise(function(res){ setTimeout(function(){
     if(o.url.indexOf('https://www.youtube.com/feeds/videos.xml?') === 0 && feeds[q]) res({ status: 200, data: feeds[q], headers: {} });
     else res({ status: 404, data: 'not found', headers: {} });
   }, 120); });
 } };
 window.Capacitor = { isNativePlatform:function(){return true;}, getPlatform:function(){return 'android';},
   registerPlugin:function(){ return P; }, Plugins:{AmplifyPlayer:P}, convertFileSrc:function(u){return u;} };
})();
""" % (json.dumps(files), json.dumps(FEEDS))

BIO = ('Alpha are an American rock band formed in 2009. Over five albums they have moved from garage rock to wide-screen '
       'synth pop, and their live shows are known for long improvised codas. The band has toured with many acts and '
       'their 2023 single topped the alternative chart for eleven weeks.')


def claims(*items):
    return {'P2397': [{'rank': r, 'mainsnak': {'datavalue': {'value': v}}} for v, r in items]}


ENTITIES = {
    'Q1': {'id': 'Q1', 'claims': claims((CH_AX, 'deprecated'), (CH_A1, 'normal'), (CH_A2, 'preferred'))},
    'Q2': {'id': 'Q2', 'claims': claims((CH_B, 'normal'))},
    'Q4': {'id': 'Q4', 'claims': claims((CH_D, 'normal'))},
    'Q9': {'id': 'Q9', 'claims': claims(('UC' + 'z' * 22, 'normal'))},   # a company called Delta
}
SEARCH = {'Bravo': [{'id': 'Q2', 'description': 'American singer'}],
          'Charlie': [{'id': 'Q3', 'description': 'American singer'}],
          'Delta': [{'id': 'Q9', 'description': 'American airline'}, {'id': 'Q4', 'description': 'English band'}]}
counts = {'wikidata': 0, 'yt_embed': []}

fails = []
def check(cond, msg):
    print(('PASS ' if cond else 'FAIL ') + msg)
    if not cond: fails.append(msg)


async def route(r):
    url = r.request.url
    u = urlparse(url)
    if '127.0.0.1' in u.netloc:
        return await r.continue_()
    if u.netloc == 'en.wikipedia.org' and u.path.startswith('/api/rest_v1/page/summary/'):
        t = unquote(u.path.split('/summary/')[1])
        if t == 'Alpha':
            return await r.fulfill(status=200, content_type='application/json', headers={'access-control-allow-origin': '*'},
                                   body=json.dumps({'type': 'standard', 'title': 'Alpha (band)', 'extract': BIO,
                                                    'description': 'American rock band',
                                                    'content_urls': {'desktop': {'page': 'https://en.wikipedia.org/wiki/Alpha_(band)'}}}))
        return await r.fulfill(status=404, body='', headers={'access-control-allow-origin': '*'})
    if u.netloc == 'www.wikidata.org':
        counts['wikidata'] += 1
        q = parse_qs(u.query)
        act = (q.get('action') or [''])[0]
        hdr = {'access-control-allow-origin': '*'}
        if act == 'wbsearchentities':
            return await r.fulfill(status=200, content_type='application/json', headers=hdr,
                                   body=json.dumps({'search': SEARCH.get(q['search'][0], [])}))
        if act == 'wbgetentities':
            if 'titles' in q:
                ents = {'Q1': ENTITIES['Q1']} if q['titles'][0] == 'Alpha (band)' else {'-1': {'missing': ''}}
            else:
                ents = {i: ENTITIES.get(i, {'id': i, 'claims': {}}) for i in q['ids'][0].split('|')}
            return await r.fulfill(status=200, content_type='application/json', headers=hdr, body=json.dumps({'entities': ents}))
        return await r.fulfill(status=404, body='', headers=hdr)
    if u.netloc == 'i.ytimg.com':
        return await r.fulfill(status=200, content_type='image/jpeg', body=THUMB_BYTES)
    if u.netloc == 'www.youtube.com' and u.path.startswith('/embed/'):
        counts['yt_embed'].append(url)
        vid = u.path.split('/embed/')[1]
        return await r.fulfill(status=200, content_type='text/html',
                               body=f'<body style="margin:0;background:#202020;color:#fff;font:20px sans-serif;display:flex;align-items:center;justify-content:center;height:100vh">EMBED {vid}</body>')
    return await r.abort()

ROW = """(()=>{ var g = document.getElementById('stationsGrid'); var kids = Array.from(g.children);
  var lab = g.querySelector('.artist-videos-label'), row = g.querySelector('.artist-videos'), al = g.querySelector('.artist-albums');
  return { label: lab ? lab.textContent : null, labelIdx: kids.indexOf(lab), albumsIdx: kids.indexOf(al), rowIdx: kids.indexOf(row),
    ids: row ? Array.from(row.querySelectorAll('.yt-tile:not(.yt-skel)')).map(function(t){ return t.dataset.vid; }) : null,
    titles: row ? Array.from(row.querySelectorAll('.yt-title')).map(function(t){ return t.textContent; }) : null,
    skel: row ? row.querySelectorAll('.yt-skel').length : 0,
    sw: row ? row.scrollWidth : 0, cw: row ? row.clientWidth : 0 }; })()"""


async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
        ctx = await b.new_context(viewport={'width': 390, 'height': 844}, device_scale_factor=2, is_mobile=True, has_touch=True, color_scheme='dark')
        await ctx.add_init_script(MOCK)
        pg = await ctx.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.route('**/*', route)
        await pg.goto(f'http://127.0.0.1:{PORT}/index.html'); await pg.wait_for_timeout(2500)
        await pg.evaluate("""(function(){ var ov=document.getElementById('addMusicOverlay'); if(ov) ov.classList.add('open');
          var btn=document.getElementById('addMusicFolderBtn'); btn.disabled=false; btn.click(); })()""")
        for _ in range(60):
            await pg.wait_for_timeout(500)
            if await pg.evaluate('__v.tracks()') >= 5: break
        await pg.evaluate("document.getElementById('addMusicOverlay').classList.remove('open')")
        await pg.wait_for_timeout(300); await pg.evaluate('__v.hide()')

        # ---- not a favourite: no videos, no requests ----
        await pg.evaluate("__v.open('Alpha')"); await pg.wait_for_timeout(1500)
        r = await pg.evaluate(ROW)
        check(r['label'] is None and r['rowIdx'] == -1, 'not a favourite: no video row')
        check(not await pg.evaluate('__http.length'), 'not a favourite: YouTube not asked')
        bio = await pg.evaluate("""(()=>{ var b = document.getElementById('artistHeroBio'), t = b.querySelector('.artist-hero-bio-text');
          var g = document.getElementById('stationsGrid').getBoundingClientRect();
          if(!t) return null; var range = document.createRange(); range.selectNodeContents(t); var rs = range.getClientRects();
          return { align: getComputedStyle(b).textAlign, left: Math.round(rs[0].left), right: Math.round(rs[0].right), gl: Math.round(g.left),
            more: Math.round(b.querySelector('.artist-hero-bio-source').getBoundingClientRect().left) }; })()""")
        print('bio', bio)
        check(bio and bio['align'] == 'left', f'bio preview is left-aligned {bio}')
        check(bio and abs(bio['left'] - bio['gl']) <= 2 and abs(bio['more'] - bio['gl']) <= 2, 'bio text and More start at the page edge')
        await pg.screenshot(path=f'{shots}/artvid-bio-left.png')

        # ---- favourite it from the artist menu: the row appears ----
        await pg.evaluate("document.getElementById('artistFavBtn').click()"); await pg.wait_for_timeout(60)
        r = await pg.evaluate(ROW)
        check(r['skel'] == 3 and r['label'] == 'Music Videos', f'favourited: placeholders while loading {r["skel"]}')
        await pg.wait_for_timeout(1500)
        r = await pg.evaluate(ROW)
        print(r)
        check(r['label'] == 'Music Videos', 'headed Music Videos')
        check(r['albumsIdx'] >= 0 and r['labelIdx'] > r['albumsIdx'] and r['rowIdx'] == r['labelIdx'] + 1, 'the row sits below the albums')
        check(r['ids'] == ['alphaVid001', 'alphaVevo01', 'alphaVid002', 'alphaVevo02'],
              f'official videos from both channels, newest first, no lyric video, interview or Short, no repeats {r["ids"]}')
        check(r['titles'][0] == 'Sunrise' and r['titles'][2] == 'Midnight Drive' and r['titles'][3] == 'Old Hit', f'titles tidied {r["titles"]}')
        urls = await pg.evaluate('__http')
        check(not any(CH_AX in u for u in urls), 'a deprecated channel is never asked')
        check(any('channel_id=' + CH_A1 in u for u in urls), 'a channel without a videos-only list falls back to its plain feed')
        check(r['sw'] > r['cw'] + 100, f'the row runs off the screen (scrolls sideways) {r["sw"]} > {r["cw"]}')
        geo = await pg.evaluate("""(()=>{ var row = document.querySelector('.artist-videos'), t = row.querySelectorAll('.yt-tile');
          var a = t[0].getBoundingClientRect(), b = t[1].getBoundingClientRect(), th = t[0].querySelector('.yt-thumb').getBoundingClientRect();
          var lab = document.querySelector('.artist-videos-label').getBoundingClientRect();
          return { top0: Math.round(a.top), top1: Math.round(b.top), left0: Math.round(a.left), labLeft: Math.round(lab.left),
            ratio: th.width / th.height, imgOk: t[0].querySelector('img').naturalWidth > 0, vw: innerWidth,
            rowL: Math.round(row.getBoundingClientRect().left), rowR: Math.round(row.getBoundingClientRect().right),
            pageX: document.scrollingElement.scrollWidth }; })()""")
        print(geo)
        check(geo['top0'] == geo['top1'], 'tiles side by side')
        check(abs(geo['left0'] - geo['labLeft']) <= 2, 'first tile lines up with the heading')
        check(abs(geo['ratio'] - 16 / 9) < 0.02 and geo['imgOk'], 'thumbnails 16:9 and loaded')
        check(geo['rowL'] == 0 and geo['rowR'] == geo['vw'] and geo['pageX'] <= geo['vw'], 'the row runs to both screen edges without sideways page scroll')
        await pg.evaluate("document.querySelector('.artist-videos').scrollIntoView({block:'center'})"); await pg.wait_for_timeout(400)
        await pg.screenshot(path=f'{shots}/artvid-row.png')
        await pg.evaluate("document.querySelector('.artist-videos').scrollBy({left: 300, behavior: 'instant'})"); await pg.wait_for_timeout(400)
        check(await pg.evaluate("document.querySelector('.artist-videos').scrollLeft") > 100, 'the row scrolls sideways')
        await pg.screenshot(path=f'{shots}/artvid-row-scrolled.png')

        # ---- play one ----
        await pg.evaluate('__v.play()'); await pg.wait_for_timeout(300)
        check(await pg.evaluate('__v.playing()'), '(setup) something is playing')
        await pg.evaluate("document.querySelectorAll('.artist-videos .yt-tile')[1].click()"); await pg.wait_for_timeout(1200)
        ov = await pg.evaluate("""(()=>{ var o = document.getElementById('ytOverlay'), f = o.querySelector('iframe'), r = o.getBoundingClientRect(), fr = f.getBoundingClientRect();
          return { open: o.classList.contains('open'), src: f.src, ref: f.getAttribute('referrerpolicy'), title: document.getElementById('ytOvTitle').textContent,
            link: document.getElementById('ytOpenLink').href, full: r.width === innerWidth && r.height === innerHeight,
            fw: Math.round(fr.width), fh: Math.round(fr.height), z: getComputedStyle(o).zIndex }; })()""")
        print(ov)
        check(ov['open'] and ov['full'], 'the player covers the screen')
        check('/embed/alphaVevo01?' in ov['src'] and 'autoplay=1' in ov['src'] and 'playsinline=1' in ov['src'] and 'fs=0' in ov['src'], 'embeds that video, autoplaying inline')
        check(ov['ref'] == 'strict-origin-when-cross-origin', 'the embed sends a referrer (no error 153)')
        check(ov['link'] == 'https://www.youtube.com/watch?v=alphaVevo01', 'Open in YouTube points at the video')
        check(ov['fw'] == 390 and abs(ov['fh'] - 390 * 9 / 16) < 2, f'video frame is full width, 16:9 ({ov["fw"]}x{ov["fh"]})')
        check(not await pg.evaluate('__v.playing()'), 'the radio pauses while a video plays')
        check(len(counts['yt_embed']) == 1, 'the embed loaded')
        await pg.screenshot(path=f'{shots}/artvid-player.png')
        await pg.evaluate("document.getElementById('ytCloseBtn').click()"); await pg.wait_for_timeout(500)
        check(await pg.evaluate("!document.getElementById('ytOverlay').classList.contains('open') && !document.querySelector('#ytOverlay iframe')"), 'closing stops and hides the video')
        check(await pg.evaluate('__v.playing()'), 'and the radio resumes')

        # ---- landscape: player stays on top of the landscape Now Playing ----
        await pg.evaluate("document.querySelectorAll('.artist-videos .yt-tile')[0].click()"); await pg.wait_for_timeout(500)
        await pg.set_viewport_size({'width': 844, 'height': 390}); await pg.wait_for_timeout(1200)
        land = await pg.evaluate("""(()=>{ var o = document.getElementById('ytOverlay'), fr = o.querySelector('iframe').getBoundingClientRect();
          var top = document.elementFromPoint(422, 200); return { onTop: o.contains(top), fw: Math.round(fr.width), fh: Math.round(fr.height), ft: Math.round(fr.top), fb: Math.round(fr.bottom) }; })()""")
        print('landscape', land)
        check(land['onTop'] and land['ft'] == 0 and land['fh'] == 390 and abs(land['fw'] - 693) <= 1, f'landscape: the video stays on top and fills the height {land}')
        await pg.screenshot(path=f'{shots}/artvid-player-land.png')
        await pg.evaluate("document.getElementById('ytCloseBtn').click()")
        await pg.set_viewport_size({'width': 390, 'height': 844}); await pg.wait_for_timeout(1200)

        # ---- unfavourite: the row goes ----
        await pg.evaluate("__v.open('Alpha')"); await pg.wait_for_timeout(500)
        await pg.evaluate("document.getElementById('artistFavBtn').click()"); await pg.wait_for_timeout(200)
        check((await pg.evaluate(ROW))['rowIdx'] == -1, 'unfavourited: the row goes')
        await pg.evaluate("document.getElementById('artistFavBtn').click()"); await pg.wait_for_timeout(200)
        check((await pg.evaluate(ROW))['ids'] == r['ids'], 'favourited again: back at once from the saved list')

        # ---- Bravo (no article: Wikidata search), Delta (non-music hit skipped; no official videos), Charlie (no channel) ----
        for n in ('Bravo', 'Charlie', 'Delta'): await pg.evaluate(f"__v.fav('{n}')")
        await pg.evaluate("__v.open('Bravo')"); await pg.wait_for_timeout(2000)
        rb = await pg.evaluate(ROW)
        check(rb['ids'] == ['bravoVid001'] and rb['label'] == 'Music Videos', f'Bravo: channel found by name search {rb["ids"]}')
        await pg.evaluate("__v.open('Delta')"); await pg.wait_for_timeout(2000)
        rd = await pg.evaluate(ROW)
        check(rd['ids'] == ['deltaTalk01', 'deltaTalk02'] and rd['label'] == 'Videos', f'Delta: skips the airline, no official videos so all shown as "Videos" {rd}')
        await pg.evaluate("__v.open('Charlie')"); await pg.wait_for_timeout(2000)
        rc = await pg.evaluate(ROW)
        check(rc['rowIdx'] == -1 and rc['skel'] == 0, 'Charlie: no channel, no row')

        # ---- after a restart: shown straight from the saved list, nothing asked ----
        await pg.reload(); await pg.wait_for_timeout(2500)
        wd0 = counts['wikidata']
        await pg.evaluate("__v.open('Alpha')"); await pg.wait_for_timeout(150)
        ra = await pg.evaluate(ROW)
        check(ra['ids'] == r['ids'] and ra['skel'] == 0, 'after a restart the row shows at once')
        await pg.wait_for_timeout(1000)
        check(not await pg.evaluate('__http.length'), 'and YouTube is not asked again within 12 hours')

        # ---- larger system text at 412 and 360 ----
        for w in (412, 360):
            await pg.set_viewport_size({'width': w, 'height': 900}); await pg.wait_for_timeout(500)
            await pg.add_style_tag(content='html{ font-size:135% } .yt-title{ font-size:18.2px !important } .yt-date{ font-size:16.2px !important } .artist-hero-bio-text{ font-size:18.2px !important } .grid-section-label{ font-size:16.9px !important }')
            await pg.evaluate("__v.open('Alpha')"); await pg.wait_for_timeout(800)
            await pg.evaluate("document.querySelector('.artist-videos').scrollIntoView({block:'center'})"); await pg.wait_for_timeout(300)
            clip = await pg.evaluate("""(()=>{ var t = document.querySelectorAll('.artist-videos .yt-tile')[0], ti = t.querySelector('.yt-title'), d = t.querySelector('.yt-date');
              return { titleH: ti.getBoundingClientRect().height, lh: parseFloat(getComputedStyle(ti).lineHeight), dateVis: d.getBoundingClientRect().height > 10 }; })()""")
            check(clip['titleH'] <= clip['lh'] * 2 + 1 and clip['dateVis'], f'{w}px, big text: title at most two lines, year shown {clip}')
            await pg.screenshot(path=f'{shots}/artvid-big-{w}.png')
        check(not errs, f'no page errors {errs[:3]}')

        # ---- desktop ----
        d = await b.new_context(viewport={'width': 1400, 'height': 900}, color_scheme='dark')
        await d.add_init_script(MOCK)
        dp = await d.new_page(); await dp.route('**/*', route)
        await dp.goto(f'http://127.0.0.1:{PORT}/index.html'); await dp.wait_for_timeout(2500)
        await dp.evaluate("""(function(){ var ov=document.getElementById('addMusicOverlay'); if(ov) ov.classList.add('open');
          var btn=document.getElementById('addMusicFolderBtn'); btn.disabled=false; btn.click(); })()""")
        for _ in range(60):
            await dp.wait_for_timeout(500)
            if await dp.evaluate('__v.tracks()') >= 5: break
        await dp.evaluate("document.getElementById('addMusicOverlay').classList.remove('open')")
        await dp.wait_for_timeout(300); await dp.evaluate('__v.hide()')
        await dp.evaluate("__v.fav('Alpha')"); await dp.evaluate("__v.open('Alpha')"); await dp.wait_for_timeout(2500)
        rr = await dp.evaluate(ROW)
        check(rr['ids'] and len(rr['ids']) == 4, 'desktop: the row shows')
        await dp.screenshot(path=f'{shots}/artvid-desktop.png', full_page=True)
        await b.close()
    print('ALL PASSED' if not fails else f'FAILED {fails}')

asyncio.run(main())
