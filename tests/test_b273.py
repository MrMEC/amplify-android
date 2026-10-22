"""Build 273 (Mark):
- Poppins is the page's font (embedded, so no network needed), buttons and inputs included.
- A podcast in the Home hero plays on a tap anywhere on its slide, not only the Play button.
- Hero titles never break inside a word: "WhatCulture Wrestling" shrinks until each word fits.
- Home's Continue Watching heading opens its own Continue Watching page (rows), not Watch / Live TV;
  back returns Home.
Run: python3 tests/test_b273.py (screenshots in /tmp/claude-0/t/shots)"""
import sys as _nsys, os as _nos; _nsys.path.insert(0, _nos.path.dirname(_nos.path.abspath(__file__))); from notice_auto import AUTO_NOTICE
import asyncio, os, json
HERE = os.path.dirname(os.path.abspath(__file__))
src = open(os.path.join(HERE, 'test_video_library.py')).read()
head = src[:src.index('async def names(pg, sel)')]
head = head.replace('8780', '8873')
exec(head)
from playwright.async_api import async_playwright
# Every native call is recorded (a podcast already cued up resumes with play, not load).
MOCK = MOCK.replace("   return function(){ return Promise.resolve({}); };", "   return function(a){ window.__calls.push([k, a && (a.url || a.id) || '']); return Promise.resolve({}); };")

CH = [{'id': 'freetv:pbs', 'name': 'PBS', 'url': 'https://pbs.example/live.m3u8', 'logo': '', 'country': 'USA', 'cats': [], 'catNames': [], 'src': 'freetv', 'addedAt': 2}]
POD = {'type': 'podcast', 'name': 'NEWS - Ilja Dragunov Injury Update, AEW Dynamite Ratings', 'collectionName': 'WhatCulture Wrestling',
       'artistName': 'WhatCulture', 'episodeUrl': 'https://pod.example/wcw-news.mp3', 'url': 'https://pod.example/wcw-news.mp3',
       'description': "Today's wrestling news, including... Ilja Dragunov's injury and more.", 'favicon': '', 'duration': 1800}
RECENT = [POD]
TITLE = """(()=>{ const s = Array.from(document.querySelectorAll('#npHero .nph-slide')).find(x => x.querySelector('.nph-title').textContent === 'WhatCulture Wrestling');
  if(!s) return null; const t = s.querySelector('.nph-title'); const cs = getComputedStyle(t);
  const r = document.createRange(); r.selectNodeContents(t); const rects = Array.from(r.getClientRects());
  const words = t.textContent.split(' '); let broken = false, off = 0;
  // each word's characters on one line
  for(const w of words){ const tn = t.firstChild; const rr = document.createRange(); rr.setStart(tn, off); rr.setEnd(tn, off + w.length);
    const tops = new Set(Array.from(rr.getClientRects()).map(q => Math.round(q.top))); if(tops.size > 1) broken = true; off += w.length + 1; }
  return { size: parseFloat(cs.fontSize), font: cs.fontFamily, lines: new Set(rects.map(q => Math.round(q.top))).size, broken,
           sw: t.scrollWidth, cw: t.clientWidth }; })()"""

