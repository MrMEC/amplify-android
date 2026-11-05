"""Build 479 (Mark): the playing border shows on every Home favourite that is tapped, not only
plain stations -- playlist radios, custom stations, artist radios and TV channels included.
Loads Mark's own backup (path as argument; default his Nov 1 file), taps each Home favourite and
checks that card is marked playing. Phone, dark."""
import sys as _nsys, os as _nos; _nsys.path.insert(0, _nos.path.dirname(_nos.path.abspath(__file__))); from notice_auto import AUTO_NOTICE
import asyncio, os, json, threading, http.server, functools, shutil, sys
from playwright.async_api import async_playwright

PORT = 8894
BACKUP = sys.argv[1] if len(sys.argv) > 1 else '/mnt/user-data/uploads/amplify-backup-2026-11-01__1_.json'
root = '/tmp/claude-0/t/srv_favplay'; shots = '/tmp/claude-0/t/shots'
shutil.rmtree(root, ignore_errors=True); os.makedirs(root)
HOOK = "window.__t = { ev: function(js){ return eval(js); } };\n"
_src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'www', 'index.html')).read()
_mark = '  var coverFlow = null;\n'
assert _src.count(_mark) == 1
open(root + '/index.html', 'w').write(_src.replace(_mark, _mark + HOOK))
store = json.load(open(BACKUP))['amplifyBackup']['store']
json.dump(store, open(root + '/store.json', 'w'))
class Q(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a): pass
srv = http.server.ThreadingHTTPServer(('127.0.0.1', PORT), functools.partial(Q, directory=root))
threading.Thread(target=srv.serve_forever, daemon=True).start()
SEED = """(function(){ try{ if(localStorage.getItem('__seeded')) return; var x = new XMLHttpRequest(); x.open('GET', '/store.json', false); x.send();
  var st = JSON.parse(x.responseText); Object.keys(st).forEach(function(k){ localStorage.setItem(k, st[k]); });
  localStorage.setItem('radioPlayerTourDone', '1'); localStorage.setItem('__seeded', '1'); }catch(e){ console.log('seed', e); } })();"""
STATIONS = json.dumps([{'name': 'Calm Station %d' % i, 'url': 'http://calm.example/%d' % i, 'url_resolved': 'http://calm.example/%d' % i, 'stationuuid': 'calm-%d' % i,
                        'favicon': '', 'tags': 'chill', 'country': '', 'codec': 'MP3', 'bitrate': 128} for i in range(5)])
fails = []
def check(c, m):
    print(('PASS ' if c else 'FAIL ') + m)
    if not c: fails.append(m)

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
        ctx = await b.new_context(viewport={'width': 412, 'height': 915}, device_scale_factor=1, is_mobile=True, has_touch=True, color_scheme='dark')
        await ctx.add_init_script(SEED); await ctx.add_init_script(AUTO_NOTICE)
        pg = await ctx.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
        async def route(r):
            u = r.request.url
            if '127.0.0.1' in u: return await r.continue_()
            if '/json/stations/search' in u: return await r.fulfill(status=200, content_type='application/json', body=STATIONS)
            if '/json/' in u: return await r.fulfill(status=200, content_type='application/json', body='[]')
            return await r.abort()
        await pg.route('**/*', route)
        await pg.goto(f'http://127.0.0.1:{PORT}/index.html'); await pg.wait_for_timeout(4000)
        await pg.evaluate("document.querySelector('.mobile-nav-btn[data-nav=home]') && document.querySelector('.mobile-nav-btn[data-nav=home]').click()"); await pg.wait_for_timeout(2500)
        cards = await pg.evaluate("Array.prototype.map.call(document.querySelectorAll('.fav-card'), c => ({ key: c.dataset.key, name: (c.querySelector('.fav-card-text, .tile-name')||{}).textContent }))")
        seen = set(); cards = [c for c in cards if c['key'] and not (c['key'] in seen or seen.add(c['key']))]
        print(len(cards), 'favourite cards on Home')
        check(len(cards) >= 10, f'Home shows the favourites ({len(cards)})')
        results = []
        for c in cards:
            if c['key'].startswith('playlistradio:') and not await pg.evaluate("(k)=>__t.ev('playlistRadioItems(' + JSON.stringify(k.slice(14)) + ').length')", c['key']):
                print('skip', c['name'], '(only songs from the music library, none loaded here; song radios are checked in test_home_favs_kinds)'); continue
            await pg.evaluate("(k)=>{ var el = Array.prototype.filter.call(document.querySelectorAll('.fav-card'), x => x.dataset.key === k)[0]; el.scrollIntoView({block:'center', inline:'center'}); el.click(); }", c['key'])
            await pg.wait_for_timeout(1500)
            st = await pg.evaluate("""(k)=>{ var els = Array.prototype.filter.call(document.querySelectorAll('.fav-card'), x => x.dataset.key === k);
              return { marked: els.length > 0 && els.every(x => x.classList.contains('playing')), n: els.length, others: Array.prototype.filter.call(document.querySelectorAll('.fav-card.playing'), x => x.dataset.key !== k && x.dataset.key !== __t.ev('currentStation ? favKey(currentStation) : ""')).map(x => x.dataset.key),
                       cur: __t.ev('currentStation ? (currentStation.name || "") + " | " + favKey(currentStation) : null') }; }""", c['key'])
            # its line-up moving on (Next) keeps the border on the favourite
            if c['key'].startswith(('customstation:', 'playlistradio:')) and st['marked']:
                before = st['cur']
                await pg.evaluate("__t.ev('playQueueStep(1)')"); await pg.wait_for_timeout(1200)
                st2 = await pg.evaluate("(k)=>({ on: Array.prototype.some.call(document.querySelectorAll('.fav-card'), x => x.dataset.key === k && x.classList.contains('playing')), cur: __t.ev('currentStation ? currentStation.name : null') })", c['key'])
                check(st2['on'] and st2['cur'] != before.split(' | ')[0], f"{(c['name'] or '').strip()!r}: after Next ({before.split(' | ')[0]} -> {st2['cur']}) the card still has the border")
            results.append((c, st))
            if c['name'] and ('Relaxing' in c['name'] or c['name'].strip() == 'Chill'):
                await pg.screenshot(path=f'{shots}/favplay-{c["name"].strip().replace(" ", "-")}.png')
            await pg.evaluate("try{ closeNowPlaying(); }catch(e){} try{ document.querySelectorAll('.video-close, #videoCloseBtn').forEach(b => b.click()); }catch(e){}")
            await pg.wait_for_timeout(300)
        for c, st in results:
            check(st['marked'] and not st['others'], f"{(c['name'] or '').strip()!r} [{c['key']}]: its card has the playing border (now: {st['cur']}) {'' if not st['others'] else 'also on ' + str(st['others'])}")
        check(not errs, f'no page errors {errs[:3]}')
        await b.close()
asyncio.run(main())
print('FAILED: %d' % len(fails) if fails else 'ALL PASS'); raise SystemExit(1 if fails else 0)
