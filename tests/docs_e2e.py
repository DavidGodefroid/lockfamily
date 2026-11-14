"""End-to-end test of lockfamily.dev/docs in a real browser (#34).

    python3 tests/docs_e2e.py SITE

SITE is a site built by docs-site/build.py. Serves it on 127.0.0.1, then, in
headless Chrome, loads docs pages at 360, 768 and 1280 px wide, in the light
and the dark scheme, and checks:
  - no horizontal scroll;
  - the tabs, the sidebar (a drawer behind "Menu" on a phone) and, wide,
    the table of contents;
  - every code block has a Copy button, and clicking it says so;
  - the search finds a known page;
  - the theme button switches system -> light -> dark, and the choice
    survives a reload;
  - the page background is the theme's --paper token, and every visible
    text passes WCAG AA against its background;
  - every resource comes from the page's own origin.

Chrome is google-chrome, chromium… on the PATH, or $CHROME. Without one it
says so and exits 0, unless SITE_E2E=required (CI).
"""

import functools
import http.server
import os
import sys
import threading

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from flow_svg_e2e import DARK, LIGHT, Handler, chrome, run  # noqa: E402
from test_site import tokens  # noqa: E402

PAGE = '''<!doctype html><meta charset="utf-8"><body style="margin:0">
<iframe id="f" src="%(page)s" style="width:%(w)dpx;height:900px;border:0"></iframe><pre id="out">pending</pre>
<script>
const sleep = ms => new Promise(ok => setTimeout(ok, ms));
function lum(c) {
  const v = c.match(/[\\d.]+/g).slice(0, 3).map(x => +x / 255)
    .map(x => x <= 0.03928 ? x / 12.92 : Math.pow((x + 0.055) / 1.055, 2.4));
  return 0.2126 * v[0] + 0.7152 * v[1] + 0.0722 * v[2];
}
function alpha(c) { const m = c.match(/[\\d.]+/g); return m.length > 3 ? +m[3] : 1; }
function ratio(a, b) { const x = lum(a), y = lum(b); return (Math.max(x, y) + 0.05) / (Math.min(x, y) + 0.05); }
function shown(w, el) { return !!el && w.getComputedStyle(el).display !== 'none' && w.getComputedStyle(el).visibility !== 'hidden' && el.getClientRects().length > 0; }
function contrast(w, d) {
  const bad = []; let checked = 0;
  for (const el of d.body.querySelectorAll('*')) {
    if (el.closest('svg, img, picture, [hidden], dialog, .sidebar:not(.open)')) continue;
    if (![...el.childNodes].some(n => n.nodeType === 3 && n.textContent.trim())) continue;
    const st = w.getComputedStyle(el);
    if (st.visibility === 'hidden' || st.display === 'none' || el.getClientRects().length === 0) continue;
    if (el.classList.contains('skip-link') || el.classList.contains('heading-anchor')) continue;
    let bg = null;
    for (let p = el; p; p = p.parentElement) { const c = w.getComputedStyle(p).backgroundColor; if (alpha(c) > 0) { bg = c; break; } }
    bg = bg || 'rgb(255, 255, 255)';
    const size = parseFloat(st.fontSize), bold = parseInt(st.fontWeight, 10) >= 700;
    const need = (size >= 24 || (bold && size >= 18.66)) ? 3 : 4.5;
    const got = ratio(st.color, bg); checked++;
    if (got < need) bad.push(el.tagName + '.' + el.className + ' "' + el.textContent.trim().slice(0, 30) + '" ' + st.color + ' on ' + bg + ' = ' + got.toFixed(2));
  }
  return [checked, bad.slice(0, 10)];
}
let step = 0;
const r = {};
document.getElementById('f').addEventListener('load', async () => {
  const f = document.getElementById('f'), w = f.contentWindow, d = w.document;
  try {
    if (step === 1) {
      // After the reload: the theme chosen before is back.
      r.reloaded = d.documentElement.dataset.theme || 'system';
      r.reloadedBg = w.getComputedStyle(d.body).backgroundColor;
      w.localStorage.removeItem('lf-theme');
      document.getElementById('out').textContent = 'RESULT' + JSON.stringify(r) + 'END';
      return;
    }
    step = 1;
    await d.fonts.ready;
    r.overflow = d.documentElement.scrollWidth - d.documentElement.clientWidth;
    r.bg = w.getComputedStyle(d.body).backgroundColor;
    r.tabs = d.querySelectorAll('.tabs a').length;
    r.currentTab = (d.querySelector('.tabs a[aria-current="page"]') || {}).textContent;
    const side = d.getElementById('sidebar'), menu = d.querySelector('.menu-button');
    r.sidebarLinks = side.querySelectorAll('a').length;
    r.sidebarShown = shown(w, side);
    r.menuShown = shown(w, menu);
    if (r.menuShown) {
      menu.click(); await sleep(400);
      r.drawerOpens = shown(w, side) && menu.getAttribute('aria-expanded') === 'true';
      d.dispatchEvent(new w.KeyboardEvent('keydown', {key: 'Escape'})); await sleep(400);
      r.drawerCloses = !side.classList.contains('open');
    }
    r.toc = shown(w, d.querySelector('.toc'));
    r.pres = d.querySelectorAll('.doc pre').length;
    r.copies = d.querySelectorAll('.doc .copy').length;
    const copy = d.querySelector('.doc .copy');
    if (copy) { copy.click(); await sleep(1300); r.copied = copy.textContent; }
    [r.checked, r.contrast] = contrast(w, d);
    // Search.
    d.querySelector('.search-button').click();
    const input = d.getElementById('search-input');
    input.value = 'lox run'; input.dispatchEvent(new w.Event('input'));
    for (let i = 0; i < 50 && !d.querySelector('.search-results a'); i++) await sleep(100);
    r.dialog = d.querySelector('dialog.search').open;
    r.results = [...d.querySelectorAll('.search-results a')].map(a => new URL(a.href).pathname);
    d.querySelector('dialog.search').close();
    // Theme: system -> light -> dark.
    const t = d.querySelector('.theme-button');
    r.theme0 = t.textContent;
    t.click(); r.theme1 = d.documentElement.dataset.theme; r.bgLight = w.getComputedStyle(d.body).backgroundColor;
    t.click(); r.theme2 = d.documentElement.dataset.theme; r.bgDark = w.getComputedStyle(d.body).backgroundColor;
    r.stored = w.localStorage.getItem('lf-theme');
    r.foreign = w.performance.getEntriesByType('resource').map(e => e.name).filter(n => !n.startsWith(location.origin));
    w.location.reload();
  } catch (e) {
    document.getElementById('out').textContent = 'RESULT' + JSON.stringify({error: String(e) + ' ' + e.stack}) + 'END';
  }
});
</script>'''

