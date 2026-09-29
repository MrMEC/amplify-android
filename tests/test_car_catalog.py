import asyncio, json, threading, http.server, functools
from playwright.async_api import async_playwright
root='/tmp/claude-0/t/srv'
H=functools.partial(http.server.SimpleHTTPRequestHandler, directory=root)
H.log_message=lambda *a: None
srv=http.server.ThreadingHTTPServer(('127.0.0.1',8766),H); threading.Thread(target=srv.serve_forever,daemon=True).start()
ep1={'type':'podcast','guid':'g1','collectionId':111,'collectionName':'Show One','artistName':'A','name':'Ep One','favicon':'https://x/a.jpg','releaseDate':'2026-09-24T10:00:00Z','duration':1800,'episodeUrl':'https://x/e1.mp3'}
ep2=dict(ep1,guid='g2',collectionId=222,collectionName='Show Two',name='Ep Two',releaseDate='2026-09-20T10:00:00Z',episodeUrl='https://x/e2.mp3')
seed={
 'radioPlayerFavorites':[{'name':'Jazz FM','urlToResolve':'http://jazz/stream','favicon':'https://x/j.png','tags':'jazz,smooth','stationuuid':'u1'}, ep1, {'type':'artist','name':'Someone'}],
 'radioPlayerRecent':[{'name':'Rock 1','urlToResolve':'http://rock/s','stationuuid':'u2'},{'type':'local','name':'song','localId':'l1'}],
 'radioPlayerCustomSearches':[{'id':'s1','label':'Smooth Jazz','query':'smooth jazz'}],
 'radioPlayerPodcastSubs':[{'collectionId':111,'collectionName':'Show One','artistName':'A','artworkUrl':'https://x/1.jpg','latestEpisode':ep1},{'collectionId':222,'collectionName':'Show Two','artistName':'B','artworkUrl':'https://x/2.jpg','latestEpisode':ep2}],
 'radioPlayerPodcastCategories':[{'id':'c1','name':'Comedy','showIds':[222]}],
}
MOCK="""
(function(){
 var seed=%s; for(var k in seed) localStorage.setItem(k, JSON.stringify(seed[k]));
 window.__cat=[];
 var P=new Proxy({}, {get:function(t,k){
   if(k==='then') return undefined;
   if(k==='setCarCatalog') return function(a){ window.__cat.push(JSON.parse(a.json)); return Promise.resolve(); };
   if(k==='takeCarProgress') return function(){ return Promise.resolve({progress:{g2:{positionSec:600,durationSec:1800,record:{guid:'g2',trackName:'Ep Two',collectionName:'Show Two',episodeUrl:'https://x/e2.mp3',collectionId:222}}}}); };
   if(k==='addListener') return function(){ return Promise.resolve({remove:function(){}}); };
   return function(){ return Promise.resolve({}); };
 }});
 window.Capacitor={isNativePlatform:function(){return true;},getPlatform:function(){return 'android';},registerPlugin:function(){return P;},Plugins:{AmplifyPlayer:P},convertFileSrc:function(u){return u;}};
})();
""" % json.dumps(seed)
async def main():
    async with async_playwright() as p:
        b=await p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
        pg=await b.new_page()
        errs=[]; pg.on('pageerror',lambda e: errs.append(str(e)))
        await pg.route('**/*radio-browser*/**', lambda r: r.fulfill(status=200, content_type='application/json', body=json.dumps([{'name':'Top One','url_resolved':'http://top/1','stationuuid':'t1','favicon':'','tags':'pop'}])))
        await pg.add_init_script(MOCK)
        await pg.goto('http://127.0.0.1:8766/index.html'); await pg.wait_for_timeout(8000)
        cats=await pg.evaluate('window.__cat')
        print('publishes:',len(cats))
        c=cats[-1] if cats else {}
        for k,v in (c.get('lists') or {}).items(): print(k, [ (i.get('t'), i.get('title'), i.get('pos'), i.get('g')) for i in v])
        print('forYou',c.get('forYou'),'cats',c.get('categories'),'speed',c.get('podcastSpeed'))
        # change a favorite -> republish
        n=len(cats)
        await pg.evaluate("localStorage.getItem('x')")
        print('errors:',errs[:5])
        await b.close()
asyncio.run(main())
