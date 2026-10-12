// Copyright 2026 Chronos Ledger Contributors
// SPDX-License-Identifier: Apache-2.0

//! The server commands: init, up, status, upgrade, backup, restore, doctor.

use std::cmp::Ordering;
use std::fs;
use std::path::{Path, PathBuf};
use std::process::{Command, Stdio};
use std::time::Duration;

use anyhow::{Context, Result, bail};

use crate::channel::{self, Channel};
use crate::env_file;
use crate::project::{self, BackupInfo, DB_NAME, DB_USER, Health, Project};
use crate::release::{self, compare_versions};

/// The compose file and env template of the release this CLI was built from.
const COMPOSE: &str = include_str!("../../docker-compose.prod.yml");
const ENV_EXAMPLE: &str = include_str!("../../.env.example");

const READY_TIMEOUT: Duration = Duration::from_secs(300);

fn tag_for(version: &str) -> String {
    format!("v{}", version.trim_start_matches('v'))
}

pub fn init(project: &Project, host: &str, tag: Option<&str>) -> Result<()> {
    if project.env_path().exists() {
        bail!(
            "{} already exists; init never overwrites it. Run `chronos doctor` to check it.",
            project.env_path().display()
        );
    }
    let tag = tag.map_or_else(|| tag_for(crate::VERSION), tag_for);
    fs::create_dir_all(&project.dir)?;

    let db_password = env_file::random_password(32);
    let admin_password = env_file::random_password(20);
    let mut env = ENV_EXAMPLE
        .replace("change_me_password", &db_password)
        .replace(
            "replace_with_64_char_hex_secret_generated_by_openssl_rand_hex_32",
            &env_file::random_hex(32),
        );
    env = env.replace("replace_with_the_first_admin_password", &admin_password);
    for (key, value) in [
        ("NEXT_PUBLIC_API_URL", format!("http://{host}/api/v1")),
        ("NEXT_PUBLIC_WS_URL", format!("ws://{host}/ws")),
        (
            "APP_CORS_ORIGINS",
            format!("http://{host},http://localhost"),
        ),
        ("VERSION", tag.clone()),
    ] {
        env = env_file::set(&env, key, &value);
    }

    if !project.compose_path().exists() {
        fs::write(project.compose_path(), COMPOSE)?;
    }
    write_private(&project.env_path(), &env)?;
    fs::create_dir_all(project.backups_dir())?;
    fs::create_dir_all(project.dir.join("certs"))?;

    println!("Wrote {} and .env, pinned to {tag}.", project::COMPOSE_FILE);
    println!();
    println!("  Sign in as admin@org.internal with: {admin_password}");
    println!(
        "  Printed once. It is also INITIAL_ADMIN_PASSWORD in .env, and you choose a new one on first sign-in."
    );
    println!();
    println!(
        "Push notifications stay off until VAPID keys are set in .env (npx web-push generate-vapid-keys)."
    );
    println!("TLS: put fullchain.pem and privkey.pem in certs/ to serve HTTPS.");
    println!("Next: chronos up");
    Ok(())
}

/// `.env` holds the database password and the signing key, so on Unix only its
/// owner may read it.
fn write_private(path: &Path, text: &str) -> Result<()> {
    fs::write(path, text).with_context(|| format!("could not write {}", path.display()))?;
    #[cfg(unix)]
    {
        use std::os::unix::fs::PermissionsExt;
        fs::set_permissions(path, fs::Permissions::from_mode(0o600))?;
    }
    Ok(())
}

pub fn up(project: &Project) -> Result<()> {
    project.compose_run(&["up", "-d"])?;
    let health = project.wait_ready(READY_TIMEOUT)?;
    println!(
        "Chronos Ledger {} is ready (schema version {}).",
        health.version,
        health.schema_version.as_deref().unwrap_or("none")
    );
    Ok(())
}

pub fn status(project: &Project) -> Result<()> {
    project.compose_run(&["ps"])?;
    match project.health() {
        Some(h) => println!(
            "\nServer {} at schema version {}. CLI {}.",
            h.version,
            h.schema_version.as_deref().unwrap_or("none"),
            crate::VERSION
        ),
        None => println!("\nThe backend is not answering /health."),
    }
    Ok(())
}

/// Refuse to manage a server newer than this CLI: its compose file and its
/// schema are ones this build has never seen.
fn require_cli_not_older(server_version: &str) -> Result<()> {
    if compare_versions(crate::VERSION, server_version) == Some(Ordering::Less) {
        bail!(
            "this CLI is {} and the server is {server_version}. Update the CLI first: chronos self update",
            crate::VERSION
        );
    }
    Ok(())
}

