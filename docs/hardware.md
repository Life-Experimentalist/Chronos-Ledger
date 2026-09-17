# Hardware requirements

How much machine Chronos Ledger needs, what it did under load, and where buying
more hardware stops helping.

## Short answer

| Setup | Verdict |
|---|---|
| Arduino or any microcontroller | Cannot run it. There is no operating system to run Docker, Python or PostgreSQL on. |
| Raspberry Pi Zero, Pi 3, anything with 1 GB RAM | Not recommended. It will start, but RAM is too tight for PostgreSQL plus the app. |
| Raspberry Pi 4 or 5 with 4 GB or more | Works for a small organization. Build the images yourself (see ARM below). |
| Old laptop, 2 cores, 4 GB, SSD | Works well for a single site with a few thousand members. |
| Cheap VPS, 1 vCPU and 1 GB | Starts and works for light use. Logins are slow and there is little RAM headroom. |
| VPS, 2 vCPU and 2 GB | The recommended minimum for production. |
| Mac mini | More than enough for one site. Build the images locally (see ARM below). |
| Server with 8+ cores | Only pays off if you run several app replicas. One app process uses about 1.2 cores. |

- Bare minimum: 1 core, 1 GB RAM, 5 GB disk.
- Recommended: 2 cores, 2 GB RAM, SSD.
- Large site: 4 cores, 4 to 8 GB RAM, SSD, three app replicas.

## How it was measured

