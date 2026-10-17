"""Build 243: the Live TV guide grid (Mark's mockups). Channels fixed down the left (favourites
first with a heart, no headings), half-hour columns across starting at the current half hour,
programs taking the nearest half hours, an accent line at now, a channel without a schedule as one
block across. Tapping what's on now plays the channel; a later block does nothing. Playing: the
video on top, the channel's name and the episode under it, the same grid below, no View Queue and
no queue swipe. Both themes at 412, 360 with larger text.
Run: python3 tests/test_epg_grid.py (screenshots in /tmp/claude-0/t/shots)"""

import sys as _nsys, os as _nos; _nsys.path.insert(0, _nos.path.dirname(_nos.path.abspath(__file__))); from notice_auto import AUTO_NOTICE
import asyncio, json, os, shutil, threading, http.server, functools, time, datetime
from urllib.parse import urlparse, parse_qs
from playwright.async_api import async_playwright
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = '/tmp/claude-0/t/srv-epg'; SHOTS = '/tmp/claude-0/t/shots'
PORT = 8846
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
                   'episode': {'name': ep or title, 'description': 'A classic game show. ' * 3, 'rating': 'TV-G', 'series': {'name': title}}})
    return {'_id': cid, 'name': 'x', 'timelines': tl}


def plex_body(day):
    t0 = int(BASE) - 60
    return {'MediaContainer': {'Metadata': [
        {'type': 'episode', 'title': 'Markets Open', 'grandparentTitle': 'Reuters Now Live', 'summary': 'Business news.', 'Media': [{'beginsAt': t0, 'endsAt': t0 + 3600}]},
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
    if u.netloc == 'epg.provider.plex.tv' and u.path == '/grid':
        q = parse_qs(u.query)
        LOG['plex'].append((q.get('channelGridKey', [''])[0], q.get('date', [''])[0]))
        LOG['tokens'].append(r.request.headers.get('x-plex-token', ''))
        if state['down']: return await r.fulfill(status=503, headers=cors, body='')
        return await r.fulfill(status=200, content_type='application/json', headers=cors, body=json.dumps(plex_body(q.get('date', [''])[0])))
    if '127.0.0.1' in u.netloc: return await r.continue_()
    return await r.abort()


SLOT = 1800
SW, CW, GAP = 124, 80, 4   # build 244: denser
def snap(t): return round(t / SLOT) * SLOT
GRID = """(()=>{ var w=document.querySelector('.epg'); if(!w) return null; var sc=w.querySelector('.epg-scroll'), wr=w.getBoundingClientRect();
  var rows=Array.from(w.querySelectorAll('.epg-row')).map(function(r){ var ch=r.querySelector('.epg-ch'); var cr=ch.getBoundingClientRect();
    return { url: r.dataset.chUrl, heart: !!ch.querySelector('.epg-heart'), logo: !!ch.querySelector('img'), chLeft: Math.round(cr.left - wr.left),
      blocks: Array.from(r.querySelectorAll('.epg-prog')).map(function(b){ return { t: b.querySelector('.epg-t').textContent, s: (b.querySelector('.epg-s')||{}).textContent||'', left: parseFloat(b.style.left), w: parseFloat(b.style.width), now: b.classList.contains('now'), whole: b.classList.contains('whole'), ss: Number(b.dataset.s), ee: Number(b.dataset.e) }; }) }; });
  var line=w.querySelector('.epg-now');
  return { t0: Number(w.dataset.t0), times: Array.from(w.querySelectorAll('.epg-time')).slice(0,3).map(function(t){ return t.textContent; }), rows: rows,
    line: parseFloat(line.style.left), lineColor: getComputedStyle(line).backgroundColor, accent: getComputedStyle(document.documentElement).getPropertyValue('--accent').trim(),
    headings: w.parentNode.querySelectorAll('.ch-group-head, .ch-row-label, .grid-section-label').length, more: w.querySelectorAll('.row-more-btn').length,
    left: Math.round(wr.left), right: Math.round(wr.right), vw: innerWidth, scroll: sc.scrollWidth > sc.clientWidth }; })()"""


async def run(p, theme, width, big):
    T = f'[{theme} {width}{" big" if big else ""}]'
    LOG['pluto'].clear(); LOG['plex'].clear(); state['down'] = False
    b = await p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
    ctx = await b.new_context(viewport={'width': width, 'height': 900}, device_scale_factor=2, is_mobile=True, has_touch=True, color_scheme=theme, locale='en-US', timezone_id='America/New_York')
    await ctx.add_init_script(MOCK); await ctx.add_init_script(AUTO_NOTICE); await ctx.add_init_script(SEED)
    fav = json.dumps(json.dumps([{'name': 'Reuters Now', 'urlToResolve': CHANNELS[1]['url'], 'favicon': '', 'videoChannel': True, 'stationuuid': None}]))
    await ctx.add_init_script("try{ localStorage.setItem('radioPlayerTheme', '%s'); if(!localStorage.getItem('__fav')){ localStorage.setItem('__fav','1'); localStorage.setItem('radioPlayerFavorites', %s); } }catch(e){}" % (theme, fav))
    pg = await ctx.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
    await pg.route('**/*', route)
    cdp = await ctx.new_cdp_session(pg)
    await pg.goto(f'http://127.0.0.1:{PORT}/index.html'); await pg.wait_for_timeout(2500)
    if big:
        await pg.add_style_tag(content='.epg-t{font-size:17.6px !important} .epg-s{font-size:15.5px !important} .epg-time{font-size:17.6px !important} .epg-logo-name{font-size:14.2px !important} .np-name{font-size:30px !important} .np-sub{font-size:19px !important}')
    await pg.evaluate("document.querySelector('.mobile-nav-btn[data-nav=video]').click()"); await pg.wait_for_timeout(2500)
    g = await pg.evaluate(GRID)
    check(g is not None and len(g['rows']) == 4, f'{T} Live TV is a guide grid with a row per channel {g and len(g["rows"])}')
    order = [r['url'] for r in g['rows']]
    check(order[0] == CHANNELS[1]['url'] and g['rows'][0]['heart'] and not any(r['heart'] for r in g['rows'][1:]), f'{T} the favourite first, with a heart')
    check(g['headings'] == 0 and g['more'] == 0, f'{T} no Favorites / My Channels headings, no 3-dot menus ({g["headings"]}, {g["more"]})')
    t0 = int(NOW // SLOT * SLOT)
    check(g['t0'] // 1000 == t0, f'{T} the grid starts at the half hour we are in')
    check(all(x.endswith(('AM', 'PM')) for x in g['times']) and len(set(g['times'])) == 3, f'{T} half-hour times across the top {g["times"]}')
    # programs take the nearest half hours
    bz = [r for r in g['rows'] if BUZZR in r['url']][0]['blocks']
    want = []
    prev = t0
    for title, ep, off, dur in [('The Price Is Right', '', -120, 1980), ('Match Game', '', 1860, 1800), ('Family Feud', '', 3660, 1800), ('Press Your Luck', '', 5460, 1800)]:
        s0 = max(snap(BASE + off), prev); e0 = snap(BASE + off + dur)
        if e0 > s0: want.append((title, s0, e0)); prev = e0
    got = [(x['t'], x['ss'] // 1000, x['ee'] // 1000) for x in bz]
    check(got == want, f'{T} programs take the nearest half hours {got} vs {want}')
    check(all(abs(x['w'] - ((x['ee'] - x['ss']) / 1000 / SLOT * SW - GAP)) < 1 for x in bz), f'{T} a block’s width is its half hours')
    ln = [r for r in g['rows'] if 'news.example' in r['url']][0]['blocks']
    check(len(ln) == 1 and ln[0]['whole'] and ln[0]['w'] > 24 * SW - 10, f'{T} a channel without a schedule is one block across {ln}')
    exp_line = CW + (NOW - t0) / SLOT * SW
    check(abs(g['line'] - exp_line) < 40 and g['lineColor'] not in ('', 'rgba(0, 0, 0, 0)'), f'{T} the now line sits at the current time, in the accent ({g["line"]:.0f} vs {exp_line:.0f})')
    check(g['left'] == 0 and g['right'] == g['vw'] and g['scroll'], f'{T} the grid runs edge to edge and scrolls sideways')
    # build 244: denser, text still fits; 18px under the tabs (as Continue)
    d = await pg.evaluate("""(()=>{ var r=document.querySelector('.epg-row'), tabs=document.querySelector('#stationsGrid .video-tabs'), e=document.querySelector('#stationsGrid > .epg');
      var over=Array.from(document.querySelectorAll('.epg-prog')).filter(function(b){ return b.scrollHeight > b.clientHeight + 1; }).length;
      return { rowH: r.getBoundingClientRect().height, gap: Math.round(e.getBoundingClientRect().top - tabs.getBoundingClientRect().bottom), over: over }; })()""")
    check(d['rowH'] <= 50 and d['over'] == 0, f'{T} rows are 50px or less and every block’s text fits {d}')
    check(d['gap'] == 18, f'{T} the grid starts 18px under the tabs, like Continue {d["gap"]}')
    # build 244: the times stick to the top while the rows scroll up, and follow the sideways scroll
    await pg.set_viewport_size({'width': width, 'height': 520}); await pg.wait_for_timeout(400)   # short (still upright), so four rows scroll
    await pg.evaluate("(()=>{ document.getElementById('stationsGrid').style.paddingBottom='900px'; window.scrollTo(0, 0); })()"); await pg.wait_for_timeout(200)
    await pg.evaluate("window.scrollBy(0, 240)"); await pg.wait_for_timeout(600)
    sk = await pg.evaluate("""(()=>{ var h=document.querySelector('#stationsGrid .epg-head').getBoundingClientRect(), hdr=document.querySelector('.app-header, header'); var hb=hdr?hdr.getBoundingClientRect().bottom:0;
      var first=document.querySelector('#stationsGrid > .epg').getBoundingClientRect(); var tb=document.querySelector('#stationsGrid .video-tabs').getBoundingClientRect(); window.__dbg=[tb.top, document.querySelector('#stationsGrid .epg-row').getBoundingClientRect().top]; return { top: Math.round(h.top), hdr: Math.round(hb), firstTop: Math.round(first.top), y: Math.round(scrollY) }; })()""")
    check(sk['firstTop'] < sk['top'] and (abs(sk['top']) <= 1 or abs(sk['top'] - sk['hdr']) <= 1), f'{T} the time row sticks at the top while the rows scroll under it {sk}')
    await pg.evaluate("document.querySelector('#stationsGrid .epg-scroll').scrollLeft = 300"); await pg.wait_for_timeout(300)
    sl = await pg.evaluate("document.querySelector('#stationsGrid .epg-head-track').scrollLeft")
    check(abs(sl - 300) <= 1, f'{T} the times follow the grid sideways ({sl})')
    await pg.evaluate("document.querySelector('#stationsGrid .epg-head-track').scrollLeft = 120"); await pg.wait_for_timeout(300)
    sl2 = await pg.evaluate("document.querySelector('#stationsGrid .epg-scroll').scrollLeft")
    check(abs(sl2 - 120) <= 1, f'{T} swiping the times scrolls the grid too ({sl2})')
    # build 245: a channel without a schedule keeps its name in view, however far the grid scrolls
    for x in (900, 2400):
        await pg.evaluate(f"document.querySelector('#stationsGrid .epg-scroll').scrollLeft = {x}"); await pg.wait_for_timeout(250)
        w = await pg.evaluate("""(()=>{ var r=Array.from(document.querySelectorAll('#stationsGrid .epg-row')).find(x=>x.dataset.chUrl.indexOf('news.example')>=0);
          var t=r.querySelector('.epg-prog.whole .epg-t').getBoundingClientRect(), c=r.querySelector('.epg-ch').getBoundingClientRect(); return [Math.round(t.left), Math.round(t.right), Math.round(c.right), innerWidth]; })()""")
        check(w[0] >= w[2] and w[1] <= w[3] and w[0] - w[2] < 20, f'{T} scrolled {x}px: the no-schedule channel’s name stays just right of the logos {w}')
    if not big: await pg.screenshot(path=f'{SHOTS}/epg-sticky-{theme}.png')
    await pg.evaluate("document.querySelector('#stationsGrid .epg-scroll').scrollLeft = 0; document.getElementById('stationsGrid').style.paddingBottom=''; window.scrollTo(0, 0)"); await pg.wait_for_timeout(300)
    await pg.set_viewport_size({'width': width, 'height': 900}); await pg.wait_for_timeout(400)
    await pg.evaluate("document.querySelector('.epg').scrollIntoView({block:'start'}); window.scrollBy(0, -140)"); await pg.wait_for_timeout(300)
    await pg.screenshot(path=f'{SHOTS}/epg-grid-{theme}-{width}{"-big" if big else ""}.png')
    # channels stay on the left while the grid scrolls
    await pg.evaluate("document.querySelector('.epg-scroll').scrollLeft = 700"); await pg.wait_for_timeout(300)
    g2 = await pg.evaluate(GRID)
    check(all(abs(r['chLeft']) <= 1 for r in g2['rows']), f'{T} the channels stay fixed on the left when the grid scrolls {[r["chLeft"] for r in g2["rows"]]}')
    if not big:
        await pg.screenshot(path=f'{SHOTS}/epg-grid-scrolled-{theme}.png')
    await pg.evaluate("document.querySelector('.epg-scroll').scrollLeft = 0"); await pg.wait_for_timeout(200)
    # a later program does nothing; what's on now plays
    n0 = len([c for c in await pg.evaluate('window.__calls') if c[0] == 'load'])
    await pg.evaluate("(()=>{ var r=Array.from(document.querySelectorAll('.epg-row')).find(x=>x.dataset.chUrl.indexOf('%s')>=0); var bs=r.querySelectorAll('.epg-prog'); bs[bs.length-1].click(); })()" % BUZZR); await pg.wait_for_timeout(800)
    n1 = len([c for c in await pg.evaluate('window.__calls') if c[0] == 'load'])
    check(n1 == n0 and not await pg.evaluate("document.body.classList.contains('np-open')"), f'{T} tapping a later program does nothing')
    await pg.evaluate("(()=>{ var r=Array.from(document.querySelectorAll('.epg-row')).find(x=>x.dataset.chUrl.indexOf('%s')>=0); r.querySelector('.epg-prog.now').click(); })()" % BUZZR); await pg.wait_for_timeout(1800)
    loads = [c[1] for c in await pg.evaluate('window.__calls') if c[0] == 'load']
    check(len(loads) > n0 and BUZZR in loads[-1], f'{T} tapping what’s on now plays the channel')
    await pg.evaluate("(id)=>window.__emit('videoSize', {id:id, width:1280, height:720})", await pg.evaluate('window.__cur')); await pg.wait_for_timeout(600)
    np = await pg.evaluate("""(()=>{ var s=document.getElementById('nowPlayingScreen'); var n=document.getElementById('npName'), sub=document.getElementById('npSub'), col=document.getElementById('npCollection');
      var grid=col.querySelector('.epg'); var h=document.getElementById('npCollectionHeading'); return { open: s.style.display==='flex', channel: s.classList.contains('np-channel'), name: n.textContent, sub: sub.textContent,
      grid: !!grid, rows: grid ? grid.querySelectorAll('.epg-row').length : 0, heading: getComputedStyle(h).display !== 'none' && h.textContent ? h.textContent : '',
      gridBelowName: grid ? grid.getBoundingClientRect().top >= n.getBoundingClientRect().bottom : false, edge: grid ? [Math.round(grid.getBoundingClientRect().left), Math.round(grid.getBoundingClientRect().right)] : null }; })()""")
    check(np['open'] and np['channel'] and np['name'] == 'Buzzr' and np['sub'] == 'The Price Is Right \u00b7 Season 12 Episode 4', f'{T} playing: the channel’s name and what’s on {np["name"]!r} / {np["sub"]!r}')
    # build 245: the title smaller, the episode tight under it, the pair centred between video and guide
    tg = await pg.evaluate("""(()=>{ var R=e=>e.getBoundingClientRect(), n=R(document.getElementById('npName')), sb=R(document.getElementById('npSub')), f=R(document.querySelector('#nowPlayingScreen .np-hero-foot')), g=R(document.querySelector('#npCollection .epg'));
      return { fs: parseFloat(getComputedStyle(document.getElementById('npName')).fontSize), gap: Math.round(sb.top - n.bottom), above: Math.round(n.top - f.top), below: Math.round(g.top - sb.bottom) }; })()""")
    check((tg['fs'] <= 17 or big) and 0 <= tg['gap'] <= 4 and abs(tg['above'] - tg['below']) <= 3, f'{T} the title is smaller, the episode right under it, centred between video and guide {tg}')
    check(np['grid'] and np['rows'] == 4 and not np['heading'] and np['gridBelowName'] and np['edge'] == [0, width], f'{T} the full grid below, edge to edge, no heading {np}')
    await pg.evaluate("document.getElementById('npMenuBtn').click()"); await pg.wait_for_timeout(300)
    q = await pg.evaluate("getComputedStyle(document.getElementById('npQueueMenuBtn')).display")
    check(q == 'none', f'{T} no View Queue in the playing channel’s menu ({q})')
    await pg.evaluate("document.getElementById('npMenuBtn').click()"); await pg.wait_for_timeout(200)
    # a sideways swipe on the screen never opens the queue
    r = await pg.evaluate("(()=>{ var n=document.getElementById('npName').getBoundingClientRect(); return {x: n.left + n.width*0.8, y: n.top + n.height/2}; })()")
    await cdp.send('Input.dispatchTouchEvent', {'type': 'touchStart', 'touchPoints': [{'x': r['x'], 'y': r['y'], 'id': 1}]})
    for i in range(1, 9):
        await cdp.send('Input.dispatchTouchEvent', {'type': 'touchMove', 'touchPoints': [{'x': r['x'] - 30 * i, 'y': r['y'], 'id': 1}]}); await pg.wait_for_timeout(16)
    await cdp.send('Input.dispatchTouchEvent', {'type': 'touchEnd', 'touchPoints': []}); await pg.wait_for_timeout(700)
    check(not await pg.evaluate("document.body.classList.contains('queue-open') || (document.getElementById('queuePanel') && document.getElementById('queuePanel').classList.contains('open'))"), f'{T} a sideways swipe doesn’t open the queue')
    await pg.evaluate("window.scrollTo(0,0); document.getElementById('nowPlayingScreen').scrollTop = 0"); await pg.wait_for_timeout(300)
    await pg.screenshot(path=f'{SHOTS}/epg-np-{theme}-{width}{"-big" if big else ""}.png')
    # the menu still plays other channels from the grid under the player
    await pg.evaluate("(()=>{ var r=Array.from(document.querySelectorAll('#npCollection .epg-row')).find(x=>x.dataset.chUrl.indexOf('news.example')>=0); r.querySelector('.epg-prog').click(); })()"); await pg.wait_for_timeout(1500)
    check((await pg.evaluate("document.getElementById('npName').textContent")) == 'Local News', f'{T} tapping a channel without a schedule plays it (its block is on now)')
    check(not errs, f'{T} no page errors {errs[:3]}')
    await b.close()


async def land(p, theme):
    # Build 244: sideways on Live TV with nothing playing: only the grid. Playing hands over to the
    # landscape Now Playing; upright again, the page is back.
    T = f'[{theme} landscape]'
    b = await p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
    ctx = await b.new_context(viewport={'width': 412, 'height': 900}, device_scale_factor=2, is_mobile=True, has_touch=True, color_scheme=theme, locale='en-US', timezone_id='America/New_York')
    await ctx.add_init_script(MOCK); await ctx.add_init_script(AUTO_NOTICE); await ctx.add_init_script(SEED)
    pg = await ctx.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
    await pg.route('**/*', route)
    await pg.goto(f'http://127.0.0.1:{PORT}/index.html'); await pg.wait_for_timeout(2500)
    await pg.evaluate("document.querySelector('.mobile-nav-btn[data-nav=video]').click()"); await pg.wait_for_timeout(2500)
    await pg.set_viewport_size({'width': 900, 'height': 412}); await pg.wait_for_timeout(1200)
    VIS = """(()=>{ var pts=[[450,20],[20,200],[450,200],[880,390],[450,395]]; return { land: document.body.classList.contains('epg-land'), rot: document.body.classList.contains('rotate-lock'),
      all: pts.every(function(p){ var e=document.elementFromPoint(p[0],p[1]); return !!(e && e.closest('#stationsGrid > .epg')); }),
      nav: (function(){ var n=document.querySelector('.mobile-nav'); if(!n) return false; var r=n.getBoundingClientRect(); var e=document.elementFromPoint(r.left+r.width/2, Math.min(innerHeight-2, r.top+r.height/2)); return !!(e && e.closest('.mobile-nav')); })(),
      head: Math.round(document.querySelector('#stationsGrid > .epg > .epg-head').getBoundingClientRect().top) }; })()"""
    v = await pg.evaluate(VIS)
    check(v['land'] and not v['rot'] and v['all'] and not v['nav'] and v['head'] == 0, f'{T} turned sideways with nothing playing: only the grid, times at the top {v}')
    await pg.screenshot(path=f'{SHOTS}/epg-land-{theme}.png')
    await pg.evaluate("document.querySelector('#stationsGrid > .epg').scrollTop = 200"); await pg.wait_for_timeout(300)
    h = await pg.evaluate("Math.round(document.querySelector('#stationsGrid > .epg > .epg-head').getBoundingClientRect().top)")
    check(h == 0, f'{T} the times stay at the top as the channels scroll ({h})')
    await pg.evaluate("(()=>{ var r=Array.from(document.querySelectorAll('.epg-row')).find(x=>x.dataset.chUrl.indexOf('%s')>=0); r.querySelector('.epg-prog.now').click(); })()" % BUZZR); await pg.wait_for_timeout(1800)
    v = await pg.evaluate("[document.body.classList.contains('epg-land'), document.body.classList.contains('rotate-lock'), document.getElementById('nowPlayingScreen').style.display]")
    check(v == [False, True, 'flex'], f'{T} playing hands over to the landscape Now Playing {v}')
    await pg.set_viewport_size({'width': 412, 'height': 900}); await pg.wait_for_timeout(1200)
    v = await pg.evaluate("[document.body.classList.contains('epg-land'), document.body.classList.contains('rotate-lock')]")
    check(v == [False, False], f'{T} upright again: the usual screens {v}')
    await pg.evaluate("document.getElementById('npBackBtn').click()"); await pg.wait_for_timeout(800)
    # something playing: turning sideways is the usual landscape Now Playing, not the grid
    await pg.set_viewport_size({'width': 900, 'height': 412}); await pg.wait_for_timeout(1200)
    v = await pg.evaluate("[document.body.classList.contains('epg-land'), document.body.classList.contains('rotate-lock')]")
    check(v == [False, True], f'{T} with something playing, sideways is Now Playing as before {v}')
    await pg.set_viewport_size({'width': 412, 'height': 900}); await pg.wait_for_timeout(1000)
    check(not errs, f'{T} no page errors {errs[:3]}')
    await b.close()


async def main():
    async with async_playwright() as p:
        await run(p, 'dark', 412, False)
        await run(p, 'light', 412, False)
        await run(p, 'dark', 360, True)
        await land(p, 'dark')
        await land(p, 'light')
    print('ALL PASSED' if not fails else f'FAILED {fails}')
asyncio.run(main())