pub fn upgrade(project: &Project, to: Option<&str>, yes: bool) -> Result<()> {
    project.require_initialised()?;
    let target = match to {
        Some(v) => v.trim_start_matches('v').to_string(),
        None => release::latest_version()?,
    };
    if compare_versions(&target, "0.0.0").is_none() {
        bail!("{target} is not a version like 0.13.0");
    }
    if compare_versions(crate::VERSION, &target) == Some(Ordering::Less) {
        bail!(
            "this CLI is {} and cannot install {target}, whose compose file it has not seen. Update the CLI first: chronos self update",
            crate::VERSION
        );
    }

    let env = project.read_env()?;
    let current = env_file::get(&env, "VERSION").unwrap_or_default();
    match compare_versions(&target, &current) {
        Some(Ordering::Equal) => {
            println!("Already on {}.", tag_for(&target));
            return Ok(());
        }
        // Going back means going back to the data as it was: the backup from before.
        Some(Ordering::Less) => bail!(
            "{} is older than the pinned {current}. To go back, set VERSION={} in .env, run `chronos up`, then restore the backup taken on it (chronos restore).",
            tag_for(&target),
            tag_for(&target)
        ),
        _ => {}
    }
    let Some(health) = project.health() else {
        bail!(
            "the server is not running. Start it with `chronos up` so a backup can be taken first."
        );
    };
    require_cli_not_older(&health.version)?;

    if !crate::confirm(
        &format!(
            "Back up, then move from {} to {}?",
            health.version,
            tag_for(&target)
        ),
        yes,
    ) {
        return Ok(());
    }
    let dump = backup(project)?;

    write_private(
        &project.env_path(),
        &env_file::set(&env, "VERSION", &tag_for(&target)),
    )?;
    project.compose_run(&["pull"])?;
    if let Err(e) = require_target_fits(project, &health, &target) {
        write_private(&project.env_path(), &env)?;
        bail!("{e:#}\nThe pin is back on {current}; nothing was restarted.");
    }
    refresh_compose_file(project, &target)?;
    project.compose_run(&["up", "-d"])?;

    match project.wait_ready(READY_TIMEOUT) {
        Ok(h) if compare_versions(&h.version, &target) == Some(Ordering::Equal) => {
            println!(
                "Upgraded to {} (schema version {}).",
                h.version,
                h.schema_version.as_deref().unwrap_or("none")
            );
            Ok(())
        }
        Ok(h) => bail!(
            "the server came up reporting {} instead of {target}",
            h.version
        ),
        Err(e) => bail!(
            "{e:#}\nThe backup from before the upgrade is {}. To go back: set VERSION={current} in .env, chronos up, then chronos restore {}",
            dump.display(),
            dump.display()
        ),
    }
}

/// There are no migrations, so the release moving in must describe the same
/// tables the database already has. Asked of the image `pull` just fetched.
fn require_target_fits(project: &Project, health: &Health, target: &str) -> Result<()> {
    let next = project.image_schema_version()?;
    if Some(next.as_str()) == health.schema_version.as_deref() {
        return Ok(());
    }
    bail!(
        "{} describes schema version {next} and this database was built at {}. Nothing carries data across before the first deployment: export what you need, then start the new release on an empty database (chronos down, remove the database volume, chronos up).",
        tag_for(target),
        health.schema_version.as_deref().unwrap_or("none")
    )
}

/// A backup fits only a server whose models describe the schema it was taken
/// at. With no migrations, nothing carries it across to another.
fn require_same_schema(info: &BackupInfo, health: &Health) -> Result<()> {
    match (&info.schema_version, &health.schema_version) {
        (Some(taken), Some(running)) if taken == running => Ok(()),
        (Some(taken), Some(running)) => bail!(
            "the backup was taken at schema version {taken} and this server is at {running}. There is no upgrade path between the two before the first deployment: restore it on the release it was taken on ({}), or export what you need and start again on an empty database.",
            info.server_version.as_deref().unwrap_or("unknown")
        ),
        (None, _) => bail!(
            "the backup records no schema version, so an earlier CLI took it, and there is no path from its tables to this server's."
        ),
        (_, None) => bail!(
            "the server reports no schema version in /health, so this CLI cannot check the backup against it."
        ),
    }
}

