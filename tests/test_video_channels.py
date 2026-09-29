"""Video > channels: Add Channels (Recommended / All Channels / From a Link), My Channels,
playing a channel, "Not working" marking, reorder and remove. Mocked sources and native bridge.
Run: python3 tests/test_video_channels.py (screenshots in /tmp/claude-0/t/shots)"""
import asyncio, json, os, shutil, threading, http.server, functools
from playwright.async_api import async_playwright
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = '/tmp/claude-0/t/srv-ch'; SHOTS = '/tmp/claude-0/t/shots'
os.makedirs(ROOT, exist_ok=True); os.makedirs(SHOTS, exist_ok=True)
shutil.copy(os.path.join(HERE, '..', 'www', 'index.html'), ROOT)
H = functools.partial(http.server.SimpleHTTPRequestHandler, directory=ROOT); H.log_message = lambda *a: None
srv = http.server.ThreadingHTTPServer(('127.0.0.1', 8777), H); threading.Thread(target=srv.serve_forever, daemon=True).start()

API = {
 'channels.json': [{'id': 'ABCNews.us', 'name': 'ABC News Live', 'country': 'US', 'categories': ['news'], 'is_nsfw': False, 'closed': None},
                   {'id': 'Weather.us', 'name': 'Weather Nation', 'country': 'US', 'categories': ['weather'], 'is_nsfw': False},
                   {'id': 'BBC.uk', 'name': 'BBC News', 'country': 'UK', 'categories': ['news'], 'is_nsfw': False},
                   {'id': 'Adult.us', 'name': 'Hidden Adult', 'country': 'US', 'categories': ['xxx'], 'is_nsfw': True},
                   {'id': 'Blocked.us', 'name': 'Blocked One', 'country': 'US', 'categories': ['news'], 'is_nsfw': False},
                   {'id': 'Ref.us', 'name': 'Needs Referrer', 'country': 'US', 'categories': ['news'], 'is_nsfw': False}],
 'streams.json': [{'channel': 'ABCNews.us', 'url': 'https://abc.example/live.m3u8', 'quality': '720p'},
                  {'channel': 'ABCNews.us', 'url': 'https://abc.example/live1080.m3u8', 'quality': '1080p'},
                  {'channel': 'Weather.us', 'url': 'https://wx.example/live.m3u8', 'quality': '480p'},
                  {'channel': 'BBC.uk', 'url': 'https://bbc.example/live.m3u8'},
                  {'channel': 'Adult.us', 'url': 'https://x.example/a.m3u8'},
                  {'channel': 'Blocked.us', 'url': 'https://b.example/b.m3u8'},
                  {'channel': 'Ref.us', 'url': 'https://r.example/r.m3u8', 'referrer': 'https://r.example/'}],
 'logos.json': [{'channel': 'ABCNews.us', 'feed': None, 'url': 'https://logo.example/abc.png'}],
 'categories.json': [{'id': 'news', 'name': 'News'}, {'id': 'weather', 'name': 'Weather'}],
 'countries.json': [{'code': 'US', 'name': 'United States'}, {'code': 'UK', 'name': 'United Kingdom'}],
 'blocklist.json': [{'channel': 'Blocked.us', 'reason': 'dmca'}],
}
FREETV = '#EXTM3U\n#EXTINF:-1 tvg-logo="https://logo.example/pbs.png" group-title="USA",PBS\nhttps://pbs.example/live.m3u8\n#EXTINF:-1 group-title="UK",Channel 4\nhttps://c4.example/live.m3u8\n'
LINKPL = '#EXTM3U\n#EXTINF:-1,Link One\nhttp://one.example/1.m3u8\n#EXTINF:-1,Link Two\n#EXTVLCOPT:http-referrer=https://x/\nhttp://two.example/2.m3u8\n#EXTINF:-1,Link Three\nhttp://three.example/3.m3u8\n'
MOCK = """
(function(){
 window.__calls=[]; window.__L={}; window.__emit=function(t,ev){ (window.__L[t]||[]).forEach(function(f){ f(ev); }); };
 var P=new Proxy({}, {get:function(t,k){
   if(k==='then') return undefined;
   if(k==='addListener') return function(n,f){ (window.__L[n]=window.__L[n]||[]).push(f); return Promise.resolve({remove:function(){}}); };
   if(k==='load') return function(a){ window.__calls.push(['load',a.url]); window.__cur=a.id;
      if(/bbc/.test(a.url)) setTimeout(function(){ window.__emit('error',{id:a.id,code:2004,name:'ERROR_CODE_IO_BAD_HTTP_STATUS'}); },60);
      else setTimeout(function(){ window.__emit('state',{id:a.id,state:'ready',isPlaying:true,playWhenReady:true,position:0,duration:-1,live:true}); },60);
      return Promise.resolve({}); };
   if(k==='fetchText') return function(a){ window.__calls.push(['fetchText',a.url]); return /list\\.m3u/.test(a.url) ? Promise.resolve({text:%s,url:a.url}) : Promise.reject(new Error('stream')); };
   if(k==='videoState') return function(){ return Promise.resolve({id:null,hasVideo:false}); };
   return function(){ return Promise.resolve({}); };
 }});
 window.Capacitor={isNativePlatform:function(){return true;},getPlatform:function(){return 'android';},Plugins:{AmplifyPlayer:P},convertFileSrc:function(u){return u;}};
})();
""" % json.dumps(LINKPL)
fails = 0
def check(ok, msg):
    global fails
    print(('PASS ' if ok else 'FAIL ') + msg); fails += 0 if ok else 1

