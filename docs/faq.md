# FAQ & Troubleshooting

Answers to the most common questions and error scenarios for Chronos Ledger.

---

## Table of Contents

- [Setup & First Boot](#setup--first-boot)
- [Authentication & Accounts](#authentication--accounts)
- [Onboarding Wizard](#onboarding-wizard)
- [CSV Import & Timetable](#csv-import--timetable)
- [Attendance & Geofencing](#attendance--geofencing)
- [Absences & Proxy](#absences--proxy)
- [Guest Kiosk](#guest-kiosk)
- [Notifications & Web Push](#notifications--web-push)
- [WebSocket / Live Updates](#websocket--live-updates)
- [Docker & Deployment](#docker--deployment)
- [CI/CD & GHCR](#cicd--ghcr)
- [New Academic Year Rollover](#new-academic-year-rollover)
- [Data & Privacy](#data--privacy)

---

## Setup & First Boot

### `setup.sh` exits immediately with no output

Make sure the script is executable and you are running it with bash, not sh:

```bash
chmod +x setup.sh
bash setup.sh
```

On some distributions `sh` is `dash`, which does not support the `local` keyword used in the script.

---

### The app loads but the API returns 502 Bad Gateway

The backend container is still starting. Wait 10–15 seconds and refresh. You can watch readiness:

```bash
docker compose logs -f backend
```

The backend prints `Application startup complete.` when it is ready. If it never prints this, check for a database connection error (see below).

---

### Backend logs: `could not connect to server: Connection refused`

PostgreSQL is not ready yet, or the `DATABASE_URL` is misconfigured.

1. Verify the postgres container is running: `docker compose ps`
2. Check `.env` — `DB_PASSWORD` must match the password embedded in `DATABASE_URL` (or use the flat variable substitution in `docker-compose.yml`).
3. If postgres crashed, inspect its logs: `docker compose logs db`

The most common cause is a password mismatch. Run `docker compose down -v` to wipe volumes, fix `.env`, and run `docker compose up` again.

---

### Alembic migration fails with `relation already exists`

You are running migrations against a database that already has tables from a previous partial run. Options:

```bash
# Wipe the database and start clean (dev only)
docker compose down -v
docker compose up

# Or stamp the current state and skip the failed migration
cd backend
uv run alembic stamp head
```

---

### `openssl` is not found when running setup.sh on Windows

`setup.sh` is designed for Linux/macOS. On Windows, use WSL2:

```powershell
wsl bash setup.sh
```

Or manually generate secrets and copy them into `.env`:

```powershell
# PowerShell equivalent
[System.Web.Security.Membership]::GeneratePassword(64,0)
```

---

### The app is accessible on localhost but not from other campus devices

The `NEXT_PUBLIC_API_URL` was built with `http://localhost` instead of the server's LAN IP.

`setup.sh` auto-detects the LAN IP. If it detected incorrectly, rebuild with the correct IP:

```bash
NEXT_PUBLIC_API_URL=http://192.168.1.10/api/v1 \
NEXT_PUBLIC_WS_URL=ws://192.168.1.10/ws \
docker compose up --build
```

Also ensure `APP_CORS_ORIGINS` in `.env` includes `http://192.168.1.10`.

---

## Authentication & Accounts

### Default credentials

| Field | Value |
|---|---|
| Email | `admin@college.internal` |
| Password | `ChronosAdmin2026!` |

**Change this immediately** — the admin is prompted to do so on first login via the Onboarding Wizard.

---

### Login fails with "Invalid credentials" after setup.sh

The seed migration creates the admin account during `alembic upgrade head`. If migrations did not run (check `docker compose logs backend`), the account does not exist.

Force migrations:

```bash
docker compose exec backend uv run alembic upgrade head
```

---

### A user is locked out and cannot reset their password

Super Admins can reset any user's password via the Admin dashboard. If the Super Admin account itself is locked, reset directly in the database:

```bash
docker compose exec db psql -U chronos_admin -d chronos_ledger -c \
  "UPDATE users SET hashed_password = crypt('NewTempPassword!', gen_salt('bf')) WHERE email = 'admin@college.internal';"
```

Requires the `pgcrypto` extension, which is enabled by the seed migration.

---

### JWT token expired errors after a system clock change

Chronos Ledger uses HS256 JWTs with 8-hour expiry. If the server clock jumped forward, existing tokens become invalid immediately. Users must log in again.

To change the expiry window, set `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` in `.env`.

---

### "Initial setup required" banner keeps appearing after onboarding

The banner is driven by `initial_login_state` on the user record. If the Onboarding Wizard password step did not complete successfully, this flag was not cleared.

Fix: complete the password step in the Onboarding Wizard (Admin Dashboard → Setup Guide), or clear it directly:

```bash
docker compose exec db psql -U chronos_admin -d chronos_ledger -c \
  "UPDATE users SET initial_login_state = false WHERE email = 'admin@college.internal';"
```

---

## Onboarding Wizard

### When does the Onboarding Wizard appear?

Automatically on first login when `initial_login_state` is `true` for a `SUPER_ADMIN` or `DEPT_ADMIN` account. It can also be reopened at any time from Admin Dashboard → **Setup Guide** button (top-right of the tab bar).

---

### Which steps are required?

| Step | Required | Can skip? |
|---|---|---|
| 1. Change password | Yes | No |
| 2. Create academic cycle | Yes | No |
| 3. Import CSV | Yes | No |
| 4. Generate ledger | Recommended | Yes |
| 5. Done | — | — |

---

### CSV import succeeded but the timetable looks empty

The ledger is not generated automatically after import. Go to **Step 4 — Generate Ledger** in the wizard (or Admin Dashboard → Import → Generate Daily Ledger). The nightly cron runs at midnight, but you can trigger it manually from the UI.

---

### I need to re-run the wizard for a new academic year

Use the **Setup Guide** link from the Admin Dashboard. On Step 2, create a new academic cycle (leave the old one — historical data is preserved under the previous cycle). Then re-upload the new semester's CSV.

The new cycle becomes active immediately for ledger generation.

---

## CSV Import & Timetable

### What columns does the CSV need?

The ingestion engine expects a student-centric format with these exact column names:

| Column | Example |
|---|---|
| `student_id` | `STU20210001` |
| `student_name` | `Alice Sharma` |
| `student_email` | `alice@college.internal` |
| `subject_code` | `CS301` |
| `subject_title` | `Operating Systems` |
| `department` | `CSE` |
| `day_of_week_index` | `1` (1 = Monday ... 7 = Sunday) |
| `time_window_start` | `09:00` |
| `time_window_end` | `10:00` |
| `teacher_id` | `FAC001` |
| `room` | `LH-3` |

Column names are case-sensitive. Extra columns are ignored. Times accept `HH:MM` or `HH:MM:SS` (24-hour).

---

### Import returns "duplicate key" errors

The import is idempotent — re-running it with the same data is safe. "Duplicate key" errors suggest the CSV has internal duplicates (the same student+course+slot appears twice). Remove duplicates and re-upload.

---

### Import failed with a 422 error

The import is all-or-nothing: any bad row rolls back the whole upload, and the response `detail` field (POST `/api/v1/ingestion/upload-csv`) explains the failure. Common causes:

- `Missing columns: {...}`: the CSV header lacks one of the required columns listed above
- `Cannot parse time value ...`: a time is not `HH:MM` or `HH:MM:SS` 24-hour format
- a database constraint error: usually `day_of_week_index` outside 1 to 7, or the same student+course+slot appearing twice

Fix the offending rows and re-upload; re-running a corrected file is safe.

---

## Attendance & Geofencing

### Students cannot mark attendance — "Location unavailable"

The browser geolocation API requires HTTPS or localhost. If the app is served over plain HTTP, the location prompt will be blocked by the browser.

Options:
1. **Recommended:** Set up TLS on nginx (see [`docs/deployment.md`](deployment.md#tls)).
2. **Testing only:** In Chrome, go to `chrome://flags/#unsafely-treat-insecure-origin-as-secure` and add your server IP.

---

### Attendance is being rejected with "Outside geofence"

The server-side check uses the room's configured lat/lon plus a 30-metre radius. If the room coordinates in the database are wrong, every mark attempt will fail.

Update room coordinates:

```bash
docker compose exec db psql -U chronos_admin -d chronos_ledger -c \
  "UPDATE master_slots SET room_lat = 12.9716, room_lon = 77.5946 WHERE target_room_identifier = 'LH-3';"
```

---

### The altitude check is blocking students on the correct floor

The altitude delta threshold is `|Δalt| < 4 metres`. GPS altitude accuracy is typically ±10–20m on mobile devices, making this check unreliable outdoors. The check only fires when the device reports altitude — if the device does not expose it, the check is skipped.

If you want to widen the threshold, it is a constant in `backend/app/services/geo_fence.py`:

```python
ALT_DELTA_THRESHOLD_M = 4.0   # change to 10.0 for looser enforcement
```

---

### Attendance marks are queuing offline but never syncing

The app drains the queue itself whenever it is open with the network up: reopening or reloading the dashboard while online flushes every pending mark. That path works in every browser, including Safari and Firefox, which have no Background Sync.

If the app is closed, Chromium browsers also flush via the service worker's Background Sync, which fires when the browser decides to, usually within a few seconds of going online. If that is not firing:

1. Make sure the PWA is installed (added to home screen), not just open in a tab.
2. Check `chrome://serviceworker-internals` to confirm the SW is registered and active.
3. Force a sync in DevTools: Application → Service Workers → Sync → push the `attendance-sync` tag.

A mark the server rejects outright (for example an expired login token) is dropped from the queue rather than retried forever; mark it again after signing back in.

---

## Absences & Proxy

### Faculty submitted an absence but the line manager never got notified

WebSocket notifications are only delivered to connected clients. The line manager must have the app open. If they are offline, the absence request will still appear in their pending queue when they next log in.

For email notifications, the current release does not include an email transport. This is a planned enhancement.

---

### Proxy assignment is not reflected on the student timeline

The student timeline reads from the live ledger. After approving a proxy, trigger a ledger refresh: Admin Dashboard → Import → Generate Daily Ledger (or wait for the midnight cron).

---

### An absence was approved but the faculty member's ledger still shows SCHEDULED

The ledger is a materialized daily snapshot. Approved absences cascade `ON_LEAVE` only when the ledger is regenerated. Use the manual Generate button in the Admin Dashboard.

---

## Guest Kiosk

### The guest form submits but the faculty member never gets the notification

The faculty member must be online with the app open. The notification arrives via WebSocket to `/faculty/dashboard`. If they are offline, the request stays pending in the database and will appear when they next log in.

Check that the faculty member's email in the guest form exactly matches their account email — the lookup is case-insensitive but the email must exist in the system.

---

### Guest check-in kiosk is accessible without a login — is this intentional?

Yes. The guest kiosk (`/guest/kiosk`) is explicitly public. It does not expose any internal data — it only allows submitting a visit request and viewing the faculty notification status. The underlying API endpoints (`/api/v1/guest/*`) are similarly unauthenticated by design.

---

## Notifications & Web Push

### Push notifications are not appearing

1. Confirm the user has granted notification permission (browser prompt when first logging in).
2. Verify VAPID keys are set in `.env` — `VAPID_PUBLIC_KEY`, `VAPID_PRIVATE_KEY`, and `VAPID_CONTACT_EMAIL`.
3. Check that the frontend was built with the matching `NEXT_PUBLIC_VAPID_PUBLIC_KEY`.
4. VAPID public key must be the same value in both places. Regenerate with `npx web-push generate-vapid-keys` if unsure, then rebuild.

---

### Class reminder push fires too early or too late

Reminders fire 15 minutes before the slot's `time_window_start` via `periodicsync` in the service worker. The accuracy depends on when the browser chooses to fire the periodic sync — browsers enforce a minimum interval of ~1 hour for battery reasons.

For more reliable reminders, the user must keep the tab open (the service worker runs JavaScript timers when the tab is active).

---

## WebSocket / Live Updates

### The live indicator shows "Offline" even though the server is running

The WebSocket connects to `NEXT_PUBLIC_WS_URL`. In the GHCR image this defaults to `/ws` (same-origin). If you are running the frontend dev server and the backend separately, ensure `NEXT_PUBLIC_WS_URL=ws://localhost:8000/ws`.

Also check nginx is proxying `/ws` correctly — see `nginx/nginx.conf`.

---

### WebSocket disconnects every few minutes

Nginx has a default proxy read timeout of 60 seconds. The Chronos Ledger nginx config sets `proxy_read_timeout 3600s` on the `/ws` location. If you see 60-second drops, nginx.conf may not have been updated — verify:

```bash
docker compose exec nginx cat /etc/nginx/nginx.conf | grep proxy_read_timeout
```

---

## Docker & Deployment

### `docker compose up` fails with "port is already allocated"

Another service on the host is using port 80. Either stop it (`sudo systemctl stop apache2` / `nginx`) or change the host port in `docker-compose.yml`:

```yaml
ports:
  - "8080:80"   # map host 8080 → container 80
```

---

### Container exits with OOM (out of memory) on low-RAM servers

Redis is configured with `--maxmemory 256mb`. PostgreSQL can spike higher during bulk import. Minimum recommended RAM: **1 GB free** after OS. On 512 MB machines, reduce Redis:

```yaml
command: redis-server --maxmemory 64mb --maxmemory-policy allkeys-lru
```

---

### How do I back up the database?

```bash
docker compose exec db pg_dump -U chronos_admin chronos_ledger \
  | gzip > chronos-backup-$(date +%Y%m%d).sql.gz
```

To restore:

```bash
gunzip -c chronos-backup-20260519.sql.gz \
  | docker compose exec -T db psql -U chronos_admin chronos_ledger
```

---

### How do I update to a new release?

```bash
# Pull the latest docker-compose.prod.yml from the release assets, or:
export VERSION=v1.2.0
docker compose -f docker-compose.prod.yml pull
docker compose -f docker-compose.prod.yml up -d
```

Chronos Ledger images are built with SBOM and provenance attestation — verify with:

```bash
docker buildx imagetools inspect ghcr.io/Life-Experimentalist/chronos-ledger-backend:v1.2.0
```

---

### Trivy reports a HIGH CVE in the production image

Check if the CVE affects Chronos Ledger's actual usage (many CVEs in base images are in code paths that are never executed). If it does:

1. Open an issue on GitHub with the CVE ID.
2. If it's in the base image (`node:20-alpine`, `python:3.11-slim`, or `nginx:1.27-alpine`), we will update the `FROM` line once the upstream image is patched.
3. If it's in a dependency, update via `uv add <package>@<fixed-version>` or `npm install <package>@<fixed-version>`.

---

## CI/CD & GHCR

### CI fails with "Process completed with exit code 1" on the frontend build

Check the `NEXT_PUBLIC_*` environment variables in the CI step. The build requires them to be set (even to empty strings) to avoid `undefined` being baked into the JS bundle.

The CI workflow sets:
```yaml
NEXT_PUBLIC_API_URL: /api/v1
NEXT_PUBLIC_WS_URL: /ws
NEXT_PUBLIC_VAPID_PUBLIC_KEY: ""
NEXT_PUBLIC_TELEMETRY_ENABLED: "false"
NEXT_PUBLIC_TELEMETRY_ENDPOINT: ""
```

If you have added new `NEXT_PUBLIC_` variables, add them to the CI `env:` block.

---

### GHCR push fails with "denied: installation not allowed to Write organization package"

The `GITHUB_TOKEN` needs `packages: write` permission. This is declared in `cd.yml`:

```yaml
permissions:
  contents: read
  packages: write
```

If it still fails, check that the repository is in the `Life-Experimentalist` organization (not a personal fork). Personal forks cannot push to org packages.

---

### Release Please is not creating a release PR

Likely causes:
1. Commits are not following [Conventional Commits](https://www.conventionalcommits.org/) — only `feat:`, `fix:`, `perf:`, and `security:` prefixes create release PRs.
2. `release-please-config.json` or `.release-please-manifest.json` is missing or malformed.
3. The `GITHUB_TOKEN` permissions do not include `pull-requests: write`.

Check `release.yml` — it declares `permissions: { contents: write, pull-requests: write, packages: write }`.

---

## New Academic Year Rollover

### How do I start a new academic year / semester?

1. Open the Onboarding Wizard: Admin Dashboard → **Setup Guide**
2. Skip to **Step 2 — Create Cycle**. Fill in the new semester's start and end dates.
3. Move to **Step 3 — Import CSV**. Upload the new semester's timetable CSV.
4. Click **Generate Ledger** to populate the first day's entries.

The old cycle is preserved in full — historical attendance records and ledger snapshots remain untouched. The new cycle is set as active.

---

### Can I have multiple cycles active simultaneously?

No. The system maintains one active cycle at a time. Switching cycles makes the new one active for ledger generation; historical data remains queryable under the old cycle's ID.

---

### How do I add a new department mid-year?

1. Prepare a CSV with only the new department's data.
2. Import it via Admin Dashboard → Import Data → CSV Import Zone.
3. The import is idempotent — existing records are not duplicated; new ones are created.
4. Regenerate the ledger to include the new slots in today's schedule.

---

## Data & Privacy

### What data does Chronos Ledger store?

All data stays on your campus server. A default install sends nothing to any external service:

- **Telemetry (opt-in, off by default):** Anonymous view counts sent to a [CFlair-Counter](https://github.com/Life-Experimentalist/CFlair-Counter) instance you point it at. No PII. Requires both `NEXT_PUBLIC_TELEMETRY_ENABLED=true` and a non-empty `NEXT_PUBLIC_TELEMETRY_ENDPOINT` at build time.
- **Web Push:** Push payloads are routed through the browser vendor's push service (Google FCM for Chrome, Mozilla for Firefox). Payload content is a short status string — no student names or sensitive data.

---

### How do I fully disable telemetry?

It is already off unless you turned it on: the shipped defaults are `NEXT_PUBLIC_TELEMETRY_ENABLED=false` with an empty `NEXT_PUBLIC_TELEMETRY_ENDPOINT`, and either of those alone is enough to suppress every ping.

If you enabled it and want it back off:

**Build-time (permanent, applies to all users):** set in your `.env` before building:
```
NEXT_PUBLIC_TELEMETRY_ENABLED=false
```
Then rebuild the frontend image. This removes all telemetry code paths at compile time.

**Runtime (per-browser):** Admin Dashboard → Overview → Privacy & Telemetry → toggle off. Stored in `localStorage`, persists across sessions for that browser.

---

### GDPR / data retention

Chronos Ledger is designed for on-premises deployment — the deploying institution is the data controller. There is no built-in automated retention or purge schedule. Administrators are responsible for implementing any required retention policies directly on the PostgreSQL database.
