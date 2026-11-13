"""Build 595: the sideways Now Playing, layout A (beside the rail): cover left, details/controls right,
nothing overlapping, everything on screen; queue panel half the screen. Both themes, two phone sizes, big text.
Run: python3 tests/test_npl.py (screenshots in /tmp/claude-0/t/shots/npl-*)"""
import sys as _nsys, os as _nos; _nsys.path.insert(0, _nos.path.dirname(_nos.path.abspath(__file__))); from notice_auto import AUTO_NOTICE
import asyncio, os, json
HERE = os.path.dirname(os.path.abspath(__file__))
src = open(os.path.join(HERE, 'test_cf_after_video.py')).read()
head = src[:src.index('fails = []')]
head = head.replace("'/tmp/claude-0/t/srv_cfv'", "'/tmp/claude-0/t/srv_npl'").replace('8848', '8851')
exec(head)
from playwright.async_api import async_playwright
fails = []
def check(c, m):
    print(('PASS ' if c else 'FAIL ') + m)
    if not c: fails.append(m)
GEO = """(()=>{ function r(q){ var e = typeof q==='string' ? document.querySelector(q) : q; if(!e) return null; var cs=getComputedStyle(e); if(cs.display==='none'||cs.visibility==='hidden') return null; var b = e.getBoundingClientRect(); if(!b.width) return null; return [Math.round(b.left), Math.round(b.top), Math.round(b.right), Math.round(b.bottom)]; }
  var ids = ['#npBackBtn','#nplFrom','.np-menu-wrap','#npName','#nowPlayingScreen .np-sub','#npSeek','#nplShuffleBtn','#npPrevBtn','#npPlayBtn','#npNextBtn','#nplQueueBtn','#npFavBtn','#nplLyricsBtn','#nplAddBtn','#nplSleepBtn','#npArt','#mobileNav','.sidebar-top .hamburger-btn'];
  var o = {}; ids.forEach(function(i){ o[i] = r(i); });
  return { g:o, npl: document.body.classList.contains('npl'), rot: document.body.classList.contains('rotate-lock'), vw: innerWidth, vh: innerHeight }; })()"""