SHOT = '''<!doctype html><meta charset="utf-8"><body style="margin:0;background:#808080">
<iframe src="%(page)s" style="width:%(w)dpx;height:1000px;border:0;display:block"></iframe>'''

PAGES = ['/docs/locks/locksql/usage/', '/docs/deck/', '/docs/lea/quick-start/']


def rgb(hexa):
    h = hexa.lstrip('#')
    return 'rgb(%d, %d, %d)' % (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


def main():
    if len(sys.argv) != 2:
        sys.exit('usage: docs_e2e.py SITE')
    site = os.path.abspath(sys.argv[1])
    browser = os.environ.get('CHROME') or chrome()
    if not browser:
        if os.environ.get('SITE_E2E') == 'required':
            sys.exit('docs e2e: no Chrome found (SITE_E2E=required)')
        print('docs e2e: skipped, no Chrome found')
        return
    t = tokens()
    paper = {'light': rgb(t['light']['paper']), 'dark': rgb(t['dark']['paper'])}

    class H(Handler):
        pages = {}
    for page in PAGES:
        for w in (360, 768, 1280):
            H.pages['/_e2e/%d%s' % (w, page)] = PAGE % {'page': page, 'w': w}
            H.pages['/_shot/%d%s' % (w, page)] = SHOT % {'page': page, 'w': w}
    srv = http.server.ThreadingHTTPServer(('127.0.0.1', 0), functools.partial(H, directory=site))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    base = 'http://127.0.0.1:%d' % srv.server_address[1]
    failures = []
    try:
        for page in PAGES:
            for scheme, flags in (('light', LIGHT), ('dark', DARK)):
                for w in (360, 768, 1280):
                    r = run(browser, '%s/_e2e/%d%s' % (base, w, page), flags, size=(w + 40, 1000))
                    where = '%s %s %dpx' % (page, scheme, w)
                    print(where, {k: r.get(k) for k in ('overflow', 'sidebarShown', 'menuShown', 'toc', 'copies', 'copied', 'checked', 'reloaded')})
                    def ok(cond, what):
                        if not cond:
                            failures.append('%s: %s (%s)' % (where, what, r))
                    if 'error' in r:
                        failures.append('%s: %s' % (where, r['error']))
                        continue
                    ok(r['overflow'] <= 0, 'horizontal scroll of %spx' % r['overflow'])
                    ok(r['bg'] == paper[scheme], 'background %s, not --paper %s' % (r['bg'], paper[scheme]))
                    ok(r['tabs'] >= 8, 'tabs')
                    ok(r['sidebarLinks'] >= 2, 'sidebar links')
                    if w < 900:
                        ok(r['menuShown'] and not r['sidebarShown'], 'the sidebar is a drawer behind Menu')
                        ok(r.get('drawerOpens') and r.get('drawerCloses'), 'the drawer opens and closes')
                    else:
                        ok(r['sidebarShown'] and not r['menuShown'], 'the sidebar shows')
                    ok(r['toc'] == (w >= 1200), 'table of contents shown only from 1200px')
                    ok(r['copies'] == r['pres'], 'a Copy button per code block')
                    if r['pres']:
                        ok(r.get('copied') in ('Copied', 'Ctrl+C'), 'the Copy button answers')
                    ok(not r['contrast'], 'contrast: %s' % r['contrast'])
                    ok(r['dialog'] and '/docs/hub/lox-run/' in r['results'][:3], 'search for "lox run" finds the lox run page first')
                    ok(r['theme0'] == 'system' and r['theme1'] == 'light' and r['theme2'] == 'dark', 'theme cycle')
                    ok(r['bgLight'] == paper['light'] and r['bgDark'] == paper['dark'], 'theme backgrounds')
                    ok(r['stored'] == 'dark' and r['reloaded'] == 'dark' and r['reloadedBg'] == paper['dark'], 'the theme survives a reload')
                    ok(not r['foreign'], 'third-party requests: %s' % r['foreign'])
                    shots = os.environ.get('DOCS_SHOTS')
                    if shots:
                        name = '%s-%s-%d.png' % (page.strip('/').replace('/', '_'), scheme, w)
                        # Through an iframe: headless Chrome has a minimum window width.
                        run(browser, '%s/_shot/%d%s' % (base, w, page), flags, screenshot=os.path.join(shots, name), size=(w, 1000))
    finally:
        srv.shutdown()
    for f in failures:
        print('FAIL', f, file=sys.stderr)
    if failures:
        sys.exit(1)
    print('docs e2e: ok')


if __name__ == '__main__':
    main()
