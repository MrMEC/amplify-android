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
        check(back == 'Watch' and [x['name'] for x in r] == ['PBS'], f'Recommended (Free-TV) opens on your country (USA), back says Video {back} {r}')
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
        labels = await pg.evaluate("Array.prototype.map.call(document.querySelectorAll('#stationsGrid .grid-section-label'),function(l){return l.textContent;}).filter(function(x){return !/^Continue Watching/.test(x);})")
        rows_ok = await pg.evaluate("document.querySelectorAll('#stationsGrid > .cl-row:not(.vw-row)').length===0 && document.querySelectorAll('#stationsGrid > .tile.tile-row.ch-item').length")
        check(labels == ['News', 'Other'] and rows_ok == 5, f'back to Video: stacked rows under a heading per category, uncategorised last {labels} rows={rows_ok}')
        check([x['name'] for x in t] == ['ABC News Live', 'BBC News', 'Link One', 'Link Three', 'PBS'], f'A to Z by default, within each category {[x["name"] for x in t]}')
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
        lbls = "Array.prototype.map.call(document.querySelectorAll('#stationsGrid .grid-section-label'),function(l){return l.textContent;}).filter(function(x){return !/^Continue Watching/.test(x);})"
        EDIT = "document.getElementById('videoReorderHeaderBtn').click()"
        opts = "Array.prototype.map.call(document.querySelectorAll('.ch-sort-opts .home-tab'),function(b){return b.textContent+(b.classList.contains('active')?'*':'');})"
        pick = "(v)=>document.querySelector('.ch-sort-opts [data-opt='+v+']').click()"
        names = "Array.prototype.map.call(document.querySelectorAll('#stationsGrid .tile[data-entity=video-channel] .tile-name'),function(n){return n.textContent;})"
        hdr = await pg.evaluate("(()=>{var s=document.getElementById('videoSortHeaderBtn'), r=document.getElementById('videoReorderHeaderBtn');return [getComputedStyle(s).display, r.textContent.trim(), !!document.querySelector('.ch-sort-opts')];})()")
        check(hdr == ['none', 'Edit', False], f'no sort options outside edit mode; the edit button reads Edit {hdr}')
        home = await pg.evaluate("Array.prototype.map.call(document.querySelectorAll('#channelsHomeGrid .tile-name'),function(n){return n.textContent;})")
        check(home == ['ABC News Live', 'BBC News', 'Link One', 'Link Three', 'PBS'], f'the Home row of My Channels is A to Z too {home}')

        await pg.evaluate(EDIT); await pg.wait_for_timeout(300)
        check(await pg.evaluate(opts) == ['A to Z*', 'Manual', 'By Category*', 'One List'], f'editing shows the sort options, A to Z and By Category ticked {await pg.evaluate(opts)}')
        drag = await pg.evaluate("document.querySelectorAll('#stationsGrid .tile.tile-draggable').length")
        check(drag == 0 and await pg.evaluate(names) == ['ABC News Live', 'BBC News', 'Link One', 'Link Three', 'PBS'], f'in A to Z the list is sorted and nothing drags ({drag})')
        await pg.screenshot(path=f'{SHOTS}/ch-edit-az.png')
        await pg.evaluate(pick, 'manual'); await pg.wait_for_timeout(300)
        drag = await pg.evaluate("document.querySelectorAll('#stationsGrid > .tile.tile-row.tile-draggable').length")
        grips = await pg.evaluate("document.querySelectorAll('#stationsGrid .ch-grip').length")
        check(drag == 5 and grips == 5, f'Manual makes the stacked rows draggable, with grips ({drag}, {grips})')
        check(await pg.evaluate(names) == ['PBS', 'ABC News Live', 'BBC News', 'Link One', 'Link Three'], f'Manual starts from the order kept by hand (here, the order added) {await pg.evaluate(names)}')
        await pg.screenshot(path=f'{SHOTS}/ch-edit-manual.png')
        # Drag Link Three to the top (moving the row is what a drag does), then One List, then Done.
        await pg.evaluate("(()=>{var g=document.getElementById('stationsGrid'); var t=Array.prototype.find.call(g.querySelectorAll('.tile[data-entity=video-channel]'),function(x){return x.querySelector('.tile-name').textContent==='Link Three';}); var first=g.querySelector('.tile[data-entity=video-channel]'); g.insertBefore(t, first);})()")
        await pg.evaluate(pick, 'list'); await pg.wait_for_timeout(300)
        await pg.evaluate(EDIT); await pg.wait_for_timeout(300)
        t = [x['name'] for x in await my_tiles(pg)]
        check(await pg.evaluate(lbls) == ['My Channels'] and t == ['Link Three', 'PBS', 'ABC News Live', 'BBC News', 'Link One'], f'Manual + One List: your dragged order {t}')
        check(not await pg.evaluate("!!document.querySelector('.ch-sort-opts')"), 'Done hides the sort options')
        await pg.reload(); await pg.wait_for_timeout(2500)
        await pg.evaluate("document.querySelector('.mobile-nav-btn[data-nav=video]').click()"); await pg.wait_for_timeout(600)
        t = [x['name'] for x in await my_tiles(pg)]
        check(await pg.evaluate(lbls) == ['My Channels'] and t[0] == 'Link Three', f'choices and manual order kept after a restart {t}')
        # Back to A to Z: sorted again; the manual order is still there for next time.
        await pg.evaluate(EDIT); await pg.wait_for_timeout(300)
        await pg.evaluate(pick, 'az'); await pg.wait_for_timeout(300)
        await pg.evaluate(pick, 'category'); await pg.wait_for_timeout(300)
        await pg.evaluate(EDIT); await pg.wait_for_timeout(300)
        t = [x['name'] for x in await my_tiles(pg)]
        check(await pg.evaluate(lbls) == ['News', 'Other'] and t == ['ABC News Live', 'BBC News', 'Link One', 'Link Three', 'PBS'], f'A to Z again, by category {t}')
        await pg.evaluate(EDIT); await pg.wait_for_timeout(300)
        await pg.evaluate(pick, 'manual'); await pg.wait_for_timeout(300)
        check((await pg.evaluate(names))[0] == 'Link Three', f'switching back to Manual finds the hand order intact {await pg.evaluate(names)}')
        await pg.evaluate(pick, 'az'); await pg.wait_for_timeout(300)
        await pg.evaluate(EDIT); await pg.wait_for_timeout(300)
        # Rename via the More menu: the row re-sorts under its new name (A to Z), the Home row
        # follows, and it's kept after a restart. Cancel leaves it alone.
        def more(name):
            return "Array.prototype.find.call(document.querySelectorAll('#stationsGrid .tile'),function(x){return x.querySelector('.tile-name').textContent===" + json.dumps(name) + ";}).querySelector('.row-more-btn').click()"
        await pg.evaluate(more('PBS')); await pg.wait_for_timeout(300)
        shown = await pg.evaluate("getComputedStyle(document.getElementById('rowMenuRename')).display")
        check(shown != 'none', f"a saved channel's More menu has Rename ({shown})")
        await pg.screenshot(path=f'{SHOTS}/ch-rename-menu.png')
        asked = []
        async def answer(d):
            asked.append((d.message, d.default_value)); await d.accept('Aardvark TV')
        pg.once('dialog', lambda d: asyncio.ensure_future(answer(d)))
        await pg.evaluate("document.getElementById('rowMenuRename').click()"); await pg.wait_for_timeout(500)
        t = [x['name'] for x in await my_tiles(pg)]
        check(asked == [('Channel name', 'PBS')] and t == ['ABC News Live', 'BBC News', 'Aardvark TV', 'Link One', 'Link Three'],
              f'Rename asks with the current name and the list re-sorts under the new one {asked} {t}')
        home = await pg.evaluate("Array.prototype.map.call(document.querySelectorAll('#channelsHomeGrid .tile-name'),function(n){return n.textContent;})")
        check(home[0] == 'Aardvark TV', f'the Home row uses the new name, in order {home}')
        await pg.evaluate(more('Link One')); await pg.wait_for_timeout(300)
        pg.once('dialog', lambda d: asyncio.ensure_future(d.dismiss()))
        await pg.evaluate("document.getElementById('rowMenuRename').click()"); await pg.wait_for_timeout(500)
        check('Link One' in [x['name'] for x in await my_tiles(pg)], 'cancelling Rename changes nothing')
        await pg.reload(); await pg.wait_for_timeout(2500)
        await pg.evaluate("document.querySelector('.mobile-nav-btn[data-nav=video]').click()"); await pg.wait_for_timeout(600)
        t = [x['name'] for x in await my_tiles(pg)]
        check('Aardvark TV' in t and 'PBS' not in t, f'the new name is kept after a restart {t}')
        await pg.screenshot(path=f'{SHOTS}/ch-renamed.png')
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
