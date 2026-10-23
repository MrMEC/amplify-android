"""Build 283 (Mark): 1) guide channel names never break inside a word ("Animatio/n", "Documen/tary"):
they shrink until each word fits, within two lines; 2) the cover behind a playing video no longer
peeks out under it (a thin coloured line): it ends with the video's box and is hidden while a video shows.
Run: python3 tests/test_b283.py (screenshots in /tmp/claude-0/t/shots)"""
import sys as _nsys, os as _nos; _nsys.path.insert(0, _nos.path.dirname(_nos.path.abspath(__file__)))
src = open(_nos.path.join(_nos.path.dirname(_nos.path.abspath(__file__)), 'test_live_channels_editor.py')).read()
src = src[:src.index('async def run2(')].replace('PORT = 8863', 'PORT = 8882').replace("srv-livech2'", "srv-b283'")
exec(src)
import json, sys
NAMES = ['Animation', 'Documentary', 'Classic TV Comedy Hits', 'Comedy', 'Supercalifragilistic Channel']
EXTRA = [{'id': 'link:x%d' % i, 'name': n, 'url': 'https://x.example/%d.m3u8' % i, 'logo': '', 'cats': [], 'catNames': [], 'src': 'link'} for i, n in enumerate(NAMES)]
CHK = """(()=>{ return Array.from(document.querySelectorAll('#stationsGrid .epg-logo-name')).map(n => {
  const t = n.firstChild, words = n.textContent.split(' '); let off = 0, broken = false;
  words.forEach(w => { const r = document.createRange(); r.setStart(t, off); r.setEnd(t, off + w.length); const tops = new Set(Array.from(r.getClientRects()).map(q => Math.round(q.top))); if(tops.size > 1) broken = true; off += w.length + 1; });
  const rr = document.createRange(); rr.selectNodeContents(n); const lines = new Set(Array.from(rr.getClientRects()).map(q => Math.round(q.top))).size;
  return { name: n.textContent, size: parseFloat(getComputedStyle(n).fontSize), broken, lines, cut: n.scrollHeight > n.clientHeight + 1, over: n.scrollWidth > n.parentNode.clientWidth + 1 }; }); })()"""
async def main():
    async with async_playwright() as p:
        for width, zoom in ((390, 1), (360, 1), (390, 1.35)):
            T = f'[{width} text x{zoom}]'
            b = await p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
            ctx = await b.new_context(viewport={'width': width, 'height': 844}, device_scale_factor=3, is_mobile=True, has_touch=True, color_scheme='dark', timezone_id='America/New_York')
            await ctx.add_init_script(MOCK); await ctx.add_init_script(AUTO_NOTICE); await ctx.add_init_script(SEED)
            await ctx.add_init_script("if(!localStorage.getItem('__x')){ localStorage.setItem('__x','1'); var c = JSON.parse(localStorage.getItem('radioPlayerVideoChannels') || '[]'); localStorage.setItem('radioPlayerVideoChannels', JSON.stringify(c.concat(%s))); }" % json.dumps(EXTRA))
            if zoom != 1:  # a phone with larger text: the names start bigger
                await ctx.add_init_script("document.addEventListener('DOMContentLoaded', function(){ var s = document.createElement('style'); s.textContent = '.epg-logo-name{ font-size:%spx; }'; document.head.appendChild(s); });" % round(10.5 * zoom, 2))
            pg = await ctx.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
            await pg.route('**/*', route)
            await pg.goto(f'http://127.0.0.1:{PORT}/index.html'); await pg.wait_for_timeout(2500)
            await pg.evaluate("document.querySelector('.mobile-nav-btn[data-nav=video]').click()"); await pg.wait_for_timeout(1500)
            res = await pg.evaluate(CHK); print(T, res)
            bad = [r for r in res if r['broken'] or r['lines'] > 2 or r['cut'] or (r['over'] and r['size'] > 6.5)]  # a word too long even at the smallest size is cut at the edge, never split
            check(len(res) >= 9 and not bad, f'{T} every channel name breaks only between words, within two lines, nothing cut off {bad}')
            short = [r for r in res if r['name'] in ('MADtv', 'Movies', 'Buzzr')]
            check(all(r['size'] >= round(10.5 * zoom, 2) - 0.5 for r in short), f'{T} short names keep their size {short}')
            await pg.screenshot(path=f'{SHOTS}/b283-guide-{width}-{zoom}.png')
            # 2) the cover behind a playing channel's video
            await pg.evaluate("Array.from(document.querySelectorAll('#stationsGrid .epg-row')).find(r => r.textContent.indexOf('Buzzr') >= 0).querySelector('.epg-prog').click()"); await pg.wait_for_timeout(1500)
            art = await pg.evaluate("""(()=>{ const a = document.querySelector('.now-playing-screen .np-art'), w = document.querySelector('.now-playing-screen .np-art-wrap'), s = document.querySelector('.now-playing-screen');
              const ar = a.getBoundingClientRect(); return { vis: getComputedStyle(a).visibility, vplayer: s.classList.contains('np-vplayer'), artBottom: Math.round(ar.bottom), artTop: Math.round(ar.top), h: Math.round(ar.height), vw: innerWidth }; })()""")
            check(art['vplayer'] and art['vis'] == 'hidden' and abs(art['h'] - min(art['vw'] * 0.5625, 844 * .52)) <= 1.5, f'{T} the cover behind the video: hidden, and only as tall as the video box {art}')
            await pg.screenshot(path=f'{SHOTS}/b283-np-{width}-{zoom}.png')
            check(not errs, f'{T} no page errors {errs[:2]}')
            await b.close()
    print('ALL PASSED' if not fails else f'{fails} FAILED')
    sys.exit(1 if fails else 0)
asyncio.run(main())
