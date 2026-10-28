"""(copied set-up from test_live_channels.py) Build 262: your own channels. The Office, MadTV and Seinfeld (from Plex) and Movies (the phone's
own movies) play as "live" channels at the top of the Live TV guide, no heading. Their videos run
end to end from a fixed start date (2026-01-01, local midnight) and repeat, so the guide shows the
real schedule (exact times, not rounded to half hours) and tuning in starts the video on now at
the right place (Plex: a seek after loading; the phone's movies: VLC opens there). Now Playing is
the channel layout: LIVE, no seek bar or skip buttons, the episode under the channel's name, the
guide under it. When a video ends the next one comes on. The videos' own progress isn't touched
(Continue Watching keeps the channel). A show the library doesn't have isn't shown; a movie
without a known length is left out; Plex movies aren't on Movies.
Run: python3 tests/test_live_channels.py (screenshots in /tmp/claude-0/t/shots)"""

import sys as _nsys, os as _nos; _nsys.path.insert(0, _nos.path.dirname(_nos.path.abspath(__file__))); from notice_auto import AUTO_NOTICE
import asyncio, json, os, shutil, threading, http.server, functools, time, datetime, zlib, struct
from zoneinfo import ZoneInfo
from urllib.parse import urlparse
from playwright.async_api import async_playwright
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = '/tmp/claude-0/t/srv-archnative'; SHOTS = '/tmp/claude-0/t/shots'
PORT = 8868
shutil.rmtree(ROOT, ignore_errors=True)
os.makedirs(ROOT, exist_ok=True); os.makedirs(SHOTS, exist_ok=True)
shutil.copy(os.path.join(HERE, '..', 'www', 'index.html'), ROOT)
H = functools.partial(http.server.SimpleHTTPRequestHandler, directory=ROOT); H.log_message = lambda *a: None
srv = http.server.ThreadingHTTPServer(('127.0.0.1', PORT), H); threading.Thread(target=srv.serve_forever, daemon=True).start()

PLEX = 'http://192.168.1.50:32400'
SRV = 'srv1abcdef99'
NOWS = int(time.time())
# The Plex library: The Office (US) 2 seasons x 6 (22 min) plus a special, MADtv 4 x 44 min,
# Seinfeld 5 x 23 min, Friends (not a channel). One movie only on Plex.
SHOWS = [{'k': '10', 't': 'The Office (US)', 'th': '/library/metadata/10/thumb/1', 'a': '/library/metadata/10/art/1', 's': 'A mockumentary on a group of typical office workers.'},
         {'k': '20', 't': 'MADtv', 'th': '/library/metadata/20/thumb/1', 'a': '', 's': 'Sketch comedy.'},
         {'k': '30', 't': 'Seinfeld', 'th': '/library/metadata/30/thumb/1', 'a': '', 's': 'A show about nothing.'},
         {'k': '40', 't': 'Friends', 'th': '/library/metadata/40/thumb/1', 'a': '', 's': ''}]
EPS = []
def ep(gk, st, sn, en, title, d):
    k = '%s%d%02d' % (gk, sn, en)
    EPS.append({'k': k, 'gk': gk, 'st': st, 'sn': sn, 'en': en, 't': title, 'th': '/library/metadata/%s/thumb/1' % k,
                'p': '/library/parts/%s/file.mkv' % k, 'w': 1280, 'h': 720, 'f': 'e%s.mkv' % k, 'd': d, 'ad': NOWS - 9000, 'vo': 0, 'vc': 0, 'lv': 0, 'sec': '1'})
ep('10', 'The Office (US)', 0, 1, 'Blooper Reel', 600)
for s in (1, 2):
    for e in range(1, 7):
        ep('10', 'The Office (US)', s, e, 'Office S%dE%d' % (s, e), 1320)
for e in range(1, 5): ep('20', 'MADtv', 1, e, 'Mad %d' % e, 2640)
for e in range(1, 6): ep('30', 'Seinfeld', 1, e, 'The Seinfeld %d' % e, 1380)
for e in range(1, 4): ep('40', 'Friends', 1, e, 'Friends %d' % e, 1320)
MOVIES = [{'k': '900', 't': 'Plex Only Movie', 'y': '2001', 's': '', 'th': '', 'a': '', 'p': '/library/parts/900/file.mkv', 'w': 1920, 'h': 1080, 'f': 'p.mkv', 'd': 6000, 'ad': NOWS - 9000, 'vo': 0, 'vc': 0, 'lv': 0, 'sec': '2'}]
LIB = {'serverId': SRV, 'at': NOWS * 1000, 'gv': 1, 'sections': [{'key': '1', 'title': 'TV Shows', 'type': 'show', 'n': 4}, {'key': '2', 'title': 'Movies', 'type': 'movie', 'n': 1}],
       'movies': MOVIES, 'shows': SHOWS, 'episodes': EPS}
