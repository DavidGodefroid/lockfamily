"""Unit tests of tools/flow_svg.py and of the SVGs it writes.

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

NS = '{http://www.w3.org/2000/svg}'
FILES = ['assets/flow-light.svg', 'assets/flow-dark.svg',
         'assets/flow-light-narrow.svg', 'assets/flow-dark-narrow.svg']


def read(rel):
    with open(os.path.join(ROOT, rel), encoding='utf-8') as fh:
        return fh.read()


def built():
    for layout in flow_svg.LAYOUTS:
        for theme in flow_svg.THEMES:
            yield (theme, layout) + flow_svg.build(theme, layout)


def scenario_of(t):
    for i, start in enumerate(flow_svg.STARTS):
        if start <= t < start + flow_svg.SCENARIOS[i][0]:
            return i
    raise AssertionError('time %s outside every scenario' % t)


class Files(unittest.TestCase):
    def test_up_to_date(self):
        for rel, content in flow_svg.outputs().items():
            self.assertEqual(read(rel), content, '%s: run python3 tools/flow_svg.py' % rel)
        self.assertEqual(sorted(flow_svg.outputs()), sorted(FILES))

    def test_deterministic(self):
        self.assertEqual(flow_svg.outputs(), flow_svg.outputs())

    def test_size(self):
        for rel in FILES:
            self.assertLess(os.path.getsize(os.path.join(ROOT, rel)), 200 * 1024, rel)

    def test_well_formed_and_accessible(self):
        for rel in FILES:
            root = ET.fromstring(read(rel))
            self.assertEqual(root.tag, NS + 'svg', rel)
            self.assertEqual(root.get('role'), 'img', rel)
            self.assertEqual(root.get('aria-labelledby'), 'flow-title flow-desc', rel)
            title = root.find(NS + 'title')
            desc = root.find(NS + 'desc')
            self.assertEqual(title.get('id'), 'flow-title', rel)
            self.assertEqual(desc.get('id'), 'flow-desc', rel)
            for w in ('never talks to the hub', 'never sees a query or a result in clear', 'lox run',
                      'auto rule', 'connect', 'UPDATE', 'DELETE', 'outside the harness'):
                self.assertIn(w, desc.text, rel)

    def test_self_contained(self):
        # Renders as an <img> on github.com: no script, no external
        # resource, no foreignObject (its HTML does not render there).
        for rel in FILES:
            svg = read(rel)
            for bad in ('<script', 'foreignObject', 'href=', '@import', 'url('):
                self.assertNotIn(bad, svg, rel)

    def test_reduced_motion(self):
        for rel in FILES:
            svg = read(rel)
            self.assertIn('@media (prefers-reduced-motion:reduce){.a{animation:none!important}}', svg, rel)
            # Every animated element carries the class the media query stops.
            for m in re.finditer(r'class="([^"]*\bk\d+\b[^"]*)"', svg):
                self.assertIn('a', m.group(1).split(), rel)

    def test_real_text(self):
        for rel in FILES:
            root = ET.fromstring(read(rel))
            words = ' '.join(''.join(t.itertext()) for t in root.iter(NS + 'text'))
            for _, num, title, _, _ in flow_svg.SCENARIOS:
                self.assertIn(num + ' · ' + title, words, rel)
            for label, _, _ in [(p[2], 0, 0) for p in flow_svg.PROPS]:
                self.assertIn(label, words, rel)
            for w in ('agent', 'Lock client', 'lock', 'hub', 'lox run', 'AUTO', 'outside the harness',
                      'Database', 'RabbitMQ', 'files', 'HTTP', 'logs'):
                self.assertIn(w, words, rel)
            self.assertNotIn('<path d="M0', read(rel), rel)  # no outlined text

    def test_light_and_dark(self):
        light, dark = read(FILES[0]), read(FILES[1])
        self.assertIn(flow_svg.THEMES['light']['bg'], light)
        self.assertNotIn(flow_svg.THEMES['dark']['bg'], light)
        self.assertIn(flow_svg.THEMES['dark']['bg'], dark)


class Layout(unittest.TestCase):
    def test_no_overflow(self):
        for theme, layout, _, s in built():
            self.assertEqual(flow_svg.problems(s), [], (theme, layout))

    def test_static_frame(self):
        # Under reduced motion the base opacities show: the flow caption and
        # the whole feed, no packet, no question card, no scenario caption.
        for _, layout, svg, _ in built():
            self.assertRegex(svg, r'<g class="a k\d+" opacity="1"><text[^>]*>agent → Lock client')
            for decision in ('auto ✓', '✔ you ✓', '✘ denied'):
                self.assertRegex(svg, r'<g class="a k\d+" opacity="1"><text[^>]*>.*' + decision, layout)
            for hidden in ('◆ QUESTION', '◆ asked', flow_svg.SCENARIOS[0][2]):
                self.assertNotRegex(svg, r'<g class="a k\d+" opacity="1">[^\n]*' + re.escape(hidden), layout)


class Flow(unittest.TestCase):
    """The animation tells the flow lockhub ships (lockhub#121)."""

    def setUp(self):
        self.s = flow_svg.build('light', 'wide')[1]
        self.by = [[] for _ in flow_svg.SCENARIOS]
        for h in sorted(self.s.hops, key=lambda h: h[2]):
            self.by[scenario_of(h[2])].append(h)

    def test_wires(self):
        # Five wires, none between the agent's harness and the hub.
        self.assertEqual(set(flow_svg.LAYOUTS['wide']['wires']), {'mcp', 'socket', 'ticket', 'tty', 'db'})
        for layout in flow_svg.LAYOUTS.values():
            self.assertEqual(set(layout['wires']), {'mcp', 'socket', 'ticket', 'tty', 'db'})

    def test_no_route_in_every_layout(self):
        # The crossed 'no route' marker between the harness and the hub, in
        # the wide and the narrow variant alike.
        for theme, layout, svg, s in built():
            nr = flow_svg.LAYOUTS[layout]['noroute']
            self.assertIsNotNone(nr, layout)
            self.assertIn('>no route</text>', svg, (theme, layout))
            self.assertIn('stroke="%s" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" '
                          'stroke-dasharray="4 5"' % flow_svg.THEMES[theme]['deny'], svg, (theme, layout))
            # It starts at the harness and ends on the hub's edge.
            hx, hy, hw, hh = flow_svg.LAYOUTS[layout]['harness']
            bx, by, bw, bh = flow_svg.LAYOUTS[layout]['hub']
            (x0, y0), (x1, y1) = nr['path'][0], nr['path'][-1]
            self.assertTrue(hx <= x0 <= hx + hw and hy <= y0 <= hy + hh, layout)
            self.assertTrue(x1 in (bx, bx + bw) and by <= y1 <= by + bh, layout)
            # The marker sits on the path, outside every box.
            mx, my = nr['mark']
            pts = nr['path']
            self.assertTrue(any(min(a[0], b[0]) <= mx <= max(a[0], b[0]) and min(a[1], b[1]) <= my <= max(a[1], b[1])
                                for a, b in zip(pts, pts[1:])), layout)
            for name in ('agent', 'client', 'lock', 'hub'):
                x, y, w, h = flow_svg.LAYOUTS[layout][name]
                self.assertFalse(x - 11 < mx < x + w + 11 and y - 11 < my < y + h + 11, (layout, name))

    def test_hub_card_wording(self):
        # lox run shows the masked request text: the hub holds masked
        # queries, never clear values.
        for theme, layout, svg, _ in built():
            self.assertIn('masked queries only, no clear values', svg, (theme, layout))
            self.assertNotIn('no query', svg, (theme, layout))

    def test_hops_inside_their_scenario(self):
        for wire, back, t0, t1, label in self.s.hops:
            self.assertEqual(scenario_of(t0), scenario_of(t1 - 1e-9), (wire, label))

    def test_no_overlap_on_a_wire(self):
        hops = sorted(self.s.hops, key=lambda h: h[2])
        for a, b in zip(hops, hops[1:]):
            if a[0] == b[0]:
                self.assertLessEqual(a[3], b[2] + 1e-9, (a, b))

    def test_hub_sees_no_clear_value(self):
        clear = re.compile(r'SELECT|UPDATE|DELETE|INSERT|@|rows?\b|\d')
        for wire, back, t0, t1, label in self.s.hops:
            if wire in ('ticket', 'tty'):
                self.assertNotRegex(label, clear, (wire, label))

    def test_every_request_goes_through_the_hub(self):
        # agent -> client -> socket -> lock -> ticket -> hub -> lox run, then
        # lox run -> hub -> signed decision -> lock, before the lock touches
        # its source.
        chain = [('mcp', False), ('socket', False), ('ticket', False), ('tty', False),
                 ('tty', True), ('ticket', True)]
        for i, hops in enumerate(self.by):
            got = [(h[0], h[1]) for h in hops]
            self.assertEqual(got[:6], chain, 'scenario %d' % (i + 1))
            decided = False
            for wire, back, _, _, label in hops:
                if (wire, back) == ('ticket', True):
                    decided = True
                if wire == 'db':
                    self.assertTrue(decided, 'scenario %d: the lock ran before a signed decision' % (i + 1))
                if wire == 'ticket' and not back:
                    decided = False
            self.assertEqual(got[-2:], [('socket', True), ('mcp', True)], 'scenario %d' % (i + 1))

    def test_scenarios(self):
        labels = [[h[4] for h in hops] for hops in self.by]
        # 1. a read decided by an auto rule.
        self.assertIn('auto', labels[0])
        # 2. a connect ticket answered y, then the read by the auto rule.
        self.assertIn('connect · primary', labels[1])
        self.assertIn('y', labels[1])
        self.assertIn('auto', labels[1])
        self.assertLess(labels[1].index('y'), labels[1].index('auto'))
        # 3. a write answered y, then run.
        self.assertIn('ticket · write', labels[2])
        self.assertIn('y', labels[2])
        self.assertIn('UPDATE', [h[4] for h in self.by[2] if h[0] == 'db'])
        # 4. a write answered n: the lock never reaches its source.
        self.assertIn('n', labels[3])
        self.assertNotIn('db', [h[0] for h in self.by[3]])
        self.assertEqual([h[4] for h in self.by[3]][-2:], ['denied', 'denied'])

    def test_lox_run_vocabulary(self):
        # The feed and the cards use lox run's own labels (lockhub
        # internal/loxrun/view.go).
        svg = flow_svg.build('dark', 'wide')[0]
        for w in ('auto ✓', '✔ you ✓', '✘ denied', '◆ asked', '◆ QUESTION connect on shop/primary',
                  '◆ QUESTION write on shop/primary', 'why asked: write is always asked',
                  'why asked: first connection to this', 'y approve', 'Shift+Tab', 'connected shop/replica'):
            self.assertIn(w, svg)


class Pages(unittest.TestCase):
    """README.md and index.html show the right file for the theme and width."""

    def check(self, rel):
        page = read(rel)
        m = re.search(r'<picture>(.*?)</picture>', page, re.S)
        self.assertIsNotNone(m, rel)
        pic = m.group(1)
        sources = re.findall(r'<source media="([^"]+)" srcset="([^"]+)"', pic)
        self.assertEqual(sources, [
            ('(max-width: 640px) and (prefers-color-scheme: dark)', 'assets/flow-dark-narrow.svg'),
            ('(max-width: 640px)', 'assets/flow-light-narrow.svg'),
            ('(prefers-color-scheme: dark)', 'assets/flow-dark.svg'),
        ], rel)
        img = re.search(r'<img src="assets/flow-light.svg"[^>]* alt="([^"]+)"', pic)
        self.assertIsNotNone(img, rel)
        for w in ('agent', 'Lock client', 'socket', 'masked ticket', 'hub', 'lox run', 'signs',
                  'never talks to the hub', 'never sees a query or a result in clear'):
            self.assertIn(w, img.group(1), rel)
        for _, src in sources:
            self.assertTrue(os.path.exists(os.path.join(ROOT, src)), src)

    def test_readme(self):
        self.check('README.md')
        readme = read('README.md')
        # Under the pitch, before the family table.
        self.assertLess(readme.index('<picture>'), readme.index('## The family'))
        self.assertLess(readme.index('> signed decision'), readme.index('<picture>'))

    def test_site(self):
        self.check('index.html')
        site = read('index.html')
        principle = site[site.index('id="principle"'):site.index('id="fit"')]
        self.assertIn('<figure class="flow-anim">', principle)
        self.assertIn('.flow-anim img', read('assets/style.css'))


if __name__ == '__main__':
    unittest.main()
