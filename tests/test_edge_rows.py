"""Build 206: on phones rows that scroll sideways (Home rows, Podcasts and Watch tabs) run to both screen edges,
with the first item on the page edge. Run: python3 tests/test_edge_rows.py"""

"""Build 204: one back button everywhere (the artist page's bare arrow, no label, no pill) and it always
goes back to the page you came from; My Stations has no "Saved Searches" label or count.
Run: python3 tests/test_back_buttons.py (screenshots in /tmp/claude-0/t/shots)"""
"""Artist and album pages slide in from the right on phones when opened (tapping a tile),
using only a transform; Back, and the system's Remove animations setting, open them in place.
Run: python3 tests/test_page_slide.py (screenshots in /tmp/claude-0/t/shots)"""
import sys as _nsys, os as _nos; _nsys.path.insert(0, _nos.path.dirname(_nos.path.abspath(__file__))); from notice_auto import AUTO_NOTICE
import asyncio, os, json, threading, http.server, functools, shutil, subprocess
from playwright.async_api import async_playwright

PORT = 8805
root = '/tmp/claude-0/t/srv_edgerows'
shots = '/tmp/claude-0/t/shots'
os.makedirs(shots, exist_ok=True)
shutil.rmtree(root, ignore_errors=True)
os.makedirs(root)
HOOK = ("window.__t = { tracks: function(){ return libraryTracks.map(function(t){ return t.name; }); },"
        " mk: function(){ stationPlaylists.push({ id: 'pl_mix', label: 'Mix', stations: [{ stationuuid: 'st-1', name: 'Radio One', url: 'http://radio.example/one', urlToResolve: 'http://radio.example/one', favicon: '' }] });"
        "   stationPlaylists.push({ id: 'pl_empty', label: 'Empty', stations: [] }); saveStationPlaylists(); renderStationPlaylistList(); },"
        " pl: function(label){ var p = stationPlaylists.filter(function(x){ return x.label === label; })[0]; return p ? p.stations.map(function(s){ return s.name; }) : null; },"
        " stored: function(label){ var p = JSON.parse(localStorage.getItem('radioPlayerStationPlaylists')).filter(function(x){ return x.label === label; })[0]; return p ? p.stations.map(function(s){ return s.name; }) : null; },"
        " openAlbum: function(a){ var al = buildAlbumIndex().filter(function(x){ return x.album === a; })[0]; openAlbumPage(al.key, null); },"
        " artists: function(){ runLibrarySection('artists'); }, ev: function(js){ return eval(js); },"
        " status: function(){ var e = document.getElementById('statusLine') || document.querySelector('.status-line'); return e ? e.textContent : ''; } };\n")
_src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'www', 'index.html')).read()
_mark = '  var coverFlow = null;\n'
assert _src.count(_mark) == 1
open(root + '/index.html', 'w').write(_src.replace(_mark, _mark + HOOK))

M = root + '/Music'
os.makedirs(M, exist_ok=True)
SONGS = [('Kay 1', 'Kay', 'Big Album', 1), ('Kay 2', 'Kay', 'Big Album', 2), ('Kay 3', 'Kay', 'Second', 1), ('Lone', 'Lee', 'Other', 1)]
for i, (t, a, al, n) in enumerate(SONGS):
    subprocess.run(['ffmpeg', '-loglevel', 'error', '-y', '-f', 'lavfi', '-i', f'sine=frequency={300 + i * 60}:duration=3',
                    '-c:a', 'libmp3lame', '-b:a', '32k', '-metadata', f'title={t}', '-metadata', f'artist={a}',
                    '-metadata', f'album={al}', '-metadata', f'track={n}', f'{M}/{i + 1:02d}.mp3'], check=True)


