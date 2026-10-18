"""Build 247 (Mark): a channel in search results (the Channels tab and Top Results) has Add to My
Channels in its More menu when it isn't saved, and Remove from My Channels when it is. The menu
follows the change straight away; Remove asks first; the Live TV guide shows the change.
Phone first: 390 dark, 360 light with larger text.
Run: python3 tests/test_search_channel_menu.py (screenshots in /tmp/claude-0/t/shots)"""
import sys as _nsys, os as _nos; _nsys.path.insert(0, _nos.path.dirname(_nos.path.abspath(__file__))); from notice_auto import AUTO_NOTICE
import asyncio, os, json
HERE = os.path.dirname(os.path.abspath(__file__))
src = open(os.path.join(HERE, 'test_search_live.py')).read()
head = src[:src.index('async def main()')]
head = head.replace('PORT = 8798', 'PORT = 8851').replace("'/tmp/claude-0/t/srv_srch'", "'/tmp/claude-0/t/srv_srchch'")
__file__ = os.path.join(HERE, 'test_search_live.py')
exec(head)

PLUTO = {'at': 9999999999999, 'list': [
    {'id': 'pluto:abc123', 'name': 'Ray Classics', 'url': 'https://pluto.example/stitch/hls/channel/abc123/master.m3u8', 'logo': '', 'cats': ['classic'], 'catNames': ['Classic TV'], 'src': 'pluto', 'country': 'US'}]}
SEED2 = SEED + "\nlocalStorage.setItem('radioPlayerPluto2', %s);" % json.dumps(json.dumps(PLUTO))

MENU = """(()=>{ var m=document.getElementById('rowMenu'); return { open: m.classList.contains('open'),
  items: Array.from(m.querySelectorAll('.np-menu-item')).filter(function(b){ return getComputedStyle(b).display !== 'none'; }).map(function(b){ return b.textContent.trim(); }) }; })()"""
SAVED = "JSON.parse(localStorage.getItem('radioPlayerVideoChannels')||'[]').map(function(c){ return c.name; })"


async def open_more(pg, where, name):
    sel = '#stationsGrid .ch-list .tile' if where == 'tab' else '#stationsGrid .top-result-row'
    title = '.tile-name' if where == 'tab' else '.song-row-title'
    await pg.evaluate("""([s, t, n])=>{ var r=Array.from(document.querySelectorAll(s)).find(function(x){ var e=x.querySelector(t); return e && e.textContent===n; });
      r.scrollIntoView({block:'center'}); r.querySelector('.row-more-btn').click(); }""", [sel, title, name])
    await pg.wait_for_timeout(300)


