"""Top Artists play counts: a play counts after 20 seconds of actual listening (pauses don't
count), a song skipped before then doesn't count, and the Top Artists page shows each artist's
count on the far right. Since build 121 artist stations count once at 20 seconds and again
for every further 3.5 minutes; a Featuring-playlist station and "<artist> Radio" count too. Uses Playwright's clock so the listening happens instantly, and a mocked
native player that reports playing/paused like the real one.
Run: python3 tests/test_top_artists.py (screenshots in /tmp/claude-0/t/shots)"""
import asyncio, os, json, threading, http.server, functools, shutil, subprocess
from playwright.async_api import async_playwright

PORT = 8790
root = '/tmp/claude-0/t/srv_top'
shots = '/tmp/claude-0/t/shots'
os.makedirs(shots, exist_ok=True)
shutil.rmtree(root, ignore_errors=True)
os.makedirs(root)
HOOK = ("window.__t = { tracks: function(){ return libraryTracks; }, runLibrarySection: runLibrarySection,"
        " plays: function(){ return loadArtistPlays(); }, openTop: function(){ openHomeSectionPage('topArtists'); },"
        " playSong: function(title){ var t = libraryTracks.filter(function(x){ return x.name === title; })[0]; playEntity(t); },"
        " toggle: function(){ togglePlayPause(); }, playing: function(){ return uiIsPlaying; },"
        " cur: function(){ return currentStation && currentStation.name; },"
        " playStation: function(n){ playStation({ stationuuid: 'st-' + n, name: n, url: 'http://radio.example/' + encodeURIComponent(n), urlToResolve: 'http://radio.example/' + encodeURIComponent(n), favicon: '', tags: '' }); },"
        " addPl: function(label, n){ stationPlaylists.push({ id: 'pl-' + label, label: label, stations: [{ stationuuid: 'st-' + n, name: n, url: 'http://radio.example/' + encodeURIComponent(n), urlToResolve: 'http://radio.example/' + encodeURIComponent(n), favicon: '' }] }); saveStationPlaylists(); } };\n")
_src = open(os.path.join(os.path.dirname(__file__), '..', 'www', 'index.html')).read()
_mark = '  var coverFlow = null;\n'
assert _src.count(_mark) == 1
open(root + '/index.html', 'w').write(_src.replace(_mark, _mark + HOOK))

tone = f'{root}/tone.mp3'
subprocess.run(['ffmpeg', '-loglevel', 'error', '-y', '-f', 'lavfi', '-i', 'sine=frequency=440:duration=60',
                '-ac', '1', '-c:a', 'libmp3lame', '-b:a', '16k', tone], check=True)
M = root + '/Music'
for artist in ['Alpha', 'Bravo', 'Charlie']:
    for n in (1, 2):
        p = f'{M}/{artist}/{n:02d}.mp3'
        os.makedirs(os.path.dirname(p), exist_ok=True)
        subprocess.run(['ffmpeg', '-loglevel', 'error', '-y', '-i', tone, '-c:a', 'copy', '-id3v2_version', '3',
                        '-metadata', f'title={artist} {n}', '-metadata', f'artist={artist}', '-metadata', f'album={artist} Album',
                        '-metadata', f'track={n}', p], check=True)

H = functools.partial(http.server.SimpleHTTPRequestHandler, directory=root)
H.log_message = lambda *a: None
srv = http.server.ThreadingHTTPServer(('127.0.0.1', PORT), H)
threading.Thread(target=srv.serve_forever, daemon=True).start()
files = []
for dp, _, fs in os.walk(M):
    for f in sorted(fs):
        p = os.path.join(dp, f); rel = os.path.relpath(p, root)
        files.append({'uri': f'http://127.0.0.1:{PORT}/' + rel.replace(' ', '%20'), 'name': f, 'relPath': rel,
                      'type': 'audio/mpeg', 'size': os.path.getsize(p), 'lastModified': 1700000000000})
