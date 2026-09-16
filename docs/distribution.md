# Distribution Plan

<!-- Copyright 2026 Chronos Ledger Contributors (Apache 2.0) -->

Status: the CLI and its first four channels are built for v0.13 (see
[cli.md](cli.md)). The other channels below wait until someone asks for them.
The Docker compose deployment in [deployment.md](deployment.md) keeps working
with or without the CLI.

## 1. What gets distributed

Chronos Ledger is a server made of four parts: the FastAPI backend, the
Next.js static frontend, nginx, and PostgreSQL (plus optional Redis). The
double-booking guarantees rely on PostgreSQL exclusion constraints, so there is
no honest single-file build of the server itself.

So there are two artifacts, shipped through different channels:

| Artifact | What it is | Channels |
|---|---|---|
| Server images | `backend`, `frontend`, `nginx` containers | GHCR, Docker Hub, compose file, Helm chart |
| `chronos` CLI | A small static binary that installs, configures, upgrades, backs up and diagnoses a server | GitHub Releases, install scripts, Homebrew tap, Scoop bucket |

The CLI is written in Rust, so it is one static file per platform with no
runtime to install first. Its release pipeline and channel detection follow
dev-prune, minus the part of dev-prune that hurt: too many channels.

A native server install (a Python wheel with the frontend bundled, run against
a PostgreSQL you manage) stays out of scope until someone asks for it.

### CLI commands

| Command | Does |
|---|---|
| `chronos init` | Writes `.env` with generated secrets, the compose file, and a pinned image tag |
| `chronos up` / `down` / `status` | Wraps `docker compose` for that project |
| `chronos upgrade [--to X.Y.Z]` | Backs up, moves the image tag, starts, waits for health |
| `chronos backup` / `restore` | `pg_dump` / restore through the running database container |
| `chronos doctor` | Finds every problem in section 3 and prints the fix |
| `chronos self update` | Updates the CLI through whichever channel installed it |
| `chronos self uninstall` | Removes the CLI through that same channel |

There is no `self install --channel`. Moving channels is uninstall, then install.

`setup.sh`, `bin/chronos_maintenance_vault.sh` and
`bin/chronos_intranet_autodiscover.sh` become thin wrappers over these
commands, then are retired one release later.

## 2. Channels

dev-prune shipped through eight channels at once, and most of its bugs were
in the seams between them: install, update, reinstall and uninstall each
worked out the channel differently, a copy from one manager got replaced by
another, and every new channel multiplied the cases to test. So Chronos starts
with the four channels that need no registry account and no secret, and adds
one only when someone asks for it.

The CLI jobs in `release.yml` run when release-please publishes a release.
Native runners build Linux x64 and arm64 (static musl), macOS x64 and arm64,
and Windows x64 and arm64. Each binary is run once, then uploaded with a
`.sha256` sidecar and a build provenance attestation.

| Channel | Install command | Built by | Status |
|---|---|---|---|
| GitHub Releases | download `chronos-vX.Y.Z-<os>-<arch>` | `cli-build` and `cli-publish` in `release.yml` | v0.13 |
| Install scripts | `curl -fsSL https://chronos.vkrishna04.me/install.sh \| sh`, `irm https://chronos.vkrishna04.me/install.ps1 \| iex` | `docs/install.sh`, `docs/install.ps1`, served by Pages | v0.13 |
| Homebrew | `brew install life-experimentalist/tap/chronos` | `chronos.rb` attached to each release; the tap copies it from the latest release | v0.13 |
| Scoop | `scoop bucket add le https://github.com/Life-Experimentalist/scoop-bucket` then `scoop install chronos` | `chronos.json` attached to each release; the bucket copies it the same way | v0.13 |
| Container images | `docker compose pull` | existing `cd.yml` | already shipping |
| WinGet | `winget install LifeExperimentalist.Chronos` | `wingetcreate submit` | on request |
| npm | `npx @life-experimentalist/chronos` | per-platform packages, trusted publishing | on request |
| PyPI | `uvx chronos-ledger` | wheels wrapping the binary, trusted publishing | on request |
| crates.io | `cargo install chronos-ledger` | `cargo publish` | on request |
| Helm, deb / rpm, MSI | | | on request |

