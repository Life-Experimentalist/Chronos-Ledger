'use client'
// Copyright 2026 Chronos Ledger Contributors
// Licensed under the Apache License, Version 2.0

import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { motion, AnimatePresence } from 'framer-motion'
import { Clock, Search, User, Phone, Building2, MessageSquare, Loader2, CheckCircle2, ArrowLeft } from 'lucide-react'
import { guestApi } from '@/lib/api'
import type { FacultyAvailability } from '@/types'

type KioskStep = 'search' | 'form' | 'pending' | 'done'

const checkInSchema = z.object({
  guest_name: z.string().min(2, 'Full name required'),
  contact_phone: z.string().min(8, 'Valid phone number required'),
  originating_body: z.string().min(2, 'Organization required'),
  visitation_intent: z.string().min(10, 'Please describe your purpose (min 10 chars)'),
})
type CheckInForm = z.infer<typeof checkInSchema>

export default function GuestKioskPage() {
  const [step, setStep] = useState<KioskStep>('search')
  const [searchQuery, setSearchQuery] = useState('')
  const [searchResults, setSearchResults] = useState<FacultyAvailability[]>([])
  const [searching, setSearching] = useState(false)
  const [selectedFaculty, setSelectedFaculty] = useState<FacultyAvailability | null>(null)
  const [referenceToken, setReferenceToken] = useState<number | null>(null)
  const [submitting, setSubmitting] = useState(false)

  const { register, handleSubmit, formState: { errors }, reset } = useForm<CheckInForm>({
    resolver: zodResolver(checkInSchema),
  })

  const handleSearch = async () => {
    if (!searchQuery.trim()) return
    setSearching(true)
    try {
      const res = await guestApi.searchFaculty(searchQuery)
      setSearchResults(res.data)
    } finally {
      setSearching(false)
    }
  }

  const selectFaculty = (faculty: FacultyAvailability) => {
    setSelectedFaculty(faculty)
    setStep('form')
  }

  const onSubmit = async (data: CheckInForm) => {
    if (!selectedFaculty) return
    setSubmitting(true)
    try {
      const res = await guestApi.checkIn({
        ...data,
        target_faculty_id: selectedFaculty.faculty_id,
      })
      setReferenceToken(res.data.reference_token)
      setStep('pending')
    } finally {
      setSubmitting(false)
    }
  }

  const resetKiosk = () => {
    setStep('search')
    setSearchQuery('')
    setSearchResults([])
    setSelectedFaculty(null)
    setReferenceToken(null)
    reset()
  }

  return (
    <div className="min-h-screen bg-chronos-dark flex flex-col items-center justify-center p-6 relative overflow-hidden">
      {/* Ambient glows */}
      <div className="absolute inset-0 pointer-events-none">
        <div className="absolute top-0 left-1/4 w-96 h-96 bg-chronos-teal/4 rounded-full blur-3xl" />
        <div className="absolute bottom-0 right-1/4 w-96 h-96 bg-chronos-emerald/4 rounded-full blur-3xl" />
      </div>

      {/* Header */}
      <div className="w-full max-w-xl mb-8 text-center relative">
        <div className="inline-flex items-center justify-center w-14 h-14 rounded-2xl bg-gradient-to-br from-chronos-teal to-chronos-emerald mb-4 shadow-teal-glow">
          <Clock className="w-7 h-7 text-chronos-dark" strokeWidth={2.5} />
        </div>
        <h1 className="text-2xl font-bold text-chronos-text">Campus Visitor Kiosk</h1>
        <p className="text-chronos-text-dim text-sm mt-1">Search for a faculty member to request a gate-pass</p>
      </div>

      <div className="w-full max-w-xl relative">
        <AnimatePresence mode="wait">

          {/* Step 1: Search */}
          {step === 'search' && (
            <motion.div key="search" initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -12 }} className="space-y-4">
              <div className="glass-card p-6">
                <p className="text-sm font-medium text-chronos-text-dim mb-3 uppercase tracking-wider text-xs">Search Faculty Member</p>
                <div className="flex gap-2">
                  <div className="relative flex-1">
                    <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-chronos-muted" />
                    <input
                      value={searchQuery}
                      onChange={(e) => setSearchQuery(e.target.value)}
                      onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
                      placeholder="Enter faculty name or department..."
                      className="input-field pl-10 text-lg py-3"
                      autoComplete="off"
                      autoFocus
                    />
                  </div>
                  <button
                    onClick={handleSearch}
                    disabled={searching || !searchQuery.trim()}
                    className="btn-primary px-5 py-3"
                  >
                    {searching ? <Loader2 className="w-5 h-5 animate-spin" /> : <Search className="w-5 h-5" />}
                  </button>
                </div>
              </div>

              {searchResults.length > 0 && (
                <div className="glass-card overflow-hidden">
                  <div className="p-4 border-b border-chronos-border/40">
                    <p className="text-xs text-chronos-muted">{searchResults.length} result(s) — select to proceed</p>
                  </div>
                  <div className="divide-y divide-chronos-border/20">
                    {searchResults.map((faculty) => (
                      <motion.button
                        key={faculty.faculty_id}
                        onClick={() => selectFaculty(faculty)}
                        whileTap={{ scale: 0.99 }}
                        className="w-full flex items-center gap-4 p-4 hover:bg-chronos-surface/60 transition-colors text-left"
                      >
                        <div className="w-12 h-12 rounded-full bg-chronos-teal/10 flex items-center justify-center text-chronos-teal text-lg font-bold shrink-0">
                          {faculty.full_name.charAt(0)}
                        </div>
                        <div className="flex-1 min-w-0">
                          <p className="font-semibold text-chronos-text">{faculty.full_name}</p>
                          <p className="text-sm text-chronos-text-dim">{faculty.department_code || 'Faculty'}</p>
                        </div>
                        <span className={`text-xs font-medium px-3 py-1.5 rounded-full border ${
                          faculty.availability_label === 'Available' || faculty.availability_label === 'Very Available'
                            ? 'text-chronos-teal bg-chronos-teal/10 border-chronos-teal/20'
                            : faculty.availability_label === 'Do Not Disturb'
                            ? 'text-chronos-danger bg-chronos-danger/10 border-chronos-danger/20'
                            : 'text-chronos-warning bg-chronos-warning/10 border-chronos-warning/20'
                        }`}>
                          {faculty.availability_label}
                        </span>
                      </motion.button>
                    ))}
                  </div>
                </div>
              )}
            </motion.div>
          )}

          {/* Step 2: Check-In Form */}
          {step === 'form' && selectedFaculty && (
            <motion.div key="form" initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -12 }} className="space-y-4">
              <button onClick={() => setStep('search')} className="flex items-center gap-1.5 text-sm text-chronos-text-dim hover:text-chronos-text transition-colors">
                <ArrowLeft className="w-4 h-4" /> Back to Search
              </button>

              <div className="glass-card p-5 border-l-4 border-l-chronos-teal">
                <p className="text-xs text-chronos-muted mb-1">Visiting</p>
                <p className="font-bold text-chronos-text text-lg">{selectedFaculty.full_name}</p>
                <p className="text-sm text-chronos-text-dim">{selectedFaculty.department_code}</p>
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

          {/* Step 3: Waiting for faculty response */}
          {step === 'pending' && (
            <motion.div key="pending" initial={{ opacity: 0, scale: 0.97 }} animate={{ opacity: 1, scale: 1 }} exit={{ opacity: 0 }} className="glass-card p-10 text-center">
              <div className="w-16 h-16 rounded-full border-4 border-chronos-teal border-t-transparent animate-spin mx-auto mb-6" />
              <h2 className="text-xl font-bold text-chronos-text mb-2">Awaiting Faculty Response</h2>
              <p className="text-chronos-text-dim text-sm mb-4">
                Your request has been sent to <strong className="text-chronos-teal">{selectedFaculty?.full_name}</strong>.
                Please wait while they review your request.
              </p>
              {referenceToken && (
                <div className="bg-chronos-surface rounded-xl p-3 inline-block">
                  <p className="text-xs text-chronos-muted">Reference Token</p>
                  <p className="text-2xl font-mono font-bold text-chronos-teal">#{referenceToken}</p>
                </div>
              )}
              <p className="text-xs text-chronos-muted mt-6">Show this screen to the security desk while waiting.</p>
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      {step !== 'pending' && (
        <p className="mt-8 text-xs text-chronos-muted text-center relative">
          <a href="/" className="hover:text-chronos-text transition-colors">Staff Sign In</a>
          {' · '}
          Campus Visitor Kiosk
        </p>
      )}
    </div>
  )
}
