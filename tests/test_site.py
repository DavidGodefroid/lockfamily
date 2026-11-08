"""Unit tests of lockfamily.dev's identity (issue #17): tokens, contrast,
fonts, logos, no third-party request, and the docs that describe them.

    python3 -m unittest discover -s tests -p 'test_*.py'
"""

import os
import re
import sys
import unittest
import xml.etree.ElementTree as ET

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tools'))

import flow_svg  # noqa: E402
import logo_svg  # noqa: E402

LOGOS = ['mark', 'locksql', 'lockmq', 'lockfile', 'lockhttp', 'locklog', 'lockssh', 'lea']


def read(rel):
    with open(os.path.join(ROOT, rel), encoding='utf-8') as fh:
        return fh.read()


def tokens():
    """{'light': {name: value}, 'dark': {name: value}} from assets/tokens.css."""
    css = read('assets/tokens.css')
    dark_at = css.index('@media (prefers-color-scheme: dark)')
    decl = re.compile(r'--([a-z0-9-]+):\s*([^;]+);')
    light = dict(decl.findall(css[css.index(':root'):dark_at]))
    dark_block = css[dark_at:css.index('@media (min-width', dark_at)]
    dark = dict(light)
    dark.update(decl.findall(dark_block))
    return {'light': light, 'dark': dark}


def luminance(hex_):
    h = hex_.lstrip('#')
    rgb = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    lin = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in rgb]
    return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]


def contrast(a, b):
    x, y = sorted([luminance(a), luminance(b)])
    return (y + 0.05) / (x + 0.05)


class Tokens(unittest.TestCase):
    TEXT = ['ink', 'ink-2', 'sign', 'stamp', 'auto', 'asked', 'mask', 'agent']
    GROUNDS = ['paper', 'paper-2', 'card']

    def test_both_themes_designed(self):
        t = tokens()
        for name in ['paper', 'paper-2', 'card', 'ink', 'ink-2', 'rule'] + self.TEXT:
            self.assertRegex(t['light'][name], r'^#[0-9a-f]{6}$', name)
            self.assertNotEqual(t['light'][name], t['dark'][name], name + ': dark is its own value')

    def test_not_the_generic_palette(self):
        # The old navy and violet are gone, from the tokens and the page.
        css = read('assets/tokens.css') + read('assets/style.css') + read('index.html')
        for old in ('#0b1020', '#8b5cf6', '#c4b5fd', '--glow-alpha', 'class="glow"', 'shimmer'):
            self.assertNotIn(old, css)

    def test_wcag_aa_text(self):
        for theme, t in tokens().items():
            for fg in self.TEXT:
                for bg in self.GROUNDS:
                    self.assertGreaterEqual(contrast(t[fg], t[bg]), 4.5, (theme, fg, bg))
            for fg in ('term-text', 'term-dim'):
                self.assertGreaterEqual(contrast(t[fg], t['term-bg']), 4.5, (theme, fg))
            # Control borders (tabs, kbd): 3:1 for non-text UI.
            self.assertGreaterEqual(contrast(t['ink-2'], t['paper']), 3, theme)

    def test_documented(self):
        doc = read('docs/identity.md')
        for theme, t in tokens().items():
            for name, value in t.items():
                if value.startswith('#'):
                    self.assertIn('`--%s`' % name, doc, name)
                    self.assertIn(value, doc, '%s %s: %s' % (theme, name, value))
        for family in ('Zilla Slab', 'Source Serif 4', 'IBM Plex Mono'):
            self.assertIn(family, doc)

    def test_flow_svg_uses_the_tokens(self):
        for theme, t in tokens().items():
            th = flow_svg.THEMES[theme]
            self.assertEqual(th['bg'], t['paper'], theme)
            self.assertEqual(th['surface'], t['card'], theme)
            self.assertEqual(th['text'], t['ink'], theme)
            self.assertEqual(th['muted'], t['ink-2'], theme)
            self.assertEqual(th['deny'], t['stamp'], theme)
            self.assertEqual(th['req'], t['agent'], theme)
            self.assertEqual(th['hub'], t['mask'], theme)

    def test_logos_use_the_tokens(self):
        t = tokens()
        self.assertEqual(logo_svg.INK, (t['light']['ink'], t['dark']['ink']))
        self.assertEqual(logo_svg.CARD, (t['light']['card'], t['dark']['card']))
        self.assertEqual(logo_svg.INK2, (t['light']['ink-2'], t['dark']['ink-2']))


