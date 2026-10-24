"""Builds 211-212: Top 100. Home row of this week's Billboard Hot 100; the page week by week (previous/next,
the date picker); rows: rank, cover, title/artist; covers from iTunes. Build 212: a song plays its music
video in YouTube's player (the video page), found on the artist's channel, MusicBrainz or Wikidata, the week's
chart listed under it, the next song at the end. Build 218: a song in the library plays whole in Now Playing; one
with no video (or one YouTube won't play here) plays its 30-second preview in Now Playing, with a YouTube search
button; a spinner while the video is looked up; never a "No official video found" screen. Chart files, iTunes, Wikidata, the channel feed, YouTube's player and the plugin are mocked.
Run: python3 tests/test_top100.py (screenshots in /tmp/claude-0/t/shots)"""
import sys as _nsys, os as _nos; _nsys.path.insert(0, _nos.path.dirname(_nos.path.abspath(__file__))); from notice_auto import AUTO_NOTICE
import asyncio, os, json, threading, http.server, functools, shutil, sys, re
from urllib.parse import urlparse, parse_qs
from playwright.async_api import async_playwright

PORT = 8808
root = '/tmp/claude-0/t/srv_top100'
OUT = '/tmp/claude-0/t/shots'
os.makedirs(OUT, exist_ok=True)
shutil.rmtree(root, ignore_errors=True); os.makedirs(root)
HOOK = "window.__h = { ev: function(js){ return eval(js); } };\n"
src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'www', 'index.html')).read()
mark = '  var coverFlow = null;\n'
assert src.count(mark) == 1
open(root + '/index.html', 'w').write(src.replace(mark, mark + HOOK))
class Q(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a): pass
srv = http.server.ThreadingHTTPServer(('127.0.0.1', PORT), functools.partial(Q, directory=root))
threading.Thread(target=srv.serve_forever, daemon=True).start()

ARTISTS = ['Taylor Swift', 'Ella Langley', 'Morgan Wallen Featuring Tate McRae', 'Sabrina Carpenter', 'Alex Warren']
def chart(date, shift):
    rows = []
    for i in range(100):
        rank = i + 1
        lw = None if (i + shift) % 9 == 0 else max(1, rank + ((i % 5) - 2))
        rows.append({'song': f'Song {rank:03d}' if i else 'Patient Zero', 'artist': ARTISTS[i % 5], 'this_week': rank,
                     'last_week': lw, 'peak_position': max(1, rank - 3), 'weeks_on_chart': 1 if lw is None else 5 + i % 7})
    return {'date': date, 'data': rows}
CHARTS = {'2026-10-10': chart('2026-10-10', 0), '2026-10-03': chart('2026-10-03', 4), '2026-09-26': chart('2026-09-26', 2),
          '2026-08-29': chart('2026-08-29', 1), '1958-08-04': chart('1958-08-04', 3)}
DATES = ['1958-08-04', '2026-08-29', '2026-09-26', '2026-10-03', '2026-10-10']
COLORS = ['#e0457b', '#3a7bd5', '#f59e0b', '#10b981', '#8b5cf6']

def art_svg(i):
    return ('<svg xmlns="http://www.w3.org/2000/svg" width="600" height="600"><rect width="600" height="600" fill="%s"/>'
            '<text x="300" y="350" font-size="160" text-anchor="middle" fill="white" font-family="sans-serif">%d</text></svg>') % (COLORS[i % 5], i)

