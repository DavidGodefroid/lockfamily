#!/bin/sh
# Tests of install.sh against fake releases of every tool in a temporary
# directory (LOCK_RELEASE_BASE), a fake tap (LOCK_TAP_BASE) and a stub
# cosign: no network, nothing outside the temporary HOME. Tests 1-19 cover
# --version (lox alone), tests 20 and up the whole family. Without cosign on PATH, install.sh downloads
# cosign-<os>-<arch> from the cosign release it pins: a stub curl serves a
# fake cosign under that name, and $installer is a copy of install.sh that
# pins the fake's sha256 instead ($real_installer is install.sh itself). With COSIGN_REAL set to a real cosign binary,
# one more test checks that a bundle that does not verify aborts.
#
#   sh tests/install_test.sh
set -u

here=$(cd "$(dirname "$0")/.." && pwd)
real_installer="$here/install.sh"
root=$(mktemp -d)
trap 'chmod -R u+w "$root" 2>/dev/null; rm -rf "$root"' EXIT INT TERM

fails=0
runs=0
pass() { runs=$((runs + 1)); printf 'ok   %s\n' "$1"; }
fail() { runs=$((runs + 1)); fails=$((fails + 1)); printf 'FAIL %s\n' "$1"; [ -f "$root/out" ] && sed 's/^/     | /' "$root/out"; }

case "$(uname -s)" in Linux) os=linux ;; Darwin) os=darwin ;; *) echo "unsupported OS" >&2; exit 1 ;; esac
case "$(uname -m)" in x86_64 | amd64) arch=amd64 ;; aarch64 | arm64) arch=arm64 ;; *) echo "unsupported arch" >&2; exit 1 ;; esac

sha256() { if command -v sha256sum >/dev/null 2>&1; then sha256sum "$1" | awk '{print $1}'; else shasum -a 256 "$1" | awk '{print $1}'; fi; }

# A fake release vVERSION: the archive for this host, checksums.txt and a
# bundle. Its "lox" is a script that prints its version.
release() {
	v=$1
	d="$root/rel/v$v"
	mkdir -p "$d" "$root/pkg"
	printf '#!/bin/sh\necho "lox %s"\n' "$v" >"$root/pkg/lox"
	chmod 0755 "$root/pkg/lox"
	echo license >"$root/pkg/LICENSE"
	(cd "$root/pkg" && tar -czf "$d/lox_${v}_${os}_${arch}.tar.gz" lox LICENSE)
	echo "not a real bundle" >"$d/checksums.txt.sigstore.json"
	(cd "$d" && for f in lox_*.tar.gz; do printf '%s  %s\n' "$(sha256 "$f")" "$f"; done >checksums.txt)
}
release 1.2.3

# Stub tools, first on PATH: cosign logs its arguments and exits with
# $COSIGN_RC; docker logs that it was called (install.sh must never call it);
# curl logs its URL and serves $root/dl/<file name> (exit 22 when missing).
mkdir -p "$root/stub" "$root/nocosign" "$root/dl"
# A cosign stub: it logs its arguments ($LOG_PREFIX first), fails when they
# contain $COSIGN_FAIL, and for `verify IMAGE` prints the digest stored in
# $DIGESTS/<image with / and : as _> (none stored: it fails).
cat >"$root/cosign-stub" <<'STUB'
printf '%s%s\n' "$LOG_PREFIX" "$*" >>"$STUB_LOG"
if [ -n "${COSIGN_FAIL:-}" ]; then case "$*" in *"$COSIGN_FAIL"*) exit 1 ;; esac; fi
if [ "$1" = verify ]; then
	for ref in "$@"; do :; done
	f="$DIGESTS/$(printf '%s' "$ref" | tr '/:' '__')"
	[ -f "$f" ] || exit 1
	printf '[{"critical":{"image":{"docker-manifest-digest":"%s"}}}]\n' "$(cat "$f")"
fi
exit "${COSIGN_RC:-0}"
STUB
{ echo '#!/bin/sh'; echo 'LOG_PREFIX='; cat "$root/cosign-stub"; } >"$root/stub/cosign"
cat >"$root/stub/docker" <<'STUB'
#!/bin/sh
echo "docker $*" >>"$STUB_LOG"
exit 1
STUB
cat >"$root/stub/curl" <<'STUB'
#!/bin/sh
out='' url=''
while [ $# -gt 0 ]; do
	case "$1" in -o) out=$2; shift ;; --proto | -w) shift ;; -*) ;; *) url=$1 ;; esac
	shift
