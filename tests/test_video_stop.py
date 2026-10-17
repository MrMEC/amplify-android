"""Build 246 (Mark): a Stop button at the top right of the video's controls. It stops and closes
the video, closes Now Playing, and leaves the page the video came from on screen: the Live TV
guide for a channel (wherever it was started from), the movie's page or the show's page for a
video on the phone. The phone's own controls (native picture) send 'videoctl' {action:'stop'},
which does the same. Sideways on a channel, Stop leaves the guide alone on screen (build 244).
Phone first: 390 dark and 360 light with larger text.
Run: python3 tests/test_video_stop.py (screenshots in /tmp/claude-0/t/shots)"""
import sys as _nsys, os as _nos; _nsys.path.insert(0, _nos.path.dirname(_nos.path.abspath(__file__))); from notice_auto import AUTO_NOTICE
import asyncio, os, json
HERE = os.path.dirname(os.path.abspath(__file__))
src = open(os.path.join(HERE, 'test_video_library.py')).read()
head = src[:src.index('async def main()')]
head = head.replace("'/tmp/claude-0/t/srv-vlib'", "'/tmp/claude-0/t/srv-vstop'").replace('8780', '8850')
exec(head)

CH = [{'id': 'iptv:ABCNews.us', 'name': 'ABC News Live', 'url': 'https://abc.example/live1080.m3u8', 'logo': '', 'country': 'US', 'cats': ['news'], 'catNames': ['News'], 'src': 'iptv', 'addedAt': 1},
      {'id': 'iptv:PBS.us', 'name': 'PBS', 'url': 'https://pbs.example/live.m3u8', 'logo': '', 'country': 'US', 'cats': [], 'catNames': [], 'src': 'iptv', 'addedAt': 2}]

NP = "document.getElementById('nowPlayingScreen').style.display"
STOPV = """(()=>{ var b=document.getElementById('vctlStop'), v=document.getElementById('vctl'); var r=b.getBoundingClientRect(), box=v.getBoundingClientRect(), cs=getComputedStyle(b);
  var hit=document.elementFromPoint(r.left+r.width/2, r.top+r.height/2);
  return { text: b.textContent, vis: cs.visibility, op: cs.opacity, inside: r.left >= box.left && r.right <= box.right + 0.5 && r.top >= box.top - 0.5,
    topRight: (box.right - r.right) <= 16 && (r.top - box.top) <= 16, hit: !!(hit && hit.closest('#vctlStop')), h: Math.round(r.height) }; })()"""
WHERE = """(()=>{ var g=document.getElementById('stationsGrid'); var active=document.querySelector('.video-tabs .home-tab.active');
  return { np: document.getElementById('nowPlayingScreen').style.display, playing: !!document.querySelector('#playerBar.playing, .player-bar.playing'),
    tab: active ? active.dataset.vtab : null, grid: !!g.querySelector(':scope > .epg'), title: (document.querySelector('.vd-title')||{}).textContent || null,
    nav: (document.querySelector('.mobile-nav-btn.active')||{}).dataset ? (document.querySelector('.mobile-nav-btn.active')||{}).dataset.nav : null,
    land: document.body.classList.contains('epg-land'), rot: document.body.classList.contains('rotate-lock'),
    loads: (window.__loadArgs||[]).length }; })()"""


async def show_controls(pg):
    cur = await pg.evaluate("window.__cur")
    await pg.evaluate("(id)=>window.__emit('video',{id:id,hasVideo:true,width:1280,height:720})", cur); await pg.wait_for_timeout(500)
    if not await pg.evaluate("document.getElementById('vctl').classList.contains('show')"):
        await pg.evaluate("document.getElementById('vctl').click()"); await pg.wait_for_timeout(300)


