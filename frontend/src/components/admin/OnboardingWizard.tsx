'use client'
// Copyright 2026 Chronos Ledger Contributors — Apache 2.0

import { useState, useCallback } from 'react'
import { useRouter } from 'next/navigation'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { motion, AnimatePresence } from 'framer-motion'
import {
  Lock, CalendarPlus, Upload, Zap, CheckCircle2,
  ChevronRight, ChevronLeft, AlertCircle, Loader2,
  Info, ExternalLink, SkipForward,
} from 'lucide-react'
import { authApi, scheduleApi, ingestionApi } from '@/lib/api'
import type { AcademicCycle } from '@/types'

// ─── Step configs ────────────────────────────────────────────────────────────
const STEPS = [
  { id: 'password',  label: 'Secure Account',    icon: Lock,         required: true  },
  { id: 'cycle',     label: 'Academic Cycle',     icon: CalendarPlus, required: false },
  { id: 'import',    label: 'Import Schedule',    icon: Upload,       required: false },
  { id: 'ledger',    label: 'Generate Ledger',    icon: Zap,          required: false },
  { id: 'done',      label: 'Ready',              icon: CheckCircle2, required: false },
] as const
type StepId = (typeof STEPS)[number]['id']

interface Props {
  /** When true (coming from dashboard) the final step shows "Back to Dashboard" */
  fromDashboard?: boolean
  /** Start on a specific step index (0-based) */
  initialStep?: number
}

// ─── Schemas ─────────────────────────────────────────────────────────────────
const passwordSchema = z.object({
  current_password: z.string().min(1, 'Required'),
  new_password: z.string().min(8, 'At least 8 characters'),
  confirm_password: z.string(),
}).refine((d) => d.new_password === d.confirm_password, {
  message: 'Passwords do not match',
  path: ['confirm_password'],
})

const cycleSchema = z.object({
  cycle_label: z.string().min(3, 'At least 3 characters'),
  date_bounds_start: z.string().min(1, 'Required'),
  date_bounds_end: z.string().min(1, 'Required'),
})

type PasswordForm = z.infer<typeof passwordSchema>
type CycleForm = z.infer<typeof cycleSchema>

