"""Build 617: Live TV channel management at Mark's phone size (327 x 709 CSS px, dpr 3.3).
 1. Add or Manage Channels is under the guide on the Live TV page (not only under a playing channel).
 2. Its menu has Build a Custom Channel; Add Channels > My Shows & Movies no longer has that card.
 3. Arrange Channels (Edit): a finger anywhere on the list scrolls it (CDP touch swipe over a row).
 4. Select: tick several channels (your own + added), Remove N Channels asks first, then removes them.
 5. The channel editor can add archive.org videos (video only), mixed with library shows, in one channel;
    the channel is scheduled from those videos and shows them in the guide.
Run: python3 tests/test_live_manage_select.py [path-to-index.html]  (screenshots in /tmp/claude-0/t/shots)"""
import sys as _nsys, os as _nos; _nsys.path.insert(0, _nos.path.dirname(_nos.path.abspath(__file__))); from notice_auto import AUTO_NOTICE
import os, json, sys, asyncio
HERE = os.path.dirname(os.path.abspath(__file__))
src = open(os.path.join(HERE, 'test_live_channels.py')).read()
head = src[:src.index('\nasync def run(')]
APP = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, '..', 'www', 'index.html')
TAG = sys.argv[2] if len(sys.argv) > 2 else 'new'
head = head.replace("'/tmp/claude-0/t/srv-livech'", "'/tmp/claude-0/t/srv-spot-%s'" % TAG).replace('PORT = 8862', 'PORT = %d' % (8880 if TAG == 'new' else 8881))
head = head.replace("shutil.copy(os.path.join(HERE, '..', 'www', 'index.html'), ROOT)", "shutil.copy(APP, os.path.join(ROOT, 'index.html'))")
exec(head)

# A realistic long list: nine of your own channels (four default + five) and 14 added channels.
OWN_EXTRA = [
    {'id': 'x1', 'name': 'Friends Marathon', 'src': {'kind': 'pick', 'shows': ['Friends'], 'movies': []}, 'order': 'sequence'},
    {'id': 'x2', 'name': 'Comedy Mix', 'src': {'kind': 'pick', 'shows': ['MADtv', 'Seinfeld'], 'movies': []}, 'order': 'shuffle'},
    {'id': 'x3', 'name': 'Office Shuffle', 'src': {'kind': 'pick', 'shows': ['The Office (US)'], 'movies': []}, 'order': 'daily'},
    {'id': 'x4', 'name': 'Everything Sitcom', 'src': {'kind': 'pick', 'shows': ['The Office (US)', 'MADtv', 'Seinfeld', 'Friends'], 'movies': []}, 'order': 'sequence'},
    {'id': 'x5', 'name': 'Late Night Laughs', 'src': {'kind': 'pick', 'shows': ['MADtv'], 'movies': []}, 'order': 'sequence'},
]
ADDED = [{'id': 'pluto:%02d' % i, 'name': n, 'url': 'https://example.test/live/%02d/master.m3u8' % i, 'logo': '', 'cats': ['Classic TV'], 'catNames': ['Classic TV'], 'src': 'pluto'}
         for i, n in enumerate(['Buzzr', 'Black Classics', 'Batman', 'BTTF', 'Cartoons', 'Classic TV', 'Comedy Central Classics', 'Bewitched', 'Animation', 'Pluto TV Action',
                                'Pluto TV Mystery', 'Pluto TV Sci-Fi', 'Pluto TV Westerns', 'Pluto TV Game Shows'])]
