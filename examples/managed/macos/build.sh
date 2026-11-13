#!/bin/sh
# Builds a macOS package that installs the company's managed.toml in
# /Library/Application Support/lockfamily (lockfamily docs/managed.md#macos).
#
#   cd examples/managed && sh macos/build.sh 1.0.0
#
# Run it from the directory that holds managed.toml, and signer.toml with
# managed.toml.sigstore.json when you sign it: they are packaged when
# present. Bump the version with every change of the policy.
set -eu
version=${1:?usage: sh macos/build.sh VERSION}
here=$(cd "$(dirname "$0")" && pwd)
root=$(mktemp -d)
trap 'rm -rf "$root"' EXIT
dir="$root/Library/Application Support/lockfamily"
mkdir -p "$dir"
cp managed.toml "$dir/"
if [ -f managed.toml.sigstore.json ]; then
	cp signer.toml managed.toml.sigstore.json "$dir/"
fi
chmod 0755 "$dir"
chmod 0644 "$dir"/*
# --ownership recommended (the default) installs the payload root:wheel;
# postinstall sets it again, with the modes.
pkgbuild --root "$root" --install-location / --scripts "$here/scripts" \
	--identifier com.example-corp.lockfamily-managed --version "$version" \
	--ownership recommended "example-corp-lockfamily-managed-$version.pkg"