class Q(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a): pass
H = functools.partial(Q, directory=root)
srv = http.server.ThreadingHTTPServer(('127.0.0.1', PORT), H)
threading.Thread(target=srv.serve_forever, daemon=True).start()
files = [{'uri': f'http://127.0.0.1:{PORT}/Music/{f}', 'name': f, 'relPath': f'Music/{f}', 'type': 'audio/mpeg',
          'size': os.path.getsize(f'{M}/{f}'), 'lastModified': 1700000000000} for f in sorted(os.listdir(M))]
MOCK = """
(function(){
 var picked = %s, listeners = {};
 var impl = {
   pickMusicFolder: function(){ return Promise.resolve({folder:'Music', files:picked, truncated:false}); },
   addListener: function(n, f){ (listeners[n] = listeners[n] || []).push(f); return Promise.resolve({remove:function(){}}); }
 };
 var P = new Proxy({}, {get:function(t,k){
   if(k==='then') return undefined;
   if(k==='setCarLibraryPart') return undefined;
   if(impl[k]) return impl[k];
   return function(){ return Promise.resolve({}); };
 }});
 window.Capacitor = { isNativePlatform:function(){return true;}, getPlatform:function(){return 'android';},
   registerPlugin:function(){ return P; }, Plugins:{AmplifyPlayer:P}, convertFileSrc:function(u){return u;} };
})();
""" % json.dumps(files)

fails = []
def check(cond, msg):
    print(('PASS ' if cond else 'FAIL ') + msg)
    if not cond: fails.append(msg)




