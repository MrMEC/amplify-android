"""Build 656 (Mark): Settings > Playback > Podcast chapters. With a mocked podcastChapterCheck,
checks the row shows only in the app, the working notice while it runs, the results page's
groups and lead, Check again, the error notice, and the no-podcasts notice. Screenshots at
Mark's phone size (327 wide, dpr 3.3), light and dark, with 99 real followed shows when
/tmp/claude-0/t/backup.json exists (else 40 made-up ones).
Run: python3 tests/test_chapter_check.py (screenshots in /tmp/claude-0/t/shots)"""
import asyncio, os, json, threading, http.server, functools, shutil, subprocess
from playwright.async_api import async_playwright

PORT = 8960
root = '/tmp/claude-0/t/srv_chapters'
shots = '/tmp/claude-0/t/shots'
os.makedirs(shots, exist_ok=True)
shutil.rmtree(root, ignore_errors=True); os.makedirs(root)
HOOK = "window.__t = { ev: function(js){ return eval(js); } };\n"
_src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'www', 'index.html')).read()
_mark = '  var coverFlow = null;\n'
assert _src.count(_mark) == 1
open(root + '/index.html', 'w').write(_src.replace(_mark, _mark + HOOK))
subprocess.run(['ffmpeg', '-loglevel', 'error', '-y', '-f', 'lavfi', '-i', 'testsrc=size=600x600:rate=1', '-frames:v', '1', root + '/cover.jpg'], check=True)
COVER = open(root + '/cover.jpg', 'rb').read()

BK = '/tmp/claude-0/t/backup.json'
if os.path.exists(BK):
    SUBS = [{k: s.get(k) for k in ('collectionId', 'collectionName', 'artistName', 'artworkUrl', 'feedUrl')} for s in json.load(open(BK))['podcastSubscriptions']]
else:
    SUBS = [{'collectionId': 1000 + i, 'collectionName': 'Show %d with a fairly long name for wrapping' % i, 'artistName': 'Host %d' % i,
             'artworkUrl': 'https://img.example/%d.jpg' % i, 'feedUrl': 'https://feeds.example/%d' % i} for i in range(40)]
ids = [str(s['collectionId']) for s in SUBS]
RES = []
for i, sid in enumerate(ids):
    st = 'ads' if i in (3, 17) else 'chapters' if i in (5, 9, 30) else 'error' if i == 11 else 'none'
    RES.append({'id': sid, 'status': st, 'scanned': 10, 'withChapters': 0 if st in ('none', 'error') else 6, 'adChapters': 2 if st == 'ads' else 0, 'error': ''})
WANT = {g: sorted(SUBS[i]['collectionName'] for i, r in enumerate(RES) if r['status'] == g) for g in ('ads', 'chapters', 'none', 'error')}

class Q(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a): pass
srv = http.server.ThreadingHTTPServer(('127.0.0.1', PORT), functools.partial(Q, directory=root))
threading.Thread(target=srv.serve_forever, daemon=True).start()

def mock(native, mode):
    return """(function(){ var calls = window.__chCalls = [];
 var impl = { podcastChapterCheck: function(o){ calls.push(o); var mode = window.__chMode || %s;
     return new Promise(function(res, rej){ setTimeout(function(){ mode === 'fail' ? rej(new Error('x')) : res({ results: %s }); }, 900); }); },
   addListener: function(){ return Promise.resolve({ remove: function(){} }); } };
 var P = new Proxy({}, { get: function(t, k){ if(k === 'then') return undefined; if(k === 'setCarLibraryPart') return undefined; if(impl[k]) return impl[k]; return function(){ return Promise.resolve({}); }; } });
 window.Capacitor = { isNativePlatform: function(){ return %s; }, getPlatform: function(){ return 'android'; }, registerPlugin: function(){ return P; }, Plugins: { AmplifyPlayer: P }, convertFileSrc: function(u){ return u; } };
})();""" % (json.dumps(mode), json.dumps(RES), 'true' if native else 'false')

fails = []
def check(c, m):
    print(('PASS ' if c else 'FAIL ') + m)
    if not c: fails.append(m)

async def route(r):
    u = r.request.url
    if '127.0.0.1' in u: return await r.continue_()
    if any(x in u for x in ('mzstatic', 'img.example', '.jpg', '.png')):
        return await r.fulfill(status=200, content_type='image/jpeg', body=COVER)
    return await r.abort()

async def page(b, scheme, native=True, subs=SUBS, mode='ok'):
    ctx = await b.new_context(viewport={'width': 327, 'height': 690}, device_scale_factor=3.3, is_mobile=True, has_touch=True, color_scheme=scheme)
    await ctx.add_init_script(mock(native, mode))
    await ctx.add_init_script("try{ localStorage.setItem('radioPlayerTheme', %s); localStorage.setItem('radioPlayerPodcastSubs', %s); localStorage.setItem('radioPlayerLtvAuto','0'); }catch(e){}"
                              % (json.dumps(scheme), json.dumps(json.dumps(subs))))
    pg = await ctx.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
    await pg.route('**/*', route)
    await pg.goto(f'http://127.0.0.1:{PORT}/index.html'); await pg.wait_for_timeout(2500)
    await pg.evaluate("__t.ev('closeNotice(); openSettings(); showSettingsCat(\\'playback\\')')"); await pg.wait_for_timeout(600)
    return ctx, pg, errs

