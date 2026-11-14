#!/usr/bin/env python3
"""Build lockfamily.dev, its docs included (#34).

    python3 docs-site/build.py [--out _site] [--sources DIR] [--offline]
    python3 docs-site/build.py --check _site

The docs are not copied by hand: every page comes from a Markdown file of
one of the family's repositories (a whole file, or sections of a README),
fetched from its default branch at build time. docs-site/nav.toml says which
file, or which sections, make which page, in which tab. Only the pages no
repo has are written here, in docs-site/pages/.

Links are rewritten: a link to a file (or a heading) that has a page goes to
that page, anything else goes to the file on GitHub. Images are copied next
to the pages: the site makes no third-party request.

The output is the whole site: the home page and its assets as they are in
this repo, and the docs under docs/. --check walks a built site and fails
on a local link, image or #fragment that does not resolve, or on a
third-party resource.
"""

import argparse
import dataclasses
import html
import io
import json
import os
import posixpath
import re
import shutil
import sys
import tarfile
import tomllib
import urllib.parse
import urllib.request

from markdown_it import MarkdownIt

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OWNER = 'DavidGodefroid'
BASE = '/docs/'
SITE = 'https://lockfamily.dev'

# The home page and what it needs, copied as they are.
HOME_FILES = ['index.html', 'install.sh', 'CNAME']
HOME_DIRS = ['assets']

MEDIA = ('.svg', '.png', '.jpg', '.jpeg', '.gif', '.webp')
# A word joiner: marks the headings made from bold bullets (see bullets()).
MADE = '⁠'
CALLOUTS = {'NOTE': 'Note', 'TIP': 'Tip', 'IMPORTANT': 'Important',
            'WARNING': 'Warning', 'CAUTION': 'Caution'}


# ---------------------------------------------------------------- sources

def fetch(repo, cache):
    """Download the Markdown files and images of repo's default branch."""
    dest = os.path.join(cache, repo)
    if os.path.isdir(dest):
        return dest
    url = 'https://codeload.github.com/%s/%s/tar.gz/HEAD' % (OWNER, repo)
    with urllib.request.urlopen(url, timeout=60) as resp:
        data = resp.read()
    tmp = dest + '.tmp'
    shutil.rmtree(tmp, ignore_errors=True)
    with tarfile.open(fileobj=io.BytesIO(data), mode='r:gz') as tar:
        for m in tar.getmembers():
            name = m.name.split('/', 1)[1] if '/' in m.name else ''
            if not m.isfile() or not name or name.startswith('.') or '/.' in name:
                continue
            if not name.lower().endswith(('.md',) + MEDIA):
                continue
            path = os.path.join(tmp, *name.split('/'))
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, 'wb') as fh:
                fh.write(tar.extractfile(m).read())
    os.replace(tmp, dest)
    return dest


class Sources:
    """Where each repo's files are: lockfamily is this checkout."""

    def __init__(self, repos, cache, offline):
        self.dirs = {'lockfamily': ROOT}
        for r in repos:
            if r == 'lockfamily':
                continue
            d = os.path.join(cache, r)
            if not os.path.isdir(d):
                if offline:
                    raise SystemExit('no sources for %s in %s (--offline)' % (r, cache))
                d = fetch(r, cache)
            self.dirs[r] = d

    def path(self, repo, rel):
        return os.path.join(self.dirs[repo], *rel.split('/'))

    def read(self, repo, rel):
        with open(self.path(repo, rel), encoding='utf-8') as fh:
            return fh.read()

    def exists(self, repo, rel):
        return repo in self.dirs and os.path.isfile(self.path(repo, rel))


# ---------------------------------------------------------------- Markdown

def slugify(text):
    """GitHub's heading anchors: lower case, punctuation dropped, spaces to -."""
    s = text.strip().lower()
    s = re.sub(r'[^\w\- ]', '', s)
    return s.replace(' ', '-')


def plain(tokens):
    """The text of an inline token's children."""
    out = []
    for t in tokens or []:
        if t.type in ('text', 'code_inline'):
            out.append(t.content)
        elif t.type == 'html_inline':
            continue
        elif t.children:
            out.append(plain(t.children))
    return ''.join(out)


