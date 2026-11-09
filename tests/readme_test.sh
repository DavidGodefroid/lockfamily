#!/bin/sh
# Tests of the README and the docs it links to: the first screen pitches the
# Lock Family and links to the site, site details stay in "About this repo",
# every relative link and anchor resolves, the quick start matches
# install.sh, the content moved out of the README is still there, and the
# lox run reference (README docs and index.html) lists its real flags.
# No network.
#
#   sh tests/readme_test.sh
set -u

here=$(cd "$(dirname "$0")/.." && pwd)
cd "$here" || exit 1

fails=0
runs=0
pass() { runs=$((runs + 1)); printf 'ok   %s\n' "$1"; }
fail() { runs=$((runs + 1)); fails=$((fails + 1)); printf 'FAIL %s\n' "$1"; }
check() { if eval "$2"; then pass "$1"; else fail "$1"; fi; }

# has FILE STRING: FILE contains STRING, as a fixed string.
has() { grep -qF -- "$2" "$1"; }

# slug HEADING: the anchor GitHub gives a Markdown heading.
slug() {
	printf '%s\n' "$1" | sed 's/^#* *//' | tr '[:upper:]' '[:lower:]' | sed 's/[^a-z0-9 _-]//g; s/ /-/g'
}

# anchors FILE: one anchor per line, for every heading of FILE outside code.
anchors() {
	awk '/^```/ { code = !code; next } !code && /^#+ / { print }' "$1" | while IFS= read -r h; do slug "$h"; done
}

# 1. The first screen: what the Lock Family is, a link to the site, and no
#    implementation detail of the site.
head -n 30 README.md >"${TMPDIR:-/tmp}/readme_head.$$"
first="${TMPDIR:-/tmp}/readme_head.$$"
check "first screen names the Lock Family" "has '$first' 'Lock Family'"
check "first screen says harness security" "has '$first' 'Harness security for AI agents'"
check "first screen links to the site" "has '$first' 'href=\"https://lockfamily.dev\"'"
check "first screen shows the banner" "has '$first' 'docs/assets/banner-light.svg'"
check "first screen has the dark banner" "has '$first' 'docs/assets/banner-dark.svg'"
for w in 'Static HTML' 'static HTML' 'GitHub Pages' 'http.server' 'CNAME' 'vanilla JavaScript'; do
	check "first screen has no site detail: $w" "! has '$first' '$w'"
done
rm -f "$first"

# 2. Site source details appear only in "About this repo".
before=$(sed -n '1,/^## About this repo$/p' README.md)
check "README has an About this repo section" "grep -q '^## About this repo$' README.md"
for w in 'static HTML' 'GitHub Pages' 'http.server' 'CNAME' 'vanilla JavaScript'; do
	case $before in *"$w"*) fail "site detail only in About this repo: $w" ;; *) pass "site detail only in About this repo: $w" ;; esac
done
check "About this repo is the last section" "[ \"\$(grep '^## ' README.md | tail -n 1)\" = '## About this repo' ]"

# 3. No hard-coded release version in the README.
check "README names no release version" "! grep -En 'v[0-9]+\\.[0-9]+\\.[0-9]+' README.md"

