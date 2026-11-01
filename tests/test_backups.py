"""Build 373: automatic backups. Settings > Privacy & Backup: turning Automatic backup on asks for
a folder and backs up at once; How often / Backups to keep; the folder line says when the last
backup was; Back Up Now replaces today's file; only the newest N are kept; Restore lists the
backups, shows what one holds, and Replace puts everything back exactly (favorites, settings,
profile, listening stats, podcast progress, and Android's own copy of the lists) after saving a
"before restore" backup; Merge only adds. Due backups run by themselves. Phone, dark and light.
Run: python3 tests/test_backups.py (screenshots in /tmp/claude-0/t/shots)"""
import sys as _nsys, os as _nos; _nsys.path.insert(0, _nos.path.dirname(_nos.path.abspath(__file__))); from notice_auto import AUTO_NOTICE
import asyncio, os, json, threading, http.server, functools, shutil
from playwright.async_api import async_playwright
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = '/tmp/claude-0/t/srv-backups'; SHOTS = '/tmp/claude-0/t/shots'; PORT = 8878
shutil.rmtree(ROOT, ignore_errors=True); os.makedirs(ROOT); os.makedirs(SHOTS, exist_ok=True)
HOOK = "window.__t = { ev: function(js){ return eval(js); }, set: function(c){ openSettings(c); } };\n"
src = open(os.path.join(HERE, '..', 'www', 'index.html')).read()
mark = '  var coverFlow = null;\n'; assert src.count(mark) == 1
open(ROOT + '/index.html', 'w').write(src.replace(mark, mark + HOOK))
H = functools.partial(http.server.SimpleHTTPRequestHandler, directory=ROOT); H.log_message = lambda *a: None
srv = http.server.ThreadingHTTPServer(('127.0.0.1', PORT), H); threading.Thread(target=srv.serve_forever, daemon=True).start()
# The phone: a backup folder and Android's copy of the lists, both kept in sessionStorage so they
# survive the reload a restore does. Notices close by themselves only for the library's progress.
MOCK = """
(function(){
  function F(){ try{ return JSON.parse(sessionStorage.getItem('__folder') || '{}'); }catch(e){ return {}; } }
  function setF(f){ sessionStorage.setItem('__folder', JSON.stringify(f)); }
  function KV(){ try{ return JSON.parse(sessionStorage.getItem('__kv') || '{}'); }catch(e){ return {}; } }
  window.__picks = 0;
  var impl = {
    saveToDownloads: function(o){ window.__saved = o.name; return Promise.resolve({ folder: 'Downloads', name: o.name }); },
    pickBackupFolder: function(){ window.__picks++; return Promise.resolve({ treeUri: 'content://tree/Backups', name: 'Amplify Backups' }); },
    backupWrite: function(o){
      var f = F(); f[o.name] = { text: o.text, at: Date.now() };
      var names = Object.keys(f).sort().reverse(), removed = [];
      names.slice(o.keep).forEach(function(n){ delete f[n]; removed.push(n); });
      setF(f); window.__writes = (window.__writes || []).concat([o.name]);
      return Promise.resolve({ name: o.name, uri: 'content://doc/' + o.name, size: o.text.length, lastModified: Date.now(), removed: removed });
    },
    backupList: function(o){ var f = F(); return Promise.resolve({ files: Object.keys(f).sort().reverse().map(function(n){ return { name: n, uri: 'content://doc/' + n, size: f[n].text.length, lastModified: f[n].at }; }) }); },
    backupRead: function(o){ var f = F(), n = o.uri.replace('content://doc/', ''); return f[n] ? Promise.resolve({ text: f[n].text }) : Promise.reject(new Error('gone')); },
    kvSet: function(o){ var k = KV(); if(o.value == null) delete k[o.key]; else k[o.key] = o.value; sessionStorage.setItem('__kv', JSON.stringify(k)); return Promise.resolve({ ok: true }); },
    kvGetAll: function(){ return Promise.resolve({ values: KV() }); },
    addListener: function(){ return Promise.resolve({ remove: function(){} }); }
  };
  var P = new Proxy({}, { get: function(t, k){ if(k === 'then') return undefined; if(k === 'setCarLibraryPart') return undefined; if(impl[k]) return impl[k]; return function(){ return Promise.resolve({}); }; } });
  window.Capacitor = { isNativePlatform: function(){ return true; }, getPlatform: function(){ return 'android'; }, registerPlugin: function(){ return P; }, Plugins: { AmplifyPlayer: P }, convertFileSrc: function(u){ return u; } };
})();
"""
NOTICES = """document.addEventListener('DOMContentLoaded', function(){
  var o = document.getElementById('importOverlay');
  var n = document.getElementById('noticeOverlay');
  if(n) new MutationObserver(function(){ if(n.classList.contains('open') && /mirrors|unreachable|offline|network/i.test(document.getElementById('noticeMsg').textContent)) setTimeout(function(){ n.classList.remove('open'); }, 0); }).observe(n, { attributes: true, attributeFilter: ['class'] });
  if(o) new MutationObserver(function(){ if(o.classList.contains('open')) setTimeout(function(){ o.classList.remove('open'); }, 0); }).observe(o, { attributes: true, attributeFilter: ['class'] });
});"""
ST = [{'name': n, 'urlToResolve': 'http://x/%d' % i, 'favicon': '', 'tags': 'soul', 'stationuuid': 'u%d' % i} for i, n in enumerate(['Motown Radio', "80's 80's", 'Jazz FM'])]
SEED = ("if(!sessionStorage.getItem('__seed')){ sessionStorage.setItem('__seed','1');"
        " localStorage.setItem('radioPlayerFavorites', %s); localStorage.setItem('radioPlayerProfile', JSON.stringify({name:'Mark'}));"
        " localStorage.setItem('radioPlayerListening', JSON.stringify({v:1,start:1,days:{'2026-10-30':{t:3600,r:3600}},hours:[],items:{},artists:{}}));"
        " localStorage.setItem('radioPlayerPlexAccount', 'secret-token');"
        " var old = {}; for(var i = 1; i <= 9; i++){ old['amplify-backup-2026-09-0' + i + '.json'] = { text: '{}', at: 1 }; } sessionStorage.setItem('__folder', JSON.stringify(old)); }") % json.dumps(json.dumps(ST))