def bullets(md, sections):
    """Turn top-level "- **Label.** text" bullets into "### Label" headings,
    in the given H2 sections only, so that they get a table of contents."""
    if not sections:
        return md
    want = {s.lower() for s in sections}
    out, fence, inside, item = [], False, False, False
    for line in md.split('\n'):
        if line.lstrip().startswith(('```', '~~~')):
            fence = not fence
        if not fence and line.startswith('## '):
            inside = line[3:].strip().lower() in want
            item = False
        m = re.match(r'- \*\*(.+?)\.?\*\* ?(.*)$', line) if inside and not fence else None
        if m:
            out += ['### ' + MADE + m.group(1).rstrip('.'), '', m.group(2)]
            item = True
            continue
        if item and line.startswith('  '):
            out.append(line[2:])
            continue
        if item and line.strip() and not line.startswith('  '):
            item = False
        out.append(line)
    return '\n'.join(out)


def markdown():
    md = MarkdownIt('commonmark', {'html': True}).enable(['table', 'strikethrough'])

    def table_open(self, tokens, idx, options, env):
        return '<div class="table-wrap">\n<table>\n'

    def table_close(self, tokens, idx, options, env):
        return '</table>\n</div>\n'

    md.add_render_rule('table_open', table_open)
    md.add_render_rule('table_close', table_close)
    return md


MD = markdown()


def callouts(tokens):
    """GitHub's alerts: > [!NOTE] … become <div class="callout note">."""
    stack = []
    for i, t in enumerate(tokens):
        if t.type == 'blockquote_open':
            kind = None
            if i + 2 < len(tokens) and tokens[i + 1].type == 'paragraph_open':
                inline = tokens[i + 2]
                m = re.match(r'\[!(%s)\]' % '|'.join(CALLOUTS), inline.content)
                if m:
                    kind = m.group(1)
                    inline.content = inline.content[m.end():].lstrip()
                    kids = inline.children or []
                    if kids and kids[0].type == 'text':
                        kids[0].content = re.sub(r'^\[!\w+\]\s*', '', kids[0].content)
                        if not kids[0].content:
                            kids.pop(0)
                            if kids and kids[0].type in ('softbreak', 'hardbreak'):
                                kids.pop(0)
            stack.append(kind)
            if kind:
                t.tag = 'div'
                t.attrSet('class', 'callout callout-' + kind.lower())
                t.attrSet('role', 'note')
        elif t.type == 'blockquote_close':
            kind = stack.pop() if stack else None
            if kind:
                t.tag = 'div'


def render(text, bullet_sections=()):
    """Markdown to HTML, with GitHub's heading ids. Returns (html, headings)."""
    text = bullets(text, bullet_sections)
    tokens = MD.parse(text)
    callouts(tokens)
    seen, heads = {}, []
    # Real headings first, so that a made heading never shifts their ids.
    order = [i for i, t in enumerate(tokens) if t.type == 'heading_open']
    made = [i for i in order if tokens[i + 1].content.startswith(MADE)]
    for i in [i for i in order if i not in made] + made:
        inline = tokens[i + 1]
        if inline.content.startswith(MADE):
            inline.content = inline.content[len(MADE):]
            if inline.children and inline.children[0].type == 'text':
                inline.children[0].content = inline.children[0].content.replace(MADE, '')
        label = plain(inline.children)
        base = slugify(label) or 'section'
        hid, n = base, seen.get(base, 0)
        if i in made:
            hid = '%s-%d' % (base, n) if n else base
            while hid in seen:
                n += 1
                hid = '%s-%d' % (base, n)
        elif n:
            hid = '%s-%d' % (base, n)
        seen[base] = n + 1
        seen[hid] = seen.get(hid, 1)
        tokens[i].attrSet('id', hid)
    out = []
    for i, t in enumerate(tokens):
        if t.type == 'heading_open':
            heads.append((int(t.tag[1]), t.attrGet('id'), plain(tokens[i + 1].children)))
    body = MD.renderer.render(tokens, MD.options, {})
    body = re.sub(r'(<div class="callout callout-(\w+)" role="note">)',
                  lambda m: m.group(1) + '\n<p class="callout-title">%s</p>' % CALLOUTS[m.group(2).upper()], body)
    return body, heads


