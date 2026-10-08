"""Build 155: a cover picked from the device is kept in IndexedDB, so a full localStorage no
longer stops it saving ("browser storage is full"); it is still there after a restart.
Run: python3 tests/test_custom_art_idb.py"""
import asyncio, os, json
HERE = os.path.dirname(os.path.abspath(__file__))
src = open(os.path.join(HERE, 'test_np_nav_pip.py')).read()
head = src[:src.index('async def main()')]
head = head.replace("'/tmp/claude-0/t/srv-pip'", "'/tmp/claude-0/t/srv-artidb'").replace('8779', '8818')
exec(head)
PNG = '/tmp/claude-0/t/noise.png'
FILL = """(()=>{ var chunk=new Array(200001).join('x'), i=0;
  try{ for(;i<200;i++) localStorage.setItem('__fill'+i, chunk); }catch(e){}
  var small=new Array(2001).join('y'); try{ for(var j=0;j<500;j++) localStorage.setItem('__fs'+j, small); }catch(e){}
  return i; })()"""

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
        ctx = await b.new_context(viewport={'width': 390, 'height': 844}, device_scale_factor=2, is_mobile=True, has_touch=True, color_scheme='dark', locale='en-US')
        await ctx.add_init_script(MOCK)
        await ctx.add_init_script("if(!localStorage.getItem('radioPlayerRecent')) localStorage.setItem('radioPlayerRecent', %s)" % repr(json.dumps(RECENT)))
        pg = await ctx.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.route('**/*', route)
        await pg.goto('http://127.0.0.1:8818/index.html'); await pg.wait_for_timeout(2500)
        n = await pg.evaluate(FILL)
        full = await pg.evaluate("(()=>{try{localStorage.setItem('__probe', new Array(50001).join('z')); localStorage.removeItem('__probe'); return false;}catch(e){return true;}})()")
        check(full, f'localStorage is full ({n} chunks)')
        await pg.evaluate("document.querySelector('#recentSection .tile[data-key]').click()"); await pg.wait_for_timeout(900)
        await pg.evaluate("document.getElementById('playerNowTrigger').click()"); await pg.wait_for_timeout(900)
        await pg.evaluate("document.getElementById('npArtEditBtn').click()"); await pg.wait_for_timeout(300)
        await pg.set_input_files('#artUrlFileInput', PNG); await pg.wait_for_timeout(1500)
        await pg.evaluate("document.getElementById('artUrlSaveBtn').click()"); await pg.wait_for_timeout(800)
        st = await pg.evaluate("""(()=>{var o=document.getElementById('artUrlOverlay'), n=document.getElementById('artUrlNote');
          var img=document.querySelector('#npArt img'); return {open:o.classList.contains('open'), note:n.textContent, src:img?img.getAttribute('src').slice(0,30):null};})()""")
        check(not st['open'] and 'full' not in st['note'] and st['src'] and st['src'].startswith('data:image'), f'the picked image saves despite a full localStorage and shows {st}')
        ls = await pg.evaluate("(localStorage.getItem('radioPlayerCustomArt')||'').indexOf('data:')")
        check(ls == -1, f'the picture itself is not in localStorage ({ls})')
        # free the space again (so the app can boot normally) and restart
        await pg.evaluate("Object.keys(localStorage).filter(function(k){return /^__f/.test(k);}).forEach(function(k){localStorage.removeItem(k);})")
        await pg.reload(); await pg.wait_for_timeout(2500)
        tile = await pg.evaluate("(()=>{var i=document.querySelector('#recentSection .tile[data-key] .tile-art img'); return i ? i.getAttribute('src').slice(0,30) : null;})()")
        check(tile and tile.startswith('data:image'), f'after a restart the station tile still wears it ({tile})')
        check(not errs, f'no page errors {errs}')
        await b.close()
    print('ALL PASSED' if not fails else f'FAILED {fails}')
asyncio.run(main())
