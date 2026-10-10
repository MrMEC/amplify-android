"""Build 189: the Favorites page's Sort dropdown (A to Z / Manual, newest first / Manual, newest
last), kept across restarts; and favourite channels first (A to Z) under a "Favorites" heading,
with the rest under "My Channels", on Watch > Live TV and in the list under a playing channel.
Run: python3 tests/test_fav_order.py (screenshots in /tmp/claude-0/t/shots)"""
import asyncio, os, re
HERE = os.path.dirname(os.path.abspath(__file__))
src = open(os.path.join(HERE, 'test_video_channels.py')).read()
head = src[:src.index('async def rows(pg)')]
head = head.replace("'/tmp/claude-0/t/srv-ch'", "'/tmp/claude-0/t/srv-favord'").replace('8777', '8819')
exec(head)
from playwright.async_api import async_playwright
# A hook into the served copy: add/remove a favourite and read the stored order.
html = open(os.path.join(ROOT, 'index.html')).read()
html = html.replace('  function toggleFavorite(station){',
    "  window.__fo = { toggle: function(s){ toggleFavorite(s); }, keys: function(){ return favorites.map(favKey); } };\n  function toggleFavorite(station){", 1)
open(os.path.join(ROOT, 'index.html'), 'w').write(html)

def ch(i, name, cats=None):
    return {'id': 'link:%d' % i, 'name': name, 'url': 'http://ch%d.example/l.m3u8' % i, 'logo': '', 'country': '',
            'cats': cats or [], 'catNames': [c.title() for c in (cats or [])], 'src': 'link', 'addedAt': i}
CHS = [ch(1, 'Zed TV', ['news']), ch(2, 'Beach TV', ['news']), ch(3, 'Movies 24'), ch(4, 'Alpha TV'), ch(5, 'Kitchen TV'), ch(6, 'Mango TV')]
def chst(c):
    return {'name': c['name'], 'urlToResolve': c['url'], 'favicon': '', 'tags': ','.join(c['cats']), 'country': '', 'codec': '', 'bitrate': '',
            'stationuuid': None, 'videoChannel': True, 'channel': {'id': c['id'], 'name': c['name'], 'url': c['url'], 'logo': '', 'country': '', 'cats': c['cats'], 'src': 'link'}}
def stn(i, name):
    return {'name': name, 'urlToResolve': 'https://s%d.example/live' % i, 'url_resolved': 'https://s%d.example/live' % i, 'stationuuid': 'u%d' % i, 'favicon': '', 'tags': 'jazz', 'country': 'US'}
