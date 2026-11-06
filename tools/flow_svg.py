#!/usr/bin/env python3
"""Generate the animated SVGs of the Lock Family request flow.

    python3 tools/flow_svg.py          # write assets/flow-*.svg
    python3 tools/flow_svg.py --check  # fail if they differ from the generator

The flow is the one lockhub ships with `lox run` (lockhub#121):

    agent -> Lock client -> socket -> lock -> masked ticket -> hub
          -> lox run -> signed decision -> lock -> agent

Four scenarios play in a loop, each with a caption: an auto read, the first
connection to a profile, an approved write, a denied write. The animation is
CSS only (no script), so it plays in GitHub's README and on lockfamily.dev;
under prefers-reduced-motion every animation stops and the static frame
(the whole flow, the full lox run feed) shows. Every word is real <text>.

Four files: light and dark, wide (desktop) and narrow (phone). Python 3
standard library only; the output is deterministic.
"""

import argparse
import os
import sys
from xml.sax.saxutils import escape

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

SANS = ('-apple-system, BlinkMacSystemFont, &quot;Segoe UI&quot;, Roboto, '
        '&quot;Helvetica Neue&quot;, Arial, &quot;Noto Sans&quot;, sans-serif')
MONO = ('ui-monospace, SFMono-Regular, Menlo, Consolas, &quot;DejaVu Sans Mono&quot;, '
        '&quot;Liberation Mono&quot;, monospace')

# Average advance of a glyph, in em: what the layout checks measure with.
SANS_EM = 0.52
SANS_BOLD_EM = 0.56
MONO_EM = 0.61

# The identity's palette (assets/tokens.css, docs/identity.md), per theme:
# paper and carbon. The lox run terminal is dark in both themes, as on the
# site.
THEMES = {
    'light': {
        'bg': '#f4efe4', 'surface': '#fffcf5', 'surface2': '#e9e2d2',
        'text': '#1d1b17', 'muted': '#575146', 'border': '#b9af98',
        'wire': '#8f8670',
        'req': '#2a55a8', 'ticket': '#0e6158', 'ok': '#2d6a35',
        'deny': '#a8201a', 'ask': '#8a5300', 'result': '#0e6158',
        'harness': '#2a55a8', 'hub': '#0e6158', 'lock': '#1d1b17',
        'term_bg': '#1a1814', 'term_border': '#1a1814', 'term_bar': '#2a2620',
    },
    'dark': {
        'bg': '#16140f', 'surface': '#25221b', 'surface2': '#1f1c16',
        'text': '#ede6d6', 'muted': '#b2a994', 'border': '#4a4438',
        'wire': '#6b6352',
        'req': '#89b4fa', 'ticket': '#6fd9c8', 'ok': '#7fcf8a',
        'deny': '#ff9384', 'ask': '#e8b860', 'result': '#6fd9c8',
        'harness': '#89b4fa', 'hub': '#6fd9c8', 'lock': '#ede6d6',
        'term_bg': '#0e0d0a', 'term_border': '#4a4438', 'term_bar': '#24211b',
    },
}

# lox run's own colours (lockhub internal/loxrun/style.go, dark terminal).
TERM = {
    'text': '#e2e8f0', 'dim': '#94a3b8', 'rule': '#334155',
    'auto': '#4ade80', 'you': '#4ade80', 'asked': '#fbbf24',
    'denied': '#f87171', 'agent': '#89b4fa', 'mask': '#5eead4',
    'write': '#fbbf24', 'badge_bg': '#14532d', 'badge': '#bbf7d0',
}

