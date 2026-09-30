"""Continue Watching: part-watched movies and watched channels (not in Continue Listening), a
three-dot menu to remove an item, shown on the Video page and on Home under Continue Listening;
My Channels as a row on Home under For You.
Run: python3 tests/test_continue_watching.py (screenshots in /tmp/claude-0/t/shots)"""
import asyncio, os, json
HERE = os.path.dirname(os.path.abspath(__file__))
src = open(os.path.join(HERE, 'test_video_library.py')).read()
head = src[:src.index('async def names(pg, sel)')]
head = head.replace('8780', '8783')
exec(head)
from playwright.async_api import async_playwright

CH = [{'id': 'iptv:ABCNews.us', 'name': 'ABC News Live', 'url': 'https://abc.example/live1080.m3u8', 'logo': '', 'country': 'US', 'cats': ['news'], 'catNames': ['News'], 'src': 'iptv', 'addedAt': 1},
      {'id': 'freetv:pbs', 'name': 'PBS', 'url': 'https://pbs.example/live.m3u8', 'logo': '', 'country': 'USA', 'cats': [], 'catNames': [], 'src': 'freetv', 'addedAt': 2}]
RECENT = [{'name': 'Jazz FM', 'url': 'https://jazz.example/s', 'url_resolved': 'https://jazz.example/s', 'urlToResolve': 'https://jazz.example/s', 'favicon': '', 'tags': 'jazz', 'country': 'US', 'stationuuid': 'j1'}]

async def tnames(pg, sel):
    return await pg.evaluate("(s)=>Array.prototype.map.call(document.querySelectorAll(s),function(t){return t.textContent;})", sel)
async def state(pg, extra):
    cur = await pg.evaluate("window.__cur")
    ev = {'id': cur, 'state': 'ready', 'isPlaying': True, 'playWhenReady': True, 'position': 0, 'duration': 8880, 'live': False}
    ev.update(extra)
    await pg.evaluate("(e)=>window.__emit('state', e)", ev)
