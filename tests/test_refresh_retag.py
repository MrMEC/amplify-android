"""Build 240: Refresh picks up tag changes made outside Amplify. A song file retagged by another
app (new size and date) is updated in place: same song (same key), new title/tags, still a
favourite, still in its playlist, its plays kept, no second copy. Copies left by older builds'
refreshes (the same file twice) are merged into one, keeping favourites and plays from both.
Real MP3/FLAC files retagged with mutagen; the mocked plugin lists the folder. 412 wide.
Run: python3 tests/test_refresh_retag.py (screenshots in /tmp/claude-0/t/shots)"""
import sys as _nsys, os as _nos; _nsys.path.insert(0, _nos.path.dirname(_nos.path.abspath(__file__))); from notice_auto import AUTO_NOTICE
import os, json, time
_here = os.path.dirname(os.path.abspath(__file__))
_src = open(os.path.join(_here, 'test_tag_covers.py')).read()
_head = _src[:_src.index('async def run(p, theme, full):')]
_head = _head.replace("PORT = 8830", "PORT = 8841").replace("srv_covers", "srv_retag")
RHOOK = (r"""window.__r = {
 find: function(title){ return libraryTracks.filter(function(x){ return x.name === title; })[0]; },
 fav: function(title){ toggleFavorite(__r.find(title)); },
 pl: function(title){ stationPlaylists.push({ id: 'pl_r', label: 'Road', stations: [__r.find(title)] }); saveStationPlaylists(); },
 plays: function(title, n){ var m = loadSongPlays(); m[favKey(__r.find(title))] = [n, Date.now()]; localStorage.setItem(SONG_PLAYS_KEY, JSON.stringify(m)); },
 key: function(title){ var t = __r.find(title); return t ? favKey(t) : null; },
 state: function(){
   var pl = stationPlaylists.filter(function(p){ return p.id === 'pl_r'; })[0];
   return { tracks: libraryTracks.map(function(t){ return [t.name, favKey(t)]; }), favKeys: favorites.map(favKey),
     storedFavKeys: JSON.parse(localStorage.getItem('radioPlayerFavorites') || '[]').map(favKey),
     pl: pl ? pl.stations.map(favKey) : [], plays: loadSongPlays() };
 },
 oldRefresh: function(name){
   return fetch('/__listing.json', { cache: 'no-store' }).then(function(r){ return r.json(); }).then(function(list){
     var f = list.filter(function(x){ return x.name === name; })[0];
     return nativeFileFromEntry(f).then(function(file){ return importLocalFiles([file], { fromFolder: true }); });
   });
 },
 statusLog: function(){ return window.__status || []; }
};
""").replace('\n', '\\n').replace('"', '\\"')
_head = _head.replace('HOOK = ("window.__t = {', 'HOOK = ("' + RHOOK + 'window.__t = {', 1)
__file__ = os.path.join(_here, 'test_tag_covers.py')
exec(_head)
from mutagen.id3 import ID3, TIT2, TCON
from mutagen.flac import FLAC

WATCH = """(()=>{ window.__status=[]; var el=document.getElementById('statusLineText');
  new MutationObserver(function(){ var t=el.textContent.trim(); if(t) window.__status.push(t); }).observe(el,{childList:true,characterData:true,subtree:true}); })()"""


def retag_mp3(name, title):
    tags = ID3(F(name)); tags.add(TIT2(encoding=3, text=title)); tags.add(TCON(encoding=3, text='Rock'))
    tags.add(TIT2(encoding=3, text=title)); tags.save(padding=lambda info: 4096)
    os.utime(F(name), (time.time() + 60, time.time() + 60))


def retag_flac(name, title):
    f = FLAC(F(name)); f['title'] = title; f.save()
    os.utime(F(name), (time.time() + 120, time.time() + 120))


