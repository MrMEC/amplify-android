"""Sleep timer (build 230): Now Playing's menu > Sleep Timer opens a sheet with 15/30/45 minutes,
1 hour, 1 hr 30 min, End of song/episode (only for something that ends) and Turn Off (only while
set). The native player counts it down (mocked here); the page shows the time left in the menu,
stops the buttons when it goes off, and doesn't go on to the next song when the timer stopped
one at its end. Both themes, 412 wide, plus a check with text 35% larger at 360.
Run: python3 tests/test_sleep_timer.py (screenshots in /tmp/claude-0/t/shots)"""
import sys as _nsys, os as _nos; _nsys.path.insert(0, _nos.path.dirname(_nos.path.abspath(__file__))); from notice_auto import AUTO_NOTICE
import asyncio, os, json, threading, http.server, functools, shutil, subprocess
from playwright.async_api import async_playwright

PORT = 8827
root = '/tmp/claude-0/t/srv_sleep'
shots = '/tmp/claude-0/t/shots'
os.makedirs(shots, exist_ok=True)
shutil.rmtree(root, ignore_errors=True)
os.makedirs(root)
ST = lambda n: ("{ stationuuid: 'st-" + n + "', name: '" + n + "', url: 'http://radio.example/" + n.replace(' ', '')
                + "', urlToResolve: 'http://radio.example/" + n.replace(' ', '') + "', favicon: '', tags: '' }")
HOOK = ("window.__t = { tracks: function(){ return libraryTracks.map(function(t){ return t.name; }); },"
        " setup: function(){ stationPlaylists.push({ id: 'pl_mix', label: 'Mix', stations: [" + ST('Radio A') + ", " + ST('Radio B') + "] }); saveStationPlaylists(); },"
        " cur: function(){ return currentStation && currentStation.name; },"
        " playing: function(){ return uiIsPlaying; },"
        " openPl: function(id){ runStationPlaylist(findStationPlaylistById(id)); },"
        " openNp: function(){ openNowPlaying(); }, closeNp: function(){ closeNowPlaying(); },"
        " songs: function(){ runLibrarySection('songs'); } };\n")
_src = open(os.path.join(os.path.dirname(__file__), '..', 'www', 'index.html')).read()
_mark = '  var coverFlow = null;\n'
assert _src.count(_mark) == 1
open(root + '/index.html', 'w').write(_src.replace(_mark, _mark + HOOK))

M = root + '/Music'
os.makedirs(M, exist_ok=True)
for i, (t, a) in enumerate([('Song 1', 'Ann'), ('Song 2', 'Ann'), ('Song 3', 'Bob')]):
    subprocess.run(['ffmpeg', '-loglevel', 'error', '-y', '-f', 'lavfi', '-i', f'sine=frequency={300 + i * 60}:duration=3',
                    '-c:a', 'libmp3lame', '-b:a', '32k', '-metadata', f'title={t}', '-metadata', f'artist={a}',
                    '-metadata', f'album={a} Album', '-metadata', f'track={i + 1}', f'{M}/{i + 1:02d}.mp3'], check=True)


class Q(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a): pass
H = functools.partial(Q, directory=root)
srv = http.server.ThreadingHTTPServer(('127.0.0.1', PORT), H)
threading.Thread(target=srv.serve_forever, daemon=True).start()
files = [{'uri': f'http://127.0.0.1:{PORT}/Music/{f}', 'name': f, 'relPath': f'Music/{f}', 'type': 'audio/mpeg',
          'size': os.path.getsize(f'{M}/{f}'), 'lastModified': 1700000000000} for f in sorted(os.listdir(M))]
