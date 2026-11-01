"""Build 387: an archive.org video with no MP4 (only Flash Video, WebM, Matroska, QuickTime) still
plays, MP4 first when there is one; an item that really can't be played says why (restricted
files, or formats phones can't play) and offers Open on archive.org. Phone, dark.
Run: python3 tests/test_archive_formats.py"""
import os, sys, json, asyncio
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
src = open(os.path.join(HERE, 'test_archive_download.py')).read().split('async def notice(pg):')[0]
src = src.replace('PORT = 8881', 'PORT = 8886').replace("ROOT = '/tmp/claude-0/t/srv-iadl'", "ROOT = '/tmp/claude-0/t/srv-iafmt'").replace("HERE = os.path.dirname(os.path.abspath(__file__))", "HERE = %r" % HERE)
exec(src)
METAS = {
  'flvonly': {'metadata': {'title': 'Funny or Die Video'}, 'files': [{'name': 'fod.flv', 'format': 'Flash Video', 'size': '9000000'}, {'name': 'fod.ogv', 'format': 'Ogg Video', 'size': '5000'}, {'name': 'fod.gif', 'format': 'Animated GIF'}]},
  'mixed': {'metadata': {'title': 'Mixed'}, 'files': [{'name': 'a.flv', 'format': 'Flash Video', 'size': '9'}, {'name': 'a.mp4', 'format': 'h.264', 'size': '8'}, {'name': 'a.webm', 'format': 'WebM', 'size': '7'}]},
  'webm': {'metadata': {'title': 'WebM'}, 'files': [{'name': 'w.webm', 'format': 'WebM', 'size': '7'}, {'name': 'w.mkv', 'format': 'Matroska', 'size': '9'}]},
  'locked': {'metadata': {'title': 'Locked'}, 'files': [{'name': 'l.mp4', 'format': 'h.264', 'private': 'true'}, {'name': 'l.jpg', 'format': 'JPEG'}]},
  'wmv': {'metadata': {'title': 'Old WMV'}, 'files': [{'name': 'x.wmv', 'format': 'Windows Media', 'size': '9'}, {'name': 'x.txt', 'format': 'Text'}]},
}
fails = []
def check(ok, msg):
    print(('PASS ' if ok else 'FAIL ') + msg)
    if not ok: fails.append(msg)
async def main():
    from playwright.async_api import async_playwright
    async with async_playwright() as p:
        B = await p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
        c, pg, errs = await page(B, 'dark', [{'treeUri': 'content://tree/Music', 'name': 'Music'}])
        async def meta(r):
            id_ = r.request.url.rstrip('/').split('/')[-1]
            await r.fulfill(status=200, content_type='application/json', headers={'Access-Control-Allow-Origin': '*'}, body=json.dumps(METAS.get(id_, {})))
        await c.route('https://archive.org/metadata/**', meta)
        await pg.evaluate("__t.ev('playStation = function(st){ window.__played = st; }; openNowPlaying = function(){}; 0')")
        async def play(id_):
            await pg.evaluate("window.__played = null; document.getElementById('noticeOverlay').classList.remove('open')")
            await pg.evaluate("(id)=>__t.ev('playArchiveItem')({ id: id, title: 'T ' + id, creator: '', video: true }, null, {})", id_)
            await pg.wait_for_timeout(500)
            return await pg.evaluate("[window.__played && window.__played.episodeUrl, document.getElementById('noticeOverlay').classList.contains('open') ? document.getElementById('noticeTitle').textContent + ' | ' + document.getElementById('noticeMsg').textContent : '', Array.prototype.map.call(document.querySelectorAll('#noticeActions button'), function(b){ return b.textContent; })]")
        r = await play('flvonly'); check(r[0] and r[0].endswith('/fod.flv') and not r[1], f'Flash Video only: it plays {r}')
        r = await play('mixed'); check(r[0] and r[0].endswith('/a.mp4'), f'MP4 is still chosen first {r[0]}')
        r = await play('webm'); check(r[0] and r[0].endswith('/w.webm'), f'WebM before Matroska {r[0]}')
        r = await play('locked'); check(not r[0] and 'restricted' in r[1] and r[2] == ['OK', 'Open on archive.org'], f'restricted files: says so, offers Open on archive.org {r}')
        await pg.screenshot(path=f'{SHOTS}/iafmt-locked.png')
        r = await play('wmv'); check(not r[0] and 'Windows Media' in r[1] and "can’t play" in r[1], f'an unplayable format: says which {r[1]}')
        check(not errs, f'no page errors {errs}')
        await B.close()
    print('ALL PASSED' if not fails else f'FAILS {len(fails)}')
asyncio.run(main())
