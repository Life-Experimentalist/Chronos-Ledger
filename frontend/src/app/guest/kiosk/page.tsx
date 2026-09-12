'use client'
// Copyright 2026 Chronos Ledger Contributors
// Licensed under the Apache License, Version 2.0

import { useCallback, useEffect, useState } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { motion, AnimatePresence } from 'framer-motion'
import { isAxiosError } from 'axios'
import { Search, User, Phone, Building2, MessageSquare, Loader2, CheckCircle2, CircleX, ArrowLeft, KeyRound } from 'lucide-react'
import { guestApi, kioskKey } from '@/lib/api'
import { useVocabulary } from '@/hooks/useVocabulary'
import type { LogVerificationState, StaffAvailability } from '@/types'

type KioskStep = 'provision' | 'search' | 'form' | 'pending' | 'done'

// How often a waiting kiosk asks for the answer, and how long it shows one
// before it clears itself for the next visitor.
const POLL_MS = 5000
const DONE_RESET_MS = 30000

// Upper bounds mirror the server's, so a visitor is told what is wrong here
// instead of meeting an opaque 422 after they press submit.
const checkInSchema = z.object({
  guest_name: z.string().min(2, 'Full name required').max(100, 'Name is too long'),
  contact_phone: z
    .string()
    .min(8, 'Valid phone number required')
    .max(20, 'Phone number is too long')
    .regex(/^[-0-9+() ]+$/, 'Digits, spaces and + ( ) - only'),
  originating_body: z
    .string()
    .min(2, 'Organization required')
    .max(100, 'Organization name is too long'),
  visitation_intent: z
    .string()
    .min(10, 'Please describe your purpose (min 10 chars)')
    .max(500, 'Please keep this under 500 characters'),
})
type CheckInForm = z.infer<typeof checkInSchema>

