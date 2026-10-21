"""Build 269 (Mark): a podcast episode's Now Playing shows the episode's full description between
the progress bar and More Episodes ("About This Episode"). The playing item's own copy may be cut
short (Continue Listening, Latest Podcasts), so the show's episode lookup replaces it with the full
text. Paragraphs and line breaks are kept; HTML is shown as text. Hidden for anything that is not
a podcast episode, and for an episode with no description.
Run: python3 tests/test_np_ep_desc.py (screenshots in /tmp/claude-0/t/shots)"""
import asyncio, os, json, threading, http.server, functools, shutil, sys
from urllib.parse import urlparse, parse_qs
from playwright.async_api import async_playwright
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from notice_auto import AUTO_NOTICE

PORT = 8853
root = '/tmp/claude-0/t/srv-epdesc'
SHOTS = '/tmp/claude-0/t/shots'
os.makedirs(SHOTS, exist_ok=True)
shutil.rmtree(root, ignore_errors=True); os.makedirs(root)
HOOK = ("window.__e = { stub: function(){ var on = false; try{ Object.defineProperty(audio, 'paused', { configurable: true, get: function(){ return !on; } }); }catch(e){} audio.play = function(){ on = true; return Promise.resolve(); }; audio.pause = function(){ on = false; }; },"
        " open: function(st){ __e.stub(); audio.play(); currentStation = st; updatePlayerMeta(st, ''); setPlayingUI(true); openNowPlaying(st, false); renderNowPlayingScreen(); },"
        " close: function(){ try{ closeNowPlaying(); }catch(e){} } };\n")
_src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'www', 'index.html')).read()
_mark = '  var coverFlow = null;\n'
assert _src.count(_mark) == 1
open(root + '/index.html', 'w').write(_src.replace(_mark, _mark + HOOK))
class Q(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a): pass
srv = http.server.ThreadingHTTPServer(('127.0.0.1', PORT), functools.partial(Q, directory=root))
threading.Thread(target=srv.serve_forever, daemon=True).start()

FULL = ('<p>In this episode we look back at <b>1984</b> &amp; the making of a classic album, from the first demo '
        'tapes to the last mix.</p><p>Plus listener mail, a deep cut and what came next for the band.</p>'
        '<ul><li>Chapter one: the demos</li><li>Chapter two: the sessions</li></ul>'
        '<p>Sponsored by Example Co. Find us at https://funk.example/show-notes-for-episode-twelve-and-more</p>'
        '<p>The last paragraph, which only the full description has: thanks for listening.</p>')
TRUNC = FULL[:200]
def ep_rec(i, desc):
    return {'wrapperType': 'podcastEpisode', 'kind': 'podcast-episode', 'collectionId': 77, 'collectionName': 'Funk History Hour',
            'artistName': 'Radio Co', 'trackName': f'Episode {i}', 'episodeGuid': f'ep-{i}', 'episodeUrl': f'https://pod.example/ep{i}.mp3',
            'releaseDate': f'2026-10-{21 - i:02d}T10:00:00Z', 'trackTimeMillis': 1800000, 'description': desc}
LOOKUP = {'resultCount': 6, 'results': [{'wrapperType': 'track', 'kind': 'podcast', 'collectionId': 77, 'collectionName': 'Funk History Hour'}]
          + [ep_rec(i, FULL if i == 12 else f'Notes for episode {i}.') for i in (12, 11, 10, 9, 8)]}
EP = {'type': 'podcast', 'guid': 'ep-12', 'name': 'Episode 12', 'collectionId': 77, 'collectionName': 'Funk History Hour',
      'artistName': 'Radio Co', 'episodeUrl': 'https://pod.example/ep12.mp3', 'duration': 1800, 'description': TRUNC}
EP_NONE = dict(EP, guid='ep-99', name='Episode 99', episodeUrl='https://pod.example/ep99.mp3', description='')
STATION = {'name': 'Smooth Jazz 24', 'url': 'https://radio.example/jazz', 'stationuuid': 'sj24', 'description': 'not shown'}

fails = 0
def check(ok, msg):
    global fails
    print(('PASS ' if ok else 'FAIL ') + msg); fails += 0 if ok else 1

async def route(r):
    u = urlparse(r.request.url)
    if u.hostname == '127.0.0.1': return await r.continue_()
    if u.hostname == 'itunes.apple.com' and u.path == '/lookup':
        cb = parse_qs(u.query)['callback'][0]
        return await r.fulfill(body=f'{cb}({json.dumps(LOOKUP)});', content_type='text/javascript')
    return await r.abort()

