"""Build 240: the TV guide for Live TV. Pluto channels' schedules (api.pluto.tv/v2/channels/<id>
?start&stop) and Plex channels' (epg.provider.plex.tv/grid?channelGridKey&date, with the
account token) show as "Now: ..." / "Next 9:30 PM: ..." on the channel rows; a "TV Guide" row
at the top of Live TV opens a guide page: one card per channel with a schedule (Now with time
left and a progress bar, then what's next), tap to play; a channel with no schedule (a link)
gets no lines and a note on the guide page. Schedules are kept, so after a restart the rows
show at once without asking again. Both themes at 412, 360 with larger text.
Run: python3 tests/test_tv_guide.py (screenshots in /tmp/claude-0/t/shots)"""
import sys as _nsys, os as _nos; _nsys.path.insert(0, _nos.path.dirname(_nos.path.abspath(__file__))); from notice_auto import AUTO_NOTICE
import asyncio, json, os, shutil, threading, http.server, functools, time, datetime
from urllib.parse import urlparse, parse_qs
from playwright.async_api import async_playwright
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = '/tmp/claude-0/t/srv-guide'; SHOTS = '/tmp/claude-0/t/shots'
PORT = 8844
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


def iso(t): return datetime.datetime.fromtimestamp(t, datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.000Z')


def pluto_body(cid):
    progs = {BUZZR: [('The Price Is Right', 'Season 12 Episode 4', -600, 1800), ('Match Game', 'Charles Nelson Reilly', 1200, 1800), ('Family Feud', '', 3000, 1800), ('Press Your Luck', '', 4800, 1800)],
             KIDS: [('Maggie and the Ferocious Beast', 'The Big Hat / The Camping Trip', -300, 1740), ('Maggie and the Ferocious Beast', 'Just a Little Off the Top', 1440, 1740)]}[cid]
    tl = []
    for title, ep, off, dur in progs:
        tl.append({'start': iso(NOW + off), 'stop': iso(NOW + off + dur), 'title': title,
                   'episode': {'name': ep or title, 'description': 'A classic game show. ' * 3, 'rating': 'TV-G', 'series': {'name': title}}})
    return {'_id': cid, 'name': 'x', 'timelines': tl}


def plex_body(day):
    t0 = int(NOW) - 900
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

ROWS = """Array.from(document.querySelectorAll('#stationsGrid .tile.ch-item')).map(function(t){ var g=t.querySelector('.ch-guide');
  return { name: t.querySelector('.tile-name').textContent, now: g && !g.hidden && g.querySelector('.ch-guide-now') ? g.querySelector('.ch-guide-now').textContent : null,
    next: g && !g.hidden && g.querySelector('.ch-guide-next') ? g.querySelector('.ch-guide-next').textContent : null }; })"""
CARDS = """Array.from(document.querySelectorAll('#stationsGrid .guide-card')).map(function(c){ return { name: c.querySelector('.guide-name').textContent,
  progs: Array.from(c.querySelectorAll('.guide-prog')).map(function(p){ return [p.querySelector('.guide-time').textContent, p.querySelector('.guide-title').textContent, (p.querySelector('.guide-sub')||{}).textContent||'', !!p.querySelector('.guide-bar span')]; }),
  empty: (c.querySelector('.guide-empty')||{}).textContent || '' }; })"""
FIT = """(()=>{ var bad=[]; document.querySelectorAll('#stationsGrid *').forEach(function(e){ var r=e.getBoundingClientRect(); if(r.width && (r.right > innerWidth + 0.5 || r.left < -0.5)) bad.push(e.className); }); return bad.slice(0,5); })()"""


async def run(p, theme, width, big):
    T = f'[{theme} {width}{" big" if big else ""}]'
    LOG['pluto'].clear(); LOG['plex'].clear(); LOG['tokens'].clear(); state['down'] = False
    b = await p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
    ctx = await b.new_context(viewport={'width': width, 'height': 900}, device_scale_factor=2, is_mobile=True, has_touch=True, color_scheme=theme, locale='en-US', timezone_id='America/New_York')
    await ctx.add_init_script(MOCK); await ctx.add_init_script(AUTO_NOTICE); await ctx.add_init_script(SEED)
    await ctx.add_init_script("try{ localStorage.setItem('radioPlayerTheme', '%s'); }catch(e){}" % theme)
    pg = await ctx.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
    await pg.route('**/*', route)
    await pg.goto(f'http://127.0.0.1:{PORT}/index.html'); await pg.wait_for_timeout(2500)
    if big:
        await pg.add_style_tag(content='.tile-name{font-size:20px !important} .ch-guide-now{font-size:17.5px !important} .ch-guide-next{font-size:16px !important} .guide-title{font-size:19.5px !important} .guide-sub,.guide-time{font-size:16.9px !important} .guide-name{font-size:21.6px !important} .guide-link-title{font-size:21px !important} .guide-link-sub{font-size:17px !important}')
    await pg.evaluate("document.querySelector('.mobile-nav-btn[data-nav=video]').click()"); await pg.wait_for_timeout(2500)
    rows = {r['name']: r for r in await pg.evaluate(ROWS)}
    check(rows.get('Buzzr', {}).get('now') == 'Now: The Price Is Right' and (rows.get('Buzzr', {}).get('next') or '').startswith('Next ') and rows['Buzzr']['next'].endswith(': Match Game'),
          f'{T} a Pluto row shows Now / Next {rows.get("Buzzr")}')
    check(rows.get('Reuters Now', {}).get('now') == 'Now: Reuters Now Live' and (rows.get('Reuters Now', {}).get('next') or '').endswith(': Reuters Now Live'), f'{T} a Plex row too {rows.get("Reuters Now")}')
    check(rows.get('Local News', {}).get('now') is None, f'{T} a link channel has no guide lines')
    nx = rows.get('Buzzr', {}).get('next') or ''
    check(('AM' in nx or 'PM' in nx), f'{T} the next time reads like a clock ({nx})')
    cids = sorted(set(x[0] for x in LOG['pluto']))
    check(cids == sorted([BUZZR, KIDS]) and len(LOG['pluto']) == 2, f'{T} each Pluto channel\'s schedule fetched once {LOG["pluto"]}')
    st, sp = LOG['pluto'][0][1], LOG['pluto'][0][2]
    span = (datetime.datetime.fromisoformat(sp.replace('Z', '+00:00')) - datetime.datetime.fromisoformat(st.replace('Z', '+00:00'))).total_seconds() / 3600
    check(12 <= span <= 14, f'{T} for the next 12 hours ({span:.1f} h)')
    check(len(LOG['plex']) >= 1 and all(k == 'reuters-now' for k, _ in LOG['plex']) and all(t == 'USERTOKEN123' for t in LOG['tokens']), f'{T} the Plex schedule by guide key, with the account token {LOG["plex"]}')
    link = await pg.evaluate("(()=>{ var l=document.querySelector('#stationsGrid .guide-link'); if(!l) return null; var r=l.getBoundingClientRect(), first=document.querySelector('#stationsGrid .tile.ch-item').getBoundingClientRect(); return { text: l.textContent, above: r.bottom <= first.top, w: Math.round(r.width) }; })()")
    check(link and 'TV Guide' in link['text'] and link['above'], f'{T} a TV Guide row at the top of Live TV {link}')
    check(await pg.evaluate(FIT) == [], f'{T} nothing runs off the screen')
    await pg.screenshot(path=f'{SHOTS}/guide-rows-{theme}-{width}{"-big" if big else ""}.png')

    # ---- the guide page ----
    await pg.evaluate("document.querySelector('#stationsGrid .guide-link').click()"); await pg.wait_for_timeout(1200)
    head = await pg.evaluate("document.getElementById('stationsHeading').textContent")
    cards = await pg.evaluate(CARDS)
    check(head == 'TV Guide' and [c['name'] for c in cards] == ['Buzzr', 'Little Stars Universe', 'Reuters Now'], f'{T} the guide page has a card per channel with a schedule {head} {[c["name"] for c in cards]}')
    bz = cards[0]['progs'] if cards else []
    check(bz and bz[0][0] == 'Now' and bz[0][1] == 'The Price Is Right' and 'min left' in bz[0][2] and bz[0][3], f'{T} Now with time left and a progress bar {bz[:1]}')
    check(len(bz) == 4 and bz[1][1] == 'Match Game' and ('AM' in bz[1][0] or 'PM' in bz[1][0]) and bz[1][2] == 'Charles Nelson Reilly' and bz[2][2] == '', f'{T} then what\'s next: its time once, and the episode name {bz[1:3]}')
    gap = await pg.evaluate("(()=>{ var p=document.querySelectorAll('.guide-card .guide-prog')[1]; var t=p.querySelector('.guide-time').getBoundingClientRect(), b=p.querySelector('.guide-title').getBoundingClientRect(); return Math.round(b.left - t.right); })()")
    check(gap >= 8, f'{T} the time and the title don\'t touch ({gap}px)')
    foot = await pg.evaluate("(document.querySelector('#stationsGrid .guide-foot')||{}).textContent")
    check(foot and 'One other channel' in foot, f'{T} a note about the channel without a schedule ({foot})')
    check(await pg.evaluate(FIT) == [], f'{T} the guide fits the screen')
    nav = await pg.evaluate("(document.querySelector('.mobile-nav-btn.active')||{}).dataset.nav")
    check(nav == 'video', f'{T} Watch stays selected in the tab bar ({nav})')
    await pg.screenshot(path=f'{SHOTS}/guide-page-{theme}-{width}{"-big" if big else ""}.png')
    await pg.evaluate("document.querySelector('.guide-card .guide-prog.now').click()"); await pg.wait_for_timeout(1500)
    loads = [c[1] for c in await pg.evaluate('window.__calls') if c[0] == 'load']
    check(loads and BUZZR in loads[-1], f'{T} tapping what\'s on now plays the channel {loads[-1:]}')
    await pg.evaluate("(()=>{ var b=document.getElementById('npBackBtn'); if(b) b.click(); })()"); await pg.wait_for_timeout(700)
    await pg.evaluate("document.getElementById('detailBackBtn').click()"); await pg.wait_for_timeout(900)
    back = await pg.evaluate("[document.getElementById('stationsHeading').textContent, !!document.querySelector('#stationsGrid .guide-link')]")
    check(back[1], f'{T} Back returns to Live TV {back}')

    # ---- kept: after a restart the rows show at once, nothing asked again ----
    n0 = len(LOG['pluto']) + len(LOG['plex'])
    await pg.reload(); await pg.wait_for_timeout(2500)
    await pg.evaluate("document.querySelector('.mobile-nav-btn[data-nav=video]').click()"); await pg.wait_for_timeout(1500)
    rows = {r['name']: r for r in await pg.evaluate(ROWS)}
    check(rows.get('Buzzr', {}).get('now') == 'Now: The Price Is Right' and len(LOG['pluto']) + len(LOG['plex']) == n0, f'{T} after a restart: shown from what was kept, no new requests ({len(LOG["pluto"]) + len(LOG["plex"]) - n0})')
    check(not errs, f'{T} no page errors {errs[:3]}')
    await b.close()


async def down(p):
    state['down'] = True
    b = await p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
    ctx = await b.new_context(viewport={'width': 412, 'height': 900}, device_scale_factor=2, is_mobile=True, has_touch=True, locale='en-US')
    await ctx.add_init_script(MOCK); await ctx.add_init_script(AUTO_NOTICE); await ctx.add_init_script(SEED)
    pg = await ctx.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
    await pg.route('**/*', route)
    await pg.goto(f'http://127.0.0.1:{PORT}/index.html'); await pg.wait_for_timeout(2500)
    await pg.evaluate("document.querySelector('.mobile-nav-btn[data-nav=video]').click()"); await pg.wait_for_timeout(2500)
    rows = await pg.evaluate(ROWS)
    check(all(r['now'] is None for r in rows) and len(rows) == 4, f'[down] with the schedules unreachable the rows are as before {rows}')
    await pg.evaluate("document.querySelector('#stationsGrid .guide-link').click()"); await pg.wait_for_timeout(1200)
    cards = await pg.evaluate(CARDS)
    check(cards and all(c['empty'] for c in cards) and not any(c['progs'] for c in cards), f'[down] the guide says there is no schedule {[c["empty"] for c in cards]}')
    check(not errs, f'[down] no page errors {errs[:3]}')
    await b.close()


async def main():
    async with async_playwright() as p:
        await run(p, 'dark', 412, False)
        await run(p, 'light', 412, False)
        await run(p, 'light', 360, True)
        await down(p)
    print('ALL PASSED' if not fails else f'FAILED {fails}')
asyncio.run(main())