done
echo "curl $url" >>"$STUB_LOG"
[ -f "$DL_DIR/${url##*/}" ] || exit 22
cp "$DL_DIR/${url##*/}" "$out"
STUB
chmod 0755 "$root/stub/cosign" "$root/stub/docker" "$root/stub/curl"
# The cosign served for download: it logs "downloaded cosign ARGS".
cosign_url="https://github.com/sigstore/cosign/releases/download/v3.0.6/cosign-$os-$arch"
{ echo '#!/bin/sh'; echo "LOG_PREFIX='downloaded cosign '"; cat "$root/cosign-stub"; } >"$root/dl/cosign-$os-$arch"
cosign_pin=$(sha256 "$root/dl/cosign-$os-$arch")
installer="$root/install-test.sh"
sed "s/^\($os-$arch) cosign_pin=\)[0-9a-f]*/\1$cosign_pin/" "$real_installer" >"$installer"
if ! grep -qx "$os-$arch) cosign_pin=$cosign_pin ;;" "$installer"; then
	echo "could not re-pin cosign-$os-$arch in a copy of install.sh" >&2
	exit 1
fi
# A PATH without cosign: the system tools only, linked one by one.
for t in sh cat cp mv rm mkdir mktemp chmod tar gzip gunzip awk sed grep tr uname find id dirname basename head tail printf sha256sum shasum ls ln readlink cut; do
	p=$(command -v "$t" 2>/dev/null) && case "$p" in /*) ln -sf "$p" "$root/nocosign/$t" ;; esac
done
ln -sf "$root/stub/docker" "$root/nocosign/docker"
ln -sf "$root/stub/curl" "$root/nocosign/curl"
# The same without any downloader (no curl, no wget).
mkdir -p "$root/nonet"
for p in "$root/nocosign"/*; do [ "${p##*/}" = curl ] || ln -sf "$(readlink "$p")" "$root/nonet/${p##*/}"; done

# run NAME ARGS...: install.sh in a fresh HOME; status in $code, output in $root/out.
run() {
	export HOME="$root/home/$1"
	shift
	mkdir -p "$HOME"
	STUB_LOG="$root/stub.log"
	: >"$STUB_LOG"
	export STUB_LOG
	# Some shells (bash as sh) keep a function's prefix assignments
	# (COSIGN_RC=1 run ...) after the call: read them, then drop them.
	rc=${COSIGN_RC:-0}
	cfail=${COSIGN_FAIL:-}
	tpath=${TPATH:-$root/stub:$PATH}
	inst=${INSTALLER:-$installer}
	dl=${DL_DIR:-$root/dl}
	tap=${TAP:-$root/tap}
	unset COSIGN_RC COSIGN_FAIL TPATH INSTALLER DL_DIR TAP
	code=0
	COSIGN_RC=$rc COSIGN_FAIL=$cfail PATH=$tpath DL_DIR=$dl DIGESTS="$root/digests" \
		LOCK_RELEASE_BASE="$root/rel" LOCK_TAP_BASE="$tap" sh "$inst" "$@" >"$root/out" 2>&1 || code=$?
}
bin() { printf '%s' "$HOME/.local/bin/lox"; }

# 1. A verified install.
run ok --version v1.2.3
if [ "$code" = 0 ] && [ -x "$(bin)" ] && [ "$("$(bin)")" = "lox 1.2.3" ] &&
	[ "$(find "$(bin)" -maxdepth 0 -perm 0755 | wc -l)" -eq 1 ] &&
	grep -q -- "--certificate-identity https://github.com/DavidGodefroid/lockhub/.github/workflows/release.yml@refs/tags/v1.2.3" "$STUB_LOG" &&
	grep -q -- "--certificate-oidc-issuer https://token.actions.githubusercontent.com" "$STUB_LOG" &&
	grep -q -- "--bundle" "$STUB_LOG"; then
	pass "verified install of v1.2.3 into ~/.local/bin/lox (0755)"
else fail "verified install"; fi
if ! grep -q '^curl' "$STUB_LOG" && ! grep -q '^downloaded cosign' "$STUB_LOG"; then pass "cosign on PATH preferred: no cosign download"; else fail "cosign on PATH preferred: no cosign download"; fi
if grep -q '^docker' "$STUB_LOG"; then fail "docker was called"; else pass "no docker call (no image pulled)"; fi
if grep -q 'not on your PATH' "$root/out" && grep -q 'export PATH=' "$root/out"; then pass "PATH hint"; else fail "PATH hint"; fi

# 2. The version without its v.
run nov --version 1.2.3
if [ "$code" = 0 ] && [ "$("$(bin)")" = "lox 1.2.3" ]; then pass "--version without v"; else fail "--version without v"; fi

# 3. A signature that does not verify aborts and installs nothing.
COSIGN_RC=1 run badsig --version v1.2.3
if [ "$code" != 0 ] && [ ! -e "$(bin)" ] && grep -q 'does not verify' "$root/out"; then pass "signature failure aborts"; else fail "signature failure aborts"; fi

# 4. A failed signature leaves a former install in place.
run keep --version v1.2.3
COSIGN_RC=1 run keep --version v1.2.3
if [ "$code" != 0 ] && [ "$("$(bin)")" = "lox 1.2.3" ]; then pass "failure keeps the former lox"; else fail "failure keeps the former lox"; fi

# 5. Without cosign on PATH: the pinned cosign is downloaded, checked and
# used from the temporary directory, never installed.
TPATH="$root/nocosign" run nocosign --version v1.2.3
if [ "$code" = 0 ] && [ "$("$(bin)")" = "lox 1.2.3" ] &&
	grep -qx "curl $cosign_url" "$STUB_LOG" &&
	grep -q -- "^downloaded cosign verify-blob --bundle .* --certificate-identity https://github.com/DavidGodefroid/lockhub/.github/workflows/release.yml@refs/tags/v1.2.3" "$STUB_LOG" &&
	[ ! -e "$HOME/.local/bin/cosign" ]; then
	pass "no cosign: verified with the downloaded pinned cosign"
else fail "no cosign: verified with the downloaded pinned cosign"; fi
TPATH="$root/nocosign" COSIGN_RC=1 run nocosignbad --version v1.2.3
if [ "$code" != 0 ] && [ ! -e "$(bin)" ] && grep -q 'does not verify' "$root/out"; then pass "no cosign: a bad signature still aborts"; else fail "no cosign: a bad signature still aborts"; fi

# 5b. A downloaded cosign that does not match its pin (here the real
# install.sh, which pins the real cosign): aborts, never runs it.
TPATH="$root/nocosign" INSTALLER="$real_installer" run cosignpin --version v1.2.3
if [ "$code" != 0 ] && [ ! -e "$(bin)" ] && grep -q 'does not match its pinned sha256' "$root/out" &&
	! grep -q '^downloaded cosign' "$STUB_LOG"; then
	pass "cosign with a wrong sha256 aborts, not run"
else fail "cosign with a wrong sha256 aborts, not run"; fi

# 5c. cosign cannot be downloaded (not served, or no curl/wget): aborts.
mkdir -p "$root/dl-empty"
TPATH="$root/nocosign" DL_DIR="$root/dl-empty" run cosigndl --version v1.2.3
if [ "$code" != 0 ] && [ ! -e "$(bin)" ] && grep -q 'cannot download cosign' "$root/out"; then pass "cosign download failure aborts"; else fail "cosign download failure aborts"; fi
TPATH="$root/nonet" run cosignnonet --version v1.2.3
if [ "$code" != 0 ] && [ ! -e "$(bin)" ] && grep -q 'cannot download cosign' "$root/out"; then pass "no cosign and no curl/wget: aborts"; else fail "no cosign and no curl/wget: aborts"; fi

# 6. Without cosign, with the right --sha256: installed, nothing downloaded
# but the archive (works offline, without any cosign).
want=$(sha256 "$root/rel/v1.2.3/lox_1.2.3_${os}_${arch}.tar.gz")
TPATH="$root/nonet" run sha --version v1.2.3 --sha256 "$want"
if [ "$code" = 0 ] && [ "$("$(bin)")" = "lox 1.2.3" ] && [ ! -s "$STUB_LOG" ]; then pass "--sha256 without cosign"; else fail "--sha256 without cosign"; fi
TPATH="$root/nocosign" run sha2 --version v1.2.3 --sha256 "$want"
if [ "$code" = 0 ] && ! grep -q '^curl' "$STUB_LOG"; then pass "--sha256: no cosign download"; else fail "--sha256: no cosign download"; fi

# 7. A wrong --sha256 aborts.
TPATH="$root/nocosign" run badsha --version v1.2.3 --sha256 "$(printf '0%.0s' $(seq 1 64))"
if [ "$code" != 0 ] && [ ! -e "$(bin)" ] && grep -q 'checksum mismatch' "$root/out"; then pass "wrong --sha256 aborts"; else fail "wrong --sha256 aborts"; fi

# 8. A malformed --sha256 is refused.
TPATH="$root/nocosign" run shafmt --version v1.2.3 --sha256 xyz
if [ "$code" != 0 ] && [ ! -e "$(bin)" ]; then pass "malformed --sha256 refused"; else fail "malformed --sha256 refused"; fi

# 9. An archive that does not match checksums.txt aborts.
release 1.2.4
echo tampered >>"$root/rel/v1.2.4/lox_1.2.4_${os}_${arch}.tar.gz"
run tampered --version v1.2.4
if [ "$code" != 0 ] && [ ! -e "$(bin)" ] && grep -q 'checksum mismatch' "$root/out"; then pass "tampered archive aborts"; else fail "tampered archive aborts"; fi

# 10. An archive missing from checksums.txt aborts.
release 1.2.5
: >"$root/rel/v1.2.5/checksums.txt"
run unlisted --version v1.2.5
if [ "$code" != 0 ] && [ ! -e "$(bin)" ] && grep -q 'not listed' "$root/out"; then pass "unlisted archive aborts"; else fail "unlisted archive aborts"; fi

# 11. A lox whose version differs from the release's aborts.
release 1.2.6
release 1.2.7
cp "$root/rel/v1.2.6/lox_1.2.6_${os}_${arch}.tar.gz" "$root/rel/v1.2.7/lox_1.2.7_${os}_${arch}.tar.gz"
(cd "$root/rel/v1.2.7" && printf '%s  %s\n' "$(sha256 "lox_1.2.7_${os}_${arch}.tar.gz")" "lox_1.2.7_${os}_${arch}.tar.gz" >checksums.txt)
run wrongver --version v1.2.7
if [ "$code" != 0 ] && [ ! -e "$(bin)" ] && grep -q 'reports' "$root/out"; then pass "version mismatch aborts"; else fail "version mismatch aborts"; fi

# 12. Invalid versions are refused before any download.
for v in latest 'v1.2.3;id' '../v1.2.3' v1.2; do
	run badver --version "$v"
	if [ "$code" != 0 ] && [ ! -e "$(bin)" ] && grep -q 'invalid version' "$root/out"; then pass "invalid version $v refused"; else fail "invalid version $v refused"; fi
done

# 13. Unknown options are refused.
run badopt --frobnicate
if [ "$code" = 2 ]; then pass "unknown option: exit 2"; else fail "unknown option: exit 2"; fi

# 14. ~/.local/bin/lox as a link to a file others can write: refused.
mkdir -p "$root/shared" "$root/home/linkw/.local/bin"
echo old >"$root/shared/lox"
chmod 0666 "$root/shared/lox"
ln -s "$root/shared/lox" "$root/home/linkw/.local/bin/lox"
run linkw --version v1.2.3
if [ "$code" != 0 ] && [ "$(cat "$root/shared/lox")" = old ] && [ -L "$(bin)" ] && grep -q 'writable by others' "$root/out"; then pass "link to a world-writable file refused"; else fail "link to a world-writable file refused"; fi

# 15. ... or in a directory others can write: refused.
mkdir -p "$root/sharedd" "$root/home/linkd/.local/bin"
chmod 0777 "$root/sharedd"
echo old >"$root/sharedd/lox"
chmod 0644 "$root/sharedd/lox"
ln -s "$root/sharedd/lox" "$root/home/linkd/.local/bin/lox"
run linkd --version v1.2.3
if [ "$code" != 0 ] && [ "$(cat "$root/sharedd/lox")" = old ] && grep -q 'writable by others' "$root/out"; then pass "link into a world-writable directory refused"; else fail "link into a world-writable directory refused"; fi

# 16. A link to the user's own, private file is replaced by the binary
# (the link itself, never the file it pointed to).
mkdir -p "$root/home/linkok/.local/bin" "$root/home/linkok/opt"
chmod 0755 "$root/home/linkok/.local/bin" "$root/home/linkok/opt"
echo old >"$root/home/linkok/opt/lox"
chmod 0755 "$root/home/linkok/opt/lox"
ln -s "$root/home/linkok/opt/lox" "$root/home/linkok/.local/bin/lox"
run linkok --version v1.2.3
if [ "$code" = 0 ] && [ ! -L "$(bin)" ] && [ "$("$(bin)")" = "lox 1.2.3" ] && [ "$(cat "$root/home/linkok/opt/lox")" = old ]; then pass "private link replaced, its target untouched"; else fail "private link replaced, its target untouched"; fi

# 17. ~/.local/bin writable by others: refused.
mkdir -p "$root/home/dirw/.local/bin"
chmod 0777 "$root/home/dirw/.local/bin"
run dirw --version v1.2.3
if [ "$code" != 0 ] && [ ! -e "$(bin)" ] && grep -q 'writable by others' "$root/out"; then pass "world-writable ~/.local/bin refused"; else fail "world-writable ~/.local/bin refused"; fi

# 18. No PATH hint when ~/.local/bin is on PATH.
TPATH="$root/home/onpath/.local/bin:$root/stub:$PATH" run onpath --version v1.2.3
if [ "$code" = 0 ] && ! grep -q 'not on your PATH' "$root/out"; then pass "no PATH hint when on PATH"; else fail "no PATH hint when on PATH"; fi

# 19. With a real cosign: the fake bundle does not verify, the install aborts.
if [ -n "${COSIGN_REAL:-}" ]; then
	mkdir -p "$root/real"
	ln -sf "$COSIGN_REAL" "$root/real/cosign"
	TPATH="$root/real:$root/nocosign" run realcosign --version v1.2.3
	if [ "$code" != 0 ] && [ ! -e "$(bin)" ] && grep -q 'does not verify' "$root/out"; then pass "real cosign: bad bundle aborts"; else fail "real cosign: bad bundle aborts"; fi
else
	echo "skip real cosign (COSIGN_REAL unset)"
fi

# The whole family (no --version): fake releases of every tool, and a fake
# tap whose formulas name them, for this system and three others.
hex() { printf '%s' "$1" >"$root/hex.in"; sha256 "$root/hex.in"; }
# fam REPOSITORY TOOL VERSION: a fake release of lea or a launcher. lea is a tree lea-vX.Y.Z/
# whose bin/lea prints its version; a launcher is scripts/TOOL with the
# lines the installer fills in (and, for lockfile, seccomp.json). The
# images' signed digests go to $root/digests.
fam() {
	d="$root/rel/$1/v$3" p="$root/pkg-$1"
	rm -rf "$p"
	mkdir -p "$d" "$p" "$root/digests"
	archive="$d/${2}_${3}_${os}_${arch}.tar.gz"
	case "$2" in
	lea)
		mkdir -p "$p/lea-v$3/bin"
		printf '#!/bin/sh\necho "v%s"\n' "$3" >"$p/lea-v$3/bin/lea"
		chmod 0755 "$p/lea-v$3/bin/lea"
		echo readme >"$p/lea-v$3/README.md"
		(cd "$p" && tar -czf "$archive" "lea-v$3")
		;;
	*)
		mkdir -p "$p/scripts"
		# shellcheck disable=SC2016 # $launcher_version is the launcher's
		printf '#!/bin/sh\nlauncher_version=dev\nimage_digest=\nvault_image_digest=\nseccomp_profile=\necho "%s launcher $launcher_version"\n' "$2" >"$p/scripts/$2"
		chmod 0755 "$p/scripts/$2"
		files="scripts/$2"
		if [ "$2" = lockfile ]; then echo '{"defaultAction":"SCMP_ACT_ERRNO"}' >"$p/seccomp.json"; files="$files seccomp.json"; fi
		# shellcheck disable=SC2086
		(cd "$p" && tar -czf "$archive" $files)
		echo "sha256:$(hex "$1-$3")" >"$root/digests/ghcr.io_davidgodefroid_$1_$3"
		echo "sha256:$(hex "$1-$3-vault")" >"$root/digests/ghcr.io_davidgodefroid_$1_$3-vault"
		;;
	esac
	echo "not a real bundle" >"$d/checksums.txt.sigstore.json"
	(cd "$d" && for f in *.tar.gz; do printf '%s  %s\n' "$(sha256 "$f")" "$f"; done >checksums.txt)
}
fam lea lea 0.4.0
fam locksql locksql 0.13.0
fam lockmq lockmq 0.6.0
fam lockhttp lockhttp 0.7.0
fam lockfile lockfile 0.6.0
# lox: the lockhub fixture of the tests above, at the tap's version. With
# --version the mirror holds lockhub's vX.Y.Z/ folders; for the family,
# <repository>/vX.Y.Z/: lockhub/ is the same folder.
release 0.3.0
ln -s . "$root/rel/lockhub"

