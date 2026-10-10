"""Builds 186-188: Pluto TV channels as their own source in Video > Add Channels (a Pluto tab, no account).
The list comes from Pluto's public channel list; channels are added to My Channels with a bare
stream address; at play time the address is built from a Pluto session started at boot.pluto.tv
(stream server, parameters and token; build 188, since without one Pluto plays its "no longer
available on this device" slate); the session is kept and renewed when it runs out; nothing saved
carries it; Pluto's test and office-only channels are left out; the list is kept for a restart;
search finds Pluto channels; the car gets a playable address.
Run: python3 tests/test_pluto.py (screenshots in /tmp/claude-0/t/shots)"""
import asyncio, json, os, shutil, threading, http.server, functools, sys
from urllib.parse import urlparse, parse_qs
from playwright.async_api import async_playwright
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = '/tmp/claude-0/t/srv-pluto'; SHOTS = '/tmp/claude-0/t/shots'
shutil.rmtree(ROOT, ignore_errors=True)
os.makedirs(ROOT, exist_ok=True); os.makedirs(SHOTS, exist_ok=True)
shutil.copy(os.path.join(HERE, '..', 'www', 'index.html'), ROOT)
H = functools.partial(http.server.SimpleHTTPRequestHandler, directory=ROOT); H.log_message = lambda *a: None
srv = http.server.ThreadingHTTPServer(('127.0.0.1', 8807), H); threading.Thread(target=srv.serve_forever, daemon=True).start()

HOST1 = 'cfd-v4-service-channel-stitcher-use1-1.prd.pluto.tv'
HOST2 = 'cfd-v5-service-channel-stitcher-use1-2.prd.pluto.tv'
QS = '?advertisingId=&appName=web&deviceDNT=0&deviceId=PLUTOSID&deviceLat=40.0400&deviceLon=-82.8600&marketingRegion=US&sid=SESSIONX&userId='
state = {'host': HOST1, 'down': False, 'stitcher': HOST1, 'bootDown': False}
def ch(cid, name, cat, number, **kw):
    c = {'_id': cid, 'slug': name.lower().replace(' ', '-'), 'name': name, 'number': number, 'category': cat,
         'summary': 'About ' + name, 'visibility': 'everyone', 'isStitched': True, 'directOnly': True, 'plutoOfficeOnly': False,
         'colorLogoPNG': {'path': f'https://images.pluto.tv/channels/{cid}/colorLogoPNG.png'},
         'logo': {'path': f'https://images.pluto.tv/channels/{cid}/logo.png'},
         'stitched': {'urls': [{'type': 'hls', 'url': f'https://{state["host"]}/stitch/hls/channel/{cid}/master.m3u8{QS}'}]}}
    c.update(kw)
    return c
def channels():
    return [
        ch('5421f71da6af422839419cb3', 'CNN Headlines', 'News + Opinion', 2533),
        ch('51c75f7bb6f26ba1cd00002f', 'Little Stars Universe', 'Kids', 3730),
        ch('5f1210d14ae1f80007bafb1d', 'The Asylum', 'Movies', 101),
        ch('5ce4475cd43850831ca91ce7', 'Pluto TV Westerns', 'Westerns', 560),
        ch('aaaaaaaaaaaaaaaaaaaaaaaa', 'Office Only', 'Movies', 1, plutoOfficeOnly=True),
        ch('bbbbbbbbbbbbbbbbbbbbbbbb', 'QA Channel', 'Testing', 2),
        ch('cccccccccccccccccccccccc', 'Hidden One', 'Drama', 3, visibility='hidden'),
    ]
LOG = {'list': 0, 'boot': 0, 'bootq': None}

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
BIGTEXT = """(function(){ var s=document.createElement('style'); s.textContent='.ch-name,.ch-sub,.home-tab{font-size:calc(1em*1.35) !important}'; document.head.appendChild(s); })()"""

fails = []
def check(ok, msg):
    print(('PASS ' if ok else 'FAIL ') + msg)
    if not ok: fails.append(msg)