/// Replace the compose file with this CLI's copy when upgrading to the CLI's own
/// version. A file that differs is kept beside it, since someone may have edited it.
fn refresh_compose_file(project: &Project, target: &str) -> Result<()> {
    if compare_versions(target, crate::VERSION) != Some(Ordering::Equal) {
        return Ok(());
    }
    let path = project.compose_path();
    let existing = fs::read_to_string(&path).unwrap_or_default();
    if existing.replace("\r\n", "\n") != COMPOSE.replace("\r\n", "\n") {
        let kept = path.with_extension("yml.before-upgrade");
        fs::copy(&path, &kept)?;
        fs::write(&path, COMPOSE)?;
        println!(
            "Updated {}; your previous copy is {}.",
            project::COMPOSE_FILE,
            kept.display()
        );
    }
    Ok(())
}

pub fn backup(project: &Project) -> Result<PathBuf> {
    project.require_initialised()?;
    // The running server knows its schema version. When it is down, the pinned
    // image is the thing that built the database, so it is asked instead.
    let health = project.health();
    let schema_version = match health.as_ref().and_then(|h| h.schema_version.clone()) {
        Some(version) => version,
        None => project.image_schema_version()?,
    };
    let server_version = health.map(|h| h.version).or_else(|| {
        project
            .read_env()
            .ok()
            .and_then(|e| env_file::get(&e, "VERSION"))
    });
    fs::create_dir_all(project.backups_dir())?;
    let stamp = chrono::Utc::now().format("%Y%m%d-%H%M%S");
    let dump = project
        .backups_dir()
        .join(format!("chronos-{stamp}-schema{schema_version}.dump"));

    let file =
        fs::File::create(&dump).with_context(|| format!("could not create {}", dump.display()))?;
    let status = project
        .compose()
        .args([
            "exec",
            "-T",
            "chronos-db",
            "pg_dump",
            "-U",
            DB_USER,
            "-d",
            DB_NAME,
            "-Fc",
        ])
        .stdin(Stdio::null())
        .stdout(file)
        .status()
        .context("could not run `docker compose`")?;
    if !status.success() {
        let _ = fs::remove_file(&dump);
        bail!("pg_dump failed; is the database container running? (chronos up)");
    }

    let info = BackupInfo {
        server_version,
        schema_version: Some(schema_version),
        created_at: chrono::Utc::now().to_rfc3339(),
    };
    fs::write(
        project::backup_info_path(&dump),
        serde_json::to_string_pretty(&info)? + "\n",
    )?;
    println!("Backup written: {}", dump.display());
    Ok(dump)
}

pub fn restore(project: &Project, file: &Path, yes: bool) -> Result<()> {
    project.require_initialised()?;
    let info: BackupInfo = serde_json::from_str(
        &fs::read_to_string(project::backup_info_path(file)).with_context(|| {
            format!(
                "{} has no {} beside it, so the schema version it was taken at is unknown. Only backups from `chronos backup` can be restored this way.",
                file.display(),
                project::backup_info_path(file).display()
            )
        })?,
    )?;
    let Some(health) = project.health() else {
        bail!(
            "the server is not running. Start it with `chronos up` so its schema version can be checked first."
        );
    };
    require_cli_not_older(&health.version)?;
    require_same_schema(&info, &health)?;

    if !crate::confirm(
        &format!(
            "Replace the entire database with {}? Everything since that backup is lost.",
            file.display()
        ),
        yes,
    ) {
        return Ok(());
    }

    project.compose_run(&["stop", "chronos-proxy", "chronos-app"])?;
    // Drop and recreate rather than pg_restore --clean: --clean only drops what
    // the dump contains, so a table the dump lacks would survive beside the
    // restored ones.
    for sql in [
        format!("DROP DATABASE IF EXISTS {DB_NAME} WITH (FORCE)"),
        format!("CREATE DATABASE {DB_NAME} OWNER {DB_USER}"),
    ] {
        let out = project.compose_output(&[
            "exec",
            "-T",
            "chronos-db",
            "psql",
            "-U",
            DB_USER,
            "-d",
            "postgres",
            "-c",
            &sql,
        ])?;
        if !out.status.success() {
            bail!(
                "{sql} failed: {}",
                String::from_utf8_lossy(&out.stderr).trim()
            );
        }
    }
    let input =
        fs::File::open(file).with_context(|| format!("could not open {}", file.display()))?;
    let status = project
        .compose()
        .args([
            "exec",
            "-T",
            "chronos-db",
            "pg_restore",
            "-U",
            DB_USER,
            "-d",
            DB_NAME,
            "--no-owner",
        ])
        .stdin(input)
        .status()
        .context("could not run `docker compose`")?;
    if !status.success() {
        bail!(
            "pg_restore failed. The database is empty; run the restore again, or restore another backup."
        );
    }
    // The schema versions match, so starting the backend changes nothing in
    // the restored database.
    up(project)
}

