"""Build 504: carousel progress inside, tighter Home, Zen preset save/restore, Presets heading reorder."""
"""Build 403 (Mark): Genres is a browse grid (a find field, "Your top genres" cards with a play button, a
two-column grid of colour cards), and a genre opens a page with a header in its colour, Play and Shuffle,
related styles, Top stations, In your library and More stations. Replaces test_genre_tabs.py (build 178).
Run: python3 tests/test_genre_page.py (screenshots in /tmp/claude-0/t/shots)"""
import sys as _nsys, os as _nos; _nsys.path.insert(0, _nos.path.dirname(_nos.path.abspath(__file__))); from notice_auto import AUTO_NOTICE
import asyncio, os, json, threading, http.server, functools, shutil, subprocess
from urllib.parse import urlparse, parse_qs
from playwright.async_api import async_playwright

PORT = 8899
root = '/tmp/claude-0/t/srv_b504r'
shots = '/tmp/claude-0/t/shots'
os.makedirs(shots, exist_ok=True)
shutil.rmtree(root, ignore_errors=True); os.makedirs(root)
HOOK = ("window.__t = { tracks: function(){ return libraryTracks.map(function(t){ return t.name; }); },"
        " genre: function(g){ searchByTag(g); }, home: function(){ openGenresHome(); }, ev: function(js){ return eval(js); },"
        " q: function(){ return { list: playQueue.map(function(s){ return s.name; }), label: queueLabel, cur: currentStation && currentStation.name }; } };\n")
_src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'www', 'index.html')).read()
_mark = '  var coverFlow = null;\n'
assert _src.count(_mark) == 1
open(root + '/index.html', 'w').write(_src.replace(_mark, _mark + HOOK))
M = root + '/Music'; os.makedirs(M)
SONGS = [('Ann One','Ann','Rock'),('Ann Two','Ann','Rock'),('Ann Three','Ann','Synthpop'),
 ('Bob One','Bob','Hip-Hop'),('Bob Two','Bob','Hip-Hop'),('Cal One','Cal','Trip-Hop'),('Cal Two','Cal','Trip-Hop'),
 ('Dee One','Dee','Synthpop'),('Dee Two','Dee','Synthpop'),('Dee Three','Dee','Trip-Hop'),('Eve One','Eve',''),('Eve Two','Eve','')]
for i,(t,a,g) in enumerate(SONGS):
    meta=['-metadata',f'title={t}','-metadata',f'artist={a}','-metadata',f'album={a} LP']+(['-metadata',f'genre={g}'] if g else [])
    subprocess.run(['ffmpeg','-loglevel','error','-y','-f','lavfi','-i',f'sine=frequency={300+i*20}:duration=3','-c:a','libmp3lame','-b:a','32k']+meta+[f'{M}/{i:02d}.mp3'],check=True)
class Q(http.server.SimpleHTTPRequestHandler):
    def log_message(self,*a): pass
srv = http.server.ThreadingHTTPServer(('127.0.0.1', PORT), functools.partial(Q, directory=root))
threading.Thread(target=srv.serve_forever, daemon=True).start()
files = [{'uri': f'http://127.0.0.1:{PORT}/Music/{f}', 'name': f, 'relPath': f'Music/{f}', 'type': 'audio/mpeg','size': os.path.getsize(f'{M}/{f}'), 'lastModified': 1700000000000} for f in sorted(os.listdir(M))]
MOCK = """(function(){ var picked = %s, listeners = {}, cur = null;
 function emit(n, ev){ (listeners[n] || []).forEach(function(f){ try{ f(ev); }catch(e){} }); }
 var impl = { pickMusicFolder: function(){ return Promise.resolve({folder:'Music', files:picked, truncated:false}); },
   cacheCheck: function(){ return Promise.resolve({ url: 'file:///cache/x.mp3' }); },
   load: function(o){ cur = o.id; setTimeout(function(){ emit('state', { id: cur, state: 'ready', isPlaying: true, playWhenReady: true, position: 0, duration: 3 }); }, 20); return Promise.resolve({}); },
   addListener: function(n, f){ (listeners[n] = listeners[n] || []).push(f); return Promise.resolve({remove:function(){}}); } };
 var P = new Proxy({}, {get:function(t,k){ if(k==='then') return undefined; if(k==='setCarLibraryPart') return undefined; if(impl[k]) return impl[k]; return function(){ return Promise.resolve({}); }; }});
 window.Capacitor = { isNativePlatform:function(){return true;}, getPlatform:function(){return 'android';}, registerPlugin:function(){ return P; }, Plugins:{AmplifyPlayer:P}, convertFileSrc:function(u){return u;} };
})();""" % json.dumps(files)
fails = []
def check(c,m):
    print(('PASS ' if c else 'FAIL ')+m)
    if not c: fails.append(m)