# ---------------------------------------------------------------- splitting

HEAD_RE = re.compile(r'<h([1-6]) id="([^"]+)">(.*?)</h\1>', re.S)


def blocks(body):
    """Split a rendered file: (h1 or None, intro, [(h2 id, h2 title, html,
    [(h3 id, h3 title, html)])]); a block's html starts with its heading."""
    h1 = None
    m = re.match(r'\s*<h1 id="([^"]+)">(.*?)</h1>\n?', body, re.S)
    if m:
        h1 = (m.group(1), m.group(2))
        body = body[m.end():]
    parts = re.split(r'(?=^<h2 id=")', body, flags=re.M)
    intro, h2s = parts[0], []
    for p in parts[1:]:
        m = HEAD_RE.match(p)
        subs = re.split(r'(?=^<h3 id=")', p, flags=re.M)
        h3s = []
        for s in subs[1:]:
            n = HEAD_RE.match(s)
            h3s.append((n.group(2), strip_tags(n.group(3)), s))
        h2s.append((m.group(2), strip_tags(m.group(3)), subs[0], h3s))
    return h1, intro, h2s


def strip_tags(s):
    return html.unescape(re.sub(r'<[^>]+>', '', s)).strip()


def clean_intro(s):
    """A README's top: drop the banner, the badges, rules and the link line;
    a centred tagline becomes the lead, a demo image stays."""
    def centred(m):
        inner = m.group(1)
        if re.search(r'<picture|shields\.io|badge\.svg', inner):
            return ''
        if '<img' in inner:
            return '<p class="figure">%s</p>\n' % inner.strip()
        if not re.sub(r'<a [^>]*>.*?</a>|<[^>]+>|\s|·|\|', '', inner):
            return ''
        return '<p class="lead">%s</p>\n' % inner.strip()
    s = re.sub(r'<(?:p|h[1-6]) align="center">(.*?)</(?:p|h[1-6])>\s*', centred, s, flags=re.S)
    s = re.sub(r'<picture>.*?</picture>\s*', '', s, flags=re.S)
    s = re.sub(r'<div align="center">.*?</div>\s*', '', s, flags=re.S)
    s = re.sub(r'<hr\s*/?>\s*', '', s)
    # A paragraph made of links only ("Quick start · How it works · …").
    s = re.sub(r'<p>(?:\s*<a [^>]*>[^<]*</a>\s*(?:·|\|)?\s*)+</p>\s*', '', s)
    return s.strip()


# ---------------------------------------------------------------- the model

@dataclasses.dataclass
class Page:
    tab: dict
    group: str
    slug: str
    repo: str
    path: str
    title: str = ''
    nav: str = ''
    sections: list = None
    intro: bool = False
    bullets: list = None
    body: str = ''
    toc: list = dataclasses.field(default_factory=list)
    ids: set = dataclasses.field(default_factory=set)
    anchor: str = ''
    title_id: str = 'top'
    description: str = ''

    @property
    def url(self):
        tab = self.tab['id']
        parts = [p for p in (tab, self.slug.strip('/')) if p]
        return BASE + ''.join(p + '/' for p in parts)

    @property
    def source_url(self):
        return 'https://github.com/%s/%s/blob/HEAD/%s%s' % (
            OWNER, self.repo, self.path, '#' + self.anchor if self.anchor else '')

    @property
    def edit_url(self):
        return 'https://github.com/%s/%s/edit/HEAD/%s' % (OWNER, self.repo, self.path)