# formula DIR REPOSITORY TOOL VERSION [vault]: Formula/TOOL.rb as the tap
# writes it: an url and sha256 per system (only this one exists), and the
# digests of a launcher.
formula() {
	f="$1/Formula/$3.rb"
	mkdir -p "$1/Formula"
	{
		echo "class Fake < Formula"
		for sys in darwin_arm64 darwin_amd64 linux_arm64 linux_amd64; do
			a="${3}_${4}_${sys}.tar.gz"
			s=0000000000000000000000000000000000000000000000000000000000000000
			[ "$sys" != "${os}_${arch}" ] || s=$(sha256 "$root/rel/$2/v$4/$a")
			echo "      url \"https://github.com/DavidGodefroid/$2/releases/download/v$4/$a\""
			echo "      sha256 \"$s\""
		done
		echo "  def install"
		case "$3" in
		lox | lea) ;;
		*)
			echo "    image_digest = \"$(cat "$root/digests/ghcr.io_davidgodefroid_$2_$4")\""
			[ "$3" = lockhttp ] || echo "    vault_image_digest = \"$(cat "$root/digests/ghcr.io_davidgodefroid_$2_$4-vault")\""
			;;
		esac
		echo "  end"
		echo "end"
	} >"$f"
}
make_tap() {
	formula "$1" lockhub lox 0.3.0
	formula "$1" lea lea 0.4.0
	formula "$1" locksql locksql 0.13.0
	formula "$1" lockmq lockmq 0.6.0
	formula "$1" lockhttp lockhttp 0.7.0
	formula "$1" lockfile lockfile 0.6.0
	cat >"$1/Formula/lockfamily.rb" <<'RB'
class Lockfamily < Formula
  depends_on "cosign"
  depends_on "davidgodefroid/tap/lea"
  depends_on "davidgodefroid/tap/lockhttp"
  depends_on "davidgodefroid/tap/lockmq"
  depends_on "davidgodefroid/tap/locksql"
  depends_on "davidgodefroid/tap/lox"
  # locklog: no published release yet; added here with its first release.

  on_linux do
    depends_on "davidgodefroid/tap/lockfile"
  end
end
RB
}
make_tap "$root/tap"
# retap NAME FILE SED: a copy of the tap, with FILE edited by SED.
retap() {
	rm -rf "$root/tap-$1"
	cp -R "$root/tap" "$root/tap-$1"
	sed "$3" "$root/tap/Formula/$2" >"$root/tap-$1/Formula/$2"
	cmp -s "$root/tap/Formula/$2" "$root/tap-$1/Formula/$2" && { echo "retap $1: $2 unchanged" >&2; exit 1; }
	return 0
}
lb() { printf '%s' "$HOME/.local/bin/$1"; }
nothing_installed() { [ ! -e "$HOME/.local/bin" ] && [ ! -e "$HOME/.local/share" ]; }
launchers="locksql lockmq lockhttp"
[ "$os" != linux ] || launchers="$launchers lockfile"

