"""Build 706 (Mark): YouTube streams as Live TV channels (YouTube player in the video box, a YouTube category).
Run: python3 tests/test_youtube_channels.py
(harness from test_multi_categories)
Build 315: the Live TV guide. Picking a channel in the guide under the player keeps the guide where it was
scrolled (it used to jump back to the top of the channel list); a cover set with Custom Cover Art shows in the
guide's channel column (MiamiTV); the channel column is dark grey in light mode so white logos show.
Phone viewport with touch; both themes.
Run: python3 tests/test_epg_keep.py (screenshots in /tmp/claude-0/t/shots)"""
import sys as _nsys, os as _nos; _nsys.path.insert(0, _nos.path.dirname(_nos.path.abspath(__file__))); from notice_auto import AUTO_NOTICE
import asyncio, json, os, shutil, threading, http.server, functools, zlib, struct
from urllib.parse import urlparse
from playwright.async_api import async_playwright

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = '/tmp/claude-0/t/srv-ytch'; SHOTS = '/tmp/claude-0/t/shots'
PORT = 8904
shutil.rmtree(ROOT, ignore_errors=True); os.makedirs(ROOT, exist_ok=True); os.makedirs(SHOTS, exist_ok=True)
src = open(os.path.join(HERE, '..', 'www', 'index.html')).read()
mark = '  var coverFlow = null;\n'
assert src.count(mark) == 1
HOOK = "window.__h = { ev: function(js){ return eval(js); } };\n"
open(ROOT + '/index.html', 'w').write(src.replace(mark, mark + HOOK))
H = functools.partial(http.server.SimpleHTTPRequestHandler, directory=ROOT); H.log_message = lambda *a: None
srv = http.server.ThreadingHTTPServer(('127.0.0.1', PORT), H); threading.Thread(target=srv.serve_forever, daemon=True).start()

def png(w, h, rgb):
    raw = b''.join(b'\x00' + bytes(rgb) * w for _ in range(h))
    ch = lambda t, d: struct.pack('>I', len(d)) + t + d + struct.pack('>I', zlib.crc32(t + d) & 0xffffffff)
    return b'\x89PNG\r\n\x1a\n' + ch(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, 2, 0, 0, 0)) + ch(b'IDAT', zlib.compress(raw)) + ch(b'IEND', b'')
WHITE = png(120, 60, (255, 255, 255))
ORANGE = png(120, 120, (255, 160, 0))

def C(i, name, cats, src='pluto', url=None, **kw):
    d = {'id': 'x:%d' % i, 'name': name, 'url': url or 'http://tv%02d.example/live.m3u8' % i, 'logo': 'https://logos.example/l%02d.png' % i, 'cats': [c.lower() for c in cats], 'catNames': cats, 'src': src}
    d.update(kw); return d
CHANNELS = [
  C(1, 'AEW Rampage Episode 3 (2021)', [], 'archive', url='amplify-archive:i:aew-rampage-ep3', archive={'id': 'aew-rampage-ep3', 'title': 'AEW Rampage Episode 3', 'video': True}),
  C(2, 'Little House on the Prairie', ['Classic TV']), C(3, 'MTV Music Videos', [], 'link'), C(4, "Three's Company", ['Classic TV']),
  C(5, 'TMZ', ['Entertainment']), C(6, 'CBS News', ['News'], 'starter'), C(7, 'Reuters TV', ['News'], 'starter'),
  C(8, 'WeatherNation', ['Weather'], 'starter'), C(9, 'Stadium', ['Sports']), C(10, 'Pluto TV Westerns', ['Westerns']),
  C(11, 'MST3K', ['Comedy']), C(12, 'Kids Animation', ['Kids']), C(13, 'Beach TV Key West', ['Live Cams'], 'starter'),
  C(14, 'Window TV', ['Live Cams'], 'starter'), C(15, 'NASA TV', ['Space'], 'starter'), C(16, 'Docurama', ['Documentary'], 'starter'),
  C(17, 'Retro TV', ['Classic TV'], 'starter'), C(18, 'Unsolved Mysteries', ['True Crime']), C(19, 'Bob Ross', ['Lifestyle + DIY']),
  C(20, 'Pluto TV Comedy Central', ['Comedy'])]
