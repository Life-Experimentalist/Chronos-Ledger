// Copyright 2026 Chronos Ledger Contributors
// SPDX-License-Identifier: Apache-2.0

//! `chronos`: install, upgrade, back up and diagnose a Chronos Ledger server.
//!
//! The server is a Docker compose stack. Everything here drives `docker compose`
//! against one project directory, which holds the compose file, `.env` and
//! `backups/`. See docs/distribution.md for the design and docs/cli.md for usage.

mod channel;
mod env_file;
mod project;
mod release;
mod selfcmd;
mod server;

use std::path::PathBuf;

use anyhow::Result;
use clap::{Parser, Subcommand};

pub const VERSION: &str = env!("CARGO_PKG_VERSION");

#[derive(Parser)]
#[command(
    name = "chronos",
    version,
    about = "Install, upgrade, back up and diagnose a Chronos Ledger server"
)]
struct Cli {
    /// The project directory holding docker-compose.yml and .env.
    #[arg(long, global = true, default_value = ".")]
    dir: PathBuf,

    #[command(subcommand)]
    command: Command,
}

#[derive(Subcommand)]
enum Command {
    /// Write docker-compose.yml and .env with generated secrets and a pinned image tag.
    Init {
        /// The address people will open in a browser.
        #[arg(long, default_value = "localhost")]
        host: String,
        /// Image tag to pin, for example v0.13.0. Defaults to this CLI's own version.
        #[arg(long)]
        tag: Option<String>,
    },
    /// Start the server and wait until it is ready.
    Up,
    /// Stop the server. Data stays in its volumes.
    Down,
    /// Show the containers and what /health reports.
    Status,
    /// Back up, move the image tag, start, and wait until ready.
    Upgrade {
        /// Target version, for example 0.13.0. Defaults to the latest release.
        #[arg(long)]
        to: Option<String>,
        /// Do not ask for confirmation.
        #[arg(long, short)]
        yes: bool,
    },
    /// Dump the database into backups/, with the migration it was taken at.
    Backup,
    /// Replace the database with a backup taken by `chronos backup`.
    Restore {
        file: PathBuf,
        /// Do not ask for confirmation.
        #[arg(long, short)]
        yes: bool,
    },
    /// Report problems with this install and how to fix them. Changes nothing.
    Doctor,
    /// Manage this CLI itself.
    #[command(name = "self")]
    SelfCmd {
        #[command(subcommand)]
        command: SelfCommand,
    },
}

#[derive(Subcommand)]
enum SelfCommand {
    /// Update the CLI through whichever channel installed it.
    Update,
    /// Remove the CLI through whichever channel installed it.
    Uninstall {
        /// Do not ask for confirmation.
        #[arg(long, short)]
        yes: bool,
    },
}

fn main() {
    if let Err(e) = run() {
        eprintln!("error: {e:#}");
        std::process::exit(1);
    }
}

fn run() -> Result<()> {
    let cli = Cli::parse();
    selfcmd::sweep_replaced_binary();
    let project = project::Project::new(cli.dir);
    match cli.command {
        Command::Init { host, tag } => server::init(&project, &host, tag.as_deref()),
        Command::Up => server::up(&project),
        Command::Down => project.compose_run(&["down"]),
        Command::Status => server::status(&project),
        Command::Upgrade { to, yes } => server::upgrade(&project, to.as_deref(), yes),
        Command::Backup => server::backup(&project).map(|_| ()),
        Command::Restore { file, yes } => server::restore(&project, &file, yes),
        Command::Doctor => server::doctor(&project),
        Command::SelfCmd { command } => match command {
            SelfCommand::Update => selfcmd::update(),
            SelfCommand::Uninstall { yes } => selfcmd::uninstall(yes),
        },
    }
}

/// Ask a yes/no question. Without a terminal the answer is no, so a script that
/// forgot `--yes` stops instead of replacing a database.
pub fn confirm(question: &str, yes: bool) -> bool {
    use std::io::{BufRead, IsTerminal, Write};
    if yes {
        return true;
    }
    if !std::io::stdin().is_terminal() {
        eprintln!("{question} (no terminal to ask on; pass --yes)");
        return false;
    }
    print!("{question} [y/N] ");
    let _ = std::io::stdout().flush();
    let mut line = String::new();
    let _ = std::io::stdin().lock().read_line(&mut line);
    matches!(line.trim(), "y" | "Y" | "yes")
}
