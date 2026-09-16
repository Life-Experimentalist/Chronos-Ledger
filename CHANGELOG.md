# Changelog

All notable changes to Chronos Ledger are documented here.

This file is automatically maintained by [Release Please](https://github.com/googleapis/release-please).
Human edits between releases will be preserved.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).
Versioning follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [0.12.0](https://github.com/Life-Experimentalist/Chronos-Ledger/compare/v0.11.0...v0.12.0) (2026-09-12)


### ⚠ BREAKING CHANGES

* **api:** PATCH /schedule/ledger/{id} and PATCH /users/{id} now treat an explicit null as clearing the field instead of keeping it, and a null on a field that cannot be empty is a 422 on those two routes and on PATCH /schedule/slots/{id}. A client that sends every field and uses null to mean "no change" has to leave those fields out instead.

### Features

* **guest:** a visitor can follow their check-in with a code ([a6ae897](https://github.com/Life-Experimentalist/Chronos-Ledger/commit/a6ae897854def228bcf1c1ab8cac0139515cdb05))


### Bug Fixes

* **api:** a PATCH could not clear a field once it was set ([cb0e0ad](https://github.com/Life-Experimentalist/Chronos-Ledger/commit/cb0e0ad193b318e5477f2fc94ee585b8b0f98b60))
* **attendance:** an absence request waited forever on a manager who had left ([72421b4](https://github.com/Life-Experimentalist/Chronos-Ledger/commit/72421b4bc89c39caf0f1f829bff2dcf8c5c8d444))
* **deps:** six backend packages had published security advisories ([5fd65f1](https://github.com/Life-Experimentalist/Chronos-Ledger/commit/5fd65f1f98db23259c59dc658ae7b112436b53ec))
* **deps:** the frontend ran on Next.js 14, which had published advisories ([eacb83d](https://github.com/Life-Experimentalist/Chronos-Ledger/commit/eacb83dddeb847461f22395a3902a8a0ec007aa7))
* **ingestion:** a blank cell was imported as the word nan ([a208da3](https://github.com/Life-Experimentalist/Chronos-Ledger/commit/a208da3471c86af736e0a6ed2ccbbace5259889f))
* **schedule:** a class somebody covered still put its lead in the room ([952cb8c](https://github.com/Life-Experimentalist/Chronos-Ledger/commit/952cb8ce356326b6b23a15a1db0db1e4fea897f4))
* **schedule:** somebody on leave read as available between classes ([ab1d464](https://github.com/Life-Experimentalist/Chronos-Ledger/commit/ab1d464322a6a777ea658ecfe94709e6dacfdc46))
* **schedule:** the staff locator failed outright whenever Redis was down ([93bd54b](https://github.com/Life-Experimentalist/Chronos-Ledger/commit/93bd54be9731e94ef27546732858417634c19392))
* **users:** a deactivated account's API keys came back with it ([e42f99a](https://github.com/Life-Experimentalist/Chronos-Ledger/commit/e42f99aba9af6938054325f65a4f702dc03d5d29))

## [0.11.0](https://github.com/Life-Experimentalist/Chronos-Ledger/compare/v0.10.0...v0.11.0) (2026-09-12)


### ⚠ BREAKING CHANGES

* **security:** DB_PASSWORD is required and compose refuses to start without it. A deployment already running on the old default has a postgres volume initialised with that password, and POSTGRES_PASSWORD only applies at initdb, so setting a fresh DB_PASSWORD on its own leaves the backend unable to authenticate. Rotate inside the database first: set DB_PASSWORD to the new value, start the database alone with `docker compose up -d chronos-db`, run `docker compose exec chronos-db psql -U chronos_admin -d chronos_ledger -c "ALTER USER chronos_admin PASSWORD 'the new value'"` (if it asks for a password, it is the old published default), then bring the rest of the stack up. Wiping the volume is the other option and loses the data.

### Features

* **api:** the list routes returned every row with no way to page ([958d0d3](https://github.com/Life-Experimentalist/Chronos-Ledger/commit/958d0d39daf6fd1655ea2633439db5bb6cfda834))
* **resources:** a room could not be registered before a timetable named it ([2200965](https://github.com/Life-Experimentalist/Chronos-Ledger/commit/220096579b8c904a82cca7ca2467571bda057130)), closes [#24](https://github.com/Life-Experimentalist/Chronos-Ledger/issues/24)
* **users:** somebody who left could only be deleted, attendance and all ([282617d](https://github.com/Life-Experimentalist/Chronos-Ledger/commit/282617d14b6da91019d04c2f1936662c22424377))


### Bug Fixes

* **alembic:** running a migration in-process silenced the app's loggers ([9f67b89](https://github.com/Life-Experimentalist/Chronos-Ledger/commit/9f67b8906ac29463b139bc36d1590e45d2bc6938))
* **api:** the published OpenAPI spec had drifted from the app ([8ab23de](https://github.com/Life-Experimentalist/Chronos-Ledger/commit/8ab23de1a5eee384182f7e0e914908f6dda90690))
* **attendance:** a batch wrote to whichever session each record named ([2380bb7](https://github.com/Life-Experimentalist/Chronos-Ledger/commit/2380bb724f3407bffce441039c55e5f3b55f48d4))
* **attendance:** a coarse location fix could pass the fence ([2172374](https://github.com/Life-Experimentalist/Chronos-Ledger/commit/217237447faeeb17ec79336b1ad225d97b3d1f08))
* **auth:** a reused refresh token looked the same as an expired one ([302a345](https://github.com/Life-Experimentalist/Chronos-Ledger/commit/302a34533204a34c5e215803a0b6a52e7bcb5c41))
* **auth:** a service account's key was held at the first-login gate ([ca50ad2](https://github.com/Life-Experimentalist/Chronos-Ledger/commit/ca50ad29c39de6494575d1e0cd47f08f3c9b9fee)), closes [#24](https://github.com/Life-Experimentalist/Chronos-Ledger/issues/24)
* **ci:** the compose file attached to a release was never stamped ([5a22574](https://github.com/Life-Experimentalist/Chronos-Ledger/commit/5a22574688e0d7ba00773070dcb369a55e149102))
* **compose:** the prod stack could not start while the dev stack was running ([32f5147](https://github.com/Life-Experimentalist/Chronos-Ledger/commit/32f5147ed097eacb6c7e464a5ce711b863532994))
* **docker:** the web image reported unhealthy while serving normally ([75df460](https://github.com/Life-Experimentalist/Chronos-Ledger/commit/75df460a6c9601d62936dd9cecf5ae0c30506208))
* **guest:** visitor check-ins were kept forever ([81e5fe1](https://github.com/Life-Experimentalist/Chronos-Ledger/commit/81e5fe1f51f89ab20c859af6da1b98de31c50359))
* **ingestion:** a CSV upload was read whole into memory ([c3b6072](https://github.com/Life-Experimentalist/Chronos-Ledger/commit/c3b60727bac365ce980cc3a5b52185f207ddad38))
* **ingestion:** a missing lead or a reused address failed without a reason ([7245ceb](https://github.com/Life-Experimentalist/Chronos-Ledger/commit/7245ceb228eb5d8d238082c5d19c99253647683e))
* **ledger:** a cycle's slots ran on dates outside the cycle ([8308e52](https://github.com/Life-Experimentalist/Chronos-Ledger/commit/8308e52b20b5ce8f7b2dca03eebfd83dc1a89323))
* **schedule:** a closed cycle kept its rooms and a clone had no slots ([1dd5de4](https://github.com/Life-Experimentalist/Chronos-Ledger/commit/1dd5de4635fd5e593d2be111778d0978d6bd3e11))
* **schedule:** the ledger PATCH wrote whatever its schema carried ([a8be698](https://github.com/Life-Experimentalist/Chronos-Ledger/commit/a8be6989ff91625b852864ac07cd558ad5d7d8ea))
* **security:** a published database password passed the production guard ([33226dc](https://github.com/Life-Experimentalist/Chronos-Ledger/commit/33226dc5e3d1c0c8062ffe688d0e8faea58c16e6))
* **users:** a manager was never checked and a changed email could 500 ([b3a6bc3](https://github.com/Life-Experimentalist/Chronos-Ledger/commit/b3a6bc388070a408d7015b300d2d2725e1846148))
* **web:** the wizard's cycle step read "an planning cycle" ([da09a73](https://github.com/Life-Experimentalist/Chronos-Ledger/commit/da09a7311382f9f1970da28e26d25372658dbdff))
* **ws:** an event reached only the instance that raised it ([86e9d65](https://github.com/Life-Experimentalist/Chronos-Ledger/commit/86e9d65ae08aea57370d82a65361a37aadebafda))


### Performance

* **ingestion:** an import queried the database several times per row ([fe345e7](https://github.com/Life-Experimentalist/Chronos-Ledger/commit/fe345e7b6ea3c7e33441154189e3e67d55e88277))
* **schedule:** the staff locator queried once per person per tier ([1bd9635](https://github.com/Life-Experimentalist/Chronos-Ledger/commit/1bd9635e268092b1a6dd31af9aea966daceebc77))

## [0.10.0](https://github.com/Life-Experimentalist/Chronos-Ledger/compare/v0.9.0...v0.10.0) (2026-09-10)


### ⚠ BREAKING CHANGES

* **vocabulary:** the staff locator returns `OFF_SITE` where it returned `OFF_CAMPUS` and `UNKNOWN` where it returned `ISOLATED_CELL`, and its `status` strings are reworded. `assigned_base_station` no longer defaults to "Staff Room Main" at any layer, so a user created without it now holds null and resolves to "Unassigned".
* **vocabulary:** ORG_PROFILE is removed. It is ignored rather than rejected, so a stale line in an environment file does nothing. GET /api/v1/config no longer returns org_profile; the response is {labels, password_min_length}. A client that branched on the profile string must read labels instead.
* **websocket:** websocket clients must send an AUTH frame instead of a ?token= query parameter, and GET /ws/stats now requires SUPER_ADMIN.

### Features

* **auth:** a password floor, set per deployment rather than assumed ([a318515](https://github.com/Life-Experimentalist/Chronos-Ledger/commit/a3185157620d8c92f75d4de6d8c2240fa23e13f0))
* **auth:** an API key was everything, forever, and undocumented ([e32d312](https://github.com/Life-Experimentalist/Chronos-Ledger/commit/e32d312286d69d67a958ec9356119c72a66cde0f))
* **ci:** publish to Docker Hub too, with signed build provenance ([4035c19](https://github.com/Life-Experimentalist/Chronos-Ledger/commit/4035c196c779f973aad93e72d444ddad2acbf412))
* **deploy:** three things stopped another stack from running this image ([e9ad56b](https://github.com/Life-Experimentalist/Chronos-Ledger/commit/e9ad56b3d17b72f6d56df48288f6b03e8496ad61))
* **ingestion:** an import said nothing about what the file left out ([12a1932](https://github.com/Life-Experimentalist/Chronos-Ledger/commit/12a19321c0bc635d67ac329a88275c5cbba088a6))
* **ledger:** a room could hold two generated days at the same hour ([165985f](https://github.com/Life-Experimentalist/Chronos-Ledger/commit/165985f2b000269d9943834a64ca95d0647d61f8))
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
* **users:** an admin can reset a password nobody knows any more ([8fdd265](https://github.com/Life-Experimentalist/Chronos-Ledger/commit/8fdd2656da23d30c71631a35d1677a75048818e1))
* **vocabulary:** a preset was the only way to name anything ([92737fa](https://github.com/Life-Experimentalist/Chronos-Ledger/commit/92737fa2ed3dc2d78159b2a418ce6259b4484ba2))
* **vocabulary:** the engine shipped the word "Course", and it should not ([60b4581](https://github.com/Life-Experimentalist/Chronos-Ledger/commit/60b4581438badd14697fbe2053aec59103efb6d4))


### Bug Fixes

* **admin:** a failed clipboard copy said nothing at all ([29db0f0](https://github.com/Life-Experimentalist/Chronos-Ledger/commit/29db0f059e3cf35d269a6072fbaf94e4921ebbd5))
* **attendance:** /mark had no authorization for non-members ([b6fd38e](https://github.com/Life-Experimentalist/Chronos-Ledger/commit/b6fd38ea7f12abf024488d17a909bbdf30e1081f))
* **attendance:** a device with no altitude can mark attendance again ([d2e4c76](https://github.com/Life-Experimentalist/Chronos-Ledger/commit/d2e4c7639dbb0eb6678647cc3a727e9f5b557a3d))
* **attendance:** a reversed leave approval left the day stuck on ON_LEAVE ([52e2fce](https://github.com/Life-Experimentalist/Chronos-Ledger/commit/52e2fce7e0ab285b78c2c7321f905ec83bc779f4))
* **attendance:** anyone signed in could read who attended every session ([5ee5d65](https://github.com/Life-Experimentalist/Chronos-Ledger/commit/5ee5d65d81acbdcc2e3b1979c777713f06b125d0))
* **auth:** a password change signed out the browser that made it ([bc7079e](https://github.com/Life-Experimentalist/Chronos-Ledger/commit/bc7079ec69b33c7e04c70286b0d95e49beef1f1e))
* **auth:** the super-admin password was published in this repository ([41d70a7](https://github.com/Life-Experimentalist/Chronos-Ledger/commit/41d70a7d3148e418a128d44ad43ba6382ebac0fc))
* **ci:** release-please proposed 1.0.0 because it never read the manifest ([c87292f](https://github.com/Life-Experimentalist/Chronos-Ledger/commit/c87292ffcb185670dd8974f246aced271b24e103))
* **ci:** the release bump reformatted the whole OpenAPI contract ([3b64007](https://github.com/Life-Experimentalist/Chronos-Ledger/commit/3b6400778a1cfe6cc825af450d2fccd4b383b608))
* **config:** a production instance published its own API surface at /docs ([4c030f5](https://github.com/Life-Experimentalist/Chronos-Ledger/commit/4c030f564b49d9ca9d25e5eb40dfdb0fd0d2c290))
* **config:** production refuses to boot on the secrets this repo publishes ([5ba830c](https://github.com/Life-Experimentalist/Chronos-Ledger/commit/5ba830c05a30b52e2e5c56d3e9938893440b2c75))
* **deploy:** a registry refuses a capital, and this owner has three ([4f71f90](https://github.com/Life-Experimentalist/Chronos-Ledger/commit/4f71f908ddda73590e144c18e81815ebc3e15b44))
* **docs:** openapi.yaml has never been parseable ([bc98b04](https://github.com/Life-Experimentalist/Chronos-Ledger/commit/bc98b04293d82f4ffc9b6a0fc5caa3c2d2f76094))
* **geofence:** the Wi-Fi fallback in the copy does not exist ([c80ea92](https://github.com/Life-Experimentalist/Chronos-Ledger/commit/c80ea9282d4248977d6664ca97198cc0376fbe02))
* **guest:** the visitor kiosk endpoints were open to the whole internet ([14a02a4](https://github.com/Life-Experimentalist/Chronos-Ledger/commit/14a02a41f597f518749ed9c6ba4068dcdf6bd06a))
* **ingestion:** a CSV could put a class on a day already generated ([56b8a75](https://github.com/Life-Experimentalist/Chronos-Ledger/commit/56b8a75378a110aeaa50ed9333a7ba2e3dbdb988))
* **ingestion:** a failed import handed back the SQL statement ([8ee9ddd](https://github.com/Life-Experimentalist/Chronos-Ledger/commit/8ee9dddedeee4a7d9b3ac5e4d77ea03026546be7))
* **ingestion:** a timetable was write-once, so a re-uploaded correction did nothing ([557d06b](https://github.com/Life-Experimentalist/Chronos-Ledger/commit/557d06b56d03d356ae4116e6ab4ace00be06ffca))
* **ingestion:** every imported member got the same password, and it is public ([e31ec42](https://github.com/Life-Experimentalist/Chronos-Ledger/commit/e31ec422776e864fcb6a96c65d8c6e6eb4cb47d9))
* **ledger:** a day that had already happened forgot what time it happened at ([a7493b7](https://github.com/Life-Experimentalist/Chronos-Ledger/commit/a7493b7fd0b8d7fd187751b57adfd1f8a676c988))
* **reservations:** two callers could both book the same room at once ([af286ad](https://github.com/Life-Experimentalist/Chronos-Ledger/commit/af286ad1241a9bf4f06e9d41e4a4791091e1462a))
* **resources:** a hold could be cancelled by somebody who did not take it ([f0650ec](https://github.com/Life-Experimentalist/Chronos-Ledger/commit/f0650ecd0491230c6cfd34d7d2f81e5acd7f0d02))
* **resources:** a room with a generated day on it read as free ([403e33d](https://github.com/Life-Experimentalist/Chronos-Ledger/commit/403e33de3ea167b2375ac84a1ac03f4a758ec896))
* **schedule:** changing a slot's lead was refused by a hold sitting on it ([cd89141](https://github.com/Life-Experimentalist/Chronos-Ledger/commit/cd8914151c891ec70cbcce8f39e0d14923adf0b4))
* **setup:** the last line of a successful install pointed at a 404 ([84f12be](https://github.com/Life-Experimentalist/Chronos-Ledger/commit/84f12bec38fcef2c998a0aea476b418562e0cf60))
* **sync:** an activity title could write its own event into a calendar ([28c63dd](https://github.com/Life-Experimentalist/Chronos-Ledger/commit/28c63dd358af2bae6d12302549f37e774338ca09))
* **sync:** the calendar feed sent times with no timezone on them ([debd627](https://github.com/Life-Experimentalist/Chronos-Ledger/commit/debd627f9e2b56be203ed6848699346858d45d8b))
* **telemetry:** the switch was on whenever nobody had touched it ([870e9c7](https://github.com/Life-Experimentalist/Chronos-Ledger/commit/870e9c71ab7111a9a182bd4258b54639bb9a94f1))
* **time:** the server asked the container what day it was ([494863e](https://github.com/Life-Experimentalist/Chronos-Ledger/commit/494863e7e52c1883f390758e9a1e7d8e8ecec4de))
* **vocabulary:** the locator answered in campus words ([1ec0c49](https://github.com/Life-Experimentalist/Chronos-Ledger/commit/1ec0c49aa39a980ff8c673a2a6231b40666ab8f4))
* **web:** a 422 detail list rendered as [object Object] ([86425af](https://github.com/Life-Experimentalist/Chronos-Ledger/commit/86425affc2db3aa8dca6629fc5e078287ef65ae2))
* **websocket:** the token was in the URL, and nothing checked the account ([76e1e6f](https://github.com/Life-Experimentalist/Chronos-Ledger/commit/76e1e6f510e24e5e306209ea2300d8104f2c1f6a))


### Dependencies

* **frontend:** npm audit found a critical and eight highs, none of them noticed ([9f54494](https://github.com/Life-Experimentalist/Chronos-Ledger/commit/9f544942315a570cb30a4dbe443cc2ca64b1cf32))

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
