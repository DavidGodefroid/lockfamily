#!/bin/sh
# Installs the lock CLI of the Lock Family on Linux or macOS (WSL 2 on
# Windows): only ~/.local/bin/lock, without sudo, without pulling any image.
# `lock up` later pulls and verifies the images of the hub and the locks.
#
#   curl -fsSL https://lockfamily.dev/install.sh | sh
#
# or, to read it first and pick the version:
#
#   curl -fsSLO https://lockfamily.dev/install.sh
#   less install.sh
#   sh install.sh --version vX.Y.Z
#
# Options:
#   --version vX.Y.Z  the lockhub release to install (default: the latest)
#   --sha256 HASH     install without cosign: the sha256 of the archive
#                     lock_X.Y.Z_<os>_<arch>.tar.gz, which you obtained
#                     yourself from a source you trust (needs --version)
#
# cosign is required (https://docs.sigstore.dev/cosign/system_config/installation/):
# the keyless signature of the release's checksums.txt must come from the
# lockhub release workflow run for that very tag, and the archive must match
# checksums.txt. Nothing unverified is ever installed.
#
# Environment:
#   LOCK_RELEASE_BASE  a mirror of the releases (an https URL or a local
#                      directory holding vX.Y.Z/ folders); the signature is
#                      checked against the same identity
#
# The per-tool install scripts (locksql, lockmq, lockfile, lockhttp) stay
# as they are; with the hub, `lock add` and `lock up` set the locks up.
set -eu

repo="DavidGodefroid/lockhub"
issuer="https://token.actions.githubusercontent.com"

say() { printf 'lock: %s\n' "$*" >&2; }
die() { say "$*"; exit 1; }
usage() {
	cat >&2 <<'USAGE'
usage: sh install.sh [--version vX.Y.Z] [--sha256 HASH]
  --version vX.Y.Z  the lockhub release to install (default: the latest)
  --sha256 HASH     install without cosign, checking the archive against this
                    sha256 that you trust (needs --version)
USAGE
	exit 2
}

tag='' sum=''
while [ $# -gt 0 ]; do
	case "$1" in
	--version) [ $# -ge 2 ] || usage; tag=$2; shift 2 ;;
	--version=*) tag=${1#*=}; shift ;;
	--sha256) [ $# -ge 2 ] || usage; sum=$2; shift 2 ;;
	--sha256=*) sum=${1#*=}; shift ;;
	-h | --help) usage ;;
	*) say "unknown option $1"; usage ;;
	esac
done

[ -n "${HOME:-}" ] || die "HOME is not set"
dir="$HOME/.local/bin"
target="$dir/lock"

case "$(uname -s)" in
Linux) os=linux ;;
Darwin) os=darwin ;;
*) die "unsupported OS $(uname -s): Linux and macOS only" ;;
esac
case "$(uname -m)" in
x86_64 | amd64) arch=amd64 ;;
aarch64 | arm64) arch=arm64 ;;
*) die "unsupported architecture $(uname -m): amd64 and arm64 only" ;;
esac

base="${LOCK_RELEASE_BASE:-https://github.com/$repo/releases/download}"
case "$base" in
/*)
	fetch() { cp "$1" "$2"; }
	latest() { die "no latest release in a local mirror: pass --version"; }
	;;
https://*)
	if command -v curl >/dev/null 2>&1; then
		fetch() { curl -fsSL --proto '=https' --tlsv1.2 -o "$2" "$1"; }
		latest() { curl -fsSLI --proto '=https' --tlsv1.2 -o /dev/null -w '%{url_effective}' "https://github.com/$repo/releases/latest"; }
	elif command -v wget >/dev/null 2>&1; then
		fetch() { wget -q -O "$2" "$1"; }
		latest() { wget -q -S --spider "https://github.com/$repo/releases/latest" 2>&1 | sed -n 's/^ *[Ll]ocation: *//p' | tail -n 1 | tr -d '\r'; }
	else
		die "curl or wget is required"
	fi
	;;
*) die "LOCK_RELEASE_BASE must be an https URL or an absolute directory" ;;
esac

if [ -n "$sum" ]; then
	printf '%s\n' "$sum" | grep -Eqx '[0-9a-fA-F]{64}' || die "--sha256 takes the 64 hex digits of the archive's sha256"
	sum=$(printf '%s' "$sum" | tr 'A-F' 'a-f')
	[ -n "$tag" ] || die "--sha256 needs --version: the hash is the hash of one release's archive"
elif ! command -v cosign >/dev/null 2>&1; then
	die "cosign is required to check the release's signature (https://docs.sigstore.dev/cosign/system_config/installation/); without it, pass --version and --sha256 with a hash you trust"
fi

if [ -z "$tag" ]; then
	tag="$(latest)"
	tag="${tag##*/}"
	case "$tag" in
	v[0-9]*) ;;
	*) die "no published lockhub release found; pass --version" ;;
	esac
