"""Build 503: editing tags in M4A files (moov at the end, moov at the front, new tags, a cover)."""
import asyncio, os, json, threading, http.server, functools, shutil, subprocess, base64
from playwright.async_api import async_playwright
PORT = 8896
root = '/tmp/claude-0/t/srv_m4a'
shutil.rmtree(root, ignore_errors=True); os.makedirs(root + '/Music')
_src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'www', 'index.html')).read()
_mark = '  var coverFlow = null;\n'
assert _src.count(_mark) == 1
open(root + '/index.html', 'w').write(_src.replace(_mark, _mark + "window.__t = { ev: function(js){ return eval(js); } };\n"))
M = root + '/Music'
def mk(name, fast, tags=True):
    meta = ['-metadata', 'title=Old Title', '-metadata', 'artist=Old Artist', '-metadata', 'genre=Rock', '-metadata', 'track=2/9'] if tags else []
    subprocess.run(['ffmpeg', '-loglevel', 'error', '-y', '-f', 'lavfi', '-i', 'sine=frequency=440:duration=3', '-c:a', 'aac', '-b:a', '48k'] + meta + (['-movflags', '+faststart'] if fast else []) + [f'{M}/{name}'], check=True)
mk('end.m4a', False); mk('front.m4a', True); mk('bare.m4a', True, False)
subprocess.run(['ffmpeg', '-loglevel', 'error', '-y', '-f', 'lavfi', '-i', 'color=c=red:s=64x64:d=1', '-frames:v', '1', f'{M}/c.png'], check=True)
class Q(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a): pass
srv = http.server.ThreadingHTTPServer(('127.0.0.1', PORT), functools.partial(Q, directory=root))
threading.Thread(target=srv.serve_forever, daemon=True).start()
fails = []
def check(c, m):
    print(('PASS ' if c else 'FAIL ') + m)
    if not c: fails.append(m)
def probe(path):
    r = subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format_tags', '-of', 'json', path], capture_output=True, text=True)
    t = (json.loads(r.stdout or '{}').get('format') or {}).get('tags') or {}
    return {k.lower(): v for k, v in t.items()}
def decodes(path):
    return subprocess.run(['ffmpeg', '-v', 'error', '-i', path, '-f', 'null', '-'], capture_output=True, text=True).stderr.strip() == ''
JS = """async (name) => {
  var blob = await (await fetch('/Music/' + name)).blob();
  var doc = await readTagDoc(blob, name);
  var before = { editable: doc.editable, values: doc.values, why: doc.whyNot };
  var png = new Uint8Array(await (await fetch('/Music/c.png')).arrayBuffer());
  var changes = { title: 'New Títle', artist: 'New Artist', genre: 'Dream Pop', year: '1999', track: '3/12', disc: '1/2', album: 'An Album', cover: { bytes: png, mime: 'image/png' } };
  var moov = buildMp4Moov(doc, changes);
  var nb = new Blob([blob.slice(0, doc.mp4.off), moov, blob.slice(doc.mp4.off + doc.mp4.size)]);
  var d2 = await readTagDoc(nb, name);
  var b64 = await new Promise(function(r){ var fr = new FileReader(); fr.onload = function(){ r(fr.result.split(',')[1]); }; fr.readAsDataURL(nb); });
  var c2 = buildMp4Moov(d2, { genre: '', title: 'Second' });
  var nb2 = new Blob([nb.slice(0, d2.mp4.off), c2, nb.slice(d2.mp4.off + d2.mp4.size)]);
  var d3 = await readTagDoc(nb2, name);
  var b64b = await new Promise(function(r){ var fr = new FileReader(); fr.onload = function(){ r(fr.result.split(',')[1]); }; fr.readAsDataURL(nb2); });
  return { before: before, after: d2.values, hasCover: !!docCover(d2), b64: b64, after2: d3.values, b64b: b64b, moovFirst: doc.mp4.off < 100, delta: moov.length - doc.mp4.size };
}"""
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        pg = await b.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.goto(f'http://127.0.0.1:{PORT}/index.html'); await pg.wait_for_timeout(2500)
        for name in ['end.m4a', 'front.m4a', 'bare.m4a']:
            r = await pg.evaluate("([code, n]) => __t.ev(\"(\" + code + \")\")(n)", [JS, name])
            check(r['before']['editable'], f'{name} is editable ({r["before"]["why"]})')
            a = r['after']
            check(a.get('title') == 'New Títle' and a.get('artist') == 'New Artist' and a.get('genre') == 'Dream Pop' and a.get('year') == '1999' and a.get('track') == '3/12' and a.get('disc') == '1/2' and a.get('album') == 'An Album', f'{name} reads back the new tags {a}')
            check(r['hasCover'], f'{name} has the cover')
            out = f'{root}/out-{name}'; open(out, 'wb').write(base64.b64decode(r['b64']))
            t = probe(out)
            check(t.get('title') == 'New Títle' and t.get('genre') == 'Dream Pop' and t.get('track') == '3/12', f'{name} ffprobe agrees {t}')
            check(decodes(out), f'{name} still plays (decodes with no errors)')
            check(os.path.getsize(f'{M}/{name}') != os.path.getsize(out), f'{name} size changed ({r["delta"]})')
            a2 = r['after2']
            check(a2.get('title') == 'Second' and 'genre' not in a2 and a2.get('artist') == 'New Artist', f'{name} second edit clears the genre {a2}')
            out2 = f'{root}/out2-{name}'; open(out2, 'wb').write(base64.b64decode(r['b64b']))
            check(decodes(out2) and probe(out2).get('title') == 'Second', f'{name} second file valid')
        check(not errs, f'no page errors {errs}')
        await b.close()
asyncio.run(main())
print('FAILS', len(fails)); import sys; sys.exit(1 if fails else 0)
