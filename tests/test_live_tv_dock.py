"""Build 573: Live TV is the video and the guide. The Watch tabs at the very top (no Watch heading, no
profile picture), the channel's video under them (muted, started by itself), the guide under that, with
the arrow at the guide's top left always there; Cast and Mute with the video's controls. Sideways: the video
on the left, the guide with its timeline on the right.
Run: python3 tests/test_live_tv_dock.py (screenshots in /tmp/claude-0/t/shots)"""
import sys as _nsys, os as _nos; _nsys.path.insert(0, _nos.path.dirname(_nos.path.abspath(__file__))); from notice_auto import AUTO_NOTICE
import os
HERE = os.path.dirname(os.path.abspath(__file__))
src = open(os.path.join(HERE, 'test_epg_grid.py')).read()
head = src[:src.index('\nasync def run(')]
head = head.replace("'/tmp/claude-0/t/srv-epg'", "'/tmp/claude-0/t/srv-dock'").replace('PORT = 8846', 'PORT = 8871')
exec(head)

STATE = """(()=>{ var r=function(sel){ var e=document.querySelector(sel); if(!e) return null; var b=e.getBoundingClientRect(); var cs=getComputedStyle(e);
  return { l:Math.round(b.left), t:Math.round(b.top), w:Math.round(b.width), h:Math.round(b.height), vis: cs.display!=='none' && cs.visibility!=='hidden' }; };
  var b=document.body;
  return { dock:b.classList.contains('ltv-dock'), land:b.classList.contains('ltv-land'), rot:b.classList.contains('rotate-lock'), np: document.getElementById('nowPlayingScreen').style.display,
    tabs: r('#ltvTabs'), tabNames: Array.from(document.querySelectorAll('#ltvTabs .home-tab')).map(function(x){ return x.textContent + (x.classList.contains('active')?'*':''); }),
    side: r('.sidebar-top'), back: r('#npBackBtn'), vwrap: r('#npVideoWrap'), art: r('#npArtWrap'), foot: r('.np-hero-foot'), grid: r('#npCollection .epg'), corner: r('#npCollection .epg .epg-corner'),
    mute: r('#vctlMute'), muted: document.getElementById('vctlMute').classList.contains('is-muted'), stop: r('#vctlStop'), castBtn: r('#vctlCast'),
    slot: document.querySelector('#npCollection .epg-time') ? document.querySelectorAll('#npCollection .epg-time')[1].getBoundingClientRect().left - document.querySelectorAll('#npCollection .epg-time')[0].getBoundingClientRect().left : null,
    nav: r('.mobile-nav'), vw: innerWidth, vh: innerHeight }; })()"""

