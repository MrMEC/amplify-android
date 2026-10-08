"""Build 159: VLC is the player for videos on the phone (movies, TV, music videos), inside the
app: the page loads them through the same call as the phone's player with engine 'vlc' (and the
hardware-decoding choice), so Now Playing, controls and the floating window are unchanged. No
"Play in VLC" item and no separate VLC screen. Settings can switch to the phone's player; a file
one player fails on is tried in the other. Plex stays on the phone's player.
Run: python3 tests/test_vlc.py"""
import asyncio, os, json
HERE = os.path.dirname(os.path.abspath(__file__))
src = open(os.path.join(HERE, 'test_music_videos.py')).read()
head = src[:src.rindex('\nasync def main()')]
head = head.replace("PORT = 8814", "PORT = 8815").replace("'/tmp/claude-0/t/srv_mv'", "'/tmp/claude-0/t/srv_vlc'")
head = head.replace("load: function(o){ cur = o.id; window.__loaded = o;", "load: function(o){ (window.__loads = window.__loads || []).push(o); if(window.__failLoad && o.url && o.url.indexOf(window.__failLoad) !== -1 && (window.__failEngine || 'vlc') === (o.engine || 'phone')){ emitErr = true; setTimeout(function(){ emit('error', { id: o.id, code: 4001, name: 'ERROR_CODE_DECODING_FAILED', message: 'decoder' }); }, 30); window.__loaded = o; cur = o.id; return Promise.resolve({}); } cur = o.id; window.__loaded = o;")
head = head.replace("var picked = %s, widths = %s, listeners = {}, cur = null;", "var picked = %s, widths = %s, listeners = {}, cur = null, emitErr = false;")
assert '__failLoad' in head
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
        rows = await pg.evaluate("[getComputedStyle(document.getElementById('videoPlayerRow')).display, document.getElementById('videoPlayerSelect').value, Array.from(document.getElementById('videoPlayerSelect').options).map(function(o){return o.value;}), document.getElementById('vlcHwSelect').value]")
        check(rows[0] != 'none' and rows[1] == 'vlc' and rows[2] == ['vlc', 'builtin'] and rows[3] == 'on', f'Settings: Video player is VLC by default (VLC / Phone\u2019s player), hardware decoding on {rows}')
        last = lambda: pg.evaluate("window.__loaded || {}")
        async def tile(name):
            await pg.evaluate("__t.openArtist('Bob')"); await pg.wait_for_timeout(1200)
            await pg.evaluate("(function(n){ Array.from(document.querySelectorAll('#stationsGrid .mv-tile')).filter(function(t){ return t.querySelector('.yt-title').textContent === n; })[0].click(); })(%s)" % json.dumps(name))
            await pg.wait_for_timeout(900)
        await tile('Live at Wembley')
        l = await last()
        check(l.get('url', '').endswith('.avi') and l.get('engine') == 'vlc' and l.get('hw') is True, f'an .avi plays in VLC through the normal player (engine vlc, hardware on) {l}')
        np = await pg.evaluate("[document.getElementById('nowPlayingScreen').style.display, !!document.getElementById('npVlcBtn')]")
        check(np[0] == 'flex' and not np[1], f'it opens the normal Now Playing; no "Play in VLC" item {np}')
        await tile('Great Song')
        l = await last()
        check('Great%20Song' in l.get('url', '') and l.get('engine') == 'vlc', f'an .mp4 plays in VLC too (VLC is the default for every video) {l}')
        # VLC fails on a file: the phone's player gets a go
        await pg.evaluate("window.__failLoad = 'carl_backstage'; window.__failEngine = 'vlc'; window.__loads = []")
        await pg.evaluate("__t.openArtist('Carl')"); await pg.wait_for_timeout(1000)
        await pg.evaluate("document.querySelector('#stationsGrid .mv-tile').click()"); await pg.wait_for_timeout(2500)
        ls = await pg.evaluate("(window.__loads || []).map(function(o){ return [o.url.split('/').pop(), o.engine || 'phone']; })")
        check(len(ls) >= 2 and ls[0][1] == 'vlc' and ls[1][1] == 'phone' and 'carl_backstage' in ls[1][0], f'VLC couldn\u2019t play it: tried in the phone\u2019s player {ls}')
        await pg.evaluate("window.__failLoad = null")
        # hardware decoding off
        await pg.evaluate("var h=document.getElementById('vlcHwSelect'); h.value='off'; h.dispatchEvent(new Event('change'));")
        await tile('Great Song')
        l = await last()
        check(l.get('engine') == 'vlc' and l.get('hw') is False, f'hardware decoding off is passed to VLC {l}')
        # Settings: the phone's player
        await pg.evaluate("var s=document.getElementById('videoPlayerSelect'); s.value='builtin'; s.dispatchEvent(new Event('change'));")
        await tile('Live at Wembley')
        l = await last()
        check(l.get('url', '').endswith('.avi') and not l.get('engine'), f'"Phone\u2019s player": videos load without VLC {l}')
        old = await pg.evaluate("localStorage.setItem('radioPlayerVideoPlayer', 'auto'); document.getElementById('videoPlayerSelect').value")
        check(not errs, f'no page errors {errs[:3]}')
        await b.close()
    print('ALL PASSED' if not fails else f'FAILED {fails}')

asyncio.run(main())
