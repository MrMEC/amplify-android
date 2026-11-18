"""Build 681 (Mark): a custom channel's archive.org video that's gone (taken down, or no longer on
archive.org) shows Nothing to play with Remove from Channel; it asks first, then the video is out of
the channel. A video that just can't play (restricted) keeps Open on archive.org. Played the way
Mark gets there: the guide's program info > Watch Now, and the More from list under the video.
327x700, dpr 3.3, dark/light. Run: python3 tests/test_ia_channel_gone.py"""
import os, sys, json, asyncio
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
src = open(os.path.join(HERE, 'test_archive_download.py')).read().split('async def notice(pg):')[0]
src = src.replace('PORT = 8881', 'PORT = 8868').replace("ROOT = '/tmp/claude-0/t/srv-iadl'", "ROOT = '/tmp/claude-0/t/srv-iagone'")
src = src.replace("HERE = os.path.dirname(os.path.abspath(__file__))", "HERE = %r" % HERE)
exec(src)
DEF = [{'id': 'pogomix', 'name': 'Pogo Mix', 'order': 'sequence', 'src': {'kind': 'pick', 'shows': [], 'movies': [], 'archive': [
  {'id': 'dark1', 'title': 'Pogo We Have Met The Enemy', 'creator': '', 'year': ''},
  {'id': 'deleted1', 'title': 'David Goldberg: Notes On Project Pogo', 'creator': '', 'year': ''},
  {'id': 'locked1', 'title': 'Pogo Videos', 'creator': 'Pogo', 'year': ''},
  {'id': 'fine1', 'title': '[ar003] Mat Pogo Live at NK', 'creator': 'Mat Pogo', 'year': '2010'}]}}]
METAS = {
  'dark1': {'is_dark': True, 'metadata': {'identifier': 'dark1'}, 'files': []},
  'deleted1': {},
  'locked1': {'metadata': {'identifier': 'locked1', 'title': 'Pogo Videos'}, 'files': [{'name': 'pogo.mp4', 'format': 'h.264', 'private': 'true', 'source': 'original'}]},
}
fails = []
def check(ok, msg):
    print(('PASS ' if ok else 'FAIL ') + msg)
    if not ok: fails.append(msg)
