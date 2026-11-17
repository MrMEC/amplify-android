"""Build 664 (Mark, option A): Add Channels > Archive.org rows have one + button, a kind tag and a
one-line detail; tapping a row opens a sheet (description, Add to Live TV, Preview, Add to a Custom
Channel, Download to Library, Remove from Live TV with a confirm). 327 wide, dpr 3.3, dark/light.
Run: python3 tests/test_ia_rows_a.py (screenshots in /tmp/claude-0/t/shots)"""
import os, sys, json, asyncio, urllib.parse
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
src = open(os.path.join(HERE, 'test_archive_download.py')).read().split('async def notice(pg):')[0]
src = src.replace('PORT = 8881', 'PORT = 8864').replace("ROOT = '/tmp/claude-0/t/srv-iadl'", "ROOT = '/tmp/claude-0/t/srv-iarowa'")
src = src.replace("HERE = os.path.dirname(os.path.abspath(__file__))", "HERE = %r" % HERE)
exec(src)
TITLES = [('pogo_el_payaso', 'audio', '', '', 27000), ('David Goldberg: Notes On Project Pogo and the White House Insider', 'movies', '', '', 4100),
  ('Pogo Videos', 'movies', 'Pogo', '', 4000), ('Pogo We Have Met The Enemy and He Is Us', 'movies', '', '', 3100),
  ('[ar003] Mat Pogo Live at NK 29/05/2010', 'audio', 'Mat Pogo', '2010', 2900), ('burnt possum', 'audio', 'The Pogo Possum Players', '1971', 2500)]
def docs_for(url):
    docs = [{'identifier': f'pogo{i}', 'title': t, 'mediatype': k, 'creator': c, 'year': y, 'downloads': d} for i, (t, k, c, y, d) in enumerate(TITLES * 4)]
    for i, d in enumerate(docs): d['identifier'] = f'pogo{i}'
    return {'response': {'numFound': len(docs), 'start': 0, 'docs': docs}}
fails = []
def check(ok, msg):
    print(('PASS ' if ok else 'FAIL ') + msg)
    if not ok: fails.append(msg)