def load_nav(path):
    with open(path, 'rb') as fh:
        nav = tomllib.load(fh)
    pages = []
    for tab in nav['tab']:
        for group in tab['group']:
            for p in group['pages']:
                repo, rel = p['src'].split(':', 1)
                pages.append(Page(tab=tab, group=group['title'], slug=p.get('slug', ''),
                                  repo=repo, path=rel, title=p.get('title', ''),
                                  nav=p.get('nav', ''), sections=p.get('sections'),
                                  intro=p.get('intro', False), bullets=p.get('bullets'),
                                  description=p.get('description', '')))
    urls = [p.url for p in pages]
    dup = {u for u in urls if urls.count(u) > 1}
    if dup:
        raise SystemExit('two pages at %s' % ', '.join(sorted(dup)))
    return nav, pages


DOC_RE = re.compile(r'(?:README|CHANGELOG|GUIDE)\.md$|docs/.+\.md$')


def uncovered(nav, pages, src):
    """The docs of the fetched repos that are neither a page nor skipped:
    README.md, CHANGELOG.md, GUIDE.md at the top, and docs/**/*.md."""
    have = {'%s:%s' % (p.repo, p.path) for p in pages}
    skip = set(nav.get('sources', {}).get('skip', []))
    missing = []
    for repo, root in sorted(src.dirs.items()):
        for dirpath, dirs, names in os.walk(root):
            dirs[:] = sorted(d for d in dirs if not d.startswith(('.', '_')) and d != 'node_modules')
            for n in sorted(names):
                rel = os.path.relpath(os.path.join(dirpath, n), root).replace(os.sep, '/')
                key = '%s:%s' % (repo, rel)
                if DOC_RE.fullmatch(rel) and key not in have and key not in skip:
                    missing.append(key)
    return missing


def shift(body, by):
    """Move every heading level by `by` (h3 -> h2 with by=-1)."""
    if not by:
        return body
    return re.sub(r'<(/?)h([1-6])\b', lambda m: '<%sh%d' % (m.group(1), min(6, max(2, int(m.group(2)) + by))), body)


def build_pages(pages, src):
    """Fill each page's body, title, toc and ids from its source."""
    files = {}
    for p in pages:
        key = (p.repo, p.path)
        if key not in files:
            bullets_in = sorted({b for q in pages if (q.repo, q.path) == key for b in (q.bullets or [])})
            files[key] = blocks(render(src.read(p.repo, p.path), bullets_in)[0])
    # Sections picked by a page as "H2 > H3" leave the page of their H2.
    claimed = {}
    for p in pages:
        for s in p.sections or []:
            if '>' in s:
                h2, h3 = [x.strip().lower() for x in s.split('>', 1)]
                claimed.setdefault((p.repo, p.path, h2), set()).add(h3)
    for p in pages:
        h1, intro, h2s = files[(p.repo, p.path)]
        if p.sections is None:
            p.title = p.title or (strip_tags(h1[1]) if h1 else os.path.basename(p.path))
            if h1:
                p.title_id = h1[0]
                p.ids.add(h1[0])
            body = intro + ''.join(h + ''.join(s for _, _, s in subs) for _, _, h, subs in h2s)
            p.body = body
            continue
        chunks = [clean_intro(intro)] if p.intro else []
        picked = []
        for sel in p.sections:
            h2, _, h3 = [x.strip() for x in sel.partition('>')]
            hit = [b for b in h2s if b[1].lower() == h2.lower() or b[0] == h2]
            if not hit:
                raise SystemExit('%s:%s has no section "%s" (page %s)' % (p.repo, p.path, h2, p.url))
            hid, htitle, head, subs = hit[0]
            if h3:
                sub = [s for s in subs if s[1].lower() == h3.lower() or s[0] == h3]
                if not sub:
                    raise SystemExit('%s:%s has no section "%s" (page %s)' % (p.repo, p.path, sel, p.url))
                picked.append((sub[0][0], sub[0][1], 3, sub[0][2]))
            else:
                skip = claimed.get((p.repo, p.path, htitle.lower()), set())
                picked.append((hid, htitle, 2, head + ''.join(s for i, t, s in subs if t.lower() not in skip)))
        if len(picked) == 1 and not p.intro:
            hid, htitle, level, chunk = picked[0]
            p.title = p.title or htitle
            p.anchor = p.title_id = hid
            # The section's heading is the page's title; its id stays.
            chunk = HEAD_RE.sub('', chunk, count=1)
            chunks.append(shift(chunk, -(level - 1)))
            p.ids.add(hid)
        else:
            if not p.title:
                raise SystemExit('page %s takes several sections: give it a title' % p.url)
            p.anchor = picked[0][0]
            for hid, htitle, level, chunk in picked:
                chunks.append(shift(chunk, 2 - level))
        p.body = '\n'.join(c for c in chunks if c)
    for p in pages:
        p.ids |= set(re.findall(r'\sid="([^"]+)"', p.body))
        p.toc = [(int(lv), hid, strip_tags(t)) for lv, hid, t in HEAD_RE.findall(p.body) if lv in ('2', '3')]
        p.nav = p.nav or p.title


