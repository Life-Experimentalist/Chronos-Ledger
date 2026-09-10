// Copyright 2026 Chronos Ledger Contributors
// Licensed under the Apache License, Version 2.0

/**
 * One reading of FastAPI's `detail`, which is not one shape.
 *
 * A raised HTTPException puts a string there. A validation failure puts a list
 * of `{loc, msg, type}` there, and `detail ?? fallback` renders that list as
 * `[object Object]`, because an array is truthy and every fallback in this app
 * was written expecting a string. A conflict on this API puts an object there
 * describing the clash in fields the caller is meant to read rather than
 * print, so that one falls through to the sentence the caller supplied.
 */
export function apiErrorMessage(error: unknown, fallback: string): string {
  const detail = (error as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail

  if (typeof detail === 'string' && detail.trim()) return detail

  if (Array.isArray(detail)) {
    const messages = detail
      .map((item) => (item as { msg?: unknown })?.msg)
      .filter((msg): msg is string => typeof msg === 'string' && msg.trim().length > 0)
      // Pydantic prefixes anything a custom validator raised. The sentence
      // after the prefix was written to be read; the prefix was not.
      .map((msg) => msg.replace(/^Value error, /, ''))
    if (messages.length) return messages.join('. ')
  }

  return fallback
}