/// One finding from `doctor`.
struct Report {
    problems: usize,
}

impl Report {
    fn ok(&self, msg: &str) {
        println!("  ok    {msg}");
    }
    fn warn(&mut self, msg: &str) {
        self.problems += 1;
        println!("  warn  {msg}");
    }
}

pub fn doctor(project: &Project) -> Result<()> {
    let mut r = Report { problems: 0 };
    println!("chronos {} at {}", crate::VERSION, running_path());

    println!("\nCLI copies");
    check_copies(&mut r);

    println!("\nDocker");
    let compose_ok = Command::new("docker")
        .args(["compose", "version", "--short"])
        .output()
        .map(|o| o.status.success())
        .unwrap_or(false);
    if compose_ok {
        r.ok("docker compose v2 is available");
    } else {
        r.warn("`docker compose` does not run. Install Docker Engine 24+ with the compose plugin.");
    }

    println!("\nProject {}", project.dir.display());
    let Ok(env) = project.read_env() else {
        r.warn("no .env here. Run `chronos init`, or pass --dir.");
        return finish(r);
    };
    for (needle, meaning) in env_file::PLACEHOLDERS {
        if env.contains(needle) {
            r.warn(meaning);
        }
    }
    let pinned = env_file::get(&env, "VERSION").unwrap_or_default();
    if compare_versions(&pinned, "0.0.0").is_none() {
        r.warn(&format!(
            "VERSION={pinned} is not a release. Pin one so upgrades are deliberate: chronos upgrade"
        ));
    } else {
        r.ok(&format!("pinned to {pinned}"));
    }
    match fs::read_to_string(project.compose_path()) {
        Err(_) => r.warn(&format!(
            "no {} here. Run `chronos init`.",
            project::COMPOSE_FILE
        )),
        Ok(text)
            if compare_versions(&pinned, crate::VERSION) == Some(Ordering::Equal)
                && text.replace("\r\n", "\n") != COMPOSE.replace("\r\n", "\n") =>
        {
            r.warn(&format!(
                "{} differs from the {pinned} release copy. Fine if you edited it on purpose.",
                project::COMPOSE_FILE
            ))
        }
        Ok(_) => {}
    }
    if !compose_ok {
        return finish(r);
    }

    println!("\nServer");
    match project.health() {
        None => {
            r.warn("the backend is not answering /health. `chronos up`, then `docker compose logs chronos-app` if it stays down.");
            // Asking the image would start a container, and doctor changes nothing.
            println!("        schema version unknown while the backend is down");
        }
        Some(h) => {
            r.ok(&format!(
                "server {} at schema version {}",
                h.version,
                h.schema_version.as_deref().unwrap_or("none")
            ));
            if compare_versions(&h.version, &pinned) != Some(Ordering::Equal)
                && compare_versions(&pinned, "0.0.0").is_some()
            {
                r.warn(&format!(
                    "the server runs {} but .env pins {pinned}. Run `chronos up` to apply the pin.",
                    h.version
                ));
            }
            if compare_versions(crate::VERSION, &h.version) == Some(Ordering::Less) {
                r.warn(&format!(
                    "this CLI ({}) is older than the server. Update it: chronos self update",
                    crate::VERSION
                ));
            }
        }
    }
    check_images_current(project, &mut r);
    finish(r)
}

fn finish(r: Report) -> Result<()> {
    println!();
    if r.problems == 0 {
        println!("No problems found.");
        Ok(())
    } else {
        bail!("{} problem(s) found", r.problems)
    }
}

fn running_path() -> String {
    std::env::current_exe().map_or_else(|_| "an unknown path".into(), |p| p.display().to_string())
}

