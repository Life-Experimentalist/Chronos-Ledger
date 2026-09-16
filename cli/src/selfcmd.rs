// Copyright 2026 Chronos Ledger Contributors
// SPDX-License-Identifier: Apache-2.0

//! `chronos self update` and `chronos self uninstall`.
//!
//! Only the manager that installed a copy changes it. Homebrew and Scoop copies
//! go through `brew` and `scoop`, so their records stay true. Files are replaced
//! or deleted directly only for the install-script copy. Anything else is
//! reported with who owns it and left exactly as it is.

use std::fs;
use std::path::{Path, PathBuf};
use std::process::Command;

use anyhow::{Context, Result, bail};
use serde::{Deserialize, Serialize};

use crate::channel::{self, Channel};
use crate::release;

/// What install.sh / install.ps1 record about what they did. Advisory: it is
/// read to undo a PATH change the script made, never to decide the channel.
#[derive(Debug, Serialize, Deserialize)]
pub struct Receipt {
    pub schema: u32,
    pub version: String,
    pub channel: String,
    pub installed_at: String,
    /// The PATH change the script made, or null when PATH already had the directory.
    pub path_entry: Option<PathEntry>,
}

#[derive(Debug, Serialize, Deserialize)]
#[serde(tag = "kind", rename_all = "kebab-case")]
pub enum PathEntry {
    /// A line appended to a shell startup file.
    RcFile { file: PathBuf, line: String },
    /// A directory added to the Windows user PATH.
    UserPath { entry: String },
}

fn receipt_path() -> PathBuf {
    channel::managed_root().join("install.json")
}

fn read_receipt() -> Option<Receipt> {
    serde_json::from_str(&fs::read_to_string(receipt_path()).ok()?).ok()
}

fn running_exe() -> Result<PathBuf> {
    let exe = std::env::current_exe().context("could not tell where this binary is")?;
    Ok(exe.canonicalize().unwrap_or(exe))
}

pub fn update() -> Result<()> {
    let exe = running_exe()?;
    let channel = Channel::detect(&exe);
    match channel {
        Channel::Homebrew | Channel::Scoop => run_manager(channel.upgrade_argv().unwrap()),
        Channel::Installer => update_installer_copy(&exe),
        Channel::Foreign(name) => bail!(
            "{} was installed by {name}, which this project does not publish to. Update or remove it with {name}, then install through a supported channel (docs/cli.md).",
            exe.display()
        ),
        Channel::Unknown => bail!(
            "{} was not installed by a supported channel, so it was left alone. Replace it with an install-script copy: see docs/cli.md.",
            exe.display()
        ),
    }
}

fn update_installer_copy(exe: &Path) -> Result<()> {
    let latest = release::latest_version()?;
    if release::compare_versions(&latest, crate::VERSION) != Some(std::cmp::Ordering::Greater) {
        println!("chronos {} is the latest release.", crate::VERSION);
        return Ok(());
    }
    let bytes = release::download_binary(&latest)?;
    replace_file(exe, &bytes)?;
    if let Some(mut receipt) = read_receipt() {
        receipt.version = latest.clone();
        if let Ok(json) = serde_json::to_string_pretty(&receipt) {
            let _ = fs::write(receipt_path(), json + "\n");
        }
    }
    println!("Updated chronos {} -> {latest}.", crate::VERSION);
    Ok(())
}

/// Write `bytes` over `target` through a staged file, so a failure part way
/// leaves the working binary in place.
fn replace_file(target: &Path, bytes: &[u8]) -> Result<()> {
    let staged = target.with_extension("new");
    fs::write(&staged, bytes).with_context(|| format!("could not write {}", staged.display()))?;
    #[cfg(unix)]
    {
        use std::os::unix::fs::PermissionsExt;
        fs::set_permissions(&staged, fs::Permissions::from_mode(0o755))?;
    }
    // Windows will not overwrite a running image but will rename it. The old
    // file is deleted by the next run (sweep_replaced_binary).
    #[cfg(windows)]
    {
        let aside = target.with_extension("exe.old");
        let _ = fs::remove_file(&aside);
        fs::rename(target, &aside)
            .with_context(|| format!("could not move {} aside", target.display()))?;
        if let Err(e) = fs::rename(&staged, target) {
            let _ = fs::rename(&aside, target);
            let _ = fs::remove_file(&staged);
            return Err(e).context("could not put the new binary in place; the old one was kept");
        }
        Ok(())
    }
    #[cfg(not(windows))]
    fs::rename(&staged, target).with_context(|| format!("could not replace {}", target.display()))
}

