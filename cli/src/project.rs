// Copyright 2026 Chronos Ledger Contributors
// SPDX-License-Identifier: Apache-2.0

//! One project directory and the `docker compose` calls made against it.

use std::path::{Path, PathBuf};
use std::process::{Command, Output, Stdio};
use std::time::{Duration, Instant};

use anyhow::{Context, Result, bail};
use serde::Deserialize;

pub const COMPOSE_FILE: &str = "docker-compose.yml";
pub const DB_USER: &str = "chronos_admin";
pub const DB_NAME: &str = "chronos_ledger";

/// What `/health` reports. `schema_version` names the shape of the tables the
/// running models describe; there are no migrations, so a database fits a build
/// only when the two agree.
#[derive(Debug, Deserialize)]
pub struct Health {
    pub version: String,
    pub schema_version: Option<String>,
}

/// Prints the backend's SCHEMA_VERSION constant, run inside its image.
const PRINT_SCHEMA_VERSION: &str =
    "from app.core.schema import SCHEMA_VERSION; print(SCHEMA_VERSION)";

pub struct Project {
    pub dir: PathBuf,
}

impl Project {
    pub fn new(dir: PathBuf) -> Self {
        Self { dir }
    }

    pub fn env_path(&self) -> PathBuf {
        self.dir.join(".env")
    }

    pub fn compose_path(&self) -> PathBuf {
        self.dir.join(COMPOSE_FILE)
    }

    pub fn backups_dir(&self) -> PathBuf {
        self.dir.join("backups")
    }

    pub fn read_env(&self) -> Result<String> {
        std::fs::read_to_string(self.env_path()).with_context(|| {
            format!(
                "no .env in {}; run `chronos init` there, or pass --dir",
                self.dir.display()
            )
        })
    }

    pub fn require_initialised(&self) -> Result<()> {
        if !self.compose_path().is_file() {
            bail!(
                "no {COMPOSE_FILE} in {}; run `chronos init` there, or pass --dir",
                self.dir.display()
            );
        }
        self.read_env().map(|_| ())
    }

    pub fn compose(&self) -> Command {
        let mut cmd = Command::new("docker");
        cmd.arg("compose")
            .arg("--project-directory")
            .arg(&self.dir)
            .arg("-f")
            .arg(self.compose_path());
        cmd
    }

    /// Run compose with its output on the terminal.
    pub fn compose_run(&self, args: &[&str]) -> Result<()> {
        self.require_initialised()?;
        let status = self
            .compose()
            .args(args)
            .status()
            .context("could not run `docker compose`; is Docker installed?")?;
        if !status.success() {
            bail!("`docker compose {}` failed", args.join(" "));
        }
        Ok(())
    }

    /// Run compose and capture its output.
    pub fn compose_output(&self, args: &[&str]) -> Result<Output> {
        self.compose()
            .args(args)
            .stdin(Stdio::null())
            .output()
            .context("could not run `docker compose`; is Docker installed?")
    }

    /// GET a path on the backend from inside its own container, so no port or
    /// proxy setting on the host is involved.
    fn backend_get(&self, path: &str) -> Result<Output> {
        let script = format!(
            "import sys,urllib.request;sys.stdout.write(urllib.request.urlopen('http://localhost:8000{path}',timeout=5).read().decode())"
        );
        self.compose_output(&["exec", "-T", "chronos-app", "python", "-c", &script])
    }

    /// `/health`, or None when the backend is not running or not answering.
    pub fn health(&self) -> Option<Health> {
        let out = self.backend_get("/health").ok()?;
        if !out.status.success() {
            return None;
        }
        serde_json::from_slice(&out.stdout).ok()
    }

    /// Poll `/health/ready` until it answers 200 or `timeout` passes.
    pub fn wait_ready(&self, timeout: Duration) -> Result<Health> {
        let start = Instant::now();
        eprint!("Waiting for the server to be ready");
        loop {
            if let Ok(out) = self.backend_get("/health/ready")
                && out.status.success()
                && let Some(health) = self.health()
            {
                eprintln!();
                return Ok(health);
            }
            if start.elapsed() > timeout {
                eprintln!();
                bail!(
                    "the server was not ready after {}s; see `docker compose --project-directory {} logs chronos-app`",
                    timeout.as_secs(),
                    self.dir.display()
                );
            }
            eprint!(".");
            std::thread::sleep(Duration::from_secs(3));
        }
    }

    /// The schema version of the image the compose file points at, asked of a
    /// throwaway container of that image. Works while the backend is stopped or
    /// crash-looping, which is when it matters. The database records no version
    /// of its own: it has whatever tables the image that started on it built,
    /// so the image is the answer.
    pub fn image_schema_version(&self) -> Result<String> {
        let out = self.compose_output(&[
            "run",
            "--rm",
            "--no-deps",
            "-T",
            "chronos-app",
            "uv",
            "run",
            "--no-sync",
            "python",
            "-c",
            PRINT_SCHEMA_VERSION,
        ])?;
        if !out.status.success() {
            bail!(
                "could not read the schema version from the backend image: {}",
                String::from_utf8_lossy(&out.stderr).trim()
            );
        }
        let version = String::from_utf8_lossy(&out.stdout).trim().to_string();
        if version.is_empty() {
            bail!("the backend image printed no schema version");
        }
        Ok(version)
    }
}

/// The sidecar written beside every backup.
#[derive(Debug, serde::Serialize, Deserialize)]
pub struct BackupInfo {
    pub server_version: Option<String>,
    pub schema_version: Option<String>,
    pub created_at: String,
}

pub fn backup_info_path(dump: &Path) -> PathBuf {
    let mut name = dump.as_os_str().to_owned();
    name.push(".json");
    PathBuf::from(name)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn a_sidecar_from_before_schema_versions_has_none() {
        let info: BackupInfo = serde_json::from_str(
            r#"{"server_version": "0.13.0", "migration_revision": "030", "created_at": "2026-01-01T00:00:00Z"}"#,
        )
        .unwrap();
        assert_eq!(info.schema_version, None);
        assert_eq!(info.server_version.as_deref(), Some("0.13.0"));
    }

    #[test]
    fn the_sidecar_sits_beside_the_dump() {
        assert_eq!(
            backup_info_path(Path::new("backups/x.dump")),
            PathBuf::from("backups/x.dump.json")
        );
    }
}
