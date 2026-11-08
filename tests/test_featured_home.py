"""Build 503: Home tabs (Favorites/Playlists/Top 100) and the Featured seasonal card + settings."""
"""Build 403 (Mark): Genres is a browse grid (a find field, "Your top genres" cards with a play button, a
two-column grid of colour cards), and a genre opens a page with a header in its colour, Play and Shuffle,
related styles, Top stations, In your library and More stations. Replaces test_genre_tabs.py (build 178).
Run: python3 tests/test_genre_page.py (screenshots in /tmp/claude-0/t/shots)"""
import sys as _nsys, os as _nos; _nsys.path.insert(0, _nos.path.dirname(_nos.path.abspath(__file__))); from notice_auto import AUTO_NOTICE
import asyncio, os, json, threading, http.server, functools, shutil, subprocess
from urllib.parse import urlparse, parse_qs
from playwright.async_api import async_playwright

PORT = 8897
root = '/tmp/claude-0/t/srv_featured'
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

HOME_JS = "(()=>{var q=function(i){var e=document.getElementById(i);return e&&getComputedStyle(e).display!=='none'&&e.getBoundingClientRect().height>0;};var tabs=Array.from(document.querySelectorAll('#homeGroupTabs .home-tab')).filter(function(b){return b.style.display!=='none';});return {bar:q('homeGroupTabs'),tabs:tabs.map(function(b){return b.textContent+(b.classList.contains('active')?'*':'');}),fav:q('favoritesSection'),pl:q('playlistsHomeSection'),top:q('top100Section'),feat:q('featuredHome'),oldTabs:q('homeTabs')};})()"
def EV(js): return "__t.ev(" + json.dumps(js) + ")"
async def run(b, scheme, w, h):
    T=f'[{scheme} {w}]'
    ctx = await b.new_context(viewport={'width': w, 'height': h}, device_scale_factor=2, is_mobile=w < 900, has_touch=w < 900, color_scheme=scheme)
    await ctx.add_init_script(MOCK); await ctx.add_init_script(AUTO_NOTICE)
    await ctx.add_init_script("try{ localStorage.setItem('radioPlayerTheme', %s); }catch(e){}" % json.dumps(scheme))
    pg = await ctx.new_page(); errs=[]; pg.on('pageerror', lambda e: errs.append(str(e)))
    await pg.route('**/*', route)
    await load(pg)
    await pg.evaluate(EV("applyHomeTab()")); await pg.wait_for_timeout(1200)
    await pg.evaluate(EV("toggleFavorite({name:'Test FM',url:'http://127.0.0.1/x',stationuuid:'t1'}); renderFavoritesSection();")); await pg.wait_for_timeout(600)
    st = await pg.evaluate(HOME_JS)
    print(T, st)
    check(not st['oldTabs'], f'{T} old tab strip stays hidden')
    check(st['bar'] and len(st['tabs'])>=1, f'{T} group tab bar shows {st["tabs"]}')
    if st['tabs']:
        check(st['tabs'][0].endswith('*') or not any(t.startswith('Favorites') for t in st['tabs']), f'{T} Favorites default (or absent when empty)')
        check(sum([st['fav'],st['pl'],st['top']])==1, f'{T} exactly one group section visible')
    # seasons logic
    r = await pg.evaluate(EV("""(()=>{function d(y,m,dd){return new Date(y,m-1,dd,12);}function n(x){var a=activeSeason(x);return a?a.sn.id:null;}
      return {oct:n(d(2026,10,15)),nov:n(d(2026,11,5)),tg:n(d(2026,11,24)),dec:n(d(2026,12,20)),ny:n(d(2027,1,1)),jan:n(d(2027,1,20)),val:n(d(2027,2,10)),pat:n(d(2027,3,15)),easter:n(d(2027,3,22)),apr:n(d(2027,4,25)),jun:n(d(2026,6,10)),j4:n(d(2026,7,2)),aug:n(d(2026,8,20)),sep:n(d(2026,9,20)),eas:easterOf(2027).getMonth()+'-'+easterOf(2027).getDate()};})()"""))
    print(T, r)
    exp={'oct':'halloween','nov':'christmas','tg':'thanksgiving','dec':'christmas','ny':'newyear','jan':None,'val':'valentines','pat':'stpatricks','easter':'easter','apr':None,'jun':'summer','j4':'july4','aug':'summer','sep':None}
    for k,v in exp.items(): check(r[k]==v, f'{T} season {k} -> {r[k]} (want {v})')
    check(r['eas']=='2-28', f'{T} Easter 2027 is Mar 28 {r["eas"]}')
    # card today (Nov 8 real date => Christmas)
    st = await pg.evaluate(HOME_JS)
    check(st['feat'], f'{T} featured card visible')
    txt = await pg.evaluate("document.getElementById('featuredHome').innerText")
    check('Christmas' in txt, f'{T} card text {txt!r}')
    box = await pg.evaluate("(()=>{var f=document.getElementById('featuredHome').getBoundingClientRect(),n=document.getElementById('npHero').getBoundingClientRect(),g=document.getElementById('homeGroupTabs').getBoundingClientRect();return {fh:f.height,belowHero:f.top>=n.bottom-1||n.height===0,aboveTabs:f.bottom<=g.top+1||g.height===0,w:f.width,vw:innerWidth};})()")
    check(box['fh']<150 and box['fh']>80, f'{T} card compact {box}')
    check(box['aboveTabs'], f'{T} card sits above tabs {box}')
    await pg.screenshot(path=f'{shots}/featured-home-{scheme}-{w}.png')
    # tap card opens genre page
    await pg.evaluate("document.querySelector('#featuredHome .fh-card').click()"); await pg.wait_for_timeout(1500)
    t = await pg.evaluate("document.getElementById('stationsGrid').innerText.slice(0,80)")
    check('Christmas' in t, f'{T} card opens Christmas genre page {t!r}')
    await pg.screenshot(path=f'{shots}/featured-genre-{scheme}-{w}.png')
    await pg.evaluate(EV("loadTopStations()")); await pg.wait_for_timeout(4000); print(await pg.evaluate(EV("[onHomeView, document.body.className, document.getElementById(\"featuredHome\").style.display]")))
    # play
    await pg.evaluate("document.querySelector('#featuredHome .fh-play').click()"); await pg.wait_for_timeout(1500)
    q = await pg.evaluate('__t.q()')
    check(q['label'] is not None, f'{T} play sets a queue {q}')
    # hide for season
    await pg.evaluate("document.querySelector('#featuredHome .fh-more').click()"); await pg.wait_for_timeout(500)
    await pg.screenshot(path=f'{shots}/featured-more-{scheme}-{w}.png')
    await pg.evaluate("Array.from(document.querySelectorAll('button')).filter(function(b){return /Hide until next year/.test(b.textContent);})[0].click()"); await pg.wait_for_timeout(600)
    check(not (await pg.evaluate(HOME_JS))['feat'], f'{T} hide removes the card')
    await pg.evaluate(EV("seasonHidden={}; saveSeasonHidden(); renderFeaturedHome();"))
    # settings page
    await pg.evaluate(EV("openSettingsAt('featured')")); await pg.wait_for_timeout(700)
    rows = await pg.evaluate("document.querySelectorAll('#seasonList .season-row').length")
    check(rows==9, f'{T} nine standard seasons listed {rows}')
    await pg.screenshot(path=f'{shots}/featured-settings-{scheme}-{w}.png')
    await pg.evaluate("document.querySelector('#seasonList .season-row[data-id=halloween]').click()"); await pg.wait_for_timeout(500)
    await pg.screenshot(path=f'{shots}/featured-edit-{scheme}-{w}.png')
    # edit: change Christmas end, name; add new; delete
    await pg.evaluate(EV("closeSeasonEdit()"))
    await pg.evaluate("document.querySelector('#seasonList .season-row[data-id=christmas]').click()")
    await pg.fill('#seName','Holiday Cheer'); await pg.select_option('#seED','25'); await pg.select_option('#seEM','12')
    await pg.click('#seSaveBtn'); await pg.wait_for_timeout(500)
    s = await pg.evaluate(EV("seasons.filter(function(x){return x.id==='christmas';})[0]"))
    check(s['name']=='Holiday Cheer' and s['end']=='12-25', f'{T} edit saved {s}')
    await pg.click('#seasonAddBtn'); await pg.fill('#seName','Test Week'); await pg.select_option('#seSM','11'); await pg.select_option('#seSD','1'); await pg.select_option('#seEM','11'); await pg.select_option('#seED','30'); await pg.fill('#seTags','zzz, yyy')
    await pg.click('#seSaveBtn'); await pg.wait_for_timeout(400)
    check(await pg.evaluate(EV("seasons.length"))==10, f'{T} season added')
    check(await pg.evaluate(EV("activeSeason(new Date(2026,10,8,12)).sn.name"))=='Test Week', f'{T} shortest window wins (new 30-day over Christmas)')
    await pg.evaluate("document.querySelector('#seasonList .season-row:last-child').click()"); await pg.evaluate(EV("window.__sn=showNotice; showNotice=function(o){ if(o && o.actions && o.title===\"Delete this season?\") o.actions[o.actions.length-1].run(); return 1; };")); await pg.click('#seDeleteBtn'); await pg.wait_for_timeout(500)
    await pg.evaluate(EV("showNotice=window.__sn;"))
    check(await pg.evaluate(EV("seasons.length"))==9, f'{T} season deleted')
    # off switch
    await pg.evaluate("(function(){var e=document.getElementById('featOnSelect');e.value='off';e.dispatchEvent(new Event('change',{bubbles:true}));})()"); await pg.wait_for_timeout(300)
    await pg.evaluate(EV("closeSettings && closeSettings()")); await pg.evaluate(EV("loadTopStations()")); await pg.wait_for_timeout(1200)
    check(not (await pg.evaluate(HOME_JS))['feat'], f'{T} Featured Off hides the card')
    # persistence
    await pg.reload(); await pg.wait_for_timeout(2500)
    check(await pg.evaluate(EV("seasons.filter(function(x){return x.id==='christmas';})[0].name"))=='Holiday Cheer' and await pg.evaluate(EV("featuredOn"))==False, f'{T} persists across reload')
    check(not errs, f'{T} no page errors {errs[:3]}')
    await ctx.close()
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        for sc,w,h in [('dark',390,844),('light',390,844)]:
            await run(b,sc,w,h)
        await b.close()
asyncio.run(main())
print('FAILED' if fails else 'ALL PASS'); raise SystemExit(1 if fails else 0)
