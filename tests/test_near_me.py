"""Build 310: Stations Near Me. A Home row right under Top 100 (up to 20 local stations, sideways, each with its
distance), shown only while location is allowed and the Settings switch is on; its heading opens every local
station grouped by genre A to Z (Other last), stations A to Z in each, with genre pills that show one genre.
Local = within 50 miles, widened to 100 when fewer than 8 are that close. The plugin (permission, position),
the reverse geocoder and the station directory are mocked.
Run: python3 tests/test_near_me.py (screenshots in /tmp/claude-0/t/shots)"""
import asyncio, os, json, threading, http.server, functools, shutil, math, re
from urllib.parse import urlparse, parse_qs
from playwright.async_api import async_playwright

PORT = 8810
root = '/tmp/claude-0/t/srv_nearme'
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

HOME = (28.549, -81.773)   # Clermont
def offset(lat, lon, miles, bearing):
    R = 3958.8; d = miles / R; b = math.radians(bearing); la1 = math.radians(lat); lo1 = math.radians(lon)
    la2 = math.asin(math.sin(la1) * math.cos(d) + math.cos(la1) * math.sin(d) * math.cos(b))
    lo2 = lo1 + math.atan2(math.sin(b) * math.sin(d) * math.cos(la1), math.cos(d) - math.sin(la1) * math.sin(la2))
    return math.degrees(la2), math.degrees(lo2)

TAGS = ['country,new country', 'news,talk', 'classic rock,rock', 'top 40,pop,hits', 'christian,ccm', 'jazz,smooth jazz',
        'hip hop,rap', 'npr,public radio,news', 'latin,spanish,tropical', 'adult contemporary,soft rock', 'sports,espn',
        'oldies,60s,70s', 'alternative,indie', 'classical', 'something odd']
NAMES = ['Zeta', 'Alpha', 'The Beacon', 'Mango', 'Kite', 'Orbit', 'Delta', 'Harbor', 'Lumen', 'Quartz', 'Echo', 'Nova',
         'Bravo', 'Indigo', 'Juniper', 'Falcon', 'Garnet', 'Pioneer', 'Raven', 'Summit']
def st(uuid, name, tags, lat, lon, clicks, state='Florida', cc='US'):
    return {'stationuuid': uuid, 'name': name, 'url': 'http://s.example/' + uuid, 'url_resolved': 'http://s.example/' + uuid,
            'favicon': '', 'homepage': '', 'tags': tags, 'country': 'The United States Of America', 'countrycode': cc,
            'state': state, 'codec': 'MP3', 'bitrate': 128, 'clickcount': clicks, 'votes': clicks // 3,
            'geo_lat': lat, 'geo_long': lon}

def florida(dense=True):
    out = []
    n = 40 if dense else 5
    for i in range(n):
        miles = 2 + (i * 1.13) % 46          # 2..48 miles
        la, lo = offset(HOME[0], HOME[1], miles, (i * 47) % 360)
        out.append(st('fl%02d' % i, '%s %d FM' % (NAMES[i % 20], 90 + i), TAGS[i % len(TAGS)], la, lo, 500 - i * 7))
    # 50-100 miles out: only used when the close ones are too few.
    for i in range(12):
        la, lo = offset(HOME[0], HOME[1], 60 + i * 3, (i * 30 + 10) % 360)
        out.append(st('far%02d' % i, 'Far %s' % NAMES[i], TAGS[(i + 3) % len(TAGS)], la, lo, 900))
    # No place in the directory, and a bogus 0,0 one.
    for i in range(3):
        out.append(st('np%02d' % i, 'Nowhere %d' % i, 'pop', None, None, 9999))
    out.append(st('zero', 'Zero Island', 'pop', 0, 0, 9999))
    return out
