# Federated Identity

<!-- Copyright 2026 Chronos Ledger Contributors (Apache 2.0) -->

Planned. Nothing in this document is built yet.

An organization that already runs an identity system should not have to give
its people a second password. This is the contract for letting one of those
systems vouch for a person, so that somebody signed in over there arrives here
signed in too.

The mechanism is a short-lived signed note. The other system mints a token
saying "the holder of this is subject `S`, and I issued it at `T`", the browser
hands it to Chronos once, and Chronos answers with its own access and refresh
pair, the same pair `POST /auth/login` returns. Chronos never sees a password
belonging to the other system and never calls back into it. There is no
redirect dance, no callback URL and no client secret.

It is off unless an operator turns it on, and turning it on is not enough on
its own: an issuer has to be registered, with its public key and what it is
allowed to assert.

This is a deliberately small piece of OIDC. It is not OIDC. There is no
discovery document, no authorization code, no userinfo endpoint and no refresh
against the issuer. If an organization needs the full protocol, the honest
answer is that Chronos does not speak it yet, and this page does not pretend
otherwise.

---

## Threat model

Written first, because every decision below follows from it. Each item is the
threat, what stops it, and what is left over.

### The note is replayed

A note that reaches Chronos once can reach it again, from anywhere, for as long
as it is valid. Anybody who reads it out of a log, a proxy, a crash report or
the browser's history gets a session as that person.

Stopped by two things together. Every note carries a `jti`, and Chronos records
each one it accepts in Redis until the note could no longer be valid; a second
arrival with the same `jti` is refused. And a note is only ever accepted with a
short life, so the window in which a stolen one is worth anything is bounded
even if the cache is bypassed.

The `jti` cache fails **closed**. This is the opposite of the rate limiter,
which fails open on purpose (`backend/app/core/rate_limit.py`), and the
difference is worth stating: a limiter that cannot reach Redis should still let
people sign in, because the alternative locks an organization out of its own
system. A replay cache that cannot reach Redis has stopped being a replay
cache, and continuing without it turns every note into a bearer token anybody
can reuse. When Redis is unreachable, federated sign-in refuses with 503.
Password sign-in keeps working, so the organization is not locked out; only the
shortcut is.

Left over: a note stolen and replayed within its own lifetime, before the
legitimate holder spends it, still works. The cache makes the two uses
exclusive, not the theft impossible.

### The note lives too long

An issuer that sets `exp` a year out has minted a bearer token for a year. It
is still a valid note by every other measure.

Chronos refuses a note whose `exp` is further ahead than
`FEDERATED_TOKEN_MAX_LIFETIME_SECONDS` (default 120) from the time it arrives.
Checking `exp` alone is not enough, because `exp` is the issuer's opinion. The
cap is Chronos's.

### The clocks disagree

Two machines that differ by thirty seconds will reject notes that are perfectly
good, and the failure looks like a broken integration rather than a clock.

`FEDERATED_CLOCK_SKEW_SECONDS` (default 60) is the tolerance, and it is not
symmetric in what it protects against. `exp` may be up to the skew in the past,
so a note that expired a moment ago on a slightly fast clock still works.
`iat` and `nbf` may be up to the skew in the *future*, so a note from a
slightly fast issuer works. There is no lower bound on `iat`: how old a note may
be is already answered by `exp` and the lifetime cap, and bounding its age by
`iat` as well would refuse a two-minute note ninety seconds into its life, which
is a note doing exactly what it was minted to do. The replay cache holds each
`jti` for the lifetime cap plus the skew, so a note cannot outlive its own
record.

One `leeway` on the verifier covers `exp` and `nbf`, and the lifetime cap is a
separate comparison after it.

Left over: skew widens the replay window by the same amount it widens the
tolerance. Sixty seconds is the trade; an operator who runs NTP everywhere can
set it lower.

### The signing key leaks

Whoever holds the issuer's private key can mint a note for any subject it is
allowed to assert, and Chronos has no way to tell that note from a real one.
This is the worst case and it cannot be mitigated by checking the note harder.

