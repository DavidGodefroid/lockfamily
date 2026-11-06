#!/usr/bin/env python3
"""Generate the Lock Family logos (assets/{mark,locksql,lockmq,lockfile,lockhttp,lea}.svg).

    python3 tools/logo_svg.py          # write them
    python3 tools/logo_svg.py --check  # fail if they differ from the generator

One drawing style (docs/identity.md): a 128 x 128 grid, ink strokes on a
paper fill, a 9px shackle, a 6px body outline, a 4.5px engraved glyph, round
caps. The family mark is the padlock whose body is a ticket stub; each Lock
is the same padlock with its source engraved in the body; lea is a sealed
container. Colours are the identity tokens (assets/tokens.css), light and
dark, switched by prefers-color-scheme inside the file so it works as an
<img> (no external resource). Python 3 standard library only.
"""

import argparse
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# (light, dark): --ink, --card, --ink-2 of assets/tokens.css.
INK = ('#1d1b17', '#ede6d6')
CARD = ('#fffcf5', '#25221b')
INK2 = ('#575146', '#b2a994')

STYLE = ('<style>.i{stroke:%s}.f{fill:%s}.p{fill:%s}.d{stroke:%s}'
         '@media (prefers-color-scheme:dark){.i{stroke:%s}.f{fill:%s}.p{fill:%s}.d{stroke:%s}}</style>'
         % (INK[0], INK[0], CARD[0], INK2[0], INK[1], INK[1], CARD[1], INK2[1]))
SHACKLE = '<path class="i" d="M40 58 V40 a24 24 0 0 1 48 0 V58" fill="none" stroke-width="9" stroke-linecap="round"/>'
BODY = '<rect class="p i" x="18" y="56" width="92" height="56" rx="6" stroke-width="6"/>'
TICKET = ('<path class="p i" d="M24 56 H104 a6 6 0 0 1 6 6 V76 a8 8 0 0 0 0 16 V106 a6 6 0 0 1 -6 6 H24 '
          'a6 6 0 0 1 -6 -6 V92 a8 8 0 0 0 0 -16 V62 a6 6 0 0 1 6 -6 Z" stroke-width="6" stroke-linejoin="round"/>')
G = 'fill="none" stroke-width="4.5" stroke-linecap="round" stroke-linejoin="round"'

LOGOS = {
    'mark': ('lock family',
             'One padlock for the family: its body is a ticket stub, a keyhole on one side, the perforation on the other.',
             SHACKLE + TICKET +
             '<path class="d" d="M86 66 V102" stroke-width="3" stroke-dasharray="1 6" stroke-linecap="round" fill="none"/>'
             '<circle class="f" cx="54" cy="79" r="7"/><path class="f" d="M50.5 83 L48.5 97 H59.5 L57.5 83 Z"/>'),
    'locksql': ('locksql', 'The family padlock; engraved in its body, a database cylinder.',
                SHACKLE + BODY +
                '<g class="i" %s><ellipse cx="64" cy="71" rx="16" ry="5"/><path d="M48 71 V95 a16 5 0 0 0 32 0 V71"/>'
                '<path d="M48 83 a16 5 0 0 0 32 0"/></g>' % G),
    'lockmq': ('lockmq', 'The family padlock; engraved in its body, a queue of messages.',
               SHACKLE + BODY +
               '<rect class="f" x="31" y="77" width="14" height="14" rx="2"/>'
               '<g class="i" %s><rect x="51" y="77" width="14" height="14" rx="2"/>'
               '<rect x="71" y="77" width="14" height="14" rx="2"/>'
               '<path d="M90 84 H98 M94 80 L98 84 L94 88"/></g>' % G),
    'lockfile': ('lockfile', 'The family padlock; engraved in its body, a page with a folded corner.',
                 SHACKLE + BODY +
                 '<g class="i" %s><path d="M51 67 H71 L79 75 V101 H51 Z"/><path d="M71 67 V75 H79"/>'
                 '<path d="M57 84 H72 M57 92 H67"/></g>' % G),
    'lockhttp': ('lockhttp', 'The family padlock; engraved in its body, a globe.',
                 SHACKLE + BODY +
                 '<g class="i" %s><circle cx="64" cy="84" r="17"/><ellipse cx="64" cy="84" rx="7" ry="17"/>'
                 '<path d="M47 84 H81"/></g>' % G),
    'lea': ('lea', 'A sealed container drawn in the family style: three agents inside, one waiting for you.',
            '<rect class="p i" x="14" y="14" width="100" height="100" rx="14" stroke-width="6"/>'
            '<g fill="none" stroke-width="6" stroke-linecap="round"><path class="i" d="M56 44 H92"/>'
            '<path class="i" d="M56 64 H84"/><path class="d" d="M56 84 H88"/></g>'
            '<circle class="f" cx="38" cy="44" r="6"/><circle class="f" cx="38" cy="64" r="6"/>'
            '<circle class="i" cx="38" cy="84" r="5" fill="none" stroke-width="3"/>'),
}


def outputs():
    out = {}
    for name, (label, desc, body) in LOGOS.items():
        out['assets/%s.svg' % name] = (
            '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 128 128" width="128" height="128" '
            'role="img" aria-label="%s logo">\n<title>%s</title>\n<desc>%s</desc>\n%s\n%s\n</svg>\n'
            % (label, label, desc, STYLE, body))
    return out


def main(argv):
    p = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    p.add_argument('--check', action='store_true', help='fail if the files differ from the generator')
    a = p.parse_args(argv)
    stale = []
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
            print('wrote %s' % rel)
    if stale:
        print('out of date, run python3 tools/logo_svg.py: ' + ', '.join(stale), file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
