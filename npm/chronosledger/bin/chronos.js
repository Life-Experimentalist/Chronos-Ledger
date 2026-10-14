#!/usr/bin/env node
// Copyright 2026 Chronos Ledger Contributors (Apache 2.0)

// Launcher for the chronos native binary.
//
// chronos is a Rust program, so this package ships no JavaScript implementation.
// The binary arrives through optionalDependencies: one package per platform, each
// declaring `os` and `cpu`, so npm installs the one that matches and skips the
// rest. There is no install script. This file finds the binary and runs it.
"use strict";

const { spawnSync } = require("node:child_process");
const os = require("node:os");
const path = require("node:path");

// npm refuses new package names that start with `win32-`, so the Windows
// packages are named `windows-*`. Their `os` field still says `win32`.
const PLATFORMS = {
  "linux-x64": "chronosledger-linux-x64",
  "linux-arm64": "chronosledger-linux-arm64",
  "darwin-x64": "chronosledger-darwin-x64",
  "darwin-arm64": "chronosledger-darwin-arm64",
  "win32-x64": "chronosledger-windows-x64",
  "win32-arm64": "chronosledger-windows-arm64",
};

const key = `${process.platform}-${process.arch}`;
const pkg = PLATFORMS[key];

function fail(message) {
  console.error(`chronos: ${message}`);
  process.exit(127);
}

if (!pkg) {
  fail(
    `there is no prebuilt binary for ${key}.\n` +
      "Install from source with: cargo install --locked chronosledger",
  );
}

let binary;
try {
  const manifest = require.resolve(`${pkg}/package.json`);
  const exe = process.platform === "win32" ? "chronos.exe" : "chronos";
  binary = path.join(path.dirname(manifest), "bin", exe);
} catch (_) {
  fail(
    `the ${pkg} package is not installed.\n` +
      "npm skips it when optional dependencies are turned off. Reinstall with:\n" +
      "  npm install -g --include=optional chronosledger@latest\n" +
      "or install from source with: cargo install --locked chronosledger",
  );
}

const result = spawnSync(binary, process.argv.slice(2), { stdio: "inherit" });

if (result.error) {
  fail(`could not run ${binary}: ${result.error.message}`);
}
if (result.signal) {
  // Let the same signal end this process, so a shell sees what really happened.
  process.kill(process.pid, result.signal);
  // Reached only if the signal was ignored or cannot be delivered here.
  process.exit(128 + (os.constants.signals[result.signal] || 0));
}
process.exit(result.status === null ? 1 : result.status);
