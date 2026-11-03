"""Build 455 (Mark): an audiobook is labelled Audiobook on Home's carousel (title, section and author; no
"Internet Archive" note), and its Now Playing has no About This Episode. A podcast still says Podcast."""
import os, sys, json, asyncio
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
src = open(os.path.join(HERE, 'test_audiobooks.py')).read().split('async def run(B, theme):')[0].replace("HERE = os.path.dirname(os.path.abspath(__file__))", "HERE = %r" % HERE).replace('PORT = 8893', 'PORT = 8899')
exec(src)
async def main():
    from playwright.async_api import async_playwright
    async with async_playwright() as p:
        B = await p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
        c, pg, errs = await page(B, 'dark', [{'treeUri': 'content://tree/Music', 'name': 'Music'}])
        async def adv(r): await r.fulfill(status=200, content_type='application/json', headers={'Access-Control-Allow-Origin': '*'}, body=json.dumps(adv_body(r.request.url)))
        async def meta(r):
            id_ = r.request.url.rstrip('/').split('/')[-1]; b = meta_body(id_); b['metadata']['year'] = '2020'
            await r.fulfill(status=200, content_type='application/json', headers={'Access-Control-Allow-Origin': '*'}, body=json.dumps(b))
        async def img(r): await r.fulfill(status=200, content_type='image/jpeg', headers={'Access-Control-Allow-Origin': '*'}, path=ROOT + '/files/cover.jpg')
        async def dl(r): await r.fulfill(status=200, content_type='audio/mpeg', path=ROOT + '/files/01 - Song One.mp3')
        await c.route('https://archive.org/advancedsearch.php**', adv); await c.route('https://archive.org/metadata/**', meta)
        await c.route('https://archive.org/services/img/**', img); await c.route('https://archive.org/download/**', dl)
        await pg.evaluate("__t.ev('openLibTab(\"audiobooks\")')"); await pg.wait_for_timeout(1500)
        await pg.evaluate("document.querySelector('.gp-row > .tile').click()"); await pg.wait_for_timeout(2000)
        about = await pg.evaluate("getComputedStyle(document.getElementById('npEpDesc')).display")
        desc = await pg.evaluate("__t.ev('currentStation.description')")
        check(about == 'none' and desc, f'no About This Episode for a book section (its note {desc!r})')
        await pg.screenshot(path='/tmp/claude-0/t/shots/ab-label-np.png')
        await pg.evaluate("__t.ev('closeNowPlaying()')"); await pg.wait_for_timeout(400)
        await pg.evaluate("document.querySelector('.mobile-nav-btn[data-nav=home]').click()"); await pg.wait_for_timeout(2000)
        slides = await pg.evaluate("Array.from(document.querySelectorAll('.nph-kicker')).map(function(k){ var s = k.closest('.nph-body') || k.parentNode; return [k.textContent, (s.querySelector('.nph-title')||{}).textContent, (s.querySelector('.nph-line')||{}).textContent, (s.querySelector('.nph-desc')||{}).textContent]; })")
        check(slides and slides[0][:2] == ['Audiobook', 'Letters of Two Brides'] and slides[0][2] == 'Section 1 · Honoré de Balzac' and not slides[0][3], f'the carousel says Audiobook, with the section and author {slides}')
        await pg.screenshot(path='/tmp/claude-0/t/shots/ab-label-home.png')
        # a real podcast episode still says Podcast and keeps About This Episode
        check('Podcast' == await pg.evaluate("__t.ev(\"heroTextFor({ type: 'podcast', guid: 'pod-1', name: 'Ep 1', collectionName: 'Show', description: 'About it' }).kicker\")"), 'a podcast episode still says Podcast')
        check(not errs, f'no page errors {errs[:2]}')
        await B.close()
    print('\nFAILS:', len(fails)); sys.exit(1 if fails else 0)
asyncio.run(main())
