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
# #38 (lockhub#193): the pages built from lockhub and locksql say that
# proxy_command is not supported under lox run (the error lox run prints),
# and give the [profiles.p.ssh] example that replaces it.
for page in hub/lox-run locks/locksql/docker; do
  grep -q 'proxy_command is not supported under lox run; reach the database through the built-in ssh bastion' "$site/docs/$page/index.html" ||
    { echo "docs/$page: does not say proxy_command is unsupported under lox run" >&2; exit 1; }
  grep -q 'profiles.prod.ssh' "$site/docs/$page/index.html" ||
    { echo "docs/$page: no [profiles.p.ssh] example" >&2; exit 1; }
done
echo "proxy_command: unsupported under lox run, on both pages"
python3 tests/docs_e2e.py "$site"
