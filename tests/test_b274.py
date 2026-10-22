"""Build 274 (Mark: "I load the app and sit and wait for the newest episodes"): Android reads every
followed show's own feed in the background (PodcastFeeds / PodcastRefreshWorker) and the page shows
what it saved the moment it starts, before any network; then one native read of all feeds replaces
the paced Apple lookups (Apple only for shows the feeds didn't cover). Coming back to the app does
the same. Apple's possibly older list never removes a newer feed episode.
Run: python3 tests/test_b274.py (screenshots in /tmp/claude-0/t/shots)"""
import sys as _nsys, os as _nos; _nsys.path.insert(0, _nos.path.dirname(_nos.path.abspath(__file__))); from notice_auto import AUTO_NOTICE
import asyncio, os, json, sys
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse, parse_qs
HERE = os.path.dirname(os.path.abspath(__file__))
src = open(os.path.join(HERE, 'test_video_library.py')).read()
head = src[:src.index('async def names(pg, sel)')]
head = head.replace('8780', '8874').replace("'/tmp/claude-0/t/srv-vlib'", "'/tmp/claude-0/t/srv-b274'")
exec(head)
_src = open(os.path.join(HERE, '..', 'www', 'index.html')).read(); _mark = '  var coverFlow = null;\n'; assert _src.count(_mark) == 1
open(os.path.join(ROOT, 'index.html'), 'w').write(_src.replace(_mark, _mark + "window.__t = { subs: function(){ return podcastSubs; }, bf: function(m, ids){ return backfillPodcastShowMeta(m, ids); } };\n"))
from playwright.async_api import async_playwright

now = datetime.now(timezone.utc).replace(microsecond=0)
def iso(h): return (now - timedelta(hours=h)).strftime('%Y-%m-%dT%H:%M:%SZ')
NAMES = {101: 'WhatCulture Wrestling', 102: 'The Ariel Helwani Show', 103: 'No Feed Show'}
def slim(cid, title, h, video=0):
    return {'g': f'g-{cid}-{title}', 'n': title, 'd': iso(h), 't': 1800, 'u': f'https://pod.example/{cid}/{title.replace(" ", "_")}.mp3',
            'f': '', 's': f'Notes for {title}', 'v': video}
# Last session left yesterday's episodes.
SUBS = [{'collectionId': c, 'collectionName': NAMES[c], 'artistName': 'Host', 'artworkUrl': f'/c/art{c}.jpg', 'feedUrl': f'https://pod.example/{c}.xml' if c != 103 else '',
         'latestEpisode': {'type': 'podcast', 'guid': f'g-{c}-Yesterday {c}', 'name': f'Yesterday {c}', 'collectionId': c, 'collectionName': NAMES[c],
                           'releaseDate': iso(20), 'duration': 1200, 'episodeUrl': f'https://pod.example/{c}/y.mp3'}} for c in (101, 102, 103)]
RECENT = {str(c): [{'g': f'g-{c}-Yesterday {c}', 'n': f'Yesterday {c}', 'd': iso(20), 't': 1200, 'u': f'https://pod.example/{c}/y.mp3', 'f': '', 's': '', 'v': 0}] for c in (101, 102, 103)}
# What the overnight background refresh saved (an hour ago): this morning's episodes.
BG = {'at': 0, 'ok': 2, 'total': 3, 'shows': {
  '101': {'ok': True, 'feedUrl': 'https://pod.example/101.xml', 'eps': [slim(101, 'NEWS - Ilja Dragunov Injury Update', 2), slim(101, 'Raw Review', 6), slim(101, 'Yesterday 101', 20)]},
  '102': {'ok': True, 'feedUrl': 'https://pod.example/102.xml', 'eps': [slim(102, 'Helwani Morning', 3)]},
  '103': {'ok': False, 'feedUrl': '', 'err': 'no feed'}}}
# What a fresh read finds now.
FRESH = json.loads(json.dumps(BG)); FRESH['shows']['101']['eps'].insert(0, slim(101, 'Brand New Just Now', 0.2))

