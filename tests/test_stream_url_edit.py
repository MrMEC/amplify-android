"""Build 480 (Mark): Now Playing's More menu says "Edit stream URL" for a radio station and opens a
dialog: the URL pre-filled in an editable input, a Copy button that copies what's in the input,
and Save that updates the station's stream URL (never saved when the input is empty). Other
streams (TV channels) keep "Copy stream URL". Uses Mark's backup; phone 412, dark + light."""
import sys, os
here = os.path.dirname(os.path.abspath(__file__))
_src = open(os.path.join(here, 'test_fav_playing.py')).read()
_head = _src[:_src.index('async def main():')].replace('PORT = 8894', 'PORT = 8897').replace('srv_favplay', 'srv_streamurl')
__file__ = os.path.join(here, 'test_fav_playing.py')
exec(_head)

async def run(b, theme):
    T = f'[{theme}]'
    ctx = await b.new_context(viewport={'width': 412, 'height': 915}, device_scale_factor=2, is_mobile=True, has_touch=True, color_scheme=theme)
    await ctx.grant_permissions(['clipboard-read', 'clipboard-write'], origin=f'http://127.0.0.1:{PORT}')
    await ctx.add_init_script(SEED); await ctx.add_init_script(AUTO_NOTICE)
    await ctx.add_init_script("try{ localStorage.setItem('radioPlayerTheme', '%s'); }catch(e){}" % theme)
    pg = await ctx.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
    played = []
    async def route(r):
        u = r.request.url
        if '127.0.0.1' in u: return await r.continue_()
        played.append(u)
        return await r.abort()
    await pg.route('**/*', route)
    await pg.goto(f'http://127.0.0.1:{PORT}/index.html'); await pg.wait_for_timeout(3500)
    ev = lambda js: pg.evaluate("(j)=>__t.ev(j)", js)
    async def menu_label(name):
        await ev("(function(){ var s = favorites.filter(function(f){ return f.name === %s; })[0]; playStation(s); openNowPlaying(s, true); })()" % json.dumps(name))
        await pg.wait_for_timeout(900)
        await pg.evaluate("document.getElementById('npMenuBtn').click()"); await pg.wait_for_timeout(400)
        return await pg.evaluate("({ label: document.getElementById('npCopyLabel').textContent, shown: getComputedStyle(document.getElementById('npCopyBtn')).display !== 'none' })")
    # a TV channel keeps Copy
    m = await menu_label('MTV')
    check(m['label'] == 'Copy stream URL', f'{T} a TV channel keeps "Copy stream URL" {m}')
    check(await pg.evaluate("getComputedStyle(document.getElementById('npEditUrlIcon')).display") == 'none', f'{T} ... with its copy icon')
    await ev("closeNpMenu()")
    for name in ('Kafka Chill', 'Jazz Cafe'):   # with a directory id / without one
        before = await ev("(function(){ var s = favorites.filter(function(f){ return f.name === %s; })[0]; return { key: favKey(s), url: s.urlToResolve, uuid: s.stationuuid || null }; })()" % json.dumps(name))
        m = await menu_label(name)
        check(m['label'] == 'Edit stream URL' and m['shown'], f'{T} {name}: the More menu says "Edit stream URL" {m}')
        ic = await pg.evaluate("(()=>{ var b = document.getElementById('npCopyBtn'), sv = document.getElementById('npEditUrlIcon'); return { svg: getComputedStyle(sv).display !== 'none' && sv.getBoundingClientRect().width > 10, copy: getComputedStyle(document.getElementById('npCopyIcon')).display }; })()")
        check(ic['svg'] and ic['copy'] == 'none', f'{T} {name}: it has its own link icon {ic}')
        if name == 'Kafka Chill': await pg.screenshot(path=f'{shots}/streamurl-{theme}-menu.png')
        await pg.evaluate("document.getElementById('npCopyBtn').click()"); await pg.wait_for_timeout(500)
        d = await pg.evaluate("""()=>{ var o = document.getElementById('streamUrlOverlay'), i = document.getElementById('streamUrlInput');
          return { open: o.classList.contains('open'), value: i.value, focused: document.activeElement === i, save: document.getElementById('streamUrlSaveBtn').disabled,
                   menuOpen: !!document.querySelector('.np-menu.open, #npMenu.open'), label: document.getElementById('streamUrlStation').textContent }; }""")
        check(d['open'] and d['value'] == before['url'], f'{T} {name}: the dialog opens with the stream URL in the input ({d["value"][:50]})')
        check(not d['focused'], f'{T} {name}: the input is not focused on opening (no keyboard until tapped)')
        check(d['save'], f'{T} {name}: Save is off until the URL is changed')
        await pg.screenshot(path=f'{shots}/streamurl-{theme}-{name.replace(" ", "-")}.png')
        # Copy copies what is in the input
        await pg.evaluate("document.getElementById('streamUrlCopyBtn').click()"); await pg.wait_for_timeout(400)
        clip = await pg.evaluate("navigator.clipboard.readText()")
        ico = await pg.evaluate("document.querySelector('#streamUrlCopyBtn i').className")
        check(clip == before['url'] and 'check' in ico, f'{T} {name}: Copy puts the URL on the clipboard and shows a tick ({clip[:40]}, {ico})')
        await pg.screenshot(path=f'{shots}/streamurl-{theme}-{name.replace(" ", "-")}-copied.png')
        # empty: never saved
        await pg.fill('#streamUrlInput', '   ')
        dis = await pg.evaluate("[document.getElementById('streamUrlSaveBtn').disabled, document.getElementById('streamUrlCopyBtn').disabled]")
        await pg.evaluate("document.getElementById('streamUrlSaveBtn').click()"); await pg.wait_for_timeout(300)
        still = await ev("(function(){ var s = favorites.filter(function(f){ return f.name === %s; })[0]; return s.urlToResolve; })()" % json.dumps(name))
        check(dis == [True, True] and still == before['url'] and await pg.evaluate("document.getElementById('streamUrlOverlay').classList.contains('open')"),
              f'{T} {name}: with the input empty Save is off and nothing is saved {dis}')
        # edited and saved (typed, as on the phone)
        new = 'https://new-stream.example/%s.mp3' % name.replace(' ', '').lower()
        await pg.fill('#streamUrlInput', '')
        await pg.type('#streamUrlInput', new)
        played.clear()
        await pg.evaluate("document.getElementById('streamUrlSaveBtn').click()"); await pg.wait_for_timeout(1500)
        after = await ev("""(function(){ var s = favorites.filter(function(f){ return f.name === %s; })[0];
          var inPl = []; stationPlaylists.forEach(function(p){ p.stations.forEach(function(x){ if(favKey(x) === favKey(s)) inPl.push(x.urlToResolve); }); });
          var stored = JSON.parse(localStorage.getItem('radioPlayerFavorites')).filter(function(f){ return f.name === %s; })[0];
          return { key: favKey(s), url: s.urlToResolve, stored: stored.urlToResolve, storedKey: favKey(stored), inPl: inPl, cur: currentStation && currentStation.urlToResolve,
                   edits: JSON.parse(localStorage.getItem('radioPlayerStreamEdits') || '{}'), open: document.getElementById('streamUrlOverlay').classList.contains('open') }; })()""" % (json.dumps(name), json.dumps(name)))
        check(not after['open'], f'{T} {name}: Save closes the dialog')
        check(after['url'] == new and after['stored'] == new and after['cur'] == new and all(u == new for u in after['inPl']),
              f'{T} {name}: the station now uses the new URL in favourites, saved storage, playlists ({len(after["inPl"])}) and on air')
        check(after['key'] == before['key'] and after['storedKey'] == before['key'], f'{T} {name}: it keeps its identity (cover, plays, favourite) {before["key"][:40]} -> {after["key"][:40]}')
        check(after['edits'].get(before['key']) == new, f'{T} {name}: the edit is remembered for the station wherever it appears')
        check(any(u.startswith(new) for u in played), f'{T} {name}: playing switches to the new address straight away {played[:2]}')
        # reopened: shows the new URL
        await pg.evaluate("document.getElementById('npMenuBtn').click()"); await pg.wait_for_timeout(300)
        await pg.evaluate("document.getElementById('npCopyBtn').click()"); await pg.wait_for_timeout(400)
        check(await pg.evaluate("document.getElementById('streamUrlInput').value") == new, f'{T} {name}: opening it again shows the new URL')
        await pg.evaluate("document.getElementById('streamUrlCloseBtn').click()"); await pg.wait_for_timeout(300)
    # a directory station coming back from the directory carries the edit
    k = await ev("stationToCardData({ stationuuid: %s, name: 'Kafka Chill', url: 'http://kafka.icu:8181/stream', url_resolved: 'http://kafka.icu:8181/stream' }).urlToResolve" % json.dumps((await ev("favorites.filter(function(f){ return f.name === 'Kafka Chill'; })[0].stationuuid"))))
    check(k == 'https://new-stream.example/kafkachill.mp3', f'{T} the same station from search / genres / Home uses the edited URL ({k})')
    # survives a restart
    await pg.reload(); await pg.wait_for_timeout(3000)
    r = await ev("favorites.filter(function(f){ return f.name === 'Jazz Cafe'; })[0].urlToResolve")
    check(r == 'https://new-stream.example/jazzcafe.mp3', f'{T} kept after restarting the app ({r})')
    check(not errs, f'{T} no page errors {errs[:3]}')
    await ctx.close()

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
        for theme in ('dark', 'light'):
            await run(b, theme)
        await b.close()
asyncio.run(main())
print('FAILED: %d' % len(fails) if fails else 'ALL PASS'); raise SystemExit(1 if fails else 0)