# 4. Every relative link and anchor of README.md and docs/*.md resolves.
for f in README.md docs/*.md; do
	dir=$(dirname "$f")
	links=$( (grep -oE '\]\([^)]+\)' "$f" | sed 's/^](//; s/)$//'
		grep -oE '(href|src)="[^"]+"' "$f" | sed 's/^[a-z]*="//; s/"$//') | sort -u)
	for l in $links; do
		case $l in http://* | https://* | mailto:*) continue ;; esac
		path=${l%%#*}
		anchor=
		case $l in *'#'*) anchor=${l#*#} ;; esac
		if [ -n "$path" ]; then target="$dir/$path"; else target=$f; fi
		if [ ! -e "$target" ]; then
			fail "$f: link $l: no $target"
			continue
		fi
		if [ -n "$anchor" ]; then
			if anchors "$target" | grep -qxF -- "$anchor"; then
				pass "$f: link $l"
			else
				fail "$f: link $l: no heading #$anchor in $target"
			fi
		else
			pass "$f: link $l"
		fi
	done
done

# 5. The quick start matches the installer: the brew formula it mirrors, its
#    URL, and its next step (lox add, then lox run).
check "quick start: brew formula as install.sh names it" "has README.md 'brew install davidgodefroid/tap/lockfamily' && has install.sh 'brew install davidgodefroid/tap/lockfamily'"
check "quick start: the installer's URL" "has README.md 'curl -fsSL https://lockfamily.dev/install.sh | sh' && has install.sh 'curl -fsSL https://lockfamily.dev/install.sh | sh'"
check "quick start: any agent, lea included" "has README.md '\`codex\`' && has README.md 'lea stop'"
check "quick start: lox add, as install.sh's next step" "grep -q '^ *lox add locksql' README.md && has install.sh 'next step: lox add <lock> in your project, then lox run'"
check "quick start: lox run" "grep -q '^ *lox run$' README.md"

# 6. Nothing lost: what left the README is in docs/. The strings are
#    literal text of the docs, not expansions.
# keeps FILE STRING
keeps() { if has "$1" "$2"; then pass "$1 keeps: $2"; else fail "$1 keeps: $2"; fi; }
# shellcheck disable=SC2016
for w in '| `lox approve [--once]` |' '| `lox audit verify' '| `lox mobile pair' '| `lox import [SUB…]` |' \
	'| `lox attach INSTANCE` |' '| `lox doctor` |' '| `lox init [--review]' '| Risk class |' \
	'seal_clear' 'require_device' 'allowed_uids: [1000]' 'host.docker.internal' \
	'locksql profile add --profile orders' '$XDG_STATE_HOME/lockfamily/' 'lea stop'; do
	keeps docs/lox.md "$w"
done
# shellcheck disable=SC2088
for w in '~/.local/share/lea-install/vX.Y.Z' 'checksums.txt' 'cosign v3.0.6' '--sha256 <hash>' \
	'Formula/lockfamily.rb' 'locklog' 'sh tests/install_test.sh' 'COSIGN_REAL'; do
	keeps docs/install.md "$w"
done
check "docs/install.md: the cosign it pins is install.sh's" "grep -q '^cosign_version=v3.0.6$' install.sh"

# 7. lox run's flags in lockhub's lox: the commands table and the site's
#    CLI tab list every one, key rotation and hub pinning included.
row=$(grep '^| `lox run ' docs/lox.md)
cli=$(sed -n '/id="hub-cli"/,/<\/pre>/p' index.html)
for flag in --manual --no-start --no-upgrade --review -v --pin --rotate; do
	case $row in *"[$flag"*) pass "docs/lox.md: lox run $flag" ;; *) fail "docs/lox.md: lox run $flag" ;; esac
	case $cli in *"[$flag"*) pass "index.html CLI tab: lox run $flag" ;; *) fail "index.html CLI tab: lox run $flag" ;; esac
done
check "README: key rotation and hub pinning" "has README.md 'lox run --rotate' && has README.md 'lox run --pin'"

# 8. lockkit: credentials are asked in lox run only for an ask profile.
check "index.html: lockkit credentials not all asked in lox run" "! has index.html 'credentials asked at the first connection in'"
check "index.html: an ask password typed in lox run" "has index.html 'an <code>ask</code> password typed at the first connection in <code>lox run</code>'"

# 9. The managed.toml v1 schema: both paths, the trust rules, every rule
#    kind and section, the precedence, and an example that is valid TOML.
# shellcheck disable=SC2016
for w in '/etc/lockfamily/managed.toml' '/Library/Application Support/lockfamily/managed.toml' \
	'managed.toml.sigstore.json' 'require_signature' 'require_confined_agent' 'refused-managed' \
	'`[<tool>.bounds]`' '`[<tool>.defaults]`' '`[<tool>.profiles.<name>]`' '**enforced**' \
	'> managed bounds and profiles' '> project file > user file' '> managed defaults > built-in defaults' \
	'## Fail closed' 'a default outside the bounds;' 'a managed profile that itself violates the bounds.' \
	'a file with a `[locklog]` section is' '### Older tools' \
	'`[locksql]`' '`[lockmq]`' '`[lockssh]`' '`[lockfile]`' '`[lockhttp]`' '### `[lox]`' '### `[lea]`'; do
	keeps docs/managed.md "$w"
done
if command -v python3 >/dev/null 2>&1 && python3 -c 'import tomllib' 2>/dev/null; then
	check "docs/managed.md: the example is valid TOML" \
		"sed -n '/^\`\`\`toml\$/,/^\`\`\`\$/p' docs/managed.md | sed '1d;\$d' | python3 -I -c 'import sys, tomllib; tomllib.loads(sys.stdin.read())'"
fi

echo
if [ "$fails" -ne 0 ]; then
	echo "$fails of $runs failed"
	exit 1
fi
echo "all $runs passed"
