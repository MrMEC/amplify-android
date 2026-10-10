"""Build 191: saved lists are copied to Android's own storage (AmplifyPlayer.kvSet), and a write
the WebView lost (Mark: a channel added to Favorites was gone after reopening the app) is put
back at start-up. The mock keeps its "Android" copy in localStorage under __kvmock (written with
the original setItem so it isn't mirrored itself); a lost write is simulated by putting the
favourites back to their old value with that same original setItem.
Run: python3 tests/test_kv_mirror.py"""
import asyncio, os
HERE = os.path.dirname(os.path.abspath(__file__))
src = open(os.path.join(HERE, 'test_fav_order.py')).read()
exec(src[:src.index('async def main')].replace('8819', '8823').replace('srv-favord', 'srv-kv'))
KV = """(function(){
  var oset = Storage.prototype.setItem, oget = Storage.prototype.getItem;
  window.__oset = function(k, v){ oset.call(localStorage, k, v); };
  function store(){ try{ return JSON.parse(oget.call(localStorage, '__kvmock') || '{}'); }catch(e){ return {}; } }
  var P = window.Capacitor.Plugins.AmplifyPlayer;
  window.Capacitor.Plugins.AmplifyPlayer = new Proxy({}, { get: function(t, k){
    if(k === 'kvSet') return function(a){ var s = store(); if(a.value === null || a.value === undefined) delete s[a.key]; else s[a.key] = a.value;
      oset.call(localStorage, '__kvmock', JSON.stringify(s)); window.__kvsets = (window.__kvsets || 0) + 1; return Promise.resolve({ ok: true }); };
    if(k === 'kvGetAll') return function(){ window.__kvgets = (window.__kvgets || 0) + 1; return Promise.resolve({ values: store() }); };
    return P[k];
  }});
})();"""

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
        await pg.goto('http://127.0.0.1:8823/index.html'); await pg.wait_for_timeout(2500)
        kv = await pg.evaluate("JSON.parse(localStorage.getItem('__kvmock') || '{}')")
        check(kv.get('__seeded') == '1' and kv.get('radioPlayerFavorites') == json.dumps(FAVS[:2]) and kv.get('radioPlayerVideoChannels') == json.dumps(CHS),
              f'first run: Android gets a copy of the saved lists {sorted(kv)}')
        check('radioPlayerRecent' not in kv and 'radioPlayerArtCache' not in kv, 'busy caches are not copied')
        before = await pg.evaluate("localStorage.getItem('radioPlayerFavorites')")
        # favourite a channel (Live TV row's More > Favorite path is toggleFavorite too)
        await pg.evaluate("(s)=>window.__fo.toggle(s)", chst(CHS[3])); await pg.wait_for_timeout(400)
        kv = await pg.evaluate("JSON.parse(localStorage.getItem('__kvmock') || '{}')")
        now = await pg.evaluate("localStorage.getItem('radioPlayerFavorites')")
        check(kv.get('radioPlayerFavorites') == now and 'Alpha TV' in now, 'adding a favourite is copied to Android at once')
        # the WebView loses that write: localStorage goes back to the old list
        await pg.evaluate("(v)=>window.__oset('radioPlayerFavorites', v)", before)
        await pg.reload(); await pg.wait_for_timeout(4000)
        favs = await pg.evaluate("JSON.parse(localStorage.getItem('radioPlayerFavorites')).map(function(f){ return f.name; })")
        check('Alpha TV' in favs and len(favs) == 3, f'a lost write is put back from Android at start-up {favs}')
        await pg.evaluate("document.querySelector('.mobile-nav-btn[data-nav=video]').click()"); await pg.wait_for_timeout(800)
        lt = await pg.evaluate("Array.prototype.map.call(document.querySelectorAll('#stationsGrid > .ch-group-head, #stationsGrid > .tile-row'), function(e){ return e.classList.contains('ch-group-head') ? '#' + e.textContent : (e.querySelector('.tile-name')||e).textContent.trim(); })")
        check(lt[:4] == ['#Favorites', 'Alpha TV', 'Zed TV', '#My Channels'], f'and the channel shows under Favorites on Live TV {lt[:5]}')
        gets = await pg.evaluate("window.__kvgets")
        # no reload loop: a further restart with everything in step reloads nothing
        await pg.reload(); await pg.wait_for_timeout(3000)
        check(await pg.evaluate("window.__kvgets") == 1, 'with both copies in step there is no extra reload')
        # removing a favourite is copied too
        await pg.evaluate("(s)=>window.__fo.toggle(s)", chst(CHS[3])); await pg.wait_for_timeout(400)
        kv = await pg.evaluate("JSON.parse(localStorage.getItem('__kvmock') || '{}')")
        check('Alpha TV' not in kv.get('radioPlayerFavorites', ''), 'removing a favourite is copied too')
        # writes made at start-up before Android answers are copied once it does
        await pg.evaluate("window.__oset('radioPlayerFavOrder', 'az')")
        await pg.evaluate("(()=>{ var s=JSON.parse(localStorage.getItem('__kvmock')); s.radioPlayerFavOrder='az'; window.__oset('__kvmock', JSON.stringify(s)); })()")
        await pg.reload(); await pg.wait_for_timeout(3000)
        check(await pg.evaluate("localStorage.getItem('radioPlayerFavOrder')") == 'az', 'a setting in step stays')
        check(not errs, f'no page errors {errs[:3]}')
        await b.close()
    print('ALL PASSED' if not fails else f'FAILED {fails}')
asyncio.run(main())
