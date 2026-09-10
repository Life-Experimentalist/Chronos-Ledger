# Changelog

All notable changes to Chronos Ledger are documented here.

This file is automatically maintained by [Release Please](https://github.com/googleapis/release-please).
Human edits between releases will be preserved.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).
Versioning follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## 1.0.0 (2026-09-10)


### ⚠ BREAKING CHANGES

* **vocabulary:** the staff locator returns `OFF_SITE` where it returned `OFF_CAMPUS` and `UNKNOWN` where it returned `ISOLATED_CELL`, and its `status` strings are reworded. `assigned_base_station` no longer defaults to "Staff Room Main" at any layer, so a user created without it now holds null and resolves to "Unassigned".
* **vocabulary:** ORG_PROFILE is removed. It is ignored rather than rejected, so a stale line in an environment file does nothing. GET /api/v1/config no longer returns org_profile; the response is {labels, password_min_length}. A client that branched on the profile string must read labels instead.
* **websocket:** websocket clients must send an AUTH frame instead of a ?token= query parameter, and GET /ws/stats now requires SUPER_ADMIN.
* **api:** CSV import headers are now member_id, member_name, member_email, activity_code, activity_title, unit, day_of_week_index, time_window_start, time_window_end, lead_id, room.

### Features

* add GitHub Pages deployment workflow for landing page ([2c3317d](https://github.com/Life-Experimentalist/Chronos-Ledger/commit/2c3317d9af0912c684bedbb331ba3bda147a59e9))
* **api:** rename the campus vocabulary to neutral organization terms ([2de35c3](https://github.com/Life-Experimentalist/Chronos-Ledger/commit/2de35c3c010e8792b78f8162899c9582b1524137))
* **auth:** a password floor, set per deployment rather than assumed ([a318515](https://github.com/Life-Experimentalist/Chronos-Ledger/commit/a3185157620d8c92f75d4de6d8c2240fa23e13f0))
* **auth:** a stolen token dies in minutes, and a session can be revoked ([f649179](https://github.com/Life-Experimentalist/Chronos-Ledger/commit/f649179b6f20d71947dfa6ebe9cd22075e3781d0))
* **auth:** an API key was everything, forever, and undocumented ([e32d312](https://github.com/Life-Experimentalist/Chronos-Ledger/commit/e32d312286d69d67a958ec9356119c72a66cde0f))
* **ci:** publish to Docker Hub too, with signed build provenance ([4035c19](https://github.com/Life-Experimentalist/Chronos-Ledger/commit/4035c196c779f973aad93e72d444ddad2acbf412))
* **deploy:** three things stopped another stack from running this image ([e9ad56b](https://github.com/Life-Experimentalist/Chronos-Ledger/commit/e9ad56b3d17b72f6d56df48288f6b03e8496ad61))
* **dx:** setup.sh --demo seeds a showable day, and docs/demo.md walks it ([00159e6](https://github.com/Life-Experimentalist/Chronos-Ledger/commit/00159e6ef61739c6e78d1a3bcea80b3b899dda2d))
* **edge:** the proxy turns on HTTPS by itself when certificates appear ([4df7e02](https://github.com/Life-Experimentalist/Chronos-Ledger/commit/4df7e023be320c6abd8bbbd33c2b9d29bffd82e4))
* enforce the first-login password change server-side for admins ([af11b8c](https://github.com/Life-Experimentalist/Chronos-Ledger/commit/af11b8cc69da4caa98c047ce87c697e20e0e4f7c))
* **ingestion:** an import said nothing about what the file left out ([12a1932](https://github.com/Life-Experimentalist/Chronos-Ledger/commit/12a19321c0bc635d67ac329a88275c5cbba088a6))
* initial release of Chronos Ledger v1.0.0 ([99effd7](https://github.com/Life-Experimentalist/Chronos-Ledger/commit/99effd72baa3958a0f059467083d840dd62393b4))
* **int-01:** a machine can hold a key, and the key is just a user ([4540f8d](https://github.com/Life-Experimentalist/Chronos-Ledger/commit/4540f8d1742017025ab93df7b32beb2ae0e093dc))
* **ledger:** a room could hold two generated days at the same hour ([165985f](https://github.com/Life-Experimentalist/Chronos-Ledger/commit/165985f2b000269d9943834a64ca95d0647d61f8))
* **pwa:** neutral routes and profile-driven vocabulary in the UI ([5500cb9](https://github.com/Life-Experimentalist/Chronos-Ledger/commit/5500cb908d9dc1dc2198422a8e98b72f417b2350))
* **reservations:** a booking may run past midnight ([8509e98](https://github.com/Life-Experimentalist/Chronos-Ledger/commit/8509e98038a0c14c4ee46dcea01defdc63690d90))
* **resources:** a room was a string, so nothing could hold what a room is ([9306248](https://github.com/Life-Experimentalist/Chronos-Ledger/commit/9306248b1a1c85291893a3bd90ec97a100484c22))
* **resources:** an outside system can hold a room, and be refused one ([9f07b7d](https://github.com/Life-Experimentalist/Chronos-Ledger/commit/9f07b7da8a21df213948f3eefcab6d6300b0b4e9))
* **resources:** nothing could ask when a room was free, or say where it is ([88e7fac](https://github.com/Life-Experimentalist/Chronos-Ledger/commit/88e7fac587aed9c258562596af92538a205411d1))
* **schedule:** a class could be put on top of a room somebody had booked ([53d7de1](https://github.com/Life-Experimentalist/Chronos-Ledger/commit/53d7de1322c5468462f49a505200d5529fab842b))
* **schedule:** a class on the timetable may run past midnight ([c5710c1](https://github.com/Life-Experimentalist/Chronos-Ledger/commit/c5710c17f2ab0ccefe5c4f20cb226aba6f74afaf))
* **schedule:** a cycle drafted closed could never be put into service ([c918615](https://github.com/Life-Experimentalist/Chronos-Ledger/commit/c918615ffa9b8177346c67786b3b6f74158a8927))
* **schedule:** a slot could be created but never changed or removed ([9eefbdc](https://github.com/Life-Experimentalist/Chronos-Ledger/commit/9eefbdc4b3be807ee5c778e96332a7679a4fb64a))
* **schedule:** one room could hold two classes at the same hour ([6b1c5a8](https://github.com/Life-Experimentalist/Chronos-Ledger/commit/6b1c5a80e1f282018b9b548cc2c66e372cd87430))
* **security:** a password could be guessed at whatever speed the network allowed ([da801a9](https://github.com/Life-Experimentalist/Chronos-Ledger/commit/da801a9f3ba10cdad19bb0a7e6eaabc216225794))
* standalone GitHub Pages landing page (pure HTML, dark/light mode, Dark Reader aware) ([ef78751](https://github.com/Life-Experimentalist/Chronos-Ledger/commit/ef78751b8dd4a4372f92ada54934e7f2a2385713))
* use real logo and icon assets throughout (nav, sidebar, kiosk, login, landing, GH Pages) ([48d350b](https://github.com/Life-Experimentalist/Chronos-Ledger/commit/48d350b98c74ee8339aa093b33f6ee47f745adb9))
* **users:** an admin can reset a password nobody knows any more ([8fdd265](https://github.com/Life-Experimentalist/Chronos-Ledger/commit/8fdd2656da23d30c71631a35d1677a75048818e1))
* **vocabulary:** a preset was the only way to name anything ([92737fa](https://github.com/Life-Experimentalist/Chronos-Ledger/commit/92737fa2ed3dc2d78159b2a418ce6259b4484ba2))
* **vocabulary:** the engine shipped the word "Course", and it should not ([60b4581](https://github.com/Life-Experimentalist/Chronos-Ledger/commit/60b4581438badd14697fbe2053aec59103efb6d4))


### Bug Fixes

* a department admin's reach stops at their own department ([3a26597](https://github.com/Life-Experimentalist/Chronos-Ledger/commit/3a26597ddb3e79a1e7a1103e0e0ea891e0af3396))
* a geo-fenced session no longer accepts a check-in that omits coordinates ([3c3e173](https://github.com/Life-Experimentalist/Chronos-Ledger/commit/3c3e173e8c18ba8e9aa829ac865bb3bd6544592d))
* **admin:** a failed clipboard copy said nothing at all ([29db0f0](https://github.com/Life-Experimentalist/Chronos-Ledger/commit/29db0f059e3cf35d269a6072fbaf94e4921ebbd5))
* **api:** a time window that runs backwards is refused at the door ([9a09ad0](https://github.com/Life-Experimentalist/Chronos-Ledger/commit/9a09ad0d232f8fbf5ff69d76d9ec46755f8ecd3d))
* **attendance:** /mark had no authorization for non-members ([b6fd38e](https://github.com/Life-Experimentalist/Chronos-Ledger/commit/b6fd38ea7f12abf024488d17a909bbdf30e1081f))
* **attendance:** a device with no altitude can mark attendance again ([d2e4c76](https://github.com/Life-Experimentalist/Chronos-Ledger/commit/d2e4c7639dbb0eb6678647cc3a727e9f5b557a3d))
* **attendance:** a reversed leave approval left the day stuck on ON_LEAVE ([52e2fce](https://github.com/Life-Experimentalist/Chronos-Ledger/commit/52e2fce7e0ab285b78c2c7321f905ec83bc779f4))
* **attendance:** anyone signed in could read who attended every session ([5ee5d65](https://github.com/Life-Experimentalist/Chronos-Ledger/commit/5ee5d65d81acbdcc2e3b1979c777713f06b125d0))
* **auth:** a password change signed out the browser that made it ([bc7079e](https://github.com/Life-Experimentalist/Chronos-Ledger/commit/bc7079ec69b33c7e04c70286b0d95e49beef1f1e))
* **auth:** the super-admin password was published in this repository ([41d70a7](https://github.com/Life-Experimentalist/Chronos-Ledger/commit/41d70a7d3148e418a128d44ad43ba6382ebac0fc))
* backend uv install and frontend TypeScript type error ([154c353](https://github.com/Life-Experimentalist/Chronos-Ledger/commit/154c353a2be6ef11587672375124d67b1b3b1b01))
* calendar feed URLs stop being guessable from user ids ([3ecabaa](https://github.com/Life-Experimentalist/Chronos-Ledger/commit/3ecabaa46f2b9b683e1b53374af576afef0f423c))
* **config:** a production instance published its own API surface at /docs ([4c030f5](https://github.com/Life-Experimentalist/Chronos-Ledger/commit/4c030f564b49d9ca9d25e5eb40dfdb0fd0d2c290))
* **config:** production refuses to boot on the secrets this repo publishes ([5ba830c](https://github.com/Life-Experimentalist/Chronos-Ledger/commit/5ba830c05a30b52e2e5c56d3e9938893440b2c75))
* declare email-validator, which EmailStr imports at startup ([c487aba](https://github.com/Life-Experimentalist/Chronos-Ledger/commit/c487aba396dc714ce721da2b2bee70770d113a70))
* declare VALUE=DATE on all-day calendar events per RFC 5545 ([393a6f1](https://github.com/Life-Experimentalist/Chronos-Ledger/commit/393a6f1813216ce2e6a20512588f7be19aa67693))
* **deploy:** a registry refuses a capital, and this owner has three ([4f71f90](https://github.com/Life-Experimentalist/Chronos-Ledger/commit/4f71f908ddda73590e144c18e81815ebc3e15b44))
* **deploy:** the container boots offline, on the venv it was built with ([636ddc2](https://github.com/Life-Experimentalist/Chronos-Ledger/commit/636ddc2e12249d358681e12c0e0a5227f28bab44))
* **docs:** openapi.yaml has never been parseable ([bc98b04](https://github.com/Life-Experimentalist/Chronos-Ledger/commit/bc98b04293d82f4ffc9b6a0fc5caa3c2d2f76094))
* **dx:** the demo command survives the Windows laptop it was written for ([fc5ccca](https://github.com/Life-Experimentalist/Chronos-Ledger/commit/fc5ccca1c66892bcfc5cbb6b2de88c4abec1d53a))
* **geofence:** the Wi-Fi fallback in the copy does not exist ([c80ea92](https://github.com/Life-Experimentalist/Chronos-Ledger/commit/c80ea9282d4248977d6664ca97198cc0376fbe02))
* **guest:** the visitor kiosk endpoints were open to the whole internet ([14a02a4](https://github.com/Life-Experimentalist/Chronos-Ledger/commit/14a02a41f597f518749ed9c6ba4068dcdf6bd06a))
* **ingestion:** a CSV could put a class on a day already generated ([56b8a75](https://github.com/Life-Experimentalist/Chronos-Ledger/commit/56b8a75378a110aeaa50ed9333a7ba2e3dbdb988))
* **ingestion:** a failed import handed back the SQL statement ([8ee9ddd](https://github.com/Life-Experimentalist/Chronos-Ledger/commit/8ee9dddedeee4a7d9b3ac5e4d77ea03026546be7))
* **ingestion:** a shared class is one master slot, not one per student ([f43adca](https://github.com/Life-Experimentalist/Chronos-Ledger/commit/f43adca181e5f2bc39db4ee98b40f478a21bff73))
* **ingestion:** a timetable was write-once, so a re-uploaded correction did nothing ([557d06b](https://github.com/Life-Experimentalist/Chronos-Ledger/commit/557d06b56d03d356ae4116e6ab4ace00be06ffca))
* **ingestion:** every imported member got the same password, and it is public ([e31ec42](https://github.com/Life-Experimentalist/Chronos-Ledger/commit/e31ec422776e864fcb6a96c65d8c6e6eb4cb47d9))
* **ledger:** a day that had already happened forgot what time it happened at ([a7493b7](https://github.com/Life-Experimentalist/Chronos-Ledger/commit/a7493b7fd0b8d7fd187751b57adfd1f8a676c988))
* **lint:** resolve remaining 9 ruff errors (UP042, SIM102, E712) ([4c3c24a](https://github.com/Life-Experimentalist/Chronos-Ledger/commit/4c3c24aff9091e3359bda371c3d6badd3c736fbb))
* make a clean docker compose up actually boot ([a62fca5](https://github.com/Life-Experimentalist/Chronos-Ledger/commit/a62fca545d8bd453116fbb472b1a6860ae3cb0fc))
* make realtime reachable through the deployed proxy ([3a4f81f](https://github.com/Life-Experimentalist/Chronos-Ledger/commit/3a4f81f28b7643c0a6c37112e5239882b9b31b83))
* make the baked-in relative /ws path work in every browser ([b28e8f9](https://github.com/Life-Experimentalist/Chronos-Ledger/commit/b28e8f9ddd9f99e3b489e2789efff3f51d7c4650))
* only a super-admin can create admin accounts ([8efdd81](https://github.com/Life-Experimentalist/Chronos-Ledger/commit/8efdd8120da1a28b848575e3bb420d3740248dfe))
* only a super-admin can modify admin accounts ([6730620](https://github.com/Life-Experimentalist/Chronos-Ledger/commit/67306209e118e20e35e01a4f59f671abeb2aedf1))
* **pwa:** offline attendance queue drains in every browser ([0eb2ca2](https://github.com/Life-Experimentalist/Chronos-Ledger/commit/0eb2ca2d277a1b8ac1ced27c0e3482db4c04a78f))
* **reservations:** two callers could both book the same room at once ([af286ad](https://github.com/Life-Experimentalist/Chronos-Ledger/commit/af286ad1241a9bf4f06e9d41e4a4791091e1462a))
* resolve all CI failures ([a82eeed](https://github.com/Life-Experimentalist/Chronos-Ledger/commit/a82eeed141e98f5809a2147130ad7cde47cb6c51))
* resolve three CI blockers on fresh repo ([c46dda2](https://github.com/Life-Experimentalist/Chronos-Ledger/commit/c46dda264a13514700175baa7e20d53abd809500))
* **resources:** a hold could be cancelled by somebody who did not take it ([f0650ec](https://github.com/Life-Experimentalist/Chronos-Ledger/commit/f0650ecd0491230c6cfd34d7d2f81e5acd7f0d02))
* **resources:** a room with a generated day on it read as free ([403e33d](https://github.com/Life-Experimentalist/Chronos-Ledger/commit/403e33de3ea167b2375ac84a1ac03f4a758ec896))
* **schedule:** changing a slot's lead was refused by a hold sitting on it ([cd89141](https://github.com/Life-Experimentalist/Chronos-Ledger/commit/cd8914151c891ec70cbcce8f39e0d14923adf0b4))
* **setup:** the last line of a successful install pointed at a 404 ([84f12be](https://github.com/Life-Experimentalist/Chronos-Ledger/commit/84f12bec38fcef2c998a0aea476b418562e0cf60))
* **sync:** an activity title could write its own event into a calendar ([28c63dd](https://github.com/Life-Experimentalist/Chronos-Ledger/commit/28c63dd358af2bae6d12302549f37e774338ca09))
* **sync:** the calendar feed sent times with no timezone on them ([debd627](https://github.com/Life-Experimentalist/Chronos-Ledger/commit/debd627f9e2b56be203ed6848699346858d45d8b))
* **telemetry:** the switch was on whenever nobody had touched it ([870e9c7](https://github.com/Life-Experimentalist/Chronos-Ledger/commit/870e9c71ab7111a9a182bd4258b54639bb9a94f1))
* **time:** the server asked the container what day it was ([494863e](https://github.com/Life-Experimentalist/Chronos-Ledger/commit/494863e7e52c1883f390758e9a1e7d8e8ecec4de))
* untrack uv.lock from gitignore and remove hardcoded default password from setup output ([13a9cfc](https://github.com/Life-Experimentalist/Chronos-Ledger/commit/13a9cfce11796ee00fa8a23426660a73e6648404))
* update telemetry endpoint URLs to new domain ([bb435b5](https://github.com/Life-Experimentalist/Chronos-Ledger/commit/bb435b5e1a4a4c8bc3e2fbfc1c4bcc0191da1604))
* **vocabulary:** the locator answered in campus words ([1ec0c49](https://github.com/Life-Experimentalist/Chronos-Ledger/commit/1ec0c49aa39a980ff8c673a2a6231b40666ab8f4))
* **web:** a 422 detail list rendered as [object Object] ([86425af](https://github.com/Life-Experimentalist/Chronos-Ledger/commit/86425affc2db3aa8dca6629fc5e078287ef65ae2))
* **websocket:** the token was in the URL, and nothing checked the account ([76e1e6f](https://github.com/Life-Experimentalist/Chronos-Ledger/commit/76e1e6f510e24e5e306209ea2300d8104f2c1f6a))

## [0.9.0], 2026-09-09

The repository declared 1.0.0 in three places and never released it: no tag, no
release, nothing depending on the number. It is reset to 0.9.0. The code works
and is worth running, and the API is about to move (RRULE replacing
`day_of_week_index`, rooms becoming a foreign key), which is what 0.x is for.
1.0.0 is earned when the API stops moving.

### Features

- Geofenced attendance: Haversine radius, plus a 4 m floor check when both the
  device and the room report an altitude
- 4-tier staff location resolution (Redis override, absence log, master slot,
  base station)
- Reverse RSVP absence system with line-manager approval workflow
- Real-time WebSocket hub for guest handshakes, absence approvals, and ledger state
- Bulk CSV import creating users, activities, timetable slots and registrations
  in one transaction
- Nightly ledger generator via APScheduler cron
- Guest kiosk with zero-login visitor check-in
- Offline-first PWA with IndexedDB queue, Background Sync, and Web Push reminders
- Admin onboarding wizard (password, cycle, import, ledger, done)
- Anonymous telemetry via CFlair-Counter with admin opt-out toggle
- One-command setup script with auto-detected LAN IP and cryptographic secret
  generation
- CI/CD pipeline: lint, type-check, build, Trivy scan, GHCR publish, automated
  semver releases