/// Delete the `chronos.exe.old` an update on Windows leaves behind. Only in the
/// managed directory, and only that one file name.
pub fn sweep_replaced_binary() {
    if cfg!(windows) {
        let _ = fs::remove_file(channel::managed_root().join("bin").join("chronos.exe.old"));
    }
}

pub fn uninstall(yes: bool) -> Result<()> {
    let exe = running_exe()?;
    let channel = Channel::detect(&exe);
    match channel {
        Channel::Homebrew | Channel::Scoop => {
            if !crate::confirm(&format!("Remove chronos with {}?", channel.name()), yes) {
                return Ok(());
            }
            run_manager(channel.uninstall_argv().unwrap())?;
        }
        Channel::Installer => {
            if !crate::confirm(
                &format!(
                    "Remove {} and what the install script added?",
                    channel::managed_root().display()
                ),
                yes,
            ) {
                return Ok(());
            }
            uninstall_installer_copy(&exe)?;
        }
        Channel::Foreign(name) => bail!(
            "{} was installed by {name}. Remove it with {name}; chronos does not delete files another manager tracks.",
            exe.display()
        ),
        Channel::Unknown => bail!(
            "{} was not installed by a supported channel, so it was left alone. Delete the file yourself if you put it there.",
            exe.display()
        ),
    }
    report_other_copies(&exe);
    Ok(())
}

fn uninstall_installer_copy(exe: &Path) -> Result<()> {
    let root = channel::managed_root();
    if let Some(entry) = read_receipt().and_then(|r| r.path_entry) {
        remove_path_entry(&entry);
    }
    let _ = fs::remove_file(receipt_path());

    #[cfg(not(windows))]
    {
        fs::remove_file(exe).with_context(|| format!("could not remove {}", exe.display()))?;
        let _ = fs::remove_dir(root.join("bin"));
        let _ = fs::remove_dir(&root);
    }
    // A running exe cannot be deleted on Windows. Move it aside, then let a
    // detached shell remove the directory once this process has exited.
    #[cfg(windows)]
    {
        use std::os::windows::process::CommandExt;
        const DETACHED_PROCESS: u32 = 0x0000_0008;
        const CREATE_NO_WINDOW: u32 = 0x0800_0000;
        let aside = exe.with_extension("exe.old");
        let _ = fs::remove_file(&aside);
        fs::rename(exe, &aside)
            .with_context(|| format!("could not move {} aside", exe.display()))?;
        // Only bin\ goes recursively, and the root only if nothing else is left
        // in it, the same as on Unix: CHRONOS_INSTALL_DIR may point somewhere shared.
        Command::new("cmd")
            .args([
                "/d",
                "/c",
                "ping",
                "127.0.0.1",
                "-n",
                "3",
                ">nul",
                "&",
                "rmdir",
                "/s",
                "/q",
            ])
            .arg(root.join("bin"))
            .args(["&", "rmdir"])
            .arg(&root)
            .creation_flags(DETACHED_PROCESS | CREATE_NO_WINDOW)
            .spawn()
            .context("could not start the cleanup of the install directory")?;
    }
    println!("Removed chronos from {}.", root.display());
    Ok(())
}

fn remove_path_entry(entry: &PathEntry) {
    match entry {
        PathEntry::RcFile { file, line } => {
            let Ok(text) = fs::read_to_string(file) else {
                return;
            };
            let kept: Vec<&str> = text
                .lines()
                .filter(|l| l.trim_end() != line.trim_end())
                .collect();
            if kept.len() != text.lines().count() {
                let _ = fs::write(file, kept.join("\n") + "\n");
                println!("Removed the PATH line from {}.", file.display());
            }
        }
        PathEntry::UserPath { entry } => remove_windows_user_path(entry),
    }
}