# ---------------------------------------------------------------- links

class Links:
    def __init__(self, pages, src, out):
        self.src, self.out = src, out
        self.by_file, self.by_anchor = {}, {}
        for p in pages:
            self.by_file.setdefault((p.repo, p.path), []).append(p)
            for i in p.ids:
                self.by_anchor.setdefault((p.repo, p.path, i), p)
        self.media = set()

    def github(self, repo, rel, frag='', folder=False):
        """The file on GitHub: a folder (a link ending in /, or a folder of
        the sources) is a tree, anything else a blob (LICENSE included)."""
        folder = folder or os.path.isdir(self.src.path(repo, rel)) if repo in self.src.dirs else folder
        kind = 'tree' if folder else 'blob'
        return 'https://github.com/%s/%s/%s/HEAD/%s%s' % (OWNER, repo, kind, rel, '#' + frag if frag else '')

    def target(self, repo, rel, frag, here):
        pages = self.by_file.get((repo, rel))
        if frag and (repo, rel, frag) in self.by_anchor:
            p = self.by_anchor[(repo, rel, frag)]
            return ('#' + frag) if p is here else p.url + '#' + frag
        if pages and not frag:
            return pages[0].url
        if pages and frag:
            # An anchor no page keeps (a section left out): GitHub has it.
            return self.github(repo, rel, frag)
        return None

    def href(self, url, page, image=False):
        url = html.unescape(url)
        if not url or url.startswith(('mailto:', 'tel:', 'data:', '/')):
            return url
        if url.startswith('#'):
            return self.target(page.repo, page.path, url[1:], page) or self.github(page.repo, page.path, url[1:])
        m = re.match(r'https://github\.com/%s/([\w.-]+)/(?:blob|tree)/(?:main|HEAD)/([^#?]*)(?:#(.*))?$' % OWNER, url, re.I)
        if m and m.group(1) in self.src.dirs:
            t = self.target(m.group(1), m.group(2).rstrip('/'), m.group(3) or '', page)
            return t or url
        if re.match(r'[a-z][a-z0-9+.-]*:', url, re.I):
            return url
        path, _, frag = url.partition('#')
        path = path.split('?')[0]
        folder = path.endswith('/')
        rel = posixpath.normpath(posixpath.join(posixpath.dirname(page.path), urllib.parse.unquote(path)))
        if rel.startswith('..'):
            return self.github(page.repo, page.path)
        if image or rel.lower().endswith(MEDIA):
            if self.src.exists(page.repo, rel):
                self.media.add((page.repo, rel))
                return BASE + '_media/%s/%s' % (page.repo, rel)
            return None
        return self.target(page.repo, rel, frag, page) or self.github(page.repo, rel, frag, folder)

    def rewrite(self, page):
        def attr(m):
            name, q, val = m.group(1), m.group(2), m.group(3)
            new = self.href(val, page, image=name in ('src', 'srcset'))
            if new is None:
                return m.group(0)
            return ' %s=%s%s%s' % (name, q, html.escape(new, quote=True), q)
        body = re.sub(r'\s(href|src|srcset)=(")([^"]*)"', attr, page.body)
        # Images that would load from another site, or that are missing: a link.
        def img(m):
            tag = m.group(0)
            s = re.search(r'\ssrc="([^"]*)"', tag)
            if s and s.group(1).startswith(BASE):
                return tag
            alt = re.search(r'\salt="([^"]*)"', tag)
            label = alt.group(1) if alt and alt.group(1) else 'image'
            return ('<a href="%s">%s</a>' % (s.group(1), label)) if s and s.group(1).startswith('http') else label
        body = re.sub(r'<img\b[^>]*>', img, body)
        body = re.sub(r'<source\b[^>]*srcset="(?!%s)[^"]*"[^>]*>' % re.escape(BASE), '', body)
        page.body = body

    def copy_media(self):
        for repo, rel in sorted(self.media):
            dest = os.path.join(self.out, 'docs', '_media', repo, *rel.split('/'))
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            shutil.copyfile(self.src.path(repo, rel), dest)