- The production compose file (`docker-compose.prod.yml`): nginx, one uvicorn process, PostgreSQL 17 and Redis.
- Seed data: 500 users and 50 bookable resources.
- Load generator: [k6](https://k6.io), running on the same Docker network and going through nginx.
- Test host: an Intel i5-1240P laptop running Docker Desktop on Windows. This is a slow host. bcrypt at cost 12 took 532 ms per hash, and a 3-million-iteration Python loop took 800 ms, which is roughly two to four times slower than a bare Linux server. Treat every absolute number below as a floor. The ratios and limits carry over.
- CPU limits in the tier table were applied with `docker update --cpus`.

## Results, one app process, no CPU limit

Throughput is requests per second. "Users" means concurrent virtual users sending requests back to back, with no think time, so 10 of them load the server more than hundreds of real people would.

| Workload | Users | Req/s | p50 | p95 |
|---|---|---|---|---|
| `/health` (no database) | 50 | 564 | 80 ms | 147 ms |
| Reads (resources, users, ledger, availability) | 1 | 42 | 21 ms | 47 ms |
| Reads | 10 | 61 | 152 ms | 256 ms |
| Reads | 25 | 50 | 472 ms | 833 ms |
| Reads | 50 | 54 | 896 ms | 1.4 s |
| Reads | 100 | 60 | 1.6 s | 2.3 s |
| Reads | 200 | 56 | 3.5 s | 5.1 s |
| Reservations (writes) | 1 | 19 | 43 ms | 122 ms |
| Reservations | 10 | 25 | 285 ms | 1.0 s |
| Mixed, 80% reads and 20% writes | 10 | 27 | 326 ms | 700 ms |
| Mixed | 25 | 25 | 846 ms | 1.8 s |
| Mixed | 200 | 51 | 3.7 s | 4.9 s |
| Reservations | 100 | 30 | 3.2 s | 4.3 s |
| Login (bcrypt) | 1 | 0.8 | 1.3 s | 1.7 s |
| Login | 16 | 7.5 | 1.8 s | 3.6 s |

Other checks:

- Double booking: 25 users hammered one room and one already-booked 30-minute slot for 30 seconds. All 489 attempts got `409`, and none got through.
- Past its capacity, a process does not slow down further. It works on at most 30 API requests at once (its connection pool), holds the rest for up to 10 seconds, and answers `503` with `Retry-After` for anything still waiting. With 200 users sending requests back to back, requests queued for about 3.5 seconds and none got `503`. `/health` kept answering throughout, and the app was back to normal a second after the load stopped.
- WebSockets: 500 authenticated sockets held open for a minute with no failures. nginx allows 16,384 connections per worker, about 8,000 proxied sockets. In a 5,000-socket burst on the test laptop, 81% connected; every socket authenticates through the app, so a burst that size queues behind it.
- Kiosk check-in: without a kiosk key the endpoint answers `401`. With a key, the per-account rate limit starts returning `429` as designed.
- Memory when idle: app about 175 MB, PostgreSQL about 70 MB, nginx and Redis under 5 MB each. Plan for about 250 MB idle and 1 GB under load.

## What it means for a real organization

- Marking attendance is one small write. 2,000 members marking inside a five-minute window is about 7 requests per second, which one core handles.
- Logins are the expensive part. bcrypt is slow on purpose, and each login costs about half a core-second on the test host. Sessions last, so logins are rare, but if everyone signs in at 9:00 on the first day, more cores help directly. This is the one workload that uses extra cores inside a single process.
- Dashboards mostly wait on WebSocket pushes rather than polling, so open screens cost memory, not CPU.

## How many people at once

Real people pause between actions. With each simulated person doing one read or booking and then waiting 10 to 30 seconds:

| People | Req/s | p50 | Turned away with 503 |
|---|---|---|---|
| 1,000 | 26 | 24 ms | 0% |
| 3,000 | 59 | 10 s | 31% |

One process handles about 1,000 people who are all active at the same moment, and the limit is the 50 to 60 requests per second it can serve, not the number of connections. Everyone started in the same second in these runs, which is harsher than a real morning.

For 10,000 people active at once (about 500 requests per second), plan for:

- about 10 app processes on hardware like the test laptop, or 3 to 5 on a server whose cores are two to four times faster,
- PgBouncer in front of PostgreSQL, or `max_connections` raised to cover 30 per process,
- PostgreSQL on its own fast SSD with 4 GB or more of RAM.

This is an estimate from the single-process and three-replica numbers above. A ten-process setup was not tested.

10,000 accounts, of whom a few hundred are active in any given minute, is a much smaller load and fits a single 2-core server.

## CPU tiers

Mixed workload, one app process, with CPU capped per container.

| App CPU | DB CPU | Mixed req/s at 10 users | p95 at 10 users | Login/s at 4 users |
|---|---|---|---|---|
| 0.3 | 0.15 | 3 | 5.5 s | 0.2 |
| 0.6 | 0.3 | 8 | 2.5 s | 0.9 |
| 1.2 | 0.6 | 48 | 373 ms | 2.7 |
| 2.4 | 1.2 | 20 to 60 | under 1 s | 2.4 |
| 5 | 2.5 | 26 to 40 | under 600 ms | 4.3 |

Runs above 1.2 cores moved around by a factor of two between repeats, because the laptop was also the load generator. Their spread is noise; there is no trend.

## Where upgrading stops helping

- Below one core, everything is slow. Half a core is not a usable server.
- From 1 to 2 cores, requests get much faster. This is the best value upgrade.
- Past 2 cores, a single app process gains nothing for ordinary requests. Python runs one request's code at a time per process, so the process tops out at about 1.2 cores. Extra cores only speed up logins.
- Past 2 GB RAM, nothing improves unless your database outgrows the PostgreSQL cache. That takes years of attendance history for one organization.
- An SSD matters more than extra cores once writes dominate. Avoid SD cards and spinning disks for the database.

To use more than 2 cores, run more app processes. This works with `docker-compose.prod.yml`, which does not pin container names:

```bash
docker compose -f docker-compose.prod.yml up -d --scale chronos-app=3
docker compose -f docker-compose.prod.yml restart chronos-proxy
```

nginx resolves the app name when it starts, so restart it after scaling. With three replicas on the same host:

| Workload | Users | 1 replica | 3 replicas |
|---|---|---|---|
| Reads | 50 | 54 req/s, p95 1.4 s | 100 req/s, p95 914 ms |
| Mixed | 10 | 27 req/s, p95 700 ms | 78 req/s, p95 296 ms |
| Reads | 100 | 60 req/s, p95 2.3 s | 68 req/s, p95 2.3 s |

Requests were spread evenly across the three replicas. Past three, you hit the limits below before you run out of cores.

- PostgreSQL defaults to `max_connections=100`, and each app process may open up to 30 (`pool_size=10`, `max_overflow=20` in `backend/app/core/database.py`). Three replicas is the untuned ceiling. Raise `max_connections` or add PgBouncer to go further.
- PostgreSQL itself becomes the bottleneck. On the test host it used about 1.5 cores with three replicas. Past that, give it faster disk and more RAM rather than more app replicas.

For a single organization, 4 cores and 4 GB with three replicas is where more hardware stops changing anything you would notice.

## ARM: Raspberry Pi and Apple Silicon

The published images are built for `linux/amd64` only. On a Raspberry Pi or an Apple Silicon Mac, use the default `docker-compose.yml`, which builds both images from source on the machine itself:

```bash
docker compose up -d --build
```

The first build takes a while on a Pi. A Mac can also run the amd64 images through emulation, but slower. Expect a Pi 4 or 5 to be several times slower than the numbers above, especially for logins. It is still fine for a few hundred members who sign in once and stay signed in.
