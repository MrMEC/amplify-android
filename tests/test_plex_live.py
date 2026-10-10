"""Build 137: Plex Live TV channels as their own source in Video > Add Channels (a Plex tab, shown
only while signed in to Plex). Channels come from Plex's channel service with the account token,
are added to My Channels, play with the token put on at play time (never stored), keep the
category, survive a restart, and the tab goes away on Sign Out.
Run: python3 tests/test_plex_live.py (screenshots in /tmp/claude-0/t/shots)"""
import asyncio, json, os, shutil, threading, http.server, functools, sys
from urllib.parse import urlparse, parse_qs
from playwright.async_api import async_playwright
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = '/tmp/claude-0/t/srv-plexlive'; SHOTS = '/tmp/claude-0/t/shots'
shutil.rmtree(ROOT, ignore_errors=True)
os.makedirs(ROOT, exist_ok=True); os.makedirs(SHOTS, exist_ok=True)
shutil.copy(os.path.join(HERE, '..', 'www', 'index.html'), ROOT)
H = functools.partial(http.server.SimpleHTTPRequestHandler, directory=ROOT); H.log_message = lambda *a: None
srv = http.server.ThreadingHTTPServer(('127.0.0.1', 8806), H); threading.Thread(target=srv.serve_forever, daemon=True).start()

LINEUP = '6a1610bebdf296985fd95603'
def ch(cid, title, genres, slug, part=True, drm=False):
    c = {'id': f'{LINEUP}-{cid}', 'title': title, 'slug': slug, 'gridKey': slug, 'callSign': slug.upper()[:6],
         'thumb': f'https://provider-static.plex.tv/epg/logos/{slug}.png', 'Genre': [{'tag': g} for g in genres]}
    if part:
        c['Media'] = [{'Part': [{'key': f'/library/parts/{LINEUP}-{cid}.m3u8'}]}]
    if drm: c['drm'] = True
    return c
CHANNELS = {'MediaContainer': {'size': 5, 'Channel': [
    ch('60d324f59adce5002c41dbc5', 'Stingray Naturescape', ['Nature', 'Music'], 'stingray-naturescape'),
    ch('5fc70600598c41002da3dd39', 'Today All Day', ['News'], 'today-all-day'),
    ch('60d4edd6b2fdec002c141125', 'The Carol Burnett Show', ['Classics', 'Comedy'], 'carol-burnett', part=False),
    ch('68fafc6e558214386ab7ca3a', 'Reuters Now', ['News'], 'reuters-now'),
    ch('aaaaaaaaaaaaaaaaaaaaaaaa', 'Locked Premium', ['Movies'], 'locked', drm=True),
]}}
LOG = {'list': [], 'tokens': []}
state = {'down': False}

MOCK = """
(function(){
 window.__calls=[]; window.__L={}; window.__emit=function(t,ev){ (window.__L[t]||[]).forEach(function(f){ f(ev); }); };
 var P=new Proxy({}, {get:function(t,k){
   if(k==='then') return undefined;
   if(k==='addListener') return function(n,f){ (window.__L[n]=window.__L[n]||[]).push(f); return Promise.resolve({remove:function(){}}); };
   if(k==='load') return function(a){ window.__calls.push(['load',a.url]); window.__cur=a.id;
      setTimeout(function(){ window.__emit('state',{id:a.id,state:'ready',isPlaying:true,playWhenReady:true,position:0,duration:-1,live:true}); },60);
      return Promise.resolve({}); };
   if(k==='setCarCatalog') return function(a){ window.__car = a; return Promise.resolve({}); };
   if(k==='videoState') return function(){ return Promise.resolve({id:null,hasVideo:false}); };
   return function(){ return Promise.resolve({}); };
 }});
 window.Capacitor={isNativePlatform:function(){return true;},getPlatform:function(){return 'android';},Plugins:{AmplifyPlayer:P},convertFileSrc:function(u){return u;}};
})();
"""
SIGNED_IN = """(function(){ if(!localStorage.getItem('__seeded')){ localStorage.setItem('__seeded','1');
  localStorage.setItem('radioPlayerPlexAccount', JSON.stringify({ token: 'USERTOKEN123', user: 'Mark', servers: [] })); } })();"""

fails = []
def check(ok, msg):
    print(('PASS ' if ok else 'FAIL ') + msg)
    if not ok: fails.append(msg)

async def route(r):
    u = urlparse(r.request.url)
    cors = {'Access-Control-Allow-Origin': '*', 'Access-Control-Allow-Headers': '*'}
    if r.request.method == 'OPTIONS': return await r.fulfill(status=204, headers=cors)
    if u.netloc == 'epg.provider.plex.tv' and u.path == '/lineups/plex/channels':
        LOG['list'].append(1)
        LOG['tokens'].append(r.request.headers.get('x-plex-token', ''))
        if state['down']: return await r.fulfill(status=503, headers=cors, body='')
        return await r.fulfill(status=200, content_type='application/json', headers=cors, body=json.dumps(CHANNELS))
    if u.netloc == 'provider-static.plex.tv': return await r.fulfill(status=404, headers=cors, body='')
    if '127.0.0.1' in u.netloc: return await r.continue_()
    return await r.abort()

