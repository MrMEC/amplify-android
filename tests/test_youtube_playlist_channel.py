"""Build 711 (Mark): a custom Live TV channel from a YouTube playlist, on the guide’s clock (YouTube player in the video box, a YouTube category).
Run: python3 tests/test_youtube_playlist_channel.py
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
ROOT = '/tmp/claude-0/t/srv-ytpl'; SHOTS = '/tmp/claude-0/t/shots'
PORT = 8906
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
    if 'youtube.com' in u.netloc and u.path.startswith('/youtubei/v1/browse'):
        body = json.loads(r.request.post_data or '{}')
        def vid(i, n, secs): return {'playlistVideoRenderer': {'videoId': 'vid%07d' % i + 'abc'[:11 - 10], 'title': {'runs': [{'text': n}]}, 'shortBylineText': {'runs': [{'text': 'Test Creator'}]}, 'lengthSeconds': str(secs), 'isPlayable': True}}
        if body.get('browseId') == 'VLPLtest1234567890':
            data = {'metadata': {'playlistMetadataRenderer': {'title': 'Classic Cartoons'}}, 'contents': {'x': {'contents': [vid(1, 'Cartoon One', 1500), vid(2, 'Cartoon Two', 1320), {'playlistVideoRenderer': {'videoId': 'privvid0000', 'title': {'simpleText': '[Private video]'}, 'isPlayable': False}}, {'continuationItemViewModel': {'trigger': 'CONTINUATION_TRIGGER_ON_ITEM_SHOWN', 'continuationCommand': {'innertubeCommand': {'continuationCommand': {'token': 'TOKEN2', 'request': 'CONTINUATION_REQUEST_TYPE_BROWSE'}}}}}]}}}
        elif body.get('continuation') == 'TOKEN2':
            # build 712: YouTube's current format (lockupViewModel, length only on the picture's badge)
            def lock(i, n, dur): return {'lockupViewModel': {'contentId': 'vid%07da' % i, 'contentType': 'LOCKUP_CONTENT_TYPE_VIDEO',
                'contentImage': {'thumbnailViewModel': {'overlays': [{'thumbnailBottomOverlayViewModel': {'badges': [{'thumbnailBadgeViewModel': {'text': dur}}]}}]}},
                'metadata': {'lockupMetadataViewModel': {'title': {'content': n}, 'metadata': {'contentMetadataViewModel': {'metadataRows': [{'metadataParts': [{'text': {'content': 'Test Creator'}}]}, {'metadataParts': [{'text': {'content': '1K views'}}]}]}}}}}}
            data = {'onResponseReceivedActions': [{'appendContinuationItemsAction': {'continuationItems': [lock(3, 'Cartoon Three', '28:00'), lock(5, 'Live Now', 'LIVE'), lock(4, 'Cartoon Four', '15:00')]}}]}
        else:
            return await r.fulfill(status=400, body='{}')
        return await r.fulfill(status=200, content_type='application/json', headers=cors, body=json.dumps(data))
    if 'youtube.com' in u.netloc and u.path == '/oembed': return await r.fulfill(status=200, content_type='application/json', headers=cors, body=json.dumps({'title': 'Live: News all day', 'author_name': 'Springfield News Live', 'thumbnail_url': 'https://i.ytimg.com/vi/abcdefghijk/hqdefault.jpg'}))
    if 'youtube.com' in u.netloc and u.path.startswith('/@'): return await r.fulfill(status=200, content_type='text/html', headers=cors, body='<html><head><meta property="og:title" content="Beach Cam Paradise"><meta property="og:image" content="https://yt3.example/a.png"></head><body>{"externalId":"UCabcdefghijklmnopqrstuv"}</body></html>')
    if 'youtube.com' in u.netloc and u.path.startswith('/embed'): return await r.fulfill(status=200, content_type='text/html', body='<html><body style="background:#300;color:#fff;font:20px sans-serif">YT PLAYER ' + u.path + '</body></html>')
    if u.netloc in ('i.ytimg.com', 'yt3.example'): return await r.fulfill(status=200, content_type='image/png', headers=cors, body=ORANGE)
    if u.netloc == 'miamitv.sfo3.cdn.example': return await r.fulfill(status=200, content_type='image/png', headers=cors, body=ORANGE)
    return await r.abort()




EV = lambda js: "() => window.__h.ev(%s)" % json.dumps(js)
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
    ids = await pg.evaluate(EV("JSON.stringify(['https://www.youtube.com/playlist?list=PLtest1234567890','https://youtube.com/watch?v=abcdefghijk&list=PLtest1234567890&index=2','https://www.youtube.com/watch?v=abcdefghijk&list=RDabcdefghijk','https://www.youtube.com/watch?v=abcdefghijk'].map(ytPlId))"))
    check(json.loads(ids) == ['PLtest1234567890', 'PLtest1234567890', '', ''], '%s playlist links are recognised (not a mix, not a plain video) %s' % (T, ids))
    # Add Channels > YouTube: the playlist
    await pg.evaluate(EV("addChannelsTab = 'youtube'; pushView(); openAddChannelsPage(); 1")); await pg.wait_for_timeout(700)
    await pg.fill('#stationsGrid .ch-tools-row input', 'https://www.youtube.com/playlist?list=PLtest1234567890')
    await pg.evaluate("() => document.querySelector('#stationsGrid .ch-tools-btns button').click()"); await pg.wait_for_timeout(1500)
    row = await pg.evaluate("() => { var r = document.querySelector('#stationsGrid .ch-row'); return r ? [r.querySelector('.ch-name').textContent, r.querySelector('.ch-sub').textContent] : null; }")
    check(row == ['Classic Cartoons', 'YouTube playlist · 4 videos · about 2 hours'], '%s the playlist is read, page after page, skipping a private video %s' % (T, row))
    await pg.screenshot(path=SHOTS + '/ytpl-find-%s.png' % theme)
    await pg.evaluate("() => document.querySelector('#stationsGrid .ch-row .ch-add').click()"); await pg.wait_for_timeout(500)
    d = json.loads(await pg.evaluate(EV("JSON.stringify(liveChDefs().filter(function(d){ return d.src.kind === 'yt'; }).map(function(d){ return { list: d.src.list, n: d.src.items.length, order: d.order, url: 'amplify-live:' + d.id }; }))")))
    check(len(d) == 1 and d[0]['list'] == 'PLtest1234567890' and d[0]['n'] == 4 and d[0]['order'] == 'sequence', '%s + makes a channel of your own from it %s' % (T, d))
    url = d[0]['url']
    added = await pg.evaluate("() => document.querySelector('#stationsGrid .ch-row .ch-add').classList.contains('added')")
    check(added, '%s and the + turns into a check' % T)
    # the guide: on the clock, one after another
    sched = json.loads(await pg.evaluate(EV("JSON.stringify((function(){ var ch = liveChannelByUrl(%s); var t = Date.now(), s1 = liveChSlot(ch, t), s2 = liveChSlot(ch, s1.e); return { name: ch.name, a: [s1.v.title, s1.s, s1.e, s1.v.duration], b: [s2.v.title, s2.s], cats: chCategories(ch), progs: liveChItems(ch).slice(0, 3).map(function(p){ return [p.t, p.sub, Math.round((p.e - p.s) / 1000)]; }) }; })())" % json.dumps(url))))
    print(T, sched)
    check(sched['name'] == 'Classic Cartoons' and sched['a'][2] - sched['a'][1] == sched['a'][3] * 1000 and sched['b'][1] == sched['a'][2], '%s the videos follow each other on the guide’s clock, each as long as it is' % T)
    seq = [x[0] for x in sched['progs']]; order = ['Cartoon One', 'Cartoon Two', 'Cartoon Three', 'Cartoon Four']
    i0 = order.index(seq[0])
    check(seq == [order[(i0 + k) % 4] for k in range(3)] and all(x[1] == 'Test Creator' for x in sched['progs']), '%s in the playlist’s order, the creator under each %s' % (T, sched['progs']))
    check(sched['cats'] == ['My Channels', 'YouTube'], '%s it is under My Channels and YouTube %s' % (T, sched['cats']))
    # tune in: the video that's on, part-way in
    await pg.evaluate(EV("openVideoHome(); 1")); await pg.wait_for_timeout(300)
    await pg.tap('.mobile-nav-btn[data-nav=video]'); await pg.wait_for_timeout(1500)
    await pg.screenshot(path=SHOTS + '/ytpl-guide-%s.png' % theme)
    loads0 = await pg.evaluate("() => window.__calls.filter(function(c){ return c[0] === 'load'; }).length")
    await pg.evaluate(EV("playStation(liveChStationOf(liveChannelByUrl(%s))); 1" % json.dumps(url))); await pg.wait_for_timeout(1500)
    st = await pg.evaluate("""() => { var f = document.querySelector('#npYtBox iframe'); var c = window.__h.ev('currentStation'); var sl = window.__h.ev('liveChSlot(liveChannelByUrl(' + JSON.stringify(%s) + '), Date.now())');
        return { src: f ? f.src : '', yt: document.getElementById('nowPlayingScreen').classList.contains('np-yt'), id: c && c.ytVideo, slotV: sl.v.v, off: Math.floor((Date.now() - sl.s) / 1000), loads: window.__calls.filter(function(c){ return c[0] === 'load'; }).length, sub: document.getElementById('playerSub').textContent }; }""" % json.dumps(url))
    print(T, st)
    import re
    m = re.search(r'/embed/([\w-]+)\?.*start=(\d+)', st['src'] or '')
    check(m and m.group(1) == st['slotV'] and abs(int(m.group(2)) - st['off']) <= 3 and st['yt'], '%s tuning in plays the video that’s on, from where it is now (start=%s, %ss in)' % (T, m and m.group(2), st['off']))
    check(st['loads'] == loads0, '%s in YouTube’s player, not the app’s' % T)
    await pg.evaluate(EV("openNowPlaying(currentStation); 1")); await pg.wait_for_timeout(900)
    bx = await pg.evaluate("() => { var f = document.querySelector('#npYtBox iframe').getBoundingClientRect(); return [document.getElementById('nowPlayingScreen').classList.contains('np-yt'), Math.round(f.width), Math.round(f.height), document.getElementById('npTitle') ? document.getElementById('npTitle').textContent : '']; }")
    check(bx[0] and bx[1] > 300 and abs(bx[2] - bx[1] * 9 / 16) < 3, '%s on the channel’s screen, YouTube’s player is in the 16:9 video box %s' % (T, bx))
    await pg.screenshot(path=SHOTS + '/ytpl-play-%s.png' % theme)
    # the video ends: the next one, from its top
    await pg.evaluate("() => { var f = document.querySelector('#npYtBox iframe'); window.dispatchEvent(new MessageEvent('message', { data: JSON.stringify({ event: 'onStateChange', info: 0 }), source: f.contentWindow, origin: 'https://www.youtube.com' })); }")
    await pg.wait_for_timeout(1200)
    nx = await pg.evaluate("() => (document.querySelector('#npYtBox iframe') || {}).src || ''")
    order_ids = {'Cartoon One': 'vid0000001a', 'Cartoon Two': 'vid0000002a', 'Cartoon Three': 'vid0000003a', 'Cartoon Four': 'vid0000004a'}
    cur_title = sched['a'][0]; nxt = order[(order.index(cur_title) + 1) % 4]
    check(('/embed/' + order_ids[nxt] + '?') in nx and 'start=' not in nx, '%s when it ends, the next video plays from its top %s' % (T, nx[:70]))
    # the editor shows it as a YouTube Playlist channel
    await pg.evaluate(EV("openLiveChEditor(%s); 1" % json.dumps(url.split(':', 1)[1]))); await pg.wait_for_timeout(600)
    ed = await pg.evaluate("() => [(document.querySelector('#liveChKind .home-tab.active') || {}).textContent, document.getElementById('liveChPaneYt').hidden, document.getElementById('liveChYtNote').textContent, document.getElementById('liveChAdsField').hidden, document.getElementById('liveChSaveBtn').disabled, document.getElementById('liveChSummary').textContent]")
    print(T, ed)
    check(ed[0] == 'YouTube Playlist' and not ed[1] and ed[2].startswith('Classic Cartoons · 4 videos') and ed[3] and not ed[4] and '4 YouTube videos' in ed[5], '%s the editor shows a YouTube Playlist channel (no commercials option) %s' % (T, ed))
    await pg.screenshot(path=SHOTS + '/ytpl-editor-%s.png' % theme)
    # save keeps the playlist
    await pg.evaluate("() => document.getElementById('liveChSaveBtn').click()"); await pg.wait_for_timeout(500)
    n2 = await pg.evaluate(EV("liveChDefs().filter(function(d){ return d.src.kind === 'yt'; })[0].src.items.length"))
    check(n2 == 4, '%s saving in the editor keeps the playlist (%s videos)' % (T, n2))
    check(not errs, '%s no page errors %s' % (T, errs[:3]))
    await b.close()
async def main():
    async with async_playwright() as p:
        await run(p, 'dark')
        await run(p, 'light')
    print('ALL PASSED' if not fails else 'FAILS %d' % len(fails))
asyncio.run(main())