What limits the damage is what an issuer is allowed to assert. The role map is
an operator's, stored on the issuer's registration in Chronos, not read from
the note. A note names a subject and, optionally, groups; it never names a
Chronos role. An issuer whose map has no entry for a group gets `MEMBER`, and
no issuer can produce `ORG_ADMIN` or `UNIT_ADMIN` at all: those two roles are
excluded from the map by validation, not by convention. A leaked key therefore
buys accounts at the level the operator chose, which is the level the issuer's
own users already had.

`POST /federation/links` refuses an admin account for the same reason, and it is
the same reason rather than a second rule: linking would hand an issuer a route
to an account the map could never have produced, so the exclusion would hold on
paper and not in fact. Refusing at link time is not enough on its own, because a
linked account can become an admin afterwards; the next item is that case.

Registration also carries `not_before` and `not_after` per key, so a key can be
retired at a known moment rather than at a restart.

### The key needs rotating

An issuer that cannot rotate without downtime will not rotate.

A registration holds a set of public keys, each with a `kid`, a `not_before`
and a `not_after`. A note's header names its `kid` and Chronos verifies against
that key only. Rotation is adding the new key, waiting for the old one's
`not_after`, and removing it. Two keys are valid at once during the overlap,
which is the point.

A note whose header carries no `kid`, or a `kid` the registration does not
know, is refused. Trying every key in turn would make a rotation window a
period in which a retired key still works.

### The algorithm is read from the note

A verifier that trusts `alg` in the header can be told to use `none`, or to
treat an RSA public key as an HMAC secret, both of which have ended in forged
tokens in real systems.

Chronos pins `EdDSA` (Ed25519) and passes exactly that one algorithm to the
verifier. The header's `alg` is not consulted to decide anything; a note that
disagrees fails verification. Ed25519 because it has one curve, one key size
and no padding mode, so there is nothing to misconfigure.

### The note is for somebody else

A note minted for a different relying party, or for a different Chronos
instance, should not work here.

`aud` is checked against the audience on the issuer's registration, and `iss`
against the registration's issuer name. An issuer that serves several relying
parties gives each one its own audience, and a note for one is refused by the
others.

### The subject collides with a local account

This is the account takeover that matters, and it is the one most likely to be
got wrong.

If a first-time `(issuer, subject)` carries an email address that already
belongs to a Chronos account, Chronos does **not** link the two. It refuses
with 409. Linking on a matching email means a compromised issuer, or an issuer
that never verified the address it is asserting, can take over any account
whose address it can guess, including an administrator's.

A link is created only by provisioning a new account, and used only when
`(issuer, subject)` is already in the link table. An existing person who should
use the shortcut is linked by an administrator, deliberately, through the
registry routes. The email address is convenience; `(issuer, subject)` is
identity.

### The linked account becomes an administrator

A link that was sound when an operator created it stops being sound if the
account behind it is promoted. Nothing about the issuer changed, and nobody did
anything wrong: an account linked while it was `STAFF` was later given an admin
role in the ordinary way, and from that moment whoever holds the issuer's
signing key can mint a note that authenticates as an administrator. That is the
one thing the role map and the link rule both exist to prevent.

So the refusal is made twice, at both moments it can be made. `POST
/federation/links` will not link an admin account, and `account_for` will not
spend a link whose account has since become one: the sign-in fails with 403 and
a sentence saying to use a password. Checking only at link time would leave the
promotion path open, and checking only at sign-in would let an operator create a
link that can never be used.

The role is read to refuse, never to rewrite. Federation does not demote the
account, because demoting somebody an administrator promoted is the thing the
item below rules out. The refusal closes a route; it does not close anybody out,
since an administrator has a password. Undoing the promotion makes the link work
again, so a promotion made by mistake needs nothing repaired beyond the role.

Left over: between the promotion and the next attempt, any session the person
already holds is still a session. This closes the shortcut, not the sessions
issued through it before the promotion.

### The upstream account goes away

Somebody who leaves the organization keeps whatever Chronos session they last
obtained until it expires.

