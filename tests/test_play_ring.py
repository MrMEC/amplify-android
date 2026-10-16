"""Build 207 (208: shades from the playing cover, faster turn, grey Top Artists ring): the playing cover has a thin border in shades of the theme colour (no glow) on Home, the
Favorites page, Shortcuts and the landscape favourites row; it turns while playing and holds when paused.
Run: python3 tests/test_play_ring.py"""
import sys as _nsys, os as _nos; _nsys.path.insert(0, _nos.path.dirname(_nos.path.abspath(__file__))); from notice_auto import AUTO_NOTICE
import asyncio, os, json, threading, http.server, functools, shutil, sys
from playwright.async_api import async_playwright
SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'www', 'index.html'); OUT = '/tmp/claude-0/t/shots'; os.makedirs(OUT, exist_ok=True); PORT = 8806
fails = []
def check(c, m):
    print(('PASS ' if c else 'FAIL ') + m)
    if not c: fails.append(m)
root = '/tmp/claude-0/t/srv_ring'; shutil.rmtree(root, ignore_errors=True); os.makedirs(root)
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
async def main():
    async with async_playwright() as pw:
        b = await pw.chromium.launch()
        for theme in ['dark', 'light']:
            ctx = await b.new_context(viewport={'width': 412, 'height': 900}, device_scale_factor=2, is_mobile=True, has_touch=True)
            await ctx.route('**/*', lambda r: r.continue_() if '127.0.0.1' in r.request.url or r.request.url.startswith('data:') else r.abort())
            async def slow_cover(route):
                name = route.request.url.rsplit('/', 1)[1].split('.')[0]
                await asyncio.sleep(0.9)
                await route.fulfill(status=200, content_type='image/png', headers={'Access-Control-Allow-Origin': '*'}, body=png_of(SVG_SLOW.get(name, '#808080')))
            await ctx.route('https://covers.example/**', slow_cover)
            await ctx.add_init_script(MOCK); await ctx.add_init_script(AUTO_NOTICE)
            await ctx.add_init_script("try{ localStorage.setItem('radioPlayerFavorites', %s); localStorage.setItem('radioPlayerRecent', %s); localStorage.setItem('radioPlayerTheme', %s); localStorage.setItem('radioPlayerArtistPlays', JSON.stringify({madonna:{name:'Madonna',count:9,last:Date.now()},prince:{name:'Prince',count:7,last:Date.now()},adele:{name:'Adele',count:5,last:Date.now()}})); localStorage.setItem('radioPlayerArtistPlaysReset1','1');}catch(e){}" % (json.dumps(json.dumps(ST)), json.dumps(json.dumps(ST[:5])), json.dumps(theme)))
            pg = await ctx.new_page()
            pg.on('pageerror', lambda e: print('PAGEERR', e))
            await pg.goto('http://127.0.0.1:%d/index.html' % PORT); await pg.wait_for_timeout(2500)
            await pg.evaluate("__r.play(1)"); await pg.wait_for_timeout(800)
            await pg.evaluate("__r.ui(true)"); await pg.wait_for_timeout(600)
            base1 = await pg.evaluate("document.body.style.getPropertyValue('--ring-base')")
            print(theme, 'ring base for orange cover', base1)
            check(base1.startswith('hsl(') and 10 <= int(base1[4:].split(',')[0]) <= 35, theme + ': ring colour comes from the orange cover')
            dur = await pg.evaluate("[...new Set(document.getAnimations().filter(a=>a.animationName==='amp-ring-turn').map(a=>a.effect.getTiming().duration))].join(',')")
            print('dur', dur); check(str(dur) == '3200', theme + ': ring turns faster (3.2s a turn, was 7s)')
            info = await pg.evaluate("""(() => [...document.querySelectorAll('.playing')].filter(e=>e.getBoundingClientRect().width>0).map(e => { const a = e.querySelector('.tile-art,.row-thumb,.shortcut-art,.vep-thumb') || e; const cs = getComputedStyle(a, '::after'); return { cls: e.className, art: a.className, after: cs.content, anim: cs.animationPlayState, ang: cs.getPropertyValue('--amp-ring-a'), shadow: getComputedStyle(a).boxShadow.slice(0,60) }; }))()""")
            for i in info: print(theme, i)
            check(len(info) >= 2 and all(i['after'] == '""' or 'fav-card' in i['cls'] for i in info), theme + ': every playing cover has its ring')
            check(all('0px 3px 20px' not in i['shadow'] for i in info), theme + ': no coloured glow under the playing cover')
            print('body', await pg.evaluate("document.body.className"))
            print('anims', await pg.evaluate("document.getAnimations().filter(a=>a.animationName==='amp-ring-turn').map(a=>[a.effect.target.className||'', a.effect.pseudoElement, a.playState, a.currentTime|0])"))
            await pg.screenshot(path='%s/ring-home-%s.png' % (OUT, theme))
            await pg.wait_for_timeout(1700)
            el = await pg.query_selector('.tile.playing .tile-art')
            if el: await el.screenshot(path='%s/ring-tile-%s-1.png' % (OUT, theme))
            await pg.wait_for_timeout(1700)
            if el: await el.screenshot(path='%s/ring-tile-%s-2.png' % (OUT, theme))
            a1 = await pg.evaluate("document.getAnimations().filter(a=>a.animationName==='amp-ring-turn').map(a=>a.playState+':'+(a.currentTime|0)).join(',')")
            await pg.evaluate("__r.ui(false)"); await pg.wait_for_timeout(500)
            p1 = await pg.evaluate("document.getAnimations().filter(a=>a.animationName==='amp-ring-turn').map(a=>a.playState+':'+(a.currentTime|0)).join(',')")
            await pg.wait_for_timeout(1200)
            p2 = await pg.evaluate("document.getAnimations().filter(a=>a.animationName==='amp-ring-turn').map(a=>a.playState+':'+(a.currentTime|0)).join(',')")
            print(theme, 'playing', a1, 'paused', p1, p2)
            check('running' in a1 and 'paused' not in a1, theme + ': ring turns while playing')
            check('running' not in p2 and p1 == p2, theme + ': ring holds still when paused')
            await pg.evaluate("__r.ev('renderTopArtistsSection()')"); await pg.wait_for_timeout(300)
            ta = await pg.evaluate("[...document.querySelectorAll('#topArtistsGrid .tile-art')].map(e=>{const c=getComputedStyle(e);return c.borderTopWidth+' '+c.borderTopColor})")
            print(theme, 'top artists', ta[:2])
            want = 'rgb(58, 58, 62)' if theme == 'dark' else 'rgb(209, 209, 214)'
            check(len(ta) >= 3 and all(x.split(' ')[0] in ('1px', '1.5px') and x.endswith(want) for x in ta), theme + ': Top Artists have a thin solid grey ring')
            el = await pg.query_selector('#topArtistsSection')
            if el: await el.screenshot(path='%s/ring-topartists-%s.png' % (OUT, theme))
            await pg.evaluate("__r.play(3)"); await pg.wait_for_timeout(800); await pg.evaluate("__r.ui(true)"); await pg.wait_for_timeout(600)
            base2 = await pg.evaluate("document.body.style.getPropertyValue('--ring-base')")
            print(theme, 'ring base for purple cover', base2)
            check(base2.startswith('hsl(') and 250 <= int(base2[4:].split(',')[0]) <= 285, theme + ': ring colour changes with the new (purple) cover')
            # Build 209: tap a station whose cover arrives late; sample every 30ms. The ring may be hidden while
            # its colour is worked out, but must never show in any colour but the cover's (pink, hue ~322).
            samples = await pg.evaluate("""(async () => { __r.play(6); setTimeout(()=>__r.ui(true), 300); const out = [];
              for(let i = 0; i < 90; i++){ await new Promise(r => setTimeout(r, 30));
                out.push([document.body.classList.contains('ring-ready'), document.body.style.getPropertyValue('--ring-base')]); }
              return out; })()""")
            shown = [b for r, b in samples if r]
            print(theme, 'slow cover: first shown', shown[:1], 'hidden samples', sum(1 for r, b in samples if not r))
            check(len(shown) > 0 and all(b.startswith('hsl(') and 300 <= int(b[4:].split(',')[0]) <= 340 for b in shown), theme + ': slow cover never shows the old or theme colours, only its own')
            check(not samples[0][0], theme + ': ring hidden straight after tapping a cover whose colour is not known yet')
            # Screenshots of the hand-over on a fresh slow cover (cache cleared): during the wait, and after.
            await pg.evaluate("__r.play(1)"); await pg.wait_for_timeout(500)
            await pg.evaluate("__r.ev('for (var k in ringTintCache) delete ringTintCache[k]'); __r.play(6)")
            for n, ms in enumerate([150, 700, 1500, 2600]):
                await pg.wait_for_timeout(ms - ([0, 150, 700, 1500][n]))
                e3 = await pg.query_selector('.fav-card.playing')
                if e3: await e3.screenshot(path='%s/ring-slow-%s-%d.png' % (OUT, theme, ms))
            # A colourless (grey) cover: the theme colour is the fallback, shown once known.
            await pg.evaluate("__r.play(7)"); await pg.wait_for_timeout(2600)
            check(await pg.evaluate("document.body.classList.contains('ring-ready') && !document.body.style.getPropertyValue('--ring-base')"), theme + ': grey cover falls back to the theme colours')
            # Back to the orange cover: known already, so it shows at once with no hidden gap.
            r2 = await pg.evaluate("(() => { __r.play(1); return new Promise(r => requestAnimationFrame(() => r([document.body.classList.contains('ring-ready'), document.body.style.getPropertyValue('--ring-base')]))); })()")
            check(r2[0] and r2[1].startswith('hsl(20'), theme + ': a cover seen before shows its colours at once')
            await pg.evaluate("__r.play(3)"); await pg.wait_for_timeout(600)
            await pg.evaluate("window.scrollTo(0,0)"); await pg.wait_for_timeout(300)
            await pg.screenshot(path='%s/ring-home2-%s.png' % (OUT, theme))
            for n, sel in enumerate(['.fav-card.playing', '#recentGrid .tile.playing, .home-row .tile.playing:not(.fav-card)']):
                e2 = await pg.query_selector(sel)
                if e2:
                    await e2.scroll_into_view_if_needed(); await pg.wait_for_timeout(200)
                    await e2.screenshot(path='%s/ring-purple-%s-%d.png' % (OUT, theme, n))
            await pg.evaluate("__r.ui(true)")
            await pg.evaluate("__r.ev(\"pushView(); openHomeSectionPage('favorites')\")"); await pg.wait_for_timeout(900)
            await pg.screenshot(path='%s/ring-favpage-%s.png' % (OUT, theme))
            check(await pg.evaluate("getComputedStyle(document.querySelector('.row-item.playing .row-thumb'),'::after').content") == '""', theme + ': Favorites page row has the ring')
            await pg.evaluate("__r.ev(\"openDrawer(); setDrawerTab('shortcuts')\")"); await pg.wait_for_timeout(900)
            await pg.screenshot(path='%s/ring-drawer-%s.png' % (OUT, theme))
            check(await pg.evaluate("getComputedStyle(document.querySelector('.shortcut.playing .shortcut-art'),'::after').content") == '""', theme + ': shortcut has the ring')
            await pg.evaluate("__r.ev('closeDrawer()')"); await pg.wait_for_timeout(400)
            await pg.set_viewport_size({'width': 844, 'height': 390}); await pg.wait_for_timeout(1200)
            t = await pg.query_selector('#npLandToggle')
            if t:
                try: await t.click(timeout=2000)
                except Exception as e: print('toggle', e)
            await pg.wait_for_timeout(900)
            await pg.screenshot(path='%s/ring-land-%s.png' % (OUT, theme))
            check(await pg.evaluate("(()=>{const e=document.querySelector('.np-land-fav.playing'); return e ? getComputedStyle(e,'::after').backgroundImage.indexOf('conic') >= 0 : false})()"), theme + ': landscape favourite has the ring')
            await ctx.close()
        await b.close()
asyncio.run(main())
print('ALL PASS' if not fails else 'FAILS: %d' % len(fails))
sys.exit(1 if fails else 0)
