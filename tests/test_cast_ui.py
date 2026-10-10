"""Build 194: the Cast button and "Casting to ..." line (Google Cast for streams). Mocked native
side: castInfo/castPick and 'cast' events; state events carrying cast:true for the current item.
Checks: no button without a Chromecast; the button beside Menu when one is found (header, Now
Playing, an album-like glass page), dark and light; it opens the picker; connected = accent
icon + title; Now Playing says "Casting to Living Room TV" for a stream on the Chromecast and
"Playing on this phone" for one that isn't; it all goes when the session ends.
Run: python3 tests/test_cast_ui.py (screenshots in /tmp/claude-0/t/shots)"""
import asyncio, os
HERE = os.path.dirname(os.path.abspath(__file__))
src = open(os.path.join(HERE, 'test_fav_order.py')).read()
exec(src[:src.index('\nasync def main():')].replace('8819', '8826').replace('srv-favord', 'srv-cast'))
CASTMOCK = """(function(){
  var P = window.Capacitor.Plugins.AmplifyPlayer;
  window.__castInfo = { supported: true, available: false, connected: false, connecting: false, device: '', active: false };
  window.__picks = 0;
  window.Capacitor.Plugins.AmplifyPlayer = new Proxy({}, { get: function(t, k){
    if(k === 'load') return function(a){ window.__loads = (window.__loads || []).concat([{ url: a.url, castVideo: !!a.castVideo }]); return P.load(a); };
    if(k === 'castInfo') return function(){ return Promise.resolve(window.__castInfo); };
    if(k === 'castPick') return function(){ window.__picks++; return Promise.resolve({}); };
    if(k === 'lastCrash') return function(){ var t = window.__crashText || ''; window.__crashText = ''; return Promise.resolve({ text: t, caught: '' }); };
    return P[k];
  }});
})();"""
VIS = """(()=>{ var b=document.getElementById('castBtn'), m=document.getElementById('hamburgerBtn'); var cs=getComputedStyle(b);
  var r=b.getBoundingClientRect(), mr=m.getBoundingClientRect();
  return { shown: cs.display !== 'none' && !b.hidden && r.width > 0, color: cs.color, w: Math.round(r.width), cy: Math.round(r.top + r.height/2), mcy: Math.round(mr.top + mr.height/2),
           leftOfMenu: r.right <= mr.left, gap: Math.round(mr.left - r.right), title: b.title, inView: r.top >= 0 && r.right <= innerWidth }; })()"""
NOTE = "(()=>{ var n=document.getElementById('npCastNote'); return n.hidden || getComputedStyle(n).display==='none' ? null : n.textContent.trim(); })()"

