"""Build 227: the Podcasts page's Latest list shows every recent episode of each followed show, not
just its newest (Mark: WhatCulture posts several a day and only one showed). Recent episodes are kept
in their own storage key (radioPlayerPodcastRecent), not inside the subscriptions; opening a show's
page also updates the list. Run: python3 tests/test_podcast_recent.py (screenshots in /tmp/claude-0/t/shots)"""
import asyncio, os, json, threading, http.server, functools, shutil, sys, re
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse, parse_qs
from playwright.async_api import async_playwright

PORT = 8817
root = '/tmp/claude-0/t/srv-podrecent'
SHOTS = '/tmp/claude-0/t/shots'
os.makedirs(SHOTS, exist_ok=True)
shutil.rmtree(root, ignore_errors=True); os.makedirs(root)
_src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'www', 'index.html')).read()
_mark = '  var coverFlow = null;\n'
assert _src.count(_mark) == 1
open(root + '/index.html', 'w').write(_src.replace(_mark, _mark + "window.__p = { show: function(id){ pushView(); openShowPage(id); }, latest: function(){ podcastTab = 'latest'; openPodcastsHome(); } };\n"))
class Q(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a): pass
srv = http.server.ThreadingHTTPServer(('127.0.0.1', PORT), functools.partial(Q, directory=root))
threading.Thread(target=srv.serve_forever, daemon=True).start()

now = datetime.now(timezone.utc).replace(microsecond=0)
def iso(h): return (now - timedelta(hours=h)).strftime('%Y-%m-%dT%H:%M:%SZ')
# WhatCulture: five today-ish and four the day before; a quiet show: one; an old one: three weeks ago.
EPS = {
  101: [('WC Money in the Bank', 1), ('WC NEWS - TNA', 2), ('WC Raw Preview', 3), ('WC NEWS - Carmelo', 4), ('WC 8 Times', 26),
        ('WC Ups & Downs', 27), ('WC NEWS - Your WWE', 28), ('WC 10 NXT', 29), ('WC Older', 30)],
  102: [('Helwani Show', 5)],
  103: [('Weekly wrap', 21 * 24)],
}
NAMES = {101: 'WhatCulture Wrestling', 102: 'The Ariel Helwani Show', 103: 'Weekly'}
def itunes_ep(cid, i, title, h):
    return {'wrapperType': 'podcastEpisode', 'kind': 'podcast-episode', 'collectionId': cid, 'collectionName': NAMES[cid],
            'trackId': cid * 1000 + i, 'trackName': title, 'releaseDate': iso(h), 'trackTimeMillis': 1200000 + i * 60000,
            'episodeUrl': f'https://pod.example/{cid}/{i}.mp3', 'episodeGuid': f'g-{cid}-{title}', 'description': 'Notes ' * 80}
def lookup(cid, limit):
    show = {'wrapperType': 'track', 'kind': 'podcast', 'collectionId': cid, 'collectionName': NAMES[cid], 'artistName': 'Host',
            'feedUrl': f'https://pod.example/{cid}.xml'}
    eps = [itunes_ep(cid, i, t, h) for i, (t, h) in enumerate(EPS[cid])][:limit]
    return {'resultCount': 1 + len(eps), 'results': [show] + eps}
# Saved the way an older build left it: only each show's newest episode.
SUBS = [{'collectionId': c, 'collectionName': NAMES[c], 'artistName': 'Host', 'artworkUrl': '', 'feedUrl': '',
         'latestEpisode': {'type': 'podcast', 'guid': f'g-{c}-{EPS[c][0][0]}', 'name': EPS[c][0][0], 'collectionId': c,
                           'collectionName': NAMES[c], 'releaseDate': iso(EPS[c][0][1]), 'duration': 1200,
                           'episodeUrl': f'https://pod.example/{c}/0.mp3'}} for c in (101, 102, 103)]
fails = 0
def check(ok, msg):
    global fails
    print(('PASS ' if ok else 'FAIL ') + msg); fails += 0 if ok else 1