Chronos's own refresh lifetime is the revocation window, and there is no way
around that short of asking the issuer on every request, which this design
does not do. The lever is Chronos: `deactivated_at` on the account ends the
session at the next request (`security.py::get_current_user`) and drops the
refresh tokens. A linked account with `deactivated_at` set is refused at
exchange and is **not** re-provisioned, so signing in again upstream does not
resurrect it.

Left over by design: an upstream demotion does not reach Chronos. Roles are set
when the account is provisioned and never re-synced, because re-syncing on
every sign-in silently undoes an administrator's own change here. Deactivation
is the lever, and the trade is stated rather than hidden.

### The note ends up somewhere it is readable

A token in a query string is written to the proxy's access log, the browser's
history, and the `Referer` of the next request the page makes.

The note reaches Chronos in a `POST` body. The handoff from the other system
puts it in the URL fragment (`#token=...`), which browsers do not send to
servers, and the page reads it client-side and posts it. The frontend is a
static export, so there is no server-side handler that could receive it in a
path or a query.

### The route itself leaks that federation exists

Probing an instance should not reveal which integrations it has.

When `FEDERATED_IDENTITY_ENABLED` is false the exchange route answers 404, not
403. An unregistered or disabled issuer gets the same 401 as a bad signature.

### Nobody is counting attempts

Flooding the exchange with invalid notes costs a signature verification per
request.

No budget, and this follows the reasoning already written into
`backend/app/core/rate_limit.py`: a budget exists where a credential is worth
guessing. An Ed25519 signature is not guessable, verification is cheap enough
that the request cost is dominated by everything around it, and a valid note
with a reused `jti` is refused by a single Redis read. What is counted instead
is the outcome: every refusal is an audit record, so a flood is visible even
though it is not throttled.

---

## The contract

Numbered so the items can be picked up in order. `F-1` through `F-4` are the
smallest thing that works; `F-5` through `F-7` are what make it usable by
anyone who is not writing SQL and curl.

### F-1. An issuer registry

- **Scope:** A `federated_issuers` table: `id`, `issuer` (the `iss` value,
  unique), `display_name`, `audience`, `enabled`, `created_at`. A
  `federated_issuer_keys` table: `id`, `issuer_id`, `kid`, `public_key` (the
  Ed25519 public key, PEM), `not_before`, `not_after`. A
  `federated_role_map` table: `id`, `issuer_id`, `group_claim_value`,
  `role_type`, `unit_code`. Validation refuses `ORG_ADMIN` and `UNIT_ADMIN` in
  the map. It does not refuse a second `STAFF` entry whose `unit_code` differs
  from an existing one: that pair is the ordinary case, and the tie is broken
  at sign-in instead, for the reason recorded under the claims table below.
- **Touches:** `backend/app/models/db.py`,
  `backend/alembic/versions/028_*.py`, `docs/data-model.md`.
- **Done when:** a registration with two keys whose validity windows overlap
  verifies notes signed by either, and the map refuses an admin role with a
  422 naming the field.

### F-2. The note is verified

- **Scope:** `backend/app/services/federated_identity.py`. Given a raw token,
  read the header for `kid` without trusting it for anything else, look up the
  key, and verify with `algorithms=["EdDSA"]` and the registration's
  `audience` and `issuer`. Then check, in this order: the key's validity
  window, `iat` within skew, `exp` within skew, `exp` no further ahead than the
  lifetime cap, and `jti` not already spent. Record the `jti` with a TTL of the
  cap plus the skew, using `SET NX`, so two notes racing cannot both win. The
  key is `fed:jti:` and a hash of the issuer and the `jti` together, not the
  `jti` itself, for the reason `rate_limit._bucket_key` hashes its subject: a
  `jti` is part of a credential and does not belong in a keyspace an operator
  reads with `KEYS`. Two issuers that happen to mint the same `jti` do not
  collide. Redis unreachable raises, and the route answers 503.
- **Touches:** `backend/app/services/federated_identity.py`,
  `backend/app/core/config.py`.
- **Done when:** a test suite covers each refusal separately: wrong algorithm,
  `alg: none`, unknown `kid`, retired `kid`, wrong `aud`, wrong `iss`, expired,
  issued in the future, `exp` beyond the cap, replayed `jti`, and Redis down.
  A note ninety seconds into a two-minute life is accepted, which is the test
  that keeps the `iat` rule from drifting back into a lower bound.

