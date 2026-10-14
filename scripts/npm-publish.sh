#!/usr/bin/env sh
# Copyright 2026 Chronos Ledger Contributors (Apache 2.0)

# Publish the packages that scripts/npm-prepare.sh produced: the six platform packages
# first, then the chronosledger dispatcher that depends on them.
#
# Usage: scripts/npm-publish.sh [--local] <out-dir>
#
#   (default)  publish with --provenance. Needs npm 11.5.1 or newer and a trusted
#              publisher registered on each package, so it runs from publish.yml.
#   --local    publish from a workstation with your own `npm login` and no provenance.
#              This is how the package names are claimed the first time, because a
#              trusted publisher can only be attached to a package that already exists.
#
# Safe to run again: a version that is already on the registry is skipped.
set -eu

usage="usage: $0 [--local] <out-dir>"
local_mode=0
if [ "${1:-}" = "--local" ]; then
    local_mode=1
    shift
fi
packages="${1:?$usage}"

# An absolute path can never be mistaken for anything but a directory. A relative
# `npm-out/chronosledger-linux-x64` matches npm's `<owner>/<repo>` GitHub shorthand, so
# npm skips the filesystem and runs `git ls-remote ssh://git@github.com/...`, which fails
# with `Permission denied (publickey)` and looks nothing like the path bug it is.
packages=$(CDPATH='' cd -- "$packages" && pwd)

if [ "$local_mode" -eq 1 ]; then
    set --
else
    set -- --provenance
fi

published=""
skipped=""

# Platform packages before the dispatcher: the dispatcher's optionalDependencies must
# already resolve when someone installs it a minute after it appears.
for pkg in \
    chronosledger-linux-x64 chronosledger-linux-arm64 \
    chronosledger-darwin-x64 chronosledger-darwin-arm64 \
    chronosledger-windows-x64 chronosledger-windows-arm64 \
    chronosledger
do
    dir="$packages/$pkg"
    [ -d "$dir" ] || { echo "missing package directory: $dir" >&2; exit 1; }

    version=$(sed -n 's/^  "version": "\([^"]*\)".*/\1/p' "$dir/package.json")
    [ -n "$version" ] || { echo "no version in $dir/package.json" >&2; exit 1; }

    # Re-running a publish after fixing one failed job is normal. Without this check the
    # second run stops with EPUBLISHCONFLICT at whichever package succeeded the first time.
    if npm view "$pkg@$version" version >/dev/null 2>&1; then
        echo "$pkg@$version is already on the registry, skipping."
        skipped="$skipped $pkg"
        continue
    fi

    echo "publishing $pkg@$version"
    # --access public matters for a package that does not exist yet, and --provenance
    # refuses to sign a package whose access it cannot confirm.
    npm publish "$dir" "$@" --access public
    published="$published $pkg"
done

echo
echo "published:${published:- none}"
if [ -n "$skipped" ]; then
    echo "already on the registry:$skipped"
fi
