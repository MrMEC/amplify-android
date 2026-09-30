"""Refresh: the music folders (My Library) and video folders (Video > Movies / TV Shows) scanned
again -- new files added, files gone from the folder removed. Also: the space under the Video
tabs, and the poster search carrying the title.
Run: python3 tests/test_media_refresh.py (screenshots in /tmp/claude-0/t/shots)"""
import asyncio, os, json
HERE = os.path.dirname(os.path.abspath(__file__))
src = open(os.path.join(HERE, 'test_video_channels.py')).read()
head = src[:src.index('async def rows(pg)')]
head = head.replace("'/tmp/claude-0/t/srv-ch'", "'/tmp/claude-0/t/srv-mref'").replace('8777', '8781')
exec(head)
from playwright.async_api import async_playwright

MT = 'content://com.android.externalstorage.documents/tree/primary%3AMusic'
def song(n):
    size = os.path.getsize(f'/tmp/claude-0/t/srv-mref/m/song{n}.mp3')
    return {'uri': MT + '/document/primary%3AMusic%2Fsong' + str(n) + '.mp3', 'name': f'song{n}.mp3', 'relPath': f'Music/song{n}.mp3',
            'type': 'audio/mpeg', 'size': size, 'lastModified': 1000 + n}
VT = 'content://com.android.externalstorage.documents/tree/primary%3AVideos'
def vid(rel):
    return {'uri': VT + '/document/' + rel.replace('/', '%2F'), 'name': rel.split('/')[-1], 'relPath': rel, 'type': '', 'video': True, 'size': 900000000, 'lastModified': 5}
V1 = [vid('Videos/Inception.2010.mkv'), vid('Videos/The.Matrix.1999.mp4')]
V2 = [vid('Videos/Inception.2010.mkv'), vid('Videos/Arrival.2016.mkv')]
EXT = """
(function(){ var P=window.Capacitor.Plugins.AmplifyPlayer;
  var FIRST=%s, SECOND=%s, V1=%s, V2=%s; window.__mscan=0; window.__vscan=0; window.__opened=[];
  window.Capacitor.convertFileSrc=function(u){ var m=/song(\\d)\\.mp3$/.exec(decodeURIComponent(u)); if(m) return '/m/song'+m[1]+'.mp3'; return u; };
  window.open=function(u){ window.__opened.push(u); return null; };
  window.Capacitor.Plugins.AmplifyPlayer=new Proxy({}, {get:function(t,k){
    if(k==='pickMusicFolder') return function(){ return Promise.resolve({folder:'Music', treeUri:'%s', files:FIRST}); };
    if(k==='rescanMusicFolder') return function(a){ window.__mscan++; return Promise.resolve({folder:'Music', treeUri:a.treeUri, files:SECOND}); };
    if(k==='pickVideoFolder') return function(){ return Promise.resolve({folder:'Videos', treeUri:'%s', files:V1}); };
    if(k==='rescanVideoFolder') return function(a){ window.__vscan++; return Promise.resolve({folder:'Videos', treeUri:a.treeUri, files:V2}); };
    if(k==='videoInfo') return function(){ return Promise.resolve({duration:6000000,width:1920,height:1080}); };
    return P[k]; }});
})();
""" % (json.dumps([song(1), song(2)]), json.dumps([song(2), song(3)]), json.dumps(V1), json.dumps(V2), MT, VT)

async def status(pg):
    return await pg.evaluate("(window.__status||[]).slice(-1)[0] || ''")
async def watch_status(pg):
    await pg.evaluate("""(()=>{ if(window.__statusObs) return; window.__status=[]; var el=document.getElementById('statusLineText');
      window.__statusObs=new MutationObserver(function(){ var t=el.textContent.trim(); if(t) window.__status.push(t); });
      window.__statusObs.observe(el,{childList:true,characterData:true,subtree:true}); })()""")
