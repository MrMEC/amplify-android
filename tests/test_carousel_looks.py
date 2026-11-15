"""Build 643: Card and Editorial carousels + Show heading, at 327 x 709 (dpr 3.3).
Run: python3 tests/test_carousel_looks.py (screenshots in /tmp/claude-0/t/shots)"""
import sys as _nsys, os as _nos; _nsys.path.insert(0, _nos.path.dirname(_nos.path.abspath(__file__))); from notice_auto import AUTO_NOTICE
import asyncio, os, json, io, threading, http.server, functools, shutil
from playwright.async_api import async_playwright
from PIL import Image
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = '/tmp/claude-0/t/srv-looks'; SHOTS = '/tmp/claude-0/t/shots'; PORT = 8878
shutil.rmtree(ROOT, ignore_errors=True); os.makedirs(ROOT); os.makedirs(SHOTS, exist_ok=True)
shutil.copy(os.path.join(HERE, '..', 'www', 'index.html'), ROOT + '/index.html')
H = functools.partial(http.server.SimpleHTTPRequestHandler, directory=ROOT); H.log_message = lambda *a: None
srv = http.server.ThreadingHTTPServer(('127.0.0.1', PORT), H); threading.Thread(target=srv.serve_forever, daemon=True).start()
fails = []
def check(ok, msg):
    print(('PASS ' if ok else 'FAIL ') + msg)
    if not ok: fails.append(msg)
def art(c1, c2):
    im = Image.new('RGB', (300, 300))
    px = im.load()
    for y in range(300):
        t = y / 299
        for x in range(300): px[x, y] = tuple(int(c1[i] * (1 - t) + c2[i] * t) for i in range(3))
    b = io.BytesIO(); im.save(b, 'PNG'); return b.getvalue()
def logo():
    im = Image.new('RGBA', (300, 120), (0, 0, 0, 0)); px = im.load()
    for y in range(30, 90):
        for x in range(20, 280): px[x, y] = (255, 255, 255, 255)
    b = io.BytesIO(); im.save(b, 'PNG'); return b.getvalue()
ARTS = {'e': logo(), 'a': art((20, 160, 150), (30, 120, 190)), 'b': art((240, 120, 40), (190, 30, 80)), 'c': art((230, 220, 180), (245, 240, 225)), 'd': art((60, 40, 120), (20, 10, 50))}
NAMES = [('a', 'R&B Now', 'Apple Music R&B'), ('b', 'Sunset Boulevard Mix Extended Edition', 'Daily Mix'), ('c', 'Tchaikovsky Undiscovered', 'Classical'), ('d', 'Midnight Drive', 'The Night Owls'), ('e', 'Lucha Plus', 'Live TV')]
async def route(r):
    u = r.request.url
    if u.startswith(f'http://127.0.0.1:{PORT}'): return await r.continue_()
    if 'archive.org/services/img/' in u:
        k = u.rsplit('/', 1)[1][:1]
        return await r.fulfill(status=200, content_type='image/png', headers={'access-control-allow-origin': '*'}, body=ARTS.get(k, ARTS['a']))
    return await r.fulfill(status=200, body='{}', content_type='application/json')