ACCT = {'token': 'USERTOK', 'user': 'Mark', 'servers': [{'id': SRV, 'name': 'Home', 'token': 'SRVTOK', 'owned': True,
        'conns': [{'uri': PLEX, 'local': True, 'relay': False}]}], 'serverId': SRV, 'base': PLEX}
# The phone's movies (one with no known length: left out).
LOCAL = [('Alien (1979).mkv', 7020), ('Heat (1995).mkv', 10200), ('Up (2009).mp4', 5760), ('Broken (2010).avi', 0)]
FILES = [{'uri': 'content://tree/movies/' + n.replace(' ', '%20'), 'name': n, 'relPath': 'Movies/' + n, 'size': 900000000, 'lastModified': NOWS * 1000 - 5000, 'video': True, 'tree': 'content://tree/movies'} for n, d in LOCAL]
INFO = {f['uri']: {'d': d, 'w': 1920, 'h': 1080, 't': ''} for f, (n, d) in zip(FILES, LOCAL)}
BUZZR = '5ef3a4c2ff6a3f0007a28f69'
CHANNELS = [{'id': 'pluto:' + BUZZR, 'name': 'Buzzr', 'url': f'https://cfd-v4-service-channel-stitcher-use1-1.prd.pluto.tv/stitch/hls/channel/{BUZZR}/master.m3u8', 'logo': '', 'cats': ['Classic TV'], 'catNames': ['Classic TV'], 'src': 'pluto'}]

# The schedule, worked out here independently: local midnight 2026-01-01 in New York.
EPOCH = datetime.datetime(2026, 1, 1, tzinfo=ZoneInfo('America/New_York')).timestamp()
def lineup(gk):
    items = [e for e in EPS if e['gk'] == gk and e['sn'] > 0]
    items.sort(key=lambda e: (e['sn'], e['en']))
    return [(e['k'], e['t'], e['sn'], e['en'], e['d']) for e in items]
def on_at(items, t):
    total = sum(x[4] for x in items)
    off = (t - EPOCH) % total
    acc = 0
    for i, x in enumerate(items):
        if acc <= off < acc + x[4]: return i, t - (off - acc), x
        acc += x[4]

def _png(w, h, rgb):
    raw = b''.join(b'\x00' + bytes(rgb) * w for _ in range(h))
    ch = lambda t, d: struct.pack('>I', len(d)) + t + d + struct.pack('>I', zlib.crc32(t + d) & 0xffffffff)
    return b'\x89PNG\r\n\x1a\n' + ch(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, 2, 0, 0, 0)) + ch(b'IDAT', zlib.compress(raw)) + ch(b'IEND', b'')
PNG = _png(160, 90, (70, 110, 170))

