import os, sys
_here = os.path.dirname(os.path.abspath(__file__))
_src = open(os.path.join(_here, 'test_home_favs_kinds.py')).read()
_head = _src[:_src.index('\nasync def main():')].replace("PORT = 8832", "PORT = 8836").replace("srv_homefavkinds", "srv_probear")
_head = _head.replace("HOOK + KHOOK", "HOOK + KHOOK + 'window.__ev = function(js){ return eval(js); };'")
__file__ = os.path.join(_here, 'test_home_favs_kinds.py')
exec(_head)
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
        for _ in range(60):
            await pg.wait_for_timeout(500)
            if len(await pg.evaluate('__t.tracks()')) >= 4: break
        await pg.evaluate("(function(){ var ov=document.getElementById('addMusicOverlay'); if(ov) ov.classList.remove('open'); })()")
        await pg.evaluate('__h.home()'); await pg.wait_for_timeout(800)
        info = await pg.evaluate('__k.seed()')
        await pg.evaluate("(n)=>__ev('(function(){ var e = buildArtistIndex().filter(function(x){ return x.name === ' + JSON.stringify(n) + '; })[0]; openArtistPage(e.key); })()')", info['artist'])
        await pg.wait_for_timeout(1500)
        heads = await pg.evaluate("Array.from(document.querySelectorAll('#stationsGrid .section-heading, #stationsGrid h2, #stationsGrid .grid-section-head')).map(h => h.textContent)")
        print('heads', heads)
        await pg.evaluate("(n)=>{ var t = Array.from(document.querySelectorAll('#stationsGrid .tile')).filter(t => /Radio/.test((t.querySelector('.tile-name')||{}).textContent))[0]; t.scrollIntoView({block:'center'}); t.click(); }", info['artist'])
        await pg.wait_for_timeout(1500)
        await pg.evaluate("__ev('closeNowPlaying()')"); await pg.wait_for_timeout(500)
        d = await pg.evaluate('''()=>{ var t = Array.from(document.querySelectorAll('#stationsGrid .tile')).filter(t => /Radio/.test((t.querySelector('.tile-name')||{}).textContent))[0];
          t.scrollIntoView({block:'center'});
          var a = t.querySelector('.tile-art'), cs = getComputedStyle(a), af = getComputedStyle(a, '::after');
          return { cls: t.className, artCls: a.className, html: a.outerHTML.slice(0, 600), pos: cs.position, w: a.getBoundingClientRect().width, afW: af.width, afH: af.height, bfW: getComputedStyle(a, '::before').width, bfRight: getComputedStyle(a, '::before').right, afPos: af.position, afInset: af.inset, afContent: af.content,
                   arts: Array.from(t.querySelectorAll('.tile-art')).length }; }''')
        print(d)
        await pg.evaluate("document.body.classList.add('ring-ready')"); await pg.wait_for_timeout(600)
        await pg.screenshot(path='/tmp/claude-0/t/shots/probe-ar.png', clip={'x': 0, 'y': 300, 'width': 260, 'height': 280})
        print(errs[:3])
        await b.close()
asyncio.run(main())