STATE = """(()=>{ var d = document.getElementById('npEpDesc'), t = document.getElementById('npEpDescText');
  var vis = function(el){ return !!el && getComputedStyle(el).display !== 'none' && el.getBoundingClientRect().height > 0; };
  var seek = document.getElementById('npSeek'), rel = document.getElementById('npRelated');
  var r = d.getBoundingClientRect();
  return { shown: vis(d), heading: d.querySelector('.np-related-heading').textContent, text: t.textContent,
    top: r.top, bottom: r.bottom, left: r.left, right: r.right, vw: innerWidth,
    seekShown: vis(seek), seekBottom: seek.getBoundingClientRect().bottom,
    ctlBottom: document.querySelector('.np-controls').getBoundingClientRect().bottom,
    relShown: vis(rel), relTop: rel.getBoundingClientRect().top, relHeading: rel.querySelector('.np-related-heading').textContent,
    relRows: document.querySelectorAll('#npRelatedGrid .song-row, #npRelatedGrid .tile').length,
    sw: t.scrollWidth, cw: t.clientWidth, lh: parseFloat(getComputedStyle(t).lineHeight), th: t.getBoundingClientRect().height }; })()"""

async def run(b, theme, w, big):
    ctx = await b.new_context(viewport={'width': w, 'height': 860}, device_scale_factor=2, is_mobile=True, has_touch=True, color_scheme=theme)
    await ctx.add_init_script(AUTO_NOTICE)
    await ctx.add_init_script("try{ localStorage.setItem('radioPlayerTheme', %s); }catch(e){}" % json.dumps(theme))
    pg = await ctx.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
    await pg.route('**/*', route)
    await pg.goto(f'http://127.0.0.1:{PORT}/index.html'); await pg.wait_for_timeout(2000)
    if big:
        await pg.add_style_tag(content='.np-ep-desc-text{ font-size:19px !important; } .np-related-heading{ font-size:17px !important; }')
    tag = f'{theme}-{w}' + ('-big' if big else '')
    await pg.evaluate(f'__e.open({json.dumps(EP)})'); await pg.wait_for_timeout(1500)
    s = await pg.evaluate(STATE)
    print({k: s[k] for k in s if k != 'text'})
    check(s['shown'] and s['heading'] == 'About This Episode', f'[{tag}] the episode shows its description section')
    check('thanks for listening' in s['text'], f'[{tag}] the full description replaces the shortened copy')
    check('<' not in s['text'] and '&amp;' not in s['text'] and '1984 & the making' in s['text'], f'[{tag}] HTML shown as plain text')
    check('\n\n' in s['text'] and '• Chapter one: the demos\n• Chapter two' in s['text'], f'[{tag}] paragraphs and list lines kept')
    lines = round(s['th'] / s['lh']) if s['lh'] else 0
    check(lines >= 8, f'[{tag}] shown in full, no line limit ({lines} lines)')
    below = s['seekBottom'] if s['seekShown'] else s['ctlBottom']
    check(s['top'] >= below + 8, f'[{tag}] below the progress bar ({below:.0f} -> {s["top"]:.0f}, seek shown {s["seekShown"]})')
    check(s['relShown'] and s['relHeading'] == 'More Episodes' and s['relRows'] == 4 and s['relTop'] >= s['bottom'] + 20,
          f'[{tag}] More Episodes follows it ({s["relRows"]} rows)')
    check(s['sw'] <= s['cw'] + 1 and s['left'] >= 10 and s['vw'] - s['right'] >= 10, f'[{tag}] text wraps inside the page margins')
    await pg.evaluate("document.querySelector('.now-playing-screen').scrollTop = 0; window.scrollTo(0, 0)")
    y = await pg.evaluate("(()=>{ var d = document.getElementById('npEpDesc'); d.scrollIntoView({block:'start'}); var sc = document.querySelector('.now-playing-screen'); if(sc.scrollTop) sc.scrollTop -= 160; else window.scrollBy(0, -160); return 0; })()")
    await pg.wait_for_timeout(400)
    await pg.screenshot(path=f'{SHOTS}/epdesc-{tag}.png')
    # an episode with no description at all: no section
    await pg.evaluate(f'__e.open({json.dumps(EP_NONE)})'); await pg.wait_for_timeout(1200)
    s = await pg.evaluate(STATE)
    check(not s['shown'], f'[{tag}] no section for an episode with no description')
    # a station: no section
    await pg.evaluate(f'__e.open({json.dumps(STATION)})'); await pg.wait_for_timeout(1200)
    s = await pg.evaluate(STATE)
    check(not s['shown'] and s['text'] == '', f'[{tag}] no section for a station')
    # back to the episode: it comes back
    await pg.evaluate(f'__e.open({json.dumps(EP)})'); await pg.wait_for_timeout(1200)
    s = await pg.evaluate(STATE)
    check(s['shown'] and 'thanks for listening' in s['text'], f'[{tag}] the episode again shows it')
    check(not errs, f'[{tag}] no page errors {errs[:3]}')
    await ctx.close()

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
        await run(b, 'dark', 412, False)
        await run(b, 'light', 412, False)
        await run(b, 'dark', 360, True)
        await b.close()
    print('ALL PASSED' if not fails else f'{fails} FAILED')
    sys.exit(1 if fails else 0)

asyncio.run(main())
