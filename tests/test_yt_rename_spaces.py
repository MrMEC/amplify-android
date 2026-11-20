"""Build 713 (Mark): spaces in a pasted YouTube link are taken out; a YouTube playlist channel can be renamed.
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
ROOT = '/tmp/claude-0/t/srv-ytrn'; SHOTS = '/tmp/claude-0/t/shots'
PORT = 8913
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
    answers = []
    async def dlg(d):
        await d.accept(answers.pop(0) if answers else '')
    pg.on('dialog', lambda d: asyncio.ensure_future(dlg(d)))
    await pg.route('**/*', route)
    await pg.goto('http://127.0.0.1:%d/index.html' % PORT); await pg.wait_for_timeout(2000)
    await pg.evaluate("() => document.getElementById('noticeOverlay').classList.remove('open')")
    await pg.evaluate(EV("addChannelsTab = 'youtube'; pushView(); openAddChannelsPage(); 1")); await pg.wait_for_timeout(700)
    # Mark's links came with a space after "playlist?" (and some paste with a line break)
    await pg.fill('#stationsGrid .ch-tools-row input', 'https://youtube.com/playlist? list=PLtest1234567890&si=KAOD Kp ')
    await pg.evaluate("() => document.querySelector('#stationsGrid .ch-tools-btns button').click()"); await pg.wait_for_timeout(1500)
    v = await pg.evaluate("() => document.querySelector('#stationsGrid .ch-tools-row input').value")
    check(v == 'https://youtube.com/playlist?list=PLtest1234567890&si=KAODKp', '%s the spaces are taken out of the link %r' % (T, v))
    row = await pg.evaluate("() => { var r = document.querySelector('#stationsGrid .ch-row'); return r ? [r.querySelector('.ch-name').textContent, getComputedStyle(r.querySelector('.ch-rename')).display] : null; }")
    check(row == ['Classic Cartoons', 'none'], '%s and the playlist loads (no Rename before it is a channel) %s' % (T, row))
    await pg.evaluate("() => document.querySelector('#stationsGrid .ch-row .ch-add:not(.ch-rename)').click()"); await pg.wait_for_timeout(500)
    url = await pg.evaluate(EV("'amplify-live:' + liveChDefs().filter(function(d){ return d.src.kind === 'yt'; })[0].id"))
    rn = await pg.evaluate("() => { var b = document.querySelector('#stationsGrid .ch-row .ch-rename'); var r = b.getBoundingClientRect(), a = document.querySelector('#stationsGrid .ch-row .ch-add.added').getBoundingClientRect(); return [getComputedStyle(b).display, Math.round(r.width), Math.round(a.left - r.right), Math.round(r.top - a.top)]; }")
    check(rn[0] != 'none' and rn[1] == 38 and rn[2] >= 4 and rn[3] == 0, '%s once added, a Rename button sits beside the check %s' % (T, rn))
    await pg.evaluate(EV("toggleFavorite(liveChStationOf(liveChannelByUrl(%s))); 1" % json.dumps(url)))
    answers.append('  Saturday   Cartoons ')
    await pg.evaluate("() => document.querySelector('#stationsGrid .ch-row .ch-rename').click()"); await pg.wait_for_timeout(600)
    await pg.evaluate("() => document.getElementById('noticeOverlay').classList.remove('open')"); await pg.wait_for_timeout(300)
    await pg.screenshot(path=SHOTS + '/ytrn-row-%s.png' % theme)
    r = json.loads(await pg.evaluate(EV("JSON.stringify([document.querySelector('#stationsGrid .ch-row .ch-name').textContent, liveChannelByUrl(%s).name, favorites.filter(function(f){ return f.liveCh === %s; }).map(function(f){ return f.name; })])" % (json.dumps(url), json.dumps(url)))))
    check(r == ['Saturday Cartoons', 'Saturday Cartoons', ['Saturday Cartoons']], '%s Rename names the channel everywhere (row, guide, Favorites) %s' % (T, r))
    # the channel's hold sheet has Rename too
    await pg.evaluate(EV("openVideoHome(); 1")); await pg.wait_for_timeout(300)
    await pg.tap('.mobile-nav-btn[data-nav=video]'); await pg.wait_for_timeout(1200)
    await pg.evaluate(EV("openChSheet(liveChannelByUrl(%s)); 1" % json.dumps(url))); await pg.wait_for_timeout(500)
    items = await pg.evaluate("() => Array.prototype.map.call(document.querySelectorAll('.ch-sheet-item'), function(b){ return b.textContent; })")
    ic = await pg.evaluate("() => { var b = Array.prototype.filter.call(document.querySelectorAll('.ch-sheet-item'), function(b){ return b.textContent === 'Rename'; })[0]; var s = b.querySelector('svg').getBoundingClientRect(), e = document.querySelectorAll('.ch-sheet-item')[1].firstElementChild.getBoundingClientRect(); return [Math.round(s.width), Math.round(s.left + s.width / 2 - (e.left + e.width / 2))]; }")
    check(ic[0] == 20 and abs(ic[1]) <= 1, '%s Rename has an icon, lined up with the others %s' % (T, ic))
    check('Rename' in items and items.index('Rename') == items.index('Edit Channel') + 1, '%s the channel’s sheet has Rename after Edit Channel %s' % (T, items))
    await pg.screenshot(path=SHOTS + '/ytrn-sheet-%s.png' % theme)
    answers.append('Toons')
    await pg.evaluate("() => Array.prototype.filter.call(document.querySelectorAll('.ch-sheet-item'), function(b){ return b.textContent === 'Rename'; })[0].click()"); await pg.wait_for_timeout(600)
    n = await pg.evaluate(EV("liveChannelByUrl(%s).name" % json.dumps(url)))
    check(n == 'Toons', '%s Rename from the sheet %r' % (T, n))
    await pg.screenshot(path=SHOTS + '/ytrn-guide-%s.png' % theme)
    answers.append('')   # an empty name goes back to the playlist's title
    await pg.evaluate(EV("promptRenameLiveChannel(%s); 1" % json.dumps(url.split(':', 1)[1]))); await pg.wait_for_timeout(400)
    n = await pg.evaluate(EV("[liveChannelByUrl(%s).name, liveChDefById(%s).name]" % (json.dumps(url), json.dumps(url.split(':', 1)[1]))))
    check(n == ['Classic Cartoons', ''], '%s an empty name goes back to the playlist’s title %s' % (T, n))
    # the editor's playlist field takes spaces out too
    await pg.evaluate(EV("openLiveChEditor(%s); 1" % json.dumps(url.split(':', 1)[1]))); await pg.wait_for_timeout(500)
    await pg.fill('#liveChYtUrl', 'https://youtube.com/playlist?\nlist=PLtest 1234567890')
    await pg.evaluate("() => document.getElementById('liveChYtLoad').click()"); await pg.wait_for_timeout(1200)
    e = await pg.evaluate("() => [document.getElementById('liveChYtUrl').value, document.getElementById('liveChYtNote').textContent]")
    check(e[0] == 'https://youtube.com/playlist?list=PLtest1234567890' and e[1].startswith('Classic Cartoons'), '%s the editor takes spaces out of its link too %s' % (T, e))
    check(not errs, '%s no page errors %s' % (T, errs[:3]))
    await b.close()
async def main():
    async with async_playwright() as p:
        await run(p, 'dark')
        await run(p, 'light')
    print('ALL PASSED' if not fails else 'FAILS %d' % len(fails))
asyncio.run(main())