async def run(p, theme, width, big):
    T = f'[{theme} {width}{" big" if big else ""}]'
    b = await p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
    ctx = await b.new_context(viewport={'width': width, 'height': 844}, device_scale_factor=2, is_mobile=True, has_touch=True, color_scheme=theme)
    await ctx.add_init_script(MOCK); await ctx.add_init_script(AUTO_NOTICE)
    await ctx.add_init_script("if(!sessionStorage.getItem('seeded')){ sessionStorage.setItem('seeded','1'); " + SEED2 + " }")
    await ctx.add_init_script("try{ localStorage.setItem('radioPlayerTheme', %s); }catch(e){}" % json.dumps(theme))
    pg = await ctx.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
    await pg.route('**/*', route)
    await pg.goto(f'http://127.0.0.1:{PORT}/index.html'); await pg.wait_for_timeout(2500)
    if big:
        await pg.add_style_tag(content='.np-menu-item{font-size:20px !important} .tile-name,.song-row-title{font-size:calc(1em*1.35) !important}')
    await pg.evaluate("document.querySelector('.mobile-nav-btn[data-nav=search]').click()"); await pg.wait_for_timeout(400)
    await pg.tap('#searchSheetInput'); await pg.wait_for_timeout(150)
    await pg.keyboard.type('ray', delay=60); await pg.wait_for_timeout(1500)
    await pg.evaluate("document.getElementById('searchSheetInput').blur()"); await pg.wait_for_timeout(300)

    # ---- Top Results
    tops = await pg.evaluate("Array.from(document.querySelectorAll('#stationsGrid .top-result-row')).filter(function(r){ return r.dataset.kind==='channels'; }).map(function(r){ return r.querySelector('.song-row-title').textContent; })")
    check('Ray Classics' in tops and 'Ray TV News' in tops, f'{T} Top Results lists both channels {tops}')
    await open_more(pg, 'top', 'Ray Classics')
    m = await pg.evaluate(MENU)
    check(m['open'] and 'Add to My Channels' in m['items'] and not any(i.startswith('Remove') for i in m['items']), f'{T} a channel not saved: Add to My Channels {m["items"]}')
    await pg.screenshot(path=f'{shots}/srchch-add-{theme}-{width}.png')
    await pg.evaluate("document.getElementById('rowMenuAddChannel').click()"); await pg.wait_for_timeout(400)
    sv = await pg.evaluate(SAVED)
    check('Ray Classics' in sv and not (await pg.evaluate(MENU))['open'], f'{T} it is added to My Channels, the menu closes {sv}')
    await open_more(pg, 'top', 'Ray Classics')
    m = await pg.evaluate(MENU)
    check('Remove from My Channels' in m['items'] and 'Add to My Channels' not in m['items'], f'{T} reopened at once: Remove from My Channels {m["items"]}')
    await pg.screenshot(path=f'{shots}/srchch-remove-{theme}-{width}.png')
    await pg.evaluate("document.getElementById('rowMenu').classList.remove('open')")

    # ---- the Channels tab
    await pg.evaluate("Array.from(document.querySelectorAll('#searchTabs .home-tab')).filter(function(b){ return /^Channels/.test(b.textContent); })[0].click()"); await pg.wait_for_timeout(400)
    await open_more(pg, 'tab', 'Ray TV News')
    m = await pg.evaluate(MENU)
    check('Remove from My Channels' in m['items'] and 'Add to My Channels' not in m['items'] and 'Rename' in m['items'], f'{T} Channels tab, a saved channel: Remove from My Channels (and Rename) {m["items"]}')
    await pg.evaluate("document.getElementById('rowMenuRemove').click()"); await pg.wait_for_timeout(400)
    dlg = await pg.evaluate("(()=>{ var d=document.querySelector('.confirm-overlay.open, #confirmOverlay.open, .confirm.open'); return d ? d.textContent.replace(/\\s+/g,' ').trim() : null; })()")
    if dlg:
        await pg.evaluate("(()=>{ var d=document.querySelector('.confirm-overlay.open, #confirmOverlay.open, .confirm.open'); var b=Array.from(d.querySelectorAll('button')).find(function(x){ return /^Remove$/.test(x.textContent.trim()); }); b.click(); })()"); await pg.wait_for_timeout(500)
    sv = await pg.evaluate(SAVED)
    check(dlg is not None and 'Ray TV News' not in sv, f'{T} Remove asks first, then takes it out of My Channels ({dlg!r}) {sv}')
    await open_more(pg, 'tab', 'Ray TV News')
    m = await pg.evaluate(MENU)
    check('Add to My Channels' in m['items'], f'{T} and now offers Add to My Channels {m["items"]}')
    await pg.evaluate("document.getElementById('rowMenu').classList.remove('open')")
    # a song's More menu has neither
    await pg.evaluate("Array.from(document.querySelectorAll('#searchTabs .home-tab')).filter(function(b){ return /^Top/.test(b.textContent); })[0].click()"); await pg.wait_for_timeout(400)
    has_song = await pg.evaluate("!!Array.from(document.querySelectorAll('#stationsGrid .top-result-row')).find(function(r){ return r.dataset.kind!=='channels' && r.querySelector('.row-more-btn'); })")
    if has_song:
        await pg.evaluate("Array.from(document.querySelectorAll('#stationsGrid .top-result-row')).find(function(r){ return r.dataset.kind!=='channels' && r.querySelector('.row-more-btn'); }).querySelector('.row-more-btn').click()"); await pg.wait_for_timeout(300)
        m = await pg.evaluate(MENU)
        check(not any('My Channels' in i for i in m['items']) and 'Remove' not in m['items'], f'{T} other results: no channel items {m["items"]}')
        await pg.evaluate("document.getElementById('rowMenu').classList.remove('open')")

    # ---- Live TV shows the change
    await pg.evaluate("document.querySelector('.mobile-nav-btn[data-nav=video]').click()"); await pg.wait_for_timeout(900)
    await pg.evaluate("(()=>{ var t=document.querySelector('.video-tabs [data-vtab=channels]'); if(t) t.click(); })()"); await pg.wait_for_timeout(600)
    g = await pg.evaluate("Array.from(document.querySelectorAll('#stationsGrid .epg-ch')).map(function(c){ return (c.getAttribute('aria-label')||'').replace(/, playing$/,''); })")
    check(g == ['Ray Classics'], f'{T} the Live TV guide: the added channel, not the removed one {g}')
    check(not errs, f'{T} no page errors {errs[:3]}')
    await b.close()


async def main():
    async with async_playwright() as p:
        await run(p, 'dark', 390, False)
        await run(p, 'light', 360, True)
    print('ALL PASSED' if not fails else f'FAILED {fails}')

asyncio.run(main())
