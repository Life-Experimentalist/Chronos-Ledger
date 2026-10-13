// Copyright 2026 Chronos Ledger Contributors
// SPDX-License-Identifier: Apache-2.0

/** One interval that stood in the way of a write refused with 409. */
export interface Conflict {
  [field: string]: unknown;
}

/**
 * Every response with status 400 or above, after retries and a token refresh
 * have been tried, arrives as this error.
 */
export class ChronosError extends Error {
  readonly status: number;
  /** `detail` exactly as the server returned it: a string, or an object for a 409. */
  readonly detail: unknown;
  /**
   * The server's code for what went wrong, such as `"EMAIL_TAKEN"`, for a
   * program to branch on. A plain string rather than the generated ErrorCode
   * union, so a code added after this client was built still arrives. Null
   * when the body had no code, for example a proxy's error page.
   */
  readonly code: string | null;
  /** The clashing intervals of a 409, or an empty list. */
  readonly conflicts: Conflict[];

  constructor(status: number, detail: unknown, code: string | null = null) {
    super(describe(status, detail));
    this.name = "ChronosError";
    this.status = status;
    this.detail = detail;
    this.code = code;
    const found = (detail as { conflicts?: unknown } | null)?.conflicts;
    this.conflicts = Array.isArray(found) ? (found as Conflict[]) : [];
  }

  static async fromResponse(response: Response): Promise<ChronosError> {
    const text = await response.text();
    let detail: unknown = text || null;
    let code: string | null = null;
    try {
      const body = JSON.parse(text) as unknown;
      detail = body && typeof body === "object" && "detail" in body ? body.detail : body;
      const found = body && typeof body === "object" && "code" in body ? body.code : null;
      code = typeof found === "string" ? found : null;
    } catch {
      // Not JSON, for example an HTML page from a proxy: keep the text.
    }
    return new ChronosError(response.status, detail, code);
  }
}

function describe(status: number, detail: unknown): string {
  if (typeof detail === "string") return `${status}: ${detail}`;
  const message = (detail as { message?: unknown } | null)?.message;
  return typeof message === "string" ? `${status}: ${message}` : `HTTP ${status}`;
}
