"""Build 265: the welcome tour, Top 100 as two rows, empty Home rows hidden, Artist radio in Library.

- Top 100 on Home is two rows of covers in one sideways scroller (1 over 2, 3 over 4, ...), so both
  rows move together.
- A first-time listener's Home has no Favorites, Continue Listening or My Stations rows while they
  are empty; they appear once there is something in them.
- The tour opens by itself at launch, steps through the features (a ring around the tab or button a
  step is about when it is on screen), comes back at the next launch after the X, and stops coming
  back after "Don't show this again" or Done. Settings > Show the tour opens it any time.
- The tour's Library card and Settings > Artist radio in Library choose whether the directory's
  artist stations (station-only artists) are listed in Library > Artists.
Run: python3 tests/test_tour_home.py (screenshots in /tmp/claude-0/t/shots)"""
import sys as _nsys, os as _nos; _nsys.path.insert(0, _nos.path.dirname(_nos.path.abspath(__file__))); from notice_auto import AUTO_NOTICE
import asyncio, os, json, threading, http.server, functools, shutil, re, sys
from urllib.parse import urlparse, parse_qs
from playwright.async_api import async_playwright

PORT = 8830
root = '/tmp/claude-0/t/srv_tour'
OUT = '/tmp/claude-0/t/shots'
os.makedirs(OUT, exist_ok=True)
shutil.rmtree(root, ignore_errors=True); os.makedirs(root)
HOOK = "window.__h = { ev: function(js){ return eval(js); } };\n"
src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'www', 'index.html')).read()
mark = '  var coverFlow = null;\n'
assert src.count(mark) == 1
open(root + '/index.html', 'w').write(src.replace(mark, mark + HOOK))
class Q(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a): pass
srv = http.server.ThreadingHTTPServer(('127.0.0.1', PORT), functools.partial(Q, directory=root))
threading.Thread(target=srv.serve_forever, daemon=True).start()

CHART = {'date': '2026-10-17', 'data': [{'song': 'Song %03d' % (i + 1), 'artist': 'Artist %d' % (i % 7), 'this_week': i + 1,
         'last_week': i + 1, 'peak_position': 1, 'weeks_on_chart': 3} for i in range(100)]}
EXCL = [{'name': 'Exclusively ' + a, 'url_resolved': 'http://s/ex-' + a, 'stationuuid': 'ex-' + a, 'favicon': '', 'tags': 'rock', 'codec': 'MP3'}
        for a in ('Zed', 'Yolanda', 'Xavier')]

async def route(r):
    u = r.request.url
    p = urlparse(u)
    if p.netloc.startswith('127.0.0.1') or u.startswith('data:'):
        return await r.continue_()
    if p.netloc in ('raw.githubusercontent.com', 'cdn.jsdelivr.net'):
        if p.path.endswith('/recent.json'):
            return await r.fulfill(status=200, content_type='application/json', headers={'Access-Control-Allow-Origin': '*'}, body=json.dumps(CHART))
        if p.path.endswith('/valid_dates.json'):
            return await r.fulfill(status=200, content_type='application/json', headers={'Access-Control-Allow-Origin': '*'}, body=json.dumps(['2026-10-17']))
        return await r.fulfill(status=404, body='nope')
    if '/json/stations/search' in u:
        q = parse_qs(p.query)
        if q.get('name', [''])[0] == 'exclusively':
            return await r.fulfill(status=200, content_type='application/json', headers={'Access-Control-Allow-Origin': '*'}, body=json.dumps(EXCL))
        return await r.fulfill(status=200, content_type='application/json', headers={'Access-Control-Allow-Origin': '*'}, body=json.dumps(
            [{'name': 'Top %d' % i, 'url_resolved': 'http://s/top%d' % i, 'stationuuid': 'top%d' % i, 'favicon': '', 'tags': 'pop', 'countrycode': 'US', 'codec': 'MP3'} for i in range(8)]))
    return await r.abort()

fails = []
def check(c, m):
    print(('PASS ' if c else 'FAIL ') + m)
    if not c: fails.append(m)

