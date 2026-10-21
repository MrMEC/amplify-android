"""Build 271 (Mark):
- Watch > Live TV > Edit: a sort line whose pills don't fit (Layout: Your Channels First / Integrate
  Channels) scrolls sideways, label and all, from screen edge to screen edge; a finger swipe brings
  Integrate Channels into view and a tap picks it. The page itself never scrolls sideways.
- A podcast's page has no More link: the show's description (from its feed) is printed in full under
  the publisher, as text, before the episodes. A feed that can't be read leaves nothing there.
Run: python3 tests/test_b271_watch_podcast.py (screenshots in /tmp/claude-0/t/shots)"""
import sys as _nsys, os as _nos; _nsys.path.insert(0, _nos.path.dirname(_nos.path.abspath(__file__))); from notice_auto import AUTO_NOTICE
import os, json, asyncio, sys, threading, http.server, functools, shutil
from urllib.parse import urlparse, parse_qs
HERE = os.path.dirname(os.path.abspath(__file__))
src = open(os.path.join(HERE, 'test_channel_layout_cast.py')).read()
head = src[:src.index('\nasync def run3(')]
head = head.replace("'/tmp/claude-0/t/srv-livech3'", "'/tmp/claude-0/t/srv-livech271'").replace('PORT = 8864', 'PORT = 8854')
exec(head)
from playwright.async_api import async_playwright

LINE = """(()=>{ const l = document.getElementById('chLayoutLine'); if(!l) return null; const r = l.getBoundingClientRect();
  const lab = l.querySelector('.ch-sort-label').getBoundingClientRect(), mix = l.querySelector('.home-tab[data-opt=mixed]').getBoundingClientRect();
  const head = document.querySelector('#stationsGrid .ch-edit-list, #stationsGrid .ch-group-head'), hr = head ? head.getBoundingClientRect() : null;
  return { left: r.left, right: r.right, vw: innerWidth, sw: l.scrollWidth, cw: l.clientWidth, sl: l.scrollLeft, y: r.top + r.height / 2,
    labLeft: lab.left, contentLeft: hr ? hr.left : null, mixLeft: mix.left, mixRight: mix.right,
    pageW: document.scrollingElement.scrollWidth }; })()"""

async def swipe(cdp, x0, x1, y, steps=10):
    await cdp.send('Input.dispatchTouchEvent', {'type': 'touchStart', 'touchPoints': [{'x': x0, 'y': y}]})
    for i in range(1, steps + 1):
        await cdp.send('Input.dispatchTouchEvent', {'type': 'touchMove', 'touchPoints': [{'x': x0 + (x1 - x0) * i / steps, 'y': y}]})
        await asyncio.sleep(0.016)
    await cdp.send('Input.dispatchTouchEvent', {'type': 'touchEnd', 'touchPoints': []})