The tests need a Redis that answers, since this cache fails closed and there is
nothing to fall back to. There is no `fakeredis` dependency and none is needed:
`tests/test_rate_limit.py` already carries a hand-written stand-in monkeypatched
over `get_redis` in the module under test, and this wants the same thing with
`set(key, value, nx=True, ex=...)` on it. That means the service imports
`get_redis` into its own namespace and calls it directly, not through
`rate_limit._counter`, which answers `None` whenever `RATE_LIMIT_ENABLED` is
false and would quietly turn the replay check off for the whole suite.

### F-3. The exchange route

- **Scope:** `POST /api/v1/auth/federated`, unauthenticated, body
  `{token: str}`, `operation_id: auth.federated`. Returns the existing
  `TokenResponse`, unchanged, so the frontend's session handling is untouched.
  404 when the feature is off. 401 for any verification failure, with one
  message for all of them, so the refusal is not an oracle. 403 when the account
  behind a sound link has become an admin, which is said plainly rather than
  folded into the 401: the note verified, the person can do nothing about the
  refusal, and reaching this answer at all takes a note the issuer's key signed,
  so it tells nobody anything about an account that is not already theirs. 409 on
  the email collision in F-4. 422 when a first-time subject arrives with no
  `email` claim, which is a note that verified correctly and then could not be
  turned into an account: a different thing from a bad note and worth a different
  answer. 503 when the replay cache is unreachable.
- **Touches:** `backend/app/api/v1/endpoints/auth.py`,
  `backend/app/schemas/auth.py`, `docs/openapi.yaml`, both SDKs,
  `docs/api.md`.
- **Done when:** `tests/test_openapi_spec_matches_app.py` passes with the new
  operation, both SDKs regenerate with no diff, and a valid note yields a pair
  that `POST /auth/refresh` accepts.

### F-4. An account appears the first time

- **Scope:** A `federated_identities` table: `id`, `issuer_id`, `subject`,
  `user_id`, `created_at`, unique on `(issuer_id, subject)`. On a note whose
  pair is already there, load that user, refuse if `deactivated_at` is set, and
  issue the session. On a pair that is not there, provision: require an `email`
  claim, resolve the role and unit from the map (no match means `MEMBER` and no
  unit), refuse with 409 if that address already belongs to an account, and
  insert a `User` with `credential_secure_hash` set to
  `hash_password(secrets.token_urlsafe(32))` and `initial_login_state` false.
  The link's `user_id` cascades on delete: `users.py` has a hard-delete path,
  and a link left pointing at a deleted account would refuse that person
  forever rather than letting them arrive as somebody new.
- **Touches:** `backend/app/models/db.py`, migration `028`,
  `backend/app/services/federated_identity.py`, `docs/data-model.md`.
- **Done when:** the second sign-in reuses the first account, a role changed by
  an administrator survives the next sign-in, an account promoted to either admin
  role is refused with 403 and not demoted, a deactivated linked account is
  refused rather than re-provisioned, a reactivated one works again, a colliding
  address is refused with 409 without writing anything, and deleting the
  account takes the link with it so the next note provisions afresh.

Why a random hash rather than a nullable column: `credential_secure_hash` is
`nullable=False`, and making it nullable puts a `None` in the path of
`verify_password` for every account in the system to accommodate accounts that
will never use it. A bcrypt hash of a string nobody holds can never match a
submitted password, which is the property wanted, and it is the recipe already
used by `security.py::ABSENT_ACCOUNT_HASH` for the same reason. It is generated
per account rather than shared, so a database dump does not identify the
federated rows by an identical hash. The link table is the record of
federation; the hash column is not.

`initial_login_state` is false because there is no initial password to move
off. `security.py::first_login_blocks` only holds `ORG_ADMIN` and `UNIT_ADMIN`,
and neither can be provisioned this way, so the gate could not catch a
federated account regardless; setting the flag correctly is about the field
meaning what it says, not about the gate.

### F-5. Administering the registry