TOUR_ON = "try{ localStorage.setItem('amplifyTourTest', '1'); }catch(e){}"
BIG = """(function(){ var st = document.createElement('style'); st.textContent = 'html{ -webkit-text-size-adjust:135%; }';
  document.addEventListener('DOMContentLoaded', function(){
    document.querySelectorAll('*').forEach(function(){});
    var fs = []; for(var i = 0; i < document.styleSheets.length; i++){ try{ fs.push(document.styleSheets[i]); }catch(e){} }
    fs.forEach(function(sh){ try{ Array.prototype.forEach.call(sh.cssRules, function(r){ if(r.style && r.style.fontSize && /px$/.test(r.style.fontSize)) r.style.fontSize = (parseFloat(r.style.fontSize) * 1.35) + 'px'; }); }catch(e){} });
  }); })();"""

async def tour_state(pg):
    return await pg.evaluate("""(()=>{ const o = document.getElementById('tourOverlay'), s = document.getElementById('tourSpot');
      const r = s.getBoundingClientRect(), p = document.getElementById('tourPanel').getBoundingClientRect();
      return { open: o.classList.contains('open'), spot: o.classList.contains('spotlit'), count: document.getElementById('tourCount').textContent,
        title: document.getElementById('tourTitle').textContent, next: document.getElementById('tourNext').textContent,
        rect: [r.left, r.top, r.width, r.height], panel: [p.left, p.top, p.right, p.bottom], never: !document.getElementById('tourNever').hidden,
        choice: !!document.querySelector('#tourExtra .tour-choice') }; })()""")

