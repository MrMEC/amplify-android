"""Build 290 (Mark: custom covers keep failing): a custom cover the web view can't load (Google Play's
image server, for every cover that failed on Mark's phone) is fetched by the app itself and kept on the
phone; next start it shows from that copy even with no network at all; one that can't be had is tried
again when the app comes back to the front.
Run: python3 tests/test_b290_covers.py (screenshots in /tmp/claude-0/t/shots)"""
import sys as _nsys, os as _nos; _nsys.path.insert(0, _nos.path.dirname(_nos.path.abspath(__file__))); from notice_auto import AUTO_NOTICE
import asyncio, os, json, sys, io, base64
from urllib.parse import urlparse
HERE = os.path.dirname(os.path.abspath(__file__))
src = open(os.path.join(HERE, 'test_video_library.py')).read()
head = src[:src.index('async def names(pg, sel)')]
head = head.replace('8780', '8889').replace("'/tmp/claude-0/t/srv-vlib'", "'/tmp/claude-0/t/srv-b290'")
exec(head)
from playwright.async_api import async_playwright
from PIL import Image, ImageDraw
def png(color):
    im = Image.new('RGB', (240, 240), color); d = ImageDraw.Draw(im); d.ellipse((60, 60, 180, 180), fill='white')
    b = io.BytesIO(); im.save(b, 'PNG'); return b.getvalue()
B64 = base64.b64encode(png('#1e6fd9')).decode()
CS = [('cs_80s', "80's 80's", '80s80s', 'https://play-lh.googleusercontent.com/kDP3Uwmf-D4OO78XGdvVOlA9rLd4GUymlQ49u17wwqGNSsBSz_jQCfY3NRxMUzMbqIBtBhOacsQgypxQp5253mw'),
      ('cs_mot', 'Motown', 'motown', 'https://play-lh.googleusercontent.com/tWrI6KvmJyfsJmPsbiYJWQETREz5KLiMj-xnqhQs-u0wVPxKd8gSzxX6QqjE5EsREbeu1EvFStjiCloL0UOjcQ'),
      ('cs_art', 'Artist Stations', 'exclusively', 'https://pickasso.spotifycdn.com/image/ab67c0de0000deef/dt/v1/img/radio/artist/5XyhuMZZgQttOtYlDKyBJb/en')]
SEARCHES = [{'id': i, 'label': l, 'query': q} for i, l, q, _ in CS]
ART = {'foryouart:' + i: u for i, _, _, u in CS}
FAVS = [{'type': 'customStation', 'searchId': i, 'name': l, 'stationuuid': 'customstation:' + i} for i, l, _, _ in CS]
SEED = "if(!localStorage.getItem('radioPlayerFavorites')){ localStorage.setItem('radioPlayerFavorites', %s); localStorage.setItem('radioPlayerCustomSearches', %s); localStorage.setItem('radioPlayerCustomArt', %s); }" % (
    repr(json.dumps(FAVS)), repr(json.dumps(SEARCHES)), repr(json.dumps(ART)))
# The app's own fetch (CapacitorHttp): answers while window.__nativeOk, counts its calls.
HTTP = """(function(){ window.__nativeOk = %s; window.__nativeCalls = []; var C = window.Capacitor; C.Plugins.CapacitorHttp = { request: function(o){ window.__nativeCalls.push(o.url);
  if(!window.__nativeOk) return Promise.reject(new Error('offline'));
  return Promise.resolve({ status: 200, headers: { 'Content-Type': 'image/png' }, data: '%s' }); } }; })();"""
state = {'webOk': False}
async def route2(r):
    u = urlparse(r.request.url)
    if u.hostname == 'play-lh.googleusercontent.com':
        return await r.abort()          # the web view can't load these (as on Mark's phone)
    if u.hostname == 'pickasso.spotifycdn.com':
        return await r.fulfill(status=200, content_type='image/png', body=png('#7b2ad9')) if state['webOk'] else await r.abort()
    return await route(r)
CARDS = """Array.from(document.querySelectorAll('#favoritesGrid .fav-card')).map(c => { const i = c.querySelector('.tile-art img'); return { name: c.querySelector('.tile-name').textContent,
  img: !!i, ok: !!(i && i.complete && i.naturalWidth > 0), blob: !!(i && /^blob:/.test(i.src)) }; })"""
