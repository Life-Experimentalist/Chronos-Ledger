// Copyright 2026 Chronos Ledger Contributors
// SPDX-License-Identifier: Apache-2.0

import assert from "node:assert/strict";
import { test } from "node:test";

import { ChronosError, createChronosClient, paginate, VERSION } from "../src/index.ts";
import { chronosFetch, retryAfter } from "../src/transport.ts";

type Handler = (request: Request) => Response | Promise<Response>;

/** A fetch that records each request and answers from `handler`. */
function server(handler: Handler) {
  const seen: Request[] = [];
  const fetch = (async (input: RequestInfo | URL, init?: RequestInit) => {
    const request = new Request(input, init);
    seen.push(request.clone());
    return handler(request);
  }) as typeof globalThis.fetch;
  return { seen, fetch };
}

const json = (status: number, body: unknown, headers: Record<string, string> = {}) =>
  new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json", ...headers } });

const noSleep = async () => {};

test("an API key goes out as X-API-Key with the user agent", async () => {
  const { seen, fetch } = server(() => json(200, []));
  const chronos = createChronosClient({ baseUrl: "https://c.test/api/v1/", apiKey: "k1", fetch });
  await chronos.GET("/api/v1/resources/");
  assert.equal(seen.length, 1);
  assert.equal(seen[0]!.url, "https://c.test/api/v1/resources/");
  assert.equal(seen[0]!.headers.get("X-API-Key"), "k1");
  assert.equal(seen[0]!.headers.get("User-Agent"), `chronos-ts/${VERSION}`);
  assert.equal(seen[0]!.headers.get("Authorization"), null);
});

test("a 401 refreshes once, stores the new pair and repeats the call", async () => {
  const { seen, fetch } = server(async (request) => {
    if (request.url.endsWith("/auth/refresh")) {
      assert.deepEqual(await request.json(), { refresh_token: "r1" });
      return json(200, { access_token: "a2", refresh_token: "r2", token_type: "bearer" });
    }
    return request.headers.get("Authorization") === "Bearer a2" ? json(200, []) : json(401, { detail: "expired" });
  });
  const stored: unknown[] = [];
  const chronos = createChronosClient({
    baseUrl: "https://c.test",
    tokens: { accessToken: "a1", refreshToken: "r1" },
    onTokens: (tokens) => void stored.push(tokens),
    fetch,
  });
  const { response } = await chronos.GET("/api/v1/resources/");
  assert.equal(response.status, 200);
  assert.deepEqual(stored, [{ accessToken: "a2", refreshToken: "r2" }]);
  assert.equal(seen.length, 3);
});

test("a refused refresh ends in the original 401, without looping", async () => {
  const { seen, fetch } = server(() => json(401, { detail: "Not authorized." }));
  const chronos = createChronosClient({ baseUrl: "https://c.test", tokens: { accessToken: "a", refreshToken: "r" }, fetch });
  await assert.rejects(chronos.GET("/api/v1/resources/"), (error: ChronosError) => {
    assert.equal(error.status, 401);
    assert.equal(error.detail, "Not authorized.");
    return true;
  });
  assert.equal(seen.length, 2);
});

test("requests that see a 401 together spend the refresh token once", async () => {
  let refreshes = 0;
  const { fetch } = server(async (request) => {
    if (request.url.endsWith("/auth/refresh")) {
      refreshes++;
      await new Promise((resolve) => setTimeout(resolve, 10));
      return json(200, { access_token: "a2", refresh_token: "r2" });
    }
    return request.headers.get("Authorization") === "Bearer a2" ? json(200, []) : json(401, { detail: "expired" });
  });
  const chronos = createChronosClient({ baseUrl: "https://c.test", tokens: { accessToken: "a1", refreshToken: "r1" }, fetch });
  await Promise.all([chronos.GET("/api/v1/resources/"), chronos.GET("/api/v1/users/"), chronos.GET("/api/v1/resources/")]);
  assert.equal(refreshes, 1);
});

test("a 429 waits for Retry-After, then succeeds", async () => {
  const waits: number[] = [];
  let calls = 0;
  const { fetch } = server(() => (++calls === 1 ? json(429, { detail: "slow down" }, { "Retry-After": "2" }) : json(200, [])));
  const send = chronosFetch({ baseUrl: "https://c.test", maxRetries: 3, fetch, sleep: async (ms) => void waits.push(ms) });
  const response = await send(new Request("https://c.test/api/v1/resources/"));
  assert.equal(response.status, 200);
  assert.deepEqual(waits, [2000]);
});