# The wide and the narrow layout: the same boxes, placed differently.
# Each box is (x, y, w, h). Wires run from their first end to their second.
LAYOUTS = {
    'wide': {
        'size': (1200, 680),
        'props': [(16, 14, 284, 38), (308, 14, 284, 38), (600, 14, 284, 38), (892, 14, 292, 38)],
        'harness': (16, 74, 300, 404),
        'agent': (36, 116, 260, 124),
        'client': (36, 350, 260, 104),
        'lock': (400, 326, 260, 140),
        'hub': (400, 100, 260, 126),
        'term': (736, 74, 448, 452),
        'chips': [(318, 536, 78), (404, 536, 78), (491, 536, 78), (578, 536, 78), (664, 536, 78)],
        'wires': {
            'mcp': [(166, 240), (166, 350)],
            'socket': [(296, 402), (400, 402)],
            'ticket': [(530, 326), (530, 226)],
            'tty': [(660, 163), (736, 163)],
            'db': [(530, 466), (530, 536)],
        },
        'wire_labels': {
            'mcp': (224, 299, 'start', ['MCP']),
            'socket': (348, 384, 'middle', ['socket']),
            'ticket': (612, 268, 'start', ['↑ masked ticket', '↓ signed decision']),
            'tty': (698, 192, 'middle', ['queue']),
        },
        # No wire between the harness and the hub: a crossed, dashed one.
        'noroute': {'path': [(296, 163), (400, 163)], 'mark': (348, 163), 'label': (348, 145, 'middle')},
        'caption': (16, 596, 1168, 70),
    },
    'narrow': {
        'size': (480, 1468),
        'props': [(16, 14, 448, 34), (16, 54, 448, 34), (16, 94, 448, 34), (16, 134, 448, 34)],
        'harness': (16, 192, 448, 168),
        'agent': (28, 228, 250, 124),
        'client': (290, 228, 162, 124),
        'lock': (46, 432, 260, 140),
        'hub': (46, 682, 260, 126),
        'term': (16, 880, 448, 452),
        'chips': [(366, 424, 86), (366, 458, 86), (366, 492, 86), (366, 526, 86), (366, 560, 86)],
        'wires': {
            'mcp': [(278, 290), (290, 290)],
            'socket': [(371, 352), (371, 386), (176, 386), (176, 432)],
            'ticket': [(176, 572), (176, 682)],
            'tty': [(176, 808), (176, 880)],
            'db': [(306, 506), (366, 506)],
        },
        'wire_labels': {
            'socket': (260, 414, 'start', ['socket']),
            'ticket': (260, 620, 'start', ['↑ masked ticket', '↓ signed decision']),
            'tty': (260, 848, 'start', ['queue']),
        },
        # Down the left margin, from the harness to the hub, past the lock.
        'noroute': {'path': [(30, 360), (30, 745), (46, 745)], 'mark': (30, 627), 'label': (48, 631, 'start')},
        'caption': (16, 1356, 448, 108),
    },
}

PROPS = [
    ('✕', 'deny', 'The agent never talks to the hub'),
    ('◆', 'hub', 'The hub sees masked queries only'),
    ('▣', 'harness', 'You approve outside the harness'),
    ('✓', 'ok', 'Reads auto · writes asked'),
]

CHIPS = ['RabbitMQ', 'files', 'Database', 'HTTP', 'logs']
DB_CHIP = 2

# The scenarios: (length in seconds, number, title, caption lines).
SCENARIOS = [
    (9.5, '1', 'A read: no question',
     'SELECT on replica: the lock sends a masked ticket, an auto rule in lox run',
     'approves it, the hub signs, masked rows come back to the agent.'),
    (12.0, '2', 'First use of a profile: asked once',
     'primary is not connected: the lock sends a connect ticket, lox run asks you',
     'y/n once this session, the lock connects on the signed decision.'),
    (10.5, '3', 'A write: always asked',
     'UPDATE on primary is asked even in auto mode; the lock runs it only on',
     'the signed approval, bound to that exact plan.'),
    (9.5, '4', 'A denied write',
     'DELETE on primary: you answer n, the signed denial reaches the lock,',
     'which never runs it. The agent only learns it was denied.'),
]
CYCLE = sum(s[0] for s in SCENARIOS)
STARTS = [sum(s[0] for s in SCENARIOS[:i]) for i in range(len(SCENARIOS))]
FADE = 0.25
HOP = 0.7

STILL_TITLE = 'agent → Lock client → socket → lock → masked ticket → hub → lox run → signed decision → lock → agent'
STILL_TITLE_NARROW = ['agent → Lock client → socket → lock', '→ masked ticket → hub → lox run',
                      '→ signed decision → lock → agent']
STILL_SUB = 'Reads pass by an auto rule; a connection, a write and DDL wait for you in lox run.'

TITLE = 'How a request flows through the Lock Family'
DESC = (
    'An agent (any MCP client: Claude Code, Codex, Cursor, lea, …) runs in its harness with a Lock client, an MCP server '
    'that holds no credential. The client reaches the lock over a socket; the lock holds the '
    'credentials and the only connection to the database, RabbitMQ, files, HTTP or logs. The '
    'lock sends a masked ticket to the hub; the hub passes it to lox run, which the human keeps '
    'open in a terminal of their own, outside the harness. lox run decides, by an auto rule or by '
    'asking the human; the hub signs the decision and the lock runs the request only on it, then '
    'masks the result for the agent. The agent never talks to the hub, and the hub never sees a '
    'query or a result in clear. Four scenarios loop: 1, a SELECT on profile replica is approved '
    'by an auto rule, no question, and masked rows come back; 2, the first request on profile '
    'primary makes the lock send a connect ticket, lox run asks y/n once for the session, and '
    'the lock connects on the signed decision; 3, an UPDATE is always asked, approved with y and '
    'run; 4, a DELETE is asked and denied with n, the lock never runs it and the agent is told it '
    'was denied.'
)


def f(v):
    """A number for an attribute: short, deterministic."""
    s = ('%.2f' % v).rstrip('0').rstrip('.')
    return '0' if s == '-0' else s


def width_of(text, size, mono, bold=False):
    if mono:
        return len(text) * size * MONO_EM
    return len(text) * size * (SANS_BOLD_EM if bold else SANS_EM)