async def watch(p, theme, width):
    T = f'[watch {theme} {width}]'
    b = await p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
    ctx = await b.new_context(viewport={'width': width, 'height': 860}, device_scale_factor=2, is_mobile=True, has_touch=True, color_scheme=theme, locale='en-US', timezone_id='America/New_York')
    await ctx.add_init_script(MOCK); await ctx.add_init_script(AUTO_NOTICE); await ctx.add_init_script(SEED)
    await ctx.add_init_script("try{ localStorage.setItem('radioPlayerTheme', '%s'); }catch(e){}" % theme)
    # Mark's phone uses larger system text (about 1.3x); that is what pushes the pills off the edge.
    await ctx.add_init_script("""document.addEventListener('DOMContentLoaded', function(){ for(const sh of document.styleSheets){ try{ for(const r of sh.cssRules){ if(r.style && /px$/.test(r.style.fontSize)) r.style.fontSize = (parseFloat(r.style.fontSize) * 1.3) + 'px'; } }catch(e){} } });""")
    pg = await ctx.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
    await pg.route('**/*', route)
    await pg.goto(f'http://127.0.0.1:{PORT}/index.html'); await pg.wait_for_timeout(3000)
    await pg.evaluate("document.querySelector('.mobile-nav-btn[data-nav=video]').click()"); await pg.wait_for_timeout(1500)
    await edit(pg)
    s = await pg.evaluate(LINE); print(T, s)
    check(s is not None and s['sw'] > s['cw'] + 4, f'{T} the Layout line is wider than the screen, so it scrolls ({s and s["sw"]} > {s and s["cw"]})')
    check(abs(s['left']) <= 1 and abs(s['right'] - s['vw']) <= 1, f'{T} it runs from screen edge to screen edge ({s["left"]}..{s["right"]})')
    check(s['contentLeft'] is None or abs(s['labLeft'] - s['contentLeft']) <= 1, f'{T} its label starts at the page margin ({s["labLeft"]} vs {s["contentLeft"]})')
    check(s['mixRight'] > s['vw'], f'{T} Integrate Channels runs off the right edge to begin with')
    check(s['pageW'] <= s['vw'], f'{T} the page itself does not scroll sideways ({s["pageW"]})')
    await pg.evaluate("window.scrollTo(0,0)"); await pg.wait_for_timeout(200)
    await pg.screenshot(path=f'{SHOTS}/b271-sortline-{theme}-{width}-start.png')
    cdp = await ctx.new_cdp_session(pg)
    await swipe(cdp, s['vw'] - 30, 20, s['y']); await pg.wait_for_timeout(300); await swipe(cdp, s['vw'] - 30, 20, s['y']); await pg.wait_for_timeout(700)
    s2 = await pg.evaluate(LINE); print(T, s2)
    check(s2['sl'] > 20 and s2['mixRight'] <= s2['vw'] + 1, f'{T} a finger swipe scrolls it and brings Integrate Channels into view (scrollLeft {s2["sl"]})')
    check(await pg.evaluate("document.scrollingElement.scrollLeft") == 0, f'{T} the page stayed put')
    await pg.screenshot(path=f'{SHOTS}/b271-sortline-{theme}-{width}-scrolled.png')
    await pg.tap('#chLayoutLine .home-tab[data-opt=mixed]'); await pg.wait_for_timeout(600)
    ln = await pg.evaluate(LINES)
    check(ln and ln[0] == 'Layout:Your Channels First/*Integrate Channels', f'{T} a tap picks Integrate Channels {ln}')
    await pick_line(pg, 'chLayoutLine', 'split')
    check(not errs, f'{T} no page errors {errs[:2]}')
    await b.close()

# ---- podcast page ----
PPORT = 8855
proot = '/tmp/claude-0/t/srv-b271pod'
shutil.rmtree(proot, ignore_errors=True); os.makedirs(proot)
PHOOK = "window.__p = { open: function(id){ openShowPage(id); } };\n"
_s = open(os.path.join(HERE, '..', 'www', 'index.html')).read()
_m = '  var coverFlow = null;\n'
assert _s.count(_m) == 1
open(proot + '/index.html', 'w').write(_s.replace(_m, _m + PHOOK))
class PQ(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a): pass
_ps = http.server.ThreadingHTTPServer(('127.0.0.1', PPORT), functools.partial(PQ, directory=proot))
threading.Thread(target=_ps.serve_forever, daemon=True).start()
SHOW_DESC = ('<p>Funk History Hour digs into the records, the bands and the cities that made funk, one story at a time.</p>'
             '<p>New episodes every week &amp; a bonus mailbag once a month.</p>'
             '<p>The last line of the description: thanks for listening.</p>')
RSS = ('<?xml version="1.0"?><rss version="2.0" xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd"><channel><title>Funk History Hour</title>'
       '<description><![CDATA[' + SHOW_DESC + ']]></description><item><title>Ep</title><description>Episode notes</description></item></channel></rss>')
def lookup(cid, feed):
    eps = [{'wrapperType': 'podcastEpisode', 'kind': 'podcast-episode', 'collectionId': cid, 'collectionName': 'Funk History Hour', 'artistName': 'Radio Co',
            'trackName': f'Episode {i}', 'episodeGuid': f'ep-{i}', 'episodeUrl': f'https://pod.example/ep{i}.mp3',
            'releaseDate': f'2026-10-{21 - i:02d}T10:00:00Z', 'trackTimeMillis': 1800000, 'description': 'Notes'} for i in (5, 4, 3)]
    return {'resultCount': 4, 'results': [{'wrapperType': 'track', 'kind': 'podcast', 'collectionId': cid, 'collectionName': 'Funk History Hour',
            'artistName': 'Radio Co', 'feedUrl': feed, 'artworkUrl600': ''}] + eps}