MOCK = r"""(function(){
 var L = {}; window.__nat = { feeds: [], deezer: [], loads: [], plays: 0, pauses: 0 };
 function emit(n, ev){ (L[n] || []).forEach(function(f){ f(ev); }); }
 window.__emit = emit;
 var cur = null;
 var impl = {
  addListener: function(n, f){ (L[n] = L[n] || []).push(f); return Promise.resolve({ remove: function(){} }); },
  load: function(o){ __nat.loads.push(o.url); cur = { id: o.id, url: o.url, pos: 0 };
    var id = o.id;
    setTimeout(function(){ if(!cur || cur.id !== id) return;
      emit('state', { id: id, state: 'buffering', isPlaying: false, playWhenReady: !!o.play, duration: -1, position: 0, external: false }); }, 30);
    setTimeout(function(){ if(!cur || cur.id !== id) return;
      emit('state', { id: id, state: 'ready', isPlaying: !!o.play, playWhenReady: !!o.play, duration: 200, position: 0, external: true, spotify: true }); }, 250);
    return Promise.resolve({}); },
  play: function(){ __nat.plays++; if(cur) setTimeout(function(){ emit('state', { id: cur.id, state: 'ready', isPlaying: true, playWhenReady: true, duration: 200, position: 10, external: true }); }, 20); return Promise.resolve({}); },
  pause: function(){ __nat.pauses++; if(cur) setTimeout(function(){ emit('state', { id: cur.id, state: 'ready', isPlaying: false, playWhenReady: false, duration: 200, position: 10, external: true }); }, 20); return Promise.resolve({}); },
  fetchText: function(o){
    if(/api\.deezer\.com/.test(o.url || '')){
      __nat.deezer.push(o.url);
      var q = decodeURIComponent((/[?&]q=([^&]*)/.exec(o.url) || [])[1] || '');
      var m = /Song (\d+)|Patient Zero/.exec(q), n = m && m[1] ? +m[1] : 1;
      var now = Date.now(); __nat.dzTimes = (__nat.dzTimes || []).filter(function(t){ return now - t < 5000; }); __nat.dzTimes.push(now);
      if(__nat.dzTimes.length > 50){ __nat.dzQuota = (__nat.dzQuota || 0) + 1; return Promise.resolve({ text: JSON.stringify({ error: { type: 'Exception', message: 'Quota limit exceeded', code: 4 } }) }); }
      if(n === 50 && !__nat.failed50){ __nat.failed50 = true; return Promise.resolve({ text: JSON.stringify({ error: { type: 'Exception', message: 'Quota limit exceeded', code: 4 } }) }); }
      if(n === 7 || n === 11) return Promise.resolve({ text: JSON.stringify({ data: [] }) });
      var title = n === 1 ? 'Patient Zero' : 'Song ' + String(n).padStart(3, '0');
      var artist = ['Taylor Swift', 'Ella Langley', 'Morgan Wallen', 'Sabrina Carpenter', 'Alex Warren'][(n - 1) % 5];
      return Promise.resolve({ text: JSON.stringify({ data: [{ title: title + ' (Live)', artist: { name: artist }, preview: 'https://preview.example/' + n + '-0.mp3', album: { title: 'Live', cover_big: 'https://art.example/999/500.jpg' } },
        { title: title, artist: { name: artist }, preview: 'https://preview.example/' + n + '-1.mp3', album: { title: 'Eighties 100 Hits', cover_big: 'https://art.example/998/500.jpg' } },
        { title: title, artist: { name: artist }, preview: 'https://preview.example/' + n + '-2.mp3', album: { title: n === 2 ? title : 'Album ' + n, cover_big: 'https://art.example/' + n + '/500.jpg' } }] }) });
    }
    __nat.feeds.push(o.url);
    var m = /playlist_id=UU(?:LF|LP)(\w+)|channel_id=UC(\w+)/.exec(o.url || '');
    var ch = m ? (m[1] || m[2]) : '';
    if(ch === 'tsTaylorChannel0000001' && /UULP/.test(o.url)) return Promise.resolve({ text: '<?xml version="1.0"?><feed xmlns="http://www.w3.org/2005/Atom" xmlns:yt="http://www.youtube.com/xml/schemas/2015">'
      + '<entry><yt:videoId>tsOld006vid</yt:videoId><title>Taylor Swift - Song 006</title><link href="https://www.youtube.com/watch?v=tsOld006vid"/><published>2014-01-01T00:00:00Z</published></entry></feed>' });
    if(ch === 'tsTaylorChannel0000001') return Promise.resolve({ text: '<?xml version="1.0"?><feed xmlns="http://www.w3.org/2005/Atom" xmlns:yt="http://www.youtube.com/xml/schemas/2015">'
      + '<entry><yt:videoId>tsLyric0001</yt:videoId><title>Taylor Swift - Patient Zero (Lyric Video)</title><link href="https://www.youtube.com/watch?v=tsLyric0001"/><published>2026-10-09T00:00:00Z</published></entry>'
      + '<entry><yt:videoId>tsPatient01</yt:videoId><title>Taylor Swift - Patient Zero (Official Music Video)</title><link href="https://www.youtube.com/watch?v=tsPatient01"/><published>2026-10-08T00:00:00Z</published></entry>'
      + '</feed>' });
    if(ch === 'awAlexChannel000000001' && /UULP/.test(o.url)) return Promise.resolve({ text: '<?xml version="1.0"?><feed xmlns="http://www.w3.org/2005/Atom" xmlns:yt="http://www.youtube.com/xml/schemas/2015">'
      + '<entry><yt:videoId>awSong005vi</yt:videoId><title>Alex Warren - Song 005 (Official Video)</title><link href="https://www.youtube.com/watch?v=awSong005vi"/><published>2025-01-01T00:00:00Z</published></entry></feed>' });
    return Promise.resolve({ text: '<?xml version="1.0"?><feed xmlns="http://www.w3.org/2005/Atom"></feed>' }); }
 };
 window.__endSong = function(){ if(cur) emit('state', { id: cur.id, state: 'ended', isPlaying: false, playWhenReady: true, duration: 200, position: 200, external: true }); };
 var P = new Proxy({}, { get: function(t, k){ if(k === 'then') return undefined; if(k === 'setCarLibraryPart') return undefined; if(impl[k]) return impl[k]; return function(){ return Promise.resolve({}); }; } });
 window.Capacitor = { isNativePlatform: function(){ return true; }, getPlatform: function(){ return 'android'; }, registerPlugin: function(){ return P; }, Plugins: { AmplifyPlayer: P }, convertFileSrc: function(u){ return u; } };
})();"""

fails = []
def check(c, m):
    print(('PASS ' if c else 'FAIL ') + m)
    if not c: fails.append(m)

