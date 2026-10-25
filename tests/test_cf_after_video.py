"""Build 318: after a video (a channel, a video on the phone) was played and stopped, turning the phone on
My Library's Albums or Artists opens Cover Flow (Mark: Artists showed the video's background picture,
Albums a black screen). Phone viewport with touch; stops both from the video's own Stop and with the
phone sideways.
Run: python3 tests/test_cf_after_video.py (screenshots in /tmp/claude-0/t/shots)"""
import sys as _nsys, os as _nos; _nsys.path.insert(0, _nos.path.dirname(_nos.path.abspath(__file__))); from notice_auto import AUTO_NOTICE
import asyncio, os, json, threading, http.server, functools, shutil, subprocess, colorsys
from playwright.async_api import async_playwright

PORT = 8848
root = '/tmp/claude-0/t/srv_cfv'
shots = '/tmp/claude-0/t/shots'
os.makedirs(shots, exist_ok=True)
shutil.rmtree(root, ignore_errors=True); os.makedirs(root)
HOOK = "window.__h = { ev: function(js){ return eval(js); } };\n"
_src = open(os.path.join(os.path.dirname(__file__), '..', 'www', 'index.html')).read()
_mark = '  var coverFlow = null;\n'
assert _src.count(_mark) == 1
open(root + '/index.html', 'w').write(_src.replace(_mark, _mark + HOOK))
tone = f'{root}/tone.mp3'
subprocess.run(['ffmpeg', '-loglevel', 'error', '-y', '-f', 'lavfi', '-i', 'sine=frequency=440:duration=2', '-c:a', 'libmp3lame', '-b:a', '48k', tone], check=True)
M = root + '/Music'
n_art = [0]
def art(label):
    n_art[0] += 1
    r, g, b = colorsys.hsv_to_rgb((n_art[0] * 0.13) % 1, .6, .8)
    p = f'{root}/a{n_art[0]}.png'
    subprocess.run(['ffmpeg', '-loglevel', 'error', '-y', '-f', 'lavfi', '-i', 'color=c=0x%02x%02x%02x:s=400x400' % (int(r * 255), int(g * 255), int(b * 255)), '-frames:v', '1', p], check=True)
    return p
def song(folder, n, title, artist, album, cover):
    p = f'{M}/{folder}/{n:02d}.mp3'
    os.makedirs(os.path.dirname(p), exist_ok=True)
    subprocess.run(['ffmpeg', '-loglevel', 'error', '-y', '-i', tone, '-i', cover, '-map', '0:a', '-map', '1:v', '-c:a', 'copy', '-c:v', 'png',
                    '-disposition:v', 'attached_pic', '-id3v2_version', '3', '-metadata', f'title={title}', '-metadata', f'artist={artist}',
                    '-metadata', f'album={album}', '-metadata', f'track={n}', p], check=True)
for artist, albums in [('Zed', ['Alpha', 'Mid']), ('Abba', ['Zulu', 'Beta']), ('Moby', ['Play']), ('Ivy', ['Green'])]:
    for al in albums:
        c = art(al)
        song(f'{artist}/{al}', 1, f'{al} one', artist, al, c)
        song(f'{artist}/{al}', 2, f'{al} two', artist, al, c)
H = functools.partial(http.server.SimpleHTTPRequestHandler, directory=root); H.log_message = lambda *a: None
srv = http.server.ThreadingHTTPServer(('127.0.0.1', PORT), H); threading.Thread(target=srv.serve_forever, daemon=True).start()
files = []
for dp, _, fs in os.walk(M):
    for f in sorted(fs):
        p = os.path.join(dp, f); rel = os.path.relpath(p, root)
        files.append({'uri': f'http://127.0.0.1:{PORT}/' + rel.replace(' ', '%20'), 'name': f, 'relPath': rel, 'type': 'audio/mpeg', 'size': os.path.getsize(p), 'lastModified': 1700000000000})
CH = [{'id': 'link:1', 'name': 'Channel One', 'url': 'http://ch1.example/l.m3u8', 'logo': '', 'country': 'US', 'cats': [], 'catNames': [], 'src': 'link', 'addedAt': 1}]
MOCK = """
(function(){
 var picked = %s;
 window.__L = {}; window.__emit = function(t, ev){ (window.__L[t] || []).forEach(function(f){ f(ev); }); };
 var P = new Proxy({}, {get:function(t,k){
   if(k==='then') return undefined;
   if(k==='pickMusicFolder') return function(){ return Promise.resolve({folder:'Music', files:picked, truncated:false}); };
   if(k==='setCarLibraryPart') return undefined;
   if(k==='addListener') return function(n, f){ (window.__L[n] = window.__L[n] || []).push(f); return Promise.resolve({remove:function(){}}); };
   if(k==='load') return function(a){ window.__cur = a.id;
     setTimeout(function(){ window.__emit('state',{id:a.id,state:'ready',isPlaying:true,playWhenReady:true,position:0,duration:-1,live:true}); },60);
     return Promise.resolve({}); };
   if(k==='videoState') return function(){ return Promise.resolve({id:null,hasVideo:false}); };
   return function(){ return Promise.resolve({}); };
 }});
 window.Capacitor = { isNativePlatform:function(){return true;}, getPlatform:function(){return 'android';},
   registerPlugin:function(){ return P; }, Plugins:{AmplifyPlayer:P}, convertFileSrc:function(u){return u;} };
})();
""" % json.dumps(files)