mbcalls=[]
async def route(r):
    u=r.request.url
    if '127.0.0.1' in u: return await r.continue_()
    if 'musicbrainz.org' in u:
        mbcalls.append(u)
        if '/artist/?' in u: return await r.fulfill(status=200,content_type='application/json',body=json.dumps({'artists':[{'id':'e1','name':'Eve','score':100}]}))
        return await r.fulfill(status=200,content_type='application/json',body=json.dumps({'genres':[{'name':'new wave','count':5},{'name':'synth-pop','count':3}]}))
    if '/json/' in u: return await r.fulfill(status=200,content_type='application/json',body='[]')
    return await r.abort()
async def load(pg):
    await pg.goto(f'http://127.0.0.1:{PORT}/index.html'); await pg.wait_for_timeout(2500)
    await pg.evaluate("""(function(){ var ov=document.getElementById('addMusicOverlay'); if(ov) ov.classList.add('open');
      var btn=document.getElementById('addMusicFolderBtn'); btn.disabled=false; btn.click(); })()""")
    for _ in range(80):
        await pg.wait_for_timeout(500)
        if len(await pg.evaluate('__t.tracks()')) >= 12: break
    await pg.wait_for_timeout(1200)
    await pg.evaluate("try{ document.getElementById('addMusicOverlay').classList.remove('open'); hideImportPanel(); setStatus('', false); }catch(e){}")