class Fonts(unittest.TestCase):
    def test_self_hosted_and_licensed(self):
        css = read('assets/tokens.css')
        faces = re.findall(r'@font-face\s*{([^}]*)}', css)
        self.assertGreaterEqual(len(faces), 3)
        families = set()
        for face in faces:
            fam = re.search(r'font-family:\s*"([^"]+)"', face).group(1)
            families.add(fam)
            url = re.search(r'url\("([^"]+)"\)', face).group(1)
            self.assertFalse(re.match(r'^[a-z]+:|^//', url), url)
            path = os.path.join(ROOT, 'assets', url)
            with open(path, 'rb') as fh:
                self.assertEqual(fh.read(4), b'wOF2', url)
            self.assertIn('font-display: swap', face)
        self.assertEqual(families, {'Zilla Slab', 'Source Serif 4', 'IBM Plex Mono'})
        for lic in ('OFL-zilla-slab.txt', 'OFL-source-serif-4.txt', 'OFL-ibm-plex-mono.txt'):
            self.assertIn('SIL Open Font License', read('assets/fonts/' + lic))

    def test_fonts_are_light(self):
        total = sum(os.path.getsize(os.path.join(ROOT, 'assets/fonts', n))
                    for n in os.listdir(os.path.join(ROOT, 'assets/fonts')) if n.endswith('.woff2'))
        self.assertLess(total, 200 * 1024)

    def test_roles(self):
        css = read('assets/tokens.css')
        self.assertRegex(css, r'--font-display:\s*"Zilla Slab"')
        self.assertRegex(css, r'--font-text:\s*"Source Serif 4"')
        self.assertRegex(css, r'--font-mono:\s*"IBM Plex Mono"')


class Logos(unittest.TestCase):
    def test_up_to_date(self):
        for rel, content in logo_svg.outputs().items():
            self.assertEqual(read(rel), content, '%s: run python3 tools/logo_svg.py' % rel)
        self.assertEqual(sorted(logo_svg.outputs()), sorted('assets/%s.svg' % n for n in LOGOS))

    def test_one_style(self):
        for name in LOGOS:
            svg = read('assets/%s.svg' % name)
            root = ET.fromstring(svg)
            self.assertEqual(root.get('viewBox'), '0 0 128 128', name)
            self.assertEqual(root.get('role'), 'img', name)
            self.assertIn('@media (prefers-color-scheme:dark)', svg, name)
            for bad in ('<script', 'href=', 'url(', 'Gradient', 'filter'):
                self.assertNotIn(bad, svg, name)
            colours = set(re.findall(r'#[0-9a-fA-F]{6}', svg))
            self.assertLessEqual(colours, set(logo_svg.INK + logo_svg.CARD + logo_svg.INK2), name)
            if name != 'lea':
                self.assertIn(logo_svg.SHACKLE, svg, name)