class Svg:
    """An SVG being drawn: elements, animations, and layout checks."""

    def __init__(self, theme, layout):
        self.t = THEMES[theme]
        self.theme = theme
        self.layout_name = layout
        self.L = LAYOUTS[layout]
        self.body = []
        self.css = []
        self.n = 0
        self.texts = []  # (text, x0, x1, box) for the layout checks

    # -- drawing -------------------------------------------------------
    def add(self, s):
        self.body.append(s)

    def text(self, x, y, s, size=13, fill=None, weight=None, anchor='start', mono=False,
             italic=False, box=None, extra=''):
        fill = fill or self.t['text']
        attrs = ['x="%s"' % f(x), 'y="%s"' % f(y), 'font-size="%s"' % f(size), 'fill="%s"' % fill]
        if mono:
            attrs.append('class="m"')
        if weight:
            attrs.append('font-weight="%s"' % weight)
        if italic:
            attrs.append('font-style="italic"')
        if anchor != 'start':
            attrs.append('text-anchor="%s"' % anchor)
        if isinstance(s, str):
            plain, inner = s, escape(s)
        else:
            # spans: [(text, fill, weight)], one line in one font.
            plain = ''.join(t for t, _, _ in s)
            inner = ''.join('<tspan fill="%s"%s>%s</tspan>' % (c, ' font-weight="%s"' % w if w else '', escape(t))
                            for t, c, w in s)
        w = width_of(plain, size, mono, bool(weight))
        x0 = {'start': x, 'middle': x - w / 2, 'end': x - w}[anchor]
        self.texts.append((plain, x0, x0 + w, box))
        return '<text %s%s>%s</text>' % (' '.join(attrs), extra, inner)

    def rect(self, x, y, w, h, rx=10, fill='none', stroke='none', sw=1, dash=None, extra=''):
        d = ' stroke-dasharray="%s"' % dash if dash else ''
        return ('<rect x="%s" y="%s" width="%s" height="%s" rx="%s" fill="%s" stroke="%s" '
                'stroke-width="%s"%s%s/>' % (f(x), f(y), f(w), f(h), f(rx), fill, stroke, f(sw), d, extra))

    def path(self, pts, stroke, sw=2, dash=None, extra=''):
        d = 'M' + ' L'.join('%s %s' % (f(x), f(y)) for x, y in pts)
        da = ' stroke-dasharray="%s"' % dash if dash else ''
        return ('<path d="%s" fill="none" stroke="%s" stroke-width="%s" stroke-linecap="round" '
                'stroke-linejoin="round"%s%s/>' % (d, stroke, f(sw), da, extra))

    # -- animation -----------------------------------------------------
    def anim(self, frames):
        """A class animating its element through frames: [(seconds, css)]."""
        self.n += 1
        name = 'k%d' % self.n
        rows = []
        last = None
        for t, css in frames:
            pct = '%.3f%%' % (100.0 * min(max(t, 0.0), CYCLE) / CYCLE)
            if pct == last:
                rows[-1] = '%s{%s}' % (pct, css)
            else:
                rows.append('%s{%s}' % (pct, css))
            last = pct
        self.css.append('@keyframes %s{%s}' % (name, ''.join(rows)))
        self.css.append('.%s{animation:%s %ss linear infinite}' % (name, name, f(CYCLE)))
        return 'a ' + name

    def show(self, windows):
        """A class showing its element during windows: [(on, off)] seconds.
        An off of None means: until the loop ends."""
        frames = [(0, 'opacity:0')]
        for on, off in windows:
            off = CYCLE - FADE - 0.05 if off is None else off
            frames += [(on, 'opacity:0'), (on + FADE, 'opacity:1'), (off, 'opacity:1'),
                       (off + FADE, 'opacity:0')]
        frames.append((CYCLE, 'opacity:0'))
        return self.anim(frames)

    def group(self, inner, windows, still=False):
        """inner, shown during windows; in the static frame if still."""
        cls = self.show(windows)
        self.add('<g class="%s" opacity="%s">%s</g>' % (cls, 1 if still else 0, ''.join(inner)))

    # -- the scene -----------------------------------------------------
    def node(self, box, title, subs, accent, title_icon=None):
        x, y, w, h = box
        t = self.t
        out = [self.rect(x, y, w, h, 12, t['surface'], t['border'], 1.2),
               self.rect(x, y, 5, h, 2.5, accent)]
        tx = x + 18
        out.append(self.text(tx, y + 26, title, 16, t['text'], 700, box=box))
        for i, s in enumerate(subs):
            out.append(self.text(tx, y + 46 + 17 * i, s, 12, t['muted'], box=box))
        return out

    def pill(self, label, kind):
        """A packet: a pill centred on (0, 0)."""
        size = 11.5
        w = width_of(label, size, True) + 20
        c = self.t[kind]
        return [self.rect(-w / 2, -11, w, 22, 11, self.t['bg'], c, 1.6),
                '<text x="0" y="4" font-size="%s" fill="%s" class="m" text-anchor="middle" '
                'font-weight="600">%s</text>' % (f(size), c, escape(label))]

    def hop(self, wire, back, t0, label, kind, dur=HOP):
        pts = list(self.L['wires'][wire])
        if back:
            pts.reverse()
        segs = [((pts[i + 1][0] - pts[i][0]) ** 2 + (pts[i + 1][1] - pts[i][1]) ** 2) ** 0.5
                for i in range(len(pts) - 1)]
        total = sum(segs)
        tr = lambda p: 'transform:translate(%spx,%spx)' % (f(p[0]), f(p[1]))
        frames = [(0, 'opacity:0;' + tr(pts[0])), (t0, 'opacity:0;' + tr(pts[0])),
                  (t0 + 0.08, 'opacity:1;' + tr(pts[0]))]
        acc = 0.0
        for i, s in enumerate(segs):
            acc += s
            frames.append((t0 + 0.08 + (dur - 0.16) * acc / total, 'opacity:1;' + tr(pts[i + 1])))
        frames += [(t0 + dur, 'opacity:0;' + tr(pts[-1])), (CYCLE, 'opacity:0;' + tr(pts[-1]))]
        cls = self.anim(frames)
        self.add('<g class="%s" opacity="0">%s</g>' % (cls, ''.join(self.pill(label, kind))))
        self.hops.append((wire, back, t0, t0 + dur, label))


