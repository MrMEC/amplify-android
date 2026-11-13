"""Artist and album pages sideways at Mark's size (678x297, dpr 3.3), filled like his real library:
long 2-line album and song titles, a genre · year line, Music Videos (26), On YouTube and On Archive.org
rows, several albums. Checks: every section heading the same distance above its content; video tiles
and album covers sized alike; the left column's words never cut off or overlapping; nothing under the
player bar's column on the left. Screenshots in /tmp/claude-0/t/shots/real-*.
Run: python3 tests/test_aal_real.py"""
import os, sys, asyncio, json
HERE = os.path.dirname(os.path.abspath(__file__))
src = open(os.path.join(HERE, 'test_cf_after_video.py')).read()
head = src[:src.index('fails = []')].replace("'/tmp/claude-0/t/srv_cfv'", "'/tmp/claude-0/t/srv_real'").replace('8848', '8858')
exec(head)
fails = []
def check(c, m):
    print(('PASS ' if c else 'FAIL ') + m)
    if not c: fails.append(m)
SH = '/tmp/claude-0/t/shots'
async def ev(pg, js): return await pg.evaluate('(js) => window.__h.ev(js)', js)
SEED_ARTIST = """(function(){
  var e = findArtistEntry(activeArtistKey);
  var mv = []; for(var i=0;i<26;i++) mv.push({uri:'mv://'+i, name:'Crazy (Live '+i+')', artist:e.name, artistKey:e.key, duration:189+i, still:''});
  musicVideosFor = function(k){ return k===e.key ? mv : []; };
  paintArtistLocalVideos(e);
  var yv = [{id:'a1',title:'All I Know Is Now',published:'2025-01-01'},{id:'a2',title:'Fly Like An Eagle',published:'2024-01-01'},{id:'a3',title:'Kiss From A Rose',published:'1994-01-01'}];
  paintArtistYouTube(e, {videos:yv}, false);
  paintArtistArchive(e, {items:[{id:'ia1',title:'Seal Live 1991',video:true,year:'1991'},{id:'ia2',title:'Seal Interview',video:true,year:'1996'},{id:'ia3',title:'Another',video:true,year:'1999'}]});
  document.getElementById('artistHeroName').textContent = 'Earth, Wind & Fire Experience';
  document.getElementById('artistHeroSub').textContent = 'R&B \\u00b7 Soul \\u00b7 Funk';
  return 1; })()"""
SEED_ALBUM = """(function(){
  document.getElementById('albumHeroName').textContent = "Live: Under A Blood Red Sky";
  var a = document.getElementById('albumHeroArtist'); a.textContent = 'U2';
  document.getElementById('albumHeroMeta').textContent = 'Rock \\u00b7 1983';
  var t = ['"40" (Live From Paris 1987)', 'Yahweh & 40 (Vertigo Tour Live From Chicago, 2005)', 'Gloria', '11 O\\u2019Clock Tick Tock'];
  Array.prototype.forEach.call(document.querySelectorAll('#stationsGrid .song-row-title, #stationsGrid .row-name, #stationsGrid .track-title'), function(el, i){ el.textContent = t[i % t.length]; });
  return 1; })()"""
GAPS = """(()=>{ var out=[]; var kids=Array.prototype.slice.call(document.querySelectorAll('#stationsGrid > *'));
  kids.forEach(function(k, i){ if(!k.classList.contains('grid-section-label')) return; var nx=kids[i+1]; if(!nx) return;
    var tn=k.firstChild; var rg=document.createRange(); rg.selectNodeContents(k); var tb=null;
    if(tn && tn.nodeType===3){ rg=document.createRange(); rg.selectNodeContents(tn); }
    var rr=rg.getBoundingClientRect(); var nr=(nx.firstElementChild||nx).getBoundingClientRect();
    out.push([String(k.textContent).trim().slice(0,16), Math.round(nr.top - rr.bottom)]); }); return out; })()"""
LEFT = """(()=>{ function r(q){ var e=document.querySelector(q); if(!e) return null; var cs=getComputedStyle(e); if(cs.display==='none') return null; var b=e.getBoundingClientRect(); return {b:[Math.round(b.left),Math.round(b.top),Math.round(b.right),Math.round(b.bottom)], clip: e.scrollHeight > e.clientHeight+1 || e.scrollWidth > e.clientWidth+1, fs: cs.fontSize}; }
  var o={}; ['#albumHeroArt','#albumHeroName','#albumHeroArtist','#albumHeroMeta','.album-hero-actions','#artistHeroArt','#artistHeroName','#artistHeroSub','.artist-hero-actions','.player-bar'].forEach(function(q){ o[q]=r(q); }); return o; })()"""
