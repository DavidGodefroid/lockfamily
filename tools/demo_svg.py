#!/usr/bin/env python3
"""Generate the animated demo of the README and the site.

    python3 tools/demo_svg.py          # write assets/demo-light.svg, demo-dark.svg
    python3 tools/demo_svg.py --check  # fail if they differ from the generator

One request, end to end, in 38 seconds: an agent on the left, `lox run` on
the right, your shell below.

  1. a read: the personal data comes back masked (<redacted>);
  2. an UPDATE: held, the agent gets a pending ticket;
  3. the approval: you press y in lox run, outside the agent;
  4. the audit: `lox audit` lists the exchange and who decided it.

This is not a screen recording: it is drawn from the captures of one real
run, kept in tools/demo_capture/ and replayed here cell by cell.

  - lox-run-s0..s4.ansi  the `lox run` screen (76 columns) before the read,
                         after it, with the question card, once approved,
                         once the write ran: `tmux capture-pane -p -e`
  - lox-audit.ansi       the whole output of `lox audit` (100 columns)
  - agent-a*.txt         the text each MCP tool call returned to the agent
                         (`locksql mcp`: locksql_plan, locksql_run)
  - versions.txt         the releases that ran (lox, lockhub, locksql)
  - capture.sh, mcp_call.py  how the captures were made

What is drawn and not captured: the window frames and their titles, the
four step captions, the sentence the user types, the "● tool" lines that
name each MCP call, and the "$ lox audit" prompt. The colours are the
family's palette, mapped from the terminal's ANSI colours. Of the plan
output only the sql, class and verdict lines are shown; long lines are
wrapped at spaces. The agent ran on the host, not in lea:
the tool calls were sent to `locksql mcp` by tools/demo_capture/mcp_call.py.

The animation is CSS only (no script), so it plays in GitHub's README and
on lockfamily.dev; under prefers-reduced-motion it stops on the last frame.
Every word is real <text>. Python 3 standard library only; deterministic.
"""

import argparse
import os
import re
import sys
import textwrap
import unicodedata
from xml.sax.saxutils import escape

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
CAP = os.path.join(HERE, 'demo_capture')

SANS = ('-apple-system, BlinkMacSystemFont, &quot;Segoe UI&quot;, Roboto, '
        '&quot;Helvetica Neue&quot;, Arial, &quot;Noto Sans&quot;, sans-serif')
MONO = ('ui-monospace, SFMono-Regular, Menlo, Consolas, &quot;DejaVu Sans Mono&quot;, '
        '&quot;Liberation Mono&quot;, monospace')

LOOP = 38.0          # seconds
END = 37.3           # the agent's lines and the audit fade out, then the loop restarts
FS = 13              # terminal font size
CW = 7.8             # one terminal cell
LH = 18              # one terminal row
PAD = 14             # inside a window
BAR = 28             # a window's title bar
W = 1200
M = 16               # outer margin and gutter

