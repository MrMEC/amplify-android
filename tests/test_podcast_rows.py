"""Build 181: on the Podcasts page (Latest and category tabs) an episode row no longer repeats its
date (the date heading above it already says it): the line under the title is just the length.
Elsewhere (a show's page, Now Playing's More Episodes) the date stays.
Run: python3 tests/test_podcast_rows.py (screenshots in /tmp/claude-0/t/shots)"""
import asyncio, os, json, threading, http.server, functools, shutil
from playwright.async_api import async_playwright

PORT = 8816
root = '/tmp/claude-0/t/srv-podrows'
SHOTS = '/tmp/claude-0/t/shots'
os.makedirs(SHOTS, exist_ok=True)
shutil.rmtree(root, ignore_errors=True); os.makedirs(root)
shutil.copy(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'www', 'index.html'), root + '/index.html')
class Q(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a): pass
srv = http.server.ThreadingHTTPServer(('127.0.0.1', PORT), functools.partial(Q, directory=root))
threading.Thread(target=srv.serve_forever, daemon=True).start()

def ep(cid, show, title, date, dur):
    return {'type': 'podcast', 'guid': f'g-{cid}', 'name': title, 'collectionId': cid, 'collectionName': show,
            'releaseDate': date, 'duration': dur, 'episodeUrl': f'https://pod.example/{cid}.mp3', 'artworkUrl': ''}
SUBS = [
  {'collectionId': 1, 'collectionName': 'Morning Show', 'artistName': 'Host', 'artworkUrl': '', 'feedUrl': 'https://pod.example/1',
   'latestEpisode': ep(1, 'Morning Show', 'A long episode title that runs on to a second line in the row', '2026-10-08T10:00:00Z', 3725)},
  {'collectionId': 2, 'collectionName': 'Evening Show', 'artistName': 'Host', 'artworkUrl': '', 'feedUrl': 'https://pod.example/2',
   'latestEpisode': ep(2, 'Evening Show', 'Short one', '2026-10-08T18:00:00Z', 1500)},
  {'collectionId': 3, 'collectionName': 'Weekly', 'artistName': 'Host', 'artworkUrl': '', 'feedUrl': 'https://pod.example/3',
   'latestEpisode': ep(3, 'Weekly', 'The weekly wrap', '2026-10-02T12:00:00Z', 2700)},
]
fails = 0
def check(ok, msg):
    global fails
    print(('PASS ' if ok else 'FAIL ') + msg); fails += 0 if ok else 1

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
        ctx = await b.new_context(viewport={'width': 390, 'height': 844}, device_scale_factor=2, is_mobile=True, has_touch=True, color_scheme='dark', locale='en-US')
        await ctx.add_init_script("localStorage.setItem('radioPlayerPodcastSubs', %s)" % json.dumps(json.dumps(SUBS)))
        pg = await ctx.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.route('**/*', lambda r: r.continue_() if '127.0.0.1' in r.request.url else r.abort())
        await pg.goto(f'http://127.0.0.1:{PORT}/index.html'); await pg.wait_for_timeout(2000)
        await pg.evaluate("document.querySelector('.mobile-nav-btn[data-nav=podcasts]').click()"); await pg.wait_for_timeout(1200)
        rows = await pg.evaluate("""Array.prototype.map.call(document.querySelectorAll('#stationsGrid .podcast-date-row'), function(r){
          var s = r.querySelector('.song-row-sub'); return [r.querySelector('.song-row-title').textContent, s ? s.textContent : null]; })""")
        heads = await pg.evaluate("Array.prototype.map.call(document.querySelectorAll('#stationsGrid .podcast-date-heading'), function(h){ return h.textContent; })")
        print(heads, rows)
        check(len(rows) == 3 and [r[1] for r in rows] == ['25:00', '1:02:05', '45:00'],
              f'Latest: each row shows only its length {rows}')
        check(len(heads) == 2 and not any('2026' in (r[1] or '') or 'Oct' in (r[1] or '') for r in rows), f'dates only in the headings {heads}')
        await pg.screenshot(path=f'{SHOTS}/podrows-latest.png')
        check(not errs, f'no page errors {errs[:3]}')
        await b.close()
    print('ALL PASSED' if not fails else f'{fails} FAILED')

asyncio.run(main())