def build(theme, layout):
    s = Svg(theme, layout)
    s.hops = []
    t = s.t
    L = s.L
    W, H = L['size']

    s.add(s.rect(0, 0, W, H, 18, t['bg']))

    # Key properties.
    for (x, y, w, h), (icon, kind, label) in zip(L['props'], PROPS):
        box = (x, y, w, h)
        s.add(s.rect(x, y, w, h, h / 2, t['surface2'], t['border'], 1))
        s.add(s.text(x + 18, y + h / 2 + 5.5, icon, 14, t[kind], 700, box=box))
        s.add(s.text(x + 36, y + h / 2 + 4.5, label, 12.5, t['text'], 600, box=box))

    # The harness: the agent and its Lock client.
    hx, hy, hw, hh = L['harness']
    s.add(s.rect(hx, hy, hw, hh, 16, 'none', t['harness'], 1.6, '6 5'))
    s.add(s.text(hx + 16, hy + 24, 'agent harness', 13, t['harness'], 700, box=L['harness']))
    s.add(s.text(hx + 122, hy + 24, 'your agent’s tools', 12, t['muted'], box=L['harness']))

    # Wires, under the boxes.
    for name, pts in L['wires'].items():
        s.add(s.path(pts, t['wire'], 2.4))
    for name, (x, y, anchor, lines) in L['wire_labels'].items():
        for i, line in enumerate(lines):
            s.add(s.text(x, y + 15 * i, line, 11.5, t['muted'], 600, anchor))
    nr = L['noroute']
    s.add(s.path(nr['path'], t['deny'], 1.8, '4 5'))
    mx, my = nr['mark']
    s.add('<circle cx="%s" cy="%s" r="11" fill="%s" stroke="%s" stroke-width="1.6"/>'
          % (f(mx), f(my), t['bg'], t['deny']))
    s.add(s.text(mx, my + 4.5, '✕', 13, t['deny'], 700, 'middle'))
    lx_, ly_, la = nr['label']
    s.add(s.text(lx_, ly_, 'no route', 11.5, t['deny'], 600, la))

    for n in s.node(L['agent'], 'agent', ['Claude Code · Codex · Cursor · lea'], t['req']):
        s.add(n)
    for n in s.node(L['client'], 'Lock client', ['MCP server', 'no credential', 'no connection'], t['req']):
        s.add(n)
    for n in s.node(L['lock'], 'lock', ['locksql · lockmq · lockfile · lockhttp',
                                        'holds the credentials', 'masks every value it returns'],
                    t['lock']):
        s.add(n)
    for n in s.node(L['hub'], 'hub', ['queues tickets, signs decisions', 'masked queries only, no clear values',
                                      'never runs one, never sees a result'], t['hub']):
        s.add(n)

    # What sits behind the lock.
    for i, (x, y, w) in enumerate(L['chips']):
        main = i == DB_CHIP
        s.add(s.rect(x, y, w, 28, 8, t['surface2'] if not main else t['surface'],
                     t['lock'] if main else t['border'], 1.6 if main else 1))
        s.add(s.text(x + w / 2, y + 18.5, CHIPS[i], 12, t['text'] if main else t['muted'],
                     700 if main else None, 'middle', box=(x, y, w, 28)))

    term(s)
    scenes(s)
    caption(s)

    css = [
        'text{font-family:%s;white-space:pre}' % SANS,
        '.m{font-family:%s}' % MONO,
        '@media (prefers-reduced-motion:reduce){.a{animation:none!important}}',
    ] + s.css
    head = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 %d %d" width="%d" height="%d" '
            'xml:space="preserve" role="img" aria-labelledby="flow-title flow-desc">' % (W, H, W, H))
    out = [head,
           '<title id="flow-title">%s</title>' % escape(TITLE),
           '<desc id="flow-desc">%s</desc>' % escape(DESC),
           '<style>%s</style>' % '\n'.join(css)]
    out += s.body
    out.append('</svg>')
    return '\n'.join(out) + '\n', s


