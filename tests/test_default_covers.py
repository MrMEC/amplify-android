"""Build 413: default covers. Stations with no picture wear vector art chosen by genre (Chill ->
aurora, Jazz -> vinyl, Pop -> synthwave, Rock -> bolt, News/Talk -> Bauhaus), with call letters or
initials on top; the same station always gets the same cover; songs get no letters.
Run: python3 tests/test_default_covers.py (screenshots in /tmp/claude-0/t/shots)"""
import asyncio, json, os, shutil, threading, http.server, functools, re, subprocess
from playwright.async_api import async_playwright
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = '/tmp/claude-0/t/srv-cov'; SHOTS = '/tmp/claude-0/t/shots'
os.makedirs(ROOT, exist_ok=True); os.makedirs(SHOTS, exist_ok=True)
html = open(os.path.join(HERE, '..', 'www', 'index.html')).read()
mark = '  function renderStationArt(container, station){'
assert html.count(mark) == 1
html = html.replace(mark, "  window.__cv = { render: function(c, s){ renderStationArt(c, s); }, spec: coverSpec, label: coverLabel, hint: coverHintFor, resolve: resolveStationArtNetwork };\n" + mark, 1)
open(ROOT + '/index.html', 'w').write(html)
H = functools.partial(http.server.SimpleHTTPRequestHandler, directory=ROOT); H.log_message = lambda *a: None
srv = http.server.ThreadingHTTPServer(('127.0.0.1', 8831), H); threading.Thread(target=srv.serve_forever, daemon=True).start()

def stn(i, name, tags):
    return {'name': name, 'urlToResolve': 'https://s%d.example/live' % i, 'url_resolved': 'https://s%d.example/live' % i,
            'stationuuid': 'u%d' % i, 'favicon': '', 'tags': tags, 'country': 'US'}
FAVS = [stn(1, 'KJAM 92.5', 'pop,top 40'), stn(2, 'Smooth Chill Lounge', 'chill,lounge'), stn(3, 'WFMT Jazz', 'jazz,blues'),
        stn(4, 'Q104.3 Classic Rock', 'classic rock'), stn(5, 'NPR News Now', 'news,talk'), stn(6, 'Mystery Station', '')]
fails = []
def check(ok, msg):
    print(('PASS ' if ok else 'FAIL ') + msg)
    if not ok: fails.append(msg)

def png(name, w, h):
    path = f'{ROOT}/{name}'
    subprocess.run(['ffmpeg', '-loglevel', 'error', '-y', '-f', 'lavfi', '-i', f'color=c=0xff8800:s={w}x{h}', '-frames:v', '1', path], check=True)
    return open(path, 'rb').read()
def tpng(name, w, h):
    path = f'{ROOT}/{name}'
    subprocess.run(['ffmpeg', '-loglevel', 'error', '-y', '-f', 'lavfi', '-i', f'testsrc2=size={w}x{h}', '-frames:v', '1', path], check=True)
    return open(path, 'rb').read()
PNGS = {'logo64.png': tpng('logo64.png', 64, 64), 'logo180.png': tpng('logo180.png', 180, 180), 'cover512.png': tpng('cover512.png', 512, 512), 'wide.png': tpng('wide.png', 600, 200),'fav32.png': png('fav32.png', 32, 32), 'touch180.png': png('touch180.png', 180, 180), 'icon512.png': png('icon512.png', 512, 512),
        'banner.png': png('banner.png', 1200, 630), 'wiki600.png': png('wiki600.png', 600, 600), 'tiny16.png': png('tiny16.png', 16, 16)}
