// Copyright 2026 Chronos Ledger Contributors
// SPDX-License-Identifier: Apache-2.0

//! Which channel installed a `chronos` binary, worked out from where it lives.
//!
//! The path is the only source of truth. A receipt says what our install script
//! did, but a copy without one is not "unmanaged", and a copy with one may have
//! been moved. This is the lesson dev-prune paid for: three commands each had
//! their own idea of the channel, and one of them deleted a file WinGet owned.
//!
//! Only three channels are supported, so only three can change a copy. Every
//! other location is reported and left alone, whoever put it there.

use std::path::{Path, PathBuf};

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Channel {
    /// install.sh / install.ps1, in the managed directory.
    Installer,
    /// `brew install life-experimentalist/tap/chronos`.
    Homebrew,
    /// `scoop install chronos` from the Life-Experimentalist bucket.
    Scoop,
    /// A manager this project does not publish to. Named, never touched.
    Foreign(&'static str),
    /// Anywhere else: a local build, a hand-copied file. Never touched.
    Unknown,
}

const HOMEBREW: &[&str] = &["/cellar/", "/homebrew/", "/linuxbrew/"];
const SCOOP: &[&str] = &["/scoop/apps/", "/scoop/shims/"];
const FOREIGN: &[(&str, &str)] = &[
    ("/.cargo/", "Cargo"),
    ("/node_modules/", "npm"),
    ("/.bun/", "Bun"),
    ("/winget/", "WinGet"),
    ("/uv/tools/", "uv"),
    ("/pipx/", "pipx"),
    ("/.volta/", "Volta"),
    ("/mise/", "mise"),
    ("/.asdf/", "asdf"),
    ("/nix/store/", "Nix"),
    ("/usr/bin/", "the system package manager"),
];

impl Channel {
    pub fn detect(exe: &Path) -> Channel {
        Self::detect_with(exe, &managed_root())
    }

    fn detect_with(exe: &Path, managed: &Path) -> Channel {
        let norm = |p: &Path| p.to_string_lossy().replace('\\', "/").to_lowercase();
        let path = norm(exe);
        if path.starts_with(&(norm(&managed.join("bin")) + "/")) {
            return Channel::Installer;
        }
        if SCOOP.iter().any(|m| path.contains(m)) {
            return Channel::Scoop;
        }
        if HOMEBREW.iter().any(|m| path.contains(m)) {
            return Channel::Homebrew;
        }
        FOREIGN
            .iter()
            .find(|(m, _)| path.contains(m))
            .map_or(Channel::Unknown, |(_, name)| Channel::Foreign(name))
    }

    pub fn name(self) -> &'static str {
        match self {
            Channel::Installer => "install script",
            Channel::Homebrew => "Homebrew",
            Channel::Scoop => "Scoop",
            Channel::Foreign(name) => name,
            Channel::Unknown => "unknown",
        }
    }

    /// The manager's own command, for channels that have one.
    pub fn upgrade_argv(self) -> Option<&'static [&'static str]> {
        match self {
            Channel::Homebrew => Some(&["brew", "upgrade", "chronos"]),
            Channel::Scoop => Some(&["scoop", "update", "chronos"]),
            _ => None,
        }
    }

    pub fn uninstall_argv(self) -> Option<&'static [&'static str]> {
        match self {
            Channel::Homebrew => Some(&["brew", "uninstall", "chronos"]),
            Channel::Scoop => Some(&["scoop", "uninstall", "chronos"]),
            _ => None,
        }
    }
}

/// Where the install scripts put the CLI: `~/.chronos` on Linux and macOS,
/// `%LOCALAPPDATA%\chronos` on Windows. The binary goes in `bin/`, the receipt
/// beside it. No spaces, so the PATH entry needs no quoting anywhere.
pub fn managed_root() -> PathBuf {
    if let Some(dir) = std::env::var_os("CHRONOS_INSTALL_DIR") {
        return PathBuf::from(dir);
    }
    #[cfg(windows)]
    let base = dirs::data_local_dir().map(|d| d.join("chronos"));
    #[cfg(not(windows))]
    let base = dirs::home_dir().map(|d| d.join(".chronos"));
    base.unwrap_or_else(|| PathBuf::from(".chronos"))
}

pub fn exe_name() -> &'static str {
    if cfg!(windows) {
        "chronos.exe"
    } else {
        "chronos"
    }
}

/// Every `chronos` on PATH, resolved through symlinks and without duplicates.
pub fn copies_on_path() -> Vec<PathBuf> {
    let mut seen: Vec<PathBuf> = Vec::new();
    let Some(path) = std::env::var_os("PATH") else {
        return seen;
    };
    for dir in std::env::split_paths(&path) {
        let candidate = dir.join(exe_name());
        if !candidate.is_file() {
            continue;
        }
        let real = candidate.canonicalize().unwrap_or(candidate);
        if !seen.contains(&real) {
            seen.push(real);
        }
    }
    seen
}

#[cfg(test)]
mod tests {
    use super::*;

    fn detect(p: &str) -> Channel {
        Channel::detect_with(Path::new(p), Path::new("/home/a/.chronos"))
    }

    #[test]
    fn each_supported_channel_is_recognised() {
        assert_eq!(detect("/home/a/.chronos/bin/chronos"), Channel::Installer);
        assert_eq!(
            detect("/opt/homebrew/Cellar/chronos/0.13.0/bin/chronos"),
            Channel::Homebrew
        );
        assert_eq!(
            detect(r"C:\Users\a\scoop\apps\chronos\current\chronos.exe"),
            Channel::Scoop
        );
    }

    #[test]
    fn other_managers_are_named_and_loose_files_are_unknown() {
        assert_eq!(
            detect("/home/a/.cargo/bin/chronos"),
            Channel::Foreign("Cargo")
        );
        assert_eq!(
            detect("/usr/bin/chronos"),
            Channel::Foreign("the system package manager")
        );
        assert_eq!(detect("/usr/local/bin/chronos"), Channel::Unknown);
        assert_eq!(detect("/home/a/.chronos/bin-old/chronos"), Channel::Unknown);
    }

    #[test]
    fn only_supported_channels_have_manager_commands() {
        assert!(Channel::Installer.upgrade_argv().is_none());
        assert!(Channel::Foreign("Cargo").uninstall_argv().is_none());
        assert!(Channel::Unknown.uninstall_argv().is_none());
        assert_eq!(Channel::Scoop.uninstall_argv().unwrap()[0], "scoop");
    }
}