test("retries stop after maxRetries and raise the last error", async () => {
  const { seen, fetch } = server(() => json(503, { detail: "down" }));
  const send = chronosFetch({ baseUrl: "https://c.test", maxRetries: 2, fetch, sleep: noSleep });
  await assert.rejects(send(new Request("https://c.test/api/v1/resources/")), { status: 503 });
  assert.equal(seen.length, 3);
});

test("a POST without an Idempotency-Key is never retried", async () => {
  const { seen, fetch } = server(() => json(503, { detail: "down" }));
  const send = chronosFetch({ baseUrl: "https://c.test", maxRetries: 3, fetch, sleep: noSleep });
  const request = new Request("https://c.test/api/v1/resources/", { method: "POST", body: "{}" });
  await assert.rejects(send(request), { status: 503 });
  assert.equal(seen.length, 1);
});

test("createReservation makes one key and sends it again on a retry", async () => {
  let calls = 0;
  const { seen, fetch } = server(() =>
    ++calls === 1 ? json(502, { detail: "bad gateway" }) : json(201, { id: 7, resource_id: 3 }),
  );
  const send = chronosFetch({ baseUrl: "https://c.test", maxRetries: 3, fetch, sleep: noSleep });
  const chronos = createChronosClient({ baseUrl: "https://c.test", apiKey: "k", fetch: ((input: Request) => send(input)) as typeof globalThis.fetch });
  const hold = await chronos.createReservation(3, { date: "2026-01-06", start: "14:00", end: "15:00", purpose: "Viva" });
  assert.equal(hold.id, 7);
  assert.equal(seen.length, 2);
  const [first, second] = seen.map((r) => r.headers.get("Idempotency-Key"));
  assert.match(first!, /^[0-9a-f-]{36}$/);
  assert.equal(first, second);
  assert.deepEqual(await seen[1]!.json(), { date: "2026-01-06", start: "14:00", end: "15:00", purpose: "Viva" });
});

test("a 409 carries the conflicts it names", async () => {
  const busy = [{ date: "2026-01-06", start: "14:00", end: "15:00", reservation_id: 4 }];
  const { fetch } = server(() => json(409, { detail: { message: "the resource is already taken", conflicts: busy } }));
  const chronos = createChronosClient({ baseUrl: "https://c.test", apiKey: "k", fetch });
  await assert.rejects(
    chronos.createReservation(3, { date: "2026-01-06", start: "14:00", end: "15:00", purpose: "Viva" }, "key-12345"),
    (error: ChronosError) => {
      assert.equal(error.status, 409);
      assert.equal(error.message, "409: the resource is already taken");
      assert.deepEqual(error.conflicts, busy);
      return true;
    },
  );
});

test("paginate walks limit and offset until X-Total-Count", async () => {
  const rows = [1, 2, 3, 4, 5].map((id) => ({ id }));
  const { seen, fetch } = server((request) => {
    const url = new URL(request.url);
    const limit = Number(url.searchParams.get("limit"));
    const offset = Number(url.searchParams.get("offset"));
    return json(200, rows.slice(offset, offset + limit), { "X-Total-Count": String(rows.length) });
  });
  const chronos = createChronosClient({ baseUrl: "https://c.test", apiKey: "k", fetch });
  const ids: unknown[] = [];
  for await (const user of paginate((limit, offset) => chronos.GET("/api/v1/users/", { params: { query: { limit, offset } } }), 2)) {
    ids.push((user as { id: unknown }).id);
  }
  assert.deepEqual(ids, [1, 2, 3, 4, 5]);
  assert.equal(seen.length, 3);
});

test("Retry-After reads seconds and HTTP dates", () => {
  assert.equal(retryAfter(new Response(null, { headers: { "Retry-After": "3" } })), 3000);
  const later = new Date(Date.now() + 5000).toUTCString();
  const ms = retryAfter(new Response(null, { headers: { "Retry-After": later } }))!;
  assert.ok(ms > 3000 && ms <= 5000);
  assert.equal(retryAfter(new Response(null)), undefined);
});

test("a non-JSON error body is kept as text", async () => {
  const { fetch } = server(() => new Response("<html>bad gateway</html>", { status: 400 }));
  const chronos = createChronosClient({ baseUrl: "https://c.test", apiKey: "k", fetch });
  await assert.rejects(chronos.GET("/api/v1/resources/"), { status: 400, detail: "<html>bad gateway</html>" });
});
