'use client'
// Copyright 2026 Chronos Ledger Contributors
// Licensed under the Apache License, Version 2.0

import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { motion, AnimatePresence } from 'framer-motion'
import { Lock, Mail, AlertCircle, Loader2, Eye, EyeOff } from 'lucide-react'
import { useAuthStore } from '@/store/auth'
import { roleRedirectPath, getStoredUser } from '@/lib/auth'

const loginSchema = z.object({
  email: z.string().email('Enter a valid email'),
  password: z.string().min(1, 'Password is required'),
})
type LoginForm = z.infer<typeof loginSchema>

export default function LoginPage() {
  const router = useRouter()
  const { login, isLoading, error, clearError } = useAuthStore()
  const [showPassword, setShowPassword] = useState(false)

  useEffect(() => {
    const user = getStoredUser()
    if (user) router.push(roleRedirectPath(user.role))
  }, [router])

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<LoginForm>({ resolver: zodResolver(loginSchema) })

  const onSubmit = async (data: LoginForm) => {
    clearError()
    const user = await login(data.email, data.password).catch(() => null)
    if (!user) return
    if (user.initial_login_state && (user.role === 'SUPER_ADMIN' || user.role === 'DEPT_ADMIN')) {
      router.push('/admin/onboarding')
    } else {
      router.push(roleRedirectPath(user.role))
    }
  }

  return (
    <div className="min-h-screen bg-chronos-dark flex items-center justify-center p-4 overflow-hidden relative">
      {/* Ambient background glows */}
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        <div className="absolute -top-40 -left-40 w-96 h-96 bg-chronos-teal/5 rounded-full blur-3xl" />
        <div className="absolute -bottom-40 -right-40 w-96 h-96 bg-chronos-emerald/5 rounded-full blur-3xl" />
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[600px] bg-chronos-teal/3 rounded-full blur-3xl" />
      </div>

      <motion.div
        initial={{ opacity: 0, y: 24 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5, ease: 'easeOut' }}
        className="w-full max-w-md relative"
      >
        {/* Logo & Brand */}
        <div className="text-center mb-8">
          <img src="/icon.png" alt="Chronos Ledger" className="w-16 h-16 rounded-2xl mb-4 shadow-teal-strong" />
          <h1 className="text-3xl font-bold text-chronos-text teal-glow-text">Chronos Ledger</h1>
          <p className="text-chronos-text-dim mt-1 text-sm">Campus Schedule & Attendance Management</p>
        </div>

        {/* Login Card */}
        <div className="glass-card p-8">
          <h2 className="text-lg font-semibold text-chronos-text mb-6">Sign in to your account</h2>

          <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
            <div>
              <label className="block text-xs font-medium text-chronos-text-dim mb-1.5 uppercase tracking-wider">
                Email Address
              </label>
              <div className="relative">
                <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-chronos-muted" />
                <input
                  {...register('email')}
                  type="email"
                  placeholder="you@college.internal"
                  className="input-field pl-10"
                  autoComplete="email"
                />
              </div>
              {errors.email && (
                <p className="text-chronos-danger text-xs mt-1 flex items-center gap-1">
                  <AlertCircle className="w-3 h-3" /> {errors.email.message}
                </p>
              )}
            </div>

            <div>
              <label className="block text-xs font-medium text-chronos-text-dim mb-1.5 uppercase tracking-wider">
                Password
              </label>
              <div className="relative">
                <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-chronos-muted" />
                <input
                  {...register('password')}
                  type={showPassword ? 'text' : 'password'}
                  placeholder="••••••••"
                  className="input-field pl-10 pr-10"
                  autoComplete="current-password"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-chronos-muted hover:text-chronos-text transition-colors"
                >
                  {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              </div>
              {errors.password && (
                <p className="text-chronos-danger text-xs mt-1 flex items-center gap-1">
                  <AlertCircle className="w-3 h-3" /> {errors.password.message}
                </p>
              )}
            </div>

            <AnimatePresence>
              {error && (
                <motion.div
                  initial={{ opacity: 0, height: 0 }}
                  animate={{ opacity: 1, height: 'auto' }}
                  exit={{ opacity: 0, height: 0 }}
                  className="bg-chronos-danger/10 border border-chronos-danger/30 rounded-lg p-3 flex items-center gap-2 text-chronos-danger text-sm"
                >
                  <AlertCircle className="w-4 h-4 shrink-0" />
                  {error}
                </motion.div>
              )}
            </AnimatePresence>

            <button
              type="submit"
              disabled={isLoading}
              className="btn-primary w-full justify-center mt-2"
            >
              {isLoading ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  Authenticating...
                </>
              ) : (
                'Sign In'
              )}
            </button>
          </form>

          <div className="mt-6 pt-5 border-t border-chronos-border/40 space-y-2">
            <p className="text-xs text-chronos-muted text-center">
              Guest campus visit?{' '}
              <a href="/guest/kiosk" className="text-chronos-teal hover:underline">
                Use the kiosk
              </a>
            </p>
            <p className="text-xs text-chronos-muted text-center">
              New here?{' '}
              <a href="/landing" className="text-chronos-teal hover:underline">
                Learn about Chronos Ledger
              </a>
            </p>
          </div>
        </div>

        <p className="text-center text-xs text-chronos-muted mt-6">
          © 2026 Chronos Ledger · Apache 2.0
        </p>
      </motion.div>
    </div>
  )
}
