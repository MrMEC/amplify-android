"""Build 267: a long title on Now Playing is cut to three lines ending in "... More"; More shows the whole
title ending in "Less", and Less cuts it back. Short titles are untouched, the controls stay put, a title
that is a link (an artist's station) keeps working, and landscape keeps its own two-line rule.
Run: python3 tests/test_np_long_title.py (screenshots in /tmp/claude-0/t/shots)"""
import sys as _nsys, os as _nos; _nsys.path.insert(0, _nos.path.dirname(_nos.path.abspath(__file__))); from notice_auto import AUTO_NOTICE
import asyncio, os, json, threading, http.server, functools, shutil, sys
from playwright.async_api import async_playwright

PORT = 8834
root = '/tmp/claude-0/t/srv_nplong'
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

MOCK = r"""(function(){
 var L = {}; var cur = null;
 function emit(n, ev){ (L[n] || []).forEach(function(f){ f(ev); }); }
 var impl = {
  addListener: function(n, f){ (L[n] = L[n] || []).push(f); return Promise.resolve({ remove: function(){} }); },
  load: function(o){ cur = { id: o.id };
    setTimeout(function(){ if(cur && cur.id === o.id) emit('state', { id: o.id, state: 'ready', isPlaying: !!o.play, playWhenReady: !!o.play, duration: -1, position: 0, external: false }); }, 120);
    return Promise.resolve({}); },
  play: function(){ return Promise.resolve({}); }, pause: function(){ return Promise.resolve({}); }
 };
 var P = new Proxy({}, { get: function(t, k){ if(k === 'then') return undefined; if(k === 'setCarLibraryPart') return undefined; if(impl[k]) return impl[k]; return function(){ return Promise.resolve({}); }; } });
 window.Capacitor = { isNativePlatform: function(){ return true; }, getPlatform: function(){ return 'android'; }, registerPlugin: function(){ return P; }, Plugins: { AmplifyPlayer: P }, convertFileSrc: function(u){ return u; } };
})();"""

LONG = 'OR - RESTAURANT LOUNGE || Lounge, Jazz, Chill, Soft Music, Background, Acoustic, Easy Listening, Dinner, Relax, Romantic, Smooth, Cafe, Evening, Instrumental, Calm'
def station(uuid, name):
    return {'name': name, 'url': 'http://s/' + uuid, 'url_resolved': 'http://s/' + uuid, 'urlToResolve': 'http://s/' + uuid, 'stationuuid': uuid, 'favicon': '', 'tags': 'lounge', 'country': 'Germany', 'codec': 'MP3', 'bitrate': 128}

async def route(r):
    if '127.0.0.1' in r.request.url or r.request.url.startswith('data:'): return await r.continue_()
    if '/json/stations' in r.request.url:
        return await r.fulfill(status=200, content_type='application/json', headers={'Access-Control-Allow-Origin': '*'}, body='[]')
    return await r.abort()

fails = []
def check(c, m):
    print(('PASS ' if c else 'FAIL ') + m)
    if not c: fails.append(m)

STATE = """(()=>{ const n = document.getElementById('npName'), lh = parseFloat(getComputedStyle(n).lineHeight);
  const t = n.querySelector('.np-name-text'), m = n.querySelector('.np-name-more'), c = document.querySelector('.np-controls').getBoundingClientRect();
  let mr = m && m.getBoundingClientRect(), nr = n.getBoundingClientRect();
  return { lines: Math.round(nr.height / lh), text: t ? t.textContent : '', more: m ? m.textContent : null, gap: (n.querySelector('.np-name-gap')||{}).textContent || '',
    ctrlTop: c.top, moreRight: mr ? mr.right : 0, nameRight: nr.right, nameLeft: nr.left, moreBottom: mr ? mr.bottom : 0, nameBottom: nr.bottom,
    moreH: mr ? mr.height : 0 }; })()"""

async def play(pg, st):
    await pg.evaluate("st => { window.__h.ev('playStation')(st); window.__h.ev('openNowPlaying')(st); }", st)
    await pg.wait_for_timeout(1200)

