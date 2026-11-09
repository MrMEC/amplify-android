"""Build 545 (Mark): Settings > Home chooses which kinds of favourite show in Home's Favorites tab
(stations, custom stations, artist radio, playlists and Zen start On; songs, artists, albums,
podcast episodes, live TV channels and videos start Off). Every card there gets the playing border
when it is what's on, a Zen preset included, and a Zen card's band takes its colour from its picture.
Run: python3 tests/test_home_fav_kinds.py (screenshots in /tmp/claude-0/t/shots)"""
import os
HERE = os.path.dirname(os.path.abspath(__file__))
src = open(os.path.join(HERE, 'test_artist_radio.py')).read()
pre = src[:src.index('\nasync def main():')]
pre = pre.replace("'/tmp/claude-0/t/srv_radio'", "'/tmp/claude-0/t/srv_hfk'").replace('PORT = 8813', 'PORT = 8871')
pre = pre.replace('noStations: function(){', 'ev: function(js){ return eval(js); }, noStations: function(){', 1)
assert 'ev: function(js)' in pre
exec(pre)
import asyncio, subprocess, base64
from playwright.async_api import async_playwright
fails = []
def check(c, m):
    print(('PASS ' if c else 'FAIL ') + m)
    if not c: fails.append(m)
EV = lambda js: "__t.ev(" + json.dumps(js) + ")"
KINDS = "Array.from(document.querySelectorAll('#favoritesGrid > .tile')).map(function(t){ return t._homeFav ? __t.ev('homeFavKind')(t._homeFav) : '?'; })"