The tap and the bucket pull from the latest release on their own schedule, so
no token in this repository can write to another one.

Package names for the on-request channels are proposals; check each registry
before a first publish. Until a channel is supported, `chronos` treats a copy
installed through it as foreign: it names the manager and changes nothing.

## 3. Drift

Drift is any state where what is installed differs from what something else
believes is installed. There are two layers, and both are handled.

### 3a. The CLI installed through more than one channel

A person installs with Homebrew, later runs the install script, and later
`npm i -g`. Now three copies exist, PATH picks one, and upgrading or
uninstalling through one manager leaves the others behind.

The rules, taken from what went wrong in dev-prune:

1. **The path decides the channel.** `chronos` works out which manager owns
   the running binary from where it lives: the install-script directory
   (`~/.chronos/bin`, or `%LOCALAPPDATA%\chronos\bin` on Windows), Homebrew,
   Scoop, a known manager this project does not publish to (Cargo, npm, uv,
   pipx, WinGet and others), or unknown. This check is the only source of
   truth, and every command uses the same one.
2. **A receipt records what our installer did.** The install scripts write
   `install.json` in that directory: schema, version, channel, installed_at,
   and the PATH change they made. It is advisory and read for one thing, so
   uninstall removes exactly the PATH line or entry the script added.
   Reinstalling keeps the entry an earlier run recorded.
3. **Only the owning manager changes a copy.** `self update` and
   `self uninstall` run `brew` or `scoop` for their copies. Files are replaced
   or deleted directly only for the install-script copy. Foreign and unknown
   copies are never changed; the error names who owns them.
4. **Install scripts never remove other copies.** If another copy is on PATH
   they say where and which tool removes it.
5. **`chronos doctor` reports and never deletes.** It lists every copy on PATH
   with its version and channel, and anything other than exactly one copy gets
   a warning with the command that removes each.
6. **Windows replaces a running exe by renaming it.** Update moves
   `chronos.exe` to `chronos.exe.old` and puts the new file in place; the next
   run deletes the `.old` file. Uninstall does the same, then a detached shell
   removes `bin` once the process has exited.
7. **The latest version comes from a redirect.** `releases/latest` answers with
   the tag in its `Location` header, so update checks spend no API rate limit.
8. **Nothing is installed before its checksum matches.** A checksum file that
   is not a SHA-256 digest (an HTML error page) is reported as that, not as
   tampering.

### 3b. The CLI, the images and the database disagree

This is the drift that breaks a running server.

| Mismatch | Detected by | Result |
|---|---|---|
| Database migrated by a newer server than the image now running (someone rolled the tag back) | Backend start: `alembic upgrade head` cannot find the revision | Today the container restarts in a loop. Planned: the backend exits once with `database is at revision X, newer than this build; run chronos upgrade --to <version that has X>` and `doctor` names the version |
| CLI older than the server it manages | CLI compares its own version with the server's `/health` version | Refuses `upgrade` and `restore`, tells the person to run `chronos self update` |
| Server running a different version than `.env` pins | `doctor` | Warning with `chronos up` |
| Compose file differs from the release's copy | `doctor` | Warning; `upgrade` keeps the old file as `docker-compose.yml.before-upgrade` |
| Images pulled but not restarted | `doctor` compares running container image digests with the pulled ones | Warning with `chronos up` |
| Backup taken on a newer migration revision than the target server | `restore` reads the revision stored in the backup | Refuses, names the version needed |

Two small server changes make 3b work: `/health` reports `version` and the
Alembic revision, and every backup records the revision it was taken at.

## 4. Signing

No option below needs download counts, stars, or a reputation history before
it will sign.