def term(s):
    """lox run, in the human's own terminal."""
    L = s.L
    x, y, w, h = L['term']
    box = L['term']
    s.add(s.rect(x, y, w, h, 12, s.t['term_bg'], s.t['term_border'], 1.2))
    # Title bar: the human, outside the harness.
    s.add(s.rect(x, y, w, 34, 12, s.t['term_bar']))
    s.add(s.rect(x, y + 22, w, 12, 0, s.t['term_bar']))
    for i, c in enumerate(['#f87171', '#fbbf24', '#4ade80']):
        s.add('<circle cx="%s" cy="%s" r="5" fill="%s"/>' % (f(x + 18 + 16 * i), f(y + 17), c))
    px, py = x + 76, y + 17
    s.add('<circle cx="%s" cy="%s" r="4.2" fill="%s"/>' % (f(px), f(py - 4), TERM['text']))
    s.add('<path d="M%s %s a7.5 7 0 0 1 15 0 z" fill="%s"/>' % (f(px - 7.5), f(py + 10), TERM['text']))
    s.add(s.text(x + 92, y + 22, 'you · your own terminal, outside the harness', 12.5, TERM['text'],
                 600, box=box))

    tx = x + 14
    s.tx = tx
    # Header: as lox run draws it.
    hy = y + 58
    s.add(s.text(tx, hy, 'lox run', 12.5, TERM['text'], 700, mono=True, box=box))
    bx = tx + 8 * 12.5 * MONO_EM
    s.add(s.rect(bx, hy - 13, 46, 18, 4, TERM['badge_bg']))
    s.add(s.text(bx + 23, hy, 'AUTO', 11.5, TERM['badge'], 700, 'middle', mono=True))
    s.add(s.text(x + w - 14, hy, '● hub up · 1 lock', 11.5, TERM['auto'], anchor='end', mono=True, box=box))
    s.add(s.text(bx + 56, hy, '~/shop', 11.5, TERM['dim'], mono=True, box=box))
    cy = hy + 20
    s.conn_line = lambda more: s.text(tx, cy, 'connected shop/replica 6m' + more, 11.5, TERM['dim'],
                                      mono=True, box=box)
    # primary joins the connected line once its connection is approved.
    s.add(s.path([(x + 1, cy + 11), (x + w - 1, cy + 11)], TERM['rule'], 1))
    s.card_y = cy + 22
    s.feed_y = y + 300
    fy = y + h - 34
    s.add(s.path([(x + 1, fy), (x + w - 1, fy)], TERM['rule'], 1))
    keys = [('Shift+Tab', 'mode'), ('a', 'audit'), ('?', 'help'), ('q', 'quit')]
    spans = []
    for i, (k, v) in enumerate(keys):
        spans += [(('  ' if i else '') + k, TERM['text'], 700), (' ' + v, TERM['dim'], None)]
    s.add(s.text(tx, fy + 21, spans, 11.5, mono=True, box=box))


FEED_COLS = [5, 6, 6, 7, 5, 14]  # time, agent, lock, profile, kind, request


def feed_line(s, row, time, profile, kind, request, decision):
    """One line of lox run's feed, its columns padded with spaces as lox
    run pads them. decision: (label, colour)."""
    y = s.feed_y + 22 * row
    kcol = TERM['write'] if kind in ('write', 'conn') else TERM['dim']
    cells = [(time, TERM['dim'], None), ('agent', TERM['agent'], None), ('◆ shop', TERM['text'], None),
             (profile, TERM['dim'], None), (kind, kcol, 700 if kind == 'write' else None),
             (request, TERM['text'], None)]
    spans = []
    for n, (txt, colr, wt) in zip(FEED_COLS, cells):
        assert len(txt) <= n, txt
        spans.append((txt.ljust(n + 1), colr, wt))
    spans.append((decision[0], decision[1], 700))
    return [s.text(s.tx, y, spans, 11.5, mono=True, box=s.L['term'])]