GEORGIA = [st('ga01', 'Atlanta Hits', 'top 40', 33.75, -84.39, 5000, state='Georgia')]
# Build 313: entries with no map position, placed by a city in their name or tags.
FL_CODE = [st('sunny', 'Sunny 105.9', 'adult contemporary,orlando', None, None, 5, state='FL')]          # state as "FL"
FL_CITY = [st('wdbo', 'News 96.5 WDBO Orlando', 'news,talk', None, None, 4)]                             # "Florida", no position
BLANK = [st('blank', 'La Rumba 99', 'latin,kissimmee', None, None, 3, state=''),                          # no state: tag search
         st('ohio', 'Orlando Ohio Hits', 'pop', None, None, 3, state='Ohio')]                               # another state: left out
CITY_ROWS = {'sunny': 'Orlando', 'wdbo': 'Orlando', 'blank': 'Kissimmee'}
CITIES = [('Orlando', 28.5384, -81.3789, 'city', '307573'), ('Kissimmee', 28.2920, -81.4076, 'city', '79226'),
          ('Tampa', 27.9506, -82.4572, 'city', '384959'), ('Clermont', 28.5494, -81.7729, 'town', '43021'),
          ('Christmas', 28.5361, -81.0181, 'town', '')]

MOCK = r"""(function(){
 var L = {}; window.__nat = { loads: [], locCalls: 0, reqCalls: 0, settings: 0 };
 window.__loc = { state: 'prompt', grantOnAsk: true, lat: 28.549, lon: -81.773 };
 try{ var keep = JSON.parse(localStorage.getItem('__locTest') || 'null'); if(keep) window.__loc = keep; }catch(e){}
 function emit(n, ev){ (L[n] || []).forEach(function(f){ f(ev); }); }
 var cur = null;
 var impl = {
  addListener: function(n, f){ (L[n] = L[n] || []).push(f); return Promise.resolve({ remove: function(){} }); },
  load: function(o){ __nat.loads.push(o.url); cur = { id: o.id };
    setTimeout(function(){ emit('state', { id: o.id, state: 'ready', isPlaying: !!o.play, playWhenReady: !!o.play, duration: -1, position: 0 }); }, 60);
    return Promise.resolve({}); },
  setCarCatalog: function(o){ window.__cat = JSON.parse(o.json); return Promise.resolve({}); },
  locationAccess: function(){ return Promise.resolve({ state: __loc.state }); },
  requestLocationAccess: function(){ __nat.reqCalls++; if(__loc.state !== 'granted') __loc.state = __loc.grantOnAsk ? 'granted' : 'denied';
    return Promise.resolve({ state: __loc.state }); },
  getLocation: function(){ __nat.locCalls++; if(__loc.state !== 'granted') return Promise.reject({ code: 'DENIED' });
    return Promise.resolve({ lat: __loc.lat, lon: __loc.lon, accuracy: 2000, at: Date.now() }); },
  openAppSettings: function(){ __nat.settings++; return Promise.resolve({}); }
 };
 var P = new Proxy({}, { get: function(t, k){ if(k === 'then') return undefined; if(k === 'setCarLibraryPart') return undefined; if(impl[k]) return impl[k]; return function(){ return Promise.resolve({}); }; } });
 window.Capacitor = { isNativePlatform: function(){ return true; }, getPlatform: function(){ return 'android'; }, registerPlugin: function(){ return P; }, Plugins: { AmplifyPlayer: P }, convertFileSrc: function(u){ return u; } };
})();"""

fails = []
def check(c, m):
    print(('PASS ' if c else 'FAIL ') + m)
    if not c: fails.append(m)

def mi(a, b):
    R = 3958.8; la1, lo1, la2, lo2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    h = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    return 2 * R * math.asin(min(1, math.sqrt(h)))