class Page(unittest.TestCase):
    def setUp(self):
        self.html = read('index.html')

    def test_no_third_party_request(self):
        # Everything the page loads is relative: links to other sites are
        # only <a href>, never a resource.
        for tag in re.findall(r'<(?:link|script|img|source|iframe)\b[^>]*>', self.html):
            if tag.startswith('<link') and 'rel="canonical"' in tag:
                continue
            for url in re.findall(r'(?:src|href|srcset)="([^"]+)"', tag):
                self.assertFalse(re.match(r'^[a-z]+:|^//', url), tag)
                self.assertTrue(os.path.exists(os.path.join(ROOT, url.split('#')[0])), url)
        for rel in ('assets/style.css', 'assets/tokens.css'):
            css = read(rel)
            self.assertNotIn('@import', css, rel)
            for url in re.findall(r'url\("?([^")]+)', css):
                self.assertFalse(re.match(r'^[a-z]+:|^//', url), (rel, url))

    def test_no_tracking(self):
        for w in ('analytics', 'gtag', 'googletagmanager', 'plausible', 'umami', 'fbq(', 'pixel'):
            self.assertNotIn(w, self.html.lower() + read('assets/main.js').lower(), w)

    def test_installer_unchanged(self):
        self.assertIn('curl -fsSL https://lockfamily.dev/install.sh | sh', self.html)
        self.assertTrue(os.path.exists(os.path.join(ROOT, 'install.sh')))

    def test_tokens_loaded_first(self):
        self.assertLess(self.html.index('href="assets/tokens.css"'), self.html.index('href="assets/style.css"'))

    def test_the_ticket_walkthrough(self):
        # A real ticket in the hero, and its life in the ledger, the hub at
        # the centre of its section.
        hero = self.html[self.html.index('class="hero'):self.html.index('class="locks-section')]
        for w in ('class="ticket"', 'class="stamp"', 'request, masked', '‹p***(4)›', 'signed decision'):
            self.assertIn(w, hero)
        principle = self.html[self.html.index('id="principle"'):self.html.index('id="fit"')]
        self.assertEqual(principle.count('<li>'), 7)
        for who in ('agent', 'lock', 'hub', 'you', 'audit'):
            self.assertIn('>%s</span>' % who, principle)
        hub = self.html[self.html.index('id="hub"'):self.html.index('id="quick-start"')]
        self.assertIn('class="board-hub"', hub)

    def test_install_box_in_hero_and_quick_start(self):
        # The brew copy-paste box: plain <pre> without JS, a Copy button
        # added by main.js, in the hero and in the quick start.
        hero = self.html[self.html.index('class="hero'):self.html.index('class="locks-section')]
        qs = self.html[self.html.index('id="quick-start"'):]
        block = ('brew trust davidgodefroid/tap\nbrew install davidgodefroid/tap/lockfamily</code></pre>')
        for part in (hero, qs):
            self.assertIn('data-copy', part)
            self.assertIn(block, part)
        self.assertNotIn('<button type="button" class="copy"', self.html)
        js = read('assets/main.js')
        for w in ('navigator.clipboard', 'execCommand("copy")', 'aria-live', '"Copied"', '".c, .prompt"'):
            self.assertIn(w, js)

    def test_every_lock_presented(self):
        locks = self.html[self.html.index('class="locks-section'):self.html.index('id="principle"')]
        fit = self.html[self.html.index('id="fit"'):self.html.index('id="hub"')]
        qs = self.html[self.html.index('id="quick-start"'):]
        footer = self.html[self.html.index('<footer'):]
        meta = re.search(r'<meta name="description" content="([^"]+)"', self.html).group(1)
        for name in ('locksql', 'lockmq', 'lockfile', 'lockhttp', 'locklog', 'lockssh'):
            self.assertIn('https://github.com/DavidGodefroid/%s"' % name, locks, name)
            self.assertIn('assets/%s.svg' % name, fit, name)
            self.assertIn('role="tab"', qs)
            self.assertIn('>%s</button>' % name, qs, name)
            self.assertIn('https://github.com/DavidGodefroid/%s"' % name, footer, name)
        for w in ('databases', 'RabbitMQ', 'files', 'HTTP', 'logs', 'servers'):
            self.assertIn(w, meta)

    def test_links_go_to_repos(self):
        # A Lock's product site is never a link target: its repository is.
        for site in ('locksql.com', 'lockmq.com', 'lockfile.pro', 'lockhttp.com', 'locklog.dev', 'leadeck.dev'):
            self.assertNotRegex(self.html, r'href="https?://(www\.)?%s' % re.escape(site), site)

    def test_agent_neutral(self):
        # No agent is the default: claude is one example among several.
        self.assertNotIn('asked by</dt><dd>claude', self.html)
        self.assertNotRegex(self.html, r'\n claude +<span class="c">')
        for w in ('Codex', 'Cursor', 'Gemini CLI', 'any MCP client'):
            self.assertIn(w, self.html)
        lead = re.search(r'<p class="lead">(.*?)</p>', self.html, re.S).group(1)
        self.assertLessEqual(len(re.findall(r'[.!?](\s|$)', re.sub(r'<[^>]+>', '', lead))), 2, lead)

    def test_no_emoji_icons(self):
        for e in ('🤖', '🔑', '🗄', '📨', '📄', '⚙︎'):
            self.assertNotIn(e, self.html)

    def test_theme_color(self):
        t = tokens()
        self.assertIn('<meta name="theme-color" content="%s" media="(prefers-color-scheme: light)">'
                      % t['light']['paper'], self.html)
        self.assertIn('<meta name="theme-color" content="%s" media="(prefers-color-scheme: dark)">'
                      % t['dark']['paper'], self.html)

    def test_docs(self):
        note = read('docs/design-note.md')
        for w in ('signed ticket', 'rejected', 'Industrial', 'Terminal-native', 'chosen'):
            self.assertIn(w, note)
        self.assertTrue(os.path.exists(os.path.join(ROOT, 'docs/mockups/directions.svg')))
        ET.fromstring(read('docs/mockups/directions.svg'))

    def test_no_version_placeholder(self):
        # Every version the page and the docs name is a real release
        # (vX.Y.Z), never a placeholder left for later (#26). An installer's
        # env var set to a pinned tag (LOCKSSH_VERSION=$V) is not one.
        for rel in ('index.html', 'README.md', 'docs/install.md', 'docs/lox.md'):
            text = read(rel)
            self.assertEqual(re.findall(r'[A-Z][A-Z0-9]*_VERSION\b(?!=)', text), [], rel)
            for m in re.finditer(r'\b(lox|lea|lockhub|locksql|lockmq|lockfile|lockhttp|locklog|lockssh|lockkit) v([0-9A-Z]\S*?)[,.;:<)]?(?=\s|<|$)', text):
                self.assertRegex(m.group(2), r'^[0-9]+\.[0-9]+\.[0-9]+$', '%s: %s' % (rel, m.group(0)))

    def test_lockssh_release_state(self):
        # lockssh is a lox lock type on lockhub's main branch (lockhub#169),
        # in no lockhub release yet (#27): the docs never say it is not a
        # type, and mark what is not released.
        lox = read('docs/lox.md')
        self.assertNotIn('lockssh is not a type yet', lox)
        self.assertIn('lockssh: unreleased', lox)
        for w in ('`lox withdraw INSTANCE/ID', '`lox tickets', '**A tab per lock**', '**Withdraw stuck tickets**'):
            self.assertIn(w, lox)
        self.assertIn('no released hub knows lockssh yet', self.html)
        self.assertIn('no released hub knows lockssh yet', read('README.md'))
        self.assertIn('lockssh', read('install.sh'))
        for theme in ('light', 'dark', 'light-narrow', 'dark-narrow'):
            self.assertIn('lockhttp · locklog · lockssh', read('assets/flow-%s.svg' % theme), theme)


if __name__ == '__main__':
    unittest.main()
