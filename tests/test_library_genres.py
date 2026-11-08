"""Build 501: library genres join the Genres list; artist genre tags."""
"""Build 403 (Mark): Genres is a browse grid (a find field, "Your top genres" cards with a play button, a
two-column grid of colour cards), and a genre opens a page with a header in its colour, Play and Shuffle,
related styles, Top stations, In your library and More stations. Replaces test_genre_tabs.py (build 178).
Run: python3 tests/test_genre_page.py (screenshots in /tmp/claude-0/t/shots)"""
import sys as _nsys, os as _nos; _nsys.path.insert(0, _nos.path.dirname(_nos.path.abspath(__file__))); from notice_auto import AUTO_NOTICE
import asyncio, os, json, threading, http.server, functools, shutil, subprocess
from urllib.parse import urlparse, parse_qs
from playwright.async_api import async_playwright

PORT = 8894
root = '/tmp/claude-0/t/srv_libgenres'
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
CARDS="Array.from(document.querySelectorAll('#stationsGrid .gb-card')).map(function(c){return c.dataset.genre;})"
CHIPS="(()=>{var b=document.getElementById('artistGenres');return {shown:!!b,chips:b?Array.from(b.querySelectorAll('.artist-genre-chip')).map(function(c){return c.textContent;}):[]};})()"
async def run(b, scheme, w, h):
    T=f'[{scheme} {w}]'
    ctx = await b.new_context(viewport={'width': w, 'height': h}, device_scale_factor=2, is_mobile=w < 900, has_touch=w < 900, color_scheme=scheme)
    await ctx.add_init_script(MOCK); await ctx.add_init_script(AUTO_NOTICE)
    await ctx.add_init_script("try{ localStorage.setItem('radioPlayerTheme', %s); }catch(e){}" % json.dumps(scheme))
    pg = await ctx.new_page(); errs=[]; pg.on('pageerror', lambda e: errs.append(str(e)))
    await pg.route('**/*', route)
    await load(pg)
    await pg.evaluate("__t.home()"); await pg.wait_for_timeout(900)
    cards = await pg.evaluate(CARDS)
    heads = await pg.evaluate("Array.from(document.querySelectorAll('#stationsGrid .gb-head')).map(function(h){return h.textContent;})")
    check('Synthpop' in cards and 'Trip-Hop' in cards, f'{T} library genres are cards in the one list {cards}')
    check(cards.count('Hip Hop')==1 and 'Hip-Hop' not in cards and 'Rock' in cards and 'Jazz' in cards, f'{T} built-ins stay, Hip-Hop merges into Hip Hop')
    check(not any('library' in x.lower() for x in heads), f'{T} no separate section {heads}')
    check('New Wave' not in cards, f'{T} an untagged artist adds no genre yet')
    await pg.screenshot(path=f'{shots}/libgenres-list-{scheme}-{w}.png')
    await pg.evaluate("__t.ev(\"openArtistPage(artistMatchKey('Ann'))\")"); await pg.wait_for_timeout(1500)
    c = await pg.evaluate(CHIPS)
    check(c['shown'] and c['chips']==['Rock','Synthpop'], f'{T} Ann shows her genres {c}')
    geo = await pg.evaluate("""(()=>{var g=document.getElementById('stationsGrid'),labels=Array.from(g.querySelectorAll('.grid-section-label')),al=labels.filter(function(l){return /^Albums/.test(l.textContent);})[0],gh=labels.filter(function(l){return /^Genres/.test(l.textContent);})[0],box=g.querySelector('.artist-albums'),ch=document.getElementById('artistGenres');
      var gcs=gh?getComputedStyle(gh):null,acs=al?getComputedStyle(al):null;
      return {hasHero:!!document.getElementById('artistHeroGenres'),below:!!(gh&&box&&gh.getBoundingClientRect().top>=box.getBoundingClientRect().bottom),chipsUnder:!!(gh&&ch&&ch.getBoundingClientRect().top>=gh.getBoundingClientRect().bottom),
        same:!!(gcs&&acs&&gcs.fontSize===acs.fontSize&&gcs.fontWeight===acs.fontWeight&&gcs.color===acs.color),last:g.lastElementChild===ch,inside:!!ch&&ch.getBoundingClientRect().right<=innerWidth,sw:document.documentElement.scrollWidth,vw:innerWidth};})()""")
    check(not geo['hasHero'] and geo['below'] and geo['chipsUnder'] and geo['same'] and geo['last'] and geo['inside'] and geo['sw']<=geo['vw'], f'{T} Genres heading + tags sit below the albums, styled like Albums {geo}')
    await pg.screenshot(path=f'{shots}/libgenres-artist-{scheme}-{w}.png')
    await pg.evaluate("document.getElementById('artistGenres').scrollIntoView({block:'center'})"); await pg.wait_for_timeout(500)
    await pg.screenshot(path=f'{shots}/libgenres-artist-bottom-{scheme}-{w}.png')
    await pg.evaluate("document.querySelectorAll('.artist-genre-chip')[1].click()"); await pg.wait_for_timeout(1200)
    gp = await pg.evaluate("""(()=>{var g=document.getElementById('stationsGrid');return {title:(g.querySelector('.gp-title')||{}).textContent,heads:Array.from(g.querySelectorAll('.gp-head')).map(function(h){return h.textContent;}),
      artists:Array.from(g.querySelectorAll('.gp-artists > .tile .tile-name')).map(function(e){return e.textContent;}),songs:Array.from(g.querySelectorAll('.gp-songs .song-row:not(.shuffle-all-row) .song-row-title')).map(function(e){return e.textContent;}),chips:Array.from(g.querySelectorAll('.gp-chip')).map(function(e){return e.textContent;}),sw:document.documentElement.scrollWidth,vw:innerWidth};})()""")
    check(gp['title']=='Synthpop' and gp['artists']==['Dee','Ann'] and sorted(gp['songs'])==['Ann Three','Dee One','Dee Two'] and 'Artists in your library' in gp['heads'], f'{T} Synthpop page {gp}')
    check('Trip-Hop' in gp['chips'] and gp['sw']<=gp['vw'], f'{T} related chips from shared artists')
    await pg.screenshot(path=f'{shots}/libgenres-page-{scheme}-{w}.png')
    await pg.evaluate("document.getElementById('detailBackBtn').click()"); await pg.wait_for_timeout(1000)
    nm = await pg.evaluate("document.getElementById('artistHeroName').textContent")
    check(nm=='Ann', f'{T} Back returns to the artist page ({nm})')
    n0=len(mbcalls)
    await pg.evaluate("__t.ev(\"openArtistPage(artistMatchKey('Eve'))\")"); await pg.wait_for_timeout(6000)
    c = await pg.evaluate(CHIPS)
    check(c['chips']==['New Wave','Synth-Pop'] and len(mbcalls)-n0==2, f'{T} Eve gets genres from MusicBrainz {c} calls {len(mbcalls)-n0}')
    await pg.screenshot(path=f'{shots}/libgenres-eve-{scheme}-{w}.png')
    await pg.evaluate("__t.home()"); await pg.wait_for_timeout(900)
    cards = await pg.evaluate(CARDS)
    check('New Wave' in cards and 'Synth-Pop' in cards, f'{T} her genres join the list {cards[-6:]}')
    await pg.evaluate("__t.ev(\"openArtistPage(artistMatchKey('Eve'))\")"); await pg.wait_for_timeout(1200)
    check(len(mbcalls)-n0==2, f'{T} no second lookup')
    # manual edit: Ann -> remove Synthpop, add Shoegaze
    await pg.evaluate("__t.ev(\"openArtistPage(artistMatchKey('Ann'))\")"); await pg.wait_for_timeout(1500)
    await pg.evaluate("document.getElementById('artistGenresEditBtn').click()"); await pg.wait_for_timeout(500)
    await pg.screenshot(path=f'{shots}/libgenres-edit-{scheme}-{w}.png')
    await pg.evaluate("(()=>{var r=document.querySelectorAll('#genreEditRows .genre-edit-row');r[1].querySelector('.genre-edit-x').click();var i=document.getElementById('genreEditAddInput');i.value='shoegaze';document.getElementById('genreEditAddBtn').click();var r2=document.querySelectorAll('#genreEditRows .genre-edit-input');r2[0].value='Classic Rock';})()")
    await pg.evaluate("document.getElementById('genreEditSaveBtn').click()"); await pg.wait_for_timeout(800)
    c = await pg.evaluate(CHIPS)
    check(c['chips']==['Classic Rock','Shoegaze'], f'{T} manual add/edit/remove {c}')
    await pg.screenshot(path=f'{shots}/libgenres-edited-{scheme}-{w}.png')
    await pg.evaluate("document.querySelectorAll('.artist-genre-chip')[1].click()"); await pg.wait_for_timeout(1200)
    gp = await pg.evaluate("(document.querySelector('#stationsGrid .gp-title')||{}).textContent+'|'+Array.from(document.querySelectorAll('#stationsGrid .gp-songs .song-row:not(.shuffle-all-row) .song-row-title')).map(function(e){return e.textContent;}).sort().join(',')")
    check(gp=='Shoegaze|Ann One,Ann Three,Ann Two', f'{T} manual genre finds all her songs {gp}')
    # rename: Shoegaze -> Dream Pop (manual labels follow)
    await pg.screenshot(path=f'{shots}/libgenres-renamebtn-{scheme}-{w}.png')
    await pg.evaluate("document.getElementById('genreRenameBtn').click()"); await pg.wait_for_timeout(400)
    await pg.screenshot(path=f'{shots}/libgenres-rename-{scheme}-{w}.png')
    await pg.evaluate("(()=>{document.querySelector('#genreEditRows .genre-edit-input').value='Dream Pop';document.getElementById('genreEditSaveBtn').click();})()"); await pg.wait_for_timeout(2500)
    gt = await pg.evaluate("(document.querySelector('#stationsGrid .gp-title')||{}).textContent")
    man = await pg.evaluate("JSON.stringify(artistGenreManual[artistMatchKey('Ann')])" if False else "__t.ev(\"JSON.stringify(artistGenreManual[artistMatchKey('Ann')])\")")
    check(gt=='Dream Pop' and 'Dream Pop' in str(man), f'{T} rename opens the new genre and follows manual genres {gt} {man}')
    await pg.evaluate("__t.home()"); await pg.wait_for_timeout(800)
    cards = await pg.evaluate(CARDS)
    check('Dream Pop' in cards and 'Shoegaze' not in cards, f'{T} renamed genre in the list')
    # sort
    await pg.evaluate("document.querySelector('#stationsGrid .gb-edit').click()"); await pg.wait_for_timeout(700)
    await pg.screenshot(path=f'{shots}/libgenres-sort-{scheme}-{w}.png')
    await pg.evaluate("document.querySelector('#genreSortOpts [data-opt=az]').click()"); await pg.wait_for_timeout(600)
    names = await pg.evaluate("Array.from(document.querySelectorAll('#stationsGrid .tile[data-entity=genre] .tile-name')).map(function(e){return e.textContent;})")
    drag = await pg.evaluate("document.querySelectorAll('#stationsGrid .tile[data-entity=genre][draggable=true], #stationsGrid .tile[data-entity=genre] [draggable=true]').length")
    check(names==sorted(names, key=str.lower) and len(names)>=18 and drag==0, f'{T} A to Z sorts and locks dragging {names[:5]} drag={drag}')
    await pg.evaluate("document.querySelector('#genreSortOpts [data-opt=manual]').click()"); await pg.wait_for_timeout(600)
    drag = await pg.evaluate("document.querySelectorAll('#stationsGrid .tile[data-entity=genre][draggable=true], #stationsGrid .tile[data-entity=genre] [draggable=true]').length")
    check(drag>0, f'{T} Manually allows dragging {drag}')
    # rename a genre carried by song tags: the songs themselves change
    await pg.evaluate("__t.ev(\"openGenre('Trip-Hop')\")"); await pg.wait_for_timeout(1500)
    await pg.evaluate("document.getElementById('genreRenameBtn').click()"); await pg.wait_for_timeout(300)
    await pg.evaluate("(()=>{document.querySelector('#genreEditRows .genre-edit-input').value='Triphop';document.getElementById('genreEditSaveBtn').click();})()"); await pg.wait_for_timeout(5000)
    gs = await pg.evaluate("__t.ev(\"JSON.stringify(libraryTracks.filter(function(t){return /trip/i.test(t.genre||'');}).map(function(t){return t.artist+':'+t.genre;}).sort())\")")
    check('Triphop' in gs and 'Trip-Hop' not in gs, f'{T} rename rewrites the songs\' genre {gs}')
    check(not errs, f'{T} no page errors {errs}')
    await ctx.close()
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        await run(b,'dark',412,900); await run(b,'light',412,900); await run(b,'dark',1280,800)
        await b.close()
asyncio.run(main())
print('FAILS',len(fails)); import sys; sys.exit(1 if fails else 0)
