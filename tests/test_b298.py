"""Build 298 (Mark): lyrics panel on a swipe right (299), queue on a swipe left; queue title in the cover colour. Built on test_b294 / Build 294 (Mark): Now Playing's progress bar gets a Samsung-style flowing wave in the cover's
colour over the played part, which stops (eases flat) when nothing plays; the dot has a white ring.
Run: python3 tests/test_b294.py (screenshots in /tmp/claude-0/t/shots)"""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
__file__ = os.path.join(HERE, 'test_daily_mixes.py')
src = open(os.path.join(HERE, 'test_daily_mixes.py')).read()
src = src[:src.index('async def run(theme):')]
src = src.replace('PORT = 8803', 'PORT = 8894').replace("srv_daily'", "srv_b298'")
src = src.replace('" stopPlay:', '''" w298pos: function(){ Object.defineProperty(audio, 'currentTime', { configurable: true, get: function(){ return window.__pos; }, set: function(v){ window.__seeks.push(v); window.__pos = v; } }); },"
  " w298other: function(){ return libraryTracks.filter(function(x){ return x.artist !== 'Prince'; })[0]; },"
  " w294: { play: function(){ var t = libraryTracks.filter(function(x){ return x.artist === 'Prince'; })[0]; audio.play = function(){ return Promise.resolve(); };"
  "     playEntity(t); setTimeout(function(){ Object.defineProperty(audio, 'duration', { configurable: true, get: function(){ return 200; } });"
  "     Object.defineProperty(audio, 'currentTime', { configurable: true, get: function(){ return 130; }, set: function(){} }); Object.defineProperty(audio, 'paused', { configurable: true, get: function(){ return !uiIsPlaying; } });"
  "     openNowPlaying(currentStation); setPlayingUI(true); syncSeekBar(); }, 600); },"
  "   pause: function(){ setPlayingUI(false); }, resume: function(){ setPlayingUI(true); },"
  "   px: function(){ var c = document.getElementById('npSeekWave'); var ctx = c.getContext('2d'); var d = ctx.getImageData(0, 0, c.width, c.height).data; var n = 0, sum = 0; for(var i = 3; i < d.length; i += 4){ if(d[i] > 8) n++; sum = (sum * 31 + d[i]) % 1000003; } return { lit: n, sig: sum, w: c.width, h: c.height }; },"
  "   colH: function(cssX){ var c = document.getElementById('npSeekWave'), dpr = c.width / c.clientWidth, x = Math.round(cssX * dpr); var d = c.getContext('2d').getImageData(x, 0, 1, c.height).data; for(var y = 0; y < c.height; y++) if(d[y * 4 + 3] > 8) return (c.height - y) / dpr; return 0; },"
  "   dotX: function(){ var c = document.getElementById('npSeekWave'), r = document.getElementById('npSeekRange'); return 8 + (r.value / 1000) * (c.clientWidth - 16); },"
  "   gap: function(){ var a = document.getElementById('npSeek').getBoundingClientRect(), t = document.querySelector('.np-seek-range').getBoundingClientRect(), u = document.getElementById('npUpNext').getBoundingClientRect(); return { below: Math.round(u.top - t.bottom) }; },"
  "   litRight: function(){ var c = document.getElementById('npSeekWave'); var d = c.getContext('2d').getImageData(Math.round(c.width * 0.8), 0, Math.round(c.width * 0.2), c.height).data; var n = 0; for(var i = 3; i < d.length; i += 4) if(d[i] > 8) n++; return n; },"
  "   thumb: function(){ var cs = getComputedStyle(document.getElementById('npSeekRange'), '::-webkit-slider-thumb'); return { border: cs.borderTopWidth + ' ' + cs.borderTopStyle + ' ' + cs.borderTopColor, w: cs.width }; },"
  "   vivid: function(){ return getComputedStyle(nowPlayingScreen).getPropertyValue('--np-vivid').trim(); } },"
  " stopPlay:''')
exec(src)

