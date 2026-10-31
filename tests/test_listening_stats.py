"""Build 367: listening time. While something plays its seconds are counted (a pause stops the
count) by day, kind, hour, the station itself and its artist; the profile shows this month's
time; "See your listening stats" opens Listening Stats (time today/week/month/year, the last 14
days as bars, this month by type, top artists and songs by plays, top stations and podcasts by
time, more numbers) and its back arrow returns to the profile. Phone, dark and light.
Run: python3 tests/test_listening_stats.py (screenshots in /tmp/claude-0/t/shots)"""
import sys as _nsys, os as _nos; _nsys.path.insert(0, _nos.path.dirname(_nos.path.abspath(__file__))); from notice_auto import AUTO_NOTICE
import asyncio, os, json, threading, http.server, functools, shutil, datetime
from playwright.async_api import async_playwright
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = '/tmp/claude-0/t/srv-stats'; SHOTS = '/tmp/claude-0/t/shots'; PORT = 8876
shutil.rmtree(ROOT, ignore_errors=True); os.makedirs(ROOT); os.makedirs(SHOTS, exist_ok=True)
HOOK = ("window.__t = { ev: function(js){ return eval(js); }, play: function(st, on){ currentStation = st; uiIsPlaying = on; },"
        " L: function(){ return loadListen(); } };\n")
src = open(os.path.join(HERE, '..', 'www', 'index.html')).read()
mark = '  var coverFlow = null;\n'; assert src.count(mark) == 1
open(ROOT + '/index.html', 'w').write(src.replace(mark, mark + HOOK))
H = functools.partial(http.server.SimpleHTTPRequestHandler, directory=ROOT); H.log_message = lambda *a: None
srv = http.server.ThreadingHTTPServer(('127.0.0.1', PORT), H); threading.Thread(target=srv.serve_forever, daemon=True).start()
today = datetime.date.today()
days = {}
for i in range(14):
    d = today - datetime.timedelta(days=i)
    t = [3600, 5400, 1800, 0, 7200, 2700, 4500, 900, 0, 6300, 3000, 1200, 4800, 2400][i]
    if t: days[d.isoformat()] = {'t': t, 'm': t * 0.5, 'r': t * 0.35, 'p': t * 0.1, 'v': t * 0.05}
hours = [0] * 24; hours[20] = 30000; hours[8] = 12000
LS = {'v': 1, 'start': int(datetime.datetime(2026, 10, 18).timestamp() * 1000), 'days': days, 'hours': hours,
      'items': {'s:1': {'n': 'Motown Radio', 'k': 'r', 's': 25000}, 's:2': {'n': "80's 80's", 'k': 'r', 's': 14000},
                'p:1': {'n': 'Episode 12', 'a': 'Talk Is Jericho', 'k': 'p', 's': 5000}},
      'artists': {'the supremes': {'n': 'The Supremes', 's': 9000}}}
SEED = ("if(!sessionStorage.getItem('s')){ sessionStorage.setItem('s','1'); localStorage.setItem('radioPlayerListening', %s);"
        " localStorage.setItem('radioPlayerArtistPlays', JSON.stringify({a:{name:'The Supremes',count:42,last:2},b:{name:'Prince',count:9,last:1},c:{name:'Madonna',count:9,last:3}}));"
        " localStorage.setItem('radioPlayerSongPlays', JSON.stringify({x:[30,1],y:[12,1]})); }") % json.dumps(json.dumps(LS))
fails = []
def check(ok, msg):
    print(('PASS ' if ok else 'FAIL ') + msg)
    if not ok: fails.append(msg)