VIS = "(id)=>{var e=document.getElementById(id); if(!e) return false; var r=e.getBoundingClientRect(); return getComputedStyle(e).display!=='none' && !e.hidden && r.height>0;}"
GROUPS = """()=>{var o={}; document.querySelectorAll('#chapterGroups .cl-list').forEach(function(l){ o[l.dataset.chGroup]=Array.from(l.querySelectorAll('.cl-name')).map(function(n){return n.textContent;}); }); return o;}"""
LAYOUT = """()=>{var bad=[]; var vw=document.documentElement.clientWidth;
  document.querySelectorAll('#chapterGroups .cl-item').forEach(function(r){ var n=r.querySelector('.cl-name'), a=r.querySelector('.cl-art'); var rn=n.getBoundingClientRect(), ra=a.getBoundingClientRect();
    if(rn.right>vw+0.5||ra.right>rn.left+0.5) bad.push('overlap '+n.textContent);
    if(n.scrollWidth>n.clientWidth+1) bad.push('cut '+n.textContent); });
  var gaps=[]; document.querySelectorAll('#chapterGroups .set-sub').forEach(function(h){ var nx=h.nextElementSibling; if(nx) gaps.push(Math.round(nx.getBoundingClientRect().top-h.getBoundingClientRect().bottom)); });
  return {bad:bad, gaps:gaps, hscroll: document.getElementById('settingsPanel').scrollWidth > document.getElementById('settingsPanel').clientWidth+1};}"""

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        for scheme in ('dark', 'light'):
            T = f'[{scheme}]'
            ctx, pg, errs = await page(b, scheme)
            check(await pg.evaluate(VIS, 'chapterCheckBtn'), T + ' Podcast chapters row shows in the app')
            check(await pg.evaluate("()=>!document.getElementById('chapterSub').hidden"), T + ' Podcasts heading shows')
            await pg.screenshot(path=f'{shots}/ch_playback_{scheme}.png')
            await pg.tap('#chapterCheckBtn'); await pg.wait_for_timeout(300)
            st = await pg.evaluate("__notice.state()")
            check(st and st['kind'] == 'working', T + ' working notice while checking')
            await pg.screenshot(path=f'{shots}/ch_working_{scheme}.png')
            await pg.wait_for_timeout(1200)
            calls = await pg.evaluate("window.__chCalls")
            check(len(calls) == 1 and len(calls[0]['shows']) == len(SUBS) and all(s['feedUrl'] for s in calls[0]['shows']), T + f' one call with all {len(SUBS)} shows and their feeds')
            check(not await pg.evaluate("document.getElementById('noticeOverlay').classList.contains('open')"), T + ' notice closed when done')
            check(await pg.evaluate("__t.ev('settingsCat')") == 'chapters', T + ' results page open')
            title = await pg.evaluate("document.getElementById('settingsTitle').textContent")
            check(title == 'Podcast chapters', T + ' title ' + title)
            g = await pg.evaluate(GROUPS)
            check(list(g.keys()) == ['ads', 'chapters', 'none', 'error'], T + ' group order ' + str(list(g.keys())))
            for k in WANT: check(sorted(g.get(k, [])) == WANT[k], T + f' {k}: {len(g.get(k, []))} shows')
            lead = await pg.evaluate("document.getElementById('chapterLead').textContent")
            check(lead.startswith('2 of your shows mark their ad breaks'), T + ' lead: ' + lead)
            lay = await pg.evaluate(LAYOUT)
            check(not lay['bad'], T + ' no cut-off or overlapping rows ' + str(lay['bad'][:3]))
            check(len(set(lay['gaps'])) == 1, T + ' same gap under every heading ' + str(lay['gaps']))
            check(not lay['hscroll'], T + ' no sideways scroll')
            await pg.screenshot(path=f'{shots}/ch_results_{scheme}.png')
            await pg.evaluate("document.getElementById('settingsPanel').scrollTop = document.querySelector('[data-ch-group=\"none\"]').offsetTop - 80"); await pg.wait_for_timeout(300)
            await pg.screenshot(path=f'{shots}/ch_results_mid_{scheme}.png')
            await pg.evaluate("document.getElementById('settingsPanel').scrollTop = 1e6"); await pg.wait_for_timeout(300)
            await pg.screenshot(path=f'{shots}/ch_results_end_{scheme}.png')
            check(await pg.evaluate(VIS, 'chapterAgainBtn'), T + ' Check again button at the end')
            await pg.tap('#chapterAgainBtn'); await pg.wait_for_timeout(1500)
            check(len(await pg.evaluate("window.__chCalls")) == 2, T + ' Check again runs it again')
            await pg.tap('#settingsCloseBtn'); await pg.wait_for_timeout(400)
            check(await pg.evaluate("__t.ev('settingsCat')") == 'playback', T + ' back returns to Playback')
            check(not errs, T + ' no page errors ' + str(errs[:2]))
            await ctx.close()
        # failure
        ctx, pg, errs = await page(b, 'dark', mode='fail')
        await pg.tap('#chapterCheckBtn'); await pg.wait_for_timeout(1500)
        st = await pg.evaluate("__notice.state()")
        check(st and st['kind'] == 'error', 'failure shows an error notice')
        await pg.screenshot(path=f'{shots}/ch_error.png')
        await ctx.close()
        # no podcasts
        ctx, pg, errs = await page(b, 'dark', subs=[])
        await pg.tap('#chapterCheckBtn'); await pg.wait_for_timeout(500)
        st = await pg.evaluate("__notice.state()")
        check(st and st['kind'] == 'info' and not await pg.evaluate("window.__chCalls.length"), 'no podcasts: info notice, no check')
        await ctx.close()
        # not the app
        ctx, pg, errs = await page(b, 'dark', native=False)
        check(not await pg.evaluate(VIS, 'chapterCheckBtn'), 'row hidden outside the app')
        check(await pg.evaluate("()=>document.getElementById('chapterSub').hidden"), 'heading hidden outside the app')
        await ctx.close()
        await b.close()
    print('ALL PASS' if not fails else f'{len(fails)} FAILED')
    if fails: raise SystemExit(1)
asyncio.run(main())
