"""Build 316: watching full screen, the next video (a channel moving on, the next of a shuffle) starts without
the controls popping up: the page's controls stay hidden and the native player is told quiet:true while the
picture comes back. Not full screen, the first look at a video still shows them; a tap still shows them.
Run: python3 tests/test_video_seamless.py (screenshots in /tmp/claude-0/t/shots)"""
import sys as _nsys, os as _nos; _nsys.path.insert(0, _nos.path.dirname(_nos.path.abspath(__file__))); from notice_auto import AUTO_NOTICE
import asyncio, os
HERE = os.path.dirname(os.path.abspath(__file__))
src = open(os.path.join(HERE, 'test_video_channels.py')).read()
head = src[:src.index('async def rows(pg)')]
head = head.replace("'/tmp/claude-0/t/srv-ch'", "'/tmp/claude-0/t/srv-seam'").replace('8777', '8816')
exec(head)
_ix = open(os.path.join(ROOT, 'index.html')).read()
_mark = '  var coverFlow = null;\n'
assert _ix.count(_mark) == 1
open(os.path.join(ROOT, 'index.html'), 'w').write(_ix.replace(_mark, _mark + "window.__h = { ev: function(js){ return eval(js); } };\n"))
from playwright.async_api import async_playwright

SEED = [{'id': 'link:%d' % i, 'name': 'Channel %02d' % i, 'url': 'http://ch%d.example/l.m3u8' % i, 'logo': '', 'country': 'US', 'cats': [], 'catNames': [], 'src': 'link', 'addedAt': 10 + i} for i in range(6)]
SPY = """
(function(){
  var P = window.Capacitor.Plugins.AmplifyPlayer;
  window.__ctl = []; window.__hold = []; window.__view = [];
  window.Capacitor.Plugins.AmplifyPlayer = new Proxy({}, {get:function(t,k){
    if(k === 'setVideoControls') return function(m){ m.t = Date.now(); window.__ctl.push(m); return Promise.resolve({}); };
    if(k === 'holdVideo') return function(m){ window.__hold.push([m.on, Date.now()]); return Promise.resolve({}); };
    if(k === 'setVideoView') return function(m){ window.__view.push([!!m.show, Math.round(m.width), Math.round(m.height), Date.now()]); return P[k](m); };
    return P[k];
  }});
})();
"""
SHOWN = "document.getElementById('vctl').classList.contains('show')"

async def play_row(pg, n):
    # The guide under the player: tap channel n's block with a finger.
    box = await pg.evaluate("""(n)=>{ var r = document.querySelectorAll('#npCollection .epg-row')[n]; r.scrollIntoView({block:'center'});
      var b = r.querySelector('.epg-prog').getBoundingClientRect(); return [Math.max(b.left + 30, 140), b.top + b.height / 2]; }""", n)
    await pg.touchscreen.tap(box[0], box[1])

