'use client'
// Copyright 2026 Chronos Ledger Contributors
// Licensed under the Apache License, Version 2.0

import { useEffect, useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { UserCheck, UserX, Clock, Building2, Loader2, RefreshCw } from 'lucide-react'
import { guestApi } from '@/lib/api'
import { formatDistanceToNow } from 'date-fns'
import type { GuestEntry } from '@/types'

export function InteractionDesk() {
  const [guests, setGuests] = useState<GuestEntry[]>([])
  const [loading, setLoading] = useState(true)
  const [processing, setProcessing] = useState<number | null>(null)

  const load = () => {
    setLoading(true)
    guestApi.getPendingGuests()
      .then((r) => setGuests(r.data))
      .finally(() => setLoading(false))
  }

  useEffect(() => { load() }, [])

  const decide = async (id: number, decision: 'VERIFIED_APPROVED' | 'VERIFIED_DENIED') => {
    setProcessing(id)
    try {
      await guestApi.decidePending(id, decision)
      setGuests((prev) => prev.filter((g) => g.id !== id))
    } finally {
      setProcessing(null)
    }
  }

  return (
    <div className="space-y-5 max-w-2xl">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold text-chronos-text">Interaction Desk</h2>
          <p className="text-sm text-chronos-muted mt-0.5">Manage campus visitor requests and student interactions</p>
        </div>
        <button onClick={load} className="btn-secondary text-xs">
          <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
          Refresh
        </button>
      </div>

      <div className="glass-card p-5">
        <p className="section-title mb-4 flex items-center gap-2">
          Pending Guest Gate-Pass Requests
          {guests.length > 0 && (
            <span className="bg-chronos-teal/20 text-chronos-teal text-xs font-bold px-1.5 py-0.5 rounded-full">
              {guests.length}
            </span>
          )}
        </p>

        {loading ? (
          <div className="flex items-center justify-center py-12">
            <Loader2 className="w-6 h-6 animate-spin text-chronos-teal" />
          </div>
        ) : guests.length === 0 ? (
          <div className="text-center py-10 text-chronos-muted">
            <UserCheck className="w-10 h-10 mx-auto mb-2 opacity-30" />
            <p className="text-sm">No pending guest requests</p>
          </div>
        ) : (
          <AnimatePresence mode="popLayout">
            {guests.map((guest) => (
              <motion.div
                key={guest.id}
                layout
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, x: 20 }}
                className="bg-chronos-surface border border-chronos-border/40 rounded-xl p-4 mb-3 last:mb-0"
              >
                <div className="flex items-start justify-between gap-4">
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2 mb-1">
                      <div className="w-8 h-8 rounded-full bg-chronos-accent/10 flex items-center justify-center text-chronos-accent text-xs font-bold shrink-0">
                        {guest.guest_name.charAt(0)}
                      </div>
                      <div>
                        <p className="text-sm font-semibold text-chronos-text">{guest.guest_name}</p>
                        <div className="flex items-center gap-1.5 text-xs text-chronos-text-dim">
                          <Building2 className="w-3 h-3" />
                          {guest.originating_body}
                        </div>
                      </div>
                    </div>
                    <p className="text-xs text-chronos-text-dim ml-10 mb-2 line-clamp-2">{guest.visitation_intent}</p>
                    <div className="flex items-center gap-1.5 ml-10 text-xs text-chronos-muted">
                      <Clock className="w-3 h-3" />
                      {formatDistanceToNow(new Date(guest.timestamp_marked), { addSuffix: true })}
                    </div>
                  </div>

                  <div className="flex flex-col gap-2 shrink-0">
                    <button
                      onClick={() => decide(guest.id, 'VERIFIED_APPROVED')}
                      disabled={processing === guest.id}
                      className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium bg-chronos-emerald/10 hover:bg-chronos-emerald/20 text-chronos-emerald border border-chronos-emerald/20 rounded-lg transition-colors"
                    >
                      {processing === guest.id ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <UserCheck className="w-3.5 h-3.5" />}
                      Allow Entry
                    </button>
                    <button
                      onClick={() => decide(guest.id, 'VERIFIED_DENIED')}
                      disabled={processing === guest.id}
                      className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium bg-chronos-danger/10 hover:bg-chronos-danger/20 text-chronos-danger border border-chronos-danger/20 rounded-lg transition-colors"
                    >
                      <UserX className="w-3.5 h-3.5" />
                      Decline
                    </button>
                  </div>
                </div>
              </motion.div>
            ))}
          </AnimatePresence>
        )}
      </div>
    </div>
  )
}