async def route(r):
    u = r.request.url
    cors = {'Access-Control-Allow-Origin': '*'}
    if 'iptv-org.github.io/api/' in u:
        name = u.rsplit('/', 1)[-1]
        return await r.fulfill(status=200, content_type='application/json', headers=cors, body=json.dumps(API.get(name, [])))
    if 'raw.githubusercontent.com/Free-TV' in u:
        return await r.fulfill(status=200, content_type='application/vnd.apple.mpegurl', headers=cors, body=FREETV)
    if 'logo.example' in u: return await r.fulfill(status=404, body='')
    if 'list.example' in u: return await r.abort()  # the page can't read it (on a phone: CORS); the app's fetch can
    return await r.continue_()

async def rows(pg):
    return await pg.evaluate("Array.prototype.map.call(document.querySelectorAll('.ch-row'),function(r){return {name:r.querySelector('.ch-name').textContent,added:r.querySelector('.ch-add').classList.contains('added')};})")
async def my_tiles(pg):
    return await pg.evaluate("Array.prototype.map.call(document.querySelectorAll('#stationsGrid .tile'),function(t){var d=t.querySelector('.ch-dead');return {name:t.querySelector('.tile-name').textContent,dead:!!d};})")
async def tab(pg, label):
    await pg.evaluate("(l)=>Array.prototype.find.call(document.querySelectorAll('.ch-tools .home-tab'),function(b){return b.textContent===l;}).click()", label)
    await pg.wait_for_timeout(900)

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
        ctx = await b.new_context(viewport={'width': 390, 'height': 844}, device_scale_factor=2, is_mobile=True, has_touch=True, color_scheme='dark', locale='en-US')
        await ctx.add_init_script(MOCK)
        pg = await ctx.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.route('**/*', route)
        await pg.goto('http://127.0.0.1:8777/index.html'); await pg.wait_for_timeout(2500)

        await pg.evaluate("document.querySelector('.mobile-nav-btn[data-nav=video]').click()"); await pg.wait_for_timeout(600)
        empty = await pg.evaluate("document.querySelector('#stationsGrid .empty-state') && document.querySelector('#stationsGrid .empty-state').textContent")
        addv = await pg.evaluate("getComputedStyle(document.getElementById('videoAddHeaderBtn')).display!=='none'")
        check(bool(empty) and 'Add Channels' in empty and addv, f'Video page: empty My Channels with Add Channels ({empty})')

        await pg.evaluate("document.getElementById('videoAddHeaderBtn').click()"); await pg.wait_for_timeout(1200)
        back = await pg.evaluate("document.getElementById('detailBackLabel').textContent")
        r = await rows(pg)
        check(back == 'Video' and [x['name'] for x in r] == ['PBS'], f'Recommended (Free-TV) opens on your country (USA), back says Video {back} {r}')
        await pg.evaluate("document.querySelector('.ch-row .ch-add').click()"); await pg.wait_for_timeout(200)
        check((await rows(pg))[0]['added'], '+ adds PBS (button turns into a check)')
        await pg.screenshot(path=f'{SHOTS}/ch-recommended.png')
        check(not await pg.evaluate("!!document.querySelector('.ch-tools-note')"), 'no instructions under the tabs (Recommended)')

        await tab(pg, 'All')
        r = await rows(pg)
        names = [x['name'] for x in r]
        check(names == ['ABC News Live', 'Weather Nation'], f'All Channels: US by default; adult, blocked, referrer-only and other countries left out {names}')
        sub = await pg.evaluate("document.querySelector('.ch-row .ch-sub').textContent")
        check(sub == 'United States · News', f'row shows country and category ({sub})')
        urls = await pg.evaluate("window.__calls.filter(function(c){return c[0]==='fetchText';}).length")
        check(urls == 0, 'GitHub sources read directly (no native fetch needed)')
        await pg.evaluate("(()=>{var i=document.querySelector('.ch-tools input');i.value='weather';i.dispatchEvent(new Event('input'));})()"); await pg.wait_for_timeout(600)
        check([x['name'] for x in await rows(pg)] == ['Weather Nation'], 'search filters as you type')
        await pg.evaluate("(()=>{var i=document.querySelector('.ch-tools input');i.value='';i.dispatchEvent(new Event('input'));})()"); await pg.wait_for_timeout(600)
        await pg.evaluate("(()=>{var s=document.querySelectorAll('.ch-tools select')[0];s.value='';s.dispatchEvent(new Event('change'));})()"); await pg.wait_for_timeout(500)
        check(len(await rows(pg)) == 3, 'All countries shows the UK channel too')
        await pg.evaluate("(()=>{var s=document.querySelectorAll('.ch-tools select')[1];s.value='weather';s.dispatchEvent(new Event('change'));})()"); await pg.wait_for_timeout(500)
        check([x['name'] for x in await rows(pg)] == ['Weather Nation'], 'category filter')
        await pg.evaluate("(()=>{var s=document.querySelectorAll('.ch-tools select')[1];s.value='';s.dispatchEvent(new Event('change'));})()"); await pg.wait_for_timeout(500)
        catopts = "Array.prototype.map.call(document.querySelectorAll('.ch-tools select')[1].options,function(o){return o.textContent;})"
        names = [x['name'] for x in await rows(pg)]
        cats = await pg.evaluate(catopts)
        noset = await pg.evaluate("!document.getElementById('adultChannelsSelect') && !/Adult channels/.test(document.getElementById('settingsPanel').textContent)")
        check('Hidden Adult' not in names and not any(c in ('Adult', 'XXX', 'xxx') for c in cats) and noset, f'no adult channels, no Adult category, no setting {names} {cats}')
        for n in ('ABC News Live', 'BBC News'):
            await pg.evaluate("(n)=>Array.prototype.find.call(document.querySelectorAll('.ch-row'),function(r){return r.querySelector('.ch-name').textContent===n;}).querySelector('.ch-add').click()", n)
        await pg.wait_for_timeout(200)
        await pg.screenshot(path=f'{SHOTS}/ch-all.png')
        check(not await pg.evaluate("!!document.querySelector('.ch-tools-note')"), 'no instructions under the tabs (All)')
        # tap a row = try it (plays + Now Playing) without adding
        await pg.evaluate("Array.prototype.find.call(document.querySelectorAll('.ch-row'),function(r){return r.querySelector('.ch-name').textContent==='Weather Nation';}).click()"); await pg.wait_for_timeout(700)
        np = await pg.evaluate("document.getElementById('nowPlayingScreen').style.display")
        last = await pg.evaluate("window.__calls.filter(function(c){return c[0]==='load';}).slice(-1)[0]")
        check(np == 'flex' and last and last[1] == 'https://wx.example/live.m3u8', f'tapping a row tries the channel: plays it, Now Playing opens {last}')
        lk = "(()=>{var l=document.getElementById('npChannelLink');return l.style.display==='none'?null:l.textContent;})()"
        mine = "JSON.parse(localStorage.getItem('radioPlayerVideoChannels')||'[]').map(function(c){return c.name;})"
        check(await pg.evaluate(lk) == 'Add to My Channels', f'Now Playing for a channel not saved: Add to My Channels ({await pg.evaluate(lk)})')
        await pg.evaluate("document.getElementById('npChannelLink').click()"); await pg.wait_for_timeout(300)
        check('Weather Nation' in await pg.evaluate(mine) and await pg.evaluate(lk) == 'Remove from My Channels', 'tapping it adds the channel, link turns into Remove from My Channels')
        inmenu = await pg.evaluate("!!document.getElementById('npChannelLink').closest('#npMenu')")
        check(inmenu, 'the option lives in the More (3-dot) menu')
        await pg.evaluate("document.getElementById('npMenuBtn').click()"); await pg.wait_for_timeout(300)
        await pg.screenshot(path=f'{SHOTS}/ch-np-link.png')
        await pg.evaluate("document.getElementById('npMenuBtn').click()"); await pg.wait_for_timeout(200)
        await pg.evaluate("document.getElementById('npChannelLink').click()"); await pg.wait_for_timeout(300)
        check('Weather Nation' not in await pg.evaluate(mine) and await pg.evaluate(lk) == 'Add to My Channels', 'tapping Remove takes it back out')
        await pg.evaluate("document.getElementById('npBackBtn').click()"); await pg.wait_for_timeout(700)

        await tab(pg, 'Link')
        await pg.evaluate("(()=>{var i=document.querySelector('.ch-tools input');i.value='https://list.example/list.m3u';i.dispatchEvent(new KeyboardEvent('keydown',{key:'Enter'}));})()"); await pg.wait_for_timeout(1200)
        r = await rows(pg)
        viaNative = await pg.evaluate("window.__calls.some(function(c){return c[0]==='fetchText' && /list/.test(c[1]);})")
        check([x['name'] for x in r] == ['Link One', 'Link Three'] and viaNative, f'playlist link read through the app (the host blocks pages); header-only channel left out {r}')
        await pg.evaluate("Array.prototype.find.call(document.querySelectorAll('#stationsGrid button'),function(b){return /^Add all/.test(b.textContent);}).click()"); await pg.wait_for_timeout(300)
        check(all(x['added'] for x in await rows(pg)), 'Add all adds them')
        await pg.screenshot(path=f'{SHOTS}/ch-link.png')
        check(not await pg.evaluate("!!document.querySelector('.ch-tools-note')"), 'no instructions under the tabs (Link)')
        await pg.evaluate("(()=>{var i=document.querySelector('.ch-tools input');i.value='https://tv.example/live/news24/index.m3u8';i.dispatchEvent(new KeyboardEvent('keydown',{key:'Enter'}));})()"); await pg.wait_for_timeout(900)
        r = await rows(pg)
        check(len(r) == 1 and r[0]['name'] == 'news24', f'a single stream link becomes one channel named from its address {r}')

        await pg.evaluate("document.getElementById('detailBackBtn').click()"); await pg.wait_for_timeout(700)
        t = await my_tiles(pg)
        labels = await pg.evaluate("Array.prototype.map.call(document.querySelectorAll('#stationsGrid .grid-section-label'),function(l){return l.textContent;})")
        rows_ok = await pg.evaluate("document.querySelectorAll('#stationsGrid > .cl-row').length===0 && document.querySelectorAll('#stationsGrid > .tile.tile-row.ch-item').length")
        check(labels == ['News2', 'Other3'] and rows_ok == 5, f'back to Video: stacked rows under a heading per category, uncategorised last {labels} rows={rows_ok}')
        check([x['name'] for x in t] == ['ABC News Live', 'BBC News', 'PBS', 'Link One', 'Link Three'], f'each row keeps the order added {[x["name"] for x in t]}')
        await pg.evaluate("Array.prototype.find.call(document.querySelectorAll('#stationsGrid .tile'),function(x){return x.querySelector('.tile-name').textContent==='BBC News';}).click()"); await pg.wait_for_timeout(900)
        await pg.evaluate("document.getElementById('npBackBtn').click()"); await pg.wait_for_timeout(700)
        t = {x['name']: x for x in await my_tiles(pg)}
        check(t['BBC News']['dead'] and not t['PBS']['dead'], 'a channel that fails is marked Not working')
        await pg.evaluate("Array.prototype.find.call(document.querySelectorAll('#stationsGrid .tile'),function(x){return x.querySelector('.tile-name').textContent==='PBS';}).click()"); await pg.wait_for_timeout(900)
        np = await pg.evaluate("document.getElementById('nowPlayingScreen').style.display")
        check(np == 'flex', 'tapping a channel tile plays it and opens Now Playing')
        lk2 = await pg.evaluate("(()=>{var l=document.getElementById('npChannelLink');return l.style.display==='none'?null:l.textContent;})()")
        check(lk2 == 'Remove from My Channels', f'a saved channel offers Remove from My Channels ({lk2})')
        await pg.evaluate("document.getElementById('npBackBtn').click()"); await pg.wait_for_timeout(700)
        await pg.screenshot(path=f'{SHOTS}/ch-my.png')
        setsort = "(v)=>{var s=document.getElementById('channelSortSelect');s.value=v;s.dispatchEvent(new Event('change'));}"
        lbls = "Array.prototype.map.call(document.querySelectorAll('#stationsGrid .grid-section-label'),function(l){return l.textContent;})"
        await pg.evaluate(setsort, 'list'); await pg.wait_for_timeout(300)
        t = [x['name'] for x in await my_tiles(pg)]
        check(await pg.evaluate(lbls) == ['My Channels5'] and t == ['PBS', 'ABC News Live', 'BBC News', 'Link One', 'Link Three'], f'Sort by List: one list in your order {t}')
        await pg.screenshot(path=f'{SHOTS}/ch-my-list.png')
        await pg.reload(); await pg.wait_for_timeout(2500)
        await pg.evaluate("document.querySelector('.mobile-nav-btn[data-nav=video]').click()"); await pg.wait_for_timeout(600)
        check(await pg.evaluate(lbls) == ['My Channels5'], 'the sort choice is kept')
        await pg.evaluate(setsort, 'category'); await pg.wait_for_timeout(300)
        check(await pg.evaluate(lbls) == ['News2', 'Other3'], 'Sort by Category brings the headings back')

        await pg.evaluate("document.getElementById('videoReorderHeaderBtn').click()"); await pg.wait_for_timeout(300)
        drag = await pg.evaluate("document.querySelectorAll('#stationsGrid .tile.tile-draggable').length")
        check(drag == 5, f'Reorder makes the tiles draggable ({drag})')
        stacked = await pg.evaluate("document.querySelectorAll('#stationsGrid > .tile.tile-row.tile-draggable').length")
        check(stacked == 5, f'Reorder uses the same stacked rows ({stacked})')
        await pg.screenshot(path=f'{SHOTS}/ch-reorder.png')
        await pg.evaluate("document.getElementById('videoReorderHeaderBtn').click()"); await pg.wait_for_timeout(300)
        # Remove via the More menu
        await pg.evaluate("Array.prototype.find.call(document.querySelectorAll('#stationsGrid .tile'),function(x){return x.querySelector('.tile-name').textContent==='Link Three';}).querySelector('.row-more-btn').click()"); await pg.wait_for_timeout(300)
        await pg.evaluate("document.getElementById('rowMenuRemove').click()"); await pg.wait_for_timeout(300)
        check('Link Three' not in [x['name'] for x in await my_tiles(pg)], 'More > Remove takes a channel out')
        await pg.reload(); await pg.wait_for_timeout(2500)
        await pg.evaluate("document.querySelector('.mobile-nav-btn[data-nav=video]').click()"); await pg.wait_for_timeout(600)
        check(len(await my_tiles(pg)) == 4, 'My Channels kept after a restart')
        check(not errs, f'no page errors {errs[:3]}')
        await b.close()
    print('ALL PASSED' if not fails else f'FAILED {fails}')
asyncio.run(main())
