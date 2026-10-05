"""Build 138: the Video section is called Watch (circle play icon) in the tab bar and the drawer;
Continue Listening on Podcasts and Continue Watching on Watch are accordions, closed by default.
Run: python3 tests/test_watch_accordions.py (screenshots in /tmp/claude-0/t/shots)"""
import asyncio, json, os, shutil, threading, http.server, functools, sys
from playwright.async_api import async_playwright
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = '/tmp/claude-0/t/srv-acc'; SHOTS = '/tmp/claude-0/t/shots'
shutil.rmtree(ROOT, ignore_errors=True); os.makedirs(ROOT); os.makedirs(SHOTS, exist_ok=True)
HOOK = ("window.__a = { watch: function(){ videoChannels.forEach(function(c){ recordChannelWatch(channelToStation(c)); }); },"
        " pod: function(){ var eps = [1,2,3].map(function(i){ return { guid: 'ep' + i, name: 'Episode ' + i, collectionId: 77, collectionName: 'Show ' + i,"
        "   artistName: 'Host', favicon: '', episodeUrl: 'https://pod.example/' + i + '.mp3', duration: 3600, type: 'podcast' }; });"
        "   return Promise.all(eps.map(function(e, i){ return savePodcastProgress(e, 300 + i * 60, 3600); })); } };\n")
src = open(os.path.join(HERE, '..', 'www', 'index.html')).read()
mark = '  var coverFlow = null;\n'
assert src.count(mark) == 1
open(ROOT + '/index.html', 'w').write(src.replace(mark, mark + HOOK))
H = functools.partial(http.server.SimpleHTTPRequestHandler, directory=ROOT); H.log_message = lambda *a: None
srv = http.server.ThreadingHTTPServer(('127.0.0.1', 8807), H); threading.Thread(target=srv.serve_forever, daemon=True).start()

CH = [{'id': 'iptv:A', 'name': 'ABC News Live', 'url': 'https://abc.example/live.m3u8', 'logo': '', 'country': 'US', 'cats': ['news'], 'catNames': ['News'], 'src': 'iptv', 'addedAt': 1},
      {'id': 'iptv:B', 'name': 'Weather Nation', 'url': 'https://wx.example/live.m3u8', 'logo': '', 'country': 'US', 'cats': ['weather'], 'catNames': ['Weather'], 'src': 'iptv', 'addedAt': 2}]
MOCK = """(function(){ var P=new Proxy({}, {get:function(t,k){ if(k==='then') return undefined;
  if(k==='addListener') return function(){ return Promise.resolve({remove:function(){}}); };
  return function(){ return Promise.resolve({}); }; }});
 window.Capacitor={isNativePlatform:function(){return true;},getPlatform:function(){return 'android';},Plugins:{AmplifyPlayer:P},convertFileSrc:function(u){return u;}};
 if(!localStorage.getItem('radioPlayerVideoChannels')) localStorage.setItem('radioPlayerVideoChannels', %s);
 if(!localStorage.getItem('radioPlayerPodcastSubs')) localStorage.setItem('radioPlayerPodcastSubs', %s); })();""" % (json.dumps(json.dumps(CH)), json.dumps(json.dumps([{'collectionId': 77, 'collectionName': 'Morning Show', 'artistName': 'Host', 'artworkUrl': '', 'feedUrl': 'https://pod.example/feed', 'latestEpisodeDate': '2026-10-01'}])))

fails = []
def check(ok, msg):
    print(('PASS ' if ok else 'FAIL ') + msg)
    if not ok: fails.append(msg)
async def route(r):
    if '127.0.0.1' in r.request.url: return await r.continue_()
    return await r.abort()
