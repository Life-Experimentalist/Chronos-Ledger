#!/bin/sh
# Copyright 2026 Chronos Ledger Contributors
# SPDX-License-Identifier: Apache-2.0
#
# Install the chronos CLI on Linux or macOS.
#
#   curl -fsSL https://chronos.vkrishna04.me/install.sh | sh
#   curl -fsSL https://chronos.vkrishna04.me/install.sh | sh -s -- --version 0.13.0
#
# Puts the binary in ~/.chronos/bin (or $CHRONOS_INSTALL_DIR/bin), checks it
# against the release's .sha256 file, adds the directory to PATH through one
# line in your shell's startup file, and records that line in install.json so
# `chronos self uninstall` can take exactly that line back out.
#
# It never touches a chronos installed any other way. If it finds one, it says
# where, and which tool removes it.

set -eu

REPO="https://github.com/Life-Experimentalist/Chronos-Ledger"
VERSION=""
FORCE=0

while [ $# -gt 0 ]; do
  case "$1" in
    --version) VERSION="${2:?--version needs a value, for example 0.13.0}"; shift 2 ;;
    --force) FORCE=1; shift ;;
    -h|--help)
      echo "usage: install.sh [--version X.Y.Z] [--force]"
      exit 0 ;;
    *) echo "install.sh: unknown option $1" >&2; exit 2 ;;
  esac
done

fail() { echo "install.sh: $*" >&2; exit 1; }
need() { command -v "$1" >/dev/null 2>&1 || fail "$1 is required"; }
need curl
need uname

case "$(uname -s)" in
  Linux) OS=linux ;;
  Darwin) OS=darwin ;;
  *) fail "no chronos binary for $(uname -s). On Windows use install.ps1." ;;
esac
case "$(uname -m)" in
  x86_64|amd64) ARCH=x64 ;;
  aarch64|arm64) ARCH=arm64 ;;
  *) fail "no chronos binary for $(uname -m)" ;;
esac

if [ -z "$VERSION" ]; then
  # The redirect releases/latest answers with names the tag. Reading it spends
  # none of the unauthenticated API rate limit.
  location=$(curl -fsSI "$REPO/releases/latest" | tr -d '\r' | sed -n 's/^[Ll]ocation: *//p' | tail -n 1)
  VERSION=${location##*/releases/tag/}
  [ -n "$location" ] && [ "$VERSION" != "$location" ] || fail "could not find the latest release on GitHub"
fi
VERSION=${VERSION#v}

ROOT=${CHRONOS_INSTALL_DIR:-$HOME/.chronos}
BIN_DIR="$ROOT/bin"
TARGET="$BIN_DIR/chronos"

if [ "$FORCE" -eq 0 ] && [ -x "$TARGET" ]; then
  current=$("$TARGET" --version 2>/dev/null | awk '{print $NF}') || current=""
  if [ "$current" = "$VERSION" ]; then
    echo "chronos $VERSION is already installed at $TARGET. Pass --force to reinstall."
    exit 0
  fi
fi

ASSET="chronos-v$VERSION-$OS-$ARCH"
URL="$REPO/releases/download/v$VERSION/$ASSET"
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT INT TERM

if ! curl -fsSL "$URL.sha256" -o "$TMP/sum"; then
  fail "release v$VERSION has no $ASSET. Binaries upload a few minutes after a release is published, so try again shortly. Releases before 0.13.0 have no CLI."
fi
echo "Downloading $ASSET"
curl -fSL --progress-bar "$URL" -o "$TMP/chronos" || fail "could not download $URL"

expected=$(awk '{print tolower($1)}' "$TMP/sum")
if command -v sha256sum >/dev/null 2>&1; then
  actual=$(sha256sum "$TMP/chronos" | awk '{print $1}')
else
  need shasum
  actual=$(shasum -a 256 "$TMP/chronos" | awk '{print $1}')
fi
[ "${#expected}" -eq 64 ] || fail "the checksum file for $ASSET is not a SHA-256 digest"
[ "$expected" = "$actual" ] || fail "checksum mismatch for $ASSET (expected $expected, got $actual). Nothing was installed."

mkdir -p "$BIN_DIR"
chmod 755 "$TMP/chronos"
# Same filesystem as the target, so the final rename cannot leave half a file.
cp "$TMP/chronos" "$TARGET.new"
mv -f "$TARGET.new" "$TARGET"

# PATH. The line names the absolute directory, so it means the same thing in
# every shell and matches exactly when uninstall looks for it.
case "${SHELL:-}" in
  */zsh) RC="$HOME/.zshrc"; LINE="export PATH=\"$BIN_DIR:\$PATH\"" ;;
  */bash) if [ "$OS" = darwin ]; then RC="$HOME/.bash_profile"; else RC="$HOME/.bashrc"; fi
          LINE="export PATH=\"$BIN_DIR:\$PATH\"" ;;
  */fish) RC="$HOME/.config/fish/config.fish"; LINE="fish_add_path \"$BIN_DIR\"" ;;
  *) RC="$HOME/.profile"; LINE="export PATH=\"$BIN_DIR:\$PATH\"" ;;
esac

path_file=""
# A line an earlier run wrote is kept on record, so reinstalling never loses it.
for candidate in "$HOME/.zshrc" "$HOME/.bashrc" "$HOME/.bash_profile" "$HOME/.profile" "$HOME/.config/fish/config.fish"; do
  for candidate_line in "export PATH=\"$BIN_DIR:\$PATH\"" "fish_add_path \"$BIN_DIR\""; do
    if [ -f "$candidate" ] && grep -Fxq "$candidate_line" "$candidate"; then
      path_file=$candidate; LINE=$candidate_line
      break 2
    fi
  done
done
if [ -z "$path_file" ]; then
  case ":$PATH:" in
    *":$BIN_DIR:"*) ;;
    *)
      mkdir -p "$(dirname "$RC")"
      printf '\n%s\n' "$LINE" >> "$RC"
      path_file=$RC
      echo "Added $BIN_DIR to PATH in $RC. Open a new terminal, or run: $LINE"
      ;;
  esac
fi

json() { printf '%s' "$1" | sed 's/\\/\\\\/g; s/"/\\"/g'; }
if [ -n "$path_file" ]; then
  entry="{\"kind\":\"rc-file\",\"file\":\"$(json "$path_file")\",\"line\":\"$(json "$LINE")\"}"
else
  entry=null
fi
cat > "$ROOT/install.json" <<EOF
{
  "schema": 1,
  "version": "$VERSION",
  "channel": "installer",
  "installed_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "path_entry": $entry
}
EOF

echo "Installed chronos $VERSION to $TARGET"

# Other copies are reported, never removed: each belongs to whatever installed it.
old_ifs=$IFS; IFS=:
for dir in $PATH; do
  [ -n "$dir" ] && [ -x "$dir/chronos" ] || continue
  [ "$dir/chronos" -ef "$TARGET" ] && continue
  echo "warning: another chronos is on PATH at $dir/chronos. Remove it with the tool that installed it (brew uninstall chronos, or delete it if you copied it there), or it may run instead of this one." >&2
done
IFS=$old_ifs
