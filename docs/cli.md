# The `chronos` CLI

`chronos` runs a Chronos Ledger server that is deployed with Docker compose. It
writes the first configuration, starts and stops the stack, upgrades it with a
backup taken first, restores backups, and tells you what is wrong with an
install. It does not replace Docker; it runs `docker compose` for you with the
checks that are easy to forget by hand.

It ships from v0.13.0. Earlier releases have no CLI binaries.

## Install

Pick one channel. Installing through two leaves two copies on PATH, and
`chronos doctor` will point that out.

| Platform | Command |
|---|---|
| Linux, macOS | `curl -fsSL https://chronos.vkrishna04.me/install.sh \| sh` |
| Windows | `irm https://chronos.vkrishna04.me/install.ps1 \| iex` |
| Homebrew | `brew install life-experimentalist/tap/chronos` |
| Scoop | `scoop bucket add le https://github.com/Life-Experimentalist/scoop-bucket` then `scoop install chronos` |
| Manual | Download `chronos-vX.Y.Z-<os>-<arch>` from the release page and check it against its `.sha256` file |

The install scripts put the binary in `~/.chronos/bin` (Windows:
`%LOCALAPPDATA%\chronos\bin`), or in `$CHRONOS_INSTALL_DIR/bin` when that is
set. They verify the checksum before anything is written, add the directory to
PATH once, and record that change in `install.json` next to `bin`. A specific
version: `sh -s -- --version 0.13.0` or `-Version 0.13.0`. Running a script
again for the version already installed does nothing unless you pass
`--force` / `-Force`.

Release binaries also carry a build provenance attestation:

```bash
gh attestation verify chronos-v0.13.0-linux-x64 --repo Life-Experimentalist/Chronos-Ledger
```

## Commands

All server commands work on the current directory; pass `--dir <path>` to use
another one.

| Command | What it does |
|---|---|
| `chronos init --host <address>` | Writes `docker-compose.yml` and `.env` with generated secrets and the image tag pinned to this CLI's version (`--tag` for another). Refuses if `.env` exists. Prints the first admin password once. |
| `chronos up` | Starts the stack and waits until `/health/ready` answers. |
| `chronos down` | Stops the stack. Data stays in its volumes. |
| `chronos status` | Container states and what `/health` reports. |
| `chronos upgrade [--to X.Y.Z] [--yes]` | Backs up, moves the pinned tag, pulls, starts, waits until ready and checks the version. On failure it prints how to go back. |
| `chronos backup` | Dumps the database to `backups/` with a `.json` file recording the version and migration revision. |
| `chronos restore <file> [--yes]` | Replaces the database with that backup. Refuses a backup newer than the server. |
| `chronos doctor` | Reports problems and how to fix each. Changes nothing. |
| `chronos self update` | Updates the CLI through the channel that installed it. |
| `chronos self uninstall [--yes]` | Removes the CLI through the channel that installed it. |

Commands that replace data ask first. Without a terminal the answer is no, so
scripts must pass `--yes`.

`upgrade` will not move to a version newer than the CLI itself, because the
compose file it writes comes from the CLI's release. Run `chronos self update`
first. If the compose file was edited by hand, the old one is kept as
`docker-compose.yml.before-upgrade`.

## Updating and removing the CLI

`chronos self update` and `chronos self uninstall` look at where the running
binary lives and hand over to whatever put it there:

| Installed with | `self update` runs | `self uninstall` runs |
|---|---|---|
| install script | downloads, verifies and replaces the binary | removes the binary, `install.json` and the PATH change the script recorded |
| Homebrew | `brew upgrade chronos` | `brew uninstall chronos` |
| Scoop | `scoop update chronos` | `scoop uninstall chronos` |
| anything else | nothing; says which tool owns the copy | nothing; says which tool owns the copy |

To switch channels, uninstall with the old one, then install with the new one.

On Windows a running `chronos.exe` cannot be overwritten, so an update renames
it to `chronos.exe.old` and the next run deletes that file. Uninstall removes
`bin` a few seconds after the command exits, and the install directory only if
nothing else is in it.

## When copies disagree

`chronos doctor` checks:

- every `chronos` on PATH, with its version and which channel owns it
- that `docker compose` works
- `.env` placeholders that were never replaced, and whether a version is pinned
- whether the compose file differs from the one in this CLI's release
- whether the running server matches the pinned version, and whether the
  running containers use the images that were last pulled
- whether the CLI is older than the server

It exits with an error when it finds a problem, so it can run in a script.
Install scripts and uninstall report other copies on PATH but never remove
them.

More on how the channels were chosen and how drift is handled:
[distribution.md](distribution.md).