import sys
from urllib.parse import urlparse, parse_qs
AUDIT=r'''// Returns the mini player art left (T) and every near-left content start in the visible page.
(() => {
  const vis = el => { if(!el) return false; const r = el.getBoundingClientRect(); if(r.width < 2 || r.height < 2) return false;
    for(let e = el; e && e !== document.documentElement; e = e.parentElement){ const c = getComputedStyle(e); if(c.display==='none'||c.visibility==='hidden'||+c.opacity===0) return false; } return r.bottom > 0 && r.top < innerHeight; };
  const pbArt = [...document.querySelectorAll('#playerBar img, #playerBar .player-art, #playerBar [class*=art]')].filter(vis).sort((a,b)=>a.getBoundingClientRect().left-b.getBoundingClientRect().left)[0];
  const T = pbArt ? pbArt.getBoundingClientRect().left : 21;
  const out = []; const seen = new Set();
  const desc = el => { let s = el.tagName.toLowerCase(); if(el.id) s += '#'+el.id; if(el.classList.length) s += '.'+[...el.classList].slice(0,3).join('.'); const p = el.parentElement; if(p) { let ps = p.tagName.toLowerCase(); if(p.id) ps+='#'+p.id; else if(p.classList.length) ps+='.'+[...p.classList].slice(0,2).join('.'); s = ps+' > '+s; } return s; };
  const roots = ['#browseView', '.main', '#nowPlayingScreen'].map(s=>document.querySelector(s)).filter(vis);
  const root = roots[0]; if(!root) return {T, items:[]};
  const skip = el => el.closest('#playerBar, .mobile-nav, .sidebar-top, .mobile-header, #npMenu, .np-menu, [role=menu]');
  // text starts
  const tw = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, { acceptNode: n => n.nodeValue.trim() ? 1 : 2 });
  let n; while((n = tw.nextNode())){
    const el = n.parentElement; if(!vis(el) || skip(el)) continue;
    const rg = document.createRange(); rg.selectNodeContents(n); const rs = rg.getClientRects(); if(!rs.length) continue;
    const r = rs[0]; if(r.top > innerHeight || r.bottom < 0) continue;
    out.push({kind:'text', left: Math.round(r.left*10)/10, top: Math.round(r.top), what: desc(el), txt: n.nodeValue.trim().slice(0,24)});
  }
  // images / art boxes / icons / buttons with no text
  root.querySelectorAll('img, svg, canvas, i, .tile-art, .row-art, .art, [class*=thumb], [class*=cover], button, input, .home-tab, .tile, .row-item').forEach(el => {
    if(!vis(el) || skip(el)) return; if(el.closest('svg') && el.tagName.toLowerCase() !== 'svg') return;
    const r = el.getBoundingClientRect(); if(r.top > innerHeight) return;
    out.push({kind: el.tagName.toLowerCase()==='i' ? 'icon' : 'box', left: Math.round(r.left*10)/10, top: Math.round(r.top), w: Math.round(r.width), what: desc(el), txt: (el.innerText||'').trim().slice(0,16)});
  });
  return {T, vw: innerWidth, items: out};
})()
'''
HDR=r'''(() => { const r = s => { const e = document.querySelector(s); if(!e) return null; const b = e.getBoundingClientRect(); return b.width ? [Math.round(b.left*10)/10, Math.round(b.right*10)/10, Math.round(b.top), Math.round(b.width)] : null; };
 return { logo: r('.sidebar-top .logo-mark') || r('.logo-mark'), logoWrap: r('.sidebar-top .logo, .sidebar-top a, .brand'), hamb: r('.sidebar-top .hamburger-btn'), npBack: r('#npBackBtn'), npCol: r('#npCollection'), npHero: r('#nowPlayingScreen .np-hero'), npTitle: r('#npName'), pb: r('#playerBar'), pbArt: r('#playerBar img') || r('#playerBar .tile-art'), vw: innerWidth }; })()
'''
TAG='edge'; W=412; THEME='light'
ONLY=os.environ.get('ONLY','')
async def net(r):
    u=r.request.url
    if '127.0.0.1' in u: return await r.continue_()
    q=parse_qs(urlparse(u).query)
    if 'radio-browser' in u:
        return await r.fulfill(status=200, content_type='application/json', headers={'Access-Control-Allow-Origin':'*'}, body=json.dumps(
            [{'name':'Chill Station %d'%i,'url_resolved':'http://s/c%d'%i,'url':'http://s/c%d'%i,'stationuuid':'c%d'%i,'favicon':'','tags':'chill,jazz','codec':'MP3','country':'US','countrycode':'US','votes':10,'clickcount':5} for i in range(8)]))
    if 'itunes.apple.com/' in u:
        cb=(q.get('callback') or [''])[0]
        body_=json.dumps({'resultCount':2,'results':[{'wrapperType':'track','kind':'podcast','collectionId':5+i,'collectionName':'Pod %d Talks'%i,'artistName':'Pod Co','artworkUrl600':'','feedUrl':'http://feed.example/%d'%i} for i in range(2)]})
        return await r.fulfill(status=200, content_type='application/javascript', body=cb+'('+body_+');')
    return await r.abort()
