"""Build 268: an artist page always has a control left of Play (Favorite when there is no Shuffle, and then
not in the menu too); on desktop the big picture is a heavy blur, an album-size portrait sits over it,
and the content below lines up with the bio. Phones keep the full picture and no portrait.
Run: python3 tests/test_artist_desktop.py"""
import sys, os, asyncio
T=os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0,T)
from notice_auto import AUTO_NOTICE
src=open(T+'/test_station_skip.py').read(); head=src[:src.index('async def main()')]
head=head.replace("'/tmp/claude-0/t/srv_skip'","'/tmp/claude-0/t/srv_ash'").replace('PORT = 8794','PORT = 8851')
EXTRA = r"""" extra: function(){ artistStations.push({ stationuuid: 'st-z', name: 'Exclusively Zed', url: 'http://radio.example/Zed', urlToResolve: 'http://radio.example/Zed', favicon: '', tags: '' }); ['Bob','Zed'].forEach(function(n){ setCustomArtUrl(artistArtKey(artistMatchKey(n)), 'https://covers.example/art.jpg'); }); }," +
 " bio: function(){ artistHeroBio.innerHTML = '<p class=artist-hero-bio-text>Bob is an American singer and songwriter whose career spans five decades. He is known for a run of hit records in the 1980s and a long string of tours across North America and Europe, and has been widely covered by other artists. His later records mixed rock with soul and gospel, and he remains a regular on classic rock radio.</p><button type=button class=artist-hero-bio-source>More</button>'; artistHeroBio.style.display=''; }," +
 " skip: function(){"""
