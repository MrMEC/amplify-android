"""Build 268: signed out of Plex, Add Channels shows a Plex button right of Pluto. It opens a how-to
dialog with Sign In (primary), I'll do this later and No thanks (stacked). Later keeps the button;
Sign In runs the Plex PIN sign-in with its progress as a notice and lands on the Plex tab; No thanks
removes the button (kept after a restart), says to use Settings, and the button returns once Plex
is signed in from Settings (and then signed out again).
Run: python3 tests/test_plex_addch.py (screenshots in /tmp/claude-0/t/shots)"""
import sys as _nsys, os as _nos; _nsys.path.insert(0, _nos.path.dirname(_nos.path.abspath(__file__)))
import asyncio, os
HERE = os.path.dirname(os.path.abspath(__file__))
src = open(os.path.join(HERE, 'test_plex.py')).read()
head = src[:src.index('async def main()')]
head = head.replace("'/tmp/claude-0/t/srv-plex'", "'/tmp/claude-0/t/srv-plexaddch'").replace('8803', '8852')
exec(head)
from playwright.async_api import async_playwright
from confirm_auto import AUTO_CONFIRM
SHOTS = '/tmp/claude-0/t/shots'
TABS = "Array.prototype.map.call(document.querySelectorAll('.ch-tools .home-tab'),function(b){return b.textContent;})"
ACTIVE = "(document.querySelector('.ch-tools .home-tab.active')||{}).textContent"
NOTICE = """(()=>{ var o=document.getElementById('noticeOverlay'), a=document.getElementById('noticeActions');
  var bs=[].map.call(a.children,function(b){ var r=b.getBoundingClientRect(); return [b.textContent, b.className, Math.round(r.top), Math.round(r.width)]; });
  return { open:o.classList.contains('open'), title:document.getElementById('noticeTitle').textContent, msg:document.getElementById('noticeMsg').textContent, btns:bs, stacked:a.classList.contains('stacked') }; })()"""

async def press(pg, label):
    await pg.evaluate("(l)=>[].find.call(document.querySelectorAll('#noticeActions button'),function(b){return b.textContent===l;}).click()", label)
    await pg.wait_for_timeout(400)
async def open_add(pg):
    await pg.evaluate("document.querySelector('.mobile-nav-btn[data-nav=video]').click()"); await pg.wait_for_timeout(600)
    await pg.evaluate("document.getElementById('videoAddHeaderBtn').click()"); await pg.wait_for_timeout(1200)
