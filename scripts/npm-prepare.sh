#!/usr/bin/env sh
# Copyright 2026 Chronos Ledger Contributors (Apache 2.0)

# Turn the release assets into publishable npm packages.
#
# Produces one package per platform, each holding the real binary and declaring
# `os` and `cpu` so npm installs exactly the matching one, plus the `chronosledger`
# dispatcher that lists all six as optionalDependencies.
#
# The platform manifests are generated from npm/platforms/*.tmpl rather than checked
# in: six near-identical files whose only job is to carry a version are six files
# that drift.
#
# Usage: scripts/npm-prepare.sh <tag> <assets-dir> <out-dir>
#   tag         the release tag, for example v0.18.0
#   assets-dir  holds chronos-<tag>-<os>-<arch>[.exe] and a .sha256 file for each
#   out-dir     is created; each subdirectory is ready for `npm publish`
set -eu

usage="usage: $0 <tag> <assets-dir> <out-dir>"
tag="${1:?$usage}"
assets="${2:?$usage}"
out="${3:?$usage}"

case "$tag" in
    v[0-9]*.[0-9]*.[0-9]*) ;;
    *) echo "tag must look like v1.2.3, got: $tag" >&2; exit 2 ;;
esac
version="${tag#v}"

repo_root=$(CDPATH='' cd -- "$(dirname -- "$0")/.." && pwd)

if command -v sha256sum >/dev/null 2>&1; then
    hash_of() { sha256sum "$1" | cut -d' ' -f1; }
else
    hash_of() { shasum -a 256 "$1" | cut -d' ' -f1; }
fi

mkdir -p "$out"

# Fed by heredoc rather than by a pipe: a piped `while` runs in a subshell, where the
# `exit 1` on a missing asset would end the subshell and let the script carry on to
# publish a set of packages with a hole in it.
#
# Columns: asset-os asset-arch node-os node-cpu exe-suffix package-name label
# An exe-suffix of "-" means none.
# The asset names come from .github/workflows/release.yml. The node names are what
# npm matches `os` and `cpu` against (process.platform and process.arch). Windows
# packages are named windows-*, never win32-*: npm's new-name spam filter answers
# E403 to the latter. Only the `os` field says win32.
while read -r asset_os asset_arch node_os node_cpu suffix pkg label; do
    [ -n "$asset_os" ] || continue
    [ "$suffix" = "-" ] && suffix=""

    asset="$assets/chronos-$tag-$asset_os-$asset_arch$suffix"
    [ -f "$asset" ] || { echo "missing asset: $asset" >&2; exit 1; }
    [ -f "$asset.sha256" ] || { echo "missing checksum: $asset.sha256" >&2; exit 1; }

    # The sidecar holds `<hex>  <file name>`. Only the digest is compared, so a
    # sidecar written with a path in front of the name still works.
    want=$(cut -d' ' -f1 "$asset.sha256")
    got=$(hash_of "$asset")
    if [ "$want" != "$got" ]; then
        echo "checksum mismatch for $asset" >&2
        echo "  expected $want" >&2
        echo "  got      $got" >&2
        exit 1
    fi

    pkg_name="chronosledger-$pkg"
    dir="$out/$pkg_name"
    rm -rf "$dir"
    mkdir -p "$dir/bin"

    exe="chronos$suffix"
    cp "$asset" "$dir/bin/$exe"
    # npm keeps the mode bits it finds in the tarball, so the executable bit is set
    # here and not at install time.
    chmod +x "$dir/bin/$exe"

    # Apache-2.0 asks for a copy of the licence beside anything redistributed, and each
    # of these packages can be installed on its own.
    cp "$repo_root/LICENSE" "$dir/LICENSE"

    # A tag, a name or a label never contains a character that is special to sed here.
    sed -e "s/@NAME@/$pkg_name/g" -e "s/@VERSION@/$version/g" \
        -e "s/@OS_LABEL@/$label/g" -e "s/@ARCH@/$asset_arch/g" \
        -e "s/@NODE_OS@/$node_os/g" -e "s/@NODE_CPU@/$node_cpu/g" \
        "$repo_root/npm/platforms/package.json.tmpl" > "$dir/package.json"
    sed -e "s/@NAME@/$pkg_name/g" -e "s/@OS_LABEL@/$label/g" -e "s/@ARCH@/$asset_arch/g" \
        "$repo_root/npm/platforms/README.md.tmpl" > "$dir/README.md"

    echo "prepared $pkg_name"
done <<'TARGETS'
linux   x64    linux  x64    -       linux-x64      Linux
linux   arm64  linux  arm64  -       linux-arm64    Linux
darwin  x64    darwin x64    -       darwin-x64     macOS
darwin  arm64  darwin arm64  -       darwin-arm64   macOS
windows x64    win32  x64    .exe    windows-x64    Windows
windows arm64  win32  arm64  .exe    windows-arm64  Windows
TARGETS

# The dispatcher. Its own version and every optionalDependency version are rewritten
# from the tag, so a release cannot ship a manifest pinned to the previous one.
dispatcher="$out/chronosledger"
rm -rf "$dispatcher"
mkdir -p "$dispatcher"
cp -R "$repo_root/npm/chronosledger/bin" "$dispatcher/bin"
chmod +x "$dispatcher/bin/chronos.js"
cp "$repo_root/npm/chronosledger/README.md" "$dispatcher/README.md"
cp "$repo_root/LICENSE" "$dispatcher/LICENSE"
sed "s/\"0\.0\.0\"/\"$version\"/g" "$repo_root/npm/chronosledger/package.json" > "$dispatcher/package.json"

# Prove the rewrite happened rather than trusting the sed. A dispatcher still pointing
# at another version installs the wrong binary, which is a quieter failure than not
# installing at all. Expected: its own version plus six optionalDependencies.
found=$(grep -c "\"$version\"" "$dispatcher/package.json" || true)
if [ "$found" -ne 7 ] || grep -q '"0\.0\.0"' "$dispatcher/package.json"; then
    echo "expected 7 occurrences of $version in the dispatcher manifest, found $found" >&2
    cat "$dispatcher/package.json" >&2
    exit 1
fi
echo "prepared chronosledger (dispatcher) at $version"