export default function GuestKioskPage() {
  const vocab = useVocabulary()
  // null until the effect below has read localStorage: rendering 'provision'
  // first would flash a key prompt at every visitor on an already-set-up kiosk.
  const [step, setStep] = useState<KioskStep | null>(null)
  const [keyInput, setKeyInput] = useState('')
  const [searchError, setSearchError] = useState<string | null>(null)
  const [searchQuery, setSearchQuery] = useState('')
  const [searchResults, setSearchResults] = useState<StaffAvailability[]>([])
  const [searching, setSearching] = useState(false)
  const [selectedStaff, setSelectedStaff] = useState<StaffAvailability | null>(null)
  const [visitCode, setVisitCode] = useState<string | null>(null)
  const [decision, setDecision] = useState<LogVerificationState | null>(null)
  const [submitting, setSubmitting] = useState(false)

  const { register, handleSubmit, formState: { errors }, reset } = useForm<CheckInForm>({
    resolver: zodResolver(checkInSchema),
  })

  useEffect(() => {
    setStep(kioskKey.read() ? 'search' : 'provision')
  }, [])

  const provisionDevice = () => {
    const key = keyInput.trim()
    if (!key) return
    kioskKey.save(key)
    setKeyInput('')
    setSearchError(null)
    setStep('search')
  }

  // A revoked, expired or mistyped key: drop it and ask for a new one rather
  // than leaving the desk staring at a search that silently returns nothing.
  const handleUnauthorized = () => {
    kioskKey.forget()
    setSearchError('This kiosk key was rejected. Ask an administrator for a new one.')
    setStep('provision')
  }

  const handleSearch = async () => {
    if (searchQuery.trim().length < 2) return
    setSearching(true)
    setSearchError(null)
    try {
      const res = await guestApi.searchStaff(searchQuery)
      setSearchResults(res.data)
      if (res.data.length === 0) setSearchError('No match. Try a different spelling.')
    } catch (err) {
      if (isAxiosError(err) && err.response?.status === 401) handleUnauthorized()
      else setSearchError('Search failed. Please try again.')
    } finally {
      setSearching(false)
    }
  }

  const selectStaff = (staff: StaffAvailability) => {
    setSelectedStaff(staff)
    setStep('form')
  }

  const onSubmit = async (data: CheckInForm) => {
    if (!selectedStaff) return
    setSubmitting(true)
    try {
      const res = await guestApi.checkIn({
        ...data,
        target_staff_id: selectedStaff.staff_id,
      })
      setVisitCode(res.data.visit_code)
      setStep('pending')
    } catch (err) {
      if (isAxiosError(err) && err.response?.status === 401) handleUnauthorized()
      else setSearchError('Could not send the request. Please try again.')
    } finally {
      setSubmitting(false)
    }
  }

  const resetKiosk = useCallback(() => {
    setStep('search')
    setSearchQuery('')
    setSearchResults([])
    setSelectedStaff(null)
    setVisitCode(null)
    setDecision(null)
    reset()
  }, [reset])

  // Nothing is pushed to a kiosk, since nobody is signed in on it to push to.
  // It asks with the visit code, the same way the visitor's phone does.
  useEffect(() => {
    if (step !== 'pending' || !visitCode) return
    let cancelled = false
    let timer: ReturnType<typeof setTimeout>
    const ask = async () => {
      try {
        const res = await guestApi.visitStatus(visitCode)
        if (cancelled) return
        if (res.data.handshake_status !== 'PENDING_VERIFICATION') {
          setDecision(res.data.handshake_status)
          setStep('done')
          return
        }
      } catch {
        // A dropped connection or a restarting server: ask again next time.
        if (cancelled) return
      }
      timer = setTimeout(ask, POLL_MS)
    }
    timer = setTimeout(ask, POLL_MS)
    return () => {
      cancelled = true
      clearTimeout(timer)
    }
  }, [step, visitCode])

  useEffect(() => {
    if (step !== 'done') return
    const timer = setTimeout(resetKiosk, DONE_RESET_MS)
    return () => clearTimeout(timer)
  }, [step, resetKiosk])

  return (
    <div className="min-h-screen bg-chronos-dark flex flex-col items-center justify-center p-6 relative overflow-hidden">
      {/* Ambient glows */}
      <div className="absolute inset-0 pointer-events-none">
        <div className="absolute top-0 left-1/4 w-96 h-96 bg-chronos-teal/4 rounded-full blur-3xl" />
        <div className="absolute bottom-0 right-1/4 w-96 h-96 bg-chronos-emerald/4 rounded-full blur-3xl" />
      </div>

      {/* Header */}
      <div className="w-full max-w-xl mb-8 text-center relative">
        <img src="/icon.png" alt="Chronos Ledger" className="w-14 h-14 rounded-2xl mb-4 shadow-teal-glow" />
        <h1 className="text-2xl font-bold text-chronos-text">Organization Visitor Kiosk</h1>
        <p className="text-chronos-text-dim text-sm mt-1">{`Search for a ${vocab.staff.toLowerCase()} member to request a gate-pass`}</p>
      </div>

      <div className="w-full max-w-xl relative">
        <AnimatePresence mode="wait">

          {/* Step 0: Device setup, once per kiosk, by an administrator */}
          {step === 'provision' && (
            <motion.div key="provision" initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -12 }} className="glass-card p-6 space-y-4">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-xl bg-chronos-teal/10 flex items-center justify-center shrink-0">
                  <KeyRound className="w-5 h-5 text-chronos-teal" />
                </div>
                <div>
                  <p className="font-semibold text-chronos-text">Set Up This Kiosk</p>
                  <p className="text-sm text-chronos-text-dim">A one-time step for an administrator.</p>
                </div>
              </div>

              {searchError && <p className="text-chronos-danger text-sm">{searchError}</p>}

              <p className="text-sm text-chronos-text-dim">
                Paste this device&apos;s kiosk key. An administrator creates one under Settings,
                API Keys. It is stored on this device only, and can be revoked there at any time.
              </p>

              <input
                value={keyInput}
                onChange={(e) => setKeyInput(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && provisionDevice()}
                placeholder="ck_..."
                className="input-field font-mono text-base"
                autoComplete="off"
                spellCheck={false}
                autoFocus
              />

              <button onClick={provisionDevice} disabled={!keyInput.trim()} className="btn-primary w-full justify-center py-3 text-base">
                Activate Kiosk
              </button>
            </motion.div>
          )}

          {/* Step 1: Search */}
          {step === 'search' && (
            <motion.div key="search" initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -12 }} className="space-y-4">
              <div className="glass-card p-6">
                <p className="text-sm font-medium text-chronos-text-dim mb-3 uppercase tracking-wider text-xs">{`Search ${vocab.staff} Member`}</p>
                <div className="flex gap-2">
                  <div className="relative flex-1">
                    <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-chronos-muted" />
                    <input
                      value={searchQuery}
                      onChange={(e) => setSearchQuery(e.target.value)}
                      onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
                      placeholder="Enter staff name or unit..."
                      className="input-field pl-10 text-lg py-3"
                      autoComplete="off"
                      autoFocus
                    />
                  </div>
                  <button
                    onClick={handleSearch}
                    disabled={searching || searchQuery.trim().length < 2}
                    className="btn-primary px-5 py-3"
                  >
                    {searching ? <Loader2 className="w-5 h-5 animate-spin" /> : <Search className="w-5 h-5" />}
                  </button>
                </div>
              </div>

              {searchError && <p className="text-chronos-danger text-sm px-1">{searchError}</p>}

              {searchResults.length > 0 && (
                <div className="glass-card overflow-hidden">
                  <div className="p-4 border-b border-chronos-border/40">
                    <p className="text-xs text-chronos-muted">{searchResults.length} result(s), select to proceed</p>
                  </div>
                  <div className="divide-y divide-chronos-border/20">
                    {searchResults.map((staff) => (
                      <motion.button
                        key={staff.staff_id}
                        onClick={() => selectStaff(staff)}
                        whileTap={{ scale: 0.99 }}
                        className="w-full flex items-center gap-4 p-4 hover:bg-chronos-surface/60 transition-colors text-left"
                      >
                        <div className="w-12 h-12 rounded-full bg-chronos-teal/10 flex items-center justify-center text-chronos-teal text-lg font-bold shrink-0">
                          {staff.full_name.charAt(0)}
                        </div>
                        <div className="flex-1 min-w-0">
                          <p className="font-semibold text-chronos-text">{staff.full_name}</p>
                          <p className="text-sm text-chronos-text-dim">{staff.unit_code || vocab.staff}</p>
                        </div>
                        <span className={`text-xs font-medium px-3 py-1.5 rounded-full border ${
                          staff.availability_label === 'Available' || staff.availability_label === 'Very Available'
                            ? 'text-chronos-teal bg-chronos-teal/10 border-chronos-teal/20'
                            : staff.availability_label === 'Do Not Disturb'
                            ? 'text-chronos-danger bg-chronos-danger/10 border-chronos-danger/20'
                            : 'text-chronos-warning bg-chronos-warning/10 border-chronos-warning/20'
                        }`}>
                          {staff.availability_label}
                        </span>
                      </motion.button>
                    ))}
                  </div>
                </div>
              )}
            </motion.div>
          )}

          {/* Step 2: Check-In Form */}
          {step === 'form' && selectedStaff && (
            <motion.div key="form" initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -12 }} className="space-y-4">
              <button onClick={() => setStep('search')} className="flex items-center gap-1.5 text-sm text-chronos-text-dim hover:text-chronos-text transition-colors">
                <ArrowLeft className="w-4 h-4" /> Back to Search
              </button>

              <div className="glass-card p-5 border-l-4 border-l-chronos-teal">
                <p className="text-xs text-chronos-muted mb-1">Visiting</p>
                <p className="font-bold text-chronos-text text-lg">{selectedStaff.full_name}</p>
                <p className="text-sm text-chronos-text-dim">{selectedStaff.unit_code}</p>
              </div>

              <form onSubmit={handleSubmit(onSubmit)} className="glass-card p-6 space-y-4">
                <p className="section-title">Your Details</p>

                <div>
                  <label className="block text-xs font-medium text-chronos-text-dim mb-1.5 uppercase tracking-wider">Full Name</label>
                  <div className="relative">
                    <User className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-chronos-muted" />
                    <input {...register('guest_name')} placeholder="Your full name" className="input-field pl-10 text-base" />
                  </div>
                  {errors.guest_name && <p className="text-chronos-danger text-xs mt-1">{errors.guest_name.message}</p>}
                </div>

                <div>
                  <label className="block text-xs font-medium text-chronos-text-dim mb-1.5 uppercase tracking-wider">Phone Number</label>
                  <div className="relative">
                    <Phone className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-chronos-muted" />
                    <input {...register('contact_phone')} type="tel" placeholder="+91 XXXXX XXXXX" className="input-field pl-10 text-base" />
                  </div>
                  {errors.contact_phone && <p className="text-chronos-danger text-xs mt-1">{errors.contact_phone.message}</p>}
                </div>

                <div>
                  <label className="block text-xs font-medium text-chronos-text-dim mb-1.5 uppercase tracking-wider">Organization</label>
                  <div className="relative">
                    <Building2 className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-chronos-muted" />
                    <input {...register('originating_body')} placeholder="Company or institution name" className="input-field pl-10 text-base" />
                  </div>
                  {errors.originating_body && <p className="text-chronos-danger text-xs mt-1">{errors.originating_body.message}</p>}
                </div>

                <div>
                  <label className="block text-xs font-medium text-chronos-text-dim mb-1.5 uppercase tracking-wider">Purpose of Visit</label>
                  <div className="relative">
                    <MessageSquare className="absolute left-3 top-3 w-4 h-4 text-chronos-muted" />
                    <textarea {...register('visitation_intent')} rows={3} placeholder="Briefly describe your reason for visiting..." className="input-field pl-10 resize-none text-base" />
                  </div>
                  {errors.visitation_intent && <p className="text-chronos-danger text-xs mt-1">{errors.visitation_intent.message}</p>}
                </div>

                <button type="submit" disabled={submitting} className="btn-primary w-full justify-center py-3 text-base">
                  {submitting ? <><Loader2 className="w-5 h-5 animate-spin" /> Submitting Request...</> : 'Request Gate-Pass'}
                </button>
              </form>
            </motion.div>
          )}

          {/* Step 3: Waiting for staff response, with the code to follow it by */}
          {step === 'pending' && (
            <motion.div key="pending" initial={{ opacity: 0, scale: 0.97 }} animate={{ opacity: 1, scale: 1 }} exit={{ opacity: 0 }} className="glass-card p-10 text-center">
              <div className="w-16 h-16 rounded-full border-4 border-chronos-teal border-t-transparent animate-spin mx-auto mb-6" />
              <h2 className="text-xl font-bold text-chronos-text mb-2">{`Awaiting ${vocab.staff} Response`}</h2>
              <p className="text-chronos-text-dim text-sm mb-4">
                Your request has been sent to <strong className="text-chronos-teal">{selectedStaff?.full_name}</strong>.
                Please wait while they review your request.
              </p>
              {visitCode && (
                <div className="bg-chronos-surface rounded-xl p-4 inline-block">
                  <p className="text-xs text-chronos-muted">Your Visit Code</p>
                  <p className="text-2xl font-mono font-bold text-chronos-teal tracking-wider">{visitCode}</p>
                  <p className="text-xs text-chronos-muted mt-2">
                    {`Follow the answer on your phone at ${window.location.host}/guest/visit`}
                  </p>
                </div>
              )}
              <button onClick={resetKiosk} className="btn-secondary w-full justify-center py-3 mt-6">
                Next Visitor
              </button>
            </motion.div>
          )}

          {/* Step 4: The answer, until the next visitor or the reset */}
          {step === 'done' && (
            <motion.div key="done" initial={{ opacity: 0, scale: 0.97 }} animate={{ opacity: 1, scale: 1 }} exit={{ opacity: 0 }} className="glass-card p-10 text-center">
              {decision === 'VERIFIED_APPROVED' ? (
                <>
                  <CheckCircle2 className="w-16 h-16 text-chronos-teal mx-auto mb-6" />
                  <h2 className="text-xl font-bold text-chronos-text mb-2">Request Approved</h2>
                  <p className="text-chronos-text-dim text-sm">
                    <strong className="text-chronos-teal">{selectedStaff?.full_name}</strong> is expecting you.
                  </p>
                </>
              ) : (
                <>
                  <CircleX className="w-16 h-16 text-chronos-danger mx-auto mb-6" />
                  <h2 className="text-xl font-bold text-chronos-text mb-2">Request Declined</h2>
                  <p className="text-chronos-text-dim text-sm">
                    <strong className="text-chronos-text">{selectedStaff?.full_name}</strong> cannot see you right now.
                    Please ask at the front desk.
                  </p>
                </>
              )}
              <button onClick={resetKiosk} className="btn-primary w-full justify-center py-3 mt-8 text-base">
                Next Visitor
              </button>
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      {step !== 'pending' && step !== 'done' && (
        <p className="mt-8 text-xs text-chronos-muted text-center relative">
          <a href="/" className="hover:text-chronos-text transition-colors">{`${vocab.staff} Sign In`}</a>
          {' · '}
          Organization Visitor Kiosk
        </p>
      )}
    </div>
  )
}
