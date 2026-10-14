// Copyright 2026 Chronos Ledger Contributors
// SPDX-License-Identifier: Apache-2.0

import { ChronosError } from "./errors.ts";
import { VERSION } from "./version.ts";

/** An access token and the single-use refresh token that came with it. */
export interface Tokens {
  accessToken: string;
  refreshToken: string;
}

/** How a failed request is tried again. Pass `retry: false` to turn retries off. */
export interface RetryOptions {
  /** Tries in all, the first one included. Default 4. */
  maxAttempts?: number;
  /** The wait before retry `n` is random between 0 and `baseDelayMs * 2 ** n`. Default 250. */
  baseDelayMs?: number;
  /** The most any one jittered wait can reach. Default 8000. */
  maxDelayMs?: number;
  /** Milliseconds from the first send. No retry starts a wait that would run past it. Default 30000. */
  deadlineMs?: number;
}

export type RetryPolicy = Required<RetryOptions>;

export const DEFAULT_RETRY: RetryPolicy = { maxAttempts: 4, baseDelayMs: 250, maxDelayMs: 8_000, deadlineMs: 30_000 };

/** Fills in the defaults and refuses values that cannot work. `false` means no retries. */
export function resolveRetry(retry: RetryOptions | false | undefined): RetryPolicy | null {
  if (retry === false) return null;
  const policy: RetryPolicy = {
    maxAttempts: retry?.maxAttempts ?? DEFAULT_RETRY.maxAttempts,
    baseDelayMs: retry?.baseDelayMs ?? DEFAULT_RETRY.baseDelayMs,
    maxDelayMs: retry?.maxDelayMs ?? DEFAULT_RETRY.maxDelayMs,
    deadlineMs: retry?.deadlineMs ?? DEFAULT_RETRY.deadlineMs,
  };
  if (!Number.isInteger(policy.maxAttempts) || policy.maxAttempts < 1) {
    throw new RangeError("maxAttempts must be a whole number, at least 1");
  }
  if (Math.min(policy.baseDelayMs, policy.maxDelayMs, policy.deadlineMs) < 0) {
    throw new RangeError("delays and the deadline cannot be negative");
  }
  return policy;
}

export interface TransportOptions {
  baseUrl: string;
  apiKey?: string;
  tokens?: Tokens;
  /** Called with each new pair. A refresh token works once, so store the new one. */
  onTokens?: (tokens: Tokens) => void | Promise<void>;
  /** Null for no retries. */
  retry: RetryPolicy | null;
  fetch: typeof globalThis.fetch;
  sleep: (ms: number) => Promise<void>;
  /** A monotonic clock in milliseconds. Defaults to `performance.now`. */
  now?: () => number;
  /** A number in [0, 1). Defaults to `Math.random`. */
  random?: () => number;
}

const RETRY_STATUSES = new Set([429, 502, 503, 504]);
/** The code of a 409 that says the first request under this key is still running. */
const IN_PROGRESS_CODE = "IDEMPOTENCY_KEY_IN_PROGRESS";
/** Methods that change nothing. Every other method is a write and goes out with an Idempotency-Key. */
const READ_METHODS = new Set(["GET", "HEAD", "OPTIONS"]);
/** A file upload goes out as this content type. Its body is sent once and never retried. */
const MULTIPART_PREFIX = "multipart/";
const USER_AGENT = `chronos-ts/${VERSION}`;