import hold_drag as _hd
def EV(js): return "__t.ev(" + json.dumps(js) + ")"
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        ctx = await b.new_context(viewport={'width':390,'height':844}, device_scale_factor=2, is_mobile=True, has_touch=True, color_scheme='dark')
        await ctx.add_init_script(MOCK); await ctx.add_init_script(AUTO_NOTICE)
        pg = await ctx.new_page(); errs=[]; pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.route('**/*', route); await load(pg)
        cdp = await ctx.new_cdp_session(pg)
        # --- Genres: the heading is the way in
        await pg.evaluate("__t.home()"); await pg.wait_for_timeout(1200)
        st = await pg.evaluate("(()=>{var h=document.querySelector('#stationsGrid .gb-head-toggle'),e=document.querySelector('#stationsGrid .gb-edit');return {text:h&&h.textContent,edit:!e||getComputedStyle(e).display==='none'};})()")
        print(st)
        check(st['text']=='Browse categories' and st['edit'], f'Genres heading is the toggle and the Edit button is hidden {st}')
        await pg.screenshot(path=f'{shots}/b504-genres-heading.png')
        await pg.evaluate("document.querySelector('#stationsGrid .gb-head-toggle').click()"); await pg.wait_for_timeout(600)
        check(await pg.evaluate(EV("genresEditing")), 'heading tap starts reordering Genres')
        await pg.screenshot(path=f'{shots}/b504-genres-reorder.png')
        names0 = await pg.evaluate("Array.from(document.querySelectorAll('#stationsGrid .gb-card, #stationsGrid .tile')).map(function(c){return c.dataset.genre||c.dataset.key;}).slice(0,4)")
        print(names0)
        pos = await pg.evaluate("(()=>{var t=Array.from(document.querySelectorAll('#stationsGrid .gb-card, #stationsGrid .tile'));var a=t[0].getBoundingClientRect(),c=t[3].getBoundingClientRect();return [a.left+a.width/2,a.top+a.height/2,c.left+c.width/2,c.top+c.height*0.7];})()")
        await _hd.hold_drag(pg, cdp, pos[0], pos[1], pos[2], pos[3])
        names1 = await pg.evaluate("Array.from(document.querySelectorAll('#stationsGrid .gb-card, #stationsGrid .tile')).map(function(c){return c.dataset.genre||c.dataset.key;}).slice(0,4)")
        print(names1)
        check(names1 != names0, f'press, hold and drag reorders genres {names0} -> {names1}')
        await pg.evaluate("document.querySelector('#stationsGrid .gb-head-toggle').click()"); await pg.wait_for_timeout(400)
        check(not await pg.evaluate(EV("genresEditing")), 'tap again finishes')
        # --- genre page: stations
        await pg.evaluate(EV("openGenre('Rock')")); await pg.wait_for_timeout(1500)
        await pg.evaluate(EV("(function(){ var st=[1,2,3,4,5].map(function(n){return {stationuuid:'g'+n,name:'Rock Stn '+n,url:'http://127.0.0.1/s'+n,urlToResolve:'http://127.0.0.1/s'+n,favicon:'',tags:'rock'};}); genrePage.allStations=st; genrePage.stations=st; genrePage.pending=false; renderGenrePage(); })()")); await pg.wait_for_timeout(800)
        st = await pg.evaluate("(()=>{var h=document.getElementById('stationsHeading');return {re:h.classList.contains('reorderable'),t:h.textContent};})()")
        check(st['re'], f'genre heading is reorderable {st}')
        await pg.evaluate("document.getElementById('stationsHeading').click()"); await pg.wait_for_timeout(600)
        await pg.screenshot(path=f'{shots}/b504-genre-reorder.png')
        row0 = await pg.evaluate("Array.from(document.querySelectorAll('#stationsGrid .gp-row .tile')).map(function(t){return t._genreSt && t._genreSt.name;})")
        pos = await pg.evaluate("(()=>{var t=Array.from(document.querySelectorAll('#stationsGrid .gp-row .tile'));t[0].scrollIntoView({block:'center'});var a=t[0].getBoundingClientRect(),c=t[2].getBoundingClientRect();return [a.left+a.width/2,a.top+a.height*0.35,c.left+c.width*0.8,c.top+c.height*0.35];})()")
        await _hd.hold_drag(pg, cdp, pos[0], pos[1], pos[2], pos[3])
        row1 = await pg.evaluate("Array.from(document.querySelectorAll('#stationsGrid .gp-row .tile')).map(function(t){return t._genreSt && t._genreSt.name;})")
        print(row0,row1)
        check(row1 != row0 and row1[0] != row0[0], f'genre stations reorder by hold and drag {row1}')
        saved = await pg.evaluate(EV("genrePref('Rock').order.length"))
        check(saved == 5, f'order saved per genre {saved}')
        # long-press menu no longer has Move items
        await pg.evaluate("document.getElementById('stationsHeading').click()"); await pg.wait_for_timeout(500)
        await pg.evaluate(EV("openGenreStMenu(Array.from(document.querySelectorAll('#stationsGrid .gp-row .tile'))[1])")); await pg.wait_for_timeout(300)
        labels = await pg.evaluate("Array.from(document.querySelectorAll('#genreStMenu .np-menu-item')).map(function(b){return b.textContent;})")
        check(labels and not any('Move' in l for l in labels), f'menu has no Move items {labels}')
        check(not errs, f'no page errors {errs[:3]}')
        await b.close()
asyncio.run(main())
print('FAILED' if fails else 'ALL PASS'); raise SystemExit(1 if fails else 0)
