# Changelog

All notable changes to Chronos Ledger are documented here.

This file is automatically maintained by [Release Please](https://github.com/googleapis/release-please).
Human edits between releases will be preserved.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).
Versioning follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

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
