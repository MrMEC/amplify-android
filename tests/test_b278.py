"""Build 278 (Mark: covers missing on Favorites "80's 80's", "Positively Radio", "Relaxing Calm"):
those are custom stations. A backup import gives each custom station / playlist a new id here and
moves its cover to it, but the favourites kept the old ids, so they pointed at nothing (placeholder,
and "no longer exists" when played). Now they are linked again at start-up (by name) and an import
relinks them through its id map.
A) the phone's state: favourites with stale ids, the custom stations under new ids -> covers show.
B) importing Mark's own backup into a fresh app -> every favourite custom station shows its cover.
Run: python3 tests/test_b278.py [backup.json] (screenshots in /tmp/claude-0/t/shots)"""
import sys as _nsys, os as _nos; _nsys.path.insert(0, _nos.path.dirname(_nos.path.abspath(__file__))); from notice_auto import AUTO_NOTICE
import asyncio, os, json, sys, io
from urllib.parse import urlparse
HERE = os.path.dirname(os.path.abspath(__file__))
src = open(os.path.join(HERE, 'test_video_library.py')).read()
head = src[:src.index('async def names(pg, sel)')]
head = head.replace('8780', '8877').replace("'/tmp/claude-0/t/srv-vlib'", "'/tmp/claude-0/t/srv-b278'")
exec(head)
from playwright.async_api import async_playwright
from PIL import Image, ImageDraw

def png(color):
    im = Image.new('RGB', (240, 240), color); d = ImageDraw.Draw(im); d.ellipse((60, 60, 180, 180), fill='white')
    b = io.BytesIO(); im.save(b, 'PNG'); return b.getvalue()
COVERS = {'kDP3': png('#1e6fd9'), 'r_tf': png('#2a9d4b'), 'qUTn': png('#e07b00'), 'pick': png('#7b2ad9')}
img_hits = []
async def route2(r):
    u = urlparse(r.request.url)
    if u.hostname in ('play-lh.googleusercontent.com', 'pickasso.spotifycdn.com'):
        key = (u.path.strip('/').split('/')[-1] if u.hostname == 'pickasso.spotifycdn.com' else u.path.strip('/'))[:4]
        img_hits.append(u.path[:12])
        body = COVERS.get(key) or COVERS['pick']
        return await r.fulfill(status=200, content_type='image/png', body=body)
    if r.request.resource_type == 'image' and u.hostname not in ('127.0.0.1', 'localhost'):
        return await r.fulfill(status=200, content_type='image/png', body=COVERS['pick'])
    return await route(r)

CS = [('cs_new80s', "80's 80's", '80s80s', 'https://play-lh.googleusercontent.com/kDP3Uwmf-D4OO78XGdvVOlA9rLd4GUymlQ49u17wwqGNSsBSz_jQCfY3NRxMUzMbqIBtBhOacsQgypxQp5253mw'),
      ('cs_newcalm', 'Relaxing Calm', 'calm', 'https://play-lh.googleusercontent.com/r_tfrFr1rGSG1vEYtf9IR-OcmnuI0hoJrAqcnhEaNvdKViEucJBYm0CNmr_0HStuWebzd7zLh2vZ7ZTi4ssx5Bk'),
      ('cs_newpos', 'Positively Radio', 'Positively', 'https://play-lh.googleusercontent.com/qUTnoHUOoC8lfcpOnGGDoSzVfcaCRwurFaElP64AEdxktHi2HodJ9Q3liPUrdqEUvBb5gFK1pK3PMAK-qSm6rA=w240-h480-rw'),
      ('cs_muh2uc1ss35s86', 'Artist Stations', 'exclusively', 'https://pickasso.spotifycdn.com/image/ab67c0de0000deef/dt/v1/img/radio/artist/5XyhuMZZgQttOtYlDKyBJb/en')]
OLD = {"80's 80's": 'cs_muh2uc1t3fgipr', 'Relaxing Calm': 'cs_muh2uc1t56sjl9', 'Positively Radio': 'cs_muhsxldf6ovj5c', 'Artist Stations': 'cs_muh2uc1ss35s86'}
SEARCHES = [{'id': i, 'label': l, 'query': q} for i, l, q, _ in CS]
ART = {'foryouart:' + i: u for i, _, _, u in CS}
# the stale copy of 80's 80's is also there under its new id (an import added it as well)
FAVS = [{'type': 'customStation', 'searchId': OLD[l], 'name': l, 'stationuuid': 'customstation:' + OLD[l]} for _, l, _, _ in CS] \
     + [{'type': 'customStation', 'searchId': 'cs_new80s', 'name': "80's 80's", 'stationuuid': 'customstation:cs_new80s'},
        {'type': 'customStation', 'searchId': 'cs_gone', 'name': 'Deleted Station', 'stationuuid': 'customstation:cs_gone'}]

CARDS = """Array.from(document.querySelectorAll('#favoritesGrid .fav-card')).map(c => ({ name: c.querySelector('.tile-name').textContent,
  img: !!c.querySelector('.tile-art img'), ok: !!(c.querySelector('.tile-art img') && c.querySelector('.tile-art img').naturalWidth > 0), key: c.dataset.key }))"""