async def main():
    subprocess.run(['ffmpeg', '-loglevel', 'error', '-y', '-f', 'lavfi', '-i', 'color=c=purple:s=200x200', '-frames:v', '1', f'{root}/cover.png'], check=True)
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
        for scheme in ['light', 'dark']:
            T = f'[{scheme}]'
            ctx = await b.new_context(viewport={'width': 390, 'height': 844}, device_scale_factor=2, is_mobile=True, has_touch=True, color_scheme=scheme)
            await ctx.add_init_script(MOCK); await ctx.add_init_script(AUTO_NOTICE)
            await ctx.add_init_script("try{ localStorage.setItem('radioPlayerTheme', '%s'); }catch(e){}" % scheme)
            pg = await ctx.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
            await pg.route('**/*', lambda route: route.continue_() if '127.0.0.1' in route.request.url else route.abort())
            await pg.goto(f'http://127.0.0.1:{PORT}/index.html'); await pg.wait_for_timeout(2500)
            await pg.evaluate("""(function(){ var ov=document.getElementById('addMusicOverlay'); if(ov) ov.classList.add('open');
              var btn=document.getElementById('addMusicFolderBtn'); btn.disabled=false; btn.click(); })()""")
            for _ in range(60):
                await pg.wait_for_timeout(500)
                if len(await pg.evaluate('__t.tracks()')) >= 6: break
            await pg.evaluate("(function(){ var ov=document.getElementById('addMusicOverlay'); if(ov) ov.classList.remove('open'); })()")
            await pg.evaluate(EV("""(function(){
              var bob = libraryTracks.filter(function(t){ return t.artist === 'Bob'; })[0];
              var al = buildAlbumIndex().filter(function(a){ return a.tracks.some(function(t){ return t.artist === 'Bob'; }); })[0];
              var adds = [
                { name: 'Test FM', url: 'http://127.0.0.1/x', urlToResolve: 'http://127.0.0.1/x', stationuuid: 'st1' },
                { type: 'zen', name: 'Campfire', zenId: 'campfire' },
                bob,
                artistFavRecord({ key: artistMatchKey('Bob'), name: 'Bob' }),
                al ? albumFavRecord(al) : null,
                { type: 'podcast', guid: 'ep1', name: 'Episode One', show: 'A Show', episodeUrl: 'http://127.0.0.1/ep1.mp3' },
                { type: 'video', id: 'mv1', name: 'A Movie' },
                { name: 'News TV', url: 'http://127.0.0.1/tv.m3u8', urlToResolve: 'http://127.0.0.1/tv.m3u8', stationuuid: 'tv1', videoChannel: true }
              ];
              adds.forEach(function(x){ if(x && !isFavorite(x)) toggleFavorite(x); });
              loadTopStations();
            })()"""))
            await pg.wait_for_timeout(1500)
            await pg.evaluate("(()=>{var b=document.getElementById('homeGroupTab-favorites'); if(b) b.click();})()"); await pg.wait_for_timeout(300)
            k0 = await pg.evaluate(KINDS)
            print(T, 'default', k0)
            check(sorted(k0) == ['stations', 'zen'], f'{T} by default the Favorites tab shows what it did before (stations, Zen) {k0}')
            # the Zen card's band is its picture, not grey
            band = await pg.evaluate("(()=>{var t=document.querySelector('#favoritesGrid .tile[data-key=\"zen:campfire\"] .fav-card-wash');return t?getComputedStyle(t).backgroundImage.slice(0,30):null;})()")
            box = await pg.evaluate("(()=>{var c=document.querySelector('#favoritesGrid .tile[data-key=\"zen:campfire\"] .fav-card-cap');c.scrollIntoView({block:'center'});var r=c.getBoundingClientRect();return {x:r.left+6,y:r.top+4,width:r.width-12,height:r.height-8};})()")
            await pg.wait_for_timeout(200)
            import io
            from PIL import Image
            im = Image.open(io.BytesIO(await pg.screenshot(clip=box))).convert('RGB').resize((1, 1))
            px = im.getpixel((0, 0))
            panel_grey = (178, 178, 178) if scheme == 'light' else (15, 17, 20)
            check(band and band.startswith('url(') and max(abs(a - b) for a, b in zip(px, panel_grey)) > 12, f'{T} the Zen card band is drawn from its picture, not the plain grey {px}')
            # Settings > Home
            await pg.evaluate(EV("openSettingsAt('home')")); await pg.wait_for_timeout(700)
            rows = await pg.evaluate("Array.from(document.querySelectorAll('#homeFavKindRows .settings-row')).map(function(r){return r.querySelector('.settings-label').textContent+'='+r.querySelector('select').value;})")
            print(T, rows)
            check(len(rows) == 11 and 'Songs=off' in rows and 'Zen mixes=on' in rows and 'Radio stations=on' in rows, f'{T} Settings > Home lists every kind with On/Off {rows}')
            check(await pg.evaluate("!document.querySelector('[data-set-page=home]').hidden"), f'{T} the Home settings page opens')
            await pg.screenshot(path=f'{shots}/b545-settings-home-{scheme}.png')
            for k in ['songs', 'artists', 'albums', 'podcasts', 'channels', 'videos']:
                await pg.evaluate("(k)=>{var e=document.getElementById('homeFavKind-'+k);e.value='on';e.dispatchEvent(new Event('change',{bubbles:true}));}", k)
            await pg.evaluate(EV("closeSettings && closeSettings()")); await pg.evaluate(EV("loadTopStations()")); await pg.wait_for_timeout(1500)
            await pg.evaluate("(()=>{var b=document.getElementById('homeGroupTab-favorites'); if(b) b.click();})()"); await pg.wait_for_timeout(300)
            k1 = await pg.evaluate(KINDS)
            print(T, 'all on', k1)
            check(sorted(set(k1)) == sorted(['stations', 'zen', 'songs', 'artists', 'albums', 'podcasts', 'videos', 'channels']), f'{T} turned on, every kind shows {k1}')
            cards = await pg.evaluate("Array.from(document.querySelectorAll('#favoritesGrid > .tile')).map(function(t){var r=t.getBoundingClientRect();return [t.classList.contains('fav-card'),Math.round(r.width),Math.round(r.height)];})")
            check(all(c[0] for c in cards) and len(set(c[1] for c in cards)) == 1, f'{T} all are cards of one size {cards}')
            await pg.evaluate("document.getElementById('favoritesSection').scrollIntoView({block:'start'})"); await pg.wait_for_timeout(300)
            await pg.screenshot(path=f'{shots}/b545-home-all-{scheme}.png')
            # playing border
            PL = "(k)=>{var t=Array.from(document.querySelectorAll('#favoritesGrid > .tile')).filter(function(x){return x._homeFav && __t.ev('homeFavKind')(x._homeFav)===k;})[0];return !!t && t.classList.contains('playing');}"
            await pg.evaluate(EV("zenSelect('campfire', true)")); await pg.wait_for_timeout(500)
            check(await pg.evaluate(PL, 'zen'), f'{T} a playing Zen preset gets the playing border')
            await pg.screenshot(path=f'{shots}/b545-zen-playing-{scheme}.png')
            await pg.evaluate(EV("zenPause()")); await pg.wait_for_timeout(300)
            check(not await pg.evaluate(PL, 'zen'), f'{T} and loses it when paused')
            await pg.evaluate(EV("playStation(libraryTracks.filter(function(t){ return t.artist === 'Bob'; })[0])")); await pg.wait_for_timeout(800)
            act = {k: await pg.evaluate(PL, k) for k in ['songs', 'artists', 'albums', 'stations', 'podcasts']}
            print(T, 'bob playing', act)
            check(act['songs'] and act['artists'] and act['albums'] and not act['stations'] and not act['podcasts'], f'{T} playing a favourite song lights the song, its artist and its album {act}')
            await pg.screenshot(path=f'{shots}/b545-song-playing-{scheme}.png')
            await pg.evaluate(EV("playStation(favorites.filter(function(f){return f.stationuuid==='st1';})[0])")); await pg.wait_for_timeout(800)
            act2 = {k: await pg.evaluate(PL, k) for k in ['songs', 'artists', 'albums', 'stations']}
            check(act2['stations'] and not act2['songs'] and not act2['artists'], f'{T} a station takes the border over {act2}')
            # off again, and it is kept
            await pg.evaluate(EV("setHomeFavKind('songs', false)")); await pg.wait_for_timeout(300)
            check('songs' not in await pg.evaluate(KINDS), f'{T} turning Songs off takes it out of the row')
            await pg.reload(); await pg.wait_for_timeout(2500)
            check(await pg.evaluate(EV("[homeFavKindOn('songs'), homeFavKindOn('albums'), homeFavKindOn('zen')]")) == [False, True, True], f'{T} the choices are kept')
            check(not errs, f'{T} no page errors {errs[:3]}')
            await ctx.close()
        await b.close()
asyncio.run(main())
print('FAILED' if fails else 'ALL PASS'); raise SystemExit(1 if fails else 0)