async def plex_btn(pg):
    await pg.evaluate("document.getElementById('addChPlexBtn').click()"); await pg.wait_for_timeout(400)

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
        for w, h, scheme in [(412, 915, 'dark'), (360, 780, 'light')]:
            PIN_POLLS[0] = 0
            ctx = await b.new_context(viewport={'width': w, 'height': h}, device_scale_factor=2, is_mobile=True, has_touch=True, color_scheme=scheme, locale='en-US')
            await ctx.add_init_script(MOCK); await ctx.add_init_script(AUTO_CONFIRM); await ctx.add_init_script(EXT)
            await ctx.add_init_script(OPEN); await ctx.add_init_script(FAILLOAD)
            pg = await ctx.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
            await pg.route('**/*', proute)
            await pg.goto('http://127.0.0.1:8852/index.html'); await pg.wait_for_timeout(2500)
            await pg.evaluate("document.getElementById('noticeOverlay').classList.remove('open')")
            tag = f'{w}-{scheme}'

            await open_add(pg)
            t = await pg.evaluate(TABS)
            check(t == ['Recommended', 'All', 'Pluto', 'Plex', 'Link'], f'{tag}: signed out, Plex right of Pluto {t}')
            act = await pg.evaluate(ACTIVE)
            await plex_btn(pg)
            n = await pg.evaluate(NOTICE)
            check(n['open'] and n['title'] == 'Sign in to Plex' and 'Tap Sign In' in n['msg'], f'{tag}: the button opens the how-to dialog {n["title"]}')
            labels = [x[0] for x in n['btns']]
            check(labels == ['Sign In', 'I’ll do this later', 'No thanks'] and n['stacked'], f'{tag}: Sign In, I’ll do this later, No thanks, stacked {labels}')
            check(n['btns'][0][1] == 'notice-ok' and n['btns'][1][1] == 'confirm-cancel' and n['btns'][2][1] == 'confirm-cancel', f'{tag}: Sign In primary, the others secondary {n["btns"]}')
            check(n['btns'][0][2] < n['btns'][1][2] < n['btns'][2][2] and len({x[3] for x in n['btns']}) == 1, f'{tag}: stacked top to bottom, same width {n["btns"]}')
            check(await pg.evaluate(ACTIVE) == act, f'{tag}: the tab does not change')
            await pg.screenshot(path=f'{SHOTS}/plexaddch-dialog-{tag}.png')
            await pg.wait_for_timeout(7000)
            check((await pg.evaluate(NOTICE))['open'], f'{tag}: the dialog stays until answered')

            # Later
            await press(pg, 'I’ll do this later')
            n = await pg.evaluate(NOTICE)
            check(not n['open'] and 'Plex' in await pg.evaluate(TABS), f'{tag}: later closes it and keeps the button')

            # Sign In from here
            await plex_btn(pg); await press(pg, 'Sign In')
            await pg.wait_for_timeout(500)
            n = await pg.evaluate(NOTICE)
            opened = await pg.evaluate("window.__opened")
            check(n['open'] and n['title'] == 'Signing in to Plex' and 'X7K2' in n['msg'] and [x[0] for x in n['btns']] == ['Open Plex Page', 'Cancel'],
                  f'{tag}: Sign In shows the code with Open Plex Page and Cancel {n}')
            check(len(opened) == 1 and 'code=X7K2' in opened[0], f'{tag}: the Plex page opens {opened}')
            await pg.screenshot(path=f'{SHOTS}/plexaddch-signing-{tag}.png')
            await pg.wait_for_timeout(8000)
            n = await pg.evaluate(NOTICE)
            t = await pg.evaluate(TABS)
            check(t == ['Recommended', 'All', 'Pluto', 'Plex', 'Link'] and await pg.evaluate(ACTIVE) == 'Plex' and not await pg.evaluate("!!document.getElementById('addChPlexBtn')"),
                  f'{tag}: signed in, the Plex tab is open {t}')
            check(n['title'] == 'Signed in to Plex', f'{tag}: says it is signed in {n["title"]}')
            await pg.screenshot(path=f'{SHOTS}/plexaddch-signedin-{tag}.png')
            await pg.evaluate("document.getElementById('noticeOverlay').classList.remove('open')")

            # Sign out (Settings): the button is back
            await pg.evaluate("document.getElementById('settingsFab').click()"); await pg.wait_for_timeout(400)
            await pg.evaluate("document.getElementById('plexSignOutBtn').click()"); await pg.wait_for_timeout(800)
            await pg.evaluate("document.getElementById('settingsCloseBtn').click()"); await pg.wait_for_timeout(300)
            await open_add(pg)
            check(await pg.evaluate(TABS) == ['Recommended', 'All', 'Pluto', 'Plex', 'Link'] and await pg.evaluate("!!document.getElementById('addChPlexBtn')"),
                  f'{tag}: signed out again, the Plex button is back')

            # No thanks
            await plex_btn(pg); await press(pg, 'No thanks')
            n = await pg.evaluate(NOTICE)
            t = await pg.evaluate(TABS)
            check(n['open'] and 'Settings' in n['msg'] and [x[0] for x in n['btns']] == ['OK'], f'{tag}: No thanks says to use Settings {n}')
            check(t == ['Recommended', 'All', 'Pluto', 'Link'], f'{tag}: the Plex button is gone {t}')
            await pg.screenshot(path=f'{SHOTS}/plexaddch-nothanks-{tag}.png')
            await pg.wait_for_timeout(7000)
            check((await pg.evaluate(NOTICE))['open'], f'{tag}: the Settings dialog waits for OK')
            await press(pg, 'OK')
            await pg.reload(); await pg.wait_for_timeout(2500)
            await pg.evaluate("document.getElementById('noticeOverlay').classList.remove('open')")
            await open_add(pg)
            check(await pg.evaluate(TABS) == ['Recommended', 'All', 'Pluto', 'Link'], f'{tag}: still gone after a restart')

            # Signed in from Settings: hidden flag cleared; sign out -> button back
            await pg.evaluate("document.getElementById('settingsFab').click()"); await pg.wait_for_timeout(400)
            await pg.evaluate("document.getElementById('plexSignInBtn').click()"); await pg.wait_for_timeout(8000)
            check(await pg.evaluate("localStorage.getItem('radioPlayerPlexAddChHidden')") is None, f'{tag}: signing in from Settings clears No thanks')
            await pg.evaluate("document.getElementById('plexSignOutBtn').click()"); await pg.wait_for_timeout(800)
            await pg.evaluate("document.getElementById('settingsCloseBtn').click()"); await pg.wait_for_timeout(300)
            await pg.evaluate("document.getElementById('noticeOverlay').classList.remove('open')")
            await open_add(pg)
            check(await pg.evaluate(TABS) == ['Recommended', 'All', 'Pluto', 'Plex', 'Link'], f'{tag}: after that, the Plex button shows again when signed out')
            check(not errs, f'{tag}: no page errors {errs[:3]}')
            await ctx.close()
        await b.close()
    print('ALL PASSED' if not fails else f'FAILED {fails}')

asyncio.run(main())