HIST = [{'k': 'video:%s.mp4' % k, 'r': 'item', 'it': {'type': 'video', 'id': '%s.mp4' % k, 'uri': 'https://archive.org/download/%s/%s.mp4' % (k, k), 'videoKind': 'archive', 'archive': True, 'name': n, 'favicon': 'https://archive.org/services/img/' + k, 'duration': 3000, 'artist': s}} for k, n, s in NAMES]
SEED = "(function(){ if(!localStorage.getItem('__s')){ localStorage.setItem('__s','1'); localStorage.setItem('radioPlayerPlayedHistory', %s); var f=[]; ['Motown Radio','Jazz FM','Chill','Organic'].forEach(function(n,i){ f.push({name:n, urlToResolve:'http://x/'+i, favicon:'', tags:'soul', stationuuid:'u'+i}); }); localStorage.setItem('radioPlayerFavorites', JSON.stringify(f)); } })();" % json.dumps(json.dumps(HIST))
async def main():
    async with async_playwright() as p:
        B = await p.chromium.launch()
        c = await B.new_context(viewport={'width': 327, 'height': 709}, device_scale_factor=3.3, is_mobile=True, has_touch=True, color_scheme='dark')
        await c.add_init_script(AUTO_NOTICE); await c.add_init_script(SEED)
        pg = await c.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.route('**/*', route)
        await pg.goto(f'http://127.0.0.1:{PORT}/index.html'); await pg.wait_for_timeout(2500)
        print('slides', await pg.evaluate("document.querySelectorAll('#npHeroTrack > .nph-slide').length"))
        await pg.set_viewport_size({'width': 360, 'height': 780}); await pg.wait_for_timeout(500)
        async def look(name, cfg):
            await pg.evaluate("window.ampCarouselSet(%s)" % json.dumps(cfg)); await pg.wait_for_timeout(1000)
            await pg.evaluate("window.scrollTo(0,0)"); await pg.evaluate(INJ); await pg.evaluate("(function(){var t=document.getElementById('npHeroTrack');t.scrollLeft+=2;})()"); await pg.wait_for_timeout(250); await pg.evaluate("document.getElementById('npHeroTrack').scrollLeft=0"); await pg.wait_for_timeout(150)
            print('T', await pg.evaluate("document.querySelector('#npHeroTrack > .nph-slide .nph-title').textContent"))
            await pg.screenshot(path=f'{SHOTS}/cl-{name}.png')
            return await pg.evaluate("""(function(){
              var tr=document.getElementById('npHeroTrack'), sl=[].slice.call(tr.children).filter(function(x){return x.classList.contains('nph-slide')});
              var fav=document.querySelector('#favoritesGrid > .tile'); var favs=document.querySelectorAll('#favoritesGrid > .tile');
              var r=function(e){var b=e.getBoundingClientRect();return {l:Math.round(b.left*10)/10,t:Math.round(b.top*10)/10,w:Math.round(b.width*10)/10,h:Math.round(b.height*10)/10,b:Math.round(b.bottom*10)/10}};
              var hero=document.getElementById('npHero'); var nxt=[].slice.call(document.querySelectorAll('button')).filter(function(b){return b.textContent.trim()=='Favorites' && b.offsetParent})[0]; var lastB=sl.reduce(function(m,s){return Math.max(m,s.getBoundingClientRect().bottom)},0);
              var arts=sl.map(function(s){return r(s.querySelector('.nph-media'))});
              var fgap = fav ? parseFloat(getComputedStyle(fav.parentNode).columnGap) : null;
              return {slideW:sl.map(function(s){return r(s).w}), slideH:sl.map(function(s){return r(s).h}), favW:fav?r(fav).w:null, favGap:fgap,
                gap:sl.length>1?Math.round((sl[1].getBoundingClientRect().left-sl[0].getBoundingClientRect().right)*10)/10:null,
                artTops:arts.map(function(a){return a.t}), artBottoms:arts.map(function(a){return a.b}), heroBottom:r(hero).b, trackBottom:r(tr).b, nextTop:nxt?r(nxt).t:null, slideBottom:lastB, nextTag:nxt?(nxt.className||nxt.tagName):null,
                titleSz:sl.map(function(s){return getComputedStyle(s.querySelector('.nph-title')).fontSize})};})()""")
        R = {}
        INJ = "(function(){var s=document.querySelectorAll('#npHeroTrack > .nph-slide');var d=[['Song','Iguazu Falls (Cataratas del Iguaz\\u00fa)','Sheena Easton','The Ultimate Collection: 100 Hits'],['Live TV','Lucha Plus','Lucha Libre AAA Worldwide','S4 E12 \\u00b7 Clash of Champions'],['Song','Strut','Sheena Easton','']];d.forEach(function(x,i){var e=s[i];e.querySelector('.nph-kicker').textContent=x[0];e.querySelector('.nph-title').textContent=x[1];e.querySelector('.nph-line').textContent=x[2];e.querySelector('.nph-line2').textContent=x[3];e._fitKey='';});})()"
        for sz in ('l', 'm', 's'):
            R['card-' + sz] = await look('card-' + sz, {'mode': 'card', 'cardSize': sz, 'heading': False})
            R['edit-' + sz] = await look('edit-' + sz, {'mode': 'edit', 'cardSize': sz, 'textPos': 'below', 'heading': True})
        R['edit-above-s'] = await look('edit-above-s', {'mode': 'edit', 'cardSize': 's', 'textPos': 'above', 'heading': True})
        R['edit-above-m'] = await look('edit-above-m', {'mode': 'edit', 'cardSize': 'm', 'textPos': 'above', 'heading': True})
        rad = await pg.evaluate("(function(){var c=document.querySelector('#favoritesGrid > .tile');return [getComputedStyle(c).borderTopLeftRadius]})()")
        await pg.evaluate("window.ampCarouselSet({mode:'card',cardSize:'s'})"); await pg.wait_for_timeout(600)
        rc = await pg.evaluate("getComputedStyle(document.querySelector('#npHeroTrack > .nph-slide')).borderTopLeftRadius")
        await pg.evaluate("window.ampCarouselSet({mode:'edit',cardSize:'s'})"); await pg.wait_for_timeout(600)
        re_ = await pg.evaluate("getComputedStyle(document.querySelector('#npHeroTrack > .nph-slide .nph-media')).borderTopLeftRadius")
        check(rad[0] == rc == re_, 'corner radius fav %s card %s editorial %s' % (rad[0], rc, re_))
        for k, v in R.items(): print(k, json.dumps(v))
        c = R['card-s']; check(c['favW'] is not None and abs(c['slideW'][0] - c['favW']) < 0.6 and abs(c['gap'] - c['favGap']) < 0.6, 'Card small = Favorites width %s vs %s, gap %s vs %s' % (c['slideW'][0], c['favW'], c['gap'], c['favGap']))
        for k, v in R.items():
            if k.startswith('edit'):
                check(max(v['artTops']) - min(v['artTops']) < 0.6, k + ' covers share one top %s' % v['artTops'])
                check(v['nextTop'] is not None and 0 <= v['nextTop'] - v['slideBottom'] <= 34, k + ' space under carousel: %s' % (v['nextTop'] - v['slideBottom'] if v['nextTop'] else None))
        r = await pg.evaluate("(function(){var h=document.getElementById('npHero');var tr=document.getElementById('npHeroTrack');var tabs=document.getElementById('homeTabs');var cs=function(e){var c=getComputedStyle(e);return [c.marginTop,c.marginBottom,c.paddingTop,c.paddingBottom].join('/')};var sl=tr.querySelector('.nph-slide').getBoundingClientRect();return {hero:cs(h),track:cs(tr),tabs:cs(tabs),tabsParent:cs(tabs.parentNode),heroBottom:h.getBoundingClientRect().bottom,slideBottom:sl.bottom,trackBottom:tr.getBoundingClientRect().bottom,tabsTop:tabs.getBoundingClientRect().top,sibs:[].map.call(h.parentNode.children,function(c){return c.id||c.className}).slice(0,8)}})()")
        r2 = {}
        for m in ({'mode':'slides'},{'mode':'flow'},{'mode':'card','cardSize':'s'},{'mode':'edit','cardSize':'m','textPos':'below'}):
            await pg.evaluate("window.ampCarouselSet(%s)" % json.dumps(m)); await pg.wait_for_timeout(900)
            r2[m['mode']] = await pg.evaluate("(function(){var g=document.getElementById('homeGroupTabs');var c=getComputedStyle(g);var sl=[].slice.call(document.querySelectorAll('#npHeroTrack > .nph-slide')).reduce(function(m,s){return Math.max(m,s.getBoundingClientRect().bottom)},0);var pill=document.getElementById('homeGroupTabs');return {gapToTabs:Math.round(pill.getBoundingClientRect().top-sl), mt:c.marginTop, disp:c.display, heroBottom:document.getElementById('npHero').getBoundingClientRect().bottom, slideBottom:sl, tabsTop:pill.getBoundingClientRect().top}})()")
        print('GAPS', json.dumps(r2))
        print('SPACING', json.dumps(r))
        print('errs', errs); await B.close()
asyncio.run(main()); print('FAILS', fails)
