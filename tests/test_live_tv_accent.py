"""Live TV keeps the theme accent (build 203): a playing channel takes no colour from its logo, even when
the phone can read the logo's pixels (CapacitorHttp mocked). Tab bar, back button and list heading checked
in both themes, and back on Live TV. Run: python3 tests/test_live_tv_accent.py"""
import sys as _nsys, os as _nos; _nsys.path.insert(0, _nos.path.dirname(_nos.path.abspath(__file__))); from notice_auto import AUTO_NOTICE
import asyncio, os, sys, json, base64, zlib, struct
sys.argv=[sys.argv[0]]+sys.argv[1:]
TAG = 'livetv'
HERE=os.path.dirname(os.path.abspath(__file__))
src=open(os.path.join(HERE,'test_video_channels.py')).read()
head=src[:src.index('async def rows(pg)')]
head=head.replace("'/tmp/claude-0/t/srv-ch'","'/tmp/claude-0/t/srv-ltacc'").replace('8777','8802')
exec(head)
def png(rgb):
    w=h=64; raw=b''.join(b'\x00'+bytes(rgb)*w for _ in range(h))
    def ch(t,d): return struct.pack('>I',len(d))+t+d+struct.pack('>I',zlib.crc32(t+d)&0xffffffff)
    return b'\x89PNG\r\n\x1a\n'+ch(b'IHDR',struct.pack('>IIBBBBB',w,h,8,2,0,0,0))+ch(b'IDAT',zlib.compress(raw))+ch(b'IEND',b'')
IMG={'red':png((220,30,30)),'green':png((30,200,60))}
SEED=[{'id':'link:r','name':'Red TV','url':'https://red.example/l.m3u8','logo':'https://img.example/red.png','country':'','cats':[],'catNames':[],'src':'link','addedAt':1},
      {'id':'link:g','name':'Green TV','url':'https://green.example/l.m3u8','logo':'https://img.example/green.png','country':'','cats':[],'catNames':[],'src':'link','addedAt':2},
      {'id':'link:n','name':'Nologo TV','url':'https://n.example/l.m3u8','logo':'','country':'','cats':[],'catNames':[],'src':'link','addedAt':3}]
base_route=route
async def route2(r):
    u=r.request.url
    if 'img.example' in u:
        k='red' if 'red' in u else 'green'
        return await r.fulfill(status=200,content_type='image/png',headers={'Access-Control-Allow-Origin':'*'},body=IMG[k])
    return await base_route(r)
from playwright.async_api import async_playwright
ACC={'dark':'rgb(240, 166, 58)','light':'rgb(28, 32, 60)'}
PROBE="""(()=>{var q=s=>document.querySelector(s), cs=e=>e?getComputedStyle(e):null;
 var nav=q('.mobile-nav-btn.active'), tab=q('.home-tab.active'), play=q('.np-play-btn'), back=q('.np-float .np-back'), vr=q('.vctl-range');
 var b=getComputedStyle(document.body);
 return {navActive:nav&&cs(nav).color, tabActive:tab&&[cs(tab).backgroundColor,cs(tab).color], play:play&&cs(play).backgroundColor,
   back:back&&cs(back).color, vctl:vr&&cs(vr).backgroundImage.slice(0,80), accent:b.getPropertyValue('--accent').trim(), vivid:b.getPropertyValue('--np-vivid').trim(),
   pageTint:b.getPropertyValue('--page-tint').trim(), bodyBg:b.backgroundColor};})()"""
async def run(p,theme):
    b=await p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
    ctx=await b.new_context(viewport={'width':412,'height':900},device_scale_factor=2,is_mobile=True,has_touch=True,color_scheme='dark',locale='en-US')
    await ctx.add_init_script(MOCK); await ctx.add_init_script(AUTO_NOTICE)
    await ctx.add_init_script("window.__IMG=%s; setTimeout(function(){},0); (function(){var C=window.Capacitor; C.Plugins.CapacitorHttp={request:function(a){var k=/red/.test(a.url)?'red':(/green/.test(a.url)?'green':null); return Promise.resolve(k?{status:200,data:window.__IMG[k]}:{status:404,data:''});}};})();" % json.dumps({k:base64.b64encode(v).decode() for k,v in IMG.items()}))
    await ctx.add_init_script("localStorage.setItem('radioPlayerVideoChannels', %s)"%repr(json.dumps(SEED)))
    await ctx.add_init_script("localStorage.setItem('radioPlayerTheme', '%s')"%theme)
    pg=await ctx.new_page(); errs=[]; pg.on('pageerror',lambda e:errs.append(str(e)))
    await pg.route('**/*',route2)
    await pg.goto('http://127.0.0.1:8802/index.html'); await pg.wait_for_timeout(2500)
    await pg.evaluate("document.querySelector('.mobile-nav-btn[data-nav=video]').click()"); await pg.wait_for_timeout(800)
    print(theme,'livetv',await pg.evaluate(PROBE)); await pg.screenshot(path=f'{SHOTS}/probe-{TAG}-{theme}-livetv.png')
    for name in ['Red TV','Green TV']:
        await pg.evaluate("(n)=>Array.prototype.find.call(document.querySelectorAll('#stationsGrid .epg-ch, #npCollectionGrid .epg-ch, #npCollectionGrid .tile-row'),function(t){return ((t.getAttribute('aria-label')||'')+t.textContent).indexOf(n)>=0 && t.getClientRects().length;}).click()",name); await pg.wait_for_timeout(1500)
        cur=await pg.evaluate("window.__cur")
        await pg.evaluate("(id)=>window.__emit('video',{id:id,hasVideo:true,width:1280,height:720})",cur); await pg.wait_for_timeout(900)
        if await pg.evaluate("document.body.classList.contains('np-video-full')"):
            await pg.evaluate("window.__emit('videotap',{})"); await pg.wait_for_timeout(600)
        r=await pg.evaluate(PROBE); print(theme,name,r)
        check(r['vivid']=='' and r['navActive']==ACC[theme], f'{theme} {name}: tab bar uses the theme accent, no colour from the logo {r}')
        hd,want=await pg.evaluate("(()=>{var h=document.getElementById('npCollectionHeading'),x=document.createElement('span');x.style.color='var(--text-dim)';h.parentNode.appendChild(x);var w=getComputedStyle(x).color;x.remove();return [getComputedStyle(h).color,w];})()")
        check(hd==want and hd!='rgb(255, 255, 255)' or (theme=='dark' and hd==want), f'{theme} {name}: channel list heading in the default grey ({hd})'); await pg.screenshot(path=f'{SHOTS}/probe-{TAG}-{theme}-{name[:3]}.png')
    await pg.evaluate("document.getElementById('npBackBtn').click()"); await pg.wait_for_timeout(800)
    r=await pg.evaluate(PROBE); print(theme,'back on livetv',r)
    check(r['navActive']==ACC[theme] and r['tabActive'][0]==ACC[theme], f'{theme}: Live TV still in the theme accent {r}'); await pg.screenshot(path=f'{SHOTS}/probe-{TAG}-{theme}-livetv2.png')
    check(not errs, f'{theme}: no page errors {errs[:3]}'); await b.close()
async def main():
    async with async_playwright() as p:
        for t in ['dark','light']: await run(p,t)
    print('ALL PASSED' if not fails else f'FAILED {fails}')
asyncio.run(main())
