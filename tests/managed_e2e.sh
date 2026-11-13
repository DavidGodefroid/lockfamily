#!/bin/sh
# End-to-end tests of docs/managed.md's recipes with the released lox and
# locksql, on a CI runner (they install into the system's managed directory
# with sudo):
#
#   sh tests/managed_e2e.sh deb     # Linux: the deb built from nfpm.yaml
#   sh tests/managed_e2e.sh sign    # Linux: keyless signing (needs id-token)
#   sh tests/managed_e2e.sh pkg     # macOS: the .pkg of macos/build.sh
#
# Needs gh (GH_TOKEN), docker for deb, cosign for sign.
set -eu

lox_version=v0.11.0
locksql_version=v0.18.1

here=$(cd "$(dirname "$0")/.." && pwd)
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT

say() { printf '\n== %s\n' "$*"; }
fail() { printf 'FAIL %s\n' "$*" >&2; exit 1; }

# fetch REPO TAG NAME: the released NAME binary for this runner, into $work/bin.
fetch() {
	os=$(uname -s | tr '[:upper:]' '[:lower:]')
	arch=$(uname -m)
	case $arch in x86_64) arch=amd64 ;; aarch64 | arm64) arch=arm64 ;; esac
	gh release download "$2" -R "DavidGodefroid/$1" -p "$3_${2#v}_${os}_${arch}.tar.gz" -D "$work/dl" --clobber
	mkdir -p "$work/x/$3" "$work/bin"
	tar -xzf "$work/dl/$3_${2#v}_${os}_${arch}.tar.gz" -C "$work/x/$3"
	cp "$work/x/$3/$3" "$work/bin/$3"
}

# expect CODE CMD…: CMD exits CODE; its output is in $work/out.
expect() {
	code=$1
	shift
	set +e
	"$@" >"$work/out" 2>&1
	got=$?
	set -e
	cat "$work/out"
	[ "$got" -eq "$code" ] || fail "$*: exit $got, want $code"
}

# has STRING: the last output contains STRING.
has() { grep -qF -- "$1" "$work/out" || fail "output lacks: $1"; }

