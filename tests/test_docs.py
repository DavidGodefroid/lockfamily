"""Unit tests of the docs site generator, docs-site/build.py (#34).

    python3 -m unittest discover -s tests -p 'test_docs.py'

Offline: the other repos are small fixtures written to a temporary folder,
read with --offline. Needs markdown-it-py (docs-site/requirements.txt).
"""

import json
import os
import re
import shutil
import sys
import tempfile
import textwrap
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'docs-site'))

import build  # noqa: E402

PNG = b'\x89PNG\r\n\x1a\n' + b'\0' * 16

FIXTURES = {
    'alpha': {
        'README.md': '''\
            <p align="center">
              <picture>
                <source media="(prefers-color-scheme: dark)" srcset="docs/assets/banner-dark.svg">
                <img alt="alpha" src="docs/assets/banner-light.svg" width="600">
              </picture>
            </p>

            <p align="center">
              <a href="https://github.com/x/y/actions"><img alt="CI" src="https://github.com/x/y/actions/workflows/ci.yml/badge.svg"></a>
              <img alt="release" src="https://img.shields.io/github/v/release/x/y">
            </p>

            <p align="center">
              <b>The alpha Lock: reads flow, writes wait.</b>
            </p>

            <p align="center">
              <a href="#quick-start">Quick start</a> ·
              <a href="#how-it-works">How it works</a>
            </p>

            ---

            alpha keeps the credentials.

            ## Why alpha

            Because.

            ## Quick start

            ```sh
            alpha init
            ```

            See [usage](docs/usage.md#flags), [config](docs/config.md),
            [the hub](https://github.com/DavidGodefroid/beta/blob/main/README.md#approvals)
            and [the licence](LICENSE).

            ![demo](docs/assets/demo.png)

            ## Highlights

            - **Masked by default.** Every PII column comes back masked.
            - **Signed.** Every decision is signed.
              On two lines.

            ## How it works

            ### The console

            It runs outside the agent.

            ### The audit

            Hash-chained.

            ## Contributing

            Not a page.
            ''',
        'docs/usage.md': '''\
            # Usage

            > [!WARNING]
            > Writes wait for you.

            ## Flags

            | Flag | Meaning |
            |---|---|
            | `--x` | the x |

            ## Flags

            Again, a second heading with the same text.

            ## What's new? (v1.2)

            Back to [the top](#usage) or [why](../README.md#why-alpha).
            ''',
        'docs/config.md': '# Configuration\n\nSee [flags](usage.md#flags-1).\n',
        'docs/internal.md': '# Internal\n',
        'docs/assets/demo.png': PNG,
        'CHANGELOG.md': '# Changelog\n\n## v1.0.0\n\nFirst.\n',
    },
    'beta': {
        'README.md': '# beta\n\n## Approvals\n\nApprove in `lox run`.\n\n## Other\n\nSee [alpha](https://github.com/DavidGodefroid/alpha/blob/HEAD/docs/usage.md).\n',
    },
}

NAV = '''
[sources]
skip = ["alpha:docs/internal.md", "lockfamily:README.md", "lockfamily:docs/install.md",
        "lockfamily:docs/lox.md", "lockfamily:docs/managed.md", "lockfamily:docs/identity.md",
        "lockfamily:docs/design-note.md"]

[[tab]]
id = ""
title = "Get started"
  [[tab.group]]
  title = "Get started"
  pages = [
    { slug = "", src = "alpha:README.md", intro = true, sections = ["Why alpha", "Quick start"], title = "alpha", nav = "Overview" },
    { slug = "highlights", src = "alpha:README.md", sections = ["Highlights"], bullets = ["Highlights"] },
    { slug = "console", src = "alpha:README.md", sections = ["How it works > The console"] },
    { slug = "how", src = "alpha:README.md", sections = ["How it works"] },
  ]

[[tab]]
id = "ref"
title = "Reference"
  [[tab.group]]
  title = "alpha"
  pages = [
    { slug = "usage", src = "alpha:docs/usage.md", nav = "Usage" },
    { slug = "config", src = "alpha:docs/config.md" },
    { slug = "changelog", src = "alpha:CHANGELOG.md", title = "alpha changelog" },
  ]
  [[tab.group]]
  title = "beta"
  pages = [
    { slug = "beta", src = "beta:README.md", sections = ["Approvals"] },
  ]
'''


def write_fixtures(cache):
    for repo, files in FIXTURES.items():
        for rel, content in files.items():
            path = os.path.join(cache, repo, *rel.split('/'))
            os.makedirs(os.path.dirname(path), exist_ok=True)
            if isinstance(content, bytes):
                with open(path, 'wb') as fh:
                    fh.write(content)
            else:
                with open(path, 'w', encoding='utf-8') as fh:
                    fh.write(textwrap.dedent(content))