# 20. The whole family, with cosign on PATH.
run family
ok=1
[ "$code" = 0 ] || ok=0
[ "$("$(lb lox)")" = "lox 0.3.0" ] || ok=0
[ "$(readlink "$(lb lea)")" = "$HOME/.local/share/lea-install/v0.4.0/bin/lea" ] && [ "$("$(lb lea)" version)" = v0.4.0 ] || ok=0
for t in $launchers; do
	v=$(sed -n 's|.*releases/download/v\([^/]*\)/.*|\1|p' "$root/tap/Formula/$t.rb" | sed -n 1p)
	[ "$(find "$(lb "$t")" -maxdepth 0 -perm 0755 | wc -l)" -eq 1 ] || ok=0
	grep -qx "launcher_version=$v" "$(lb "$t")" || ok=0
	grep -qx "image_digest=$(cat "$root/digests/ghcr.io_davidgodefroid_${t}_$v")" "$(lb "$t")" || ok=0
	if [ "$t" != lockhttp ]; then grep -qx "vault_image_digest=$(cat "$root/digests/ghcr.io_davidgodefroid_${t}_$v-vault")" "$(lb "$t")" || ok=0; fi
	grep -q -- "verify-blob --bundle .* --certificate-identity https://github.com/DavidGodefroid/$t/.github/workflows/release.yml@refs/tags/v$v " "$STUB_LOG" || ok=0
	grep -q -- "^verify --certificate-identity https://github.com/DavidGodefroid/$t/.github/workflows/release.yml@refs/tags/v$v .* ghcr.io/davidgodefroid/$t:$v$" "$STUB_LOG" || ok=0
