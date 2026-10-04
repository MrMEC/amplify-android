"""Plex (build 130): Settings > Plex sign-in (PIN flow, mocked plex.tv), the server found at its
remote address when the local one doesn't answer, its movies and shows added to Video next to a
local folder (duplicates shown once, shows merged), Plex posters and summaries (no Wikipedia
lookups), Plex watch state in Continue Watching, playing straight from the server with its
subtitle file, progress and watched sent back, the library kept after a restart, Sign Out.
Run: python3 tests/test_plex.py (screenshots in /tmp/claude-0/t/shots)"""
import asyncio, os, json, time, zlib, struct, hashlib
from urllib.parse import urlparse, parse_qs
HERE = os.path.dirname(os.path.abspath(__file__))
src = open(os.path.join(HERE, 'test_video_library.py')).read()
head = src[:src.index('async def names(pg, sel)')]
head = head.replace("'/tmp/claude-0/t/srv-vlib'", "'/tmp/claude-0/t/srv-plex'").replace('8780', '8803')
exec(head)
from playwright.async_api import async_playwright

LOCAL = 'https://10-0-0-5.abc.plex.direct:32400'
REMOTE = 'https://99-1-2-3.abc.plex.direct:32400'
RELAY = 'https://relay-1.abc.plex.direct:8443'
NOW = int(time.time())
RES = [
  {'name': 'Home Server', 'clientIdentifier': 'srvabcdef123', 'provides': 'server', 'owned': True, 'accessToken': 'SRVTOKEN',
   'connections': [{'uri': RELAY, 'local': False, 'relay': True}, {'uri': LOCAL, 'local': True, 'relay': False}, {'uri': REMOTE, 'local': False, 'relay': False}]},
  {'name': 'Friend Server', 'clientIdentifier': 'friend999', 'provides': 'server', 'owned': False, 'accessToken': 'FT',
   'connections': [{'uri': 'https://friend.plex.direct:32400', 'local': False, 'relay': False}]},
  {'name': 'Mark Phone', 'clientIdentifier': 'phone1', 'provides': 'player', 'connections': []},
]
def part(k, w=1920, h=1080):
    return [{'width': w, 'height': h, 'Part': [{'key': '/library/parts/%s/1/file.mkv' % k, 'file': '/media/%s.mkv' % k}]}]
MOVIES = [
  {'ratingKey': '500', 'title': 'Inception', 'year': 2010, 'thumb': '/library/metadata/500/thumb/1', 'duration': 8880000, 'addedAt': NOW - 900000, 'Media': part(500)},
  {'ratingKey': '501', 'title': 'Dune', 'year': 2021, 'summary': 'Paul Atreides leads nomadic tribes in a battle to control the desert planet Arrakis.',
   'thumb': '/library/metadata/501/thumb/1', 'art': '/library/metadata/501/art/1', 'duration': 9300000, 'addedAt': NOW - 100, 'Media': part(501, 3840, 2160)},
  {'ratingKey': '502', 'title': 'Heat', 'year': 1995, 'thumb': '/library/metadata/502/thumb/1', 'duration': 10200000, 'addedAt': NOW - 5000,
   'viewCount': 1, 'lastViewedAt': NOW - 86400, 'Media': part(502)},
]
HOME = [{'ratingKey': '900', 'title': 'Birthday Party', 'year': 2019, 'duration': 600000, 'addedAt': NOW - 2000, 'Media': part(900)}]
SHOWS = [{'ratingKey': '10', 'title': 'Breaking Bad', 'thumb': '/library/metadata/10/thumb/1'},
         {'ratingKey': '20', 'title': 'Severance', 'year': 2022, 'summary': 'Mark leads a team of office workers whose memories have been surgically divided.',
          'thumb': '/library/metadata/20/thumb/1', 'art': '/library/metadata/20/art/1'}]