/** The `fetch` handed to openapi-fetch. Auth, retries and errors happen here. */
export function chronosFetch(options: TransportOptions): (request: Request) => Promise<Response> {
  let tokens = options.tokens;
  let refreshing: Promise<boolean> | undefined;

  const now = options.now ?? (() => performance.now());
  const random = options.random ?? Math.random;

  const authorize = (request: Request, idempotencyKey: string | undefined): Request => {
    const out = request.clone();
    out.headers.set("User-Agent", USER_AGENT);
    if (idempotencyKey) out.headers.set("Idempotency-Key", idempotencyKey);
    if (options.apiKey) out.headers.set("X-API-Key", options.apiKey);
    else if (tokens) out.headers.set("Authorization", `Bearer ${tokens.accessToken}`);
    return out;
  };

  // Shared by every request that sees a 401 at the same time. A refresh token
  // is spent on first use, so a second refresh would sign the caller out.
  const refresh = (current: Tokens): Promise<boolean> => {
    refreshing ??= (async () => {
      // Any failure here ends in the caller's original 401, not in a new error.
      let body: { access_token?: unknown; refresh_token?: unknown };
      try {
        const response = await options.fetch(`${options.baseUrl}/api/v1/auth/refresh`, {
          method: "POST",
          headers: { "Content-Type": "application/json", "User-Agent": USER_AGENT },
          body: JSON.stringify({ refresh_token: current.refreshToken }),
        });
        if (!response.ok) {
          await response.body?.cancel();
          return false;
        }
        body = (await response.json()) as typeof body;
      } catch {
        return false;
      }
      if (typeof body?.access_token !== "string" || typeof body.refresh_token !== "string") return false;
      tokens = { accessToken: body.access_token, refreshToken: body.refresh_token };
      await options.onTokens?.(tokens);
      return true;
    })().finally(() => {
      refreshing = undefined;
    });
    return refreshing;
  };

  return async (request: Request): Promise<Response> => {
    // One key for the whole call, so every try of a write is the same write.
    const idempotencyKey =
      READ_METHODS.has(request.method) || request.headers.has("Idempotency-Key") ? undefined : crypto.randomUUID();
    // A file upload is sent once: no retry and no resend after a token refresh.
    const repeatable = !request.headers.get("Content-Type")?.toLowerCase().startsWith(MULTIPART_PREFIX);
    const started = now();
    let refreshed = false;
    let attempt = 0;

    /** Milliseconds to sleep before the next try, or undefined when this failure is final. */
    const waitFor = (response?: Response): number | undefined => {
      const policy = options.retry;
      if (!policy || !repeatable || attempt + 1 >= policy.maxAttempts) return undefined;
      const ceiling = Math.min(policy.maxDelayMs, policy.baseDelayMs * 2 ** attempt);
      const wait = (response && retryAfter(response)) ?? random() * ceiling;
      return now() + wait - started > policy.deadlineMs ? undefined : wait;
    };
    /** Sleeps, unless the caller gave up while this was waiting. */
    const pause = async (wait: number): Promise<void> => {
      await options.sleep(wait);
      request.signal.throwIfAborted();
      attempt++;
    };

    for (;;) {
      const sentWith = tokens;
      let response: Response;
      try {
        response = await options.fetch(authorize(request, idempotencyKey));
      } catch (error) {
        // The caller's own abort or timeout is an answer, not a failure to retry.
        const wait = request.signal.aborted ? undefined : waitFor();
        if (wait === undefined) throw error;
        await pause(wait);
        continue;
      }

      if (response.status === 401 && sentWith && !options.apiKey && !refreshed && repeatable) {
        refreshed = true;
        // Another request may have refreshed while this one was out.
        if (sentWith !== tokens || (await refresh(sentWith))) {
          await response.body?.cancel();
          continue;
        }
      }
      if (response.status < 400) return response;
      const error = await ChronosError.fromResponse(response);
      if (RETRY_STATUSES.has(response.status) || error.code === IN_PROGRESS_CODE) {
        const wait = waitFor(response);
        if (wait !== undefined) {
          await pause(wait);
          continue;
        }
      }
      throw error;
    }
  };
}

/** Milliseconds from a Retry-After header, given in seconds or as an HTTP date. */
export function retryAfter(response: Response): number | undefined {
  const value = response.headers.get("Retry-After");
  if (!value) return undefined;
  const seconds = Number(value);
  // A negative or NaN value is not a wait: the caller falls back to the jittered one.
  if (!Number.isNaN(seconds)) return seconds < 0 ? undefined : Math.min(seconds, 1e9) * 1000;
  const date = Date.parse(value);
  return Number.isNaN(date) ? undefined : Math.max(0, date - Date.now());
}
