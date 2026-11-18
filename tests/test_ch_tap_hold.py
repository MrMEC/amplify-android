"""Build 683 (Mark): Live TV channel buttons play on a tap and open the channel menu on a long press
(Watch page guide and the guide under the playing video); Watch comes before Podcasts in the bottom
nav; the channel menu's Category list follows the order of the grid's category chips.
Run: python3 tests/test_ch_tap_hold.py (screenshots in /tmp/claude-0/t/shots)"""


import sys as _nsys, os as _nos; _nsys.path.insert(0, _nos.path.dirname(_nos.path.abspath(__file__))); from notice_auto import AUTO_NOTICE
import asyncio, json, os, shutil, threading, http.server, functools, time, datetime
from urllib.parse import urlparse, parse_qs
from playwright.async_api import async_playwright
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = '/tmp/claude-0/t/srv-chhold'; SHOTS = '/tmp/claude-0/t/shots'
PORT = 8883
shutil.rmtree(ROOT, ignore_errors=True)
os.makedirs(ROOT, exist_ok=True); os.makedirs(SHOTS, exist_ok=True)
shutil.copy(os.path.join(HERE, '..', 'www', 'index.html'), ROOT)
H = functools.partial(http.server.SimpleHTTPRequestHandler, directory=ROOT); H.log_message = lambda *a: None
srv = http.server.ThreadingHTTPServer(('127.0.0.1', PORT), H); threading.Thread(target=srv.serve_forever, daemon=True).start()

BUZZR = '5ef3a4c2ff6a3f0007a28f69'
KIDS = '51c75f7bb6f26ba1cd00002f'
CHANNELS = [
    {'id': 'pluto:' + BUZZR, 'name': 'Buzzr', 'url': f'https://cfd-v4-service-channel-stitcher-use1-1.prd.pluto.tv/stitch/hls/channel/{BUZZR}/master.m3u8', 'logo': '', 'cats': ['Classic TV'], 'catNames': ['Classic TV'], 'src': 'pluto'},
    {'id': 'plexlive:abc-def', 'name': 'Reuters Now', 'url': 'https://epg.provider.plex.tv/library/parts/abc-def.m3u8', 'logo': '', 'cats': ['News'], 'catNames': ['News'], 'src': 'plex', 'gridKey': 'reuters-now'},
    {'id': 'pluto:' + KIDS, 'name': 'Little Stars Universe', 'url': f'https://cfd-v4-service-channel-stitcher-use1-1.prd.pluto.tv/stitch/hls/channel/{KIDS}/master.m3u8', 'logo': '', 'cats': ['Kids'], 'catNames': ['Kids'], 'src': 'pluto'},
    {'id': 'link:x', 'name': 'Local News', 'url': 'http://news.example/live.m3u8', 'logo': '', 'cats': [], 'catNames': [], 'src': 'link'},
]
LOG = {'pluto': [], 'plex': [], 'tokens': []}
# a 16x9 picture for the programs (build 248)
import zlib, struct
def _png(w, h, rgb):
    raw = b''.join(b'\x00' + bytes(rgb) * w for _ in range(h))
    ch = lambda t, d: struct.pack('>I', len(d)) + t + d + struct.pack('>I', zlib.crc32(t + d) & 0xffffffff)
    return b'\x89PNG\r\n\x1a\n' + ch(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, 2, 0, 0, 0)) + ch(b'IDAT', zlib.compress(raw)) + ch(b'IEND', b'')
PNG = _png(160, 90, (60, 120, 200))
state = {'down': False}
NOW = time.time()
# Programs placed around the half hour we're in (not just around now), so the one on now still
# rounds to a block containing now whatever minute the test runs (build 244).
BASE = NOW // 1800 * 1800