done
grep -q -- "--certificate-identity https://github.com/DavidGodefroid/lockhub/.github/workflows/release.yml@refs/tags/v0.3.0 " "$STUB_LOG" || ok=0
grep -q -- "--certificate-identity https://github.com/DavidGodefroid/lea/.github/workflows/release.yml@refs/tags/v0.4.0 " "$STUB_LOG" || ok=0
if [ $ok = 1 ]; then pass "family: every tool at its tap version, each verified against its own release workflow"; else fail "family: every tool at its tap version"; fi
if [ "$os" = linux ]; then
	if grep -qx "seccomp_profile=$HOME/.local/share/lockfile/seccomp.json" "$(lb lockfile)" && [ -f "$HOME/.local/share/lockfile/seccomp.json" ]; then
		pass "family: lockfile's seccomp profile"
	else fail "family: lockfile's seccomp profile"; fi
else
	if [ ! -e "$(lb lockfile)" ] && grep -q 'lockfile: Linux only, skipped' "$root/out"; then pass "family: lockfile skipped (not Linux)"; else fail "family: lockfile skipped (not Linux)"; fi
fi
if grep -q 'locklog: no published release yet, skipped' "$root/out" && grep -q 'next step: lox init' "$root/out"; then pass "family: locklog skipped, next step lox init"; else fail "family: locklog skipped, next step lox init"; fi
if [ ! -e "$(lb cosign)" ] && ! grep -q '^curl' "$STUB_LOG" && ! grep -q '^docker' "$STUB_LOG"; then pass "family: cosign on PATH used, nothing downloaded, no docker call"; else fail "family: cosign on PATH used, nothing downloaded, no docker call"; fi