RUN_COLS = 76        # the captured width of lox run
AUDIT_COLS = 100     # the captured width of lox audit
RUN_W = RUN_COLS * CW + 2 * PAD
AGENT_W = W - 3 * M - RUN_W
AGENT_COLS = int((AGENT_W - 2 * PAD) // CW)

# The identity's palette (assets/tokens.css, docs/identity.md). The windows
# follow the theme: paper in light, carbon in dark.
THEMES = {
    'light': {
        'bg': '#f4efe4', 'win': '#fffcf5', 'bar': '#e9e2d2', 'border': '#b9af98',
        'text': '#1d1b17', 'dim': '#575146', 'title': '#1d1b17', 'muted': '#575146',
        'green': '#2d6a35', 'yellow': '#8a5300', 'cyan': '#0e6158', 'red': '#a8201a',
        'blue': '#2a55a8', 'step_on': '#1f4a9c', 'step_bg': '#fffcf5', 'key': '#2d6a35',
    },
    'dark': {
        'bg': '#16140f', 'win': '#0e0d0a', 'bar': '#24211b', 'border': '#4a4438',
        'text': '#ede6d6', 'dim': '#b2a994', 'title': '#ede6d6', 'muted': '#b2a994',
        'green': '#7fcf8a', 'yellow': '#e8b860', 'cyan': '#6fd9c8', 'red': '#ff9384',
        'blue': '#89b4fa', 'step_on': '#89b4fa', 'step_bg': '#25221b', 'key': '#7fcf8a',
    },
}
ANSI_FG = {30: 'win', 31: 'red', 32: 'green', 33: 'yellow', 34: 'blue', 35: 'blue', 36: 'cyan',
           37: 'text', 90: 'dim', 91: 'red', 92: 'green', 93: 'yellow', 94: 'blue', 95: 'blue',
           96: 'blue', 97: 'text'}
ANSI_BG = {40: 'text', 41: 'red', 42: 'green', 43: 'yellow', 44: 'blue', 45: 'blue', 46: 'cyan',
           47: 'text'}

# (number, caption, start, end) of the four steps.
STEPS = [
    ('1', 'A read: personal data comes back masked', 2.0, 9.0),
    ('2', 'A write: held, the agent gets a ticket', 9.0, 16.0),
    ('3', 'You approve in lox run, outside the agent', 16.0, 25.0),
    ('4', 'lox audit lists who decided', 25.0, END),
]
USER_ASKS = 'Refund the pending order.'

# When each lox run screen replaces the one before, and when the key shows.
T_READ, T_ASK, T_KEY, T_YES, T_RAN = 6.0, 12.5, 20.0, 21.0, 23.5
T_AUDIT = 26.0


def read(name):
    with open(os.path.join(CAP, name), encoding='utf-8') as f:
        return f.read()


def cells(s):
    """Terminal cells a string takes."""
    return sum(2 if unicodedata.east_asian_width(c) in 'WF' else 1 for c in s)


def parse_ansi(data):
    """An ANSI capture as rows of runs: (col, text, fg, bg, bold, dim, italic).

    fg and bg are palette keys or None. The SGR state carries from one row
    to the next, as tmux writes it.
    """
    rows = []
    st = {'fg': None, 'bg': None, 'bold': False, 'dim': False, 'italic': False, 'inv': False}
    for line in data.split('\n'):
        runs, col = [], 0
        for part in re.split(r'(\x1b\[[0-9;]*m)', line):
            if part.startswith('\x1b['):
                for code in [int(c or 0) for c in part[2:-1].split(';')]:
                    if code == 0:
                        st.update(fg=None, bg=None, bold=False, dim=False, italic=False, inv=False)
                    elif code == 1:
                        st['bold'] = True
                    elif code == 2:
                        st['dim'] = True
                    elif code == 3:
                        st['italic'] = True
                    elif code == 7:
                        st['inv'] = True
                    elif code == 22:
                        st['bold'] = st['dim'] = False
                    elif code == 39:
                        st['fg'] = None
                    elif code == 49:
                        st['bg'] = None
                    elif code in ANSI_FG:
                        st['fg'] = ANSI_FG[code]
                    elif code in ANSI_BG:
                        st['bg'] = ANSI_BG[code]
            elif part:
                fg, bg = st['fg'], st['bg']
                if st['inv']:
                    fg, bg = bg or 'win', fg or 'text'
                runs.append((col, part, fg, bg, st['bold'], st['dim'], st['italic']))
                col += cells(part)
        rows.append(runs)
    while rows and not any(r[1].strip() for r in rows[-1]):
        rows.pop()
    return rows


def plain(rows):
    return [''.join(r[1] for r in row) for row in rows]


def wrap(s, width):
    """Wrap at spaces, as the agent's interface does."""
    lines = textwrap.wrap(s, width, break_long_words=True, break_on_hyphens=False, drop_whitespace=True,
                          replace_whitespace=False)
    return lines or ['']


def tool_text(name, keep=None):
    """A tool result's lines; keep: only the lines starting with these words."""
    lines = read(name).rstrip('\n').split('\n')
    if keep:
        lines = [x for x in lines if x.split(' ')[0] in keep]
    if any('\t' in x for x in lines):
        # A result table: tab-separated as the tool returns it, aligned here.
        table = [x.split('\t') for x in lines if '\t' in x]
        widths = [max(len(r[i]) for r in table) for i in range(len(table[0]))]
        lines = ['  '.join(c.ljust(w) for c, w in zip(x.split('\t'), widths)).rstrip() if '\t' in x else x
                 for x in lines]
    return lines


def agent_script():
    """The agent window: (time, kind, text) per row, top to bottom.

    kind: user, tool (the MCP call, drawn), out (captured text), blank.
    """
    ticket = re.search(r'ticket (\w+)', read('agent-a4-pending.txt')).group(1)
    plan = ('sql', 'class', 'verdict')
    blocks = [
        (1.0, 'user', ['> ' + USER_ASKS]),
        (2.6, 'tool', ['● locksql_plan']),
        (3.0, 'out', tool_text('agent-a1-plan.txt', plan)),
        (4.6, 'tool', ['● locksql_run']),
        (T_READ, 'out', tool_text('agent-a2-run.txt')),
        (9.4, 'tool', ['● locksql_plan']),
        (9.8, 'out', tool_text('agent-a3-plan.txt', plan)),
        (11.6, 'tool', ['● locksql_run']),
        (T_ASK, 'out', tool_text('agent-a4-pending.txt')),
        (22.4, 'tool', ['● locksql_run  ticket ' + ticket]),
        (T_RAN, 'out', tool_text('agent-a5-done.txt')),
    ]
    rows = []
    for t, kind, lines in blocks:
        if kind in ('tool',) and rows:
            rows.append((t, 'blank', ''))
        for line in lines:
            indent = '  ' if kind == 'out' else ''
            for piece in wrap(line, AGENT_COLS - len(indent)):
                rows.append((t, kind, indent + piece))
    return rows


class Svg:
    def __init__(self, theme):
        self.c = THEMES[theme]
        self.css = []
        self.out = []
        self.n = 0

    def anim(self, frames):
        """Keyframes [(seconds, declarations)] -> the classes of an animated element."""
        self.n += 1
        name = 'k%d' % self.n
        steps = ' '.join('%.2f%%{%s}' % (t / LOOP * 100, d) for t, d in frames)
        self.css.append('@keyframes %s{%s}' % (name, steps))
        self.css.append('.%s{animation:%s %gs linear infinite}' % (name, name, LOOP))
        return 'a ' + name

    def window(self, t0, t1, fade=0.15):
        """Visible from t0 to t1 only."""
        frames = [(0, 'opacity:0')]
        if t0 > 0:
            frames += [(t0, 'opacity:0'), (t0 + fade, 'opacity:1')]
        else:
            frames = [(0, 'opacity:1')]
        if t1 < LOOP:
            frames += [(t1, 'opacity:1'), (min(LOOP, t1 + fade), 'opacity:0'), (LOOP, 'opacity:0')]
        else:
            frames += [(LOOP, 'opacity:1')]
        return self.anim(frames)

    def add(self, s):
        self.out.append(s)

    def frame(self, x, y, w, h, title, note):
        c = self.c
        self.add('<rect x="%g" y="%g" width="%g" height="%g" rx="6" fill="%s" stroke="%s"/>'
                 % (x, y, w, h, c['win'], c['border']))
        self.add('<path d="M%g %gh%gv%gh-%gz" fill="%s"/>' % (x + 1, y + BAR, w - 2, 0.5, w - 2, c['border']))
        self.add('<rect x="%g" y="%g" width="%g" height="%g" rx="5" fill="%s"/>'
                 % (x + 1, y + 1, w - 2, BAR - 1, c['bar']))
        self.add('<text x="%g" y="%g" font-family="%s" font-size="13" font-weight="600" fill="%s">%s'
                 '<tspan font-weight="400" fill="%s">  ·  %s</tspan></text>'
                 % (x + PAD, y + 19, SANS, c['title'], escape(title), c['muted'], escape(note)))

    def run(self, x, y, text, fg=None, bold=False, dim=False, italic=False, bg=None):
        """One run of terminal cells at the baseline y, starting at pixel x."""
        c = self.c
        n = cells(text)
        if bg:
            self.add('<rect x="%g" y="%g" width="%g" height="%d" fill="%s"/>'
                     % (x, y - LH + 5, n * CW, LH, c[bg]))
        if not text.strip():
            return
        # Words more than one space apart are placed one by one: a browser
        # collapses the spaces of an SVG text.
        parts = re.split(r'( {2,})', text)
        if len(parts) > 1:
            for part in parts:
                if part.strip():
                    self.run(x, y, part, fg, bold, dim, italic)
                x += cells(part) * CW
            return
        lead = len(text) - len(text.lstrip(' '))
        text = text.strip(' ')
        x += lead * CW
        n = cells(text)
        colour = c[fg] if fg else (c['dim'] if dim else c['text'])
        if fg and dim and not bold:
            colour = c[fg]
        attrs = ''
        if bold:
            attrs += ' font-weight="700"'
        if italic:
            attrs += ' font-style="italic"'
        if dim and fg and not bold:
            attrs += ' opacity="0.8"'
        length = ' textLength="%g" lengthAdjust="spacingAndGlyphs"' % (n * CW) if n > 1 else ''
        self.add('<text x="%g" y="%g" fill="%s"%s%s>%s</text>' % (x, y, colour, attrs, length, escape(text)))

    def screen(self, x, y, rows):
        for i, row in enumerate(rows):
            for col, text, fg, bg, bold, dim, italic in row:
                self.run(x + col * CW, y + (i + 1) * LH, text, fg, bold, dim, italic, bg)


def build(theme):
    s = Svg(theme)
    c = s.c
    screens = [parse_ansi(read('lox-run-s%d.ansi' % i)) for i in range(5)]
    audit = parse_ansi(read('lox-audit.ansi'))
    agent = agent_script()

    rows = max(len(agent), max(len(x) for x in screens)) + 1
    steps_y = M
    steps_h = 34
    top = steps_y + steps_h + M
    pane_h = BAR + PAD + rows * LH
    audit_y = top + pane_h + M
    audit_h = BAR + PAD + (len(audit) + 2) * LH
    H = audit_y + audit_h + M

    s.add('<rect width="%d" height="%d" rx="10" fill="%s"/>' % (W, H, c['bg']))

    # The four steps: all readable at any time, the current one inked.
    sw = (W - 2 * M - 3 * 8) / 4
    for i, (num, label, t0, t1) in enumerate(STEPS):
        x = M + i * (sw + 8)
        s.add('<rect x="%g" y="%g" width="%g" height="%d" rx="4" fill="%s" stroke="%s"/>'
              % (x, steps_y, sw, steps_h, c['step_bg'], c['border']))
        on = s.anim([(0, 'opacity:0'), (t0, 'opacity:0'), (t0 + 0.2, 'opacity:1'),
                     (t1, 'opacity:1'), (min(LOOP, t1 + 0.2), 'opacity:0'), (LOOP, 'opacity:0')])
        s.add('<rect class="%s" opacity="%d" x="%g" y="%g" width="%g" height="%d" rx="4" fill="none" '
              'stroke="%s" stroke-width="2"/>' % (on, 1 if i == len(STEPS) - 1 else 0, x, steps_y, sw, steps_h,
                                                 c['step_on']))
        s.add('<text x="%g" y="%g" font-family="%s" font-size="13" fill="%s">'
              '<tspan font-weight="700" fill="%s">%s</tspan>  %s</text>'
              % (x + 10, steps_y + 22, SANS, c['text'], c['step_on'], num, escape(label)))

    # The agent, on the left.
    ax, rx = M, M + AGENT_W + M
    s.frame(ax, top, AGENT_W, pane_h, 'agent', 'an MCP client, with no password and no connection')
    s.add('<g font-family="%s" font-size="%d" xml:space="preserve">' % (MONO, FS))
    for i, (t, kind, text) in enumerate(agent):
        if kind == 'blank':
            continue
        y = top + BAR + PAD + (i + 1) * LH - 6
        s.add('<g class="%s" opacity="1">' % s.window(t, END))
        if kind == 'user':
            s.run(ax + PAD, y, text, bold=True)
        elif kind == 'tool':
            s.run(ax + PAD, y, text[:1], fg='blue')
            s.run(ax + PAD + CW, y, text[1:], bold=True)
        else:
            masked = [m.span() for m in re.finditer(r'<redacted>', text)]
            pos = 0
            for a, b in masked:
                s.run(ax + PAD + pos * CW, y, text[pos:a], dim=True)
                s.run(ax + PAD + a * CW, y, text[a:b], fg='cyan', bold=True)
                pos = b
            pending = text.strip().startswith('Pending human approval') or 'End your turn' in text
            s.run(ax + PAD + pos * CW, y, text[pos:], fg='yellow' if pending else None, dim=not pending)
        s.add('</g>')
    s.add('</g>')

    # lox run, on the right: one captured screen at a time.
    s.frame(rx, top, RUN_W, pane_h, 'lox run', 'your terminal, outside the agent')
    times = [0, T_READ, T_ASK, T_YES, T_RAN, LOOP]
    s.add('<g font-family="%s" font-size="%d" xml:space="preserve">' % (MONO, FS))
    for i, rows_i in enumerate(screens):
        last = i == len(screens) - 1
        s.add('<g class="%s" opacity="%d">' % (s.window(times[i], times[i + 1], 0.05), 1 if last else 0))
        s.screen(rx + PAD, top + BAR + PAD - 6, rows_i)
        s.add('</g>')
    s.add('</g>')
    # The key you press, beside the question card.
    card = next(i for i, x in enumerate(plain(screens[2])) if 'y approve' in x)
    kx, ky = rx + PAD + 2 * CW, top + BAR + PAD - 6 + (card + 2) * LH + 8
    s.add('<g class="%s" opacity="0">' % s.window(T_KEY, T_YES + 0.6))
    s.add('<rect x="%g" y="%g" width="150" height="26" rx="5" fill="%s"/>' % (kx, ky, c['key']))
    s.add('<text x="%g" y="%g" font-family="%s" font-size="13" font-weight="700" fill="%s" '
          'text-anchor="middle">you press y</text>' % (kx + 75, ky + 18, SANS, c['win']))
    s.add('</g>')

    # Your shell, below: lox audit.
    s.frame(M, audit_y, W - 2 * M, audit_h, 'your shell', 'the same exchange, afterwards')
    s.add('<g font-family="%s" font-size="%d" xml:space="preserve">' % (MONO, FS))
    y0 = audit_y + BAR + PAD - 6
    s.add('<g class="%s" opacity="1">' % s.window(T_AUDIT - 0.8, END))
    s.run(M + PAD, y0 + LH, '$', dim=True)
    s.run(M + PAD + 2 * CW, y0 + LH, 'lox audit', bold=True)
    s.add('</g>')
    s.add('<g class="%s" opacity="1">' % s.window(T_AUDIT, END))
    s.screen(M + PAD, y0 + LH, audit)
    s.add('</g>')
    s.add('</g>')

    title = 'One request through the Lock Family: masked read, held write, approval, audit'
    desc = ('An agent on the left, lox run on the right, your shell below. '
            'Step 1: the agent reads the pending order through locksql; the customer name and email come back '
            'as <redacted>, and lox run logs the read as approved by an auto rule. '
            'Step 2: the agent asks for an UPDATE of the order status; it gets a pending ticket, and lox run '
            'shows a question card with the statement, its values masked. '
            'Step 3: you press y in lox run, outside the agent; the agent runs the write with the decided '
            'ticket and one row changes. '
            'Step 4: lox audit lists both exchanges, the read decided by an auto rule and the write by a human.')
    head = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 %d %d" width="%d" height="%d" role="img" '
            'aria-labelledby="demo-title demo-desc">\n<title id="demo-title">%s</title>\n'
            '<desc id="demo-desc">%s</desc>\n<style>%s\n'
            '@media (prefers-reduced-motion:reduce){.a{animation:none!important}}</style>\n'
            % (W, H, W, H, escape(title), escape(desc), '\n'.join(s.css)))
    return head + '\n'.join(s.out) + '\n</svg>\n'


FILES = {'assets/demo-light.svg': 'light', 'assets/demo-dark.svg': 'dark'}


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--check', action='store_true', help='fail if the files differ from the generator')
    args = ap.parse_args()
    bad = 0
    for rel, theme in FILES.items():
        svg = build(theme)
        path = os.path.join(ROOT, rel)
        if args.check:
            try:
                with open(path, encoding='utf-8') as f:
                    same = f.read() == svg
            except OSError:
                same = False
            if not same:
                print('%s is not up to date: run python3 tools/demo_svg.py' % rel, file=sys.stderr)
                bad = 1
        else:
            with open(path, 'w', encoding='utf-8') as f:
                f.write(svg)
            print('%s: %d bytes' % (rel, len(svg.encode('utf-8'))))
    sys.exit(bad)


if __name__ == '__main__':
    main()