async def run(p, theme):
    b = await p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
    ctx = await b.new_context(viewport={'width': 412, 'height': 900}, device_scale_factor=2, is_mobile=True, has_touch=True, color_scheme=theme, locale='en-US')
    await ctx.add_init_script(MOCK)
    await ctx.add_init_script(CASTMOCK)
    if theme == 'dark':
        await ctx.add_init_script("if(!sessionStorage.getItem('crashShown')){ sessionStorage.setItem('crashShown','1'); window.__crashText = '2026-10-10 12:31:00 Android 16 (36) SM-S948U thread main\\njava.lang.IllegalStateException: test crash\\n\\tat com.markcoleman.amplify.CastBridge.load(CastBridge.java:1)'; }")
    await ctx.add_init_script("localStorage.setItem('radioPlayerVideoChannels', %s); localStorage.setItem('radioPlayerFavorites', %s); localStorage.setItem('radioPlayerTheme', '%s');" % (repr(json.dumps(CHS)), repr(json.dumps(FAVS)), theme))
    pg = await ctx.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
    await pg.route('**/*', route)
    await pg.goto('http://127.0.0.1:8826/index.html'); await pg.wait_for_timeout(2500)
    t = theme
    if theme == 'dark':
        await pg.wait_for_timeout(1200)
        d = await pg.evaluate("[document.getElementById('dataDialogOverlay').classList.contains('open'), document.getElementById('dataDialogTitle').textContent, document.getElementById('dataDialogMessage').textContent]")
        check(d[0] and d[1] == 'Amplify closed unexpectedly' and 'IllegalStateException: test crash' in d[2], f'{t}: after a crash the next start shows the error once {d[:2]}')
        await pg.screenshot(path=f'{SHOTS}/cast-crash-dialog.png')
        await pg.evaluate("document.getElementById('dataDialogOkBtn').click()"); await pg.wait_for_timeout(300)
    v = await pg.evaluate(VIS)
    check(not v['shown'], f'{t}: no Cast button without a Chromecast on the network {v}')
    await pg.evaluate("window.__castInfo.available = true; window.__emit('cast', window.__castInfo)"); await pg.wait_for_timeout(300)
    v = await pg.evaluate(VIS)
    check(not v['shown'], f'{t}: build 196: no Cast button in the header, even with a Chromecast found {v}')
    mb = await pg.evaluate("(()=>{ var b=document.getElementById('hamburgerBtn'), r=b.getBoundingClientRect(), l=b.querySelector('.hb-label'); return {w:Math.round(r.width), h:Math.round(r.height), label: !!(l && getComputedStyle(l).display!=='none'), right: Math.round(innerWidth - r.right)}; })()")
    check(not mb['label'] and mb['w'] == mb['h'] and mb['w'] in (38, 40), f'{t}: the Menu button is its icon only, round {mb}')
    await pg.screenshot(path=f'{SHOTS}/cast-{t}-header.png', clip={'x': 0, 'y': 0, 'width': 412, 'height': 140})
    # play a station (a stream)
    await pg.evaluate("document.querySelector('.mobile-nav-btn[data-nav=home]').click()"); await pg.wait_for_timeout(500)
    await pg.evaluate("document.getElementById('favoritesHeading').click()"); await pg.wait_for_timeout(800)
    await pg.evaluate("document.querySelector('#stationsGrid .row-item').click()"); await pg.wait_for_timeout(1200)
    await pg.evaluate("(()=>{ var b=document.getElementById('playerNowTrigger') || document.querySelector('.player-bar'); b && b.click(); })()"); await pg.wait_for_timeout(1000)
    check(await pg.evaluate(NOTE) is None, f'{t}: no cast line while not casting')
    v = await pg.evaluate(VIS)
    check(v['shown'] and v['leftOfMenu'] and abs(v['cy'] - v['mcy']) <= 1 and 6 <= v['gap'] <= 14 and v['title'] == 'Cast', f'{t}: on Now Playing the Cast button is just left of Menu, level with it {v}')
    sty = await pg.evaluate("(()=>{ function st(e){ var c=getComputedStyle(e), r=e.getBoundingClientRect(); return [c.backgroundColor, c.backdropFilter || c.webkitBackdropFilter, Math.round(r.width), Math.round(r.height)]; } var ln=getComputedStyle(document.querySelector('#hamburgerBtn span')).backgroundColor; return [st(document.getElementById('castBtn')), st(document.getElementById('hamburgerBtn')), getComputedStyle(document.getElementById('castBtn')).color, ln]; })()")
    check(sty[0][0] == sty[1][0] and sty[0][1] == sty[1][1] and sty[0][2:] == sty[1][2:] == [40, 40] and sty[2] == sty[3], f'{t}: on Now Playing Cast and Menu are matching round glass buttons, same icon colour {sty}')
    await pg.screenshot(path=f'{SHOTS}/cast-{t}-np-off.png', clip={'x': 0, 'y': 0, 'width': 412, 'height': 120})
    await pg.evaluate("window.__castInfo.connected = true; window.__castInfo.device = 'Living Room TV'; window.__emit('cast', window.__castInfo)"); await pg.wait_for_timeout(200)
    await pg.evaluate("(id)=>window.__emit('state', {id:id, state:'ready', isPlaying:true, playWhenReady:true, position:0, duration:-1, live:true, cast:true, castDevice:'Living Room TV', external:true})", await pg.evaluate("window.__cur"))
    await pg.wait_for_timeout(400)
    note = await pg.evaluate(NOTE)
    v = await pg.evaluate(VIS)
    acc = await pg.evaluate("getComputedStyle(document.documentElement).getPropertyValue('--accent').trim()")
    check(note == 'Casting to Living Room TV', f'{t}: Now Playing says "Casting to Living Room TV" ({note})')
    check(v['shown'] and v['title'] == 'Casting to Living Room TV' and abs(v['cy'] - v['mcy']) <= 1, f'{t}: on Now Playing the button sits beside Menu and names the device {v}')
    await pg.evaluate("document.getElementById('castBtn').click()"); await pg.wait_for_timeout(300)
    check(await pg.evaluate("window.__picks") == 1, f'{t}: tapping it opens the device picker')
    await pg.screenshot(path=f'{SHOTS}/cast-{t}-np.png')
    # a song on the phone while connected
    await pg.evaluate("(id)=>window.__emit('state', {id:id, state:'ready', isPlaying:true, playWhenReady:true, position:0, duration:-1, live:true, external:true})", await pg.evaluate("window.__cur"))
    await pg.wait_for_timeout(300)
    note = await pg.evaluate(NOTE)
    check(note and note.startswith('Playing on this phone'), f'{t}: something not cast says it plays on the phone ({note})')
    # the Chromecast refuses something: the reason is shown, and it isn't retried as a network error
    loads0 = len([c for c in await pg.evaluate('window.__calls') if c[0] == 'load'])
    await pg.evaluate("(id)=>window.__emit('error', {id:id, code:4005, cast:true, name:'Chromecast couldn\\'t play it (error 311 HLS)', message:'The Chromecast couldn\\'t play this (error 311 HLS)'})", await pg.evaluate("window.__cur"))
    await pg.wait_for_timeout(2500)
    st = await pg.evaluate("document.getElementById('statusLine').textContent")
    loads1 = len([c for c in await pg.evaluate('window.__calls') if c[0] == 'load'])
    check('error 311' in st and 'Check storage' in st and loads1 - loads0 <= 1, f'{t}: a Chromecast refusal shows its reason, no retry loop ({st.strip()[:90]}, loads {loads0}->{loads1})')
    # session ends
    await pg.evaluate("window.__castInfo.connected = false; window.__castInfo.device = ''; window.__emit('cast', window.__castInfo)"); await pg.wait_for_timeout(300)
    check(await pg.evaluate(NOTE) is None and (await pg.evaluate(VIS))['title'] == 'Cast', f'{t}: session over: the line goes, the button says Cast')
    # a TV channel cast (video player layout)
    await pg.evaluate("window.__castInfo.connected = true; window.__castInfo.device = 'Living Room TV'; window.__emit('cast', window.__castInfo)"); await pg.wait_for_timeout(200)
    await pg.evaluate("document.getElementById('npBackBtn').click()"); await pg.wait_for_timeout(600)
    await pg.evaluate("document.querySelector('.mobile-nav-btn[data-nav=video]').click()"); await pg.wait_for_timeout(800)
    await pg.evaluate("document.querySelector('#stationsGrid .tile-row').click()"); await pg.wait_for_timeout(1500)
    await pg.evaluate("(id)=>window.__emit('state', {id:id, state:'ready', isPlaying:true, playWhenReady:true, position:0, duration:-1, live:true, cast:true, castDevice:'Living Room TV', external:true})", await pg.evaluate("window.__cur"))
    await pg.wait_for_timeout(500)
    lv = await pg.evaluate("window.__loads")
    check(lv and lv[-1]['castVideo'] and not lv[0]['castVideo'], f'{t}: a TV channel is sent as video for casting, a station is not {lv}')
    note = await pg.evaluate(NOTE)
    g = await pg.evaluate("(()=>{ var n=document.getElementById('npCastNote').getBoundingClientRect(), nm=document.getElementById('npName').getBoundingClientRect(), c=getComputedStyle(document.getElementById('npCastNote')).color; return {below: n.top >= nm.bottom - 1, color: c}; })()")
    check(note == 'Casting to Living Room TV' and g['below'], f'{t}: a TV channel on the Chromecast: the line sits under the channel name {note} {g}')
    await pg.screenshot(path=f'{SHOTS}/cast-{t}-channel.png')
    await pg.evaluate("window.__castInfo.connected = false; window.__emit('cast', window.__castInfo)"); await pg.wait_for_timeout(200)
    # immersive hides it with Menu
    check(not errs, f'{t}: no page errors {errs[:3]}')
    await b.close()

async def main():
    async with async_playwright() as p:
        await run(p, 'dark')
        await run(p, 'light')
    print('ALL PASSED' if not fails else f'FAILED {fails}')
asyncio.run(main())