# 21. Installing again over it.
run family
if [ "$code" = 0 ] && [ "$("$(lb lea)" version)" = v0.4.0 ] && [ "$("$(lb lox)")" = "lox 0.3.0" ]; then pass "family: a second install replaces the first"; else fail "family: a second install replaces the first"; fi

# 22. Without cosign: the pinned cosign is downloaded, used, then installed.
TPATH="$root/nocosign" run familynocosign
if [ "$code" = 0 ] && [ "$("$(lb lox)")" = "lox 0.3.0" ] && grep -qx "curl $cosign_url" "$STUB_LOG" &&
	grep -q '^downloaded cosign verify --certificate-identity https://github.com/DavidGodefroid/locksql/' "$STUB_LOG" &&
	cmp -s "$(lb cosign)" "$root/dl/cosign-$os-$arch" && [ "$(find "$(lb cosign)" -maxdepth 0 -perm 0755 | wc -l)" -eq 1 ]; then
	pass "family without cosign: the pinned cosign verifies, then is installed"
else fail "family without cosign: the pinned cosign verifies, then is installed"; fi

# 23. A tap digest that is not the one cosign verifies: nothing installed.
retap digest lockmq.rb "s/^\\(    image_digest = \\)\"sha256:[0-9a-f]*\"/\\1\"sha256:$(hex other)\"/"
TAP="$root/tap-digest" run familydigest
if [ "$code" != 0 ] && nothing_installed && grep -q 'cosign: ghcr.io/davidgodefroid/lockmq:0.6.0 is not' "$root/out"; then pass "family: a tap digest cosign does not verify aborts, nothing installed"; else fail "family: a tap digest cosign does not verify aborts"; fi

