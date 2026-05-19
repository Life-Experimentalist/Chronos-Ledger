<div align="center">
  <img src="assets/logo.svg" alt="Chronos Ledger" width="320" height="80" />
  <br/><br/>

  **Campus Schedule & Attendance Management — self-hosted, offline-first, production-ready.**

  <br/>

  [![CI](https://github.com/Life-Experimentalist/chronos-ledger/actions/workflows/ci.yml/badge.svg)](https://github.com/Life-Experimentalist/chronos-ledger/actions/workflows/ci.yml)
  [![Release](https://github.com/Life-Experimentalist/chronos-ledger/actions/workflows/release.yml/badge.svg)](https://github.com/Life-Experimentalist/chronos-ledger/actions/workflows/release.yml)
  [![License](https://img.shields.io/badge/License-Apache_2.0-14b8a6.svg)](LICENSE)
  [![Docker — Backend](https://ghcr-badge.egpl.dev/Life-Experimentalist/chronos-ledger-backend/size?label=backend)](https://github.com/Life-Experimentalist/chronos-ledger/pkgs/container/chronos-ledger-backend)
  [![Docker — Web](https://ghcr-badge.egpl.dev/Life-Experimentalist/chronos-ledger-web/size?label=web)](https://github.com/Life-Experimentalist/chronos-ledger/pkgs/container/chronos-ledger-web)
  [![PRs Welcome](https://img.shields.io/badge/PRs-welcome-10b981.svg)](https://github.com/Life-Experimentalist/chronos-ledger/pulls)
  [![Views](https://cflair-counter.pages.dev/api/views/chronos-ledger-landing/badge)](https://github.com/Life-Experimentalist/chronos-ledger)

</div>

---

## The Problem

Universities and colleges track attendance on paper, manage timetables in Excel, and learn of faculty absences only when students complain. Campus networks are unreliable. Faculty don't know where their colleagues are. Visitors have no formal check-in system.

**Chronos Ledger** solves all of this in a single, self-hosted, Docker-deployable stack that runs entirely on your campus intranet — no cloud subscription, no data leaving your network.

---

## Key Metrics

| Metric | Value |
|---|---|
| REST API endpoints | 30+ |
| Role-specific dashboards | 4 |
| Database tables | 9 |
| Offline capability | 100% (read + queue writes) |
| Setup time | < 5 minutes |
| Runtime dependencies | Docker + Docker Compose only |
| License | Apache 2.0 |

---

## Quick Start — One Command

```bash
# Clone, configure, and launch everything
git clone https://github.com/Life-Experimentalist/chronos-ledger.git
cd chronos-ledger
chmod +x setup.sh && ./setup.sh
```

`setup.sh` auto-detects your LAN IP, generates cryptographic secrets, and launches all services. When it finishes:

- **App** → `http://<your-server-ip>`
- **API docs** → `http://<your-server-ip>/docs`
- **Default login** → `admin@college.internal` / `ChronosAdmin2026!` *(change immediately)*

### Or pull from GHCR (no build required)

```bash
curl -fsSL https://raw.githubusercontent.com/Life-Experimentalist/chronos-ledger/main/docker-compose.prod.yml \
  -o docker-compose.prod.yml

export JWT_SECRET_SIGNING_KEY=$(openssl rand -hex 32)
export DB_PASSWORD=$(openssl rand -base64 24 | tr -d '/+=' | head -c 32)
export GHCR_OWNER=Life-Experimentalist

docker compose -f docker-compose.prod.yml up -d
```

Pin any release: `VERSION=v1.2.0 docker compose -f docker-compose.prod.yml up -d`

---

## Architecture

```
  Clients (PWA)                 Campus Server
  ┌─────────────┐              ┌────────────────────────────────────────┐
  │ Student     │              │  Docker network: chronos_net           │
  │ Faculty     │──HTTPS/WSS──▶│  ┌──────────┐     ┌────────────────┐  │
  │ Admin       │              │  │  Nginx   │────▶│  FastAPI       │  │
  │ Guest Kiosk │              │  │  :80/443 │     │  :8000         │  │
  └─────────────┘              │  └──────────┘     └───────┬────────┘  │
                               │       │                   │           │
                               │  Static files         ┌───┴──────┐    │
                               │  (Next.js export)     │PostgreSQL│    │
                               │                       │ Redis    │    │
                               └───────────────────────┴──────────┴────┘
```

Full diagrams with Mermaid charts: [`docs/architecture.md`](docs/architecture.md)

---

## Feature Highlights

### 3D Geofenced Attendance
Students mark attendance via GPS. The server runs a Haversine distance check **plus** an altitude delta (`|Δalt| < 4m`) to prevent students on floors above or below from registering. When GPS accuracy exceeds 30m, the client flags a BSSID Wi-Fi fallback.

### 4-Tier Faculty Location Resolution
Always know where faculty are — in priority order:
1. **Redis manual override** (e.g., "In meeting — back at 15:00")
2. **Approved absence** from the daily exception log
3. **Active master slot** room from the live timetable
4. **Base station fallback** (their configured office/staffroom)

### Reverse RSVP Absence System
Presence is the default state. Faculty *file* absences rather than *confirming* presence. Requests route to the line manager for approval. Approved absences cascade `ON_LEAVE` to every affected ledger entry and fire a WebSocket notification to the faculty member.

### Offline-First PWA
Campus Wi-Fi drops. Chronos Ledger keeps working:
- Attendance marks queue to IndexedDB → Background Sync flushes on reconnect
- Today's schedule cached locally for 12 hours
- Class reminders fire 15 minutes before start — even with the app closed — via `periodicsync` in the service worker

### Real-Time WebSocket Hub
JWT-authenticated persistent connections. Guest handshake requests, absence approvals, and ledger state changes arrive in milliseconds — no polling.

### CSV Bulk Import
Drop a student-centric CSV on the Admin dashboard. One upload creates/updates users, course offerings, master timetable slots, and student registrations atomically and idempotently.

---

## Role Dashboards

| Role | Path | Core capabilities |
|---|---|---|
| **Super Admin** | `/admin/dashboard` | CSV import, cycle management, proxy assignment, user provisioning |
| **Dept Admin** | `/admin/dashboard` | Absence approvals, ledger overrides for own department |
| **Faculty** | `/faculty/dashboard` | Availability switcher, attendance matrix, absence requests, guest desk |
| **Student** | `/student/dashboard` | Live timeline, geofenced self-mark, faculty locator, offline queue |
| **Guest** | `/guest/kiosk` | No login — check-in form, real-time faculty notification |

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python 3.11 · FastAPI 0.115 · SQLAlchemy 2 · Alembic · APScheduler |
| Auth | PyJWT 2.10 · bcrypt 4.2 (no CVE-affected packages) |
| Database | PostgreSQL 17 |
| Cache / PubSub | Redis 7.4 |
| Frontend | Next.js 14 App Router · TypeScript · Tailwind CSS |
| State | Zustand · React Hook Form · Zod |
| PWA | @ducanh2912/next-pwa (Workbox) · IndexedDB (idb) · Web Push (VAPID) |
| Reverse proxy | Nginx 1.27 |
| Packaging | uv (Python) · npm (Node.js) |
| Container | Docker 24 · Docker Compose 2.20 |
| CI/CD | GitHub Actions · GHCR |
| Releases | Release Please (semver, CHANGELOG) |

---

## Project Structure

```
chronos-ledger/
├── .github/
│   ├── workflows/
│   │   ├── ci.yml          # Lint, type-check, build, Trivy scan
│   │   ├── cd.yml          # Build & push to GHCR (main + releases)
│   │   └── release.yml     # Release Please automated semver releases
│   └── dependabot.yml      # Automated dep updates (pip, npm, Docker, Actions)
├── assets/
│   ├── logo.svg            # Vector wordmark
│   ├── Logo.png            # Raster logo
│   └── Icon.png            # App icon
├── backend/                # FastAPI application (uv managed)
│   ├── pyproject.toml
│   ├── alembic/            # DB migrations
│   └── app/
│       ├── core/           # Config, DB, security, Redis, WebSocket manager
│       ├── models/         # SQLAlchemy ORM (9 tables)
│       ├── schemas/        # Pydantic request/response models
│       ├── api/v1/         # Route handlers per domain
│       ├── services/       # Business logic (geo-fence, RSVP, ingestion)
│       └── cron/           # Nightly ledger generator (APScheduler)
├── frontend/               # Next.js 14 PWA (npm managed)
│   ├── public/
│   │   ├── manifest.webmanifest
│   │   └── sw-custom.js    # Background sync + push + periodicsync
│   └── src/
│       ├── app/            # App Router pages per role
│       ├── components/     # Role-scoped UI components
│       ├── hooks/          # useWebSocket, useGeolocation, useAuth, useScheduleNotifications
│       ├── lib/            # Axios API client, IndexedDB helpers, auth utils
│       └── store/          # Zustand: auth + notifications
├── nginx/
│   ├── nginx.conf          # Reverse proxy + static serving + security headers
│   └── Dockerfile          # Multi-stage: Next.js build → nginx image (for GHCR)
├── docs/
│   ├── openapi.yaml        # Static OpenAPI 3.1 contract (all 30+ endpoints)
│   ├── architecture.md     # Mermaid system diagrams
│   ├── data-model.md       # Mermaid ERD (all 9 tables)
│   ├── flows.md            # Sequence diagrams (attendance, RSVP, guest, cron)
│   ├── api.md              # Human-readable API reference with examples
│   └── deployment.md       # Deployment guide with topology diagram
├── bin/
│   ├── chronos_intranet_autodiscover.sh
│   └── chronos_maintenance_vault.sh
├── docker-compose.yml      # Local dev / self-build (builds from source)
├── docker-compose.prod.yml # Production (pulls from GHCR, no build)
├── setup.sh                # One-command setup script
├── .env.example            # Environment template
└── version.txt             # Source of truth for semver (managed by Release Please)
```

---

## Local Development

### Backend

```bash
cd backend
uv sync                         # install deps (including dev)
uv run alembic upgrade head     # apply migrations
uv run uvicorn app.main:app --reload --port 8000
```

API: `http://localhost:8000` · Swagger: `http://localhost:8000/docs`

### Frontend

```bash
cd frontend
npm install
NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1 \
NEXT_PUBLIC_WS_URL=ws://localhost:8000/ws \
npm run dev
```

App: `http://localhost:3000`

---

## CI/CD Pipeline

```
Pull Request ──▶ ci.yml ──▶ ruff + mypy
                       ├──▶ eslint + tsc + build
                       ├──▶ Trivy security scan
                       └──▶ Docker build check (no push)

Push to main ──▶ ci.yml (all above)
             └──▶ cd.yml ──▶ Build backend + web images
                         └──▶ Push to GHCR (sha tag + latest)

Merge release PR ──▶ release.yml ──▶ GitHub Release created
                                 ├──▶ CHANGELOG.md updated
                                 ├──▶ version.txt bumped
                                 └──▶ cd.yml (version tag) ──▶ GHCR vX.Y.Z
```

GHCR images:
- `ghcr.io/Life-Experimentalist/chronos-ledger-backend:latest`
- `ghcr.io/Life-Experimentalist/chronos-ledger-web:latest`

---

## Environment Reference

| Variable | Required | Description |
|---|---|---|
| `JWT_SECRET_SIGNING_KEY` | **yes** | 64-char hex — `openssl rand -hex 32` |
| `DB_PASSWORD` | **yes** | PostgreSQL password |
| `VAPID_PUBLIC_KEY` | recommended | Web Push — `npx web-push generate-vapid-keys` |
| `VAPID_PRIVATE_KEY` | recommended | Web Push |
| `VAPID_CONTACT_EMAIL` | recommended | Admin contact for push service |
| `NEXT_PUBLIC_API_URL` | dev only | Baked in at build time; defaults to `/api/v1` in GHCR image |
| `NEXT_PUBLIC_WS_URL` | dev only | Defaults to `/ws` in GHCR image |
| `APP_CORS_ORIGINS` | prod | Comma-separated allowed origins |
| `GHCR_OWNER` | prod only | GitHub org/username for GHCR image pull |
| `VERSION` | prod only | Image tag to deploy (default: `latest`) |

See [`.env.example`](.env.example) for the full template.

---

## Default Credentials (First Boot)

The Alembic seed migration creates one super-admin:

| Field | Value |
|---|---|
| Email | `admin@college.internal` |
| Password | `ChronosAdmin2026!` |

**Change this password immediately** via Admin Portal → Profile → Change Password.

---

## Documentation

| Document | Description |
|---|---|
| [`docs/openapi.yaml`](docs/openapi.yaml) | OpenAPI 3.1 contract — all endpoints, schemas, enums |
| [`docs/architecture.md`](docs/architecture.md) | System topology, module deps, location resolution, WebSocket lifecycle |
| [`docs/data-model.md`](docs/data-model.md) | ERD for all 9 database tables |
| [`docs/flows.md`](docs/flows.md) | Sequence diagrams: attendance, RSVP, guest handshake, ledger cron |
| [`docs/api.md`](docs/api.md) | Human-readable API reference with examples |
| [`docs/deployment.md`](docs/deployment.md) | Deployment guide, cycle rollover, TLS, scaling |
| [`docs/faq.md`](docs/faq.md) | FAQ & troubleshooting — setup, auth, CSV import, geofencing, CI/CD |
| [`CONTRIBUTING.md`](CONTRIBUTING.md) | Development setup, commit conventions, PR checklist |
| [`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md) | Community standards and enforcement |
| [`SECURITY.md`](SECURITY.md) | Vulnerability reporting and disclosure policy |
| [`CHANGELOG.md`](CHANGELOG.md) | Release history (managed by Release Please) |

---

## Telemetry

Chronos Ledger collects **anonymous, aggregate view counts** via [CFlair-Counter](https://github.com/Life-Experimentalist/CFlair-Counter) — a privacy-first, self-hostable analytics service. No IP addresses, usernames, or session data are ever collected or transmitted.

### What is tracked

| Event | Project key |
|---|---|
| Landing page visits | `chronos-ledger-landing` |
| Admin dashboard logins | `chronos-ledger-app` |

### Opt out

**Admin-level (runtime):** Go to Admin Dashboard → Overview → Privacy & Telemetry and toggle off "Anonymous usage analytics". The preference is stored locally and persists across sessions.

**Build-time (permanent):** Set `NEXT_PUBLIC_TELEMETRY_ENABLED=false` in your environment before building. This removes all telemetry code paths at compile time.

**Self-host CFlair-Counter:** Deploy your own instance and point `NEXT_PUBLIC_TELEMETRY_ENDPOINT` at it.

---

## Contributing

Contributions are welcome. Please:

1. Fork the repo and create a feature branch.
2. Follow [Conventional Commits](https://www.conventionalcommits.org/) so Release Please can generate the changelog.
3. Open a PR — CI runs automatically (lint, type-check, build, Trivy scan).
4. All checks must pass before merge.

Commit examples:
```
feat: add department-level attendance export to CSV
fix: resolve geofence false positive on altitude boundary
perf: cache faculty location resolver result in Redis
security: upgrade cryptography to 44.0.1
```

---

## License

Copyright 2026 Chronos Ledger Contributors

Licensed under the [Apache License, Version 2.0](LICENSE).
