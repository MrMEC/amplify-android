"""Build 290 (Mark): Home's Artist Videos comes from any library artist (not only favourites), and an
artist never comes back until every artist has had a turn; never a combined credit ("A feat. B"),
never one known to have no videos. Run: python3 tests/test_b290_videos.py"""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
__file__ = os.path.join(HERE, 'test_daily_mixes.py')
src = open(os.path.join(HERE, 'test_daily_mixes.py')).read()
src = src[:src.index('async def run(theme):')]
src = src.replace('PORT = 8803', 'PORT = 8890').replace("srv_daily'", "srv_b290v'")
src = src.replace("('Earth, Wind & Fire', 'Funk', 5)]", "('Earth, Wind & Fire', 'Funk', 5), ('Ne-Yo', 'R&B', 6), ('Ne-Yo feat. Peedi Crakk', 'R&B', 2)]")
src = src.replace('" stopPlay:', '''" v290: { seed: function(withVids){ buildArtistIndex().forEach(function(e){ var v = withVids.indexOf(e.name) !== -1;"
  "     ytStore[e.key] = { channels: v ? ['UC' + 'x'.repeat(22)] : [], chTs: Date.now(), ts: Date.now(), fv: YT_FV, mv: v, videos: v ? [{ id: (e.key + 'vvvvvvvvvvv').slice(0, 11), title: e.name + ' - Song (Official Video)', published: '2024-01-01' }] : [] }; }); ytSave(); },"
  "   unknown: function(name){ delete ytStore[artistMatchKey(name)]; ytSave(); },"
  "   day: function(){ ensureDailyLists(); return dailyState.videoKey ? findArtistEntry(dailyState.videoKey).name : null; },"
  "   nextDay: function(){ var s = JSON.parse(localStorage.getItem('radioPlayerDailyMixes')); s.day = '2000-1-1'; localStorage.setItem('radioPlayerDailyMixes', JSON.stringify(s)); dailyState = null;"
  "     var h = JSON.parse(localStorage.getItem('radioPlayerVideoArtistHistory') || '[]'); h.forEach(function(x){ x.day = 'old-' + x.day; }); localStorage.setItem('radioPlayerVideoArtistHistory', JSON.stringify(h)); },"
  "   favs: function(){ return favorites.filter(function(f){ return f.type === 'artist'; }).length; } },"
  " stopPlay:''')
exec(src)
VIDROW = "(()=>{ const s = document.querySelector('#dailyHomeSections .daily-home-section[data-daily=videos]'); return s && s.style.display !== 'none' ? s.querySelector('h2').textContent.trim() : null; })()"
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
        ctx = await b.new_context(viewport={'width': 412, 'height': 900}, device_scale_factor=2, is_mobile=True, has_touch=True, color_scheme='dark')
        await ctx.add_init_script(MOCK); await ctx.add_init_script(AUTO_NOTICE)
        pg = await ctx.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.route('**/*', lambda route: route.continue_() if '127.0.0.1' in route.request.url else route.abort())
        await pg.goto(f'http://127.0.0.1:{PORT}/index.html'); await pg.wait_for_timeout(2500)
        await pg.evaluate("""(function(){ var ov=document.getElementById('addMusicOverlay'); if(ov) ov.classList.add('open');
          var btn=document.getElementById('addMusicFolderBtn'); btn.disabled=false; btn.click(); })()""")
        for _ in range(90):
            await pg.wait_for_timeout(500)
            if await pg.evaluate("__d.n()") >= len(SONGS): break
        await pg.evaluate("document.getElementById('addMusicOverlay').classList.remove('open'); try{ hideImportPanel(); setStatus('', false); }catch(e){}")
        check(await pg.evaluate("__d.n()") == len(SONGS), 'library imported')
        check(await pg.evaluate("__d.v290.favs()") == 0, 'no favourite artists')
        WITH = ['Prince', 'Madonna', 'Kay', 'Lee', 'Ne-Yo', 'Ne-Yo feat. Peedi Crakk']
        await pg.evaluate("(w) => { __d.plays(); __d.reset(); __d.v290.seed(w); }", WITH)
        picks = []
        for day in range(5):
            name = await pg.evaluate("__d.v290.day()")
            picks.append(name)
            if day == 0:
                await pg.evaluate("__d.home()"); await pg.wait_for_timeout(1200)
                h = await pg.evaluate(VIDROW)
                check(h == name, f"Home shows the day's artist ({h})")
                again = await pg.evaluate("__d.v290.day()")
                check(again == name, 'the same artist all day')
            await pg.evaluate("__d.v290.nextDay()")
        print('picks', picks)
        eligible = ['Prince', 'Madonna', 'Kay', 'Lee', 'Ne-Yo']
        check(sorted(picks) == sorted(eligible), f'five days, five different artists, each with videos, none a favourite {picks}')
        check('Ne-Yo feat. Peedi Crakk' not in picks, 'never the combined credit')
        check(not any(x in picks for x in ['Rick James', 'Morris Day', 'Earth, Wind & Fire']), 'never one known to have no videos')
        # everyone with videos has had a turn; one artist not looked up yet: looked up (no network here, so
        # nothing found) rather than repeating an earlier one
        # day 6: everyone with videos has had a turn, the rest are known to have none: it starts over
        # (the last month kept out, so with 5 artists all have been shown recently: the one shown longest ago... any)
        n6 = await pg.evaluate("__d.v290.day()")
        print('day 6', n6)
        check(n6 in eligible, f'day 6: when everyone has had a turn it starts over instead of showing nothing ({n6})')
        check(not errs, f'no page errors {errs[:2]}')
        await b.close()
    print('ALL PASSED' if not fails else f'{len(fails)} FAILED')
    sys.exit(1 if fails else 0)
asyncio.run(main())
