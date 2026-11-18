"""Unit tests of the demo (assets/demo-*.svg, tools/demo_svg.py).

    python3 -m unittest tests.test_demo_svg

The demo is drawn from the captures of a real run (tools/demo_capture/):
these tests check that the files are up to date, self-contained and
accessible, that every captured line is in the drawing unchanged, that the
four steps are there, and that the README shows it under the tagline.
"""

import os
import re
import sys
import unittest
import xml.etree.ElementTree as ET

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tools'))
import demo_svg  # noqa: E402

NS = '{http://www.w3.org/2000/svg}'


def read(rel):
    with open(os.path.join(ROOT, rel), encoding='utf-8') as f:
        return f.read()


def words(svg):
    """Every text of the drawing, spaces dropped (runs are placed word by word)."""
    root = ET.fromstring(svg)
    return re.sub(r'\s+', '', ''.join(''.join(t.itertext()) for t in root.iter(NS + 'text')))


def squeeze(s):
    return re.sub(r'\s+', '', s)


class Files(unittest.TestCase):
    def test_up_to_date(self):
        for rel, theme in demo_svg.FILES.items():
            self.assertEqual(read(rel), demo_svg.build(theme), rel + ': run python3 tools/demo_svg.py')

    def test_size(self):
        for rel in demo_svg.FILES:
            self.assertLess(len(read(rel).encode('utf-8')), 200 * 1024, rel)

    def test_self_contained(self):
        # Renders as an <img> on github.com: no script, no external resource.
        for rel in demo_svg.FILES:
            for bad in ('<script', 'foreignObject', 'href=', '@import', 'url('):
                self.assertNotIn(bad, read(rel), rel)

    def test_accessible(self):
        for rel in demo_svg.FILES:
            root = ET.fromstring(read(rel))
            self.assertEqual(root.get('role'), 'img', rel)
            self.assertEqual(root.get('aria-labelledby'), 'demo-title demo-desc', rel)
            desc = root.find(NS + 'desc').text
            for w in ('Step 1', 'Step 2', 'Step 3', 'Step 4', '<redacted>', 'UPDATE', 'press y', 'lox audit'):
                self.assertIn(w, desc, rel)

    def test_reduced_motion(self):
        for rel in demo_svg.FILES:
            svg = read(rel)
            self.assertIn('@media (prefers-reduced-motion:reduce){.a{animation:none!important}}', svg, rel)
            for m in re.finditer(r'class="([^"]*\bk\d+\b[^"]*)"', svg):
                self.assertIn('a', m.group(1).split(), rel)

    def test_duration(self):
        # The ticket asks for 30 to 45 seconds.
        self.assertTrue(30 <= demo_svg.LOOP <= 45)
        self.assertIn('%gs linear infinite' % demo_svg.LOOP, read('assets/demo-light.svg'))


class RealText(unittest.TestCase):
    """Nothing of a captured screen is reworded."""

    def setUp(self):
        self.words = words(read('assets/demo-light.svg'))

    def test_lox_run_screens(self):
        for i in range(5):
            rows = demo_svg.plain(demo_svg.parse_ansi(demo_svg.read('lox-run-s%d.ansi' % i)))
            for row in rows:
                self.assertIn(squeeze(row), self.words, 'lox-run-s%d: %s' % (i, row))

    def test_lox_audit(self):
        for row in demo_svg.plain(demo_svg.parse_ansi(demo_svg.read('lox-audit.ansi'))):
            self.assertIn(squeeze(row), self.words, row)

    def test_agent_results(self):
        for name in ('agent-a2-run.txt', 'agent-a4-pending.txt', 'agent-a5-done.txt'):
            for line in demo_svg.read(name).splitlines():
                self.assertIn(squeeze(line), self.words, name + ': ' + line)
        for name in ('agent-a1-plan.txt', 'agent-a3-plan.txt'):
            for line in demo_svg.read(name).splitlines():
                if line.split(' ')[0] in ('sql', 'class', 'verdict'):
                    self.assertIn(squeeze(line), self.words, name + ': ' + line)

    def test_four_steps(self):
        # The masked read, the held write, the approval, the audit line.
        for w in ('4812<redacted><redacted>89.90pending', 'auto:read✓', 'Pendinghumanapproval:ticket',
                  '◆QUESTIONwriteonshop/shop', 'yapprovendeny', 'youpressy', '✔you✓', '(1rowsaffected)',
                  '$loxaudit', '✔human✓'):
            self.assertIn(w, self.words, w)
        self.assertEqual(len(demo_svg.STEPS), 4)

    def test_no_clear_value_on_the_hub_side(self):
        # lox run and lox audit never show the literals of the UPDATE.
        for name in ['lox-run-s%d.ansi' % i for i in range(5)] + ['lox-audit.ansi']:
            self.assertNotIn('refunded', demo_svg.read(name), name)


class Readme(unittest.TestCase):
    def test_under_the_tagline(self):
        readme = read('README.md')
        tagline = readme.index('<b>Harness security for AI agents.</b>')
        demo = readme.index('src="assets/demo-light.svg"')
        nav = readme.index('<a href="#quick-start">Quick start</a>')
        self.assertTrue(tagline < demo < nav)
        self.assertIn('srcset="assets/demo-dark.svg"', readme)
        alt = re.search(r'<img src="assets/demo-light.svg"[^>]*alt="([^"]+)"', readme).group(1)
        for w in ('Step 1', 'Step 2', 'Step 3', 'Step 4', '&lt;redacted&gt;', 'UPDATE', 'press y', 'lox audit'):
            self.assertIn(w, alt)


if __name__ == '__main__':
    unittest.main()