head=head.replace('" skip: function(){', EXTRA)
assert 'extra:' in head
exec(head)
import subprocess
subprocess.run(['ffmpeg','-loglevel','error','-y','-f','lavfi','-i','cellauto=s=120x120:rule=110,format=rgb24','-vf','scale=240:240:flags=neighbor,hue=h=200:s=3','-frames:v','1',root+'/art.jpg'],check=True)
from playwright.async_api import async_playwright
OUT='/tmp/claude-0/t/shots'
async def run(p, w, h, mobile, tag, big=False):
    b=await p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
    kw=dict(viewport={'width':w,'height':h}, device_scale_factor=2 if mobile else 1, color_scheme='dark')
    if mobile: kw.update(is_mobile=True, has_touch=True)
    ctx=await b.new_context(**kw); await ctx.add_init_script(MOCK); await ctx.add_init_script(AUTO_NOTICE)
    pg=await ctx.new_page(); errs=[]; pg.on('pageerror', lambda e: errs.append(str(e)))
    ART=open(root+'/art.jpg','rb').read()
    async def rt(r):
        u=r.request.url
        if 'covers.example' in u: await r.fulfill(status=200, body=ART, content_type='image/jpeg')
        elif '127.0.0.1' in u: await r.continue_()
        else: await r.abort()
    await pg.route('**/*', rt)
    await pg.goto(f'http://127.0.0.1:{PORT}/index.html'); await pg.wait_for_timeout(2500)
    if big: await pg.add_style_tag(content='html{ font-size:135% } .artist-hero-name{ font-size:54px !important } .album-play-pill{ font-size:21px !important }')
    await pg.evaluate("""(function(){ var ov=document.getElementById('addMusicOverlay'); if(ov) ov.classList.add('open');
      var btn=document.getElementById('addMusicFolderBtn'); btn.disabled=false; btn.click(); })()""")
    for _ in range(60):
        await pg.wait_for_timeout(500)
        if len(await pg.evaluate('__t.tracks()'))>=3: break
    await pg.evaluate('__t.setup()'); await pg.evaluate('__t.extra()')
    desk = not mobile
    for n in ['Bob','Zed']:
        await pg.evaluate(f"__t.openArtist('{n}')"); await pg.wait_for_timeout(1200)
        await pg.evaluate('__t.bio()'); await pg.wait_for_timeout(300)
        await pg.screenshot(path=f'{OUT}/a268-{tag}-{n}.png')
        r=await pg.evaluate("""(function(){ function r(el){ if(!el) return null; var b=el.getBoundingClientRect(); return [Math.round(b.left),Math.round(b.top),Math.round(b.width),Math.round(b.height), getComputedStyle(el).display]; }
          var row=document.querySelector('.artist-hero-actions'); var vis=[].filter.call(row.children,function(c){return getComputedStyle(c).display!=='none';});
          var play=document.getElementById('artistPlayBtn').getBoundingClientRect(), wrap=document.getElementById('artistHeroArtWrap').getBoundingClientRect();
          var lab=document.querySelector('#stationsGrid .grid-section-label'), tile=document.querySelector('#stationsGrid > .tile');
          var img=document.querySelector('#artistHeroArt img'), th=document.querySelector('#artistHeroThumb img');
          return { row: vis.map(function(c){return c.id||c.className;}), left: vis[0] ? r(vis[0]) : null, play: [Math.round(play.left), Math.round(play.right)],
            rowMid: Math.round((row.getBoundingClientRect().left+row.getBoundingClientRect().right)/2),
            thumb: r(document.getElementById('artistHeroThumb')), thumbImg: !!th, bio: r(document.querySelector('.artist-hero-bio-text')), label: r(lab), tile: r(tile),
            menuFav: getComputedStyle(document.getElementById('artistFavBtn')).display, blur: img ? getComputedStyle(img).filter : '',
            actionsBottom: Math.round(row.getBoundingClientRect().bottom), wrapBottom: Math.round(wrap.bottom), wrapTop: Math.round(wrap.top),
            nameTop: Math.round(document.getElementById('artistHeroName').getBoundingClientRect().top),
            album: r(document.querySelector('.album-hero-art-wrap')) }; })()""")
        check(r['row'][1] == 'artistPlayBtn' and len(r['row']) == 3, f'{tag} {n}: an icon left of Play, menu right {r["row"]}')
        check(abs((r['play'][0]+r['play'][1])/2 - r['rowMid']) <= 2, f'{tag} {n}: Play centred in its row {r["play"]} {r["rowMid"]}')
        if n == 'Bob':
            check(r['row'][0] == 'artistShuffleBtn' and r['menuFav'] != 'none', f'{tag} Bob (songs): Shuffle left of Play, Favorite in the menu')
        else:
            check(r['row'][0] == 'artistHeroFavBtn' and r['menuFav'] == 'none', f'{tag} Zed (no songs): Favorite left of Play, not also in the menu')
        if desk:
            check('blur(38px)' in r['blur'], f'{tag} {n}: background picture heavily blurred {r["blur"]}')
            sz = min(300, w*.68, h*.40)
            check(r['thumb'][4] == 'flex' and r['thumbImg'] and abs(r['thumb'][2]-sz) <= 1 and r['thumb'][2] == r['thumb'][3], f'{tag} {n}: album-size portrait {r["thumb"]} want {sz}')
            check(r['thumb'][1] >= r['wrapTop'] + 50 and r['actionsBottom'] <= r['wrapBottom'], f'{tag} {n}: portrait, name and controls inside the hero {r["thumb"]} {r["actionsBottom"]} {r["wrapBottom"]}')
            check(r['label'][0] == r['bio'][0] and r['tile'][0] == r['bio'][0], f'{tag} {n}: stations line up with the bio {r["label"]} {r["tile"]} {r["bio"]}')
        else:
            check(r['thumb'][4] == 'none' and 'blur' not in r['blur'], f'{tag} {n}: phone: no portrait, picture not blurred {r["thumb"]} {r["blur"]}')
            check(r['label'][0] == r['bio'][0], f'{tag} {n}: phone layout as before {r["label"]} {r["bio"]}')
        if n == 'Zed':
            await pg.click('#artistHeroFavBtn'); await pg.wait_for_timeout(300)
            on = await pg.evaluate("[document.getElementById('artistHeroFavBtn').classList.contains('on'), document.getElementById('artistHeroFavBtn').getAttribute('aria-pressed'), document.getElementById('artistFavBtn').textContent.trim()==='Favorited']")
            check(on[0] and on[1] == 'true' and on[2], f'{tag}: the row heart favourites the artist {on}')
            await pg.screenshot(path=f'{OUT}/a268-{tag}-Zed-fav.png')
            await pg.click('#artistHeroFavBtn'); await pg.wait_for_timeout(300)
            off = await pg.evaluate("document.getElementById('artistHeroFavBtn').classList.contains('on')")
            check(not off, f'{tag}: and again un-favourites')
    check(not errs, f'{tag}: no page errors {errs[:3]}')
    await b.close()
async def main():
    async with async_playwright() as p:
        await run(p,1440,900,False,'desk')
        await run(p,1024,640,False,'desk-short')
        await run(p,412,915,True,'phone')
        await run(p,360,780,True,'phone-big', big=True)
    print('ALL PASSED' if not fails else f'FAILED {fails}')
asyncio.run(main())