# ---------------------------------------------------------------- output

def esc(s):
    return html.escape(s, quote=True)


def theme_css():
    """The dark tokens for an explicit choice: the page can be dark on a
    light system and light on a dark one. Taken from tokens.css, not copied."""
    with open(os.path.join(ROOT, 'assets', 'tokens.css'), encoding='utf-8') as fh:
        css = fh.read()
    root = re.search(r'^:root \{(.*?)^\}', css, re.S | re.M).group(1)
    dark = re.search(r'@media \(prefers-color-scheme: dark\) \{\s*:root \{(.*?)\}', css, re.S).group(1)
    names = re.findall(r'(--[\w-]+):', dark)
    light = '\n'.join(re.search(r'\s*%s:[^;]+;' % re.escape(n), root).group(0).strip() for n in names)
    light += '\n  color-scheme: light;'
    return ('/* Generated by docs-site/build.py from assets/tokens.css: do not edit. */\n'
            ':root[data-theme="light"] {\n  %s\n}\n:root[data-theme="dark"] {%s}\n'
            % (light.replace('\n', '\n  '), dark))


def sidebar(tab, pages, current):
    out, group = [], None
    for p in pages:
        if p.tab is not tab:
            continue
        if p.group != group:
            if group is not None:
                out.append('</ul></details>')
            group = p.group
            here = any(q is current for q in pages if q.tab is tab and q.group == group)
            out.append('<details class="nav-group"%s><summary>%s</summary><ul>'
                       % (' open' if here or not tab.get('fold') else '', esc(group)))
        cur = ' aria-current="page"' if p is current else ''
        out.append('<li><a href="%s"%s>%s</a></li>' % (p.url, cur, esc(p.nav)))
    out.append('</ul></details>')
    return '\n'.join(out)


def tabs_html(nav, pages, current):
    out = []
    for tab in nav['tab']:
        first = next(p for p in pages if p.tab is tab)
        cur = ' aria-current="page"' if current.tab is tab else ''
        out.append('<li><a href="%s"%s>%s</a></li>' % (first.url, cur, esc(tab['title'])))
    return '\n'.join(out)


def toc_html(page):
    if len(page.toc) < 2:
        return ''
    out = ['<nav class="toc" aria-labelledby="toc-title"><p class="label" id="toc-title">On this page</p><ul>']
    for level, hid, text in page.toc:
        out.append('<li class="toc-%d"><a href="#%s">%s</a></li>' % (level, esc(hid), esc(text)))
    out.append('</ul></nav>')
    return '\n'.join(out)


def anchors(body):
    """A # link on every h2 and h3, for sharing a section."""
    return re.sub(r'<h([23]) id="([^"]+)">(.*?)</h\1>',
                  lambda m: '<h%s id="%s">%s <a class="heading-anchor" href="#%s" aria-label="Link to this section">#</a></h%s>'
                  % (m.group(1), m.group(2), m.group(3), m.group(2), m.group(1)), body, flags=re.S)


def describe(page):
    if page.description:
        return page.description
    m = re.search(r'<p>(.*?)</p>', page.body, re.S)
    text = strip_tags(m.group(1)) if m else page.title
    text = re.sub(r'\s+', ' ', text)
    return text if len(text) <= 160 else text[:157].rsplit(' ', 1)[0] + '…'