ACC = """(id)=>{ var h = document.querySelector('#stationsGrid .acc-head[data-acc="' + id + '"]'); if(!h) return null;
  var row = h.nextElementSibling, ft = row.querySelector('.tile, .vw-tile'), rb = (ft && getComputedStyle(row).display !== 'none') ? ft.getBoundingClientRect() : row.getBoundingClientRect(), hb = h.getBoundingClientRect(), nx = row.nextElementSibling;
  var nb = nx ? nx.getBoundingClientRect() : null;
  return { text: h.textContent.trim(), expanded: h.getAttribute('aria-expanded'), rowShown: getComputedStyle(row).display !== 'none',
    tiles: row.querySelectorAll('.tile, .vw-tile').length, headTop: Math.round(hb.top), headBottom: Math.round(hb.bottom), headH: Math.round(hb.height),
    rowTop: Math.round(rb.top), rowBottom: Math.round(row.getBoundingClientRect().bottom), next: nx ? nx.className : '', nextTop: nb ? Math.round(nb.top) : null,
    chev: !!h.querySelector('.acc-chev'), chevRot: getComputedStyle(h.querySelector('.acc-chev')).transform }; }"""

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
        for theme in ('dark', 'light'):
            ctx = await b.new_context(viewport={'width': 412, 'height': 900}, device_scale_factor=2, is_mobile=True, has_touch=True, color_scheme=theme, locale='en-US')
            await ctx.add_init_script(MOCK)
            if theme == 'light': await ctx.add_init_script("localStorage.setItem('radioPlayerTheme','light')")
            pg = await ctx.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
            await pg.route('**/*', route)
            await pg.goto('http://127.0.0.1:8807/index.html'); await pg.wait_for_timeout(2200)

            nav = await pg.evaluate("""(()=>{ var b = document.querySelector('.mobile-nav-btn[data-nav=video]'); return { label: b.querySelector('span').textContent, aria: b.getAttribute('aria-label'),
              circle: !!b.querySelector('svg circle'), drawer: document.getElementById('videoHeading').textContent.trim() }; })()""")
            check(nav == {'label': 'Watch', 'aria': 'Watch', 'circle': True, 'drawer': 'Watch'}, f'[{theme}] tab bar and drawer say Watch with a circle play icon {nav}')

            # ---- Watch: Continue Watching ----
            await pg.evaluate('__a.watch()'); await pg.wait_for_timeout(200)
            await pg.evaluate("document.querySelector('.mobile-nav-btn[data-nav=video]').click()"); await pg.wait_for_timeout(800)
            head = await pg.evaluate("document.getElementById('stationsHeading').textContent")
            check(head == 'Watch', f'[{theme}] page heading reads Watch ({head})')
            a = await pg.evaluate(ACC, 'watchContinue')
            print(a)
            check(a and a['expanded'] == 'false' and not a['rowShown'] and a['chev'], f'[{theme}] Continue Watching closed by default {a}')
            check(a and a['text'].startswith('Continue Watching') and a['text'].endswith('2'), f'[{theme}] heading shows the count')
            check(a and a['headH'] >= 40, f'[{theme}] heading is a comfortable tap target ({a and a["headH"]}px)')
            gap_closed = a['nextTop'] - a['headBottom'] if a else None
            await pg.screenshot(path=f'{SHOTS}/acc-watch-closed-{theme}.png')
            await pg.evaluate("document.querySelector('.acc-head[data-acc=watchContinue]').click()"); await pg.wait_for_timeout(400)
            a2 = await pg.evaluate(ACC, 'watchContinue')
            print(a2)
            check(a2['expanded'] == 'true' and a2['rowShown'] and a2['tiles'] == 2, f'[{theme}] tapping opens it: both channels {a2}')
            check(a2['rowTop'] - a2['headBottom'] >= 8, f'[{theme}] row starts clear of the heading ({a2["rowTop"] - a2["headBottom"]}px)')
            check(a2['nextTop'] - a2['rowBottom'] >= 8, f'[{theme}] room under the open row ({a2["nextTop"] - a2["rowBottom"]}px)')
            check(gap_closed is not None and 8 <= gap_closed <= 40, f'[{theme}] closed: tidy gap to the tabs ({gap_closed}px)')
            await pg.screenshot(path=f'{SHOTS}/acc-watch-open-{theme}.png')
            # a redraw keeps it open
            await pg.evaluate("document.querySelector('.video-tabs [data-vtab=movies]').click()"); await pg.wait_for_timeout(300)
            await pg.evaluate("document.querySelector('.video-tabs [data-vtab=channels]').click()"); await pg.wait_for_timeout(300)
            a3 = await pg.evaluate(ACC, 'watchContinue')
            check(a3['expanded'] == 'true' and a3['rowShown'], f'[{theme}] stays open across a redraw')
            await pg.evaluate("document.querySelector('.acc-head[data-acc=watchContinue]').click()"); await pg.wait_for_timeout(300)
            check(not (await pg.evaluate(ACC, 'watchContinue'))['rowShown'], f'[{theme}] tapping again closes it')

            # ---- Podcasts: Continue Listening ----
            await pg.evaluate('__a.pod()'); await pg.wait_for_timeout(200)
            await pg.evaluate("document.querySelector('.mobile-nav-btn[data-nav=podcasts]').click()"); await pg.wait_for_timeout(1200)
            print('podcasts grid', await pg.evaluate("Array.prototype.map.call(document.getElementById('stationsGrid').children,function(e){return e.className+':'+e.textContent.slice(0,40);}).slice(0,6)"))
            c = await pg.evaluate(ACC, 'podcastContinue')
            print(c)
            check(c and c['expanded'] == 'false' and not c['rowShown'] and c['text'].endswith('3'), f'[{theme}] Continue Listening on Podcasts closed by default, count 3 {c}')
            await pg.screenshot(path=f'{SHOTS}/acc-pod-closed-{theme}.png')
            await pg.evaluate("document.querySelector('.acc-head[data-acc=podcastContinue]').click()"); await pg.wait_for_timeout(400)
            c2 = await pg.evaluate(ACC, 'podcastContinue')
            check(c2['rowShown'] and c2['tiles'] == 3 and c2['rowTop'] - c2['headBottom'] >= 8, f'[{theme}] opens with the three episodes {c2}')
            await pg.screenshot(path=f'{SHOTS}/acc-pod-open-{theme}.png')
            # Home's Continue Listening is untouched (not an accordion)
            await pg.evaluate("document.querySelector('.mobile-nav-btn[data-nav=home]').click()"); await pg.wait_for_timeout(600)
            check(not await pg.evaluate("!!document.querySelector('#recentSection .acc-head')"), f'[{theme}] Home rows are not accordions')
            check(not errs, f'[{theme}] no page errors {errs[:3]}')
            await ctx.close()
        await b.close()
    srv.shutdown()
    print('FAILS:', len(fails))
    sys.exit(1 if fails else 0)
asyncio.run(main())