async def run(B, theme, seed):
    T = f'[{theme}]'
    c = await B.new_context(viewport={'width': 390, 'height': 844}, device_scale_factor=2, is_mobile=True, has_touch=True, color_scheme=theme)
    await c.add_init_script(AUTO_NOTICE)
    if seed: await c.add_init_script(SEED)
    pg = await c.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
    await pg.goto(f'http://127.0.0.1:{PORT}/index.html'); await pg.wait_for_timeout(2000)
    if not seed:
        # counting: 3 seconds playing a station, then 2 paused
        await pg.evaluate("__t.play({name:'Exclusively Prince', urlToResolve:'http://x/p', stationuuid:'zz'}, true)")
        await pg.wait_for_timeout(3200)
        await pg.evaluate("__t.play({name:'Exclusively Prince', urlToResolve:'http://x/p', stationuuid:'zz'}, false)")
        await pg.wait_for_timeout(2200)
        L = await pg.evaluate("__t.L()")
        day = list(L['days'].values())[0] if L['days'] else {}
        items = list(L['items'].values())
        check(2.0 <= day.get('t', 0) <= 4.5 and day.get('r', 0) == day.get('t'), f'{T} about 3 seconds counted, as radio; nothing while paused {day}')
        check(items and items[0]['n'] == 'Prince' and items[0]['k'] == 'r', f'{T} counted for the station {items}')
        check(sum(L['hours']) == day.get('t'), f'{T} and in its hour of the day')
        await pg.evaluate("__t.ev('saveListen(true)')")
        check(await pg.evaluate("!!localStorage.getItem('radioPlayerListening')"), f'{T} kept on the phone')
        await c.close(); return
    # (set after start-up: start-up drops play counts for artists that aren't in the library)
    await pg.evaluate("localStorage.setItem('radioPlayerArtistPlays', JSON.stringify({a:{name:'The Supremes',count:42,last:2},b:{name:'Prince',count:9,last:1},c:{name:'Madonna',count:9,last:3}}))")
    await pg.tap('#hamburgerBtn'); await pg.wait_for_timeout(400)
    stats = await pg.evaluate("Array.prototype.map.call(document.querySelectorAll('.pf-stat'), function(s){ return s.textContent; })")
    month_secs = sum(v['t'] for k, v in days.items() if k >= today.replace(day=1).isoformat())
    check(stats[1].endswith('This month') and stats[1].startswith(str(int(month_secs // 3600)) + 'h'), f'{T} the profile shows time listened this month {stats} ({month_secs}s)')
    await pg.screenshot(path=f'{SHOTS}/stats-{theme}-profile.png')
    await pg.tap('#pfStatsLink'); await pg.wait_for_timeout(400)
    check(await pg.evaluate("document.getElementById('statsOverlay').classList.contains('open')"), f'{T} the link opens Listening Stats')
    cards = await pg.evaluate("Array.prototype.map.call(document.querySelectorAll('.st-card'), function(s){ return s.textContent; })")
    check(cards[0] == '1hToday', f'{T} today is 1h {cards}')
    bars = await pg.evaluate("Array.prototype.map.call(document.querySelectorAll('.st-bar i'), function(b){ return parseInt(b.style.height); })")
    check(len(bars) == 14 and max(bars) == 100 and bars[-1] == 50, f'{T} 14 bars, today half the tallest {bars}')
    tops = await pg.evaluate("Array.prototype.map.call(document.querySelectorAll('.st-sec'), function(s){ return [s.querySelector('.st-h2').textContent, Array.prototype.map.call(s.querySelectorAll('.st-row-n, .st-fact span:first-child'), function(x){ return x.textContent; }).slice(0, 3)]; })")
    d = dict((t[0], t[1]) for t in tops)
    check(d.get('Top artists', [])[:2] == ['The Supremes', 'Madonna'], f'{T} top artists by plays (a tie goes to the latest) {d.get("Top artists")}')
    check(d.get('Top stations', [])[:2] == ['Motown Radio', "80's 80's"], f'{T} top stations by time {d.get("Top stations")}')
    check(d.get('Top podcasts', [])[:1] == ['Talk Is Jericho'], f'{T} top podcasts by show {d.get("Top podcasts")}')
    facts = await pg.evaluate("Array.prototype.map.call(document.querySelectorAll('.st-fact'), function(f){ return f.textContent; })")
    check('Songs played42' in facts and 'Favorite time to listen8pm–9pm' in facts, f'{T} plays and favorite time {facts}')
    await pg.screenshot(path=f'{SHOTS}/stats-{theme}-1.png')
    for i, y in enumerate((700, 1400, 2100)):
        await pg.evaluate(f"document.getElementById('statsPage').scrollTop = {y}"); await pg.wait_for_timeout(150)
        await pg.screenshot(path=f'{SHOTS}/stats-{theme}-{i + 2}.png')
    await pg.tap('#statsBackBtn'); await pg.wait_for_timeout(300)
    check(await pg.evaluate("!document.getElementById('statsOverlay').classList.contains('open') && document.getElementById('profileOverlay').classList.contains('open')"), f'{T} back returns to the profile')
    check(not errs, f'{T} no page errors {errs}')
    await c.close()
async def main():
    async with async_playwright() as p:
        B = await p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
        await run(B, 'dark', False)
        for th in ('dark', 'light'): await run(B, th, True)
        await B.close()
    print('ALL PASSED' if not fails else f'FAILS {len(fails)}')
asyncio.run(main())
