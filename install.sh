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
# The keyless signature of the release's checksums.txt must come from the
# lockhub release workflow run for that very tag, and the archive must match
# checksums.txt. Nothing unverified is ever installed. The signature is
# checked with the cosign on PATH; without one, a pinned cosign release is
# downloaded to a temporary directory, checked against its pinned sha256,
# used for this check only and never installed.
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

# https downloads (the releases, and cosign when it is not on PATH).
if command -v curl >/dev/null 2>&1; then
	net=curl
	fetch_https() { curl -fsSL --proto '=https' --tlsv1.2 -o "$2" "$1"; }
	latest() { curl -fsSLI --proto '=https' --tlsv1.2 -o /dev/null -w '%{url_effective}' "https://github.com/$repo/releases/latest"; }
elif command -v wget >/dev/null 2>&1; then
	net=wget
	# GNU wget refuses non-https redirects with --https-only; busybox wget
	# has no such option (the cosign signature, or cosign's pinned sha256,
	# still guards the content).
	if wget --help 2>&1 | grep -q -- --https-only; then
		fetch_https() { wget -q --https-only -O "$2" "$1"; }
	else
		fetch_https() { wget -q -O "$2" "$1"; }
	fi
	latest() { wget -q -S --spider "https://github.com/$repo/releases/latest" 2>&1 | sed -n 's/^ *[Ll]ocation: *//p' | tail -n 1 | tr -d '\r'; }
else
	net=''
	fetch_https() { say "curl or wget is required to download $1"; return 1; }
fi

base="${LOCK_RELEASE_BASE:-https://github.com/$repo/releases/download}"
case "$base" in
/*)
	fetch() { cp "$1" "$2"; }
	latest() { die "no latest release in a local mirror: pass --version"; }
	;;
https://*)
	[ -n "$net" ] || die "curl or wget is required"
	fetch() { fetch_https "$1" "$2"; }
	;;
*) die "LOCK_RELEASE_BASE must be an https URL or an absolute directory" ;;
esac

# Without cosign on PATH, this cosign release is downloaded and checked
# against its sha256, pinned here (the digests of the release's
# cosign_checksums.txt, the same pins as lea's installer). Never "latest":
# a new version changes these lines.
cosign_version=v3.0.6
case "$os-$arch" in
linux-amd64) cosign_pin=c956e5dfcac53d52bcf058360d579472f0c1d2d9b69f55209e256fe7783f4c74 ;;
linux-arm64) cosign_pin=bedac92e8c3729864e13d4a17048007cfafa79d5deca993a43a90ffe018ef2b8 ;;
darwin-amd64) cosign_pin=4c3e7af8372d3ca3296e62fa56f23fcbb5721cc6ac1827900d398f110d7cd280 ;;
darwin-arm64) cosign_pin=5fadd012ae6381a6a29ff86a7d39aa873878852f1073fc90b15995961ecfb084 ;;
esac
cosign_url="https://github.com/sigstore/cosign/releases/download/$cosign_version/cosign-$os-$arch"

if [ -n "$sum" ]; then
	printf '%s\n' "$sum" | grep -Eqx '[0-9a-fA-F]{64}' || die "--sha256 takes the 64 hex digits of the archive's sha256"
	sum=$(printf '%s' "$sum" | tr 'A-F' 'a-f')
	[ -n "$tag" ] || die "--sha256 needs --version: the hash is the hash of one release's archive"
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

sha256() {
	if command -v sha256sum >/dev/null 2>&1; then
		sha256sum "$1" | awk '{ print $1 }'
	else
		shasum -a 256 "$1" | awk '{ print $1 }'
	fi
}
got="$(sha256 "$tmp/$archive")"

if [ -n "$sum" ]; then
	[ "$sum" = "$got" ] || die "checksum mismatch for $archive: expected $sum, got $got"
	say "WARNING: no cosign: $archive checked against the --sha256 you gave only"
else
	fetch "$url/checksums.txt" "$tmp/checksums.txt" || die "download failed: checksums.txt"
	fetch "$url/checksums.txt.sigstore.json" "$tmp/checksums.txt.sigstore.json" ||
		die "download failed: checksums.txt.sigstore.json"
	if command -v cosign >/dev/null 2>&1; then
		cosign=cosign
	else
		say "cosign is not installed: downloading cosign $cosign_version to check the signature (not installed)"
		fetch_https "$cosign_url" "$tmp/cosign" ||
			die "cannot download cosign from $cosign_url: install cosign (https://docs.sigstore.dev/cosign/system_config/installation/), or pass --version and --sha256 with a hash you trust; nothing installed"
		[ "$(sha256 "$tmp/cosign")" = "$cosign_pin" ] ||
			die "the cosign downloaded from $cosign_url does not match its pinned sha256: install cosign (https://docs.sigstore.dev/cosign/system_config/installation/), then rerun; nothing installed"
		chmod 0755 "$tmp/cosign"
		cosign="$tmp/cosign"
	fi
	# The release workflow run for this very tag: a tag moved to an older
	# release's signed files does not verify.
	identity="https://github.com/$repo/.github/workflows/release.yml@refs/tags/$tag"
	"$cosign" verify-blob --bundle "$tmp/checksums.txt.sigstore.json" \
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
if [ ! -d "$dir" ]; then
	mkdir -p "$dir"
	chmod 0755 "$dir"
fi
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