def template():
    with open(os.path.join(HERE, 'template.html'), encoding='utf-8') as fh:
        return fh.read()


def page_html(tpl, nav, pages, page, prev, nxt):
    source = '%s/%s' % (page.repo, page.path)
    if page.sections:
        source += ' › ' + ', '.join(s.split('>')[-1].strip() for s in page.sections)
    pn = []
    if prev:
        pn.append('<a class="prev" href="%s"><span class="label">Previous</span> %s</a>' % (prev.url, esc(prev.nav)))
    if nxt:
        pn.append('<a class="next" href="%s"><span class="label">Next</span> %s</a>' % (nxt.url, esc(nxt.nav)))
    values = {
        'TITLE': esc(page.title),
        'TAB': esc(page.tab['title']),
        'EYEBROW': esc(page.tab['title'] + (' · ' + page.group if page.group and page.group != page.tab['title'] else '')),
        'DESCRIPTION': esc(describe(page)),
        'URL': esc(SITE + page.url),
        'TABS': tabs_html(nav, pages, page),
        'SIDEBAR': sidebar(page.tab, pages, page),
        'TOC': toc_html(page),
        'BODY': anchors(page.body),
        'PREVNEXT': '\n'.join(pn),
        'SOURCE': esc(source),
        'SOURCE_URL': esc(page.source_url),
        'EDIT_URL': esc(page.edit_url),
        'TITLE_ID': esc(page.title_id),
    }
    return re.sub(r'\{\{(\w+)\}\}', lambda m: values[m.group(1)], tpl)


def search_index(pages):
    """One entry per page and per h2/h3 section: title, heading, text."""
    out = []
    for p in pages:
        parts = re.split(r'(?=<h[23] id=")', p.body)
        for i, part in enumerate(parts):
            m = HEAD_RE.match(part)
            text = strip_tags(HEAD_RE.sub('', part, count=1) if m else part)
            text = re.sub(r'\s+', ' ', text)[:1500]
            if not text and not m:
                continue
            out.append({'u': p.url + ('#' + m.group(2) if m else ''), 't': p.title,
                        'h': strip_tags(m.group(3)) if m else '', 'b': p.tab['title'], 'x': text})
    return out


def copy_home(out):
    for f in HOME_FILES:
        shutil.copyfile(os.path.join(ROOT, f), os.path.join(out, f))
    for d in HOME_DIRS:
        shutil.copytree(os.path.join(ROOT, d), os.path.join(out, d))


def sitemap(pages):
    urls = [SITE + '/'] + [SITE + p.url for p in pages]
    return ('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
            + ''.join('  <url><loc>%s</loc></url>\n' % esc(u) for u in urls) + '</urlset>\n')


def build(out, cache, offline, nav_path):
    nav, pages = load_nav(nav_path)
    src = Sources(sorted({p.repo for p in pages}), cache, offline)
    missing = uncovered(nav, pages, src)
    if missing:
        raise SystemExit('docs with no page in nav.toml (add a page, or [sources] skip):\n  '
                         + '\n  '.join(missing))
    build_pages(pages, src)
    shutil.rmtree(out, ignore_errors=True)
    os.makedirs(out)
    copy_home(out)
    links = Links(pages, src, out)
    for p in pages:
        links.rewrite(p)
    links.copy_media()
    tpl = template()
    for tab in nav['tab']:
        tp = [p for p in pages if p.tab is tab]
        for i, p in enumerate(tp):
            d = os.path.join(out, *p.url.strip('/').split('/'))
            os.makedirs(d, exist_ok=True)
            with open(os.path.join(d, 'index.html'), 'w', encoding='utf-8') as fh:
                fh.write(page_html(tpl, nav, pages, p, tp[i - 1] if i else None, tp[i + 1] if i + 1 < len(tp) else None))
    assets = os.path.join(out, 'docs', '_assets')
    os.makedirs(assets, exist_ok=True)
    for f in os.listdir(os.path.join(HERE, 'assets')):
        shutil.copyfile(os.path.join(HERE, 'assets', f), os.path.join(assets, f))
    with open(os.path.join(assets, 'theme.css'), 'w', encoding='utf-8') as fh:
        fh.write(theme_css())
    with open(os.path.join(assets, 'search.json'), 'w', encoding='utf-8') as fh:
        json.dump(search_index(pages), fh, ensure_ascii=False, separators=(',', ':'))
    with open(os.path.join(out, 'sitemap.xml'), 'w', encoding='utf-8') as fh:
        fh.write(sitemap(pages))
    notfound = Page(tab=nav['tab'][0], group='', slug='', repo='lockfamily', path='docs-site/pages/404.md',
                    title='Page not found', body='<p>This page does not exist, or moved. Try the search, or start from the <a href="%s">docs home</a>.</p>' % BASE)
    nf = page_html(tpl, nav, pages, notfound, None, None).replace('<link rel="canonical" href="%s">' % esc(SITE + notfound.url), '')
    with open(os.path.join(out, '404.html'), 'w', encoding='utf-8') as fh:
        fh.write(nf)
    return pages


