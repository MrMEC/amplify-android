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
        if 'advancedsearch' in u.path: return await r.fulfill(status=200, content_type='application/json', headers=CORS, body=json.dumps({'response': {'docs': [{'identifier': 'pop%d' % i, 'title': 'Popeye %d' % i + (' and a remarkably long title that keeps going for many words to test wrapping' * (2 if i == 1 else 0)), 'creator': ('Fleischer Studios Paramount Famous Lasky Corporation ' * (4 if i == 1 else 0)) or None, 'year': '1950', 'mediatype': 'movies', 'downloads': 100 - i} for i in range(1, 4)]}}))
        if '/metadata/show1' in u.path: return await r.fulfill(status=200, content_type='application/json', headers=CORS, body=json.dumps({'files': [{'name': 't%d.mp3' % i, 'format': 'VBR MP3', 'track': str(i), 'title': 'Song %d' % i, 'length': '200'} for i in (1, 2, 3)]}))
        if '/metadata/' in u.path: return await r.fulfill(status=200, content_type='application/json', headers=CORS, body=json.dumps({'files': [{'name': 'x.mp4', 'format': 'h.264', 'size': '10', 'length': '600'}]}))
        return await r.fulfill(status=200, content_type='image/png', headers=CORS, body=PNG)
    return await route(r)

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
        ctx = await b.new_context(viewport={'width': 390, 'height': 860}, device_scale_factor=2, is_mobile=True, has_touch=True, color_scheme='dark', locale='en-US', timezone_id='America/New_York')
        await ctx.add_init_script(MOCK); await ctx.add_init_script(AUTO_NOTICE); await ctx.add_init_script(SEED)
        await ctx.add_init_script("localStorage.setItem('radioPlayerVideoTab','channels');")
        await ctx.add_init_script("window.__dt=0; (function(){ var n=Date.now; Date.now=function(){ return n.call(Date)+window.__dt; }; })();")
        pg = await ctx.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e) + ' ' + (e.stack or '')[:300]))
        await pg.route('**/*', route2)
        await pg.goto(f'http://127.0.0.1:{PORT}/index.html'); await pg.wait_for_timeout(2500)
        await pg.evaluate("""localStorage.setItem('radioPlayerVideoChannels', JSON.stringify(JSON.parse(localStorage.getItem('radioPlayerVideoChannels')).concat([{ id: 'archive:c:classic_cartoons', name: 'Classic Cartoons', url: 'amplify-archive:c:classic_cartoons', logo: '', cats: ['archive.org'], catNames: ['Archive.org'], src: 'archive', archive: { collection: 'classic_cartoons' } }])))""")
        await pg.reload(); await pg.wait_for_timeout(2500)
        await pg.evaluate("document.querySelector('.mobile-nav-btn[data-nav=video]').click()"); await pg.wait_for_timeout(2500)
        # The schedule, worked out here: three 10-minute cartoons end to end from 2026-01-01 local midnight
        def on_now(t):
            off = (t - EPOCH) % 1800
            return int(off // 600), off % 600, t - (off % 600)
        g = await grid(pg)
        row = [r for r in g['rows'] if r['url'] == 'amplify-archive:c:classic_cartoons'][0]
        blocks = [b2 for b2 in row['blocks'] if b2['ss'] // 1000 > g['t0'] / 1000][:4]
        okb = all(abs((b2['ee'] - b2['ss']) / 1000 - 600) < 2 and abs(((b2['ss'] / 1000 - EPOCH) % 600)) < 2 for b2 in blocks)
        idx0 = int(((blocks[0]['ss'] / 1000 - EPOCH) % 1800) // 600) if blocks else -1
        check(len(blocks) >= 3 and okb and blocks[0]['t'] == 'Popeye %d' % (idx0 + 1), f'guide: each cartoon at its real time, 10 minutes each {[(b2["t"], (b2["ee"]-b2["ss"])//1000) for b2 in blocks]}')
        nowb = [b2 for b2 in row['blocks'] if b2['now']]
        i_now, off_now, s_now = on_now(time.time())
        check(len(nowb) == 1 and nowb[0]['t'] == 'Popeye %d' % (i_now + 1), f'what’s on now is the scheduled cartoon {[b2["t"] for b2 in nowb]} vs Popeye {i_now + 1}')
        await pg.screenshot(path=f'{SHOTS}/archlive-guide.png')
        # Tune in: the cartoon on now, joined where the schedule is
        await pg.evaluate("window.__loads=[]; window.__seeks=[]")
        await tap_now(pg, 'amplify-archive:c:classic_cartoons'); await pg.wait_for_timeout(2500)
        la = await pg.evaluate("window.__loads.length ? window.__loads[window.__loads.length-1] : null")
        i_now, off_now, s_now = on_now(time.time())
        check(la and ('archive.org/download/pop%d/' % (i_now + 1)) in la['url'], f'tuning in plays the cartoon on now {la and la["url"]}')
        check(la and abs((la.get('start') or 0) - off_now) < 6 and la.get('engine') != 'vlc', f'it joins in progress where the schedule is ({la and la.get("start")} vs {off_now:.0f}s), on the phone’s player')
        np = await pg.evaluate(NP)
        check(np['open'] and np['channel'] and np['live'] and not np['seek'] and not np['skip'], f'Now Playing is live: LIVE, no seek bar, no skip buttons {np}')
        check(np['name'] == 'Classic Cartoons' and np['sub'].startswith('Popeye %d' % (i_now + 1)), f'the channel’s name, the cartoon under it {np["name"]!r} {np["sub"]!r}')
        check(np['grid'], 'the guide grid is under the video')
        # the bar and the range can't be used to skip
        rng = await pg.evaluate("(function(){ var r=document.getElementById('vctlRange'), l=document.getElementById('vctlLive'); return getComputedStyle(r).visibility + '|' + getComputedStyle(l).display; })()")
        check(rng == 'hidden|block', f'the video controls show LIVE, no scrubber {rng}')
        # and dragging it anyway does nothing
        await pg.evaluate("window.__seeks=[]; var r=document.getElementById('vctlRange'); r.value='900'; r.dispatchEvent(new Event('input',{bubbles:true})); r.dispatchEvent(new Event('change',{bubbles:true}));"); await pg.wait_for_timeout(400)
        check(await pg.evaluate("window.__seeks.length") == 0, 'no seeking')
        # the native player reports a picture: drawn natively
        cid = await pg.evaluate("window.__cur")
        await pg.evaluate("window.__emit('video', { id: %s, hasVideo: true, width: 640, height: 480 })" % json.dumps(cid)); await pg.wait_for_timeout(600)
        st = await pg.evaluate("({on: document.getElementById('nowPlayingScreen').classList.contains('np-video-on'), stream: document.getElementById('nowPlayingScreen').classList.contains('np-video-stream')})")
        check(st['on'] and st['stream'], f'the picture is on by itself, drawn by the native player {st}')
        await pg.screenshot(path=f'{SHOTS}/archlive-np.png')
        # It ends: the next cartoon comes on from its top
        await pg.evaluate("window.__loads=[]")
        await pg.evaluate("window.__emit('state', { id: %s, state: 'ended', isPlaying: false, playWhenReady: false, position: 600, duration: 600 })" % json.dumps(cid)); await pg.wait_for_timeout(2500)
        la = await pg.evaluate("window.__loads.length ? window.__loads[window.__loads.length-1] : null")
        nxt = (i_now + 1) % 3
        check(la and ('archive.org/download/pop%d/' % (nxt + 1)) in la['url'] and (la.get('start') or 0) <= 3, f'when it ends, the next cartoon from its top {la and la["url"]} start={la and la.get("start")}')
        np = await pg.evaluate(NP)
        check(np['live'] and np['sub'].startswith('Popeye %d' % (nxt + 1)), f'Now Playing follows it, still live {np["sub"]!r}')
        # Continue Watching keeps the channel, not the cartoon
        hist = await pg.evaluate("(JSON.parse(localStorage.getItem('radioPlayerChannelHistory') || '[]')[0] || {}).url")
        check(hist == 'amplify-archive:c:classic_cartoons', f'Continue Watching keeps the channel ({hist})')

        # A concert (one item, three songs) on a channel of your own: one program in the guide; tuning
        # in plays the song on now where it is. Nothing is known yet (first time): looked up, then played.
        await pg.evaluate("document.getElementById('npBackBtn') && document.getElementById('npBackBtn').click()")
        await pg.evaluate("localStorage.removeItem('radioPlayerArchiveFiles'); localStorage.setItem('radioPlayerVideoChannels', JSON.stringify(JSON.parse(localStorage.getItem('radioPlayerVideoChannels')).concat([{ id: 'archive:m:x', name: 'Concerts', url: 'amplify-archive:m:x', logo: '', cats: ['archive.org'], catNames: ['Archive.org'], src: 'archive', archive: { items: [{ id: 'show1', title: 'Live 1977', creator: 'Band', year: '1977', video: false }, { id: 'pop1', title: 'Popeye 1', video: true }], order: 'sequence' } }])))")
        await pg.reload(); await pg.wait_for_timeout(300)
        await pg.evaluate("document.querySelector('.mobile-nav-btn[data-nav=video]').click()"); await pg.wait_for_timeout(200)
        await pg.evaluate("window.__loads=[]")
        await tap_now(pg, 'amplify-archive:m:x'); await pg.wait_for_timeout(3000)
        la = await pg.evaluate("window.__loads.length ? window.__loads[window.__loads.length-1] : null")
        off = (time.time() - EPOCH) % 1200
        if off < 600:
            want = 'show1/t%d.mp3' % (int(off // 200) + 1); want_off = off % 200
        else:
            want = 'pop1/x.mp4'; want_off = off - 600
        check(la and want in la['url'] and abs((la.get('start') or 0) - want_off) < 6, f'first time: looked up, then the file on now, joined in progress ({la and la["url"]} @ {la and la.get("start")} vs {want} @ {want_off:.0f})')
        await pg.evaluate("document.getElementById('npBackBtn') && document.getElementById('npBackBtn').click()"); await pg.wait_for_timeout(300)
        await pg.evaluate("document.querySelector('.mobile-nav-btn[data-nav=video]').click()"); await pg.wait_for_timeout(1200)
        g = await grid(pg)
        row = [r for r in g['rows'] if r['url'] == 'amplify-archive:m:x'][0]
        full = [(b2['t'], round((b2['ee'] - b2['ss']) / 1000)) for b2 in row['blocks'] if b2['ss'] // 1000 > g['t0'] / 1000][:3]
        check(any(t == 'Live 1977' and d == 600 for t, d in full) and all(t != 'Song 2' for t, d in full), f'the concert is one program in the guide (its songs together) {full}')
        # In the middle of the concert (the clock moved to 5 minutes into it): song 2, 100 seconds in
        off = (time.time() - EPOCH) % 1200
        await pg.evaluate("window.__dt = %f; window.__loads = []" % ((300 - off) * 1000))
        await tap_now(pg, 'amplify-archive:m:x'); await pg.wait_for_timeout(2000)
        la = await pg.evaluate("window.__loads.length ? window.__loads[window.__loads.length-1] : null")
        check(la and 'show1/t2.mp3' in la['url'] and abs((la.get('start') or 0) - 100) < 6, f'mid-concert: the song on now, where it is ({la and la["url"]} @ {la and la.get("start")})')
        np = await pg.evaluate(NP)
        check(np['live'] and np['sub'].startswith('Song 2') and 'Live 1977' in np['sub'], f'Now Playing: the song and the show {np["sub"]!r}')
        # ---- Build 345: Add Channels > Archive.org with Search everything on
        await pg.evaluate("document.getElementById('npBackBtn') && document.getElementById('npBackBtn').click()"); await pg.wait_for_timeout(300)
        # something from archive.org already in Continue Listening / Continue Watching
        await pg.evaluate("""(function(){ var r = JSON.parse(localStorage.getItem('radioPlayerRecent')||'[]'); r.unshift({ type:'podcast', guid:'ia:old/x.mp4', name:'Old Result', episodeUrl:'https://archive.org/download/old/x.mp4' }); localStorage.setItem('radioPlayerRecent', JSON.stringify(r));
          var h = JSON.parse(localStorage.getItem('radioPlayerChannelHistory')||'[]'); h.unshift({ url:'amplify-archive:i:old', name:'Old Channel', at: Date.now() }); localStorage.setItem('radioPlayerChannelHistory', JSON.stringify(h)); })()""")
        await pg.reload(); await pg.wait_for_timeout(2000)
        await pg.evaluate("document.querySelector('.mobile-nav-btn[data-nav=video]').click()"); await pg.wait_for_timeout(800)
        await pg.evaluate("document.getElementById('videoAddHeaderBtn').click()"); await pg.wait_for_timeout(800)
        await pg.evaluate("Array.prototype.find.call(document.querySelectorAll('.ch-tools .home-tab'),function(t){return t.textContent.trim()==='Archive.org';}).click()"); await pg.wait_for_timeout(600)
        await pg.evaluate("var c=document.querySelector('.ia-switch input'); c.checked=true; c.dispatchEvent(new Event('change',{bubbles:true}));"); await pg.wait_for_timeout(300)
        recent = await pg.evaluate("JSON.parse(localStorage.getItem('radioPlayerRecent')||'[]').map(function(r){return r.guid||r.name;})")
        hist = await pg.evaluate("JSON.parse(localStorage.getItem('radioPlayerChannelHistory')||'[]').map(function(h){return h.url;})")
        check(not any(str(x).startswith('ia:') for x in recent) and not any(str(x).startswith('amplify-archive:i:') for x in hist), f'turning it on takes archive.org results out of Continue Listening / Watching {recent[:3]} {hist[:3]}')
        # typing: no mini player while the keyboard is up
        await pg.focus('.ch-tools input[type=search]'); await pg.keyboard.type('popeye cartoon with a very long name'); await pg.wait_for_timeout(1400)
        bar = await pg.evaluate("({kb: document.body.classList.contains('kb-open'), bar: getComputedStyle(document.getElementById('playerBar')).display})")
        check(bar['kb'] and bar['bar'] == 'none', f'no mini Now Playing while typing in Add Channels {bar}')
        await pg.screenshot(path=f'{SHOTS}/addch-typing.png')
        # four lines at most for the name and for the description
        cl = await pg.evaluate("""(function(){ var rows = document.querySelectorAll('.ia-item'); var one = function(sel){ return rows[1].querySelector(sel).getBoundingClientRect().height; };
          return Array.prototype.map.call(rows, function(r){ var n=r.querySelector('.ch-name'), s=r.querySelector('.ch-sub');
            return { n: Math.round(n.getBoundingClientRect().height / one('.ch-name')), s: Math.round(s.getBoundingClientRect().height / one('.ch-sub')), cn: getComputedStyle(n).webkitLineClamp, cs: getComputedStyle(s).webkitLineClamp }; }); })()""")
        check(cl and all(c['n'] <= 4 and c['s'] <= 4 and c['cn'] == '4' and c['cs'] == '4' for c in cl) and cl[0]['n'] == 4 and cl[0]['s'] == 4, f'names and descriptions: up to four lines each {cl}')
        await pg.evaluate("document.activeElement.blur()"); await pg.wait_for_timeout(300)
        await pg.screenshot(path=f'{SHOTS}/addch-4lines.png')
        # a result played: nothing goes into Continue Listening
        await pg.evaluate("window.__loads=[]")
        await pg.evaluate("document.querySelector('.ia-item').click()"); await pg.wait_for_timeout(2500)
        ld = await pg.evaluate("window.__loads.map(function(a){return a.url;})")
        recent = await pg.evaluate("JSON.parse(localStorage.getItem('radioPlayerRecent')||'[]').map(function(r){return r.guid||r.name;})")
        check(ld and 'archive.org/download/' in ld[-1] and not any(str(x).startswith('ia:') for x in recent), f'a result plays and stays out of Continue Listening {ld[-1:]} {recent[:3]}')
        # the search isn't kept: leaving and coming back finds the box empty
        await pg.evaluate("document.getElementById('npBackBtn') && document.getElementById('npBackBtn').click()"); await pg.wait_for_timeout(300)
        await pg.evaluate("Array.prototype.find.call(document.querySelectorAll('.ch-tools .home-tab'),function(t){return t.textContent.trim()==='Pluto';}).click()"); await pg.wait_for_timeout(500)
        await pg.evaluate("Array.prototype.find.call(document.querySelectorAll('.ch-tools .home-tab'),function(t){return t.textContent.trim()==='Archive.org';}).click()"); await pg.wait_for_timeout(500)
        q = await pg.evaluate("document.querySelector('.ch-tools input[type=search]').value")
        check(q == '', f'the archive.org search isn’t kept ({q!r})')
        check(not errs, f'no page errors {errs[:3]}')
        await b.close()
    print('FAILS', len(fails)); raise SystemExit(1 if fails else 0)
asyncio.run(main())
