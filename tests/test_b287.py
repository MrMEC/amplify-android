"""Build 287 (Mark: don't group): your channels' blocks follow each video's real times again; build 286's rows stay. (Was build 286: 1) roomier guide rows: 5 rows visible on a phone (was 6); 2) on your own channels
no block is narrower than half an hour: short back-to-back videos share one block ("2 episodes" on a
one-show channel, "The Office (US) / Seinfeld" or "Seinfeld · 2 episodes" on a mix), with their codes
underneath; a block still plays (the one on now) or opens its details.
Run: python3 tests/test_b286.py (screenshots in /tmp/claude-0/t/shots)"""
import sys as _nsys, os as _nos; _nsys.path.insert(0, _nos.path.dirname(_nos.path.abspath(__file__)))
src = open(_nos.path.join(_nos.path.dirname(_nos.path.abspath(__file__)), 'test_live_channels_editor.py')).read()
src = src[:src.index('async def run2(')].replace('PORT = 8863', 'PORT = 8886').replace("srv-livech2'", "srv-b287'")
exec(src)
import json, sys
DEFS = [{'id': 'office', 'name': '', 'src': {'kind': 'pick', 'shows': ['The Office'], 'movies': []}, 'order': 'sequence'},
        {'id': 'madtv', 'name': '', 'src': {'kind': 'pick', 'shows': ['MadTV'], 'movies': []}, 'order': 'sequence'},
        {'id': 'seinfeld', 'name': '', 'src': {'kind': 'pick', 'shows': ['Seinfeld'], 'movies': []}, 'order': 'sequence'},
        {'id': 'mix', 'name': 'Comedy Mix', 'src': {'kind': 'pick', 'shows': ['The Office', 'Seinfeld'], 'movies': []}, 'order': 'shuffle'},
        {'id': 'movies', 'name': 'Movies', 'src': {'kind': 'movies', 'from': 'phone'}, 'order': 'shuffle'}]
ROWS = """Array.from(document.querySelectorAll('#stationsGrid .epg-row')).map(r => ({ ch: r.querySelector('.epg-ch').getAttribute('aria-label'), url: r.dataset.chUrl,
  blocks: Array.from(r.querySelectorAll('.epg-prog')).map(b => ({ w: Math.round(b.getBoundingClientRect().width), t: (b.querySelector('.epg-t')||{}).textContent, s: (b.querySelector('.epg-s')||{}).textContent, now: b.classList.contains('now'), btn: b.tagName === 'BUTTON' })) }))"""
async def main():
    async with async_playwright() as p:
        for width, height in ((390, 844), (360, 780)):
            T = f'[{width}x{height}]'
            b = await p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
            ctx = await b.new_context(viewport={'width': width, 'height': height}, device_scale_factor=3, is_mobile=True, has_touch=True, color_scheme='dark', timezone_id='America/New_York')
            await ctx.add_init_script(MOCK); await ctx.add_init_script(AUTO_NOTICE); await ctx.add_init_script(SEED)
            await ctx.add_init_script("if(!localStorage.getItem('__d')){ localStorage.setItem('__d','1'); localStorage.setItem('radioPlayerLiveChannels', %s); }" % json.dumps(json.dumps(DEFS)))
            pg = await ctx.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
            await pg.route('**/*', route)
            await pg.goto(f'http://127.0.0.1:{PORT}/index.html'); await pg.wait_for_timeout(2500)
            await pg.evaluate("document.querySelector('.mobile-nav-btn[data-nav=video]').click()"); await pg.wait_for_timeout(1500)
            # 1) rows that fit between the time bar and the mini player
            vis = await pg.evaluate("""(()=>{ const top = document.querySelector('#stationsGrid .epg-head').getBoundingClientRect().bottom, bot = document.getElementById('playerBar').getBoundingClientRect().top;
              const rows = Array.from(document.querySelectorAll('#stationsGrid .epg-row')); const h = rows[0].getBoundingClientRect().height;
              return { h, pitch: Math.round(rows[1].getBoundingClientRect().top - rows[0].getBoundingClientRect().top), fit: (bot - top) / (rows[1].getBoundingClientRect().top - rows[0].getBoundingClientRect().top) }; })()""")
            print(T, vis)
            check(vis['h'] == 62 and vis['pitch'] == 66 and 6 * 53 / vis['pitch'] < 5, f'{T} rows 25% taller (66px apart, was 53): where 6 fitted, under 5 now {vis}')
            rows = await pg.evaluate(ROWS)
            byid = {r['url'].split(':')[1]: r for r in rows if r['url'].startswith('amplify-live:')}
            o = byid['office']['blocks']; print(T, json.dumps(o[:5]))
            check(o and not any('episodes' in (x['t'] or '') or ' / ' in (x['t'] or '') for r in byid.values() for x in r['blocks']), f'{T} no grouped blocks on any of your channels')
            mid = o[1:-1]
            check(mid and all(x['t'].startswith('Office S') and abs(x['w'] - (22 / 30 * 124 - 4)) <= 2 for x in mid), f'{T} The Office: one block per 22-minute episode, as wide as its real length {mid[:3]}')
            mx = byid['mix']['blocks'][1:-1]
            check(mx and all(abs(x['w'] - (22 / 30 * 124 - 4)) <= 2 or abs(x['w'] - (23 / 30 * 124 - 4)) <= 2 for x in mx), f'{T} the mix: one block per episode {mx[:3]}')
            check(sum(1 for x in o if x['now']) == 1 and all(x['btn'] for x in o), f'{T} one block on now; blocks still tappable')
            await pg.screenshot(path=f'{SHOTS}/b287-guide-{width}.png')
            # the block on now plays the channel
            await pg.evaluate("Array.from(document.querySelectorAll('#stationsGrid .epg-row')).find(r => r.dataset.chUrl === 'amplify-live:office').querySelector('.epg-prog.now').click()"); await pg.wait_for_timeout(1500)
            cur = await pg.evaluate("window.__cur || (document.getElementById('playerName')||{}).textContent")
            check(bool(cur), f'{T} tapping the block on now plays the channel ({cur})')
            check(not errs, f'{T} no page errors {errs[:2]}')
            await b.close()
    print('ALL PASSED' if not fails else f'{fails} FAILED')
    sys.exit(1 if fails else 0)
asyncio.run(main())