async def picture(pg):
    cur = await pg.evaluate("window.__cur")
    await pg.evaluate("(id)=>window.__emit('video',{id:id,hasVideo:true,width:1280,height:720})", cur)

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
        ctx = await b.new_context(viewport={'width': 390, 'height': 844}, device_scale_factor=2, is_mobile=True, has_touch=True, color_scheme='dark', locale='en-US')
        await ctx.add_init_script(MOCK); await ctx.add_init_script(AUTO_NOTICE); await ctx.add_init_script(SPY)
        await ctx.add_init_script("localStorage.setItem('radioPlayerVideoChannels', %s)" % repr(json.dumps(SEED)))
        pg = await ctx.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.route('**/*', route)
        await pg.goto('http://127.0.0.1:8816/index.html'); await pg.wait_for_timeout(2500)
        await pg.tap('.mobile-nav-btn[data-nav=video]'); await pg.wait_for_timeout(700)
        await pg.evaluate("document.querySelector('#stationsGrid .epg-row .epg-prog').click()"); await pg.wait_for_timeout(600)
        await picture(pg); await pg.wait_for_timeout(500)
        # Not full screen: the first look still shows the controls (as before).
        if await pg.evaluate("document.body.classList.contains('np-video-full')"):
            await pg.evaluate("document.getElementById('npVideoFullBtn').click()"); await pg.wait_for_timeout(300)
        first = [m for m in await pg.evaluate("window.__ctl") if m['enabled']]
        check(first and not first[0]['quiet'], 'not full screen: the first video is not quiet (controls show as before) %s' % (first[:1],))
        # Channel 2, still not full screen: shows as before.
        await play_row(pg, 2); await pg.wait_for_timeout(700)
        await picture(pg); await pg.wait_for_timeout(400)
        check(await pg.evaluate(SHOWN), 'not full screen, the next channel shows them as before')
        await pg.wait_for_timeout(3500)
        # Full screen, then the channel moves on (Channel 3).
        await pg.evaluate("window.__emit('videoctl',{action:'full'})"); await pg.wait_for_timeout(600)
        check(await pg.evaluate("document.body.classList.contains('np-video-full')"), 'full screen on')
        await pg.evaluate("document.getElementById('vctl').classList.remove('show')")
        n0 = await pg.evaluate("window.__ctl.length")
        await pg.evaluate("() => window.__h.ev(\"playChannel(findVideoChannel('http://ch3.example/l.m3u8')); 1\")")
        await pg.wait_for_timeout(50)
        seen = []
        for _ in range(12):
            seen.append(await pg.evaluate(SHOWN)); await pg.wait_for_timeout(50)
        await picture(pg)
        for _ in range(30):
            seen.append(await pg.evaluate(SHOWN)); await pg.wait_for_timeout(50)
        msgs = (await pg.evaluate("window.__ctl"))[n0:]
        name = await pg.evaluate("document.getElementById('npName').textContent")
        check(name == 'Channel 03', 'full screen: on to Channel 03 (%s)' % name)
        check(not any(seen), "full screen: the page's controls never show as the next video starts (%d samples)" % len(seen))
        off = next((i for i, m in enumerate(msgs) if not m['enabled']), None)
        back = [m for m in msgs[(off or 0):] if m['enabled']]
        check(all(m['quiet'] for m in msgs if m['enabled'] and not m['full']) and back and back[0]['quiet'], 'the native player is told quiet while the picture comes back %s' % [(m['enabled'], m['quiet'], m['full']) for m in msgs[:6]])
        check(await pg.evaluate("document.body.classList.contains('np-video-full')"), 'and full screen holds')
        await pg.screenshot(path=f'{SHOTS}/seamless-full-next.png')
        hold = await pg.evaluate("window.__hold")
        check(len(hold) >= 2 and hold[0][0] is True and hold[-1][0] is False, 'the phone holds the picture between the two videos and lets go after %s' % hold)
        on_t = hold[0][1]; off_t = hold[-1][1]
        views = await pg.evaluate("window.__view")
        full_after = [v for v in views if v[3] > on_t and v[3] < off_t and v[0] and v[2] >= 800]
        check(full_after, 'the full screen box is reported again before letting go %s' % [v[:3] for v in views if v[3] > on_t][:5])
        # A tap still shows them.
        bx = await pg.evaluate("(()=>{var r=document.getElementById('vctl').getBoundingClientRect();return [r.left,r.top,r.width,r.height];})()")
        await pg.touchscreen.tap(bx[0] + bx[2] * .2, bx[1] + bx[3] * .3); await pg.wait_for_timeout(350)
        check(await pg.evaluate(SHOWN), 'a tap still shows them')
        await pg.screenshot(path=f'{SHOTS}/seamless-full-tap.png')
        check(not errs, 'no page errors %s' % errs[:3])
        await b.close()
    print('ALL PASSED' if not fails else f'{fails} FAILED')
    raise SystemExit(1 if fails else 0)

asyncio.run(main())