# The mock keeps the timer like SleepTimer does (set/cancel/info) and records every call.
MOCK = """
(function(){
 var picked = %s, listeners = {}, cur = null, sleep = { active: false, endOfItem: false, until: 0 };
 function emit(n, ev){ (listeners[n] || []).forEach(function(f){ try{ f(ev); }catch(e){} }); }
 function info(fired){ return { active: sleep.active, endOfItem: sleep.endOfItem, until: sleep.until,
   remaining: sleep.until ? Math.max(0, sleep.until - Date.now()) : 0, fired: !!fired, at: Date.now() }; }
 window.__calls = [];
 window.__mock = {
   cur: function(){ return cur; },
   emit: emit,
   // the timed sleep going off: the player pauses (an outside pause) and says so
   fire: function(){ sleep = { active: false, endOfItem: false, until: 0 };
     emit('state', { id: cur, state: 'ready', isPlaying: false, playWhenReady: false, position: 1, duration: 0, external: true });
     emit('sleep', info(true)); },
   // "end of song": the item ends; the native timer holds it and says so
   endHeld: function(){ sleep = { active: false, endOfItem: false, until: 0 };
     emit('state', { id: cur, state: 'ended', isPlaying: false, playWhenReady: true, position: 3, duration: 3, sleepHold: true, at: Date.now() });
     emit('sleep', info(true)); },
   // an ordinary end (no hold from the native timer)
   end: function(){ emit('state', { id: cur, state: 'ended', isPlaying: false, playWhenReady: true, position: 3, duration: 3, at: Date.now() }); }
 };
 var impl = {
   pickMusicFolder: function(){ return Promise.resolve({folder:'Music', files:picked, truncated:false}); },
   cacheCheck: function(){ return Promise.resolve({ url: 'file:///cache/x.mp3' }); },
   load: function(o){ cur = o.id; setTimeout(function(){ emit('state', { id: cur, state: 'ready', isPlaying: true, playWhenReady: true, position: 0, duration: 3 }); }, 20); return Promise.resolve({}); },
   setSleep: function(o){ window.__calls.push(o);
     if(o.ms > 0) sleep = { active: true, endOfItem: false, until: Date.now() + o.ms };
     else if(o.endOfItem) sleep = { active: true, endOfItem: true, until: 0 };
     else sleep = { active: false, endOfItem: false, until: 0 };
     return Promise.resolve(info(false)); },
   play: function(){ setTimeout(function(){ emit('state', { id: cur, state: 'ready', isPlaying: true, playWhenReady: true, position: 0, duration: 3 }); }, 20); return Promise.resolve({}); },
   sleepInfo: function(){ return Promise.resolve(info(false)); },
   addListener: function(n, f){ (listeners[n] = listeners[n] || []).push(f); return Promise.resolve({remove:function(){}}); }
 };
 var P = new Proxy({}, {get:function(t,k){
   if(k==='then') return undefined;
   if(k==='setCarLibraryPart') return undefined;
   if(impl[k]) return impl[k];
   return function(){ return Promise.resolve({}); };
 }});
 window.Capacitor = { isNativePlatform:function(){return true;}, getPlatform:function(){return 'android';},
   registerPlugin:function(){ return P; }, Plugins:{AmplifyPlayer:P}, convertFileSrc:function(u){return u;} };
})();
""" % json.dumps(files)

fails = []
def check(cond, msg):
    print(('PASS ' if cond else 'FAIL ') + msg)
    if not cond: fails.append(msg)

CLICK = """(name) => { var el = Array.from(document.querySelectorAll('#stationsGrid .tile, #stationsGrid .row-item, #stationsGrid .song-row')).filter(function(e){
  var n = e.querySelector('.tile-name, .song-row-title, .row-name'); return n && n.textContent === name; })[0]; if(el) el.click(); return !!el; }"""
SHEET = """() => { var ov = document.getElementById('sleepOverlay'); var st = document.getElementById('sleepStatus');
  return { open: ov.classList.contains('open') && getComputedStyle(ov).display !== 'none',
    opts: Array.from(ov.querySelectorAll('.sleep-opt')).map(function(b){ return b.textContent.trim(); }),
    on: Array.from(ov.querySelectorAll('.sleep-opt.on')).map(function(b){ return b.textContent.trim(); }),
    status: st.hidden ? '' : st.textContent }; }"""
MENU = """() => { var b = document.getElementById('npSleepBtn'), l = document.getElementById('npSleepLeft');
  var r = b.getBoundingClientRect(), q = document.getElementById('npQueueMenuBtn').getBoundingClientRect();
  var lc = getComputedStyle(l).color, bc = getComputedStyle(b).color;
  return { shown: getComputedStyle(b).display !== 'none' && r.height > 0, left: l.hidden ? '' : l.textContent,
    fits: b.scrollWidth <= b.clientWidth + 1 && Math.abs(r.height - q.height) < 2 && b.getBoundingClientRect().right <= innerWidth,
    sameColour: lc === bc, text: b.textContent.replace(/\\s+/g, ' ').trim() }; }"""


