#!/bin/sh
# Tests of lockfamily.dev's identity (#17): the logos match
# tools/logo_svg.py, the unit tests (tokens, WCAG AA contrast, fonts, logos,
# no third-party request, docs), then the end-to-end test in a headless
# Chrome (skipped without one, unless SITE_E2E=required).
#
#   sh tests/site_test.sh
set -eu

here=$(cd "$(dirname "$0")/.." && pwd)
cd "$here"

python3 tools/logo_svg.py --check
python3 -m unittest discover -s tests -p 'test_site.py'
python3 tests/site_e2e.py