async def run(B, theme):
    T = f'[{theme}]'
    c, pg, errs = await page(B, theme, [{'treeUri': 'content://tree/Music', 'name': 'Music'}])
    await pg.set_viewport_size({'width': 327, 'height': 700}); await pg.reload(); await pg.wait_for_timeout(2500)
    async def adv(r):
        await r.fulfill(status=200, content_type='application/json', headers={'Access-Control-Allow-Origin': '*'}, body=json.dumps(docs_for(r.request.url)))
    async def meta(r):
        await r.fulfill(status=200, content_type='application/json', headers={'Access-Control-Allow-Origin': '*'}, body=json.dumps({'result': {'description': 'These videos contain information from the classified files known as <b>Project Pogo</b> and Project Possum.<br>They contain notes about David’s contact with the &quot;White House Insider&quot; and various other sources over many years.'}}))
    await c.route('https://archive.org/advancedsearch.php**', adv)
    await c.route('https://archive.org/metadata/*/metadata', meta)
    await pg.evaluate("__t.ev('addChannelsState.archiveQ = \"pogo\"; addChannelsTab = \"archive\"; openAddChannelsPage()')"); await pg.wait_for_timeout(2000)
    await pg.evaluate("document.getElementById('noticeOverlay').classList.remove('open')")
    r = await pg.evaluate("""(()=>{ var rows=[].slice.call(document.querySelectorAll('.ia-item')); var r=rows[1];
      return { n: rows.length, btns: rows.map(function(x){ return [].filter.call(x.querySelectorAll('button'), function(b){ return b.offsetWidth>0; }).length; }),
        tag: r.querySelector('.ia-kind-tag').textContent, nameLines: Math.round(r.querySelector('.ch-name').getBoundingClientRect().height / parseFloat(getComputedStyle(r.querySelector('.ch-name')).lineHeight || 20)),
        subH: Math.round(r.querySelector('.ch-sub').getBoundingClientRect().height), rowH: Math.round(r.getBoundingClientRect().height) }; })()""")
    check(r['n'] == 24 and all(b == 1 for b in r['btns']), f'{T} every row has one button {r["btns"][:6]}')
    check(r['tag'] == 'VIDEO' and r['subH'] < 24, f'{T} kind tag and a one-line detail {r}')
    await pg.evaluate("document.querySelector('.ia-kind') && document.querySelector('.ia-kind').scrollIntoView({block:'start'}); window.scrollBy(0,-170)"); await pg.wait_for_timeout(300)
    # add one by the + (row 3)
    await pg.evaluate("document.querySelectorAll('.ia-item')[2].querySelector('.ch-add').click()"); await pg.wait_for_timeout(200)
    await pg.screenshot(path=f'{SHOTS}/iarowa-{theme}-list.png')
    # open the sheet for row 2
    await pg.evaluate("document.querySelectorAll('.ia-item')[1].click()"); await pg.wait_for_timeout(700)
    sh = await pg.evaluate("""(()=>{ var o=document.getElementById('chSheetOverlay'); return { open:o.classList.contains('open'), ia:o.classList.contains('ia-item-sheet'),
      items:[].map.call(o.querySelectorAll('.ia-sheet-primary, .ch-sheet-item'), function(b){ return b.textContent.trim(); }),
      desc:(o.querySelector('.ia-sheet-desc')||{}).textContent, played: !!(window.__played) }; })()""")
    check(sh['open'] and sh['items'][0] == 'Add to Live TV' and 'Preview' in sh['items'] and 'Add to a Custom Channel' in sh['items'], f'{T} the sheet opens with its actions {sh["items"]}')
    check((sh['desc'] or '').startswith('These videos contain') and '<b>' not in sh['desc'], f'{T} the description shows as plain text')
    await pg.screenshot(path=f'{SHOTS}/iarowa-{theme}-sheet.png')
    await pg.evaluate("document.querySelector('.ia-sheet-primary').click()"); await pg.wait_for_timeout(300)
    added = await pg.evaluate("[!document.getElementById('chSheetOverlay').classList.contains('open'), document.querySelectorAll('.ia-item')[1].querySelector('.ch-add').classList.contains('added')]")
    check(all(added), f'{T} Add to Live TV closes the sheet and the row shows the check {added}')
    await pg.evaluate("document.querySelectorAll('.ia-item')[1].click()"); await pg.wait_for_timeout(500)
    sh = await pg.evaluate("[].map.call(document.querySelectorAll('#chSheetOverlay .ia-sheet-primary, #chSheetOverlay .ch-sheet-item'), function(b){ return b.textContent.trim(); })")
    check(sh[0] == 'On Live TV' and sh[-1] == 'Remove from Live TV', f'{T} once added: On Live TV, and Remove at the end {sh}')
    await pg.screenshot(path=f'{SHOTS}/iarowa-{theme}-sheet-added.png')
    await pg.evaluate("[].slice.call(document.querySelectorAll('#chSheetOverlay .ch-sheet-item')).pop().click()"); await pg.wait_for_timeout(500)
    conf = await pg.evaluate("!!document.querySelector('.confirm-overlay.open')")
    check(conf, f'{T} Remove asks first')
    await pg.screenshot(path=f'{SHOTS}/iarowa-{theme}-confirm.png')
    # the Live TV channel sheet still looks as before (no archive class)
    await pg.evaluate("document.querySelectorAll('.confirm-overlay.open').forEach(function(o){ o.classList.remove('open'); })")
    check(not errs, f'{T} no page errors {errs}')
    await c.close()
async def main():
    from playwright.async_api import async_playwright
    async with async_playwright() as p:
        B = await p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
        for th in ('dark', 'light'): await run(B, th)
        await B.close()
    print('ALL PASSED' if not fails else f'FAILS {len(fails)}')
asyncio.run(main())