async def run(theme, b):
    ctx = await b.new_context(viewport={'width': 412, 'height': 900}, device_scale_factor=2, is_mobile=True, has_touch=True, locale='en-US')
    counts = {'itunes': 0, 'mb': 0, 'wiki': [], 'embeds': [], 'charts': [], 'ytapi': []}
    async def route(r):
        u = r.request.url
        p = urlparse(u)
        if p.netloc.startswith('127.0.0.1') or u.startswith('data:'):
            return await r.continue_()
        if p.netloc in ('raw.githubusercontent.com', 'cdn.jsdelivr.net'):
            counts['charts'].append(p.netloc + p.path)
            if p.netloc == 'raw.githubusercontent.com' and '/date/' in p.path:
                return await r.fulfill(status=503, body='busy')   # GitHub's raw files flaky: the CDN has them
            if p.path.endswith('/recent.json'): body = json.dumps(CHARTS['2026-10-10'])
            elif p.path.endswith('/valid_dates.json'): body = json.dumps(DATES)
            else:
                m = re.search(r'/date/(\d{4}-\d{2}-\d{2})\.json$', p.path)
                if not m or m.group(1) not in CHARTS: return await r.fulfill(status=404, body='nope')
                body = json.dumps(CHARTS[m.group(1)])
            return await r.fulfill(status=200, content_type='application/json', headers={'Access-Control-Allow-Origin': '*'}, body=body)
        if p.netloc == 'itunes.apple.com':
            counts['itunes'] += 1
            q = parse_qs(p.query); cb = q['callback'][0]; term = q['term'][0]
            counts.setdefault('iterms', []).append(term)
            m = re.search(r'Song (\d+)|Patient Zero', term)
            n = int(m.group(1)) if m and m.group(1) else 1
            title = 'Patient Zero' if n == 1 else f'Song {n:03d}'
            artist = ARTISTS[(n - 1) % 5].split(' Featuring ')[0]
            res = {'resultCount': 1, 'results': [{'trackName': title, 'artistName': artist, 'artworkUrl100': f'https://art.example/{n}/100x100bb.jpg'}]} if n == 7 else {'resultCount': 0, 'results': []}
            return await r.fulfill(status=200, content_type='text/javascript', body=f'{cb}({json.dumps(res)});')
        if p.netloc == 'art.example':
            n = int(p.path.split('/')[1])
            return await r.fulfill(status=200, content_type='image/svg+xml', body=art_svg(n))
        if p.netloc == 'musicbrainz.org':
            counts['mb'] += 1
            q = parse_qs(p.query).get('query', [''])[0]
            counts.setdefault('mbq', []).append(p.path + ' ' + q)
            if '/recording/rec-003v' in p.path:
                body = {'id': 'rec-003v', 'relations': [{'type': 'free streaming', 'url': {'resource': 'https://www.youtube.com/watch?v=mwSong003vi'}}]}
            elif p.path.rstrip('/').endswith('/recording'):
                recs = [{'id': 'rec-003v', 'title': 'Song 003', 'score': 100, 'video': True, 'artist-credit': [{'name': 'Morgan Wallen'}]}] if 'Song 003' in q and 'video:true' in q else []
                body = {'recordings': recs}
            elif '/artist/art-aw' in p.path:
                body = {'id': 'art-aw', 'relations': [{'type': 'youtube', 'url': {'resource': 'https://www.youtube.com/channel/UCawAlexChannel000000001'}}]}
            elif p.path.rstrip('/').endswith('/artist'):
                body = {'artists': [{'id': 'art-aw', 'name': 'Alex Warren', 'score': 100}] if 'Alex Warren' in q else []}
            else:
                body = {'release-groups': [{'id': 'rg-011', 'title': 'Song 011', 'score': 100, 'primary-type': 'Single'}] if 'Song 011' in q else []}
            return await r.fulfill(status=200, content_type='application/json', headers={'Access-Control-Allow-Origin': '*'}, body=json.dumps(body))
        if p.netloc == 'coverartarchive.org':
            if p.path.endswith('/front-500'):
                return await r.fulfill(status=200, content_type='image/svg+xml', body=art_svg(11))
            return await r.fulfill(status=200, content_type='application/json', headers={'Access-Control-Allow-Origin': '*'}, body='{"images":[{"front":true}]}')
        if p.netloc == 'www.googleapis.com' and p.path == '/youtube/v3/search':
            q = parse_qs(p.query); key = q.get('key', [''])[0]; term = q.get('q', [''])[0]
            counts['ytapi'].append(term)
            if key != 'AIzaGoodKey000000000000000000000000000':
                return await r.fulfill(status=400, content_type='application/json', headers={'Access-Control-Allow-Origin': '*'},
                    body=json.dumps({'error': {'code': 400, 'message': 'API key not valid. Please pass a valid API key.', 'errors': [{'reason': 'keyInvalid'}]}}))
            items = []
            if 'Song 003' in term:
                items = [{'id': {'videoId': 'lyrSong0031'}, 'snippet': {'title': 'Morgan Wallen - Song 003 (Lyrics)', 'channelTitle': 'Lyric Vault'}},
                         {'id': {'videoId': 'mwSong003vi'}, 'snippet': {'title': 'Morgan Wallen - Song 003 (Official Music Video)', 'channelTitle': 'MorganWallenVEVO'}}]
            return await r.fulfill(status=200, content_type='application/json', headers={'Access-Control-Allow-Origin': '*'}, body=json.dumps({'items': items}))
        if p.netloc == 'www.wikidata.org':
            q = parse_qs(p.query); act = q.get('action', [''])[0]
            counts['wiki'].append(u)
            if act == 'wbsearchentities':
                term = q.get('search', [''])[0]
                hits = []
                if term == 'Taylor Swift': hits = [{'id': 'Q26876', 'label': 'Taylor Swift', 'description': 'American singer-songwriter (born 1989)'}]
                elif term == 'Song 002': hits = [{'id': 'Q900002', 'label': 'Song 002', 'description': '2026 single by Ella Langley'}, {'id': 'Q900099', 'label': 'Song 002', 'description': 'song by someone else'}]
                body = json.dumps({'search': hits})
            elif act == 'wbgetentities':
                ids = q.get('ids', [''])[0].split('|')
                ents = {}
                for i in ids:
                    if i == 'Q26876': ents[i] = {'claims': {'P2397': [{'rank': 'preferred', 'mainsnak': {'datavalue': {'value': 'UCtsTaylorChannel0000001'}}}]}}
                    elif i == 'Q900002': ents[i] = {'claims': {'P1651': [{'rank': 'normal', 'mainsnak': {'datavalue': {'value': 'ellaSong002'}}}]}}
                    else: ents[i] = {'claims': {}}
                body = json.dumps({'entities': ents})
            else: body = '{}'
            return await r.fulfill(status=200, content_type='application/json', headers={'Access-Control-Allow-Origin': '*'}, body=body)
        if p.netloc == 'www.youtube.com' and p.path.startswith('/embed/'):
            counts['embeds'].append(p.path.split('/')[2])
            return await r.fulfill(status=200, content_type='text/html', body='<!doctype html><body style="background:#111;color:#fff;font:20px sans-serif">VIDEO ' + p.path.split('/')[2] + '</body>')
        return await r.abort()
    await ctx.route('**/*', route)
    await ctx.add_init_script(MOCK); await ctx.add_init_script(AUTO_NOTICE)
    await ctx.add_init_script("try{ localStorage.setItem('radioPlayerTheme', %s); }catch(e){}" % json.dumps(theme))
    pg = await ctx.new_page(); errs = []
    pg.on('pageerror', lambda e: errs.append(str(e)))
    await pg.goto(f'http://127.0.0.1:{PORT}/index.html'); await pg.wait_for_timeout(2500)

    # ---- Home row
    home = await pg.evaluate("""(()=>{ const s = document.getElementById('top100Section'), g = document.getElementById('top100HomeGrid');
      const t = [...g.querySelectorAll('.tile')]; return { shown: s && getComputedStyle(s).display !== 'none', n: t.length,
      first: t[0] ? t[0].querySelector('.tile-name').textContent + ' / ' + (t[0].querySelector('.tile-sub')||{}).textContent : '',
      row: g.classList.contains('home-row') || (g.parentElement && g.parentElement.classList.contains('home-row')),
      before: !!(s && s.nextElementSibling && s.nextElementSibling.id === 'nearMeSection' && s.nextElementSibling.nextElementSibling.id === 'dailyHomeSections' && s.nextElementSibling.nextElementSibling.nextElementSibling.id === 'madeForYouSection') }; })()""")
    print(theme, home)
    check(home['shown'] and home['n'] == 20 and home['first'] == '1. Patient Zero / Taylor Swift', f'{theme}: Home shows a Top 100 row of this week\'s top 20 {home}')
    check(home['before'], f'{theme}: Top 100, then Stations Near Me (build 310), the daily rows (build 219), then Made for You')
    el = await pg.query_selector('#top100Section')
    await el.scroll_into_view_if_needed(); await pg.wait_for_timeout(1800)
    imgs = await pg.evaluate("[...document.querySelectorAll('#top100HomeGrid .tile-art img')].map(i => i.src).slice(0, 3)")
    check(len(imgs) >= 2 and all(u.endswith('/500.jpg') and '/999/' not in u for u in imgs), f'{theme}: covers come from Deezer (the studio version, not a live one) {imgs[:2]}')
    await el.screenshot(path=f'{OUT}/top100-home-{theme}.png')

    await pg.wait_for_timeout(14000)
    pre = await pg.evaluate("__h.ev('Object.keys(songArt).length')")
    check(pre >= 95, f'{theme}: this week\'s covers are fetched in the background from Home, before the page is opened ({pre})')
    # ---- a chart song that's in the library: its own cover
    await pg.evaluate("""__h.ev("libraryTracks.push({ type: 'local', localId: 'lib-song-009', name: 'Song 009', artist: 'Sabrina Carpenter', album: '' }); setCustomArtUrl('lib-song-009', 'https://art.example/9/library.jpg')")""")
    # ---- the page
    await pg.evaluate("document.getElementById('top100Heading').click()"); await pg.wait_for_timeout(1500)
    quick = await pg.evaluate("[...document.querySelectorAll('.chart-row')].slice(0, 7).map(r => { const i = r.querySelector('.tile-art img'); return !i ? 0 : (i.src.indexOf('coverartarchive') >= 0 ? 11 : +i.src.split('/')[3]); })")
    check(quick == [1, 2, 3, 4, 5, 6, 7], f'{theme}: the rows on screen get their covers within a moment {quick}')
    page = await pg.evaluate("""(()=>({ head: document.getElementById('stationsHeading').textContent,
      week: (()=>{ const x = document.querySelector('.chart-week-label'); const c = x.cloneNode(true); c.querySelectorAll('select').forEach(s => s.remove()); document.body.appendChild(c); const t = c.innerText; c.remove(); return t; })(), rows: document.querySelectorAll('.chart-row').length,
      prev: document.querySelectorAll('.chart-week-btn')[0].disabled, next: document.querySelectorAll('.chart-week-btn')[1].disabled,
      moves: document.querySelectorAll('.chart-move').length, more: document.querySelectorAll('.chart-row .row-more-btn, .chart-row button').length }))()""")
    print(theme, page)
    check(page['head'] == 'Top 100' and page['rows'] == 100, f'{theme}: the page lists all 100 {page["head"]} {page["rows"]}')
    check(page['week'].startswith('Week of\nOctober 10, 2026') and 'this week' in page['week'], f'{theme}: "Week of" on its own line, then the date {page["week"]!r}')
    check(not page['prev'] and page['next'], f'{theme}: previous week offered, no next week on the newest chart')
    btns = await pg.evaluate("[...document.querySelectorAll('.chart-week-btn')].map(b => { const r = b.getBoundingClientRect(); return [Math.round(r.width), Math.round(r.height)]; })")
    check(btns == [[40, 40], [40, 40]], f'{theme}: the week arrows are round 40px buttons {btns}')
    check(page['moves'] == 0 and page['more'] == 0, f'{theme}: no chart-movement column and no More button (build 212)')
    geo = await pg.evaluate("""(()=>{ const r = [...document.querySelectorAll('.chart-row')].slice(0, 12), x = r[11] || r[0];
      const k = x.querySelector('.chart-rank').getBoundingClientRect(), a = x.querySelector('.tile-art').getBoundingClientRect(),
            b = x.querySelector('.song-row-body').getBoundingClientRect(), row = x.getBoundingClientRect(), h = document.getElementById('stationsHeading').getBoundingClientRect();
      return { rankLeft: Math.round(k.left), head: Math.round(h.left), rankBeforeArt: k.right <= a.left, gapRankArt: Math.round(a.left - k.right),
               gapArtText: Math.round(b.left - a.right), textW: Math.round(b.width), rowW: Math.round(row.width), textRight: Math.round(row.right - b.right) }; })()""")
    print(theme, geo)
    check(geo['rankBeforeArt'] and abs(geo['rankLeft'] - geo['head']) <= 1, f'{theme}: the rank comes first, on the page edge, then the cover {geo}')
    check(geo['gapRankArt'] <= 12 and geo['gapArtText'] <= 11, f'{theme}: tight gaps between rank, cover and text {geo}')
    check(geo['textRight'] <= 2 and geo['textW'] >= geo['rowW'] - 120, f'{theme}: title and artist get the rest of the row {geo}')
    await pg.wait_for_timeout(1500)
    painted = await pg.evaluate("[...document.querySelectorAll('.chart-row')].slice(0, 6).map(r => { const i = r.querySelector('.tile-art img'); return i ? i.src.split('/')[3] : null; })")
    check(painted == ['1', '2', '3', '4', '5', '6'], f'{theme}: every row on screen has its cover, including ones found on Home {painted}')
    await pg.screenshot(path=f'{OUT}/top100-page-{theme}.png')
    for y in range(0, 9000, 600):
        await pg.evaluate(f"window.scrollTo(0, {y})"); await pg.wait_for_timeout(250)
    await pg.wait_for_timeout(12000)   # Song 050's first ask was refused: Deezer rests 5.6s and asks again
    allp = await pg.evaluate("[...document.querySelectorAll('.chart-row')].map(r => { const i = r.querySelector('.tile-art img'); return !i ? 0 : (i.src.indexOf('coverartarchive') >= 0 ? 11 : +i.src.split('/')[3]); })")
    missing = [i + 1 for i, v in enumerate(allp) if v != i + 1]
    check(not missing, f'{theme}: all 100 rows get their covers, past the first 20 (one that failed is asked again) missing={missing[:8]}')
    lib9 = await pg.evaluate("document.querySelectorAll('.chart-row')[8].querySelector('.tile-art img').src")
    check(lib9.endswith('/9/library.jpg'), f'{theme}: a chart song in the library shows the library\'s cover ({lib9})')
    cover_asks = [t for t in counts.get('iterms', []) if 'Song ' in t or 'Patient Zero' in t]
    check(len(cover_asks) == 2 and counts['mb'] >= 1, f'{theme}: Apple only for what Deezer lacks (2 asks: Song 007 found, Song 011 not), then MusicBrainz ({cover_asks}, {counts["mb"]})')
    check(not await pg.evaluate("__nat.dzQuota || 0"), f'{theme}: Deezer paced under its limit (no quota refusals)')
    diag = await pg.evaluate("__h.ev('songArtStats')")
    print(theme, 'stats', diag)
    check(diag['library'] >= 1 and diag['deezer'] >= 90 and diag['itunes'] == 1 and diag['musicbrainz'] == 1, f'{theme}: the tally adds up {diag}')
    await pg.evaluate("window.scrollTo(0, 0)"); await pg.wait_for_timeout(300)
    hdr = await pg.query_selector('.chart-week')
    await hdr.screenshot(path=f'{OUT}/top100-week-{theme}.png')
    # previous week, then the month, day and year pickers
    await pg.evaluate("document.querySelectorAll('.chart-week-btn')[0].click()"); await pg.wait_for_timeout(900)
    w2 = await pg.evaluate("""(()=>{ const x = document.querySelector('.chart-week-label'); if(!x) return ''; const c = x.cloneNode(true); c.querySelectorAll('select').forEach(s => s.remove()); document.body.appendChild(c); const t = c.innerText; c.remove(); return t; })()""")
    nx2 = await pg.evaluate("document.querySelectorAll('.chart-week-btn')[1].disabled")
    check(w2.startswith('Week of\nOctober 3, 2026') and not nx2, f'{theme}: Previous shows the week before, with Next back ({w2!r})')
    check(any('cdn.jsdelivr.net' in c and '2026-10-03' in c for c in counts['charts']), f'{theme}: past weeks come from the CDN when GitHub\'s raw files fail')
    def pick(cls, value):
        return pg.evaluate(f"(()=>{{ const s = document.querySelector('.cw-seg.{cls} select'); s.value = '{value}'; s.dispatchEvent(new Event('change')); }})()")
    sels = await pg.evaluate("[...document.querySelectorAll('.cw-seg select')].map(s => [s.getAttribute('aria-label'), s.options.length, [...s.options].filter(o => o.disabled).length])")
    check([x[0] for x in sels] == ['Month', 'Week', 'Year'] and sels[0][1] == 12 and sels[0][2] == 9 and sels[1][1] == 2 and sels[2][1] == 2026 - 1958 + 1,
          f'{theme}: month, day and year each open a picker (months without charts greyed, the month\'s chart weeks, every year) {sels}')
    await pick('cw-d', '2026-10-10'); await pg.wait_for_timeout(800)
    check((await pg.evaluate("""(()=>{ const x = document.querySelector('.chart-week-date'); if(!x) return ''; const c = x.cloneNode(true); c.querySelectorAll('select').forEach(s => s.remove()); document.body.appendChild(c); const t = c.innerText; c.remove(); return t; })()""")) == 'October 10, 2026', f'{theme}: picking a day shows that week')
    await pick('cw-m', '9'); await pg.wait_for_timeout(900)
    w3 = await pg.evaluate("""(()=>{ const x = document.querySelector('.chart-week-date'); if(!x) return ''; const c = x.cloneNode(true); c.querySelectorAll('select').forEach(s => s.remove()); document.body.appendChild(c); const t = c.innerText; c.remove(); return t; })()""")
    check(w3 == 'September 26, 2026', f'{theme}: picking a month shows its week closest to the day ({w3!r})')
    await pick('cw-m', '8'); await pg.wait_for_timeout(900)
    check((await pg.evaluate("""(()=>{ const x = document.querySelector('.chart-week-date'); if(!x) return ''; const c = x.cloneNode(true); c.querySelectorAll('select').forEach(s => s.remove()); document.body.appendChild(c); const t = c.innerText; c.remove(); return t; })()""")) == 'August 29, 2026', f'{theme}: and another month')
    await pick('cw-y', '1958'); await pg.wait_for_timeout(900)
    w4 = await pg.evaluate("""(()=>{ const x = document.querySelector('.chart-week-date'); if(!x) return ''; const c = x.cloneNode(true); c.querySelectorAll('select').forEach(s => s.remove()); document.body.appendChild(c); const t = c.innerText; c.remove(); return t; })()""")
    rows4 = await pg.evaluate("document.querySelectorAll('.chart-row').length")
    check(w4 == 'August 4, 1958' and rows4 == 100, f'{theme}: picking a year jumps to that year\'s chart nearest the date ({w4!r})')
    await pick('cw-y', '2026'); await pg.wait_for_timeout(900)
    await pick('cw-m', '10'); await pg.wait_for_timeout(900)
    await pick('cw-d', '2026-10-10'); await pg.wait_for_timeout(900)
    check((await pg.evaluate("""(()=>{ const x = document.querySelector('.chart-week-label'); if(!x) return ''; const c = x.cloneNode(true); c.querySelectorAll('select').forEach(s => s.remove()); document.body.appendChild(c); const t = c.innerText; c.remove(); return t; })()""")).endswith('this week'), f'{theme}: back on this week')

    # ---- build 218: tapping a song. A spinner on its cover while the video is looked up (no "Finding the video")
    spin = await pg.evaluate("""(()=>{ const r = document.querySelectorAll('.chart-row')[0]; r.click();
      return { spinner: !!r.querySelector('.tile-art .chart-art-loading .spinner'), text: document.body.innerText.indexOf('Finding the video') >= 0 }; })()""")
    check(spin['spinner'] and not spin['text'], f'{theme}: a loading spinner on the cover first, no "Finding the video" text {spin}')
    r0 = await pg.query_selector('.chart-row'); await r0.screenshot(path=f'{OUT}/top100-spinner-{theme}.png')
    await pg.wait_for_timeout(2500)
    ov = await pg.evaluate("""(()=>{ const o = document.getElementById('ytOverlay'), f = document.querySelector('#ytOvFrame iframe');
      return { open: !!o && o.classList.contains('open'), src: f ? f.src : '', title: document.getElementById('ytOvTitle').textContent,
        sub: document.getElementById('ytOvSub').textContent, head: (document.querySelector('.yt-ov-list-head')||{}).textContent,
        rows: document.querySelectorAll('.chart-vrow').length, on: (document.querySelector('.chart-vrow.on .chart-vrow-title')||{}).textContent,
        loads: __nat.loads.length, spin: document.querySelectorAll('.chart-art-loading').length }; })()""")
    print(theme, ov)
    check(ov['open'] and '/embed/tsPatient01' in ov['src'] and 'enablejsapi=1' in ov['src'], f'{theme}: #1 plays its official video from the artist\'s channel (not the lyric video) {ov["src"][:70]}')
    check(ov['title'] == 'Patient Zero' and ov['sub'] == 'Taylor Swift · No. 1', f'{theme}: titled with the song, artist and rank {ov["title"]!r} {ov["sub"]!r}')
    check(ov['head'] == 'Top 100 · Week of October 10, 2026' and ov['rows'] == 100 and ov['on'] == 'Patient Zero', f'{theme}: the week\'s chart under it, this song marked')
    check(ov['loads'] == 0 and ov['spin'] == 0, f'{theme}: nothing goes to the audio player; the spinner is gone')
    await pg.wait_for_timeout(1200)
    await pg.screenshot(path=f'{OUT}/top100-video-{theme}.png')
    # ended -> next song; #2 found through Wikidata (P1651)
    fr = [f for f in pg.frames if '/embed/tsPatient01' in f.url][0]
    await fr.evaluate("parent.postMessage(JSON.stringify({ event: 'onStateChange', info: 0 }), '*')"); await pg.wait_for_timeout(2500)
    src2 = await pg.evaluate("(document.querySelector('#ytOvFrame iframe')||{}).src || ''")
    on2 = await pg.evaluate("document.querySelector('.chart-vrow.on .chart-vrow-title').textContent")
    check('/embed/ellaSong002' in src2 and on2 == 'Song 002', f'{theme}: at the end the next song plays (its video from Wikidata) {src2[:60]} {on2}')
    # a video YouTube won't play outside YouTube: the song's preview in Now Playing instead
    fr2 = [f for f in pg.frames if '/embed/ellaSong002' in f.url][0]
    await fr2.evaluate("parent.postMessage(JSON.stringify({ event: 'onError', info: 150 }), '*')"); await pg.wait_for_timeout(1500)
    np = await pg.evaluate("""(()=>{ const s = document.getElementById('nowPlayingScreen'), y = document.getElementById('npYouTubeBtn');
      return { ov: document.getElementById('ytOverlay').classList.contains('open'), np: getComputedStyle(s).display === 'flex',
        name: document.getElementById('npName').textContent, sub: document.getElementById('npSub').textContent,
        yt: !!y && !y.hidden && y.getBoundingClientRect().width > 0, load: __nat.loads[__nat.loads.length - 1] || '',
        note: document.querySelectorAll('.chart-v-note').length, seek: getComputedStyle(document.getElementById('npSeek')).display !== 'none' }; })()""")
    print(theme, np)
    check(not np['ov'] and np['np'] and np['name'] == 'Song 002' and 'preview.example/2-2.mp3' in np['load'] and np['note'] == 0,
          f'{theme}: a video YouTube won\'t play here gives way to the song\'s preview in Now Playing (the studio version) {np}')
    check('Ella Langley' in np['sub'] and '30-Second Preview' in np['sub'] and np['yt'] and np['seek'], f'{theme}: Now Playing says it is a preview, with a seek bar and a YouTube button {np["sub"]!r}')
    await pg.wait_for_timeout(800)
    await pg.screenshot(path=f'{OUT}/top100-preview-{theme}.png')
    await pg.evaluate("window.__opened = []; window.open = function(u, t){ __opened.push([u, t]); return null; }; 0")
    await pg.evaluate("document.getElementById('npYouTubeBtn').click()"); await pg.wait_for_timeout(300)
    opened = await pg.evaluate("__opened")
    check(len(opened) == 1 and opened[0][0].startswith('https://www.youtube.com/results?search_query=') and 'Ella%20Langley%20Song%20002' in opened[0][0] and opened[0][1] == '_blank',
          f'{theme}: the YouTube button searches YouTube for the song\'s video, in a new window {opened}')
    # the preview's end: the next song down the chart, as audio
    await pg.evaluate("__h.ev('togglePlayPause()')"); await pg.wait_for_timeout(400)
    await pg.evaluate("__endSong()"); await pg.wait_for_timeout(1500)
    nxt = await pg.evaluate("({ name: document.getElementById('npName').textContent, load: __nat.loads[__nat.loads.length - 1] || '' })")
    check(nxt['name'] == 'Song 003' and 'preview.example/3-' in nxt['load'], f'{theme}: when the preview ends the next chart song\'s preview plays {nxt}')
    await pg.evaluate("document.getElementById('npBackBtn').click()"); await pg.wait_for_timeout(700)

    # ---- MusicBrainz: Song 003's video recording, linked to YouTube
    await pg.evaluate("document.querySelectorAll('.chart-row')[2].click()"); await pg.wait_for_timeout(5000)
    src3 = await pg.evaluate("(document.querySelector('#ytOverlay.open #ytOvFrame iframe')||{}).src || ''")
    check('/embed/mwSong003vi' in src3, f'{theme}: a video MusicBrainz lists for the song is found {src3[:60]}')
    # MusicBrainz: Song 005's artist's channel (only MusicBrainz names it), its popular uploads
    await pg.evaluate("[...document.querySelectorAll('.chart-vrow')][4].click()"); await pg.wait_for_timeout(300)
    fl = await pg.evaluate("({ spin: !!document.querySelector('#ytOvFrame .chart-v-loading .spinner'), text: document.getElementById('ytOvFrame').innerText })")
    check(fl['spin'] and 'Finding' not in fl['text'], f'{theme}: on the video page, a spinner while the next video is looked up {fl}')
    await pg.wait_for_timeout(6000)
    src5 = await pg.evaluate("(document.querySelector('#ytOverlay.open #ytOvFrame iframe')||{}).src || ''")
    check('/embed/awSong005vi' in src5, f'{theme}: the artist\'s channel as MusicBrainz lists it is searched {src5[:60]}')
    # an older hit: not among the latest uploads, found in the channel's popular uploads
    await pg.evaluate("[...document.querySelectorAll('.chart-vrow')][5].click()"); await pg.wait_for_timeout(2500)
    src6 = await pg.evaluate("(document.querySelector('#ytOvFrame iframe')||{}).src || ''")
    check('/embed/tsOld006vid' in src6, f'{theme}: an older hit is found among the channel\'s most popular videos {src6[:60]}')
    # found videos are remembered: reopening #1 asks nothing new
    nwiki, nfeeds = len(counts['wiki']), await pg.evaluate("__nat.feeds.length")
    await pg.evaluate("[...document.querySelectorAll('.chart-vrow')][0].click()"); await pg.wait_for_timeout(800)
    check(len(counts['wiki']) == nwiki and await pg.evaluate("__nat.feeds.length") == nfeeds and '/embed/tsPatient01' in await pg.evaluate("document.querySelector('#ytOvFrame iframe').src"),
          f'{theme}: a video found before plays without looking it up again')
    # no video anywhere (Song 004): never a "no video" screen -- its preview plays in Now Playing
    await pg.evaluate("[...document.querySelectorAll('.chart-vrow')][3].click()"); await pg.wait_for_timeout(7000)
    nv = await pg.evaluate("""({ ov: document.getElementById('ytOverlay').classList.contains('open'), np: getComputedStyle(document.getElementById('nowPlayingScreen')).display === 'flex',
      name: document.getElementById('npName').textContent, load: __nat.loads[__nat.loads.length - 1] || '', text: document.body.innerText,
      q: __h.ev('playQueue.length'), label: __h.ev('queueLabel') })""")
    check(not nv['ov'] and nv['np'] and nv['name'] == 'Song 004' and 'preview.example/4-' in nv['load'], f'{theme}: a song with no video plays its preview in Now Playing {nv["name"]} {nv["load"]}')
    check('No official video' not in nv['text'] and 'Find on YouTube' not in nv['text'] and not await pg.evaluate("document.querySelectorAll('.chart-v-note').length"),
          f'{theme}: never a "No official video found" screen')
    check(nv['q'] == 100 and nv['label'].startswith('Top 100'), f'{theme}: the week\'s chart is the queue {nv["q"]} {nv["label"]!r}')
    sett = await pg.evaluate("document.getElementById('settingsPanel') ? document.getElementById('settingsPanel').innerText : ''")
    check('API key' not in sett and 'YouTube key' not in sett and not await pg.evaluate("!!document.getElementById('youtubeSettingsRow')"), f'{theme}: nothing in Settings about a YouTube key')
    await pg.evaluate("document.getElementById('npBackBtn').click()"); await pg.wait_for_timeout(700)
    # ---- a song in the library: the whole song, in Now Playing
    nl = await pg.evaluate("__nat.loads.length")
    await pg.evaluate("document.querySelectorAll('.chart-row')[8].click()"); await pg.wait_for_timeout(1500)
    lib = await pg.evaluate("""({ ov: document.getElementById('ytOverlay').classList.contains('open'), np: getComputedStyle(document.getElementById('nowPlayingScreen')).display === 'flex',
      cur: __h.ev('currentStation && currentStation.type + ":" + currentStation.localId'), yt: !document.getElementById('npYouTubeBtn').hidden,
      label: __h.ev('queueLabel'), qi: __h.ev('queueIndex'), embeds: document.querySelectorAll('#ytOvFrame iframe').length })""")
    print(theme, lib)
    check(not lib['ov'] and lib['np'] and lib['cur'] == 'local:lib-song-009' and not lib['yt'] and lib['qi'] == 8 and lib['label'].startswith('Top 100'),
          f'{theme}: a chart song in the library plays the whole song from the library, in Now Playing {lib}')
    await pg.evaluate("document.getElementById('npBackBtn').click()"); await pg.wait_for_timeout(700)
    # Home's row: the spinner there too
    await pg.evaluate("document.getElementById('homeBtn') && document.getElementById('homeBtn').click()")
    check(not errs, f'{theme}: no page errors {errs[:2]}')
    await ctx.close()

async def main():
    async with async_playwright() as pw:
        b = await pw.chromium.launch()
        for theme in ['dark', 'light']:
            await run(theme, b)
        await b.close()
asyncio.run(main())
print('ALL PASS' if not fails else 'FAILS: %d' % len(fails))
sys.exit(1 if fails else 0)
