"""Build 181: the video player's controls sit on the picture. Play/Pause in the middle, LIVE (or
the progress bar) and full screen along the bottom; a tap shows them, a tap on an empty spot
hides them, and they hide after 3 seconds of playing (not while paused). Under the picture
only the name and More remain (no skip buttons, no seek bar, no Next card, Favorite is in More),
so the channel list gets the height. The same state goes to the native player
(setVideoControls), whose buttons come back as 'videoctl' events.
Run: python3 tests/test_video_controls.py (screenshots in /tmp/claude-0/t/shots)"""
import asyncio, os
HERE = os.path.dirname(os.path.abspath(__file__))
src = open(os.path.join(HERE, 'test_video_channels.py')).read()
head = src[:src.index('async def rows(pg)')]
head = head.replace("'/tmp/claude-0/t/srv-ch'", "'/tmp/claude-0/t/srv-vctl'").replace('8777', '8815')
exec(head)
from playwright.async_api import async_playwright

SEED = [{'id': 'link:%d' % i, 'name': 'Channel %02d' % i, 'url': 'http://ch%d.example/l.m3u8' % i, 'logo': '', 'country': 'US', 'cats': [], 'catNames': [], 'src': 'link', 'addedAt': 10 + i} for i in range(12)]
# Records what the page tells the native player about its controls, and play/pause.
SPY = """
(function(){
  var P = window.Capacitor.Plugins.AmplifyPlayer;
  window.__ctl = [];
  window.Capacitor.Plugins.AmplifyPlayer = new Proxy({}, {get:function(t,k){
    if(k === 'setVideoControls') return function(m){ window.__ctl.push(m); return Promise.resolve({}); };
    if(k === 'pause' || k === 'play') return function(){ window.__calls.push([k]); return Promise.resolve({}); };
    return P[k];
  }});
})();
"""
STATE = """(()=>{ var s = document.getElementById('nowPlayingScreen'), v = document.getElementById('vctl');
  function shown(id){ var e = document.getElementById(id); return !!e && getComputedStyle(e).display !== 'none' && e.getClientRects().length > 0; }
  var box = v.getBoundingClientRect(), vw = document.getElementById('npVideoWrap').getBoundingClientRect();
  var grid = document.getElementById('npCollectionGrid').getBoundingClientRect();
  return { vplayer: s.classList.contains('np-vplayer'), inWrap: v.parentNode.id, show: v.classList.contains('show'),
    playing: v.classList.contains('playing'), live: v.classList.contains('live'), noFull: v.classList.contains('no-full'),
    playVis: getComputedStyle(document.getElementById('vctlPlay')).visibility,
    box: [Math.round(box.top), Math.round(box.height)], wrap: [Math.round(vw.top), Math.round(vw.height)],
    gone: ['npFavBtn','npPrevBtn','npNextBtn','npSkipBackBtn','npSkipFwdBtn','npPlayBtn','npSeek','npUpNext'].filter(shown),
    more: shown('npMenuBtn'), full: document.body.classList.contains('np-video-full'),
    gridH: Math.round(grid.height), gridTop: Math.round(grid.top), ctl: (window.__ctl || []).slice(-1)[0] || null }; })()"""

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
        ctx = await b.new_context(viewport={'width': 390, 'height': 844}, device_scale_factor=2, is_mobile=True, has_touch=True, color_scheme='dark', locale='en-US')
        await ctx.add_init_script(MOCK)
        await ctx.add_init_script(SPY)
        await ctx.add_init_script("localStorage.setItem('radioPlayerVideoChannels', %s)" % repr(json.dumps(SEED)))
        pg = await ctx.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.route('**/*', route)
        await pg.goto('http://127.0.0.1:8815/index.html'); await pg.wait_for_timeout(2500)
        await pg.evaluate("document.querySelector('.mobile-nav-btn[data-nav=video]').click()"); await pg.wait_for_timeout(600)
        await pg.evaluate("document.querySelector('#stationsGrid .tile.ch-item').click()"); await pg.wait_for_timeout(500)
        g = await pg.evaluate(STATE)
        check(g['vplayer'] and g['inWrap'] == 'npArtWrap' and g['show'] and g['noFull'], f'before the picture: controls over the logo, no full screen button {g}')
        await pg.screenshot(path=f'{SHOTS}/vctl-ch-logo.png')
        cur = await pg.evaluate("window.__cur")
        await pg.evaluate("(id)=>window.__emit('video',{id:id,hasVideo:true,width:1280,height:720})", cur); await pg.wait_for_timeout(500)
        if await pg.evaluate("document.body.classList.contains('np-video-full')"):
            await pg.evaluate("document.getElementById('npVideoFullBtn').click()"); await pg.wait_for_timeout(300)
        if not await pg.evaluate("document.getElementById('vctl').classList.contains('show')"):
            await pg.evaluate("document.getElementById('vctl').click()"); await pg.wait_for_timeout(300)
        g = await pg.evaluate(STATE)
        check(g['inWrap'] == 'npVideoWrap' and g['box'] == g['wrap'] and not g['noFull'], f'with the picture: the controls cover the video box {g["box"]} {g["wrap"]}')
        check(g['show'] and g['playing'] and g['live'] and g['playVis'] == 'visible', f'shown: Pause, LIVE {g}')
        check(g['gone'] == [] and g['more'], f'under the picture only More is left (no heart, skip, play, seek or Next) {g["gone"]}')
        c = g['ctl']
        check(c and c['enabled'] and c['live'] and c['playing'] and not c['full'], f'the native player is told to draw the controls {c}')
        await pg.screenshot(path=f'{SHOTS}/vctl-ch-shown.png')
        await pg.wait_for_timeout(3400)
        g = await pg.evaluate(STATE)
        check(not g['show'] and g['playVis'] == 'hidden', f'they hide after 3 seconds of playing {g["show"]} {g["playVis"]}')
        await pg.screenshot(path=f'{SHOTS}/vctl-ch-hidden.png')
        bx = await pg.evaluate("(()=>{var r=document.getElementById('vctl').getBoundingClientRect();return [r.left,r.top,r.width,r.height];})()")
        await pg.touchscreen.tap(bx[0] + bx[2] * .2, bx[1] + bx[3] * .3); await pg.wait_for_timeout(350)
        g = await pg.evaluate(STATE)
        check(g['show'], 'a tap on the picture shows them')
        await pg.touchscreen.tap(bx[0] + bx[2] * .2, bx[1] + bx[3] * .3); await pg.wait_for_timeout(350)
        g = await pg.evaluate(STATE)
        check(not g['show'], 'a tap on an empty spot hides them')
        await pg.touchscreen.tap(bx[0] + bx[2] * .2, bx[1] + bx[3] * .3); await pg.wait_for_timeout(350)
        n0 = await pg.evaluate("window.__calls.filter(function(c){return c[0]==='pause';}).length")
        await pg.touchscreen.tap(bx[0] + bx[2] / 2, bx[1] + bx[3] / 2); await pg.wait_for_timeout(300)
        await pg.evaluate("(id)=>window.__emit('state',{id:id,state:'ready',isPlaying:false,playWhenReady:false,position:0,duration:-1,live:true})", cur)
        await pg.wait_for_timeout(300)
        n1 = await pg.evaluate("window.__calls.filter(function(c){return c[0]==='pause';}).length")
        check(n1 > n0, f'the middle button pauses ({n0} -> {n1})')
        await pg.wait_for_timeout(3400)
        g = await pg.evaluate(STATE)
        check(g['show'] and not g['playing'] and g['ctl'] and not g['ctl']['playing'], f'paused: they stay up, showing Play {g}')
        await pg.screenshot(path=f'{SHOTS}/vctl-ch-paused.png')
        # the native player's buttons
        await pg.evaluate("window.__emit('videoctl',{action:'play'})"); await pg.wait_for_timeout(200)
        n2 = await pg.evaluate("window.__calls.filter(function(c){return c[0]==='play';}).length")
        check(n2 >= 1, f'videoctl play plays ({n2})')
        await pg.evaluate("(id)=>window.__emit('state',{id:id,state:'ready',isPlaying:true,playWhenReady:true,position:0,duration:-1,live:true})", cur)
        await pg.evaluate("window.__emit('videoctl',{action:'full'})"); await pg.wait_for_timeout(500)
        g = await pg.evaluate(STATE)
        check(g['full'] and g['box'][1] == 844 and g['ctl']['full'], f'videoctl full goes full screen, controls over the whole screen {g["box"]}')
        if not await pg.evaluate("document.getElementById('vctl').classList.contains('show')"):
            await pg.evaluate("document.getElementById('vctl').click()")
        await pg.wait_for_timeout(300)
        check(await pg.evaluate("document.getElementById('vctl').classList.contains('show')"), 'full screen: the controls show')
        await pg.screenshot(path=f'{SHOTS}/vctl-ch-full.png')
        await pg.evaluate("document.getElementById('npVideoFullBtn').click()"); await pg.wait_for_timeout(400)
        g = await pg.evaluate(STATE)
        check(not g['full'], 'the full screen button comes back out')
        check(g['gridH'] >= 380, f'the channel list is taller than before (327px in build 180) ({g["gridH"]}px from {g["gridTop"]})')
        # Favorite moved into More
        await pg.evaluate("document.getElementById('npMenuBtn').click()"); await pg.wait_for_timeout(300)
        fm = await pg.evaluate("[getComputedStyle(document.getElementById('npFavMenuBtn')).display, document.getElementById('npFavMenuBtn').textContent]")
        hit = await pg.evaluate("(()=>{var r=document.getElementById('npFavMenuBtn').getBoundingClientRect();var e=document.elementFromPoint(r.left+r.width/2,r.top+r.height/2);return !!e && document.getElementById('npMenu').contains(e);})()")
        check(fm[0] == 'flex' and fm[1] == 'Add to Favorites' and hit, f'More starts with Add to Favorites, drawn above the list {fm} {hit}')
        await pg.screenshot(path=f'{SHOTS}/vctl-ch-menu.png')
        await pg.evaluate("document.getElementById('npFavMenuBtn').click()"); await pg.wait_for_timeout(300)
        fm = await pg.evaluate("document.getElementById('npFavMenuBtn').textContent")
        check(fm == 'Remove from Favorites', f'it adds the channel to Favorites ({fm})')
        # floating window: the native player draws no controls
        await pg.evaluate("document.getElementById('npBackBtn').click()"); await pg.wait_for_timeout(700)
        c = await pg.evaluate("window.__ctl.slice(-1)[0]")
        check(c and not c['enabled'], f'no native controls on the floating window {c}')
        check(not errs, f'no page errors {errs[:3]}')
        # light theme
        await b.close()
        b = await p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
        ctx = await b.new_context(viewport={'width': 360, 'height': 780}, device_scale_factor=2, is_mobile=True, has_touch=True, color_scheme='light', locale='en-US')
        await ctx.add_init_script(MOCK); await ctx.add_init_script(SPY)
        await ctx.add_init_script("localStorage.setItem('radioPlayerVideoChannels', %s)" % repr(json.dumps(SEED)))
        await ctx.add_init_script("localStorage.setItem('radioPlayerTheme', 'light')")
        await ctx.add_init_script("document.addEventListener('DOMContentLoaded',function(){var s=document.createElement('style');s.textContent='.np-name,.np-sub,.tile-name,.np-related-heading{font-size:calc(1em*1.3) !important}';document.head.appendChild(s);})")
        pg = await ctx.new_page(); pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.route('**/*', route)
        await pg.goto('http://127.0.0.1:8815/index.html'); await pg.wait_for_timeout(2500)
        await pg.evaluate("document.querySelector('.mobile-nav-btn[data-nav=video]').click()"); await pg.wait_for_timeout(600)
        await pg.evaluate("document.querySelector('#stationsGrid .tile.ch-item').click()"); await pg.wait_for_timeout(500)
        cur = await pg.evaluate("window.__cur")
        await pg.evaluate("(id)=>window.__emit('video',{id:id,hasVideo:true,width:1280,height:720})", cur); await pg.wait_for_timeout(400)
        if not await pg.evaluate("document.getElementById('vctl').classList.contains('show')"):
            await pg.evaluate("document.getElementById('vctl').click()")
        await pg.wait_for_timeout(300)
        await pg.screenshot(path=f'{SHOTS}/vctl-ch-light-360.png')
        check(not errs, f'light 360: no page errors {errs[:3]}')
        await b.close()
    print('ALL PASSED' if not fails else f'{fails} FAILED')

asyncio.run(main())
