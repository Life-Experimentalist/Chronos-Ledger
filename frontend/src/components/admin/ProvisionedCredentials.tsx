'use client'
// Copyright 2026 Chronos Ledger Contributors
// Licensed under the Apache License, Version 2.0

import { useState } from 'react'
import { KeyRound, Download, Copy, Check } from 'lucide-react'
import type { ProvisionedCredential } from '@/types'

/**
 * The passwords a CSV import just generated, shown the one time they exist.
 *
 * The server hashes them and forgets them, so this panel is the only copy.
 * An admin who closes it without saving has to reset each member from
 * POST /users/{id}/reset-password, one at a time.
 */
export function ProvisionedCredentials({ credentials }: { credentials: ProvisionedCredential[] }) {
  const [copied, setCopied] = useState(false)
  const [copyFailed, setCopyFailed] = useState(false)

  if (credentials.length === 0) return null

  const asCsv = () => {
    const header = 'member_id,email_address,initial_password'
    const rows = credentials.map((c) =>
      [c.member_id, c.email_address, c.initial_password].join(','),
    )
    return [header, ...rows].join('\n')
  }

  const download = () => {
    const blob = new Blob([asCsv()], { type: 'text/csv;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `chronos-initial-passwords-${new Date().toISOString().slice(0, 10)}.csv`
    a.click()
    URL.revokeObjectURL(url)
  }

  const copy = async () => {
    try {
      // Absent on a plain-HTTP origin, which a LAN deployment often is.
      await navigator.clipboard.writeText(asCsv())
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch {
      setCopyFailed(true)
    }
  }

  return (
    <div className="p-4 rounded-xl bg-chronos-warning/10 border border-chronos-warning/30 space-y-3">
      <div className="flex items-start gap-3">
        <KeyRound className="w-5 h-5 text-chronos-warning shrink-0 mt-0.5" />
        <div>
          <p className="text-sm font-medium text-chronos-warning">
            {credentials.length} new {credentials.length === 1 ? 'account' : 'accounts'}, shown once
          </p>
          <p className="text-xs text-chronos-text-dim mt-0.5">
            Save these before leaving the page. They are not stored anywhere and cannot be shown
            again. A password that goes missing has to be reset per member.
          </p>
        </div>
      </div>

      <div className="flex gap-2">
        <button onClick={download} className="btn-secondary text-xs">
          <Download className="w-3.5 h-3.5" /> Download CSV
        </button>
        <button onClick={copy} className="btn-secondary text-xs">
          {copied ? <Check className="w-3.5 h-3.5" /> : <Copy className="w-3.5 h-3.5" />}
          {copied ? 'Copied' : 'Copy all'}
        </button>
        {copyFailed && (
          <span className="text-xs text-chronos-text-dim self-center">
            Clipboard unavailable, use Download.
          </span>
        )}
      </div>

      <div className="max-h-52 overflow-y-auto rounded-lg border border-chronos-border">
        <table className="w-full text-xs font-mono">
          <thead className="sticky top-0 bg-chronos-surface">
            <tr className="text-left text-chronos-muted">
              <th className="px-3 py-2 font-medium">Member</th>
              <th className="px-3 py-2 font-medium">Email</th>
              <th className="px-3 py-2 font-medium">Password</th>
            </tr>
          </thead>
          <tbody>
            {credentials.map((c) => (
              <tr key={c.member_id} className="border-t border-chronos-border/50">
                <td className="px-3 py-1.5 text-chronos-text-dim">{c.member_id}</td>
                <td className="px-3 py-1.5 text-chronos-text-dim">{c.email_address}</td>
                <td className="px-3 py-1.5 text-chronos-text select-all">{c.initial_password}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
