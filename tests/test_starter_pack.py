"""Build 660: first-time Live TV has a starter pack (live cams, space, weather, news, classic TV) of
removable channels, added once on a fresh install only; nothing is seeded any more.
Run: python3 tests/test_starter_pack.py (screenshots in /tmp/claude-0/t/shots)"""
import asyncio, json, os, shutil, threading, http.server, functools, zlib, struct
from urllib.parse import urlparse
from playwright.async_api import async_playwright
import sys as _s; _s.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from notice_auto import AUTO_NOTICE
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = '/tmp/claude-0/t/srv-starter'; SHOTS = '/tmp/claude-0/t/shots'; PORT = 8861
shutil.rmtree(ROOT, ignore_errors=True); os.makedirs(ROOT, exist_ok=True); os.makedirs(SHOTS, exist_ok=True)
shutil.copy(os.path.join(HERE, '..', 'www', 'index.html'), ROOT)
H = functools.partial(http.server.SimpleHTTPRequestHandler, directory=ROOT); H.log_message = lambda *a: None
threading.Thread(target=http.server.ThreadingHTTPServer(('127.0.0.1', PORT), H).serve_forever, daemon=True).start()
def _png(w, h, rgb):
    raw = b''.join(b'\x00' + bytes(rgb) * w for _ in range(h))
    ch = lambda t, d: struct.pack('>I', len(d)) + t + d + struct.pack('>I', zlib.crc32(t + d) & 0xffffffff)
    return b'\x89PNG\r\n\x1a\n' + ch(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, 2, 0, 0, 0)) + ch(b'IDAT', zlib.compress(raw)) + ch(b'IEND', b'')
PNG = _png(200, 200, (40, 90, 160))
MOCK = """(function(){ var P=new Proxy({}, {get:function(t,k){ if(k==='then') return undefined; if(k==='addListener') return function(){ return Promise.resolve({remove:function(){}}); };
 if(k==='fetchText') return function(a){ return fetch(a.url).then(function(r){ return r.text(); }).then(function(t){ return { text: t, status: 200 }; }); };
 if(k==='videoState') return function(){ return Promise.resolve({id:null,hasVideo:false}); }; return function(){ return Promise.resolve({}); }; }});
 window.Capacitor={isNativePlatform:function(){return true;},getPlatform:function(){return 'android';},Plugins:{AmplifyPlayer:P},convertFileSrc:function(u){return u;}}; })();"""
fails = []
def check(ok, msg):
    print(('PASS ' if ok else 'FAIL ') + msg)
    if not ok: fails.append(msg)
async def route(r):
    u = urlparse(r.request.url)
    if '127.0.0.1' in u.netloc: return await r.continue_()
    if r.request.resource_type == 'image': return await r.fulfill(status=200, content_type='image/png', body=PNG, headers={'Access-Control-Allow-Origin': '*'})
    return await r.abort()
GRID = """(()=>Array.from(document.querySelectorAll('.epg-row')).map(function(r){ var ch=r.querySelector('.epg-ch'); var im=ch.querySelector('img'); return { n:(r.querySelector('.epg-logo-name')||ch).textContent.trim(), url:r.dataset.chUrl, img: !!im, w: im?Math.round(im.getBoundingClientRect().width):0 }; }))()"""
async def new(p, theme, width, seed=None, ctx=None):
    b = await p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
    ctx = await b.new_context(viewport={'width': width, 'height': 760}, device_scale_factor=3.3, is_mobile=True, has_touch=True, color_scheme=theme, locale='en-US', timezone_id='America/New_York')
    await ctx.add_init_script(MOCK); await ctx.add_init_script(AUTO_NOTICE)
    await ctx.add_init_script("try{ localStorage.setItem('radioPlayerTheme','%s'); localStorage.setItem('radioPlayerTourDone','1'); }catch(e){}" % theme)
    if seed: await ctx.add_init_script("if(!localStorage.getItem('__s')){ localStorage.setItem('__s','1'); %s }" % seed)
    pg = await ctx.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
    await pg.route('**/*', route)
    await pg.goto(f'http://127.0.0.1:{PORT}/index.html'); await pg.wait_for_timeout(2500)
    return b, ctx, pg, errs
async def live(pg):
    await pg.evaluate("document.querySelector('.mobile-nav-btn[data-nav=video]').click()"); await pg.wait_for_timeout(2500)
async def main():
    async with async_playwright() as p:
        for theme, width in (('dark', 327), ('light', 327), ('dark', 412)):
            T = f'[{theme} {width}]'
            b, ctx, pg, errs = await new(p, theme, width)
            await live(pg)
            rows = await pg.evaluate(GRID)
            names = [r['n'] for r in rows]
            check(len(rows) == 10, f'{T} a fresh install has the 10 starter channels {names}')
            check(all(r['img'] for r in rows), f'{T} every channel has a logo')
            st = await pg.evaluate("JSON.parse(localStorage.getItem('radioPlayerLiveChannels')||'[]')")
            check(not st, f'{T} no seeded own channels {st}')
            check(not errs, f'{T} no page errors {errs}')
            await pg.screenshot(path=f'{SHOTS}/starter_{theme}_{width}.png')
            if theme == 'dark' and width == 327:
                # remove one (the guide's channel sheet), reload: it stays removed
                await pg.evaluate("(()=>{ var c=JSON.parse(localStorage.getItem('radioPlayerVideoChannels')); c=c.filter(function(x){ return x.id!=='starter:docurama'; }); localStorage.setItem('radioPlayerVideoChannels', JSON.stringify(c)); })()")
                await pg.reload(); await pg.wait_for_timeout(2500); await live(pg)
                rows = await pg.evaluate(GRID)
                check(len(rows) == 9 and not any('Docurama' in r['n'] for r in rows), f'{T} a removed starter channel stays removed after a restart ({len(rows)})')
                # scroll the page to see them all
                await pg.evaluate("window.scrollTo(0, 99999)"); await pg.wait_for_timeout(400)
                await pg.screenshot(path=f'{SHOTS}/starter_dark_327_bottom.png')
            await b.close()
        # an existing install (Mark's: own channels already saved) isn't given the pack
        seed = "localStorage.setItem('radioPlayerLiveChannels', JSON.stringify([{id:'office',name:'',src:{kind:'pick',shows:['The Office'],movies:[]},order:'sequence'}]));"
        b, ctx, pg, errs = await new(p, 'dark', 327, seed); await live(pg)
        vc = await pg.evaluate("JSON.parse(localStorage.getItem('radioPlayerVideoChannels')||'[]')")
        check(not vc, f'an existing install gets no starter pack {len(vc)}')
        await b.close()
    print('FAILS', fails)
asyncio.run(main())
