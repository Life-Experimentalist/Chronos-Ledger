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
- [CI/CD & container registries](#cicd--container-registries)
- [New Cycle Rollover](#new-cycle-rollover)
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
docker compose logs -f chronos-app
```

The backend prints `Application startup complete.` when it is ready. If it never prints this, check for a database connection error (see below).

---

### Backend logs: `could not connect to server: Connection refused`

PostgreSQL is not ready yet, or the `DATABASE_URL` is misconfigured.

1. Verify the postgres container is running: `docker compose ps`
2. Check `.env`: `DB_PASSWORD` must match the password embedded in `DATABASE_URL` (or use the flat variable substitution in `docker-compose.yml`).
3. If postgres crashed, inspect its logs: `docker compose logs chronos-db`

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

### The app is accessible on localhost but not from other organization devices

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

### First login credentials

| Field | Value |
|---|---|
| Email | `admin@org.internal` |
| Password | `INITIAL_ADMIN_PASSWORD` from your `.env` |

`setup.sh` generates that password and prints it once, in its summary. Nothing can log in as the administrator until the variable is set, and the admin is prompted to choose their own password on first login via the Onboarding Wizard.

---

### Login fails with "Invalid credentials" after setup.sh

Usually `INITIAL_ADMIN_PASSWORD` is empty or missing from `.env`. The seed migration stores a hash of a random string it throws away, so the administrator is deliberately unreachable until that variable gives it a password, and `docker compose logs chronos-app` says `INITIAL_ADMIN_PASSWORD is not set` on boot. Set it and restart:

```bash
docker compose up -d --force-recreate chronos-app
```

Otherwise the account may not exist at all. The seed migration creates it during `alembic upgrade head`; if migrations did not run (check `docker compose logs chronos-app`), there is nothing to log into.

Force migrations:

```bash
docker compose exec chronos-app uv run --no-sync alembic upgrade head
```

---

### A user is locked out and cannot reset their password

Super Admins can reset any user's password via the Admin dashboard. If the Super Admin account itself is locked, reset directly in the database. It takes two steps, because the stored hash is bcrypt written by the application: Postgres has no function that produces one this app will accept.

First generate the hash inside the backend container:

```bash
docker compose exec chronos-app uv run --no-sync python -c \
  "from app.core.security import hash_password; print(hash_password('NewTempPassword!'))"
```

Then open psql and write it, setting the first-login flag so the temporary password has to be replaced at the next login:

```bash
docker compose exec chronos-db psql -U chronos_admin -d chronos_ledger
```

```sql
UPDATE users
   SET credential_secure_hash = '<paste the hash>',
       initial_login_state = true
 WHERE email_address = 'admin@org.internal';
```

Run the UPDATE at the psql prompt rather than through `psql -c` from your shell. A bcrypt hash contains `$` characters and a shell will eat them.

While `initial_login_state` is true, a Super Admin token is refused everywhere except the password-change endpoints, so the temporary password cannot be used for anything else.

---

### JWT token expired errors after a system clock change

Chronos Ledger uses HS256 access tokens with a 15-minute expiry, refreshed against a 30-day refresh token. If the server clock jumped forward, existing access tokens become invalid immediately. The web client refreshes on its own; anything holding a token directly has to call `POST /api/v1/auth/refresh` or log in again.

To change the windows, set `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` and `JWT_REFRESH_TOKEN_EXPIRE_DAYS` in `.env`.

---

### "Initial setup required" banner keeps appearing after onboarding

The banner is driven by `initial_login_state` on the user record. If the Onboarding Wizard password step did not complete successfully, this flag was not cleared.

Fix: complete the password step in the Onboarding Wizard (Admin Dashboard → Setup Guide), or clear it directly:

```bash
docker compose exec chronos-db psql -U chronos_admin -d chronos_ledger -c \
  "UPDATE users SET initial_login_state = false WHERE email_address = 'admin@org.internal';"
```

---

## Onboarding Wizard

### When does the Onboarding Wizard appear?

Automatically on first login when `initial_login_state` is `true` for a `SUPER_ADMIN` or `UNIT_ADMIN` account. It can also be reopened at any time from Admin Dashboard → **Setup Guide** button (top-right of the tab bar).

---

### Which steps are required?

| Step | Required | Can skip? |
|---|---|---|
| 1. Change password | Yes | No |
| 2. Create planning cycle | Yes | No |
| 3. Import CSV | Yes | No |
| 4. Generate ledger | Recommended | Yes |
| 5. Done | - | - |

---

### CSV import succeeded but the timetable looks empty

The ledger is not generated automatically after import. Go to **Step 4: Generate Ledger** in the wizard (or Admin Dashboard → Import → Generate Daily Ledger). The nightly job only writes the next day, at 23:00 in `ORG_TIMEZONE`, but you can trigger it manually from the UI.

---

### I need to re-run the wizard for a new planning cycle

Use the **Setup Guide** link from the Admin Dashboard. On Step 2, create a new planning cycle (leave the old one, historical data is preserved under the previous cycle). Then re-upload the new term's CSV.

The wizard creates the new cycle open, and the old one stays open alongside it until you close it with `PATCH /schedule/cycles/{id}/close` once its last day has run.

---

## CSV Import & Timetable

### What columns does the CSV need?

The ingestion engine expects a member-centric format with these exact column names:

| Column | Example |
|---|---|
| `member_id` | `STU20210001` |
| `member_name` | `Alice Sharma` |
| `member_email` | `alice@org.internal` |
| `activity_code` | `CS301` |
| `activity_title` | `Operating Systems` |
| `unit` | `CSE` |
| `day_of_week_index` | `1` (1 = Monday ... 7 = Sunday) |
| `time_window_start` | `09:00` |
| `time_window_end` | `10:00` |
| `lead_id` | `FAC001` |
| `room` | `LH-3` |

Column names are case-sensitive. Extra columns are ignored. Times accept `HH:MM` or `HH:MM:SS` (24-hour).

---

### Can I upload the same file twice?

Yes. An import matches what already exists and reuses it: a slot is matched on activity, weekday and start time, and a row repeated in the file is taken once. Where a matched slot's end time, lead or room has changed, the slot is corrected and the days already generated follow it. A changed start time cannot be matched, so it arrives as a second slot and the old one is listed in `not_in_file`. That list is a report only; an import never deletes anything. The CSV import section of [`docs/api.md`](api.md) covers what to do with it.

---

### Import failed with a 422 error

The import is all-or-nothing: any bad row rolls back the whole upload, and the response `detail` field (POST `/api/v1/ingestion/upload-csv`) explains the failure. Common causes:

- `Missing columns: {...}`: the CSV header lacks one of the required columns listed above
- `Cannot parse time value ...`: a time is not `HH:MM` or `HH:MM:SS` 24-hour format
- `email ... already belongs to ...`: the row gives a member an address another account already has
- `lead '...' does not exist`: `lead_id` names nobody; the lead needs an account before a file can name them
- `... is deactivated`: the row names a member or lead who has been deactivated; reactivate them or change the file
- a message naming a room: the row puts a class in a room something else holds at that hour
- `the import failed and nothing was saved`: the database refused a row, for example a `day_of_week_index` outside 1 to 7, and the server log has the reason

Fix the offending rows and re-upload; re-running a corrected file is safe.

---

## Attendance & Geofencing

### Members cannot mark attendance: "Location unavailable"

The browser geolocation API requires HTTPS or localhost. If the app is served over plain HTTP, the location prompt will be blocked by the browser.

Options:
1. **Recommended:** Set up TLS on nginx (see [`docs/deployment.md`](deployment.md#tls)).
2. **Testing only:** In Chrome, go to `chrome://flags/#unsafely-treat-insecure-origin-as-secure` and add your server IP.

---

### Attendance is being rejected with "Outside geofence"

The server-side check uses the room's coordinates and a 15-meter radius. A room placed at the wrong point refuses every mark; a room never placed at all is not fenced, and every mark is accepted.

Find the room and see where it thinks it is:

```bash
curl -H "Authorization: Bearer $TOKEN" "https://chronos.example.org/api/v1/resources/?code=LH-3"
```

Then move it, using the `id` that came back:

```bash
curl -X PATCH -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" -d '{"latitude": 12.9716, "longitude": 77.5946, "altitude_target": 920.0}' "https://chronos.example.org/api/v1/resources/12"
```

`latitude` and `longitude` are set or cleared together: sending one without the other is refused, since half a location fences the room to a point on the equator. `altitude_target` is optional, and a room without one is fenced horizontally only.

One day held somewhere else is a day-level override, `PATCH /schedule/ledger/{id}` with `latitude_target` and `longitude_target`. Where a day carries its own coordinates the room's are not consulted. The radius is the day's `precision_radius_meters`, defaulting to 15 meters.

---

### A member in the room is told their location accuracy is too coarse

The phone reports how far off its fix may be, and the server refuses a mark whose fix is coarser than `GEOFENCE_ACCURACY_FACTOR` times the fence radius: 30 meters on the default 15 meter radius. Indoors and away from a window, a phone on a network-based fix often reports 50 meters or more. Waiting a few seconds for the fix to settle, or moving nearer a window, is usually enough.

To loosen it, raise `GEOFENCE_ACCURACY_FACTOR` or widen the day's `precision_radius_meters`; `0` turns the accuracy check off. The web client separately refuses to mark when the accuracy is worse than 30 meters, whatever the server allows.

---

### The altitude check is blocking members on the correct floor

The altitude delta threshold is `|Δalt| < 4 meters`. GPS altitude accuracy is typically ±10–20m on mobile devices, making this check unreliable outdoors. The check only fires when the device reports altitude, if the device does not expose it, the check is skipped.

If you want to widen the threshold, it is a constant in `backend/app/services/geo_fence.py`:

```python
FLOOR_TOLERANCE_METERS = 4.0   # change to 10.0 for looser enforcement
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

### Staff submitted an absence but the line manager never got notified

WebSocket notifications are only delivered to connected clients. The line manager must have the app open. If they are offline, the absence request will still appear in their pending queue when they next log in.

For email notifications, the current release does not include an email transport. This is a planned enhancement.

---

### Proxy assignment is not reflected on the member timeline

The member timeline reads from the live ledger. After approving a proxy, trigger a ledger refresh: Admin Dashboard → Import → Generate Daily Ledger (or wait for the midnight cron).

---

### An absence was approved but the staff member's ledger still shows SCHEDULED

The ledger is a materialized daily snapshot. Approved absences cascade `ON_LEAVE` only when the ledger is regenerated. Use the manual Generate button in the Admin Dashboard.

---

## Guest Kiosk

### The guest form submits but the staff member never gets the notification

The staff member must be online with the app open. The notification arrives via WebSocket to `/staff/dashboard`. If they are offline, the request stays pending in the database and will appear when they next log in.

Check that the staff member's email in the guest form exactly matches their account email, the lookup is case-insensitive but the email must exist in the system.

---

### Guest check-in kiosk is accessible without a login, is this intentional?

Yes. The guest kiosk (`/guest/kiosk`) is explicitly public. It does not expose any internal data, it only allows submitting a visit request and viewing the staff notification status. The underlying API endpoints (`/api/v1/guest/*`) are similarly unauthenticated by design.

---

## Notifications & Web Push

### Push notifications are not appearing

1. Confirm the user has granted notification permission (browser prompt when first logging in).
2. Verify VAPID keys are set in `.env`: `VAPID_PUBLIC_KEY`, `VAPID_PRIVATE_KEY`, and `VAPID_CONTACT_EMAIL`.
3. Check that the frontend was built with the matching `NEXT_PUBLIC_VAPID_PUBLIC_KEY`.
4. VAPID public key must be the same value in both places. Regenerate with `npx web-push generate-vapid-keys` if unsure, then rebuild.

---

### Class reminder push fires too early or too late

Reminders fire 15 minutes before the slot's `time_window_start` via `periodicsync` in the service worker. The accuracy depends on when the browser chooses to fire the periodic sync, browsers enforce a minimum interval of ~1 hour for battery reasons.

For more reliable reminders, the user must keep the tab open (the service worker runs JavaScript timers when the tab is active).

---

## WebSocket / Live Updates

### The live indicator shows "Offline" even though the server is running

The WebSocket connects to `NEXT_PUBLIC_WS_URL`. In the GHCR image this defaults to `/ws` (same-origin). If you are running the frontend dev server and the backend separately, ensure `NEXT_PUBLIC_WS_URL=ws://localhost:8000/ws`.

Also check nginx is proxying `/ws` correctly, see `nginx/nginx.conf`.

---

### WebSocket disconnects every few minutes

Nginx has a default proxy read timeout of 60 seconds. The Chronos Ledger nginx config sets `proxy_read_timeout 3600s` on the `/ws` location. If you see 60-second drops, nginx.conf may not have been updated, verify:

```bash
docker compose exec chronos-proxy cat /etc/nginx/nginx.conf | grep proxy_read_timeout
```

---

## Docker & Deployment

### `docker compose up` fails with "port is already allocated"

Another service on the host owns port 80 or 443. Either stop it (`sudo systemctl stop apache2` / `nginx`), or move the Chronos edge proxy aside in `.env`, without editing any compose file:

```bash
EDGE_HTTP_PORT=8080
EDGE_HTTPS_PORT=8443
```

Only the host side moves. The proxy container still listens on 80 and 443, so nothing inside the stack changes. This is also how you put Chronos behind an outer reverse proxy that owns the host's 80 and 443.

---

### Container exits with OOM (out of memory) on low-RAM servers

`docker-compose.prod.yml` runs Redis with `--maxmemory 256mb`; the development compose file sets no limit. PostgreSQL can spike higher during bulk import. Minimum recommended RAM: **1 GB free** after OS. On 512 MB machines, reduce Redis:

```yaml
command: redis-server --maxmemory 64mb --maxmemory-policy allkeys-lru
```

---

### How do I back up the database?

```bash
docker compose exec chronos-db pg_dump -U chronos_admin chronos_ledger \
  | gzip > chronos-backup-$(date +%Y%m%d).sql.gz
```

To restore:

```bash
gunzip -c chronos-backup-20260519.sql.gz \
  | docker compose exec -T chronos-db psql -U chronos_admin chronos_ledger
```

---

### How do I update to a new release?

```bash
# Pull the latest docker-compose.prod.yml from the release assets, or:
export VERSION=v1.2.0
docker compose -f docker-compose.prod.yml pull
docker compose -f docker-compose.prod.yml up -d
```

Chronos Ledger images are built with an SBOM and build provenance. Those ride
inside the image index, so they are there whichever registry you pulled from:

```bash
docker buildx imagetools inspect ghcr.io/life-experimentalist/chronos-ledger-backend:v1.2.0
docker buildx imagetools inspect vkrishna04/chronos-ledger-backend:v1.2.0
```

There is also a Sigstore-signed SLSA provenance attestation, which says which
workflow run built the image and from which commit:

```bash
gh attestation verify oci://ghcr.io/life-experimentalist/chronos-ledger-backend:v1.2.0 \
  --owner Life-Experimentalist
```

The Docker Hub copy verifies the same way (`oci://docker.io/vkrishna04/...`). `gh`
resolves the digest from the registry and then asks GitHub for the attestation,
so it does not matter that only the GHCR copy carries it as a registry referrer.

---

### Trivy reports a HIGH CVE in the production image

Check if the CVE affects Chronos Ledger's actual usage (many CVEs in base images are in code paths that are never executed). If it does:

1. Open an issue on GitHub with the CVE ID.
2. If it's in the base image (`node:20-alpine`, `python:3.11-slim`, or `nginx:1.27-alpine`), we will update the `FROM` line once the upstream image is patched.
3. If it's in a dependency, update via `uv add <package>@<fixed-version>` or `npm install <package>@<fixed-version>`.

A HIGH is reported and does not stop the build. A CRITICAL with a published fix
does stop it, and no image is pushed until it is dealt with. A CRITICAL with no
fix available anywhere is reported but not blocking, because there would be
nothing to do about it except turn the check off.

---

## CI/CD & container registries

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

### Nothing is appearing on Docker Hub

Docker Hub publishing turns itself off when it is not configured, and says so in
the run summary rather than failing the run. It needs both halves:

- repository **variable** `DOCKERHUB_NAMESPACE`, the account the images live
  under, which is what appears in `docker pull <namespace>/chronos-ledger-backend`
- repository **secret** `DOCKERHUB_TOKEN`, a Docker Hub personal access token
  with Read & Write scope. Not the account password.

`DOCKERHUB_USERNAME` is optional. Without it the login uses the namespace, which
is the same string for a personal account and differs only when pushing into an
organization.

```bash
gh variable set DOCKERHUB_NAMESPACE --body "your-account"
gh secret set DOCKERHUB_TOKEN        # paste the PAT when prompted
```

Set one and not the other and the run writes a notice saying so, then pushes to
GHCR only. Docker Hub creates both repositories on the first push with whatever
default visibility the account has, so check they came out public if that is what
you wanted.

---

### `gh attestation verify` says no attestations were found

Three things it could be:

1. The image predates the signed attestations, which start from the first build
   after they were added. The SBOM and provenance that buildkit attaches are
   older and are read with `docker buildx imagetools inspect` instead.
2. `--owner` is wrong. It is the GitHub account that owns the *repository*, not
   the Docker Hub namespace, so it stays `Life-Experimentalist` even when
   verifying a `docker.io/` image. It also keeps its capitals, unlike the
   `ghcr.io/` path beside it: a registry refuses a repository path with a
   capital in it, a GitHub account name is free to have one.
3. The workflow could not mint one. `attest-build-provenance` needs both
   `id-token: write` and `attestations: write`, and a called workflow's token
   is capped by the job that calls it, so all four of `cd.yml`, `release.yml`
   and the two calling jobs in `ci.yml` declare them. Drop one and the step
   fails loudly.

---

### Release Please is not creating a release PR

Likely causes:
1. CI failed on `main`. Release Please runs from `ci.yml` once every gate has passed, so a red `main` leaves the release PR where it is until the failure is fixed.
2. Commits are not following [Conventional Commits](https://www.conventionalcommits.org/), only `feat:`, `fix:`, `perf:`, and `security:` prefixes create release PRs.
3. `release-please-config.json` or `.release-please-manifest.json` is missing or malformed.
4. The `GITHUB_TOKEN` permissions do not include `pull-requests: write`.

Permissions are granted by the `release` job in `ci.yml`: a called workflow's token is capped by the calling job, so that is the one place to change them. Inside `release.yml` the `release-please` job declares `contents: write` and `pull-requests: write`.

---

## New Cycle Rollover

### How do I start a new planning cycle or term?

1. Open the Onboarding Wizard: Admin Dashboard → **Setup Guide**
2. Skip to **Step 2: Create Cycle**. Fill in the new term's start and end dates.
3. Move to **Step 3: Import CSV**. Upload the new term's timetable CSV.
4. Click **Generate Ledger** to populate the first day's entries.

The old cycle is preserved in full; historical attendance records and ledger snapshots remain untouched. The wizard opens the new cycle and leaves the old one open too, so close the old one with `PATCH /schedule/cycles/{id}/close` once its last day has run. [Planning Cycle Rollover](deployment.md#planning-cycle-rollover) in the deployment guide walks through it.

---

### Can I have multiple cycles active simultaneously?

Yes. Several cycles can be open at once, and each writes days only for dates inside its own start and end, so a spring cycle and an autumn cycle never touch. Opening a cycle checks its slots against the rooms already taken on the dates it shares with the other open cycles and is refused with `409` on a clash; two cycles whose dates do not overlap can use the same room at the same hour. Close a cycle with `PATCH /schedule/cycles/{id}/close` once its last day has run; its history stays queryable under its ID.

---

### How do I add a new unit mid-year?

1. Prepare a CSV with only the new unit's data.
2. Import it via Admin Dashboard → Import Data → CSV Import Zone.
3. The import is idempotent, existing records are not duplicated; new ones are created.
4. Regenerate the ledger to include the new slots in today's schedule.

---

## Data & Privacy

### What data does Chronos Ledger store?

All data stays on your organization server. A default install sends nothing to any external service:

- **Telemetry (opt-in, off by default):** Anonymous view counts sent to a [CFlair-Counter](https://github.com/Life-Experimentalist/CFlair-Counter) instance you point it at. No PII. Requires both `NEXT_PUBLIC_TELEMETRY_ENABLED=true` and a non-empty `NEXT_PUBLIC_TELEMETRY_ENDPOINT` at build time.
- **Web Push:** Push payloads are routed through the browser vendor's push service (Google FCM for Chrome, Mozilla for Firefox). Payload content is a short status string, no member names or sensitive data.

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

Chronos Ledger is designed for on-premises deployment, and the deploying institution is the data controller. Visitor check-ins have a retention setting of their own, since each one holds a visitor's name and phone number: set `GUEST_RETENTION_DAYS` to a number of days, such as 90, and a job at 03:30 in `ORG_TIMEZONE` deletes the check-ins older than that every day, whether or not anyone acted on them. It defaults to 0, which keeps them forever. Other records, attendance included, are kept until an administrator removes them, so any other retention policy is implemented directly on the PostgreSQL database.
