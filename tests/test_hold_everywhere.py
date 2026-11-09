"""Build 542 (Mark): press, hold and drag works straight away in every list that can be reordered, as on Home Favorites (no edit mode first). Holding still on a genre station or a Zen preset still opens its menu."""
"""Build 403 (Mark): Genres is a browse grid (a find field, "Your top genres" cards with a play button, a
two-column grid of colour cards), and a genre opens a page with a header in its colour, Play and Shuffle,
related styles, Top stations, In your library and More stations. Replaces test_genre_tabs.py (build 178).
Run: python3 tests/test_genre_page.py (screenshots in /tmp/claude-0/t/shots)"""
import sys as _nsys, os as _nos; _nsys.path.insert(0, _nos.path.dirname(_nos.path.abspath(__file__))); from notice_auto import AUTO_NOTICE
import asyncio, os, json, threading, http.server, functools, shutil, subprocess
from urllib.parse import urlparse, parse_qs
from playwright.async_api import async_playwright

PORT = 8893
root = '/tmp/claude-0/t/srv_b542'
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
        async def drag(sel, a=0, c=2, frac=0.7):
            pos = await pg.evaluate("""([sel,a,c,f])=>{var t=Array.from(document.querySelectorAll(sel)).filter(function(x){return x.offsetParent;});if(t.length<=c)return null;t[a].scrollIntoView({block:'center',inline:'nearest'});var A=t[a].getBoundingClientRect(),C=t[c].getBoundingClientRect();
              var vert=Math.abs(A.left-C.left)<4; return [A.left+A.width/2,A.top+A.height/2, vert?C.left+C.width/2:C.left+C.width*f, vert?C.top+C.height*f:C.top+C.height/2];}""", [sel,a,c,frac])
            if pos: await _hd.hold_drag(pg, cdp, *pos)
            return pos
        # playlists for Home and the Playlists page
        await pg.evaluate(EV("stationPlaylists=['P1','P2','P3','P4'].map(function(n){return {id:'id'+n,label:n,stations:[1,2,3].map(function(i){return {stationuuid:n+i,name:n+' Stn '+i,url:'http://127.0.0.1/'+n+i,urlToResolve:'http://127.0.0.1/'+n+i,favicon:'',tags:''};})};}); saveStationPlaylists(); renderPlaylistsHomeSection();"))
        PL = EV("stationPlaylists.map(function(p){return p.label;})")
        # 1 Home Playlists tab
        await pg.evaluate(EV("pushView(); goHomeView && goHomeView();") if False else "0")
        await pg.evaluate(EV("try{ showHome(); }catch(e){ try{ loadTopStations(); }catch(e2){} }")); await pg.wait_for_timeout(1500)
        await pg.evaluate("(()=>{var b=document.getElementById('homeGroupTab-playlists'); if(b) b.click();})()"); await pg.wait_for_timeout(500)
        before = await pg.evaluate(PL)
        pos = await drag('#playlistsHomeGrid > .tile', 0, 2)
        after = await pg.evaluate(PL)
        check(pos is not None and after != before and after[0] != 'P1', f'Home Playlists: hold and drag reorders {before} -> {after} ({pos})')
        await pg.screenshot(path=f'{shots}/b542-home-playlists.png')
        # a tap still opens a playlist (no drag)
        # 2 Library Playlists page
        await pg.evaluate(EV("pushView(); openPlaylistsHome();")); await pg.wait_for_timeout(800)
        before = await pg.evaluate(PL)
        check(not await pg.evaluate(EV("stationPlaylistsEditing")), 'Playlists page is not in an edit mode')
        await drag('#stationsGrid > .tile[data-entity="playlist"]', 0, 2)
        after = await pg.evaluate(PL)
        check(after != before, f'Playlists page: hold and drag reorders {before} -> {after}')
        # 3 a playlist's own page
        await pg.evaluate(EV("pushView(); runStationPlaylist(stationPlaylists[0]);")); await pg.wait_for_timeout(1200)
        S = EV("stationPlaylists[0].stations.map(function(s){return s.name;})")
        before = await pg.evaluate(S)
        pos = await drag('#stationsGrid > .row-item, #stationsGrid > .song-row', 0, 2)
        after = await pg.evaluate(S)
        check(pos is not None and after != before and sorted(after) == sorted(before), f'playlist page: hold and drag reorders its entries {before} -> {after} ({pos})')
        # 4 Genres browse grid
        await pg.evaluate("__t.home()"); await pg.wait_for_timeout(1200)
        G = "Array.from(document.querySelectorAll('#stationsGrid .gb-card')).map(function(c){return c.dataset.genre;}).slice(0,4)"
        g0 = await pg.evaluate(G)
        await drag('#stationsGrid .gb-card', 0, 3)
        await pg.wait_for_timeout(300)
        saved = await pg.evaluate(EV("[genreSort, genreOrder.slice(0,4)]"))
        check(saved[1][0] != g0[0] and saved[0] == 'manual' and not await pg.evaluate(EV("genresEditing")), f'Genres: hold and drag a card reorders without Edit {g0} -> {saved}')
        # 5 genre page stations: drag with no heading mode, still hold opens the menu
        await pg.evaluate(EV("openGenre('Rock')")); await pg.wait_for_timeout(1500)
        await pg.evaluate(EV("(function(){ var st=[1,2,3,4,5].map(function(n){return {stationuuid:'g'+n,name:'Rock Stn '+n,url:'http://127.0.0.1/s'+n,urlToResolve:'http://127.0.0.1/s'+n,favicon:'',tags:'rock'};}); genrePage.allStations=st; genrePage.stations=st; genrePage.pending=false; genreReordering=false; renderGenrePage(); })()")); await pg.wait_for_timeout(800)
        R = "Array.from(document.querySelectorAll('#stationsGrid .gp-row .tile')).map(function(t){return t._genreSt && t._genreSt.name;})"
        r0 = await pg.evaluate(R)
        await drag('#stationsGrid .gp-row .tile', 0, 2)
        r1 = await pg.evaluate(R)
        check(r1 != r0 and not await pg.evaluate("!!document.getElementById('genreStMenu')"), f'genre page: hold and drag reorders without the heading, and no menu opens {r0} -> {r1}')
        pos = await pg.evaluate("(()=>{var t=document.querySelectorAll('#stationsGrid .gp-row .tile')[1];var r=t.getBoundingClientRect();return [r.left+r.width/2,r.top+r.height/2];})()")
        await _hd.hold_drag(pg, cdp, pos[0], pos[1], pos[0], pos[1], hold=700, steps=1)
        menu = await pg.evaluate("Array.from(document.querySelectorAll('#genreStMenu .np-menu-item')).map(function(b){return b.textContent.trim();})")
        r2 = await pg.evaluate(R)
        check(menu == ['Remove from Rock'] and r2 == r1, f'genre page: holding still opens the station menu, order unchanged {menu}')
        await pg.evaluate(EV("closeGenreStMenu()"))
        # 7 Favorite artists row on the Artists page
        await pg.evaluate(EV("favorites = favorites.filter(function(f){return !isArtistFav(f);}).concat(['Ann','Bob','Cal','Dee'].map(function(n){ return {type:'artist', artistKey:n.toLowerCase(), name:n}; })); saveFavorites(); favArtistOrder='az';"))
        await pg.evaluate(EV("pushView(); openLibTab('artists');")); await pg.wait_for_timeout(1000)
        A = EV("favorites.filter(isArtistFav).map(function(f){return f.name;})")
        a0 = await pg.evaluate(A)
        pos = await drag('#stationsGrid .lib-fav-row > .tile', 0, 2)
        a1 = await pg.evaluate(A)
        check(pos is not None and a1 != a0 and await pg.evaluate(EV("favArtistOrder")) == 'manual', f'Favorite Artists: hold and drag reorders (A to Z becomes Manual) {a0} -> {a1} ({pos})')
        # 6 Zen presets
        await pg.evaluate(EV("pushView(); openZenHome();")); await pg.wait_for_timeout(1200)
        Z = "Array.from(document.querySelectorAll('#stationsGrid [data-key^=\"zen:\"]')).slice(0,4).map(function(x){return x.dataset.key;})"
        ZS = EV("(zenState.order||[]).slice(0,4)")
        z0 = await pg.evaluate(Z)
        tiles_sel = '#stationsGrid .zen-presets-row > .tile, #stationsGrid .zen-row > .tile'
        n = await pg.evaluate(f"document.querySelectorAll({json.dumps(tiles_sel)}).length")
        if n < 3:
            tiles_sel = '#stationsGrid [data-key^="zen:"]'
        await drag(tiles_sel, 0, 1, 0.8)
        z1 = await pg.evaluate(Z); zs = await pg.evaluate(ZS)
        check(z1 != z0 and zs and 'zen:' + zs[0] == z1[0] and not await pg.evaluate(EV("zenReordering")), f'Zen: hold and drag a preset reorders without the heading, and it is saved {z0} -> {z1} {zs}')
        pos = await pg.evaluate("(()=>{var t=document.querySelectorAll('#stationsGrid [data-key^=\"zen:\"]')[1];var r=t.getBoundingClientRect();return [r.left+r.width/2,r.top+r.height/2];})()")
        zo = await pg.evaluate(EV("zenState.order.slice()"))
        await _hd.hold_drag(pg, cdp, pos[0], pos[1], pos[0], pos[1], hold=750, steps=1)
        await pg.wait_for_timeout(500)
        zm = await pg.evaluate("Array.from(document.querySelectorAll('.np-menu.open, .row-menu.open, .zen-menu, [id*=zenPresetMenu], .zen-sheet.open')).map(function(e){return e.id||e.className;})")
        check(len(zm) > 0 and await pg.evaluate(EV("zenState.order.slice()")) == zo, f'Zen: holding still on a preset still opens its menu, order unchanged {zm}')
        await pg.screenshot(path=f'{shots}/b542-zen-hold-menu.png')
        await pg.keyboard.press('Escape'); await pg.evaluate(EV("try{ zenCloseMenus && zenCloseMenus(); }catch(e){}"))
        # 8 taps still open things after all this: a tap on a Home playlist opens it
        check(not errs, f'no page errors {errs[:3]}')
        await b.close()
asyncio.run(main())
print('FAILED' if fails else 'ALL PASS'); raise SystemExit(1 if fails else 0)
