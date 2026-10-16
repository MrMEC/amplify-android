"""Build 210: Library's heading, podcast dates without capitals, smaller cover corners, no counts on the
Favorites / Top Artists / Top Stations / Continue Listening pages, larger Top Artists on Home.
Run: python3 tests/test_b210.py (screenshots in /tmp/claude-0/t/shots)"""
import sys as _nsys, os as _nos; _nsys.path.insert(0, _nos.path.dirname(_nos.path.abspath(__file__))); from notice_auto import AUTO_NOTICE
import asyncio, os, json, threading, http.server, functools, shutil, sys
from playwright.async_api import async_playwright
SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'www', 'index.html'); OUT = '/tmp/claude-0/t/shots'; os.makedirs(OUT, exist_ok=True); PORT = 8807
fails = []
def check(c, m):
    print(('PASS ' if c else 'FAIL ') + m)
    if not c: fails.append(m)
root = '/tmp/claude-0/t/srv_b210'; shutil.rmtree(root, ignore_errors=True); os.makedirs(root)
HOOK = "window.__r = { play: function(i){ var s = JSON.parse(localStorage.getItem('radioPlayerFavorites'))[i]; playStation(s); }, ui: function(b){ setPlayingUI(b); }, ev: function(js){ return eval(js); } };\n"
src = open(SRC).read(); mark = '  var coverFlow = null;\n'; assert src.count(mark) == 1
open(root + '/index.html', 'w').write(src.replace(mark, mark + HOOK))
COLS = ['#2b6cb0', '#c05621', '#2f855a', '#6b46c1', '#b83280', '#975a16']
def svg(c, t):
    return 'data:image/svg+xml;utf8,' + ('<svg xmlns="http://www.w3.org/2000/svg" width="200" height="200"><rect width="200" height="200" fill="%s"/><text x="100" y="118" font-size="60" text-anchor="middle" fill="white" font-family="sans-serif">%s</text></svg>' % (c, t)).replace('#', '%23')
ST = [{'stationuuid': 'st-%d' % i, 'name': 'Station %d' % i, 'url': 'http://radio.example/%d' % i, 'url_resolved': 'http://radio.example/%d' % i,
       'urlToResolve': 'http://radio.example/%d' % i, 'favicon': svg(COLS[i], 'S%d' % i), 'country': 'United States', 'tags': 'pop'} for i in range(6)]
# Build 209: covers served slowly (as from a station's site), to catch any colour shown before the cover's own.
import time as _time, io as _io
from PIL import Image as _Image
def png_of(hexcol):
    b = _io.BytesIO(); _Image.new('RGB', (200, 200), hexcol).save(b, 'PNG'); return b.getvalue()
SVG_SLOW = {'pink': '#b83280', 'grey': '#808080'}
ST.append({'stationuuid': 'st-slow', 'name': 'Slow Pink', 'url': 'http://radio.example/sp', 'url_resolved': 'http://radio.example/sp', 'urlToResolve': 'http://radio.example/sp', 'favicon': 'https://covers.example/slow/pink.png', 'country': 'United States', 'tags': 'pop'})
ST.append({'stationuuid': 'st-grey', 'name': 'Grey', 'url': 'http://radio.example/gr', 'url_resolved': 'http://radio.example/gr', 'urlToResolve': 'http://radio.example/gr', 'favicon': 'https://covers.example/slow/grey.png', 'country': 'United States', 'tags': 'pop'})
class Q(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a): pass
    def do_GET(self):
        if self.path.startswith('/slow/'):
            name = self.path.split('/')[2].split('.')[0]
            _time.sleep(0.9)
            body = ('<svg xmlns="http://www.w3.org/2000/svg" width="200" height="200"><rect width="200" height="200" fill="%s"/></svg>' % SVG_SLOW.get(name, '#808080')).encode()
            self.send_response(200); self.send_header('Content-Type', 'image/svg+xml'); self.send_header('Content-Length', str(len(body))); self.end_headers(); self.wfile.write(body); return
        return super().do_GET()
srv = http.server.ThreadingHTTPServer(('127.0.0.1', PORT), functools.partial(Q, directory=root))
threading.Thread(target=srv.serve_forever, daemon=True).start()
MOCK = """(function(){ var L = {}; var impl = {
 addListener: function(n, f){ (L[n] = L[n] || []).push(f); return Promise.resolve({remove:function(){}}); },
 load: function(o){ setTimeout(function(){ (L.state||[]).forEach(function(f){ f({ state: o.play ? 'playing' : 'paused', playing: !!o.play, id: o.id }); }); }, 50); return Promise.resolve({}); } };
 var P = new Proxy({}, {get:function(t,k){ if(k==='then') return undefined; if(k==='setCarLibraryPart') return undefined; if(impl[k]) return impl[k]; return function(){ return Promise.resolve({}); }; }});
 window.Capacitor = { isNativePlatform:function(){return true;}, getPlatform:function(){return 'android';}, registerPlugin:function(){ return P; }, Plugins:{AmplifyPlayer:P, CapacitorHttp:{ request: function(o){ return fetch(o.url).then(function(r){ return r.blob().then(function(b){ return new Promise(function(res){ var fr = new FileReader(); fr.onload = function(){ res({ status: r.status, data: String(fr.result).replace(/^data:[^,]*,/, '') }); }; fr.readAsDataURL(b); }); }); }); } }}, convertFileSrc:function(u){return u;} };
})();"""

