# Publishing to npm, PyPI and crates.io

From 0.18.0 each release is also published to three registries:

| Registry | CLI | SDK |
|---|---|---|
| npm | `chronosledger` and six platform packages | `chronosledger-client` |
| PyPI | `chronosledger` (six wheels) | `chronosledger-client` |
| crates.io | `chronosledger` (the `chronos` binary) | `chronosledger-client` |

The Go SDK is not uploaded anywhere. Its module path is
`chronos.vkrishna04.me/sdks/go`, and the workflow tags `sdks/go/vX.Y.Z` so
`go get` can resolve it.

`.github/workflows/publish.yml` does all of it. No token or password is stored
anywhere: every registry trusts the short-lived OIDC identity the workflow is
given. Each registry stays off until its repository variable is `true`, so
merging the workflow publishes nothing.

This page is the one-time setup, in the order it has to be done. A trusted
publisher can only be attached to a package that already exists on npm and
crates.io, so the first upload of those two comes from your own machine. PyPI
has no such step.

The workflow file name `publish.yml` is part of every registration below. Do not
rename it.

## Before you start

The workflow publishes an existing release. It downloads the six CLI binaries
and their `.sha256` files from the GitHub release for the tag, so the release
for `v0.18.0` must exist first (release-please makes it, and `release.yml`
attaches the binaries). Until then the `Release assets` job fails and nothing
else runs.

For steps a to e you need Node with npm, the `gh` CLI logged in, and a POSIX
shell (Git Bash is fine on Windows) for the two `scripts/npm-*.sh` files. The
workflow installs the npm 11.5.1 or newer that trusted publishing needs; your
own npm does not have to be that new.

Tags have to look like `v1.2.3`. A prerelease tag such as `v0.19.0-rc.1` is
refused.

## a. Claim the npm names

npm cannot attach a trusted publisher to a package that does not exist, so
publish each of the eight packages once by hand.

```sh
npm login
TAG=v0.18.0

# The six binaries and their checksums, from the release
mkdir -p ~/chronos-publish/assets
gh release download "$TAG" --repo Life-Experimentalist/Chronos-Ledger \
  --pattern "chronos-$TAG-*" --dir ~/chronos-publish/assets

# Build the six platform packages and the dispatcher, then publish them
scripts/npm-prepare.sh "$TAG" ~/chronos-publish/assets ~/chronos-publish/npm-out
scripts/npm-publish.sh --local ~/chronos-publish/npm-out
```

`npm-prepare.sh` checks every binary against its `.sha256` file and writes
`chronosledger`, `chronosledger-linux-x64`, `chronosledger-linux-arm64`,
`chronosledger-darwin-x64`, `chronosledger-darwin-arm64`,
`chronosledger-windows-x64` and `chronosledger-windows-arm64` into the output
directory. `npm-publish.sh --local` publishes the platform packages first and
the dispatcher last, skips any version already on the registry, and can be run
again after a failure. The `--local` flag publishes with your login and without
provenance. The workflow does the same job with provenance.

Then the SDK. Check out the tag so the version matches, and publish from there:

```sh
git switch --detach "$TAG"
cd sdks/typescript
npm ci --ignore-scripts
npm publish --access public
```

`prepack` builds the package, so there is no separate build step. The versions
uploaded this way carry no provenance. The workflow skips them later because
they are already on the registry, and every version after them is published
with provenance.

## b. Add a trusted publisher on npm

For each of the eight packages, open `https://www.npmjs.com/package/<name>/access`,
choose Trusted Publisher, GitHub Actions, and enter:

| Field | Value |
|---|---|
| Organization or user | `Life-Experimentalist` |
| Repository | `Chronos-Ledger` |
| Workflow filename | `publish.yml` |
| Environment | leave empty |

The eight names are `chronosledger`, `chronosledger-linux-x64`,
`chronosledger-linux-arm64`, `chronosledger-darwin-x64`,
`chronosledger-darwin-arm64`, `chronosledger-windows-x64`,
`chronosledger-windows-arm64` and `chronosledger-client`.

The npm jobs use no environment, so the field stays empty. A value there would
make npm reject the workflow's token.

## c. Add pending publishers on PyPI

PyPI lets you register a publisher before the project exists, so there is no
manual upload. At `https://pypi.org/manage/account/publishing/`, add a pending
publisher twice:

| Field | First | Second |
|---|---|---|
| PyPI project name | `chronosledger` | `chronosledger-client` |
| Owner | `Life-Experimentalist` | `Life-Experimentalist` |
| Repository name | `Chronos-Ledger` | `Chronos-Ledger` |
| Workflow name | `publish.yml` | `publish.yml` |
| Environment name | `pypi` | `pypi` |

The first successful publish turns each pending publisher into a normal one.

## d. Publish the crates once, then add trusted publishers