EPS = [
  {'ratingKey': '11', 'grandparentRatingKey': '10', 'grandparentTitle': 'Breaking Bad', 'parentIndex': 1, 'index': 1, 'title': 'Pilot (Plex)', 'duration': 2820000, 'addedAt': NOW - 99999, 'Media': part(11)},
  {'ratingKey': '12', 'grandparentRatingKey': '10', 'grandparentTitle': 'Breaking Bad', 'parentIndex': 3, 'index': 1, 'title': 'No Más', 'thumb': '/library/metadata/12/thumb/1', 'duration': 2820000, 'addedAt': NOW - 99999, 'Media': part(12)},
  {'ratingKey': '21', 'grandparentRatingKey': '20', 'grandparentTitle': 'Severance', 'parentIndex': 1, 'index': 1, 'title': 'Good News About Hell', 'thumb': '/library/metadata/21/thumb/1',
   'duration': 3420000, 'addedAt': NOW - 50000, 'viewOffset': 600000, 'lastViewedAt': NOW - 3600, 'Media': part(21)},
  {'ratingKey': '22', 'grandparentRatingKey': '20', 'grandparentTitle': 'Severance', 'parentIndex': 1, 'index': 2, 'title': 'Half Loop', 'thumb': '/library/metadata/22/thumb/1',
   'duration': 3420000, 'addedAt': NOW - 50000, 'Media': part(22)},
]
META501 = {'MediaContainer': {'Metadata': [{'ratingKey': '501', 'Media': [{'Part': [{'key': '/library/parts/501/1/file.mkv', 'Stream': [
  {'streamType': 1, 'codec': 'hevc'}, {'streamType': 2, 'codec': 'eac3'},
  {'streamType': 3, 'key': '/library/streams/9001', 'codec': 'srt', 'languageTag': 'en', 'displayTitle': 'English (SRT External)'},
  {'streamType': 3, 'codec': 'pgs', 'languageTag': 'fr', 'displayTitle': 'French (PGS)'}]}]}]}]}}

def png(seed):
    h = hashlib.md5(seed.encode()).digest()
    w, hh = 40, 60
    row = b'\x00' + bytes([h[0], h[1], h[2]]) * w
    raw = row * hh
    def chunk(t, d): return struct.pack('>I', len(d)) + t + d + struct.pack('>I', zlib.crc32(t + d) & 0xffffffff)
    return b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', w, hh, 8, 2, 0, 0, 0)) + chunk(b'IDAT', zlib.compress(raw)) + chunk(b'IEND', b'')

REQ = []
PIN_POLLS = [0]
CORS = {'Access-Control-Allow-Origin': '*', 'Access-Control-Allow-Headers': '*', 'Access-Control-Allow-Methods': 'GET,POST,DELETE,PUT,OPTIONS'}
async def jr(r, obj, status=200):
    return await r.fulfill(status=status, content_type='application/json', headers=CORS, body=json.dumps(obj))