def overlap(a, b): return a and b and a[0] < b[2] - 1 and b[0] < a[2] - 1 and a[1] < b[3] - 1 and b[1] < a[3] - 1
CASES = [('dark', (678, 297), False), ('light', (678, 297), False), ('dark', (700, 310), False), ('dark', (891, 411), False)]  # Mark's S26 Ultra sideways is ~678x297 CSS px at dpr ~3.3
if os.environ.get('ONLY'): CASES = CASES[:int(os.environ['ONLY'])]
ZOOM = """(()=>{ var els = Array.from(document.querySelectorAll('body *')); var fs = els.map(function(e){ return parseFloat(getComputedStyle(e).fontSize); });
  els.forEach(function(e, i){ if(fs[i]) e.style.setProperty('font-size', (fs[i] * 1.3) + 'px', 'important'); }); })()"""
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
        for theme, size, big in CASES:
            ctx = await b.new_context(viewport={'width': 390, 'height': 844}, device_scale_factor=3.3, is_mobile=True, has_touch=True, color_scheme=theme)
            await ctx.add_init_script(MOCK); await ctx.add_init_script(AUTO_NOTICE)
            await ctx.add_init_script("localStorage.setItem('radioPlayerTheme', '%s')" % theme)
            pg = await ctx.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
            await pg.goto(f'http://127.0.0.1:{PORT}/index.html'); await pg.wait_for_timeout(2500)
            await pg.evaluate("""(function(){ var ov=document.getElementById('addMusicOverlay'); if(ov) ov.classList.add('open');
              var btn=document.getElementById('addMusicFolderBtn'); btn.disabled=false; btn.click(); })()""")
            for _ in range(60):
                await pg.wait_for_timeout(500)
                if await pg.evaluate("(js)=>window.__h.ev(js)", 'libraryTracks.length') >= len(files): break
            await pg.evaluate("(js)=>window.__h.ev(js)", "runLibrarySection('songs'); 1"); await pg.wait_for_timeout(800)
            await pg.tap('#stationsGrid .song-row:not(.shuffle-all-row)'); await pg.wait_for_timeout(1200)
            await pg.evaluate("document.body.classList.add('cast-avail'); var cb=document.querySelector('.sidebar-top .cast-btn'); if(cb) cb.hidden=false;")
            await pg.set_viewport_size({'width': size[0], 'height': size[1]}); await pg.wait_for_timeout(1200)
            await pg.evaluate("document.getElementById('playerNowTrigger').click()"); await pg.wait_for_timeout(1500)
            if big: await pg.evaluate(ZOOM); await pg.wait_for_timeout(300)
            T = '[%s %dx%d%s]' % (theme, size[0], size[1], ' big' if big else '')
            r = await pg.evaluate(GEO); g = r['g']
            await pg.screenshot(path='/tmp/claude-0/t/shots/npl-%s-%d%s.png' % (theme, size[0], '-big' if big else ''))
            check(r['npl'] and not r['rot'], T + ' layout A on %s' % r)
            vis = {k: v for k, v in g.items() if v}
            off = [k for k, v in vis.items() if v[0] < 0 or v[1] < 0 or v[2] > r['vw'] + 1 or v[3] > r['vh'] + 1]
            check(not off, T + ' everything on screen %s' % off)
            keys = [k for k in vis if k not in ('#mobileNav',)]
            ov = [(a, c) for i, a in enumerate(keys) for c in keys[i+1:] if overlap(vis[a], vis[c]) and not ({a, c} <= {'#mobileNav', '.sidebar-top .hamburger-btn'})]
            check(not ov, T + ' nothing overlaps %s' % ov)
            for k in ('#npArt', '#npName', '#npPlayBtn', '#npSeek', '#nplLyricsBtn', '#npFavBtn', '.sidebar-top .hamburger-btn', '#npBackBtn', '.np-menu-wrap'):
                check(bool(g[k]), T + ' shows ' + k)
            art = g['#npArt']; check(art and abs((art[2]-art[0]) - (art[3]-art[1])) <= 2 and art[0] >= 76, T + ' square cover beside the rail %s' % art)
            # menu opens on screen
            await pg.evaluate("document.getElementById('npMenuBtn').click()"); await pg.wait_for_timeout(500)
            m = await pg.evaluate("(()=>{ var e=document.getElementById('npMenu'); var b=e.getBoundingClientRect(); return [Math.round(b.left),Math.round(b.top),Math.round(b.right),Math.round(b.bottom), getComputedStyle(e).display]; })()")
            await pg.screenshot(path='/tmp/claude-0/t/shots/npl-menu-%s-%d%s.png' % (theme, size[0], '-big' if big else ''))
            check(m[0] >= 0 and m[1] >= 0 and m[2] <= size[0] + 1 and m[3] <= size[1] + 1, T + ' menu on screen %s' % m)
            await pg.keyboard.press('Escape'); await pg.mouse.click(size[0] - 10, size[1] - 10); await pg.wait_for_timeout(400)
            await pg.evaluate("document.getElementById('npMenu').classList.remove('open')")
            # queue: half the screen
            await pg.evaluate("document.getElementById('nplQueueBtn').click()"); await pg.wait_for_timeout(700)
            q = await pg.evaluate("(()=>{ var b=document.getElementById('queuePanel').getBoundingClientRect(); return [Math.round(b.left), Math.round(b.right), document.getElementById('queuePanel').classList.contains('open')]; })()")
            await pg.screenshot(path='/tmp/claude-0/t/shots/npl-queue-%s-%d%s.png' % (theme, size[0], '-big' if big else ''))
            check(q[2] and abs(q[0] - size[0] / 2) <= 2 and q[1] == size[0], T + ' queue fills the right half %s' % q)
            # a radio station: no seek bar, no shuffle, nothing overlapping
            await pg.evaluate("document.getElementById('queueCloseBtn') && document.getElementById('queueCloseBtn').click()"); await pg.wait_for_timeout(500)
            await pg.evaluate("(js)=>window.__h.ev(js)", "playEntity({name:'Test FM Radio With A Rather Long Station Name', url:'http://r.example/a.mp3', url_resolved:'http://r.example/a.mp3', urlToResolve:'http://r.example/a.mp3', stationuuid:'tfm1', favicon:'', country:'Germany', codec:'AAC'}); 1"); await pg.wait_for_timeout(1500)
            r = await pg.evaluate(GEO); g = r['g']
            await pg.screenshot(path='/tmp/claude-0/t/shots/npl-station-%s-%d%s.png' % (theme, size[0], '-big' if big else ''))
            vis = {k: v for k, v in g.items() if v}
            ov = [(a, c) for i, a in enumerate(vis) for c in list(vis)[i+1:] if overlap(vis[a], vis[c]) and not ({a, c} <= {'#mobileNav', '.sidebar-top .hamburger-btn'})]
            check(r['npl'] and not ov and not g['#nplShuffleBtn'], T + ' station: layout A, nothing overlaps %s %s' % (ov, r['npl']))
            check(not errs, T + ' no page errors %s' % errs[:2])
            await ctx.close()
        await b.close()
    print('ALL PASSED' if not fails else 'FAILED %s' % fails)
    raise SystemExit(1 if fails else 0)
asyncio.run(main())
