# Changelog

All notable changes to Chronos Ledger are documented here.

This file is automatically maintained by [Release Please](https://github.com/googleapis/release-please).
Human edits between releases will be preserved.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).
Versioning follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## 1.0.0 (2026-09-07)


### ⚠ BREAKING CHANGES

* **api:** CSV import headers are now member_id, member_name, member_email, activity_code, activity_title, unit, day_of_week_index, time_window_start, time_window_end, lead_id, room.

### Features

* add GitHub Pages deployment workflow for landing page ([2c3317d](https://github.com/Life-Experimentalist/Chronos-Ledger/commit/2c3317d9af0912c684bedbb331ba3bda147a59e9))
* **api:** rename the campus vocabulary to neutral organization terms ([2de35c3](https://github.com/Life-Experimentalist/Chronos-Ledger/commit/2de35c3c010e8792b78f8162899c9582b1524137))
* **auth:** a stolen token dies in minutes, and a session can be revoked ([f649179](https://github.com/Life-Experimentalist/Chronos-Ledger/commit/f649179b6f20d71947dfa6ebe9cd22075e3781d0))
* **dx:** setup.sh --demo seeds a showable day, and docs/demo.md walks it ([00159e6](https://github.com/Life-Experimentalist/Chronos-Ledger/commit/00159e6ef61739c6e78d1a3bcea80b3b899dda2d))
* **edge:** the proxy turns on HTTPS by itself when certificates appear ([4df7e02](https://github.com/Life-Experimentalist/Chronos-Ledger/commit/4df7e023be320c6abd8bbbd33c2b9d29bffd82e4))
* enforce the first-login password change server-side for admins ([af11b8c](https://github.com/Life-Experimentalist/Chronos-Ledger/commit/af11b8cc69da4caa98c047ce87c697e20e0e4f7c))
* initial release of Chronos Ledger v1.0.0 ([99effd7](https://github.com/Life-Experimentalist/Chronos-Ledger/commit/99effd72baa3958a0f059467083d840dd62393b4))
* **int-01:** a machine can hold a key, and the key is just a user ([4540f8d](https://github.com/Life-Experimentalist/Chronos-Ledger/commit/4540f8d1742017025ab93df7b32beb2ae0e093dc))
* **pwa:** neutral routes and profile-driven vocabulary in the UI ([5500cb9](https://github.com/Life-Experimentalist/Chronos-Ledger/commit/5500cb908d9dc1dc2198422a8e98b72f417b2350))
* standalone GitHub Pages landing page (pure HTML, dark/light mode, Dark Reader aware) ([ef78751](https://github.com/Life-Experimentalist/Chronos-Ledger/commit/ef78751b8dd4a4372f92ada54934e7f2a2385713))
* use real logo and icon assets throughout (nav, sidebar, kiosk, login, landing, GH Pages) ([48d350b](https://github.com/Life-Experimentalist/Chronos-Ledger/commit/48d350b98c74ee8339aa093b33f6ee47f745adb9))


### Bug Fixes

* a department admin's reach stops at their own department ([3a26597](https://github.com/Life-Experimentalist/Chronos-Ledger/commit/3a26597ddb3e79a1e7a1103e0e0ea891e0af3396))
* a geo-fenced session no longer accepts a check-in that omits coordinates ([3c3e173](https://github.com/Life-Experimentalist/Chronos-Ledger/commit/3c3e173e8c18ba8e9aa829ac865bb3bd6544592d))
* **api:** a time window that runs backwards is refused at the door ([9a09ad0](https://github.com/Life-Experimentalist/Chronos-Ledger/commit/9a09ad0d232f8fbf5ff69d76d9ec46755f8ecd3d))
* backend uv install and frontend TypeScript type error ([154c353](https://github.com/Life-Experimentalist/Chronos-Ledger/commit/154c353a2be6ef11587672375124d67b1b3b1b01))
* calendar feed URLs stop being guessable from user ids ([3ecabaa](https://github.com/Life-Experimentalist/Chronos-Ledger/commit/3ecabaa46f2b9b683e1b53374af576afef0f423c))
* declare email-validator, which EmailStr imports at startup ([c487aba](https://github.com/Life-Experimentalist/Chronos-Ledger/commit/c487aba396dc714ce721da2b2bee70770d113a70))
* declare VALUE=DATE on all-day calendar events per RFC 5545 ([393a6f1](https://github.com/Life-Experimentalist/Chronos-Ledger/commit/393a6f1813216ce2e6a20512588f7be19aa67693))
* **deploy:** the container boots offline, on the venv it was built with ([636ddc2](https://github.com/Life-Experimentalist/Chronos-Ledger/commit/636ddc2e12249d358681e12c0e0a5227f28bab44))
* **dx:** the demo command survives the Windows laptop it was written for ([fc5ccca](https://github.com/Life-Experimentalist/Chronos-Ledger/commit/fc5ccca1c66892bcfc5cbb6b2de88c4abec1d53a))
* **ingestion:** a shared class is one master slot, not one per student ([f43adca](https://github.com/Life-Experimentalist/Chronos-Ledger/commit/f43adca181e5f2bc39db4ee98b40f478a21bff73))
* **lint:** resolve remaining 9 ruff errors (UP042, SIM102, E712) ([4c3c24a](https://github.com/Life-Experimentalist/Chronos-Ledger/commit/4c3c24aff9091e3359bda371c3d6badd3c736fbb))
* make a clean docker compose up actually boot ([a62fca5](https://github.com/Life-Experimentalist/Chronos-Ledger/commit/a62fca545d8bd453116fbb472b1a6860ae3cb0fc))
* make realtime reachable through the deployed proxy ([3a4f81f](https://github.com/Life-Experimentalist/Chronos-Ledger/commit/3a4f81f28b7643c0a6c37112e5239882b9b31b83))
* make the baked-in relative /ws path work in every browser ([b28e8f9](https://github.com/Life-Experimentalist/Chronos-Ledger/commit/b28e8f9ddd9f99e3b489e2789efff3f51d7c4650))
* only a super-admin can create admin accounts ([8efdd81](https://github.com/Life-Experimentalist/Chronos-Ledger/commit/8efdd8120da1a28b848575e3bb420d3740248dfe))
* only a super-admin can modify admin accounts ([6730620](https://github.com/Life-Experimentalist/Chronos-Ledger/commit/67306209e118e20e35e01a4f59f671abeb2aedf1))
* **pwa:** offline attendance queue drains in every browser ([0eb2ca2](https://github.com/Life-Experimentalist/Chronos-Ledger/commit/0eb2ca2d277a1b8ac1ced27c0e3482db4c04a78f))
* resolve all CI failures ([a82eeed](https://github.com/Life-Experimentalist/Chronos-Ledger/commit/a82eeed141e98f5809a2147130ad7cde47cb6c51))
* resolve three CI blockers on fresh repo ([c46dda2](https://github.com/Life-Experimentalist/Chronos-Ledger/commit/c46dda264a13514700175baa7e20d53abd809500))
* untrack uv.lock from gitignore and remove hardcoded default password from setup output ([13a9cfc](https://github.com/Life-Experimentalist/Chronos-Ledger/commit/13a9cfce11796ee00fa8a23426660a73e6648404))
* update telemetry endpoint URLs to new domain ([bb435b5](https://github.com/Life-Experimentalist/Chronos-Ledger/commit/bb435b5e1a4a4c8bc3e2fbfc1c4bcc0191da1604))

## [1.0.0] — 2026-05-19

### Features

- 3D geofenced attendance with Haversine + altitude delta check
- 4-tier faculty location resolution (Redis override → absence log → master slot → base station)
- Reverse RSVP absence system with line-manager approval workflow
- Real-time WebSocket hub for guest handshakes, absence approvals, and ledger state
- Bulk CSV import — creates/updates users, courses, timetable slots, and registrations atomically
- Nightly ledger generator via APScheduler cron
- Guest Kiosk with zero-login campus visit check-in
- Offline-first PWA with IndexedDB queue, Background Sync, and Web Push reminders
- Admin Onboarding Wizard (5-step: password → cycle → import → ledger → done)
- Anonymous telemetry via CFlair-Counter with admin opt-out toggle
- One-command setup script with auto-detected LAN IP and cryptographic secret generation
- Full CI/CD pipeline: lint, type-check, build, Trivy scan, GHCR publish, automated semver releases
