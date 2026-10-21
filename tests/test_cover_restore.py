"""Build 272 (Mark: many covers no longer appearing on Home):
- covers uploaded for a custom station and a playlist (kept only in IndexedDB, which answers after the
  page draws) show on Home's Favorites, as an uploaded station cover already did;
- a station whose logo lookup once found nothing still shows its own logo (favicon);
- a miss older than a day is looked up again (here: the site's apple-touch-icon); a fresh one is not.
Run: python3 tests/test_cover_restore.py [index.html]  (exit 1 on failure; screenshot in /tmp/claude-0/t/shots)"""
import asyncio, os, json, threading, http.server, functools, shutil, base64, sys, subprocess
from playwright.async_api import async_playwright
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); from notice_auto import AUTO_NOTICE

PORT = 8871
root = '/tmp/claude-0/t/srv-covers'
shutil.rmtree(root, ignore_errors=True); os.makedirs(root)
SRC = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'www', 'index.html')
shutil.copy(SRC, root + '/index.html')
class Q(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a): pass
threading.Thread(target=http.server.ThreadingHTTPServer(('127.0.0.1', PORT), functools.partial(Q, directory=root)).serve_forever, daemon=True).start()
subprocess.run(['ffmpeg', '-loglevel', 'error', '-y', '-f', 'lavfi', '-i', 'mandelbrot=size=300x300:rate=1', '-frames:v', '1', root + '/c.png'], check=True)
PNG = open(root + '/c.png', 'rb').read()
DATA = 'data:image/png;base64,' + base64.b64encode(PNG).decode()

def st(uuid, name, **kw):
    d = {'name': name, 'stationuuid': uuid, 'url': 'https://s/' + uuid, 'urlToResolve': 'https://s/' + uuid, 'favicon': '', 'tags': '', 'country': ''}
    d.update(kw); return d
FAVS = [{'type': 'customStation', 'searchId': 'c1', 'name': "80's 80's", 'stationuuid': 'customstation:c1'},
        st('s1', 'Relaxing Calm', favicon='https://img.example/relax.png'),
        st('s2', 'Uploaded Cover Station'),
        {'type': 'playlistRadio', 'playlistId': 'p1', 'name': 'Mix', 'stationuuid': 'playlistradio:p1'},
        st('s3', 'Old Miss', homepage='https://oldmiss.example/'),
        st('s4', 'Fresh Miss', homepage='https://freshmiss.example/')]
SEARCHES = [{'id': 'c1', 'label': "80's 80's", 'query': '80s'}]
PLS = [{'id': 'p1', 'label': 'Mix', 'stations': []}]
SEED = """(function(){ if(localStorage.getItem('__s')) return; localStorage.setItem('__s','1');
 localStorage.setItem('radioPlayerFavorites', %s); localStorage.setItem('radioPlayerCustomSearches', %s);
 localStorage.setItem('radioPlayerStationPlaylists', %s);
 var now = Date.now();
 localStorage.setItem('radioPlayerArtCache', JSON.stringify({ s1: { url: null, ts: now - 3600000 }, s3: { url: null, ts: now - 2 * 86400000 }, s4: { url: null, ts: now - 3600000 } }));
 var r = indexedDB.open('amplifyCustomArt', 1); r.onupgradeneeded = function(){ r.result.createObjectStore('art'); };
 r.onsuccess = function(){ var tx = r.result.transaction('art','readwrite'); var s = tx.objectStore('art');
   s.put(%s, 'foryouart:c1'); s.put(%s, 's2'); s.put(%s, 'playlistart:p1'); };
})();""" % tuple(json.dumps(x) for x in (json.dumps(FAVS), json.dumps(SEARCHES), json.dumps(PLS), DATA, DATA, DATA))

HITS = []
fails = []
def check(c, m):
    print(('PASS ' if c else 'FAIL ') + m)
    if not c: fails.append(m)

async def route(r):
    u = r.request.url
    if '127.0.0.1' in u or u.startswith('data:'): return await r.continue_()
    if 'freshmiss.example' in u: HITS.append(u)
    if 'img.example' in u or ('oldmiss.example' in u and 'apple-touch-icon.png' in u):
        return await r.fulfill(body=PNG, content_type='image/png', headers={'Access-Control-Allow-Origin': '*'})
    if '/json/' in u: return await r.fulfill(body='[]', content_type='application/json', headers={'Access-Control-Allow-Origin': '*'})
    return await r.abort()

TILES = """Array.from(document.querySelectorAll('[id*=avorites] .tile')).map(function(t){ var a = t.querySelector('.tile-art'), i = a && a.querySelector('img');
  return [t.dataset.key, !!i, i ? (i.complete && i.naturalWidth) : null]; })"""

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
        ctx = await b.new_context(viewport={'width': 412, 'height': 900}, device_scale_factor=2, is_mobile=True, has_touch=True, color_scheme='dark')
        await ctx.add_init_script(SEED); await ctx.add_init_script(AUTO_NOTICE)
        await ctx.route('**/*', route)
        pg = await ctx.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.goto(f'http://127.0.0.1:{PORT}/index.html'); await pg.wait_for_timeout(2500)
        await pg.reload(); await pg.wait_for_timeout(5000)   # second start: the covers are in IndexedDB only
        res = await pg.evaluate(TILES); print(res)
        got = {k: (i, w) for k, i, w in res}
        check(got.get('customstation:c1') == (True, 300), "a custom station's uploaded cover shows (80's 80's)")
        check(got.get('playlistradio:p1') == (True, 300), "a playlist's uploaded cover shows")
        check(got.get('s2') == (True, 300), "a station's uploaded cover shows")
        check(got.get('s1') == (True, 300), 'a station whose lookup once found nothing still shows its own logo')
        check(got.get('s3') == (True, 300), 'a miss older than a day is looked up again and found')
        check(got.get('s4') == (False, None) and not HITS, f'a fresh miss is not looked up again {HITS}')
        os.makedirs('/tmp/claude-0/t/shots', exist_ok=True)
        await pg.evaluate("document.querySelector('[id*=avorites] .tile').scrollIntoView({block:'center'})"); await pg.wait_for_timeout(1500)
        await pg.screenshot(path='/tmp/claude-0/t/shots/cover-restore.png')
        check(not errs, f'no page errors {errs[:3]}')
        await b.close()

asyncio.run(main())
print('ALL PASSED' if not fails else f'{len(fails)} FAILED'); sys.exit(1 if fails else 0)