# 24. An archive that does not match its formula's sha256: nothing installed.
retap sha lea.rb "/${os}_${arch}/{n;s/sha256 \"[0-9a-f]*\"/sha256 \"$(hex other)\"/;}"
TAP="$root/tap-sha" run familysha
if [ "$code" != 0 ] && nothing_installed && grep -q 'the tap and the release disagree' "$root/out"; then pass "family: formula sha256 mismatch aborts, nothing installed"; else fail "family: formula sha256 mismatch aborts"; fi

# 25. One project's signature that does not verify: nothing installed.
COSIGN_FAIL="DavidGodefroid/lockhttp/" run familysig
if [ "$code" != 0 ] && nothing_installed && grep -q 'signature of the lockhttp checksums.txt does not verify' "$root/out"; then pass "family: one bad signature aborts, nothing installed"; else fail "family: one bad signature aborts"; fi

# 26. A formula whose version is not a release version: refused.
retap ver locksql.rb 's|download/v0\.13\.0/locksql_0\.13\.0_|download/v0.13;id/locksql_0.13;id_|'
TAP="$root/tap-ver" run familyver
if [ "$code" != 0 ] && nothing_installed && grep -q 'locksql.rb has no valid release archive' "$root/out"; then pass "family: invalid formula version refused"; else fail "family: invalid formula version refused"; fi

