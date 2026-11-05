"""Build 479 (Mark): 5px more between the rows on every Podcasts tab. Episode rows (Latest, the
listener's categories, Continue) and rows of show covers (A-Z, Popular); A-Z letter headings keep
their spacing. Uses Mark's backup (path as argument). Phone 412, dark + light. Screenshots in
/tmp/claude-0/t/shots. Gaps are measured edge to edge (next row's top minus this row's bottom)."""
import sys, os
here = os.path.dirname(os.path.abspath(__file__))
_src = open(os.path.join(here, 'test_fav_playing.py')).read()
_head = _src[:_src.index('async def main():')].replace('PORT = 8894', 'PORT = 8896').replace('srv_favplay', 'srv_podspace')
__file__ = os.path.join(here, 'test_fav_playing.py')
exec(_head)
POP = json.dumps({'feed': {'entry': []}})
# Before build 479 (measured on build 477): episode rows -8px edge to edge (their own padding makes
# the visual space), cover rows 24px, Continue rows 4px; letters 46px after a cover row, 30px before.
WANT = {'ep': -3, 'cover': 29, 'cont': 9, 'letter_before': 46, 'letter_after': 30}
GAPS = """(sel)=>{ var g = document.getElementById('stationsGrid'), out = { ep: [], cover: [], cont: [], lb: [], la: [] };
  var kids = Array.from(g.children).filter(c => c.getBoundingClientRect().height > 0);
  for(var i = 1; i < kids.length; i++){
    var a = kids[i-1], b = kids[i], ra = a.getBoundingClientRect(), rb = b.getBoundingClientRect();
    if(Math.abs(rb.top - ra.top) < 2) continue;            // same grid row
    var gap = Math.round(rb.top - ra.bottom);
    if(a.classList.contains('pc-continue-row') && b.classList.contains('pc-continue-row')) out.cont.push(gap);
    else if(a.classList.contains('podcast-date-row') && b.classList.contains('podcast-date-row')) out.ep.push(gap);
    else if(b.classList.contains('song-letter')) out.lb.push(gap);
    else if(a.classList.contains('song-letter')) out.la.push(gap);
    else if(a.classList.contains('tile') && b.classList.contains('tile')){
      // the row above's bottom is its tallest tile
      var rowTop = ra.top, bottom = Math.max.apply(null, kids.filter(k => Math.abs(k.getBoundingClientRect().top - rowTop) < 2).map(k => k.getBoundingClientRect().bottom));
      out.cover.push(Math.round(rb.top - bottom));
    }
  }
  return out; }"""

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
        for theme in ('dark', 'light'):
            T = f'[{theme}]'
            ctx = await b.new_context(viewport={'width': 412, 'height': 915}, device_scale_factor=2, is_mobile=True, has_touch=True, color_scheme=theme)
            await ctx.add_init_script(SEED); await ctx.add_init_script(AUTO_NOTICE)
            await ctx.add_init_script("try{ localStorage.setItem('radioPlayerTheme', '%s'); }catch(e){}" % theme)
            pg = await ctx.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
            subs = json.loads(store['radioPlayerPodcastSubs'])[:12]
            popular = [{'collectionId': s['collectionId'], 'collectionName': s['collectionName'], 'artistName': s.get('artistName', ''), 'artworkUrl600': '', 'feedUrl': s.get('feedUrl', '')} for s in subs]
            async def route(r):
                u = r.request.url
                if '127.0.0.1' in u: return await r.continue_()
                return await r.abort()
            await pg.route('**/*', route)
            await pg.goto(f'http://127.0.0.1:{PORT}/index.html'); await pg.wait_for_timeout(3500)
            # Popular comes from the network: give it the first dozen followed shows. Continue: a
            # few episodes part-way through.
            await pg.evaluate("(list)=>{ __t.ev('podcastPopularCache = ' + JSON.stringify(list)); }", popular)
            await pg.evaluate("""()=>__t.ev(`(function(){ var n = 0; podcastSubs.slice(0, 8).forEach(function(s){ if(s.latestEpisode){ savePodcastProgress(s.latestEpisode, 300 + n * 60, 1800); n++; } }); return n; })()`)""")
            await pg.wait_for_timeout(800)
            await pg.evaluate("document.querySelector('.mobile-nav-btn[data-nav=podcasts]').click()"); await pg.wait_for_timeout(2500)
            tabs = await pg.evaluate("Array.from(document.querySelectorAll('#podcastTabs .home-tab')).map(b => b.textContent.trim())")
            print(T, tabs)
            for i, t in enumerate(tabs):
                await pg.evaluate("(i)=>{ document.querySelectorAll('#podcastTabs .home-tab')[i].click(); window.scrollTo(0,0); }", i); await pg.wait_for_timeout(1800)
                g = await pg.evaluate(GAPS)
                await pg.screenshot(path=f'{shots}/podspace-{theme}-{t.replace(" ", "_").replace("+", "and")}.png')
                print(T, t, {k: sorted(set(v)) for k, v in g.items() if v})
                kinds = [k for k in ('ep', 'cover', 'cont') if g[k]]
                check(kinds, f'{T} {t}: has rows to measure')
                for k in kinds:
                    check(all(x == WANT[k] for x in g[k]), f'{T} {t}: every gap between rows is the old one + 5px ({WANT[k]}) -> {sorted(set(g[k]))}')
                if g['lb']: check(all(x == WANT['letter_before'] for x in g['lb']), f'{T} {t}: letters keep their space above ({sorted(set(g["lb"]))})')
                if g['la']: check(all(x == WANT['letter_after'] for x in g['la']), f'{T} {t}: letters keep their space below ({sorted(set(g["la"]))})')
                # no other page picks it up: leaving Podcasts drops the class
            await pg.evaluate("document.querySelector('.mobile-nav-btn[data-nav=library]').click()"); await pg.wait_for_timeout(1500)
            check(not await pg.evaluate("document.getElementById('stationsGrid').classList.contains('pc-shows-grid')"), f'{T} other pages keep their own spacing')
            check(not errs, f'{T} no page errors {errs[:3]}')
            await ctx.close()
        await b.close()
asyncio.run(main())
print('FAILED: %d' % len(fails) if fails else 'ALL PASS'); raise SystemExit(1 if fails else 0)