async def proute(r):
    u = r.request.url; m = r.request.method
    if m == 'OPTIONS' and ('plex.tv' in u or 'plex.direct' in u):
        return await r.fulfill(status=204, headers=CORS, body='')
    if 'wikipedia.org' in u or 'wikidata.org' in u:
        REQ.append(('WIKI', u))
        return await jr(r, {'query': {'pages': {}}})
    if u.startswith('https://plex.tv/'):
        REQ.append((m, u, r.request.headers.get('x-plex-token', ''), r.request.headers.get('x-plex-client-identifier', '')))
        p = urlparse(u).path
        if p == '/api/v2/pins' and m == 'POST': return await jr(r, {'id': 77, 'code': 'X7K2'}, 201)
        if p == '/api/v2/pins/77':
            PIN_POLLS[0] += 1
            return await jr(r, {'id': 77, 'code': 'X7K2', 'authToken': 'TOKEN1' if PIN_POLLS[0] >= 2 else None})
        if p == '/api/v2/user': return await jr(r, {'username': 'mark', 'title': 'Mark'})
        if p == '/api/v2/resources': return await jr(r, RES)
        if p.startswith('/api/v2/devices/'): return await jr(r, {})
        return await r.fulfill(status=404, headers=CORS, body='')
    if LOCAL in u or 'friend.plex.direct' in u or RELAY in u:
        REQ.append((m, u, 'blocked'))
        return await r.abort()
    if u.startswith(REMOTE):
        pu = urlparse(u); p = pu.path; q = parse_qs(pu.query)
        tok = r.request.headers.get('x-plex-token', '') or (q.get('X-Plex-Token') or [''])[0]
        REQ.append((m, u, tok))
        if tok != 'SRVTOKEN': return await r.fulfill(status=401, headers=CORS, body='')
        if p == '/identity': return await jr(r, {'MediaContainer': {'machineIdentifier': 'srvabcdef123'}})
        if p == '/library/sections': return await jr(r, {'MediaContainer': {'Directory': [{'key': '1', 'type': 'movie', 'title': 'Movies'},
                                                       {'key': '2', 'type': 'show', 'title': 'TV Shows'}, {'key': '3', 'type': 'artist', 'title': 'Music'},
                                                       {'key': '4', 'type': 'movie', 'title': 'Home Movies'}]}})
        if p == '/library/sections/1/all': return await jr(r, {'MediaContainer': {'totalSize': len(MOVIES), 'Metadata': MOVIES}})
        if p == '/library/sections/4/all': return await jr(r, {'MediaContainer': {'totalSize': 1, 'Metadata': HOME}})
        if p == '/library/sections/2/all':
            t = q.get('type', [''])[0]
            lst = SHOWS if t == '2' else EPS
            return await jr(r, {'MediaContainer': {'totalSize': len(lst), 'Metadata': lst}})
        if p == '/library/metadata/501': return await jr(r, META501)
        if p.startswith('/library/metadata/'): return await jr(r, {'MediaContainer': {'Metadata': [{}]}})
        if p.startswith('/photo/'): return await r.fulfill(status=200, content_type='image/png', headers=CORS, body=png(q.get('url', [''])[0]))
        if p.startswith('/:/'): return await r.fulfill(status=200, headers=CORS, body='')
        return await r.fulfill(status=404, headers=CORS, body='')
    return await route(r)

async def names(pg, sel):
    return await pg.evaluate("(s)=>Array.prototype.map.call(document.querySelectorAll(s),function(t){return t.textContent;})", sel)
async def tab(pg, v):
    await pg.evaluate("(v)=>document.querySelector('.video-tabs [data-vtab='+v+']').click()", v); await pg.wait_for_timeout(400)
async def state(pg, extra):
    cur = await pg.evaluate("window.__cur")
    ev = {'id': cur, 'state': 'ready', 'isPlaying': True, 'playWhenReady': True, 'position': 0, 'duration': 8880, 'live': False}
    ev.update(extra)
    await pg.evaluate("(e)=>window.__emit('state', e)", ev)
OPEN = "window.__opened=[]; window.open=function(u){ window.__opened.push(u); return null; };"
def plexreqs(sub):
    return [x for x in REQ if x[0] != 'WIKI' and sub in x[1]]
async def settings(pg):
    await pg.evaluate("openSettings ? document.getElementById('settingsFab').click() : 0"); await pg.wait_for_timeout(300)
async def close_settings(pg):
    await pg.evaluate("document.getElementById('settingsCloseBtn').click()"); await pg.wait_for_timeout(300)
