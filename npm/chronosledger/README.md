# chronosledger

`chronos` sets up and runs a [Chronos Ledger](https://chronos.vkrishna04.me) server that is deployed with Docker compose. It writes the first configuration with generated secrets, starts and stops the stack, upgrades it with a backup taken first, restores backups, and reports what is wrong with an install.

```sh
npm i -g chronosledger
chronos init --host chronos.example.org
chronos up
```

Or run it once without installing:

```sh
npx chronosledger@latest doctor
```

npx keeps a cached copy, so add `@latest` to get the newest release. To update an installed copy, run `npm i -g chronosledger@latest` or `chronos self update`.

The package holds a small launcher. The program itself is a native binary that comes from one of six platform packages (`chronosledger-linux-x64`, `chronosledger-linux-arm64`, `chronosledger-darwin-x64`, `chronosledger-darwin-arm64`, `chronosledger-windows-x64`, `chronosledger-windows-arm64`). npm installs only the one that fits your machine. Docker is still needed to run the server.

Commands are described in the [CLI guide](https://github.com/Life-Experimentalist/Chronos-Ledger/blob/main/docs/cli.md).

Apache License 2.0.