async def main():
    async with async_playwright() as pw:
        b = await pw.chromium.launch()
        ctx = await b.new_context(viewport={'width': 412, 'height': 900}, device_scale_factor=2, is_mobile=True, has_touch=True, locale='en-US')
        await ctx.route('**/*', route)
        await ctx.add_init_script(AUTO_NOTICE)
        await ctx.add_init_script(TOUR_ON)
        pg = await ctx.new_page(); errs = []
        pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.goto(f'http://127.0.0.1:{PORT}/index.html')
        await pg.wait_for_timeout(600)
        check(not await pg.evaluate("document.getElementById('tourOverlay').classList.contains('open')"), 'tour waits a moment after launch')
        await pg.wait_for_timeout(2400)

        # ---- the tour opens by itself
        t = await tour_state(pg)
        check(t['open'] and t['count'] == '1 of 15' and t['title'] == 'Welcome to Amplify' and t['next'] == 'Start' and not t['spot'], f'tour opens at launch on the welcome card {t}')
        vw = await pg.evaluate('innerWidth'); vh = await pg.evaluate('innerHeight')
        check(t['panel'][0] >= 16 and t['panel'][2] <= vw - 16 and t['panel'][1] >= 0 and t['panel'][3] <= vh, f'tour card fits the screen {t["panel"]}')
        await pg.screenshot(path=f'{OUT}/tour-1-welcome.png')

        # ---- empty Home rows hidden behind it; Top 100 two rows
        await pg.evaluate("window.__amplifyTour.close(false)")
        home = await pg.evaluate("""(()=>{ const d = id => getComputedStyle(document.getElementById(id)).display;
          const g = document.getElementById('top100HomeGrid'); const t = [...g.querySelectorAll('.tile')].map(e => e.getBoundingClientRect());
          return { fav: d('favoritesSection'), recent: d('recentSection'), mine: d('forYouSection'), top: d('top100Section'),
            gd: getComputedStyle(g).display, n: t.length, t0: t[0] && [t[0].left, t[0].top, t[0].width], t1: t[1] && [t[1].left, t[1].top],
            t2: t[2] && [t[2].left, t[2].top], sw: g.scrollWidth, cw: g.clientWidth }; })()""")
        print(home)
        check(home['fav'] == 'none' and home['recent'] == 'none' and home['mine'] == 'none', f'first-time Home hides empty Favorites, Continue Listening, My Stations {home}')
        check(home['top'] != 'none' and home['gd'] == 'grid' and home['n'] == 20, 'Top 100 shows 20 covers in a grid')
        check(abs(home['t0'][0] - home['t1'][0]) < 1 and home['t1'][1] > home['t0'][1] + home['t0'][2] * 0.9, 'Top 100: #2 sits under #1 (two rows)')
        check(abs(home['t2'][1] - home['t0'][1]) < 1 and home['t2'][0] > home['t0'][0] + 50, 'Top 100: #3 sits right of #1')
        check(home['sw'] > home['cw'] + 300, 'Top 100 rows run on sideways')
        await pg.evaluate("document.getElementById('top100Section').scrollIntoView({block:'start'}); window.scrollBy(0, -80)")
        await pg.wait_for_timeout(500)
        await pg.screenshot(path=f'{OUT}/tour-top100-two-rows.png')
        # one swipe moves both rows
        g = await pg.evaluate("(()=>{ const r = document.getElementById('top100HomeGrid').getBoundingClientRect(); return [r.left, r.top, r.width, r.height]; })()")
        y = g[1] + g[3] * 0.25
        cdp = await ctx.new_cdp_session(pg)
        await cdp.send('Input.dispatchTouchEvent', {'type': 'touchStart', 'touchPoints': [{'x': 300, 'y': y}]})
        for i in range(1, 13):
            await cdp.send('Input.dispatchTouchEvent', {'type': 'touchMove', 'touchPoints': [{'x': 300 - i * 18, 'y': y}]})
            await pg.wait_for_timeout(16)
        await cdp.send('Input.dispatchTouchEvent', {'type': 'touchEnd', 'touchPoints': []})
        await pg.wait_for_timeout(900)
        moved = await pg.evaluate("""(()=>{ const t = [...document.querySelectorAll('#top100HomeGrid .tile')].map(e => e.getBoundingClientRect().left);
          return { sl: document.getElementById('top100HomeGrid').scrollLeft, a: t[0], b: t[1] }; })()""")
        check(moved['sl'] > 50 and abs(moved['a'] - moved['b']) < 1, f'a finger swipe on the top row scrolls both rows together {moved}')
        await pg.screenshot(path=f'{OUT}/tour-top100-swiped.png')

        # ---- relaunch: X only closed it for now, so it is back
        await pg.reload(); await pg.wait_for_timeout(3200)
        t = await tour_state(pg)
        check(t['open'] and t['count'] == '1 of 15', 'after X the tour opens again at the next launch')
        await pg.click('#tourNext'); await pg.wait_for_timeout(450)
        t = await tour_state(pg)
        sb = await pg.evaluate("(()=>{ const r = document.querySelector('.mobile-nav-btn[data-nav=search]').getBoundingClientRect(); return [r.left, r.top, r.width, r.height]; })()")
        check(t['title'] == 'Search' and t['spot'], f'step 2 rings the Search tab {t}')
        check(t['rect'][0] <= sb[0] and t['rect'][1] <= sb[1] and t['rect'][0] + t['rect'][2] >= min(sb[0] + sb[2], vw - 3) - 1 and t['rect'][1] + t['rect'][3] >= min(sb[1] + sb[3], vh - 3) - 1 and t['rect'][0] + t['rect'][2] <= vw and t['rect'][1] + t['rect'][3] <= vh, f'the ring surrounds the Search tab {t["rect"]} {sb}')
        check(t['panel'][3] < t['rect'][1], 'the card does not cover the ringed tab')
        await pg.screenshot(path=f'{OUT}/tour-2-search.png')
        await pg.click('#tourBack'); await pg.wait_for_timeout(200)
        check((await tour_state(pg))['count'] == '1 of 15', 'Back steps back')
        # every card in turn
        titles = []
        for i in range(15):
            t = await tour_state(pg); titles.append(t['title'])
            if t['title'] == 'Your Library':
                check(t['choice'] and t['spot'], 'the Library card rings the Library tab and asks about artist radio')
                await pg.screenshot(path=f'{OUT}/tour-5-library.png')
                await pg.click('.tour-choice-opts button[data-val=off]'); await pg.wait_for_timeout(200)
                st = await pg.evaluate("[localStorage.getItem('radioPlayerLibArtistRadio'), document.getElementById('libArtistRadioSelect').value, document.querySelector('.tour-choice-opts button.on').dataset.val]")
                check(st == ['off', 'off', 'off'], f'choosing Hide in the tour saves it and Settings shows it {st}')
                await pg.screenshot(path=f'{OUT}/tour-5-library-hide.png')
            if t['title'] == 'Live TV':
                check(t['spot'], 'Live TV rings the Watch tab')
            if t['title'] == 'Settings':
                check(t['spot'] and t['next'] == 'Done' and not t['never'], f'last card rings the menu button, says Done {t}')
                await pg.screenshot(path=f'{OUT}/tour-15-settings.png')
            if i < 14: await pg.click('#tourNext'); await pg.wait_for_timeout(330)
        print(titles)
        check(titles[:5] == ['Welcome to Amplify', 'Search', 'Favorites', 'Continue Listening', 'Your Library'] and len(set(titles)) == 15, 'cards run in order of importance, all different')
        for cap in ['Favorites', 'Continue Listening', 'My Stations', 'Cover Flow', 'Podcasts', 'Live TV', 'Your Own Channels']:
            check(cap in titles, f'tour covers {cap}')

        # ---- Library > Artists without artist radio, then with
        async def artists():
            await pg.evaluate("window.__h.ev('runLibrarySection(\"artists\")')")
            await pg.wait_for_timeout(900)
            return await pg.evaluate("[...document.querySelectorAll('#stationsGrid .tile[data-entity=artist] .tile-name')].map(e => e.textContent)")
        await pg.evaluate("window.__amplifyTour.close(false)")
        a = await artists()
        check('Zed' not in a and 'Yolanda' not in a, f'artist radio hidden: no station-only artists in Library > Artists {a}')
        await pg.screenshot(path=f'{OUT}/tour-lib-artists-hidden.png')
        cnt = await pg.evaluate("window.__h.ev('libraryArtistIndex().length + \"/\" + buildArtistIndex().length')")
        check(cnt == '0/3', f'Library count leaves them out, the index keeps them {cnt}')
        await pg.evaluate("document.getElementById('libArtistRadioSelect').value = 'on'; document.getElementById('libArtistRadioSelect').dispatchEvent(new Event('change'))")
        await pg.wait_for_timeout(500)
        a2 = await pg.evaluate("[...document.querySelectorAll('#stationsGrid .tile[data-entity=artist] .tile-name')].map(e => e.textContent)")
        check('Zed' in a2 and 'Yolanda' in a2 and 'Xavier' in a2, f'Settings Show puts them back straight away {a2}')
        await pg.screenshot(path=f'{OUT}/tour-lib-artists-shown.png')

        # ---- Done dismisses for good; Settings opens it again
        await pg.reload(); await pg.wait_for_timeout(3200)
        check((await tour_state(pg))['open'], 'still opens at launch before it is dismissed')
        await pg.click('#tourNever'); await pg.wait_for_timeout(200)
        check(not (await tour_state(pg))['open'] and await pg.evaluate("localStorage.getItem('radioPlayerTourDone')") == '1', "Don't show this again closes it and remembers")
        await pg.reload(); await pg.wait_for_timeout(4500)
        check(not (await tour_state(pg))['open'], 'dismissed: no tour at the next launch')
        sel = await pg.evaluate("document.getElementById('libArtistRadioSelect').value")
        check(sel == 'on', f'Settings shows the saved artist radio choice after a restart {sel}')
        await pg.click('.hamburger-btn'); await pg.wait_for_timeout(500)
        await pg.evaluate("document.getElementById('settingsFab') && document.getElementById('settingsFab').click()")
        await pg.wait_for_timeout(600)
        await pg.screenshot(path=f'{OUT}/tour-settings.png')
        # Build 349: Settings is in categories (the artist radio choice under Library, the tour under About); build 352: it's a switch.
        await pg.click('.set-cat[data-set-cat=library]'); await pg.wait_for_timeout(300)
        s_ok = await pg.evaluate("(()=>{ const s = document.getElementById('libArtistRadioSelectSwitch').getBoundingClientRect(); return s.width > 0 && s.height > 0; })()")
        await pg.click('#settingsCloseBtn'); await pg.wait_for_timeout(200)
        await pg.click('.set-cat[data-set-cat=about]'); await pg.wait_for_timeout(300)
        b_ok = await pg.evaluate("(()=>{ const b = document.getElementById('tourOpenBtn').getBoundingClientRect(); return b.width > 0 && b.height > 0; })()")
        vis = [b_ok, s_ok]
        check(vis == [True, True], f'Settings shows the tour button and the artist radio choice {vis}')
        await pg.evaluate("document.getElementById('tourOpenBtn').scrollIntoView({block:'center'})"); await pg.wait_for_timeout(300)
        await pg.screenshot(path=f'{OUT}/tour-settings-rows.png')
        await pg.click('#tourOpenBtn'); await pg.wait_for_timeout(500)
        t = await tour_state(pg)
        check(t['open'] and t['count'] == '1 of 15', 'Settings > Show the tour opens it from the start')
        for i in range(14): await pg.click('#tourNext'); await pg.wait_for_timeout(60)
        await pg.click('#tourNext'); await pg.wait_for_timeout(200)
        check(not (await tour_state(pg))['open'], 'Done on the last card closes it')

        # ---- rows come back once there is something in them
        await pg.evaluate("""(()=>{ const st = { name: 'Top 1', url: 'http://s/top1', url_resolved: 'http://s/top1', stationuuid: 'top1', favicon: '', tags: 'pop' };
          localStorage.setItem('radioPlayerFavorites', JSON.stringify([st]));
          localStorage.setItem('radioPlayerRecent', JSON.stringify([st]));
          localStorage.setItem('radioPlayerCustomSearches', JSON.stringify([{ id: 'cs1', label: 'Jazz', query: 'jazz', type: 'tag' }])); })()""")
        await pg.reload(); await pg.wait_for_timeout(3500)
        d = await pg.evaluate("['favoritesSection','recentSection','forYouSection'].map(id => getComputedStyle(document.getElementById(id)).display)")
        check('none' not in d, f'with favorites, plays and a custom station the three rows show {d}')
        await pg.screenshot(path=f'{OUT}/tour-home-filled.png')
        check(not errs, f'no page errors {errs[:3]}')
        await ctx.close()

        # ---- larger system text, narrow phone, light theme
        for w, theme in ((360, 'light'), (412, 'dark')):
            ctx = await b.new_context(viewport={'width': w, 'height': 760}, device_scale_factor=2, is_mobile=True, has_touch=True, locale='en-US')
            await ctx.route('**/*', route)
            await ctx.add_init_script(AUTO_NOTICE); await ctx.add_init_script(TOUR_ON); await ctx.add_init_script(BIG)
            await ctx.add_init_script("try{ localStorage.setItem('radioPlayerTheme', %s); }catch(e){}" % json.dumps(theme))
            pg = await ctx.new_page()
            await pg.goto(f'http://127.0.0.1:{PORT}/index.html'); await pg.wait_for_timeout(3200)
            for step in (0, 4, 6):
                await pg.evaluate("window.__amplifyTour.open(%d)" % step); await pg.wait_for_timeout(450)
                fit = await pg.evaluate("""(()=>{ const p = document.getElementById('tourPanel'), r = p.getBoundingClientRect();
                  const btns = [...p.querySelectorAll('button')].filter(x => x.offsetParent).map(x => x.getBoundingClientRect());
                  return { r: [r.left, r.top, r.right, r.bottom], over: p.scrollWidth > p.clientWidth + 1,
                    clipped: [...p.querySelectorAll('.tour-actions button, .tour-choice-opts button')].some(x => x.scrollWidth > x.clientWidth + 1) }; })()""")
                check(fit['r'][0] >= 0 and fit['r'][2] <= w and fit['r'][3] <= 760 and not fit['over'] and not fit['clipped'], f'{w}px {theme} big text, card {step + 1} fits {fit}')
                await pg.screenshot(path=f'{OUT}/tour-big-{w}-{theme}-{step + 1}.png')
            await ctx.close()
        await b.close()
    print('FAILS:', len(fails))
    for f in fails: print('  ', f)
    sys.exit(1 if fails else 0)

asyncio.run(main())
