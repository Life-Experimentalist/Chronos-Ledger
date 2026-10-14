// Copyright 2026 Chronos Ledger Contributors
// SPDX-License-Identifier: Apache-2.0
//
// Retries: which failures are tried again, how long they wait, and when they stop.

import assert from "node:assert/strict";
import { test } from "node:test";

import { ChronosError, createChronosClient } from "../src/index.ts";
import { chronosFetch, resolveRetry, type RetryOptions } from "../src/transport.ts";

type Answer = Response | Error;

const json = (status: number, body: unknown = {}, headers: Record<string, string> = {}) =>
  new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json", ...headers } });

const URL = "https://c.test/api/v1/resources/";

/** A stubbed fetch that plays `answers` in order (or one handler), with a clock that only sleeping moves. */
function harness(answers: Answer[] | ((request: Request) => Response), retry: RetryOptions | false = {}, random = () => 1) {
  const seen: Request[] = [];
  const waits: number[] = [];
  let clock = 1000;
  const queue = Array.isArray(answers) ? [...answers] : undefined;
  const fetch = (async (input: RequestInfo | URL, init?: RequestInit) => {
    const request = new Request(input, init);
    seen.push(request.clone());
    if (!queue) return (answers as (request: Request) => Response)(request);
    const answer = queue.shift()!;
    if (answer instanceof Error) throw answer;
    return answer;
  }) as typeof globalThis.fetch;
  const send = chronosFetch({
    baseUrl: "https://c.test",
    apiKey: "k",
    retry: resolveRetry(retry),
    fetch,
    sleep: async (ms) => {
      waits.push(ms);
      clock += ms;
    },
    now: () => clock,
    random,
  });
  const keys = () => seen.map((r) => r.headers.get("Idempotency-Key"));
  return { seen, waits, send, keys, fetch };
}

const post = (headers: Record<string, string> = {}) =>
  new Request(URL, { method: "POST", body: JSON.stringify({ code: "R1" }), headers: { "Content-Type": "application/json", ...headers } });

test("a dropped response is retried and the create goes out under one key", async () => {
  const h = harness([new TypeError("fetch failed"), json(201, { id: 7, resource_id: 3 })]);
  const chronos = createChronosClient({ baseUrl: "https://c.test", apiKey: "k", fetch: ((input: Request) => h.send(input)) as typeof globalThis.fetch });
  const hold = await chronos.createReservation(3, { date: "2026-01-06", start: "14:00", end: "15:00", purpose: "Viva" });
  assert.equal(hold.id, 7);
  assert.equal(h.seen.length, 2);
  const [first, second] = h.keys();
  assert.ok(first);
  assert.equal(first, second);
});

test("a write the caller gave no key gets one and keeps it across retries", async () => {
  const h = harness([json(503), json(503), json(200)]);
  const response = await h.send(post());
  assert.equal(response.status, 200);
  const [first, second, third] = h.keys();
  assert.match(first!, /^[0-9a-f-]{36}$/);
  assert.equal(first, second);
  assert.equal(first, third);
});

for (const method of ["POST", "PATCH", "PUT", "DELETE"]) {
  test(`a ${method} is never sent without a key`, async () => {
    const h = harness([json(200)]);
    await h.send(new Request(URL, { method, body: method === "DELETE" ? null : "{}" }));
    assert.ok(h.keys()[0]);
  });
}

test("a key the caller chose is kept", async () => {
  const h = harness([json(502), json(200)]);
  await h.send(post({ "Idempotency-Key": "mine-12345" }));
  assert.deepEqual(h.keys(), ["mine-12345", "mine-12345"]);
});

test("a read carries no key", async () => {
  const h = harness([json(200, [])]);
  await h.send(new Request(URL));
  assert.deepEqual(h.keys(), [null]);
});

for (const status of [400, 401, 403, 404, 409, 422]) {
  test(`a ${status} is never retried`, async () => {
    const h = harness(() => json(status, { detail: "no", code: "SOME_CODE" }));
    await assert.rejects(h.send(post()), { status, code: "SOME_CODE" });
    assert.equal(h.seen.length, 1);
    assert.deepEqual(h.waits, []);
  });
}

for (const status of [429, 502, 503, 504]) {
  test(`a ${status} is retried for reads and writes`, async () => {
    for (const request of [new Request(URL), post()]) {
      const h = harness([json(status), json(200)]);
      assert.equal((await h.send(request)).status, 200);
      assert.equal(h.seen.length, 2);
    }
  });
}

test("a 409 while the first request is running is retried with the same key", async () => {
  const h = harness([json(409, { detail: "still running", code: "IDEMPOTENCY_KEY_IN_PROGRESS" }), json(201)]);
  assert.equal((await h.send(post())).status, 201);
  const [first, second] = h.keys();
  assert.equal(first, second);
});

test("a 503 with Retry-After waits that long", async () => {
  const h = harness([json(503, {}, { "Retry-After": "7" }), json(200)]);
  await h.send(new Request(URL));
  assert.deepEqual(h.waits, [7000]);
});

test("Retry-After as an HTTP date is honoured", async () => {
  const later = new Date(Date.now() + 5000).toUTCString();
  const h = harness([json(429, {}, { "Retry-After": later }), json(200)]);
  await h.send(new Request(URL));
  assert.equal(h.waits.length, 1);
  assert.ok(h.waits[0]! > 3000 && h.waits[0]! <= 5000);
});

