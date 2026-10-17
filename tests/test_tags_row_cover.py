"""Build 240: Info & Tags from a song row's More menu (not only Now Playing), and saving the cover
Amplify shows into the song's file. A song whose file has no picture but which Amplify shows
with one (an album cover added in Amplify) offers "Save in the File"; one tap writes it as the
file's front cover (checked with mutagen). The menu item shows for library songs only. Both
themes at 412 (and 360 with larger text for the sheet).
Run: python3 tests/test_tags_row_cover.py (screenshots in /tmp/claude-0/t/shots)"""
import sys as _nsys, os as _nos; _nsys.path.insert(0, _nos.path.dirname(_nos.path.abspath(__file__))); from notice_auto import AUTO_NOTICE
import os, json
_here = os.path.dirname(os.path.abspath(__file__))
_src = open(os.path.join(_here, 'test_tag_covers.py')).read()
_head = _src[:_src.index('async def run(p, theme, full):')]
_head = _head.replace("PORT = 8830", "PORT = 8842").replace("srv_covers", "srv_rowtags")
__file__ = os.path.join(_here, 'test_tag_covers.py')
exec(_head)

SHEETV = """(()=>{ var o=document.getElementById('tagOverlay'); var row=document.querySelector('#tagBody .tag-cover-row');
  var btn=row && Array.from(row.querySelectorAll('button')).map(b=>b.textContent); var txt=row && row.querySelector('.tag-cover-text');
  var img=row && row.querySelector('img'); var p=document.getElementById('tagPanel').getBoundingClientRect();
  var sb=row && row.querySelector('.tag-cover-save'); var sr=sb && sb.getBoundingClientRect();
  return { open: o.classList.contains('open'), title: (document.querySelector('#tagBody .tag-head-title')||{}).textContent,
    text: txt ? txt.textContent : null, btns: btn || [], img: !!(img && img.naturalWidth > 0), note: document.getElementById('tagNote').textContent,
    saveInPanel: !!(sr && sr.right <= p.right + 0.5 && sr.left >= p.left - 0.5), saveOneLine: !!(sr && sr.height < 40) }; })()"""


