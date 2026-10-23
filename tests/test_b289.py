"""Build 289 (Mark: featured videos from "Ne-Yo feat. Peedi Crakk", not a favourite, and that artist
shouldn't have videos at all): the YouTube lookup dropped "feat. ..." and filed Ne-Yo's videos under
the song's combined credit, and Home's Artist Videos picked any library artist with videos.
Now: Artist Videos only from favourite artists; a combined credit gets no YouTube videos (old ones
cleared); a phone video "A feat. B - Song" goes to A; a stale pick for today is replaced.
Run: python3 tests/test_b289.py (screenshots in /tmp/claude-0/t/shots)"""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
__file__ = os.path.join(HERE, 'test_daily_mixes.py')
src = open(os.path.join(HERE, 'test_daily_mixes.py')).read()
src = src[:src.index('async def run(theme):')]
src = src.replace('PORT = 8803', 'PORT = 8888').replace("srv_daily'", "srv_b289'")
src = src.replace("('Earth, Wind & Fire', 'Funk', 5)]", "('Earth, Wind & Fire', 'Funk', 5), ('Ne-Yo', 'R&B', 6), ('Ne-Yo feat. Peedi Crakk', 'R&B', 2)]")
src = src.replace('" stopPlay:', '''" b289: { neyoKey: function(){ return artistMatchKey('Ne-Yo feat. Peedi Crakk'); },"
  "   stale: function(){ var k = artistMatchKey('Ne-Yo feat. Peedi Crakk'); ytStore[k] = { channels: ['UC' + 'n'.repeat(22)], chTs: Date.now(), ts: Date.now(), fv: YT_FV, mv: true,"
  "     videos: [{ id: 'neyoVid0001', title: 'Ne-Yo - Miss Independent (Official Video)', published: '2024-01-01' }] }; ytSave(); },"
  "   fav: function(n){ var e = findArtistEntry(artistMatchKey(n)); if(!isFavorite(artistFavRecord(e))) toggleFavorite(artistFavRecord(e)); },"
  "   pickNeyo: function(){ ensureDailyLists(); dailyState.videoKey = artistMatchKey('Ne-Yo feat. Peedi Crakk'); dailySave(); },"
  "   key: function(n){ return artistMatchKey(n); }, stored: function(){ return (ytStore[artistMatchKey('Ne-Yo feat. Peedi Crakk')].videos || []).length; }, keys: function(){ return dailyVideoArtistKeys(); }, today: function(){ ensureDailyLists(); return dailyState.videoKey; },"
  "   load: function(){ var e = findArtistEntry(artistMatchKey('Ne-Yo feat. Peedi Crakk')); return loadArtistVideos(e).then(function(r){ return (r.videos || []).length; }); },"
  "   mvFile: function(){ musicVideos.files.push({ uri: 'content://mv/1', name: 'Ne-Yo feat. Peedi Crakk - Can We Chill.mp4', relPath: 'Videos/Ne-Yo feat. Peedi Crakk - Can We Chill.mp4', size: 1, lastModified: 1 }); musicVideos.at = Date.now(); mvIndexCache = null;"
  "     return { lead: musicVideosFor(artistMatchKey('Ne-Yo')).map(function(v){ return v.name; }), combined: musicVideosFor(artistMatchKey('Ne-Yo feat. Peedi Crakk')).length }; } },"
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
        # how it was: Ne-Yo's videos filed under the combined credit, Kay's looked up; no favourite artists
        await pg.evaluate("__d.plays(); __d.vid(); __d.b289.stale(); __d.reset(); __d.b289.pickNeyo();")
        keys = await pg.evaluate("__d.b289.keys()"); nk = await pg.evaluate("__d.b289.neyoKey()")
        check(nk not in keys, f'the combined credit never qualifies for Artist Videos {keys}')
        today = await pg.evaluate("__d.b289.today()")
        check(today != nk, f'today\'s stale pick of "Ne-Yo feat. Peedi Crakk" is replaced ({today})')
        await pg.evaluate("__d.home()"); await pg.wait_for_timeout(1500)
        h = await pg.evaluate(VIDROW)
        check(h == 'Kay', f'Home: Artist Videos from a library artist with videos (build 290: favourites not needed) ({h})')
        # a favourite artist with videos: that one
        await pg.evaluate("__d.b289.fav('Kay'); __d.b289.fav('Ne-Yo feat. Peedi Crakk'); __d.reset();")
        keys = await pg.evaluate("__d.b289.keys()")
        check(nk not in keys, f'the combined credit never qualifies, favourite or not {keys}')
        await pg.evaluate("__d.home()"); await pg.wait_for_timeout(1500)
        h = await pg.evaluate(VIDROW)
        check(h == 'Kay', f'Home: Artist Videos is still Kay all day ({h})')
        await pg.evaluate("document.getElementById('dailyHomeSections').scrollIntoView()"); await pg.wait_for_timeout(300)
        await pg.screenshot(path=f'{shots}/b289-home.png')
        # the combined credit's page: no YouTube videos (the old ones cleared)
        n = await pg.evaluate("__d.b289.load()")
        stored = await pg.evaluate("__d.b289.stored()")
        check(n == 0 and stored == 0, f'"Ne-Yo feat. Peedi Crakk" has no YouTube videos; Ne-Yo\'s copies under it are gone ({n}, {stored})')
        # a phone video credited "A feat. B" goes to A
        mv = await pg.evaluate("__d.b289.mvFile()")
        check(mv['lead'] == ['Can We Chill'] and mv['combined'] == 0, f'a phone video "Ne-Yo feat. Peedi Crakk - Can We Chill" goes to Ne-Yo {mv}')
        check(not errs, f'no page errors {errs[:2]}')
        await b.close()
    print('ALL PASSED' if not fails else f'{len(fails)} FAILED')
    sys.exit(1 if fails else 0)
asyncio.run(main())
