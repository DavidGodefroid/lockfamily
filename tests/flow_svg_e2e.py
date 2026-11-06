"""End-to-end test of the animated request flow in a real browser.

    python3 tests/flow_svg_e2e.py

Serves the repository on 127.0.0.1, then, in headless Chrome:
  - loads index.html and checks the flow's <picture> resolves to the right
    file for the width and the colour scheme, and that it loads;
  - loads each SVG in a test page and checks it animates, and that under
    prefers-reduced-motion nothing runs and the static frame shows;
  - renders each SVG mid-scenario and as the static frame, and checks the
    screenshot is not blank.

Without Chrome it says so and exits 0, unless FLOW_E2E=required (CI).
No network beyond 127.0.0.1.
"""

import functools
import http.server
import json
import os
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import threading
import zlib

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# Chrome's preferred colour scheme: 0 dark, 1 light (whatever the host's).
LIGHT = ['--blink-settings=preferredColorScheme=1']
DARK = ['--force-dark-mode', '--blink-settings=preferredColorScheme=0']
FILES = ['assets/flow-light.svg', 'assets/flow-dark.svg',
         'assets/flow-light-narrow.svg', 'assets/flow-dark-narrow.svg']

PROBE = '''<!doctype html><meta charset="utf-8"><body style="margin:0">
<div id="svg"></div><pre id="out">pending</pre>
<script>
(async () => {
  const r = {};
  const svg = await (await fetch('/%(file)s')).text();
  document.getElementById('svg').innerHTML = svg;
  await new Promise(ok => setTimeout(ok, 300));
  const root = document.querySelector('#svg svg');
  const anims = root.getAnimations({subtree: true});
  r.animations = anims.length;
  r.running = anims.filter(a => a.playState === 'running').length;
  r.reduced = matchMedia('(prefers-reduced-motion: reduce)').matches;
  // The static frame: what shows with no animation.
  const shown = [...root.querySelectorAll('g.a')].filter(g => getComputedStyle(g).opacity === '1')
    .map(g => g.textContent);
  r.still = shown.join(' | ');
  r.title = root.querySelector('title').textContent;
  r.texts = root.querySelectorAll('text').length;
  document.getElementById('out').textContent = 'RESULT' + JSON.stringify(r) + 'END';
})().catch(e => { document.getElementById('out').textContent = 'RESULT' + JSON.stringify({error: String(e)}) + 'END'; });
</script>'''

SITE = '''<!doctype html><meta charset="utf-8"><body style="margin:0">
<iframe id="f" src="/index.html" style="width:%(w)dpx;height:800px;border:0"></iframe><pre id="out">pending</pre>
<script>
document.getElementById('f').addEventListener('load', async () => {
  const d = document.getElementById('f').contentDocument;
  const img = d.querySelector('.flow-anim img');
  img.loading = 'eager';
  img.scrollIntoView();
  for (let i = 0; i < 50 && !(img.complete && img.naturalWidth); i++) await new Promise(ok => setTimeout(ok, 100));
  const r = {src: img.currentSrc.replace(location.origin + '/', ''), width: img.naturalWidth, alt: img.alt.length};
  document.getElementById('out').textContent = 'RESULT' + JSON.stringify(r) + 'END';
});
</script>'''

FRAME = '''<!doctype html><meta charset="utf-8"><body style="margin:0;background:#808080">
<div id="svg"></div>
<script>
fetch('/%(file)s').then(r => r.text()).then(svg => {
  document.getElementById('svg').innerHTML = svg;
  for (const a of document.getAnimations()) { %(at)s }
});
</script>'''


def chrome():
    for name in ('google-chrome', 'google-chrome-stable', 'chromium', 'chromium-browser', 'chrome'):
        path = shutil.which(name)
        if path:
            return path
    return None


class Handler(http.server.SimpleHTTPRequestHandler):
    pages = {}

    def do_GET(self):
        page = self.pages.get(self.path.split('?')[0])
        if page is None:
            return super().do_GET()
        body = page.encode('utf-8')
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