MOCK = """
(function(){
 window.__calls=[]; window.__L={}; window.__emit=function(t,ev){ (window.__L[t]||[]).forEach(function(f){ f(ev); }); };
 var P=new Proxy({}, {get:function(t,k){
   if(k==='then') return undefined;
   if(k==='addListener') return function(n,f){ (window.__L[n]=window.__L[n]||[]).push(f); return Promise.resolve({remove:function(){}}); };
   if(k==='load') return function(a){ window.__calls.push(['load',a.url]);
      setTimeout(function(){ window.__emit('state',{id:a.id,state:'ready',isPlaying:true,playWhenReady:true,position:0,duration:-1,live:true}); },60);
      return Promise.resolve({}); };
   if(k==='fetchText') return function(a){ return fetch(a.url).then(function(r){ return r.text(); }).then(function(t){ return { text: t }; }); };
   if(k==='videoState') return function(){ return Promise.resolve({id:null,hasVideo:false}); };
   return function(){ return Promise.resolve({}); };
 }});
 window.Capacitor={isNativePlatform:function(){return true;},getPlatform:function(){return 'android';},Plugins:{AmplifyPlayer:P},convertFileSrc:function(u){return u;}};
})();
"""
SEED = """(function(){ if(!localStorage.getItem('__seeded')){ localStorage.setItem('__seeded','1');
  localStorage.setItem('radioPlayerVideoChannels', %s);
  localStorage.setItem('radioPlayerVideoTab', 'channels'); localStorage.setItem('radioPlayerTourDone', '1'); localStorage.setItem('radioPlayerStarterPack', '1'); localStorage.setItem('radioPlayerLiveChannels', '[]'); } })();""" % json.dumps(json.dumps(CHANNELS))

fails = []
def check(ok, msg):
    print(('PASS ' if ok else 'FAIL ') + msg)
    if not ok: fails.append(msg)

async def route(r):
    u = urlparse(r.request.url)
    cors = {'Access-Control-Allow-Origin': '*'}
    if '127.0.0.1' in u.netloc: return await r.continue_()
    if u.netloc == 'logos.example': return await r.fulfill(status=200, content_type='image/png', headers=cors, body=png(160, 90, (20 + (hash(u.path) % 7) * 30, 60, 140)))
    if 'archive.org' in u.netloc and r.request.resource_type == 'image': return await r.fulfill(status=200, content_type='image/png', headers=cors, body=ORANGE)
    if 'youtube.com' in u.netloc and u.path == '/oembed': return await r.fulfill(status=200, content_type='application/json', headers=cors, body=json.dumps({'title': 'Live: News all day', 'author_name': 'Springfield News Live', 'thumbnail_url': 'https://i.ytimg.com/vi/abcdefghijk/hqdefault.jpg'}))
    if 'youtube.com' in u.netloc and u.path.startswith('/@'): return await r.fulfill(status=200, content_type='text/html', headers=cors, body='<html><head><meta property="og:title" content="Beach Cam Paradise"><meta property="og:image" content="https://yt3.example/a.png"></head><body>{"externalId":"UCabcdefghijklmnopqrstuv"}</body></html>')
    if 'youtube.com' in u.netloc and u.path.startswith('/embed'): return await r.fulfill(status=200, content_type='text/html', body='<html><body style="background:#300;color:#fff;font:20px sans-serif">YT PLAYER ' + u.path + '</body></html>')
    if u.netloc in ('i.ytimg.com', 'yt3.example'): return await r.fulfill(status=200, content_type='image/png', headers=cors, body=ORANGE)
    if u.netloc == 'miamitv.sfo3.cdn.example': return await r.fulfill(status=200, content_type='image/png', headers=cors, body=ORANGE)
    return await r.abort()