def card(s, title, lines):
    """A question card above the feed."""
    x, y, w, h = s.L['term']
    box = (x + 10, s.card_y, w - 20, 150)
    cx, cy, cw_, ch = box
    tx = cx + 14
    out = [s.rect(cx, cy, cw_, ch, 8, '#1c1917', TERM['asked'], 1.6)]
    out.append(s.text(tx, cy + 22, '◆ QUESTION ' + title, 12, TERM['asked'], 700, mono=True, box=box))
    out.append(s.text(tx, cy + 42, 'agent asks · ◆ locksql', 11.5, TERM['dim'], mono=True, box=box))
    for i, (txt, colr) in enumerate(lines):
        out.append(s.text(tx, cy + 62 + 18 * i, txt, 11.5, colr, mono=True, box=box))
    out.append(s.text(tx, cy + 136, 'y approve   n deny   d details', 11.5, TERM['dim'], mono=True, box=box))
    # The bell: lox run rings only when a question waits.
    bx, by = cx + cw_ - 26, cy + 16
    out.append('<path d="M%s %s c0-5 2.5-8 6-8 s6 3 6 8 v4 l2 2 h-16 l2-2 z M%s %s a2.4 2.4 0 0 0 4.8 0" '
               'fill="%s"/>' % (f(bx - 6), f(by + 4), f(bx - 2.4), f(by + 10.5), TERM['asked']))
    return out, box