fails = []
def check(c, m):
    print(('PASS ' if c else 'FAIL ') + m)
    if not c: fails.append(m)

STATE = """(()=>{ var s = document.getElementById('nowPlayingScreen'), la = document.getElementById('npLandAlbums');
  var r = la.getBoundingClientRect(); var cs = getComputedStyle(la);
  var cov = document.querySelectorAll('#npLandAlbums .cf-cover').length;
  var top = document.elementFromPoint(innerWidth / 2, innerHeight / 2);
  return { np: s.style.display, rot: document.body.classList.contains('rotate-lock'), la: s.classList.contains('la-open'),
    laVis: cs.visibility, laOp: cs.opacity, laW: Math.round(r.width), covers: cov,
    channel: s.classList.contains('np-channel'), vplayer: s.classList.contains('np-vplayer'), videoOn: s.classList.contains('np-video-on'),
    top: top ? (top.closest('#npLandAlbums') ? 'coverflow' : (top.id || top.className || top.tagName)) : null }; })()"""

async def rotate(pg, land):
    await pg.set_viewport_size({'width': 844, 'height': 390} if land else {'width': 390, 'height': 844})
    await pg.wait_for_timeout(1400)

async def ev(pg, js): return await pg.evaluate('(js) => window.__h.ev(js)', js)

async def play_and_stop(pg, sideways):
    await ev(pg, "playChannel(findVideoChannel('http://ch1.example/l.m3u8')); 1")
    await pg.wait_for_timeout(700)
    cur = await pg.evaluate("window.__cur")
    await pg.evaluate("(id)=>window.__emit('video',{id:id,hasVideo:true,width:1280,height:720})", cur); await pg.wait_for_timeout(600)
    if sideways:
        await rotate(pg, True)
    await pg.evaluate("window.__emit('videoctl',{action:'stop'})"); await pg.wait_for_timeout(800)
    if sideways:
        await rotate(pg, False)

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        ctx = await b.new_context(viewport={'width': 390, 'height': 844}, device_scale_factor=2, is_mobile=True, has_touch=True, color_scheme='dark')
        await ctx.add_init_script(MOCK); await ctx.add_init_script(AUTO_NOTICE)
        await ctx.add_init_script("if(!localStorage.getItem('radioPlayerVideoChannels')) localStorage.setItem('radioPlayerVideoChannels', %s)" % repr(json.dumps(CH)))
        pg = await ctx.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.goto(f'http://127.0.0.1:{PORT}/index.html'); await pg.wait_for_timeout(2500)
        await pg.evaluate("""(function(){ var ov=document.getElementById('addMusicOverlay'); if(ov) ov.classList.add('open');
          var btn=document.getElementById('addMusicFolderBtn'); btn.disabled=false; btn.click(); })()""")
        for _ in range(60):
            await pg.wait_for_timeout(500)
            if await ev(pg, 'libraryTracks.length') >= len(files): break
        await pg.wait_for_timeout(1000)
        for case, sideways in (('upright stop', False), ('sideways stop', True)):
            for section in ('albums', 'artists'):
                await play_and_stop(pg, sideways)
                await ev(pg, "runLibrarySection('%s'); 1" % section); await pg.wait_for_timeout(800)
                await pg.evaluate("window.scrollTo(0,0)")
                await rotate(pg, True)
                s = await pg.evaluate(STATE)
                check(s['rot'] and s['la'] and s['covers'] > 0 and s['top'] == 'coverflow' and s['laOp'] == '1' and not s['videoOn'],
                      '%s, %s: turning the phone opens Cover Flow %s' % (case, section, s))
                await pg.screenshot(path=f'{shots}/cfv-{section}-{case.split()[0]}.png')
                await rotate(pg, False)
                back = await pg.evaluate("[document.getElementById('nowPlayingScreen').style.display, !!document.querySelector(\".tile[data-entity='%s']\")]" % section[:-1])
                check(back[0] != 'flex' and back[1], '%s, %s: upright again, back on the list %s' % (case, section, back))
        check(not errs, 'no page errors %s' % errs[:3])
        await b.close()
    print('ALL PASSED' if not fails else 'FAILED %s' % fails)
    raise SystemExit(1 if fails else 0)
asyncio.run(main())