async def route(r):
    u = urlparse(r.request.url)
    cors = {'Access-Control-Allow-Origin': '*', 'Access-Control-Allow-Headers': '*'}
    if r.request.method == 'OPTIONS': return await r.fulfill(status=204, headers=cors)
    if u.netloc == 'api.pluto.tv' and u.path == '/v2/channels.json':
        LOG['list'] += 1
        if state['down']: return await r.fulfill(status=503, headers=cors, body='')
        return await r.fulfill(status=200, content_type='application/json', headers=cors, body=json.dumps(channels()))
    if u.netloc == 'boot.pluto.tv' and u.path == '/v4/start':
        LOG['boot'] += 1; LOG['bootq'] = parse_qs(u.query, keep_blank_values=True)
        if state['bootDown']: return await r.fulfill(status=503, headers=cors, body='')
        n = LOG['boot']
        body = {'servers': {'stitcher': 'https://' + state['stitcher']}, 'session': {'activeRegion': 'US'},
                'stitcherParams': f'appName=web&deviceDNT=0&deviceId=DEV&marketingRegion=US&sid=S{n}&sessionID=S{n}',
                'sessionToken': f'JWTTOKEN{n}', 'refreshInSec': 28800}
        return await r.fulfill(status=200, content_type='application/json', headers=cors, body=json.dumps(body))
    if u.netloc == 'images.pluto.tv': return await r.fulfill(status=404, headers=cors, body='')
    if '127.0.0.1' in u.netloc: return await r.continue_()
    return await r.abort()

ROWS = "Array.prototype.map.call(document.querySelectorAll('.ch-row'),function(r){var s=r.querySelector('.ch-sub');return {name:r.querySelector('.ch-name').textContent,sub:s?s.textContent:'',added:r.querySelector('.ch-add').classList.contains('added')};})"
TABS = "Array.prototype.map.call(document.querySelectorAll('.ch-tools .home-tab'),function(b){return b.textContent;})"
FIT = """(()=>{ var t = document.querySelector('.ch-tools .home-tabs'), bs = t.querySelectorAll('.home-tab'), l = bs[bs.length-1].getBoundingClientRect(), g = document.getElementById('stationsGrid').getBoundingClientRect();
  var clip = Array.prototype.some.call(bs, function(b){ return b.scrollWidth > b.clientWidth + 1; });
  return { right: Math.round(l.right), edge: Math.round(g.right), sw: t.scrollWidth, cw: t.clientWidth, clip: clip }; })()"""
async def tab(pg, label):
    await pg.evaluate("(l)=>Array.prototype.find.call(document.querySelectorAll('.ch-tools .home-tab'),function(b){return b.textContent===l;}).click()", label)
    await pg.wait_for_timeout(900)
async def open_add(pg):
    await pg.evaluate("document.querySelector('.mobile-nav-btn[data-nav=video]').click()"); await pg.wait_for_timeout(600)
    await pg.evaluate("document.getElementById('videoAddHeaderBtn').click()"); await pg.wait_for_timeout(1200)
