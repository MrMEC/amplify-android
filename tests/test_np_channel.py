"""Now Playing for a TV channel: video box on top, one-line name right under it, controls
close below, and a channel list under the controls (My Channels for a saved channel, more
from its category for one that isn't). A radio station keeps the normal layout.
Run: python3 tests/test_np_channel.py (screenshots in /tmp/claude-0/t/shots)"""
import asyncio, os, re
HERE = os.path.dirname(os.path.abspath(__file__))
src = open(os.path.join(HERE, 'test_video_channels.py')).read()
head = src[:src.index('async def rows(pg)')]
head = head.replace("'/tmp/claude-0/t/srv-ch'", "'/tmp/claude-0/t/srv-npch'").replace('8777', '8778')
exec(head)
API['channels.json'].append({'id': 'CNN.us', 'name': 'CNN', 'country': 'US', 'categories': ['news'], 'is_nsfw': False})
API['streams.json'].append({'channel': 'CNN.us', 'url': 'https://cnn.example/live.m3u8'})
from playwright.async_api import async_playwright

SEED = [
 {'id': 'iptv:ABCNews.us', 'name': 'ABC News Live From The Newsroom With A Very Long Channel Name', 'url': 'https://abc.example/live1080.m3u8', 'logo': '', 'country': 'US', 'cats': ['news'], 'catNames': ['News'], 'src': 'iptv', 'addedAt': 1},
 {'id': 'freetv:pbs', 'name': 'PBS', 'url': 'https://pbs.example/live.m3u8', 'logo': '', 'country': 'USA', 'cats': [], 'catNames': [], 'src': 'freetv', 'addedAt': 2},
 {'id': 'link:x', 'name': 'Link One', 'url': 'http://one.example/1.m3u8', 'logo': '', 'country': '', 'cats': [], 'catNames': [], 'src': 'link', 'addedAt': 3},
]
SEED += [{'id': 'link:%d' % i, 'name': 'Channel %02d' % i, 'url': 'http://ch%d.example/l.m3u8' % i, 'logo': '', 'country': '', 'cats': [], 'catNames': [], 'src': 'link', 'addedAt': 10 + i} for i in range(15)]
async def geom(pg):
    return await pg.evaluate("""(()=>{
      var v=document.getElementById('npVideoWrap').getBoundingClientRect(), a=document.getElementById('npArtWrap').getBoundingClientRect(),
          n=document.getElementById('npName'), nr=n.getBoundingClientRect(), c=document.querySelector('.np-controls').getBoundingClientRect();
      var lh=parseFloat(getComputedStyle(n).lineHeight)||nr.height;
      return {artBottom:a.bottom, videoBottom:v.bottom, videoShown:!document.getElementById('npVideoWrap').hidden, nameTop:nr.top, nameH:nr.height, lh:lh, ctrlTop:c.top,
        channel:document.getElementById('nowPlayingScreen').classList.contains('np-channel'),
        heading:(document.getElementById('npCollection').style.display!=='none')?document.getElementById('npCollectionHeading').textContent:null,
        rows:Array.prototype.map.call(document.querySelectorAll('#npCollectionGrid .tile-row'),function(r){return r.querySelector('.tile-name').textContent;}),
        playing:Array.prototype.map.call(document.querySelectorAll('#npCollectionGrid .tile-row.playing'),function(r){return r.querySelector('.tile-name').textContent;}),
        related:getComputedStyle(document.getElementById('npRelated')).display};
    })()""")