crates.io has the same rule as npm: the crate must exist first. From a checkout
of the release tag, with an API token from `https://crates.io/settings/tokens`
(scope `publish-new` and `publish-update`) in `cargo login`:

```sh
git switch --detach v0.18.0
cargo publish --locked --manifest-path cli/Cargo.toml
cargo publish --locked --manifest-path sdks/rust/Cargo.toml
```

Revoke the token afterwards. It is not needed again.

Then, for each crate, open `https://crates.io/crates/<name>/settings`, add a
trusted publisher with GitHub, and enter:

| Field | Value |
|---|---|
| Repository owner | `Life-Experimentalist` |
| Repository name | `Chronos-Ledger` |
| Workflow filename | `publish.yml` |
| Environment | `crates-io` |

Do this for `chronosledger` and for `chronosledger-client`.

## e. Create the environments and switch the channels on

The PyPI and crates.io jobs run in GitHub environments so the registry can tell
them apart from any other workflow. Create two, with no secrets, no reviewers
and no other settings:

```sh
gh api -X PUT repos/Life-Experimentalist/Chronos-Ledger/environments/pypi
gh api -X PUT repos/Life-Experimentalist/Chronos-Ledger/environments/crates-io
```

(Or Settings, Environments, New environment.) Then turn each channel on:

```sh
gh variable set NPM_PUBLISH --body true --repo Life-Experimentalist/Chronos-Ledger
gh variable set PYPI_PUBLISH --body true --repo Life-Experimentalist/Chronos-Ledger
gh variable set CRATES_PUBLISH --body true --repo Life-Experimentalist/Chronos-Ledger
```

You can enable one channel at a time. A channel whose variable is not `true`
is skipped, and the summary says so.

## f. Run it

```sh
gh workflow run publish.yml -f tag=v0.18.0 --repo Life-Experimentalist/Chronos-Ledger
gh run watch --repo Life-Experimentalist/Chronos-Ledger
```

Open the run and read the summary at the bottom of its page. It is a table with
one row per package and one of these results:

| Result | Meaning |
|---|---|
| published | uploaded, or that version was already there |
| skipped, set the repository variable ... | the channel is off |
| **failed** | open that job's log |
| **not run** | an earlier job failed, so this one never started |

A green run where everything says `skipped` published nothing. The table is
there so that cannot be mistaken for success.

Every job can be run again for the same tag. A version already on a registry is
skipped, and an existing `sdks/go/<tag>` tag is left alone. If one job fails,
fix the cause and run the workflow again; the jobs that succeeded do nothing the
second time.

## After setup

Nothing more is needed. When release-please publishes a release, the `release`
job in `ci.yml` starts `release.yml`, which attaches the binaries and then runs
`gh workflow run publish.yml` for the new tag. The first run that has all three
variables set publishes the release without anyone touching it.

To check a published release from a clean machine:

```sh
npx chronosledger@latest --version
uvx chronosledger@latest --version
cargo binstall chronosledger
```

## How the packages are built

- **npm.** `chronosledger` is a small Node script plus `optionalDependencies` on
  the six platform packages. npm installs only the one whose `os` and `cpu`
  match, and the script runs that package's binary. There is no `postinstall`
  script, nothing is downloaded when you install, and `--ignore-scripts` changes
  nothing. The Windows packages are named `chronosledger-windows-*` and declare
  `os: win32`, because npm rejects new names that begin with `win32-`.
- **PyPI.** `scripts/build_wheels.py` writes the wheels directly, one per
  platform, each holding the same binary under both command names. There is no
  Python code in them. The Linux binaries are static musl builds, so one binary
  carries both the `manylinux` and `musllinux` tags.
- **crates.io.** `cargo publish` uploads the source. `cargo install` compiles it;
  `cargo binstall` fetches the release binary instead.

Every platform package is built from the binaries on the GitHub release, after
checking each against its `.sha256` file. Nothing is compiled during a publish.

## When something goes wrong

- **npm answers 404 or "not found" when publishing.** The package name does not
  exist yet or the trusted publisher is missing. Redo steps a and b for that
  name.
- **npm answers 403.** The trusted publisher's workflow file name or environment
  does not match. npm wants `publish.yml` and no environment.
- **PyPI answers `invalid-publisher`.** The pending publisher's environment must
  be `pypi`, and the workflow name `publish.yml`.
- **crates.io rejects the token exchange.** The trusted publisher on the crate
  needs the environment `crates-io`, and the environment must exist in the
  repository.
- **A job is `skipped` although the variable is set.** Variables are case
  sensitive and must be exactly `true`.
- **The Go proxy step fails.** `chronos.vkrishna04.me/sdks/go` resolves through
  the `go-import` tag on the Pages site. The site has to be live for the proxy to
  find the module. The tag itself is already created by then, and running the
  workflow again repeats only the lookup.