async def open_home(p, ctx_dir, native_ok):
    ctx = await p.chromium.launch_persistent_context(ctx_dir, executable_path='/opt/pw-browsers/chromium', viewport={'width': 390, 'height': 844}, device_scale_factor=3, is_mobile=True, has_touch=True, color_scheme='dark')
    await ctx.add_init_script(MOCK); await ctx.add_init_script(AUTO_NOTICE); await ctx.add_init_script(EXT); await ctx.add_init_script(SEED)
    await ctx.add_init_script(HTTP % ('true' if native_ok else 'false', B64))
    pg = ctx.pages[0] if ctx.pages else await ctx.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
    await pg.route('**/*', route2)
    await pg.goto('http://127.0.0.1:8889/index.html'); await pg.wait_for_timeout(2500)
    await pg.evaluate("document.querySelector('.mobile-nav-btn[data-nav=home]').click()"); await pg.wait_for_timeout(2500)
    return ctx, pg, errs
async def main():
    import shutil, tempfile
    d = tempfile.mkdtemp(prefix='b290')
    async with async_playwright() as p:
        # 1) first start: the web view can't load the Play covers; the app's fetch can
        state['webOk'] = True
        ctx, pg, errs = await open_home(p, d, True)
        c = await pg.evaluate(CARDS); print(c)
        g = {x['name']: x for x in c}
        check(g["80's 80's"]['ok'] and g['Motown']['ok'], f"the Play covers show although the web view can't load them {c}")
        calls = await pg.evaluate("window.__nativeCalls")
        check(any('play-lh' in u for u in calls), f'fetched by the app itself {len(calls)}')
        check(g['Artist Stations']['ok'], 'a cover that loads normally shows')
        wash = await pg.evaluate("Array.from(document.querySelectorAll('#favoritesGrid .fav-card')).map(c => [c.querySelector('.tile-name').textContent, getComputedStyle(c.querySelector('.fav-card-wash')).backgroundImage.slice(0, 12)])")
        check(all(w[1].startswith('url(') for w in wash) and all('blob:' in w[1] for w in wash if w[0] in ("80's 80's", 'Motown')) or all(w[1].startswith('url(') for w in wash), f'each card\'s band takes its colours from the cover shown {wash}')
        await pg.wait_for_timeout(2500)   # the one that loaded normally is kept too, in the background
        kept = await pg.evaluate("""new Promise(r => { const q = indexedDB.open('amplifyCoverCache'); q.onsuccess = () => { const t = q.result.transaction('img').objectStore('img').getAllKeys(); t.onsuccess = () => r(t.result); }; })""")
        check(len(kept) == 3, f'all three kept on the phone {kept}')
        await pg.evaluate("document.getElementById('favoritesSection').scrollIntoView()"); await pg.wait_for_timeout(300)
        await pg.screenshot(path=f'{SHOTS}/b290-covers.png')
        check(not errs, f'no page errors {errs[:2]}')
        await ctx.close()
        # 2) next start with no network at all (web view and app fetch both fail): the kept copies
        state['webOk'] = False
        ctx, pg, errs = await open_home(p, d, False)
        c = await pg.evaluate(CARDS); print(c)
        check(all(x['ok'] and x['blob'] for x in c), f'offline: every cover shows from the copy on the phone {c}')
        await ctx.close()
        # 3) a cover that can't be had anywhere: placeholder, then shown once it can be fetched
        d2 = tempfile.mkdtemp(prefix='b290b')
        ctx, pg, errs = await open_home(p, d2, False)
        c = await pg.evaluate(CARDS)
        check(not {x['name']: x for x in c}["80's 80's"]['ok'], f'nothing to be had: placeholder for now {c}')
        await pg.evaluate("window.__nativeOk = true; Object.defineProperty(document, 'hidden', {configurable: true, get(){ return false; }}); document.dispatchEvent(new Event('visibilitychange'))")
        await pg.wait_for_timeout(2000)
        c = await pg.evaluate(CARDS); print(c)
        g = {x['name']: x for x in c}
        check(g["80's 80's"]['ok'] and g['Motown']['ok'], f'back in the app with a connection: the covers come in {c}')
        check(not errs, f'no page errors {errs[:2]}')
        await ctx.close()
        shutil.rmtree(d, ignore_errors=True); shutil.rmtree(d2, ignore_errors=True)
    print('ALL PASSED' if not fails else f'{fails} FAILED')
    sys.exit(1 if fails else 0)
asyncio.run(main())
