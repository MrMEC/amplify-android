"""Build 138: in Immersive View the favourite, progress bar, three-dot menu and Up Next row fade
away (space kept, Play stays put) and Play / skip buttons take a bright version of the screen's
colour; the shade under the title (normal and immersive) is a dark version of that colour, not
black. Run: python3 tests/test_immersive_colors.py (screenshots in /tmp/claude-0/t/shots)"""
import asyncio, os, subprocess, colorsys, re
HERE = os.path.dirname(os.path.abspath(__file__))
src = open(os.path.join(HERE, 'test_station_skip.py')).read()
head = src[:src.index('async def main()')]
head = head.replace("'/tmp/claude-0/t/srv_skip'", "'/tmp/claude-0/t/srv_immcol'").replace('PORT = 8794', 'PORT = 8808')
head = head.replace('" skip: function(){', '" closeNp: function(){ closeNowPlaying(false, false); }, play: function(x){ playStation(x); }, skip: function(){')
head = head.replace('skip: function(){ return window.__skip; }', 'ui: function(b){ setPlayingUI(b); }, imm: function(b){ setNpImmersive(b); }, skip: function(){ return window.__skip; }')
assert 'closeNp' in head and 'setNpImmersive' in head
exec(head)
from playwright.async_api import async_playwright

def parse_rgb(s):
    m = re.match(r'rgba?\(([\d.]+),\s*([\d.]+),\s*([\d.]+)', s or '')
    if m: return tuple(float(x) for x in m.groups())
    m = re.match(r'color\(srgb ([\d.]+) ([\d.]+) ([\d.]+)', s or '')
    return tuple(round(float(x) * 255) for x in m.groups()) if m else None
def hue(rgb):
    h, l, s = colorsys.rgb_to_hls(*(c / 255 for c in rgb))
    return h * 360, s, l

ST = """(()=>{ function r(id){ var el = document.getElementById(id) || document.querySelector(id); if(!el) return null; var c = getComputedStyle(el), b = el.getBoundingClientRect();
    return { op: parseFloat(c.opacity), vis: c.visibility, pe: c.pointerEvents, shown: c.display !== 'none', x: Math.round(b.left + b.width / 2), y: Math.round(b.top) }; }
  var cs = getComputedStyle(document.getElementById('nowPlayingScreen'));
  var foot = getComputedStyle(document.querySelector('.np-hero-foot'), '::before');
  var probe = document.createElement('div'); document.body.appendChild(probe);
  function rgbOf(v){ probe.style.color = v; var x = getComputedStyle(probe).color; return x; }
  var out = { imm: document.body.classList.contains('np-immersive'),
    fav: r('npFavBtn'), menu: r('.now-playing-screen .np-menu-wrap'), seek: r('npSeek'), upnext: r('npUpNext'), play: r('npPlayBtn'),
    prev: r('npPrevBtn'), next: r('npNextBtn'),
    playBg: getComputedStyle(document.getElementById('npPlayBtn')).backgroundColor, playFg: getComputedStyle(document.getElementById('npPlayBtn')).color,
    nextFg: getComputedStyle(document.getElementById('npNextBtn')).color,
    tint: rgbOf(cs.getPropertyValue('--np-tint').trim()), shade: rgbOf(cs.getPropertyValue('--np-shade').trim()), vivid: rgbOf(cs.getPropertyValue('--np-vivid').trim()),
    footBg: foot.backgroundImage };
  probe.remove(); return out; })()"""


