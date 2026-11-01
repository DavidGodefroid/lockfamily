#!/bin/sh
# Installs the Lock Family on Linux or macOS (WSL 2 on Windows): the same
# tools, at the same versions, as the Homebrew meta formula
# (brew install davidgodefroid/tap/lockfamily), into ~/.local/bin, without
# sudo and without pulling any image (each tool pulls its images, by digest,
# on first use). Then run `lox init`.
#
#   curl -fsSL https://lockfamily.dev/install.sh | sh
#
# or, to read it first:
#
#   curl -fsSLO https://lockfamily.dev/install.sh
#   less install.sh
#   sh install.sh
#
# What it installs, each from its project's signed release:
#   lox       ~/.local/bin/lox, the CLI of the approval hub (lockhub)
#   lea       the release tree in ~/.local/share/lea-install/vX.Y.Z, linked
#             as ~/.local/bin/lea (as lea's own installer, without lea init)
#   locksql, lockmq, lockhttp, and lockfile (Linux only)
#             the launchers, ~/.local/bin/<tool>, which run their release's
#             images by digest; lockfile's seccomp profile goes to
#             ~/.local/share/lockfile/seccomp.json
#   cosign    ~/.local/bin/cosign, only when no cosign is on PATH: the pinned
#             release below, checked against its sha256 (the meta formula
#             installs cosign too; the launchers' `update` and `lox init`
#             use it)
# locklog has no published release yet: it is skipped.
#
# The set and the versions are read from the tap (DavidGodefroid/homebrew-tap):
# the tools the meta formula Formula/lockfamily.rb depends on, and in each
# Formula/<tool>.rb the release URL for this system, its sha256 and the image
# digests. The formulas are read as text, never run, and every value must
# match a strict pattern. The tap only says which release: for every tool,
# the keyless signature of the release's checksums.txt must come from THAT
# project's release workflow run for that very tag, the archive must match
# checksums.txt and the formula, and a launcher's image digests must be the
# ones cosign verifies for that tag. Everything is verified before anything
# is installed. The signatures are checked with the cosign on PATH; without
# one, a pinned cosign release is downloaded and checked against its pinned
# sha256.
#
# Options:
#   --version vX.Y.Z  install lox alone, from that lockhub release (cosign,
#                     when downloaded, is then used for the check only)
#   --sha256 HASH     with --version: install lox without cosign, checking
#                     lox_X.Y.Z_<os>_<arch>.tar.gz against this sha256, which
#                     you obtained yourself from a source you trust
#
# Environment:
#   LOCK_RELEASE_BASE  a mirror of the releases (an https URL or a local
#                      directory) holding <repository>/vX.Y.Z/ folders, or,
#                      with --version, lockhub's vX.Y.Z/ folders (as before);
#                      the signatures are checked against the same identities
#   LOCK_TAP_BASE      a mirror of the tap (an https URL or a local directory
#                      holding Formula/<tool>.rb)
set -eu

owner="DavidGodefroid"
registry_owner="ghcr.io/davidgodefroid"
issuer="https://token.actions.githubusercontent.com"
semver='[0-9]+\.[0-9]+\.[0-9]+(-[0-9A-Za-z.]+)?'