#[cfg(windows)]
fn remove_windows_user_path(entry: &str) {
    use std::borrow::Cow;
    use winreg::enums::{HKEY_CURRENT_USER, KEY_READ, KEY_WRITE};
    use winreg::{RegKey, RegValue};
    let Ok(env) = RegKey::predef(HKEY_CURRENT_USER)
        .open_subkey_with_flags("Environment", KEY_READ | KEY_WRITE)
    else {
        return;
    };
    // Raw, so an REG_EXPAND_SZ Path keeps its type and its %VARIABLES% unexpanded.
    let Ok(raw) = env.get_raw_value("Path") else {
        return;
    };
    let units: Vec<u16> = raw
        .bytes
        .chunks_exact(2)
        .map(|c| u16::from_le_bytes([c[0], c[1]]))
        .collect();
    let path = String::from_utf16_lossy(&units)
        .trim_end_matches('\0')
        .to_string();
    let norm = |s: &str| s.trim_end_matches('\\').to_lowercase();
    let kept: Vec<&str> = path.split(';').filter(|p| norm(p) != norm(entry)).collect();
    if kept.len() == path.split(';').count() {
        return;
    }
    let bytes: Vec<u8> = kept
        .join(";")
        .encode_utf16()
        .chain([0])
        .flat_map(u16::to_le_bytes)
        .collect();
    let value = RegValue {
        bytes: Cow::Owned(bytes),
        vtype: raw.vtype,
    };
    if env.set_raw_value("Path", &value).is_ok() {
        println!("Removed {entry} from your user PATH. Open a new terminal to see it.");
    }
}

#[cfg(not(windows))]
fn remove_windows_user_path(_: &str) {}

fn run_manager(argv: &[&str]) -> Result<()> {
    println!("Running: {}", argv.join(" "));
    let status = Command::new(argv[0])
        .args(&argv[1..])
        .status()
        .with_context(|| format!("could not start `{}`", argv[0]))?;
    if !status.success() {
        bail!("`{}` failed", argv.join(" "));
    }
    Ok(())
}

/// Other copies are named, never removed: each belongs to whoever installed it.
fn report_other_copies(removed: &Path) {
    for copy in channel::copies_on_path()
        .into_iter()
        .filter(|c| c != removed)
    {
        println!(
            "Another copy is still on PATH: {} (installed by {}).",
            copy.display(),
            Channel::detect(&copy).name()
        );
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn receipts_written_by_both_install_scripts_parse() {
        let sh = r#"{"schema":1,"version":"0.13.0","channel":"installer","installed_at":"2026-09-17T00:00:00Z",
            "path_entry":{"kind":"rc-file","file":"/home/a/.bashrc","line":"export PATH=\"$HOME/.chronos/bin:$PATH\""}}"#;
        let ps1 = r#"{"schema":1,"version":"0.13.0","channel":"installer","installed_at":"2026-09-17T00:00:00Z",
            "path_entry":{"kind":"user-path","entry":"C:\\Users\\a\\AppData\\Local\\chronos\\bin"}}"#;
        let none = r#"{"schema":1,"version":"0.13.0","channel":"installer","installed_at":"x","path_entry":null}"#;
        assert!(matches!(
            serde_json::from_str::<Receipt>(sh).unwrap().path_entry,
            Some(PathEntry::RcFile { .. })
        ));
        assert!(matches!(
            serde_json::from_str::<Receipt>(ps1).unwrap().path_entry,
            Some(PathEntry::UserPath { .. })
        ));
        assert!(
            serde_json::from_str::<Receipt>(none)
                .unwrap()
                .path_entry
                .is_none()
        );
    }

    #[test]
    fn only_the_exact_rc_line_is_removed() {
        let dir = tempfile::tempdir().unwrap();
        let rc = dir.path().join(".bashrc");
        let line = r#"export PATH="$HOME/.chronos/bin:$PATH""#;
        fs::write(&rc, format!("alias x=y\n{line}\n# {line}\n")).unwrap();
        remove_path_entry(&PathEntry::RcFile {
            file: rc.clone(),
            line: line.into(),
        });
        assert_eq!(
            fs::read_to_string(&rc).unwrap(),
            format!("alias x=y\n# {line}\n")
        );
    }
}