class Site(unittest.TestCase):
    """One build of the fixture site, shared by the tests below."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp()
        cls.cache = os.path.join(cls.tmp, 'cache')
        cls.out = os.path.join(cls.tmp, 'site')
        write_fixtures(cls.cache)
        cls.nav = os.path.join(cls.tmp, 'nav.toml')
        with open(cls.nav, 'w', encoding='utf-8') as fh:
            fh.write(NAV)
        cls.pages = build.build(cls.out, cls.cache, True, cls.nav)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def page(self, url):
        with open(os.path.join(self.out, url.strip('/'), 'index.html'), encoding='utf-8') as fh:
            return fh.read()

    def body(self, url):
        text = self.page(url)
        return text[text.index('<article'):text.index('</article>')]


class Markdown(unittest.TestCase):
    def test_heading_ids_like_github(self):
        body, heads = build.render("# Usage\n\n## What's new? (v1.2)\n\n## `lox run`'s screen\n\n## Flags\n\n## Flags\n")
        self.assertEqual([h[1] for h in heads], ['usage', 'whats-new-v12', 'lox-runs-screen', 'flags', 'flags-1'])

    def test_made_headings_never_shift_real_ids(self):
        md = '## Notes\n\n- **Notes.** a bullet named like the section\n\n## Notes\n'
        _, heads = build.render(md, ['Notes'])
        # The two real "Notes" keep notes and notes-1, as on GitHub.
        self.assertEqual([h[1] for h in heads], ['notes', 'notes-2', 'notes-1'])

    def test_callouts(self):
        for kind, title in build.CALLOUTS.items():
            body, _ = build.render('> [!%s]\n> Mind the gap.\n' % kind)
            self.assertIn('<div class="callout callout-%s" role="note">' % kind.lower(), body)
            self.assertIn('<p class="callout-title">%s</p>' % title, body)
            self.assertIn('Mind the gap.', body)
            self.assertNotIn('[!', body)
            self.assertNotIn('blockquote', body)

    def test_plain_blockquote_stays(self):
        body, _ = build.render('> Just a quote.\n')
        self.assertIn('<blockquote>', body)

    def test_tables_are_wrapped(self):
        body, _ = build.render('| a | b |\n|---|---|\n| 1 | 2 |\n')
        self.assertIn('<div class="table-wrap">\n<table>', body)
        self.assertIn('<td>1</td>', body)

    def test_code_blocks(self):
        body, _ = build.render('```sh\nlox run --auto <x>\n```\n\nand `inline`\n')
        self.assertIn('<pre><code class="language-sh">lox run --auto &lt;x&gt;\n</code></pre>', body)
        self.assertIn('<code>inline</code>', body)

    def test_nested_lists_with_two_spaces(self):
        body, _ = build.render('- one\n  - two\n')
        self.assertEqual(body.count('<ul>'), 2)

    def test_bullets_become_headings(self):
        md = build.bullets('## Highlights\n\n- **Masked.** Text.\n  More.\n- **Signed** Text.\n\n## Other\n\n- **Kept.** as is\n', ['Highlights'])
        self.assertIn('### %sMasked\n\nText.\nMore.' % build.MADE, md)
        self.assertIn('### %sSigned' % build.MADE, md)
        self.assertIn('- **Kept.** as is', md)


class Split(Site):
    def test_intro_is_cleaned(self):
        b = self.body('/docs/')
        self.assertIn('<p class="lead"><b>The alpha Lock: reads flow, writes wait.</b></p>', b)
        self.assertNotIn('banner', b)
        self.assertNotIn('badge', b)
        self.assertNotIn('shields.io', b)
        self.assertNotIn('<hr', b)
        self.assertNotIn('>Quick start</a> ·', b)
        self.assertIn('alpha keeps the credentials.', b)

    def test_sections_in_order(self):
        b = self.body('/docs/')
        self.assertLess(b.index('id="why-alpha"'), b.index('id="quick-start"'))
        self.assertNotIn('Highlights', b)
        self.assertNotIn('Contributing', b)

    def test_one_section_is_the_title(self):
        b = self.body('/docs/highlights/')
        self.assertIn('<h1 id="highlights">Highlights</h1>', b)
        self.assertIn('<h2 id="masked-by-default">Masked by default', b)
        self.assertIn('On two lines.', b)

    def test_h3_leaves_its_h2(self):
        self.assertIn('<h1 id="the-console">The console</h1>', self.body('/docs/console/'))
        how = self.body('/docs/how/')
        self.assertNotIn('The console', how)
        self.assertIn('Hash-chained.', how)
        # The H3 left alone becomes an h2 of its page.
        self.assertIn('<h2 id="the-audit">', how)

    def test_whole_file(self):
        b = self.body('/docs/ref/usage/')
        self.assertIn('<h1 id="usage">Usage</h1>', b)
        self.assertIn('callout-warning', b)

    def test_missing_section_fails_loudly(self):
        nav = os.path.join(self.tmp, 'bad.toml')
        with open(nav, 'w', encoding='utf-8') as fh:
            fh.write(NAV.replace('"Why alpha"', '"Why not"'))
        with self.assertRaises(SystemExit) as e:
            build.build(os.path.join(self.tmp, 'bad'), self.cache, True, nav)
        self.assertIn('has no section "Why not"', str(e.exception))


class Links(Site):
    def test_relative_link_to_a_page_and_anchor(self):
        b = self.body('/docs/')
        self.assertIn('href="/docs/ref/usage/#flags"', b)
        self.assertIn('href="/docs/ref/config/"', b)

    def test_anchor_of_a_second_heading(self):
        self.assertIn('href="/docs/ref/usage/#flags-1"', self.body('/docs/ref/config/'))

    def test_cross_repo_github_url_to_a_page(self):
        self.assertIn('href="/docs/ref/beta/#approvals"', self.body('/docs/'))

    def test_github_fallback(self):
        b = self.body('/docs/')
        self.assertIn('href="https://github.com/DavidGodefroid/alpha/blob/HEAD/LICENSE"', b)

    def test_anchor_on_the_same_page_and_up(self):
        b = self.body('/docs/ref/usage/')
        self.assertIn('href="#usage"', b)
        self.assertIn('href="/docs/#why-alpha"', b)

    def test_section_left_out_goes_to_github(self):
        nav = os.path.join(self.tmp, 'out.toml')
        with open(nav, 'w', encoding='utf-8') as fh:
            fh.write(NAV.replace('{ slug = "beta", src = "beta:README.md", sections = ["Approvals"] },',
                                 '{ slug = "beta", src = "beta:README.md", sections = ["Other"] },'))
        build.build(os.path.join(self.tmp, 'out'), self.cache, True, nav)
        with open(os.path.join(self.tmp, 'out', 'docs', 'index.html'), encoding='utf-8') as fh:
            self.assertIn('href="https://github.com/DavidGodefroid/beta/blob/HEAD/README.md#approvals"', fh.read())

    def test_images_are_copied(self):
        self.assertIn('src="/docs/_media/alpha/docs/assets/demo.png"', self.body('/docs/'))
        self.assertTrue(os.path.isfile(os.path.join(self.out, 'docs', '_media', 'alpha', 'docs', 'assets', 'demo.png')))

    def test_remote_images_become_links(self):
        body = build.Links([], build.Sources([], self.cache, True), self.out)
        page = build.Page(tab={'id': ''}, group='', slug='', repo='alpha', path='README.md',
                          body='<p><img alt="chart" src="https://example.com/c.png"> <img src="gone.png" alt="x"></p>')
        body.rewrite(page)
        self.assertIn('<a href="https://example.com/c.png">chart</a>', page.body)
        self.assertNotIn('<img', page.body)

    def test_check_passes(self):
        self.assertTrue(build.check(self.out))

    def test_check_catches_breakage(self):
        bad = os.path.join(self.tmp, 'broken')
        shutil.copytree(self.out, bad)
        with open(os.path.join(bad, 'docs', 'x.html'), 'w', encoding='utf-8') as fh:
            fh.write('<a href="/docs/nope/">a</a><a href="/docs/#nope">b</a><script src="https://cdn.example/x.js"></script>')
        self.assertFalse(build.check(bad))


class Nav(Site):
    def test_tabs_and_sidebar(self):
        p = self.page('/docs/ref/usage/')
        self.assertIn('<li><a href="/docs/ref/usage/" aria-current="page">Reference</a></li>', p)
        self.assertIn('<li><a href="/docs/ref/usage/" aria-current="page">Usage</a></li>', p)
        self.assertIn('<summary>beta</summary>', p)

    def test_prev_next_within_a_tab(self):
        def pn(url):
            p = self.page(url)
            return (re.search(r'class="prev" href="([^"]+)"', p), re.search(r'class="next" href="([^"]+)"', p))
        prev, nxt = pn('/docs/')
        self.assertIsNone(prev)
        self.assertEqual(nxt.group(1), '/docs/highlights/')
        prev, nxt = pn('/docs/how/')
        self.assertEqual(prev.group(1), '/docs/console/')
        self.assertIsNone(nxt)  # the end of the tab, not the next tab
        prev, nxt = pn('/docs/ref/changelog/')
        self.assertEqual((prev.group(1), nxt.group(1)), ('/docs/ref/config/', '/docs/ref/beta/'))

    def test_source_and_edit_links(self):
        p = self.page('/docs/ref/usage/')
        self.assertIn('href="https://github.com/DavidGodefroid/alpha/blob/HEAD/docs/usage.md"', p)
        self.assertIn('href="https://github.com/DavidGodefroid/alpha/edit/HEAD/docs/usage.md"', p)
        self.assertIn('href="https://github.com/DavidGodefroid/alpha/blob/HEAD/README.md#highlights"', self.page('/docs/highlights/'))

    def test_toc(self):
        p = self.page('/docs/ref/usage/')
        self.assertIn('<li class="toc-2"><a href="#flags-1">Flags</a></li>', p)

    def test_two_pages_at_one_url(self):
        nav = os.path.join(self.tmp, 'dup.toml')
        with open(nav, 'w', encoding='utf-8') as fh:
            fh.write(NAV.replace('slug = "config"', 'slug = "usage"'))
        with self.assertRaises(SystemExit):
            build.load_nav(nav)

    def test_a_doc_with_no_page_fails(self):
        nav = os.path.join(self.tmp, 'cover.toml')
        with open(nav, 'w', encoding='utf-8') as fh:
            fh.write(NAV.replace('"alpha:docs/internal.md", ', ''))
        with self.assertRaises(SystemExit) as e:
            build.build(os.path.join(self.tmp, 'cover'), self.cache, True, nav)
        self.assertIn('alpha:docs/internal.md', str(e.exception))

    def test_sitemap_and_404(self):
        with open(os.path.join(self.out, 'sitemap.xml'), encoding='utf-8') as fh:
            sm = fh.read()
        self.assertIn('<loc>https://lockfamily.dev/docs/ref/usage/</loc>', sm)
        self.assertEqual(sm.count('<loc>'), len(self.pages) + 1)
        self.assertTrue(os.path.isfile(os.path.join(self.out, '404.html')))


class Search(Site):
    def test_index(self):
        with open(os.path.join(self.out, 'docs', '_assets', 'search.json'), encoding='utf-8') as fh:
            idx = json.load(fh)
        by_url = {e['u']: e for e in idx}
        self.assertIn('/docs/ref/usage/#flags', by_url)
        e = by_url['/docs/ref/beta/']
        self.assertEqual((e['t'], e['b']), ('Approvals', 'Reference'))
        self.assertIn('Approve in lox run.', e['x'])
        self.assertTrue(all(set(e) == {'u', 't', 'h', 'b', 'x'} for e in idx))
        self.assertTrue(all('<' not in e['x'] for e in idx))


class Home(Site):
    def test_home_copied_as_is(self):
        for f in build.HOME_FILES:
            with open(os.path.join(ROOT, f), 'rb') as a, open(os.path.join(self.out, f), 'rb') as b:
                self.assertEqual(a.read(), b.read(), f)
        self.assertTrue(os.path.isfile(os.path.join(self.out, 'assets', 'tokens.css')))

    def test_home_links_to_the_docs(self):
        with open(os.path.join(ROOT, 'index.html'), encoding='utf-8') as fh:
            self.assertRegex(fh.read(), r'<a [^>]*href="/docs/"')


class Theme(unittest.TestCase):
    def test_tokens_taken_from_tokens_css(self):
        with open(os.path.join(ROOT, 'assets', 'tokens.css'), encoding='utf-8') as fh:
            css = fh.read()
        out = build.theme_css()
        light = dict(re.findall(r'(--[\w-]+):\s*([^;]+);', out.split(':root[data-theme="dark"]')[0]))
        dark = dict(re.findall(r'(--[\w-]+):\s*([^;]+);', out.split(':root[data-theme="dark"]')[1]))
        root = dict(re.findall(r'(--[\w-]+):\s*([^;]+);', re.search(r'^:root \{(.*?)^\}', css, re.S | re.M).group(1)))
        media = re.search(r'@media \(prefers-color-scheme: dark\) \{\s*:root \{(.*?)\}', css, re.S).group(1)
        self.assertEqual(dark, dict(re.findall(r'(--[\w-]+):\s*([^;]+);', media)))
        self.assertIn('--paper', dark)
        for name in dark:
            self.assertEqual(light[name], root[name], name)
        self.assertIn('color-scheme: light;', out)


if __name__ == '__main__':
    unittest.main()