say() { printf 'lockfamily: %s\n' "$*" >&2; }
die() { say "$*"; exit 1; }
usage() {
	cat >&2 <<'USAGE'
usage: sh install.sh [--version vX.Y.Z [--sha256 HASH]]
  (no option)       the Lock Family: the tools and versions of the Homebrew
                    meta formula lockfamily, into ~/.local/bin
  --version vX.Y.Z  lox alone, from that lockhub release
  --sha256 HASH     with --version: install lox without cosign, checking the
                    archive against this sha256 that you trust
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
bindir="$HOME/.local/bin"
leadir="$HOME/.local/share/lea-install"
lfshare="$HOME/.local/share/lockfile"

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

# https downloads (the releases, the tap, and cosign when it is not on PATH).
if command -v curl >/dev/null 2>&1; then
	fetch_https() { curl -fsSL --proto '=https' --tlsv1.2 -o "$2" "$1"; }
elif command -v wget >/dev/null 2>&1; then
	# GNU wget refuses non-https redirects with --https-only; busybox wget
	# has no such option (the cosign signatures, or cosign's pinned sha256,
	# still guard the content).
	if wget --help 2>&1 | grep -q -- --https-only; then
		fetch_https() { wget -q --https-only -O "$2" "$1"; }
	else
		fetch_https() { wget -q -O "$2" "$1"; }
	fi
else
	fetch_https() { say "curl or wget is required to download $1"; return 1; }
fi
# fetch SOURCE FILE: SOURCE is an https URL or a local path (a mirror).
fetch() {
	case "$1" in
	/*) cp "$1" "$2" ;;
	https://*) fetch_https "$1" "$2" ;;
	*) return 1 ;;
	esac
}
# mirror_base VARIABLE VALUE: an https URL or an absolute directory.
mirror_base() {
	case "$2" in
	/* | https://*) printf '%s' "${2%/}" ;;
	*) die "$1 must be an https URL or an absolute directory" ;;
	esac
}

release_base="${LOCK_RELEASE_BASE:-}"
[ -z "$release_base" ] || release_base="$(mirror_base LOCK_RELEASE_BASE "$release_base")"
# release_url REPOSITORY TAG: where the files of that release are.
release_url() {
	if [ -n "$release_base" ] && [ -n "$tag" ]; then
		printf '%s/%s' "$release_base" "$2"
	elif [ -n "$release_base" ]; then
		printf '%s/%s/%s' "$release_base" "$1" "$2"
	else
		printf 'https://github.com/%s/%s/releases/download/%s' "$owner" "$1" "$2"
	fi
}
tap_base="$(mirror_base LOCK_TAP_BASE "${LOCK_TAP_BASE:-https://raw.githubusercontent.com/$owner/homebrew-tap/main}")"

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
if [ -n "$tag" ]; then
	case "$tag" in v*) ;; *) tag="v$tag" ;; esac
	# Only a version tag: it goes into URLs, file names and the signer identity.
	printf '%s\n' "$tag" | grep -Eqx "v$semver" || die "invalid version $tag: a release tag, vX.Y.Z"
fi

# What the installer writes must be the user's own, not writable by others:
# someone else could swap a binary.
others_can_write() { [ -n "$(find -H "$1" -maxdepth 0 \( -perm -0020 -o -perm -0002 -o ! -user "$(id -u)" \) 2>/dev/null)" ]; }
check_dir() {
	if [ -e "$1" ]; then
		[ -d "$1" ] || die "$1 is not a directory"
		others_can_write "$1" && die "$1 is writable by others or not yours: fix its owner and mode first"
	fi
	return 0
}
# check_target NAME: ~/.local/bin/NAME, and what it points to, must be the
# user's own too. It is replaced by a rename, never written through.
check_target() {
	ct="$bindir/$1"
	[ ! -d "$ct" ] || die "$ct is a directory, or a link to one: remove it first"
	if [ -L "$ct" ]; then
		link=$(readlink "$ct")
		case "$link" in /*) ;; *) link="$bindir/$link" ;; esac
		ldir=$(cd "$(dirname "$link")" 2>/dev/null && pwd -P) || die "$ct is a link to $link, which does not resolve: remove it first"
		if others_can_write "$ldir" || { [ -e "$link" ] && others_can_write "$link"; }; then
			die "$ct is a link to $link, which is writable by others or not yours: remove the link first"
		fi
	elif [ -e "$ct" ] && [ ! -f "$ct" ]; then
		die "$ct exists and is not a file"
	fi
}

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT INT TERM

sha256() {
	if command -v sha256sum >/dev/null 2>&1; then
		sha256sum "$1" | awk '{ print $1 }'
	else
		shasum -a 256 "$1" | awk '{ print $1 }'
	fi
}

# need_cosign: sets $cosign, the cosign on PATH, else the pinned release,
# downloaded to the temporary directory and checked against its sha256.
cosign='' cosign_downloaded=0
need_cosign() {
	[ -z "$cosign" ] || return 0
	if command -v cosign >/dev/null 2>&1; then
		cosign=cosign
		return 0
	fi
	say "cosign is not installed: downloading cosign $cosign_version to check the signatures"
	fetch_https "$cosign_url" "$tmp/cosign" ||
		die "cannot download cosign from $cosign_url: install cosign (https://docs.sigstore.dev/cosign/system_config/installation/), or pass --version and --sha256 with a hash you trust; nothing installed"
	[ "$(sha256 "$tmp/cosign")" = "$cosign_pin" ] ||
		die "the cosign downloaded from $cosign_url does not match its pinned sha256: install cosign (https://docs.sigstore.dev/cosign/system_config/installation/), then rerun; nothing installed"
	chmod 0755 "$tmp/cosign"
	cosign="$tmp/cosign"
	cosign_downloaded=1
}

identity_of() { printf 'https://github.com/%s/%s/.github/workflows/release.yml@refs/tags/%s' "$owner" "$1" "$2"; }

# verify_release REPOSITORY TAG ARCHIVE [SHA256]: downloads the archive of
# that release to $tmp/REPOSITORY/ARCHIVE, then checks that checksums.txt is
# signed by the repository's release workflow run for TAG and that the
# archive matches it (and SHA256, the tap formula's, when given).
verify_release() {
	vr_dir="$tmp/$1"
	mkdir -p "$vr_dir"
	vr_url="$(release_url "$1" "$2")"
	say "$1 $2: downloading $3"
	fetch "$vr_url/$3" "$vr_dir/$3" || die "download failed: $vr_url/$3"
	fetch "$vr_url/checksums.txt" "$vr_dir/checksums.txt" || die "download failed: $vr_url/checksums.txt"
	fetch "$vr_url/checksums.txt.sigstore.json" "$vr_dir/checksums.txt.sigstore.json" ||
		die "download failed: $vr_url/checksums.txt.sigstore.json"
	need_cosign
	# The release workflow run for this very tag: a tag moved to an older
	# release's signed files does not verify.
	vr_identity="$(identity_of "$1" "$2")"
	"$cosign" verify-blob --bundle "$vr_dir/checksums.txt.sigstore.json" \
		--certificate-identity "$vr_identity" \
		--certificate-oidc-issuer "$issuer" \
		"$vr_dir/checksums.txt" >"$tmp/cosign.log" 2>&1 ||
		die "cosign: the signature of the $1 checksums.txt does not verify (signer $vr_identity); nothing installed"
	say "cosign: checksums.txt signed by the $1 release workflow for $2"
	vr_want="$(awk -v f="$3" '$2 == f || $2 == "*" f { print $1 }' "$vr_dir/checksums.txt")"
	[ -n "$vr_want" ] || die "$3 is not listed in checksums.txt"
	vr_got="$(sha256 "$vr_dir/$3")"
	[ "$vr_want" = "$vr_got" ] || die "checksum mismatch for $3"
	if [ -n "${4:-}" ] && [ "$4" != "$vr_got" ]; then
		die "$3 does not match the sha256 of its tap formula: the tap and the release disagree; nothing installed"
	fi
}

# formula_release FILE REPOSITORY NAME: "VERSION SHA256" of the formula's
# archive for this system, NAME_VERSION_<os>_<arch>.tar.gz of the
# repository's releases, and the sha256 on the line after its url.
formula_release() {
	awk -v pre="https://github.com/$owner/$2/releases/download/v" -v name="$3" -v suf="_${os}_${arch}.tar.gz" '
want && /^ *sha256 "[0-9a-f]*"$/ { s = $0; sub(/^ *sha256 "/, "", s); sub(/"$/, "", s); sha = s; want = 0; next }
{ want = 0 }
/^ *url "[^"]*"$/ {
	u = $0; sub(/^ *url "/, "", u); sub(/"$/, "", u)
	if (index(u, pre) != 1) next
	rest = substr(u, length(pre) + 1); i = index(rest, "/")
	if (i == 0) next
	v = substr(rest, 1, i - 1)
	if (substr(rest, i + 1) != name "_" v suf) next
	n++; ver = v; want = 1
}
END { if (n == 1 && sha != "") print ver, sha }' "$1"
}

# formula_digest FILE KEY: the digest of the formula's KEY = "sha256:..."
# line (image_digest, vault_image_digest), when there is exactly one.
formula_digest() {
	fd=$(sed -n "s/^ *$2 = \"\\(sha256:[0-9a-f]*\\)\"\$/\\1/p" "$1")
	printf '%s\n' "$fd" | grep -Eqx 'sha256:[0-9a-f]{64}' && [ "$(printf '%s\n' "$fd" | grep -c .)" = 1 ] && printf '%s' "$fd"
}

# verified_digest REPOSITORY TAG IMAGE_TAG: the digest of the image
# ghcr.io/davidgodefroid/REPOSITORY:IMAGE_TAG whose signature verifies
# against the repository's release workflow run for TAG.
verified_digest() {
	"$cosign" verify --certificate-identity "$(identity_of "$1" "$2")" \
		--certificate-oidc-issuer "$issuer" \
		"$registry_owner/$1:$3" 2>"$tmp/cosign.log" |
		sed -n 's/.*"docker-manifest-digest":"\(sha256:[0-9a-f]\{64\}\)".*/\1/p' | sed -n 1p
}

# stage_lox TAG [SHA256]: the verified lox binary of that lockhub release,
# to $tmp/stage/lox. With $sum (--sha256), checked against it only.
stage_lox() {
	sl_version="${1#v}"
	sl_archive="lox_${sl_version}_${os}_${arch}.tar.gz"
	if [ -n "$sum" ]; then
		mkdir -p "$tmp/lockhub"
		sl_url="$(release_url lockhub "$1")"
		say "lockhub $1: downloading $sl_archive"
		fetch "$sl_url/$sl_archive" "$tmp/lockhub/$sl_archive" || die "download failed: $sl_url/$sl_archive"
		[ "$sum" = "$(sha256 "$tmp/lockhub/$sl_archive")" ] ||
			die "checksum mismatch for $sl_archive: expected $sum, got $(sha256 "$tmp/lockhub/$sl_archive")"
		say "WARNING: no cosign: $sl_archive checked against the --sha256 you gave only"
	else
		verify_release lockhub "$1" "$sl_archive" "${2:-}"
	fi
	mkdir -p "$tmp/x/lox"
	tar -xzf "$tmp/lockhub/$sl_archive" -C "$tmp/x/lox" lox 2>/dev/null || die "$sl_archive holds no lox binary"
	if [ ! -f "$tmp/x/lox/lox" ] || [ -L "$tmp/x/lox/lox" ]; then die "$sl_archive: lox is not a regular file"; fi
	chmod 0755 "$tmp/x/lox/lox"
	sl_reported="$("$tmp/x/lox/lox" version 2>/dev/null || true)"
	[ "$sl_reported" = "lox $sl_version" ] || die "the lox of $sl_archive reports \"$sl_reported\", not \"lox $sl_version\""
	cp "$tmp/x/lox/lox" "$tmp/stage/lox"
}

# stage_lea TAG SHA256: the verified release tree of lea, to
# $tmp/stage/lea-TAG.
stage_lea() {
	sa_archive="lea_${1#v}_${os}_${arch}.tar.gz"
	verify_release lea "$1" "$sa_archive" "$2"
	# Every entry under lea-TAG/, none climbing out of it.
	tar -tzf "$tmp/lea/$sa_archive" >"$tmp/lea.list" 2>/dev/null || die "$sa_archive is not a readable archive"
	awk -v p="lea-$1/" 'index($0, p) != 1 || /(^|\/)\.\.(\/|$)/ { bad = 1 } END { exit bad }' "$tmp/lea.list" ||
		die "$sa_archive holds files outside lea-$1/"
	tar -xzf "$tmp/lea/$sa_archive" -C "$tmp/stage" || die "cannot unpack $sa_archive"
	# Whatever the umask: nobody else may write into the tree lea runs from.
	chmod -R go-w "$tmp/stage/lea-$1"
	[ -f "$tmp/stage/lea-$1/bin/lea" ] || die "$sa_archive holds no bin/lea"
	sa_reported="$("$tmp/stage/lea-$1/bin/lea" version 2>/dev/null || true)"
	[ "$sa_reported" = "$1" ] || die "the lea of $sa_archive reports \"$sa_reported\", not \"$1\""
}

# stage_launcher TOOL TAG SHA256 FORMULA: the launcher scripts/TOOL of that
# release, to $tmp/stage/TOOL, with its version and its images' digests
# filled in as the tap formula does (and, for lockfile, its seccomp profile,
# to $tmp/stage/seccomp.json). The digests are the formula's, and each must be
# the digest cosign verifies for the release's image tag.
stage_launcher() {
	st_version="${2#v}"
	st_archive="${1}_${st_version}_${os}_${arch}.tar.gz"
	verify_release "$1" "$2" "$st_archive" "$3"
	mkdir -p "$tmp/x/$1"
	st_files="scripts/$1"
	[ "$1" != lockfile ] || st_files="$st_files seccomp.json"
	# shellcheck disable=SC2086 # the member names, split on purpose
	tar -xzf "$tmp/$1/$st_archive" -C "$tmp/x/$1" $st_files 2>/dev/null ||
		die "$st_archive holds no launcher ($st_files)"
	st_digest="$(formula_digest "$4" image_digest)" || die "the tap formula $1.rb has no valid image_digest"
	st_vdigest=''
	case "$1" in
	locksql | lockmq | lockfile)
		st_vdigest="$(formula_digest "$4" vault_image_digest)" || die "the tap formula $1.rb has no valid vault_image_digest"
		[ "$st_digest" != "$st_vdigest" ] || die "the tap formula $1.rb gives the same digest to both images"
		;;
	esac
	[ "$(verified_digest "$1" "$2" "$st_version")" = "$st_digest" ] || {
		cat "$tmp/cosign.log" >&2
		die "cosign: $registry_owner/$1:$st_version is not $st_digest signed by the $1 release workflow for $2; nothing installed"
	}
	if [ -n "$st_vdigest" ]; then
		[ "$(verified_digest "$1" "$2" "$st_version-vault")" = "$st_vdigest" ] || {
			cat "$tmp/cosign.log" >&2
			die "cosign: $registry_owner/$1:$st_version-vault is not $st_vdigest signed by the $1 release workflow for $2; nothing installed"
		}
	fi
	say "cosign: the $1 images of $2 verified ($st_digest${st_vdigest:+, vault $st_vdigest})"
	sed -e "s/^launcher_version=dev\$/launcher_version=$st_version/" \
		-e "s/^image_digest=\$/image_digest=$st_digest/" \
		-e "s/^vault_image_digest=\$/vault_image_digest=$st_vdigest/" \
		-e "s|^seccomp_profile=\$|seccomp_profile=$lfshare/seccomp.json|" \
		"$tmp/x/$1/scripts/$1" >"$tmp/stage/$1"
	if ! grep -Fqx "launcher_version=$st_version" "$tmp/stage/$1" || ! grep -Fqx "image_digest=$st_digest" "$tmp/stage/$1"; then
		die "the launcher of $1 $2 does not take its version and image digest"
	fi
	if [ -n "$st_vdigest" ]; then
		grep -Fqx "vault_image_digest=$st_vdigest" "$tmp/stage/$1" || die "the launcher of $1 $2 does not take its vault image digest"
	fi
	if [ "$1" = lockfile ]; then
		grep -Fqx "seccomp_profile=$lfshare/seccomp.json" "$tmp/stage/$1" || die "the launcher of lockfile $2 does not take its seccomp profile"
		cp "$tmp/x/$1/seccomp.json" "$tmp/stage/seccomp.json"
	fi
}