async def run(p, width):
    T = f'[{width}]'
    b = await p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
    ctx = await b.new_context(viewport={'width': width, 'height': 844}, device_scale_factor=3, is_mobile=True, has_touch=True, color_scheme='dark', locale='en-US')
    await ctx.add_init_script(MOCK); await ctx.add_init_script(AUTO_NOTICE); await ctx.add_init_script(EXT)
    await ctx.add_init_script("if(!localStorage.getItem('radioPlayerVideoChannels')){localStorage.setItem('radioPlayerVideoChannels', %s); localStorage.setItem('radioPlayerRecent', %s);}" % (repr(json.dumps(CH)), repr(json.dumps(RECENT))))
    pg = await ctx.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e) + ' @ ' + (e.stack or '')[:300]))
    await pg.route('**/*', route)
    await pg.goto(f'http://127.0.0.1:8873/index.html'); await pg.wait_for_timeout(2500)
    await pg.evaluate("document.querySelector('.mobile-nav-btn[data-nav=home]').click()"); await pg.wait_for_timeout(1200)

    # Poppins
    f = await pg.evaluate("""(()=>({ body: getComputedStyle(document.body).fontFamily, btn: getComputedStyle(document.querySelector('.mobile-nav-btn')).fontFamily,
        ok: document.fonts.check('800 20px Poppins'), loaded: Array.from(document.fonts).filter(x => x.family.replace(/["']/g,'') === 'Poppins' && x.status === 'loaded').length,
        google: !!document.querySelector('link[href*="fonts.googleapis"]') }))()""")
    check(f['body'].startswith('Poppins') and f['btn'].startswith('Poppins') and f['loaded'] >= 1 and not f['google'], f'{T} Poppins is the font (page and buttons), embedded {f}')

    # hero title
    t = await pg.evaluate(TITLE); print(T, t)
    check(t and not t['broken'] and t['sw'] <= t['cw'] + 1 and t['lines'] <= 2, f'{T} the hero title breaks only between words, within two lines {t}')
    await pg.screenshot(path=f'{SHOTS}/b273-hero-{width}.png')

    # tap the slide's text (not the Play button): the podcast plays
    box = await pg.evaluate("(()=>{ const r = document.querySelector('#npHero .nph-slide .nph-desc').getBoundingClientRect(); return [r.left + 20, r.top + r.height/2]; })()")
    await pg.evaluate('window.__calls.length = 0')
    await pg.touchscreen.tap(box[0], box[1]); await pg.wait_for_timeout(1200)
    cur = await pg.evaluate("(()=>({ name: document.getElementById('playerName') && document.getElementById('playerName').textContent, view: document.getElementById('nowPlayingScreen') ? getComputedStyle(document.getElementById('nowPlayingScreen')).display : '' }))()")
    calls = await pg.evaluate("window.__calls.filter(function(c){ return c[0] === 'load' || c[0] === 'play' || c[0] === 'resume'; }).map(function(c){ return c[0]; })")
    check('Dragunov' in (cur['name'] or '') and calls, f'{T} a tap on the podcast slide (not its Play button) plays it {cur} {calls}')
    await pg.screenshot(path=f'{SHOTS}/b273-hero-tapped-{width}.png')
    # a second tap leaves it playing
    await pg.evaluate("window.__emit && window.__emit('state', {id: window.__cur, state:'ready', isPlaying:true, playWhenReady:true, position:10, duration:1800, live:false})"); await pg.wait_for_timeout(300)
    await pg.touchscreen.tap(box[0], box[1]); await pg.wait_for_timeout(500)
    pp = await pg.evaluate("document.querySelector('#npHero .nph-slide .nph-play').dataset.state")
    check(pp == 'pause', f'{T} tapping the slide that is playing leaves it playing (button shows {pp})')

    # Continue Watching: a channel watched from My Channels, then the heading
    await pg.evaluate("document.querySelector('.mobile-nav-btn[data-nav=home]').click()"); await pg.wait_for_timeout(800)
    await pg.evaluate("document.querySelector('#channelsHomeGrid .tile').click()"); await pg.wait_for_timeout(1000)
    await pg.evaluate("document.getElementById('npBackBtn') && document.getElementById('npBackBtn').click()"); await pg.wait_for_timeout(600)
    await pg.evaluate("document.querySelector('.mobile-nav-btn[data-nav=home]').click()"); await pg.wait_for_timeout(800)
    await pg.evaluate("document.getElementById('continueWatchingHomeHeading').scrollIntoView({block:'center'})"); await pg.wait_for_timeout(300)
    await pg.screenshot(path=f'{SHOTS}/b273-home-cw-{width}.png')
    await pg.evaluate("document.getElementById('continueWatchingHomeHeading').click()"); await pg.wait_for_timeout(900)
    pgst = await pg.evaluate("""(()=>({ h: document.getElementById('stationsHeading').textContent.trim(),
        rows: Array.from(document.querySelectorAll('#stationsGrid .cw-row .song-row-title')).map(x => x.textContent),
        tabs: !!document.querySelector('#stationsGrid .video-tabs'), back: !!document.querySelector('#sectionHeadingRow [class*=back]:not([style*="none"])') }))()""")
    check(pgst['h'] == 'Continue Watching' and pgst['rows'] == ['PBS'] and not pgst['tabs'], f'{T} the heading opens the Continue Watching page, not Watch / Live TV {pgst}')
    await pg.evaluate("window.scrollTo(0,0)"); await pg.screenshot(path=f'{SHOTS}/b273-cw-page-{width}.png')
    await pg.evaluate("document.getElementById('detailBackBtn').click()"); await pg.wait_for_timeout(900)
    home = await pg.evaluate("getComputedStyle(document.getElementById('continueWatchingHomeSection')).display !== 'none'")
    check(home, f'{T} back returns Home')
    check(not errs, f'{T} no page errors {errs}')
    await b.close()

async def main():
    async with async_playwright() as p:
        for w in (390, 360, 412):
            await run(p, w)
    print('ALL PASSED' if not fails else f'FAILED {fails}')
asyncio.run(main())