EV = lambda js: "() => window.__h.ev(%s)" % json.dumps(js)
CHIPS = "() => Array.from(document.querySelectorAll('#stationsGrid .epg-cat')).map(function(b){ return (b.classList.contains('active') ? '*' : '') + b.textContent; })"
async def run(p, theme, W=327, H=675):
    T = '[%s]' % theme
    b = await p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
    ctx = await b.new_context(viewport={'width': W, 'height': H}, device_scale_factor=3.3, is_mobile=True, has_touch=True, color_scheme=theme, locale='en-US')
    await ctx.add_init_script(MOCK); await ctx.add_init_script(SEED)
    await ctx.add_init_script("try{ localStorage.setItem('radioPlayerTheme', '%s'); localStorage.setItem('radioPlayerLtvAuto', '0'); }catch(e){}" % theme)
    pg = await ctx.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
    await pg.route('**/*', route)
    await pg.goto('http://127.0.0.1:%d/index.html' % PORT); await pg.wait_for_timeout(2000)
    await pg.evaluate("() => document.getElementById('noticeOverlay').classList.remove('open')")
    # parsing
    pr = await pg.evaluate(EV("JSON.stringify(['https://www.youtube.com/watch?v=abcdefghijk','https://youtu.be/abcdefghijk','https://www.youtube.com/live/abcdefghijk?si=x','https://www.youtube.com/@BeachCams','https://www.youtube.com/channel/UCabcdefghijklmnopqrstuv','youtube.com/c/foo','https://example.com/a.m3u8'].map(ytLiveParse))"))
    print(pr)
    check(pr == json.dumps([{'v':'abcdefghijk'},{'v':'abcdefghijk'},{'v':'abcdefghijk'},{'handle':'@BeachCams'},{'ch':'UCabcdefghijklmnopqrstuv'},{'path':'/c/foo'},None]).replace(' ', ''), '%s YouTube links of every kind are recognised, other links are not' % T)
    # Add Channels > YouTube
    await pg.evaluate(EV("pushView(); openAddChannelsPage(); 1")); await pg.wait_for_timeout(600)
    tabs = await pg.evaluate("() => Array.from(document.querySelectorAll('#stationsGrid .home-tabs .home-tab')).map(function(b){ return b.textContent; })")
    check(tabs[-1] == 'YouTube', '%s Add Channels has a YouTube tab %s' % (T, tabs))
    await pg.evaluate("() => Array.from(document.querySelectorAll('#stationsGrid .home-tabs .home-tab')).find(function(b){ return b.textContent === 'YouTube'; }).click()"); await pg.wait_for_timeout(500)
    await pg.fill('#stationsGrid .ch-tools-row input', 'https://www.youtube.com/@BeachCams'); await pg.evaluate("() => document.querySelector('#stationsGrid .ch-tools-row button').click()"); await pg.wait_for_timeout(1200)
    row = await pg.evaluate("() => { var r = document.querySelector('#stationsGrid .ch-row'); return r ? [r.querySelector('.ch-name').textContent, (r.querySelector('.ch-sub') || {}).textContent] : null; }")
    check(row == ['Beach Cam Paradise', 'YouTube'], '%s a channel link finds the channel (name from YouTube) %s' % (T, row))
    await pg.screenshot(path=SHOTS + '/ytch-add-%s.png' % theme)
    await pg.evaluate("() => document.querySelector('#stationsGrid .ch-row .ch-add').click()"); await pg.wait_for_timeout(400)
    await pg.fill('#stationsGrid .ch-tools-row input', 'youtu.be/abcdefghijk'); await pg.evaluate("() => document.querySelector('#stationsGrid .ch-tools-row button').click()"); await pg.wait_for_timeout(1200)
    await pg.evaluate("() => document.querySelector('#stationsGrid .ch-row .ch-add').click()"); await pg.wait_for_timeout(400)
    added = await pg.evaluate(EV("JSON.stringify(videoChannels.filter(function(c){ return c.src === 'youtube'; }).map(function(c){ return [c.name, c.url]; }))"))
    check(json.loads(added) == [['Beach Cam Paradise', 'https://www.youtube.com/channel/UCabcdefghijklmnopqrstuv/live'], ['Springfield News Live', 'https://www.youtube.com/watch?v=abcdefghijk']], '%s both added to My Channels %s' % (T, added))
    await pg.screenshot(path=SHOTS + '/ytch-tab-%s.png' % theme)
    # the Link tab sends a YouTube link the same way
    lk = await pg.evaluate(EV("JSON.stringify(ytLiveParse('https://m.youtube.com/watch?v=abcdefghijk&t=3'))"))
    check(lk == '{"v":"abcdefghijk"}', '%s mobile links too %s' % (T, lk))
    # categories
    cats = await pg.evaluate(EV("JSON.stringify(videoChannels.filter(function(c){ return c.src === 'youtube'; }).map(function(c){ return chCategories(c); }))"))
    check(json.loads(cats) == [['YouTube', 'Live Cams'], ['YouTube', 'News']], '%s YouTube channels are grouped under YouTube (and where their name puts them: Live Cams, News) %s' % (T, cats))
    await pg.evaluate(EV("openVideoHome(); 1")); await pg.wait_for_timeout(300)
    await pg.tap('.mobile-nav-btn[data-nav=video]'); await pg.wait_for_timeout(1500)
    chips = await pg.evaluate(CHIPS); print(chips)
    check('YouTube' in chips, '%s a YouTube chip on Live TV %s' % (T, chips))
    await pg.evaluate("() => Array.from(document.querySelectorAll('#stationsGrid .epg-cat')).find(function(b){ return b.textContent === 'YouTube'; }).click()"); await pg.wait_for_timeout(600)
    rows = await pg.evaluate("() => Array.from(document.querySelectorAll('#stationsGrid .epg-row')).map(function(r){ return r.querySelector('.epg-ch').getAttribute('aria-label').split(',')[0]; })")
    check(sorted(rows) == ['Beach Cam Paradise', 'Springfield News Live'], '%s the YouTube chip shows just those %s' % (T, rows))
    await pg.screenshot(path=SHOTS + '/ytch-guide-%s.png' % theme)
    # play one: YouTube's player in the video box, the app's player stopped
    loads0 = await pg.evaluate("() => window.__calls.filter(function(c){ return c[0] === 'load'; }).length")
    await pg.evaluate(EV("playChannel(videoChannels.filter(function(c){ return c.src === 'youtube'; })[0]); 1")); await pg.wait_for_timeout(1500)
    st = await pg.evaluate("() => { var f = document.querySelector('#npYtBox iframe'); var n = document.getElementById('nowPlayingScreen'); var r = f ? f.getBoundingClientRect() : null; return { src: f ? f.src : null, yt: n.classList.contains('np-yt'), wrap: !document.getElementById('npVideoWrap').hidden, w: r ? Math.round(r.width) : 0, h: r ? Math.round(r.height) : 0, vid: getComputedStyle(document.getElementById('npVideo')).display, loads: window.__calls.filter(function(c){ return c[0] === 'load'; }).length, playing: window.__h.ev('uiIsPlaying') }; }")
    print(T, st)
    check(st['src'] and 'embed/live_stream?channel=UCabcdefghijklmnopqrstuv' in st['src'] and st['yt'] and st['wrap'] and st['w'] > 300 and abs(st['h'] - st['w'] * 9 / 16) < 3 and st['vid'] == 'none', '%s plays in YouTube’s player, in the 16:9 video box' % T)
    check(st['loads'] == loads0 and st['playing'], '%s the app’s own player isn’t asked to load it; it shows as playing' % T)
    await pg.screenshot(path=SHOTS + '/ytch-play-%s.png' % theme)
    # pause / play through the mini player send commands to YouTube's player
    await pg.evaluate("() => { window.__ytmsgs = []; var f = document.querySelector('#npYtBox iframe'); var orig = f.contentWindow.postMessage.bind(f.contentWindow); }")
    await pg.evaluate(EV("togglePlayPause(); 1")); await pg.wait_for_timeout(200)
    p1 = await pg.evaluate(EV("[uiIsPlaying, ytLive.playing]"))
    await pg.evaluate(EV("togglePlayPause(); 1")); await pg.wait_for_timeout(200)
    p2 = await pg.evaluate(EV("[uiIsPlaying, ytLive.playing]"))
    check(p1 == [False, False] and p2 == [True, True], '%s Pause / Play go to YouTube’s player %s %s' % (T, p1, p2))
    # another channel: YouTube's player goes, the normal player takes over
    await pg.evaluate(EV("playChannel(videoChannels[1]); 1")); await pg.wait_for_timeout(1200)
    st2 = await pg.evaluate("() => ({ f: !!document.querySelector('#npYtBox iframe'), yt: document.getElementById('nowPlayingScreen').classList.contains('np-yt'), loads: window.__calls.filter(function(c){ return c[0] === 'load'; }).length })")
    check(not st2['f'] and not st2['yt'] and st2['loads'] == loads0 + 1, '%s a normal channel next: YouTube’s player is gone, the app’s player plays it %s' % (T, st2))
    # the video link one
    await pg.evaluate(EV("playChannel(videoChannels.filter(function(c){ return c.src === 'youtube'; })[1]); 1")); await pg.wait_for_timeout(1000)
    s3 = await pg.evaluate("() => (document.querySelector('#npYtBox iframe') || {}).src || ''")
    check('/embed/abcdefghijk?' in s3, '%s a live video link plays that video %s' % (T, s3[:60]))
    # error from YouTube's player shows a message
    await pg.evaluate("() => { var f = document.querySelector('#npYtBox iframe'); window.dispatchEvent(new MessageEvent('message', { data: JSON.stringify({ event: 'onError', info: 150 }), source: f.contentWindow, origin: 'https://www.youtube.com' })); }"); await pg.wait_for_timeout(300)
    sub = await pg.evaluate("() => document.getElementById('playerSub').textContent")
    check('outside YouTube' in sub, '%s an embed-blocked stream says so %s' % (T, sub))
    check(not errs, '%s no page errors %s' % (T, errs[:3]))
    await b.close()
async def main():
    async with async_playwright() as p:
        await run(p, 'dark')
        await run(p, 'light')
    print('ALL PASSED' if not fails else 'FAILS %d' % len(fails))
asyncio.run(main())