PODMOCK = """(function(){ var P = window.Capacitor.Plugins.AmplifyPlayer; window.__pc = { get: 0, refresh: 0 };
  window.__bg = %s; window.__fresh = %s;
  window.Capacitor.Plugins.AmplifyPlayer = new Proxy({}, { get: function(t, k){
    if(k === 'podcastFeedsGet') return function(){ window.__pc.get++; return Promise.resolve(JSON.parse(JSON.stringify(window.__bg))); };
    if(k === 'podcastRefresh') return function(){ window.__pc.refresh++; var r = JSON.parse(JSON.stringify(window.__fresh)); r.at = Date.now();
      return new Promise(function(res){ setTimeout(function(){ res(r); }, window.__refreshDelay || 300); }); };
    return P[k]; } });
})();""" % (json.dumps(BG), json.dumps(FRESH))

itunes = []
async def route2(r):
    u = urlparse(r.request.url)
    if u.hostname == 'itunes.apple.com' and u.path == '/lookup':
        q = parse_qs(u.query); cid = int(q['id'][0].split(',')[0]); cb = q['callback'][0]; itunes.append(cid)
        show = {'wrapperType': 'track', 'kind': 'podcast', 'collectionId': cid, 'collectionName': NAMES.get(cid, 'x'), 'artistName': 'Host', 'feedUrl': ''}
        # Apple's copy trails: it only knows yesterday's episode
        ep = {'wrapperType': 'podcastEpisode', 'kind': 'podcast-episode', 'collectionId': cid, 'collectionName': NAMES.get(cid, 'x'), 'trackId': cid * 10,
              'trackName': f'Yesterday {cid}', 'releaseDate': iso(20), 'episodeUrl': f'https://pod.example/{cid}/y.mp3', 'episodeGuid': f'g-{cid}-Yesterday {cid}'}
        return await r.fulfill(status=200, content_type='application/javascript', body=cb + '(' + json.dumps({'resultCount': 2, 'results': [show, ep]}) + ');')
    return await route(r)

