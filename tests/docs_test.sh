#!/bin/sh
# Tests of lockfamily.dev/docs (#34): the generator's unit tests (offline),
# then the whole site built from the live sources of every repository, its
# local links, anchors and resources checked, install.sh served as it is,
# and the docs pages in a headless Chrome (skipped without one, unless
# SITE_E2E=required).
#
#   sh tests/docs_test.sh [SITE]
#
# PYTHON is a Python with docs-site/requirements.txt installed (python3 by
# default). SITE (default: _site) is where the site is built.
set -eu

here=$(cd "$(dirname "$0")/.." && pwd)
cd "$here"
py=${PYTHON:-python3}
site=${1:-_site}

"$py" -m unittest discover -s tests -p 'test_docs.py'
"$py" docs-site/build.py --out "$site"
"$py" docs-site/build.py --check "$site"
cmp install.sh "$site/install.sh"
echo "install.sh: served as it is"
python3 tests/docs_e2e.py "$site"
