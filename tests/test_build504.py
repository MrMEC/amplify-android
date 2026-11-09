"""Build 504: carousel progress inside, tighter Home, Zen preset save/restore, Presets heading reorder."""
"""Build 403 (Mark): Genres is a browse grid (a find field, "Your top genres" cards with a play button, a
two-column grid of colour cards), and a genre opens a page with a header in its colour, Play and Shuffle,
related styles, Top stations, In your library and More stations. Replaces test_genre_tabs.py (build 178).
Run: python3 tests/test_genre_page.py (screenshots in /tmp/claude-0/t/shots)"""
import sys as _nsys, os as _nos; _nsys.path.insert(0, _nos.path.dirname(_nos.path.abspath(__file__))); from notice_auto import AUTO_NOTICE
import asyncio, os, json, threading, http.server, functools, shutil, subprocess
from urllib.parse import urlparse, parse_qs
from playwright.async_api import async_playwright

PORT = 8898
root = '/tmp/claude-0/t/srv_b504'
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

def EV(js): return "__t.ev(" + json.dumps(js) + ")"
async def run(b, scheme, w, h):
    T=f'[{scheme} {w}]'
    ctx = await b.new_context(viewport={'width': w, 'height': h}, device_scale_factor=2, is_mobile=True, has_touch=True, color_scheme=scheme)
    await ctx.add_init_script(MOCK); await ctx.add_init_script(AUTO_NOTICE)
    await ctx.add_init_script("try{ localStorage.setItem('radioPlayerTheme', %s); }catch(e){}" % json.dumps(scheme))
    pg = await ctx.new_page(); errs=[]; pg.on('pageerror', lambda e: errs.append(str(e)))
    await pg.route('**/*', route)
    await load(pg)
    await pg.evaluate(EV("toggleFavorite({name:'Test FM',url:'http://127.0.0.1/x',stationuuid:'t1'}); renderFavoritesSection(); zenSelect('campfire', false); zenNote(); zenSelect('rainy-night', false); zenNote(); renderNpHero();")); await pg.wait_for_timeout(1500)
    g = await pg.evaluate("""(()=>{var hero=document.getElementById('npHero'),pr=document.getElementById('npHeroProgress'),f=document.getElementById('featuredHome'),t=document.getElementById('homeGroupTabs');
      var hr=hero.getBoundingClientRect(),pb=pr.getBoundingClientRect(),fr=f.getBoundingClientRect(),tr=t.getBoundingClientRect();
      return {heroShown:hr.height>0,progShown:pb.height>0,inside:pb.top>=hr.top&&pb.bottom<=hr.bottom,gap:Math.round(fr.top-hr.bottom),tabsBottom:Math.round(tr.bottom),vh:innerHeight,tabsTop:Math.round(tr.top)};})()""")
    print(T,g)
    check(g['heroShown'] and g['progShown'] and g['inside'], f'{T} progress bar sits inside the carousel')
    check(g['tabsBottom']<=g['vh']-150, f'{T} tabs visible without scrolling {g}')
    await pg.screenshot(path=f'{shots}/b504-home-{scheme}.png')
    # zen
    await pg.evaluate(EV("pushView(); openLibTab('zen')")); await pg.wait_for_timeout(1500)
    heads = await pg.evaluate("Array.from(document.querySelectorAll('#stationsGrid .gb-head')).map(function(h){return h.textContent;})")
    check('Presets' in heads and not await pg.evaluate("Array.from(document.querySelectorAll('.zen-addbtn')).some(function(b){return /Reorder presets/.test(b.textContent);})"), f'{T} no Reorder presets button {heads}')
    await pg.screenshot(path=f'{shots}/b504-zen-{scheme}.png')
    ids0 = await pg.evaluate(EV("zenAllPresets().map(function(p){return p.id;}).slice(0,4)"))
    await pg.evaluate("document.querySelector('.zen-reorder-head').click()"); await pg.wait_for_timeout(300)
    check(await pg.evaluate(EV("zenReordering")), f'{T} heading tap starts reordering')
    await pg.screenshot(path=f'{shots}/b504-zen-reorder-{scheme}.png')
    # drag first preset onto 3rd position by touch events
    pos = await pg.evaluate("""(()=>{var r=document.querySelector('.zen-row-tiles.zen-reordering'),t=Array.from(r.children).filter(function(x){return x.classList.contains('tile');});t[0].scrollIntoView({block:'center'});var a=t[0].getBoundingClientRect(),c=t[2].getBoundingClientRect();return {ax:a.left+a.width/2,ay:a.top+a.height*0.35,cx:c.left+c.width*0.8,cy:c.top+c.height*0.35};})()""")
    cdp = await ctx.new_cdp_session(pg)
    async def touch(t,x,y): await cdp.send('Input.dispatchTouchEvent',{'type':t,'touchPoints':([{'x':x,'y':y,'id':1}] if t!='touchEnd' else [])})
    await touch('touchStart',pos['ax'],pos['ay']); await pg.wait_for_timeout(650)
    for i in range(1,11): await touch('touchMove',pos['ax']+(pos['cx']-pos['ax'])*i/10,pos['ay']); await pg.wait_for_timeout(30)
    await touch('touchEnd',0,0); await pg.wait_for_timeout(500)
    ids1 = await pg.evaluate(EV("zenAllPresets().map(function(p){return p.id;}).slice(0,4)"))
    check(ids1!=ids0 and ids1[0]!=ids0[0], f'{T} long-press drag reorders presets {ids0} -> {ids1}')
    await pg.evaluate("document.querySelector('.zen-reorder-head').click()")
    # save/restore edit
    await pg.evaluate(EV("zenOpenScreen('rainy-night', false); zenMixOpen = true; zenMix[0].v = .2; zenDirty = true; zenRemember(); zenSyncUi();")); await pg.wait_for_timeout(800)
    check(await pg.evaluate("!!document.getElementById('zenMixSave')"), f'{T} Save changes offered when the mix is edited')
    await pg.screenshot(path=f'{shots}/b504-zen-mixer-{scheme}.png')
    await pg.evaluate("document.getElementById('zenMixSave').click()"); await pg.wait_for_timeout(400)
    v = await pg.evaluate(EV("zenPreset('rainy-night').s[0].v"))
    check(abs(v-.2)<.001 and await pg.evaluate(EV("zenPreset('rainy-night').edited")), f'{T} edit saved {v}')
    await pg.reload(); await pg.wait_for_timeout(2500)
    v = await pg.evaluate(EV("zenPreset('rainy-night').s[0].v"))
    check(abs(v-.2)<.001, f'{T} edit survives restart {v}')
    await pg.evaluate(EV("zenOpenScreen('rainy-night', false); zenMixOpen = true; zenSyncUi();")); await pg.wait_for_timeout(800)
    check(await pg.evaluate("!!document.getElementById('zenMixRestore')"), f'{T} Restore default offered')
    await pg.evaluate("document.getElementById('zenMixRestore').click()"); await pg.wait_for_timeout(400)
    v = await pg.evaluate(EV("zenPreset('rainy-night').s[0].v"))
    check(abs(v-.7)<.001 and not await pg.evaluate(EV("zenPreset('rainy-night').edited")), f'{T} restored to default {v}')
    check(not errs, f'{T} no page errors {errs[:3]}')
    await ctx.close()
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        for sc in ['dark','light']: await run(b,sc,390,844)
        await b.close()
asyncio.run(main())
print('FAILED' if fails else 'ALL PASS'); raise SystemExit(1 if fails else 0)
