"""Build 658 (Mark): podcast skip lengths. Settings > Playback > Podcasts has Skip back (5/10/15/30)
and Skip forward (15/30/45/60/90); the choice is saved, sent to the phone's player
(setPodcastSkip, also at start), and used by Now Playing's skip buttons (number in the arrow,
title) and the lock screen's seek handlers. Videos keep 10. Screenshots at Mark's phone size
(327x690 upright, 678x297 sideways, dpr 3.3), dark and light.
Run: python3 tests/test_podcast_skip.py (screenshots in /tmp/claude-0/t/shots)"""
import asyncio, os, json, threading, http.server, functools, shutil, subprocess
from playwright.async_api import async_playwright

PORT = 8961
root = '/tmp/claude-0/t/srv_podskip'
shots = '/tmp/claude-0/t/shots'
os.makedirs(shots, exist_ok=True)
shutil.rmtree(root, ignore_errors=True); os.makedirs(root)
HOOK = "window.__t = { ev: function(js){ return eval(js); } };\n"
_src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'www', 'index.html')).read()
_mark = '  var coverFlow = null;\n'
assert _src.count(_mark) == 1
open(root + '/index.html', 'w').write(_src.replace(_mark, _mark + HOOK))
subprocess.run(['ffmpeg', '-loglevel', 'error', '-y', '-f', 'lavfi', '-i', 'sine=frequency=330:duration=600', '-c:a', 'libmp3lame', '-b:a', '16k', root + '/ep.mp3'], check=True)
subprocess.run(['ffmpeg', '-loglevel', 'error', '-y', '-f', 'lavfi', '-i', 'testsrc=size=600x600:rate=1', '-frames:v', '1', root + '/cover.jpg'], check=True)
EP = {'type': 'podcast', 'guid': 'g1', 'collectionId': 1, 'collectionName': 'The Disney Dish with Jim Hill', 'artistName': 'Jim Hill',
      'name': 'Why the Adventurers Club still matters, and what Imagineering learned from it', 'favicon': f'http://127.0.0.1:{PORT}/cover.jpg',
      'releaseDate': '2026-11-15T10:00:00Z', 'duration': 600, 'episodeUrl': f'http://127.0.0.1:{PORT}/ep.mp3', 'description': ''}

class Q(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a): pass
srv = http.server.ThreadingHTTPServer(('127.0.0.1', PORT), functools.partial(Q, directory=root))
threading.Thread(target=srv.serve_forever, daemon=True).start()

MOCK = """(function(){ var calls = window.__skipCalls = [];
 var impl = { setPodcastSkip: function(o){ calls.push(o); return Promise.resolve({ back: o.back, fwd: o.fwd }); },
   addListener: function(){ return Promise.resolve({ remove: function(){} }); } };
 var P = new Proxy({}, { get: function(t, k){ if(k === 'then') return undefined; if(k === 'setCarLibraryPart' || k === 'load' || k === 'kvSet' || k === 'kvGetAll' || k === 'podcastRefresh' || k === 'podcastFeedsGet') return undefined; if(impl[k]) return impl[k]; return function(){ return Promise.resolve({}); }; } });
 window.Capacitor = { isNativePlatform: function(){ return true; }, getPlatform: function(){ return 'android'; }, registerPlugin: function(){ return P; }, Plugins: { AmplifyPlayer: P }, convertFileSrc: function(u){ return u; } };
})();"""

fails = []
def check(c, m):
    print(('PASS ' if c else 'FAIL ') + m)
    if not c: fails.append(m)

async def route(r):
    if '127.0.0.1' in r.request.url: return await r.continue_()
    return await r.abort()

def EV(js): return "__t.ev(" + json.dumps(js) + ")"
BTN = """()=>{var o={}; ['npSkipBackBtn','npSkipFwdBtn','npPlayBtn'].forEach(function(id){var e=document.getElementById(id), r=e.getBoundingClientRect(); var n=e.querySelector('.np-skip-num'); var nr=n?n.getBoundingClientRect():null; var ic=e.querySelector('svg'); var ir=ic?ic.getBoundingClientRect():null;
  o[id]={vis:getComputedStyle(e).display!=='none'&&r.width>0, x:r.left+r.width/2, y:r.top+r.height/2, w:r.width, title:e.title, num:n?n.textContent:null,
   numIn: nr&&ir? (nr.left>=ir.left && nr.right<=ir.right && nr.top>=ir.top && nr.bottom<=ir.bottom):null, numW: nr?nr.width:0, iconW: ir?ir.width:0};}); return o;}"""