def scenes(s):
    t = s.t
    L = s.L
    ax, ay, aw, ah = L['agent']
    abox = L['agent']
    lx, ly, lw, lh = L['lock']
    lbox = L['lock']

    def agent_lines(start, length, req, res, res_kind, res_t, still=False):
        s.group([s.text(ax + 18, ay + 78, '› ' + req, 11.5, t['req'], 600, mono=True, box=abox)],
                [(start + 0.2, start + length - 0.35)], still)
        s.group([s.text(ax + 18, ay + 102, '‹ ' + res, 11.5, t[res_kind], 600, mono=True, box=abox)],
                [(start + res_t, start + length - 0.35)], still)

    # The lock's connections: replica throughout, primary from scenario 2.
    conn1 = s.text(lx + 18, ly + 124, '● replica   ○ primary', 11.5, t['muted'], mono=True, box=lbox)
    conn2 = s.text(lx + 18, ly + 124, '● replica   ● primary', 11.5, t['ok'], 600, mono=True, box=lbox)

    # 1. A SELECT, decided by an auto rule.
    a = STARTS[0]
    agent_lines(a, SCENARIOS[0][0], 'SELECT email FROM customers', 'j***@example.com ×20', 'result', 7.7, True)
    s.hop('mcp', False, a + 0.4, 'SELECT', 'req')
    s.hop('socket', False, a + 1.1, 'SELECT', 'req')
    s.hop('ticket', False, a + 1.8, 'ticket · masked', 'ticket')
    s.hop('tty', False, a + 2.5, 'ticket', 'ticket')
    s.hop('tty', True, a + 3.5, 'auto', 'ok')
    s.hop('ticket', True, a + 4.2, 'signed ✓', 'ok')
    s.hop('db', False, a + 4.9, 'SELECT', 'req', 0.6)
    s.hop('db', True, a + 5.5, 'rows', 'result', 0.6)
    s.hop('socket', True, a + 6.2, 'masked rows', 'result')
    s.hop('mcp', True, a + 6.9, 'masked rows', 'result')
    s.group(feed_line(s, 0, '14:01', 'replica', 'read', 'SELECT email…', ('auto ✓', TERM['auto'])),
            [(a + 3.2, None)], True)

    # 2. First use of primary: a connect ticket, asked once.
    b = STARTS[1]
    s.group([conn1], [(-FADE, b + 6.9)], False)
    s.group([conn2], [(b + 6.9, None)], True)
    agent_lines(b, SCENARIOS[1][0], 'SELECT count(*) FROM orders', '1 row', 'result', 10.6)
    s.hop('mcp', False, b + 0.4, 'SELECT', 'req')
    s.hop('socket', False, b + 1.1, 'SELECT', 'req')
    s.hop('ticket', False, b + 1.8, 'connect · primary', 'ticket')
    s.hop('tty', False, b + 2.5, 'connect', 'ticket')
    inner, _ = card(s, 'connect on shop/primary', [
        ('shop / primary · connect db:5432/shop', TERM['text']),
        ('why asked: first connection to this', TERM['dim']),
        ('profile in this session', TERM['dim'])])
    s.group(inner, [(b + 3.2, b + 5.0)])
    answer(s, 'y', b + 4.5, b + 5.0)
    s.group(feed_line(s, 1, '14:02', 'primary', 'conn', 'connect', ('◆ asked', TERM['asked'])),
            [(b + 3.2, b + 5.0)])
    s.group(feed_line(s, 1, '14:02', 'primary', 'conn', 'connect', ('✔ you ✓', TERM['you'])),
            [(b + 5.0, None)], True)
    s.hop('tty', True, b + 5.0, 'y', 'ok')
    s.hop('ticket', True, b + 5.7, 'signed ✓', 'ok')
    s.hop('db', False, b + 6.4, 'connect', 'ok', 0.5)
    s.group([s.conn_line('')], [(-FADE, b + 6.9)])
    s.group([s.conn_line(' · shop/primary 0s')], [(b + 6.9, None)], True)
    # Then the read itself, by the auto rule.
    s.hop('ticket', False, b + 7.0, 'ticket · masked', 'ticket', 0.5)
    s.hop('tty', False, b + 7.5, 'ticket', 'ticket', 0.45)
    s.group(feed_line(s, 2, '14:02', 'primary', 'read', 'SELECT count(…', ('auto ✓', TERM['auto'])),
            [(b + 7.95, None)], True)
    s.hop('tty', True, b + 8.0, 'auto', 'ok', 0.45)
    s.hop('ticket', True, b + 8.45, 'signed ✓', 'ok', 0.5)
    s.hop('db', False, b + 8.95, 'SELECT', 'req', 0.4)
    s.hop('db', True, b + 9.35, '1 row', 'result', 0.4)
    s.hop('socket', True, b + 9.75, '1 row', 'result', 0.45)
    s.hop('mcp', True, b + 10.2, '1 row', 'result', 0.45)

    # 3. An UPDATE: always asked.
    c = STARTS[2]
    agent_lines(c, SCENARIOS[2][0], 'UPDATE orders SET status=…', '1 row updated', 'ok', 9.0)
    s.hop('mcp', False, c + 0.4, 'UPDATE', 'req')
    s.hop('socket', False, c + 1.1, 'UPDATE', 'req')
    s.hop('ticket', False, c + 1.8, 'ticket · write', 'ticket')
    s.hop('tty', False, c + 2.5, 'ticket', 'ticket')
    inner, _ = card(s, 'write on shop/primary', [
        ('UPDATE orders SET status = ‹p***(4)›', TERM['text']),
        ('  WHERE id = ‹4***(5)›  -- 1 row', TERM['text']),
        ('why asked: write is always asked', TERM['dim'])])
    s.group(inner, [(c + 3.2, c + 5.0)])
    answer(s, 'y', c + 4.5, c + 5.0)
    s.group(feed_line(s, 3, '14:03', 'primary', 'write', 'UPDATE orders…', ('◆ asked', TERM['asked'])),
            [(c + 3.2, c + 5.0)])
    s.group(feed_line(s, 3, '14:03', 'primary', 'write', 'UPDATE orders…', ('✔ you ✓', TERM['you'])),
            [(c + 5.0, None)], True)
    s.hop('tty', True, c + 5.0, 'y', 'ok')
    s.hop('ticket', True, c + 5.7, 'signed ✓', 'ok')
    s.hop('db', False, c + 6.4, 'UPDATE', 'req', 0.6)
    s.hop('db', True, c + 7.0, '1 row', 'result', 0.6)
    s.hop('socket', True, c + 7.6, '1 row updated', 'ok')
    s.hop('mcp', True, c + 8.3, '1 row updated', 'ok')

    # 4. A DELETE: asked, denied, never run.
    d = STARTS[3]
    agent_lines(d, SCENARIOS[3][0], 'DELETE FROM customers …', 'denied in lox run', 'deny', 8.0)
    s.hop('mcp', False, d + 0.4, 'DELETE', 'req')
    s.hop('socket', False, d + 1.1, 'DELETE', 'req')
    s.hop('ticket', False, d + 1.8, 'ticket · write', 'ticket')
    s.hop('tty', False, d + 2.5, 'ticket', 'ticket')
    inner, _ = card(s, 'write on shop/primary', [
        ('DELETE FROM customers', TERM['text']),
        ('  WHERE created < ‹2***(10)›  -- 3812 rows', TERM['text']),
        ('why asked: write is always asked', TERM['dim'])])
    s.group(inner, [(d + 3.2, d + 5.0)])
    answer(s, 'n', d + 4.5, d + 5.0)
    s.group(feed_line(s, 4, '14:04', 'primary', 'write', 'DELETE FROM c…', ('◆ asked', TERM['asked'])),
            [(d + 3.2, d + 5.0)])
    s.group(feed_line(s, 4, '14:04', 'primary', 'write', 'DELETE FROM c…', ('✘ denied', TERM['denied'])),
            [(d + 5.0, None)], True)
    s.hop('tty', True, d + 5.0, 'n', 'deny')
    s.hop('ticket', True, d + 5.7, 'signed ✘', 'deny')
    # The lock does not run it: the database is never reached.
    (x0, y0), (x1, y1) = L['wires']['db']
    mx, my = (x0 + x1) / 2, (y0 + y1) / 2
    s.group(['<circle cx="%s" cy="%s" r="11" fill="%s" stroke="%s" stroke-width="1.6"/>'
             % (f(mx), f(my), t['bg'], t['deny']),
             s.text(mx, my + 4.5, '✕', 13, t['deny'], 700, 'middle'),
             s.text(mx + 18, my + 4.5, 'not run', 11.5, t['deny'], 700)],
            [(d + 6.3, d + SCENARIOS[3][0] - 0.4)])
    s.hop('socket', True, d + 6.5, 'denied', 'deny')
    s.hop('mcp', True, d + 7.2, 'denied', 'deny')


