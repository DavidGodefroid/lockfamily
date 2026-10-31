#!/bin/sh
# Tests of install.sh against a fake lockhub release in a temporary
# directory (LOCK_RELEASE_BASE), with a stub cosign: no network, nothing
# outside the temporary HOME. Without cosign on PATH, install.sh downloads
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
# bundle. Its "lock" is a script that prints its version.
release() {
	v=$1
	d="$root/rel/v$v"
	mkdir -p "$d" "$root/pkg"
	printf '#!/bin/sh\necho "lock %s"\n' "$v" >"$root/pkg/lock"
	chmod 0755 "$root/pkg/lock"
	echo license >"$root/pkg/LICENSE"
	(cd "$root/pkg" && tar -czf "$d/lock_${v}_${os}_${arch}.tar.gz" lock LICENSE)
	echo "not a real bundle" >"$d/checksums.txt.sigstore.json"
	(cd "$d" && for f in lock_*.tar.gz; do printf '%s  %s\n' "$(sha256 "$f")" "$f"; done >checksums.txt)
}
release 1.2.3

# Stub tools, first on PATH: cosign logs its arguments and exits with
# $COSIGN_RC; docker logs that it was called (install.sh must never call it);
# curl logs its URL and serves $root/dl/<file name> (exit 22 when missing).
mkdir -p "$root/stub" "$root/nocosign" "$root/dl"
cat >"$root/stub/cosign" <<'STUB'
#!/bin/sh
printf '%s\n' "$*" >>"$STUB_LOG"
exit "${COSIGN_RC:-0}"
STUB
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
cat >"$root/dl/cosign-$os-$arch" <<'STUB'
#!/bin/sh
printf 'downloaded cosign %s\n' "$*" >>"$STUB_LOG"
exit "${COSIGN_RC:-0}"
STUB
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
	tpath=${TPATH:-$root/stub:$PATH}
	inst=${INSTALLER:-$installer}
	dl=${DL_DIR:-$root/dl}
	unset COSIGN_RC TPATH INSTALLER DL_DIR
	code=0
	COSIGN_RC=$rc PATH=$tpath DL_DIR=$dl LOCK_RELEASE_BASE="$root/rel" sh "$inst" "$@" >"$root/out" 2>&1 || code=$?
}
bin() { printf '%s' "$HOME/.local/bin/lock"; }

# 1. A verified install.
run ok --version v1.2.3
if [ "$code" = 0 ] && [ -x "$(bin)" ] && [ "$("$(bin)")" = "lock 1.2.3" ] &&
	[ "$(find "$(bin)" -maxdepth 0 -perm 0755 | wc -l)" -eq 1 ] &&
	grep -q -- "--certificate-identity https://github.com/DavidGodefroid/lockhub/.github/workflows/release.yml@refs/tags/v1.2.3" "$STUB_LOG" &&
	grep -q -- "--certificate-oidc-issuer https://token.actions.githubusercontent.com" "$STUB_LOG" &&
	grep -q -- "--bundle" "$STUB_LOG"; then
	pass "verified install of v1.2.3 into ~/.local/bin/lock (0755)"
else fail "verified install"; fi
if ! grep -q '^curl' "$STUB_LOG" && ! grep -q '^downloaded cosign' "$STUB_LOG"; then pass "cosign on PATH preferred: no cosign download"; else fail "cosign on PATH preferred: no cosign download"; fi
if grep -q '^docker' "$STUB_LOG"; then fail "docker was called"; else pass "no docker call (no image pulled)"; fi
if grep -q 'not on your PATH' "$root/out" && grep -q 'export PATH=' "$root/out"; then pass "PATH hint"; else fail "PATH hint"; fi

# 2. The version without its v.
run nov --version 1.2.3
if [ "$code" = 0 ] && [ "$("$(bin)")" = "lock 1.2.3" ]; then pass "--version without v"; else fail "--version without v"; fi

# 3. A signature that does not verify aborts and installs nothing.
COSIGN_RC=1 run badsig --version v1.2.3
if [ "$code" != 0 ] && [ ! -e "$(bin)" ] && grep -q 'does not verify' "$root/out"; then pass "signature failure aborts"; else fail "signature failure aborts"; fi