MOCK = """
(function(){
 window.__loads=[]; window.__seeks=[]; window.__L={}; window.__emit=function(t,ev){ (window.__L[t]||[]).forEach(function(f){ f(ev); }); };
 var P=new Proxy({}, {get:function(t,k){
   if(k==='then') return undefined;
   if(k==='addListener') return function(n,f){ (window.__L[n]=window.__L[n]||[]).push(f); return Promise.resolve({remove:function(){}}); };
   if(k==='load') return function(a){ window.__loads.push(a); window.__cur=a.id;
      var d = window.__durFor ? window.__durFor(a.url) : 1320;
      setTimeout(function(){ window.__emit('state',{id:a.id,state:'ready',isPlaying:true,playWhenReady:true,position:a.start||0,duration:d}); },80);
      return Promise.resolve({}); };
   if(k==='seek') return function(a){ window.__seeks.push(a.position); return Promise.resolve({}); };
   if(k==='fetchText') return function(a){ return fetch(a.url).then(function(r){ if(!r.ok) throw new Error('HTTP ' + r.status); return r.text(); }).then(function(t){ return { text: t, status: 200 }; }); };
   if(k==='videoState') return function(){ return Promise.resolve({id:null,hasVideo:false}); };
   if(k==='videoInfo') return function(){ return Promise.reject(new Error('no')); };
   return function(){ return Promise.resolve({}); };
 }});
 window.Capacitor={isNativePlatform:function(){return true;},getPlatform:function(){return 'android';},Plugins:{AmplifyPlayer:P},convertFileSrc:function(u){return u;}};
})();
"""
SEED = """(function(){ if(!localStorage.getItem('__seeded')){ localStorage.setItem('__seeded','1');
  localStorage.setItem('radioPlayerPlexAccount', %s);
  var lib = %s; lib.at = Date.now(); localStorage.setItem('radioPlayerPlexLib', JSON.stringify(lib));
  localStorage.setItem('radioPlayerVideoFiles', %s);
  localStorage.setItem('radioPlayerVideoInfo', %s);
  localStorage.setItem('radioPlayerVideoChannels', %s);
  localStorage.setItem('radioPlayerVideoTab', 'channels'); } })();""" % tuple(json.dumps(json.dumps(x)) for x in (ACCT, LIB, FILES, INFO, CHANNELS))
SEED = SEED.replace("var lib = %s" % json.dumps(json.dumps(LIB)), "var lib = JSON.parse(%s)" % json.dumps(json.dumps(LIB)))

fails = []
def check(ok, msg):
    print(('PASS ' if ok else 'FAIL ') + msg)
    if not ok: fails.append(msg)

CORS = {'Access-Control-Allow-Origin': '*', 'Access-Control-Allow-Headers': '*'}
async def route(r):
    u = urlparse(r.request.url)
    if r.request.method == 'OPTIONS': return await r.fulfill(status=204, headers=CORS)
    if r.request.url.startswith(PLEX):
        if u.path == '/identity': return await r.fulfill(status=200, content_type='application/json', headers=CORS, body='{"MediaContainer":{}}')
        if '/photo/' in u.path: return await r.fulfill(status=200, content_type='image/png', headers=CORS, body=PNG)
        return await r.fulfill(status=404, headers=CORS, body='')
    if u.netloc == 'api.pluto.tv': return await r.fulfill(status=200, content_type='application/json', headers=CORS, body='{"timelines":[]}')
    if '127.0.0.1' in u.netloc: return await r.continue_()
    return await r.abort()

GRID = """(()=>{ var w=document.querySelector(arguments_sel); if(!w) return null;
  return { t0: Number(w.dataset.t0), rows: Array.from(w.querySelectorAll('.epg-row')).map(function(r){ var ch=r.querySelector('.epg-ch');
    return { url: r.dataset.chUrl, name: ch.textContent.trim(), playing: ch.classList.contains('playing'), heart: !!ch.querySelector('.epg-heart'),
      blocks: Array.from(r.querySelectorAll('.epg-prog')).map(function(b){ return { t: b.querySelector('.epg-t').textContent, s: (b.querySelector('.epg-s')||{}).textContent||'',
        left: parseFloat(b.style.left), w: parseFloat(b.style.width), now: b.classList.contains('now'), ss: Number(b.dataset.s), ee: Number(b.dataset.e) }; }) }; }),
    headings: w.parentNode.querySelectorAll('.ch-group-head, .ch-row-label').length }; })()"""
async def grid(pg, sel='#stationsGrid .epg'):
    return await pg.evaluate(GRID.replace('arguments_sel', repr(sel)))
NP = """(()=>{ var n=document.getElementById('nowPlayingScreen'); var v=document.querySelector('.vctl'); var vis=function(id){ var e=document.getElementById(id); return !!e && getComputedStyle(e).display!=='none'; };
  return { open: n.style.display==='flex', channel: n.classList.contains('np-channel'), name: document.getElementById('npName').textContent, sub: document.getElementById('npSub').textContent,
    live: !!v && v.classList.contains('live'), seek: vis('npSeek'), skip: vis('npSkipBackBtn') || vis('npSkipFwdBtn'), grid: !!document.querySelector('#npCollection .epg'),
    bar: document.getElementById('playerName') ? document.getElementById('playerName').textContent : '' }; })()"""