async def context(b, dense=True, loc=None, width=412, scale=None):
    ctx = await b.new_context(viewport={'width': width, 'height': 900}, device_scale_factor=2, is_mobile=True, has_touch=True, locale='en-US')
    hits = {'geo': [], 'states': []}
    fl = florida(dense)
    async def route(r):
        u = r.request.url; p = urlparse(u)
        if p.netloc.startswith('127.0.0.1') or u.startswith('data:'):
            return await r.continue_()
        if p.netloc.endswith('api.radio-browser.info'):
            q = parse_qs(p.query)
            if 'state' in q:
                hits['states'].append(q['state'][0])
                body = fl if q['state'][0] == 'Florida' else GEORGIA if q['state'][0] == 'Georgia' else []
                if q['state'][0] == 'Florida' and dense: body = body + FL_CITY
                if q['state'][0] == 'FL' and q.get('stateExact') == ['true'] and dense: body = FL_CODE
            elif 'name' in q or 'tag' in q:
                hits.setdefault('names', []).append(('name:' + q['name'][0]) if 'name' in q else ('tag:' + q['tag'][0]))
                w = (q.get('name') or q.get('tag'))[0].lower()
                pool = (FL_CODE + FL_CITY + BLANK) if dense else []
                body = [x for x in pool if w in (x['name'] + ',' + x['tags']).lower()]
            else:
                body = [st('top%d' % i, 'Top %d' % i, 'pop', None, None, 10) for i in range(6)]
            return await r.fulfill(status=200, content_type='application/json', headers={'Access-Control-Allow-Origin': '*'}, body=json.dumps(body))
        if p.netloc == 'overpass-api.de':
            hits.setdefault('overpass', []).append(r.request.post_data or '')
            els = [{'type': 'node', 'lat': c[1], 'lon': c[2], 'tags': {'name': c[0], 'place': c[3], **({'population': c[4]} if c[4] else {})}} for c in CITIES]
            return await r.fulfill(status=200, content_type='application/json', headers={'Access-Control-Allow-Origin': '*'}, body=json.dumps({'elements': els}))
        if p.netloc == 'api.bigdatacloud.net':
            q = parse_qs(p.query); la = float(q['latitude'][0]); lo = float(q['longitude'][0])
            hits['geo'].append((la, lo))
            if lo > -80.4: body = {'countryCode': '', 'principalSubdivision': ''}      # the Atlantic
            elif la > 29.9: body = {'countryCode': 'US', 'principalSubdivision': 'Georgia', 'city': 'Valdosta'}
            else: body = {'countryCode': 'US', 'principalSubdivision': 'Florida', 'city': 'Clermont' if abs(la - HOME[0]) < 0.1 else 'Somewhere'}
            return await r.fulfill(status=200, content_type='application/json', headers={'Access-Control-Allow-Origin': '*'}, body=json.dumps(body))
        return await r.fulfill(status=404, body='')
    await ctx.route('**/*', route)
    init = MOCK
    if loc: init = "localStorage.setItem('__locTest', " + json.dumps(json.dumps(loc)) + ");\n" + MOCK
    await ctx.add_init_script(init)
    if scale:
        await ctx.add_init_script("document.addEventListener('DOMContentLoaded', function(){ var s = document.createElement('style');"
            " s.textContent = '.tile-name,.tile-sub,.song-row-title,.song-row-sub,.near-where,.home-tab,.grid-section-label,.home-heading-link{ zoom:%s; }';"
            " document.head.appendChild(s); });" % scale)
    page = await ctx.new_page()
    errs = []
    page.on('pageerror', lambda e: errs.append(str(e)))
    await page.goto('http://127.0.0.1:%d/index.html' % PORT)
    await page.wait_for_timeout(1500)
    return ctx, page, hits, errs

async def ev(page, js):
    return await page.evaluate('(js) => window.__h.ev(js)', js)

async def turn_on(page):
    await ev(page, 'openSettings()')
    await page.wait_for_timeout(400)
    await page.select_option('#nearMeSelect', 'on')
    await page.wait_for_timeout(1500)
    await ev(page, 'closeSettings && closeSettings()')
    await page.wait_for_timeout(300)

