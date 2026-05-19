# Contributing to Chronos Ledger

Thank you for taking the time to contribute. This document covers the development workflow, commit conventions, and quality expectations.

---

## Code of Conduct

Be respectful. Treat other contributors the way you would want to be treated. Issues or PRs with harassment will be closed.

---

## Before You Start

- Check [open issues](https://github.com/Life-Experimentalist/chronos-ledger/issues) to avoid duplicate work.
- For significant changes, open an issue first to align on scope before writing code.
- Security vulnerabilities: **do not open a public issue.** See [SECURITY.md](SECURITY.md).

---

## Development Setup

### Requirements

- Docker 24+ and Docker Compose 2.20+
- Python 3.11+ and [uv](https://github.com/astral-sh/uv)
- Node.js 20+ and npm

### Backend

```bash
cd backend
uv sync --dev                       # install all deps including dev tools
uv run alembic upgrade head         # apply migrations
uv run uvicorn app.main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1 \
NEXT_PUBLIC_WS_URL=ws://localhost:8000/ws \
npm run dev
```

### Full stack (Docker)

```bash
cp .env.example .env   # fill in secrets
docker compose up --build
```

---

## Commit Message Convention

Chronos Ledger uses [Conventional Commits](https://www.conventionalcommits.org/). Release Please reads these to determine version bumps and generate CHANGELOG entries.

| Prefix | Effect | Example |
|---|---|---|
| `feat:` | Bumps MINOR | `feat: add department CSV export` |
| `fix:` | Bumps PATCH | `fix: geofence false positive on altitude boundary` |
| `feat!:` or `BREAKING CHANGE:` | Bumps MAJOR | `feat!: remove v0 API compatibility shim` |
| `perf:` | Bumps PATCH | `perf: cache location resolver result in Redis` |
| `security:` | Bumps PATCH | `security: upgrade cryptography to 44.0.1` |
| `docs:`, `chore:`, `refactor:`, `test:` | No bump | No release PR update |

Commit messages should complete the sentence: *"If applied, this commit will…"*

```
feat: add student attendance export to CSV

Adds a new GET /schedule/attendance/export endpoint that streams a
gzip-compressed CSV of all attendance records for the current cycle.
Only accessible by SUPER_ADMIN and DEPT_ADMIN.
```

---

## Pull Request Checklist

Before opening a PR, verify all of the following locally:

**Backend**
```bash
cd backend
uv run ruff format .          # auto-format (run this first)
uv run ruff check .           # zero lint errors
uv run alembic check          # no pending migrations
```

**Frontend**
```bash
cd frontend
npm run lint                  # zero ESLint errors
npm run type-check            # zero TypeScript errors
npm run build                 # successful production build
```

CI runs the same checks automatically. PRs cannot merge until all jobs are green.

---

## Project Layout

```
backend/app/
  core/           Config, DB, Redis, WebSocket manager, security
  models/         SQLAlchemy ORM models (db.py — all 9 tables)
  schemas/        Pydantic request/response models per domain
  api/v1/         Route handlers (one file per domain)
  services/       Business logic — geo_fence, reverse_rsvp, location_resolver, ingestion_engine
  cron/           APScheduler jobs — ledger_generator

frontend/src/
  app/            Next.js App Router pages (admin, faculty, student, guest, landing)
  components/     UI split by role (admin/, faculty/, student/, shared/, ui/)
  hooks/          useAuth, useWebSocket, useGeolocation, useScheduleNotifications
  lib/            API client (axios), IndexedDB helpers, auth utils, telemetry
  store/          Zustand: auth + notifications
```

---

## Database Migrations

Always create a migration for any model change:

```bash
cd backend
uv run alembic revision --autogenerate -m "describe the change"
uv run alembic upgrade head
```

Review the generated file in `backend/alembic/versions/` before committing. Autogenerate is not perfect — check for missing `server_default`, wrong `nullable`, or dropped-index regressions.

---

## API Changes

All endpoint changes must be reflected in `docs/openapi.yaml`. The OpenAPI contract is the source of truth for the API surface — keep it in sync with the route handlers and Pydantic schemas.

---

## Releasing

Releases are fully automated. Merging the Release Please PR:

1. Creates a GitHub Release tagged `vX.Y.Z`
2. Updates `CHANGELOG.md` and `version.txt`
3. Triggers CD to build and push `chronos-ledger-backend:vX.Y.Z` and `chronos-ledger-web:vX.Y.Z` to GHCR
4. Attaches a versioned `docker-compose.prod.yml` to the release

You do not need to manually tag, push, or bump versions.

---

## License

By contributing, you agree your changes will be licensed under the [Apache License 2.0](LICENSE).
