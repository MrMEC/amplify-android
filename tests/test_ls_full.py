"""Build 192: with settings storage (localStorage) full of caches, adding a favourite channel
still saves (a cache is cleared to make room) and is there after a restart; with it full of the
listener's own data, Android's copy (kvSet) still gets the new list and puts it back at start-up.
Check storage reports how full it is. Mark: a channel added to Favorites was gone after reopening.
Run: python3 tests/test_ls_full.py"""
import asyncio, os
HERE = os.path.dirname(os.path.abspath(__file__))
src = open(os.path.join(HERE, 'test_kv_mirror.py')).read()
exec(src[:src.index('\nasync def main():')].replace('8823', '8824').replace('srv-kv', 'srv-lsfull'))
# Android's copy kept in window.name here (it survives a reload, and a full localStorage can't refuse it).
KV = KV.replace("function store(){ try{ return JSON.parse(oget.call(localStorage, '__kvmock') || '{}'); }catch(e){ return {}; } }",
                "function store(){ try{ return JSON.parse(window.name || '{}'); }catch(e){ return {}; } }")
KV = KV.replace("oset.call(localStorage, '__kvmock', JSON.stringify(s));", "window.name = JSON.stringify(s);")
assert 'window.name = JSON' in KV
# Fill localStorage to the brim (Chromium: about 5.2M characters), in 256K pieces.
FILL = """(prefix)=>{ var piece = new Array(262145).join('x'), n = 0;
  for(var i = 0; i < 40; i++){ try{ window.__oset(prefix + i, piece); n++; }catch(e){ break; } }
  [8192, 1024, 128, 16].forEach(function(sz, t){ var small = new Array(sz + 1).join('y');
    for(var j = 0; j < 200; j++){ try{ window.__oset(prefix + 's' + t + '_' + j, small); }catch(e){ break; } } });
  return n; }"""

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
        ctx = await b.new_context(viewport={'width': 412, 'height': 900}, device_scale_factor=2, is_mobile=True, has_touch=True, color_scheme='dark', locale='en-US')
        await ctx.add_init_script(MOCK)
        await ctx.add_init_script(KV)
        await ctx.add_init_script("if(!localStorage.getItem('__seeded')){ localStorage.setItem('__seeded','1'); localStorage.setItem('radioPlayerVideoChannels', %s); localStorage.setItem('radioPlayerFavorites', %s); }"
                                  % (repr(json.dumps(CHS)), repr(json.dumps(FAVS[:2]))))
        pg = await ctx.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.route('**/*', route)
        await pg.goto('http://127.0.0.1:8824/index.html'); await pg.wait_for_timeout(2500)

        # 1) full of caches (amplifyFallback:*, the artist-bio cache's kind of entry)
        n = await pg.evaluate(FILL, 'amplifyFallback:fill')
        full = await pg.evaluate("(()=>{ try{ window.__oset('__probe', new Array(4097).join('p')); localStorage.removeItem('__probe'); return false; }catch(e){ return e.name; } })()")
        check(n > 5 and full == 'QuotaExceededError', f'storage filled with caches ({n} big pieces; {full})')
        await pg.evaluate("(s)=>window.__fo.toggle(s)", chst(CHS[3])); await pg.wait_for_timeout(400)
        saved = await pg.evaluate("localStorage.getItem('radioPlayerFavorites')")
        log = await pg.evaluate("window.__amplifyLsLog")
        check('Alpha TV' in (saved or '') and len(log['freed']) >= 1 and log['freed'][0]['key'].startswith('amplifyFallback:'),
              f'a full store makes room by clearing a cache, and the favourite is saved (cleared {len(log["freed"])})')
        await pg.reload(); await pg.wait_for_timeout(3000)
        await pg.evaluate("document.querySelector('.mobile-nav-btn[data-nav=video]').click()"); await pg.wait_for_timeout(800)
        lt = await pg.evaluate("Array.prototype.map.call(document.querySelectorAll('#stationsGrid > .ch-group-head, #stationsGrid > .tile-row'), function(e){ return e.classList.contains('ch-group-head') ? '#' + e.textContent : (e.querySelector('.tile-name')||e).textContent.trim(); })")
        check(lt[:3] == ['#Favorites', 'Alpha TV', 'Zed TV'], f'after a restart the channel is still under Favorites {lt[:4]}')
        check(await pg.evaluate("localStorage.getItem('radioPlayerVideoChannels') !== null && localStorage.getItem('radioPlayerFavorites') !== null"), 'the listener\'s own lists are never cleared')

        # 2) full of things that aren't caches: localStorage refuses, Android's copy still gets it
        await pg.evaluate("(()=>{ var c = ['radioPlayerArtCache','radioPlayerPluto2','radioPlayerPluto','radioPlayerPlexLib','radioPlayerPodcastPopular','amplifyTagVocab','amplifySlowMoments','radioPlayerLastSearch','radioPlayerVideoStations','radioPlayerMadeForYou'];"
                          " Object.keys(localStorage).forEach(function(k){ if(k.indexOf('amplifyFallback:') === 0 || c.indexOf(k) !== -1) localStorage.removeItem(k); }); })()")
        n2 = await pg.evaluate(FILL, 'userStuff')
        await pg.evaluate("(s)=>window.__fo.toggle(s)", chst(CHS[5])); await pg.wait_for_timeout(400)
        kv = await pg.evaluate("JSON.parse(window.name || '{}')")
        ls_has = await pg.evaluate("(localStorage.getItem('radioPlayerFavorites') || '').indexOf('Mango TV') !== -1")
        log = await pg.evaluate("window.__amplifyLsLog")
        check(n2 > 5 and not ls_has and 'Mango TV' in kv.get('radioPlayerFavorites', '') and log['failed'] and log['failed']['key'] == 'radioPlayerFavorites',
              f'with no cache left to clear, localStorage refuses but Android\'s copy has the new favourite ({ls_has}, {log["failed"]})')
        await pg.evaluate("document.querySelector('.mobile-nav-btn[data-nav=home]').click()"); await pg.wait_for_timeout(500)
        # make room again (as clearing something would) and restart: Android's copy is put back
        await pg.evaluate("Object.keys(localStorage).forEach(function(k){ if(k.indexOf('userStuff') === 0) localStorage.removeItem(k); })")
        await pg.reload(); await pg.wait_for_timeout(4000)
        favs = await pg.evaluate("JSON.parse(localStorage.getItem('radioPlayerFavorites')).map(function(f){ return f.name; })")
        check('Mango TV' in favs and 'Alpha TV' in favs, f'at start-up the refused save is put back from Android {favs}')

        # Check storage shows how full it is
        await pg.evaluate("(()=>{ var b=document.getElementById('diagnosticsBtn'); b.click(); })()"); await pg.wait_for_timeout(1500)
        txt = await pg.evaluate("document.getElementById('diagnosticsBtn').parentElement.parentElement.textContent")
        check('Settings storage used' in txt, 'Check storage shows how much settings storage is used')
        check(not errs, f'no page errors {errs[:3]}')
        await b.close()
    print('ALL PASSED' if not fails else f'FAILED {fails}')
asyncio.run(main())