fails = []
def check(ok, msg):
    print(('PASS ' if ok else 'FAIL ') + msg)
    if not ok: fails.append(msg)
async def notice(pg):
    return await pg.evaluate("[document.getElementById('noticeOverlay').classList.contains('open'), document.getElementById('noticeTitle').textContent, document.getElementById('noticeMsg').textContent, Array.prototype.map.call(document.querySelectorAll('#noticeActions button'), function(b){ return b.textContent; })]")
async def act(pg, label):
    await pg.evaluate("(l)=>Array.prototype.filter.call(document.querySelectorAll('#noticeActions button'), function(b){ return b.textContent === l; })[0].click()", label)
async def run(B, theme):
    T = f'[{theme}]'
    c = await B.new_context(viewport={'width': 390, 'height': 844}, device_scale_factor=2, is_mobile=True, has_touch=True, color_scheme=theme)
    await c.add_init_script(MOCK); await c.add_init_script(NOTICES); await c.add_init_script(SEED)
    pg = await c.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
    await pg.goto(f'http://127.0.0.1:{PORT}/index.html'); await pg.wait_for_timeout(2200)
    await pg.evaluate("__t.set('privacy')"); await pg.wait_for_timeout(300)
    vis = await pg.evaluate("['bkAutoRow','bkFolderRow','bkEveryRow'].map(function(id){ return getComputedStyle(document.getElementById(id)).display !== 'none'; })")
    check(vis == [True, True, False], f'{T} the app shows Automatic backup and the folder; How often only once it is on {vis}')
    await pg.screenshot(path=f'{SHOTS}/backup-{theme}-off.png')
    await pg.click('#bkAutoSelectSwitch', timeout=6000); await pg.wait_for_timeout(800)
    st = await pg.evaluate("[window.__picks, (window.__writes||[]).length, document.getElementById('bkFolderDesc').textContent, JSON.parse(sessionStorage.getItem('__folder')) ]")
    names = sorted(st[3].keys(), reverse=True)
    today = await pg.evaluate("__t.ev('backupDateName()')")
    check(st[0] == 1 and st[1] == 1 and names[0] == today, f'{T} turning it on asks for a folder and backs up at once {st[:3]} {names[:2]}')
    check(len(names) == 8, f'{T} only the newest 8 are kept (9 old + 1 new) {len(names)}')
    check(st[2].startswith('Amplify Backups · Last backup today'), f'{T} the folder line says when {st[2]!r}')
    data = json.loads(st[3][today]['text'])
    store = data['amplifyBackup']['store']
    check('radioPlayerFavorites' in store and 'radioPlayerProfile' in store and 'radioPlayerListening' in store, f'{T} the backup holds lists, profile and stats')
    check('radioPlayerPlexAccount' not in store and 'radioPlayerBackupSettings' not in store, f'{T} but not the Plex sign-in or the backup settings')
    check(len(data.get('favorites', [])) == 3, f'{T} and the Export fields, so Import can merge it')
    await pg.screenshot(path=f'{SHOTS}/backup-{theme}-on.png')
    # change things after the backup
    await pg.evaluate("localStorage.setItem('radioPlayerFavorites', JSON.stringify([])); localStorage.setItem('radioPlayerProfile', JSON.stringify({name:'Someone Else'})); localStorage.setItem('radioPlayerTheme', 'light');")
    # Restore: the list, then the backup, then Replace
    await pg.click('#bkRestoreBtn'); await pg.wait_for_timeout(500)
    n = await notice(pg)
    files = await pg.evaluate("Array.prototype.map.call(document.querySelectorAll('.bk-file .bk-file-name'), function(e){ return e.textContent; })")
    check(n[1] == 'Restore' and len(files) == 8, f'{T} Restore lists the backups {files[:2]}')
    await pg.screenshot(path=f'{SHOTS}/backup-{theme}-list.png')
    await pg.evaluate("document.querySelector('.bk-file').click()"); await pg.wait_for_timeout(500)
    n = await notice(pg)
    check(n[1] == 'Restore this backup?' and '3 favorites' in n[2] and n[3] == ['Replace Everything', 'Merge', 'Cancel'], f'{T} it says what the backup holds and offers Replace or Merge {n}')
    await pg.screenshot(path=f'{SHOTS}/backup-{theme}-choice.png')
    await act(pg, 'Replace Everything'); await pg.wait_for_timeout(300)
    conf = await pg.evaluate("[document.getElementById('confirmOverlay').classList.contains('open'), document.getElementById('confirmTitle').textContent, document.getElementById('confirmMsg').textContent]")
    check(conf[0] and conf[1] == 'Replace everything?' and 'saved first' in conf[2], f'{T} Replace asks first {conf}')
    await pg.screenshot(path=f'{SHOTS}/backup-{theme}-confirm.png')
    await pg.click('#confirmOk')
    await pg.wait_for_load_state('load'); await pg.wait_for_timeout(2500)
    after = await pg.evaluate("[JSON.parse(localStorage.getItem('radioPlayerFavorites')).length, JSON.parse(localStorage.getItem('radioPlayerProfile')).name, localStorage.getItem('radioPlayerTheme'), localStorage.getItem('radioPlayerPlexAccount'), JSON.parse(sessionStorage.getItem('__kv')).radioPlayerFavorites]")
    check(after[0] == 3 and after[1] == 'Mark' and after[2] is None and after[3] == 'secret-token', f'{T} after the reload everything is as it was (Plex sign-in untouched) {after[:4]}')
    check(after[4] and len(json.loads(after[4])) == 3, f'{T} the Android copy of the lists was updated before the reload (or it would put the old ones back)')
    folder = await pg.evaluate("Object.keys(JSON.parse(sessionStorage.getItem('__folder')))")
    check(any('before-restore' in x for x in folder), f'{T} a backup of how things were was saved first {[x for x in folder if "before" in x]}')
    n = await notice(pg)
    check(n[1] == 'Restored', f'{T} it says Restored {n[:2]}')
    # Merge from a file with Import: a backup with everything opens the same choice
    await pg.evaluate("localStorage.setItem('radioPlayerFavorites', JSON.stringify([]))")
    await pg.reload(); await pg.wait_for_timeout(2000)
    data['amplifyBackup']['at'] = '2026-10-31T12:00:00Z'
    p = ROOT + '/b.json'; open(p, 'w').write(json.dumps(data))
    await pg.evaluate("__t.set('privacy')"); await pg.wait_for_timeout(200)
    await pg.set_input_files('#importFavInput', p); await pg.wait_for_timeout(500)
    n = await notice(pg)
    check(n[1] == 'Restore this backup?', f'{T} Import of a full backup offers Replace or Merge too')
    await act(pg, 'Merge'); await pg.wait_for_timeout(500)
    favs = await pg.evaluate("JSON.parse(localStorage.getItem('radioPlayerFavorites')).length")
    check(favs == 3, f'{T} Merge adds what is missing ({favs})')
    # Export: the message comes up over Settings, and OK goes back to Settings, not the homepage
    await pg.evaluate("document.getElementById('dataDialogOkBtn').click()")
    await pg.click('#exportFavBtn'); await pg.wait_for_timeout(600)
    ex = await pg.evaluate("[window.__saved, document.getElementById('dataDialogTitle').textContent, document.getElementById('settingsOverlay').classList.contains('open'), (function(){ var b = document.getElementById('dataDialogOkBtn').getBoundingClientRect(); var e = document.elementFromPoint(b.x + b.width/2, b.y + b.height/2); return e && e.id; })()]")
    check(ex[0] and ex[1] == 'Export Complete' and ex[2] and ex[3] == 'dataDialogOkBtn', f'{T} Export says where it saved, over Settings {ex}')
    await pg.screenshot(path=f'{SHOTS}/backup-{theme}-export.png')
    await pg.click('#dataDialogOkBtn'); await pg.wait_for_timeout(300)
    back = await pg.evaluate("[document.getElementById('settingsOverlay').classList.contains('open'), getComputedStyle(document.getElementById('bkFolderRow')).display !== 'none']")
    check(back == [True, True], f'{T} OK goes back to Privacy & Backup {back}')
    # due: a week old
    await pg.evaluate("var b = JSON.parse(localStorage.getItem('radioPlayerBackupSettings')); b.last = Date.now() - 8*86400000; localStorage.setItem('radioPlayerBackupSettings', JSON.stringify(b)); window.__writes = [];")
    await pg.evaluate("__t.ev('runDueBackup()')"); await pg.wait_for_timeout(600)
    check(await pg.evaluate("(window.__writes||[]).length") == 1, f'{T} a week later it backs up by itself')
    await pg.evaluate("window.__writes = []; __t.ev('runDueBackup()')"); await pg.wait_for_timeout(600)
    check(await pg.evaluate("(window.__writes||[]).length") == 0, f'{T} and not again until the next is due')
    check(not errs, f'{T} no page errors {errs}')
    await c.close()
async def main():
    async with async_playwright() as p:
        B = await p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
        for th in ('dark', 'light'): await run(B, th)
        await B.close()
    print('ALL PASSED' if not fails else f'FAILS {len(fails)}')
asyncio.run(main())