DEFAULTS = [
    {'id': 'office', 'name': '', 'src': {'kind': 'pick', 'shows': ['The Office'], 'movies': []}, 'order': 'sequence'},
    {'id': 'madtv', 'name': '', 'src': {'kind': 'pick', 'shows': ['MadTV'], 'movies': []}, 'order': 'sequence'},
    {'id': 'seinfeld', 'name': '', 'src': {'kind': 'pick', 'shows': ['Seinfeld'], 'movies': []}, 'order': 'sequence'},
    {'id': 'movies', 'name': 'Movies', 'src': {'kind': 'movies', 'from': 'phone'}, 'order': 'shuffle'},
]
SEED2 = """(function(){ if(!localStorage.getItem('__seeded')){ localStorage.setItem('__seeded','1');
  localStorage.setItem('radioPlayerPlexAccount', %s);
  var lib = JSON.parse(%s); lib.at = Date.now(); localStorage.setItem('radioPlayerPlexLib', JSON.stringify(lib));
  localStorage.setItem('radioPlayerVideoFiles', %s);
  localStorage.setItem('radioPlayerVideoInfo', %s);
  localStorage.setItem('radioPlayerVideoChannels', %s);
  localStorage.setItem('radioPlayerLiveChannels', %s);
  localStorage.setItem('radioPlayerVideoTab', 'channels'); } })();""" % tuple(json.dumps(json.dumps(x)) for x in (ACCT, LIB, FILES, INFO, ADDED, DEFAULTS + OWN_EXTRA))

IA_DOCS = [{'identifier': 'cartoon_one', 'title': 'Superman: The Mechanical Monsters', 'mediatype': 'movies', 'creator': 'Fleischer Studios', 'year': '1941', 'downloads': 90000},
           {'identifier': 'cartoon_two', 'title': 'Popeye the Sailor Meets Sindbad', 'mediatype': 'movies', 'creator': 'Fleischer Studios', 'year': '1936', 'downloads': 80000},
           {'identifier': 'cartoon_three', 'title': 'Betty Boop: Snow-White', 'mediatype': 'movies', 'creator': 'Fleischer Studios', 'year': '1933', 'downloads': 70000}]
LEN = {'cartoon_one': '600', 'cartoon_two': '1200', 'cartoon_three': '420'}
IA_Q = []
async def route2(r):
    u = r.request.url; pu = urlparse(u)
    if 'archive.org' in u:
        if r.request.method == 'OPTIONS': return await r.fulfill(status=204, headers=CORS)
        if 'advancedsearch' in u:
            IA_Q.append(parse_qs(pu.query).get('q', [''])[0])
            return await r.fulfill(status=200, content_type='application/json', headers=CORS, body=json.dumps({'response': {'numFound': 3, 'docs': IA_DOCS}}))
        if '/metadata/' in u:
            i = pu.path.rsplit('/', 1)[1]
            return await r.fulfill(status=200, content_type='application/json', headers=CORS, body=json.dumps({'files': [{'name': i + '.mp4', 'format': 'h.264', 'size': '9000', 'length': LEN.get(i, '300')}]}))
        return await r.fulfill(status=200, content_type='image/png', headers=CORS, body=PNG)
    if u.startswith('https://example.test'): return await r.fulfill(status=200, content_type='application/vnd.apple.mpegurl', headers=CORS, body='#EXTM3U')
    return await route(r)
from urllib.parse import parse_qs

W, H_ = 327, 709
ART = ['Taylor Swift','Queen','Bruno Mars','Adele','Coldplay','Prince','Madonna','Beyonce','Eminem','Rihanna','Drake','Nirvana','U2','ABBA','Sia','Pink','Usher','Shakira','Weezer','Blondie',
       'Lizzo','Cher','Journey','Heart','Toto','Rush','Yes','Genesis','Kiss','Bon Jovi','Foreigner','Boston','Styx','Air Supply','Cream','Dido','Enya','Lorde','Muse','Oasis']
FILES = []; INFO = {}
for n, a in enumerate(ART + ['Queen', 'Queen', 'Adele']):
    t = 'Hit Song Number %d' % n
    nm = '%s - %s.mp4' % (a, t); uri = 'content://mv/%d' % n
    FILES.append({'uri': uri, 'name': nm, 'relPath': 'Music Videos/' + nm, 'size': 90000 + n, 'lastModified': 1700000000000 + n * 1000, 'tree': 'tree:music'})
    INFO[uri] = {'d': 180 + n, 'w': 1280, 'h': 720, 't': 'https://archive.org/services/img/still%d' % n}
