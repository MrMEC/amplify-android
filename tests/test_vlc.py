"""Build 153: videos the phone can't decode go to the VLC player screen. Automatic asks the phone
per file (an .avi here can't be decoded, an .mp4 can), "VLC" sends every video there, "Built-in"
none; a video the phone's player fails on is tried in VLC; Now Playing has "Play in VLC"; what VLC
hands back (position, ended) is kept and the next video follows.
Run: python3 tests/test_vlc.py"""
import asyncio, os, json
HERE = os.path.dirname(os.path.abspath(__file__))
src = open(os.path.join(HERE, 'test_music_videos.py')).read()
head = src[:src.rindex('\nasync def main()')]
head = head.replace("PORT = 8814", "PORT = 8815").replace("'/tmp/claude-0/t/srv_mv'", "'/tmp/claude-0/t/srv_vlc'")
head = head.replace("   cacheCheck: function(){", """   videoDecodable: function(o){ window.__dec = (window.__dec || 0) + 1; return Promise.resolve(/\\.avi$/i.test(decodeURIComponent(o.uri)) ? { ok: false, why: 'the phone cannot open this kind of file' } : { ok: true, why: '' }); },
   playWithVlc: function(o){ (window.__vlc = window.__vlc || []).push(o); var r = window.__vlcResult || { position: 30000, duration: 125000, ended: false }; return new Promise(function(res){ setTimeout(function(){ res(r); }, 200); }); },
   cacheCheck: function(){""")