def iso(t): return datetime.datetime.fromtimestamp(t, datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.000Z')


def pluto_body(cid):
    progs = {BUZZR: [('The Price Is Right', 'Season 12 Episode 4', -120, 1980), ('Match Game', 'Charles Nelson Reilly', 1860, 1800), ('Family Feud', '', 3660, 1800), ('Press Your Luck', '', 5460, 1800)],
             KIDS: [('Maggie and the Ferocious Beast', 'The Big Hat / The Camping Trip', -60, 1740), ('Maggie and the Ferocious Beast', 'Just a Little Off the Top', 1680, 1740)]}[cid]
    tl = []
    for title, ep, off, dur in progs:
        tl.append({'start': iso(BASE + off), 'stop': iso(BASE + off + dur), 'title': title,
                   'episode': {'name': ep or title, 'description': 'A classic game show. ' * 3, 'rating': 'TV-G',
                               'poster16_9': {'path': 'https://images.pluto.tv/episodes/%s-%d/poster16_9.jpg?fm=jpg' % (cid[-4:], off)},
                               'thumbnail': {'path': 'https://images.pluto.tv/episodes/%s-%d/thumbnail.jpg' % (cid[-4:], off)},
                               'series': {'name': title, 'tile': {'path': 'https://images.pluto.tv/series/%s/tile.jpg' % cid[-4:]}}}})
    return {'_id': cid, 'name': 'x', 'timelines': tl}


def plex_body(day):
    t0 = int(BASE) - 60
    return {'MediaContainer': {'Metadata': [
        {'type': 'episode', 'title': 'Markets Open', 'grandparentTitle': 'Reuters Now Live', 'summary': 'Business news.', 'thumb': 'https://provider-static.plex.tv/epg/images/markets.jpg', 'Media': [{'beginsAt': t0, 'endsAt': t0 + 3600}]},
        {'type': 'episode', 'title': 'World Report', 'grandparentTitle': 'Reuters Now Live', 'Media': [{'beginsAt': t0 + 3600, 'endsAt': t0 + 7200}]},
    ]}}


MOCK = """
(function(){
 window.__calls=[]; window.__L={}; window.__emit=function(t,ev){ (window.__L[t]||[]).forEach(function(f){ f(ev); }); };
 var P=new Proxy({}, {get:function(t,k){
   if(k==='then') return undefined;
   if(k==='addListener') return function(n,f){ (window.__L[n]=window.__L[n]||[]).push(f); return Promise.resolve({remove:function(){}}); };
   if(k==='load') return function(a){ window.__calls.push(['load',a.url]); window.__cur=a.id;
      setTimeout(function(){ window.__emit('state',{id:a.id,state:'ready',isPlaying:true,playWhenReady:true,position:0,duration:-1,live:true}); },60);
      return Promise.resolve({}); };
   if(k==='fetchText') return function(a){ return fetch(a.url).then(function(r){ if(!r.ok) throw new Error('HTTP ' + r.status); return r.text(); }).then(function(t){ return { text: t, status: 200 }; }); };
   if(k==='videoState') return function(){ return Promise.resolve({id:null,hasVideo:false}); };
   return function(){ return Promise.resolve({}); };
 }});
 window.Capacitor={isNativePlatform:function(){return true;},getPlatform:function(){return 'android';},Plugins:{AmplifyPlayer:P},convertFileSrc:function(u){return u;}};
})();
"""
SEED = """(function(){ if(!localStorage.getItem('__seeded')){ localStorage.setItem('__seeded','1');
  localStorage.setItem('radioPlayerPlexAccount', JSON.stringify({ token: 'USERTOKEN123', user: 'Mark', servers: [] }));
  localStorage.setItem('radioPlayerVideoChannels', %s);
  localStorage.setItem('radioPlayerVideoTab', 'channels'); } })();""" % json.dumps(json.dumps(CHANNELS))

fails = []
INFO = """(()=>{ var o=document.getElementById('epgInfoOverlay'), p=o.querySelector('.epg-info-panel'); var pic=document.getElementById('epgInfoPic'), img=pic.querySelector('img');
  var r=p.getBoundingClientRect(); var vis=function(id){ var e=document.getElementById(id); return !e.hidden && getComputedStyle(e).display!=='none'; };
  return { open: o.classList.contains('open'), channel: document.getElementById('epgInfoChannel').textContent, show: document.getElementById('epgInfoShow').textContent,
    ep: vis('epgInfoEp') ? document.getElementById('epgInfoEp').textContent : null, meta: document.getElementById('epgInfoMeta').textContent,
    desc: vis('epgInfoDesc') ? document.getElementById('epgInfoDesc').textContent : null, pic: !pic.hidden && img.naturalWidth > 0, picW: Math.round(pic.getBoundingClientRect().width),
    watch: vis('epgInfoWatch'), fits: r.left >= 0 && r.right <= innerWidth + 0.5 && r.top >= 0 && r.bottom <= innerHeight + 0.5 }; })()"""

CORNER = """(()=>{ var b=document.querySelector(arguments_sel); var cs=getComputedStyle(b); return { disabled: b.disabled, label: b.getAttribute('aria-label'), arrow: b.dataset.arrow, op: parseFloat(cs.opacity), hidden: cs.visibility === 'hidden', w: Math.round(b.getBoundingClientRect().width) }; })()"""
async def corner(pg, sel):
    return await pg.evaluate(CORNER.replace('arguments_sel', repr(sel)))
FOOT = """(()=>{ var f=document.querySelector('#nowPlayingScreen .np-hero-foot'), g=document.querySelector('#npCollection .epg'); return { h: Math.round(f.getBoundingClientRect().height),
  gridTop: Math.round(g.getBoundingClientRect().top), collapsed: document.getElementById('nowPlayingScreen').classList.contains('np-foot-collapsed'), saved: localStorage.getItem('radioPlayerNpDetailsHidden') }; })()"""

def check(ok, msg):
    print(('PASS ' if ok else 'FAIL ') + msg)
    if not ok: fails.append(msg)


async def route(r):
    u = urlparse(r.request.url)
    cors = {'Access-Control-Allow-Origin': '*', 'Access-Control-Allow-Headers': '*'}
    if r.request.method == 'OPTIONS': return await r.fulfill(status=204, headers=cors)
    if u.netloc == 'api.pluto.tv' and u.path.startswith('/v2/channels/'):
        cid = u.path.rsplit('/', 1)[1]; q = parse_qs(u.query)
        LOG['pluto'].append((cid, q.get('start', [''])[0], q.get('stop', [''])[0]))
        if state['down']: return await r.fulfill(status=503, headers=cors, body='')
        return await r.fulfill(status=200, content_type='application/json', headers=cors, body=json.dumps(pluto_body(cid)))
    if u.netloc in ('images.pluto.tv', 'provider-static.plex.tv'):
        LOG.setdefault('img', []).append(r.request.url)
        return await r.fulfill(status=200, content_type='image/png', headers=cors, body=PNG)
    if u.netloc == 'epg.provider.plex.tv' and u.path == '/grid':
        q = parse_qs(u.query)
        LOG['plex'].append((q.get('channelGridKey', [''])[0], q.get('date', [''])[0]))
        LOG['tokens'].append(r.request.headers.get('x-plex-token', ''))
        if state['down']: return await r.fulfill(status=503, headers=cors, body='')
        return await r.fulfill(status=200, content_type='application/json', headers=cors, body=json.dumps(plex_body(q.get('date', [''])[0])))
    if '127.0.0.1' in u.netloc: return await r.continue_()
    return await r.abort()



W, HT, DPR = 327, 700, 3.3
CHIPS = "Array.from(document.querySelectorAll('#stationsGrid .epg-cat')).map(function(b){ return b.dataset.cat; })"
CELL = """(url)=>{ var r=Array.from(document.querySelectorAll('%s .epg-row')).find(function(x){ return x.dataset.chUrl===url; }); if(!r) return null;
  var c=r.querySelector('.epg-ch'); c.scrollIntoView({block:'center'}); var b=c.getBoundingClientRect(); return { x: b.left + b.width/2, y: b.top + b.height/2 }; }"""
STATE = "({ sheet: document.getElementById('chSheetOverlay').classList.contains('open'), calls: (window.__calls||[]).filter(function(c){ return c[0]==='load'; }).map(function(c){ return c[1]; }), np: document.getElementById('nowPlayingScreen').style.display })"
LABELS = "Array.from(document.querySelectorAll('#chSheetItems .ch-sheet-item')).map(function(b){ return b.textContent.trim().replace(/\\s+/g,' '); })"


async def touch(pg, cdp, pt, hold_ms):
    await cdp.send('Input.dispatchTouchEvent', {'type': 'touchStart', 'touchPoints': [{'x': pt['x'], 'y': pt['y'], 'id': 1}]})
    await pg.wait_for_timeout(hold_ms)
    await cdp.send('Input.dispatchTouchEvent', {'type': 'touchEnd', 'touchPoints': []})
    await pg.wait_for_timeout(900)


async def run(p, theme):
    T = f'[{theme} {W}]'
    state['down'] = False
    b = await p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
    ctx = await b.new_context(viewport={'width': W, 'height': HT}, device_scale_factor=DPR, is_mobile=True, has_touch=True, color_scheme=theme, locale='en-US', timezone_id='America/New_York')
    await ctx.add_init_script(MOCK); await ctx.add_init_script(AUTO_NOTICE); await ctx.add_init_script(SEED)
    await ctx.add_init_script("try{ localStorage.setItem('radioPlayerTheme', '%s'); }catch(e){}" % theme)
    pg = await ctx.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
    await pg.route('**/*', route)
    cdp = await ctx.new_cdp_session(pg)
    await pg.goto(f'http://127.0.0.1:{PORT}/index.html'); await pg.wait_for_timeout(2500)

    # bottom nav order
    labels = await pg.evaluate("Array.from(document.querySelectorAll('#mobileNav .mobile-nav-btn')).map(function(b){ return b.dataset.nav; })")
    check(labels == ['home', 'library', 'video', 'podcasts', 'search'], f'{T} bottom nav order {labels}')
    await pg.screenshot(path=f'{SHOTS}/b683_nav_{theme}.png', clip={'x': 0, 'y': HT - 110, 'width': W, 'height': 110})
    for n in ('video', 'podcasts', 'video'):
        await pg.evaluate("document.querySelector('.mobile-nav-btn[data-nav=%s]').click()" % n); await pg.wait_for_timeout(1200)
    on = await pg.evaluate("(document.querySelector('#stationsGrid .epg')||{}).nodeType||0")
    check(on == 1, f'{T} Watch (Live TV guide) still opens from its new place')

    # the default chip order, then our own
    chips0 = await pg.evaluate(CHIPS)
    cats0 = [c for c in chips0 if c.startswith('cat:')]
    check(len(cats0) >= 2, f'{T} the guide has categories {chips0}')
    mine = list(reversed(cats0))
    await pg.evaluate("localStorage.setItem('radioPlayerGuideCatOrder', %s)" % json.dumps(json.dumps(mine)))
    await pg.reload(); await pg.wait_for_timeout(2500)
    await pg.evaluate("document.querySelector('.mobile-nav-btn[data-nav=video]').click()"); await pg.wait_for_timeout(1500)
    chips = await pg.evaluate(CHIPS)
    check([c for c in chips if c.startswith('cat:')] == mine, f'{T} chips follow the saved order {chips}')
    await pg.screenshot(path=f'{SHOTS}/b683_guide_{theme}.png')

    # tap plays, nothing opens
    url = CHANNELS[2]['url']
    pt = await pg.evaluate(CELL % '#stationsGrid', url)
    await pg.evaluate("window.__calls=[]")
    await touch(pg, cdp, pt, 60)
    s = await pg.evaluate(STATE)
    check(url in s['calls'] and not s['sheet'], f'{T} a tap plays the channel and does not open the menu {s}')
    await pg.screenshot(path=f'{SHOTS}/b683_tap_{theme}.png')
    await pg.evaluate("document.getElementById('npBackBtn').click()"); await pg.wait_for_timeout(900)

    # hold opens the menu, does not play, and the release doesn't play either
    url = CHANNELS[0]['url']
    pt = await pg.evaluate(CELL % '#stationsGrid', url)
    await pg.evaluate("window.__calls=[]")
    await touch(pg, cdp, pt, 700)
    s = await pg.evaluate(STATE)
    check(s['sheet'] and url not in s['calls'], f'{T} a long press opens the menu and does not play {s}')
    lab = await pg.evaluate(LABELS)
    check(any(x.startswith('Watch Now') for x in lab) and any(x.startswith('Category') for x in lab), f'{T} the menu is the channel menu {lab}')
    await pg.screenshot(path=f'{SHOTS}/b683_menu_{theme}.png')

    # Category list: the chips' order
    await pg.evaluate("Array.from(document.querySelectorAll('#chSheetItems .ch-sheet-item')).find(function(b){ return /^Category/.test(b.textContent.trim()); }).click()"); await pg.wait_for_timeout(600)
    cl = await pg.evaluate("Array.from(document.querySelectorAll('#chSheetItems .ch-cat-opt')).map(function(b){ return b.textContent.trim().replace(/\\s+/g,' '); })")
    names = [c[4:] for c in mine]
    pos = [next((i for i, x in enumerate(cl) if x == n or x.startswith(n + ' ')), -1) for n in names]
    check(-1 not in pos and pos == sorted(pos) and pos[0] == 1, f'{T} Category list starts with the grid order {names} at {pos} in {cl}')
    rest = cl[1 + len(names):]
    check(len(rest) > 5, f'{T} the other categories follow {rest[:6]}')
    await pg.screenshot(path=f'{SHOTS}/b683_cats_{theme}.png')
    await pg.keyboard.press('Escape'); await pg.wait_for_timeout(400)

    # under the playing video: tap plays another channel, hold opens its menu
    await pg.evaluate("window.__calls=[]")
    pt = await pg.evaluate(CELL % '#stationsGrid', CHANNELS[1]['url'])
    await touch(pg, cdp, pt, 60)
    ok = await pg.evaluate("document.getElementById('nowPlayingScreen').style.display")
    check(ok == 'flex', f'{T} Now Playing is open on the channel {ok}')
    url = CHANNELS[0]['url']
    pt = await pg.evaluate(CELL % '#npCollection', url)
    check(pt is not None, f'{T} the guide is under the video')
    await pg.evaluate("window.__calls=[]")
    await touch(pg, cdp, pt, 60)
    s = await pg.evaluate(STATE)
    check(url in s['calls'] and not s['sheet'], f'{T} under the video, a tap plays the channel {s}')
    pt = await pg.evaluate(CELL % '#npCollection', CHANNELS[2]['url'])
    await pg.evaluate("window.__calls=[]")
    await touch(pg, cdp, pt, 700)
    s = await pg.evaluate(STATE)
    check(s['sheet'] and not s['calls'], f'{T} under the video, a long press opens the menu {s}')
    lab = await pg.evaluate(LABELS)
    check(any(l.startswith('Watch Now') for l in lab) and any(l.startswith('Category') for l in lab), f'{T} under the video the menu is the main channel menu, the release tapped nothing in it {lab[:4]}')
    await pg.screenshot(path=f'{SHOTS}/b683_np_menu_{theme}.png')

    # a swipe over the button scrolls, doesn't open the menu
    await pg.keyboard.press('Escape'); await pg.wait_for_timeout(400)
    await pg.evaluate("window.__calls=[]")
    await cdp.send('Input.dispatchTouchEvent', {'type': 'touchStart', 'touchPoints': [{'x': pt['x'], 'y': pt['y'], 'id': 1}]})
    for i in range(1, 8):
        await cdp.send('Input.dispatchTouchEvent', {'type': 'touchMove', 'touchPoints': [{'x': pt['x'], 'y': pt['y'] - 12 * i, 'id': 1}]}); await pg.wait_for_timeout(120)
    await cdp.send('Input.dispatchTouchEvent', {'type': 'touchEnd', 'touchPoints': []}); await pg.wait_for_timeout(700)
    s = await pg.evaluate(STATE)
    check(not s['sheet'] and not s['calls'], f'{T} a swipe starting on the button neither plays nor opens the menu {s}')
    check(not errs, f'{T} no page errors {errs[:3]}')
    await b.close()


async def main():
    async with async_playwright() as p:
        await run(p, 'dark')
        await run(p, 'light')
    print('ALL PASSED' if not fails else f'FAILED {fails}')
asyncio.run(main())
