"""Build 683 (Mark): a channel that played before and is down now reads "Off air" (calm colour, "try
again later" in the player); one that never played, or hasn't for two weeks, reads "Not working" (red).
Run: python3 tests/test_off_air.py (screenshots in /tmp/claude-0/t/shots)"""



import sys as _nsys, os as _nos; _nsys.path.insert(0, _nos.path.dirname(_nos.path.abspath(__file__))); from notice_auto import AUTO_NOTICE
import asyncio, json, os, shutil, threading, http.server, functools, time, datetime
from urllib.parse import urlparse, parse_qs
from playwright.async_api import async_playwright
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = '/tmp/claude-0/t/srv-offair'; SHOTS = '/tmp/claude-0/t/shots'
PORT = 8884
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
   if(k==='load') return function(a){ window.__calls.push(['load',a.url]); window.__cur=a.id; if(window.__failLoad) return Promise.reject(new Error('HTTP 404'));
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
HRS = 3600 * 1000
NOWMS = int(time.time() * 1000)
def link(i, name): return {'id': 'link:' + i, 'name': name, 'url': f'http://{i}.example/live.m3u8', 'logo': '', 'cats': ['News'], 'catNames': ['News'], 'src': 'link'}
# channels with no schedule (a station's newscast stream): the whole row is one block with its status
CH = [link('wesh', 'WESH 2 Orlando'), link('never', 'Never Worked TV'), link('old', 'Old News 7')]
CH[0]['dead'] = True; CH[0]['lastOk'] = NOWMS - 2 * HRS            # played 2 hours ago
CH[1]['dead'] = True                                               # never played
CH[2]['dead'] = True; CH[2]['lastOk'] = NOWMS - 20 * 24 * HRS      # 20 days ago
ROWS = """(()=>Array.from(document.querySelectorAll('#stationsGrid .epg-row')).map(function(r){ var s=r.querySelector('.epg-s'); return { url: r.dataset.chUrl, text: s ? s.textContent : '', cls: s ? s.className : '', color: s ? getComputedStyle(s).color : '' }; }))()"""


async def run(p, theme):
    T = f'[{theme} {W}]'
    state['down'] = False
    b = await p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
    ctx = await b.new_context(viewport={'width': W, 'height': HT}, device_scale_factor=DPR, is_mobile=True, has_touch=True, color_scheme=theme, locale='en-US', timezone_id='America/New_York')
    seed = SEED.replace(json.dumps(json.dumps(CHANNELS)), json.dumps(json.dumps(CH)))
    assert json.dumps(json.dumps(CH)) in seed
    await ctx.add_init_script(MOCK); await ctx.add_init_script(AUTO_NOTICE); await ctx.add_init_script(seed)
    await ctx.add_init_script("try{ localStorage.setItem('radioPlayerTheme', '%s'); }catch(e){}" % theme)
    pg = await ctx.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
    await pg.route('**/*', route)
    await pg.goto(f'http://127.0.0.1:{PORT}/index.html'); await pg.wait_for_timeout(2500)
    await pg.evaluate("document.querySelector('.mobile-nav-btn[data-nav=video]').click()"); await pg.wait_for_timeout(2500)
    rows = {r['url']: r for r in await pg.evaluate(ROWS)}
    a, n, o = rows[CH[0]['url']], rows[CH[1]['url']], rows[CH[2]['url']]
    check(a['text'] == 'Off air' and 'ch-off' in a['cls'], f'{T} played 2 hours ago: "Off air" {a}')
    check(n['text'] == 'Not working' and 'ch-dead' in n['cls'] and n['color'] == 'rgb(229, 83, 75)', f'{T} never played: "Not working" in red {n}')
    check(o['text'] == 'Not working' and 'ch-dead' in o['cls'], f'{T} last played 20 days ago: "Not working" {o}')
    check(a['color'] != n['color'] and a['color'] != 'rgb(229, 83, 75)', f'{T} Off air is not the error red {a["color"]}')
    await pg.screenshot(path=f'{SHOTS}/b683_offair_{theme}.png')

    # failing now: a channel that played before says off air in the player; one that never did, the error
    await pg.evaluate("window.__failLoad = true")
    await pg.evaluate("(url)=>{ var r=Array.from(document.querySelectorAll('#stationsGrid .epg-row')).find(function(x){ return x.dataset.chUrl===url; }); r.querySelector('.epg-ch').click(); }", CH[0]['url'])
    await pg.wait_for_timeout(1800)
    sub = await pg.evaluate("document.getElementById('playerSub') ? document.getElementById('playerSub').textContent : ''")
    check(sub.startswith('Off air right now') and 'try again later' in sub, f'{T} the player says it is off air {sub!r}')
    await pg.screenshot(path=f'{SHOTS}/b683_offair_player_{theme}.png')
    card = await pg.evaluate("(function(){ var e=document.getElementById('npOffAir'); var r=e.getBoundingClientRect(); var cs=getComputedStyle(e); return { hidden: e.hidden, disp: cs.display, w: Math.round(r.width), h: Math.round(r.height), top: Math.round(r.top), sub: document.getElementById('npOffAirSub').textContent, title: e.querySelector('.oa-title').textContent, btn: document.getElementById('npOffAirRetry').getBoundingClientRect().height }; })()")
    check(not card['hidden'] and card['disp'] == 'block' and card['w'] > 300 and card['h'] > 150, f'{T} the off-air test card shows over the picture {card}')
    check(card['title'] == 'OFF-AIR' and card['sub'].startswith('Last on air ') and card['sub'].endswith(' ago'), f'{T} card text {card["sub"]!r}')
    await pg.screenshot(path=f'{SHOTS}/b685_card_{theme}.png')
    # Check again retries (still failing: the card stays) and a good play hides it
    await pg.evaluate("document.getElementById('npOffAirRetry').click()"); await pg.wait_for_timeout(1500)
    check(not await pg.evaluate("document.getElementById('npOffAir').hidden"), f'{T} Check again with the stream still down keeps the card')
    await pg.evaluate("window.__failLoad = false")
    await pg.evaluate("document.getElementById('npOffAirRetry').click()"); await pg.wait_for_timeout(2000)
    check(await pg.evaluate("document.getElementById('npOffAir').hidden"), f'{T} Check again once the stream is back hides the card')
    await pg.evaluate("window.__failLoad = true")
    await pg.evaluate("(url)=>{ var r=Array.from(document.querySelectorAll('#stationsGrid .epg-row')).find(function(x){ return x.dataset.chUrl===url; }); r.querySelector('.epg-ch').click(); }", CH[0]['url']); await pg.wait_for_timeout(1500)
    await pg.evaluate("(url)=>{ var r=Array.from(document.querySelectorAll('#stationsGrid .epg-row')).find(function(x){ return x.dataset.chUrl===url; }); r.querySelector('.epg-ch').click(); }", CH[1]['url'])
    await pg.wait_for_timeout(1800)
    sub = await pg.evaluate("document.getElementById('playerSub').textContent")
    check(await pg.evaluate("document.getElementById('npOffAir').hidden"), f'{T} a channel that never played shows no off-air card')
    check(sub.startswith('Could not play'), f'{T} a channel that never played still shows the error {sub[:60]!r}')

    # a channel that plays again is cleared and remembered
    await pg.evaluate("window.__failLoad = false")
    await pg.evaluate("(url)=>{ var r=Array.from(document.querySelectorAll('#stationsGrid .epg-row')).find(function(x){ return x.dataset.chUrl===url; }); r.querySelector('.epg-ch').click(); }", CH[0]['url'])
    await pg.wait_for_timeout(2000)
    st = await pg.evaluate("JSON.parse(localStorage.getItem('radioPlayerVideoChannels')).map(function(c){ return { n: c.name, dead: !!c.dead, ok: c.lastOk || 0 }; })")
    bz = [c for c in st if c['n'] == 'WESH 2 Orlando'][0]
    check(not bz['dead'] and bz['ok'] > NOWMS - 60 * 1000, f'{T} it plays again: cleared and the time remembered {bz}')
    check(not errs, f'{T} no page errors {errs[:3]}')
    await b.close()


async def main():
    async with async_playwright() as p:
        await run(p, 'dark')
        await run(p, 'light')
    print('ALL PASSED' if not fails else f'FAILED {fails}')
asyncio.run(main())
