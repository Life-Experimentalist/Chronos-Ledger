// Copyright 2026 Chronos Ledger Contributors (Apache 2.0)
//
// Lightweight telemetry via CFlair-Counter (Life-Experimentalist/CFlair-Counter).
// Sends anonymous view counts, no PII, no session tracking.
//
// Opt-out: Admin → Settings → Privacy → disable telemetry.
// The opt-out preference is stored in localStorage under `chronos_telemetry_opted_out`.
// Set NEXT_PUBLIC_TELEMETRY_ENABLED=false at build time to disable permanently.

const ENDPOINT = process.env.NEXT_PUBLIC_TELEMETRY_ENDPOINT ?? ''
const GLOBALLY_ENABLED = process.env.NEXT_PUBLIC_TELEMETRY_ENABLED !== 'false'

const OPT_OUT_KEY = 'chronos_telemetry_opted_out'

export function isTelemetryEnabled(): boolean {
  if (!GLOBALLY_ENABLED || !ENDPOINT) return false
  if (typeof window === 'undefined') return false
  return localStorage.getItem(OPT_OUT_KEY) !== 'true'
}

export function setTelemetryOptOut(optOut: boolean): void {
  if (typeof window === 'undefined') return
  if (optOut) {
    localStorage.setItem(OPT_OUT_KEY, 'true')
  } else {
    localStorage.removeItem(OPT_OUT_KEY)
  }
}

/**
 * Record a named view event. Fire-and-forget, never throws, never blocks.
 * Only sends if telemetry is enabled and globally configured.
 *
 * @param page  Suffix appended to the project name, e.g. "landing", "app"
 */
export function recordView(page: string): void {
  if (!isTelemetryEnabled()) return
  fetch(`${ENDPOINT}/api/views/chronos-ledger-${page}`, {
    method: 'POST',
    keepalive: true,
  }).catch(() => {})
}