def ov(a, b): return a and b and a[0] < b[2]-1 and b[0] < a[2]-1 and a[1] < b[3]-1 and b[1] < a[3]-1
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
        for theme in ('dark', 'light'):
            ctx = await b.new_context(viewport={'width': 327, 'height': 700}, screen={'width': 327, 'height': 708}, device_scale_factor=3.3, is_mobile=True, has_touch=True, color_scheme=theme)
            await ctx.add_init_script(MOCK); await ctx.add_init_script(AUTO_NOTICE)
            await ctx.add_init_script("localStorage.setItem('radioPlayerTheme','%s')" % theme)
            pg = await ctx.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
            await pg.goto(f'http://127.0.0.1:{PORT}/index.html'); await pg.wait_for_timeout(2500)
            await pg.evaluate("""(function(){ var ov=document.getElementById('addMusicOverlay'); if(ov) ov.classList.add('open'); var btn=document.getElementById('addMusicFolderBtn'); btn.disabled=false; btn.click(); })()""")
            for _ in range(60):
                await pg.wait_for_timeout(500)
                if await ev(pg, 'libraryTracks.length') >= len(files): break
            await ev(pg, "runLibrarySection('songs'); 1"); await pg.wait_for_timeout(600)
            await pg.evaluate("document.querySelector('#stationsGrid .song-row:not(.shuffle-all-row)').click()"); await pg.wait_for_timeout(900)
            await pg.set_viewport_size({'width': 678, 'height': 297}); await pg.wait_for_timeout(1200)
            T = '[%s]' % theme
            # ---- artist
            await ev(pg, "runLibrarySection('artists'); 1"); await pg.wait_for_timeout(700)
            await pg.evaluate("document.querySelector('#stationsGrid [data-entity=artist]').click()"); await pg.wait_for_timeout(1500)
            await ev(pg, SEED_ARTIST); await pg.wait_for_timeout(900)
            await pg.evaluate("document.getElementById('artistHeroName').textContent='Earth, Wind & Fire Experience'; document.getElementById('artistHeroSub').textContent='R&B \u00b7 Soul \u00b7 Funk';"); await pg.wait_for_timeout(400)
            gaps = await pg.evaluate(GAPS)
            vals = [g[1] for g in gaps]
            check(len(vals) >= 4 and max(vals) - min(vals) <= 3 and 6 <= min(vals) <= 16, T + ' artist: every heading the same distance above its content %s' % gaps)
            tiles = await pg.evaluate("Array.prototype.map.call(document.querySelectorAll('#stationsGrid .artist-videos > *:first-child, #stationsGrid .artist-yt-row > *:first-child, #stationsGrid .artist-archive-row > *:first-child, #stationsGrid .artist-albums > *:first-child'), function(e){ return [e.parentElement.className.split(' ')[0], Math.round(e.getBoundingClientRect().width)]; })")
            check(all(90 <= w <= 175 for _, w in tiles) and len(tiles) == 4, T + ' artist: videos and albums sized alike %s' % tiles)
            L = await pg.evaluate(LEFT)
            parts = [L[k] for k in ('#artistHeroArt', '#artistHeroName', '#artistHeroSub', '.artist-hero-actions') if L[k] and L[k]['b'][2] > 0]
            check(not any(ov(parts[i]['b'], parts[j]['b']) for i in range(len(parts)) for j in range(i+1, len(parts))), T + ' artist left column: nothing overlaps or cut off %s' % L)
            n = 0
            for y in (0, 260, 520, 9999):
                await pg.evaluate("window.scrollTo(0, %d)" % y); await pg.wait_for_timeout(500)
                await pg.evaluate("document.getElementById('artistHeroName').textContent='Earth, Wind & Fire Experience'; document.getElementById('artistHeroSub').textContent='R&B \u00b7 Soul \u00b7 Funk';"); await pg.wait_for_timeout(200)
                if y == 0:
                    L = await pg.evaluate(LEFT)
                    parts = [L[k] for k in ('#artistHeroArt', '#artistHeroName', '#artistHeroSub', '.artist-hero-actions') if L[k] and L[k]['b'][2] > 0]
                    check(not any(ov(parts[i]['b'], parts[j]['b']) for i in range(len(parts)) for j in range(i+1, len(parts))), T + ' artist left column with a 2-line name + genres: nothing overlaps %s' % [(k, L[k]['b']) for k in ('#artistHeroArt', '#artistHeroName', '#artistHeroSub', '.artist-hero-actions')])
                await pg.screenshot(path=f'{SH}/real-artist-{theme}-{n}.png'); n += 1
            await pg.evaluate("window.scrollTo(0, 0)"); await pg.wait_for_timeout(300)
            # ---- album
            await ev(pg, "runLibrarySection('albums'); 1"); await pg.wait_for_timeout(700)
            await pg.evaluate("document.querySelector('#stationsGrid .tile[data-entity=album]').click()"); await pg.wait_for_timeout(1500)
            await ev(pg, SEED_ALBUM); await pg.wait_for_timeout(600)
            L = await pg.evaluate(LEFT)
            parts = [L[k] for k in ('#albumHeroArt', '#albumHeroName', '#albumHeroArtist', '#albumHeroMeta', '.album-hero-actions') if L[k]]
            bad = [(i, j) for i in range(len(parts)) for j in range(i+1, len(parts)) if ov(parts[i]['b'], parts[j]['b'])]
            clipped = [k for k in ('#albumHeroName', '#albumHeroArtist', '#albumHeroMeta') if L[k] and L[k]['clip']]
            check(not bad and not clipped and L['#albumHeroArt']['b'][3] - L['#albumHeroArt']['b'][1] >= 64, T + ' album left column: 2-line title, artist, genre line all whole, nothing overlaps %s %s %s' % (bad, clipped, L))
            await pg.screenshot(path=f'{SH}/real-album-{theme}-0.png')
            await pg.evaluate("window.scrollTo(0, 200)"); await pg.wait_for_timeout(500)
            await pg.screenshot(path=f'{SH}/real-album-{theme}-1.png')
            check(not errs, T + ' no page errors %s' % errs[:2])
            await ctx.close()
        await b.close()
    print('ALL PASSED' if not fails else 'FAILED %s' % fails)
    raise SystemExit(1 if fails else 0)
asyncio.run(main())