calls = []
offline = {'on': False}
async def route(r):
    u = urlparse(r.request.url)
    if u.hostname == '127.0.0.1': return await r.continue_()
    if u.hostname == 'itunes.apple.com' and u.path == '/lookup' and not offline['on']:
        q = parse_qs(u.query); cid = int(q['id'][0].split(',')[0]); cb = q['callback'][0]
        calls.append((cid, int(q.get('limit', ['40'])[0])))
        body = cb + '(' + json.dumps(lookup(cid, int(q.get('limit', ['40'])[0]))) + ');'
        return await r.fulfill(status=200, content_type='application/javascript', body=body)
    return await r.abort()
ROWS = """Array.prototype.map.call(document.querySelectorAll('#stationsGrid .podcast-date-row'), function(r){ return r.querySelector('.song-row-title').textContent; })"""

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
        ctx = await b.new_context(viewport={'width': 390, 'height': 844}, device_scale_factor=2, is_mobile=True, has_touch=True, color_scheme='dark', locale='en-US')
        await ctx.add_init_script("if(!sessionStorage.getItem('s')){ sessionStorage.setItem('s','1'); localStorage.setItem('radioPlayerPodcastSubs', %s); }" % json.dumps(json.dumps(SUBS)))
        pg = await ctx.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.route('**/*', route)
        await pg.goto(f'http://127.0.0.1:{PORT}/index.html'); await pg.wait_for_timeout(2000)
        await pg.evaluate("document.querySelector('.mobile-nav-btn[data-nav=podcasts]').click()")
        for _ in range(40):
            await pg.wait_for_timeout(500)
            if len(await pg.evaluate(ROWS)) >= 10: break
        rows = await pg.evaluate(ROWS); print(rows)
        wc = [t for t in rows if t.startswith('WC ')]
        check(len(wc) == 9, f'every recent WhatCulture episode is listed, not just the newest ({len(wc)} of 9)')
        check('Helwani Show' in rows, 'and the other shows still are')
        check(rows[:5] == ['WC Money in the Bank', 'WC NEWS - TNA', 'WC Raw Preview', 'WC NEWS - Carmelo', 'Helwani Show'], f'newest first {rows[:5]}')
        check(all(l >= 40 for _, l in calls), f'each show asked for its recent episodes, not 1 {calls[:3]}')
        heads = await pg.evaluate("Array.prototype.map.call(document.querySelectorAll('#stationsGrid .podcast-date-heading'), function(h){ return h.textContent; })")
        print(heads)
        await pg.screenshot(path=f'{SHOTS}/podcast-recent.png')
        st = await pg.evaluate("[localStorage.getItem('radioPlayerPodcastSubs'), localStorage.getItem('radioPlayerPodcastRecent')]")
        check('recentEpisodes' not in st[0] and st[1] and len(json.loads(st[1])['101']) == 9, 'recent episodes are stored on their own, not in the followed shows')
        check(len(st[1]) < 12000, f'and kept small ({len(st[1])} bytes for 13 episodes)')
        # restart offline: still all there
        offline['on'] = True
        await pg.reload(); await pg.wait_for_timeout(2000)
        await pg.evaluate("document.querySelector('.mobile-nav-btn[data-nav=podcasts]').click()"); await pg.wait_for_timeout(1500)
        rows2 = await pg.evaluate(ROWS)
        check(rows2 == rows, f'after a restart (offline), the same list ({len(rows2)} rows)')
        # a new episode, seen on the show's page, shows in the list straight away
        offline['on'] = False
        EPS[101].insert(0, ('WC Brand New', 0.1))
        await pg.evaluate("__p.show(101)"); await pg.wait_for_timeout(1500)
        showRows = await pg.evaluate("Array.prototype.map.call(document.querySelectorAll('#stationsGrid .song-row-title'), function(r){ return r.textContent; })")
        check('WC Brand New' in showRows, f'(the show page lists the new episode) {showRows[:2]}')
        await pg.evaluate("__p.latest()"); await pg.wait_for_timeout(800)
        rows3 = await pg.evaluate(ROWS)
        check(rows3[:1] == ['WC Brand New'] and len([t for t in rows3 if t.startswith('WC ')]) == 10, f'an episode seen on the show page is in the list at once {rows3[:3]}')
        check(not errs, f'no page errors {errs[:3]}')
        await b.close()
    print('ALL PASSED' if not fails else f'{fails} FAILED')
    sys.exit(1 if fails else 0)

asyncio.run(main())