async def opt(pg, label):
    return await pg.evaluate("""(l) => { var b = Array.from(document.querySelectorAll('#sleepOverlay .sleep-opt')).filter(function(x){ return x.textContent.trim() === l; })[0]; if(b) b.click(); return !!b; }""", label)


async def open_menu(pg):
    await pg.evaluate("document.getElementById('npMenuBtn').click()"); await pg.wait_for_timeout(250)


async def run(p, scheme):
    b = await p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
    ctx = await b.new_context(viewport={'width': 412, 'height': 900}, device_scale_factor=2, is_mobile=True, has_touch=True, color_scheme=scheme)
    await ctx.add_init_script(MOCK); await ctx.add_init_script(AUTO_NOTICE)
    pg = await ctx.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
    await pg.route('**/*', lambda route: route.continue_() if '127.0.0.1' in route.request.url else route.abort())
    await pg.goto(f'http://127.0.0.1:{PORT}/index.html'); await pg.wait_for_timeout(2500)
    await pg.evaluate(f"document.documentElement.setAttribute('data-theme', '{scheme}')")
    await pg.evaluate("""(function(){ var ov=document.getElementById('addMusicOverlay'); if(ov) ov.classList.add('open');
      var btn=document.getElementById('addMusicFolderBtn'); btn.disabled=false; btn.click(); })()""")
    for _ in range(60):
        await pg.wait_for_timeout(500)
        if len(await pg.evaluate('__t.tracks()')) >= 3: break
    await pg.evaluate("(function(){ var ov=document.getElementById('addMusicOverlay'); if(ov) ov.classList.remove('open'); })()")
    await pg.evaluate('__t.setup()')
    calls = lambda: pg.evaluate('window.__calls.slice()')

    # ---- a station: the menu item, the sheet, 30 minutes ----
    await pg.evaluate("__t.openPl('pl_mix')"); await pg.wait_for_timeout(600)
    check(await pg.evaluate(CLICK, 'Radio A'), f'[{scheme}] played Radio A')
    await pg.wait_for_timeout(500)
    await pg.evaluate('__t.openNp()'); await pg.wait_for_timeout(700)
    await open_menu(pg)
    m = await pg.evaluate(MENU)
    check(m['shown'] and m['left'] == '' and m['text'] == 'Sleep Timer', f'[{scheme}] menu has Sleep Timer, nothing set {m}')
    await pg.screenshot(path=f'{shots}/sleep-menu-off-{scheme}.png')
    await pg.evaluate("document.getElementById('npSleepBtn').click()"); await pg.wait_for_timeout(300)
    sh = await pg.evaluate(SHEET)
    check(sh['open'], f'[{scheme}] the sheet opens')
    check(sh['opts'] == ['15 minutes', '30 minutes', '45 minutes', '1 hour', '1 hr 30 min'] and not sh['on'] and sh['status'] == '',
          f'[{scheme}] a station: times only, no End of song, no Turn Off {sh}')
    menu_open = await pg.evaluate("document.getElementById('npMenu').classList.contains('open')")
    check(not menu_open, f'[{scheme}] the menu closed behind the sheet')
    await pg.screenshot(path=f'{shots}/sleep-sheet-off-{scheme}.png')
    await opt(pg, '30 minutes'); await pg.wait_for_timeout(300)
    c = await calls()
    check(c and c[-1].get('ms') == 1800000 and not c[-1].get('endOfItem'), f'[{scheme}] 30 minutes sent to the player {c[-1:]}')
    check(not (await pg.evaluate(SHEET))['open'], f'[{scheme}] the sheet closes on a choice')
    await open_menu(pg)
    m = await pg.evaluate(MENU)
    check(m['left'] in ('30 min', '29 min') and m['fits'] and m['sameColour'], f'[{scheme}] menu shows the time left {m}')
    await pg.screenshot(path=f'{shots}/sleep-menu-on-{scheme}.png')
    await pg.evaluate("document.getElementById('npSleepBtn').click()"); await pg.wait_for_timeout(1300)
    sh = await pg.evaluate(SHEET)
    check(sh['on'] == ['30 minutes'] and 'Turn Off' in sh['opts'] and sh['status'].startswith('Stops in 29:5'),
          f'[{scheme}] the sheet ticks 30 minutes, counts down, offers Turn Off {sh}')
    await pg.screenshot(path=f'{shots}/sleep-sheet-on-{scheme}.png')
    # tap outside closes it, and so does Escape
    await pg.mouse.click(10, 10); await pg.wait_for_timeout(200)
    check(not (await pg.evaluate(SHEET))['open'], f'[{scheme}] a tap outside closes the sheet')
    await pg.evaluate("document.getElementById('npSleepBtn').click()"); await pg.wait_for_timeout(200)
    await pg.keyboard.press('Escape'); await pg.wait_for_timeout(200)
    check(not (await pg.evaluate(SHEET))['open'], f'[{scheme}] Escape closes the sheet')
    check(await pg.evaluate('__t.playing()'), f'[{scheme}] still playing before it goes off')

    # ---- it goes off: the buttons stop, the menu clears ----
    await pg.evaluate('window.__mock.fire()'); await pg.wait_for_timeout(400)
    check(not await pg.evaluate('__t.playing()'), f'[{scheme}] the timer going off stops the buttons')
    play_icon = await pg.evaluate("!!document.querySelector('#npPlayBtn .fa-play')")
    check(play_icon, f'[{scheme}] Now Playing shows Play again')
    await open_menu(pg)
    check((await pg.evaluate(MENU))['left'] == '', f'[{scheme}] menu has no time left after it went off')
    await open_menu(pg)

    # ---- Turn Off ----
    await pg.evaluate("document.getElementById('npSleepBtn').click()"); await pg.wait_for_timeout(200)
    await opt(pg, '15 minutes'); await pg.wait_for_timeout(200)
    await pg.evaluate("document.getElementById('npSleepBtn').click()"); await pg.wait_for_timeout(200)
    await opt(pg, 'Turn Off'); await pg.wait_for_timeout(200)
    c = await calls()
    check(c[-1].get('ms') == 0 and not c[-1].get('endOfItem'), f'[{scheme}] Turn Off turns it off in the player {c[-1:]}')
    await open_menu(pg)
    check((await pg.evaluate(MENU))['left'] == '', f'[{scheme}] menu clear after Turn Off')
    await open_menu(pg)

    # ---- a song: an ordinary end goes on to the next song ----
    await pg.evaluate("__t.closeNp()"); await pg.wait_for_timeout(300)
    await pg.evaluate('__t.songs()'); await pg.wait_for_timeout(700)
    check(await pg.evaluate(CLICK, 'Song 1'), f'[{scheme}] played Song 1')
    await pg.wait_for_timeout(600)
    await pg.evaluate('window.__mock.end()'); await pg.wait_for_timeout(700)
    check(await pg.evaluate('__t.cur()') == 'Song 2', f'[{scheme}] without the timer the next song plays ({await pg.evaluate("__t.cur()")})')

    # ---- End of song, held by the native timer: stays on the song, stopped ----
    await pg.evaluate('__t.openNp()'); await pg.wait_for_timeout(600)
    await pg.evaluate("document.getElementById('npSleepBtn').click()"); await pg.wait_for_timeout(200)
    sh = await pg.evaluate(SHEET)
    check('End of song' in sh['opts'], f'[{scheme}] a song offers End of song {sh["opts"]}')
    await opt(pg, 'End of song'); await pg.wait_for_timeout(200)
    c = await calls()
    check(c[-1].get('endOfItem') is True and not c[-1].get('ms'), f'[{scheme}] End of song sent to the player {c[-1:]}')
    await open_menu(pg)
    m = await pg.evaluate(MENU)
    check(m['left'] == 'End of song' and m['fits'], f'[{scheme}] menu says End of song {m}')
    await pg.screenshot(path=f'{shots}/sleep-menu-end-{scheme}.png')
    await open_menu(pg)
    await pg.evaluate("document.getElementById('npSleepBtn').click()"); await pg.wait_for_timeout(200)
    sh = await pg.evaluate(SHEET)
    check(sh['on'] == ['End of song'] and sh['status'] == 'Stops at the end of this song', f'[{scheme}] sheet ticks End of song {sh}')
    await pg.keyboard.press('Escape'); await pg.wait_for_timeout(150)
    await pg.evaluate('window.__mock.endHeld()'); await pg.wait_for_timeout(700)
    check(await pg.evaluate('__t.cur()') == 'Song 2' and not await pg.evaluate('__t.playing()'),
          f'[{scheme}] held at the end: no next song, stopped ({await pg.evaluate("__t.cur()")})')
    await open_menu(pg)
    check((await pg.evaluate(MENU))['left'] == '', f'[{scheme}] menu clear after the end')
    await open_menu(pg)

    # ---- End of song when the end reaches the page first (e.g. a video in VLC) ----
    await pg.evaluate("document.getElementById('npPlayBtn').click()"); await pg.wait_for_timeout(500)
    await pg.evaluate("document.getElementById('npSleepBtn').click()"); await pg.wait_for_timeout(200)
    await opt(pg, 'End of song'); await pg.wait_for_timeout(200)
    n_before = len(await calls())
    await pg.evaluate('window.__mock.end()'); await pg.wait_for_timeout(700)
    c = await calls()
    check(await pg.evaluate('__t.cur()') == 'Song 2' and not await pg.evaluate('__t.playing()'),
          f'[{scheme}] page-side end: stays on the song, stopped ({await pg.evaluate("__t.cur()")})')
    check(len(c) > n_before and c[-1].get('ms') == 0 and not c[-1].get('endOfItem'), f'[{scheme}] and the player\'s timer is turned off {c[-1:]}')
    # after that, an ordinary end goes on again
    await pg.evaluate("document.getElementById('npPlayBtn').click()"); await pg.wait_for_timeout(500)
    await pg.evaluate('window.__mock.end()'); await pg.wait_for_timeout(700)
    check(await pg.evaluate('__t.cur()') == 'Song 3', f'[{scheme}] the next ordinary end goes on ({await pg.evaluate("__t.cur()")})')

    check(not errs, f'[{scheme}] no page errors {errs[:3]}')
    await b.close()