SEEDMV = "(function(){ if(!localStorage.getItem('__seeded')){ localStorage.setItem('__seeded','1'); localStorage.setItem('radioPlayerMusicVideos', %s); localStorage.setItem('radioPlayerVideoInfo', %s); } })();" % (json.dumps(json.dumps({'files': FILES, 'probed': {}, 'at': 5})), json.dumps(json.dumps(INFO)))

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
        ctx = await b.new_context(viewport={'width': W, 'height': H_}, device_scale_factor=3.3, is_mobile=True, has_touch=True, color_scheme='dark', locale='en-US', timezone_id='America/New_York')
        await ctx.add_init_script(MOCK); await ctx.add_init_script(AUTO_NOTICE); await ctx.add_init_script(SEEDMV)
        pg = await ctx.new_page(); cdp = await ctx.new_cdp_session(pg); errs = []; pg.on('pageerror', lambda e: errs.append(str(e) + ' ' + (e.stack or '')[:300]))
        await pg.route('**/*', route2)
        await pg.goto(f'http://127.0.0.1:{PORT}/index.html'); await pg.wait_for_timeout(3000)
        await pg.evaluate("document.querySelector('.mobile-nav-btn[data-nav=video]').click()"); await pg.wait_for_timeout(1500)
        await pg.evaluate("document.querySelector('#stationsGrid > .watch-tabs .home-tab[data-vtab=music]').click()"); await pg.wait_for_timeout(2000)
        r = await pg.evaluate("""(function(){ var g=document.getElementById('stationsGrid'); var kids=Array.from(g.children).map(function(e){return e.className.split(' ').slice(0,3).join('.')+':'+(e.textContent||'').slice(0,14)});
          var sp=g.querySelector('.mv-spotlight'); var tiles=sp?Array.from(sp.querySelectorAll('.mv-tile')):[];
          var arts=tiles.map(function(t){return t.querySelector('.yt-date').textContent}); var uniq={}; arts.forEach(function(a){uniq[a]=1});
          return {kids:kids.slice(0,6), n:tiles.length, uniq:Object.keys(uniq).length, first:tiles.slice(0,3).map(function(t){return t.querySelector('.yt-title').textContent+' | '+t.querySelector('.yt-date').textContent})} })()""")
        print(r)
        async def pull(dist, steps=24, hold=0, x=160, y0=300):
            await cdp.send('Input.dispatchTouchEvent', {'type': 'touchStart', 'touchPoints': [{'x': x, 'y': y0}]})
            for k in range(1, steps + 1):
                await cdp.send('Input.dispatchTouchEvent', {'type': 'touchMove', 'touchPoints': [{'x': x, 'y': y0 + dist * k / steps}]})
                await asyncio.sleep(0.012)
        async def lift(): await cdp.send('Input.dispatchTouchEvent', {'type': 'touchEnd', 'touchPoints': []})
        first = lambda: pg.evaluate("Array.from(document.querySelectorAll('.mv-spotlight .yt-title')).map(function(e){return e.textContent}).join('|')")
        before = await first()
        await pull(260); await pg.wait_for_timeout(100)
        print('transform mid-pull', await pg.evaluate("document.querySelector('main.main').style.transform"), await pg.evaluate("getComputedStyle(document.querySelector('.ptr-ind')).opacity"))
        await pg.screenshot(path=f'{SHOTS}/ptr-pull.png')
        await lift(); await pg.wait_for_timeout(450)
        await pg.screenshot(path=f'{SHOTS}/ptr-hold.png')
        await pg.wait_for_timeout(1800)
        after = await first()
        print('reshuffled', before != after, 'n', after.count('|') + 1, 'transform after', repr(await pg.evaluate("document.querySelector('main.main').style.transform")))
        # a short pull: no refresh, just a bounce back
        before = after
        await pull(60); await lift(); await pg.wait_for_timeout(1200)
        print('short pull same', before == await first())
        # a pull that starts scrolled down does nothing
        await pg.evaluate("window.scrollTo(0, 300)"); await pg.wait_for_timeout(300)
        await pull(260); await lift(); await pg.wait_for_timeout(300)
        print('scrolled pull transform', repr(await pg.evaluate("document.querySelector('main.main').style.transform")))
        await pg.screenshot(path=f'{SHOTS}/spot-{TAG}-1.png')
        print('errs', errs); await b.close()

asyncio.run(main())