- **Scope:** `GET`, `POST`, `PATCH`, `DELETE` under
  `/api/v1/federation/issuers`, plus nested routes for keys and the role map,
  and `POST /api/v1/federation/links` and `DELETE
  /api/v1/federation/links/{id}` to link an existing account to an
  `(issuer, subject)` pair and to unlink it again. The create route is the only
  way an account that already exists comes to use the shortcut, since the
  exchange itself never links on a matching address. `GET
  /api/v1/federation/links` is here too, added during the build and not in the
  first draft of this list: a link made by a first sign-in has an id nobody was
  ever told, so without it unlinking would mean reading the id out of the
  database by hand. The create route refuses an `ORG_ADMIN` or `UNIT_ADMIN`
  account, for the reason the role map excludes both roles, and F-3 refuses the
  sign-in for the same reason when an already-linked account is promoted later. `ORG_ADMIN`
  only: an issuer is organization-wide and a role map can place somebody in any
  unit, so a unit admin is the wrong scope for it. Scopes derive from the path,
  so `federation:read` and `federation:write` need no registration
  (`security.py::required_scope`). Public keys are readable; there are no
  secrets in this table.
- **Touches:** `backend/app/api/v1/endpoints/federation.py`,
  `backend/app/api/v1/router.py`, `backend/app/schemas/federation.py`,
  `docs/openapi.yaml`, both SDKs, `docs/api.md`.
- **Done when:** an `ORG_ADMIN` can add a key, retire it, link and unlink an
  account and delete an issuer; a `UNIT_ADMIN` gets 403 on all of it; a link to
  an `(issuer, subject)` pair that is already taken is refused with 409; and
  every write lands an audit record.

### F-6. It is visible when it goes wrong

- **Scope:** The exchange is a `POST` under `/api/v1/`, so
  `core/audit.py::AuditMiddleware` already records every attempt and how it
  ended, with no call sites to add. Two things on top of that. The service sets
  `request.state.actor_id` to the resolved account on success, the way
  `security.py` does for a bearer token, so the record names who got the
  session; on a first sign-in that reads as the new account having been created
  by its own arrival, which is what happened. And each refusal logs a WARNING
  naming the issuer, the `kid` and the reason, never the raw note.
- **Touches:** `backend/app/api/v1/endpoints/auth.py`,
  `backend/app/services/federated_identity.py`, `docs/api.md`.
- **Done when:** a successful exchange produces an audit record whose
  `actor_id` is the account, a refused one produces a record with a null actor
  and the refusing status, and each refusal reason appears once in the log.

Reasons live in the log rather than the audit table because `audit_records`
holds `method`, `path` and `status_code` and nothing free-form, on purpose: no
bodies, ever. Adding a reason column for one feature is the wrong trade. What
the table answers is how many attempts arrived and how they ended, which is the
question a flood raises; what the log answers is why a particular one failed,
which is the question an integrator raises.

### F-7. Where the person lands

- **Scope:** A page at `/auth/federated` that reads the note from the URL
  fragment, posts it once, and then does what the landing page already does
  with a `TokenResponse`: `saveSession(data)` and route by role
  (`frontend/src/store/auth.ts`). The fragment is cleared from the address bar
  before anything else happens, so a reload does not re-post a spent note and
  the note does not sit in the history. A refusal shows what went wrong in
  plain words with a link to sign in with a password instead, because a
  federated failure must not leave somebody with no way in.
- **Touches:** `frontend/src/app/auth/federated/page.tsx`,
  `frontend/src/store/auth.ts`, `frontend/src/lib/api.ts`.
- **Done when:** the page appears in the static export's route list, a spent
  note reloaded shows the refusal rather than a blank screen, and the fragment
  is gone from the address bar by the time the first request goes out.

Without this item the contract is backend-only and the URL-fragment reasoning in
the threat model describes something that does not exist. The integrating system
sends its person to `/auth/federated#token=...`; a fragment never reaches a
server, so it stays out of the proxy's access log and out of the `Referer` of
whatever the page loads next. There is nowhere else to put it: the frontend is a
static export with no server-side handler that could receive it.

### Settings