async def run_dock(p, theme):
    T = f'[{theme}]'
    b = await p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
    ctx = await b.new_context(viewport={'width': 390, 'height': 844}, device_scale_factor=2, is_mobile=True, has_touch=True, color_scheme=theme, locale='en-US', timezone_id='America/New_York')
    await ctx.add_init_script(MOCK); await ctx.add_init_script(AUTO_NOTICE); await ctx.add_init_script(SEED)
    await ctx.add_init_script("try{ localStorage.setItem('radioPlayerLtvAuto', '1'); }catch(e){}")
    await ctx.add_init_script("try{ localStorage.setItem('radioPlayerTheme', '%s'); }catch(e){}" % theme)
    pg = await ctx.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e) + ' ' + (e.stack or '')[:300]))
    await pg.route('**/*', route)
    await pg.goto(f'http://127.0.0.1:{PORT}/index.html'); await pg.wait_for_timeout(2500)
    await pg.evaluate("document.querySelector('.mobile-nav-btn[data-nav=video]').click()"); await pg.wait_for_timeout(2800)
    check(not await pg.evaluate("document.getElementById('vctl').classList.contains('show')"), f'{T} the controls are not up as the channel starts')
    await pg.evaluate("document.querySelectorAll('#npCollection .epg-block')[1] && document.querySelectorAll('#npCollection .epg-ch')[1].click()"); await pg.wait_for_timeout(1200)
    check(not await pg.evaluate("document.getElementById('vctl').classList.contains('show')"), f'{T} nor after changing channel')
    s = await pg.evaluate(STATE)
    check(s['dock'] and s['np'] == 'flex', f'{T} opening Live TV starts a channel by itself and docks it {s["dock"]} {s["np"]}')
    check(s['tabNames'] == ['Live TV*', 'Movies', 'TV Shows', 'Music Videos', 'Continue'] and s['tabs']['t'] == 0 and s['tabs']['vis'], f'{T} the Watch tabs at the very top {s["tabNames"]} {s["tabs"]}')
    check(not (s['side'] and s['side']['w'] > 0 and s['side']['vis']) and not (s['back'] and s['back']['w'] > 0), f'{T} no Watch heading / profile picture / minimize button {s["side"]} {s["back"]}')
    check(s['muted'], f'{T} it starts muted')
    check(abs(s['art']['h'] - s['tabs']['h'] - round(390 * 9 / 16)) <= 2 and s['art']['t'] + s['art']['h'] <= s['grid']['t'], f'{T} the video right under the tabs, the guide under it {s["art"]} {s["grid"]}')
    check(s['corner'] and s['corner']['vis'], f'{T} the arrow at the grid\'s top left is showing {s["corner"]}')
    print('G2', await pg.evaluate("['.np-hero','.np-hero-foot','.np-hero-top','.np-below','#npCollection','#npCollectionGrid','#npCollection .epg'].map(function(q){var e=document.querySelector(q),b=e.getBoundingClientRect(),c=getComputedStyle(e);return [q,Math.round(b.top),Math.round(b.bottom),c.marginTop,c.marginBottom,c.paddingTop,c.paddingBottom]})"))
    print('GAP', await pg.evaluate("(()=>{var f=document.querySelector('.np-hero-foot'),g=document.querySelector('#npCollection .epg'),t=document.querySelector('.np-details'); return [Math.round(t.getBoundingClientRect().bottom), Math.round(f.getBoundingClientRect().bottom), Math.round(g.getBoundingClientRect().top)]})()"))
    await pg.screenshot(path=f'{SHOTS}/ltv-portrait-{theme}.png')
    # paused: the arrow stays
    await pg.evaluate("document.getElementById('npPlayBtn').click()"); await pg.wait_for_timeout(600)
    s2 = await pg.evaluate(STATE)
    check(s2['corner'] and s2['corner']['vis'], f'{T} paused, the arrow is still there {s2["corner"]}')
    await pg.evaluate("document.getElementById('npPlayBtn').click()"); await pg.wait_for_timeout(600)
    # the arrow hides and shows the details
    await pg.evaluate("document.querySelector('#npCollection .epg .epg-corner').click()"); await pg.wait_for_timeout(700)
    s3 = await pg.evaluate(STATE)
    check(s3['foot']['h'] <= 2, f'{T} the arrow hides the channel details {s3["foot"]}')
    await pg.screenshot(path=f'{SHOTS}/ltv-portrait-collapsed-{theme}.png')
    await pg.evaluate("document.querySelector('#npCollection .epg .epg-corner').click()"); await pg.wait_for_timeout(700)
    # controls: show them and look at Mute, Cast, Stop
    await pg.evaluate("document.getElementById('vctl').classList.add('show')"); await pg.wait_for_timeout(400)
    await pg.screenshot(path=f'{SHOTS}/ltv-portrait-controls-{theme}.png')
    s4 = await pg.evaluate(STATE)
    check(s4['mute'] and s4['mute']['vis'] and s4['stop'] and s4['stop']['vis'], f'{T} Mute beside Stop on the controls {s4["mute"]} {s4["stop"]}')
    await pg.evaluate("document.getElementById('vctlMute').click()"); await pg.wait_for_timeout(300)
    check(not (await pg.evaluate(STATE))['muted'], f'{T} Mute turns the sound on')
    # a tab: Movies leaves, Live TV back starts again
    await pg.evaluate("document.querySelector('#ltvTabs .home-tab[data-vtab=movies]').click()"); await pg.wait_for_timeout(1200)
    s5 = await pg.evaluate(STATE)
    check(not s5['dock'] and s5['np'] != 'flex', f'{T} Movies tab leaves the video {s5["dock"]} {s5["np"]}')
    await pg.screenshot(path=f'{SHOTS}/ltv-movies-{theme}.png')
    # sideways
    await pg.evaluate("document.querySelector('.watch-tabs .home-tab[data-vtab=channels]').click()"); await pg.wait_for_timeout(2500)
    await pg.set_viewport_size({'width': 844, 'height': 390}); await pg.wait_for_timeout(1500)
    s6 = await pg.evaluate(STATE)
    check(s6['land'] and not s6['rot'], f'{T} sideways: the Live TV layout, not the landscape Now Playing {s6["land"]} {s6["rot"]}')
    check(s6['art']['l'] < s6['grid']['l'] and s6['grid']['w'] > 300 and s6['art']['w'] > 380, f'{T} the video left, the guide right {s6["art"]} {s6["grid"]}')
    print('COVER', await pg.evaluate("(()=>{var a=document.getElementById('npArtWrap').getBoundingClientRect(); var out=[]; [[.1,.1],[.5,.5],[.9,.5],[.5,.9],[.9,.9]].forEach(function(p){ var el=document.elementFromPoint(a.left+a.width*p[0], a.top+a.height*p[1]); out.push(el?(el.tagName+'#'+el.id+'.'+String(el.className).split(' ')[0]):'none'); }); return [Math.round(a.left),Math.round(a.top),Math.round(a.width),Math.round(a.height),out]; })()"))
    print('KIDS', await pg.evaluate("Array.from(document.getElementById('npCollection').children).map(function(e){ var b=e.getBoundingClientRect(); return [e.id||e.className, Math.round(b.top), Math.round(b.height), getComputedStyle(e).display]; })"))
    print('CHAIN', await pg.evaluate("['.np-hero','.np-below','#npCollection','#npCollectionGrid','#npCollection .epg'].map(function(q){ var e=document.querySelector(q), b=e.getBoundingClientRect(), cs=getComputedStyle(e); return [q, Math.round(b.left), Math.round(b.top), Math.round(b.width), Math.round(b.height), cs.marginTop, cs.marginLeft, cs.paddingTop, cs.paddingLeft]; })"))
    print('LAND', s6['art'], s6['foot'], s6['grid'], s6['tabs'], s6['slot'])
    check(not (s6['nav'] and s6['nav']['vis']), f'{T} no tab bar sideways')
    await pg.screenshot(path=f'{SHOTS}/ltv-land-{theme}.png')
    await pg.set_viewport_size({'width': 390, 'height': 844}); await pg.wait_for_timeout(1500)
    s7 = await pg.evaluate(STATE)
    check(s7['dock'] and not s7['land'], f'{T} upright again {s7["dock"]} {s7["land"]}')
    check(not errs, f'{T} no page errors {errs}')
    await b.close()

async def main():
    from playwright.async_api import async_playwright
    async with async_playwright() as p:
        for th in ('dark', 'light'): await run_dock(p, th)
    print('FAILED' if fails else 'ALL PASSED', fails)
asyncio.run(main())
