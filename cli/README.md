# chronosledger

`chronos` sets up and runs a [Chronos Ledger](https://chronos.vkrishna04.me) server that is deployed with Docker compose. It writes the first configuration with generated secrets, starts and stops the stack, upgrades it with a backup taken first, restores backups, and reports what is wrong with an install.

The program is a single native binary named `chronos`. This package carries it so that your usual package manager can fetch it. Docker is still needed to run the server itself.

## Install

From 0.18.0 the same binary is on every registry:

```sh
npm i -g chronosledger          # or: npx chronosledger@latest
uv tool install chronosledger   # or: uvx chronosledger@latest
pipx install chronosledger
cargo install --locked chronosledger   # or: cargo binstall chronosledger
```

The install scripts, Homebrew and Scoop work too. Pick one channel; two copies on PATH are reported by `chronos doctor`.

To update, ask the manager that installed it: `npm i -g chronosledger@latest`, `uv tool upgrade chronosledger`, `pipx upgrade chronosledger`, `cargo install --locked chronosledger`, or run `chronos self update`, which does the right one for you. `npx` and `uvx` fetch a copy into a cache, so add `@latest` to get the newest release.

## Use

```sh
chronos init --host chronos.example.org
chronos up
chronos status
chronos doctor
```

Every command is described in the [CLI guide](https://github.com/Life-Experimentalist/Chronos-Ledger/blob/main/docs/cli.md). The server, its API and the SDKs live in the [main repository](https://github.com/Life-Experimentalist/Chronos-Ledger).

Apache License 2.0.
