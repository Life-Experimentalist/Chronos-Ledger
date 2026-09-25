'use client'
// Copyright 2026 Chronos Ledger Contributors
// Licensed under the Apache License, Version 2.0

import { useEffect, useRef, useState } from 'react'
import { useRouter } from 'next/navigation'
import Link from 'next/link'
import { motion } from 'framer-motion'
import { AlertCircle, Loader2 } from 'lucide-react'
import { useAuthStore } from '@/store/auth'
import { roleRedirectPath } from '@/lib/auth'
import { apiErrorMessage } from '@/lib/errors'

// The integrating system sends its person to /auth/federated#token=<note>. A
// fragment never reaches a server, so the note stays out of the proxy's access
// log and out of the Referer of whatever loads next. There is nowhere else to
// put it: this frontend is a static export with no handler that could receive
// a POST.
function noteFromFragment(hash: string): string | null {
  const note = new URLSearchParams(hash.replace(/^#/, '')).get('token')
  return note && note.trim() ? note : null
}

// Arriving here with nothing to spend is a refusal like any other, and goes
// down the same path so that neither message is set from the effect body.
class NoNote extends Error {}

const NOTHING_TO_SPEND =
  'There is no sign-in note in this address. This page opens from your organization, and a note is spent the moment it arrives, so a reload or a bookmark lands here with nothing left to use.'

// What the server says, where what it says was written to be read. The 404 is
// the exception: it answers `Not Found` on purpose, so that probing an instance
// cannot tell whether it has an integration at all, and showing that to
// somebody who arrived from their own organization would be no help to them.
function refusalMessage(err: unknown): string {
  if (err instanceof NoNote) return NOTHING_TO_SPEND
  const status = (err as { response?: { status?: number } })?.response?.status
  if (status === 404) return 'Federated sign-in is not enabled on this instance.'
  if (status === 401) {
    return 'That sign-in note was refused. It may have expired, or already been used: a note works once, and opening this page again reuses nothing. Ask your organization to send you here again.'
  }
  return apiErrorMessage(err, 'Federated sign-in could not be completed.')
}

export default function FederatedSignInPage() {
  const router = useRouter()
  const { federatedSignIn } = useAuthStore()
  const [error, setError] = useState<string | null>(null)
  // React runs effects twice in development, and the second run of this one
  // would post a note the first has already spent, turning every successful
  // sign-in in development into a 401.
  const started = useRef(false)

  useEffect(() => {
    if (started.current) return
    started.current = true

    // Read and clear before anything asynchronous. The address bar is clean
    // before the first request goes out, so a reload cannot re-post the note
    // and the note is not left in the session history for the next person at
    // this machine to scroll back to. The existing state is handed back
    // unchanged because the app router keeps its own bookkeeping in there, and
    // replacing it with null strands the `router.replace` below.
    const note = noteFromFragment(window.location.hash)
    window.history.replaceState(
      window.history.state,
      '',
      window.location.pathname + window.location.search
    )

    Promise.resolve()
      .then(() => {
        if (!note) throw new NoNote()
        return federatedSignIn(note)
      })
      .then((user) => {
        // The same branch `src/app/page.tsx` takes after a password sign-in,
        // and it is reachable from here: `account_for` does not re-read the
        // role of an account that already exists, so one linked while it was
        // STAFF and promoted since arrives with the role it has now. replace,
        // not push: going back to this page would find the fragment gone and
        // show a refusal for a sign-in that worked.
        const onboarding =
          user.initial_login_state &&
          (user.role === 'ORG_ADMIN' || user.role === 'UNIT_ADMIN')
        router.replace(onboarding ? '/admin/onboarding' : roleRedirectPath(user.role))
      })
      .catch((err: unknown) => setError(refusalMessage(err)))
  }, [federatedSignIn, router])

  return (
    <div className="min-h-screen bg-chronos-dark flex items-center justify-center p-4">
      <motion.div
        initial={{ opacity: 0, y: 24 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5, ease: 'easeOut' }}
        className="w-full max-w-md"
      >
        <div className="text-center mb-8">
          <img src="/icon.png" alt="Chronos Ledger" className="w-16 h-16 rounded-2xl mb-4 mx-auto" />
          <h1 className="text-2xl font-bold text-chronos-text teal-glow-text">Chronos Ledger</h1>
        </div>

        <div className="glass-card p-8">
          {error ? (
            <>
              <h2 className="text-lg font-semibold text-chronos-text mb-4">Sign-in did not complete</h2>
              <div className="bg-chronos-danger/10 border border-chronos-danger/30 rounded-lg p-3 flex items-start gap-2 text-chronos-danger text-sm">
                <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
                <p>{error}</p>
              </div>
              {/* A federated failure must not leave somebody with no way in. */}
              <Link href="/" className="btn-primary w-full justify-center mt-6">
                Sign in with a password
              </Link>
            </>
          ) : (
            <div className="flex items-center gap-3 text-chronos-text-dim text-sm">
              <Loader2 className="w-4 h-4 animate-spin text-chronos-teal" />
              Signing you in through your organization...
            </div>
          )}
        </div>

        <p className="text-center text-xs text-chronos-muted mt-6">
          © 2026 Chronos Ledger · Apache 2.0
        </p>
      </motion.div>
    </div>
  )
}
