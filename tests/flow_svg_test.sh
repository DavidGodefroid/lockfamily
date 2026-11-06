#!/bin/sh
# Tests of the animated request flow (assets/flow-*.svg): the files match
# tools/flow_svg.py, the unit tests (accessibility, size, layout, the flow
# lockhub ships, README and site wiring), then the end-to-end test in a
# headless Chrome (skipped without one, unless FLOW_E2E=required).
#
#   sh tests/flow_svg_test.sh
set -eu

here=$(cd "$(dirname "$0")/.." && pwd)
cd "$here"

python3 tools/flow_svg.py --check
python3 -m unittest discover -s tests -p 'test_*.py'
python3 tests/flow_svg_e2e.py
