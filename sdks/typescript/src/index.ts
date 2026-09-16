// Copyright 2026 Chronos Ledger Contributors
// SPDX-License-Identifier: Apache-2.0

import createClient from "openapi-fetch";

import type { components, paths } from "./generated/schema.ts";
import { chronosFetch, type Tokens } from "./transport.ts";

export { ChronosError, type Conflict } from "./errors.ts";
export { paginate } from "./paginate.ts";
export type { Tokens } from "./transport.ts";
export { VERSION } from "./version.ts";
export type { components, operations, paths } from "./generated/schema.ts";

export interface ChronosOptions {
  /** Where the server is, for example `https://chronos.example.org`. Paths carry `/api/v1`. */
  baseUrl: string;
  /** A scoped API key, sent as `X-API-Key`. */
  apiKey?: string;
  /** Tokens from `POST /api/v1/auth/login`. Refreshed once on a 401. */
  tokens?: Tokens;
  /** Called with each refreshed pair, so it can be stored. */
  onTokens?: (tokens: Tokens) => void | Promise<void>;
  /** Retries for 429, 502, 503, 504 and network errors. Default 3. */
  maxRetries?: number;
  /** The underlying fetch. Defaults to the global one. */
  fetch?: typeof globalThis.fetch;
}

export type ReservationCreate = components["schemas"]["ReservationCreate"];
export type ReservationResponse = components["schemas"]["ReservationResponse"];

export function createChronosClient(options: ChronosOptions) {
  if (options.apiKey && options.tokens) {
    throw new Error("pass apiKey or tokens, not both");
  }
  const baseUrl = options.baseUrl.replace(/\/+$/, "").replace(/\/api\/v1$/, "");
  const client = createClient<paths>({
    baseUrl,
    fetch: chronosFetch({
      baseUrl,
      apiKey: options.apiKey,
      tokens: options.tokens,
      onTokens: options.onTokens,
      maxRetries: options.maxRetries ?? 3,
      fetch: options.fetch ?? globalThis.fetch.bind(globalThis),
      sleep: (ms) => new Promise((resolve) => setTimeout(resolve, ms)),
    }),
  });

  return Object.assign(client, {
    /**
     * Hold a resource. An Idempotency-Key is made when none is given, and the
     * same key goes out on every retry, so a retry never takes a second hold.
     */
    async createReservation(
      resourceId: number,
      body: ReservationCreate,
      idempotencyKey: string = crypto.randomUUID(),
    ): Promise<ReservationResponse> {
      const { data } = await client.POST("/api/v1/resources/{resource_id}/reservations", {
        params: { path: { resource_id: resourceId }, header: { "Idempotency-Key": idempotencyKey } },
        body,
      });
      return data!;
    },
  });
}

export type ChronosClient = ReturnType<typeof createChronosClient>;
