# Run it and show it: a five-minute demo

This gets Chronos Ledger running on one machine with realistic data, so you
can walk someone through it. For a real deployment, see
[deployment.md](deployment.md).

## What you need

- Docker Desktop (running)
- On Windows: Git Bash (installed with Git). Open it in the repo folder.

## One command

```bash
./setup.sh --build --demo
```

This creates `.env` with fresh secrets, builds and starts everything, and
loads a small demo data set: two staff, one member, three activities with
sessions scheduled today. The first build takes a few minutes.

When it finishes, the script prints the address to open on its `App:` line
(http://localhost when everything runs on the same laptop).

## Sign in

| Who | Email | Password |
| --- | --- | --- |
| Admin | `admin@org.internal` | `ChronosAdmin2026!` |
| Staff | `staff@demo.internal` | `StaffDemo2026!` |
| Staff | `staff2@demo.internal` | `StaffDemo2026!` |
| Member | `member@demo.internal` | `MemberDemo2026!` |

The admin account asks you to set a new password on first login. That is
deliberate (seeded credentials are never left active); pick one and note it.

## The walkthrough

Signing in at that address routes each person to their own portal
automatically. Sign out between steps to switch roles.

1. **Admin**: sign in as admin. The dashboard shows today's schedule
   across the organization; onboarding is where new people and units are
   added.
2. **Staff**: sign in as `staff@demo.internal`. The dashboard shows the
   sessions this person leads today, and lets them report a planned
   absence.
3. **Member**: sign in as `member@demo.internal`. Today's sessions are
   listed, and attendance can be marked. The marking card lights up
   during a session's time window (the demo day has sessions at 09:00,
   11:00, and 15:00). Demo sessions carry no location pin, so marking
   works from any laptop with no GPS needed; in a real deployment each
   session is geo-fenced to its room's coordinates.
4. **Guest kiosk** (`/guest/kiosk/` on the same address): no login needed. A
   visitor registers a check-in here and the responsible staff member gets
   a live notification to approve or decline.
5. **API** (`/docs` on the same address): the whole API, interactive, if your
   audience is technical.

## Reset and rerun

To wipe everything (including the demo data and any password you set) and
start fresh:

```bash
docker compose down -v
./setup.sh --build --demo
```

To load the demo data into an already-running stack:

```bash
docker compose run --rm chronos-app uv run --no-sync python -m app.demo_seed
```

Running the seed twice is safe. On demo day, rerun it once: today's
sessions are generated nightly and only while the stack is running, and
the seed fills in any that are missing.