async def big_text(p):
    """Mark's phone: larger system text at 360 wide. The menu row and the sheet still fit."""
    b = await p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
    ctx = await b.new_context(viewport={'width': 360, 'height': 780}, device_scale_factor=2, is_mobile=True, has_touch=True, color_scheme='dark')
    await ctx.add_init_script(MOCK); await ctx.add_init_script(AUTO_NOTICE)
    pg = await ctx.new_page()
    await pg.route('**/*', lambda route: route.continue_() if '127.0.0.1' in route.request.url else route.abort())
    await pg.goto(f'http://127.0.0.1:{PORT}/index.html'); await pg.wait_for_timeout(2500)
    await pg.evaluate('__t.setup()')
    await pg.evaluate("__t.openPl('pl_mix')"); await pg.wait_for_timeout(600)
    await pg.evaluate(CLICK, 'Radio A'); await pg.wait_for_timeout(500)
    await pg.evaluate('__t.openNp()'); await pg.wait_for_timeout(700)
    await pg.add_style_tag(content='.np-menu-item, .sleep-opt, .sleep-status, .confirm-title { zoom: 1.35; }')
    await pg.evaluate("window.__sleep.set(90, false)"); await pg.wait_for_timeout(300)
    await open_menu(pg)
    m = await pg.evaluate(MENU)
    r = await pg.evaluate("(function(){ var r = document.getElementById('npMenu').getBoundingClientRect(); return [r.left, r.right]; })()")
    check(m['fits'] and m['left'] == '90 min' and r[0] >= 0 and r[1] <= 360, f'[big text 360] menu row fits {m} {r}')
    await pg.screenshot(path=f'{shots}/sleep-menu-bigtext.png')
    await pg.evaluate("document.getElementById('npSleepBtn').click()"); await pg.wait_for_timeout(300)
    fit = await pg.evaluate("""(function(){ var p = document.querySelector('.sleep-panel').getBoundingClientRect();
      var ok = Array.from(document.querySelectorAll('.sleep-opt span')).every(function(s){ return s.scrollWidth <= s.clientWidth + 1; });
      return { ok: ok, left: p.left, right: p.right, top: p.top, bottom: p.bottom }; })()""")
    check(fit['ok'] and fit['left'] >= 0 and fit['right'] <= 360 and fit['top'] >= 0 and fit['bottom'] <= 780, f'[big text 360] sheet fits {fit}')
    await pg.screenshot(path=f'{shots}/sleep-sheet-bigtext.png')
    await b.close()


async def main():
    async with async_playwright() as p:
        for scheme in ('dark', 'light'):
            await run(p, scheme)
        await big_text(p)
    print('ALL PASSED' if not fails else f'FAILED {fails}')

asyncio.run(main())