# put SOURCE TARGET MODE: written next to the target, then renamed over it:
# a link there is replaced, never written through.
put() {
	pt_new="$(mktemp "$(dirname "$2")/.$(basename "$2").XXXXXX")"
	if ! { cp "$1" "$pt_new" && chmod "$3" "$pt_new" && mv -f "$pt_new" "$2"; }; then
		rm -f "$pt_new"
		die "could not write $2"
	fi
}
make_dir() {
	if [ ! -d "$1" ]; then
		mkdir -p "$1"
		chmod 0755 "$1"
	fi
}

mkdir "$tmp/stage" "$tmp/x"
check_dir "$bindir"

# --version: lox alone, as this script did before the whole family.
if [ -n "$tag" ]; then
	check_target lox
	stage_lox "$tag"
	make_dir "$bindir"
	put "$tmp/stage/lox" "$bindir/lox" 0755
	say "installed lox $tag to $bindir/lox"
	case ":$PATH:" in
	*":$bindir:"*) ;;
	*)
		say "$bindir is not on your PATH; add it to your shell profile:"
		say "  export PATH=\"\$HOME/.local/bin:\$PATH\""
		;;
	esac
	command -v docker >/dev/null 2>&1 || say "docker is not installed: lox up needs it"
	exit 0
fi