head = head.replace("load: function(o){ cur = o.id; window.__loaded = o;", "load: function(o){ if(window.__failLoad && o.url && o.url.indexOf(window.__failLoad) !== -1){ emitErr = true; setTimeout(function(){ emit('error', { id: o.id, code: 4001, name: 'ERROR_CODE_DECODING_FAILED', message: 'decoder' }); }, 30); window.__loaded = o; cur = o.id; return Promise.resolve({}); } cur = o.id; window.__loaded = o;")
head = head.replace("var picked = %s, widths = %s, listeners = {}, cur = null;", "var picked = %s, widths = %s, listeners = {}, cur = null, emitErr = false;")
assert 'playWithVlc' in head and '__failLoad' in head
exec(head)

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
        ctx = await b.new_context(viewport={'width': 390, 'height': 844}, device_scale_factor=2, is_mobile=True, has_touch=True, color_scheme='dark')
        await ctx.add_init_script(MOCK)
        pg = await ctx.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.route('**/*', lambda route: route.continue_() if '127.0.0.1' in route.request.url else route.abort())
        await pg.goto(f'http://127.0.0.1:{PORT}/index.html'); await pg.wait_for_timeout(2500)
        await pg.evaluate("""(function(){ var ov=document.getElementById('addMusicOverlay'); if(ov) ov.classList.add('open');
          var btn=document.getElementById('addMusicFolderBtn'); btn.disabled=false; btn.click(); })()""")
        for _ in range(60):
            await pg.wait_for_timeout(500)
            if len(await pg.evaluate('__t.tracks()')) >= 8: break
        await pg.wait_for_timeout(1500)
        print('ERRS', errs[:3]); print(await pg.evaluate('typeof window.Capacitor + " " + (window.Capacitor && window.Capacitor.isNativePlatform())'))
        rows = await pg.evaluate("[getComputedStyle(document.getElementById('videoPlayerRow')).display, document.getElementById('videoPlayerSelect').value, document.getElementById('vlcHwSelect').value]")
        check(rows == ['flex', 'auto', 'on'] or (rows[0] != 'none' and rows[1:] == ['auto', 'on']), f'Settings: Video player (Automatic) and VLC hardware decoding (On) {rows}')
        vlc = lambda: pg.evaluate('window.__vlc || []')
        loaded = lambda: pg.evaluate("(window.__loaded || {}).url || ''")
        async def tile(name):
            await pg.evaluate("__t.openArtist('Bob')"); await pg.wait_for_timeout(1200)
            await pg.evaluate("(function(n){ Array.from(document.querySelectorAll('#stationsGrid .mv-tile')).filter(function(t){ return t.querySelector('.yt-title').textContent === n; })[0].click(); })(%s)" % json.dumps(name))
            await pg.wait_for_timeout(900)
        # Automatic: the .avi goes to VLC
        await tile('Live at Wembley')
        v = await vlc(); print(v)
        check(len(v) == 1 and v[0]['uri'].endswith('.avi') and v[0]['title'] == 'Live at Wembley · Bob' and v[0]['hw'] is True and v[0]['startMs'] == 0,
              f'Automatic: the .avi the phone can’t decode opens in VLC {v}')
        check('.avi' not in await loaded(), 'and is not loaded in the phone’s player')
        await pg.wait_for_timeout(400)
        prog = await pg.evaluate("(function(){ var p = JSON.parse(localStorage.getItem('radioPlayerVideoProgress') || '{}'); return p['mv:Music/Bob/Live at Wembley.avi'] || null; })()")
        check(prog and abs(prog['pos'] - 30) < .5 and abs(prog['dur'] - 125) < .5, f'where VLC got to is kept {prog}')
        sub = await pg.evaluate("document.getElementById('playerSub').textContent")
        check('Bob' in sub, f'the player bar is back to its normal line {sub!r}')
        # Automatic: the .mp4 plays in the phone's player
        await tile('Great Song')
        check(len(await vlc()) == 1 and 'Great%20Song' in await loaded(), 'Automatic: the .mp4 the phone can decode plays in the phone’s player')
        np = await pg.evaluate("getComputedStyle(document.getElementById('npVlcBtn')).display")
        check(np != 'none', 'Now Playing’s menu has "Play in VLC" for it')
        await pg.evaluate("window.__vlcResult = { position: 125000, duration: 125000, ended: true }")
        await pg.evaluate("document.getElementById('npVlcBtn').click()"); await pg.wait_for_timeout(1500)
        v = await vlc(); s = await pg.evaluate('__t.q()')
        print('VLC CALLS', [x['uri'][-12:] for x in v])
        check(len(v) >= 2 and v[1]['uri'].endswith('.mp4'), f'"Play in VLC" opens it in VLC {v[1:2]}')
        check(s['cur'] == 'Live at Wembley' and len(await vlc()) == 3, f'it ended in VLC: the next video follows (in VLC, as an .avi) {s}')
        await pg.wait_for_timeout(500)
        # Built-in failure: tried in VLC
        await pg.evaluate("window.__vlcResult = { position: 5000, duration: 125000, ended: false }")
        await pg.evaluate("window.__failLoad = 'carl_backstage'")
        await pg.evaluate("__t.openArtist('Carl')"); await pg.wait_for_timeout(1000)
        await pg.evaluate("document.querySelector('#stationsGrid .mv-tile').click()"); await pg.wait_for_timeout(2500)
        v = await vlc()
        check(v[-1]['uri'].endswith('carl_backstage.mp4'), f'the phone’s player failed on it: tried in VLC {v[-1:]}')
        # Settings: VLC for everything; hardware decoding off
        await pg.evaluate("var s=document.getElementById('videoPlayerSelect'); s.value='vlc'; s.dispatchEvent(new Event('change')); var h=document.getElementById('vlcHwSelect'); h.value='off'; h.dispatchEvent(new Event('change'));")
        n0 = len(await vlc())
        await tile('Great Song')
        v = await vlc()
        check(len(v) == n0 + 1 and v[-1]['uri'].endswith('.mp4') and v[-1]['hw'] is False, f'"VLC": every video opens in VLC, with hardware decoding off {v[-1:]}')
        # Settings: Built-in never uses VLC
        await pg.evaluate("var s=document.getElementById('videoPlayerSelect'); s.value='builtin'; s.dispatchEvent(new Event('change'));")
        n0 = len(await vlc())
        await tile('Live at Wembley')
        check(len(await vlc()) == n0 and '.avi' in await loaded(), '"Built-in": even the .avi goes to the phone’s player')
        dec = await pg.evaluate('window.__dec')
        check(dec == 3, f'the phone is asked about each of the three files once ({dec})')
        check(not errs, f'no page errors {errs[:3]}')
        await b.close()
    print('ALL PASSED' if not fails else f'FAILED {fails}')

asyncio.run(main())
