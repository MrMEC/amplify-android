"""Build 144: a Shuffle button at the top right of the queue panel puts everything coming up in a
new random order (Up Next among itself, then the rest of the list among itself); the current
track stays; Clear moves to the Up Next heading.
Run: python3 tests/test_queue_shuffle.py (screenshots in /tmp/claude-0/t/shots)"""
import asyncio, os
HERE = os.path.dirname(os.path.abspath(__file__))
src = open(os.path.join(HERE, 'test_station_skip.py')).read()
head = src[:src.index('async def main()')]
head = head.replace("'/tmp/claude-0/t/srv_skip'", "'/tmp/claude-0/t/srv_qsh'").replace('PORT = 8794', 'PORT = 8810')
UPJS = '" upnext: function(n){ upNext.push(window.__t.T(n)); onUpNextChanged(); }, openQ: function(){ openQueuePanel(); }, closeQ: function(){ closeQueuePanel(); }, trim: function(){ playQueue.splice(queueIndex + 2); onQueueContextChanged(); }, ui: function(b){ setPlayingUI(b); }, up: function(){ return { up: upNext.map(function(t){ return t.name; }), rest: playQueue.slice(queueRestStart()).map(function(t){ return t.name; }), cur: currentStation && currentStation.name, rows: Array.from(document.querySelectorAll(\'#queueUpList .queue-row-title, #queueCtxList .queue-row-title\')).map(function(e){ return e.textContent; }) }; }, skip: function(){'
head = head.replace('" skip: function(){', UPJS)
assert 'openQ' in head
exec(head)
from playwright.async_api import async_playwright

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
            if len(await pg.evaluate('__t.tracks()')) >= 3: break
        await pg.evaluate('__t.setup()')
        await pg.evaluate("__t.openPl('pl_mix')"); await pg.wait_for_timeout(600)
        await pg.evaluate(CLICK, 'Radio A'); await pg.wait_for_timeout(700)
        await pg.evaluate('__t.openNp()'); await pg.wait_for_timeout(900)
        await pg.evaluate('__t.ui(true)')

        # one thing coming: no shuffle
        await pg.evaluate("__t.trim()"); await pg.evaluate('__t.openQ()'); await pg.wait_for_timeout(500)
        hid = await pg.evaluate("document.getElementById('queueShuffleBtn').hidden")
        check(hid, 'with only one track coming there is nothing to shuffle: the button is hidden')
        await pg.evaluate("__t.closeQ()")
        await pg.evaluate("__t.openPl('pl_mix')"); await pg.wait_for_timeout(600)
        await pg.evaluate(CLICK, 'Radio A'); await pg.wait_for_timeout(700)
        await pg.evaluate('__t.openNp()'); await pg.wait_for_timeout(700)
        await pg.evaluate("__t.upnext('Song 2'); __t.upnext('Song 3')")
        await pg.evaluate('__t.openQ()'); await pg.wait_for_timeout(600)
        q0 = await pg.evaluate('__t.up()')
        print(q0)
        check(q0['up'] == ['Song 2', 'Song 3'] and q0['rest'] == ['Song 1', 'Radio B', 'Radio C'] and q0['rows'] == q0['up'] + q0['rest'], f'before: Up Next then the rest of the playlist {q0}')
        geo = await pg.evaluate("""(()=>{ var s = document.getElementById('queueShuffleBtn').getBoundingClientRect(), t = document.querySelector('.queue-title').getBoundingClientRect(),
          c = document.getElementById('queueClearBtn'), cr = c.getBoundingClientRect(), h = document.querySelector('.queue-heading-row').getBoundingClientRect();
          return { sR: s.right, sTop: s.top, tTop: t.top, W: innerWidth, hidden: document.getElementById('queueShuffleBtn').hidden,
            color: getComputedStyle(document.getElementById('queueShuffleBtn')).color, vivid: getComputedStyle(document.body).getPropertyValue('--np-vivid').trim(),
            clearInRow: c.closest('.queue-heading-row') !== null, clearVis: getComputedStyle(c).visibility, cTop: cr.top, cBottom: cr.bottom, hTop: h.top, hBottom: h.bottom, cR: cr.right }; })()""")
        print(geo)
        check(not geo['hidden'] and geo['W'] - geo['sR'] <= 20 and abs(geo['sTop'] - geo['tTop']) < 20, f'Shuffle sits at the top right of the panel {geo}')
        check(geo['clearInRow'] and geo['clearVis'] == 'visible' and geo['cR'] > geo['W'] - 40, f'Clear sits at the right end of the Up Next heading {geo}')
        rgb = await pg.evaluate("(function(){ var d=document.createElement('div'); d.style.color=getComputedStyle(document.body).getPropertyValue('--np-vivid'); document.body.appendChild(d); var c=getComputedStyle(d).color; d.remove(); return c; })()")
        check(geo['color'] == rgb, f"Shuffle wears the artwork's colour {geo['color']} vs {rgb}")
        await pg.screenshot(path=f'{shots}/qshuffle-before.png')

        seen = set()
        for i in range(6):
            await pg.click('#queueShuffleBtn')
            if i == 0:
                await pg.wait_for_timeout(120)
                anim = await pg.evaluate("document.getElementById('queuePanel').classList.contains('shuffling') && document.querySelectorAll('#queueUpList .queue-row, #queueCtxList .queue-row')[1].getAnimations().length > 0")
                check(anim, 'the new order animates in')
                await pg.screenshot(path=f'{shots}/qshuffle-anim.png')
                await pg.wait_for_timeout(900)
            else:
                await pg.wait_for_timeout(150)
            q = await pg.evaluate('__t.up()')
            check(sorted(q['up']) == ['Song 2', 'Song 3'] and sorted(q['rest']) == ['Radio B', 'Radio C', 'Song 1'] and q['cur'] == 'Radio A', f'shuffle {i}: same tracks, Up Next still first, the current one untouched {q}')
            check(q['rows'] == q['up'] + q['rest'], f'shuffle {i}: the panel shows the new order {q["rows"]}')
            check(q['up'] + q['rest'] != prev if i else q['up'] + q['rest'] != q0['up'] + q0['rest'], f'shuffle {i}: the order changed')
            prev = q['up'] + q['rest']
            seen.add(tuple(q['rest']))
        check(len(seen) >= 2, f'shuffles are random {seen}')
        saved = await pg.evaluate("JSON.parse(localStorage.getItem('amplifyUpNext') || '[]').map(function(t){ return t.name; })")
        check(saved == q['up'], f'the shuffled Up Next is saved {saved}')
        await pg.wait_for_timeout(900)
        await pg.screenshot(path=f'{shots}/qshuffle-after.png')
        # what plays next follows the new order
        await pg.evaluate("__t.closeQ()")
        first = q['up'][0]
        await pg.evaluate("window.__amplifyPlayUpcoming(1)"); await pg.wait_for_timeout(600)
        cur = (await pg.evaluate('__t.up()'))['cur']
        check(cur == first, f'next up plays the first of the new order ({cur} vs {first})')
        check(not errs, f'no page errors {errs[:3]}')
        await b.close()
    print('ALL PASSED' if not fails else f'FAILED {fails}')

asyncio.run(main())
