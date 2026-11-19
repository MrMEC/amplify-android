"""Build 693 (Mark): TV channels never wear placeholder or program art: a show playing on one of your
channels is painted as the channel (your picture for it, else its logo). 327x675, dpr 3.3, dark."""
import os, sys, json, asyncio, base64
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
src = open(os.path.join(HERE, 'test_archive_download.py')).read().split('async def notice(pg):')[0]
src = src.replace('PORT = 8881', 'PORT = 8877').replace("ROOT = '/tmp/claude-0/t/srv-iadl'", "ROOT = '/tmp/claude-0/t/srv-charts'")
src = src.replace("HERE = os.path.dirname(os.path.abspath(__file__))", "HERE = %r" % HERE)
exec(src)
AEW = 'data:image/png;base64,' + base64.b64encode(open('/tmp/mock3/aew.png', 'rb').read()).decode()
DEF = [{'id': 'aewch', 'name': 'AEW', 'order': 'sequence', 'src': {'kind': 'pick', 'shows': [], 'movies': [], 'archive': [{'id': 'aew-dyn', 'title': 'AEW Friday Night Dynamite', 'creator': '', 'year': '2021'}]}}]
fails = []
def check(ok, msg):
    print(('PASS ' if ok else 'FAIL ') + msg)
    if not ok: fails.append(msg)
async def main():
    from playwright.async_api import async_playwright
    async with async_playwright() as p:
        B = await p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
        c, pg, errs = await page(B, 'dark', [{'treeUri': 'content://tree/Music', 'name': 'Music'}])
        await pg.set_viewport_size({'width': 327, 'height': 675})
        await pg.evaluate("__t.ev(%s)" % json.dumps('localStorage.setItem("radioPlayerLiveChannels", %s); liveChStore = null; liveChCache = null; 1' % json.dumps(json.dumps(DEF))))
        # a program on the channel, as the player holds it: an archive video with its own picture
        track = "({ type: 'video', id: 'aew-dyn/x.mp4', archive: true, videoKind: 'archive', favicon: 'https://archive.org/services/img/aew-dyn', liveCh: 'amplify-live:aewch', name: 'AEW', liveTitle: 'AEW Friday Night Dynamite', duration: 6180 })"
        probe = """(function(t){ var out = {}; ['player', 'slide'].forEach(function(k){
            var box = document.createElement('div'); box.style.cssText = 'width:120px;height:120px;position:relative';
            if(k === 'slide'){ var sl = document.createElement('div'); sl.className = 'nph-slide'; sl.appendChild(box); document.body.appendChild(sl); } else document.body.appendChild(box);
            renderStationArt(k === 'player' ? playerIcon : box, t);
            var host = k === 'player' ? playerIcon : box, img = host.querySelector('img');
            out[k] = { img: img ? (img.src.slice(0, 40)) : null, ph: host.className + ' ' + (host.style.background || '').slice(0, 30) }; }); return out; })(%s)"""
        # 1) your picture for the channel
        await pg.evaluate("__t.ev(%s)" % json.dumps('setCustomArtUrl("livech:amplify-live:aewch", %s); 1' % json.dumps(AEW)))
        await pg.wait_for_timeout(300)
        r = await pg.evaluate("__t.ev(%s)" % json.dumps(probe % track)); await pg.wait_for_timeout(600)
        r = await pg.evaluate("__t.ev(%s)" % json.dumps(probe % track))
        print('custom', r)
        check(r['player']['img'] and r['player']['img'].startswith('data:image/png') and r['slide']['img'] and r['slide']['img'].startswith('data:image/png'), 'your picture for the channel, in the mini player and the Home carousel')
        # 2) no picture of yours: the channel's own logo (not the program's picture)
        await pg.evaluate("__t.ev(%s)" % json.dumps('clearCustomArtUrl("livech:amplify-live:aewch"); 1')); await pg.wait_for_timeout(300)
        r = await pg.evaluate("__t.ev(%s)" % json.dumps(probe % track)); await pg.wait_for_timeout(600)
        r = await pg.evaluate("__t.ev(%s)" % json.dumps(probe % track))
        chArt = await pg.evaluate("__t.ev('(liveChannelByUrl(\"amplify-live:aewch\") || {}).art || \"\"')")
        print('own logo', r, chArt[:60])
        check('channel-art' in r['player']['ph'] and 'rgb(43, 44, 49)' in r['player']['ph'] and 'channel-art' in r['slide']['ph'], 'without your picture: a channel tile (dark grey under its logo), no generated placeholder %s' % r)
        await pg.evaluate("__t.ev(%s)" % json.dumps('setCustomArtUrl("livech:amplify-live:aewch", %s); 1' % json.dumps(AEW)))
        await pg.evaluate("__t.ev(%s)" % json.dumps('currentStation = %s; renderStationArt(playerIcon, currentStation); 1' % track[1:-1]))
        await pg.wait_for_timeout(800)
        await pg.screenshot(path='/tmp/claude-0/t/shots/chart-mini.png')
        print('errs', errs[:3])
        await c.close(); await B.close()
    print('ALL PASSED' if not fails else 'FAILS %d' % len(fails))
asyncio.run(main())