PAGES=[
 ('home', "loadTopStations(); document.querySelector('.mobile-nav-btn[data-nav=home]').click()"),
 ('library', "openMyLibraryHome()"),
 ('artists', "pushView(); runLibrarySection('artists')"),
 ('albums', "pushView(); runLibrarySection('albums')"),
 ('songs', "pushView(); runLibrarySection('songs')"),
 ('artist', "pushView(); openArtistPage(buildArtistIndex()[0].key)"),
 ('album', "pushView(); openAlbumPage(buildAlbumIndex()[0].key, null)"),
 ('playlists', "pushView(); openPlaylistsHome()"),
 ('playlist', "pushView(); runStationPlaylist(stationPlaylists[0])"),
 ('mystations', "pushView(); openStationsHome()"),
 ('customsearch', "pushView(); runCustomSearch(customSearches[0])"),
 ('favorites', "pushView(); openHomeSectionPage('favorites')"),
 ('topartists', "pushView(); openHomeSectionPage('topArtists')"),
 ('genres', "pushView(); openGenresHome()"),
 ('genre', "pushView(); searchByTag('Jazz')"),
 ('podcasts', "document.querySelector('.mobile-nav-btn[data-nav=podcasts]').click()"),
 ('watch', "document.querySelector('.mobile-nav-btn[data-nav=video]').click()"),
 ('addchannels', "pushView(); openAddChannelsPage()"),
 ('movies', "document.querySelector('.mobile-nav-btn[data-nav=video]').click(); Array.from(document.querySelectorAll('.video-tabs .home-tab')).filter(function(b){return /Movies/.test(b.textContent)})[0].click()"),
 ('madeforyou', "pushView(); openHomeSectionPage('madeForYou')"),
 ('topstations', "pushView(); openHomeSectionPage('topStations')"),
 ('nowplaying', "playStation({stationuuid:'c1',name:'Chill Station 1',url:'http://s/c1',urlToResolve:'http://s/c1',favicon:'',tags:'chill'}); openNowPlaying()"),
 ('search', "closeNowPlaying(); document.querySelector('.mobile-nav-btn[data-nav=search]').click(); setSearchBoxes('chill'); searchByName('chill')"),
]

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
        for W in (412, 360):
            ctx = await b.new_context(viewport={'width': W, 'height': 900}, device_scale_factor=2, is_mobile=True, has_touch=True)
            await ctx.add_init_script(MOCK); await ctx.add_init_script(AUTO_NOTICE)
            await ctx.add_init_script("localStorage.setItem('radioPlayerFavorites', JSON.stringify(Array.from({length:8},function(_,i){return {stationuuid:'s'+i,name:'Fav FM '+i,url:'http://f.example/'+i,favicon:''};})));")
            pg = await ctx.new_page(); errs=[]; pg.on('pageerror', lambda e: errs.append(str(e))); await pg.route('**/*', net)
            await pg.goto(f'http://127.0.0.1:{PORT}/index.html'); await pg.wait_for_timeout(2500)
            r = await pg.evaluate("""(()=>{ var g=document.getElementById('favoritesGrid'), b=g.getBoundingClientRect(); g.style.scrollBehavior='auto';
              var f=g.firstElementChild.getBoundingClientRect().left; g.scrollLeft=70; return {box:[b.left,b.right], first:f}; })()""")
            await pg.wait_for_timeout(200); await pg.screenshot(path=f'{shots}/edgerows-home-{W}.png')
            check(r['box'] == [0, W] and abs(r['first'] - 21) < 1, f'{W}: Home rows scroll edge to edge, first cover on the page edge {r}')
            for nav, sel in [('podcasts', '#podcastTabs'), ('video', '.video-tabs')]:
                await pg.evaluate(f"document.querySelector('.mobile-nav-btn[data-nav={nav}]').click()"); await pg.wait_for_timeout(900)
                r = await pg.evaluate("""(sel)=>{ var t=document.querySelector(sel); ['Wrestling','Disney + Universal','News'].forEach(function(n){ var b=document.createElement('button'); b.className='home-tab'; b.textContent=n; t.appendChild(b); });
                  var tr=t.getBoundingClientRect(); var first=t.firstElementChild.getBoundingClientRect().left;
                  t.scrollLeft=1e5; var last=t.lastElementChild.getBoundingClientRect().right; return {box:[tr.left,tr.right], first:first, lastAtEnd:last}; }""", sel)
                await pg.evaluate("(sel)=>{ document.querySelector(sel).scrollLeft=120; }", sel); await pg.wait_for_timeout(200)
                await pg.screenshot(path=f'{shots}/edgerows-{nav}-{W}.png')
                check(r['box'] == [0, W] and abs(r['first'] - 21) < 1 and abs(r['lastAtEnd'] - (W - 21)) < 1.5,
                      f'{W} {nav}: tabs run to both screen edges, start on the page edge and end the same distance from the right {r}')
            check(not errs, f'{W}: no page errors {errs[:3]}')
            await ctx.close()
        await b.close()
    print('ALL PASSED' if not fails else f'FAILED {fails}')
asyncio.run(main())