def run(browser, url, flags=(), screenshot=None, size=(1200, 800)):
    profile = tempfile.mkdtemp(prefix='flow-e2e-')
    try:
        cmd = [browser, '--headless=new', '--disable-gpu', '--no-sandbox', '--no-first-run',
               '--hide-scrollbars', '--user-data-dir=' + profile, '--virtual-time-budget=8000',
               '--window-size=%d,%d' % size] + list(flags)
        cmd += ['--screenshot=' + screenshot] if screenshot else ['--dump-dom']
        out = subprocess.run(cmd + [url], capture_output=True, text=True, timeout=120)
        if screenshot:
            return None
        m = re.search(r'RESULT(.*?)END', out.stdout, re.S)
        if not m:
            raise AssertionError('no result from %s: %s %s' % (url, out.stdout[-500:], out.stderr[-500:]))
        return json.loads(m.group(1).replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>'))
    finally:
        shutil.rmtree(profile, ignore_errors=True)


def png_colours(path):
    """The number of distinct colours of an RGB(A) 8-bit PNG (sampled)."""
    with open(path, 'rb') as fh:
        data = fh.read()
    assert data[:8] == b'\x89PNG\r\n\x1a\n', path
    pos, idat, w, h, ctype = 8, b'', 0, 0, 0
    while pos < len(data):
        n, kind = struct.unpack('>I4s', data[pos:pos + 8])
        chunk = data[pos + 8:pos + 8 + n]
        if kind == b'IHDR':
            w, h, depth, ctype = struct.unpack('>IIBB', chunk[:10])
            assert depth == 8 and ctype in (2, 6), (depth, ctype)
        elif kind == b'IDAT':
            idat += chunk
        pos += 12 + n
    bpp = 4 if ctype == 6 else 3
    raw = zlib.decompress(idat)
    stride = w * bpp
    prev = bytearray(stride)
    colours = set()
    i = 0
    for y in range(h):
        ft = raw[i]
        line = bytearray(raw[i + 1:i + 1 + stride])
        i += 1 + stride
        for x in range(stride):
            a = line[x - bpp] if x >= bpp else 0
            b = prev[x]
            c = prev[x - bpp] if x >= bpp else 0
            if ft == 1:
                line[x] = (line[x] + a) & 255
            elif ft == 2:
                line[x] = (line[x] + b) & 255
            elif ft == 3:
                line[x] = (line[x] + (a + b) // 2) & 255
            elif ft == 4:
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                line[x] = (line[x] + (a if pa <= pb and pa <= pc else b if pb <= pc else c)) & 255
        prev = line
        if y % 8 == 0:
            for x in range(0, w, 8):
                colours.add(bytes(line[x * bpp:x * bpp + 3]))
    return len(colours)


def main():
    browser = chrome()
    if not browser:
        if os.environ.get('FLOW_E2E') == 'required':
            print('FAIL no Chrome, and FLOW_E2E=required')
            return 1
        print('skip: no Chrome found (FLOW_E2E=required makes this a failure)')
        return 0

    for i, rel in enumerate(FILES):
        Handler.pages['/__probe%d.html' % i] = PROBE % {'file': rel}
        Handler.pages['/__frame%d.html' % i] = FRAME % {'file': rel, 'at': 'a.pause(); a.currentTime = 13700;'}
        Handler.pages['/__still%d.html' % i] = FRAME % {'file': rel, 'at': 'a.cancel();'}
    Handler.pages['/__site_wide.html'] = SITE % {'w': 1200}
    Handler.pages['/__site_narrow.html'] = SITE % {'w': 400}

    srv = http.server.ThreadingHTTPServer(('127.0.0.1', 0), functools.partial(Handler, directory=ROOT))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    base = 'http://127.0.0.1:%d' % srv.server_address[1]
    fails = []
    runs = 0

    def check(name, ok, detail=''):
        nonlocal runs
        runs += 1
        print(('ok   ' if ok else 'FAIL ') + name + ('' if ok else ': ' + str(detail)))
        if not ok:
            fails.append(name)

    try:
        for i, rel in enumerate(FILES):
            r = run(browser, base + '/__probe%d.html' % i)
            check(rel + ': loads, real text', 'error' not in r and r['texts'] > 50, r)
            check(rel + ': animates', r.get('running', 0) > 50 and not r.get('reduced'), r)
            r = run(browser, base + '/__probe%d.html' % i, ['--force-prefers-reduced-motion'])
            check(rel + ': reduced motion: nothing runs', r.get('reduced') and r.get('running') == 0, r)
            still = r.get('still', '')
            check(rel + ': reduced motion: the static frame',
                  'agent → Lock client' in still and '✘ denied' in still and 'QUESTION' not in still, still)

        tmp = tempfile.mkdtemp(prefix='flow-shots-')
        try:
            for i, rel in enumerate(FILES):
                size = (1200, 680) if 'narrow' not in rel else (480, 1468)
                for kind in ('frame', 'still'):
                    shot = os.path.join(tmp, '%s%d.png' % (kind, i))
                    run(browser, base + '/__%s%d.html' % (kind, i), screenshot=shot, size=size)
                    n = png_colours(shot) if os.path.exists(shot) else 0
                    check('%s: renders (%s)' % (rel, kind), n > 20, '%d colours' % n)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

        for page, flags, want in (
                ('wide', LIGHT, 'assets/flow-light.svg'),
                ('wide', DARK, 'assets/flow-dark.svg'),
                ('narrow', LIGHT, 'assets/flow-light-narrow.svg'),
                ('narrow', DARK, 'assets/flow-dark-narrow.svg')):
            r = run(browser, base + '/__site_%s.html' % page, flags)
            check('index.html (%s, %s): %s' % (page, 'dark' if flags is DARK else 'light', want),
                  r.get('src') == want and r.get('width', 0) > 0 and r.get('alt', 0) > 200, r)
    finally:
        srv.shutdown()

    print()
    if fails:
        print('%d of %d failed' % (len(fails), runs))
        return 1
    print('all %d passed' % runs)
    return 0


if __name__ == '__main__':
    sys.exit(main())