async def tap_now(pg, url, sel='#stationsGrid'):
    await pg.evaluate("(function(u, s){ var r=Array.from(document.querySelectorAll(s + ' .epg-row')).filter(function(x){ return x.dataset.chUrl===u; })[0]; r.querySelector('.epg-prog.now').click(); })(%s, %s)" % (json.dumps(url), json.dumps(sel)))




async def route2(r):
    u = urlparse(r.request.url)
    if 'archive.org' in u.netloc:
        if 'advancedsearch' in u.path: return await r.fulfill(status=200, content_type='application/json', headers=CORS, body=json.dumps({'response': {'docs': [{'identifier': 'pop%d' % i, 'title': 'Popeye %d' % i, 'mediatype': 'movies', 'downloads': 100 - i} for i in range(1, 4)]}}))
        if '/metadata/' in u.path: return await r.fulfill(status=200, content_type='application/json', headers=CORS, body=json.dumps({'files': [{'name': 'x.mp4', 'format': 'h.264', 'size': '10', 'length': '600'}]}))
        return await r.fulfill(status=200, content_type='image/png', headers=CORS, body=PNG)
    return await route(r)

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
        ctx = await b.new_context(viewport={'width': 390, 'height': 860}, device_scale_factor=2, is_mobile=True, has_touch=True, color_scheme='dark', locale='en-US', timezone_id='America/New_York')
        await ctx.add_init_script(MOCK); await ctx.add_init_script(AUTO_NOTICE); await ctx.add_init_script(SEED)
        await ctx.add_init_script("localStorage.setItem('radioPlayerVideoTab','channels');")
        pg = await ctx.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e) + ' ' + (e.stack or '')[:300]))
        await pg.route('**/*', route2)
        await pg.goto(f'http://127.0.0.1:{PORT}/index.html'); await pg.wait_for_timeout(2500)
        await pg.evaluate("""localStorage.setItem('radioPlayerVideoChannels', JSON.stringify(JSON.parse(localStorage.getItem('radioPlayerVideoChannels')).concat([{ id: 'archive:c:classic_cartoons', name: 'Classic Cartoons', url: 'amplify-archive:c:classic_cartoons', logo: '', cats: ['archive.org'], catNames: ['Archive.org'], src: 'archive', archive: { collection: 'classic_cartoons' } }])))""")
        await pg.reload(); await pg.wait_for_timeout(2500)
        await pg.evaluate("document.querySelector('.mobile-nav-btn[data-nav=video]').click()"); await pg.wait_for_timeout(1500)
        await pg.evaluate("window.__loads=[]")
        await tap_now(pg, 'amplify-archive:c:classic_cartoons'); await pg.wait_for_timeout(2500)
        ld = await pg.evaluate("window.__loads.map(function(a){ return a.url; })")
        check(ld and 'archive.org/download/pop1/' in ld[-1], f'the channel loads the first show in the native player {ld[-1:]}')
        # the native player reports a picture: the page draws it through the native view (not its own <video>)
        cid = await pg.evaluate("window.__cur")
        await pg.evaluate("window.__emit('video', { id: %s, hasVideo: true, width: 640, height: 480 })" % json.dumps(cid)); await pg.wait_for_timeout(600)
        st = await pg.evaluate("({on: document.getElementById('nowPlayingScreen').classList.contains('np-video-on'), stream: document.getElementById('nowPlayingScreen').classList.contains('np-video-stream'), vsrc: document.getElementById('npVideo').getAttribute('src') || ''})")
        check(st['on'] and st['stream'] and not st['vsrc'], f'the picture is on by itself, drawn natively, not by the page’s <video> {st}')
        np = await pg.evaluate("({ch: document.getElementById('nowPlayingScreen').classList.contains('np-channel'), tg: getComputedStyle(document.getElementById('npVideoToggle')).display, grid: !!document.querySelector('#npCollection .epg'), rows: Array.from(document.querySelectorAll('#npCollection .epg-row')).map(function(r){return r.dataset.chUrl;})})")
        check(np['ch'] and np['tg'] == 'none' and np['grid'] and 'amplify-archive:c:classic_cartoons' in np['rows'], f'channel layout with the guide grid under the video {np}')
        await pg.screenshot(path=f'{SHOTS}/archch-native.png')
        check(not errs, f'no page errors {errs[:3]}')
        await b.close()
    print('FAILS', len(fails)); raise SystemExit(1 if fails else 0)
asyncio.run(main())