async def plex_texts(pg):
    return await pg.evaluate("Array.prototype.map.call(document.querySelectorAll('#plexSettingsBody > *'),function(e){return e.textContent;})")

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
        ctx = await b.new_context(viewport={'width': 390, 'height': 844}, device_scale_factor=2, is_mobile=True, has_touch=True, color_scheme='dark', locale='en-US')
        await ctx.add_init_script(MOCK)
        await ctx.add_init_script(EXT)
        await ctx.add_init_script(OPEN)
        pg = await ctx.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e) + ' @ ' + (e.stack or '')[:300]))
        dialogs = []
        async def ondialog(d):
            dialogs.append(d.message); await d.accept()
        pg.on('dialog', lambda d: asyncio.ensure_future(ondialog(d)))
        await pg.route('**/*', proute)
        await pg.goto('http://127.0.0.1:8803/index.html'); await pg.wait_for_timeout(2500)

        # a local folder first (Inception, Breaking Bad S1-2 among others)
        await pg.evaluate("document.querySelector('.mobile-nav-btn[data-nav=video]').click()"); await pg.wait_for_timeout(500)
        await tab(pg, 'movies')
        await pg.evaluate("document.getElementById('videoAddHeaderBtn').click()"); await pg.wait_for_timeout(2000)

        # Settings: signed out
        await pg.evaluate("document.getElementById('settingsFab').click()"); await pg.wait_for_timeout(400)
        t = await plex_texts(pg)
        check(t == ['Add the movies and TV shows on your Plex server to Video.', 'Sign In with Plex'], f'Settings > Plex signed out {t}')
        await pg.evaluate("document.getElementById('plexSettingsRow').scrollIntoView()"); await pg.wait_for_timeout(200)
        await pg.screenshot(path=f'{SHOTS}/plex-settings-out.png')
        await pg.evaluate("document.getElementById('plexSignInBtn').click()"); await pg.wait_for_timeout(600)
        opened = await pg.evaluate("window.__opened")
        t = await plex_texts(pg)
        status = await pg.evaluate("document.getElementById('plexStatus').textContent")
        check(len(opened) == 1 and opened[0].startswith('https://app.plex.tv/auth#?clientID=amplify-') and 'code=X7K2' in opened[0] and 'product%5D=Amplify' in opened[0],
              f'the Plex approval page opens with the PIN {opened}')
        check(status == 'Signing in…' and 'X7K2' in t and 'Open Plex Page' in t[-1] and 'Cancel' in t[-1], f'waiting shows the code, Open Plex Page and Cancel {status} {t}')
        await pg.evaluate("document.getElementById('plexSettingsRow').scrollIntoView()"); await pg.wait_for_timeout(200)
        await pg.screenshot(path=f'{SHOTS}/plex-settings-waiting.png')
        pins = [x for x in REQ if 'api/v2/pins' in x[1]]
        check(pins and pins[0][0] == 'POST' and pins[0][3].startswith('amplify-'), f'PIN asked for with the client id {pins[:1]}')
        await pg.wait_for_timeout(7000)   # two polls, then user, resources, connect, sync
        t = await plex_texts(pg)
        status = await pg.evaluate("document.getElementById('plexStatus').textContent")
        check(status == 'Connected' and t[0] == 'Signed in as Mark', f'signed in {status} {t}')
        sel = await pg.evaluate("Array.prototype.map.call(document.querySelectorAll('#plexServerSelect option'),function(o){return [o.textContent,o.selected];})")
        check(sel == [['Home Server', True], ['Friend Server', False]], f'servers to choose from, the owned one first and chosen {sel}')
        check(any('4 movies · 2 shows' in x for x in t), f'library counted {t}')
        libs = await pg.evaluate("Array.prototype.map.call(document.querySelectorAll('#plexLibraries .plex-lib'),function(b){return [b.querySelector('.plex-lib-name').textContent,b.querySelector('.plex-lib-sub').textContent,b.getAttribute('aria-checked')];})")
        check(libs == [['Movies', '3 movies', 'true'], ['TV Shows', '2 shows', 'true'], ['Home Movies', '1 movie', 'true']], f'every movie and show library listed with a switch, all on (music left out) {libs}')
        await pg.evaluate("document.getElementById('plexLibraries').scrollIntoView()"); await pg.wait_for_timeout(200)
        await pg.screenshot(path=f'{SHOTS}/plex-libraries-on.png')
        await pg.evaluate("document.querySelector('#plexLibraries .plex-lib[data-key=\"4\"]').click()"); await pg.wait_for_timeout(300)
        t = await plex_texts(pg)
        libs = await pg.evaluate("Array.prototype.map.call(document.querySelectorAll('#plexLibraries .plex-lib'),function(b){return b.getAttribute('aria-checked');})")
        check(libs == ['true', 'true', 'false'] and any('3 movies · 2 shows' in x for x in t), f'Home Movies switched off, count follows {libs} {t}')
        await pg.evaluate("document.getElementById('plexLibraries').scrollIntoView()"); await pg.wait_for_timeout(200)
        await pg.screenshot(path=f'{SHOTS}/plex-libraries-off.png')
        tokens = [x for x in REQ if x[1].startswith('https://plex.tv/api/v2/user') or x[1].startswith('https://plex.tv/api/v2/resources')]
        check(tokens and all(x[2] == 'TOKEN1' for x in tokens), f'plex.tv asked with the new token {tokens}')
        ident = [x[1] for x in REQ if x[1].endswith('/identity')]
        check(any(LOCAL in x for x in ident) and any(REMOTE in x for x in ident), f'local and remote tried {ident}')
        acct = await pg.evaluate("JSON.parse(localStorage.getItem('radioPlayerPlexAccount')).base")
        check(acct == REMOTE, f'the remote address chosen (local not answering, relay last) {acct}')
        await pg.evaluate("document.getElementById('plexSettingsRow').scrollIntoView()"); await pg.wait_for_timeout(200)
        await pg.screenshot(path=f'{SHOTS}/plex-settings-in.png')
        over = await pg.evaluate("(()=>{var p=document.getElementById('settingsPanel');return [p.scrollWidth,p.clientWidth];})()")
        check(over[0] <= over[1], f'nothing runs off the settings card {over}')
        await close_settings(pg)

        # Movies: local + Plex, Inception once
        await pg.evaluate("document.querySelector('.mobile-nav-btn[data-nav=home]').click()"); await pg.wait_for_timeout(300)
        await pg.evaluate("document.querySelector('.mobile-nav-btn[data-nav=video]').click()"); await pg.wait_for_timeout(500)
        await tab(pg, 'movies')
        mv = await names(pg, '#stationsGrid .tile.vposter .tile-name')
        check(sorted(mv) == ['Arrival', 'Dune', 'Heat', 'Inception', 'The Matrix'], f'Plex movies beside the local ones, Inception once, Home Movies left out {mv}')
        check(mv[0] == 'Dune', f'Recently Added puts the newest Plex movie first {mv}')
        imgs = await pg.evaluate("Array.prototype.map.call(document.querySelectorAll('#stationsGrid .tile.vposter'),function(t){var i=t.querySelector('img');return [t.querySelector('.tile-name').textContent, i?i.getAttribute('src'):''];})")
        dune = [x[1] for x in imgs if x[0] == 'Dune'][0]
        check(dune.startswith(REMOTE + '/photo/:/transcode?width=400&height=600') and 'X-Plex-Token=SRVTOKEN' in dune, f'Dune poster from the server {dune}')
        src = await names(pg, '#stationsGrid .v-folder-name')
        heading = await pg.evaluate("Array.prototype.map.call(document.querySelectorAll('#stationsGrid .v-folders-label'),function(e){return e.textContent;})")
        check(src == ['Plex · Home Server', 'Videos'] and heading == ['Sources'], f'Sources lists Plex and the folder {heading} {src}')
        watched = await pg.evaluate("Array.prototype.some.call(document.querySelectorAll('#stationsGrid .tile.vposter'),function(t){return t.querySelector('.tile-name').textContent==='Heat' && !!t.querySelector('.v-watched');})")
        check(watched, 'Heat shows watched (Plex says so)')
        await pg.wait_for_timeout(500)
        await pg.screenshot(path=f'{SHOTS}/plex-movies.png')
        # Continue Watching: Severance from Plex's progress
        cw = await pg.evaluate("Array.prototype.map.call(document.querySelectorAll('#stationsGrid .vw-tile'),function(t){return t.querySelector('.tile-name').textContent+'|'+t.querySelector('.tile-sub').textContent;})")
        check(cw and cw[0] == 'Severance|S1 E1 · Good News About Hell', f'Continue Watching carries on with Plex progress {cw}')

        # TV Shows: Breaking Bad merged, Severance added
        await tab(pg, 'shows')
        sh = await names(pg, '#stationsGrid .tile.vposter .tile-name')
        check(sorted(sh) == ['Breaking Bad', 'Friends', 'Severance', 'The Office'], f'shows merged by name {sh}')
        await pg.screenshot(path=f'{SHOTS}/plex-shows.png')
        await pg.evaluate("Array.prototype.find.call(document.querySelectorAll('#stationsGrid .tile.vposter'),function(t){return t.querySelector('.tile-name').textContent==='Breaking Bad';}).click()"); await pg.wait_for_timeout(600)
        seasons = await names(pg, '.vd-seasons .home-tab')
        eps = await names(pg, '#stationsGrid .vep-title')
        check(seasons == ['Season 1', 'Season 2', 'Season 3'] and eps == ['1. Pilot', '2. Cats in the Bag'], f'Breaking Bad: Season 3 from Plex, S1E1 shown once (the local file) {seasons} {eps}')
        await pg.evaluate("Array.prototype.find.call(document.querySelectorAll('.vd-seasons .home-tab'),function(b){return b.textContent==='Season 3';}).click()"); await pg.wait_for_timeout(300)
        eps = await names(pg, '#stationsGrid .vep-title')
        check(eps == ['1. No Más'], f'Season 3 {eps}')
        await pg.evaluate("history.back ? document.getElementById('detailBackBtn').click() : 0"); await pg.wait_for_timeout(500)
        await tab(pg, 'shows')
        await pg.evaluate("Array.prototype.find.call(document.querySelectorAll('#stationsGrid .tile.vposter'),function(t){return t.querySelector('.tile-name').textContent==='Severance';}).click()"); await pg.wait_for_timeout(600)
        info = await pg.evaluate("[document.querySelector('.vd-play').textContent, (document.querySelector('.vd-overview-text')||{}).textContent||'', document.querySelector('.vd-poster img') ? document.querySelector('.vd-poster img').getAttribute('src') : '']")
        check(info[0] == 'Resume S1 E1' and info[1].startswith('Mark leads a team') and info[2].startswith(REMOTE), f'Severance page: Resume S1 E1, Plex summary and poster {info}')
        thumbs = await pg.evaluate("Array.prototype.map.call(document.querySelectorAll('#stationsGrid .vep-thumb img'),function(i){return i.getAttribute('src');})")
        check(len(thumbs) == 2 and all('width=640' in x for x in thumbs), f'episode pictures from Plex {thumbs}')
        await pg.wait_for_timeout(400)
        await pg.screenshot(path=f'{SHOTS}/plex-show.png')
        await pg.evaluate("document.getElementById('detailBackBtn').click()"); await pg.wait_for_timeout(500)

        # Dune: details, play from the server with its subtitle file
        await tab(pg, 'movies')
        await pg.evaluate("Array.prototype.find.call(document.querySelectorAll('#stationsGrid .tile.vposter'),function(t){return t.querySelector('.tile-name').textContent==='Dune';}).click()"); await pg.wait_for_timeout(600)
        info = await pg.evaluate("[document.querySelector('.vd-meta').textContent, (document.querySelector('.vd-overview-text')||{}).textContent||'', document.querySelector('.vd-file').textContent]")
        check(info[0] == '2021 · 2h 35m · 4K' and info[1].startswith('Paul Atreides') and info[2] == 'Plex · Home Server', f'Dune page {info}')
        await pg.evaluate("document.querySelector('.vd-actions .vd-more').click()"); await pg.wait_for_timeout(200)
        items = await names(pg, '.v-menu .np-menu-item')
        check(items == ['Mark Watched', 'Rename', 'Change Poster'], f'Plex movie menu leaves out the local-file fixes {items}')
        await pg.screenshot(path=f'{SHOTS}/plex-movie.png')
        await pg.evaluate("document.body.click()"); await pg.wait_for_timeout(200)
        await pg.evaluate("document.querySelector('.vd-play').click()"); await pg.wait_for_timeout(1500)
        la = await pg.evaluate("window.__loadArgs.slice(-1)[0]")
        check(la and la['url'] == REMOTE + '/library/parts/501/1/file.mkv?X-Plex-Token=SRVTOKEN', f'played straight from the server {la and la.get("url")}')
        subs = (la or {}).get('subs') or []
        check(len(subs) == 1 and subs[0]['uri'] == REMOTE + '/library/streams/9001?X-Plex-Token=SRVTOKEN' and subs[0]['label'] == 'English (SRT External)'
              and subs[0]['language'] == 'en' and subs[0]['name'].endswith('.srt'), f'the server subtitle file comes along (the PGS one is left to the player) {subs}')
        await state(pg, {'position': 1200, 'duration': 9300}); await pg.wait_for_timeout(300)
        await state(pg, {'position': 1200, 'duration': 9300, 'isPlaying': False, 'playWhenReady': False, 'external': True}); await pg.wait_for_timeout(800)
        prog = [x[1] for x in plexreqs('/:/progress')]
        check(any('key=501' in x and 'time=1200000' in x and 'state=paused' in x for x in prog), f'progress sent back on pause {prog}')
        await pg.evaluate("document.getElementById('npBackBtn').click()"); await pg.wait_for_timeout(500)
        await pg.evaluate("document.querySelector('.vd-actions .vd-more').click()"); await pg.wait_for_timeout(200)
        await pg.evaluate("Array.prototype.find.call(document.querySelectorAll('.v-menu .np-menu-item'),function(b){return b.textContent==='Mark Watched';}).click()"); await pg.wait_for_timeout(600)
        scr = [x[1] for x in plexreqs('/:/scrobble')]
        check(any('key=501' in x for x in scr), f'Mark Watched tells Plex {scr}')
        wiki = [x[1] for x in REQ if x[0] == 'WIKI' and ('Dune' in x[1] or 'Severance' in x[1] or 'Heat' in x[1])]
        check(not wiki, f'no Wikipedia lookups for Plex titles {wiki[:3]}')

        # restart: the library is there at once
        await pg.reload(); await pg.wait_for_timeout(600)
        await pg.evaluate("document.querySelector('.mobile-nav-btn[data-nav=video]').click()"); await pg.wait_for_timeout(400)
        await tab(pg, 'movies')
        mv = await names(pg, '#stationsGrid .tile.vposter .tile-name')
        check('Dune' in mv and 'Heat' in mv and 'Birthday Party' not in mv, f'after a restart the Plex movies are there straight away, Home Movies still left out {mv}')
        await pg.wait_for_timeout(2500)
        syncs = len([x for x in REQ if x[1].startswith(REMOTE + '/library/sections/1/all')])
        check(syncs == 1, f'a fresh library isn\'t fetched again on start-up ({syncs} fetches)')

        # bigger text at 360 wide: the Plex part of Settings still fits
        await pg.set_viewport_size({'width': 360, 'height': 780})
        await pg.add_style_tag(content='#settingsPanel .settings-data-btn, #settingsPanel .settings-select{ font-size:17px !important; } #settingsPanel .plex-line, #settingsPanel .plex-note{ font-size:17.5px !important; } #settingsPanel .settings-label, #settingsPanel .plex-status{ font-size:17.5px !important; } #settingsPanel .plex-code{ font-size:27px !important; }')
        await pg.evaluate("document.getElementById('settingsFab').click()"); await pg.wait_for_timeout(400)
        await pg.evaluate("document.getElementById('plexSettingsRow').scrollIntoView()"); await pg.wait_for_timeout(200)
        over = await pg.evaluate("""(()=>{var p=document.getElementById('settingsPanel'),r=p.getBoundingClientRect(),bad=[];
          document.querySelectorAll('#plexSettingsRow *').forEach(function(e){var b=e.getBoundingClientRect(); if(b.width && (b.right>r.right+1||b.left<r.left-1)) bad.push(e.className||e.tagName);
            if((e.tagName==='BUTTON') && e.scrollWidth>e.clientWidth+1) bad.push('clip:'+e.textContent);});return bad;})()""")
        check(not over, f'large text at 360: nothing in Plex settings spills or clips {over}')
        await pg.screenshot(path=f'{SHOTS}/plex-settings-bigtext.png')

        # TV Shows off: Severance leaves, Breaking Bad keeps only the local seasons; on again brings them back
        await pg.evaluate("document.querySelector('#plexLibraries .plex-lib[data-key=\"2\"]').click()"); await pg.wait_for_timeout(300)
        await close_settings(pg)
        await tab(pg, 'movies'); await tab(pg, 'shows')
        sh = await names(pg, '#stationsGrid .tile.vposter .tile-name')
        cw = await names(pg, '#stationsGrid .vw-tile .tile-name')
        check(sorted(sh) == ['Breaking Bad', 'Friends', 'The Office'] and 'Severance' not in cw, f'TV Shows library off: its shows leave Video and Continue Watching {sh} {cw}')
        await pg.evaluate("document.getElementById('settingsFab').click()"); await pg.wait_for_timeout(300)
        await pg.evaluate("document.querySelector('#plexLibraries .plex-lib[data-key=\"2\"]').click()"); await pg.wait_for_timeout(300)
        await pg.evaluate("document.querySelector('#plexLibraries .plex-lib[data-key=\"4\"]').click()"); await pg.wait_for_timeout(300)
        await close_settings(pg)
        await tab(pg, 'movies'); await tab(pg, 'shows')
        sh = await names(pg, '#stationsGrid .tile.vposter .tile-name')
        check('Severance' in sh, f'switched back on, no sync needed {sh}')
        await tab(pg, 'movies')
        mv = await names(pg, '#stationsGrid .tile.vposter .tile-name')
        check('Birthday Party' in mv, f'Home Movies back on {mv}')
        await pg.evaluate("document.getElementById('settingsFab').click()"); await pg.wait_for_timeout(300)
        # Sign Out
        await pg.evaluate("document.getElementById('plexSignOutBtn').click()"); await pg.wait_for_timeout(600)
        t = await plex_texts(pg)
        check(t[-1] == 'Sign In with Plex' and any('Sign out of Plex' in d for d in dialogs), f'signed out after confirming {t}')
        await close_settings(pg)
        await tab(pg, 'shows'); await tab(pg, 'movies')
        mv = await names(pg, '#stationsGrid .tile.vposter .tile-name')
        check(sorted(mv) == ['Arrival', 'Inception', 'The Matrix'], f'Plex movies gone, local ones stay {mv}')
        gone = await pg.evaluate("[localStorage.getItem('radioPlayerPlexAccount'), localStorage.getItem('radioPlayerPlexLib')]")
        check(gone == [None, None], f'account and library forgotten {gone}')
        check(not errs, f'no page errors {errs[:3]}')
        await b.close()
    print('ALL PASSED' if not fails else f'FAILED {fails}')
asyncio.run(main())