# 4. A failed signature leaves a former install in place.
run keep --version v1.2.3
COSIGN_RC=1 run keep --version v1.2.3
if [ "$code" != 0 ] && [ "$("$(bin)")" = "lock 1.2.3" ]; then pass "failure keeps the former lock"; else fail "failure keeps the former lock"; fi

# 5. Without cosign on PATH: the pinned cosign is downloaded, checked and
# used from the temporary directory, never installed.
TPATH="$root/nocosign" run nocosign --version v1.2.3
if [ "$code" = 0 ] && [ "$("$(bin)")" = "lock 1.2.3" ] &&
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
want=$(sha256 "$root/rel/v1.2.3/lock_1.2.3_${os}_${arch}.tar.gz")
TPATH="$root/nonet" run sha --version v1.2.3 --sha256 "$want"
if [ "$code" = 0 ] && [ "$("$(bin)")" = "lock 1.2.3" ] && [ ! -s "$STUB_LOG" ]; then pass "--sha256 without cosign"; else fail "--sha256 without cosign"; fi
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
echo tampered >>"$root/rel/v1.2.4/lock_1.2.4_${os}_${arch}.tar.gz"
run tampered --version v1.2.4
if [ "$code" != 0 ] && [ ! -e "$(bin)" ] && grep -q 'checksum mismatch' "$root/out"; then pass "tampered archive aborts"; else fail "tampered archive aborts"; fi

# 10. An archive missing from checksums.txt aborts.
release 1.2.5
: >"$root/rel/v1.2.5/checksums.txt"
run unlisted --version v1.2.5
if [ "$code" != 0 ] && [ ! -e "$(bin)" ] && grep -q 'not listed' "$root/out"; then pass "unlisted archive aborts"; else fail "unlisted archive aborts"; fi

# 11. A lock whose version differs from the release's aborts.
release 1.2.6
release 1.2.7
cp "$root/rel/v1.2.6/lock_1.2.6_${os}_${arch}.tar.gz" "$root/rel/v1.2.7/lock_1.2.7_${os}_${arch}.tar.gz"
(cd "$root/rel/v1.2.7" && printf '%s  %s\n' "$(sha256 "lock_1.2.7_${os}_${arch}.tar.gz")" "lock_1.2.7_${os}_${arch}.tar.gz" >checksums.txt)
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

# 14. ~/.local/bin/lock as a link to a file others can write: refused.
mkdir -p "$root/shared" "$root/home/linkw/.local/bin"
echo old >"$root/shared/lock"
chmod 0666 "$root/shared/lock"
ln -s "$root/shared/lock" "$root/home/linkw/.local/bin/lock"
run linkw --version v1.2.3
if [ "$code" != 0 ] && [ "$(cat "$root/shared/lock")" = old ] && [ -L "$(bin)" ] && grep -q 'writable by others' "$root/out"; then pass "link to a world-writable file refused"; else fail "link to a world-writable file refused"; fi

# 15. ... or in a directory others can write: refused.
mkdir -p "$root/sharedd" "$root/home/linkd/.local/bin"
chmod 0777 "$root/sharedd"
echo old >"$root/sharedd/lock"
chmod 0644 "$root/sharedd/lock"
ln -s "$root/sharedd/lock" "$root/home/linkd/.local/bin/lock"
run linkd --version v1.2.3
if [ "$code" != 0 ] && [ "$(cat "$root/sharedd/lock")" = old ] && grep -q 'writable by others' "$root/out"; then pass "link into a world-writable directory refused"; else fail "link into a world-writable directory refused"; fi

# 16. A link to the user's own, private file is replaced by the binary
# (the link itself, never the file it pointed to).
mkdir -p "$root/home/linkok/.local/bin" "$root/home/linkok/opt"
chmod 0755 "$root/home/linkok/.local/bin" "$root/home/linkok/opt"
echo old >"$root/home/linkok/opt/lock"
chmod 0755 "$root/home/linkok/opt/lock"
ln -s "$root/home/linkok/opt/lock" "$root/home/linkok/.local/bin/lock"
run linkok --version v1.2.3
if [ "$code" = 0 ] && [ ! -L "$(bin)" ] && [ "$("$(bin)")" = "lock 1.2.3" ] && [ "$(cat "$root/home/linkok/opt/lock")" = old ]; then pass "private link replaced, its target untouched"; else fail "private link replaced, its target untouched"; fi

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

echo "$runs tests, $fails failed"
[ "$fails" = 0 ]
