"""Build 403 (Mark): Genres is a browse grid (a find field, "Your top genres" cards with a play button, a
two-column grid of colour cards), and a genre opens a page with a header in its colour, Play and Shuffle,
related styles, Top stations, In your library and More stations. Replaces test_genre_tabs.py (build 178).
Run: python3 tests/test_genre_page.py (screenshots in /tmp/claude-0/t/shots)"""
import sys as _nsys, os as _nos; _nsys.path.insert(0, _nos.path.dirname(_nos.path.abspath(__file__))); from notice_auto import AUTO_NOTICE
import asyncio, os, json, threading, http.server, functools, shutil, subprocess
from urllib.parse import urlparse, parse_qs
from playwright.async_api import async_playwright

PORT = 8888
root = '/tmp/claude-0/t/srv_genrepage'
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
SONGS = [('Rock One', 'Ann', 'Rock'), ('Rock Two', 'Ann', 'Rock'), ('Rock Three', 'Bob', 'Rock'), ('Jazz Tune', 'Cal', 'Jazz')]
for i, (t, a, g) in enumerate(SONGS):
    subprocess.run(['ffmpeg', '-loglevel', 'error', '-y', '-f', 'lavfi', '-i', f'sine=frequency={300 + i * 50}:duration=3', '-c:a', 'libmp3lame', '-b:a', '32k',
                    '-metadata', f'title={t}', '-metadata', f'artist={a}', '-metadata', f'album={a} LP', '-metadata', f'genre={g}', f'{M}/{i:02d}.mp3'], check=True)
class Q(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a): pass
srv = http.server.ThreadingHTTPServer(('127.0.0.1', PORT), functools.partial(Q, directory=root))
threading.Thread(target=srv.serve_forever, daemon=True).start()
files = [{'uri': f'http://127.0.0.1:{PORT}/Music/{f}', 'name': f, 'relPath': f'Music/{f}', 'type': 'audio/mpeg',
          'size': os.path.getsize(f'{M}/{f}'), 'lastModified': 1700000000000} for f in sorted(os.listdir(M))]
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
def check(cond, msg):
    print(('PASS ' if cond else 'FAIL ') + msg)
    if not cond: fails.append(msg)
STATIONS = {'rock': 14, 'jazz': 0, 'blues': 3, 'polka': 0, 'classic rock': 4}
delay = {'ms': 0}
async def route(r):
    u = r.request.url
    if '127.0.0.1' in u: return await r.continue_()
    q = parse_qs(urlparse(u).query)
    if '/json/stations/search' in u and 'tag' in q:
        tag = q['tag'][0]
        if delay['ms']: await asyncio.sleep(delay['ms'] / 1000)
        return await r.fulfill(status=200, content_type='application/json', body=json.dumps(
            [{'name': '%s Station %d' % (tag.title(), i), 'url_resolved': 'http://s/%s%d' % (tag, i), 'stationuuid': '%s-%d' % (tag, i), 'favicon': '', 'tags': tag, 'codec': 'MP3'} for i in range(STATIONS.get(tag, 0))]))
    if '/json/' in u: return await r.fulfill(status=200, content_type='application/json', body='[]')
    return await r.abort()

GB = """(()=>{ var g = document.getElementById('stationsGrid');
  var cards = Array.from(g.querySelectorAll('.gb-card')).filter(function(c){ return !c.hidden; });
  return { search: !!g.querySelector('.sec-filter.gb-find input'), heads: Array.from(g.querySelectorAll('.gb-head')).filter(function(h){ return !h.hidden; }).map(function(h){ return h.querySelector('.gb-edit') ? h.firstChild.textContent : h.textContent; }), edit: !!g.querySelector('.gb-head .gb-edit:not([hidden])'),
    top: Array.from(g.querySelectorAll('.gb-top:not([hidden]) .gb-topcard-name')).map(function(e){ return e.textContent; }),
    cards: cards.map(function(c){ return c.dataset.genre; }), lefts: Array.from(new Set(cards.map(function(c){ return Math.round(c.getBoundingClientRect().left); }))).length,
    colors: Array.from(new Set(cards.map(function(c){ return getComputedStyle(c).backgroundColor; }))).length,
    none: (g.querySelector('.gb-none:not([hidden])') || {}).textContent || '', rows: g.querySelectorAll('.tile.tile-row').length,
    sw: document.documentElement.scrollWidth, vw: innerWidth }; })()"""