LATEST = """Array.prototype.map.call(document.querySelectorAll('#latestPodcastsGrid .tile .tile-name, #latestPodcastsGrid .tile-name'), function(t){ return t.textContent; })"""
HERO = """Array.prototype.map.call(document.querySelectorAll('#npHero .nph-slide .nph-sub, #npHero .nph-slide .nph-ep'), function(t){ return t.textContent; })"""

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
        ctx = await b.new_context(viewport={'width': 390, 'height': 844}, device_scale_factor=3, is_mobile=True, has_touch=True, color_scheme='dark', locale='en-US')
        await ctx.add_init_script(MOCK); await ctx.add_init_script(AUTO_NOTICE); await ctx.add_init_script(EXT); await ctx.add_init_script(PODMOCK)
        await ctx.add_init_script("window.__bg.at = Date.now() - 3600000; window.__fresh.at = 0;")
        await ctx.add_init_script("if(!localStorage.getItem('radioPlayerPodcastSubs')){ localStorage.setItem('radioPlayerPodcastSubs', %s); localStorage.setItem('radioPlayerPodcastRecent', %s); }"
                                  % (repr(json.dumps(SUBS)), repr(json.dumps(RECENT))))
        pg = await ctx.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e) + ' @ ' + (e.stack or '')[:300]))
        await pg.route('**/*', route2)
        await pg.add_init_script("window.__refreshDelay = 4000;")  # a slow network: the saved result must not wait for it
        await pg.goto('http://127.0.0.1:8874/index.html'); await pg.wait_for_timeout(1500)
        await pg.evaluate("document.querySelector('.mobile-nav-btn[data-nav=home]').click()"); await pg.wait_for_timeout(700)
        # 1) at once, before the fresh read answers: the background refresh's episodes
        st = await pg.evaluate("(()=>({ pc: window.__pc, subs: __t.subs().map(function(s){ return [s.collectionId, s.latestEpisode && s.latestEpisode.name, (s.recentEpisodes||[]).map(function(e){return e.name;})]; }) }))()")
        print(st)
        s101 = [x for x in st['subs'] if x[0] == 101][0]; s102 = [x for x in st['subs'] if x[0] == 102][0]
        check(st['pc']['get'] == 1, 'the background refresh\'s saved result is read at start')
        check(s101[1] == 'NEWS - Ilja Dragunov Injury Update' and s101[2][:3] == ['NEWS - Ilja Dragunov Injury Update', 'Raw Review', 'Yesterday 101'],
              f'this morning\'s episodes are there at once, before any network answer {s101}')
        check(s102[1] == 'Helwani Morning', 'for every show with a feed')
        latest = await pg.evaluate(LATEST); print('home latest', latest)
        check(any('Ilja' in t for t in latest) or any('Ilja' in t for t in await pg.evaluate("Array.from(document.querySelectorAll('#npHero .nph-slide')).map(function(s){return s.textContent;})")),
              'Home shows them (latest podcasts / hero)')
        await pg.screenshot(path=f'{SHOTS}/b274-home-at-start.png')
        # 2) background saved an hour ago (> 5 min): one native read of every feed, not one Apple lookup per show
        check(st['pc']['refresh'] == 1, f'one fresh native read of all feeds on start {st["pc"]}')
        check(await pg.evaluate("document.getElementById('podcastRefreshHeaderBtn').classList.contains('refreshing')"), 'refresh button shows it is working meanwhile')
        await pg.wait_for_timeout(4500)
        names101 = await pg.evaluate("(__t.subs().filter(function(s){return s.collectionId==101})[0].recentEpisodes||[]).map(function(e){return e.name;})")
        check(names101[:1] == ['Brand New Just Now'], f'the fresh read adds the newest episode {names101[:3]}')
        await pg.wait_for_timeout(1500)
        print('itunes lookups', itunes)
        check(itunes == [103], f'Apple is asked only about the show whose feed could not be read {itunes}')
        names101b = await pg.evaluate("(__t.subs().filter(function(s){return s.collectionId==101})[0].recentEpisodes||[]).map(function(e){return e.name;})")
        check(names101b == names101, 'nothing lost')
        # Apple's older list for a show never takes its newer feed episodes away
        await pg.evaluate("__t.bf('manual', {101: 1})"); await pg.wait_for_timeout(1500)
        names101c = await pg.evaluate("(__t.subs().filter(function(s){return s.collectionId==101})[0].recentEpisodes||[]).map(function(e){return e.name;})")
        le = await pg.evaluate("__t.subs().filter(function(s){return s.collectionId==101})[0].latestEpisode.name")
        check(names101c[:2] == ['Brand New Just Now', 'NEWS - Ilja Dragunov Injury Update'] and le == 'Brand New Just Now', f'Apple\'s older list keeps the feed\'s newer episodes {names101c} / {le}')
        check(names101c.count('Yesterday 101') == 1, 'one copy of an episode both know')
        # 3) Podcasts page Latest list
        await pg.evaluate("document.querySelector('.mobile-nav-btn[data-nav=podcasts]').click()"); await pg.wait_for_timeout(1200)
        rows = await pg.evaluate("Array.prototype.map.call(document.querySelectorAll('#stationsGrid .song-row-title'), function(r){ return r.textContent; })")
        print('podcasts rows', rows)
        check(rows[:3] == ['Brand New Just Now', 'NEWS - Ilja Dragunov Injury Update', 'Helwani Morning'], f'Podcasts > Latest, newest first {rows[:4]}')
        await pg.screenshot(path=f'{SHOTS}/b274-podcasts.png')
        n_before = await pg.evaluate("window.__pc.refresh")
        await pg.evaluate("document.querySelector('.mobile-nav-btn[data-nav=home]').click()"); await pg.wait_for_timeout(500)
        # 5) coming back to the app later: saved result read again, fresh read if over 5 minutes
        await pg.evaluate("window.__bg = JSON.parse(JSON.stringify(window.__fresh)); window.__bg.at = Date.now(); window.__bg.shows['102'].eps.unshift(%s);" % json.dumps(slim(102, 'Helwani Lunch', 0.1)))
        await pg.evaluate("Object.defineProperty(document, 'hidden', {configurable: true, get: function(){ return false; }}); document.dispatchEvent(new Event('visibilitychange'))")
        await pg.wait_for_timeout(1500)
        r = await pg.evaluate("({ pc: window.__pc, le: __t.subs().filter(function(s){return s.collectionId==102})[0].latestEpisode.name })")
        check(r['le'] == 'Helwani Lunch', f'coming back to the app shows what the background found meanwhile {r}')
        check(r['pc']['refresh'] == n_before, 'and does not read every feed again when the background did minutes ago')
        await pg.screenshot(path=f'{SHOTS}/b274-home-resume.png')
        check(not errs, f'no page errors {errs[:3]}')
        await b.close()
    print('ALL PASSED' if not fails else f'{fails} FAILED')
    sys.exit(1 if fails else 0)

asyncio.run(main())
