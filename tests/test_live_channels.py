"""Build 262: your own channels. The Office, MadTV and Seinfeld (from Plex) and Movies (the phone's
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
ROOT = '/tmp/claude-0/t/srv-livech'; SHOTS = '/tmp/claude-0/t/shots'
PORT = 8862
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


async def run(p, theme, width):
    T = f'[{theme} {width}]'
    b = await p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
    ctx = await b.new_context(viewport={'width': width, 'height': 860}, device_scale_factor=2, is_mobile=True, has_touch=True, color_scheme=theme, locale='en-US', timezone_id='America/New_York')
    await ctx.add_init_script(MOCK); await ctx.add_init_script(AUTO_NOTICE); await ctx.add_init_script(SEED)
    await ctx.add_init_script("try{ localStorage.setItem('radioPlayerTheme', '%s'); }catch(e){}" % theme)
    pg = await ctx.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e) + ' ' + (e.stack or '')[:300]))
    await pg.route('**/*', route)
    await pg.goto(f'http://127.0.0.1:{PORT}/index.html'); await pg.wait_for_timeout(3000)
    await pg.evaluate("document.querySelector('.mobile-nav-btn[data-nav=video]').click()"); await pg.wait_for_timeout(1500)
    g = await grid(pg)
    urls = [r['url'] for r in g['rows']]
    check(urls[:4] == ['amplify-live:office', 'amplify-live:madtv', 'amplify-live:seinfeld', 'amplify-live:movies'] and urls[4:] == [CHANNELS[0]['url']],
          f'{T} the four channels head the Live TV guide, then the added channels {urls}')
    check(g['headings'] == 0, f'{T} no separate heading for them ({g["headings"]})')
    names = [r['name'] for r in g['rows'][:4]]
    check(names == ['The Office (US)', 'MADtv', 'Seinfeld', 'Movies'], f'{T} named as the library names them {names}')
    check(not any(r['name'] == 'Friends' for r in g['rows']), f'{T} a show that isn’t a channel isn’t there')
    # The schedule: exact times, matching the independent calculation
    t0 = g['t0'] / 1000
    of = g['rows'][0]['blocks']
    items = lineup('10')
    i, s, x = on_at(items, t0)
    want = []
    while s < t0 + 12 * 3600:
        ss, ee = max(s, t0), min(s + x[4], t0 + 12 * 3600)
        if ee - ss >= 60: want.append((x[1], 'S%d E%d' % (x[2], x[3]), int(ss), int(ee)))
        s += x[4]; i = (i + 1) % len(items); x = items[i]
    got = [(b2['t'], b2['s'], b2['ss'] // 1000, b2['ee'] // 1000) for b2 in of]
    check(len(got) == len(want) and all(a[:2] == w[:2] and abs(a[2] - w[2]) <= 1 and abs(a[3] - w[3]) <= 1 for a, w in zip(got, want)),
          f'{T} The Office: every episode at its real time, in order, no special ({got[:3]} vs {want[:3]}, {len(got)}/{len(want)})')
    full = [b2 for b2 in of if b2['ss'] // 1000 > t0][:3]
    check(all(abs(b2['w'] - (1320 / 1800 * 124 - 4)) < 0.6 for b2 in full), f'{T} a 22-minute episode is 22 minutes wide (not rounded to the half hour) {[round(b2["w"],1) for b2 in full]}')
    nowb = [b2 for b2 in of if b2['now']]
    i_now, s_now, x_now = on_at(items, time.time())
    check(len(nowb) == 1 and nowb[0]['t'] == x_now[1], f'{T} what’s on now is the scheduled episode ({[b2["t"] for b2 in nowb]} vs {x_now[1]})')
    mv = g['rows'][3]['blocks']
    mv_titles = set(b2['t'] for b2 in mv)
    check(mv_titles <= {'Alien', 'Heat', 'Up'} and len(mv_titles) >= 2 and 'Plex Only Movie' not in mv_titles and 'Broken' not in mv_titles,
          f'{T} Movies plays the phone’s movies only, those with a known length {mv_titles}')
    await pg.evaluate("window.scrollTo(0,0)"); await pg.wait_for_timeout(300)
    await pg.screenshot(path=f'{SHOTS}/livech-guide-{theme}-{width}.png')

    # A later program opens its details
    await pg.evaluate("(function(){ var r=document.querySelector('#stationsGrid .epg-row[data-ch-url=\"amplify-live:office\"]'); r.querySelector('.epg-prog.info').click(); })()"); await pg.wait_for_timeout(700)
    info = await pg.evaluate("""(()=>{ var o=document.getElementById('epgInfoOverlay'); var pic=document.getElementById('epgInfoPic');
      return { open: o.classList.contains('open'), ch: document.getElementById('epgInfoChannel').textContent, show: document.getElementById('epgInfoShow').textContent,
        ep: document.getElementById('epgInfoEp').textContent, pic: !pic.hidden && pic.querySelector('img').naturalWidth > 0, src: pic.querySelector('img').getAttribute('src') || '',
        desc: document.getElementById('epgInfoDesc').textContent, watch: !document.getElementById('epgInfoWatch').hidden }; })()""")
    check(info['open'] and info['ch'] == 'The Office (US)' and info['show'].startswith('Office S') and info['ep'].startswith('S') and info['pic'] and info['src'].startswith(PLEX) and 'mockumentary' in info['desc'] and not info['watch'],
          f'{T} a later episode opens its details: title, S/E, its picture from the home server (http kept), the show’s summary {info}')
    await pg.screenshot(path=f'{SHOTS}/livech-info-{theme}-{width}.png')
    await pg.evaluate("document.getElementById('epgInfoClose').click()"); await pg.wait_for_timeout(300)

    # Tune in to The Office
    await pg.evaluate("window.__loads=[]; window.__seeks=[]")
    i_now, s_now, x_now = on_at(items, time.time())
    await tap_now(pg, 'amplify-live:office'); await pg.wait_for_timeout(2500)
    ld = await pg.evaluate("window.__loads.map(function(a){ return { url: a.url, engine: a.engine || '', start: a.start || 0 }; })")
    seeks = await pg.evaluate("window.__seeks")
    want_off = time.time() - s_now
    check(len(ld) >= 1 and ('/library/parts/%s/' % x_now[0]) in ld[-1]['url'] and ld[-1]['engine'] != 'vlc', f'{T} tuning in plays the episode on now from Plex {ld[-1:]}')
    check(seeks and abs(seeks[-1] - want_off) < 6, f'{T} it joins the episode where the schedule is ({seeks[-1:]} vs {want_off:.0f}s)')
    np = await pg.evaluate(NP)
    check(np['open'] and np['channel'] and np['name'] == 'The Office (US)' and np['sub'] == 'S%d E%d · %s' % (x_now[2], x_now[3], x_now[1]),
          f'{T} Now Playing: the channel’s name, the episode under it {np["name"]!r} {np["sub"]!r}')
    check(np['live'] and not np['seek'] and not np['skip'], f'{T} it’s live: LIVE, no seek bar, no skip buttons {np}')
    check(np['bar'] == 'The Office (US)', f'{T} the player bar names the channel {np["bar"]!r}')
    ng = await grid(pg, '#npCollection .epg')
    check(np['grid'] and ng and [r['url'] for r in ng['rows']][:4] == urls[:4] and ng['rows'][0]['playing'] and not any(r['playing'] for r in ng['rows'][1:]),
          f'{T} the guide is under it, this channel marked playing')
    await pg.evaluate("document.getElementById('nowPlayingScreen').scrollTop = 0"); await pg.wait_for_timeout(300)
    await pg.screenshot(path=f'{SHOTS}/livech-np-{theme}-{width}.png')
    # Its progress isn't kept as the episode's (no Continue Watching for it), the channel is
    cid = await pg.evaluate("window.__cur")
    await pg.evaluate("window.__emit('progress', { id: %s, position: %f, duration: 1320 })" % (json.dumps(cid), want_off + 30)); await pg.wait_for_timeout(300)
    await pg.evaluate("document.getElementById('npPlayBtn').click()"); await pg.wait_for_timeout(600)
    prog = await pg.evaluate("Object.keys(JSON.parse(localStorage.getItem('radioPlayerVideoProgress') || '{}'))")
    hist = await pg.evaluate("(JSON.parse(localStorage.getItem('radioPlayerChannelHistory') || '[]')[0] || {}).url")
    check(not any(x_now[0] in k for k in prog), f'{T} the episode’s own progress isn’t touched {prog}')
    check(hist == 'amplify-live:office', f'{T} the channel goes to Continue Watching as a channel ({hist})')
    await pg.evaluate("document.getElementById('npPlayBtn').click()"); await pg.wait_for_timeout(600)

    # It ends (early, before the schedule says): the next episode comes on from the top
    await pg.evaluate("window.__loads=[]; window.__seeks=[]")
    cid = await pg.evaluate("window.__cur")
    await pg.evaluate("window.__emit('state', { id: %s, state: 'ended', isPlaying: false, playWhenReady: false, position: 1320, duration: 1320 })" % json.dumps(cid)); await pg.wait_for_timeout(2500)
    nxt = items[(i_now + 1) % len(items)]
    ld = await pg.evaluate("window.__loads.map(function(a){ return a.url; })")
    seeks = await pg.evaluate("window.__seeks")
    np = await pg.evaluate(NP)
    check(ld and ('/library/parts/%s/' % nxt[0]) in ld[-1] and not any(s2 > 3 for s2 in seeks), f'{T} when it ends the next episode comes on, from the top {ld[-1:]} {seeks}')
    check(np['open'] and np['sub'] == 'S%d E%d · %s' % (nxt[2], nxt[3], nxt[1]), f'{T} Now Playing follows it {np["sub"]!r}')

    # Favourite the channel from Now Playing: the channel is the favourite, not the episode
    await pg.evaluate("document.getElementById('npFavBtn').click()"); await pg.wait_for_timeout(500)
    favs = await pg.evaluate("JSON.parse(localStorage.getItem('radioPlayerFavorites') || '[]').map(function(f){ return [f.liveCh || '', f.type || '', f.name]; })")
    check(any(f[0] == 'amplify-live:office' and f[1] != 'video' for f in favs), f'{T} the heart favourites the channel {favs}')
    ng = await grid(pg, '#npCollection .epg')
    check(ng['rows'][0]['url'] == 'amplify-live:office' and ng['rows'][0]['heart'], f'{T} it keeps its place at the top, with a heart')

    # Movies: the phone's movie on now, opened by VLC at the right place
    await pg.evaluate("window.__loads=[]; window.__seeks=[]")
    await tap_now(pg, 'amplify-live:movies', '#npCollection'); await pg.wait_for_timeout(2500)
    ld = await pg.evaluate("window.__loads.map(function(a){ return { url: a.url, engine: a.engine || '', start: a.start || 0 }; })")
    np = await pg.evaluate(NP)
    nowm = [b2 for b2 in (await grid(pg, '#npCollection .epg'))['rows'][3]['blocks'] if b2['now']][0]
    dur = {'Alien': 7020, 'Heat': 10200, 'Up': 5760}[nowm['t']]
    # the block's start is cut at the guide's left edge; its end is the movie's real end
    off = time.time() - (nowm['ee'] / 1000 - dur)
    check(ld and ld[-1]['url'].startswith('content://tree/movies/') and nowm['t'] in ld[-1]['url'] and ld[-1]['engine'] == 'vlc' and abs(ld[-1]['start'] - off) < 6,
          f'{T} Movies: the phone’s movie on now opens in VLC where the schedule is {ld[-1:]} ~{off:.0f}s')
    check(np['name'] == 'Movies' and np['sub'].startswith(nowm['t']) and np['live'], f'{T} Now Playing: Movies, the movie and its year under it {np["sub"]!r}')
    await pg.screenshot(path=f'{SHOTS}/livech-np-movies-{theme}-{width}.png')

    # Stop: back to the Live TV guide
    await pg.evaluate("document.getElementById('vctlStop').click()"); await pg.wait_for_timeout(800)
    st = await pg.evaluate("[document.getElementById('nowPlayingScreen').style.display, !!document.querySelector('#stationsGrid .epg')]")
    check(st[0] != 'flex' and st[1], f'{T} Stop closes it and shows the Live TV guide {st}')
    # Play it again from Continue Watching on Home: tunes in to what's on now (not a stream)
    await pg.evaluate("document.querySelector('.mobile-nav-btn[data-nav=home]').click()"); await pg.wait_for_timeout(1200)
    await pg.evaluate("window.__loads=[]")
    tapped = await pg.evaluate("""(()=>{ var t=Array.from(document.querySelectorAll('[data-key="livech:amplify-live:office"]')).filter(function(x){ return x.offsetParent; })[0]; if(!t) return false; t.click(); return true; })()""")
    await pg.wait_for_timeout(2500)
    ld = await pg.evaluate("window.__loads.map(function(a){ return a.url; })")
    i2, s2, x2 = on_at(items, time.time())
    check(tapped and ld and ('/library/parts/%s/' % x2[0]) in ld[-1], f'{T} The Office in Continue Watching on Home tunes in to what’s on now {tapped} {ld[-1:]}')
    await pg.evaluate("window.scrollTo(0,0)"); await pg.wait_for_timeout(300)
    await pg.screenshot(path=f'{SHOTS}/livech-home-{theme}-{width}.png')
    check(not errs, f'{T} no page errors {errs[:3]}')
    await b.close()


async def main():
    async with async_playwright() as p:
        await run(p, 'dark', 412)
        await run(p, 'light', 360)
    print('ALL PASSED' if not fails else f'FAILED {len(fails)}: {fails}')

asyncio.run(main())