# Stored (manual) order: added in this order.
FAVS = [stn(1, 'Kiss FM'), chst(CHS[0]), stn(2, 'Bravo Radio'), chst(CHS[4]), stn(3, 'Echo FM')]
NEW = stn(4, 'Delta FM')

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
        ctx = await b.new_context(viewport={'width': 412, 'height': 900}, device_scale_factor=2, is_mobile=True, has_touch=True, color_scheme='dark', locale='en-US')
        await ctx.add_init_script(MOCK)
        await ctx.add_init_script("if(!localStorage.getItem('__seeded')){ localStorage.setItem('__seeded','1'); localStorage.setItem('radioPlayerVideoChannels', %s); localStorage.setItem('radioPlayerFavorites', %s); }"
                                  % (repr(json.dumps(CHS)), repr(json.dumps(FAVS))))
        pg = await ctx.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.route('**/*', route)
        await pg.goto('http://127.0.0.1:8819/index.html'); await pg.wait_for_timeout(2500)

        async def fav_page():
            await pg.evaluate("document.querySelector('.mobile-nav-btn[data-nav=home]').click()"); await pg.wait_for_timeout(600)
            await pg.evaluate("document.getElementById('favoritesHeading').click()"); await pg.wait_for_timeout(800)
        async def names(sel='#stationsGrid .row-item'):
            return await pg.evaluate("(sel)=>Array.prototype.map.call(document.querySelectorAll(sel), function(r){ var n=r.querySelector('.row-name'); return (n||r).textContent.trim(); })", sel)
        async def pick(v):
            await pg.evaluate("document.querySelector('.fav-order-btn').click()"); await pg.wait_for_timeout(300)
            await pg.evaluate("(v)=>document.querySelector('.fav-order-menu [data-order=\"'+v+'\"]').click()", v); await pg.wait_for_timeout(500)

        await fav_page()
        bar = await pg.evaluate("(()=>{ var b=document.querySelector('#stationsGrid > .fav-order-bar'); if(!b) return null; var r=b.getBoundingClientRect(); return {first: b===document.getElementById('stationsGrid').firstElementChild, text:b.textContent.trim(), w:r.width, x:r.left}; })()")
        check(bar and bar['first'] and 'Manual, newest last' in bar['text'], f'Favorites page starts with the Sort dropdown, on Manual, newest last {bar}')
        n0 = await names()
        check(n0 == ['Kiss FM', 'Zed TV', 'Bravo Radio', 'Kitchen TV', 'Echo FM'], f'newest last keeps the stored order {n0}')
        await pg.evaluate("document.querySelector('.fav-order-btn').click()"); await pg.wait_for_timeout(400)
        menu = await pg.evaluate("(()=>{ var m=document.querySelector('.fav-order-menu'); if(!m) return null; var r=m.getBoundingClientRect(), br=document.querySelector('.fav-order-btn').getBoundingClientRect();"
                                 " return {items:Array.prototype.map.call(m.querySelectorAll('.np-menu-item'),function(i){return [i.dataset.order,i.textContent.trim(),i.getAttribute('aria-checked')];}), below:r.top>=br.bottom, inside:r.right<=innerWidth}; })()")
        await pg.screenshot(path=f'{SHOTS}/favord-menu.png')
        check(menu and [i[1] for i in menu['items']] == ['A to Z', 'Manual, newest first', 'Manual, newest last'] and menu['items'][2][2] == 'true' and menu['below'] and menu['inside'],
              f'the dropdown offers the three choices, current one ticked, under the button on screen {menu}')
        await pg.evaluate("document.body.click()"); await pg.wait_for_timeout(300)
        check(not await pg.evaluate("!!document.querySelector('.fav-order-menu')"), 'a tap elsewhere closes it')

        await pick('az')
        n1 = await names()
        check(n1 == ['Bravo Radio', 'Echo FM', 'Kiss FM', 'Kitchen TV', 'Zed TV'], f'A to Z sorts the list {n1}')
        await pg.screenshot(path=f'{SHOTS}/favord-az.png')
        home = await pg.evaluate("Array.prototype.map.call(document.querySelectorAll('#favoritesGrid .tile .tile-name'), function(e){ return e.textContent.trim(); })")
        check(home[:5] == ['Bravo Radio', 'Echo FM', 'Kiss FM', 'Kitchen TV', 'Zed TV'], f'the Home Favorites row follows A to Z {home}')
        await pg.evaluate("document.getElementById('favPageEditBtn').click()"); await pg.wait_for_timeout(500)
        ed = await pg.evaluate("[document.querySelectorAll('#stationsGrid .fav-edit-row').length, document.querySelectorAll('#stationsGrid .row-drag-handle').length, document.querySelectorAll('#stationsGrid .fav-remove-btn').length, !!document.querySelector('#stationsGrid .fav-order-bar')]")
        check(ed == [5, 0, 5, True], f'Edit in A to Z: remove buttons, no grips (nothing to drag), dropdown still there {ed}')
        await pg.evaluate("document.getElementById('favPageEditBtn').click()"); await pg.wait_for_timeout(400)
        keys = await pg.evaluate("window.__fo.keys()")
        check(keys == [('u1'), CHS[0]['url'], 'u2', CHS[4]['url'], 'u3'], f'A to Z (and Edit/Done in it) leaves the stored manual order alone {keys}')

        # kept across a restart
        await pg.reload(); await pg.wait_for_timeout(2500)
        await fav_page()
        n2 = await names(); t2 = await pg.evaluate("document.querySelector('.fav-order-btn').textContent.trim()")
        check(t2 == 'A to Z' and n2 == n1, f'A to Z is kept after a restart {t2} {n2}')

        await pick('newest')
        n3 = await names()
        check(n3 == ['Echo FM', 'Kitchen TV', 'Bravo Radio', 'Zed TV', 'Kiss FM'], f'Manual, newest first shows the newest favourite first {n3}')
        await pg.evaluate("(s)=>window.__fo.toggle(s)", NEW); await pg.wait_for_timeout(500)
        await fav_page()
        n4 = await names()
        check(n4[0] == 'Delta FM' and n4[1:] == n3, f'a new favourite goes first {n4}')
        await pg.evaluate("document.getElementById('favPageEditBtn').click()"); await pg.wait_for_timeout(500)
        g = await pg.evaluate("document.querySelectorAll('#stationsGrid .row-drag-handle').length")
        check(g == 6, f'Edit in Manual has grips to reorder ({g})')
        await pg.screenshot(path=f'{SHOTS}/favord-newest-edit.png')
        # finger-drag the last row to the top
        hs = await pg.evaluate("Array.prototype.map.call(document.querySelectorAll('#stationsGrid .row-drag-handle'), function(h){ var r=h.getBoundingClientRect(); return [r.left+r.width/2, r.top+r.height/2]; })")
        src_, dst = hs[-1], hs[0]
        await pg.evaluate("""([sx,sy,dx,dy])=>{ var h=document.querySelectorAll('#stationsGrid .row-drag-handle'); var el=h[h.length-1];
          function ev(t,x,y){ el.dispatchEvent(new PointerEvent(t,{bubbles:true,cancelable:true,pointerId:7,pointerType:'touch',clientX:x,clientY:y,isPrimary:true})); }
          ev('pointerdown',sx,sy); for(var i=1;i<=12;i++) ev('pointermove',sx,sy+(dy-8-sy)*i/12); ev('pointerup',sx,dy-8); }""", [src_[0], src_[1], dst[0], dst[1]])
        await pg.wait_for_timeout(600)
        await pg.evaluate("document.getElementById('favPageEditBtn').click()"); await pg.wait_for_timeout(500)
        n5 = await names()
        check(n5[0] == 'Kiss FM' and len(n5) == 6, f'dragging in Manual, newest first reorders the list {n5}')
        await pg.reload(); await pg.wait_for_timeout(2500)
        await fav_page()
        n6 = await names(); t6 = await pg.evaluate("document.querySelector('.fav-order-btn').textContent.trim()")
        check(t6 == 'Manual, newest first' and n6 == n5, f'the choice and the hand-made order are kept after a restart {t6} {n6}')

        await pick('oldest')
        n7 = await names()
        check(n7 == list(reversed(n6)), f'Manual, newest last mirrors it (newest at the end) {n7}')
        await pg.evaluate("(s)=>window.__fo.toggle(s)", stn(5, 'Foxtrot FM')); await pg.wait_for_timeout(400)
        await fav_page()
        n8 = await names()
        check(n8[-1] == 'Foxtrot FM' and n8[:-1] == n7, f'and a new favourite goes last {n8}')
        await pg.screenshot(path=f'{SHOTS}/favord-oldest.png')

        # ---- Live TV: favourite channels first
        await pg.evaluate("document.querySelector('.mobile-nav-btn[data-nav=video]').click()"); await pg.wait_for_timeout(800)
        await pg.evaluate("(()=>{ var t=document.querySelector('#stationsGrid .video-tabs [data-tab=channels]') || Array.prototype.find.call(document.querySelectorAll('#stationsGrid .home-tab'), function(b){ return /Live TV/.test(b.textContent); }); if(t) t.click(); })()"); await pg.wait_for_timeout(700)
        LIST = """(()=>Array.prototype.filter.call(document.querySelectorAll('#stationsGrid > *'), function(e){ return e.classList.contains('ch-group-head') || e.classList.contains('grid-section-label') || e.classList.contains('tile-row'); })
          .map(function(e){ return e.classList.contains('tile-row') ? (e.querySelector('.tile-name')||e).textContent.trim() : '#' + e.textContent.trim(); }))()"""
        lt = await pg.evaluate(LIST)
        check(lt[:4] == ['#Favorites', 'Kitchen TV', 'Zed TV', '#My Channels'] and 'Zed TV' not in lt[4:] and 'Kitchen TV' not in lt[4:] and all(x in lt for x in ['Alpha TV', 'Beach TV', 'Mango TV', 'Movies 24']),
              f'Live TV: Favorites (A to Z) first, then My Channels with the rest {lt}')
        await pg.screenshot(path=f'{SHOTS}/favord-livetv.png')
        lsz = await pg.evaluate("Array.prototype.map.call(document.querySelectorAll('#stationsGrid > .ch-group-head'), function(e){ var c=getComputedStyle(e); return [c.fontSize, c.fontWeight, c.color]; })")
        # ---- the list under a playing channel
        await pg.evaluate("Array.prototype.find.call(document.querySelectorAll('#stationsGrid .tile-row'), function(r){ return /Alpha TV/.test(r.textContent); }).click()"); await pg.wait_for_timeout(1500)
        cur = await pg.evaluate("window.__cur")
        await pg.evaluate("(id)=>window.__emit('video',{id:id,hasVideo:true,width:1280,height:720})", cur); await pg.wait_for_timeout(900)
        if await pg.evaluate("document.body.classList.contains('np-video-full')"):
            await pg.evaluate("window.__emit('videotap',{})"); await pg.wait_for_timeout(600)
        np = await pg.evaluate("""(()=>{ var out=[document.getElementById('npCollectionHeading').textContent.trim()];
          Array.prototype.forEach.call(document.querySelectorAll('#npCollectionGrid > *'), function(e){ out.push(e.classList.contains('ch-group-head') ? '#' + e.textContent.trim() : (e.querySelector('.tile-name')||e).textContent.trim()); });
          var h=document.getElementById('npCollectionHeading'), s=document.querySelector('#npCollectionGrid > .ch-group-head'); var hc=getComputedStyle(h), sc=s?getComputedStyle(s):null;
          return {list:out, head:[hc.fontSize, hc.fontWeight, hc.color], sub:sc?[sc.fontSize, sc.fontWeight, sc.color]:null}; })()""")
        check(np['list'][:4] == ['Favorites', 'Kitchen TV', 'Zed TV', '#My Channels'] and len(np['list']) == 1 + 2 + 1 + 4,
              f'under a playing channel: Favorites (A to Z), then My Channels with the rest {np["list"]}')
        check(np['sub'] == np['head'], f'the My Channels heading matches the list heading {np["head"]} {np["sub"]}')
        check(all(x[0] == np['head'][0] and x[1] == np['head'][1] for x in lsz) and len(lsz) == 2, f'Live TV headings are the same size {lsz} vs {np["head"]}')
        dim = await pg.evaluate("(()=>{ var d=document.createElement('div'); d.style.color='var(--text-dim)'; document.body.appendChild(d); var c=getComputedStyle(d).color; d.remove(); return c; })()")
        check(all(x[2] == dim for x in lsz), f'Live TV headings use the default grey heading colour {lsz} vs {dim}')
        await pg.evaluate("document.getElementById('npCollectionGrid').scrollIntoView({block:'start'})"); await pg.wait_for_timeout(300)
        await pg.screenshot(path=f'{SHOTS}/favord-np.png')
        # un-favourite both channels: no headings (back to the plain My Channels list)
        for c in [CHS[0], CHS[4]]:
            await pg.evaluate("(s)=>window.__fo.toggle(s)", chst(c)); await pg.wait_for_timeout(300)
        await pg.wait_for_timeout(400)
        np2 = await pg.evaluate("[document.getElementById('npCollectionHeading').textContent.trim(), document.querySelectorAll('#npCollectionGrid > .ch-group-head').length, document.querySelectorAll('#npCollectionGrid .tile-row').length]")
        check(np2 == ['My Channels', 0, 6], f'with no favourite channels the list is My Channels alone, updated at once {np2}')
        await pg.evaluate("document.querySelector('#npMinimize, .np-float .np-back, #npBackBtn') && document.querySelector('#npMinimize, .np-float .np-back, #npBackBtn').click()"); await pg.wait_for_timeout(800)
        await pg.evaluate("document.querySelector('.mobile-nav-btn[data-nav=video]').click()"); await pg.wait_for_timeout(800)
        h3 = await pg.evaluate("document.querySelectorAll('#stationsGrid > .ch-group-head').length")
        check(h3 == 0, f'and Live TV shows no Favorites / My Channels headings ({h3})')
        check(not errs, f'no page errors {errs[:3]}')
        await b.close()
    print('ALL PASSED' if not fails else f'FAILED {fails}')
asyncio.run(main())
