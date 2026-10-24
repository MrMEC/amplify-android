"""Build 309 (Mark), part 2: TV episodes and movies on the video Now Playing screen get the picture
beside their details (the poster) and the show/hide arrow beside the list heading, like music videos.
Run: python3 tests/test_b309b.py"""
import sys as _nsys, os as _nos; _nsys.path.insert(0, _nos.path.dirname(_nos.path.abspath(__file__)))
src = open(_nos.path.join(_nos.path.dirname(_nos.path.abspath(__file__)), 'test_live_channels_editor.py')).read()
src = src[:src.index('async def run2(')].replace('PORT = 8863', 'PORT = 8903').replace("srv-livech2'", "srv-b309b'")
exec(src)
MOVIES[0]['th'] = '/library/metadata/900/thumb/1'
SEED = """(function(){ if(!localStorage.getItem('__seeded')){ localStorage.setItem('__seeded','1');
  localStorage.setItem('radioPlayerPlexAccount', %s);
  var lib = JSON.parse(%s); lib.at = Date.now(); localStorage.setItem('radioPlayerPlexLib', JSON.stringify(lib));
  localStorage.setItem('radioPlayerVideoFiles', %s);
  localStorage.setItem('radioPlayerVideoInfo', %s);
  localStorage.setItem('radioPlayerVideoChannels', %s);
  localStorage.setItem('radioPlayerVideoTab', 'channels'); } })();""" % tuple(json.dumps(json.dumps(x)) for x in (ACCT, LIB, FILES, INFO, CHANNELS))
fails2 = []
def chk(c, m):
    print(('PASS ' if c else 'FAIL ') + m)
    if not c: fails2.append(m)
STATE = """(()=>{ const t = document.getElementById('npEpThumb'), d = document.querySelector('#nowPlayingScreen .np-details'), g = document.getElementById('npFootToggle'), h = document.getElementById('npCollectionHeading');
  const gr = g.getBoundingClientRect(), hr = h.getBoundingClientRect();
  return { name: document.getElementById('npName').textContent, thumb: !t.hidden, src: t.querySelector('img').getAttribute('src') || '', hasEp: d.classList.contains('np-has-ep'),
    toggle: getComputedStyle(g).display !== 'none' && gr.width > 0, left: gr.right <= hr.left + 1, head: h.textContent }; })()"""
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
        ctx = await b.new_context(viewport={'width': 390, 'height': 860}, device_scale_factor=3, is_mobile=True, has_touch=True, color_scheme='dark', locale='en-US', timezone_id='America/New_York')
        await ctx.add_init_script(MOCK); await ctx.add_init_script(AUTO_NOTICE); await ctx.add_init_script(SEED)
        pg = await ctx.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.route('**/*', route)
        await pg.goto(f'http://127.0.0.1:{PORT}/index.html'); await pg.wait_for_timeout(3000)
        await pg.evaluate("document.querySelector('.mobile-nav-btn[data-nav=video]').click()"); await pg.wait_for_timeout(1200)
        # a TV episode
        await pg.evaluate("document.querySelector('.watch-tabs .home-tab[data-vtab=shows]').click()"); await pg.wait_for_timeout(800)
        await pg.evaluate("document.querySelector('#stationsGrid .tile.vposter').click()"); await pg.wait_for_timeout(800)
        await pg.evaluate("document.querySelector('.vd-actions .vd-play').click()"); await pg.wait_for_timeout(2500)
        e = await pg.evaluate(STATE); print('episode', e)
        chk(e['thumb'] and e['hasEp'] and e['src'], f'a TV episode: its poster beside the details {e}')
        chk(e['toggle'] and e['left'] and e['head'], f'and the show/hide arrow left of the list heading {e["head"]}')
        await pg.screenshot(path='/tmp/claude-0/t/shots/b309-episode.png')
        await pg.evaluate("document.getElementById('npBackBtn').click()"); await pg.wait_for_timeout(800)
        # a movie
        await pg.evaluate("document.querySelector('.mobile-nav-btn[data-nav=video]').click()"); await pg.wait_for_timeout(800)
        await pg.evaluate("document.querySelector('.watch-tabs .home-tab[data-vtab=movies]').click()"); await pg.wait_for_timeout(800)
        names = await pg.evaluate("[...document.querySelectorAll('#stationsGrid .tile.vposter .tile-name')].map(e => e.textContent)")
        print('movies', names)
        # one with no picture at all: nothing shown (not the episode's left behind)
        await pg.evaluate("[...document.querySelectorAll('#stationsGrid .tile.vposter')].find(t => t.querySelector('.tile-name').textContent === 'Alien').click()"); await pg.wait_for_timeout(800)
        await pg.evaluate("document.querySelector('.vd-actions .vd-play').click()"); await pg.wait_for_timeout(2500)
        a = await pg.evaluate(STATE)
        chk(not a['thumb'] and not a['hasEp'], f'a movie with no picture anywhere: none shown, nothing left over {a["thumb"]}')
        await pg.evaluate("document.getElementById('npBackBtn').click()"); await pg.wait_for_timeout(800)
        await pg.evaluate("document.querySelector('.mobile-nav-btn[data-nav=video]').click()"); await pg.wait_for_timeout(800)
        await pg.evaluate("[...document.querySelectorAll('#stationsGrid .tile.vposter')].find(t => t.querySelector('.tile-name').textContent === 'Plex Only Movie').click()"); await pg.wait_for_timeout(800)
        await pg.evaluate("document.querySelector('.vd-actions .vd-play').click()"); await pg.wait_for_timeout(2500)
        m = await pg.evaluate(STATE); print('movie', m)
        chk(m['thumb'] and m['hasEp'] and '900' in m['src'], f"a movie: its poster beside the details {m}")
        chk(m['toggle'] and m['left'], f'and the arrow by "{m["head"]}"')
        await pg.screenshot(path='/tmp/claude-0/t/shots/b309-movie.png')
        chk(not errs, f'no page errors {errs[:2]}')
        await b.close()
    print('ALL PASSED' if not fails2 else f'FAILED {len(fails2)}')
asyncio.run(main())
