// Copyright 2026 Chronos Ledger Contributors
// SPDX-License-Identifier: Apache-2.0

//! Which channel installed a `chronos` binary, worked out from where it lives.
//!
//! The path is the only source of truth. A receipt says what our install script
//! did, but a copy without one is not "unmanaged", and a copy with one may have
//! been moved. This is the lesson dev-prune paid for: three commands each had
//! their own idea of the channel, and one of them deleted a file WinGet owned.
//!
//! Only the managers this project publishes to can change a copy: the install
//! script, Homebrew, Scoop, npm, Cargo, uv and pipx. A copy fetched by `npx`,
//! `uvx` or `pipx run` lives in a throwaway cache and is never touched at all.
//! Every other location is reported and left alone, whoever put it there.

use std::path::{Path, PathBuf};

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Channel {
    /// install.sh / install.ps1, in the managed directory.
    Installer,
    /// `brew install life-experimentalist/tap/chronos`.
    Homebrew,
    /// `scoop install chronos` from the Life-Experimentalist bucket.
    Scoop,
    /// `npm install -g chronosledger`.
    Npm,
    /// `cargo install chronosledger` or `cargo binstall chronosledger`.
    Cargo,
    /// `uv tool install chronosledger`.
    Uv,
    /// `pipx install chronosledger`.
    Pipx,
    /// A copy fetched into a cache by `npx`, `uvx` or `pipx run`. The string is
    /// the runner. Nothing is installed, so nothing is updated or removed.
    Temporary(&'static str),
    /// A manager this project does not publish to, or a project dependency.
    /// Named, never touched.
    Foreign(&'static str),
    /// Anywhere else: a local build, a hand-copied file. Never touched.
    Unknown,
}

const HOMEBREW: &[&str] = &["/cellar/", "/homebrew/", "/linuxbrew/"];
const SCOOP: &[&str] = &["/scoop/apps/", "/scoop/shims/"];
/// The caches that `npx`, `uvx` and `pipx run` unpack into. Checked before the
/// managers below, because an npx cache path also contains `/node_modules/`.
const TEMPORARY: &[(&str, &str)] = &[
    ("/_npx/", "npx"),
    ("/uv/archive-v0/", "uvx"),
    ("/uv/cache/", "uvx"),
    ("/.cache/uv/", "uvx"),
    ("/caches/uv/", "uvx"),
    ("/pipx/.cache/", "pipx run"),
];
/// A global npm install nests the platform package inside the `chronosledger`
/// one. The trailing slash keeps `chronosledger-client` and any other package
/// with the same prefix out.
const NPM_GLOBAL: &[&str] = &[
    "/lib/node_modules/chronosledger/",
    "/npm/node_modules/chronosledger/",
];
const FOREIGN: &[(&str, &str)] = &[
    ("/node_modules/", "an npm project dependency"),
    ("/site-packages/", "pip"),
    ("/python/python3", "pip"),
    ("/.bun/", "Bun"),
    ("/winget/", "WinGet"),
    ("/.volta/", "Volta"),
    ("/mise/", "mise"),
    ("/.asdf/", "asdf"),
    ("/nix/store/", "Nix"),
    ("/usr/bin/", "the system package manager"),
];

/// `npm` is a `.cmd` launcher on Windows, and `CreateProcess` does not apply
/// PATHEXT, so the bare name is not found there.
#[cfg(windows)]
const NPM: &str = "npm.cmd";
#[cfg(not(windows))]
const NPM: &str = "npm";

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
        if let Some((_, runner)) = TEMPORARY.iter().find(|(m, _)| path.contains(m)) {
            return Channel::Temporary(runner);
        }
        if NPM_GLOBAL.iter().any(|m| path.contains(m)) {
            return Channel::Npm;
        }
        if path.contains("/.cargo/bin/") {
            return Channel::Cargo;
        }
        if path.contains("/uv/tools/") {
            return Channel::Uv;
        }
        if path.contains("/pipx/") {
            return Channel::Pipx;
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
            Channel::Npm => "npm",
            Channel::Cargo => "Cargo",
            Channel::Uv => "uv",
            Channel::Pipx => "pipx",
            Channel::Temporary(runner) => runner,
            Channel::Foreign(name) => name,
            Channel::Unknown => "unknown",
        }
    }

    /// The manager's own command, for channels that have one.
    pub fn upgrade_argv(self) -> Option<&'static [&'static str]> {
        match self {
            Channel::Homebrew => Some(&["brew", "upgrade", "chronos"]),
            Channel::Scoop => Some(&["scoop", "update", "chronos"]),
            Channel::Npm => Some(&[NPM, "install", "-g", "chronosledger@latest"]),
            Channel::Cargo => Some(&["cargo", "install", "--locked", "chronosledger"]),
            Channel::Uv => Some(&["uv", "tool", "upgrade", "chronosledger"]),
            Channel::Pipx => Some(&["pipx", "upgrade", "chronosledger"]),
            _ => None,
        }
    }

    pub fn uninstall_argv(self) -> Option<&'static [&'static str]> {
        match self {
            Channel::Homebrew => Some(&["brew", "uninstall", "chronos"]),
            Channel::Scoop => Some(&["scoop", "uninstall", "chronos"]),
            Channel::Npm => Some(&[NPM, "uninstall", "-g", "chronosledger"]),
            Channel::Cargo => Some(&["cargo", "uninstall", "chronosledger"]),
            Channel::Uv => Some(&["uv", "tool", "uninstall", "chronosledger"]),
            Channel::Pipx => Some(&["pipx", "uninstall", "chronosledger"]),
            _ => None,
        }
    }

    /// For a temporary copy: how to get the newest release next time.
    pub fn fresh_command(self) -> Option<&'static str> {
        match self {
            Channel::Temporary("npx") => Some("npx chronosledger@latest"),
            Channel::Temporary("uvx") => Some("uvx chronosledger@latest"),
            Channel::Temporary(_) => Some("pipx run --no-cache chronosledger"),
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
    fn a_global_npm_install_is_owned_in_its_nested_layout() {
        assert_eq!(
            detect(
                "/usr/lib/node_modules/chronosledger/node_modules/chronosledger-linux-x64/bin/chronos"
            ),
            Channel::Npm
        );
        assert_eq!(
            detect(
                "/home/a/.nvm/versions/node/v24.1.0/lib/node_modules/chronosledger/node_modules/chronosledger-darwin-arm64/bin/chronos"
            ),
            Channel::Npm
        );
        assert_eq!(
            detect(
                r"C:\Users\a\AppData\Roaming\npm\node_modules\chronosledger\node_modules\chronosledger-windows-x64\bin\chronos.exe"
            ),
            Channel::Npm
        );
        // The extended-length form that canonicalize() returns on Windows.
        assert_eq!(
            detect(
                r"\\?\C:\Users\a\AppData\Roaming\npm\node_modules\chronosledger\node_modules\chronosledger-windows-arm64\bin\chronos.exe"
            ),
            Channel::Npm
        );
    }

    #[test]
    fn another_package_with_the_same_prefix_is_not_ours() {
        assert_eq!(
            detect("/usr/lib/node_modules/chronosledger-client/bin/chronos"),
            Channel::Foreign("an npm project dependency")
        );
    }

    #[test]
    fn a_project_dependency_stays_foreign() {
        assert_eq!(
            detect(
                "/work/app/node_modules/chronosledger/node_modules/chronosledger-linux-x64/bin/chronos"
            ),
            Channel::Foreign("an npm project dependency")
        );
        assert_eq!(
            detect(r"C:\work\app\node_modules\chronosledger-windows-x64\bin\chronos.exe"),
            Channel::Foreign("an npm project dependency")
        );
    }

    #[test]
    fn cargo_uv_and_pipx_copies_are_owned() {
        assert_eq!(detect("/home/a/.cargo/bin/chronos"), Channel::Cargo);
        assert_eq!(detect(r"C:\Users\a\.cargo\bin\chronos.exe"), Channel::Cargo);
        assert_eq!(
            detect("/home/a/.local/share/uv/tools/chronosledger/bin/chronos"),
            Channel::Uv
        );
        assert_eq!(
            detect(r"C:\Users\a\AppData\Roaming\uv\tools\chronosledger\Scripts\chronos.exe"),
            Channel::Uv
        );
        assert_eq!(
            detect("/home/a/.local/share/pipx/venvs/chronosledger/bin/chronos"),
            Channel::Pipx
        );
        assert_eq!(
            detect(r"C:\Users\a\pipx\venvs\chronosledger\Scripts\chronos.exe"),
            Channel::Pipx
        );
    }

    #[test]
    fn a_cache_from_npx_uvx_or_pipx_run_is_temporary() {
        let npx = [
            "/home/a/.npm/_npx/1a2b3c/node_modules/chronosledger/node_modules/chronosledger-linux-x64/bin/chronos",
            "/home/a/.npm/_npx/1a2b3c/node_modules/chronosledger-linux-x64/bin/chronos",
            r"C:\Users\a\AppData\Local\npm-cache\_npx\1a2b3c\node_modules\chronosledger-windows-x64\bin\chronos.exe",
        ];
        for p in npx {
            assert_eq!(detect(p), Channel::Temporary("npx"), "{p}");
        }
        let uvx = [
            "/home/a/.cache/uv/archive-v0/abc123/bin/chronos",
            "/home/a/Library/Caches/uv/archive-v0/abc123/bin/chronos",
            r"C:\Users\a\AppData\Local\uv\cache\archive-v0\abc123\Scripts\chronos.exe",
        ];
        for p in uvx {
            assert_eq!(detect(p), Channel::Temporary("uvx"), "{p}");
        }
        assert_eq!(
            detect("/home/a/.local/pipx/.cache/9f8e/bin/chronos"),
            Channel::Temporary("pipx run")
        );
    }

    #[test]
    fn a_temporary_copy_has_a_fresh_command_and_no_manager_command() {
        let npx = Channel::Temporary("npx");
        assert_eq!(npx.fresh_command(), Some("npx chronosledger@latest"));
        assert_eq!(
            Channel::Temporary("uvx").fresh_command(),
            Some("uvx chronosledger@latest")
        );
        assert!(npx.upgrade_argv().is_none());
        assert!(npx.uninstall_argv().is_none());
        assert!(Channel::Npm.fresh_command().is_none());
    }

    #[test]
    fn other_managers_are_named_and_loose_files_are_unknown() {
        assert_eq!(
            detect("/usr/bin/chronos"),
            Channel::Foreign("the system package manager")
        );
        assert_eq!(
            detect(r"C:\Users\a\AppData\Local\Programs\Python\Python314\Scripts\chronos.exe"),
            Channel::Foreign("pip")
        );
        assert_eq!(
            detect("/usr/lib/python3.12/site-packages/bin/chronos"),
            Channel::Foreign("pip")
        );
        assert_eq!(detect("/usr/local/bin/chronos"), Channel::Unknown);
        assert_eq!(detect("/home/a/.chronos/bin-old/chronos"), Channel::Unknown);
    }

    #[test]
    fn only_owning_channels_have_manager_commands() {
        assert!(Channel::Installer.upgrade_argv().is_none());
        assert!(Channel::Foreign("pip").uninstall_argv().is_none());
        assert!(Channel::Unknown.uninstall_argv().is_none());
        assert_eq!(Channel::Scoop.uninstall_argv().unwrap()[0], "scoop");
        assert_eq!(
            Channel::Cargo.upgrade_argv().unwrap(),
            ["cargo", "install", "--locked", "chronosledger"]
        );
        assert_eq!(
            Channel::Cargo.uninstall_argv().unwrap(),
            ["cargo", "uninstall", "chronosledger"]
        );
        assert_eq!(
            Channel::Uv.upgrade_argv().unwrap(),
            ["uv", "tool", "upgrade", "chronosledger"]
        );
        assert_eq!(
            Channel::Uv.uninstall_argv().unwrap(),
            ["uv", "tool", "uninstall", "chronosledger"]
        );
        assert_eq!(
            Channel::Pipx.upgrade_argv().unwrap(),
            ["pipx", "upgrade", "chronosledger"]
        );
        assert_eq!(
            Channel::Pipx.uninstall_argv().unwrap(),
            ["pipx", "uninstall", "chronosledger"]
        );
        assert_eq!(
            Channel::Npm.upgrade_argv().unwrap()[1..],
            ["install", "-g", "chronosledger@latest"]
        );
        assert_eq!(
            Channel::Npm.uninstall_argv().unwrap()[1..],
            ["uninstall", "-g", "chronosledger"]
        );
    }
}