# ---------------------------------------------------------------- check

def check(out):
    """Every local href, src and #fragment of the built site resolves; no
    page loads anything from another origin."""
    errors, ids = [], {}

    def page_ids(path):
        if path not in ids:
            with open(path, encoding='utf-8') as fh:
                ids[path] = set(re.findall(r'\sid="([^"]+)"', fh.read()))
        return ids[path]

    def resolve(url, here):
        path = urllib.parse.unquote(url.split('#')[0].split('?')[0])
        if not path:
            return here
        full = os.path.join(out, path.lstrip('/')) if path.startswith('/') else os.path.join(os.path.dirname(here), path)
        if os.path.isdir(full):
            full = os.path.join(full, 'index.html')
        return os.path.normpath(full)

    count = 0
    for dirpath, _, names in os.walk(out):
        for n in names:
            if not n.endswith('.html'):
                continue
            here = os.path.join(dirpath, n)
            rel = os.path.relpath(here, out)
            with open(here, encoding='utf-8') as fh:
                text = fh.read()
            text = re.sub(r'<(pre|code)\b.*?</\1>', '', text, flags=re.S)
            for tag in re.findall(r'<(?:link|script|img|source|iframe|video|audio)\b[^>]*>', text):
                if re.search(r'\srel="(?:canonical|alternate)"', tag):
                    continue
                for u in re.findall(r'\s(?:src|srcset|href)="([^"]*)"', tag):
                    if re.match(r'(https?:)?//', u):
                        errors.append('%s: third-party resource %s' % (rel, u))
            for u in re.findall(r'\s(?:href|src)="([^"]*)"', text):
                u = html.unescape(u)
                if re.match(r'[a-z][a-z0-9+.-]*:|//', u, re.I):
                    continue
                count += 1
                target = resolve(u, here)
                if not os.path.exists(target):
                    errors.append('%s: %s does not exist' % (rel, u))
                elif '#' in u and target.endswith('.html'):
                    frag = urllib.parse.unquote(u.split('#', 1)[1])
                    if frag and frag not in page_ids(target):
                        errors.append('%s: %s has no #%s' % (rel, u.split('#')[0] or n, frag))
    for e in errors:
        print(e, file=sys.stderr)
    print('%d local links checked, %d broken' % (count, len(errors)))
    return not errors


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    ap.add_argument('--out', default=os.path.join(ROOT, '_site'))
    ap.add_argument('--sources', default=os.path.join(ROOT, '.docs-cache'),
                    help='where the other repos are fetched (one folder per repo)')
    ap.add_argument('--offline', action='store_true', help='use --sources only, never download')
    ap.add_argument('--nav', default=os.path.join(HERE, 'nav.toml'))
    ap.add_argument('--check', metavar='SITE', help='check a built site instead')
    a = ap.parse_args()
    if a.check:
        sys.exit(0 if check(a.check) else 1)
    pages = build(a.out, a.sources, a.offline, a.nav)
    print('built %d pages in %s' % (len(pages), a.out))


if __name__ == '__main__':
    main()
