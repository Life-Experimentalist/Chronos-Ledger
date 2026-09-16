# Distribution Plan

<!-- Copyright 2026 Chronos Ledger Contributors (Apache 2.0) -->

Status: planned for v0.13, not built. Today the only supported install is the
Docker compose deployment in [deployment.md](deployment.md), using the images
on GHCR and Docker Hub. This page is the design the work follows, written so
each step can be picked up and finished on its own.

## 1. What gets distributed

Chronos Ledger is a server made of four parts: the FastAPI backend, the
Next.js static frontend, nginx, and PostgreSQL (plus optional Redis). The
double-booking guarantees rely on PostgreSQL exclusion constraints, so there is
no honest single-file build of the server itself.

So there are two artifacts, shipped through different channels:

| Artifact | What it is | Channels |
|---|---|---|
| Server images | `backend`, `frontend`, `nginx` containers | GHCR, Docker Hub, compose file, Helm chart |
| `chronos` CLI | A small static binary that installs, configures, upgrades, backs up and diagnoses a server | GitHub Releases, install scripts, Homebrew tap, Scoop bucket, WinGet, npm, PyPI, crates.io, later deb/rpm |

The CLI is where the channels live. It is written in Rust so the release
pipeline, channel detection and install receipt from dev-prune can be reused
almost unchanged: dev-prune already ships one static binary through every
channel above from one tag-triggered workflow.

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

`setup.sh`, `bin/chronos_maintenance_vault.sh` and
`bin/chronos_intranet_autodiscover.sh` become thin wrappers over these
commands, then are retired one release later.

## 2. Channels

Every channel is fed by one workflow on `v*` tags, after release-please has
cut the release. Build targets follow dev-prune: Linux x64 and arm64 (static
musl), macOS x64 and arm64, Windows x64, arm64 and x86.

| Channel | Install command | Built by | Ready when |
|---|---|---|---|
| GitHub Releases | download archive | `cargo build` per target, `.sha256` sidecars | v0.13 |
| Install scripts | `curl -fsSL <site>/install.sh \| sh`, `irm <site>/install.ps1 \| iex` | served from the Pages site | v0.13 |
| Homebrew | `brew install life-experimentalist/tap/chronos` | formula rendered from sidecars, synced into the existing tap | v0.13 |
| Scoop | `scoop bucket add le https://github.com/Life-Experimentalist/scoop-bucket` then `scoop install chronos` | manifest rendered from sidecars | v0.13 |
| WinGet | `winget install LifeExperimentalist.Chronos` | `wingetcreate submit` | v0.13, merge depends on Microsoft review |
| npm | `npx @life-experimentalist/chronos` | per-platform packages with `optionalDependencies`, trusted publishing | v0.13 |
| PyPI | `uvx chronos-ledger` / `pipx install chronos-ledger` | wheels wrapping the binary, trusted publishing | v0.13 |
| crates.io | `cargo install chronos-ledger` / `cargo binstall` | `cargo publish` | v0.13 |
| Container images | `docker compose pull` | existing `cd.yml` | already shipping |
| Helm | `helm install chronos oci://ghcr.io/life-experimentalist/charts/chronos` | chart pushed as OCI artifact | v0.14 |
| deb / rpm | `apt install chronos` / `dnf install chronos` | nfpm, GPG-signed repo on Pages | v0.14 |
| MSI | `msiexec /i chronos.msi` | WiX, only if an organization needs Group Policy deploys | on request |

Package names above are proposals; check each registry for availability
before the first publish and record the final names in this table.

Prerelease tags publish only to GitHub Releases and npm's `next` tag. They
never touch the Homebrew, Scoop or WinGet manifests.

## 3. Drift

Drift is any state where what is installed differs from what something else
believes is installed. There are two layers, and both are handled.

### 3a. The CLI installed through more than one channel

A person installs with Homebrew, later runs the install script, and later
`npm i -g`. Now three copies exist, PATH picks one, and upgrading or
uninstalling through one manager leaves the others behind.

The rules, taken from dev-prune where they already hold up:

1. **The path decides the channel.** `chronos` works out which manager owns
   the running binary from where it lives (WinGet, Scoop, Homebrew, Cargo,
   npm-family, uv, pipx, pip, the managed install directory, or unknown). This
   check is the only source of truth.
2. **A receipt records what our installer did.** The install scripts write
   `install.json` beside the binary: schema, version, channel, installed_at,
   the PATH entry they added. It is advisory: a missing receipt means our
   installer did not write one, not that the copy is unmanaged. The receipt
   exists so uninstall only removes a PATH entry it added.
3. **Only the owning manager changes a copy.** `self update` and
   `self uninstall` run that manager's own command (`brew upgrade`,
   `scoop update`, `winget upgrade`, `npm i -g`, `uv tool upgrade`, `pipx
   upgrade`, `cargo install`). Files are replaced or deleted directly only for
   the install-script copy. Deleting a file behind a manager's back leaves
   that manager's records pointing at nothing.
4. **Moving channels is one command.** `chronos self install --channel <name>`
   installs through the new manager first, then removes the old copy through
   its own manager. `--dry-run` prints the plan.
5. **Install scripts never remove other copies.** If another copy is on PATH
   they say so and offer the move above once. `CI`, no terminal, or
   `CHRONOS_NO_MIGRATE_PROMPT=1` skips the question.
6. **`chronos doctor` reports and never deletes.** It scans PATH and the known
   manager directories, and lists every copy with its version and channel.
   Anything other than exactly one copy gets a warning with the exact commands
   that fix it.
7. **Windows ships one exe hash.** Aliases are byte-identical copies so
   SmartScreen and Defender build one reputation record, not several.

### 3b. The CLI, the images and the database disagree

This is the drift that breaks a running server.

| Mismatch | Detected by | Result |
|---|---|---|
| Database migrated by a newer server than the image now running (someone rolled the tag back) | Backend start: `alembic upgrade head` cannot find the revision | Today the container restarts in a loop. Planned: the backend exits once with `database is at revision X, newer than this build; run chronos upgrade --to <version that has X>` and `doctor` names the version |
| CLI older than the server it manages | CLI compares its supported range with the server's `/health` version | Refuses `upgrade` and `restore`, tells the person to update the CLI through its channel |
| Compose file edited by hand to a different tag than `.env` records | `doctor` | Warning showing both values |
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
| npm, PyPI, crates.io | Trusted publishing with provenance | free | No long-lived tokens (crates.io via its trusted publishing where available, token otherwise) |
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
downloads may still see a warning. Shipping one exe hash (rule 7) and keeping
the certificate across releases both help.

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

1. `/health` reports version and migration revision; backups record the revision.
2. The CLI with `init`, `up`, `down`, `status`, `upgrade`, `backup`, `restore`, `doctor`.
3. Channel detection, receipt, `self update`, `self uninstall`, `self install --channel`.
4. Release workflow for the CLI: build matrix, sidecars, attestations, hygiene check.
5. Channels in this order: GitHub Releases, install scripts, Homebrew tap, Scoop, npm, PyPI, crates.io, WinGet.
6. Windows signing once the Certum certificate is issued.
7. Helm chart, then deb/rpm.

Each step ships on its own and leaves the compose install working as it does today.

## Acceptance checks

- Installing through any two channels, `chronos doctor` lists both copies and prints commands that leave exactly one.
- `chronos self uninstall` from each channel leaves no binary, receipt or PATH entry behind, and the owning manager no longer lists it.
- Rolling the image tag back past a migration makes the backend print which version is needed instead of looping.
- `gh attestation verify` passes for every archive and image of a release.
- A fresh `chronos init && chronos up` on Linux, macOS and Windows reaches a healthy `/health`.

## Sources

- Azure Artifact Signing eligibility: <https://learn.microsoft.com/en-us/windows/apps/package-and-deploy/code-signing-options>
- Certum Open Source Code Signing: <https://shop.certum.eu/code-signing.html>
- Homebrew acceptable formulae and notability: <https://docs.brew.sh/Acceptable-Formulae>