/// Exactly one copy on PATH is the healthy state. Anything else gets the commands
/// that fix it, and doctor itself removes nothing.
fn check_copies(r: &mut Report) {
    let copies = channel::copies_on_path();
    match copies.len() {
        0 => r.warn("chronos is not on PATH; this copy runs only from where it is."),
        1 => r.ok(&format!(
            "one copy on PATH ({})",
            Channel::detect(&copies[0]).name()
        )),
        _ => {
            r.warn(&format!(
                "{} copies on PATH; the first one wins, and updates reach only one of them:",
                copies.len()
            ));
            for copy in &copies {
                let channel = Channel::detect(copy);
                let version = Command::new(copy)
                    .arg("--version")
                    .output()
                    .ok()
                    .map(|o| String::from_utf8_lossy(&o.stdout).trim().to_string())
                    .unwrap_or_default();
                let how = match channel {
                    Channel::Installer | Channel::Homebrew | Channel::Scoop => {
                        format!("remove with: {} self uninstall", copy.display())
                    }
                    Channel::Foreign(name) => format!("remove with {name}"),
                    Channel::Unknown => "delete the file if you put it there".into(),
                };
                println!(
                    "        {}  [{}] {version}  ({how})",
                    copy.display(),
                    channel.name()
                );
            }
        }
    }
}

/// A pulled image that is not the one running means an upgrade was half done.
fn check_images_current(project: &Project, r: &mut Report) {
    for service in ["chronos-app", "chronos-proxy"] {
        let Some(container) = output_line(project.compose_output(&["ps", "-q", service])) else {
            continue;
        };
        let inspect = |args: &[&str]| {
            output_line(
                Command::new("docker")
                    .args(args)
                    .stdin(Stdio::null())
                    .output()
                    .map_err(Into::into),
            )
        };
        let (Some(running), Some(reference)) = (
            inspect(&["inspect", "--format", "{{.Image}}", &container]),
            inspect(&["inspect", "--format", "{{.Config.Image}}", &container]),
        ) else {
            continue;
        };
        match inspect(&["image", "inspect", "--format", "{{.Id}}", &reference]) {
            Some(pulled) if pulled != running => r.warn(&format!(
                "{service} runs an older image than the {reference} that was pulled. Run `chronos up`."
            )),
            _ => {}
        }
    }
}

fn output_line(out: Result<std::process::Output>) -> Option<String> {
    let out = out.ok().filter(|o| o.status.success())?;
    let line = String::from_utf8_lossy(&out.stdout).trim().to_string();
    (!line.is_empty()).then_some(line)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn tags_always_carry_one_v() {
        assert_eq!(tag_for("0.13.0"), "v0.13.0");
        assert_eq!(tag_for("v0.13.0"), "v0.13.0");
    }

    #[test]
    fn init_writes_secrets_and_a_pin_and_never_overwrites() {
        let dir = tempfile::tempdir().unwrap();
        let project = Project::new(dir.path().to_path_buf());
        init(&project, "10.0.0.5", Some("0.13.0")).unwrap();
        let env = fs::read_to_string(project.env_path()).unwrap();
        assert_eq!(env_file::get(&env, "VERSION").as_deref(), Some("v0.13.0"));
        assert_eq!(
            env_file::get(&env, "APP_CORS_ORIGINS").as_deref(),
            Some("http://10.0.0.5,http://localhost")
        );
        for (needle, _) in &env_file::PLACEHOLDERS[..3] {
            assert!(!env.contains(needle), "{needle} left in .env");
        }
        let db = env_file::get(&env, "DB_PASSWORD").unwrap();
        assert!(env_file::get(&env, "DATABASE_URL").unwrap().contains(&db));
        assert!(project.compose_path().is_file());
        assert!(init(&project, "localhost", None).is_err());
    }

    #[test]
    fn the_embedded_compose_file_reads_version_from_env() {
        assert!(COMPOSE.contains("chronos-ledger-backend:${VERSION:-latest}"));
        assert!(COMPOSE.contains("chronos-db:"));
    }

    fn taken_at(schema: Option<&str>) -> BackupInfo {
        BackupInfo {
            server_version: Some("0.14.0".into()),
            schema_version: schema.map(Into::into),
            created_at: String::new(),
        }
    }

    fn running_at(schema: Option<&str>) -> Health {
        Health {
            version: "0.14.0".into(),
            schema_version: schema.map(Into::into),
        }
    }

    #[test]
    fn a_backup_restores_only_onto_the_schema_it_was_taken_at() {
        assert!(require_same_schema(&taken_at(Some("1")), &running_at(Some("1"))).is_ok());

        let refused = require_same_schema(&taken_at(Some("1")), &running_at(Some("2")))
            .unwrap_err()
            .to_string();
        assert!(refused.contains("taken at schema version 1"));
        assert!(refused.contains("no upgrade path"));
        assert!(refused.contains("0.14.0"));

        assert!(require_same_schema(&taken_at(None), &running_at(Some("1"))).is_err());
        assert!(require_same_schema(&taken_at(Some("1")), &running_at(None)).is_err());
    }
}
