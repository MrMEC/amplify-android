"""Build 448 (Mark: "Exclusively Radio stations don't appear under Genres"): a genre page has an Artist radio
row after Top stations: the Exclusively channels of artists whose library songs carry the genre first, then
the channels the directory tags with it; none already among the genre's stations; none when Settings >
Library > Artist radio in Library is Hide. Phone, dark and light.
Run: python3 tests/test_genre_artist_radio.py (screenshots in /tmp/claude-0/t/shots)"""
import os, sys, json, asyncio
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
src = open(os.path.join(HERE, 'test_genre_page.py')).read().split('async def run(')[0]
src = src.replace("os.path.dirname(os.path.abspath(__file__))", repr(HERE)).replace('PORT = 8888', 'PORT = 8897').replace("srv_genrepage", "srv_genreradio")
exec(src)

EXCL = [  # the directory's "exclusively" search, most listened first
    {'name': 'EXCLUSIVELY Zed', 'url_resolved': 'http://x/zed', 'stationuuid': 'x-zed', 'favicon': '', 'tags': 'rock,classic rock', 'codec': 'MP3'},
    {'name': 'Exclusively Pop Star', 'url_resolved': 'http://x/pop', 'stationuuid': 'x-pop', 'favicon': '', 'tags': 'pop', 'codec': 'MP3'},
    {'name': 'Exclusively Rock Legend', 'url_resolved': 'http://s/rock0', 'stationuuid': 'x-dup', 'favicon': '', 'tags': 'rock', 'codec': 'MP3'},  # also Rock's top station
    {'name': 'Exclusively Ann', 'url_resolved': 'http://x/ann', 'stationuuid': 'x-ann', 'favicon': '', 'tags': '', 'codec': 'MP3'},
    {'name': 'Exclusively Cal', 'url_resolved': 'http://x/cal', 'stationuuid': 'x-cal', 'favicon': '', 'tags': '', 'codec': 'MP3'},
]
async def route2(r):
    u = r.request.url
    q = parse_qs(urlparse(u).query)
    if '/json/stations/search' in u and q.get('name', [''])[0] == 'exclusively':
        return await r.fulfill(status=200, content_type='application/json', body=json.dumps(EXCL))
    return await route(r)

PROBE = """(()=>{ var g = document.getElementById('stationsGrid');
  var heads = Array.from(g.querySelectorAll('.gp-head')).map(function(h){ return h.textContent; });
  var row = g.querySelector('.gp-artist-radio');
  return { heads: heads, radio: row ? Array.from(row.querySelectorAll('.tile-name')).map(function(e){ return e.textContent; }) : null,
    meta: (g.querySelector('.gp-meta') || {}).textContent, sw: document.documentElement.scrollWidth, vw: innerWidth }; })()"""

async def run2(b, scheme, w, h):
    T = f'[{scheme} {w}]'
    ctx = await b.new_context(viewport={'width': w, 'height': h}, device_scale_factor=2, is_mobile=True, has_touch=True, color_scheme=scheme)
    await ctx.add_init_script(MOCK); await ctx.add_init_script(AUTO_NOTICE)
    await ctx.add_init_script("try{ localStorage.setItem('radioPlayerTheme', %s); }catch(e){}" % json.dumps(scheme))
    pg = await ctx.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
    await pg.route('**/*', route2)
    await load(pg)
    await pg.evaluate("__t.genre('Rock')"); await pg.wait_for_timeout(1800)
    p = await pg.evaluate(PROBE); print(T, p)
    check(p['heads'] == ['Top stations', 'Artist radio', 'In your library', 'More Rock stations'], f'{T} Rock has an Artist radio row after Top stations {p["heads"]}')
    check(p['radio'] == ['Ann', 'Zed'], f'{T} the library\'s Rock artist first (untagged channel), then the channel tagged rock; not Pop, not one already in Top stations {p["radio"]}')
    check(p['meta'] == '14 stations · 3 songs in your library', f'{T} the counts above are unchanged {p["meta"]!r}')
    check(p['sw'] <= p['vw'], f'{T} nothing scrolls sideways')
    await pg.screenshot(path=f'{shots}/genre-radio-{scheme}-{w}.png')
    await pg.evaluate("document.querySelector('.gp-artist-radio').scrollIntoView({block:'center'})"); await pg.wait_for_timeout(300)
    await pg.screenshot(path=f'{shots}/genre-radio-row-{scheme}-{w}.png')
    await pg.evaluate("document.querySelector('.gp-artist-radio .tile').click()"); await pg.wait_for_timeout(1500)
    q = await pg.evaluate('__t.q()')
    check(q['cur'] == 'Ann', f'{T} tapping one plays that channel {q["cur"]}')
    await pg.evaluate("__t.ev('closeNowPlaying()')"); await pg.wait_for_timeout(400)
    # Jazz: no stations of its own, but Cal's songs are Jazz
    await pg.evaluate("__t.genre('Jazz')"); await pg.wait_for_timeout(1500)
    p = await pg.evaluate(PROBE)
    check(p['heads'] == ['Artist radio', 'In your library'] and p['radio'] == ['Cal'], f'{T} Jazz: Cal\'s channel, from the library\'s Jazz songs {p["heads"]} {p["radio"]}')
    # Classic Rock: the tag reaches Zed's channel; no library songs
    await pg.evaluate("__t.genre('Classic Rock')"); await pg.wait_for_timeout(1500)
    p = await pg.evaluate(PROBE)
    check(p['radio'] == ['Zed'], f'{T} Classic Rock: the channel tagged with it {p["radio"]}')
    # Polka: nothing anywhere
    await pg.evaluate("__t.genre('Polka')"); await pg.wait_for_timeout(1500)
    p = await pg.evaluate(PROBE)
    check(p['radio'] is None, f'{T} no row when no channel fits {p["heads"]}')
    # Hidden in Settings > Library
    await pg.evaluate("__t.ev('setLibArtistRadio(false)')"); await pg.wait_for_timeout(300)
    await pg.evaluate("__t.genre('Rock')"); await pg.wait_for_timeout(1500)
    p = await pg.evaluate(PROBE)
    check(p['radio'] is None and 'Artist radio' not in p['heads'], f'{T} Artist radio in Library: Hide hides the row too {p["heads"]}')
    await pg.evaluate("__t.ev('setLibArtistRadio(true)')")
    check(not errs, f'{T} no page errors {errs[:3]}')
    await ctx.close()

async def main2():
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
        await run2(b, 'dark', 390, 844)
        await run2(b, 'light', 360, 780)
        await b.close()
    print('ALL PASSED' if not fails else 'FAILED %s' % fails)
    sys.exit(1 if fails else 0)
asyncio.run(main2())