async def home(pg):
    await pg.evaluate("document.querySelector('.mobile-nav-btn[data-nav=home]').click()"); await pg.wait_for_timeout(800)

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
        ctx = await b.new_context(viewport={'width': 390, 'height': 844}, device_scale_factor=2, is_mobile=True, has_touch=True, color_scheme='dark', locale='en-US')
        await ctx.add_init_script(MOCK)
        await ctx.add_init_script(EXT)
        await ctx.add_init_script("if(!localStorage.getItem('radioPlayerVideoChannels')){localStorage.setItem('radioPlayerVideoChannels', %s); localStorage.setItem('radioPlayerRecent', %s);}" % (repr(json.dumps(CH)), repr(json.dumps(RECENT))))
        pg = await ctx.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e) + ' @ ' + (e.stack or '')[:300]))
        await pg.route('**/*', route)
        await pg.goto('http://127.0.0.1:8783/index.html'); await pg.wait_for_timeout(2500)

        # Home: My Channels row under For You
        await home(pg)
        order = await pg.evaluate("""(()=>{var ids=['recentSection','continueWatchingHomeSection','forYouSection','channelsHomeSection'];
            return ids.map(function(i){var e=document.getElementById(i);return [i, getComputedStyle(e).display!=='none', Math.round(e.getBoundingClientRect().top)];});})()""")
        vis = {o[0]: o for o in order}
        chs = await tnames(pg, '#channelsHomeGrid .tile-name')
        check(vis['channelsHomeSection'][1] and chs == ['ABC News Live', 'PBS'] and vis['channelsHomeSection'][2] > vis['forYouSection'][2],
              f'Home: My Channels row under For You {chs} {order}')
        check(not vis['continueWatchingHomeSection'][1], 'Continue Watching stays hidden while there is nothing to continue')
        await pg.screenshot(path=f'{SHOTS}/cw-home-channels.png', full_page=True)
        # a movie, part watched
        await pg.evaluate("document.querySelector('.mobile-nav-btn[data-nav=video]').click()"); await pg.wait_for_timeout(500)
        await pg.evaluate("document.querySelector('.video-tabs [data-vtab=movies]').click()"); await pg.wait_for_timeout(300)
        await pg.evaluate("document.getElementById('videoAddHeaderBtn').click()"); await pg.wait_for_timeout(2000)
        await pg.evaluate("Array.prototype.find.call(document.querySelectorAll('#stationsGrid .tile.vposter'),function(t){return t.querySelector('.tile-name').textContent==='Inception';}).click()"); await pg.wait_for_timeout(500)
        await pg.evaluate("document.querySelector('.vd-play').click()"); await pg.wait_for_timeout(900)
        await state(pg, {'position': 3000, 'duration': 8880}); await pg.wait_for_timeout(300)
        await state(pg, {'position': 3000, 'duration': 8880, 'isPlaying': False, 'playWhenReady': False, 'external': True}); await pg.wait_for_timeout(400)
        await pg.evaluate("document.getElementById('npBackBtn').click()"); await pg.wait_for_timeout(500)
        # a channel, watched (from the Home row)
        await home(pg)
        await pg.evaluate("document.querySelector('#channelsHomeGrid .tile').click()"); await pg.wait_for_timeout(1000)
        await pg.evaluate("document.getElementById('npBackBtn').click()"); await pg.wait_for_timeout(600)
        await home(pg)
        cw = await tnames(pg, '#continueWatchingHomeGrid .vw-tile .tile-name')
        rec = await pg.evaluate("JSON.parse(localStorage.getItem('radioPlayerRecent')||'[]').map(function(r){return r.name;})")
        check(cw == ['ABC News Live', 'Inception'], f'Continue Watching: the channel just watched, then the part-watched movie {cw}')
        check('ABC News Live' not in rec, f'channels stay out of Continue Listening {rec}')
        order = await pg.evaluate("['recentSection','continueWatchingHomeSection','forYouSection'].map(function(i){var e=document.getElementById(i);return [getComputedStyle(e).display!=='none', Math.round(e.getBoundingClientRect().top)];})")
        check(order[1][0] and order[0][1] < order[1][1] < order[2][1], f'Home: Continue Watching under Continue Listening, above For You {order}')
        sz = await pg.evaluate("""(()=>{var r=function(s){var e=document.querySelector(s);if(!e)return null;var b=e.getBoundingClientRect();return [Math.round(b.width),Math.round(b.height)];};
          return {cl:r('#recentSection .tile .tile-art'), ch:r('#continueWatchingHomeGrid .vw-channel .vw-thumb'), mv:r('#continueWatchingHomeGrid .vw-tile:not(.vw-channel) .vw-thumb')};})()""")
        check(sz['ch'] and sz['cl'] and abs(sz['ch'][0] - sz['cl'][0]) <= 1 and abs(sz['ch'][1] - sz['cl'][1]) <= 1, f'a channel is the size of a Continue Listening cover {sz}')
        check(sz['mv'] and sz['mv'][0] > sz['ch'][0] + 60, f'movies keep the wide frame {sz}')
        await pg.evaluate("document.getElementById('recentSection').scrollIntoView()"); await pg.wait_for_timeout(300)
        await pg.screenshot(path=f'{SHOTS}/cw-home-sizes.png')
        await pg.evaluate("document.getElementById('continueWatchingHomeSection').scrollIntoView()"); await pg.wait_for_timeout(300)
        await pg.screenshot(path=f'{SHOTS}/cw-home.png')
        # remove the channel with its menu
        await pg.evaluate("document.querySelector('#continueWatchingHomeGrid .vw-tile .vw-more').click()"); await pg.wait_for_timeout(200)
        items = await tnames(pg, '.v-menu .np-menu-item')
        check(items == ['Remove from Continue Watching'], f'a channel tile menu offers Remove {items}')
        await pg.screenshot(path=f'{SHOTS}/cw-menu.png')
        await pg.evaluate("document.querySelector('.v-menu .np-menu-item').click()"); await pg.wait_for_timeout(400)
        cw = await tnames(pg, '#continueWatchingHomeGrid .vw-tile .tile-name')
        check(cw == ['Inception'], f'removed from the list {cw}')
        # the movie menu
        await pg.evaluate("document.querySelector('#continueWatchingHomeGrid .vw-tile .vw-more').click()"); await pg.wait_for_timeout(200)
        items = await tnames(pg, '.v-menu .np-menu-item')
        check(items == ['Mark Watched', 'Remove from Continue Watching'], f'a movie tile menu {items}')
        await pg.evaluate("Array.prototype.find.call(document.querySelectorAll('.v-menu .np-menu-item'),function(b){return b.textContent==='Remove from Continue Watching';}).click()"); await pg.wait_for_timeout(400)
        vis = await pg.evaluate("getComputedStyle(document.getElementById('continueWatchingHomeSection')).display")
        check(vis == 'none', f'an empty Continue Watching hides ({vis})')
        # the Video page agrees; watching the channel again brings it back
        await pg.evaluate("document.querySelector('.mobile-nav-btn[data-nav=video]').click()"); await pg.wait_for_timeout(500)
        cwv = await tnames(pg, '#stationsGrid .vw-tile .tile-name')
        check(cwv == [], f'the Video page list matches {cwv}')
        await home(pg)
        await pg.evaluate("document.querySelector('#channelsHomeGrid .tile').click()"); await pg.wait_for_timeout(1000)
        await pg.evaluate("document.getElementById('npBackBtn').click()"); await pg.wait_for_timeout(600)
        await home(pg)
        cw = await tnames(pg, '#continueWatchingHomeGrid .vw-tile .tile-name')
        check(cw == ['ABC News Live'], f'watching it again puts it back {cw}')
        await pg.evaluate("document.querySelector('.mobile-nav-btn[data-nav=video]').click()"); await pg.wait_for_timeout(500)
        await pg.screenshot(path=f'{SHOTS}/cw-video.png')
        check(not errs, f'no page errors {errs[:3]}')
        await b.close()
    print('ALL PASSED' if not fails else f'FAILED {fails}')
asyncio.run(main())
