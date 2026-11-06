"""End-to-end test of lockfamily.dev's identity in a real browser (#17).

    python3 tests/site_e2e.py

Serves the repository on 127.0.0.1, then, in headless Chrome, loads
index.html at 360, 768 and 1280 px wide, in the light and the dark scheme,
and checks:
  - no horizontal scroll;
  - the three self-hosted faces load, and the headings use the display face;
  - every resource comes from the page's own origin (no third party);
  - the page background is the theme's --paper token;
  - every visible text passes WCAG AA against its effective background
    (4.5:1, 3:1 for large text);
  - with reduced motion, nothing animates.

Without Chrome it says so and exits 0, unless SITE_E2E=required (CI).
"""

import functools
import http.server
import os
import sys
import threading

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from flow_svg_e2e import DARK, LIGHT, ROOT, Handler, chrome, run  # noqa: E402
from test_site import tokens  # noqa: E402

PAGE = '''<!doctype html><meta charset="utf-8"><body style="margin:0">
<iframe id="f" src="/index.html" style="width:%(w)dpx;height:900px;border:0"></iframe><pre id="out">pending</pre>
<script>
function lum(c) {
  const v = c.match(/[\\d.]+/g).slice(0, 3).map(x => +x / 255)
    .map(x => x <= 0.03928 ? x / 12.92 : Math.pow((x + 0.055) / 1.055, 2.4));
  return 0.2126 * v[0] + 0.7152 * v[1] + 0.0722 * v[2];
}
function alpha(c) { const m = c.match(/[\\d.]+/g); return m.length > 3 ? +m[3] : 1; }
function ratio(a, b) { const x = lum(a), y = lum(b); return (Math.max(x, y) + 0.05) / (Math.min(x, y) + 0.05); }
document.getElementById('f').addEventListener('load', async () => {
  const w = document.getElementById('f').contentWindow, d = w.document;
  await d.fonts.ready;
  await Promise.all([...d.fonts].map(f => f.load().catch(() => null)));
  const r = {};
  r.overflow = d.documentElement.scrollWidth - d.documentElement.clientWidth;
  r.loaded = [...d.fonts].filter(f => f.status === 'loaded').map(f => f.family.replace(/"/g, '') + ' ' + f.weight + ' ' + f.style);
  r.h1 = w.getComputedStyle(d.querySelector('h1')).fontFamily;
  r.body = w.getComputedStyle(d.body).fontFamily;
  r.bg = w.getComputedStyle(d.body).backgroundColor;
  r.foreign = w.performance.getEntriesByType('resource').map(e => e.name).filter(n => !n.startsWith(location.origin));
  r.running = d.getAnimations().filter(a => a.playState === 'running').length;
  const bad = [];
  let checked = 0;
  for (const el of d.body.querySelectorAll('*')) {
    if (el.closest('svg, img, picture, [hidden]')) continue;
    const own = [...el.childNodes].some(n => n.nodeType === 3 && n.textContent.trim());
    if (!own) continue;
    const st = w.getComputedStyle(el);
    if (st.visibility === 'hidden' || st.display === 'none' || el.getClientRects().length === 0) continue;
    if (el.classList.contains('skip-link')) continue;
    let bg = null;
    for (let p = el; p; p = p.parentElement) {
      const c = w.getComputedStyle(p).backgroundColor;
      if (alpha(c) > 0) { bg = c; break; }
    }
    bg = bg || 'rgb(255, 255, 255)';
    const size = parseFloat(st.fontSize), bold = parseInt(st.fontWeight, 10) >= 700;
    const need = (size >= 24 || (bold && size >= 18.66)) ? 3 : 4.5;
    const got = ratio(st.color, bg);
    checked++;
    if (got < need) bad.push(el.tagName + '.' + el.className + ' "' + el.textContent.trim().slice(0, 30) + '" ' + st.color + ' on ' + bg + ' = ' + got.toFixed(2));
  }
  r.checked = checked;
  r.contrast = bad.slice(0, 10);
  document.getElementById('out').textContent = 'RESULT' + JSON.stringify(r) + 'END';
});
</script>'''

FACES = ['Zilla Slab 700 normal', 'Source Serif 4 400 normal', 'IBM Plex Mono 400 normal']


def rgb(hex_):
    h = hex_.lstrip('#')
    return 'rgb(%d, %d, %d)' % tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def main():
    browser = chrome()
    if not browser:
        if os.environ.get('SITE_E2E') == 'required':
            print('FAIL no Chrome, and SITE_E2E=required')
            return 1
        print('skip: no Chrome found (SITE_E2E=required makes this a failure)')
        return 0

    widths = (360, 768, 1280)
    for w in widths:
        Handler.pages['/__site%d.html' % w] = PAGE % {'w': w}
    srv = http.server.ThreadingHTTPServer(('127.0.0.1', 0), functools.partial(Handler, directory=ROOT))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    base = 'http://127.0.0.1:%d' % srv.server_address[1]
    t = tokens()
    fails, runs = [], 0

    def check(name, ok, detail=''):
        nonlocal runs
        runs += 1
        print(('ok   ' if ok else 'FAIL ') + name + ('' if ok else ': ' + str(detail)))
        if not ok:
            fails.append(name)

    try:
        for scheme, flags in (('light', LIGHT), ('dark', DARK)):
            for w in widths:
                r = run(browser, base + '/__site%d.html' % w, flags + ['--force-prefers-reduced-motion'])
                tag = '%s, %dpx' % (scheme, w)
                check(tag + ': no horizontal scroll', r.get('overflow', 1) <= 0, r.get('overflow'))
                check(tag + ': self-hosted faces loaded', all(f in r.get('loaded', []) for f in FACES), r.get('loaded'))
                check(tag + ': display face on headings', r.get('h1', '').startswith('"Zilla Slab"'), r.get('h1'))
                check(tag + ': text face on body', r.get('body', '').startswith('"Source Serif 4"'), r.get('body'))
                check(tag + ': no third-party request', r.get('foreign') == [], r.get('foreign'))
                check(tag + ': --paper background', r.get('bg') == rgb(t[scheme]['paper']), r.get('bg'))
                check(tag + ': WCAG AA contrast (%s texts)' % r.get('checked'),
                      r.get('checked', 0) > 100 and r.get('contrast') == [], r.get('contrast'))
                check(tag + ': reduced motion, nothing runs', r.get('running') == 0, r.get('running'))
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