| Setting | Default | What it does |
|---|---|---|
| `FEDERATED_IDENTITY_ENABLED` | `false` | Off means the exchange route answers 404 |
| `FEDERATED_TOKEN_MAX_LIFETIME_SECONDS` | `120` | A note whose `exp` is further ahead is refused |
| `FEDERATED_CLOCK_SKEW_SECONDS` | `60` | How far `exp` may be past, and `iat` and `nbf` may be future |

Three settings, on the same reasoning as the rate limiter's: these are the
numbers an operator has an opinion about. The algorithm, the claim names and
the shape of the replay key are not settings.

### What the note has to contain

| Claim | Required | Checked against |
|---|---|---|
| `iss` | yes | The registration's `issuer` |
| `aud` | yes | The registration's `audience` |
| `sub` | yes | The link table, as `(issuer, subject)` |
| `jti` | yes | The replay cache |
| `iat` | yes | Not more than the skew in the future. No lower bound |
| `nbf` | no | Not more than the skew in the future, if present |
| `exp` | yes | Now, allowing the skew, and the lifetime cap |
| `email` | on first sign-in only | Refused if it belongs to an existing account |
| `name` | no | Stored as `full_name`, or the part of the address before the `@` |
| `groups` | no | The role map; no match means `MEMBER` |

The header must carry `kid`. `alg` is not consulted.

`groups` is a list of strings; a bare string is read as a list of one. Several
entries can match the map, and only two roles are reachable, so the rule is
short: `STAFF` beats `MEMBER`, and among the matching rows of the winning role
the oldest entry supplies the unit.

An earlier draft of this document promised that two matches both saying `STAFF`
with different `unit_code` values could never happen, because a validator would
refuse the pair when the map was written. That validator was dropped, and the
reason is worth recording: the pair it would refuse is the ordinary case. A
library and a lab each mapping their own staff group is what the map is for, and
somebody who belongs to both is not a misconfiguration. So the pair is allowed
and the tie is broken at sign-in, by entry age rather than by anything the note
controls, which keeps the answer the same however the issuer ordered its list.

### Build order

F-1, then F-2 with its refusal tests and no route yet, then F-4 in the same
service, then F-3 with F-6 folded into it, then F-5, then F-7. F-5 is last of
the backend items because it carries the spec tests and a regeneration of both
SDKs, and it is not optional for a release: without it the only way to register
an issuer is SQL against a running database.

---

## Stated assumptions

Three, written here rather than asked, because each has an answer that is
clearly better and reversing one is a small change:

1. **No new dependency.** `PyJWT[crypto]>=2.10.1` is already declared in
   `backend/pyproject.toml` and brings `cryptography`, so `EdDSA` is available
   with nothing added. Verified against the installed environment.
2. **The registry is a table, not environment variables.** Environment-only is
   simpler and costs no spec or SDK work, but it makes key rotation a restart
   and revocation a deploy, and rotation and revocation are two of the threats
   above. The cost is F-5: routes in `docs/openapi.yaml`, the spec tests, and a
   regeneration of both SDKs. That cost is known and paid routinely on this
   branch.
3. **A colliding email is refused, never linked.** The alternative is an
   account takeover path, so this is not really a choice; it is written down
   because somebody will eventually ask for the convenience and the answer
   needs to be on record.

## What this does not do

- No discovery, no JWKS fetch. Keys are registered, not downloaded. Fetching
  them would put an outbound HTTP call on the sign-in path and make an issuer's
  DNS part of Chronos's trust boundary.
- No SAML.
- No group membership sync. Groups are read once, when the account is created.
- No federating an issuer that has no email address for its people. The address
  is required on a first sign-in, because `email_address` is unique and not null
  on `User` and a synthesized one (`subject@issuer`, say) would be a real-looking
  address that reaches nobody, in the field an administrator uses to find a
  person and the system uses to write to them. An issuer in that position should
  be linked to accounts an administrator created.
- No outbound direction. Chronos does not issue notes other systems can verify.
- No QR codes, badges or kiosk shortcuts. The verification here is the support
  such things would need; whether any of them get built is a separate decision.
