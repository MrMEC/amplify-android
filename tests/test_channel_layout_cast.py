"""Build 264: channel layout and sorting, and casting your own channels.
Edit has Layout: Your Channels First (Your Channels with Order A to Z / Manual, then Added
Channels with their own Order) or Integrate Channels (one list of both, Order A to Z / Manual).
The guide follows, favourites first in each list; a guide under a playing channel follows too.
Casting: a channel's video is loaded with the schedule's start and marked as a video with a
length; a Plex MKV goes through Plex's conversion while a Chromecast is connected; a Chromecast
picked while a Plex MKV channel plays tunes in again through the conversion.
Run: python3 tests/test_channel_layout_cast.py (screenshots in /tmp/claude-0/t/shots)"""
import sys as _nsys, os as _nos; _nsys.path.insert(0, _nos.path.dirname(_nos.path.abspath(__file__))); from notice_auto import AUTO_NOTICE
import os, json, time, asyncio
HERE = os.path.dirname(os.path.abspath(__file__))
src = open(os.path.join(HERE, 'test_live_channels.py')).read()
head = src[:src.index('\nasync def run(')]
head = head.replace("'/tmp/claude-0/t/srv-livech'", "'/tmp/claude-0/t/srv-livech3'").replace('PORT = 8862', 'PORT = 8864')
exec(head)
CHANNELS.append({'id': 'link:z', 'name': 'Zed News', 'url': 'http://zed.example/live.m3u8', 'logo': '', 'cats': [], 'catNames': [], 'src': 'link'})
SEED = """(function(){ if(!localStorage.getItem('__seeded')){ localStorage.setItem('__seeded','1');
  localStorage.setItem('radioPlayerPlexAccount', %s);
  var lib = JSON.parse(%s); lib.at = Date.now(); localStorage.setItem('radioPlayerPlexLib', JSON.stringify(lib));
  localStorage.setItem('radioPlayerVideoFiles', %s);
  localStorage.setItem('radioPlayerVideoInfo', %s);
  localStorage.setItem('radioPlayerVideoChannels', %s);
  localStorage.setItem('radioPlayerVideoTab', 'channels'); } })();""" % tuple(json.dumps(json.dumps(x)) for x in (ACCT, LIB, FILES, INFO, CHANNELS))

LIVE = ['amplify-live:office', 'amplify-live:madtv', 'amplify-live:seinfeld', 'amplify-live:movies']
NAME = {'amplify-live:office': 'The Office (US)', 'amplify-live:madtv': 'MADtv', 'amplify-live:seinfeld': 'Seinfeld', 'amplify-live:movies': 'Movies',
        CHANNELS[0]['url']: 'Buzzr', CHANNELS[1]['url']: 'Zed News'}
EDITROWS = """(()=>Array.from(document.querySelectorAll('#stationsGrid .ch-edit-list')).map(function(l){ return { cls: l.className.replace('ch-edit-list ',''),
  rows: Array.from(l.querySelectorAll(':scope > .tile')).map(function(t){ return t.querySelector('.tile-name').textContent; }),
  drag: l.querySelectorAll(':scope > .tile.tile-draggable').length, grips: l.querySelectorAll('.ch-grip').length }; }))()"""
LINES = """(()=>Array.from(document.querySelectorAll('#stationsGrid .ch-sort-line')).map(function(l){ return l.querySelector('.ch-sort-label').textContent + ':' + Array.from(l.querySelectorAll('.home-tab')).map(function(b){ return (b.classList.contains('active') ? '*' : '') + b.textContent; }).join('/'); }))()"""
HEADS = "Array.from(document.querySelectorAll('#stationsGrid > .ch-group-head')).map(function(h){ return h.textContent; })"
async def pick_line(pg, line_id, opt):
    await pg.evaluate("(function(i,o){ document.querySelector('#'+i+' .home-tab[data-opt=\"'+o+'\"]').click(); })(%s,%s)" % (json.dumps(line_id), json.dumps(opt)))
    await pg.wait_for_timeout(400)
async def edit(pg):
    await pg.evaluate("document.getElementById('videoReorderHeaderBtn').click()"); await pg.wait_for_timeout(600)
async def guide_names(pg, sel='#stationsGrid .epg'):
    g = await grid(pg, sel)
    return [NAME.get(r['url'], r['url']) for r in g['rows']]