async def run(p, theme, width, big):
    T = f'[{theme} {width}{" big" if big else ""}]'
    b = await p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
    ctx = await b.new_context(viewport={'width': width, 'height': 844}, device_scale_factor=2, is_mobile=True, has_touch=True, color_scheme=theme, locale='en-US')
    await ctx.add_init_script(MOCK); await ctx.add_init_script(AUTO_NOTICE); await ctx.add_init_script(EXT)
    await ctx.add_init_script("localStorage.setItem('radioPlayerVideoChannels', %s)" % repr(json.dumps(CH)))
    await ctx.add_init_script("try{ localStorage.setItem('radioPlayerTheme', %s); }catch(e){}" % json.dumps(theme))
    pg = await ctx.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
    await pg.route('**/*', route)
    await pg.goto('http://127.0.0.1:8850/index.html'); await pg.wait_for_timeout(2500)
    if big:
        await pg.add_style_tag(content='.vctl-stop{font-size:17.5px !important} .np-name,.tile-name{font-size:calc(1em*1.35) !important}')
    await pg.evaluate("document.querySelector('.mobile-nav-btn[data-nav=video]').click()"); await pg.wait_for_timeout(700)
    await pg.evaluate("document.querySelector('.video-tabs [data-vtab=channels]').click()"); await pg.wait_for_timeout(600)

    # ---- a channel from the guide
    await pg.evaluate("document.querySelector('#stationsGrid .epg-ch').click()"); await pg.wait_for_timeout(900)
    await show_controls(pg)
    sv = await pg.evaluate(STOPV)
    check(sv['text'] == 'Stop' and sv['vis'] == 'visible' and sv['op'] == '1' and sv['inside'] and sv['topRight'] and sv['hit'], f'{T} Stop shows at the top right of the video controls {sv}')
    await pg.screenshot(path=f'{SHOTS}/vstop-channel-{theme}-{width}.png')
    await pg.evaluate("document.getElementById('vctl').click()"); await pg.wait_for_timeout(500)
    hid = await pg.evaluate("getComputedStyle(document.getElementById('vctlStop')).visibility")
    check(hid == 'hidden', f'{T} it hides with the other controls ({hid})')
    await pg.evaluate("document.getElementById('vctl').click()"); await pg.wait_for_timeout(300)
    await pg.evaluate("document.getElementById('vctlStop').click()"); await pg.wait_for_timeout(900)
    w = await pg.evaluate(WHERE)
    cur = await pg.evaluate("(()=>{ try{ return !!window.__cur && false; }catch(e){ return false; } })()")
    check(w['np'] == 'none' and w['tab'] == 'channels' and w['grid'] and w['nav'] == 'video', f'{T} Stop: Now Playing closes, the Live TV guide is on screen {w}')
    bar = await pg.evaluate("(document.getElementById('playerName')||{}).textContent || ''")
    check(not await pg.evaluate("document.querySelector('#stationsGrid .epg-ch.playing') !== null"), f'{T} nothing is playing any more (no channel marked playing; bar: {bar!r})')
    # ---- a channel started elsewhere (Home, from the player bar): Stop still lands on the guide
    await pg.evaluate("document.querySelector('#stationsGrid .epg-ch').click()"); await pg.wait_for_timeout(900)
    await pg.evaluate("document.getElementById('npBackBtn').click()"); await pg.wait_for_timeout(700)
    await pg.evaluate("document.querySelector('.mobile-nav-btn[data-nav=home]').click()"); await pg.wait_for_timeout(700)
    await pg.evaluate("document.querySelector('.video-tabs') && null")
    await pg.evaluate("(()=>{ var b=document.getElementById('playerBar') || document.querySelector('.player-bar'); (b.querySelector('.player-info, .player-meta') || b).click(); })()"); await pg.wait_for_timeout(1000)
    np = await pg.evaluate(NP)
    check(np == 'flex', f'{T} (Now Playing reopened from the player bar on Home: {np})')
    await show_controls(pg)
    # the phone's own controls send stop
    await pg.evaluate("window.__emit('videoctl',{action:'stop'})"); await pg.wait_for_timeout(900)
    w = await pg.evaluate(WHERE)
    check(w['np'] == 'none' and w['tab'] == 'channels' and w['grid'] and w['nav'] == 'video', f'{T} Stop from the phone’s own controls, started from Home: the Live TV guide {w}')

    # ---- a movie
    await pg.evaluate("document.querySelector('.video-tabs [data-vtab=movies]').click()"); await pg.wait_for_timeout(500)
    await pg.evaluate("document.getElementById('videoAddHeaderBtn').click()"); await pg.wait_for_timeout(2500)
    await pg.evaluate("Array.prototype.find.call(document.querySelectorAll('#stationsGrid .tile.vposter'),function(t){return t.querySelector('.tile-name').textContent==='Inception';}).click()"); await pg.wait_for_timeout(900)
    await pg.evaluate("document.querySelector('.vd-play').click()"); await pg.wait_for_timeout(1200)
    await state(pg, {})
    await show_controls(pg)
    sv = await pg.evaluate(STOPV)
    check(sv['inside'] and sv['topRight'] and sv['hit'], f'{T} a movie: Stop at the top right too {sv}')
    await pg.screenshot(path=f'{SHOTS}/vstop-movie-{theme}-{width}.png')
    # leave the movie page while it plays, then Stop from Now Playing
    await pg.evaluate("document.getElementById('npBackBtn').click()"); await pg.wait_for_timeout(600)
    await pg.evaluate("document.querySelector('.mobile-nav-btn[data-nav=home]').click()"); await pg.wait_for_timeout(700)
    await pg.evaluate("(()=>{ var b=document.getElementById('playerBar') || document.querySelector('.player-bar'); (b.querySelector('.player-info, .player-meta') || b).click(); })()"); await pg.wait_for_timeout(1000)
    await show_controls(pg)
    await pg.evaluate("document.getElementById('vctlStop').click()"); await pg.wait_for_timeout(900)
    w = await pg.evaluate(WHERE)
    check(w['np'] == 'none' and w['title'] == 'Inception', f'{T} Stop on a movie: back on the movie’s page {w}')
    await pg.screenshot(path=f'{SHOTS}/vstop-movie-after-{theme}-{width}.png')
    # Back from there goes where it went before (not a second copy of the page)
    # ---- an episode
    await pg.evaluate("document.querySelector('.mobile-nav-btn[data-nav=video]').click()"); await pg.wait_for_timeout(700)
    await pg.evaluate("(()=>{ var d=document.getElementById('detailBackBtn'); if(d && d.offsetParent) d.click(); })()"); await pg.wait_for_timeout(500)
    await pg.evaluate("document.querySelector('.video-tabs [data-vtab=shows]').click()"); await pg.wait_for_timeout(500)
    await pg.evaluate("Array.prototype.find.call(document.querySelectorAll('#stationsGrid .tile.vposter'),function(t){return t.querySelector('.tile-name').textContent==='Breaking Bad';}).click()"); await pg.wait_for_timeout(900)
    await pg.evaluate("document.querySelector('#stationsGrid .vep-row').click()"); await pg.wait_for_timeout(1200)
    await state(pg, {'duration': 2820})
    await show_controls(pg)
    await pg.evaluate("document.getElementById('vctlStop').click()"); await pg.wait_for_timeout(900)
    w = await pg.evaluate(WHERE)
    check(w['np'] == 'none' and w['title'] == 'Breaking Bad', f'{T} Stop on an episode: back on the show’s page {w}')
    # Back from the show page: one step back, to the shows list (no duplicate page in the history)
    await pg.evaluate("document.getElementById('detailBackBtn').click()"); await pg.wait_for_timeout(700)
    w2 = await pg.evaluate(WHERE)
    check(w2['title'] is None and w2['tab'] == 'shows', f'{T} Back from there: the TV Shows list, not the same page again {w2}')

    # ---- sideways on a channel: Stop leaves the guide alone on screen
    await pg.evaluate("document.querySelector('.video-tabs [data-vtab=channels]').click()"); await pg.wait_for_timeout(600)
    await pg.evaluate("document.querySelector('#stationsGrid .epg-ch').click()"); await pg.wait_for_timeout(900)
    await show_controls(pg)
    await pg.set_viewport_size({'width': 844, 'height': width}); await pg.wait_for_timeout(1200)
    r0 = await pg.evaluate("[document.body.classList.contains('rotate-lock'), document.body.classList.contains('np-video-full')]")
    await show_controls(pg)
    sv = await pg.evaluate(STOPV)
    check(sv['hit'], f'{T} sideways (full screen video {r0}): Stop is there {sv}')
    await pg.screenshot(path=f'{SHOTS}/vstop-land-{theme}-{width}.png')
    await pg.evaluate("document.getElementById('vctlStop').click()"); await pg.wait_for_timeout(1200)
    w = await pg.evaluate(WHERE)
    check(w['np'] == 'none' and w['land'] and not w['rot'], f'{T} Stop sideways: the guide alone fills the screen {w}')
    await pg.screenshot(path=f'{SHOTS}/vstop-land-after-{theme}-{width}.png')
    await pg.set_viewport_size({'width': width, 'height': 844}); await pg.wait_for_timeout(1000)
    w = await pg.evaluate(WHERE)
    check(not w['land'] and w['grid'], f'{T} upright again: the Live TV page {w}')
    check(not errs, f'{T} no page errors {errs[:3]}')
    await b.close()


async def main():
    async with async_playwright() as p:
        await run(p, 'dark', 390, False)
        await run(p, 'light', 360, True)
    print('ALL PASSED' if not fails else f'FAILED {fails}')

asyncio.run(main())