# The set: the tools the meta formula depends on, in this order.
fetch "$tap_base/Formula/lockfamily.rb" "$tmp/lockfamily.rb" || die "cannot read the tap: $tap_base/Formula/lockfamily.rb"
sed -n 's|^ *depends_on "davidgodefroid/tap/\([a-z0-9-]*\)"$|\1|p' "$tmp/lockfamily.rb" >"$tmp/components"
grep -q . "$tmp/components" || die "the tap's meta formula lockfamily.rb names no tool"
listed() { grep -qx "$1" "$tmp/components"; }
while read -r c; do
	case "$c" in
	lox | lea | locksql | lockmq | lockhttp | lockfile) ;;
	*) say "the meta formula also names $c, which this install.sh does not install yet: skipped (see https://lockfamily.dev/install.sh)" ;;
	esac
done <"$tmp/components"
listed locklog || say "locklog: no published release yet, skipped"
tools=''
for t in lox lea locksql lockmq lockhttp lockfile; do
	listed "$t" || continue
	if [ "$t" = lockfile ] && [ "$os" != linux ]; then
		say "lockfile: Linux only, skipped"
		continue
	fi
	tools="$tools $t"
done

# Checked before anything is downloaded.
for t in $tools; do check_target "$t"; done
check_dir "$leadir"
check_dir "$lfshare"
command -v cosign >/dev/null 2>&1 || check_target cosign