def loads(calls): return [c[1] for c in calls if c[0] == 'load']

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
        ctx = await b.new_context(viewport={'width': 360, 'height': 780}, device_scale_factor=2, is_mobile=True, has_touch=True, color_scheme='dark', locale='en-US')
        await ctx.add_init_script(MOCK)
        pg = await ctx.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.route('**/*', route)

        # a one-channel list saved by build 186 must not be used
        await pg.goto('http://127.0.0.1:8807/index.html'); await pg.wait_for_timeout(500)
        await pg.evaluate("localStorage.setItem('radioPlayerPluto', JSON.stringify({at: Date.now(), list: [{id:'pluto:x', plutoId:'5421f71da6af422839419cb3', name:'Only One', url:'https://x.pluto.tv/stitch/hls/channel/5421f71da6af422839419cb3/master.m3u8', cats:[], src:'pluto'}]}))")
        await pg.reload(); await pg.wait_for_timeout(2000)
        check(await pg.evaluate("localStorage.getItem('radioPlayerPluto')") is None, 'build 186\'s saved list is thrown away')
        await open_add(pg)
        t = await pg.evaluate(TABS)
        check(t == ['Recommended', 'All', 'Pluto', 'Link'], f'tabs Recommended, All, Pluto, Link (no account needed) {t}')
        check(LOG['list'] == 0, 'Pluto not asked until its tab is opened')
        await tab(pg, 'Pluto')
        r = await pg.evaluate(ROWS)
        print(r)
        names = [x['name'] for x in r]
        check(names == ['CNN Headlines', 'Little Stars Universe', 'Pluto TV Westerns', 'The Asylum'],
              f'Pluto channels A to Z; test, office-only and hidden ones left out {names}')
        check(r[0]['sub'] == 'Pluto TV · News + Opinion', f'row says Pluto TV and its category ({r[0]["sub"]})')
        sels = await pg.evaluate("Array.prototype.map.call(document.querySelectorAll('.ch-tools select'),function(s){return Array.prototype.map.call(s.options,function(o){return o.textContent;});})")
        check(len(sels) == 1 and sels[0] == ['All categories', 'Kids', 'Movies', 'News + Opinion', 'Westerns'], f'one Category picker (no country) {sels}')
        await pg.evaluate("(()=>{var s=document.querySelector('.ch-tools select');s.value='Kids';s.dispatchEvent(new Event('change'));})()"); await pg.wait_for_timeout(500)
        check([x['name'] for x in await pg.evaluate(ROWS)] == ['Little Stars Universe'], 'category filter')
        await pg.evaluate("(()=>{var s=document.querySelector('.ch-tools select');s.value='';s.dispatchEvent(new Event('change'));})()"); await pg.wait_for_timeout(500)
        await pg.evaluate("(()=>{var i=document.querySelector('.ch-tools input');i.value='cnn';i.dispatchEvent(new Event('input'));})()"); await pg.wait_for_timeout(600)
        check([x['name'] for x in await pg.evaluate(ROWS)] == ['CNN Headlines'], 'search filters as you type')
        await pg.evaluate("(()=>{var i=document.querySelector('.ch-tools input');i.value='';i.dispatchEvent(new Event('input'));})()"); await pg.wait_for_timeout(600)
        await pg.screenshot(path=f'{SHOTS}/pluto-tab.png')

        # ---- add two ----
        for n in ('CNN Headlines', 'Pluto TV Westerns'):
            await pg.evaluate("(n)=>Array.prototype.find.call(document.querySelectorAll('.ch-row'),function(r){return r.querySelector('.ch-name').textContent===n;}).querySelector('.ch-add').click()", n)
        await pg.wait_for_timeout(300)
        saved = await pg.evaluate("JSON.parse(localStorage.getItem('radioPlayerVideoChannels'))")
        print(saved)
        check([c['name'] for c in saved] == ['CNN Headlines', 'Pluto TV Westerns'], 'both added to My Channels')
        check(saved[0]['url'] == f'https://{HOST1}/stitch/hls/channel/5421f71da6af422839419cb3/master.m3u8', f'saved without session details ({saved[0]["url"]})')
        check(saved[0]['src'] == 'pluto' and saved[0]['catNames'] == ['News + Opinion'] and 'colorLogoPNG' in saved[0]['logo'], f'source, category, colour logo kept {saved[0]}')

        # ---- play: through a Pluto session ----
        check(LOG['boot'] == 0, 'no Pluto session started before anything is played')
        await pg.evaluate("Array.prototype.find.call(document.querySelectorAll('.ch-row'),function(r){return r.querySelector('.ch-name').textContent==='CNN Headlines';}).click()")
        await pg.wait_for_timeout(1500)
        ls = loads(await pg.evaluate('window.__calls'))
        l1 = ls[-1]
        print('load', l1)
        u1 = urlparse(l1); q1 = parse_qs(u1.query)
        check(LOG['boot'] == 1, f'a Pluto session is started for the first play ({LOG["boot"]})')
        bq = LOG['bootq'] or {}
        check(bq.get('appName') == ['web'] and bq.get('clientID') and bq.get('deviceType') == ['web'], f'started like Pluto\'s web player {bq}')
        check(all('jwt=' in x for x in ls if 'pluto' in x), 'never played without the session (no slate-only address)')
        check(u1.netloc == HOST1 and u1.path == '/v2/stitch/hls/channel/5421f71da6af422839419cb3/master.m3u8', f'plays the channel from the session\'s stream server {l1}')
        check(q1.get('jwt') == ['JWTTOKEN1'] and q1.get('masterJWTPassthrough') == ['true'] and q1.get('sid') == ['S1'] and q1.get('deviceDNT') == ['0'],
              f'session token and parameters on the address {q1}')
        await pg.screenshot(path=f'{SHOTS}/pluto-playing.png')
        store = await pg.evaluate("[localStorage.getItem('radioPlayerChannelHistory')||'', localStorage.getItem('radioPlayerFavorites')||'', localStorage.getItem('radioPlayerRecent')||'', localStorage.getItem('radioPlayerVideoChannels')||'', localStorage.getItem('radioPlayerPluto2')||''].join('|')")
        check('JWTTOKEN' not in store and 'sid=S' not in store, 'nothing saved with channels, history or the list carries the session')
        await pg.wait_for_timeout(2500)
        car = await pg.evaluate("JSON.stringify(window.__car||{})")
        if 'cnn headlines' in car.lower():
            check('jwt=JWTTOKEN1' in car and '/v2/stitch/' in car, 'Android Auto gets a playable (session) address')
        else:
            print('note: CNN Headlines not in the car catalog yet')

        # ---- second play: same session, no new start ----
        await pg.evaluate("Array.prototype.find.call(document.querySelectorAll('.ch-row'),function(r){return r.querySelector('.ch-name').textContent==='Pluto TV Westerns';}).click()")
        await pg.wait_for_timeout(1500)
        q2 = parse_qs(urlparse(loads(await pg.evaluate('window.__calls'))[-1]).query)
        check(q2.get('jwt') == ['JWTTOKEN1'] and LOG['boot'] == 1, f'the session is reused ({LOG["boot"]} starts)')

        # ---- search finds Pluto channels once the list is on the phone (Search > Channels) ----
        await pg.evaluate("document.querySelector('.mobile-nav-btn[data-nav=search]').click()"); await pg.wait_for_timeout(600)
        await pg.evaluate("(()=>{var i=document.getElementById('searchSheetInput')||document.getElementById('searchInput'); i.dispatchEvent(new Event('focus')); i.value='little stars'; i.dispatchEvent(new Event('input',{bubbles:true}));})()")
        await pg.wait_for_timeout(1500)
        await pg.evaluate("(()=>{var b=Array.prototype.find.call(document.querySelectorAll('#searchTabs .home-tab, #searchTabs button'),function(x){return /channel/i.test(x.textContent);}); if(b) b.click();})()")
        await pg.wait_for_timeout(700)
        found = await pg.evaluate("Array.prototype.map.call(document.querySelectorAll('#stationsGrid .ch-name, #stationsGrid .tile-name, #stationsGrid .song-row-title'),function(x){return x.textContent;})")
        check('Little Stars Universe' in found, f'search finds a Pluto channel {found[:8]}')
        await pg.screenshot(path=f'{SHOTS}/pluto-search.png')

        # ---- restart with Pluto down: list kept; Pluto moved its servers: saved channel follows ----
        n0 = LOG['list']
        state['down'] = True
        await pg.reload(); await pg.wait_for_timeout(2000)
        await open_add(pg); await tab(pg, 'Pluto')
        r = await pg.evaluate(ROWS)
        check(len(r) == 4 and LOG['list'] == n0, f'Pluto tab opens from the kept list (no request) {len(r)}')
        check([x['name'] for x in r if x['added']] == ['CNN Headlines', 'Pluto TV Westerns'], 'added ones show a check')
        state['down'] = False
        await pg.evaluate("(()=>{var k=JSON.parse(localStorage.getItem('radioPlayerPluto2'));k.at=0;localStorage.setItem('radioPlayerPluto2',JSON.stringify(k));})()")
        await pg.reload(); await pg.wait_for_timeout(2000)
        await open_add(pg); await tab(pg, 'Pluto')
        check(LOG['list'] == n0 + 1, 'an old kept list is refreshed')
        # the kept session is used after a restart; once it has run out a new one is started,
        # and its stream server is used
        b0 = LOG['boot']
        await pg.evaluate("document.querySelector('.mobile-nav-btn[data-nav=video]').click()"); await pg.wait_for_timeout(800)
        PLAY_CNN = """(()=>{ var t = Array.prototype.find.call(document.querySelectorAll('#stationsGrid .ch-list .tile, #stationsGrid .tile'), function(x){ var n = x.querySelector('.tile-name'); return n && n.textContent === 'CNN Headlines'; }); t.click(); })()"""
        await pg.evaluate(PLAY_CNN); await pg.wait_for_timeout(1500)
        l3 = loads(await pg.evaluate('window.__calls'))[-1]
        check('jwt=JWTTOKEN1' in l3 and LOG['boot'] == b0, f'after a restart the kept session plays My Channels without a new start {l3}')
        await pg.screenshot(path=f'{SHOTS}/pluto-mychannels.png')
        state['stitcher'] = HOST2
        await pg.evaluate("(()=>{var s=JSON.parse(localStorage.getItem('radioPlayerPlutoSession'));s.until=Date.now()-1000;localStorage.setItem('radioPlayerPlutoSession',JSON.stringify(s));})()")
        await pg.reload(); await pg.wait_for_timeout(2500)
        check(LOG['boot'] == b0 + 1, f'a run-out session is renewed at start-up when Pluto channels are saved ({LOG["boot"] - b0})')
        await pg.evaluate("document.querySelector('.mobile-nav-btn[data-nav=video]').click()"); await pg.wait_for_timeout(800)
        await pg.evaluate(PLAY_CNN); await pg.wait_for_timeout(1500)
        l4 = loads(await pg.evaluate('window.__calls'))[-1]
        check(urlparse(l4).netloc == HOST2 and 'jwt=JWTTOKEN2' in l4, f'plays from the new session\'s stream server with its token {l4}')
        # Pluto's start service down and no session: no slate address is played
        state['bootDown'] = True
        await pg.evaluate("localStorage.removeItem('radioPlayerPlutoSession')")
        await pg.reload(); await pg.wait_for_timeout(2500)
        n_before = len(loads(await pg.evaluate('window.__calls')))
        await pg.evaluate("document.querySelector('.mobile-nav-btn[data-nav=video]').click()"); await pg.wait_for_timeout(800)
        await pg.evaluate(PLAY_CNN); await pg.wait_for_timeout(1800)
        after = loads(await pg.evaluate('window.__calls'))[n_before:]
        check(not any('deviceDNT' in x or 'jwt' in x for x in after), f'without a session nothing playable-looking is sent (bare address fails normally) {after}')
        state['bootDown'] = False

        # ---- Pluto down, nothing kept: a clear message ----
        await pg.evaluate("localStorage.removeItem('radioPlayerPluto2')")
        state['down'] = True
        await pg.reload(); await pg.wait_for_timeout(2000)
        await open_add(pg); await tab(pg, 'Pluto')
        msg = await pg.evaluate("(document.querySelector('#stationsGrid .empty-state')||{}).textContent||''")
        check('Pluto' in msg and 'undefined' not in msg and 'JSON' not in msg, f'Pluto unreachable: says so plainly ({msg})')
        state['down'] = False

        # ---- tabs fit (with Plex signed in too) at 360 and 412, big text ----
        await pg.evaluate("localStorage.setItem('radioPlayerPlexAccount', JSON.stringify({ token: 'T', user: 'Mark', servers: [] }))")
        for w in (360, 412):
            await pg.set_viewport_size({'width': w, 'height': 800})
            await pg.reload(); await pg.wait_for_timeout(2000)
            await pg.evaluate(BIGTEXT)
            await open_add(pg); await tab(pg, 'Pluto')
            t = await pg.evaluate(TABS)
            fit = await pg.evaluate(FIT)
            check(t == ['Recommended', 'All', 'Pluto', 'Plex', 'Link'], f'{w}px with Plex: five tabs {t}')
            check(not fit['clip'], f'{w}px big text: no tab label cut off {fit}')
            act = await pg.evaluate("(()=>{var a=document.querySelector('.ch-tools .home-tab.active').getBoundingClientRect(); return [Math.round(a.left), Math.round(a.right), innerWidth];})()")
            check(act[0] >= 0 and act[1] <= act[2], f'{w}px: the open tab (Pluto) is on screen {act}')
            await pg.screenshot(path=f'{SHOTS}/pluto-tabs-{w}-bigtext.png')
            # every tab reachable: scroll the row to its end and check Link is on screen
            await pg.evaluate("(()=>{var t=document.querySelector('.ch-tools .home-tabs'); t.scrollLeft=t.scrollWidth;})()")
            last = await pg.evaluate("(()=>{var bs=document.querySelectorAll('.ch-tools .home-tab'), l=bs[bs.length-1].getBoundingClientRect(); return [Math.round(l.left), Math.round(l.right), innerWidth];})()")
            check(last[1] <= last[2] and last[0] >= 0, f'{w}px: Link reachable on screen {last}')

        check(not errs, f'no page errors {errs[:3]}')
        await b.close()
    srv.shutdown()
    print('FAILS:', len(fails))
    sys.exit(1 if fails else 0)

asyncio.run(main())