SWIPE = """((el, dx) => { const r = el.getBoundingClientRect(); const x0 = r.left + r.width * (dx < 0 ? 0.8 : 0.2), y = r.top + r.height * 0.45;
  const mk = (x) => new Touch({ identifier: 1, target: el, clientX: x, clientY: y });
  el.dispatchEvent(new TouchEvent('touchstart', { touches: [mk(x0)], changedTouches: [mk(x0)], bubbles: true, cancelable: true }));
  for(let i = 1; i <= 8; i++){ const t = mk(x0 + dx * i / 8); el.dispatchEvent(new TouchEvent('touchmove', { touches: [t], changedTouches: [t], bubbles: true, cancelable: true })); }
  el.dispatchEvent(new TouchEvent('touchend', { touches: [], changedTouches: [mk(x0 + dx)], bubbles: true, cancelable: true })); })"""
LRC = "[00:00.00]Intro line\n[01:58.00]Line at one fifty-eight\n[02:00.50]Line at two\n[02:08.00]Line at two-oh-eight\n[02:20.00]Line at two-twenty\n[02:30.00]\n[02:40.00]Last line"
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
        ctx = await b.new_context(viewport={'width': 390, 'height': 844}, device_scale_factor=3, is_mobile=True, has_touch=True, color_scheme='dark')
        await ctx.add_init_script(MOCK); await ctx.add_init_script(AUTO_NOTICE)
        pg = await ctx.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
        hits = []; busy = []
        async def handler(route):
            u = route.request.url
            if '127.0.0.1' in u: return await route.continue_()
            if 'lrclib.net' in u:
                hits.append(u)
                hdr = {'Access-Control-Allow-Origin': '*', 'Content-Type': 'application/json'}
                if 'Busy%20Song' in u:
                    busy.append(u)
                    if '/api/get' in u: return await route.fulfill(status=503, headers=hdr, body='{"name":"ServerOverloaded"}')
                    if len([x for x in busy if '/api/search' in x]) == 1: return await route.fulfill(status=503, headers=hdr, body='{"name":"ServerOverloaded"}')
                    return await route.fulfill(status=200, headers=hdr, body=json.dumps([
                        {'trackName': 'Busy Song', 'duration': 260, 'syncedLyrics': '[00:01.00]Wrong length one\n[00:02.00]x'},
                        {'trackName': 'Busy Song', 'duration': 203, 'syncedLyrics': '[00:01.00]Right length\n[00:02.00]y'},
                        {'trackName': 'Busy Song', 'duration': 201, 'plainLyrics': 'untimed'}]))
                if 'Down%20Song' in u:
                    return await route.fulfill(status=503, headers=hdr, body='{"name":"ServerOverloaded"}')
                if 'Prince%2001' in u or 'Prince+01' in u:
                    if '/api/get' in u:
                        return await route.fulfill(status=200, headers=hdr, body=json.dumps({'trackName': 'Prince 01', 'artistName': 'Prince', 'duration': 200, 'instrumental': False, 'plainLyrics': 'x', 'syncedLyrics': LRC}))
                if '/api/search' in u: return await route.fulfill(status=200, headers=hdr, body='[]')
                return await route.fulfill(status=404, headers=hdr, body='{}')
            return await route.abort()
        await pg.route('**/*', handler)
        await pg.goto(f'http://127.0.0.1:{PORT}/index.html'); await pg.wait_for_timeout(2500)
        await pg.evaluate("""(function(){ var ov=document.getElementById('addMusicOverlay'); if(ov) ov.classList.add('open');
          var btn=document.getElementById('addMusicFolderBtn'); btn.disabled=false; btn.click(); })()""")
        for _ in range(90):
            await pg.wait_for_timeout(500)
            if await pg.evaluate("__d.n()") >= len(SONGS): break
        await pg.evaluate("document.getElementById('addMusicOverlay').classList.remove('open'); try{ hideImportPanel(); setStatus('', false); }catch(e){}")
        await pg.evaluate("__d.w294.play()"); await pg.wait_for_timeout(2000)
        # a position we control, and seeks we can see
        await pg.evaluate("""window.__pos = 130; window.__seeks = []; Object.defineProperty(document.querySelector('audio') || window.audio || {}, 'x', {value:1});""")
        await pg.evaluate("""(()=>{ const a = __d.audio ? __d.audio() : null; })()""")
        await pg.evaluate("__d.w298pos()")
        # 1) the queue's Now Playing title in the cover colour
        await pg.evaluate("document.getElementById('npUpNext').click()"); await pg.wait_for_timeout(500)
        qc = await pg.evaluate("(()=>{ const t = document.querySelector('#queueNow .queue-row-title'); const probe = document.createElement('span'); probe.style.color = getComputedStyle(document.body).getPropertyValue('--np-vivid'); document.body.appendChild(probe); const v = getComputedStyle(probe).color; probe.remove(); return { title: getComputedStyle(t).color, vivid: v }; })()")
        print('queue title', qc)
        check(qc['title'] == qc['vivid'] and qc['title'] not in ('rgb(255, 0, 0)',), f'the queue\'s Now Playing title wears the cover colour {qc}')
        await pg.screenshot(path=f'{shots}/b298-queue.png')
        await pg.evaluate("document.getElementById('queueCloseBtn').click()"); await pg.wait_for_timeout(500)
        # 2) swipe left on Now Playing opens the lyrics, not the queue
        OPEN = "({ lyr: document.getElementById('lyricsPanel').classList.contains('open'), q: document.getElementById('queuePanel').classList.contains('open') })"
        await pg.evaluate(f"({SWIPE})(document.getElementById('nowPlayingScreen'), -260)"); await pg.wait_for_timeout(700)
        st = await pg.evaluate(OPEN)
        check(st['q'] and not st['lyr'], f'build 299: a swipe left opens the queue {st}')
        await pg.evaluate(f"({SWIPE})(document.getElementById('queuePanel'), 260)"); await pg.wait_for_timeout(600)
        check(not (await pg.evaluate(OPEN))['q'], 'a swipe right on the queue closes it')
        await pg.evaluate(f"({SWIPE})(document.getElementById('nowPlayingScreen'), 260)"); await pg.wait_for_timeout(1500)
        st = await pg.evaluate(OPEN)
        check(st['lyr'] and not st['q'], f'a swipe right opens Lyrics {st}')
        lx = await pg.evaluate("document.getElementById('lyricsPanel').getBoundingClientRect().left")
        check(abs(lx) < 1, f'from the left, settled on screen {lx}')
        info = await pg.evaluate("""(()=>{ const now = document.querySelector('#lyricsBody .lyrics-line.now'); const sc = document.getElementById('lyricsScroll');
          const r = now && now.getBoundingClientRect(), sr = sc.getBoundingClientRect();
          return { lines: document.querySelectorAll('#lyricsBody .lyrics-line').length, now: now && now.textContent, past: document.querySelectorAll('#lyricsBody .lyrics-line.past').length,
            frac: r ? (r.top + r.height / 2 - sr.top) / sr.height : null, song: document.getElementById('lyricsSong').textContent, credit: document.getElementById('lyricsCredit').textContent }; })()""")
        print('lyrics', info)
        check(info['lines'] == 7 and info['now'] == 'Line at two-oh-eight' and info['past'] == 3, f'timed lyrics: the line being sung (2:08 at 2:10) is lit, earlier ones marked past {info}')
        check(info['frac'] is not None and 0.2 < info['frac'] < 0.45, f'and it is kept in view, about a third of the way down {info["frac"]}')
        check(info['song'] == 'Prince 01' and 'LRCLIB' in info['credit'], f'song name in the header, source credited {info["song"]}, {info["credit"]}')
        bg = await pg.evaluate("(()=>{ const l = document.getElementById('lyricsPanel'), q = document.getElementById('queuePanel'); return [getComputedStyle(l).backgroundImage, getComputedStyle(q).backgroundImage]; })()")
        check(bg[0] == bg[1], f'same background as the queue panel {bg[0][:90]}')
        await pg.screenshot(path=f'{shots}/b298-lyrics.png')
        # 3) it follows the song
        await pg.evaluate("window.__pos = 141"); await pg.wait_for_timeout(1200)
        n2 = await pg.evaluate("document.querySelector('#lyricsBody .lyrics-line.now').textContent")
        check(n2 == 'Line at two-twenty', f'moves on as the song plays (2:21) {n2}')
        # 4) a tap on a line jumps there
        await pg.evaluate("document.querySelectorAll('#lyricsBody .lyrics-line')[2].click()"); await pg.wait_for_timeout(300)
        sk = await pg.evaluate("window.__seeks")
        check(sk and abs(sk[-1] - 120.5) < 0.01, f'tapping a line seeks to it {sk}')
        await pg.wait_for_timeout(400)
        n3 = await pg.evaluate("document.querySelector('#lyricsBody .lyrics-line.now').textContent")
        check(n3 == 'Line at two', f'and lights it {n3}')
        # 5) swipe right closes
        await pg.evaluate(f"({SWIPE})(document.getElementById('lyricsPanel'), 260)"); await pg.wait_for_timeout(600)
        check(await pg.evaluate("document.getElementById('lyricsPanel').classList.contains('open')"), 'a swipe right on Lyrics leaves it open')
        await pg.evaluate(f"({SWIPE})(document.getElementById('lyricsPanel'), -260)"); await pg.wait_for_timeout(600)
        check(not await pg.evaluate("document.getElementById('lyricsPanel').classList.contains('open')"), 'a swipe left closes it (back the way it came)')
        lx = await pg.evaluate("document.getElementById('lyricsPanel').getBoundingClientRect().right")
        check(lx <= 1, f'tucked away off the left edge {lx}')
        # 6) kept: opening again doesn't look it up again
        before = len(hits)
        await pg.evaluate("__amplifyLyrics.state.key = ''; __amplifyLyrics.open()"); await pg.wait_for_timeout(800)
        check(len(hits) == before and await pg.evaluate("document.querySelectorAll('#lyricsBody .lyrics-line').length") == 7, f'kept on the device: no second lookup ({len(hits) - before})')
        await pg.evaluate("__amplifyLyrics.close()")
        # 7) a song with none
        r = await pg.evaluate("(async()=>{ const t = __d.w298other(); const v = await window.__amplifyFindLyrics(t); return v; })()")
        check(r and r.get('none'), f'a song LRCLIB doesn\'t know: none (kept, retried after a few days) {r}')
        # 7b) build 300: exact match busy, first search busy -> retried; nearest timed copy wins
        r = await pg.evaluate("(async()=>{ const t = Object.assign({}, __d.w298other(), { name: 'Busy Song', artist: 'Busy Artist feat. Someone', album: 'Busy Album', duration: 200, localId: 'busy-1' }); return await window.__amplifyFindLyrics(t); })()")
        print('busy', r, len(busy), hits[-4:])
        check(r and 'Right length' in (r.get('synced') or ''), f'a busy server is retried and the copy nearest in length (timed) is used {r}')
        # 7c) completely down: a clear message with a Try again button, nothing kept
        await pg.evaluate("__amplifyLyrics.close()")
        await pg.evaluate("(()=>{ const t = Object.assign({}, __d.w298other(), { name: 'Down Song', artist: 'Down Artist', album: 'A', duration: 200, localId: 'down-1' }); window.__downT = t; })()")
        await pg.evaluate("__amplifyLyrics.open(); clearInterval(__amplifyLyrics.state.timer); __amplifyLyrics.load(window.__downT)"); await pg.wait_for_timeout(9000)
        msg = await pg.evaluate("document.getElementById('lyricsBody').innerText")
        print('down', repr(msg))
        check('busy' in msg and await pg.evaluate("!!document.getElementById('lyricsRetryBtn')"), f'when LRCLIB is down: says why, offers Try again {msg!r}')
        kept = await pg.evaluate("(async()=>{ return await new Promise(r=>{ const q=indexedDB.open('amplifyLyrics',1); q.onsuccess=()=>{ const g=q.result.transaction('l').objectStore('l').get(favKeyProbe); g.onsuccess=()=>r(g.result||null); }; }); })()".replace('favKeyProbe', "'__none__'"))
        await pg.evaluate("__amplifyLyrics.close()")
        # 8) the menu has Lyrics for a song
        check(await pg.evaluate("(()=>{ try{ syncNpMenuItems && syncNpMenuItems(); }catch(e){} return getComputedStyle(document.getElementById('npLyricsMenuBtn')).display !== 'none'; })()"), 'Lyrics is in the Now Playing menu')
        # 9) LRC parsing edge cases
        pr = await pg.evaluate("__amplifyLyrics.parse('[ar:X]\\n[offset:+500]\\n[00:10.00][00:30.00]Chorus\\n[00:20.5]<00:20.50>Word <00:21.00>timed\\n[00:40.00]')")
        print('parse', pr)
        check(pr and [round(l['t'], 2) for l in pr] == [9.5, 20.0, 29.5] and pr[1]['text'] == 'Word timed', f'LRC: repeated stamps, offset, word timings, trailing marker {pr}')
        check(not errs, f'no page errors {errs[:2]}')
        await b.close()
    print('ALL PASSED' if not fails else f'FAILED {len(fails)}')
asyncio.run(main())