HOME = '<html><head><link rel="apple-touch-icon" sizes="180x180" href="/touch180.png"><link rel="manifest" href="/site.webmanifest"><meta property="og:image" content="/banner.png"></head></html>'
MANI = json.dumps({'icons': [{'src': '/touch180.png', 'sizes': '180x180'}, {'src': '/icon512.png', 'sizes': '512x512'}]})
CORS = {'access-control-allow-origin': '*'}

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
        ctx = await b.new_context(viewport={'width': 390, 'height': 844}, device_scale_factor=2, is_mobile=True, has_touch=True, color_scheme='dark')
        await ctx.add_init_script("if(!localStorage.getItem('__seeded')){ localStorage.setItem('__seeded','1'); localStorage.setItem('radioPlayerFavorites', %s); localStorage.setItem('radioPlayerRecent', %s); localStorage.setItem('radioPlayerTourSeen','1'); }"
                                  % (repr(json.dumps(FAVS)), repr(json.dumps(FAVS[:4]))))
        pg = await ctx.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
        async def route(r):
            u = r.request.url
            if u.startswith('http://127.0.0.1:8831'): await r.continue_(); return
            m = re.match(r'https://(a|b|c)\.radio\.example(/.*)?$', u)
            if m:
                site, path = m.group(1), (m.group(2) or '/')
                name = path.lstrip('/')
                if site == 'a' and path == '/': await r.fulfill(status=200, headers={**CORS, 'content-type': 'text/html'}, body=HOME); return
                if site == 'a' and path == '/site.webmanifest': await r.fulfill(status=200, headers={**CORS, 'content-type': 'application/json'}, body=MANI); return
                if site == 'b' and path == '/': await r.fulfill(status=200, headers={**CORS, 'content-type': 'text/html'}, body='<html><head><meta property="og:image" content="/banner.png"></head></html>'); return
                if name in PNGS: await r.fulfill(status=200, headers={**CORS, 'content-type': 'image/png'}, body=PNGS[name]); return
                await r.fulfill(status=404, body='no'); return
            if 'wikipedia.org' in u:
                await r.fulfill(status=200, headers={**CORS, 'content-type': 'application/json'}, body=json.dumps({'query': {'pages': {'1': {'index': 1, 'title': 'KWIK (FM)', 'thumbnail': {'source': 'https://c.radio.example/wiki600.png'}, 'terms': {'description': ['American radio station']}}}}})); return
            await r.abort()
        await pg.route('**/*', route)
        await pg.goto('http://127.0.0.1:8831/index.html'); await pg.wait_for_timeout(2500)
        # 1. the cover sheet, drawn by the app's own renderer
        await pg.evaluate("""(()=>{ var d=document.createElement('div'); d.id='covsheet';
          d.style.cssText='position:fixed;inset:0;z-index:99999;background:#101014;display:grid;grid-template-columns:repeat(3,1fr);gap:10px;padding:14px;align-content:start;overflow:auto';
          document.body.appendChild(d); })()""")
        names = [('KJAM 92.5','pop'),('Hit Radio One','top 40,hits'),('Neon Nights','80s,synth'),('Smooth Chill Lounge','chill,lounge'),('Ambient Dreams','ambient'),('Sunday Relax','relax'),
                 ('WFMT Jazz','jazz,blues'),('Blue Note Cafe','soul,jazz'),('Motown Gold','motown,oldies'),('Q104.3 Classic Rock','classic rock'),('Heavy Metal Radio','metal'),('Indie Garage','indie'),
                 ('NPR News Now','news,talk'),('Classical Union','classical'),('Mystery Station',''),('Radio Sol','')]
        for i,(n,t) in enumerate(names):
            await pg.evaluate("""([i,n,t])=>{ var w=document.createElement('div'); w.innerHTML='<div class="tile-art" style="font-size:12px"></div><div style="color:#ccc;font:11px sans-serif;margin-top:4px">'+n+'</div>';
              document.getElementById('covsheet').appendChild(w); window.__cv.render(w.firstChild, {name:n, urlToResolve:'https://x'+i+'.example/s', stationuuid:'cv'+i, tags:t, favicon:''}); }""", [i,n,t])
        await pg.wait_for_timeout(500)
        await pg.screenshot(path=f'{SHOTS}/covers-sheet.png')
        # genre -> look
        got = await pg.evaluate("""()=>{ var o={}; [['pop','x'],['chill,lounge','x'],['jazz','x'],['classic rock','x'],['news,talk','x'],['smooth jazz','x'],['soft rock','x'],['top 40','x']].forEach(function(a){ o[a[0]] = window.__cv.spec('k-'+a[0], {name:'Z', tags:a[0]}).style; }); return o; }""")
        print(got)
        # build 436: each genre picks from its own family of looks
        fam = {'pop': ['synth','equalizer','cassette','sunburst'], 'chill,lounge': ['aurora','waves','mountains'], 'jazz': ['vinyl','mic','radio'], 'classic rock': ['rock','speaker','checker'], 'news,talk': ['bauhaus','mic','radio']}
        check(all(got[k] in v for k, v in fam.items()), f'genres pick their looks {got}')
        spread = await pg.evaluate("""()=>{ var o={}; ['rock','pop','jazz','chill','news'].forEach(function(g){ var c={}; for(var i=0;i<40;i++) c[window.__cv.spec('s'+i+g,{name:'S'+i,tags:g}).style]=1; o[g]=Object.keys(c).length; }); var all={}; for(var i=0;i<200;i++) all[window.__cv.spec('n'+i,{name:'S'+i,tags:''}).style]=1; o.all=Object.keys(all).length; return o; }""")
        check(spread['rock'] == 3 and spread['pop'] == 4 and spread['jazz'] == 3 and spread['chill'] == 3 and spread['news'] == 3 and spread['all'] == 15, f'build 436: every genre shows its whole family, untagged stations all 15 looks {spread}')
        check(got['smooth jazz'] == 'vinyl' and got['soft rock'] == 'rock' and got['top 40'] == 'synth', 'overlaps resolve sensibly')
        lab = await pg.evaluate("()=>['KJAM 92.5','Q104.3 Classic Rock','Smooth Jazz 24/7','The Beat','Rock FM','NPR News Now','93.3 The Fox','Kiss FM'].map(window.__cv.label)")
        print(lab)
        check(lab[0] == 'KJAM' and lab[1] == 'Q104.3' and lab[2] == 'SJ' and lab[5] == 'NPR' and lab[7] == 'KISS', 'labels: call letters, frequencies, initials')
        a = await pg.evaluate("()=>[window.__cv.spec('same',{name:'Foo FM',tags:'jazz'}).css, window.__cv.spec('same',{name:'Foo FM',tags:'jazz'}).css].every(function(x,i,arr){return x===arr[0];})")
        check(a, 'same station, same cover')
        hs = await pg.evaluate("()=>[window.__cv.hint({name:'Song Title', album:'', localTrack:false})]")
        await pg.evaluate("document.getElementById('covsheet').remove()")
        # 2. the real app: Home with favourites and recents, phone
        await pg.evaluate("document.querySelector('.mobile-nav-btn[data-nav=home]').click()"); await pg.wait_for_timeout(1200)
        await pg.screenshot(path=f'{SHOTS}/covers-home.png')
        gen = await pg.evaluate("document.querySelectorAll('.generated-art').length")
        check(gen >= 6, f'home shows generated covers ({gen})')
        bad = await pg.evaluate("Array.prototype.filter.call(document.querySelectorAll('.generated-art'), function(e){ return e.style.background.indexOf('radial-gradient') !== -1; }).length")
        check(bad == 0, 'no old gradient covers left')
        check(not errs, f'no page errors {errs[:3]}')
        # 3. the sharpest cover wins
        res = await pg.evaluate("window.__cv.resolve({name:'Alpha FM', homepage:'https://a.radio.example/', urlToResolve:'https://a.radio.example/live', favicon:'https://a.radio.example/fav32.png'})")
        check(res and res['url'].endswith('icon512.png') and res['w'] == 512, f'manifest 512 beats the 32px favicon and 180px touch icon {res}')
        res = await pg.evaluate("window.__cv.resolve({name:'Beta FM', homepage:'https://b.radio.example/', urlToResolve:'https://b.radio.example/live', favicon:'https://b.radio.example/touch180.png'})")
        check(res and res['url'].endswith('touch180.png'), f'a clean 180px logo beats a cropped banner {res}')
        res = await pg.evaluate("window.__cv.resolve({name:'KWIK', homepage:'', urlToResolve:'https://c.radio.example/live', favicon:'https://c.radio.example/tiny16.png'})")
        check(res and res['url'].endswith('wiki600.png') and res['w'] == 600, f'Wikipedia logo at 600px is found when the site has nothing {res}')
        res = await pg.evaluate("window.__cv.resolve({name:'Nothing', homepage:'', urlToResolve:'', favicon:''})")
        check(res is None, 'no candidates -> null (placeholder stays)')
        # a legacy cached soft cover is upgraded in place
        await pg.evaluate("localStorage.setItem('radioPlayerArtCache', JSON.stringify({}))")
        await pg.evaluate("""()=>{ var d=document.createElement('div'); d.className='tile-art'; d.id='upg'; d.style.cssText='width:120px;height:120px;position:fixed;top:10px;left:10px;z-index:99999'; document.body.appendChild(d);
          window.__st = {name:'Alpha FM', homepage:'https://a.radio.example/', urlToResolve:'https://a.radio.example/live', stationuuid:'alpha', favicon:'https://a.radio.example/fav32.png', tags:'pop'}; }""")
        await pg.evaluate("window.__cv.render(document.getElementById('upg'), window.__st)")
        await pg.wait_for_timeout(2500)
        src = await pg.evaluate("(document.querySelector('#upg img')||{}).src || ''")
        check(src.endswith('icon512.png'), f'the tile upgrades to the 512px cover {src}')
        cache = await pg.evaluate("JSON.parse(localStorage.getItem('radioPlayerArtCache')||'{}')")
        print(cache)
        # 4. small and wide logos sit on a blurred backdrop; a sharp square cover fills the tile
        await pg.evaluate("""()=>{ var d=document.createElement('div'); d.id='softsheet';
          d.style.cssText='position:fixed;inset:0;z-index:99999;background:#101014;display:grid;grid-template-columns:repeat(2,1fr);gap:14px;padding:16px;align-content:start';
          document.body.appendChild(d);
          [['64px logo','logo64.png'],['180px logo','logo180.png'],['512px cover','cover512.png'],['wide banner','wide.png']].forEach(function(a,i){
            var w=document.createElement('div'); w.innerHTML='<div class="tile-art"></div><div style="color:#ccc;font:12px sans-serif;margin-top:4px">'+a[0]+'</div>'; d.appendChild(w);
            window.__cv.render(w.firstChild, {name:a[0], urlToResolve:'https://a.radio.example/s'+i, stationuuid:'soft'+i, tags:'pop', favicon:'https://a.radio.example/'+a[1]}); }); }""")
        await pg.wait_for_timeout(1500)
        cls = await pg.evaluate("Array.prototype.map.call(document.querySelectorAll('#softsheet .tile-art'), function(e){ return e.classList.contains('art-soft'); })")
        check(cls == [True, True, False, True], f'small and wide logos are soft, the 512px cover is not {cls}')
        await pg.screenshot(path=f'{SHOTS}/covers-soft.png')
        await b.close()
    print('FAILS:', fails)
asyncio.run(main())