async def song_count(pg):
    return await pg.evaluate("(()=>{var t=Array.prototype.find.call(document.querySelectorAll('#stationsGrid .tile[data-entity=library-section]'),function(x){return /Songs/.test(x.textContent);});return t?t.querySelector('.tile-sub').textContent:null;})()")

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
        ctx = await b.new_context(viewport={'width': 390, 'height': 844}, device_scale_factor=2, is_mobile=True, has_touch=True, color_scheme='dark', locale='en-US')
        await ctx.add_init_script(MOCK)
        await ctx.add_init_script(EXT)
        pg = await ctx.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e) + ' @ ' + (e.stack or '')[:300]))
        pg.on('dialog', lambda d: asyncio.ensure_future(d.accept()))
        await pg.route('**/*', route)
        await pg.goto('http://127.0.0.1:8781/index.html'); await pg.wait_for_timeout(2500)

        await watch_status(pg)
        # ---- music
        await pg.evaluate("document.querySelector('.mobile-nav-btn[data-nav=library]').click()"); await pg.wait_for_timeout(700)
        vis = await pg.evaluate("(()=>{var r=document.getElementById('libraryRefreshHeaderBtn'), a=document.getElementById('libraryAddHeaderBtn');return [getComputedStyle(r).display!=='none', !!(r.compareDocumentPosition(a) & Node.DOCUMENT_POSITION_FOLLOWING)];})()")
        check(all(vis), f'My Library has a refresh button beside + {vis}')
        await pg.evaluate("document.getElementById('libraryAddHeaderBtn').click()"); await pg.wait_for_timeout(300)
        await pg.evaluate("document.getElementById('addMusicFolderBtn').click()"); await pg.wait_for_timeout(4000)
        await pg.evaluate("document.querySelector('.mobile-nav-btn[data-nav=library]').click()"); await pg.wait_for_timeout(700)
        c1 = await song_count(pg)
        folders = await pg.evaluate("localStorage.getItem('radioPlayerMusicFolders')")
        check(c1 and c1.startswith('2') and 'primary%3AMusic' in (folders or ''), f'a picked music folder is imported and remembered ({c1}) {folders}')
        await pg.screenshot(path=f'{SHOTS}/mref-library.png')
        await pg.evaluate("document.getElementById('libraryRefreshHeaderBtn').click()"); await pg.wait_for_timeout(4500)
        st = await status(pg)
        await pg.evaluate("document.querySelector('.mobile-nav-btn[data-nav=library]').click()"); await pg.wait_for_timeout(700)
        c2 = await song_count(pg)
        check(c2 and c2.startswith('2') and await pg.evaluate("window.__mscan") == 1, f'Refresh: song1 gone from the folder is removed, song3 added (still 2) ({c2})')
        check('1 new song added' in st and '1 song removed' in st, f'Refresh says what changed ({st!r})')
        await pg.evaluate("document.getElementById('libraryRefreshHeaderBtn').click()"); await pg.wait_for_timeout(2500)
        st = await status(pg)
        check('up to date' in st, f'Refresh again: nothing changed ({st!r})')
        # songs list names
        # ---- video
        await pg.evaluate("document.querySelector('.mobile-nav-btn[data-nav=video]').click()"); await pg.wait_for_timeout(600)
        rv = await pg.evaluate("getComputedStyle(document.getElementById('videoRefreshHeaderBtn')).display")
        check(rv == 'none', f'no refresh on the Channels tab ({rv})')
        gap = await pg.evaluate("(()=>{var t=document.querySelector('.video-tabs').getBoundingClientRect();var n=document.querySelector('.video-tabs').nextElementSibling;return n?Math.round(n.getBoundingClientRect().top - t.bottom):null;})()")
        check(gap is not None and gap >= 24, f'space under the tabs, Channels tab ({gap}px)')
        await pg.screenshot(path=f'{SHOTS}/mref-channels.png')
        await pg.evaluate("document.querySelector('.video-tabs [data-vtab=movies]').click()"); await pg.wait_for_timeout(300)
        await pg.evaluate("document.getElementById('videoAddHeaderBtn').click()"); await pg.wait_for_timeout(1200)
        gap = await pg.evaluate("(()=>{var t=document.querySelector('.video-tabs').getBoundingClientRect();var n=document.querySelector('.video-tabs').nextElementSibling;return Math.round(n.getBoundingClientRect().top - t.bottom);})()")
        check(gap >= 24, f'space under the tabs, Movies tab ({gap}px)')
        vis = await pg.evaluate("(()=>{var r=document.getElementById('videoRefreshHeaderBtn'), a=document.getElementById('videoAddHeaderBtn');return [getComputedStyle(r).display!=='none', !!(r.compareDocumentPosition(a) & Node.DOCUMENT_POSITION_FOLLOWING)];})()")
        check(all(vis), f'Movies has a refresh button beside + {vis}')
        await pg.screenshot(path=f'{SHOTS}/mref-movies.png')
        await pg.evaluate("document.getElementById('videoRefreshHeaderBtn').click()"); await pg.wait_for_timeout(1200)
        st = await status(pg)
        mv = await pg.evaluate("Array.prototype.map.call(document.querySelectorAll('#stationsGrid .tile.vposter .tile-name'),function(t){return t.textContent;})")
        check(sorted(mv) == ['Arrival', 'Inception'] and '1 new video added' in st and '1 video removed' in st, f'Refresh on Movies: Matrix gone, Arrival added ({st!r}) {mv}')
        await pg.evaluate("document.querySelector('.video-tabs [data-vtab=shows]').click()"); await pg.wait_for_timeout(300)
        rv = await pg.evaluate("getComputedStyle(document.getElementById('videoRefreshHeaderBtn')).display")
        gap = await pg.evaluate("(()=>{var t=document.querySelector('.video-tabs').getBoundingClientRect();var n=document.querySelector('.video-tabs').nextElementSibling;return Math.round(n.getBoundingClientRect().top - t.bottom);})()")
        check(rv != 'none' and gap >= 24, f'TV Shows: refresh button, space under the tabs ({rv}, {gap}px)')
        await pg.screenshot(path=f'{SHOTS}/mref-shows.png')
        # ---- poster search carries the title
        await pg.evaluate("document.querySelector('.video-tabs [data-vtab=movies]').click()"); await pg.wait_for_timeout(300)
        await pg.evaluate("Array.prototype.find.call(document.querySelectorAll('#stationsGrid .tile.vposter'),function(t){return t.querySelector('.tile-name').textContent==='Inception';}).click()"); await pg.wait_for_timeout(500)
        await pg.evaluate("document.querySelector('.vd-actions .vd-more').click()"); await pg.wait_for_timeout(200)
        await pg.evaluate("Array.prototype.find.call(document.querySelectorAll('.v-menu .np-menu-item'),function(b){return b.textContent==='Change Poster';}).click()"); await pg.wait_for_timeout(300)
        await pg.evaluate("document.getElementById('artUrlSearchBtn').click()"); await pg.wait_for_timeout(200)
        op = await pg.evaluate("window.__opened.slice(-1)[0]")
        check(op and 'Inception%202010%20movie%20poster' in op, f'Search Google looks up the movie poster ({op})')
        check(not errs, f'no page errors {errs[:3]}')
        await b.close()
    print('ALL PASSED' if not fails else f'FAILED {fails}')
asyncio.run(main())
