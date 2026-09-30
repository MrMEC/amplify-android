"""Now Playing keeps the bottom navigation for every kind of item (a radio station here), rising
from behind it; the channel list has no count; picture-in-picture: the page tells the app when
leaving should float the video, and fills the window with the picture while it floats.
Run: python3 tests/test_np_nav_pip.py (screenshots in /tmp/claude-0/t/shots)"""
import asyncio, os
HERE = os.path.dirname(os.path.abspath(__file__))
src = open(os.path.join(HERE, 'test_video_channels.py')).read()
head = src[:src.index('async def rows(pg)')]
head = head.replace("'/tmp/claude-0/t/srv-ch'", "'/tmp/claude-0/t/srv-pip'").replace('8777', '8779')
exec(head)
from playwright.async_api import async_playwright

RECENT = [{'name': 'Jazz FM', 'url': 'https://jazz.example/s', 'url_resolved': 'https://jazz.example/s', 'urlToResolve': 'https://jazz.example/s', 'favicon': '', 'tags': 'jazz', 'country': 'US', 'stationuuid': 'j1', 'codec': 'MP3', 'bitrate': 128}]
CH = [{'id': 'iptv:ABCNews.us', 'name': 'ABC News Live', 'url': 'https://abc.example/live1080.m3u8', 'logo': '', 'country': 'US', 'cats': ['news'], 'catNames': ['News'], 'src': 'iptv', 'addedAt': 1},
      {'id': 'freetv:pbs', 'name': 'PBS', 'url': 'https://pbs.example/live.m3u8', 'logo': '', 'country': 'USA', 'cats': [], 'catNames': [], 'src': 'freetv', 'addedAt': 2}]