async def proute(r):
    u = urlparse(r.request.url)
    if u.hostname == '127.0.0.1': return await r.continue_()
    if u.hostname == 'itunes.apple.com' and u.path == '/lookup':
        q = parse_qs(u.query); cid = int(q['id'][0])
        feed = 'https://feeds.example/funk.xml' if cid == 77 else 'https://blocked.example/feed.xml'
        return await r.fulfill(body=f"{q['callback'][0]}({json.dumps(lookup(cid, feed))});", content_type='text/javascript')
    if u.hostname == 'feeds.example':
        return await r.fulfill(body=RSS, content_type='application/rss+xml', headers={'Access-Control-Allow-Origin': '*'})
    return await r.abort()
PSTATE = """(()=>{ const h = document.querySelector('#stationsGrid .podcast-show-header'); if(!h) return null;
  const d = h.querySelector('.podcast-show-desc'), a = h.querySelector('.album-hero-artist'), first = h.nextElementSibling;
  const dr = d && d.getBoundingClientRect();
  return { more: !!document.querySelector('#stationsGrid .podcast-more-link'), text: d ? d.textContent : null,
    afterArtist: !!(d && a && (a.compareDocumentPosition(d) & 4)), descTop: dr ? dr.top : 0, artistBottom: a ? a.getBoundingClientRect().bottom : 0,
    left: dr ? dr.left : 0, right: dr ? dr.right : 0, vw: innerWidth, align: d ? getComputedStyle(d).textAlign : '',
    nextTop: first ? first.getBoundingClientRect().top : 0, bottom: dr ? dr.bottom : 0, sw: d ? d.scrollWidth : 0, cw: d ? d.clientWidth : 0 }; })()"""
async def podcast(p, theme, width, big):
    T = f'[podcast {theme} {width}' + (' big' if big else '') + ']'
    b = await p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
    ctx = await b.new_context(viewport={'width': width, 'height': 860}, device_scale_factor=2, is_mobile=True, has_touch=True, color_scheme=theme)
    await ctx.add_init_script(AUTO_NOTICE)
    await ctx.add_init_script("try{ localStorage.setItem('radioPlayerTheme', '%s'); }catch(e){}" % theme)
    pg = await ctx.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
    await pg.route('**/*', proute)
    await pg.goto(f'http://127.0.0.1:{PPORT}/index.html'); await pg.wait_for_timeout(2000)
    if big: await pg.add_style_tag(content='.podcast-show-desc{ font-size:18px !important; }')
    await pg.evaluate("document.querySelector('.mobile-nav-btn[data-nav=podcasts]').click()"); await pg.wait_for_timeout(800)
    await pg.evaluate('__p.open(77)'); await pg.wait_for_timeout(1800)
    s = await pg.evaluate(PSTATE); print(T, {k: v for k, v in (s or {}).items() if k != 'text'})
    check(s and not s['more'], f'{T} no More link on the show page')
    check(s and s['text'] and 'Funk History Hour digs into' in s['text'] and 'thanks for listening' in s['text'], f'{T} the show description is on the page, in full')
    check(s and '<' not in s['text'] and '&amp;' not in s['text'] and 'week & a bonus' in s['text'] and '\n\n' in s['text'], f'{T} shown as text, paragraphs kept')
    check(s and s['afterArtist'] and s['descTop'] >= s['artistBottom'] and s['nextTop'] >= s['bottom'], f'{T} under the publisher, before the episodes')
    check(s and s['left'] >= 10 and s['vw'] - s['right'] >= 10 and s['sw'] <= s['cw'] + 1, f'{T} inside the page margins')
    await pg.evaluate("window.scrollTo(0,0)"); await pg.wait_for_timeout(200)
    await pg.screenshot(path=f'{SHOTS}/b271-podcast-{theme}-{width}' + ('-big' if big else '') + '.png')
    # a feed that can't be read: nothing in its place
    await pg.evaluate('__p.open(78)'); await pg.wait_for_timeout(1800)
    s = await pg.evaluate(PSTATE)
    check(s and not s['more'] and s['text'] is None, f'{T} an unreadable feed leaves no description and no More')
    check(not errs, f'{T} no page errors {errs[:2]}')
    await b.close()

async def main():
    async with async_playwright() as p:
        for theme, w in (('dark', 412), ('light', 360)):
            await watch(p, theme, w)
        for theme, w, big in (('dark', 412, False), ('light', 360, False), ('dark', 360, True)):
            await podcast(p, theme, w, big)
    print('ALL PASSED' if not FAILS else f'{len(FAILS)} FAILED')
    sys.exit(1 if FAILS else 0)

FAILS = []
_check = check
def check(c, m):
    if not c: FAILS.append(m)
    try: _check(c, m)
    except Exception: print(('PASS ' if c else 'FAIL ') + m)
asyncio.run(main())
