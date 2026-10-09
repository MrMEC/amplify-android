"""Build 138: the Video section is called Watch (circle play icon) in the tab bar and the drawer;
after visiting a Library page, opening Watch highlights Watch in the tab bar.
Build 180: Continue Listening (Podcasts) and Continue Watching (Watch) are no longer accordions
on the page: each is a Continue tab, the last tab, listing stacked rows; the tab rows scroll
sideways; Live TV has no "My Channels" label; My Library's counts are bare numbers.
Run: python3 tests/test_watch_accordions.py (screenshots in /tmp/claude-0/t/shots)"""
import asyncio, json, os, shutil, threading, http.server, functools, sys
from playwright.async_api import async_playwright
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = '/tmp/claude-0/t/srv-acc'; SHOTS = '/tmp/claude-0/t/shots'
shutil.rmtree(ROOT, ignore_errors=True); os.makedirs(ROOT); os.makedirs(SHOTS, exist_ok=True)
HOOK = ("window.__a = { artists: function(){ runLibrarySection('artists'); }, nav: function(){ var b = document.querySelector('.mobile-nav-btn.active'); return b ? b.dataset.nav : null; }, watch: function(){ videoChannels.forEach(function(c){ recordChannelWatch(channelToStation(c)); }); },"
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

SAMPLE = """(id)=>new Promise(function(res){ var h = document.querySelector('#stationsGrid .acc-head[data-acc="' + id + '"]'), row = h.nextElementSibling, nx = row.nextElementSibling, out = [];
  var t0 = performance.now(); h.click();
  (function f(){ out.push([Math.round(performance.now() - t0), Math.round(nx.getBoundingClientRect().top), Math.round(row.getBoundingClientRect().height)]);
    if(performance.now() - t0 < 600) requestAnimationFrame(f); else res(out); })(); })"""
def smooth(frames, start, end):
    tops = [f[1] for f in frames]
    mids = [t for t in tops if min(start, end) + 4 < t < max(start, end) - 4]
    mono = all((b - a) * (end - start) >= -1 for a, b in zip(tops, tops[1:]))
    return len(mids) >= 5 and mono and abs(tops[0] - start) <= 3 and abs(tops[-1] - end) <= 1

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
            # Library first (the screenshot Mark sent: Library stayed lit on Watch)
            await pg.evaluate("document.querySelector('.mobile-nav-btn[data-nav=library]').click()"); await pg.wait_for_timeout(500)
            await pg.evaluate('__a.artists()'); await pg.wait_for_timeout(600)
            check(await pg.evaluate('__a.nav()') == 'library', f'[{theme}] on Artists the Library tab is lit')
            await pg.evaluate("document.querySelector('.mobile-nav-btn[data-nav=video]').click()"); await pg.wait_for_timeout(800)
            lit = await pg.evaluate('__a.nav()')
            check(lit == 'video', f'[{theme}] Watch opened from a Library page lights Watch, not Library ({lit})')
            head = await pg.evaluate("document.getElementById('stationsHeading').textContent")
            check(head == 'Watch', f'[{theme}] page heading reads Watch ({head})')
            TABS = """(sel)=>{ var t = document.querySelector(sel); if(!t) return null; var cs = getComputedStyle(t);
              return { names: Array.from(t.querySelectorAll('.home-tab')).map(function(b){ return b.textContent.trim(); }),
                active: (t.querySelector('.home-tab.active') || {}).textContent, scroll: cs.overflowX, wrap: cs.flexWrap,
                sw: t.scrollWidth, cw: t.clientWidth }; }"""
            GRID = """(()=>{ var g = document.getElementById('stationsGrid');
              return { acc: g.querySelectorAll('.acc-head').length, labels: Array.from(g.querySelectorAll('.grid-section-label')).map(function(e){ return e.textContent.trim(); }),
                rows: Array.from(g.querySelectorAll('.song-row')).map(function(r){ return { t: (r.querySelector('.song-row-title') || {}).textContent, s: (r.querySelector('.song-row-sub') || {}).textContent || '',
                  more: !!r.querySelector('.row-more-btn'), h: Math.round(r.getBoundingClientRect().height), l: Math.round(r.getBoundingClientRect().left) }; }),
                cl: g.querySelectorAll('.cl-row').length, text: g.innerText.slice(0, 300) }; })()"""
            # ---- Watch: no accordion; Continue is the last tab ----
            gw = await pg.evaluate(GRID)
            check(gw['acc'] == 0 and gw['cl'] == 0 and 'Continue Watching' not in gw['text'], f'[{theme}] Watch has no Continue Watching section on the page {gw["labels"]}')
            check('My Channels' not in gw['labels'], f'[{theme}] Live TV: no "My Channels" label {gw["labels"]}')
            tw = await pg.evaluate(TABS, '.video-tabs')
            check(tw['names'] == ['Live TV', 'Movies', 'TV Shows', 'Continue'], f'[{theme}] Continue is the last Watch tab {tw["names"]}')
            check(tw['scroll'] in ('auto', 'scroll') and tw['wrap'] == 'nowrap', f'[{theme}] Watch tabs scroll sideways, on one line {tw}')
            await pg.screenshot(path=f'{SHOTS}/cont-watch-live-{theme}.png')
            await pg.evaluate("document.querySelector('.video-tabs [data-vtab=continue]').click()"); await pg.wait_for_timeout(500)
            cw = await pg.evaluate(GRID); print(cw['rows'])
            check(len(cw['rows']) == 2 and all(r['more'] for r in cw['rows']) and len(set(r['l'] for r in cw['rows'])) == 1,
                  f'[{theme}] the Continue tab lists the two channels as stacked rows, each with More {cw["rows"]}')
            check((await pg.evaluate(TABS, '.video-tabs'))['active'] == 'Continue', f'[{theme}] and is the open tab')
            await pg.screenshot(path=f'{SHOTS}/cont-watch-{theme}.png')
            # a row's More menu: Remove takes it off the list
            await pg.evaluate("document.querySelector('#stationsGrid .cw-row .row-more-btn').click()"); await pg.wait_for_timeout(300)
            await pg.evaluate("Array.from(document.querySelectorAll('.v-menu .np-menu-item')).filter(function(b){ return /Remove/.test(b.textContent); })[0].click()"); await pg.wait_for_timeout(500)
            check(len((await pg.evaluate(GRID))['rows']) == 1, f'[{theme}] Remove from Continue Watching takes the row away')
            # remembered, like the other tabs
            await pg.evaluate("document.querySelector('.mobile-nav-btn[data-nav=home]').click()"); await pg.wait_for_timeout(500)
            await pg.evaluate("document.querySelector('.mobile-nav-btn[data-nav=video]').click()"); await pg.wait_for_timeout(700)
            check((await pg.evaluate(TABS, '.video-tabs'))['active'] == 'Continue', f'[{theme}] Watch comes back on the Continue tab')
            await pg.evaluate("document.querySelector('.video-tabs [data-vtab=channels]').click()"); await pg.wait_for_timeout(300)

            # ---- Podcasts: no accordion; Continue is the last tab ----
            await pg.evaluate('__a.pod()'); await pg.wait_for_timeout(200)
            await pg.evaluate("document.querySelector('.mobile-nav-btn[data-nav=podcasts]').click()"); await pg.wait_for_timeout(1200)
            gp = await pg.evaluate(GRID)
            check(gp['acc'] == 0 and gp['cl'] == 0 and 'Continue Listening' not in gp['text'], f'[{theme}] Latest has no Continue Listening section {gp["text"][:80]!r}')
            tp = await pg.evaluate(TABS, '#podcastTabs')
            check(tp['names'][-1] == 'Continue' and tp['scroll'] in ('auto', 'scroll') and tp['wrap'] == 'nowrap', f'[{theme}] Continue is the last Podcasts tab, and the tabs scroll sideways {tp}')
            await pg.screenshot(path=f'{SHOTS}/cont-pod-latest-{theme}.png')
            await pg.evaluate("Array.from(document.querySelectorAll('#podcastTabs .home-tab')).filter(function(b){ return b.textContent.trim() === 'Continue'; })[0].click()"); await pg.wait_for_timeout(900)
            cp = await pg.evaluate(GRID); print(cp['rows'])
            check(sorted(r['t'] for r in cp['rows']) == ['Episode 1', 'Episode 2', 'Episode 3'] and all(r['more'] for r in cp['rows']),
                  f'[{theme}] the Continue tab lists the episodes in progress as rows with More {cp["rows"]}')
            check(all('left' in r['s'] for r in cp['rows']), f'[{theme}] each says how much is left {[r["s"] for r in cp["rows"]]}')
            await pg.screenshot(path=f'{SHOTS}/cont-pod-{theme}.png')
            # My Library: bare numbers
            await pg.evaluate("document.querySelector('.mobile-nav-btn[data-nav=library]').click()"); await pg.wait_for_timeout(800)
            subs = await pg.evaluate("Array.from(document.querySelectorAll('#stationsGrid .tile[data-entity=library-section] .tile-sub')).map(function(e){ return e.textContent; })")
            check(subs and all(x.isdigit() for x in subs), f'[{theme}] My Library counts are numbers only {subs}')
            # Add Music: no "never uploaded" line
            note = await pg.evaluate("document.getElementById('addMusicOverlay').textContent")
            check('never uploaded' not in note, f'[{theme}] the Add Music dialog has no "never uploaded" line')
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
