"""Build 494 (Mark): station covers set on the phone reach the car. (Built from test_car_recent_plays.) Build 493: Android Auto's Listen > Continue Listening is one list of songs, stations and
unfinished episodes in the order they were played (Recent Songs folded into it); Podcasts' own
Continue Listening stays episodes only. Run: python3 tests/test_car_recent_plays.py"""
import sys as _nsys, os as _nos; _nsys.path.insert(0, _nos.path.dirname(_nos.path.abspath(__file__))); from notice_auto import AUTO_NOTICE
import os, sys, json
_here = os.path.dirname(os.path.abspath(__file__))
_src = open(os.path.join(_here, 'test_custom_station_fav.py')).read()
_src = _src[:_src.index('\nasync def main():')].replace('PORT = 8833', 'PORT = 8842').replace('srv_csfav', 'srv_carart').replace('window.__c = {\n', 'window.__c = {\n ev: function(c){ return eval(c); },\n', 1)
__file__ = os.path.join(_here, 'test_custom_station_fav.py')
exec(_src)


async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
        ctx = await b.new_context(viewport={'width': 412, 'height': 900}, is_mobile=True, has_touch=True)
        await ctx.add_init_script(MOCK); await ctx.add_init_script(AUTO_NOTICE)
        pg = await ctx.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.route('**/*', directory)
        await pg.goto(f'http://127.0.0.1:{PORT}/index.html'); await pg.wait_for_timeout(2500)
        await pg.evaluate("""(function(){ var ov=document.getElementById('addMusicOverlay'); if(ov) ov.classList.add('open');
          var btn=document.getElementById('addMusicFolderBtn'); btn.disabled=false; btn.click(); })()""")
        for _ in range(60):
            await pg.wait_for_timeout(500)
            if len(await pg.evaluate('__t.tracks()')) >= 4: break
        await pg.evaluate("(function(){ var ov=document.getElementById('addMusicOverlay'); if(ov) ov.classList.remove('open'); })()")
        SEED = """(function(){
          var park = { name: 'DMagicWorld', url: 'https://jenny.torontocast.com:9014/stream', urlToResolve: 'https://jenny.torontocast.com:9014/stream', favicon: '', tags: 'disney' };
          favorites = [park]; saveFavorites();
          var m = loadCustomArtMap(); m[favKey(park)] = 'https://img.example/dmw.jpg'; m['uuid-1234-5678-9abc-def012345678'] = 'https://img.example/dir.jpg'; m['artist:kay'] = 'https://img.example/a.jpg';
          try{ localStorage.setItem(CUSTOM_ART_KEY, JSON.stringify(m)); }catch(e){}
          genrePrefs['disney'] = { order: ['b'], hidden: ['c'], parkOrder: [], parkHidden: [] };
          return 1; })()"""
        await pg.evaluate("c => __c.ev(c)", SEED)
        await pg.evaluate('__c.car()')
        for _ in range(20):
            await pg.wait_for_timeout(500)
            if await pg.evaluate("!!(window.__cat && window.__cat.stationArt)"): break
        cat = await pg.evaluate("({ art: window.__cat.stationArt, park: window.__cat.lists.parkRadio, gp: window.__cat.genrePrefs })")
        print(cat)
        art = cat['art'] or {}
        check(art.get('https://jenny.torontocast.com:9014/stream') == 'https://img.example/dmw.jpg', 'a park station\'s cover by its stream address')
        check(art.get('uuid-1234-5678-9abc-def012345678') == 'https://img.example/dir.jpg', 'a directory station\'s cover by its id')
        check('artist:kay' not in art, 'no artist pictures in the station map')
        check([p['title'] for p in (cat['park'] or [])] == ['DMagicWorld'] and cat['park'][0]['art'] == 'https://img.example/dmw.jpg', 'Park radio list with its cover')
        check(cat['gp'].get('disney', {}).get('hidden') == ['c'], 'genre prefs carried')
        check(not errs, f'no page errors {errs[:2]}')
        await b.close()
    print('ALL PASS' if not fails else f'FAILED {fails}')

asyncio.run(main())