# moves a row to the top of its list, as a drag does, and lets go
DRAG_TOP = """(function(n){ var t=Array.from(document.querySelectorAll('#stationsGrid .ch-edit-list > .tile')).filter(function(x){ return x.querySelector('.tile-name').textContent===n; })[0];
  t.parentNode.insertBefore(t, t.parentNode.firstElementChild); t.dispatchEvent(new Event('dragend')); })"""


async def run3(p, theme, width):
    T = f'[{theme} {width}]'
    b = await p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
    ctx = await b.new_context(viewport={'width': width, 'height': 860}, device_scale_factor=2, is_mobile=True, has_touch=True, color_scheme=theme, locale='en-US', timezone_id='America/New_York')
    await ctx.add_init_script(MOCK); await ctx.add_init_script(AUTO_NOTICE); await ctx.add_init_script(SEED)
    await ctx.add_init_script("try{ localStorage.setItem('radioPlayerTheme', '%s'); }catch(e){}" % theme)
    pg = await ctx.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e) + ' ' + (e.stack or '')[:300]))
    await pg.route('**/*', route)
    await pg.goto(f'http://127.0.0.1:{PORT}/index.html'); await pg.wait_for_timeout(3000)
    await pg.evaluate("document.querySelector('.mobile-nav-btn[data-nav=video]').click()"); await pg.wait_for_timeout(1500)
    check(await guide_names(pg) == ['The Office (US)', 'MADtv', 'Seinfeld', 'Movies', 'Buzzr', 'Zed News'], f'{T} to begin with: your channels first, as before')

    # Edit: Layout, Your Channels (Order: Manual), Added Channels (Order: A to Z)
    await edit(pg)
    ln = await pg.evaluate(LINES)
    check(ln == ['Layout:*Your Channels First/Integrate Channels', 'Order:A to Z/*Manual', 'Order:*A to Z/Manual'], f'{T} Edit: the layout, then an order for each list {ln}')
    check(await pg.evaluate(HEADS) == ['Your Channels', 'Added Channels'], f'{T} with their headings')
    rows = await pg.evaluate(EDITROWS)
    check(rows[0]['rows'] == ['The Office (US)', 'MADtv', 'Seinfeld', 'Movies'] and rows[0]['drag'] == 4 and rows[0]['grips'] == 4 and rows[1]['rows'] == ['Buzzr', 'Zed News'] and rows[1]['drag'] == 0,
          f'{T} Your Channels drag (Manual), the added ones don’t (A to Z) {rows}')
    await pg.evaluate("window.scrollTo(0,0)"); await pg.wait_for_timeout(200)
    await pg.screenshot(path=f'{SHOTS}/chlayout-split-{theme}-{width}.png')
    # a real tap on a row that drags (Manual) still opens the channel
    await pg.tap('.lc-row[data-live-id="madtv"] .tile-name'); await pg.wait_for_timeout(600)
    op = await pg.evaluate("[document.getElementById('liveChOverlay').classList.contains('open'), document.getElementById('liveChName').placeholder]")
    check(op == [True, 'MADtv'], f'{T} a tap on a row that drags still opens its channel {op}')
    await pg.evaluate("document.getElementById('liveChCloseBtn').click()"); await pg.wait_for_timeout(300)
    # Manual: drag Movies to the top of Your Channels
    await pg.evaluate(DRAG_TOP + "('Movies')"); await pg.wait_for_timeout(400)
    d = await pg.evaluate("JSON.parse(localStorage.getItem('radioPlayerLiveChannels')).map(function(x){ return x.id; })")
    check(d == ['movies', 'office', 'madtv', 'seinfeld'], f'{T} a dragged order is kept {d}')
    # A to Z
    await pick_line(pg, 'chLiveOrderLine', 'az')
    rows = await pg.evaluate(EDITROWS)
    check(rows[0]['rows'] == ['MADtv', 'Movies', 'Seinfeld', 'The Office (US)'] and rows[0]['drag'] == 0, f'{T} Your Channels A to Z {rows[0]}')
    await edit(pg)
    check(await guide_names(pg) == ['MADtv', 'Movies', 'Seinfeld', 'The Office (US)', 'Buzzr', 'Zed News'], f'{T} the guide follows: your channels A to Z, then the added ones')
    # Back to Manual: the dragged order is still there
    await edit(pg)
    await pick_line(pg, 'chLiveOrderLine', 'manual')
    rows = await pg.evaluate(EDITROWS)
    check(rows[0]['rows'] == ['Movies', 'The Office (US)', 'MADtv', 'Seinfeld'], f'{T} back to Manual: the hand order is kept {rows[0]["rows"]}')
    # Added Channels: Manual, Zed News to the top
    await pick_line(pg, 'chOrderLine' if await pg.evaluate("!!document.getElementById('chOrderLine')") else 'x', 'manual') if False else None
    await pg.evaluate("(function(){ var l=document.querySelectorAll('#stationsGrid .ch-sort-line'); l[l.length-1].querySelector('.home-tab[data-opt=manual]').click(); })()"); await pg.wait_for_timeout(400)
    await pg.evaluate(DRAG_TOP + "('Zed News')"); await pg.wait_for_timeout(300)
    await edit(pg)
    check(await guide_names(pg) == ['Movies', 'The Office (US)', 'MADtv', 'Seinfeld', 'Zed News', 'Buzzr'], f'{T} each list keeps its own order in the guide {await guide_names(pg)}')

    # Integrate Channels: one list, A to Z to begin with
    await edit(pg)
    await pick_line(pg, 'chLayoutLine', 'mixed')
    ln = await pg.evaluate(LINES)
    rows = await pg.evaluate(EDITROWS)
    check(ln == ['Layout:Your Channels First/*Integrate Channels', 'Order:*A to Z/Manual'] and await pg.evaluate(HEADS) == [], f'{T} Integrate Channels: one Order, no headings {ln}')
    want = ['Buzzr', 'MADtv', 'Movies', 'Seinfeld', 'The Office (US)', 'Zed News']
    check(len(rows) == 1 and rows[0]['rows'] == want and rows[0]['drag'] == 0, f'{T} one list of everything, A to Z {rows}')
    await pg.evaluate("window.scrollTo(0,0)"); await pg.wait_for_timeout(200)
    await pg.screenshot(path=f'{SHOTS}/chlayout-mixed-{theme}-{width}.png')
    # a channel of yours still opens its editor; an added one still has Rename
    await pg.evaluate("Array.from(document.querySelectorAll('.ch-mix-list .tile')).filter(function(t){ return t.querySelector('.tile-name').textContent==='Seinfeld'; })[0].click()"); await pg.wait_for_timeout(500)
    check(await pg.evaluate("document.getElementById('liveChOverlay').classList.contains('open') && document.getElementById('liveChTitle').textContent==='Edit Channel'"), f'{T} tapping one of yours opens its editor')
    await pg.evaluate("document.getElementById('liveChCloseBtn').click()"); await pg.wait_for_timeout(300)
    await edit(pg)
    check(await guide_names(pg) == want, f'{T} the guide: everything A to Z together {await guide_names(pg)}')
    # Manual: drag Zed News to the top
    await edit(pg)
    await pick_line(pg, 'chMixOrderLine', 'manual')
    rows = await pg.evaluate(EDITROWS)
    check(rows[0]['rows'] == want and rows[0]['drag'] == 6 and rows[0]['grips'] == 6, f'{T} Manual starts from the order showing, every row drags {rows}')
    await pg.evaluate(DRAG_TOP + "('Zed News')"); await pg.wait_for_timeout(400)
    mix = await pg.evaluate("JSON.parse(localStorage.getItem('radioPlayerChannelMix'))")
    check([NAME[u] for u in mix] == ['Zed News'] + want[:-1], f'{T} the dragged order is kept {[NAME[u] for u in mix]}')
    # a favourite leads (Seinfeld)
    await pg.evaluate("(function(){ var t=Array.from(document.querySelectorAll('.ch-mix-list .tile')).filter(function(t){ return t.querySelector('.tile-name').textContent==='Seinfeld'; })[0]; t.querySelector('.row-more-btn').click(); })()"); await pg.wait_for_timeout(300)
    await pg.evaluate("document.getElementById('rowMenuFav').click()"); await pg.wait_for_timeout(400)
    await edit(pg)
    gn = await guide_names(pg)
    check(gn == ['Seinfeld', 'Zed News', 'Buzzr', 'MADtv', 'Movies', 'The Office (US)'], f'{T} the guide: your order, a favourite first {gn}')
    await pg.evaluate("window.scrollTo(0,0)"); await pg.wait_for_timeout(200)
    await pg.screenshot(path=f'{SHOTS}/chlayout-mixed-guide-{theme}-{width}.png')
    # it's kept after a restart
    await pg.reload(); await pg.wait_for_timeout(2500)
    await pg.evaluate("document.querySelector('.mobile-nav-btn[data-nav=video]').click()"); await pg.wait_for_timeout(1200)
    gr = await guide_names(pg)
    check(gr == gn, f'{T} kept after a restart {gr}')
    # the guide under a playing channel follows a change made in Edit
    await tap_now(pg, 'amplify-live:madtv'); await pg.wait_for_timeout(2000)
    gp = await guide_names(pg, '#npCollection .epg')
    check(gp == gn, f'{T} the guide under a playing channel has the same order {gp}')
    await pg.evaluate("document.getElementById('npBackBtn').click()"); await pg.wait_for_timeout(600)
    await edit(pg)
    await pick_line(pg, 'chLayoutLine', 'split')
    np_g = await guide_names(pg, '#npCollection .epg')
    check(np_g[:4] == ['Seinfeld', 'Movies', 'The Office (US)', 'MADtv'] and np_g[4:] == ['Zed News', 'Buzzr'], f'{T} back to Your Channels First: their own orders again, and the playing channel’s guide follows {np_g}')
    await edit(pg)

    # ---- casting
    await pg.evaluate("window.__emit('cast', { supported: true, available: true, connected: true, device: 'Family Room TV', active: false })"); await pg.wait_for_timeout(300)
    await pg.evaluate("window.__loads=[]")
    items = lineup('10')
    i_now, s_now, x_now = on_at(items, time.time())
    await tap_now(pg, 'amplify-live:office'); await pg.wait_for_timeout(2500)
    la = await pg.evaluate("window.__loads[window.__loads.length-1] || {}")
    off = time.time() - s_now
    check('/video/:/transcode/universal/start.m3u8' in la.get('url', '') and ('%2Flibrary%2Fmetadata%2F' + x_now[0]) in la.get('url', '') and abs(la.get('start', 0) - off) < 6
          and la.get('castVideo') is True and la.get('castVod') is True,
          f'{T} casting: a Plex MKV goes through Plex’s conversion, from the schedule’s place, as a video with a length {la.get("url", "")[:90]} {la.get("start")} ~{off:.0f}')
    await pg.evaluate("window.__loads=[]")
    await pg.evaluate("document.getElementById('npBackBtn').click()"); await pg.wait_for_timeout(500)
    await tap_now(pg, 'amplify-live:movies'); await pg.wait_for_timeout(2500)
    la = await pg.evaluate("window.__loads[window.__loads.length-1] || {}")
    check(la.get('url', '').startswith('content://tree/movies/') and la.get('engine') == 'vlc' and la.get('start', 0) > 3 and la.get('castVideo') is True and la.get('castVod') is True,
          f'{T} casting: a phone movie goes as it is (the phone serves it), from the schedule’s place {la}')
    # A Chromecast picked while a Plex MKV channel plays on the phone: it tunes in again, converted
    await pg.evaluate("window.__emit('cast', { supported: true, available: true, connected: false, device: '', active: false })"); await pg.wait_for_timeout(300)
    await pg.evaluate("document.getElementById('npBackBtn').click()"); await pg.wait_for_timeout(500)
    await pg.evaluate("window.__loads=[]")
    await tap_now(pg, 'amplify-live:office'); await pg.wait_for_timeout(2500)
    la = await pg.evaluate("window.__loads[window.__loads.length-1] || {}")
    check('/library/parts/' in la.get('url', ''), f'{T} not casting: the original file plays on the phone {la.get("url", "")[:60]}')
    await pg.evaluate("window.__loads=[]")
    await pg.evaluate("window.__emit('cast', { supported: true, available: true, connected: true, device: 'Family Room TV', active: false })"); await pg.wait_for_timeout(2500)
    la = await pg.evaluate("window.__loads[window.__loads.length-1] || {}")
    i_now, s_now, x_now = on_at(items, time.time())
    check('/video/:/transcode/universal/start.m3u8' in la.get('url', '') and abs(la.get('start', 0) - (time.time() - s_now)) < 6,
          f'{T} a Chromecast picked mid-episode: it tunes in again through the conversion {la.get("url", "")[:70]} {la.get("start")}')
    np = await pg.evaluate(NP)
    check(np['open'] and np['name'] == 'The Office (US)', f'{T} Now Playing stays on the channel')
    check(not errs, f'{T} no page errors {errs[:3]}')
    await b.close()


async def main():
    async with async_playwright() as p:
        await run3(p, 'dark', 412)
        await run3(p, 'light', 360)
    print('ALL PASSED' if not fails else f'FAILED {len(fails)}: {fails}')

asyncio.run(main())