async def main():
    async with async_playwright() as p:
        make_library()
        open(f'{root}/__listing.json', 'w').write(json.dumps(listing()))
        b = await p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
        ctx = await b.new_context(viewport={'width': 412, 'height': 900}, device_scale_factor=2, is_mobile=True, has_touch=True, color_scheme='dark')
        await ctx.add_init_script(MOCK); await ctx.add_init_script(AUTO_NOTICE)
        await ctx.add_init_script('window.__listing = %s;' % json.dumps(listing()))
        pg = await ctx.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.goto(f'http://127.0.0.1:{PORT}/index.html'); await pg.wait_for_timeout(2500)
        await pg.evaluate("""(function(){ var ov=document.getElementById('addMusicOverlay'); if(ov) ov.classList.add('open');
          var btn=document.getElementById('addMusicFolderBtn'); btn.disabled=false; btn.click(); })()""")
        for _ in range(60):
            await pg.wait_for_timeout(500)
            if await pg.evaluate('__t.tracks().length') >= 4: break
        await pg.evaluate("(function(){ var ov=document.getElementById('addMusicOverlay'); if(ov) ov.classList.remove('open'); try{ hideImportPanel(); }catch(e){} })()")
        await pg.evaluate(WATCH)
        check(await pg.evaluate('__t.tracks().length') == 4, 'library imported (4 songs)')

        # ---- a song retagged outside Amplify ----
        k2 = await pg.evaluate("__r.key('Ann Two')")
        await pg.evaluate("__r.fav('Ann Two'); __r.pl('Ann Two'); __r.plays('Ann Two', 5)")
        retag_mp3('02 Two.mp3', 'Ann Two (Remastered)')
        open(f'{root}/__listing.json', 'w').write(json.dumps(listing()))
        await pg.evaluate('__t.refresh()')
        for _ in range(40):
            await pg.wait_for_timeout(500)
            if any('updated' in x or 'up to date' in x for x in await pg.evaluate('__r.statusLog()')): break
        st = await pg.evaluate('__r.state()')
        names = [t[0] for t in st['tracks']]
        check(len(names) == 4 and names.count('Ann Two (Remastered)') == 1 and 'Ann Two' not in names, f'the retagged song is updated, no second copy {names}')
        check(await pg.evaluate("__r.key('Ann Two (Remastered)')") == k2, 'it is the same song (same key)')
        check(k2 in st['favKeys'] and k2 in st['storedFavKeys'], 'still a favourite (and saved)')
        check(st['pl'] == [k2], f'still in its playlist {st["pl"]}')
        check((st['plays'].get(k2) or [0])[0] == 5, f'its plays kept {st["plays"].get(k2)}')
        tg = await pg.evaluate("(()=>{ var t = __r.find('Ann Two (Remastered)'); return [t.genre, t.tags]; })()")
        check(tg[0] == 'Rock', f'other tags too (genre {tg})')
        log = await pg.evaluate('__r.statusLog()')
        check(any('1 song updated' in x for x in log), f'Refresh says it updated a song {log[-2:]}')
        # the Songs list shows it once
        await pg.evaluate("__t.runLibrarySection('songs')"); await pg.wait_for_timeout(800)
        rows = await pg.evaluate("Array.from(document.querySelectorAll('#stationsGrid .song-row-title')).map(e=>e.textContent)")
        check(rows.count('Ann Two (Remastered)') == 1 and 'Ann Two' not in rows, f'the Songs list shows it once {rows}')
        await pg.screenshot(path=f'{shots}/retag-songs.png')
        # refreshing again changes nothing
        await pg.evaluate("window.__status = []; __t.refresh()")
        for _ in range(30):
            await pg.wait_for_timeout(400)
            if await pg.evaluate('__r.statusLog().length'): break
        log = await pg.evaluate('__r.statusLog()')
        check(any('up to date' in x for x in log) and await pg.evaluate('__t.tracks().length') == 4, f'refresh again: up to date {log}')

        # ---- a duplicate left by an older build ----
        k3 = await pg.evaluate("__r.key('Ann Three')")
        await pg.evaluate("__r.plays('Ann Three', 3)")
        retag_flac('03 Three.flac', 'Ann Three (Live)')
        open(f'{root}/__listing.json', 'w').write(json.dumps(listing()))
        await pg.evaluate("__r.oldRefresh('03 Three.flac')"); await pg.wait_for_timeout(2500)
        await pg.evaluate("(function(){ try{ hideImportPanel(); }catch(e){} })()")
        st = await pg.evaluate('__r.state()')
        names = [t[0] for t in st['tracks']]
        check(len(names) == 5 and 'Ann Three' in names and 'Ann Three (Live)' in names, f'(the old refresh made a second copy) {names}')
        await pg.evaluate("__r.fav('Ann Three (Live)')")
        kdup = await pg.evaluate("__r.key('Ann Three (Live)')")
        await pg.evaluate("window.__status = []; __t.refresh()")
        for _ in range(40):
            await pg.wait_for_timeout(500)
            if any('merged' in x or 'up to date' in x for x in await pg.evaluate('__r.statusLog()')): break
        st = await pg.evaluate('__r.state()')
        names = [t[0] for t in st['tracks']]
        kept = await pg.evaluate("__r.key('Ann Three (Live)')")
        check(len(names) == 4 and names.count('Ann Three (Live)') == 1 and 'Ann Three' not in names, f'refresh merges the copies into one {names}')
        check(kept in st['favKeys'] and (st['plays'].get(kept) or [0])[0] == 3, f'the one kept has the favourite and the plays ({kept in st["favKeys"]}, {st["plays"].get(kept)})')
        check(not (set([k3, kdup]) - set([kept])) & set(st['favKeys']) and len([x for x in st['plays'] if x in (k3, kdup) and x != kept]) == 0, 'nothing points at the removed copy')
        log = await pg.evaluate('__r.statusLog()')
        check(any('1 duplicate merged' in x for x in log), f'Refresh says it merged a duplicate {log[-2:]}')
        # survives a restart
        await pg.reload(); await pg.wait_for_timeout(3000)
        n = await pg.evaluate('__t.tracks().map(function(t){ return t.name; })')
        check(sorted(n) == sorted(['Ann One', 'Ann Two (Remastered)', 'Ann Three (Live)', 'Ann Four']), f'kept after a restart {n}')
        check(not errs, f'no page errors {errs[:3]}')
        await b.close()
    print('ALL PASSED' if not fails else f'FAILED {fails}')

asyncio.run(main())