REC = """
(function(){ var P=window.Capacitor.Plugins.AmplifyPlayer; window.__pip=[];
  window.Capacitor.Plugins.AmplifyPlayer=new Proxy({}, {get:function(t,k){
    if(k==='setPip') return function(a){ window.__pip.push(a); return Promise.resolve({}); };
    return P[k]; }});
})();
"""
NAVSTATE = """(()=>{var nav=document.getElementById('mobileNav'), scr=document.getElementById('nowPlayingScreen');
  var nr=nav.getBoundingClientRect(), sr=scr.getBoundingClientRect();
  var hit=document.elementFromPoint(nr.left+nr.width/2, nr.top+nr.height/2);
  return {sheet:document.body.classList.contains('np-sheet'), open:document.body.classList.contains('np-open'),
    navShown:getComputedStyle(nav).display!=='none' && !!hit && nav.contains(hit), top:Math.round(sr.top), bottom:Math.round(sr.bottom), navTop:Math.round(nr.top)};})()"""

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
        ctx = await b.new_context(viewport={'width': 390, 'height': 844}, device_scale_factor=2, is_mobile=True, has_touch=True, color_scheme='dark', locale='en-US')
        await ctx.add_init_script(MOCK)
        await ctx.add_init_script(REC)
        await ctx.add_init_script("localStorage.setItem('radioPlayerRecent', %s); localStorage.setItem('radioPlayerVideoChannels', %s)" % (repr(json.dumps(RECENT)), repr(json.dumps(CH))))
        pg = await ctx.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e) + ' @ ' + (e.stack or '')[:400]))
        await pg.route('**/*', route)
        await pg.goto('http://127.0.0.1:8779/index.html'); await pg.wait_for_timeout(2500)

        # a radio station from Continue Listening, then Now Playing from the mini player
        await pg.evaluate("document.querySelector('#recentSection .tile[data-key]').click()"); await pg.wait_for_timeout(900)
        await pg.evaluate("document.getElementById('playerNowTrigger').click()")
        frames = []
        for i in range(6):
            await pg.wait_for_timeout(45)
            frames.append(await pg.evaluate(NAVSTATE))
        await pg.wait_for_timeout(700)
        end = await pg.evaluate(NAVSTATE)
        check(all(f['navShown'] for f in frames) and any(f['sheet'] and f['top'] > 0 for f in frames) and all(f['top'] <= f['navTop'] for f in frames),
              f'station Now Playing rises from behind the tab bar {frames}')
        check(end['open'] and end['navShown'] and abs(end['bottom'] - end['navTop']) <= 1, f'station Now Playing shows the tab bar under it {end}')
        chan = await pg.evaluate("document.getElementById('nowPlayingScreen').classList.contains('np-channel')")
        check(not chan, 'a station keeps the normal layout')
        bar = await pg.evaluate("""(()=>{var b=document.getElementById('playerBar'), nav=document.getElementById('mobileNav');
          var r=b.getBoundingClientRect(), hit=document.elementFromPoint(r.left+r.width/2, r.top+r.height/2);
          return {shown:getComputedStyle(b).display!=='none' && !!hit && b.contains(hit), bottom:Math.round(r.bottom), navTop:Math.round(nav.getBoundingClientRect().top)};})()""")
        check(bar['shown'] and bar['bottom'] <= bar['navTop'], f'the mini player shows above the tab bar on a station Now Playing {bar}')
        await pg.screenshot(path=f'{SHOTS}/np-station-nav.png')
        await pg.evaluate("document.querySelector('.mobile-nav-btn[data-nav=search]').click()"); await pg.wait_for_timeout(500)
        st = await pg.evaluate("""(()=>{var s=document.getElementById('searchSheet'), r=s.getBoundingClientRect(), hit=document.elementFromPoint(r.left+r.width/2, r.top+r.height/2);
          return [document.body.classList.contains('np-open'), document.getElementById('nowPlayingScreen').style.display, s.classList.contains('open') && !!hit && s.contains(hit)];})()""")
        check(st[0] and st[1] == 'flex' and st[2], f'Search opens its box over Now Playing without closing it {st}')
        await pg.screenshot(path=f'{SHOTS}/np-station-search.png')
        await pg.evaluate("document.getElementById('searchSheetClose').click()"); await pg.wait_for_timeout(500)
        st = await pg.evaluate("[document.getElementById('nowPlayingScreen').style.display, getComputedStyle(document.getElementById('playerBar')).display, document.body.classList.contains('search-open')]")
        check(st[0] == 'flex' and st[1] != 'none' and not st[2], f'closing the search box leaves Now Playing with its mini player {st}')
        await pg.evaluate("document.getElementById('npBackBtn').click()"); await pg.wait_for_timeout(700)
        closed = await pg.evaluate("document.getElementById('nowPlayingScreen').style.display")
        check(closed == 'none', f'station Now Playing still closes ({closed})')

        # a channel with video
        await pg.evaluate("document.querySelector('.mobile-nav-btn[data-nav=video]').click()"); await pg.wait_for_timeout(600)
        await pg.evaluate("document.querySelector('#stationsGrid .tile.ch-item').click()"); await pg.wait_for_timeout(900)
        cur = await pg.evaluate("window.__cur")
        await pg.evaluate("(id)=>window.__emit('video',{id:id,hasVideo:true,width:1280,height:720})", cur); await pg.wait_for_timeout(1500)
        hid = await pg.evaluate("getComputedStyle(document.getElementById('playerBar')).display")
        check(hid == 'none', f'a channel Now Playing has no mini player ({hid})')
        await pg.evaluate("document.querySelector('.mobile-nav-btn[data-nav=search]').click()"); await pg.wait_for_timeout(500)
        st = await pg.evaluate("[document.getElementById('nowPlayingScreen').style.display, document.getElementById('searchSheet').classList.contains('open'), getComputedStyle(document.getElementById('playerBar')).display]")
        check(st[0] == 'flex' and st[1] and st[2] == 'none', f'on a channel, Search shows only the search box {st}')
        await pg.screenshot(path=f'{SHOTS}/np-channel-search.png')
        await pg.evaluate("document.getElementById('searchSheetClose').click()"); await pg.wait_for_timeout(500)
        st = await pg.evaluate("[document.getElementById('nowPlayingScreen').style.display, getComputedStyle(document.getElementById('playerBar')).display]")
        check(st[0] == 'flex' and st[1] == 'none', f'closing it there leaves no mini player {st}')
        await pg.evaluate("document.querySelector('.mobile-nav-btn[data-nav=search]').click()"); await pg.wait_for_timeout(500)
        st = await pg.evaluate("[document.getElementById('nowPlayingScreen').style.display, document.getElementById('searchSheet').classList.contains('open')]")
        check(st[0] == 'flex' and st[1], f'on a channel too, Search only opens the box {st}')
        await pg.screenshot(path=f'{SHOTS}/np-channel-search.png')
        await pg.evaluate("document.getElementById('searchSheetClose').click()"); await pg.wait_for_timeout(400)
        heading = await pg.evaluate("document.getElementById('npCollectionHeading').textContent")
        check(heading == 'My Channels', f'no count over the channel list ({heading!r})')
        last = await pg.evaluate("window.__pip.slice(-1)[0]")
        check(last and last.get('allowed') and last.get('width') == 1280 and last.get('height') == 720, f'the app is told leaving should float the video (16:9) {last}')
        await pg.evaluate("window.__emit('pip',{active:true})"); await pg.wait_for_timeout(400)
        st = await pg.evaluate("[document.body.classList.contains('in-pip'), document.body.classList.contains('np-video-full')]")
        check(st[0] and st[1], f'in the floating window the picture fills it {st}')
        await pg.evaluate("window.__emit('pip',{active:false})"); await pg.wait_for_timeout(400)
        st = await pg.evaluate("[document.body.classList.contains('in-pip'), document.body.classList.contains('np-video-full'), document.getElementById('nowPlayingScreen').style.display]")
        check(not st[0] and not st[1] and st[2] == 'flex', f'back in the app: as it was (Now Playing, not full screen) {st}')
        # leaving from another page while the channel plays: Now Playing opens for the window, closes after
        await pg.evaluate("document.getElementById('npBackBtn').click()"); await pg.wait_for_timeout(700)
        vis = await pg.evaluate("getComputedStyle(document.getElementById('playerBar')).display")
        check(vis != 'none', f'back on the Video page the mini player shows ({vis})')
        await pg.evaluate("window.__emit('pip',{active:true})"); await pg.wait_for_timeout(500)
        st = await pg.evaluate("[document.getElementById('nowPlayingScreen').style.display, document.body.classList.contains('np-video-full')]")
        check(st[0] == 'flex' and st[1], f'leaving from another page still floats the picture {st}')
        await pg.screenshot(path=f'{SHOTS}/np-pip.png')
        await pg.evaluate("window.__emit('pip',{active:false})"); await pg.wait_for_timeout(500)
        st = await pg.evaluate("[document.getElementById('nowPlayingScreen').style.display, document.body.classList.contains('np-video-full')]")
        check(st[0] == 'none' and not st[1], f'and returns to that page afterwards {st}')
        # paused: nothing to float
        await pg.evaluate("(id)=>window.__emit('state',{id:id,state:'ready',isPlaying:false,playWhenReady:false,position:0,duration:-1,live:true,external:true})", cur); await pg.wait_for_timeout(1500)
        last = await pg.evaluate("window.__pip.slice(-1)[0]")
        check(last and last.get('allowed') is False, f'paused: leaving does not float anything {last}')
        check(not errs, f'no page errors {errs[:3]}')
        await b.close()
    print('ALL PASSED' if not fails else f'FAILED {fails}')
asyncio.run(main())