| Target | Method | Cost | Why this one |
|---|---|---|---|
| Container images | GitHub build provenance attestations (Sigstore, keyless). Already in `cd.yml`. Add `cosign sign` keyless for registries and tooling that expect cosign signatures | free | Identity is the workflow, no key to leak |
| Release archives and binaries | `actions/attest-build-provenance`, verified with `gh attestation verify` | free | Same as dev-prune |
| npm, PyPI, crates.io, when added | Trusted publishing with provenance | free | No long-lived tokens |
| Windows `chronos.exe` and any MSI | Certum Open Source Code Signing certificate, cloud key through SimplySign | about $50 for the certificate | Issued to an individual open source developer; no popularity requirement |
| macOS prebuilt binaries | Apple Developer ID and notarization | $99 per year | Only needed if Gatekeeper warnings on direct downloads become a problem; Homebrew installs are not affected |
| deb / rpm repository | A dedicated GPG key, public key published on the site | free | What apt and dnf check |

What does not work, so nobody spends time on it again:

- **Azure Artifact Signing (formerly Trusted Signing)** only issues public-trust
  certificates to individuals in the United States and Canada.
- **SignPath Foundation's free open source program** turned down dev-prune for
  not having enough reputation yet, and would do the same here.

Signing a Windows binary removes the "unknown publisher" wording. SmartScreen
still builds reputation per certificate and per file over time, so early
downloads may still see a warning. Shipping one exe per architecture and
keeping the certificate across releases both help.

Automating SimplySign in CI is awkward because it expects an interactive
login. Plan for signing on a release step the maintainer runs on Windows,
then uploading the signed files to the draft release, and automate later if a
supported path appears.

## 5. Homebrew and popularity

The Life-Experimentalist tap has no popularity requirement: anything in the
tap installs with `brew install life-experimentalist/tap/chronos`. That is the
plan.

homebrew-core is different. It needs the project to be notable (at least 75
stars, 30 forks or 30 watchers, and a higher bar when the author submits it),
and it builds from source. Move to core only when the repository meets that
bar on its own. Nothing in the tap has to change first.

WinGet has no popularity requirement, but its validation runs Defender on the
installer, so the binary hygiene checks from dev-prune's release workflow
come across too. Scoop's main bucket is selective; the project's own bucket is
not.

## 6. Order of work

1. Done: `/health` reports version and migration revision; backups record the revision.
2. Done: the CLI with `init`, `up`, `down`, `status`, `upgrade`, `backup`, `restore`, `doctor`.
3. Done: channel detection, receipt, `self update`, `self uninstall`.
4. Done: release jobs for the CLI: build matrix, sidecars, attestations, formula and manifest.
5. After the first CLI release: the tap and the bucket copy `chronos.rb` and `chronos.json` from it.
6. Windows signing once the Certum certificate is issued.
7. Other channels, one at a time, when asked for.

`setup.sh` and the scripts in `bin/` keep working through 0.13 and are retired
once the CLI has been through one release.

## Acceptance checks

- Installing through any two channels, `chronos doctor` lists both copies and prints commands that leave exactly one.
- `chronos self uninstall` from each channel leaves no binary, receipt or PATH entry behind, and the owning manager no longer lists it.
- Running the install script twice for the same version changes nothing, and uninstalling afterwards still removes the PATH entry.
- Rolling the image tag back past a migration makes the backend print which version is needed instead of looping.
- `gh attestation verify` passes for every binary and image of a release.
- A fresh `chronos init && chronos up` on Linux, macOS and Windows reaches a healthy `/health`.

## Sources

- Azure Artifact Signing eligibility: <https://learn.microsoft.com/en-us/windows/apps/package-and-deploy/code-signing-options>
- Certum Open Source Code Signing: <https://shop.certum.eu/code-signing.html>
- Homebrew acceptable formulae and notability: <https://docs.brew.sh/Acceptable-Formulae>