GP = """(()=>{ var g = document.getElementById('stationsGrid'), h = g.querySelector('.gp-hero');
  var back = document.getElementById('detailBackBtn').getBoundingClientRect(), hr = h ? h.getBoundingClientRect() : null;
  function names(sel){ return Array.from(g.querySelectorAll(sel)).map(function(e){ return e.textContent; }); }
  var more = Array.from(g.querySelectorAll('.gp-grid > .tile'));
  return { heading: document.getElementById('stationsHeading').textContent, title: h ? h.querySelector('.gp-title').textContent : null,
    eyebrow: h ? h.querySelector('.gp-eyebrow').textContent : null, bg: h ? getComputedStyle(h).backgroundColor : null,
    backOnHero: !!hr && back.top >= hr.top && back.bottom <= hr.bottom && back.width > 0,
    heroFull: !!hr && Math.round(hr.left) === 0 && Math.round(hr.right) === innerWidth, heroTop: hr ? Math.round(hr.top) : null, backTop: Math.round(back.top), backH: Math.round(back.height), scrollY: Math.round(scrollY),
    play: !!g.querySelector('.gp-play') && !g.querySelector('.gp-play').disabled, meta: (g.querySelector('.gp-meta') || {}).textContent || '',
    chips: names('.gp-chip'), heads: names('.gp-head'), top: g.querySelectorAll('.gp-row > .tile').length, more: more.length,
    songs: names('.gp-songs .song-row:not(.shuffle-all-row) .song-row-title'), shuffleAll: !!g.querySelector('.gp-songs .shuffle-all-row'),
    seeAll: (g.querySelector('.gp-more') || {}).textContent || '', spinner: !!g.querySelector('.loading-state'),
    empty: (g.querySelector('.empty-state') || {}).textContent || '', sw: document.documentElement.scrollWidth, vw: innerWidth }; })()"""

async def load(pg):
    await pg.goto(f'http://127.0.0.1:{PORT}/index.html'); await pg.wait_for_timeout(2500)
    await pg.evaluate("""(function(){ var ov=document.getElementById('addMusicOverlay'); if(ov) ov.classList.add('open');
      var btn=document.getElementById('addMusicFolderBtn'); btn.disabled=false; btn.click(); })()""")
    for _ in range(60):
        await pg.wait_for_timeout(500)
        if len(await pg.evaluate('__t.tracks()')) >= 4: break
    await pg.wait_for_timeout(1200)
    await pg.evaluate("try{ document.getElementById('addMusicOverlay').classList.remove('open'); hideImportPanel(); setStatus('', false); }catch(e){}")