BAR = """(()=>{ var b = document.getElementById('playerBar'), r = b.getBoundingClientRect(), c = getComputedStyle(b), sh = document.getElementById('searchSheet'), sr = sh.getBoundingClientRect();
  return { top: Math.round(r.top), op: parseFloat(c.opacity), pe: c.pointerEvents, H: innerHeight, sheetTop: Math.round(sr.top), sheetOpen: sh.classList.contains('open') }; })()"""

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
        ctx = await b.new_context(viewport={'width': 412, 'height': 900}, device_scale_factor=2, is_mobile=True, has_touch=True, color_scheme='dark')
        await ctx.add_init_script(MOCK)
        # The phone's native request (CapacitorHttp): reads the cover with no cross-site rule.
        await ctx.add_init_script("""(function(){ var C = window.Capacitor; if(!C) return; C.Plugins = C.Plugins || {};
          C.Plugins.CapacitorHttp = { request: function(o){ window.__nativeReq = (window.__nativeReq || 0) + 1;
            var m = /covers\\.example\\/(.+)$/.exec(o.url); if(!m) return Promise.resolve({ status: 404, data: '' });
            return fetch('/' + m[1]).then(function(r){ return r.arrayBuffer(); }).then(function(b){ var u = new Uint8Array(b), s = '';
              for(var i = 0; i < u.length; i++) s += String.fromCharCode(u[i]); return { status: 200, data: btoa(s), headers: {} }; }); } }; })();""")
        pg = await ctx.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.route('**/*', lambda route: route.continue_() if '127.0.0.1' in route.request.url else route.abort())
        for name, spec in (('orange', 'color=c=0xE07020:s=300x300'), ('blue', 'color=c=0x2050D0:s=300x300'), ('pale', 'color=c=0xF4E9A0:s=300x300')):
            subprocess.run(['ffmpeg', '-loglevel', 'error', '-y', '-f', 'lavfi', '-i', spec, '-frames:v', '1', f'{root}/{name}.png'], check=True)
        async def covers(route):
            n = route.request.url.rsplit('/', 1)[1]
            await route.fulfill(status=200, content_type='image/png', body=open(f'{root}/{n}', 'rb').read())
        await pg.route('https://covers.example/**', covers)
        await pg.goto(f'http://127.0.0.1:{PORT}/index.html'); await pg.wait_for_timeout(2500)
        await pg.evaluate("""(function(){ var ov=document.getElementById('addMusicOverlay'); if(ov) ov.classList.add('open');
          var btn=document.getElementById('addMusicFolderBtn'); btn.disabled=false; btn.click(); })()""")
        for _ in range(60):
            await pg.wait_for_timeout(500)
            if len(await pg.evaluate('__t.tracks()')) >= 3: break
        await pg.evaluate('__t.setup()')

        STN = lambda n, cov: ("{ stationuuid: 'st-" + n + "', name: '" + n + "', url: 'http://radio.example/" + n + "', urlToResolve: 'http://radio.example/" + n
                              + "', favicon: 'http://covers.example/" + cov + ".png', tags: '' }")

        # ---- a song from a list, so the progress bar and Up Next both show ----
        await pg.evaluate("__t.songs(); setTimeout(function(){ document.querySelector('#stationsGrid .song-row:not(.shuffle-all-row)').click(); }, 300)")
        await pg.wait_for_timeout(1500)
        await pg.evaluate('__t.openNp()'); await pg.wait_for_timeout(900)
        await pg.evaluate('__t.ui(true)'); await pg.wait_for_timeout(300)
        s0 = await pg.evaluate(ST)
        print('song normal', {k: s0[k] for k in ('fav', 'menu', 'seek', 'upnext', 'play')})
        check(all(s0[k] and s0[k]['op'] == 1 and s0[k]['vis'] == 'visible' for k in ('fav', 'menu')) and s0['seek']['shown'] and s0['seek']['op'] == 1,
              'normal: favourite, menu and progress bar showing')
        has_upnext = bool(s0['upnext'] and s0['upnext']['shown'])
        print('up next shown', has_upnext)
        check(parse_rgb(s0['playBg']) == parse_rgb(s0['vivid']) and parse_rgb(s0['nextFg']) == parse_rgb(s0['vivid']), f"normal: Play and skip already in the bright colour ({s0['playBg']} {s0['nextFg']} {s0['vivid']})")
        cols = await pg.evaluate("""(()=>{ var q = function(s){ return getComputedStyle(document.querySelector(s)); };
          return { fav: q('#npFavBtn').color, menu: q('#npMenuBtn').color, seek: q('#npSeekRange').backgroundImage, upnext: q('#npUpNext').backgroundColor,
            nav: q('.mobile-nav-btn.active').color, navKey: document.querySelector('.mobile-nav-btn.active').dataset.nav }; })()""")
        print('colours', cols)
        v = parse_rgb(s0['vivid'])
        check(parse_rgb(cols['fav']) == v and parse_rgb(cols['menu']) == v, f"favourite and menu in the bright colour {cols['fav']} {cols['menu']}")
        sg = re.findall(r'rgba?\([^)]*\)', cols['seek'])
        check(sg and parse_rgb(sg[0]) == v, f"progress bar's played part in the bright colour {cols['seek'][:120]}")
        up = re.match(r'rgba?\(([\d.]+),\s*([\d.]+),\s*([\d.]+),\s*([\d.]+)', cols['upnext']) or re.match(r'color\(srgb ([\d.]+) ([\d.]+) ([\d.]+) / ([\d.]+)', cols['upnext'])
        print('upnext', cols['upnext'])
        check(up and abs(float(up.group(4)) - 0.24) < 0.02, f"Up Next row: the colour, lighter (24%) ({cols['upnext']})")
        bar = await pg.evaluate(BAR)
        check(bar['top'] >= bar['H'] and bar['op'] == 0 and bar['pe'] == 'none', f'mini player slid off the bottom while Now Playing is open {bar}')
        more = await pg.evaluate("""(()=>({ head: getComputedStyle(document.querySelector('.now-playing-screen .np-related-heading')).color,
          headText: document.querySelector('.now-playing-screen .np-related-heading').textContent,
          dots: Array.from(document.querySelectorAll('.now-playing-screen .row-more-btn, .now-playing-screen .tile-more')).filter(function(b){ return b.offsetParent; }).map(function(b){ return getComputedStyle(b).color; }),
          label: getComputedStyle(document.getElementById('npUpNextLabel') || document.querySelector('.np-upnext-label')).color }))()""")
        print('more from', more)
        check(parse_rgb(more['head']) == v and more['headText'], f"'{more['headText']}' heading in the colour {more['head']}")
        check(more['dots'] and all(parse_rgb(d) == v for d in more['dots']), f"every three-dot button in the list in the colour ({len(more['dots'])}) {more['dots'][:3]}")
        check(parse_rgb(more['label']) == v, f"Up Next's 'Next' label in the colour {more['label']}")
        top = await pg.evaluate("""(()=>({ back: getComputedStyle(document.getElementById('npBackBtn')).color,
          ham: getComputedStyle(document.querySelector('.sidebar-top .hamburger-btn span')).backgroundColor }))()""")
        check(parse_rgb(top['back']) == v and parse_rgb(top['ham']) == v, f"close (top left) and menu (top right) in the colour {top}")
        check(parse_rgb(cols['nav']) == v, f"tab bar's selected icon ({cols['navKey']}) in the bright colour while Now Playing is open {cols['nav']}")
        await pg.evaluate("(()=>{ var ic = document.getElementById('importPanelClose'); if(ic) ic.click(); var r = document.getElementById('npSeekRange'); r.value = 400; r.dispatchEvent(new Event('input')); })()"); await pg.wait_for_timeout(300)
        await pg.screenshot(path=f'{shots}/immcol-song-normal.png')
        await pg.evaluate('__t.imm(true)'); await pg.wait_for_timeout(900)
        s1 = await pg.evaluate(ST)
        print('song imm', {k: s1[k] for k in ('fav', 'menu', 'seek', 'upnext', 'play', 'playBg', 'nextFg', 'vivid')})
        gone = [k for k in ('fav', 'menu', 'seek') + (('upnext',) if has_upnext else ()) if not (s1[k]['op'] == 0 and s1[k]['vis'] == 'hidden' and s1[k]['pe'] == 'none')]
        check(not gone, f'immersive: favourite, menu, progress bar and Up Next faded and untappable (not: {gone})')
        check(s1['play']['x'] == s0['play']['x'], f"Play stays in place ({s0['play']['x']} -> {s1['play']['x']})")
        check(parse_rgb(s1['playBg']) == parse_rgb(s1['vivid']) and parse_rgb(s1['nextFg']) == parse_rgb(s1['vivid']),
              f"immersive: Play and skip still the artwork colour {s1['playBg']} {s1['nextFg']} {s1['vivid']}")
        await pg.screenshot(path=f'{shots}/immcol-song-imm.png')
        tr = await pg.evaluate("""(()=>({ play: getComputedStyle(document.getElementById('npPlayBtn')).backgroundColor, next: getComputedStyle(document.getElementById('npNextBtn')).color }))()""")
        print('immersive see-through', tr)
        alpha = lambda c: float((re.search(r'/\s*([\d.]+)\)', c) or re.search(r'rgba\([^,]+,[^,]+,[^,]+,\s*([\d.]+)', c)).group(1))
        check(parse_rgb(tr['play']) == parse_rgb(s1['vivid']) and 'color(' not in tr['play'] and '/ ' not in tr['next'], f"Immersive View: Play and skip solid, as in the normal view {tr}")
        await pg.evaluate('__t.imm(false)'); await pg.wait_for_timeout(900)
        s2 = await pg.evaluate(ST)
        check(s2['fav']['op'] == 1 and s2['seek']['op'] == 1 and parse_rgb(s2['playBg']) == parse_rgb(s2['vivid']), 'leaving immersive brings them back, still coloured')

        # ---- coloured covers: the colours follow the artwork ----
        for name, want_h in (('orange', 26), ('blue', 224), ('pale', 52)):
            await pg.evaluate("__t.play(" + STN('Radio ' + name, name) + ")"); await pg.wait_for_timeout(1200)
            await pg.evaluate('__t.ui(true)'); await pg.wait_for_timeout(300)
            n = await pg.evaluate(ST)
            print('art', await pg.evaluate("(()=>{ var i = document.querySelector('#npArt img'); return i ? [i.src.slice(0,80), i.complete, i.naturalWidth, i.crossOrigin] : null; })()"), await pg.evaluate("document.getElementById('npName') ? document.getElementById('npName').textContent : ''"))
            th, ts, tl = hue(parse_rgb(n['tint'])); sh, ss, sl = hue(parse_rgb(n['shade'])); vh, vs, vl = hue(parse_rgb(n['vivid']))
            print(name, 'tint', round(th), round(ts, 2), round(tl, 2), 'shade', round(sh), round(ss, 2), round(sl, 2), 'vivid', round(vh), round(vs, 2), round(vl, 2))
            close = lambda a, b2: min(abs(a - b2), 360 - abs(a - b2)) <= 18
            check(close(th, want_h), f'[{name}] tint follows the cover (hue {round(th)} ~ {want_h})')
            check(close(sh, th) and sl < tl and ss >= 0.2, f'[{name}] shade: same hue, darker than the background, not grey (h {round(sh)} s {ss:.2f} l {sl:.2f})')
            check(close(vh, th) and vl > 0.55 and vs >= 0.5, f'[{name}] bright colour: same hue, light and saturated (h {round(vh)} s {vs:.2f} l {vl:.2f})')
            check('color-mix' in n['footBg'] or 'rgb' in n['footBg'], f'[{name}] the title shade is built from the colour ({n["footBg"][:90]})')
            # the shade pixel under the title is coloured, not grey
            await pg.screenshot(path=f'{shots}/immcol-{name}-normal.png')
            await pg.evaluate('__t.imm(true)'); await pg.wait_for_timeout(1200)
            await pg.screenshot(path=f'{shots}/immcol-{name}-imm.png')
            from PIL import Image
            import io
            im = Image.open(io.BytesIO(await pg.screenshot())).convert('RGB')
            px = await pg.evaluate("(()=>{ var b = document.getElementById('npPlayBtn').getBoundingClientRect(); return [Math.round(b.left + 8), Math.round(b.top + b.height / 2)]; })()")
            c = im.getpixel((px[0] * 2, px[1] * 2))
            ph, ps, pl = hue(c)
            check(close(ph, th) and ps > 0.4, f'[{name}] Play button pixels are the artwork colour on screen {c}')
            await pg.evaluate('__t.imm(false)'); await pg.wait_for_timeout(600)

        # ---- the search box opened from the tab bar over Now Playing ----
        await pg.evaluate("document.querySelector('.mobile-nav-btn[data-nav=search]').click()"); await pg.wait_for_timeout(500)
        go = await pg.evaluate("(()=>{ var c = getComputedStyle(document.getElementById('searchSheetGo')); return [c.backgroundColor, document.body.classList.contains('np-open'), getComputedStyle(document.getElementById('searchSheet')).display]; })()")
        vv = parse_rgb((await pg.evaluate(ST))['vivid'])
        check(go[1] and parse_rgb(go[0]) == vv, f'search button in the colour while Now Playing is open {go}')
        await pg.screenshot(path=f'{shots}/immcol-search.png')
        bar = await pg.evaluate(BAR)
        print('bar with search open over Now Playing', bar)
        check(bar['sheetOpen'] and bar['sheetTop'] < bar['H'] - 60 and bar['top'] >= bar['H'] and bar['op'] == 0, f'Search rises in from the tab bar; the mini player stays down {bar}')
        await pg.evaluate("document.getElementById('searchSheetClose').click()"); await pg.wait_for_timeout(700)
        bar = await pg.evaluate(BAR)
        check(bar['top'] >= bar['H'] and bar['op'] == 0 and bar['pe'] == 'none', f'closing Search on Now Playing does not bring the mini player back {bar}')
        await pg.screenshot(path=f'{shots}/immcol-search-closed.png')
        # ---- closing Now Playing: the tab bar's colour goes back ----
        await pg.evaluate('__t.imm(false)'); await pg.wait_for_timeout(300)
        await pg.evaluate('__t.closeNp()'); await pg.wait_for_timeout(900)
        back = await pg.evaluate("(()=>{ var p = document.createElement('div'); p.style.color = getComputedStyle(document.body).getPropertyValue('--accent'); document.body.appendChild(p); var a = getComputedStyle(p).color; p.remove(); return [getComputedStyle(document.querySelector('.mobile-nav-btn.active')).color, a]; })()")
        check(back[0] == back[1], f'after closing Now Playing the selected tab is the app colour again {back}')
        bar = await pg.evaluate(BAR)
        check(bar['top'] < bar['H'] - 60 and bar['op'] == 1 and bar['pe'] != 'none', f'the mini player slides back up once Now Playing closes {bar}')
        fr = await pg.evaluate("""new Promise(function(res){ var b = document.getElementById('playerBar'), out = [], t0 = performance.now(); __t.openNp();
          (function f(){ out.push(Math.round(b.getBoundingClientRect().top)); if(performance.now() - t0 < 700) requestAnimationFrame(f); else res(out); })(); })""")
        mids = [t for t in fr if fr[0] + 6 < t < fr[-1] - 6]
        print('bar frames opening Now Playing', fr[:3], fr[-2:], len(mids))
        check(len(mids) >= 4 and fr[-1] >= 900, f'the mini player slides down (not a jump) as Now Playing opens ({len(mids)} in-between frames)')
        await pg.evaluate('__t.closeNp()'); await pg.wait_for_timeout(900)
        await pg.evaluate("document.querySelector('.mobile-nav-btn[data-nav=search]').click()"); await pg.wait_for_timeout(500)
        go2 = await pg.evaluate("(()=>{ var p = document.createElement('div'); p.style.color = getComputedStyle(document.body).getPropertyValue('--accent'); document.body.appendChild(p); var a = getComputedStyle(p).color; p.remove(); return [getComputedStyle(document.getElementById('searchSheetGo')).backgroundColor, a]; })()")
        check(go2[0] == go2[1], f'search button back to the app colour away from Now Playing {go2}')
        await pg.evaluate("document.getElementById('searchSheetClose').click()"); await pg.wait_for_timeout(400)
        await pg.screenshot(path=f'{shots}/immcol-closed.png')
        await pg.evaluate('__t.openNp()'); await pg.wait_for_timeout(900)
        # ---- a menu open when entering immersive closes ----
        await pg.evaluate("document.getElementById('npMenuBtn').click()"); await pg.wait_for_timeout(200)
        await pg.evaluate('__t.imm(true)'); await pg.wait_for_timeout(500)
        check(not await pg.evaluate("document.getElementById('npMenu').classList.contains('open')"), 'an open menu closes on entering Immersive View')
        check(not errs, f'no page errors {errs[:3]}')
        await b.close()
    srv.shutdown()
    print('FAILS:', len(fails) if isinstance(fails, list) else fails)

asyncio.run(main())