async def main():
    async with async_playwright() as pw:
        b = await pw.chromium.launch()

        # ---- genre sorting rules ----
        ctx, page, hits, errs = await context(b)
        g = await page.evaluate("""() => ['country,new country','news,talk','classic rock,rock','hits','npr,news','rock','soft rock,adult contemporary',
            'smooth jazz','foo,bar',''].map(window.__nearMe.genreOf)""")
        check(g == ['Country', 'News', 'Classic Rock', 'Pop & Top 40', 'Public Radio', 'Rock', 'Adult Contemporary', 'Jazz', 'Other', 'Other'], 'genre of tags: %s' % g)

        # ---- no permission yet: nothing on Home, nothing asked ----
        shown = await page.evaluate("() => getComputedStyle(document.getElementById('nearMeSection')).display")
        check(shown == 'none', 'hidden before location is allowed (%s)' % shown)
        check(not hits['geo'] and not hits['states'], 'no lookups without permission')
        n = await page.evaluate('() => __nat.reqCalls')
        check(n == 0, 'never asks on its own (%d)' % n)
        order = await page.evaluate("() => document.getElementById('nearMeSection').previousElementSibling.id")
        check(order == 'top100Section', 'section sits right under Top 100 (%s)' % order)

        # ---- Settings: On asks, then the row appears ----
        await ev(page, 'openSettings()'); await page.wait_for_timeout(400)
        v = await page.evaluate("() => document.getElementById('nearMeSelect').value")
        check(v == 'off', 'Settings shows Off before permission (%s)' % v)
        await page.screenshot(path=OUT + '/nearme-settings.png')
        await page.select_option('#nearMeSelect', 'on'); await page.wait_for_timeout(1500)
        await ev(page, 'closeSettings && closeSettings()'); await page.wait_for_timeout(400)
        n = await page.evaluate('() => __nat.reqCalls')
        check(n == 1, 'turning it on asked for permission once (%d)' % n)
        info = await page.evaluate("""() => { var s = document.getElementById('nearMeSection'); var g = document.getElementById('nearMeHomeGrid');
            var tiles = Array.from(g.querySelectorAll(':scope > .tile'));
            var r = g.getBoundingClientRect();
            return { disp: getComputedStyle(s).display, n: tiles.length, subs: tiles.map(t => (t.querySelector('.tile-sub')||{}).textContent),
              names: tiles.map(t => t.querySelector('.tile-name').textContent), left: r.left, right: r.right, sw: g.scrollWidth, cw: g.clientWidth,
              row: !!g.parentElement.classList.contains('home-row'), keys: tiles.map(t => t.dataset.key) }; }""")
        check(info['disp'] != 'none', 'shown once allowed')
        check(info['n'] == 20, 'Home row has 20 stations (%d)' % info['n'])
        check(all(re.match(r'^(\d+|< 1) mi$', s or '') for s in info['subs']), 'each shows its distance: %s' % info['subs'][:5])
        check(all(int(s.split()[0]) <= 50 for s in info['subs'] if s and s[0].isdigit()), 'all within 50 miles')
        check(not any(k.startswith('far') or k.startswith('np') or k == 'zero' for k in info['keys']), 'no far, unplaced or 0,0 stations: %s' % [k for k in info['keys'] if not k.startswith('fl')])
        check(info['row'] and info['sw'] > info['cw'] + 100, 'a sideways row that scrolls (%d > %d)' % (info['sw'], info['cw']))
        check(abs(info['left']) < 1 and abs(info['right'] - 412) < 1, 'row runs to both screen edges (%.1f..%.1f)' % (info['left'], info['right']))
        check(info['keys'][0] == 'fl00', 'most popular first (%s)' % info['keys'][0])
        check(sorted(set(hits['states'])) == ['FL', 'Florida', 'GA', 'Georgia'], 'looked up the states around (%s)' % sorted(set(hits['states'])))
        await page.evaluate("() => document.getElementById('nearMeSection').scrollIntoView({ block: 'center' })")
        await page.wait_for_timeout(500)
        await page.screenshot(path=OUT + '/nearme-home.png')
        # Scroll the row with a finger.
        box = await page.evaluate("() => { var r = document.getElementById('nearMeHomeGrid').getBoundingClientRect(); return [r.left, r.top, r.width, r.height]; }")
        cdp = await ctx.new_cdp_session(page)
        y = box[1] + 60
        await cdp.send('Input.dispatchTouchEvent', {'type': 'touchStart', 'touchPoints': [{'x': 300, 'y': y}]})
        for k in range(1, 11):
            await cdp.send('Input.dispatchTouchEvent', {'type': 'touchMove', 'touchPoints': [{'x': 300 - k * 22, 'y': y}]})
            await page.wait_for_timeout(16)
        await cdp.send('Input.dispatchTouchEvent', {'type': 'touchEnd', 'touchPoints': []})
        await page.wait_for_timeout(700)
        sl = await page.evaluate("() => document.getElementById('nearMeHomeGrid').scrollLeft")
        check(sl > 100, 'finger swipe scrolls the row (%d)' % sl)
        await page.evaluate("() => document.getElementById('nearMeHomeGrid').scrollLeft = 0")

        # Tap a tile: it plays.
        await page.tap('#nearMeHomeGrid > .tile:nth-child(2) .tile-art')
        await page.wait_for_timeout(800)
        loads = await page.evaluate('() => __nat.loads')
        check(any('s.example/' in u for u in loads), 'tapping a tile plays it (%s)' % loads[-1:])

        # Car: Stations Near Me, every local station with genre and distance.
        await page.evaluate('() => window.AmplifyPublishCarMenu && window.AmplifyPublishCarMenu()')
        await page.wait_for_timeout(1500)
        car = await page.evaluate("() => (window.__cat && window.__cat.lists && window.__cat.lists.nearMe) || null")
        check(car is not None and len(car) == 43, 'car list has every local station (%s)' % (len(car) if car else car))
        check(car and ' · ' in (car[0].get('sub') or '') and car[0]['sub'].endswith(' mi'), 'car rows say genre and distance (%s)' % (car[0].get('sub') if car else ''))

        # ---- the page ----
        await page.evaluate("() => window.scrollTo(0, 0)")
        await page.evaluate("() => document.getElementById('nearMeHeading').scrollIntoView({ block: 'center' })")
        await page.tap('#nearMeHeading')
        await page.wait_for_timeout(900)
        pg = await page.evaluate("""() => { var g = document.getElementById('stationsGrid');
            var out = { title: document.getElementById('stationsHeading').textContent, where: (g.querySelector('.near-where')||{}).textContent,
              pills: Array.from(g.querySelectorAll('.near-genre-tabs .home-tab')).map(b => b.textContent),
              active: (g.querySelector('.near-genre-tabs .home-tab.active')||{}).textContent, groups: [] };
            var cur = null;
            Array.from(g.children).forEach(function(c){
              if(c.classList.contains('grid-section-label')){ cur = { g: c.textContent, rows: [] }; out.groups.push(cur); }
              else if(c.classList.contains('near-row') && cur) cur.rows.push({ n: c.querySelector('.song-row-title').textContent, s: c.querySelector('.song-row-sub').textContent, k: c.dataset.key, more: !!c.querySelector('.row-more-btn, .song-more-btn, button') });
            });
            return out; }""")
        check(pg['title'] == 'Stations Near Me', 'page title (%s)' % pg['title'])
        check(pg['where'] == 'Near Clermont, Florida · Within 50 miles', 'where line (%s)' % pg['where'])
        gnames = [x['g'] for x in pg['groups']]
        expect = sorted([x for x in gnames if x != 'Other'])
        check(gnames[:-1] == expect and gnames[-1] == 'Other', 'genres A to Z, Other last: %s' % gnames)
        total = sum(len(x['rows']) for x in pg['groups'])
        check(total == 43, 'every local station, no limit (%d)' % total)
        cityrows = {r['k']: r['s'] for x in pg['groups'] for r in x['rows'] if r['k'] in CITY_ROWS}
        check(cityrows == CITY_ROWS, 'no map position: placed by the city in the name or tags, city shown (%s)' % cityrows)
        check(not any(r['k'] == 'ohio' for x in pg['groups'] for r in x['rows']), 'a city name in another state is left out')
        check(any(n == 'tag:kissimmee' for n in hits.get('names', [])) and any(n == 'name:Orlando' for n in hits.get('names', [])), 'asked by city name and tag (%s)' % hits.get('names', [])[:6])
        def key(n): return re.sub(r'[^a-z0-9]+', ' ', re.sub(r'^(the|a|an)\s+', '', n.lower())).strip()
        ok = all([key(r['n']) for r in x['rows']] == sorted(key(r['n']) for r in x['rows']) for x in pg['groups'])
        check(ok, 'stations A to Z within each genre')
        beacon = [r for x in pg['groups'] for r in x['rows'] if r['n'].startswith('The Beacon')]
        check(bool(beacon), 'names kept as they are ("The Beacon")')
        check(pg['pills'][0] == 'All' and pg['pills'][1:] == gnames and pg['active'] == 'All', 'pills: All then the genres (%s)' % pg['pills'][:4])
        check(all(r['more'] for x in pg['groups'] for r in x['rows']), 'each row has its More button')
        await page.screenshot(path=OUT + '/nearme-page.png')
        await page.screenshot(path=OUT + '/nearme-page-full.png', full_page=True)
        # Only the right stations, at the right distances.
        fl = {s['stationuuid']: s for s in florida(True)}
        bad = []
        for x in pg['groups']:
            for r in x['rows']:
                if r['k'] in CITY_ROWS: continue
                s = fl.get(r['k'])
                if not s: bad.append(r['k']); continue
                d = mi(HOME, (s['geo_lat'], s['geo_long']))
                want = '< 1 mi' if d < 1 else '%d mi' % round(d)
                if r['s'] != want: bad.append((r['k'], r['s'], want))
        check(not bad, 'distances right (%s)' % bad[:3])
        # A genre pill shows only that genre.
        country_n = [len(x['rows']) for x in pg['groups'] if x['g'] == 'Country'][0]
        await page.tap('.near-genre-tabs .home-tab[data-genre="Country"]')
        await page.wait_for_timeout(400)
        one = await page.evaluate("""() => { var g = document.getElementById('stationsGrid');
            return { labels: Array.from(g.querySelectorAll('.grid-section-label')).map(x => x.textContent), rows: g.querySelectorAll('.near-row').length,
              active: (g.querySelector('.near-genre-tabs .home-tab.active')||{}).textContent, y: window.scrollY }; }""")
        check(one['labels'] == ['Country'] and one['rows'] == country_n and one['active'] == 'Country', 'Country pill: only Country (%s, %d)' % (one['labels'], one['rows']))
        await page.screenshot(path=OUT + '/nearme-page-country.png')
        pills = await page.evaluate("() => { var t = document.querySelector('.near-genre-tabs'); var r = t.getBoundingClientRect(); return [r.left, r.right, t.scrollWidth > t.clientWidth]; }")
        check(abs(pills[0]) < 1 and abs(pills[1] - 412) < 1 and pills[2], 'pills scroll sideways edge to edge (%s)' % pills)
        await page.tap('.near-genre-tabs .home-tab[data-genre="all"]')
        await page.wait_for_timeout(400)
        n_all = await page.evaluate("() => document.querySelectorAll('#stationsGrid .near-row').length")
        check(n_all == 43, 'All brings everything back (%d)' % n_all)
        # Tap a row: it plays through its genre.
        before = len(await page.evaluate('() => __nat.loads'))
        await page.tap('#stationsGrid .near-row .song-row-title')
        await page.wait_for_timeout(800)
        after = len(await page.evaluate('() => __nat.loads'))
        check(after > before, 'tapping a row plays it')
        # Back to Home.
        await ev(page, "document.getElementById('detailBackBtn').click()")
        await page.wait_for_timeout(700)
        home = await ev(page, "!!onHomeView && getComputedStyle(document.getElementById('nearMeSection')).display !== 'none'")
        check(home, 'Back returns to Home with the row')

        # ---- a reload uses the kept list straight away (no new lookups) ----
        g0, s0 = len(hits['geo']), len(hits['states'])
        await page.evaluate("() => localStorage.setItem('__locTest', JSON.stringify(__loc))")
        await page.reload(); await page.wait_for_timeout(1500)
        n2 = await page.evaluate("() => document.querySelectorAll('#nearMeHomeGrid > .tile').length")
        check(n2 == 20 and len(hits['states']) == s0, 'restart: kept list shown, nothing fetched again (%d, %d new)' % (n2, len(hits['states']) - s0))
        # Moved 30 miles: worked out again.
        await page.evaluate("() => { __loc.lat = 28.98; window.__nearMe.refresh(false); }")
        await page.wait_for_timeout(1500)
        rec = await page.evaluate("() => window.__nearMe.load()")
        check(abs(rec['lat'] - 28.98) < 0.01, 'moving 30 miles works the list out again')
        await page.evaluate("() => { __loc.lat = 28.549; return window.__nearMe.refresh(true); }")
        await page.wait_for_timeout(1500)

        # ---- Station proximity (build 312) ----
        await ev(page, 'openSettings()'); await page.wait_for_timeout(400)
        pr = await page.evaluate("() => { var r = document.getElementById('nearRadiusRow'), s = document.getElementById('nearRadiusSelect');"
            " return { shown: getComputedStyle(r).display !== 'none', v: s.value, opts: Array.from(s.options).map(o => o.textContent),"
            " after: r.previousElementSibling.querySelector('#nearMeSelect') !== null }; }")
        check(pr['shown'] and pr['v'] == '50' and pr['opts'] == ['50 miles', '100 miles', '200 miles'] and pr['after'],
              'Station proximity under Stations Near Me: 50 / 100 / 200 miles, 50 chosen (%s)' % pr)
        await page.evaluate("() => document.getElementById('nearRadiusRow').scrollIntoView({ block: 'center' })")
        await page.wait_for_timeout(300)
        await page.screenshot(path=OUT + '/nearme-proximity.png')
        g1 = len(hits['geo'])
        await page.select_option('#nearRadiusSelect', '100'); await page.wait_for_timeout(1800)
        rec = await page.evaluate("() => window.__nearMe.load()")
        check(rec['radius'] == 100 and rec['want'] == 100 and len(rec['items']) == 55, '100 miles: the 60-93 mile stations join (%s, %d)' % (rec['radius'], len(rec['items'])))
        await page.select_option('#nearRadiusSelect', '200'); await page.wait_for_timeout(1800)
        rec = await page.evaluate("() => window.__nearMe.load()")
        far = max(mi(HOME, p) for p in hits['geo'][g1:]) if len(hits['geo']) > g1 else 0
        check(rec['radius'] == 200 and len(rec['items']) == 55 and far > 190, '200 miles: looks out to 200 (%s, %d, %.0f)' % (rec['radius'], len(rec['items']), far))
        await ev(page, 'closeSettings && closeSettings()'); await page.wait_for_timeout(300)
        await page.reload(); await page.wait_for_timeout(1500)
        v = await page.evaluate("() => document.getElementById('nearRadiusSelect').value")
        check(v == '200', 'proximity kept after a restart (%s)' % v)
        await ev(page, 'openSettings()'); await page.wait_for_timeout(300)
        await page.select_option('#nearRadiusSelect', '50'); await page.wait_for_timeout(1800)
        await ev(page, 'closeSettings && closeSettings()'); await page.wait_for_timeout(300)
        rec = await page.evaluate("() => window.__nearMe.load()")
        check(rec['radius'] == 50 and len(rec['items']) == 43, 'back to 50 miles (%d)' % len(rec['items']))

        # ---- larger text at 412 and 360 wide ----
        for w in (412, 360):
            c2, p2, h2, e2 = await context(b, loc={'state': 'granted', 'grantOnAsk': True, 'lat': 28.549, 'lon': -81.773}, width=w, scale='1.35')
            await p2.wait_for_timeout(1500)
            await p2.evaluate("() => document.getElementById('nearMeSection').scrollIntoView({ block: 'center' })")
            await p2.wait_for_timeout(400)
            await p2.screenshot(path=OUT + '/nearme-home-big-%d.png' % w)
            await p2.tap('#nearMeHeading'); await p2.wait_for_timeout(900)
            await p2.screenshot(path=OUT + '/nearme-page-big-%d.png' % w)
            ov = await p2.evaluate("() => document.documentElement.scrollWidth <= innerWidth + 1")
            check(ov, 'no sideways page scroll at %d with big text' % w)
            check(not e2, 'no page errors at %d (%s)' % (w, e2[:2]))
            await c2.close()

        # ---- turning it off hides it, and the car folder empties ----
        await turn_on(page)  # already on: stays on
        await ev(page, 'openSettings()'); await page.wait_for_timeout(300)
        await page.select_option('#nearMeSelect', 'off'); await page.wait_for_timeout(600)
        await ev(page, 'closeSettings && closeSettings()'); await page.wait_for_timeout(300)
        d = await page.evaluate("() => getComputedStyle(document.getElementById('nearMeSection')).display")
        check(d == 'none', 'Off hides the row (%s)' % d)
        d = await page.evaluate("() => getComputedStyle(document.getElementById('nearRadiusRow')).display")
        check(d == 'none', 'Off hides Station proximity too (%s)' % d)
        await page.evaluate('() => window.AmplifyPublishCarMenu && window.AmplifyPublishCarMenu()'); await page.wait_for_timeout(1200)
        car = await page.evaluate("() => (window.__cat.lists.nearMe || []).length")
        check(car == 0, 'car folder empty when off (%d)' % car)
        await page.reload(); await page.wait_for_timeout(1500)
        d = await page.evaluate("() => getComputedStyle(document.getElementById('nearMeSection')).display")
        check(d == 'none', 'stays off after a restart')
        check(not errs, 'no page errors (%s)' % errs[:2])
        await ctx.close()

        # ---- permission refused ----
        ctx, page, hits, errs = await context(b, loc={'state': 'prompt', 'grantOnAsk': False, 'lat': 28.549, 'lon': -81.773})
        await ev(page, 'openSettings()'); await page.wait_for_timeout(300)
        await page.select_option('#nearMeSelect', 'on'); await page.wait_for_timeout(800)
        nt = await page.evaluate("""() => { var o = document.getElementById('noticeOverlay');
            return { open: o.classList.contains('open'), text: o.textContent, btns: Array.from(o.querySelectorAll('button')).map(b => b.textContent) }; }""")
        check(nt['open'] and 'Open Settings' in nt['btns'], 'refused: a notice offers Open Settings (%s)' % nt['btns'])
        await page.screenshot(path=OUT + '/nearme-denied.png')
        v = await page.evaluate("() => document.getElementById('nearMeSelect').value")
        check(v == 'off', 'switch back to Off (%s)' % v)
        await page.click('#noticeOverlay button:has-text("Open Settings")'); await page.wait_for_timeout(300)
        check(await page.evaluate('() => __nat.settings') == 1, 'Open Settings opens Android settings')
        # Allowed later in Android's settings: back in the app, the row appears.
        await page.evaluate("() => { __loc.state = 'granted'; }")
        await ev(page, 'closeSettings && closeSettings()')
        await page.evaluate("() => window.__nearMe.refresh(false)"); await page.wait_for_timeout(1500)
        n3 = await page.evaluate("() => document.querySelectorAll('#nearMeHomeGrid > .tile').length")
        check(n3 == 20, 'granted outside the app: row appears (%d)' % n3)
        await ctx.close()

        # ---- a sparse area widens to 100 miles ----
        ctx, page, hits, errs = await context(b, dense=False, loc={'state': 'granted', 'grantOnAsk': True, 'lat': 28.549, 'lon': -81.773})
        await page.wait_for_timeout(1500)
        rec = await page.evaluate("() => window.__nearMe.load()")
        n = len(rec['items']) if rec else 0
        check(rec and rec['radius'] == 100 and n == 17, 'fewer than 8 close: widened to 100 miles (%s, %d)' % (rec and rec['radius'], n))
        await page.tap('#nearMeHeading'); await page.wait_for_timeout(800)
        w = await page.evaluate("() => document.querySelector('#stationsGrid .near-where').textContent")
        check(w.endswith('Within 100 miles'), 'page says 100 miles (%s)' % w)
        check(not errs, 'no page errors (%s)' % errs[:2])
        await ctx.close()
        await b.close()
    print('\n%d failures' % len(fails))
    for f in fails: print(' -', f)
    raise SystemExit(1 if fails else 0)

asyncio.run(main())