ROWS = "Array.prototype.map.call(document.querySelectorAll('.ch-row'),function(r){var s=r.querySelector('.ch-sub');return {name:r.querySelector('.ch-name').textContent,sub:s?s.textContent:'',added:r.querySelector('.ch-add').classList.contains('added')};})"
TABS = "Array.prototype.map.call(document.querySelectorAll('.ch-tools .home-tab'),function(b){return b.textContent;})"
async def tab(pg, label):
    await pg.evaluate("(l)=>Array.prototype.find.call(document.querySelectorAll('.ch-tools .home-tab'),function(b){return b.textContent===l;}).click()", label)
    await pg.wait_for_timeout(900)
async def open_add(pg):
    await pg.evaluate("document.querySelector('.mobile-nav-btn[data-nav=video]').click()"); await pg.wait_for_timeout(600)
    await pg.evaluate("document.getElementById('videoAddHeaderBtn').click()"); await pg.wait_for_timeout(1200)

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
        ctx = await b.new_context(viewport={'width': 360, 'height': 780}, device_scale_factor=2, is_mobile=True, has_touch=True, color_scheme='dark', locale='en-US')
        await ctx.add_init_script(MOCK)
        pg = await ctx.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.route('**/*', route)

        # ---- signed out: no Plex tab, nothing asked ----
        await pg.goto('http://127.0.0.1:8806/index.html'); await pg.wait_for_timeout(2000)
        await open_add(pg)
        t = await pg.evaluate(TABS)
        check('Plex' not in t and not LOG['list'], f'signed out: no Plex tab and Plex not asked {t}')

        # ---- signed in ----
        await ctx.add_init_script(SIGNED_IN)
        await pg.reload(); await pg.wait_for_timeout(2000)
        await open_add(pg)
        t = await pg.evaluate(TABS)
        check(t == ['Recommended', 'All', 'Pluto', 'Plex', 'Link'], f'signed in: tabs Recommended, All, Pluto, Plex, Link {t}')
        fit = await pg.evaluate("""(()=>{ var bs = document.querySelectorAll('.ch-tools .home-tab'), l = bs[bs.length-1].getBoundingClientRect(), g = document.getElementById('stationsGrid').getBoundingClientRect();
          return { right: Math.round(l.right), edge: Math.round(g.right), sw: document.querySelector('.ch-tools .home-tabs').scrollWidth, cw: document.querySelector('.ch-tools .home-tabs').clientWidth }; })()""")
        # Build 186: five tabs with Pluto; the row scrolls sideways (checked in test_pluto.py).
        check(fit['sw'] >= fit['cw'], f'tab row present {fit}')
        check(not LOG['list'], 'Plex not asked until its tab is opened')
        await tab(pg, 'Plex')
        r = await pg.evaluate(ROWS)
        print(r)
        names = [x['name'] for x in r]
        check(names == ['Reuters Now', 'Stingray Naturescape', 'The Carol Burnett Show', 'Today All Day'],
              f'Plex tab lists Plex channels A to Z, "The" ignored as everywhere (DRM one left out) {names}')
        check(LOG['tokens'] and LOG['tokens'][-1] == 'USERTOKEN123', f'asked with the account token {LOG["tokens"]}')
        check(r[1]['sub'] == 'Plex · Nature · Music', f'row says Plex and its categories ({r[1]["sub"]})')
        sels = await pg.evaluate("Array.prototype.map.call(document.querySelectorAll('.ch-tools select'),function(s){return Array.prototype.map.call(s.options,function(o){return o.textContent;});})")
        check(len(sels) == 1 and sels[0] == ['All categories', 'Classics', 'Comedy', 'Music', 'Nature', 'News'], f'one Category picker (no country) {sels}')
        await pg.evaluate("(()=>{var s=document.querySelector('.ch-tools select');s.value='News';s.dispatchEvent(new Event('change'));})()"); await pg.wait_for_timeout(500)
        check([x['name'] for x in await pg.evaluate(ROWS)] == ['Reuters Now', 'Today All Day'], 'category filter')
        await pg.evaluate("(()=>{var s=document.querySelector('.ch-tools select');s.value='';s.dispatchEvent(new Event('change'));})()"); await pg.wait_for_timeout(500)
        await pg.evaluate("(()=>{var i=document.querySelector('.ch-tools input');i.value='stingray';i.dispatchEvent(new Event('input'));})()"); await pg.wait_for_timeout(600)
        check([x['name'] for x in await pg.evaluate(ROWS)] == ['Stingray Naturescape'], 'search filters as you type')
        await pg.evaluate("(()=>{var i=document.querySelector('.ch-tools input');i.value='';i.dispatchEvent(new Event('input'));})()"); await pg.wait_for_timeout(600)
        await pg.screenshot(path=f'{SHOTS}/plexlive-tab.png')

        # ---- add two ----
        for n in ('Stingray Naturescape', 'The Carol Burnett Show'):
            await pg.evaluate("(n)=>Array.prototype.find.call(document.querySelectorAll('.ch-row'),function(r){return r.querySelector('.ch-name').textContent===n;}).querySelector('.ch-add').click()", n)
        await pg.wait_for_timeout(300)
        saved = await pg.evaluate("JSON.parse(localStorage.getItem('radioPlayerVideoChannels'))")
        print(saved)
        check([c['name'] for c in saved] == ['Stingray Naturescape', 'The Carol Burnett Show'], 'both added to My Channels')
        check(saved[0]['url'] == f'https://epg.provider.plex.tv/library/parts/{LINEUP}-60d324f59adce5002c41dbc5.m3u8', f'stream address from Plex ({saved[0]["url"]})')
        check(saved[1]['url'] == f'https://epg.provider.plex.tv/library/parts/{LINEUP}-60d4edd6b2fdec002c141125.m3u8', 'a channel without a listed part gets the standard address')
        check(all('USERTOKEN' not in json.dumps(c) for c in saved), 'the token is never stored with a channel')
        check(saved[0]['src'] == 'plex' and saved[0]['catNames'] == ['Nature', 'Music'] and saved[0]['gridKey'] == 'stingray-naturescape', f'source, categories and guide key kept {saved[0]}')

        # ---- play: token put on at play time ----
        await pg.evaluate("Array.prototype.find.call(document.querySelectorAll('.ch-row'),function(r){return r.querySelector('.ch-name').textContent==='Stingray Naturescape';}).click()")
        await pg.wait_for_timeout(1500)
        load = await pg.evaluate("window.__calls.filter(function(c){return c[0]==='load';}).slice(-1)[0]")
        print('load', load)
        check(load and load[1].startswith(f'https://epg.provider.plex.tv/library/parts/{LINEUP}-60d324f59adce5002c41dbc5.m3u8?X-Plex-Token=USERTOKEN123'),
              f'plays with the token added {load}')
        await pg.screenshot(path=f'{SHOTS}/plexlive-playing.png')
        store = await pg.evaluate("[localStorage.getItem('radioPlayerChannelHistory')||'', localStorage.getItem('radioPlayerFavorites')||'', localStorage.getItem('radioPlayerRecent')||'', localStorage.getItem('radioPlayerVideoChannels')||''].join('|')")
        check('USERTOKEN' not in store, 'nothing saved after playing carries the token')
        await pg.wait_for_timeout(1500)
        car = await pg.evaluate("JSON.stringify(window.__car||{})")
        stingray_in_car = 'stingray' in car.lower()
        print('car has stingray', stingray_in_car)
        if stingray_in_car:
            check('X-Plex-Token=USERTOKEN123' in car, 'Android Auto gets a playable (token) address')

        # ---- My Channels after a restart, no network: kept, list from the saved copy ----
        n_list = len(LOG['list'])
        state['down'] = True
        await pg.reload(); await pg.wait_for_timeout(2000)
        await pg.evaluate("document.querySelector('.mobile-nav-btn[data-nav=video]').click()"); await pg.wait_for_timeout(800)
        mine = await pg.evaluate("Array.prototype.map.call(document.querySelectorAll('#stationsGrid .tile .tile-name, #stationsGrid .ch-list .tile-name'),function(t){return t.textContent;})")
        check('Stingray Naturescape' in mine and 'The Carol Burnett Show' in mine, f'My Channels keeps them after a restart {mine}')
        await pg.screenshot(path=f'{SHOTS}/plexlive-mychannels.png')
        await pg.evaluate("document.getElementById('videoAddHeaderBtn').click()"); await pg.wait_for_timeout(1000)
        await tab(pg, 'Plex')
        r = await pg.evaluate(ROWS)
        check(len(r) == 4 and len(LOG['list']) == n_list, f'Plex tab opens from the saved list (no request; Plex down) {len(r)} {len(LOG["list"]) - n_list}')
        check([x['name'] for x in r if x['added']] == ['Stingray Naturescape', 'The Carol Burnett Show'], 'added ones show a check')

        # ---- Plex down and nothing saved: a clear message ----
        await pg.evaluate("localStorage.removeItem('radioPlayerPlexLive')")
        await pg.reload(); await pg.wait_for_timeout(2000)
        await open_add(pg); await tab(pg, 'Plex')
        msg = await pg.evaluate("(document.querySelector('#stationsGrid .empty-state')||{}).textContent||''")
        check('Plex' in msg and 'Settings' in msg, f'Plex unreachable: says so ({msg})')
        state['down'] = False

        # ---- Sign Out: tab gone, list forgotten ----
        await pg.evaluate("localStorage.removeItem('radioPlayerPlexAccount')")
        await pg.reload(); await pg.wait_for_timeout(2000)
        await open_add(pg)
        t = await pg.evaluate(TABS)
        check('Plex' not in t, f'signed out again: no Plex tab {t}')

        check(not errs, f'no page errors {errs[:3]}')
        await b.close()
    srv.shutdown()
    print('FAILS:', len(fails))
    sys.exit(1 if fails else 0)

asyncio.run(main())