test("a Retry-After past the deadline ends retrying with the last error", async () => {
  const h = harness(() => json(429, { detail: "slow", code: "RATE_LIMITED" }, { "Retry-After": "60" }), { deadlineMs: 30_000 });
  await assert.rejects(h.send(new Request(URL)), { status: 429, code: "RATE_LIMITED" });
  assert.equal(h.seen.length, 1);
  assert.deepEqual(h.waits, []);
});

test("backoff is full jitter over a doubling ceiling capped by maxDelayMs", async () => {
  const retry = { maxAttempts: 6, baseDelayMs: 250, maxDelayMs: 1000, deadlineMs: 1_000_000 };
  const full = harness(() => json(503), retry, () => 1);
  await assert.rejects(full.send(new Request(URL)), { status: 503 });
  assert.deepEqual(full.waits, [250, 500, 1000, 1000, 1000]);
  const half = harness(() => json(503), retry, () => 0.5);
  await assert.rejects(half.send(new Request(URL)), { status: 503 });
  assert.deepEqual(half.waits, [125, 250, 500, 500, 500]);
});

test("the deadline stops retrying before the attempts run out", async () => {
  const h = harness(() => json(503, { detail: "down" }), { maxAttempts: 10, baseDelayMs: 4000, maxDelayMs: 8000, deadlineMs: 10_000 });
  await assert.rejects(h.send(new Request(URL)), { status: 503 });
  // Waits of 4 s and 8 s: the first fits in 10 s, the second would end at 12 s.
  assert.deepEqual(h.waits, [4000]);
  assert.equal(h.seen.length, 2);
});

test("attempts run out and the last error is thrown", async () => {
  const h = harness(() => json(502, { detail: "bad gateway" }), { maxAttempts: 3 });
  await assert.rejects(h.send(new Request(URL)), (error: ChronosError) => {
    assert.equal(error.status, 502);
    assert.equal(error.detail, "bad gateway");
    return true;
  });
  assert.equal(h.seen.length, 3);
});

test("a network error is thrown as it came when attempts run out", async () => {
  const failure = new TypeError("fetch failed");
  const h = harness([failure, failure], { maxAttempts: 2 });
  await assert.rejects(h.send(new Request(URL)), (error) => error === failure);
  assert.equal(h.seen.length, 2);
});

test("the caller's own abort is not retried", async () => {
  const controller = new AbortController();
  controller.abort();
  const h = harness([new DOMException("aborted", "AbortError"), json(200)]);
  await assert.rejects(h.send(new Request(URL, { signal: controller.signal })), { name: "AbortError" });
  assert.equal(h.seen.length, 1);
});

test("retry: false turns retries off, but a write still carries a key", async () => {
  const h = harness(() => json(503, { detail: "down" }), false);
  await assert.rejects(h.send(post()), { status: 503 });
  assert.equal(h.seen.length, 1);
  assert.ok(h.keys()[0]);
});

test("createChronosClient passes the retry settings on", async () => {
  let calls = 0;
  const fetch = (async () => (++calls < 3 ? json(503) : json(200, []))) as typeof globalThis.fetch;
  const chronos = createChronosClient({ baseUrl: "https://c.test", apiKey: "k", retry: { maxAttempts: 3, baseDelayMs: 0 }, fetch });
  const { response } = await chronos.GET("/api/v1/resources/");
  assert.equal(response.status, 200);
  assert.equal(calls, 3);
});

test("settings that cannot work are refused", () => {
  assert.throws(() => resolveRetry({ maxAttempts: 0 }), RangeError);
  assert.throws(() => resolveRetry({ baseDelayMs: -1 }), RangeError);
  assert.equal(resolveRetry(false), null);
});

test("the retried body is the same body", async () => {
  const h = harness([json(503), json(200)]);
  await h.send(post());
  const bodies = await Promise.all(h.seen.map((r) => r.json()));
  assert.deepEqual(bodies, [{ code: "R1" }, { code: "R1" }]);
});

const upload = () => {
  const form = new FormData();
  form.set("file", new Blob(["member_id,unit\n1,A\n"], { type: "text/csv" }), "matrix.csv");
  return new Request("https://c.test/api/v1/ingestion/upload-csv", { method: "POST", body: form });
};

test("a file upload is sent once even when the status is retryable", async () => {
  const h = harness([json(503, { detail: "down" }), json(200)]);
  await assert.rejects(h.send(upload()), { status: 503 });
  assert.equal(h.seen.length, 1);
  assert.deepEqual(h.waits, []);
  assert.ok(h.keys()[0]); // the upload still carries a key, like any write
});

test("a file upload is sent once when no response arrives", async () => {
  const failure = new TypeError("fetch failed");
  const h = harness([failure, json(200)]);
  await assert.rejects(h.send(upload()), (error) => error === failure);
  assert.equal(h.seen.length, 1);
  assert.deepEqual(h.waits, []);
});

for (const [name, value] of [["negative", "-5"], ["NaN", "nan"]] as const) {
  test(`a ${name} Retry-After falls back to the jittered wait`, async () => {
    const h = harness([json(503, {}, { "Retry-After": value }), json(200)]);
    await h.send(new Request(URL));
    assert.deepEqual(h.waits, [250]); // random() is 1, so the ceiling of the first retry
  });
}
