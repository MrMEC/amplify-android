import asyncio, os, json, threading, http.server, functools, shutil, sys, time, statistics
sys.path.insert(0, '/home/claude/amplify-android/tests')
from notice_auto import AUTO_NOTICE
from playwright.async_api import async_playwright
PORT = 8901
SRC = os.environ.get('SRC', '/home/claude/amplify-android/www/index.html')
root = '/tmp/claude-0/t/srv_perf2'
shutil.rmtree(root, ignore_errors=True); os.makedirs(root)
os.symlink('/tmp/claude-0/t/biglib/Music', root + '/Music')
HOOK = "window.__t = { n: function(){ return libraryTracks.length; }, ev: function(js){ return eval(js); } };\n"
_src = open(SRC).read(); _mark = '  var coverFlow = null;\n'
open(root + '/index.html', 'w').write(_src.replace(_mark, _mark + HOOK))
M = '/tmp/claude-0/t/biglib/Music'
files = [{'uri': f'http://127.0.0.1:{PORT}/Music/{f}', 'name': f, 'relPath': f'Music/{f}', 'type': 'audio/mpeg', 'size': os.path.getsize(f'{M}/{f}'), 'lastModified': 1700000000000} for f in sorted(os.listdir(M))]
json.dump(files, open(root + '/files.json', 'w'))
class Q(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a): pass
srv = http.server.ThreadingHTTPServer(('127.0.0.1', PORT), functools.partial(Q, directory=root))
threading.Thread(target=srv.serve_forever, daemon=True).start()
MOCK = """(function(){ var x = new XMLHttpRequest(); x.open('GET', '/files.json', false); x.send(); var picked = JSON.parse(x.responseText), listeners = {};
 var impl = { pickMusicFolder: function(){ return Promise.resolve({folder:'Music', treeUri:'tree:music', files:picked, truncated:false}); },
   rescanMusicFolder: function(){ return Promise.resolve({folder:'Music', treeUri:'tree:music', files:picked, truncated:false}); },
   cacheCheck: function(){ return Promise.resolve({ url: 'file:///cache/x.mp3' }); },
   addListener: function(n, f){ (listeners[n] = listeners[n] || []).push(f); return Promise.resolve({remove:function(){}}); } };
 var P = new Proxy({}, {get:function(t,k){ if(k==='then') return undefined; if(k==='setCarLibraryPart') return undefined; if(impl[k]) return impl[k]; return function(){ return Promise.resolve({}); }; }});
 window.Capacitor = { isNativePlatform:function(){return true;}, getPlatform:function(){return 'android';}, registerPlugin:function(){ return P; }, Plugins:{AmplifyPlayer:P}, convertFileSrc:function(u){return u;} };
 try{ localStorage.setItem('radioPlayerTourDone','1'); }catch(e){}
})();"""
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
        ctx = await b.new_context(viewport={'width': 412, 'height': 915}, is_mobile=True, has_touch=True, color_scheme='dark')
        await ctx.add_init_script(MOCK); await ctx.add_init_script(AUTO_NOTICE)
        pg = await ctx.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.route('**/*', lambda r: r.continue_() if '127.0.0.1' in r.request.url else r.abort())
        await pg.goto(f'http://127.0.0.1:{PORT}/index.html'); await pg.wait_for_timeout(2500)
        await pg.evaluate("""(function(){ var ov=document.getElementById('addMusicOverlay'); if(ov) ov.classList.add('open'); var btn=document.getElementById('addMusicFolderBtn'); btn.disabled=false; btn.click(); })()""")
        last = -1
        for _ in range(600):
            await pg.wait_for_timeout(1000)
            n = await pg.evaluate('__t.n()')
            if n >= len(files) or (n == last and n > 0 and _ > 20): break
            last = n
        await pg.wait_for_timeout(3000)
        await pg.evaluate("try{ document.getElementById('addMusicOverlay').classList.remove('open'); hideImportPanel(); }catch(e){}")
        # seed plays / years / added
        await pg.evaluate("""__t.ev('(function(){ var sp={}, now=Date.now(); libraryTracks.forEach(function(t,i){ if(i%7===0) sp[favKey(t)]=[1, now - i*60000]; t.year = (i%5===0) ? "" : String(1970 + (i*37)%55); if(i%3===0) t.addedAt = now - i*1000; }); localStorage.setItem("radioPlayerSongPlays", JSON.stringify(sp)); localStorage.removeItem("radioPlayerLibSort"); libSortBy = {artists:"recent",albums:"recent",songs:"recent"}; return 1; })()')""")
        await pg.evaluate("document.querySelector('.mobile-nav-btn[data-nav=library]').click()"); await pg.wait_for_timeout(2500)
        RAIL = "(()=>{ var r=document.getElementById('azRail'); return {disp:r.style.display, kids:r.children.length, on:document.body.classList.contains('az-on'), show:document.body.classList.contains('az-show')}; })()"
        async def pick(mode):
            await pg.evaluate("document.getElementById('libSortBtn').click()"); await pg.wait_for_timeout(200)
            await pg.evaluate(f"document.querySelector('.lib-sort-menu [data-sort={mode}]') && document.querySelector('.lib-sort-menu [data-sort={mode}]').click()"); await pg.wait_for_timeout(900)
            await pg.evaluate("document.body.click()")
        async def scrolled():
            await pg.evaluate("window.scrollTo(0, 1500)"); await pg.wait_for_timeout(400)
            r = await pg.evaluate(RAIL); await pg.evaluate("window.scrollTo(0,0)"); await pg.wait_for_timeout(300); return r
        async def filt():
            await pg.evaluate("(()=>{var i=document.getElementById('secFilterInput'); i.focus(); i.value='be'; i.dispatchEvent(new Event('input',{bubbles:true}));})()"); await pg.wait_for_timeout(500)
            await pg.evaluate("(()=>{var i=document.getElementById('secFilterInput'); i.value=''; i.dispatchEvent(new Event('input',{bubbles:true})); i.blur();})()"); await pg.wait_for_timeout(600)
        bad = []
        for tab in ['artists','albums','songs']:
            await pg.evaluate(f"document.querySelector('#stationsGrid > .lib-tabs [data-libtab={tab}]').click()"); await pg.wait_for_timeout(1500)
            await pick('az'); r = await scrolled(); print(tab, 'az', r)
            if r['disp'] == 'none' or not r['show']: bad.append((tab,'az',r))
            for mode in ['recent','added','release']:
                await pick(mode); r1 = await scrolled(); await filt(); r2 = await scrolled()
                print(tab, mode, r1, r2)
                if r1['disp'] != 'none' or r2['disp'] != 'none' or r1['show'] or r2['show']: bad.append((tab,mode,r1,r2))
            # leave on recent and go to next tab to see it carries nothing
        # A-Z then filter then clear: rail comes back
        await pick('az'); await filt(); r = await scrolled(); print('songs az after filter', r)
        if r['disp'] == 'none': bad.append(('songs az after filter', r))
        print('BAD', bad, 'errors', errs[:3])
        await b.close(); return
        print('MEDIAN busy', statistics.median(res), 'errors', errs[:2])
        await b.close()
asyncio.run(main())