# Verified and staged, all of them, before anything is installed.
summary='' lea_tag=''
for t in $tools; do
	case "$t" in lox) repo=lockhub ;; *) repo=$t ;; esac
	fetch "$tap_base/Formula/$t.rb" "$tmp/$t.rb" || die "cannot read the tap: $tap_base/Formula/$t.rb"
	rel="$(formula_release "$tmp/$t.rb" "$repo" "$t")"
	version="${rel% *}" fsum="${rel#* }"
	if ! printf '%s\n' "$version" | grep -Eqx "$semver" || ! printf '%s\n' "$fsum" | grep -Eqx '[0-9a-f]{64}'; then
		die "the tap formula $t.rb has no valid release archive for $os/$arch"
	fi
	case "$t" in
	lox) stage_lox "v$version" "$fsum" ;;
	lea) stage_lea "v$version" "$fsum" ;;
	*) stage_launcher "$t" "v$version" "$fsum" "$tmp/$t.rb" ;;
	esac
	summary="$summary $t v$version,"
	[ "$t" != lea ] || lea_tag="v$version"
done

make_dir "$bindir"
for t in $tools; do
	case "$t" in
	lea)
		make_dir "$leadir"
		rm -rf "${leadir:?}/${lea_tag:?}"
		mv "$tmp/stage/lea-$lea_tag" "$leadir/$lea_tag" || die "could not write $leadir/$lea_tag"
		ln_new="$bindir/.lea.link.$$"
		rm -f "$ln_new"
		{ ln -s "$leadir/$lea_tag/bin/lea" "$ln_new" && mv -f "$ln_new" "$bindir/lea"; } || {
			rm -f "$ln_new"
			die "could not link $bindir/lea"
		}
		;;
	lockfile)
		make_dir "$lfshare"
		put "$tmp/stage/seccomp.json" "$lfshare/seccomp.json" 0644
		put "$tmp/stage/lockfile" "$bindir/lockfile" 0755
		;;
	*) put "$tmp/stage/$t" "$bindir/$t" 0755 ;;
	esac
done
installed="$tools"
if [ "$cosign_downloaded" = 1 ]; then
	put "$tmp/cosign" "$bindir/cosign" 0755
	summary="$summary cosign $cosign_version,"
	installed="$installed cosign"
fi
say "installed to $bindir:${summary%,}"

case ":$PATH:" in
*":$bindir:"*)
	for t in $installed; do
		p="$(command -v "$t" 2>/dev/null || true)"
		[ -z "$p" ] || [ "$p" = "$bindir/$t" ] || say "note: $p comes before $bindir/$t on your PATH"
	done
	;;
*)
	say "$bindir is not on your PATH; add it to your shell profile:"
	say "  export PATH=\"\$HOME/.local/bin:\$PATH\""
	;;
esac
command -v docker >/dev/null 2>&1 ||
	say "docker is not installed: the Lock Family runs in Docker (Docker Engine on Linux, Docker Desktop on macOS)"
say "next step: lox init"