def answer(s, key, on, off):
    """The key the human types, shown in the card."""
    x, y, w, h = s.L['term']
    cx = x + 10 + (w - 20) - 46
    cy = s.card_y + 124
    colr = TERM['you'] if key == 'y' else TERM['denied']
    s.group([s.rect(cx, cy, 32, 20, 5, colr),
             s.text(cx + 16, cy + 15, key, 13, '#1a1814', 700, 'middle', mono=True)], [(on, off)])


def caption(s):
    t = s.t
    x, y, w, h = s.L['caption']
    box = s.L['caption']
    narrow = s.layout_name == 'narrow'
    seg = 34
    for i, (length, num, title, l1, l2) in enumerate(SCENARIOS):
        st = STARTS[i]
        # Progress: the scenario playing.
        px = x + w - 4 * (seg + 6) + i * (seg + 6)
        s.add(s.rect(px, y - 12, seg, 5, 2.5, t['border']))
        s.group([s.rect(px, y - 12, seg, 5, 2.5, t['req'])], [(st, st + length - 0.3)])
        lines = [s.text(x, y + 20, num + ' · ' + title, 17, t['text'], 700, box=box)]
        if narrow:
            words = (l1 + ' ' + l2).split()
            rows, cur = [], ''
            for wd in words:
                if width_of(cur + ' ' + wd, 13, False) > w - 8 and cur:
                    rows.append(cur)
                    cur = wd
                else:
                    cur = (cur + ' ' + wd).strip()
            rows.append(cur)
            for j, r in enumerate(rows):
                lines.append(s.text(x, y + 42 + 18 * j, r, 13, t['muted'], box=box))
        else:
            lines.append(s.text(x, y + 42, l1, 13, t['muted'], box=box))
            lines.append(s.text(x, y + 60, l2, 13, t['muted'], box=box))
        s.group(lines, [(st + 0.05, st + length - 0.35)])
    # The static frame's caption: the whole flow.
    still = []
    if narrow:
        for j, r in enumerate(STILL_TITLE_NARROW):
            still.append(s.text(x, y + 20 + 20 * j, r, 15, t['text'], 700, box=box))
        still.append(s.text(x, y + 84, 'Reads pass by an auto rule; a connection,', 13, t['muted'], box=box))
        still.append(s.text(x, y + 102, 'a write and DDL wait for you in lox run.', 13, t['muted'], box=box))
    else:
        still.append(s.text(x, y + 20, STILL_TITLE, 15, t['text'], 700, box=box))
        still.append(s.text(x, y + 42, STILL_SUB, 13, t['muted'], box=box))
    s.group(still, [], True)


def problems(s):
    """Layout problems of a drawn Svg: a text out of its box or the canvas,
    by the average glyph widths above (with a 4px margin)."""
    W, H = s.L['size']
    out = []
    for text, x0, x1, box in s.texts:
        bx, bw = (box[0], box[2]) if box else (0, W)
        if x0 < bx - 0.01 or x1 > bx + bw - 4 + 0.01:
            out.append('%s/%s: %r overflows [%s, %s]: [%s, %s]'
                       % (s.theme, s.layout_name, text, f(bx), f(bx + bw), f(x0), f(x1)))
    for wire, back, t0, t1, _ in s.hops:
        if not 0 <= t0 < t1 <= CYCLE:
            out.append('%s/%s: hop on %s at %s-%s outside the loop' % (s.theme, s.layout_name, wire, f(t0), f(t1)))
    return out


def outputs():
    """{relative path: content} of every generated file."""
    out = {}
    for layout, suffix in (('wide', ''), ('narrow', '-narrow')):
        for theme in ('light', 'dark'):
            out['assets/flow-%s%s.svg' % (theme, suffix)] = build(theme, layout)[0]
    return out


def main(argv):
    p = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    p.add_argument('--check', action='store_true', help='fail if the files differ from the generator')
    a = p.parse_args(argv)
    stale = []
    bad = [pr for layout in LAYOUTS for theme in THEMES for pr in problems(build(theme, layout)[1])]
    for pr in bad:
        print(pr, file=sys.stderr)
    if bad:
        return 1
    for rel, content in outputs().items():
        path = os.path.join(ROOT, rel)
        if a.check:
            try:
                with open(path, encoding='utf-8') as fh:
                    if fh.read() != content:
                        stale.append(rel)
            except FileNotFoundError:
                stale.append(rel)
        else:
            with open(path, 'w', encoding='utf-8') as fh:
                fh.write(content)
            print('wrote %s (%d bytes)' % (rel, len(content.encode('utf-8'))))
    if stale:
        print('out of date, run python3 tools/flow_svg.py: ' + ', '.join(stale), file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