async def run(B, theme):
    T = '[%s]' % theme
    c, pg, errs = await page(B, theme, [{'treeUri': 'content://tree/Music', 'name': 'Music'}])
    await pg.set_viewport_size({'width': 327, 'height': 700})
    async def meta(r):
        iid = r.request.url.split('/metadata/')[1].split('/')[0].split('?')[0]
        if iid in METAS: return await r.fulfill(status=200, content_type='application/json', headers={'Access-Control-Allow-Origin': '*'}, body=json.dumps(METAS[iid]))
        return await r.fallback()
    await c.route('https://archive.org/metadata/**', meta)
    await pg.evaluate("__t.ev(%s)" % json.dumps('localStorage.setItem("radioPlayerLiveChannels", %s); liveChStore = null; liveChCache = null; 1' % json.dumps(json.dumps(DEF))))
    chan = "liveChannels().find(function(c){ return c.url === \"amplify-live:pogomix\"; }) || { url: \"amplify-live:pogomix\", name: \"Pogo Mix\" }"
    stub = lambda i: json.dumps({'id': DEF[0]['src']['archive'][i]['id'], 'title': DEF[0]['src']['archive'][i]['title'], 'creator': '', 'year': '', 'video': True})
    async def watch_now(i):
        await pg.evaluate("__t.ev('openEpgInfo(%s, { s: Date.now() - 60000, e: Date.now() + 600000, t: %s, ai: %s }); document.getElementById(\"epgInfoWatch\").hidden = false; document.getElementById(\"epgInfoWatch\").click(); 1')" % (chan, json.dumps(json.loads(stub(i))['title']), stub(i)).replace("'", "\\'") if False else
            "__t.ev(%s)" % json.dumps('openEpgInfo(%s, { s: Date.now() - 60000, e: Date.now() + 600000, t: %s, ai: %s }); document.getElementById("epgInfoWatch").hidden = false; document.getElementById("epgInfoWatch").click(); 1' % (chan, json.dumps(json.loads(stub(i))['title']), stub(i))))
        await pg.wait_for_timeout(1500)
    acts = "Array.from(document.querySelectorAll('#noticeActions button')).map(function(b){ return b.textContent; })"
    # 1) taken down
    await watch_now(0)
    n = await pg.evaluate("[document.getElementById('noticeOverlay').classList.contains('open'), document.getElementById('noticeTitle').textContent, document.getElementById('noticeMsg').textContent, %s]" % acts)
    check(n[0] and n[1] == 'Nothing to play' and 'taken this item down' in n[2] and n[3] == ['OK', 'Remove from Channel'], '%s taken down: dialog with Remove from Channel %s' % (T, n))
    await pg.screenshot(path=SHOTS + '/iagone-%s-dialog.png' % theme)
    await pg.evaluate("Array.from(document.querySelectorAll('#noticeActions button')).find(function(b){ return b.textContent === 'Remove from Channel'; }).click()"); await pg.wait_for_timeout(500)
    cf = await pg.evaluate("[document.querySelector('.confirm-overlay.open') ? document.getElementById('confirmTitle').textContent : '', document.getElementById('confirmOk').textContent, document.getElementById('noticeOverlay').classList.contains('open')]")
    check(cf[0] == 'Remove “Pogo We Have Met The Enemy” from Pogo Mix?' and cf[1] == 'Remove' and not cf[2], '%s asks first, naming the channel %s' % (T, cf))
    await pg.screenshot(path=SHOTS + '/iagone-%s-confirm.png' % theme)
    # Cancel keeps it
    await pg.evaluate("document.getElementById('confirmCancel').click()"); await pg.wait_for_timeout(300)
    ids = await pg.evaluate("__t.ev('liveChDefById(\"pogomix\").src.archive.map(function(a){ return a.id; })')")
    check(ids == ['dark1', 'deleted1', 'locked1', 'fine1'], '%s Cancel keeps it %s' % (T, ids))
    await watch_now(0)
    await pg.evaluate("Array.from(document.querySelectorAll('#noticeActions button')).find(function(b){ return b.textContent === 'Remove from Channel'; }).click()"); await pg.wait_for_timeout(400)
    await pg.evaluate("document.getElementById('confirmOk').click()"); await pg.wait_for_timeout(500)
    ids = await pg.evaluate("__t.ev('liveChDefById(\"pogomix\").src.archive.map(function(a){ return a.id; })')")
    saved = await pg.evaluate("JSON.parse(localStorage.getItem('radioPlayerLiveChannels'))[0].src.archive.map(function(a){ return a.id; })")
    check(ids == ['deleted1', 'locked1', 'fine1'] and saved == ids, '%s Remove takes it out of the channel (and saves) %s' % (T, saved))
    # 2) no longer on archive.org at all (empty answer)
    await watch_now(1)
    n = await pg.evaluate("[document.getElementById('noticeMsg').textContent, %s]" % acts)
    check('doesn’t have it any more' in n[0] and n[1] == ['OK', 'Remove from Channel'], '%s no longer on archive.org: Remove from Channel %s' % (T, n))
    await pg.evaluate("document.getElementById('noticeOverlay').classList.remove('open')")
    # 3) restricted (still exists): no Remove, Open on archive.org as before
    await watch_now(2)
    n = await pg.evaluate("[document.getElementById('noticeMsg').textContent, %s]" % acts)
    check('restricted' in n[0] and n[1] == ['OK', 'Open on archive.org'], '%s restricted but there: Open on archive.org as before %s' % (T, n))
    await pg.evaluate("document.getElementById('noticeOverlay').classList.remove('open')")
    # 4) not from a channel (Search / Add Channels): no Remove
    await pg.evaluate("__t.ev(%s)" % json.dumps('playArchiveItem({ id: "dark1", title: "Pogo We Have Met The Enemy", video: true }, null); 1')); await pg.wait_for_timeout(1500)
    n = await pg.evaluate(acts)
    check(n == ['OK', 'Open on archive.org'], '%s played from Search (no channel): no Remove %s' % (T, n))
    await pg.evaluate("document.getElementById('noticeOverlay').classList.remove('open')")
    # 5) from the More from list under a playing video (list carries the channel)
    await pg.evaluate("__t.ev(%s)" % json.dumps('archiveNpResults = { items: archiveListForChannel(%s, null), noHistory: false, label: "Pogo Mix", chUrl: "amplify-live:pogomix" }; var it = archiveNpResults.items.find(function(x){ return x.id === "deleted1"; }); playArchiveItem(it, null, { list: archiveNpResults.items, label: "Pogo Mix", chUrl: archiveNpResults.chUrl }); 1' % chan)); await pg.wait_for_timeout(1500)
    n = await pg.evaluate(acts)
    check(n == ['OK', 'Remove from Channel'], '%s from More from Pogo Mix: Remove from Channel %s' % (T, n))
    check(not errs, '%s no page errors %s' % (T, errs[:3]))
    await c.close()
async def main():
    from playwright.async_api import async_playwright
    async with async_playwright() as p:
        B = await p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
        for th in ('dark', 'light'): await run(B, th)
        await B.close()
    print('ALL PASSED' if not fails else 'FAILS %d' % len(fails))
asyncio.run(main())