case ${1:-} in
deb)
	dir=/etc/lockfamily
	fetch lockhub "$lox_version" lox
	fetch locksql "$locksql_version" locksql
	say "build the deb from examples/managed/nfpm.yaml"
	docker run --rm -v "$here/examples/managed:/src:ro" -v "$work:/out" -w /src \
		docker.io/goreleaser/nfpm:v2.44.1 package -p deb -f nfpm.yaml -t /out/
	sudo dpkg -i "$work"/*.deb
	ls -ld "$dir" "$dir/managed.toml"
	[ "$(stat -c '%U:%G %a' "$dir")" = "root:root 755" ] || fail "$dir: not root:root 755"
	[ "$(stat -c '%U:%G %a' "$dir/managed.toml")" = "root:root 644" ] || fail "managed.toml: not root:root 644"
	cmp "$dir/managed.toml" "$here/examples/managed/managed.toml"
	say "lox managed show"
	expect 0 "$work/bin/lox" managed show
	has 'Managed by Example Corp (sha256:'
	has 'signed: no'
	has 'auto_max.ddl = deny'
	has 'allow_no_upgrade = false'
	has 'vault from the managed configuration ([family] vault): https://vault.example.com, required'
	say "locksql managed check: the managed profile within the bounds"
	expect 0 "$work/bin/locksql" managed check
	has 'ok: 1 profile within the company policy (prod-erp)'
	say "lox run --no-upgrade: refused"
	mkdir -p "$work/project"
	(cd "$work/project" && expect 3 "$work/bin/lox" run --no-upgrade)
	has 'blocked by company policy: lox.allow_no_upgrade = false'
	say "chmod 0666: lox managed show and lox run refuse"
	sudo chmod 0666 "$dir/managed.toml"
	expect 3 "$work/bin/lox" managed show
	has 'must be writable by root only (mode 0666)'
	(cd "$work/project" && expect 3 "$work/bin/lox" run --no-start)
	has 'must be writable by root only (mode 0666)'
	sudo dpkg --purge example-corp-lockfamily-managed
	;;
sign)
	dir=/etc/lockfamily
	fetch lockhub "$lox_version" lox
	fetch locksql "$locksql_version" locksql
	say "sign the example keyless, as examples/managed/sign.yml"
	cp "$here/examples/managed/managed.toml" "$work/managed.toml"
	(cd "$work" && cosign sign-blob --yes --bundle managed.toml.sigstore.json managed.toml)
	# This job's identity, as signer.toml names sign.yml's in the docs.
	printf 'certificate_identity_regexp = "^https://github.com/%s/.github/workflows/ci.yml@%s$"\noidc_issuer = "https://token.actions.githubusercontent.com"\n' \
		"$GITHUB_REPOSITORY" "$GITHUB_REF" >"$work/signer.toml"
	cat "$work/signer.toml"
	sudo mkdir -p "$dir"
	sudo install -o root -g root -m 0644 "$work/managed.toml" "$work/signer.toml" "$work/managed.toml.sigstore.json" "$dir/"
	sudo chmod 0755 "$dir"
	say "lox managed show: signed"
	expect 0 "$work/bin/lox" managed show
	has 'signed: yes'
	has ', signed)'
	expect 0 "$work/bin/locksql" managed show
	has 'signed: yes'
	say "require_signature with the bundle: accepted"
	sed 's/^require_signature = false$/require_signature = true/' "$work/managed.toml" >"$work/required.toml"
	(cd "$work" && cosign sign-blob --yes --bundle required.toml.sigstore.json required.toml)
	sudo install -o root -g root -m 0644 "$work/required.toml" "$dir/managed.toml"
	sudo install -o root -g root -m 0644 "$work/required.toml.sigstore.json" "$dir/managed.toml.sigstore.json"
	expect 0 "$work/bin/lox" managed show
	has 'signed: yes'
	say "one byte changed: refused"
	sed 's/^organisation = "Example Corp"$/organisation = "Example Corq"/' "$work/required.toml" >"$work/altered.toml"
	sudo install -o root -g root -m 0644 "$work/altered.toml" "$dir/managed.toml"
	expect 3 "$work/bin/lox" managed show
	has 'the signature does not verify'
	expect 3 "$work/bin/locksql" managed check
	has 'the signature does not verify'
	say "require_signature without the bundle: refused"
	sudo rm "$dir/managed.toml.sigstore.json"
	sudo install -o root -g root -m 0644 "$work/required.toml" "$dir/managed.toml"
	expect 3 "$work/bin/lox" managed show
	has '[family] require_signature is set but managed.toml.sigstore.json is missing'
	sudo rm -rf "$dir"
	;;
pkg)
	dir="/Library/Application Support/lockfamily"
	fetch lockhub "$lox_version" lox
	say "build the .pkg with examples/managed/macos/build.sh"
	(cd "$here/examples/managed" && sh macos/build.sh 1.0.0 && mv example-corp-lockfamily-managed-1.0.0.pkg "$work/")
	sudo installer -pkg "$work/example-corp-lockfamily-managed-1.0.0.pkg" -target /
	ls -ld "$dir" "$dir/managed.toml"
	[ "$(stat -f '%Su:%Sg %Lp' "$dir")" = "root:wheel 755" ] || fail "$dir: not root:wheel 755"
	[ "$(stat -f '%Su:%Sg %Lp' "$dir/managed.toml")" = "root:wheel 644" ] || fail "managed.toml: not root:wheel 644"
	say "lox managed show"
	expect 0 "$work/bin/lox" managed show
	has 'Managed by Example Corp (sha256:'
	has "path: $dir/managed.toml"
	sudo chmod 0666 "$dir/managed.toml"
	expect 3 "$work/bin/lox" managed show
	has 'must be writable by root only (mode 0666)'
	sudo rm -rf "$dir"
	;;
*)
	echo "usage: sh tests/managed_e2e.sh deb|sign|pkg" >&2
	exit 2
	;;
esac
say "ok: $1"
