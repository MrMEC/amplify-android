"""Audiobooks in Android Auto (Library > Audiobooks): what the page sends the car.
The catalog carries the categories (and book covers chosen on the phone) only while Settings > Sources >
Audiobooks is on, and lists.abContinue has one entry per book in progress (a Project Gutenberg book
stands in as its last section).  Run: python3 tests/test_car_audiobooks.py"""
import asyncio, json, os, threading, http.server, functools
from playwright.async_api import async_playwright
HERE = os.path.dirname(os.path.abspath(__file__))
root = os.path.join(HERE, '..', 'www')
H = functools.partial(http.server.SimpleHTTPRequestHandler, directory=root)
H.log_message = lambda *a: None
srv = http.server.ThreadingHTTPServer(('127.0.0.1', 8892), H); threading.Thread(target=srv.serve_forever, daemon=True).start()
def sec(guid, book, name, who='An Author', art=''):
    return {'type': 'podcast', 'guid': guid, 'collectionId': '', 'collectionName': book, 'artistName': who, 'name': name,
            'favicon': 'https://archive.org/services/img/x', 'duration': 600, 'episodeUrl': 'https://archive.org/download/' + guid.split(':')[1]}
seed = {
 'radioPlayerRecent': [
   sec('ia:dracula_librivox/dracula_02.mp3', 'Dracula', 'Chapter 2', 'Bram Stoker'),
   sec('ia:dracula_librivox/dracula_01.mp3', 'Dracula', 'Chapter 1', 'Bram Stoker'),
   sec('gb:84/part1.mp3', 'Frankenstein', 'Part 1', 'Mary Shelley'),
   sec('ia:notabook/file.mp3', 'A Podcast Episode', 'Ep'),
   sec('ia:emma_librivox/emma_01.mp3', 'Emma', 'Chapter 1', 'Jane Austen'),
 ],
 # a cover chosen for the book, and one chosen before build 442 for a section of another
 'radioPlayerCustomArt': {'audiobook:dracula_librivox': 'https://example.com/dracula.jpg',
                          'podcast:ia:emma_librivox/emma_01.mp3': 'https://example.com/emma.jpg'}
}
def mock(sources_off):
    s = dict(seed)
    if sources_off: s['radioPlayerSourcesOff'] = {'audiobooks': True}
    return """
(function(){
 var seed=%s; for(var k in seed) localStorage.setItem(k, JSON.stringify(seed[k]));
 window.__cat=[];
 var P=new Proxy({}, {get:function(t,k){
   if(k==='then') return undefined;
   if(k==='setCarCatalog') return function(a){ window.__cat.push(JSON.parse(a.json)); return Promise.resolve(); };
   if(k==='takeCarProgress') return function(){ return Promise.resolve({progress:{}}); };
   if(k==='addListener') return function(){ return Promise.resolve({remove:function(){}}); };
   return function(){ return Promise.resolve({}); };
 }});
 window.Capacitor={isNativePlatform:function(){return true;},getPlatform:function(){return 'android';},registerPlugin:function(){return P;},Plugins:{AmplifyPlayer:P},convertFileSrc:function(u){return u;}};
})();
""" % json.dumps(s)
fails = []
def check(c, m):
    print(('PASS ' if c else 'FAIL ') + m)
    if not c: fails.append(m)
async def run(b, off):
    pg = await b.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
    await pg.route('**/*', lambda r: r.continue_() if '127.0.0.1' in r.request.url else r.abort())
    await pg.add_init_script(mock(off))
    await pg.goto('http://127.0.0.1:8892/index.html'); await pg.wait_for_timeout(6000)
    cats = await pg.evaluate('window.__cat')
    await pg.close()
    return cats[-1] if cats else None, errs
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
        c, errs = await run(b, False)
        check(c is not None, 'the page sends the car its catalog')
        ab = c.get('audiobooks')
        check(ab and len(ab['cats']) == 12 and ab['cats'][0] == {'name': 'Classics', 'subject': 'classics'}, 'on: the categories are sent %s' % (ab and ab['cats'][:2]))
        check(ab and ab['cats'][2]['subject'] == '"science fiction"', 'a two-word subject keeps its quotes')
        check(ab and ab['art'] == {'dracula_librivox': 'https://example.com/dracula.jpg', 'emma_librivox': 'https://example.com/emma.jpg'}, 'custom covers (also pre-442 section ones) are sent by book id %s' % (ab and ab['art']))
        cont = c['lists']['abContinue']
        print([(e['t'], e.get('id') or e.get('guid'), e.get('title')) for e in cont])
        check([e['t'] for e in cont] == ['book', 'episode', 'book'], 'Dracula (two sections played) is one book, Frankenstein (Gutenberg) is its last section, then Emma')
        check(cont[0]['art'] == 'https://example.com/dracula.jpg' and cont[2]['art'] == 'https://example.com/emma.jpg', 'Continue Listening books use their custom cover')
        check(cont[0]['id'] == 'dracula_librivox' and cont[0]['title'] == 'Dracula' and cont[0]['sub'] == 'Bram Stoker', 'the book row has its id, title and author')
        check(cont[1]['guid'] == 'gb:84/part1.mp3' and cont[1]['url'], 'the Gutenberg stand-in plays')
        check(not any('Podcast' in (e.get('title') or '') for e in cont), 'an ordinary podcast episode is not a book')
        check(not errs, 'no page errors %s' % errs[:3])
        c2, errs2 = await run(b, True)
        check(c2 is not None and c2.get('audiobooks') is None, 'off: the car gets no Audiobooks')
        check(c2 is not None and c2['lists']['abContinue'] == [], 'off: no books in progress are sent')
        await b.close()
    print('FAILS:', fails)
    raise SystemExit(1 if fails else 0)
asyncio.run(main())
