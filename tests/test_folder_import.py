import asyncio, os, json, threading, http.server, functools
from playwright.async_api import async_playwright
root='/tmp/claude-0/t/srv'
H=functools.partial(http.server.SimpleHTTPRequestHandler, directory=root)
srv=http.server.ThreadingHTTPServer(('127.0.0.1',8765),H); threading.Thread(target=srv.serve_forever,daemon=True).start()
files=[]
for dp,_,fs in os.walk(root+'/Music'):
    for f in fs:
        p=os.path.join(dp,f); rel=os.path.relpath(p,root)
        files.append({'uri':'http://127.0.0.1:8765/'+rel.replace(' ','%20'),'name':f,'relPath':rel,
          'type':'audio/wav' if f.endswith('wav') else 'image/png','size':os.path.getsize(p),'lastModified':1700000000000})
MOCK="""
(function(){
 var picked = %s;
 function proxy(){ return new Proxy({}, {get:function(t,k){
   if(k==='then') return undefined;
   if(k==='pickMusicFolder') return function(){ window.__picked=true; return Promise.resolve({folder:'Music', files:picked, truncated:false}); };
   if(k==='addListener') return function(){ return Promise.resolve({remove:function(){}}); };
   return function(){ return Promise.resolve({}); };
 }}); }
 var P = proxy();
 window.Capacitor = { isNativePlatform:function(){return true;}, getPlatform:function(){return 'android';},
   registerPlugin:function(){ return P; }, Plugins:{AmplifyPlayer:P}, convertFileSrc:function(u){return u;} };
})();
""" % json.dumps(files)
async def main():
    async with async_playwright() as p:
        b=await p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
        pg=await b.new_page(viewport={'width':412,'height':900})
        errs=[]; pg.on('pageerror',lambda e: errs.append(str(e)))
        await pg.add_init_script(MOCK)
        await pg.goto('http://127.0.0.1:8765/index.html'); await pg.wait_for_timeout(2500)
        print('folder btn disabled:', await pg.evaluate("document.getElementById('addMusicFolderBtn') && document.getElementById('addMusicFolderBtn').disabled"))
        # open dialog then click folder
        await pg.evaluate("""(function(){ var b=document.getElementById('libraryAddHeaderBtn'); })()""")
        ok = await pg.evaluate("""(function(){
          var ov=document.getElementById('addMusicOverlay'); if(ov) ov.classList.add('open');
          var btn=document.getElementById('addMusicFolderBtn'); btn.disabled=false; btn.click(); return true; })()""")
        await pg.wait_for_timeout(5000)
        print('picked:', await pg.evaluate('window.__picked'))
        print('status:', await pg.evaluate("(document.getElementById('importPanel')||document.body).innerText.slice(0,300)"))
        await pg.screenshot(path='/tmp/claude-0/t/shot.png')
        print('errors:', errs[:5])
        await b.close()
asyncio.run(main())
