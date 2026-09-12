'use client'
// Copyright 2026 Chronos Ledger Contributors
// Licensed under the Apache License, Version 2.0

import { useEffect, useState } from 'react'
import { isAxiosError } from 'axios'
import { Search, Loader2, CheckCircle2, CircleX } from 'lucide-react'
import { guestApi } from '@/lib/api'
import { useVocabulary } from '@/hooks/useVocabulary'
import type { LogVerificationState } from '@/types'

const POLL_MS = 5000

type Lookup =
  | { state: 'checking' }
  | { state: 'missing' }
  | { state: 'found'; status: LogVerificationState }

// Where a visitor follows their check-in from their own phone. Nobody signs
// in: the code the kiosk showed them is the whole credential, and all it
// opens is whether that one visit was approved.
export default function GuestVisitPage() {
  const vocab = useVocabulary()
  const [input, setInput] = useState('')
  const [code, setCode] = useState<string | null>(null)
  const [lookup, setLookup] = useState<Lookup | null>(null)

  // A link can carry the code, as /guest/visit/?code=..., for an integrator
  // that sends its visitors one.
  useEffect(() => {
    const linked = new URLSearchParams(window.location.search).get('code')
    if (linked) {
      setInput(linked)
      setCode(linked)
    }
  }, [])

  useEffect(() => {
    if (!code) return
    let cancelled = false
    let timer: ReturnType<typeof setTimeout>
    setLookup({ state: 'checking' })
    const ask = async () => {
      try {
        const res = await guestApi.visitStatus(code)
        if (cancelled) return
        setLookup({ state: 'found', status: res.data.handshake_status })
        // Once decided there is nothing more to wait for.
        if (res.data.handshake_status !== 'PENDING_VERIFICATION') return
      } catch (err) {
        if (cancelled) return
        if (isAxiosError(err) && err.response?.status === 404) {
          setLookup({ state: 'missing' })
          return
        }
        // Anything else is the network or a restart: ask again.
      }
      timer = setTimeout(ask, POLL_MS)
    }
    ask()
    return () => {
      cancelled = true
      clearTimeout(timer)
    }
  }, [code])

  const submit = () => {
    const typed = input.trim()
    if (typed) setCode(typed)
  }

  return (
    <div className="min-h-screen bg-chronos-dark flex flex-col items-center justify-center p-6 relative overflow-hidden">
      {/* Ambient glows */}
      <div className="absolute inset-0 pointer-events-none">
        <div className="absolute top-0 left-1/4 w-96 h-96 bg-chronos-teal/4 rounded-full blur-3xl" />
        <div className="absolute bottom-0 right-1/4 w-96 h-96 bg-chronos-emerald/4 rounded-full blur-3xl" />
      </div>

      {/* Header */}
      <div className="w-full max-w-md mb-8 text-center relative">
        <img src="/icon.png" alt="Chronos Ledger" className="w-14 h-14 rounded-2xl mb-4 shadow-teal-glow" />
        <h1 className="text-2xl font-bold text-chronos-text">Your Visit</h1>
        <p className="text-chronos-text-dim text-sm mt-1">Enter the code the kiosk showed you to see the answer.</p>
      </div>

      <div className="w-full max-w-md relative space-y-4">
        <div className="glass-card p-6">
          <div className="flex gap-2">
            <div className="flex-1">
              <input
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && submit()}
                placeholder="XXXX-XXXX-XXXX-XXXX"
                aria-label="Visit code"
                className="input-field font-mono text-lg py-3 uppercase"
                autoComplete="off"
                autoCapitalize="characters"
                spellCheck={false}
                autoFocus
              />
            </div>
            <button onClick={submit} disabled={!input.trim()} aria-label="Check" className="btn-primary px-5 py-3">
              <Search className="w-5 h-5" />
            </button>
          </div>
        </div>

        {lookup?.state === 'checking' && (
          <div className="glass-card p-8 text-center">
            <Loader2 className="w-8 h-8 animate-spin text-chronos-teal mx-auto" />
          </div>
        )}

        {lookup?.state === 'missing' && (
          <p className="text-chronos-danger text-sm px-1">
            No visit matches that code. Check it against the kiosk screen.
          </p>
        )}

        {lookup?.state === 'found' && lookup.status === 'PENDING_VERIFICATION' && (
          <div className="glass-card p-8 text-center">
            <div className="w-12 h-12 rounded-full border-4 border-chronos-teal border-t-transparent animate-spin mx-auto mb-4" />
            <h2 className="text-lg font-bold text-chronos-text mb-1">{`Awaiting ${vocab.staff} Response`}</h2>
            <p className="text-chronos-text-dim text-sm">This page updates by itself.</p>
          </div>
        )}

        {lookup?.state === 'found' && lookup.status === 'VERIFIED_APPROVED' && (
          <div className="glass-card p-8 text-center">
            <CheckCircle2 className="w-14 h-14 text-chronos-teal mx-auto mb-4" />
            <h2 className="text-lg font-bold text-chronos-text mb-1">Request Approved</h2>
            <p className="text-chronos-text-dim text-sm">You are expected. Please proceed.</p>
          </div>
        )}

        {lookup?.state === 'found' && lookup.status === 'VERIFIED_DENIED' && (
          <div className="glass-card p-8 text-center">
            <CircleX className="w-14 h-14 text-chronos-danger mx-auto mb-4" />
            <h2 className="text-lg font-bold text-chronos-text mb-1">Request Declined</h2>
            <p className="text-chronos-text-dim text-sm">Please ask at the front desk.</p>
          </div>
        )}
      </div>
    </div>
  )
}
