// Copyright 2026 Chronos Ledger Contributors
// SPDX-License-Identifier: Apache-2.0

//! Releases on GitHub: the latest version, and verified downloads of the CLI.

use std::cmp::Ordering;
use std::io::Read;
use std::time::Duration;

use anyhow::{Context, Result, bail};

const REPO: &str = "https://github.com/Life-Experimentalist/Chronos-Ledger";

/// The latest release's version, without its `v`.
///
/// Read from the redirect `releases/latest` answers with, not from api.github.com,
/// so it spends no API rate limit (60 requests an hour without a token).
pub fn latest_version() -> Result<String> {
    let response = ureq::get(&format!("{REPO}/releases/latest"))
        .header("User-Agent", &format!("chronos-cli/{}", crate::VERSION))
        .config()
        .timeout_global(Some(Duration::from_secs(15)))
        .max_redirects(0)
        .build()
        .call()
        .context("could not reach GitHub to find the latest release")?;
    let location = response
        .headers()
        .get("location")
        .and_then(|v| v.to_str().ok())
        .context("GitHub did not answer with a redirect")?;
    version_from_location(location).context("GitHub did not redirect to a release tag")
}

fn version_from_location(location: &str) -> Option<String> {
    let tag = location
        .split_once("/releases/tag/")?
        .1
        .trim_end_matches('/');
    if tag.is_empty() || tag.contains('/') {
        return None;
    }
    Some(tag.trim_start_matches('v').to_string())
}

/// Compare `major.minor.patch` versions, ignoring a leading `v` and any suffix.
/// None when either is not in that form, rather than a guess.
pub fn compare_versions(a: &str, b: &str) -> Option<Ordering> {
    let parse = |v: &str| -> Option<[u64; 3]> {
        let core = v.trim_start_matches('v').split(['-', '+']).next()?;
        let mut parts = core.split('.');
        let out = [
            parts.next()?.parse().ok()?,
            parts.next()?.parse().ok()?,
            parts.next()?.parse().ok()?,
        ];
        parts.next().is_none().then_some(out)
    };
    Some(parse(a)?.cmp(&parse(b)?))
}

/// The raw binary's asset name for this platform, as release.yml publishes it.
pub fn asset_name(version: &str) -> Result<String> {
    let os = match std::env::consts::OS {
        "linux" => "linux",
        "macos" => "darwin",
        "windows" => "windows",
        other => bail!("no published binary for {other}"),
    };
    let arch = match std::env::consts::ARCH {
        "x86_64" => "x64",
        "aarch64" => "arm64",
        other => bail!("no published binary for {other}"),
    };
    let ext = if os == "windows" { ".exe" } else { "" };
    Ok(format!("chronos-v{version}-{os}-{arch}{ext}"))
}

/// Download this platform's binary for `version` and check it against its
/// `.sha256` sidecar. Nothing is returned unless the digest matches.
pub fn download_binary(version: &str) -> Result<Vec<u8>> {
    let asset = asset_name(version)?;
    let url = format!("{REPO}/releases/download/v{version}/{asset}");
    let sidecar = String::from_utf8(fetch(&format!("{url}.sha256"))?)
        .context("the checksum sidecar was not text")?;
    let expected = parse_sidecar(&sidecar)?;
    eprintln!("Downloading {asset}");
    let bytes = fetch(&url)?;
    let actual = sha256_hex(&bytes);
    if actual != expected {
        bail!(
            "checksum mismatch for {asset}: expected {expected}, got {actual}. Nothing was installed."
        );
    }
    Ok(bytes)
}

pub fn sha256_hex(bytes: &[u8]) -> String {
    use sha2::{Digest, Sha256};
    Sha256::digest(bytes)
        .iter()
        .map(|b| format!("{b:02x}"))
        .collect()
}

/// `sha256sum` format. Validated, because what arrives in its place on a bad
/// day is an HTML error page, and that should not read as tampering.
fn parse_sidecar(body: &str) -> Result<String> {
    let hash = body
        .split_whitespace()
        .next()
        .context("the checksum sidecar was empty")?
        .to_ascii_lowercase();
    if hash.len() != 64 || !hash.bytes().all(|b| b.is_ascii_hexdigit()) {
        bail!("the checksum sidecar did not contain a SHA-256 digest");
    }
    Ok(hash)
}

fn fetch(url: &str) -> Result<Vec<u8>> {
    let mut response = ureq::get(url)
        .header("User-Agent", &format!("chronos-cli/{}", crate::VERSION))
        .config()
        .timeout_global(Some(Duration::from_secs(120)))
        .build()
        .call()
        .with_context(|| format!("could not download {url}"))?;
    let mut buf = Vec::new();
    response
        .body_mut()
        .as_reader()
        .read_to_end(&mut buf)
        .with_context(|| format!("could not read {url}"))?;
    Ok(buf)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn the_version_comes_from_the_redirect() {
        let loc = "https://github.com/Life-Experimentalist/Chronos-Ledger/releases/tag/v0.13.0";
        assert_eq!(version_from_location(loc).as_deref(), Some("0.13.0"));
        assert_eq!(
            version_from_location("https://github.com/x/y/releases"),
            None
        );
    }

    #[test]
    fn versions_compare_by_component() {
        assert_eq!(compare_versions("0.10.0", "0.9.9"), Some(Ordering::Greater));
        assert_eq!(compare_versions("v0.13.0", "0.13.0"), Some(Ordering::Equal));
        assert_eq!(compare_versions("latest", "0.13.0"), None);
    }

    #[test]
    fn a_sidecar_must_hold_a_digest() {
        let digest = "a".repeat(64);
        assert_eq!(
            parse_sidecar(&format!("{digest}  chronos")).unwrap(),
            digest
        );
        assert!(parse_sidecar("<!DOCTYPE html>").is_err());
    }
}
