# Changelog

All notable changes to Chronos Ledger are documented here.

This file is automatically maintained by [Release Please](https://github.com/googleapis/release-please).
Human edits between releases will be preserved.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).
Versioning follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [1.0.0], 2026-05-19

### Features

- 3D geofenced attendance with Haversine + altitude delta check
- 4-tier faculty location resolution (Redis override → absence log → master slot → base station)
- Reverse RSVP absence system with line-manager approval workflow
- Real-time WebSocket hub for guest handshakes, absence approvals, and ledger state
- Bulk CSV import, creates/updates users, courses, timetable slots, and registrations atomically
- Nightly ledger generator via APScheduler cron
- Guest Kiosk with zero-login campus visit check-in
- Offline-first PWA with IndexedDB queue, Background Sync, and Web Push reminders
- Admin Onboarding Wizard (5-step: password → cycle → import → ledger → done)
- Anonymous telemetry via CFlair-Counter with admin opt-out toggle
- One-command setup script with auto-detected LAN IP and cryptographic secret generation
- Full CI/CD pipeline: lint, type-check, build, Trivy scan, GHCR publish, automated semver releases
