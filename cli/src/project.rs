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

/// What `/health` reports.
#[derive(Debug, Deserialize)]
pub struct Health {
    pub version: String,
    pub migration_revision: Option<String>,
}

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

    /// The migration the database is at, read from the database container. Works
    /// while the backend is stopped or crash-looping, which is when it matters.
    pub fn database_revision(&self) -> Result<Option<String>> {
        let out = self.compose_output(&[
            "exec",
            "-T",
            "chronos-db",
            "psql",
            "-U",
            DB_USER,
            "-d",
            DB_NAME,
            "-tAc",
            "SELECT version_num FROM alembic_version",
        ])?;
        if !out.status.success() {
            bail!(
                "could not read the migration from the database: {}",
                String::from_utf8_lossy(&out.stderr).trim()
            );
        }
        let rev = String::from_utf8_lossy(&out.stdout).trim().to_string();
        Ok((!rev.is_empty()).then_some(rev))
    }
}

/// Order two Alembic revisions. This project numbers them ("021", "022"), so they
/// compare as integers. None when either is not a number.
pub fn compare_revisions(a: &str, b: &str) -> Option<std::cmp::Ordering> {
    Some(a.parse::<u64>().ok()?.cmp(&b.parse::<u64>().ok()?))
}

/// The sidecar written beside every backup.
#[derive(Debug, serde::Serialize, Deserialize)]
pub struct BackupInfo {
    pub server_version: Option<String>,
    pub migration_revision: Option<String>,
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
    use std::cmp::Ordering;

    #[test]
    fn revisions_compare_numerically() {
        assert_eq!(compare_revisions("022", "021"), Some(Ordering::Greater));
        assert_eq!(compare_revisions("9", "010"), Some(Ordering::Less));
        assert_eq!(compare_revisions("abc123", "022"), None);
    }

    #[test]
    fn the_sidecar_sits_beside_the_dump() {
        assert_eq!(
            backup_info_path(Path::new("backups/x.dump")),
            PathBuf::from("backups/x.dump.json")
        );
    }
}
