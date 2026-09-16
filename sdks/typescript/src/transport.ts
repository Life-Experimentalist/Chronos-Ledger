// Copyright 2026 Chronos Ledger Contributors
// SPDX-License-Identifier: Apache-2.0

import { ChronosError } from "./errors.ts";
import { VERSION } from "./version.ts";

/** An access token and the single-use refresh token that came with it. */
export interface Tokens {
  accessToken: string;
  refreshToken: string;
}

export interface TransportOptions {
  baseUrl: string;
  apiKey?: string;
  tokens?: Tokens;
  /** Called with each new pair. A refresh token works once, so store the new one. */
  onTokens?: (tokens: Tokens) => void | Promise<void>;
  maxRetries: number;
  fetch: typeof globalThis.fetch;
  sleep: (ms: number) => Promise<void>;
}

const RETRY_STATUSES = new Set([429, 502, 503, 504]);
const IDEMPOTENT_METHODS = new Set(["GET", "HEAD", "PUT", "DELETE", "OPTIONS"]);
const MAX_DELAY_MS = 30_000;
const USER_AGENT = `chronos-ts/${VERSION}`;

/** The `fetch` handed to openapi-fetch. Auth, retries and errors happen here. */
export function chronosFetch(options: TransportOptions): (request: Request) => Promise<Response> {
  let tokens = options.tokens;
  let refreshing: Promise<boolean> | undefined;

  const authorize = (request: Request): Request => {
    const out = request.clone();
    out.headers.set("User-Agent", USER_AGENT);
    if (options.apiKey) out.headers.set("X-API-Key", options.apiKey);
    else if (tokens) out.headers.set("Authorization", `Bearer ${tokens.accessToken}`);
    return out;
  };

  // Shared by every request that sees a 401 at the same time. A refresh token
  // is spent on first use, so a second refresh would sign the caller out.
  const refresh = (current: Tokens): Promise<boolean> => {
    refreshing ??= (async () => {
      const response = await options.fetch(`${options.baseUrl}/api/v1/auth/refresh`, {
        method: "POST",
        headers: { "Content-Type": "application/json", "User-Agent": USER_AGENT },
        body: JSON.stringify({ refresh_token: current.refreshToken }),
      });
      if (!response.ok) {
        await response.body?.cancel();
        return false;
      }
      const body = (await response.json()) as { access_token: string; refresh_token: string };
      tokens = { accessToken: body.access_token, refreshToken: body.refresh_token };
      await options.onTokens?.(tokens);
      return true;
    })().finally(() => {
      refreshing = undefined;
    });
    return refreshing;
  };

  return async (request: Request): Promise<Response> => {
    const retryable = IDEMPOTENT_METHODS.has(request.method) || request.headers.has("Idempotency-Key");
    let refreshed = false;
    let attempt = 0;
    for (;;) {
      const sentWith = tokens;
      let response: Response;
      try {
        response = await options.fetch(authorize(request));
      } catch (error) {
        if (!retryable || attempt >= options.maxRetries) throw error;
        await options.sleep(backoff(attempt++));
        continue;
      }

      if (response.status === 401 && sentWith && !options.apiKey && !refreshed) {
        refreshed = true;
        // Another request may have refreshed while this one was out.
        if (sentWith !== tokens || (await refresh(sentWith))) {
          await response.body?.cancel();
          continue;
        }
      }
      if (RETRY_STATUSES.has(response.status) && retryable && attempt < options.maxRetries) {
        const wait = retryAfter(response) ?? backoff(attempt);
        if (wait <= MAX_DELAY_MS) {
          await response.body?.cancel();
          await options.sleep(wait);
          attempt++;
          continue;
        }
      }
      if (response.status >= 400) throw await ChronosError.fromResponse(response);
      return response;
    }
  };
}

function backoff(attempt: number): number {
  return Math.min(500 * 2 ** attempt, 8_000);
}

/** Milliseconds from a Retry-After header, given in seconds or as an HTTP date. */
export function retryAfter(response: Response): number | undefined {
  const value = response.headers.get("Retry-After");
  if (!value) return undefined;
  const seconds = Number(value);
  if (Number.isFinite(seconds)) return Math.max(0, seconds * 1000);
  const date = Date.parse(value);
  return Number.isNaN(date) ? undefined : Math.max(0, date - Date.now());
}