async def page(p, init):
    b = await p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
    ctx = await b.new_context(viewport={'width': 390, 'height': 844}, device_scale_factor=3, is_mobile=True, has_touch=True, color_scheme='light', locale='en-US')
    await ctx.add_init_script(MOCK); await ctx.add_init_script(AUTO_NOTICE); await ctx.add_init_script(EXT)
    if init: await ctx.add_init_script(init)
    pg = await ctx.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e) + ' @ ' + (e.stack or '')[:300]))
    await pg.route('**/*', route2)
    await pg.goto('http://127.0.0.1:8877/index.html'); await pg.wait_for_timeout(2500)
    await pg.evaluate("document.querySelector('.mobile-nav-btn[data-nav=home]').click()"); await pg.wait_for_timeout(1500)
    return b, pg, errs

async def main():
    backup = sys.argv[1] if len(sys.argv) > 1 else None
    async with async_playwright() as p:
        # A) the phone's state
        init = "if(!localStorage.getItem('radioPlayerFavorites')){ localStorage.setItem('radioPlayerFavorites', %s); localStorage.setItem('radioPlayerCustomSearches', %s); localStorage.setItem('radioPlayerCustomArt', %s); }" % (
            repr(json.dumps(FAVS)), repr(json.dumps(SEARCHES)), repr(json.dumps(ART)))
        b, pg, errs = await page(p, init)
        cards = await pg.evaluate(CARDS); print(cards)
        names = [c['name'] for c in cards]
        for l in ("80's 80's", 'Relaxing Calm', 'Positively Radio', 'Artist Stations'):
            c = [x for x in cards if x['name'] == l]
            check(len(c) == 1 and c[0]['ok'], f'A: {l} shows its cover {c}')
        check(names.count("80's 80's") == 1, 'A: the duplicate left by the import is gone')
        check('Deleted Station' not in names, 'A: a favourite whose custom station really was deleted still goes, as before')
        favs = await pg.evaluate("JSON.parse(localStorage.getItem('radioPlayerFavorites'))")
        check(any(f.get('searchId') == 'cs_newpos' for f in favs) and not any(f.get('searchId') == 'cs_muhsxldf6ovj5c' for f in favs), 'A: saved with the new ids')
        await pg.evaluate("document.getElementById('favoritesSection').scrollIntoView()"); await pg.wait_for_timeout(400)
        await pg.screenshot(path=f'{SHOTS}/b278-favs.png')
        # playing one no longer says it doesn't exist
        await pg.evaluate("Array.from(document.querySelectorAll('#favoritesGrid .fav-card')).find(c => c.querySelector('.tile-name').textContent === 'Positively Radio').click()")
        await pg.wait_for_timeout(1200)
        st = await pg.evaluate("document.body.innerText")
        check('Positively Radio no longer exists' not in st, 'A: playing it finds its custom station')
        check(not errs, f'A: no page errors {errs[:2]}')
        await b.close()
        # C) a favourite whose custom station exists but has no cover, while a copy with the same name has it
        SE2 = SEARCHES + [{'id': 'cs_dupcalm', 'label': 'Relaxing Calm', 'query': 'calm'}]
        F2 = [{'type': 'customStation', 'searchId': 'cs_dupcalm', 'name': 'Relaxing Calm', 'stationuuid': 'customstation:cs_dupcalm'}]
        init = "if(!localStorage.getItem('radioPlayerFavorites')){ localStorage.setItem('radioPlayerFavorites', %s); localStorage.setItem('radioPlayerCustomSearches', %s); localStorage.setItem('radioPlayerCustomArt', %s); }" % (
            repr(json.dumps(F2)), repr(json.dumps(SE2)), repr(json.dumps(ART)))
        b, pg, errs = await page(p, init)
        cards = await pg.evaluate(CARDS); print(cards)
        check(len(cards) == 1 and cards[0]['ok'], f'C: a copy without a cover wears the one saved under its name {cards}')
        check(not errs, f'C: no page errors {errs[:2]}')
        await b.close()
        # B) Mark's backup imported into a fresh app
        if backup:
            b, pg, errs = await page(p, None)
            await pg.set_input_files('#importFavInput', backup); await pg.wait_for_timeout(4000)
            await pg.evaluate("document.querySelector('.mobile-nav-btn[data-nav=home]').click()"); await pg.wait_for_timeout(2500)
            data = json.load(open(backup))
            want = [f['name'] for f in data['favorites'] if f.get('type') == 'customStation' and ('foryouart:' + f['searchId']) in data['customArt']]
            cards = await pg.evaluate(CARDS)
            got = {c['name']: c for c in cards if (c['key'] or '').startswith('customstation:')}
            print('custom stations with covers in the backup:', want)
            bad = [n for n in want if not (n in got and got[n]['img'])]
            check(want and not bad, f'B: after importing the backup every favourite custom station has its cover (missing: {bad})')
            pls = [f['name'] for f in data['favorites'] if f.get('type') == 'playlistRadio']
            favs = await pg.evaluate("JSON.parse(localStorage.getItem('radioPlayerFavorites'))")
            dangling = await pg.evaluate("""(favs)=>favs.filter(f => f.type === 'customStation').map(f => f.name)""", favs)
            ids = await pg.evaluate("JSON.parse(localStorage.getItem('radioPlayerCustomSearches')).map(c => c.id)")
            stale = [f['name'] for f in favs if f.get('type') == 'customStation' and f['searchId'] not in ids]
            check(not stale, f'B: no favourite custom station points at a missing one {stale}')
            check(not errs, f'B: no page errors {errs[:2]}')
            await pg.evaluate("document.getElementById('favoritesSection').scrollIntoView()"); await pg.wait_for_timeout(1500)
            await pg.screenshot(path=f'{SHOTS}/b278-import.png')
            await b.close()
    print('ALL PASSED' if not fails else f'{fails} FAILED')
    sys.exit(1 if fails else 0)
asyncio.run(main())