async def run(p, w, h, tag):
    b = await p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
    mobile = w < 900
    ctx = await b.new_context(viewport={'width': w, 'height': h}, device_scale_factor=2, is_mobile=mobile, has_touch=mobile, color_scheme='dark', locale='en-US')
    await ctx.add_init_script(MOCK)
    await ctx.add_init_script("localStorage.setItem('radioPlayerVideoChannels', %s)" % repr(json.dumps(SEED)))
    pg = await ctx.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
    await pg.route('**/*', route)
    await pg.goto('http://127.0.0.1:8778/index.html'); await pg.wait_for_timeout(2500)
    await pg.evaluate("document.querySelector('.mobile-nav-btn[data-nav=video]') ? document.querySelector('.mobile-nav-btn[data-nav=video]').click() : document.querySelector('[data-nav=video]').click()"); await pg.wait_for_timeout(600)
    # a saved channel
    await pg.evaluate("document.querySelector('#stationsGrid .tile.ch-item').click()")
    if mobile:
        # Mid-slide: the tab bar stays on top and the screen rises from behind it.
        frames = []
        for i in range(6):
            await pg.wait_for_timeout(45)
            frames.append(await pg.evaluate("""(()=>{var nav=document.getElementById('mobileNav'), scr=document.getElementById('nowPlayingScreen');
              var nr=nav.getBoundingClientRect(), sr=scr.getBoundingClientRect();
              var hit=document.elementFromPoint(nr.left+nr.width/2, nr.top+nr.height/2);
              return {sheet:document.body.classList.contains('np-sheet'), navShown:getComputedStyle(nav).display!=='none' && !!hit && nav.contains(hit),
                top:Math.round(sr.top), bottom:Math.round(sr.bottom), navTop:Math.round(nr.top)};})()"""))
            if i == 2: await pg.screenshot(path=f'{SHOTS}/npch-{tag}-sliding.png')
        mid = [f for f in frames if f['sheet']]
        check(mid and all(f['navShown'] for f in frames) and all(f['top'] <= f['navTop'] for f in frames) and frames[-1]['bottom'] <= frames[-1]['navTop'] + 1 and any(f['top'] > 0 for f in mid),
              f'{tag}: while sliding up the tab bar stays visible and the screen rises from behind it {frames}')
    await pg.wait_for_timeout(900)
    cur = await pg.evaluate("window.__cur")
    await pg.evaluate("(id)=>window.__emit('video',{id:id,hasVideo:true,width:1280,height:720})", cur); await pg.wait_for_timeout(900)
    if await pg.evaluate("document.body.classList.contains('np-video-full')"):
        await pg.evaluate("window.__emit('videotap',{})"); await pg.wait_for_timeout(600)
    g = await geom(pg)
    check(g['channel'], f'{tag}: a channel gets the channel layout')
    check(g['videoShown'] and 0 <= g['nameTop'] - g['videoBottom'] <= 30, f'{tag}: the name sits right under the video ({g["nameTop"] - g["videoBottom"]:.0f}px)')
    check(g['nameH'] <= g['lh'] * 1.3, f'{tag}: the name is one line ({g["nameH"]:.0f} / {g["lh"]:.0f})')
    check(g['ctrlTop'] - g['nameTop'] < 80, f'{tag}: controls close under the name ({g["ctrlTop"] - g["nameTop"]:.0f}px)')
    check(g['heading'] and g['heading'].startswith('My Channels') and len(g['rows']) == 18 and len(g['playing']) == 1 and g['related'] == 'none',
          f'{tag}: saved channel lists My Channels, current one highlighted, no Related Stations {g["heading"]} {g["rows"]} {g["playing"]}')
    await pg.screenshot(path=f'{SHOTS}/npch-{tag}-saved.png')
    if mobile:
        sc = await pg.evaluate("""(()=>{
          var nav=document.getElementById('mobileNav'), scr=document.getElementById('nowPlayingScreen'), grid=document.getElementById('npCollectionGrid');
          var v0=document.getElementById('npVideoWrap').getBoundingClientRect().top, c0=document.querySelector('.np-controls').getBoundingClientRect().top;
          grid.scrollTop=400; scr.scrollTop=400;
          var v1=document.getElementById('npVideoWrap').getBoundingClientRect().top, c1=document.querySelector('.np-controls').getBoundingClientRect().top;
          var r={nav:getComputedStyle(nav).display, navTop:nav.getBoundingClientRect().top, scrBottom:scr.getBoundingClientRect().bottom,
            gridScrolled:grid.scrollTop, gridBottom:grid.getBoundingClientRect().bottom, fixed:v0===v1 && c0===c1};
          return r;})()""")
        check(sc['nav'] == 'flex' and abs(sc['navTop'] - sc['scrBottom']) < 2, f'{tag}: bottom navigation shows under Now Playing {sc}')
        check(sc['gridScrolled'] > 0 and sc['fixed'] and sc['gridBottom'] <= sc['navTop'] + 1, f'{tag}: only the channel list scrolls; header, video and controls stay put')
        await pg.screenshot(path=f'{SHOTS}/npch-{tag}-scrolled.png')
        await pg.evaluate("document.getElementById('npCollectionGrid').scrollTop=0")
    await pg.evaluate("document.getElementById('npMenuBtn').click()"); await pg.wait_for_timeout(300)
    vm = await pg.evaluate("(()=>{var b=document.getElementById('npVideoMenuBtn');return b.style.display==='none'?null:b.textContent;})()")
    pill = await pg.evaluate("getComputedStyle(document.getElementById('npVideoToggle')).display")
    check(vm == 'Turn Off Video' and pill == 'none', f'{tag}: video on/off is in the More menu, not a pill ({vm}, pill {pill})')
    await pg.screenshot(path=f'{SHOTS}/npch-{tag}-menu.png')
    await pg.evaluate("document.getElementById('npVideoMenuBtn').click()"); await pg.wait_for_timeout(500)
    off = await pg.evaluate("document.getElementById('npVideoWrap').hidden")
    vm = await pg.evaluate("document.getElementById('npVideoMenuBtn').textContent")
    check(off and vm == 'Turn On Video', f'{tag}: Turn Off Video turns it off ({vm})')
    await pg.screenshot(path=f'{SHOTS}/npch-{tag}-off.png')
    await pg.evaluate("document.getElementById('npVideoMenuBtn').click()"); await pg.wait_for_timeout(500)
    if await pg.evaluate("document.body.classList.contains('np-video-full')"):
        await pg.evaluate("window.__emit('videotap',{})"); await pg.wait_for_timeout(600)
    if mobile:
        box = await pg.evaluate("(()=>{var r=document.getElementById('npCollectionGrid').getBoundingClientRect();return [r.left+r.width/2, r.top+40];})()")
        await pg.evaluate("document.getElementById('npCollectionGrid').scrollTop=0")
        cdp = await ctx.new_cdp_session(pg)
        x, y = box
        await cdp.send('Input.dispatchTouchEvent', {'type': 'touchStart', 'touchPoints': [{'x': x, 'y': y}]})
        for k in range(1, 8):
            await cdp.send('Input.dispatchTouchEvent', {'type': 'touchMove', 'touchPoints': [{'x': x, 'y': y + k * 30}]})
            await pg.wait_for_timeout(16)
        await cdp.send('Input.dispatchTouchEvent', {'type': 'touchEnd', 'touchPoints': []})
        await pg.wait_for_timeout(600)
        st = await pg.evaluate("[document.body.classList.contains('np-open'), document.getElementById('nowPlayingScreen').style.transform, document.body.classList.contains('np-sheet')]")
        check(st[0] and not st[1] and not st[2], f'{tag}: pulling down on the channel list does not drag the screen away {st}')
    # tap another channel in the list
    await pg.evaluate("Array.prototype.find.call(document.querySelectorAll('#npCollectionGrid .tile-row'),function(r){return r.querySelector('.tile-name').textContent==='PBS';}).click()"); await pg.wait_for_timeout(900)
    g = await geom(pg)
    check(g['playing'] == ['PBS'], f'{tag}: tapping a channel in the list switches to it {g["playing"]}')
    # a channel not in My Channels (from All, category News)
    await pg.evaluate("document.getElementById('npBackBtn').click()"); await pg.wait_for_timeout(600)
    await pg.evaluate("document.getElementById('videoAddHeaderBtn').click()"); await pg.wait_for_timeout(900)
    await pg.evaluate("Array.prototype.find.call(document.querySelectorAll('.ch-tools .home-tab'),function(b){return b.textContent==='All';}).click()"); await pg.wait_for_timeout(900)
    await pg.evaluate("(()=>{var s=document.querySelectorAll('.ch-tools select')[0];s.value='';s.dispatchEvent(new Event('change'));})()"); await pg.wait_for_timeout(600)
    await pg.evaluate("Array.prototype.find.call(document.querySelectorAll('.ch-row'),function(r){return r.querySelector('.ch-name').textContent==='BBC News';}).click()"); await pg.wait_for_timeout(1200)
    g = await geom(pg)
    check(g['channel'] and g['heading'] and g['heading'].startswith('More News') and 'BBC News' not in g['rows'] and 'ABC News Live' not in g['rows'],
          f'{tag}: unsaved channel lists more from its category (not itself, not ones already saved) {g["heading"]} {g["rows"]}')
    await pg.screenshot(path=f'{SHOTS}/npch-{tag}-unsaved.png')
    await pg.evaluate("document.getElementById('npChannelLink').click()"); await pg.wait_for_timeout(500)
    g = await geom(pg)
    check(g['heading'] and g['heading'].startswith('My Channels') and 'BBC News' in g['rows'], f'{tag}: adding it from the menu switches the list to My Channels {g["heading"]} {g["rows"]}')
    if mobile:
        await pg.evaluate("document.getElementById('npBackBtn').click()"); await pg.wait_for_timeout(40)
        st = await pg.evaluate("[document.body.classList.contains('np-sheet'), getComputedStyle(document.getElementById('nowPlayingScreen')).display]")
        check(not st[0] and st[1] == 'none', f'{tag}: the back button closes a channel at once, no slide down {st}')
        await pg.evaluate("(()=>{var r=Array.prototype.find.call(document.querySelectorAll('.ch-row'),function(r){return r.querySelector('.ch-name').textContent==='CNN';}); if(r) r.click();})()"); await pg.wait_for_timeout(900)
        await pg.evaluate("document.querySelector('.mobile-nav-btn[data-nav=home]').click()"); await pg.wait_for_timeout(700)
        st = await pg.evaluate("[document.body.classList.contains('np-open'), getComputedStyle(document.getElementById('nowPlayingScreen')).display]")
        check(not st[0] and st[1] == 'none', f'{tag}: tapping Home in the tab bar leaves Now Playing {st}')
    check(not errs, f'{tag}: no page errors {errs[:3]}')
    await b.close()

async def main():
    async with async_playwright() as p:
        await run(p, 390, 844, 'phone')
        await run(p, 1400, 900, 'desktop')
    print('ALL PASSED' if not fails else f'FAILED {fails}')
asyncio.run(main())
