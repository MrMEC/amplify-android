"""Build 616: after a restart, local movies and TV shows in the Home carousel keep their titles,
and a TV show reads "TV Show". Mark's size 327x700 dpr 3.3. Run: python3 tests/test_hero_video_restart.py"""
import os, asyncio
HERE = os.path.dirname(os.path.abspath(__file__))
src = open(os.path.join(HERE, 'test_cf_after_video.py')).read()
head = src[:src.index('fails = []')].replace("'/tmp/claude-0/t/srv_cfv'", "'/tmp/claude-0/t/srv_616'").replace('8848', '8864')
exec(head)
fails = []
def check(c, m):
    print(('PASS ' if c else 'FAIL ') + m)
    if not c: fails.append(m)
async def ev(pg, js): return await pg.evaluate('(js) => window.__h.ev(js)', js)
SH = '/tmp/claude-0/t/shots'
SEED = """(function(){
  var ep = {type:'video', id:'v:ep1', uri:'x', fileName:'All in the Family S01E01.mkv', kind:'episode', show:'All in the Family', showKey:'all in the family', season:1, episode:1, epTitle:'Meet the Bunkers', duration:1560, addedAt:1};
  var ep2 = {type:'video', id:'v:ep2', uri:'y', fileName:'The 90s S01E01.mkv', kind:'episode', show:'The 90s: The Last Great Decade', showKey:'the 90s', season:1, episode:2, epTitle:'', duration:5280, addedAt:1};
  var mv = {type:'video', id:'v:mv1', uri:'z', fileName:'Groundhog Day (1993).mkv', kind:'movie', title:'Groundhog Day', year:1993, duration:6060, addedAt:1};
  videoLib = { movies:[mv], shows:[{key:'all in the family', title:'All in the Family', episodes:[ep], seasons:[1]}, {key:'the 90s', title:'The 90s: The Last Great Decade', episodes:[ep2], seasons:[1]}],
    byId:{'v:ep1':ep, 'v:ep2':ep2, 'v:mv1':mv}, showsByKey:{'all in the family':{key:'all in the family', title:'All in the Family', episodes:[ep], seasonPosters:{}, poster:'', backdrop:''}, 'the 90s':{key:'the 90s', title:'The 90s: The Last Great Decade', episodes:[ep2], seasonPosters:{}, poster:'', backdrop:''}} };
  heroHist = [{k:'video:v:ep1', r:'video', id:'v:ep1'}, {k:'video:v:ep2', r:'video', id:'v:ep2'}, {k:'video:v:mv1', r:'video', id:'v:mv1'}];
  renderNpHero(); return 1; })()"""
READ = "heroSlides.map(function(s){ return [s.querySelector('.nph-kicker').textContent, s.querySelector('.nph-title').textContent, s.querySelector('.nph-line').textContent]; })"
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
        ctx = await b.new_context(viewport={'width': 327, 'height': 700}, device_scale_factor=3.3, is_mobile=True, has_touch=True, color_scheme='dark')
        await ctx.add_init_script(MOCK); await ctx.add_init_script(AUTO_NOTICE)
        pg = await ctx.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.goto(f'http://127.0.0.1:{PORT}/index.html'); await pg.wait_for_timeout(2500)
        await ev(pg, SEED); await pg.wait_for_timeout(800)
        print(await ev(pg, "JSON.stringify(heroItems().map(function(t){return [t.name,t.videoKind]})) + ' ' + JSON.stringify(heroHistLoad().map(function(r){var t=heroResolve(r); return t? [favKey(t), isBlacklisted(t)] : null;}))"))
        sl = await ev(pg, READ); print(sl)
        await pg.screenshot(path=f'{SH}/616-hero-port.png')
        d = {x[1]: x for x in sl}
        check('All in the Family' in d and d['All in the Family'][0] == 'TV Show', 'episode titled and called TV Show %s' % d.get('All in the Family'))
        check('The 90s: The Last Great Decade' in d and d['The 90s: The Last Great Decade'][0] == 'TV Show', '2nd show OK')
        check('Groundhog Day' in d and d['Groundhog Day'][0] == 'Movie' and '1993' in d['Groundhog Day'][2], 'movie titled, Movie, year %s' % d.get('Groundhog Day'))
        check(all(x[1] for x in sl), 'no slide without a title')
        check(not errs, 'no errors %s' % errs[:2])
        await ev(pg, "var b=document.querySelector('[data-carousel-opt=flow]'); b.click(); 1"); await pg.wait_for_timeout(1200)
        fi = await ev(pg, "(function(){ var f=document.querySelector('.nph-flow-info'); return f ? [f.querySelector('.nph-kicker').textContent, f.querySelector('.nph-title').textContent, f.querySelector('.nph-line').textContent] : null; })()")
        print('flow', fi); await pg.screenshot(path=f'{SH}/616-hero-flow.png')
        check(fi and fi[0]=='TV Show' and fi[1]=='All in the Family', 'Flow caption TV Show + title %s' % fi)
        await b.close()
    print('ALL PASSED' if not fails else 'FAILED %s' % fails)
asyncio.run(main())
