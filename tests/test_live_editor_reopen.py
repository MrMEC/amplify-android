"""Build 650: Edit Channel opened blank after the editor had been left by a bottom tab (its panel was out of the page).
Run: python3 tests/test_live_editor_reopen.py"""
import sys; sys.path.insert(0,'/home/claude/amplify-android/tests')
import asyncio, os, json, shutil, threading, http.server, functools
from playwright.async_api import async_playwright
from notice_auto import AUTO_NOTICE
ROOT='/tmp/claude-0/t/srv-lc'; PORT=8891
shutil.rmtree(ROOT, ignore_errors=True); os.makedirs(ROOT)
h=open('/home/claude/amplify-android/www/index.html').read()
h=h.replace("  function liveChPageLeft(){","  window.__openLC = openLiveChEditor;\n  function liveChPageLeft(){",1)
open(ROOT+'/index.html','w').write(h)
H=functools.partial(http.server.SimpleHTTPRequestHandler, directory=ROOT); H.log_message=lambda *a:None
srv=http.server.ThreadingHTTPServer(('127.0.0.1',PORT),H); threading.Thread(target=srv.serve_forever,daemon=True).start()
A=lambda n:[{'id':'mup%d'%i,'title':'Muppet Show ep %d'%i,'creator':'Henson','year':'1976','video':True} for i in range(n)]
def D(src,**k):
    d={'id':'cmup','name':'The Muppets','src':src,'order':'sequence','ads':0,'gridDesc':''}; d.update(k); return d
VARS0={
 'ads1800+daily':D({'kind':'pick','shows':[],'movies':[],'archive':A(3)},ads=1800,order='daily'),
 'big40':D({'kind':'pick','shows':[],'movies':[],'archive':A(40)},order='shuffle'),
 'sparse-items':D({'kind':'pick','shows':[],'movies':[],'archive':[{'id':'x'},{'id':'y','title':None}]}),
 'longdesc':D({'kind':'pick','shows':[],'movies':[],'archive':A(2)},gridDesc='x'*140,name='The Muppets & "Friends" <b>'),
 'mixed':D({'kind':'pick','shows':['Muppets'],'movies':['Muppet Movie'],'archive':A(2)}),
 'no-order':{'id':'cmup','name':'The Muppets','src':{'kind':'pick','archive':A(2)}},
 'artist-mv':D({'kind':'mv','all':False,'artists':['kermit']}),
 'archive-str':D({'kind':'pick','shows':[],'movies':[],'archive':'muppets'}),
}
VARS={'archive':D({'kind':'pick','shows':[],'movies':[],'archive':A(3)}),'shows':D({'kind':'pick','shows':['The Office (US)'],'movies':[]})}
CUSTOMART={'data':"data:image/png;base64,iVBORw0KGgo=",'idb':"idb:abc123",'https':"https://example.test/x.png"}
async def main():
    async with async_playwright() as p:
        B=await p.chromium.launch()
        for name,src in VARS.items():
            c=await B.new_context(viewport={'width':360,'height':780},device_scale_factor=2,is_mobile=True,has_touch=True,color_scheme='dark')
            await c.add_init_script(AUTO_NOTICE)
            await c.add_init_script("if(!localStorage.getItem('__s')){localStorage.setItem('__s','1');localStorage.setItem('radioPlayerLiveChannels',%s);}" % json.dumps(json.dumps([src])))
            pg=await c.new_page(); errs=[]; pg.on('pageerror',lambda e:errs.append(str(e)))
            async def route(r):
                u=r.request.url
                if u.startswith('http://127.0.0.1:%d'%PORT): return await r.continue_()
                return await r.fulfill(status=200,body='{}',content_type='application/json')
            await pg.route('**/*',route)
            await pg.goto('http://127.0.0.1:%d/index.html'%PORT); await pg.wait_for_timeout(1800)
            try: await pg.evaluate("window.__openLC('cmup')")
            except Exception as e: errs.append('EVAL '+str(e)[:200])
            await pg.wait_for_timeout(800)
            async def st(tag):
                v=await pg.evaluate("(function(){var p=document.getElementById('liveChPanel');var r=p.getBoundingClientRect();return [p.parentNode.id, Math.round(r.height), document.getElementById('stationsHeading').textContent, document.body.className.indexOf('lc-page-open')>=0]})()")
                print(' ',name,tag,v,errs[-1:])
            await st('open')
            await pg.evaluate("document.querySelector('.mobile-nav-btn[data-nav=home]').click()"); await pg.wait_for_timeout(1000); print('  home: panel in DOM =', await pg.evaluate("!!document.getElementById('liveChPanel')"))
            try: await pg.evaluate("window.__openLC('cmup')")
            except Exception as e: print('  REOPEN ERR', str(e)[:160])
            await pg.wait_for_timeout(800)
            try: await st('reopen')
            except Exception as e: print('  reopen state ERR', str(e)[:100])
            await pg.screenshot(path='/tmp/claude-0/t/shots/lc-%s.png'%name)
            await c.close(); continue
            vis=await pg.evaluate("(function(){var p=document.getElementById('liveChPanel');var r=p.getBoundingClientRect();return [p.parentNode.id, Math.round(r.height), document.getElementById('liveChName').value]})()")
            print(name, vis, errs[:2])
            await pg.screenshot(path='/tmp/claude-0/t/shots/lc-%s.png'%name)
            await c.close()
        await B.close()
asyncio.run(main())
