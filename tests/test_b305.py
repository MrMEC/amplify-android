"""Build 305 (Mark): Add Channels tabs to the edge; music video channels; New Channel as a page; Music Videos page buttons. Built on test_b304 / Build 304 (Mark): grey rings on artist circles; three artists across on the Artists page; Back on artist pages goes to the page you came from; no favourite star on the Music Videos artists. Built on test_b301 / Build 301 (Mark): Watch > Music Videos: every music video on the phone by artist (artists with
videos but no songs included), Other Videos for the rest; an artist's page plays their videos.
Build 302: no Artist button, the name links to the artist page, the artist page heading links back, Recently Added shows the artist. Run: python3 tests/test_b301.py (screenshots in /tmp/claude-0/t/shots)"""
import os, sys, json
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
__file__ = os.path.join(HERE, 'test_daily_mixes.py')
src = open(os.path.join(HERE, 'test_daily_mixes.py')).read()
src = src[:src.index('async def run(theme):')]
src = src.replace('PORT = 8803', 'PORT = 8898').replace("srv_daily'", "srv_b305'")
src = src.replace('" stopPlay:', '''" mv301: { seed: function(files){ musicVideos.files = files.map(function(f, i){ return { uri: 'content://v/' + i, name: f[0].split('/').pop(), relPath: f[0], size: 1000 + i, lastModified: f[1], tree: 't' }; });"
  "     musicVideos.files.forEach(function(f, i){ videoInfo[f.uri] = { d: 200 + i * 10, w: 640, h: 360, t: '' }; }); saveMusicVideos(); mvCatalogCache = null; },"
  "   where: function(){ return { heading: stationsHeading.textContent, artist: activeArtistKey, sect: activeLibrarySection, home: document.body.classList.contains('home-view'), video: onVideoView, vdetail: onVideoDetailView, mv: (document.querySelector('.mv-hero-name') || {}).textContent || '', hist: viewHistory.map(function(v){ return v.label; }) }; },"
  "   back: function(){ var b = document.getElementById('detailBackBtn'); var vis = b && getComputedStyle(b).display !== 'none'; if(vis){ b.click(); return 'detailBack'; } return 'none'; },"
  "   key: function(n){ return artistMatchKey(n); },"
  "   np: function(){ var t = libraryTracks.filter(function(x){ return x.artist === 'Prince'; })[0]; audio.play = function(){ return Promise.resolve(); }; playEntity(t); setTimeout(function(){ openNowPlaying(currentStation); }, 500); },"
  "   edit: function(id){ openLiveChEditor(id); },"
  "   defs: function(){ return JSON.parse(JSON.stringify(liveChDefs())); },"
  "   addCh: function(){ videoTab = 'channels'; addChannelsTab = 'mine'; pushView(); openAddChannelsPage(); },"
  "   liveTv: function(){ videoTab = 'channels'; pushView(); openVideoHome(); },"
  "   tune: function(id){ var ok = tuneLiveChannel('amplify-live:' + id, {}); return { ok: ok, cur: currentStation && { kind: currentStation.videoKind, liveTitle: currentStation.liveTitle, artist: currentStation.liveArtist, text: liveTrackText(currentStation), name: currentStation.name } }; },"
  "   guide: function(id){ var c = liveChannelByUrl('amplify-live:' + id); return c ? liveChItems(c).slice(0, 3).map(function(p){ return p.t + '|' + p.sub; }) : null; },"
  "   isFavArtist: function(n){ var e = findArtistEntry(artistMatchKey(n)); return e ? isFavorite(artistFavRecord(e)) : null; },"
  "   queue: function(){ return upNext.map(function(t){ return t.name; }); },"
  "   watch: function(){ videoTab = 'music'; pushView(); openVideoHome(); },"
  "   q: function(){ return { n: playQueue.length, cur: currentStation && currentStation.name, kind: currentStation && currentStation.videoKind, label: queueLabel }; } },"
  " stopPlay:''')