def ep(cid, show, title, date, dur):
    return {'type': 'podcast', 'guid': f'g-{cid}', 'name': title, 'collectionId': cid, 'collectionName': show,
            'releaseDate': date, 'duration': dur, 'episodeUrl': f'https://pod.example/{cid}.mp3', 'artworkUrl': ''}
SUBS = [{'collectionId': i, 'collectionName': n, 'artistName': 'Host', 'artworkUrl': '', 'feedUrl': f'https://pod.example/{i}',
         'latestEpisode': ep(i, n, t, d, 1800)} for i, n, t, d in [(1, 'Morning Show', 'Monday news', '2026-10-08T10:00:00Z'), (2, 'Weekly', 'The weekly wrap', '2026-10-02T12:00:00Z')]]
COUNT_HIDDEN = "(function(){ var e = document.getElementById('resultCount'); return !e || getComputedStyle(e).display === 'none' || !e.textContent.trim(); })()"
async def main():
    async with async_playwright() as pw:
        b = await pw.chromium.launch()
        for theme in ['dark', 'light']:
            ctx = await b.new_context(viewport={'width': 412, 'height': 900}, device_scale_factor=2, is_mobile=True, has_touch=True, locale='en-US')
            await ctx.route('**/*', lambda r: r.continue_() if '127.0.0.1' in r.request.url or r.request.url.startswith('data:') else r.abort())
            await ctx.add_init_script(MOCK); await ctx.add_init_script(AUTO_NOTICE)
            await ctx.add_init_script("try{ localStorage.setItem('radioPlayerFavorites', %s); localStorage.setItem('radioPlayerRecent', %s); localStorage.setItem('radioPlayerTheme', %s); localStorage.setItem('radioPlayerPodcastSubs', %s); localStorage.setItem('radioPlayerArtistPlays', JSON.stringify({madonna:{name:'Madonna',count:9,last:Date.now()},prince:{name:'Prince',count:7,last:Date.now()},adele:{name:'Adele',count:5,last:Date.now()},sade:{name:'Sade',count:4,last:Date.now()},cher:{name:'Cher',count:3,last:Date.now()}})); localStorage.setItem('radioPlayerArtistPlaysReset1','1');}catch(e){}" % (json.dumps(json.dumps(ST[:6])), json.dumps(json.dumps(ST[:5])), json.dumps(theme), json.dumps(json.dumps(SUBS))))
            pg = await ctx.new_page(); errs = []
            pg.on('pageerror', lambda e: errs.append(str(e)))
            await pg.goto('http://127.0.0.1:%d/index.html' % PORT); await pg.wait_for_timeout(2500)
            await pg.evaluate("__r.ev('renderTopArtistsSection(); renderRecentSection()')"); await pg.wait_for_timeout(500)
            g = await pg.evaluate("""(()=>{ const t = document.querySelector('#topArtistsGrid .tile'), a = document.querySelector('#topArtistsGrid .tile-art'),
               c = document.querySelector('.home-row .tile:not(.fav-card):not([data-entity="artist"]) .tile-art'), f = document.querySelector('.fav-card');
               return { w: t ? Math.round(t.getBoundingClientRect().width) : 0, aw: a ? Math.round(a.getBoundingClientRect().width) : 0,
                 cr: c ? getComputedStyle(c).borderTopLeftRadius : '', fr: f ? getComputedStyle(f).borderTopLeftRadius : '' }; })()""")
            print(theme, g)
            check(76 <= g['w'] <= 86, f'{theme}: Top Artists portraits a little larger at 412px (was 69px) {g["w"]}')
            check(g['cr'] == '8.5px' and g['fr'] == '9.5px', f'{theme}: covers have smaller corners (8.5px, was 14; Favorites cards 9.5, was 16) {g}')
            el = await pg.query_selector('#topArtistsSection')
            if el:
                await el.scroll_into_view_if_needed(); await pg.wait_for_timeout(200)
            await pg.evaluate("window.scrollTo(0,0)"); await pg.wait_for_timeout(200)
            await pg.screenshot(path=f'{OUT}/b210-home-{theme}.png', full_page=False)
            for sec, label in [('favorites', 'Favorites'), ('topArtists', 'Top Artists'), ('topStations', 'Top Stations'), ('recentStations', 'Continue Listening')]:
                await pg.evaluate(f"__r.ev(\"openHomeSectionPage('{sec}')\")"); await pg.wait_for_timeout(1200)
                hid = await pg.evaluate(COUNT_HIDDEN)
                txt = await pg.evaluate("(document.getElementById('resultCount')||{}).textContent || ''")
                check(hid, f'{theme}: no count on the {label} page ({txt!r})')
                await pg.screenshot(path=f'{OUT}/b210-{sec}-{theme}.png')
            await pg.evaluate("document.querySelector('.mobile-nav-btn[data-nav=podcasts]').click()"); await pg.wait_for_timeout(1500)
            heads = await pg.evaluate("Array.from(document.querySelectorAll('#stationsGrid .podcast-date-heading')).map(function(h){ var c = getComputedStyle(h); return [h.innerText, c.textTransform]; })")
            print(theme, heads)
            check(len(heads) == 2 and all(t == 'none' and v != v.upper() for v, t in heads), f'{theme}: podcast dates not in capitals {heads}')
            await pg.screenshot(path=f'{OUT}/b210-podcasts-{theme}.png')
            check(not errs, f'{theme}: no page errors {errs[:2]}')
            await ctx.close()
        await b.close()
asyncio.run(main())
print('ALL PASS' if not fails else 'FAILS: %d' % len(fails))
sys.exit(1 if fails else 0)
