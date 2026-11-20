"""Build 715 (Mark): the Live TV filter is a search button fixed at the left of the guide's category bar (Watch and under a playing channel): the box slides out over the chips; Stop on the YouTube player.
Build 711 (Mark): a custom Live TV channel from a YouTube playlist, on the guide’s clock (YouTube player in the video box, a YouTube category).
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
ROOT = '/tmp/claude-0/t/srv-epgfind'; SHOTS = '/tmp/claude-0/t/shots'
PORT = 8915
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
BAR = """(sel) => { var root = document.querySelector(sel); var b = root.querySelector('.epg-catbar'); if(!b) return null;
  var btn = b.querySelector('.epg-find-btn').getBoundingClientRect(), f = b.querySelector('.epg-find').getBoundingClientRect(), bb = b.getBoundingClientRect(), slot = b.querySelector('.epg-cats-slot'), cats = b.querySelector('.epg-cats');
  var rows = Array.prototype.filter.call(root.querySelectorAll('.epg-row'), function(r){ return r.offsetParent; }).map(function(r){ var c = r.querySelector('.epg-ch'); return c.getAttribute('aria-label') || c.textContent; });
  return { open: b.classList.contains('find-open'), btnL: Math.round(btn.left - bb.left), btnW: Math.round(btn.width), fL: Math.round(f.left), fR: Math.round(f.right), barR: Math.round(bb.right), btnR: Math.round(btn.right),
    slotVis: getComputedStyle(slot).visibility, catsSL: cats ? cats.scrollLeft : null, rows: rows, none: (root.querySelector('.epg-find-none') || {}).hidden === false ? root.querySelector('.epg-find-none').textContent : '' }; }"""
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
    await pg.tap('.mobile-nav-btn[data-nav=video]'); await pg.wait_for_timeout(3500)   # the archive.org channel's lineup settles (a redraw)
    old = await pg.evaluate("() => { var f = document.getElementById('secFilter'); return !!(f && f.isConnected && f.offsetParent); }")
    check(not old, '%s the old Filter channels box is gone from Live TV' % T)
    r = await pg.evaluate(BAR, '#stationsGrid')
    print(T, r)
    check(r and not r['open'] and r['btnL'] == 4 and r['btnW'] == 38 and r['fR'] <= r['btnR'] + 1 and r['slotVis'] == 'visible', '%s a search button sits at the left of the category bar, the box tucked away' % T)
    await pg.screenshot(path=SHOTS + '/epgfind-closed-%s.png' % theme)
    # the chips scroll; the button stays put
    r2 = await pg.evaluate("() => { var c = document.querySelector('#stationsGrid .epg-cats'), b = document.querySelector('#stationsGrid .epg-find-btn'), x0 = b.getBoundingClientRect().left; c.scrollLeft = 200; return { catsSL: c.scrollLeft, btnL: Math.round(b.getBoundingClientRect().left - x0 + 4) }; }")
    check(r2['catsSL'] > 0 and r2['btnL'] == 4, '%s scrolling the chips sideways leaves the button where it is (chips at %s)' % (T, r2['catsSL']))
    await pg.screenshot(path=SHOTS + '/epgfind-scrolled-%s.png' % theme)
    await pg.evaluate("() => { var f = document.querySelector('#stationsGrid .epg-find'); window.__xs = []; var t0 = performance.now(); (function tick(){ window.__xs.push(Math.round(f.getBoundingClientRect().left)); if(performance.now() - t0 < 400) requestAnimationFrame(tick); })(); }")
    await pg.tap('#stationsGrid .epg-find-btn'); await pg.wait_for_timeout(500)
    xs = await pg.evaluate("() => window.__xs")
    mid = {'fL': min([x for x in xs if -230 < x < 49] or [99])}
    print(T, 'slide', xs)
    r3 = await pg.evaluate(BAR, '#stationsGrid')
    foc = await pg.evaluate("() => document.activeElement && document.activeElement.closest('.epg-find') ? 1 : 0")
    print(T, 'mid', mid['fL'], 'end', r3)
    check(r3['open'] and r3['slotVis'] == 'hidden' and r3['fL'] == r3['btnR'] + 7 and r3['fR'] == r3['barR'] - 4 and mid['fL'] < r3['fL'] and foc, '%s a tap slides the box out from the left over the chips (hidden), ready to type' % T)
    await pg.keyboard.type('three')
    await pg.wait_for_timeout(300)
    r4 = await pg.evaluate(BAR, '#stationsGrid')
    check(r4['rows'] == ["Three's Company"], '%s typing filters the guide %s' % (T, r4['rows']))
    await pg.screenshot(path=SHOTS + '/epgfind-open-%s.png' % theme)
    # a redraw of the guide keeps the box, its text and the focus
    await pg.evaluate(EV("rebuildEpgGridsInPlace(); 1")); await pg.wait_for_timeout(300)
    r5 = await pg.evaluate(BAR, '#stationsGrid')
    foc = await pg.evaluate("() => document.activeElement && document.activeElement.closest('.epg-find') ? document.activeElement.value : ''")
    check(r5['open'] and r5['rows'] == ["Three's Company"] and foc == 'three', '%s a guide redraw keeps the box, its text and the keyboard %s' % (T, r5['rows']))
    await pg.keyboard.type('zz'); await pg.wait_for_timeout(200)
    r6 = await pg.evaluate(BAR, '#stationsGrid')
    check(r6['rows'] == [] and 'threezz' in r6['none'], '%s nothing matching says so %r' % (T, r6['none']))
    await pg.tap('#stationsGrid .epg-find-btn'); await pg.wait_for_timeout(500)
    r7 = await pg.evaluate(BAR, '#stationsGrid')
    v = await pg.evaluate("() => document.querySelector('#stationsGrid .epg-find input').value")
    check(not r7['open'] and r7['slotVis'] == 'visible' and len(r7['rows']) > 5 and v == '' and r7['fR'] <= r7['btnR'] + 1 and not r7['none'], '%s another tap slides it back, clears it, and the chips return' % T)
    # under a playing channel
    await pg.evaluate(EV("playChannel(videoChannels[1]); 1")); await pg.wait_for_timeout(800)
    await pg.evaluate(EV("openNowPlaying(currentStation); 1")); await pg.wait_for_timeout(1200)
    n = await pg.evaluate(BAR, '#npCollection')
    print(T, 'np', n and {k: n[k] for k in ('open', 'btnL', 'slotVis')})
    check(n and n['btnL'] == 4 and not n['open'], '%s the guide under a playing channel has the button too' % T)
    await pg.tap('#npCollection .epg-find-btn'); await pg.wait_for_timeout(500)
    await pg.keyboard.type('prairie'); await pg.wait_for_timeout(300)
    n2 = await pg.evaluate(BAR, '#npCollection')
    check(n2['open'] and n2['rows'] == ['Little House on the Prairie, playing'], '%s and filters that guide %s' % (T, n2['rows']))
    await pg.evaluate("() => document.activeElement && document.activeElement.blur()")
    await pg.screenshot(path=SHOTS + '/epgfind-np-%s.png' % theme)
    await pg.tap('#npCollection .epg-find-btn'); await pg.wait_for_timeout(400)
    await pg.evaluate(EV("closeNowPlaying(); 1")); await pg.wait_for_timeout(500)
    # YouTube player: Stop
    await pg.evaluate(EV("ytPlaylistFetch('PLtest1234567890').then(function(p){ window.__d = ytPlaylistChannel(p); }); 1")); await pg.wait_for_timeout(1500)
    await pg.evaluate(EV("playStation(liveChStationOf(liveChannelByUrl('amplify-live:' + window.__d.id))); 1")); await pg.wait_for_timeout(1200)
    await pg.evaluate(EV("openNowPlaying(currentStation); 1")); await pg.wait_for_timeout(1200)
    await pg.evaluate("() => document.getElementById('npVideoWrap').dispatchEvent(new PointerEvent('pointerdown', { bubbles: true }))"); await pg.wait_for_timeout(400)
    sb = await pg.evaluate("() => { var s = document.getElementById('npYtStop').getBoundingClientRect(), f = document.getElementById('npYtFull').getBoundingClientRect(), v = document.querySelector('#npYtBox iframe').getBoundingClientRect(); return [getComputedStyle(document.getElementById('npYtStop')).opacity, Math.round(s.left - v.left), Math.round(s.top - v.top), Math.round(f.top - v.top), Math.round(v.right - f.right), Math.round(s.width)]; }")
    print(T, 'stop', sb)
    check(sb[0] == '1' and sb[1] == 8 and sb[2] == sb[3] == 8 and sb[4] == 8 and sb[5] == 36, '%s a tap on the picture shows Stop (top left) with Full screen (top right) %s' % (T, sb))
    await pg.screenshot(path=SHOTS + '/epgfind-ytstop-%s.png' % theme)
    await pg.wait_for_timeout(3300)
    fo = await pg.evaluate("() => getComputedStyle(document.getElementById('npYtStop')).opacity")
    check(fo == '0', '%s and it fades with it' % T)
    await pg.evaluate("() => document.getElementById('npVideoWrap').dispatchEvent(new PointerEvent('pointerdown', { bubbles: true }))"); await pg.wait_for_timeout(400)
    await pg.tap('#npYtStop'); await pg.wait_for_timeout(800)
    st = await pg.evaluate(EV("[!!ytLive, !!currentStation, document.getElementById('npYtBox').children.length, nowPlayingScreen.style.display]"))
    check(st[:3] == [False, False, 0] and st[3] != 'flex', '%s Stop stops the channel and closes its player %s' % (T, st))
    await pg.screenshot(path=SHOTS + '/epgfind-afterstop-%s.png' % theme)
    check(not errs, '%s no page errors %s' % (T, errs[:3]))
    await b.close()
async def main():
    async with async_playwright() as p:
        await run(p, 'dark')
        await run(p, 'light')
    print('ALL PASSED' if not fails else 'FAILS %d' % len(fails))
asyncio.run(main())
