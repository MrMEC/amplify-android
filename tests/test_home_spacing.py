"""Build 397 (Mark): every section on Home ends the same distance above the next heading, whatever the row
holds (covers with a detail line, artist circles with none, 16:9 videos, two-row Playlists, the favourite
cards, Continue Listening and Recent Songs, the daily rows, Top Stations). Uses the library and plays of
test_daily_mixes.py plus the trimmed backup in fixtures. Build 400: the space is 40px. Measures, for each section, the distance from the
bottom of its last row to the next heading; all must match. Also that a long title stops at two lines on Home.
Run: python3 tests/test_home_spacing.py (screenshots in /tmp/claude-0/t/shots)"""
import asyncio, json, sys, os
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
__file__ = os.path.join(HERE, 'test_daily_mixes.py')
_src = open(__file__).read().split("async def run(theme):")[0].replace("PORT = 8803", "PORT = 8886").replace("srv_daily", "srv_spacing").replace('" stopPlay: function', '" imp: function(d){ importBackupData(d, \'merge\'); }, rfr: function(){ refreshDailyPicks(); }, dst: function(){ ensureDailyLists(); return JSON.parse(JSON.stringify({ day: dailyState.day, video: dailyState.videoKey, mixes: dailyState.mixes.map(function(m){ return m.id + \':\' + (m.songs || []).slice(0, 8).join(\',\'); }), mfy: madeForYou().rediscover ? madeForYou().rediscover.map(function(x){ return x.key || x.name || JSON.stringify(x).slice(0, 40); }) : [] })); }, stopPlay: function')
exec(_src)
BACKUP = json.load(open(os.path.join(HERE, 'fixtures', 'layout_backup.json')))
MEASURE = r"""(()=>{
  var bv = document.getElementById('browseView'), blocks = [];
  Array.from(bv.children).forEach(function(e){
    if(!e.offsetParent || e.getBoundingClientRect().height <= 0) return;
    if(e.id === 'dailyHomeSections'){ Array.from(e.children).forEach(function(c){ if(c.offsetParent) blocks.push(c); }); return; }
    if(e.classList.contains('recent-section')){ Array.from(e.querySelectorAll('.recent-col')).forEach(function(c){ if(c.offsetParent) blocks.push(c); }); return; }
    if(e.id === 'npHero' || e.id === 'statusLine' || e.classList.contains('home-tabs')) return;
    blocks.push(e);
  });
  var vw = innerWidth;
  return blocks.map(function(b){
    var h = b.matches('h2, .home-section-head') ? b : b.querySelector('h2');
    var items = Array.from(b.querySelectorAll('.tile, .yt-tile, .vw-tile, .song-row, .mfy-row, .empty-state, .loading-state')).filter(function(x){ return x.offsetParent && !x.parentElement.closest('.tile, .yt-tile, .vw-tile, .song-row'); });
    var boxBottom = items.length ? Math.max.apply(null, items.map(function(x){ return x.getBoundingClientRect().bottom; })) : null;
    var ink = Array.from(b.querySelectorAll('.tile-art, .yt-thumb, .vw-thumb, .tile-name, .tile-sub, .yt-title, .yt-date, .fav-card, .song-row, .empty-state')).filter(function(x){ var r = x.getBoundingClientRect(); return x.offsetParent && r.height > 0 && r.left < vw && r.right > 0; });
    var inkBottom = ink.length ? Math.max.apply(null, ink.map(function(x){ return x.getBoundingClientRect().bottom; })) : null;
    var clamp = Array.from(b.querySelectorAll('.home-row .tile-name, .home-row .yt-title')).filter(function(x){ return x.offsetParent && !x.closest('.fav-card, .tile-row, .song-row'); }).map(function(x){ var cs = getComputedStyle(x); return Math.round(x.getBoundingClientRect().height / (parseFloat(cs.lineHeight) || 17)); });
    return { name: (h ? h.textContent.trim() : (b.id || b.className)).slice(0, 24), headTop: h ? Math.round(h.getBoundingClientRect().top) : null,
             boxBottom: boxBottom === null ? null : Math.round(boxBottom), inkBottom: inkBottom === null ? null : Math.round(inkBottom), maxLines: clamp.length ? Math.max.apply(null, clamp) : 0 };
  });
})()"""
async def run(theme, w, h):
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
        ctx = await b.new_context(viewport={'width': w, 'height': h}, device_scale_factor=2, is_mobile=True, has_touch=True, color_scheme=theme)
        await ctx.add_init_script(MOCK); await ctx.add_init_script(AUTO_NOTICE)
        await ctx.add_init_script("try{ localStorage.setItem('radioPlayerTheme', %s); }catch(e){}" % json.dumps(theme))
        pg = await ctx.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.route('**/*', lambda route: route.continue_() if '127.0.0.1' in route.request.url else route.abort())
        await pg.goto(f'http://127.0.0.1:{PORT}/index.html'); await pg.wait_for_timeout(2500)
        await pg.evaluate("""(function(){ var ov=document.getElementById('addMusicOverlay'); if(ov) ov.classList.add('open');
          var btn=document.getElementById('addMusicFolderBtn'); btn.disabled=false; btn.click(); })()""")
        for _ in range(90):
            await pg.wait_for_timeout(500)
            if await pg.evaluate("__d.n()") >= len(SONGS): break
        await pg.evaluate("document.getElementById('addMusicOverlay').classList.remove('open')")
        await pg.evaluate('__d.plays(); __d.vid(); __d.reset();')
        await pg.evaluate("(d)=>{ __d.imp(d); }", BACKUP); await pg.wait_for_timeout(2000)
        await pg.evaluate("try{ hideImportPanel(); setStatus('', false); }catch(e){}")
        await pg.evaluate('__d.home()'); await pg.wait_for_timeout(2500)
        await pg.evaluate("document.querySelectorAll('button').forEach(x=>{ if(x.textContent.trim()==='OK' && x.offsetParent) x.click(); })"); await pg.wait_for_timeout(600)
        if os.environ.get('NOEQ'): await pg.evaluate("document.querySelectorAll('[style*=min-height]').forEach(function(t){ if(t.closest('.home-row')) t.style.minHeight=''; })"); await pg.wait_for_timeout(300)
        r = await pg.evaluate(MEASURE)
        if os.environ.get('DBG'): print(await pg.evaluate(os.environ['DBG']))
        T = f'[{theme} {w}]'
        gaps = []
        for i in range(len(r) - 1):
            a, nx = r[i], r[i + 1]
            if a['boxBottom'] is None or nx['headTop'] is None: continue
            gaps.append((a['name'], nx['name'], nx['headTop'] - a['boxBottom'], nx['headTop'] - (a['inkBottom'] or a['boxBottom'])))
        for g in gaps: print(T, g)
        names = [x['name'] for x in r]
        check(any('Top Artists' in n for n in names) and any('Hear It Again' in n for n in names) and ('homeGroupTabs' in names) and any(n == 'Kay' for n in names), f'{T} the busy Home has every kind of row {names}')
        vals = sorted(set(g[2] for g in gaps))
        check(len(gaps) >= 8 and vals[-1] - vals[0] <= 1 and vals[0] == 40, f'{T} every section ends 40px above the next heading {vals}')
        ink = [g[3] - g[2] for g in gaps]
        check(all(0 <= x <= 20 for x in ink), f'{T} no row leaves more than one line of blank under what is on screen {ink}')
        check(all(x['maxLines'] <= 2 for x in r), f'{T} titles on Home rows stop at two lines {[(x["name"], x["maxLines"]) for x in r]}')
        pl = await pg.evaluate("""(()=>{ var t=Array.from(document.querySelectorAll('#playlistsHomeGrid > .tile')).filter(x=>x.offsetParent); if(t.length<2) return null;
          var tops=[...new Set(t.map(x=>Math.round(x.getBoundingClientRect().top)))].sort((a,b)=>a-b); if(tops.length<2) return null;
          var r1=t.filter(x=>Math.round(x.getBoundingClientRect().top)===tops[0]); var b1=Math.max(...r1.map(x=>Math.max(...Array.from(x.querySelectorAll('.tile-name,.tile-sub')).map(y=>y.getBoundingClientRect().bottom))));
          return Math.round(tops[1]-b1); })()""")
        if pl is not None: check(pl <= 24, f'{T} the two Playlists rows sit close together ({pl}px)')
        # Build 402: a library refresh picks the Daily Mixes, Discover, Made for You and the video artist again
        before = await pg.evaluate("__d.dst()")
        await pg.evaluate("__d.rfr()"); await pg.wait_for_timeout(1200)
        after = await pg.evaluate("__d.dst()")
        changed = [i for i, (a, c) in enumerate(zip(before['mixes'], after['mixes'])) if a != c]
        check(after['day'].endswith('#1') and len(changed) >= 1, f'{T} refresh makes new mixes (day {after["day"]}, {len(changed)} of {len(after["mixes"])} lists changed)')
        await pg.evaluate("__d.rfr()"); await pg.wait_for_timeout(600)
        check((await pg.evaluate("__d.dst()"))['day'].endswith('#2'), f'{T} and again on the next refresh')
        names2 = [x['name'] for x in await pg.evaluate(MEASURE)]
        check(any('Daily Mix' in n for n in names2) and any(n == 'Kay' for n in names2), f'{T} Home still shows the rows after a refresh {names2}')
        H = await pg.evaluate("document.documentElement.scrollHeight")
        await pg.set_viewport_size({'width': w, 'height': min(H, 7000)}); await pg.wait_for_timeout(800)
        await pg.screenshot(path=f'{shots}/home-spacing-{theme}-{w}.png')
        check(not errs, f'{T} no page errors {errs[:3]}')
        await b.close()
async def main():
    await run('dark', 412, 900)
    await run('light', 360, 800)
    print('ALL PASSED' if not fails else f'FAILED {fails}')
    sys.exit(1 if fails else 0)
asyncio.run(main())