// ─── Component ───────────────────────────────────────────────────────────────
export function OnboardingWizard({ fromDashboard = false, initialStep = 0 }: Props) {
  const router = useRouter()
  const [currentStep, setCurrentStep] = useState(initialStep)
  const [createdCycle, setCreatedCycle] = useState<AcademicCycle | null>(null)
  const [csvFile, setCsvFile] = useState<File | null>(null)
  const [dragOver, setDragOver] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  const step = STEPS[currentStep]

  const next = useCallback(() => {
    setError(null)
    setSuccess(null)
    setCurrentStep((s) => Math.min(s + 1, STEPS.length - 1))
  }, [])

  const prev = useCallback(() => {
    setError(null)
    setSuccess(null)
    setCurrentStep((s) => Math.max(s - 1, 0))
  }, [])

  const finish = () => router.push('/admin/dashboard')

  // ── Password step ──────────────────────────────────────────────────────────
  const pwForm = useForm<PasswordForm>({ resolver: zodResolver(passwordSchema) })

  const submitPassword = pwForm.handleSubmit(async (data) => {
    setLoading(true)
    setError(null)
    try {
      await authApi.changePassword(data.current_password, data.new_password)
      // Clear initial_login_state flag from localStorage
      const raw = localStorage.getItem('chronos_user')
      if (raw) {
        const user = JSON.parse(raw)
        localStorage.setItem('chronos_user', JSON.stringify({ ...user, initial_login_state: false }))
      }
      setSuccess('Password updated successfully.')
      setTimeout(next, 800)
    } catch (e: unknown) {
      const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      setError(msg ?? 'Current password is incorrect.')
    } finally {
      setLoading(false)
    }
  })

  // ── Cycle step ─────────────────────────────────────────────────────────────
  const cycleForm = useForm<CycleForm>({ resolver: zodResolver(cycleSchema) })

  const submitCycle = cycleForm.handleSubmit(async (data) => {
    setLoading(true)
    setError(null)
    try {
      const res = await scheduleApi.createCycle({ ...data, operational_status: true })
      setCreatedCycle(res.data as AcademicCycle)
      setSuccess(`Cycle "${data.cycle_label}" created.`)
      setTimeout(next, 800)
    } catch (e: unknown) {
      const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      setError(msg ?? 'Failed to create cycle.')
    } finally {
      setLoading(false)
    }
  })

  // ── CSV import step ────────────────────────────────────────────────────────
  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    setDragOver(false)
    const file = e.dataTransfer.files[0]
    if (file?.name.endsWith('.csv')) setCsvFile(file)
    else setError('Please drop a .csv file.')
  }, [])

  const submitCsv = async () => {
    if (!csvFile || !createdCycle) return
    setLoading(true)
    setError(null)
    try {
      const res = await ingestionApi.uploadCsv(createdCycle.id, csvFile)
      const d = res.data as { rows_processed: number; users_created: number }
      setSuccess(`Imported ${d.rows_processed} rows, created ${d.users_created} users.`)
      setTimeout(next, 1000)
    } catch (e: unknown) {
      const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      setError(msg ?? 'CSV import failed. Check the file format.')
    } finally {
      setLoading(false)
    }
  }

  // ── Generate ledger step ───────────────────────────────────────────────────
  const generateLedger = async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await ingestionApi.generateLedger()
      const d = res.data as { generated: number; target_date: string }
      setSuccess(`Generated ${d.generated} ledger entries for ${d.target_date}.`)
      setTimeout(next, 800)
    } catch (e: unknown) {
      const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      setError(msg ?? 'Ledger generation failed.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="max-w-2xl mx-auto">
      {/* Progress */}
      <div className="flex items-center gap-2 mb-10">
        {STEPS.map((s, i) => (
          <div key={s.id} className="flex items-center gap-2 flex-1 last:flex-none">
            <button
              onClick={() => { if (i < currentStep) { setError(null); setSuccess(null); setCurrentStep(i) } }}
              className={`flex items-center justify-center w-8 h-8 rounded-full border-2 text-xs font-bold shrink-0 transition-all ${
                i < currentStep
                  ? 'border-chronos-teal bg-chronos-teal text-chronos-dark cursor-pointer'
                  : i === currentStep
                  ? 'border-chronos-teal text-chronos-teal'
                  : 'border-chronos-border text-chronos-muted cursor-not-allowed'
              }`}
            >
              {i < currentStep ? <CheckCircle2 className="w-4 h-4" /> : i + 1}
            </button>
            <span className={`text-xs hidden sm:block ${i === currentStep ? 'text-chronos-text font-medium' : 'text-chronos-muted'}`}>
              {s.label}
            </span>
            {i < STEPS.length - 1 && (
              <div className={`flex-1 h-px mx-1 ${i < currentStep ? 'bg-chronos-teal' : 'bg-chronos-border/40'}`} />
            )}
          </div>
        ))}
      </div>

      {/* Step content */}
      <AnimatePresence mode="wait">
        <motion.div
          key={step.id}
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -12 }}
          transition={{ duration: 0.2 }}
        >
          {/* ── Step: Change Password ─────────────────────────────────────── */}
          {step.id === 'password' && (
            <div className="glass-card p-8 space-y-6">
              <div>
                <h2 className="text-xl font-bold text-chronos-text">Secure your account</h2>
                <p className="text-sm text-chronos-muted mt-1">
                  The default password must be changed before you can proceed.
                </p>
              </div>
              <div className="bg-chronos-warning/10 border border-chronos-warning/30 rounded-lg p-3 flex gap-2 text-chronos-warning text-sm">
                <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
                Default credentials are publicly known. Change the password now.
              </div>
              <form onSubmit={submitPassword} className="space-y-4">
                <div>
                  <label className="block text-xs font-medium text-chronos-text-dim mb-1.5 uppercase tracking-wider">Current Password</label>
                  <input {...pwForm.register('current_password')} type="password" className="input-field" placeholder="ChronosAdmin2026!" />
                  {pwForm.formState.errors.current_password && (
                    <p className="text-chronos-danger text-xs mt-1">{pwForm.formState.errors.current_password.message}</p>
                  )}
                </div>
                <div>
                  <label className="block text-xs font-medium text-chronos-text-dim mb-1.5 uppercase tracking-wider">New Password</label>
                  <input {...pwForm.register('new_password')} type="password" className="input-field" placeholder="Min. 8 characters" />
                  {pwForm.formState.errors.new_password && (
                    <p className="text-chronos-danger text-xs mt-1">{pwForm.formState.errors.new_password.message}</p>
                  )}
                </div>
                <div>
                  <label className="block text-xs font-medium text-chronos-text-dim mb-1.5 uppercase tracking-wider">Confirm Password</label>
                  <input {...pwForm.register('confirm_password')} type="password" className="input-field" placeholder="Repeat new password" />
                  {pwForm.formState.errors.confirm_password && (
                    <p className="text-chronos-danger text-xs mt-1">{pwForm.formState.errors.confirm_password.message}</p>
                  )}
                </div>
                <FeedbackBanner error={error} success={success} />
                <button type="submit" disabled={loading} className="btn-primary w-full justify-center">
                  {loading ? <><Loader2 className="w-4 h-4 animate-spin" /> Updating…</> : 'Update Password & Continue'}
                </button>
              </form>
            </div>
          )}

          {/* ── Step: Academic Cycle ──────────────────────────────────────── */}
          {step.id === 'cycle' && (
            <div className="glass-card p-8 space-y-6">
              <div>
                <h2 className="text-xl font-bold text-chronos-text">Create an academic cycle</h2>
                <p className="text-sm text-chronos-muted mt-1">
                  An academic cycle defines the semester/trimester boundaries. Schedules and attendance records are scoped to it.
                </p>
              </div>
              <form onSubmit={submitCycle} className="space-y-4">
                <div>
                  <label className="block text-xs font-medium text-chronos-text-dim mb-1.5 uppercase tracking-wider">Cycle Name</label>
                  <input {...cycleForm.register('cycle_label')} className="input-field" placeholder="e.g. 2026-Fall-Semester" />
                  {cycleForm.formState.errors.cycle_label && (
                    <p className="text-chronos-danger text-xs mt-1">{cycleForm.formState.errors.cycle_label.message}</p>
                  )}
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-xs font-medium text-chronos-text-dim mb-1.5 uppercase tracking-wider">Start Date</label>
                    <input {...cycleForm.register('date_bounds_start')} type="date" className="input-field" />
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-chronos-text-dim mb-1.5 uppercase tracking-wider">End Date</label>
                    <input {...cycleForm.register('date_bounds_end')} type="date" className="input-field" />
                  </div>
                </div>
                <FeedbackBanner error={error} success={success} />
                <div className="flex gap-3">
                  <button type="submit" disabled={loading} className="btn-primary flex-1 justify-center">
                    {loading ? <><Loader2 className="w-4 h-4 animate-spin" /> Creating…</> : 'Create Cycle'}
                  </button>
                  <button type="button" onClick={next} className="btn-secondary flex items-center gap-1.5">
                    <SkipForward className="w-4 h-4" /> Skip
                  </button>
                </div>
              </form>
            </div>
          )}

          {/* ── Step: CSV Import ──────────────────────────────────────────── */}
          {step.id === 'import' && (
            <div className="glass-card p-8 space-y-6">
              <div>
                <h2 className="text-xl font-bold text-chronos-text">Import your schedule</h2>
                <p className="text-sm text-chronos-muted mt-1">
                  Upload a student-centric CSV to create courses, faculty, students, and timetable slots in one go.
                </p>
              </div>
              {!createdCycle && (
                <div className="bg-chronos-warning/10 border border-chronos-warning/30 rounded-lg p-3 flex gap-2 text-chronos-warning text-sm">
                  <Info className="w-4 h-4 shrink-0 mt-0.5" />
                  No cycle was created. Go back to create one first, or import will use the active cycle.
                </div>
              )}
              <div>
                <p className="text-xs font-medium text-chronos-text-dim mb-2 uppercase tracking-wider">Required CSV columns</p>
                <div className="font-mono text-xs text-chronos-muted bg-chronos-dark rounded-lg p-3 border border-chronos-border/40 leading-relaxed">
                  student_id, student_name, student_email, subject_code, subject_title,<br/>
                  department, day_of_week_index, time_window_start, time_window_end,<br/>
                  teacher_id, room
                </div>
              </div>
              {/* Drop zone */}
              <div
                onDrop={handleDrop}
                onDragOver={(e) => { e.preventDefault(); setDragOver(true) }}
                onDragLeave={() => setDragOver(false)}
                className={`border-2 border-dashed rounded-xl p-10 text-center transition-all ${
                  dragOver ? 'border-chronos-teal bg-chronos-teal/5' : 'border-chronos-border/50 hover:border-chronos-teal/40'
                }`}
              >
                <Upload className="w-8 h-8 text-chronos-muted mx-auto mb-3" />
                {csvFile ? (
                  <p className="text-chronos-teal font-medium">{csvFile.name}</p>
                ) : (
                  <>
                    <p className="text-chronos-text-dim text-sm">Drop your .csv file here</p>
                    <p className="text-chronos-muted text-xs mt-1">or</p>
                  </>
                )}
                <label className="mt-3 inline-block cursor-pointer text-sm text-chronos-teal hover:underline">
                  Browse file
                  <input
                    type="file"
                    accept=".csv"
                    className="hidden"
                    onChange={(e) => {
                      const f = e.target.files?.[0]
                      if (f) setCsvFile(f)
                    }}
                  />
                </label>
              </div>
              <FeedbackBanner error={error} success={success} />
              <div className="flex gap-3">
                <button
                  onClick={submitCsv}
                  disabled={loading || !csvFile}
                  className="btn-primary flex-1 justify-center"
                >
                  {loading ? <><Loader2 className="w-4 h-4 animate-spin" /> Importing…</> : 'Import Schedule'}
                </button>
                <button onClick={next} className="btn-secondary flex items-center gap-1.5">
                  <SkipForward className="w-4 h-4" /> Skip
                </button>
              </div>
            </div>
          )}

          {/* ── Step: Generate Ledger ─────────────────────────────────────── */}
          {step.id === 'ledger' && (
            <div className="glass-card p-8 space-y-6">
              <div>
                <h2 className="text-xl font-bold text-chronos-text">Generate today's ledger</h2>
                <p className="text-sm text-chronos-muted mt-1">
                  The daily ledger materialises your timetable into session records that attendance, proxies, and notifications are built on.
                  The nightly cron job does this automatically — this button generates it for today immediately.
                </p>
              </div>
              <div className="bg-chronos-teal/5 border border-chronos-teal/20 rounded-lg p-4 flex gap-3">
                <Info className="w-4 h-4 text-chronos-teal shrink-0 mt-0.5" />
                <p className="text-sm text-chronos-text-dim">
                  Safe to run multiple times — existing entries are skipped (idempotent).
                  The cron job runs automatically at 23:00 UTC each night.
                </p>
              </div>
              <FeedbackBanner error={error} success={success} />
              <div className="flex gap-3">
                <button
                  onClick={generateLedger}
                  disabled={loading}
                  className="btn-primary flex-1 justify-center"
                >
                  {loading ? <><Loader2 className="w-4 h-4 animate-spin" /> Generating…</> : 'Generate Ledger Now'}
                </button>
                <button onClick={next} className="btn-secondary flex items-center gap-1.5">
                  <SkipForward className="w-4 h-4" /> Skip
                </button>
              </div>
            </div>
          )}

          {/* ── Step: Done ────────────────────────────────────────────────── */}
          {step.id === 'done' && (
            <div className="glass-card p-8 space-y-6 text-center">
              <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-chronos-teal to-chronos-emerald flex items-center justify-center mx-auto shadow-teal-strong">
                <CheckCircle2 className="w-9 h-9 text-chronos-dark" />
              </div>
              <div>
                <h2 className="text-xl font-bold text-chronos-text">You&apos;re all set!</h2>
                <p className="text-sm text-chronos-muted mt-2 max-w-md mx-auto">
                  Chronos Ledger is configured and ready. Here&apos;s what you can do next.
                </p>
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-left">
                {[
                  { title: 'Invite faculty & students', desc: 'Create accounts via Admin → Users or import via CSV.', href: '/admin/dashboard?tab=import' },
                  { title: 'Configure timetable', desc: 'Upload or manually adjust master slots for each course.', href: '/admin/dashboard?tab=import' },
                  { title: 'Read the API docs', desc: 'OpenAPI spec and guides in /docs on your server.', href: '/docs', external: true },
                  { title: 'Set up push notifications', desc: 'Add VAPID keys to .env and rebuild the frontend container.', href: 'https://github.com/Life-Experimentalist/chronos-ledger/blob/main/docs/deployment.md', external: true },
                ].map((item) => (
                  <a
                    key={item.title}
                    href={item.href}
                    target={item.external ? '_blank' : undefined}
                    rel={item.external ? 'noopener noreferrer' : undefined}
                    className="glass-card-hover p-4 rounded-xl text-left group"
                  >
                    <div className="flex items-center justify-between mb-1">
                      <p className="text-sm font-semibold text-chronos-text group-hover:text-chronos-teal transition-colors">{item.title}</p>
                      {item.external && <ExternalLink className="w-3.5 h-3.5 text-chronos-muted" />}
                    </div>
                    <p className="text-xs text-chronos-muted">{item.desc}</p>
                  </a>
                ))}
              </div>
              <button onClick={finish} className="btn-primary mx-auto">
                {fromDashboard ? 'Back to Dashboard' : 'Go to Dashboard'} <ChevronRight className="w-4 h-4" />
              </button>
            </div>
          )}
        </motion.div>
      </AnimatePresence>

      {/* Back button (not on first or last step) */}
      {currentStep > 0 && currentStep < STEPS.length - 1 && (
        <button onClick={prev} className="mt-4 flex items-center gap-1.5 text-sm text-chronos-muted hover:text-chronos-text transition-colors">
          <ChevronLeft className="w-4 h-4" /> Back
        </button>
      )}
    </div>
  )
}

// ─── Helpers ──────────────────────────────────────────────────────────────────
function FeedbackBanner({ error, success }: { error: string | null; success: string | null }) {
  if (!error && !success) return null
  return (
    <div className={`rounded-lg p-3 flex items-center gap-2 text-sm ${
      error
        ? 'bg-chronos-danger/10 border border-chronos-danger/30 text-chronos-danger'
        : 'bg-chronos-emerald/10 border border-chronos-emerald/30 text-chronos-emerald'
    }`}>
      {error ? <AlertCircle className="w-4 h-4 shrink-0" /> : <CheckCircle2 className="w-4 h-4 shrink-0" />}
      {error ?? success}
    </div>
  )
}