# A native player that answers like the real one: a load starts playing, play/pause report back.
MOCK = """
(function(){
 var picked = %s, listeners = {}, cur = null;
 function emit(n, ev){ (listeners[n] || []).forEach(function(f){ try{ f(ev); }catch(e){} }); }
 function state(playing){ if(cur) setTimeout(function(){ emit('state', { id: cur, state: 'ready', isPlaying: playing, playWhenReady: playing, position: 0, duration: 60 }); }, 20); }
 var impl = {
   pickMusicFolder: function(){ return Promise.resolve({folder:'Music', files:picked, truncated:false}); },
   cacheCheck: function(){ return Promise.resolve({ url: 'file:///cache/x.mp3' }); },
   load: function(o){ cur = o.id; state(!!o.play); return Promise.resolve({}); },
   play: function(){ state(true); return Promise.resolve({}); },
   pause: function(){ state(false); return Promise.resolve({}); },
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


async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
        ctx = await b.new_context(viewport={'width': 390, 'height': 844}, device_scale_factor=2, is_mobile=True, has_touch=True, color_scheme='dark')
        await ctx.add_init_script(MOCK)
        pg = await ctx.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.clock.install()
        await pg.goto(f'http://127.0.0.1:{PORT}/index.html'); await pg.wait_for_timeout(2500)
        await pg.evaluate("""(function(){ var ov=document.getElementById('addMusicOverlay'); if(ov) ov.classList.add('open');
          var btn=document.getElementById('addMusicFolderBtn'); btn.disabled=false; btn.click(); })()""")
        for _ in range(60):
            await pg.wait_for_timeout(500)
            if await pg.evaluate('__t.tracks().length') >= len(files): break
        check(await pg.evaluate('__t.tracks().length') == len(files), f'library imported ({len(files)} songs)')
        counts = lambda: pg.evaluate("(function(){ var p=__t.plays(), o={}; Object.keys(p).forEach(function(k){ o[p[k].name]=p[k].count; }); return o; })()")
        async def listen(sec):
            await pg.clock.run_for(int(sec * 1000)); await pg.wait_for_timeout(50)

        # A song listened to for 20 seconds counts once.
        await pg.evaluate("__t.playSong('Alpha 1')"); await pg.wait_for_timeout(600)
        check(await pg.evaluate('__t.playing()'), 'song is playing (mock player reports it)')
        check(await counts() == {}, f'not counted the moment it starts {await counts()}')
        await listen(12)
        check(await counts() == {}, f'not counted after 12 seconds {await counts()}')
        await listen(10)
        check(await counts() == {'Alpha': 1}, f'counted after 20 seconds of listening {await counts()}')
        await listen(60)
        check(await counts() == {'Alpha': 1}, f'counted once, however long it plays {await counts()}')

        # Skipped after 5 seconds: no play for that artist.
        await pg.evaluate("__t.playSong('Bravo 1')"); await pg.wait_for_timeout(400)
        await listen(5)
        await pg.evaluate("__t.playSong('Charlie 1')"); await pg.wait_for_timeout(400)
        await listen(25)
        c = await counts()
        check('Bravo' not in c and c.get('Charlie') == 1, f'a song skipped after 5 seconds is not a play; the next one is {c}')

        # Paused time doesn't count: 10s, pause a minute, 5s -> no; 6s more -> yes.
        await pg.evaluate("__t.playSong('Alpha 2')"); await pg.wait_for_timeout(400)
        await listen(10)
        await pg.evaluate('__t.toggle()'); await pg.wait_for_timeout(300)
        check(not await pg.evaluate('__t.playing()'), 'paused')
        await listen(60)
        await pg.evaluate('__t.toggle()'); await pg.wait_for_timeout(300)
        await listen(5)
        check((await counts()).get('Alpha') == 1, f'paused time does not count toward 20 seconds {await counts()}')
        await listen(6)
        check((await counts()).get('Alpha') == 2, f'counted once 20 seconds of actual listening is reached {await counts()}')

        # Bravo heard properly three times.
        for i in range(3):
            await pg.evaluate(f"__t.playSong('Bravo {1 + i % 2}')"); await pg.wait_for_timeout(400)
            await listen(21)
        c = await counts()
        check(c == {'Alpha': 2, 'Bravo': 3, 'Charlie': 1}, f'totals {c}')

        # The Top Artists page: most played first, with the count on the far right of each row.
        await pg.evaluate('__t.openTop()'); await pg.wait_for_timeout(800)
        rows = await pg.evaluate("""Array.from(document.querySelectorAll('#stationsGrid .row-item')).map(function(r){
          var c=r.querySelector('.row-count'), n=r.querySelector('.row-name'); var rr=r.getBoundingClientRect(), cr=c?c.getBoundingClientRect():null, nr=n.getBoundingClientRect();
          return { name: n.textContent, count: c ? c.textContent : null, rightGap: cr ? Math.round(rr.right - cr.right) : null, afterName: cr ? cr.left >= nr.right : null }; })""")
        print(rows)
        check([(r['name'], r['count']) for r in rows] == [('Bravo', '3 plays'), ('Alpha', '2 plays'), ('Charlie', '1 play')],
              'Top Artists lists Bravo 3, Alpha 2, Charlie 1, in that order')
        check(all(r['rightGap'] is not None and r['rightGap'] <= 14 and r['afterName'] for r in rows), 'counts sit at the far right of each row')
        # The page clock is under the test's control; let it run so the page paints first.
        await pg.clock.run_for(2000); await pg.wait_for_timeout(500)
        await pg.screenshot(path=f'{shots}/top-artists-counts.png')
        # ---- stations (build 121) ----
        # An artist station counts like songs: once at 20 seconds, then every 3.5 minutes more.
        base = await counts()
        await pg.evaluate("__t.playStation('Exclusively Alpha')"); await pg.wait_for_timeout(600)
        check(await pg.evaluate('__t.playing()') and await pg.evaluate('__t.cur()') == 'Exclusively Alpha', 'an artist station is playing')
        await listen(21)
        check((await counts()).get('Alpha') == base['Alpha'] + 1, f"an artist station counts after 20 seconds {await counts()}")
        await listen(200)
        check((await counts()).get('Alpha') == base['Alpha'] + 1, 'not again before another 3.5 minutes')
        await listen(15)
        check((await counts()).get('Alpha') == base['Alpha'] + 2, f"and again after 3.5 minutes more (about one song) {await counts()}")
        await listen(8 * 60 - 236)
        check((await counts()).get('Alpha') == base['Alpha'] + 3, f"8 minutes of an artist station: 3 plays {await counts()}")
        # paused time doesn't count
        await pg.evaluate('__t.toggle()'); await pg.wait_for_timeout(300)
        await listen(30 * 60)
        check((await counts()).get('Alpha') == base['Alpha'] + 3, 'half an hour paused adds nothing')
        await pg.evaluate('__t.toggle()'); await pg.wait_for_timeout(300)
        # a station in a playlist named after an artist (their Featuring list) counts for them
        await pg.evaluate("__t.addPl('Bravo', 'Bravo Fan Stream')")
        await pg.evaluate("__t.playStation('Bravo Fan Stream')"); await pg.wait_for_timeout(600)
        await listen(21)
        check((await counts()).get('Bravo') == base['Bravo'] + 1, f"a station under Featuring Bravo counts for Bravo {await counts()}")
        # "<artist> Radio" counts for that artist
        await pg.evaluate("__t.playStation('Charlie Radio')"); await pg.wait_for_timeout(600)
        await listen(21)
        check((await counts()).get('Charlie') == base['Charlie'] + 1, f"'Charlie Radio' counts for Charlie {await counts()}")
        # a general station (no artist in its name, not under anyone's Featuring) counts for nobody
        before = await counts()
        await pg.evaluate("__t.playStation('Alpha FM')"); await pg.wait_for_timeout(600)
        await listen(5 * 60)
        await pg.evaluate("__t.playStation('Smooth Jazz 24')"); await pg.wait_for_timeout(600)
        await listen(5 * 60)
        check(await counts() == before, f"general stations ('Alpha FM', 'Smooth Jazz 24') count for no one {await counts()}")
        # a song after a station: the station stops counting, the song counts once
        await pg.evaluate("__t.playStation('Exclusively Alpha')"); await pg.wait_for_timeout(600)
        await listen(100)
        a0 = (await counts()).get('Alpha')
        await pg.evaluate("__t.playSong('Charlie 2')"); await pg.wait_for_timeout(400)
        await listen(6 * 60)
        c = await counts()
        check(c.get('Alpha') == a0 and c.get('Charlie') == before['Charlie'] + 1, f'switching to a song stops the station counting {c}')

        # One-time reset: counts saved before this build are cleared on the first start only.
        OLD = json.dumps({'zed': {'name': 'Zed', 'count': 99, 'last': 1}})
        await pg.evaluate(f"localStorage.setItem('radioPlayerArtistPlays', {json.dumps(OLD)}); localStorage.removeItem('radioPlayerArtistPlaysReset1');")
        await pg.reload(); await pg.wait_for_timeout(2500)
        check(await counts() == {}, f'old counts are cleared once on the first start of this build {await counts()}')
        await pg.evaluate(f"localStorage.setItem('radioPlayerArtistPlays', {json.dumps(OLD)})")
        await pg.reload(); await pg.wait_for_timeout(2500)
        check(await counts() == {'Zed': 99}, f'after that, counts are kept across restarts {await counts()}')
        check(not errs, f'no page errors {errs[:3]}')
        await b.close()
    print('ALL PASSED' if not fails else f'FAILED {fails}')

asyncio.run(main())
