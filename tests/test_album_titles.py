"""Build 193: on album pages a long song title wraps to a second line (and ends in an ellipsis
after two); a short title stays on one line. Checked at 412 and 360 wide with text 1.35x.
Run: python3 tests/test_album_titles.py (screenshots in /tmp/claude-0/t/shots)"""
import os
HERE = os.path.dirname(os.path.abspath(__file__))
src = open(os.path.join(HERE, 'test_add_to_playlist.py')).read()
head = src[:src.index('\nasync def main():')]
head = head.replace('PORT = 8795', 'PORT = 8825').replace("'/tmp/claude-0/t/srv_addpl'", "'/tmp/claude-0/t/srv_albtitles'")
head = head.replace("SONGS = [('Kay 1', 'Kay', 'Big Album', 1), ('Kay 3', 'Kay', 'Big Album', 3), ('Kay 2', 'Kay', 'Big Album', 2), ('Lone', 'Lee', 'Other', 1)]",
    "SONGS = [('Short One', 'Kay', 'Big Album', 1), ('A Rather Long Song Title That Needs Two Lines To Read', 'Kay', 'Big Album', 2), "
    "('An Extremely Long Song Title That Goes On And On Well Past Any Two Lines Of Text On A Phone Screen At All', 'Kay', 'Big Album', 3), ('Lone', 'Lee', 'Other', 1)]")
assert 'Short One' in head
exec(head)
LINES = """(()=>Array.prototype.map.call(document.querySelectorAll('#stationsGrid.grid-album .song-row'), function(r){
  var t = r.querySelector('.song-row-title'), cs = getComputedStyle(t), lh = parseFloat(cs.lineHeight);
  var tm = r.querySelector('.song-row-time'), rr = r.getBoundingClientRect();
  return { name: t.textContent, lines: Math.round(t.getBoundingClientRect().height / lh), clipped: t.scrollHeight > t.clientHeight + 1,
           timeIn: !tm || tm.getBoundingClientRect().right <= rr.right + 1, over: t.getBoundingClientRect().right <= (tm ? tm.getBoundingClientRect().left : rr.right) + 1 }; }))()"""

async def run(p, w, big):
    b = await p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
    ctx = await b.new_context(viewport={'width': w, 'height': 844}, device_scale_factor=2, is_mobile=True, has_touch=True, color_scheme='dark')
    await ctx.add_init_script(MOCK)
    pg = await ctx.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
    await pg.route('**/*', lambda route: route.continue_() if '127.0.0.1' in route.request.url else route.abort())
    await pg.goto(f'http://127.0.0.1:{PORT}/index.html'); await pg.wait_for_timeout(2500)
    await pg.evaluate("""(function(){ var ov=document.getElementById('addMusicOverlay'); if(ov) ov.classList.add('open');
      var btn=document.getElementById('addMusicFolderBtn'); btn.disabled=false; btn.click(); })()""")
    for _ in range(60):
        await pg.wait_for_timeout(500)
        if len(await pg.evaluate('__t.tracks()')) >= 4: break
    if big: await pg.add_style_tag(content='.song-row-title,.song-row-num,.song-row-time{font-size:calc(15px*1.35) !important}')
    await pg.evaluate("__t.openAlbum('Big Album')"); await pg.wait_for_timeout(900)
    tag = f'{w}' + ('-big' if big else '')
    r = await pg.evaluate(LINES)
    byn = {x['name'][:6]: x for x in r}
    check(byn['Short '][ 'lines'] == 1, f'{tag}: a short title stays on one line {byn["Short "]}')
    check(byn['A Rath']['lines'] == 2 and (big or not byn['A Rath']['clipped']), f'{tag}: a long title wraps to two lines (all of it at normal size) {byn["A Rath"]}')
    check(byn['An Ext']['lines'] == 2 and byn['An Ext']['clipped'], f'{tag}: a very long title stops at two lines (ellipsis) {byn["An Ext"]}')
    check(all(x['timeIn'] and x['over'] for x in r), f'{tag}: titles stay clear of the song length {r}')
    await pg.evaluate("(()=>{ document.querySelectorAll('.lib-progress, .import-toast, #importToast, .toast').forEach(function(e){ e.style.display='none'; }); var r=document.querySelector('#stationsGrid .song-row'); window.scrollTo(0, r.getBoundingClientRect().top + scrollY - 120); })()")
    await pg.wait_for_timeout(400)
    await pg.screenshot(path=f'{shots}/albtitles-{tag}.png')
    check(not errs, f'{tag}: no page errors {errs[:2]}')
    await b.close()

async def main():
    async with async_playwright() as p:
        await run(p, 412, False)
        await run(p, 412, True)
        await run(p, 360, True)
    print('ALL PASSED' if not fails else f'FAILED {fails}')
asyncio.run(main())