async def run(b, scheme, w, h, full):
    T = f'[{scheme} {w}]'
    ctx = await b.new_context(viewport={'width': w, 'height': h}, device_scale_factor=2, is_mobile=w < 900, has_touch=w < 900, color_scheme=scheme)
    await ctx.add_init_script(MOCK); await ctx.add_init_script(AUTO_NOTICE)
    await ctx.add_init_script("try{ localStorage.setItem('radioPlayerTheme', %s); }catch(e){}" % json.dumps(scheme))
    pg = await ctx.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
    await pg.route('**/*', route)
    await load(pg)
    # ---- Genres: the browse grid ----
    await pg.evaluate("__t.home()"); await pg.wait_for_timeout(800)
    r = await pg.evaluate(GB); print(T, r)
    check(r['search'] and r['heads'] == ['Your top picks', 'Browse categories'] and r['edit'], f'{T} a find field, then Your top genres and Browse all {r["heads"]}')
    check(r['top'][:2] == ['Rock', 'Jazz'], f'{T} top genres follow what is in the library (Rock 3 songs, then Jazz) {r["top"]}')
    # build 412: ten minutes of Jazz played puts it first, ahead of the library's Rock
    await pg.evaluate("__t.ev(\"listenCredit(localTracksWithTag('Jazz')[0], 600)\")"); await pg.evaluate("__t.home()"); await pg.wait_for_timeout(600)
    r2 = await pg.evaluate(GB)
    check(r2['top'][:2] == ['Jazz', 'Rock'], f'{T} top picks follow recent listening (Jazz played, then the library\'s Rock) {r2["top"]}')
    check(len(r['cards']) == 16 and r['colors'] >= 12, f'{T} every genre is a card in its own colour ({len(r["cards"])} cards, {r["colors"]} colours)')
    check(r['lefts'] == (2 if w < 900 else r['lefts']) and r['lefts'] >= 2, f'{T} cards in columns ({r["lefts"]})')
    check(r['sw'] <= r['vw'], f'{T} nothing scrolls sideways ({r["sw"]} > {r["vw"]})')
    await pg.screenshot(path=f'{shots}/genres-{scheme}-{w}.png', full_page=full)
    # Build 404: the find box is the app's filter box, its placeholder fits, and no word breaks (at the biggest text too)
    st = await pg.evaluate("""(()=>{ var i=document.getElementById('genreFindInput'), cs=getComputedStyle(i);
      var c=document.createElement('canvas').getContext('2d'); c.font=cs.fontWeight+' '+cs.fontSize+' '+cs.fontFamily;
      var room=i.clientWidth-parseFloat(cs.paddingLeft)-parseFloat(cs.paddingRight);
      return { cls: i.parentElement.className, h: Math.round(i.getBoundingClientRect().height), ph: i.placeholder, fits: c.measureText(i.placeholder).width <= room, room: Math.round(room), radius: cs.borderTopLeftRadius, bg: cs.backgroundColor, panel: getComputedStyle(document.body).getPropertyValue('--panel-2') }; })()""")
    check(st['cls'] == 'sec-filter gb-find' and st['h'] == 46 and st['ph'] == 'Filter genres' and st['fits'], f'{T} the find box is the app\'s filter box and its placeholder fits {st}')
    if w < 900:
        await pg.evaluate("(()=>{ var r=document.getElementById('fontSizeRange'); r.value='150'; r.dispatchEvent(new Event('input')); r.dispatchEvent(new Event('change')); })()"); await pg.wait_for_timeout(900)
        await pg.evaluate("window.scrollTo(0, 99999)"); await pg.wait_for_timeout(500); await pg.evaluate("window.scrollTo(0, 0)"); await pg.wait_for_timeout(500)
        wb = await pg.evaluate("""(()=>{ var bad=[]; document.querySelectorAll('.gb-card-name, .gb-topcard-name, #genreFindInput').forEach(function(e){
            if(e.tagName==='INPUT'){ return; } if(e.scrollWidth > e.clientWidth + 1) bad.push(e.textContent + ' ' + e.scrollWidth + '>' + e.clientWidth); }); return bad; })()""")
        st2 = await pg.evaluate("""(()=>{ var i=document.getElementById('genreFindInput'), cs=getComputedStyle(i); var c=document.createElement('canvas').getContext('2d'); c.font=cs.fontWeight+' '+cs.fontSize+' '+cs.fontFamily;
            return c.measureText(i.placeholder).width <= i.clientWidth-parseFloat(cs.paddingLeft)-parseFloat(cs.paddingRight); })()""")
        check(not wb and st2, f'{T} text at 150%: every genre name fits whole, no word broken, placeholder still fits {wb}')
        await pg.screenshot(path=f'{shots}/genres-big-{scheme}-{w}.png')
        await pg.evaluate("__t.genre('Electronic')"); await pg.wait_for_timeout(1200)
        gt = await pg.evaluate("(()=>{ var e=document.querySelector('.gp-title'); return [e.scrollWidth, e.clientWidth, getComputedStyle(e).fontSize]; })()")
        check(gt[0] <= gt[1] + 1, f'{T} text at 150%: the genre title "Electronic" fits on one line, shrunk ({gt})')
        await pg.screenshot(path=f'{shots}/genre-big-{scheme}-{w}.png')
        await pg.evaluate("(()=>{ var r=document.getElementById('fontSizeRange'); r.value='100'; r.dispatchEvent(new Event('input')); r.dispatchEvent(new Event('change')); })()"); await pg.wait_for_timeout(600)
        await pg.evaluate("__t.home()"); await pg.wait_for_timeout(800)
        # with the keyboard up the mini Now Playing never shows
        await pg.evaluate("document.querySelector('.gb-topcard-play').click()"); await pg.wait_for_timeout(1500)
        await pg.evaluate("__t.ev('closeNowPlaying()')"); await pg.wait_for_timeout(500)
        before = await pg.evaluate("getComputedStyle(document.querySelector('.player-bar')).display")
        await pg.tap('#genreFindInput'); await pg.wait_for_timeout(500)
        kb = await pg.evaluate("({ kb: document.body.classList.contains('kb-open'), bar: getComputedStyle(document.querySelector('.player-bar')).display })")
        check(before != 'none' and kb['kb'] and kb['bar'] == 'none', f'{T} typing in the find box hides the mini Now Playing (before {before}, now {kb})')
        await pg.evaluate("document.activeElement.blur()"); await pg.wait_for_timeout(400)
        check(await pg.evaluate("getComputedStyle(document.querySelector('.player-bar')).display") != 'none', f'{T} and it is back when the keyboard closes')
        await pg.evaluate("__t.home()"); await pg.wait_for_timeout(600)
    if not full: return await ctx.close()
    await pg.fill('#genreFindInput', 'ja'); await pg.wait_for_timeout(200)
    r = await pg.evaluate(GB)
    check(r['cards'] == ['Jazz'] and r['top'] == [] and r['heads'] == ['Genres'], f'{T} typing narrows the cards, the top row steps aside {r["cards"]} {r["heads"]}')
    await pg.fill('#genreFindInput', 'polka'); await pg.wait_for_timeout(200)
    r = await pg.evaluate(GB)
    check(not r['cards'] and 'Enter' in r['none'], f'{T} no match says Enter looks it up {r["none"]!r}')
    await pg.press('#genreFindInput', 'Enter'); await pg.wait_for_timeout(1200)
    p = await pg.evaluate(GP)
    check(p['title'] == 'polka' and 'No songs or stations' in p['empty'] and not p['play'], f'{T} Enter opens a page for it; with nothing found it says so and Play is off {p["title"]} {p["empty"]!r}')
    await pg.evaluate("__t.home()"); await pg.wait_for_timeout(600)
    await pg.evaluate("document.querySelector('.gb-topcard[aria-label=Rock] .gb-topcard-play').click()"); await pg.wait_for_timeout(1500)
    q = await pg.evaluate('__t.q()')
    check(q['cur'] == 'Rock Station 0' and q['label'] == 'Rock' and len(q['list']) == 14, f'{T} a top card\'s play button plays the genre\'s top station, its stations queued {q["cur"]} {q["label"]} {len(q["list"])}')
    await pg.evaluate("__t.ev('closeNowPlaying()')"); await pg.wait_for_timeout(400)
    await pg.evaluate("__t.home()"); await pg.wait_for_timeout(600)
    await pg.evaluate("document.querySelector('.gb-edit').click()"); await pg.wait_for_timeout(500)
    r = await pg.evaluate(GB)
    check(r['rows'] == 16 and not r['cards'], f'{T} rearranging shows the list to drag ({r["rows"]} rows)')
    await pg.evaluate("document.querySelector('.gb-edit').click()"); await pg.wait_for_timeout(500)
    check(len((await pg.evaluate(GB))['cards']) == 16, f'{T} and the cards come back after')
    # ---- a genre page ----
    await pg.evaluate("document.querySelector('.gb-card[data-genre=\"Rock\"]').click()"); await pg.wait_for_timeout(1500)
    p = await pg.evaluate(GP); print(T, p)
    check(p['title'] == 'Rock' and p['heading'] == 'Rock' and p['eyebrow'] == 'Genre' and p['bg'] == 'rgb(138, 38, 38)', f'{T} a header in the genre\'s colour, titled Rock {p["bg"]}')
    check(p['heroFull'] and p['backOnHero'], f'{T} the header runs edge to edge with Back on it')
    check(p['play'] and p['meta'] == '14 stations · 3 songs in your library', f'{T} Play and Shuffle, and what there is {p["meta"]!r}')
    check(p['chips'][:2] == ['Classic Rock', 'Alternative'], f'{T} related styles as chips {p["chips"]}')
    check(p['heads'] == ['Top stations', 'In your library', 'More Rock stations'] and p['top'] == 10 and p['more'] == 4, f'{T} Top stations (10), In your library, More stations (4) {p["heads"]} {p["top"]} {p["more"]}')
    check(p['songs'] == ['Rock One', 'Rock Three', 'Rock Two'] and p['shuffleAll'] and not p['seeAll'], f'{T} the library\'s Rock songs with Shuffle All {p["songs"]}')
    check(p['sw'] <= p['vw'], f'{T} nothing scrolls sideways on the genre page')
    await pg.screenshot(path=f'{shots}/genre-page-{scheme}-{w}.png')
    await pg.screenshot(path=f'{shots}/genre-page-full-{scheme}-{w}.png', full_page=True)
    await pg.evaluate("document.querySelector('.gp-play').click()"); await pg.wait_for_timeout(1500)
    q = await pg.evaluate('__t.q()')
    check(q['cur'] == 'Rock Station 0' and q['label'] == 'Rock' and len(q['list']) == 14, f'{T} Play plays the top station with every Rock station queued {q["cur"]}')
    await pg.evaluate("__t.ev('closeNowPlaying()')"); await pg.wait_for_timeout(400)
    await pg.evaluate("document.querySelector('.gp-round').click()"); await pg.wait_for_timeout(1500)
    q = await pg.evaluate('__t.q()')
    check(q['cur'] and q['cur'].startswith('Rock Station') and len(q['list']) == 14, f'{T} Shuffle plays a Rock station from a shuffled queue {q["cur"]}')
    await pg.evaluate("__t.ev('closeNowPlaying()')"); await pg.wait_for_timeout(400)
    await pg.evaluate("Array.from(document.querySelectorAll('.gp-chip')).filter(function(c){ return c.textContent === 'Classic Rock'; })[0].click()"); await pg.wait_for_timeout(1500)
    p = await pg.evaluate(GP)
    check(p['title'] == 'Classic Rock' and p['top'] == 4, f'{T} a chip opens that style\'s page {p["title"]} {p["top"]}')
    await pg.evaluate("document.getElementById('detailBackBtn').click()"); await pg.wait_for_timeout(1200)
    check((await pg.evaluate(GP))['title'] == 'Rock', f'{T} Back from a style returns to the genre it came from')
    await pg.evaluate("document.getElementById('detailBackBtn').click()"); await pg.wait_for_timeout(1000)
    check((await pg.evaluate(GB))['search'], f'{T} and Back again to Genres')
    # Jazz: songs only
    await pg.evaluate("__t.genre('Jazz')"); await pg.wait_for_timeout(1500)
    p = await pg.evaluate(GP)
    check(p['heads'] == ['In your library'] and p['songs'] == ['Jazz Tune'] and p['play'] and not p['spinner'], f'{T} songs only: just In your library, and Play works {p["heads"]}')
    await pg.evaluate("document.querySelector('.gp-play').click()"); await pg.wait_for_timeout(1500)
    q = await pg.evaluate('__t.q()')
    check(q['cur'] == 'Jazz Tune', f'{T} Play plays the song {q["cur"]}')
    await pg.evaluate("__t.ev('closeNowPlaying()')"); await pg.wait_for_timeout(400)
    # stations still on their way
    delay['ms'] = 2500
    await pg.evaluate("__t.genre('Rock')"); await pg.wait_for_timeout(600)
    e = await pg.evaluate(GP)
    check(e['songs'] == ['Rock One', 'Rock Three', 'Rock Two'] and e['spinner'] and e['top'] == 0, f'{T} the songs show at once while the stations load {e["spinner"]}')
    await pg.wait_for_timeout(3000)
    check((await pg.evaluate(GP))['top'] == 10, f'{T} then the stations arrive')
    delay['ms'] = 0
    check(not errs, f'{T} no page errors {errs[:3]}')
    await ctx.close()

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
        await run(b, 'dark', 390, 844, True)
        await run(b, 'light', 360, 780, True)
        await run(b, 'dark', 1280, 860, False)
        await b.close()
    print('ALL PASSED' if not fails else 'FAILED %s' % fails)
asyncio.run(main())