# 27. A formula without its vault image digest: refused.
retap novault lockmq.rb '/vault_image_digest/d'
TAP="$root/tap-novault" run familynovault
if [ "$code" != 0 ] && nothing_installed && grep -q 'lockmq.rb has no valid vault_image_digest' "$root/out"; then pass "family: missing vault digest refused"; else fail "family: missing vault digest refused"; fi

# 28. No tap: refused before any download.
TAP="$root/no-tap" run familynotap
if [ "$code" != 0 ] && nothing_installed && grep -q 'cannot read the tap' "$root/out"; then pass "family: unreachable tap aborts"; else fail "family: unreachable tap aborts"; fi

# 29. A tool the meta formula names that this script does not know: skipped
# with a message, the others installed.
retap extra lockfamily.rb 's|^  depends_on "cosign"$|  depends_on "davidgodefroid/tap/lockfoo"|'
TAP="$root/tap-extra" run familyextra
if [ "$code" = 0 ] && grep -q 'also names lockfoo' "$root/out" && [ "$("$(lb lox)")" = "lox 0.3.0" ]; then pass "family: an unknown tool of the meta formula is skipped"; else fail "family: an unknown tool of the meta formula is skipped"; fi

# 30. ~/.local/bin/lea a directory: refused.
mkdir -p "$root/home/leadir/.local/bin/lea"
chmod 0755 "$root/home/leadir/.local" "$root/home/leadir/.local/bin"
run leadir
if [ "$code" != 0 ] && [ ! -e "$(lb lox)" ] && grep -q 'is a directory' "$root/out"; then pass "family: ~/.local/bin/lea a directory, refused"; else fail "family: ~/.local/bin/lea a directory, refused"; fi

# 31. A cosign 2 on PATH (it does not find signatures made in the sigstore
# bundle format only): the pinned cosign is downloaded and used, and not
# installed over the user's own.
mkdir -p "$root/oldcosign"
for p in "$root/nocosign"/*; do ln -sf "$(readlink "$p")" "$root/oldcosign/${p##*/}"; done
{
	cat <<'STUB'
#!/bin/sh
if [ "$1" = version ]; then printf 'GitVersion:    v2.6.1\n'; exit 0; fi
LOG_PREFIX="old "
STUB
	cat "$root/cosign-stub"
} >"$root/oldcosign/cosign"
chmod 0755 "$root/oldcosign/cosign"
TPATH="$root/oldcosign" run familyoldcosign
if [ "$code" = 0 ] && [ "$("$(lb lox)")" = "lox 0.3.0" ] && grep -qx "curl $cosign_url" "$STUB_LOG" &&
	grep -q '^downloaded cosign verify --certificate-identity https://github.com/DavidGodefroid/locksql/' "$STUB_LOG" &&
	! grep -q '^old .*verify' "$STUB_LOG" && [ ! -e "$(lb cosign)" ] && grep -q 'older than v3' "$root/out"; then
	pass "family with cosign 2 on PATH: the pinned cosign verifies, the user's is left alone"
else fail "family with cosign 2 on PATH: the pinned cosign verifies, the user's is left alone"; fi

echo "$runs tests, $fails failed"
[ "$fails" = 0 ]