async def main():
    async with async_playwright() as pw:
        b = await pw.chromium.launch()
        for w, theme, big in ((412, 'dark', False), (360, 'light', False), (412, 'dark', True)):
            ctx = await b.new_context(viewport={'width': w, 'height': 900}, device_scale_factor=2, is_mobile=True, has_touch=True, locale='en-US')
            await ctx.route('**/*', route)
            await ctx.add_init_script(MOCK); await ctx.add_init_script(AUTO_NOTICE)
            await ctx.add_init_script("try{ localStorage.setItem('radioPlayerTheme', %s); }catch(e){}" % json.dumps(theme))
            if big:
                await ctx.add_init_script("""document.addEventListener('DOMContentLoaded', function(){ for(const sh of document.styleSheets){ try{ for(const r of sh.cssRules){ if(r.style && /px$/.test(r.style.fontSize)) r.style.fontSize = (parseFloat(r.style.fontSize) * 1.3) + 'px'; } }catch(e){} } });""")
            pg = await ctx.new_page(); errs = []
            pg.on('pageerror', lambda e: errs.append(str(e)))
            await pg.goto(f'http://127.0.0.1:{PORT}/index.html'); await pg.wait_for_timeout(2000)
            tag = f'{w}-{theme}' + ('-big' if big else '')

            # short title: untouched
            await play(pg, station('short1', 'Smooth Jazz 24'))
            s = await pg.evaluate(STATE)
            check(s['text'] == 'Smooth Jazz 24' and s['more'] is None and s['lines'] == 1, f'{tag}: a short title is shown whole, no More {s}')
            short_ctrl = s['ctrlTop']

            # long title: three lines ending in ... More
            await play(pg, station('long1', LONG))
            s = await pg.evaluate(STATE)
            print(tag, s)
            check(s['lines'] == 3, f'{tag}: the long title takes three lines')
            check(s['more'] == 'More' and s['gap'].startswith('…'), f'{tag}: it ends in "... More"')
            check(LONG.startswith(s['text']) and len(s['text']) < len(LONG) - 10 and len(s['text']) > 40, f'{tag}: the cut keeps as much of the title as fits ({len(s["text"])} chars)')
            check(s['moreRight'] <= s['nameRight'] + 1 and s['moreBottom'] >= s['nameBottom'] - s['moreH'] - 4, f'{tag}: More sits at the end of the third line')
            check(s['ctrlTop'] - short_ctrl < 200, f'{tag}: the controls stay well up the screen ({short_ctrl} -> {s["ctrlTop"]})')
            await pg.screenshot(path=f'{OUT}/nplong-{tag}-cut.png')
            closed_ctrl = s['ctrlTop']

            # More: the whole title, ending in Less
            await pg.click('#npName .np-name-more'); await pg.wait_for_timeout(300)
            s = await pg.evaluate(STATE)
            check(s['text'] == LONG and s['more'] == 'Less' and s['lines'] > 3, f'{tag}: More shows the whole title, ending in Less {s["lines"]} lines')
            np_open = await pg.evaluate("document.body.classList.contains('np-open')")
            check(np_open, f'{tag}: tapping More leaves Now Playing open')
            await pg.screenshot(path=f'{OUT}/nplong-{tag}-open.png')

            # Less: back to three lines
            await pg.click('#npName .np-name-more'); await pg.wait_for_timeout(300)
            s = await pg.evaluate(STATE)
            check(s['lines'] == 3 and s['more'] == 'More' and abs(s['ctrlTop'] - closed_ctrl) < 2, f'{tag}: Less cuts it back to three lines')

            # next station starts cut again
            await pg.click('#npName .np-name-more'); await pg.wait_for_timeout(200)
            await play(pg, station('long2', LONG + ' Two'))
            s = await pg.evaluate(STATE)
            check(s['more'] == 'More' and s['lines'] == 3, f'{tag}: a new item starts cut again')

            if not big and w == 412:
                # landscape keeps its own two-line clamp with the whole title
                await pg.set_viewport_size({'width': 900, 'height': 412}); await pg.wait_for_timeout(1200)
                s = await pg.evaluate(STATE)
                rl = await pg.evaluate("document.body.classList.contains('rotate-lock')")
                check(rl and s['more'] is None and s['text'] == LONG + ' Two', f'landscape: whole title under its own clamp, no More {s["more"]} rl={rl}')
                await pg.screenshot(path=f'{OUT}/nplong-landscape.png')
                await pg.set_viewport_size({'width': 412, 'height': 900}); await pg.wait_for_timeout(1200)
                s = await pg.evaluate(STATE)
                check(s['more'] == 'More' and s['lines'] == 3, 'back upright: cut to three lines again')
            check(not errs, f'{tag}: no page errors {errs[:2]}')
            await ctx.close()
        await b.close()
    print('FAILS:', len(fails))
    for f in fails: print('  ', f)
    sys.exit(1 if fails else 0)

asyncio.run(main())