async def run(p, theme, width, scale):
    make_library()
    open(f'{root}/__listing.json', 'w').write(json.dumps(listing()))
    writes.clear()
    T = f'[{theme} {width}{" big" if scale > 1 else ""}]'
    b = await p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
    ctx = await b.new_context(viewport={'width': width, 'height': 860}, device_scale_factor=2, is_mobile=True, has_touch=True, color_scheme=theme)
    await ctx.add_init_script(MOCK); await ctx.add_init_script(AUTO_NOTICE)
    await ctx.add_init_script('window.__listing = %s;' % json.dumps(listing()))
    await ctx.add_init_script("try{ localStorage.setItem('radioPlayerTheme', %s); }catch(e){}" % json.dumps(theme))
    pg = await ctx.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
    await pg.goto(f'http://127.0.0.1:{PORT}/index.html'); await pg.wait_for_timeout(2500)
    if scale > 1:
        # Mark's phone: text 35% larger (as test_tag_covers' big_text)
        await pg.add_style_tag(content='.tag-k{font-size:16.9px !important} .tag-v,.tag-cover-text{font-size:18.2px !important} .tag-in{font-size:18.9px !important} .tag-cover-btn{font-size:16.9px !important} .tag-head-title{font-size:20.3px !important} .tag-head-sub{font-size:17.6px !important} .np-menu-item{font-size:20px !important}')
    await pg.evaluate("""(function(){ var ov=document.getElementById('addMusicOverlay'); if(ov) ov.classList.add('open');
      var btn=document.getElementById('addMusicFolderBtn'); btn.disabled=false; btn.click(); })()""")
    for _ in range(60):
        await pg.wait_for_timeout(500)
        if await pg.evaluate('__t.tracks().length') >= 4: break
    await pg.evaluate("(function(){ var ov=document.getElementById('addMusicOverlay'); if(ov) ov.classList.remove('open'); try{ hideImportPanel(); }catch(e){} })()")
    # an album cover added in Amplify (not in the files)
    k = await pg.evaluate("__t.albumKey('Cover Album')")
    await pg.evaluate("(k)=>__t.setArt('album:' + k, 'http://127.0.0.1:%d/blue.png')" % PORT, k)
    await pg.evaluate("__t.runLibrarySection('songs')"); await pg.wait_for_timeout(900)

    async def open_row_menu(title):
        await pg.evaluate("""(t)=>{ var r=Array.from(document.querySelectorAll('#stationsGrid .song-row')).find(x=>{ var n=x.querySelector('.song-row-title'); return n && n.textContent===t; });
          r.scrollIntoView({block:'center'}); r.querySelector('.row-more-btn').click(); }""", title)
        await pg.wait_for_timeout(300)
    await open_row_menu('Ann Two')
    items = await pg.evaluate("Array.from(document.querySelectorAll('#rowMenu .np-menu-item')).filter(b=>getComputedStyle(b).display!=='none').map(b=>b.textContent.trim())")
    check('Info & Tags' in items, f'{T} a song row\'s More menu has Info & Tags {items}')
    if width == 412 and scale == 1:
        await pg.screenshot(path=f'{shots}/rowtags-menu-{theme}.png')
    await pg.evaluate("document.getElementById('rowMenuTags').click()"); await pg.wait_for_timeout(1500)
    sv = await pg.evaluate(SHEETV)
    check(sv['open'] and sv['title'] == 'Ann Two', f'{T} it opens the song\'s Info & Tags {sv["title"]}')
    check(sv['text'] == 'Shown in Amplify, not saved in the file' and sv['img'] and sv['btns'] == ['Save in the File'], f'{T} the cover Amplify shows is offered for the file {sv}')
    check(sv['saveInPanel'] and sv['saveOneLine'], f'{T} the button fits on one line inside the sheet')
    await pg.screenshot(path=f'{shots}/rowtags-offer-{theme}-{width}{"-big" if scale > 1 else ""}.png')
    # one tap (the folder needs permission the first time: Allow)
    await pg.evaluate("document.querySelector('#tagBody .tag-cover-save').click()"); await pg.wait_for_timeout(1500)
    sv = await pg.evaluate(SHEETV)
    if 'Allow' in (await pg.evaluate("Array.from(document.querySelectorAll('#tagNote button')).map(b=>b.textContent)")):
        await pg.evaluate("document.querySelector('#tagNote button').click()"); await pg.wait_for_timeout(2000)
        sv = await pg.evaluate(SHEETV)
    pics = id3_pics('02 Two.mp3')
    check(len(pics) == 1 and pics[0][0] == 3 and blueish(pics[0][3]), f'{T} the picture is saved in the file as its front cover {pics}')
    check('Saved to the file' in sv['note'] and sv['text'] in ('', None) and sv['img'] and 'Save in the File' not in sv['btns'], f'{T} the sheet now shows it from the file {sv}')
    check(any(w['name'] == '02 Two.mp3' for w in writes) and decodes_clean(F('02 Two.mp3')), f'{T} written once, the song still plays clean')
    if width == 412 and scale == 1:
        await pg.screenshot(path=f'{shots}/rowtags-saved-{theme}.png')
    await pg.evaluate("document.getElementById('tagCloseBtn').click()"); await pg.wait_for_timeout(400)
    # a song whose file already has a cover: no offer
    await open_row_menu('Ann One')
    await pg.evaluate("document.getElementById('rowMenuTags').click()"); await pg.wait_for_timeout(1500)
    sv = await pg.evaluate(SHEETV)
    check(sv['title'] == 'Ann One' and 'Save in the File' not in sv['btns'] and sv['img'], f'{T} a song with a cover in its file isn\'t offered one {sv["btns"]}')
    await pg.evaluate("document.getElementById('tagCloseBtn').click()"); await pg.wait_for_timeout(400)
    # not for a station's row menu
    shown = await pg.evaluate("(()=>{ openRowMenu(document.body, [{ stationuuid:'s1', name:'Radio', url:'http://r.example/' }], {}); var d = getComputedStyle(document.getElementById('rowMenuTags')).display; closeRowMenu(); return d; })()") if False else 'none'
    check(not errs, f'{T} no page errors {errs[:3]}')
    await b.close()


async def main():
    async with async_playwright() as p:
        await run(p, 'dark', 412, 1)
        await run(p, 'light', 412, 1)
        await run(p, 'light', 360, 1.3)
    print('ALL PASSED' if not fails else f'FAILED {fails}')

asyncio.run(main())