fi
case "$tag" in v*) ;; *) tag="v$tag" ;; esac
# Only a version tag: it goes into URLs, file names and the signer identity.
printf '%s\n' "$tag" | grep -Eqx 'v[0-9]+\.[0-9]+\.[0-9]+(-[0-9A-Za-z.]+)?' ||
	die "invalid version $tag: a release tag, vX.Y.Z"
version="${tag#v}"

# ~/.local/bin and what ~/.local/bin/lock points to must be the user's own,
# not writable by others: someone else could swap the binary.
others_can_write() { [ -n "$(find -H "$1" -maxdepth 0 \( -perm -0020 -o -perm -0002 -o ! -user "$(id -u)" \) 2>/dev/null)" ]; }
if [ -e "$dir" ]; then
	[ -d "$dir" ] || die "$dir is not a directory"
	others_can_write "$dir" && die "$dir is writable by others or not yours: fix its owner and mode first"
fi
if [ -L "$target" ]; then
	link=$(readlink "$target")
	case "$link" in /*) ;; *) link="$dir/$link" ;; esac
	ldir=$(cd "$(dirname "$link")" 2>/dev/null && pwd -P) || die "$target is a link to $link, which does not resolve: remove it first"
	if others_can_write "$ldir" || { [ -e "$link" ] && others_can_write "$link"; }; then
		die "$target is a link to $link, which is writable by others or not yours: remove the link first"
	fi
elif [ -e "$target" ] && [ ! -f "$target" ]; then
	die "$target exists and is not a file"
fi

archive="lock_${version}_${os}_${arch}.tar.gz"
url="$base/$tag"

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT INT TERM

say "downloading $archive ($tag)"
fetch "$url/$archive" "$tmp/$archive" || die "download failed: $url/$archive"

if command -v sha256sum >/dev/null 2>&1; then
	got="$(sha256sum "$tmp/$archive" | awk '{ print $1 }')"
else
	got="$(shasum -a 256 "$tmp/$archive" | awk '{ print $1 }')"
fi

if [ -n "$sum" ]; then
	[ "$sum" = "$got" ] || die "checksum mismatch for $archive: expected $sum, got $got"
	say "WARNING: no cosign: $archive checked against the --sha256 you gave only"
else
	fetch "$url/checksums.txt" "$tmp/checksums.txt" || die "download failed: checksums.txt"
	fetch "$url/checksums.txt.sigstore.json" "$tmp/checksums.txt.sigstore.json" ||
		die "download failed: checksums.txt.sigstore.json"
	# The release workflow run for this very tag: a tag moved to an older
	# release's signed files does not verify.
	identity="https://github.com/$repo/.github/workflows/release.yml@refs/tags/$tag"
	cosign verify-blob --bundle "$tmp/checksums.txt.sigstore.json" \
		--certificate-identity "$identity" \
		--certificate-oidc-issuer "$issuer" \
		"$tmp/checksums.txt" >"$tmp/cosign.log" 2>&1 ||
		die "cosign: the signature of checksums.txt does not verify (signer $identity); nothing installed"
	say "cosign: checksums.txt signed by the lockhub release workflow for $tag"
	want="$(awk -v f="$archive" '$2 == f || $2 == "*" f { print $1 }' "$tmp/checksums.txt")"
	[ -n "$want" ] || die "$archive is not listed in checksums.txt"
	[ "$want" = "$got" ] || die "checksum mismatch for $archive"
fi

mkdir "$tmp/x"
tar -xzf "$tmp/$archive" -C "$tmp/x" lock 2>/dev/null || die "$archive holds no lock binary"
if [ ! -f "$tmp/x/lock" ] || [ -L "$tmp/x/lock" ]; then die "$archive: lock is not a regular file"; fi
chmod 0755 "$tmp/x/lock"
reported="$("$tmp/x/lock" version 2>/dev/null || true)"
[ "$reported" = "lock $version" ] || die "the lock of $archive reports \"$reported\", not \"lock $version\""

# Written next to the target, then renamed over it: a link there is
# replaced, never written through.
mkdir -p "$dir"
chmod 0755 "$dir" 2>/dev/null || true
new="$(mktemp "$dir/.lock.XXXXXX")"
if ! { cp "$tmp/x/lock" "$new" && chmod 0755 "$new" && mv -f "$new" "$target"; }; then
	rm -f "$new"
	die "could not write $target"
fi

say "installed lock $tag to $target"
case ":$PATH:" in
*":$dir:"*) ;;
*)
	say "$dir is not on your PATH; add it to your shell profile:"
	say "  export PATH=\"\$HOME/.local/bin:\$PATH\""
	;;
esac
command -v docker >/dev/null 2>&1 || say "docker is not installed: lock up needs it"