exec(src)
FILES = [
  ('Music/Prince/Prince - Prince 01 (Official Video).mp4', 5000),
  ('Music/Prince/Prince - Purple Rain.mp4', 9000),
  ('Music/Madonna/Madonna - Vogue.mp4', 3000),
  ('Music/Videos/Janet Jackson - Rhythm Nation.mp4', 8000),
  ('Music/Videos/Janet Jackson feat. Q-Tip - Got Til Its Gone.mp4', 7000),
  ('Music/Sade/Smooth Operator.mp4', 6000),
  ('Music/Videos/random clip.mp4', 4000),
  ('Music/Videos/01 - Something.mp4', 1000),
]
TILES = "[...document.querySelectorAll('#stationsGrid .tile.mv-artist')].map(t => t.querySelector('.tile-name').textContent + '|' + (t.querySelector('.tile-sub') || {}).textContent)"


async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
        ctx = await b.new_context(viewport={'width': 390, 'height': 844}, device_scale_factor=3, is_mobile=True, has_touch=True, color_scheme='dark')
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
        await pg.evaluate("(f) => __d.mv301.seed(f)", [list(x) for x in FILES])
        # 1) Add Channels: tabs to the edge
        await pg.evaluate("__d.mv301.liveTv()"); await pg.wait_for_timeout(600)
        await pg.evaluate("__d.mv301.addCh()"); await pg.wait_for_timeout(1000)
        tr = await pg.evaluate("(()=>{ const t = document.querySelector('.ch-tools .home-tabs'); const r = t.getBoundingClientRect(); return [r.left, r.right, innerWidth]; })()")
        check(tr[0] <= 0.5 and abs(tr[1] - tr[2]) <= 0.5, f'Add Channels tabs run edge to edge {tr}')
        # 2) music video rows on My Shows & Movies
        rows = await pg.evaluate("(()=>{ const hs = [...document.querySelectorAll('.ch-mine-head')].map(h => h.textContent); const names = [...document.querySelectorAll('.ch-list .ch-row .ch-name')].map(n => n.textContent); return { hs, names }; })()")
        print('mine', rows)
        check('Music Videos' in rows['hs'] and 'All Music Videos' in rows['names'] and 'Prince' in rows['names'] and 'Janet Jackson' in rows['names'],
              f'a Music Videos section: all of them, or one artist {rows}')
        await pg.evaluate("[...document.querySelectorAll('.ch-list .ch-row')].find(r => r.querySelector('.ch-name').textContent === 'All Music Videos').click()"); await pg.wait_for_timeout(500)
        defs = await pg.evaluate("__d.mv301.defs()")
        mvdef = [d for d in defs if d['src']['kind'] == 'mv']
        check(len(mvdef) == 1 and mvdef[0]['src'].get('all') and mvdef[0]['order'] == 'shuffle', f'one tap makes an All Music Videos channel (shuffled) {mvdef}')
        await pg.screenshot(path=f'{shots}/b305-addch.png')
        g = await pg.evaluate(f"__d.mv301.guide('{mvdef[0]['id']}')")
        print('guide', g)
        OK_PAIRS = {'Prince 01|Prince', 'Purple Rain|Prince', 'Vogue|Madonna', 'Rhythm Nation|Janet Jackson', 'Got Til Its Gone|Janet Jackson', 'Smooth Operator|Sade', 'random clip|', 'Something|'}
        check(g and all(x in OK_PAIRS for x in g), f'the guide shows each video with its artist (none for Other Videos) {g}')
        tu = await pg.evaluate(f"__d.mv301.tune('{mvdef[0]['id']}')")
        print('tune', tu)
        c = tu['cur']
        check(tu['ok'] and c['kind'] == 'music' and c['text'] == ' · '.join(x for x in [c['liveTitle'], c['artist']] if x), f'tuning in plays a music video, title · artist {tu}')
        await pg.evaluate("document.getElementById('npBackBtn').click()"); await pg.wait_for_timeout(600)
        # 3) the editor is a page
        await pg.evaluate("__d.mv301.addCh()"); await pg.wait_for_timeout(800)
        await pg.evaluate("document.getElementById('chCustomBtn').click()"); await pg.wait_for_timeout(800)
        pgst = await pg.evaluate("""(()=>{ const p = document.getElementById('liveChPanel'); const r = id => document.getElementById(id).getBoundingClientRect();
          const tops = sel => new Set([...document.querySelectorAll(sel + ' .home-tab')].map(b => Math.round(b.getBoundingClientRect().top))).size;
          return { inPage: p.parentNode.id, overlayOpen: document.getElementById('liveChOverlay').classList.contains('open'), heading: document.getElementById('stationsHeading').textContent,
            back: getComputedStyle(document.getElementById('detailBackBtn')).display !== 'none',
            artTop: r('liveChArtBtn').top, artRight: r('liveChArtBtn').right, nameLeft: r('liveChName').left, nameBottom: r('liveChName').bottom, artBottom: r('liveChArtBtn').bottom,
            kindRows: tops('#liveChKind'), orderRows: tops('#liveChOrder'), kinds: [...document.querySelectorAll('#liveChKind .home-tab')].map(b => b.textContent),
            text: p.innerText }; })()""")
        print('page', {k: v for k, v in pgst.items() if k != 'text'})
        check(pgst['inPage'] == 'stationsGrid' and not pgst['overlayOpen'] and pgst['heading'] == 'New Channel' and pgst['back'], f'New Channel is a page with a back arrow, not a dialog {pgst["inPage"]}')
        check(pgst['nameLeft'] > pgst['artRight'] and abs(pgst['nameBottom'] - pgst['artBottom']) < 30, 'name beside the picture')
        check(pgst['kindRows'] == 1 and pgst['orderRows'] == 1, f'Plays and Order are one row each {pgst["kindRows"]}, {pgst["orderRows"]}')
        check('Music Videos' in pgst['kinds'], f'Music Videos is one of the choices {pgst["kinds"]}')
        kr = await pg.evaluate("(()=>{ const r = document.getElementById('liveChKind').getBoundingClientRect(); return [r.left, r.right]; })()")
        check(kr[0] <= 0.5 and kr[1] >= 389.5, f'the Plays row runs to the screen edges {kr}')
        check(await pg.evaluate("document.querySelector('.mobile-nav-btn[data-nav=video]').classList.contains('active')"), 'Watch stays lit in the tab bar')
        check('Pick the shows and movies' not in pgst['text'], 'no "Pick the shows and movies it plays"')
        await pg.screenshot(path=f'{shots}/b305-editor.png')
        await pg.evaluate("document.querySelector('#liveChKind .home-tab[data-opt=mv]').click()"); await pg.wait_for_timeout(300)
        await pg.evaluate("document.querySelector('#liveChMvWho .home-tab[data-opt=pick]').click()"); await pg.wait_for_timeout(400)
        arts = await pg.evaluate("[...document.querySelectorAll('#liveChMvList .artist-info-name')].map(e => e.textContent)")
        check(arts == ['Janet Jackson', 'Madonna', 'Prince', 'Sade'], f'the artists to pick {arts}')
        check(await pg.evaluate("document.getElementById('liveChSaveBtn').disabled"), 'nothing picked: Save waits')
        await pg.evaluate("[...document.querySelectorAll('#liveChMvList .artist-info-row')].find(r => r.textContent.indexOf('Prince') !== -1).click()"); await pg.wait_for_timeout(300)
        summ = await pg.evaluate("({ s: document.getElementById('liveChSummary').textContent, ph: document.getElementById('liveChName').placeholder, dis: document.getElementById('liveChSaveBtn').disabled })")
        print('summary', summ)
        check('2 music videos' in summ['s'] and summ['ph'] == 'Prince Videos' and not summ['dis'], f'Prince picked: 2 music videos, named "Prince Videos" {summ}')
        await pg.screenshot(path=f'{shots}/b305-editor-mv.png')
        await pg.evaluate("document.getElementById('liveChSaveBtn').click()"); await pg.wait_for_timeout(900)
        w = await pg.evaluate("({ heading: document.getElementById('stationsHeading').textContent, panelHome: document.getElementById('liveChPanel').parentNode.id })")
        defs = await pg.evaluate("__d.mv301.defs()")
        pdef = [d for d in defs if d['src']['kind'] == 'mv' and not d['src'].get('all')]
        check(len(pdef) == 1 and pdef[0]['src']['artists'] == ['prince'], f"saved: a channel of Prince's videos {pdef}")
        check(w['panelHome'] == 'liveChOverlay' and w['heading'] != 'New Channel', f'Save goes back to the page it came from {w}')
        # Edit it, then Back without saving
        await pg.evaluate("__d.mv301.liveTv()"); await pg.wait_for_timeout(600)
        await pg.evaluate("(id) => __d.mv301.edit(id)", pdef[0]['id']); await pg.wait_for_timeout(700)
        e1 = await pg.evaluate("({ h: document.getElementById('stationsHeading').textContent, kind: (document.querySelector('#liveChKind .home-tab.active') || {}).textContent, sel: [...document.querySelectorAll('#liveChMvList .artist-info-row[aria-selected=true] .artist-info-name')].map(e => e.textContent) })")
        check(e1['h'] == 'Edit Channel' and e1['kind'] == 'Music Videos' and e1['sel'] == ['Prince'], f'Edit Channel opens with what it plays {e1}')
        await pg.evaluate("[...document.querySelectorAll('#liveChMvList .artist-info-row')].find(r => r.textContent.indexOf('Madonna') !== -1).click()")
        await pg.evaluate("document.getElementById('detailBackBtn').click()"); await pg.wait_for_timeout(700)
        w = await pg.evaluate("({ video: __d.mv301.where().video, panelHome: document.getElementById('liveChPanel').parentNode.id })")
        defs = await pg.evaluate("__d.mv301.defs()")
        pdef2 = [d for d in defs if d['id'] == pdef[0]['id']][0]
        check(w['video'] and w['panelHome'] == 'liveChOverlay' and pdef2['src']['artists'] == ['prince'], f'Back leaves without saving, to Live TV {w} {pdef2["src"]}')
        # 4) Music Videos page buttons
        await pg.evaluate("__amplifyOpenMusicVideoArtist(__d.mv301.key('Prince'))"); await pg.wait_for_timeout(700)
        bt = await pg.evaluate("""(()=>{ const bs = [...document.querySelectorAll('.mv-page-acts > button')]; const p = document.querySelector('.mv-page-acts .mv-play');
          const probe = document.createElement('span'); probe.style.color = getComputedStyle(document.documentElement).getPropertyValue('--accent'); document.body.appendChild(probe); const acc = getComputedStyle(probe).color; probe.remove();
          return { order: bs.map(b => b.className.split(' ').filter(c => c.indexOf('mv-') === 0)[0]), label: p.textContent.trim(), bg: getComputedStyle(p).backgroundColor, acc }; })()""")
        print('buttons', bt)
        check(bt['order'] == ['mv-shuffle', 'mv-play', 'mv-more'] and bt['label'] == 'Play', f'Shuffle, Play, More, like the artist page {bt}')
        check(bt['bg'] == bt['acc'], f'Play in the theme colour {bt}')
        await pg.screenshot(path=f'{shots}/b305-mvpage.png')
        await pg.evaluate("document.querySelector('.mv-page-acts .mv-more').click()"); await pg.wait_for_timeout(300)
        mi = await pg.evaluate("[...document.querySelectorAll('.mv-menu .np-menu-item')].map(b => b.textContent.trim())")
        check(mi == ['Favorite', 'Play Next', 'Add to Queue'], f'More: Favorite, Play Next, Add to Queue {mi}')
        await pg.screenshot(path=f'{shots}/b305-mvmenu.png')
        await pg.evaluate("document.getElementById('mvMenuFav').click()"); await pg.wait_for_timeout(300)
        check(await pg.evaluate("__d.mv301.isFavArtist('Prince')") is True, 'Favorite adds the artist to Favorites')
        await pg.evaluate("document.querySelector('.mv-page-acts .mv-more').click()"); await pg.wait_for_timeout(300)
        check(await pg.evaluate("document.getElementById('mvMenuFav').textContent.trim()") == 'Favorited', 'and the menu then says Favorited')
        await pg.evaluate("document.getElementById('mvMenuQueue').click()"); await pg.wait_for_timeout(300)
        check(await pg.evaluate("__d.mv301.queue()") == ['Prince 01', 'Purple Rain'], "Add to Queue queues the artist's videos")
        await pg.evaluate("__amplifyOpenMusicVideoArtist(__d.mv301.key('Janet Jackson'))"); await pg.wait_for_timeout(500)
        await pg.evaluate("document.querySelector('.mv-page-acts .mv-more').click()"); await pg.wait_for_timeout(300)
        mi2 = await pg.evaluate("[...document.querySelectorAll('.mv-menu .np-menu-item')].map(b => b.textContent.trim())")
        check(mi2 == ['Play Next', 'Add to Queue'], f'a videos-only artist (no artist page): no Favorite {mi2}')
        check(not errs, f'no page errors {errs[:2]}')
        await b.close()
    print('ALL PASSED' if not fails else f'FAILED {len(fails)}')
asyncio.run(main())