async def ctx_page(b, scheme, w, h, store=None):
    ctx = await b.new_context(viewport={'width': w, 'height': h}, device_scale_factor=3.3, is_mobile=True, has_touch=True, color_scheme=scheme)
    await ctx.add_init_script(MOCK)
    init = {'radioPlayerTheme': scheme, 'radioPlayerLtvAuto': '0'}
    init.update(store or {})
    await ctx.add_init_script("try{ var o=%s; for(var k in o) localStorage.setItem(k, o[k]); }catch(e){}" % json.dumps(init))
    pg = await ctx.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
    await pg.route('**/*', route)
    await pg.goto(f'http://127.0.0.1:{PORT}/index.html'); await pg.wait_for_timeout(2500)
    await pg.evaluate(EV("closeNotice()"))
    return ctx, pg, errs

async def play(pg):
    await pg.evaluate(EV("playPodcastEpisode(%s); openNowPlaying(currentStation)" % json.dumps(EP)))
    for _ in range(40):
        await pg.wait_for_timeout(250)
        if await pg.evaluate("isFinite(document.querySelector('audio') ? 1 : 1) && __t.ev('isFinite(audio.duration) && audio.duration > 0')"): break
    await pg.wait_for_timeout(800)

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(args=['--autoplay-policy=no-user-gesture-required'])
        for scheme in ('dark', 'light'):
            T = f'[{scheme}]'
            ctx, pg, errs = await ctx_page(b, scheme, 327, 690)
            calls = await pg.evaluate("window.__skipCalls")
            check(calls[:1] == [{'back': 15, 'fwd': 30}], T + ' defaults sent to the player at start ' + str(calls[:1]))
            await play(pg)
            bt = await pg.evaluate(BTN)
            check(bt['npSkipBackBtn']['vis'] and bt['npSkipFwdBtn']['vis'], T + ' skip buttons show for an episode')
            check(bt['npSkipBackBtn']['num'] == '15' and bt['npSkipFwdBtn']['num'] == '30', T + ' default numbers 15 / 30')
            check(bt['npSkipBackBtn']['numIn'] and bt['npSkipFwdBtn']['numIn'], T + ' numbers sit inside the arrows')
            mid = (bt['npSkipBackBtn']['x'] + bt['npSkipFwdBtn']['x']) / 2
            check(abs(mid - bt['npPlayBtn']['x']) < 1.5, T + f' Play centred between skips ({mid:.1f} vs {bt["npPlayBtn"]["x"]:.1f})')
            await pg.screenshot(path=f'{shots}/podskip_np_default_{scheme}.png')
            # settings
            await pg.evaluate(EV("closeNowPlaying(); openSettings(); showSettingsCat('playback')")); await pg.wait_for_timeout(600)
            await pg.evaluate("document.getElementById('settingsPanel').scrollTop = 1e6"); await pg.wait_for_timeout(300)
            await pg.screenshot(path=f'{shots}/podskip_settings_{scheme}.png')
            opts = await pg.evaluate("[Array.from(document.querySelectorAll('#podSkipBackSelect option')).map(o=>o.value), Array.from(document.querySelectorAll('#podSkipFwdSelect option')).map(o=>o.value), document.getElementById('podSkipBackSelect').value, document.getElementById('podSkipFwdSelect').value]")
            check(opts[0] == ['5', '10', '15', '30'] and opts[1] == ['15', '30', '45', '60', '90'], T + ' choices ' + str(opts[:2]))
            check(opts[2] == '15' and opts[3] == '30', T + ' selects start at 15 / 30')
            lay = await pg.evaluate("""()=>{var r=['podSkipBackSelect','podSkipFwdSelect'].map(function(id){var s=document.getElementById(id); var b=s.getBoundingClientRect(); return {right:b.right, w:b.width, cut: s.scrollWidth > s.clientWidth + 1};}); return {r:r, vw:document.documentElement.clientWidth, hs: document.getElementById('settingsPanel').scrollWidth > document.getElementById('settingsPanel').clientWidth + 1};}""")
            check(all(x['right'] <= lay['vw'] + .5 for x in lay['r']) and not lay['hs'], T + ' selects fit the screen, no sideways scroll')
            await pg.select_option('#podSkipBackSelect', '10'); await pg.select_option('#podSkipFwdSelect', '45'); await pg.wait_for_timeout(300)
            calls = await pg.evaluate("window.__skipCalls")
            check(calls[-1] == {'back': 10, 'fwd': 45}, T + ' change sent to the player ' + str(calls[-1]))
            stored = await pg.evaluate("[localStorage.getItem('radioPlayerPodcastSkipBack'), localStorage.getItem('radioPlayerPodcastSkipFwd')]")
            check(stored == ['10', '45'], T + ' saved ' + str(stored))
            await pg.evaluate(EV("closeSettings(); openNowPlaying(currentStation)")); await pg.wait_for_timeout(700)
            bt = await pg.evaluate(BTN)
            check(bt['npSkipBackBtn']['num'] == '10' and bt['npSkipFwdBtn']['num'] == '45', T + ' Now Playing shows 10 / 45')
            check(bt['npSkipBackBtn']['title'] == 'Back 10 seconds' and bt['npSkipFwdBtn']['title'] == 'Forward 45 seconds', T + ' titles updated')
            await pg.screenshot(path=f'{shots}/podskip_np_10_45_{scheme}.png')
            await pg.evaluate(EV("audio.currentTime = 100")); await pg.wait_for_timeout(300)
            t0 = await pg.evaluate(EV("audio.currentTime"))
            await pg.tap('#npSkipFwdBtn'); await pg.wait_for_timeout(300)
            t1 = await pg.evaluate(EV("audio.currentTime"))
            check(abs((t1 - t0) - 45) < 1.5, T + f' forward skips 45 ({t1 - t0:.1f})')
            await pg.tap('#npSkipBackBtn'); await pg.wait_for_timeout(300)
            t2 = await pg.evaluate(EV("audio.currentTime"))
            check(abs((t1 - t2) - 10) < 1.5, T + f' back skips 10 ({t1 - t2:.1f})')
            check(await pg.evaluate(EV("podcastSkipBack() === 10 && podcastSkipFwd() === 45")), T + ' lock-screen handlers read the same values')
            # 90 is the widest number
            await pg.evaluate("localStorage.setItem('radioPlayerPodcastSkipFwd','90'); localStorage.setItem('radioPlayerPodcastSkipBack','5')")
            await pg.evaluate(EV("syncNpPodcastControls()")); await pg.wait_for_timeout(200)
            bt = await pg.evaluate(BTN)
            check(bt['npSkipFwdBtn']['num'] == '90' and bt['npSkipFwdBtn']['numIn'] and bt['npSkipBackBtn']['numIn'], T + ' 5 / 90 fit inside the arrows')
            await pg.screenshot(path=f'{shots}/podskip_np_5_90_{scheme}.png')
            check(not errs, T + ' no page errors ' + str(errs[:2]))
            await ctx.close()
            # sideways
            ctx, pg, errs = await ctx_page(b, scheme, 678, 297, {'radioPlayerPodcastSkipBack': '30', 'radioPlayerPodcastSkipFwd': '60'})
            calls = await pg.evaluate("window.__skipCalls")
            check(calls[:1] == [{'back': 30, 'fwd': 60}], T + ' saved values sent at start ' + str(calls[:1]))
            await play(pg)
            bt = await pg.evaluate(BTN)
            check(bt['npSkipBackBtn']['vis'] and bt['npSkipBackBtn']['num'] == '30' and bt['npSkipFwdBtn']['num'] == '60' and bt['npSkipBackBtn']['numIn'] and bt['npSkipFwdBtn']['numIn'], T + ' sideways: 30 / 60 inside the arrows')
            await pg.screenshot(path=f'{shots}/podskip_np_side_{scheme}.png')
            check(not errs, T + ' sideways: no page errors ' + str(errs[:2]))
            await ctx.close()
        # bad stored value falls back
        ctx, pg, errs = await ctx_page(b, 'dark', 327, 690, {'radioPlayerPodcastSkipBack': '7', 'radioPlayerPodcastSkipFwd': 'x'})
        check(await pg.evaluate(EV("podcastSkipBack() === 15 && podcastSkipFwd() === 30")), 'unknown stored values fall back to 15 / 30')
        await ctx.close()
        await b.close()
    print('ALL PASS' if not fails else f'{len(fails)} FAILED')
    if fails: raise SystemExit(1)
asyncio.run(main())
