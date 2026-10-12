"""Build 211: Top 100. Home row of this week's Billboard Hot 100; the page week by week (previous/next,
movement, the date picker); covers from iTunes; Spotify set-up in Settings; songs found with Spotify's
search and played through the plugin's spotify: route, Next down the chart, the end of a song playing the
next. The chart files, iTunes, Spotify's API and the native plugin are all mocked.
Run: python3 tests/test_top100.py (screenshots in /tmp/claude-0/t/shots)"""
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
CHARTS = {'2026-10-10': chart('2026-10-10', 0), '2026-10-03': chart('2026-10-03', 4), '2026-09-26': chart('2026-09-26', 2)}
DATES = ['1958-08-04', '2026-09-26', '2026-10-03', '2026-10-10']
COLORS = ['#e0457b', '#3a7bd5', '#f59e0b', '#10b981', '#8b5cf6']

def art_svg(i):
    return ('<svg xmlns="http://www.w3.org/2000/svg" width="600" height="600"><rect width="600" height="600" fill="%s"/>'
            '<text x="300" y="350" font-size="160" text-anchor="middle" fill="white" font-family="sans-serif">%d</text></svg>') % (COLORS[i % 5], i)

MOCK = r"""(function(){
 var L = {}; window.__nat = { next: [], loads: [], signIns: 0, clientId: '', signedIn: false, plays: 0, pauses: 0 };
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
  spotifyStatus: function(){ return Promise.resolve({ clientId: __nat.clientId, signedIn: __nat.signedIn, installed: true, connected: false, redirectUri: 'amplify-spotify://callback' }); },
  spotifySetClientId: function(o){ __nat.clientId = o.clientId; __nat.signedIn = false; return impl.spotifyStatus(); },
  spotifySignIn: function(){ __nat.signIns++; return Promise.resolve({}); },
  spotifySignOut: function(){ __nat.signedIn = false; return impl.spotifyStatus(); },
  spotifySetNext: function(o){ __nat.next = o.items; return Promise.resolve({}); },
  spotifyToken: function(){ return __nat.signedIn ? Promise.resolve({ token: 'TOK123' }) : Promise.reject(new Error('Not signed in to Spotify')); }
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
    counts = {'itunes': 0, 'spotify': [], 'charts': []}
    async def route(r):
        u = r.request.url
        if '127.0.0.1' in u or u.startswith('data:'):
            return await r.continue_()
        p = urlparse(u)
        if p.netloc == 'raw.githubusercontent.com':
            counts['charts'].append(p.path)
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
            m = re.search(r'Song (\d+)|Patient Zero', term)
            n = int(m.group(1)) if m and m.group(1) else 1
            title = 'Patient Zero' if n == 1 else f'Song {n:03d}'
            artist = ARTISTS[(n - 1) % 5].split(' Featuring ')[0]
            res = {'resultCount': 1, 'results': [{'trackName': title, 'artistName': artist, 'artworkUrl100': f'https://art.example/{n}/100x100bb.jpg'}]}
            return await r.fulfill(status=200, content_type='text/javascript', body=f'{cb}({json.dumps(res)});')
        if p.netloc == 'art.example':
            n = int(p.path.split('/')[1])
            return await r.fulfill(status=200, content_type='image/svg+xml', body=art_svg(n))
        if p.netloc == 'api.spotify.com':
            counts['spotify'].append((parse_qs(p.query).get('q', [''])[0], r.request.headers.get('authorization')))
            q = parse_qs(p.query)['q'][0]
            m = re.search(r'Song (\d+)|Patient Zero', q)
            n = int(m.group(1)) if m and m.group(1) else 1
            title = 'Patient Zero' if n == 1 else f'Song {n:03d}'
            artist = ARTISTS[(n - 1) % 5].split(' Featuring ')[0]
            items = [{'name': title + ' - Remix', 'uri': f'spotify:track:remix{n}', 'artists': [{'name': artist}], 'album': {'images': []}},
                     {'name': title, 'uri': f'spotify:track:t{n}', 'artists': [{'name': artist}], 'album': {'images': [{'url': f'https://art.example/{n}/640.jpg'}]}}]
            return await r.fulfill(status=200, content_type='application/json', headers={'Access-Control-Allow-Origin': '*'}, body=json.dumps({'tracks': {'items': items}}))
        return await r.abort()
    await ctx.route('**/*', route)
    await ctx.add_init_script(MOCK)
    await ctx.add_init_script("try{ localStorage.setItem('radioPlayerTheme', %s); }catch(e){}" % json.dumps(theme))
    pg = await ctx.new_page(); errs = []
    pg.on('pageerror', lambda e: errs.append(str(e)))
    await pg.goto(f'http://127.0.0.1:{PORT}/index.html'); await pg.wait_for_timeout(2500)

    # ---- Home row
    home = await pg.evaluate("""(()=>{ const s = document.getElementById('top100Section'), g = document.getElementById('top100HomeGrid');
      const t = [...g.querySelectorAll('.tile')]; return { shown: s && getComputedStyle(s).display !== 'none', n: t.length,
      first: t[0] ? t[0].querySelector('.tile-name').textContent + ' / ' + (t[0].querySelector('.tile-sub')||{}).textContent : '',
      row: g.classList.contains('home-row') || (g.parentElement && g.parentElement.classList.contains('home-row')),
      before: !!(s && s.compareDocumentPosition(document.getElementById('madeForYouSection')) & 4) && s.nextElementSibling && s.nextElementSibling.id === 'madeForYouSection' }; })()""")
    print(theme, home)
    check(home['shown'] and home['n'] == 20 and home['first'] == '1. Patient Zero / Taylor Swift', f'{theme}: Home shows a Top 100 row of this week\'s top 20 {home}')
    check(home['before'], f'{theme}: Top 100 sits right above Made for You (which stays right above Top Stations)')
    el = await pg.query_selector('#top100Section')
    await el.scroll_into_view_if_needed(); await pg.wait_for_timeout(1800)
    imgs = await pg.evaluate("[...document.querySelectorAll('#top100HomeGrid .tile-art img')].map(i => i.src).slice(0, 3)")
    check(len(imgs) >= 2 and all('600x600bb' in u for u in imgs), f'{theme}: covers come from iTunes at 600px {imgs[:2]}')
    await el.screenshot(path=f'{OUT}/top100-home-{theme}.png')

    # ---- the page
    await pg.evaluate("document.getElementById('top100Heading').click()"); await pg.wait_for_timeout(1200)
    page = await pg.evaluate("""(()=>({ head: document.getElementById('stationsHeading').textContent,
      week: (document.querySelector('.chart-week-label')||{}).innerText, rows: document.querySelectorAll('.chart-row').length,
      prev: document.querySelectorAll('.chart-week-btn')[0].disabled, next: document.querySelectorAll('.chart-week-btn')[1].disabled,
      moves: [...document.querySelectorAll('.chart-move')].slice(0, 6).map(m => m.textContent),
      notice: (document.querySelector('.chart-notice')||{}).innerText || '' }))()""")
    print(theme, page)
    check(page['head'] == 'Top 100' and page['rows'] == 100, f'{theme}: the page lists all 100 {page["head"]} {page["rows"]}')
    check(page['week'].startswith('Week of October 10, 2026') and 'this week' in page['week'], f'{theme}: headed with the week {page["week"]!r}')
    check(not page['prev'] and page['next'], f'{theme}: previous week offered, no next week on the newest chart')
    check(page['moves'][0] in ('NEW', 'RE') and any(m.startswith('▲') for m in page['moves']) and any(m.startswith('▼') for m in page['moves']) and '–' in page['moves'],
          f'{theme}: movement shown (new, up, down, same) {page["moves"]}')
    check('Set up Spotify' in page['notice'], f'{theme}: says to set up Spotify {page["notice"]!r}')
    await pg.wait_for_timeout(1500)
    painted = await pg.evaluate("[...document.querySelectorAll('.chart-row')].slice(0, 6).map(r => { const i = r.querySelector('.tile-art img'); return i ? i.src.split('/')[3] : null; })")
    edge = await pg.evaluate("""(()=>{ const a = document.querySelector('.chart-row .tile-art').getBoundingClientRect(), n = document.querySelector('.chart-row .song-row-num').getBoundingClientRect(),
       m = document.querySelector('#playerBar .player-icon, #playerIcon').getBoundingClientRect(), h = document.getElementById('stationsHeading').getBoundingClientRect();
       return { art: Math.round(a.left), mini: Math.round(m.left), head: Math.round(h.left), rankAfter: n.left >= a.right }; })()""")
    check(abs(edge['art'] - edge['mini']) <= 1 and abs(edge['head'] - edge['mini']) <= 1 and edge['rankAfter'], f'{theme}: covers on the left margin (mini player art, heading), rank after the cover {edge}')
    check(painted == ['1', '2', '3', '4', '5', '6'], f'{theme}: every row on screen has its cover, including ones found on Home {painted}')
    await pg.screenshot(path=f'{OUT}/top100-page-{theme}.png')
    await pg.evaluate("document.querySelectorAll('.chart-row')[1].click()"); await pg.wait_for_timeout(600)
    sub = await pg.evaluate("document.getElementById('playerSub') ? document.getElementById('playerSub').textContent : ''")
    check('Set up Spotify' in sub and not await pg.evaluate("__nat.loads.length"), f'{theme}: without Spotify a tap explains, nothing loads ({sub!r})')
    # previous week, then the date picker
    await pg.evaluate("document.querySelectorAll('.chart-week-btn')[0].click()"); await pg.wait_for_timeout(900)
    w2 = await pg.evaluate("document.querySelector('.chart-week-label').innerText")
    nx2 = await pg.evaluate("document.querySelectorAll('.chart-week-btn')[1].disabled")
    check(w2.startswith('Week of October 3, 2026') and not nx2, f'{theme}: Previous shows the week before, with Next back ({w2!r})')
    await pg.evaluate("(()=>{ const i = document.querySelector('.chart-date-input'); i.value = '2026-09-30'; i.dispatchEvent(new Event('change')); })()"); await pg.wait_for_timeout(900)
    w3 = await pg.evaluate("document.querySelector('.chart-week-label').innerText")
    check(w3.startswith('Week of September 26, 2026'), f'{theme}: a picked day shows the chart for that week ({w3!r})')
    await pg.evaluate("document.querySelectorAll('.chart-week-btn')[1].click()"); await pg.wait_for_timeout(500)
    await pg.evaluate("document.querySelectorAll('.chart-week-btn')[1].click()"); await pg.wait_for_timeout(700)

    # ---- Settings: set up and sign in
    await pg.evaluate("__h.ev('openSettings()')"); await pg.wait_for_timeout(500)
    st = await pg.evaluate("document.getElementById('spotifySettingsBody').innerText")
    check('amplify-spotify://callback' in st and 'com.markcoleman.amplify' in st and '7E:C7:97' in st, f'{theme}: Settings gives the Spotify app set-up details')
    row = await pg.query_selector('#spotifySettingsRow')
    await row.scroll_into_view_if_needed(); await pg.wait_for_timeout(200)
    await row.screenshot(path=f'{OUT}/top100-settings-{theme}.png')
    await pg.fill('#spotifyClientIdInput', 'abc'); await pg.click('#spotifySaveBtn'); await pg.wait_for_timeout(200)
    check('32 letters' in await pg.evaluate("document.getElementById('spotifySettingsBody').innerText"), f'{theme}: a wrong ID is explained')
    await pg.fill('#spotifyClientIdInput', '0123456789abcdef0123456789abcdef'); await pg.click('#spotifySaveBtn'); await pg.wait_for_timeout(300)
    check(await pg.evaluate("__nat.clientId") == '0123456789abcdef0123456789abcdef' and await pg.evaluate("__nat.signIns") == 1, f'{theme}: Save stores the ID and opens Spotify sign-in')
    await pg.evaluate("__nat.signedIn = true; __emit('spotify', { event: 'auth', ok: true, signedIn: true, clientId: __nat.clientId })"); await pg.wait_for_timeout(300)
    check(await pg.evaluate("document.getElementById('spotifyStatus').textContent") == 'Connected', f'{theme}: signed in shows Connected')
    await row.screenshot(path=f'{OUT}/top100-settings-on-{theme}.png')
    await pg.evaluate("document.getElementById('settingsCloseBtn').click()"); await pg.wait_for_timeout(300)
    check(not await pg.evaluate("!!document.querySelector('.chart-notice')"), f'{theme}: the set-up note leaves the page once signed in')

    # ---- play #2: found on Spotify, played through the spotify: route
    await pg.evaluate("document.querySelectorAll('.chart-row')[1].click()"); await pg.wait_for_timeout(1200)
    loads = await pg.evaluate("__nat.loads")
    q = next((x for x in counts['spotify'] if 'Song 002' in x[0]), ('', ''))
    pre = any('Song 003' in x[0] for x in counts['spotify'])
    check(loads[-1:] == ['spotify:track:t2'], f'{theme}: #2 plays its Spotify song (not the remix) {loads}')
    check(q[1] == 'Bearer TOK123' and 'track:Song 002' in q[0] and 'artist:Ella Langley' in q[0], f'{theme}: found with Spotify search, signed in {q}')
    check(pre, f'{theme}: the next song down the chart is looked up ahead')
    np = await pg.evaluate("""(()=>({ title: document.getElementById('playerName') ? document.getElementById('playerName').textContent : '',
       sub: document.getElementById('playerSub').textContent, playing: document.body.classList.contains('ui-playing'),
       rowPlaying: document.querySelectorAll('.chart-row')[1].classList.contains('playing') }))()""")
    print(theme, np)
    check(np['playing'] and np['rowPlaying'] and 'Ella Langley' in np['sub'], f'{theme}: player bar shows it playing, the row marked {np}')
    await pg.evaluate("__h.ev('openNowPlaying()')"); await pg.wait_for_timeout(900)
    npsub = await pg.evaluate("document.getElementById('npSub').textContent")
    check('No. 2 on the Hot 100' in npsub, f'{theme}: Now Playing says where it charts ({npsub!r})')
    await pg.screenshot(path=f'{OUT}/top100-np-{theme}.png')
    # Next goes down the chart; the end of a song plays the next
    await pg.evaluate("__h.ev('playNextInLine()')"); await pg.wait_for_timeout(1000)
    loads = await pg.evaluate("__nat.loads")
    check(loads[-1:] == ['spotify:track:t3'], f'{theme}: Next plays #3 {loads[-2:]}')
    await pg.evaluate("__endSong()"); await pg.wait_for_timeout(1200)
    loads = await pg.evaluate("__nat.loads")
    check(loads[-1:] == ['spotify:track:t4'], f'{theme}: the end of #3 plays #4 {loads[-2:]}')
    nsearch = len(counts['spotify'])
    await pg.evaluate("__h.ev('playNextInLine()')"); await pg.wait_for_timeout(800)
    check(await pg.evaluate("__nat.loads.slice(-1)[0]") == 'spotify:track:t5', f'{theme}: Next again plays #5')
    # the next few are handed to the native side, which can carry on by itself (locked phone)
    await pg.wait_for_timeout(600)
    nx = await pg.evaluate("__nat.next")
    check([x['uri'] for x in nx] == ['spotify:track:t6', 'spotify:track:t7', 'spotify:track:t8', 'spotify:track:t9'] and nx[0]['key'].startswith('song:'),
          f'{theme}: the next four are handed to the native side {[x["uri"] for x in nx]}')
    nloads = await pg.evaluate("__nat.loads.length")
    await pg.evaluate("__emit('spotifyadvance', { id: __h.ev('audio._id'), key: __nat.next[0].key })"); await pg.wait_for_timeout(800)
    adv = await pg.evaluate("""(()=>({ name: document.getElementById('playerName').textContent, loads: __nat.loads.length,
       row: document.querySelectorAll('.chart-row')[5].classList.contains('playing'), next: __nat.next.map(x => x.uri) }))()""")
    check(adv['name'] == 'Song 006' and adv['loads'] == nloads and adv['row'], f'{theme}: when the native side moves on by itself the page follows, without loading again {adv}')
    check(adv['next'][:1] == ['spotify:track:t7'], f'{theme}: and hands over the following ones {adv["next"]}')
    # pause / resume go to the plugin
    await pg.evaluate("__h.ev('togglePlayPause()')"); await pg.wait_for_timeout(300)
    check(await pg.evaluate("__nat.pauses") >= 1 and not await pg.evaluate("document.body.classList.contains('ui-playing')"), f'{theme}: Pause pauses it')
    await pg.evaluate("__h.ev('togglePlayPause()')"); await pg.wait_for_timeout(300)
    check(await pg.evaluate("__nat.plays") >= 1 and await pg.evaluate("document.body.classList.contains('ui-playing')"), f'{theme}: Play resumes it')
    # a song played before is not searched again
    await pg.evaluate("__h.ev('closeNowPlaying()')"); await pg.wait_for_timeout(400)
    before = len(counts['spotify'])
    await pg.evaluate("document.querySelectorAll('.chart-row')[1].click()"); await pg.wait_for_timeout(800)
    check(len(counts['spotify']) == before and await pg.evaluate("__nat.loads.slice(-1)[0]") == 'spotify:track:t2', f'{theme}: a song found before plays without searching again')
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
