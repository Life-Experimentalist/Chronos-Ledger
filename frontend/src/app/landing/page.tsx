'use client'
// Copyright 2026 Chronos Ledger Contributors
// Licensed under the Apache License, Version 2.0

import { useState, useEffect } from 'react'
import Link from 'next/link'
import { motion } from 'framer-motion'
import {
  MapPin, Users, WifiOff, Bell, Calendar,
  Shield, Upload, ChevronRight, Check, Zap,
  BookOpen, UserCheck, Navigation, BarChart3, Star, Github,
} from 'lucide-react'
import { recordView } from '@/lib/telemetry'

const fadeUp = {
  hidden: { opacity: 0, y: 24 },
  show: (i = 0) => ({ opacity: 1, y: 0, transition: { delay: i * 0.07, duration: 0.4, ease: 'easeOut' } }),
}

export default function LandingPage() {
  const [activeFeature, setActiveFeature] = useState(0)

  useEffect(() => { recordView('landing') }, [])

  return (
    <div className="min-h-screen bg-chronos-dark text-chronos-text overflow-x-hidden">

      {/* ── Nav ─────────────────────────────────────────────────────────────── */}
      <nav className="fixed top-0 left-0 right-0 z-50 h-16 flex items-center justify-between px-6 md:px-12 border-b border-chronos-border/30 bg-chronos-dark/80 backdrop-blur-md">
        <img src="/logo-dark.svg" alt="Chronos Ledger" className="h-9 w-auto" />
        <div className="hidden md:flex items-center gap-8 text-sm text-chronos-muted">
          <a href="#features" className="hover:text-chronos-text transition-colors">Features</a>
          <a href="#roles" className="hover:text-chronos-text transition-colors">Who It&apos;s For</a>
          <a href="#install" className="hover:text-chronos-text transition-colors">Install</a>
          <a href="#api" className="hover:text-chronos-text transition-colors">API</a>
        </div>
        <div className="flex items-center gap-2">
          <a
            href="https://github.com/Life-Experimentalist/chronos-ledger"
            target="_blank"
            rel="noopener noreferrer"
            className="hidden sm:flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg border border-chronos-border text-chronos-muted hover:text-chronos-text hover:border-chronos-teal/40 transition-colors"
          >
            <Star className="w-3.5 h-3.5" /> Star
          </a>
          <Link
            href="/"
            className="px-4 py-2 text-sm font-medium rounded-lg bg-chronos-teal text-chronos-dark hover:bg-chronos-teal/90 transition-colors"
          >
            Sign In
          </Link>
        </div>
      </nav>

      {/* ── Hero ────────────────────────────────────────────────────────────── */}
      <section className="pt-36 pb-24 px-6 md:px-12 max-w-6xl mx-auto text-center">
        <motion.div variants={fadeUp} initial="hidden" animate="show" custom={0}>
          <span className="inline-flex items-center gap-1.5 text-xs font-medium px-3 py-1 rounded-full bg-chronos-teal/10 text-chronos-teal border border-chronos-teal/20 mb-6">
            <Zap className="w-3 h-3" /> Open Source · Apache 2.0 · Intranet-Ready
          </span>
        </motion.div>

        <motion.h1
          variants={fadeUp} initial="hidden" animate="show" custom={1}
          className="text-4xl md:text-6xl font-extrabold leading-tight tracking-tight mb-6"
        >
          Campus schedule &amp;{' '}
          <span className="bg-gradient-to-r from-chronos-teal to-chronos-emerald bg-clip-text text-transparent">
            attendance
          </span>
          <br />that works offline
        </motion.h1>

        <motion.p
          variants={fadeUp} initial="hidden" animate="show" custom={2}
          className="text-lg text-chronos-muted max-w-2xl mx-auto mb-10"
        >
          Chronos Ledger is a production-ready PWA for universities and colleges. Live timetables,
          geofenced attendance, faculty location resolution, and smart offline notifications — all
          self-hosted on your campus intranet.
        </motion.p>

        <motion.div
          variants={fadeUp} initial="hidden" animate="show" custom={3}
          className="flex flex-col sm:flex-row gap-3 justify-center"
        >
          <Link href="/" className="px-6 py-3 font-semibold rounded-xl bg-gradient-to-r from-chronos-teal to-chronos-emerald text-chronos-dark hover:opacity-90 transition-opacity flex items-center justify-center gap-2">
            Open App <ChevronRight className="w-4 h-4" />
          </Link>
          <a
            href="#install"
            className="px-6 py-3 font-semibold rounded-xl border border-chronos-border text-chronos-text-dim hover:text-chronos-text hover:border-chronos-teal/40 transition-colors"
          >
            Self-Host in 5 min
          </a>
        </motion.div>

        {/* Hero screenshot / terminal mockup */}
        <motion.div
          variants={fadeUp} initial="hidden" animate="show" custom={4}
          className="mt-16 rounded-2xl border border-chronos-border/50 bg-chronos-surface overflow-hidden shadow-2xl shadow-black/40 text-left"
        >
          <div className="flex items-center gap-1.5 px-4 py-3 border-b border-chronos-border/40 bg-chronos-surface/80">
            <span className="w-3 h-3 rounded-full bg-red-500/70" />
            <span className="w-3 h-3 rounded-full bg-yellow-500/70" />
            <span className="w-3 h-3 rounded-full bg-green-500/70" />
            <span className="ml-3 text-xs text-chronos-muted font-mono">chronos-ledger — docker compose up</span>
          </div>
          <div className="p-6 font-mono text-sm space-y-1.5">
            {[
              { text: '$ docker compose up -d', color: 'text-chronos-text' },
              { text: '[+] Running 5/5', color: 'text-chronos-emerald' },
              { text: ' ✔ chronos-db         Started', color: 'text-chronos-teal' },
              { text: ' ✔ chronos-cache      Started', color: 'text-chronos-teal' },
              { text: ' ✔ chronos-app        Healthy (migrations applied)', color: 'text-chronos-teal' },
              { text: ' ✔ chronos-frontend   Built → static files ready', color: 'text-chronos-teal' },
              { text: ' ✔ chronos-proxy      Listening on :80', color: 'text-chronos-teal' },
              { text: '', color: '' },
              { text: '  Admin login: admin@college.internal / ChronosAdmin2026!', color: 'text-chronos-warning' },
              { text: '  Swagger UI:  http://localhost/docs', color: 'text-chronos-muted' },
            ].map((line, i) => (
              <p key={i} className={`${line.color} leading-relaxed`}>{line.text || ' '}</p>
            ))}
          </div>
        </motion.div>
      </section>

      {/* ── Stats bar ───────────────────────────────────────────────────────── */}
      <section className="border-y border-chronos-border/30 bg-chronos-surface/40 py-8 px-6">
        <div className="max-w-4xl mx-auto grid grid-cols-2 md:grid-cols-4 gap-6 text-center">
          {[
            { label: 'API Endpoints', value: '30+' },
            { label: 'User Roles', value: '4' },
            { label: 'Offline-First', value: '100%' },
            { label: 'License', value: 'Apache 2.0' },
          ].map((s) => (
            <div key={s.label}>
              <p className="text-2xl font-bold text-chronos-teal">{s.value}</p>
              <p className="text-xs text-chronos-muted mt-0.5">{s.label}</p>
            </div>
          ))}
        </div>
      </section>

      {/* ── Features ────────────────────────────────────────────────────────── */}
      <section id="features" className="py-24 px-6 md:px-12 max-w-6xl mx-auto">
        <div className="text-center mb-16">
          <h2 className="text-3xl md:text-4xl font-bold mb-4">Everything a campus needs</h2>
          <p className="text-chronos-muted max-w-xl mx-auto">
            Designed for educational institutions with unreliable Wi-Fi, shared devices, and complex
            scheduling requirements.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
          {FEATURES.map((f, i) => (
            <motion.div
              key={f.title}
              variants={fadeUp} initial="hidden" whileInView="show" viewport={{ once: true }} custom={i % 3}
              onClick={() => setActiveFeature(i)}
              className={`glass-card p-6 cursor-default transition-all duration-200 hover:border-chronos-teal/30 ${
                activeFeature === i ? 'border-chronos-teal/40 shadow-teal-glow' : ''
              }`}
            >
              <div className={`w-10 h-10 rounded-xl flex items-center justify-center mb-4 ${f.iconBg}`}>
                <f.icon className={`w-5 h-5 ${f.iconColor}`} />
              </div>
              <h3 className="font-semibold text-chronos-text mb-2">{f.title}</h3>
              <p className="text-sm text-chronos-muted leading-relaxed">{f.desc}</p>
            </motion.div>
          ))}
        </div>
      </section>

      {/* ── Role dashboards ──────────────────────────────────────────────────── */}
      <section id="roles" className="py-24 px-6 md:px-12 bg-chronos-surface/30 border-y border-chronos-border/30">
        <div className="max-w-5xl mx-auto">
          <div className="text-center mb-16">
            <h2 className="text-3xl md:text-4xl font-bold mb-4">Four role-specific interfaces</h2>
            <p className="text-chronos-muted max-w-xl mx-auto">
              Each role sees exactly what they need — nothing more, nothing less.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
            {ROLES.map((role, i) => (
              <motion.div
                key={role.name}
                variants={fadeUp} initial="hidden" whileInView="show" viewport={{ once: true }} custom={i}
                className="glass-card p-6"
              >
                <div className="flex items-center gap-3 mb-4">
                  <div className={`w-9 h-9 rounded-lg flex items-center justify-center ${role.iconBg}`}>
                    <role.icon className={`w-5 h-5 ${role.iconColor}`} />
                  </div>
                  <div>
                    <p className="font-semibold text-chronos-text">{role.name}</p>
                    <p className="text-xs text-chronos-muted">{role.path}</p>
                  </div>
                </div>
                <ul className="space-y-2">
                  {role.capabilities.map((cap) => (
                    <li key={cap} className="flex items-start gap-2 text-sm text-chronos-text-dim">
                      <Check className="w-3.5 h-3.5 text-chronos-emerald mt-0.5 shrink-0" />
                      {cap}
                    </li>
                  ))}
                </ul>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* ── Offline section ──────────────────────────────────────────────────── */}
      <section className="py-24 px-6 md:px-12 max-w-5xl mx-auto">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-12 items-center">
          <motion.div variants={fadeUp} initial="hidden" whileInView="show" viewport={{ once: true }}>
            <span className="inline-flex items-center gap-1.5 text-xs font-medium px-3 py-1 rounded-full bg-chronos-warning/10 text-chronos-warning border border-chronos-warning/20 mb-4">
              <WifiOff className="w-3 h-3" /> Offline-First
            </span>
            <h2 className="text-3xl font-bold mb-4">Campus Wi-Fi drops. Your data doesn&apos;t.</h2>
            <p className="text-chronos-muted mb-6 leading-relaxed">
              Chronos Ledger uses Service Workers, IndexedDB, and Background Sync so students can
              mark attendance and faculty can view their schedule even without connectivity. Everything
              syncs automatically when the network returns.
            </p>
            <ul className="space-y-3">
              {[
                'Attendance marks queue in IndexedDB and flush on reconnect',
                'Today\'s schedule cached for 12 hours — works fully offline',
                'Class start notifications fire even when the app is closed',
                'Workbox NetworkFirst for APIs · CacheFirst for static assets',
              ].map((item) => (
                <li key={item} className="flex items-start gap-2.5 text-sm text-chronos-text-dim">
                  <Check className="w-4 h-4 text-chronos-teal mt-0.5 shrink-0" />
                  {item}
                </li>
              ))}
            </ul>
          </motion.div>

          <motion.div
            variants={fadeUp} initial="hidden" whileInView="show" viewport={{ once: true }} custom={1}
            className="glass-card p-6 space-y-3"
          >
            <p className="text-xs font-semibold uppercase tracking-wider text-chronos-muted">Offline queue status</p>
            {[
              { label: 'Attendance marks pending sync', count: 3, color: 'text-chronos-warning' },
              { label: 'Schedule cached (expires in 8h)', count: null, color: 'text-chronos-emerald', badge: 'FRESH' },
              { label: 'Service worker active', count: null, color: 'text-chronos-teal', badge: 'v2.1' },
            ].map((row) => (
              <div key={row.label} className="flex items-center justify-between py-2.5 border-b border-chronos-border/20 last:border-0">
                <div className="flex items-center gap-2">
                  <span className={`w-2 h-2 rounded-full ${row.color.replace('text-', 'bg-')} animate-pulse`} />
                  <span className="text-sm text-chronos-text-dim">{row.label}</span>
                </div>
                {row.count !== null ? (
                  <span className={`text-sm font-bold ${row.color}`}>{row.count}</span>
                ) : (
                  <span className={`text-xs font-medium px-2 py-0.5 rounded-full bg-current/10 ${row.color}`}>{row.badge}</span>
                )}
              </div>
            ))}
          </motion.div>
        </div>
      </section>

      {/* ── Install ──────────────────────────────────────────────────────────── */}
      <section id="install" className="py-24 px-6 md:px-12 bg-chronos-surface/30 border-y border-chronos-border/30">
        <div className="max-w-3xl mx-auto">
          <div className="text-center mb-12">
            <h2 className="text-3xl md:text-4xl font-bold mb-4">Up and running in minutes</h2>
            <p className="text-chronos-muted">Docker Compose is all you need.</p>
          </div>

          <div className="space-y-4">
            {INSTALL_STEPS.map((step, i) => (
              <motion.div
                key={step.title}
                variants={fadeUp} initial="hidden" whileInView="show" viewport={{ once: true }} custom={i}
                className="glass-card p-5"
              >
                <div className="flex items-start gap-4">
                  <span className="w-7 h-7 rounded-full bg-chronos-teal/10 text-chronos-teal text-xs font-bold flex items-center justify-center shrink-0 mt-0.5">
                    {i + 1}
                  </span>
                  <div className="flex-1 min-w-0">
                    <p className="font-medium text-chronos-text mb-2">{step.title}</p>
                    <pre className="bg-chronos-dark rounded-lg px-4 py-3 text-sm font-mono text-chronos-teal overflow-x-auto border border-chronos-border/40">
                      <code>{step.code}</code>
                    </pre>
                    {step.note && <p className="text-xs text-chronos-muted mt-2">{step.note}</p>}
                  </div>
                </div>
              </motion.div>
            ))}
          </div>

          <div className="mt-8 glass-card p-5 border border-chronos-warning/20 bg-chronos-warning/5">
            <p className="text-sm font-semibold text-chronos-warning mb-2">Before you deploy</p>
            <ul className="space-y-1.5">
              {[
                'Change JWT_SECRET_SIGNING_KEY to a random 64-char string',
                'Change the seed admin password immediately after first login',
                'Generate VAPID keys for push notifications: npx web-push generate-vapid-keys',
                'Restrict /docs and /redoc to internal IPs in nginx.conf for production',
              ].map((item) => (
                <li key={item} className="flex items-start gap-2 text-xs text-chronos-text-dim">
                  <span className="text-chronos-warning shrink-0 mt-0.5">→</span>
                  {item}
                </li>
              ))}
            </ul>
          </div>
        </div>
      </section>

      {/* ── API section ──────────────────────────────────────────────────────── */}
      <section id="api" className="py-24 px-6 md:px-12 max-w-5xl mx-auto">
        <div className="text-center mb-12">
          <h2 className="text-3xl md:text-4xl font-bold mb-4">First-class REST API</h2>
          <p className="text-chronos-muted max-w-xl mx-auto">
            Full OpenAPI 3.0 spec. Every endpoint is documented and testable via Swagger UI at <code className="text-chronos-teal">/docs</code>.
          </p>
        </div>

        <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
          {API_GROUPS.map((g, i) => (
            <motion.div
              key={g.group}
              variants={fadeUp} initial="hidden" whileInView="show" viewport={{ once: true }} custom={i % 3}
              className="glass-card p-4"
            >
              <p className="text-xs font-semibold uppercase tracking-wider text-chronos-teal mb-3">{g.group}</p>
              <ul className="space-y-1.5">
                {g.endpoints.map((ep) => (
                  <li key={ep} className="text-xs text-chronos-text-dim font-mono">{ep}</li>
                ))}
              </ul>
            </motion.div>
          ))}
        </div>

        <div className="mt-8 text-center">
          <p className="text-sm text-chronos-muted">
            Subscribe to your personal iCal feed:{' '}
            <code className="text-chronos-teal text-xs bg-chronos-surface px-2 py-0.5 rounded">
              GET /api/v1/sync/user-feed/{'{'}feed_token{'}'}.ics
            </code>
          </p>
        </div>
      </section>

      {/* ── GitHub CTA ──────────────────────────────────────────────────────── */}
      <section className="py-20 px-6 md:px-12">
        <div className="max-w-3xl mx-auto text-center">
          <motion.div variants={fadeUp} initial="hidden" whileInView="show" viewport={{ once: true }}>
            <div className="inline-flex items-center justify-center w-14 h-14 rounded-2xl bg-gradient-to-br from-chronos-teal to-chronos-emerald mb-6 shadow-teal-strong">
              <Github className="w-7 h-7 text-chronos-dark" />
            </div>
            <h2 className="text-3xl font-bold mb-4">Open Source · Apache 2.0</h2>
            <p className="text-chronos-muted mb-8 max-w-xl mx-auto">
              Chronos Ledger is freely available under the Apache 2.0 license. Fork it, self-host it,
              extend it. Contributions, bug reports, and feature requests are welcome.
            </p>
            <div className="flex flex-col sm:flex-row gap-3 justify-center">
              <a
                href="https://github.com/Life-Experimentalist/chronos-ledger"
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center justify-center gap-2 px-6 py-3 font-semibold rounded-xl border border-chronos-border text-chronos-text hover:border-chronos-teal/40 hover:text-chronos-teal transition-colors"
              >
                <Github className="w-4 h-4" /> View on GitHub
              </a>
              <a
                href="https://github.com/Life-Experimentalist/chronos-ledger"
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center justify-center gap-2 px-6 py-3 font-semibold rounded-xl bg-gradient-to-r from-chronos-teal to-chronos-emerald text-chronos-dark hover:opacity-90 transition-opacity"
              >
                <Star className="w-4 h-4" /> Star the repo
              </a>
            </div>
            <div className="mt-8 grid grid-cols-3 gap-4 max-w-sm mx-auto">
              {[
                { label: 'Version', value: 'v1.0.0' },
                { label: 'License', value: 'Apache 2.0' },
                { label: 'Language', value: 'Python · TS' },
              ].map((s) => (
                <div key={s.label} className="glass-card p-3 text-center">
                  <p className="text-sm font-semibold text-chronos-teal">{s.value}</p>
                  <p className="text-xs text-chronos-muted mt-0.5">{s.label}</p>
                </div>
              ))}
            </div>
          </motion.div>
        </div>
      </section>

      {/* ── Footer ──────────────────────────────────────────────────────────── */}
      <footer className="border-t border-chronos-border/30 py-12 px-6 md:px-12">
        <div className="max-w-5xl mx-auto flex flex-col md:flex-row items-center justify-between gap-4">
          <img src="/logo-dark.svg" alt="Chronos Ledger" className="h-7 w-auto" />
          <p className="text-xs text-chronos-muted text-center">
            Licensed under the{' '}
            <span className="text-chronos-teal">Apache License 2.0</span>.
            Built for campus intranet deployments.
          </p>
          <div className="flex items-center gap-3">
            <a
              href="https://github.com/Life-Experimentalist/chronos-ledger"
              target="_blank"
              rel="noopener noreferrer"
              className="text-xs text-chronos-muted hover:text-chronos-text transition-colors flex items-center gap-1"
            >
              <Github className="w-3.5 h-3.5" /> GitHub
            </a>
            <Link
              href="/"
              className="text-sm font-medium text-chronos-teal hover:text-chronos-teal/80 transition-colors flex items-center gap-1"
            >
              Open App <ChevronRight className="w-3.5 h-3.5" />
            </Link>
          </div>
        </div>
      </footer>
    </div>
  )
}

// ── Static data ──────────────────────────────────────────────────────────────

const FEATURES = [
  {
    title: 'Live Faculty Locator',
    desc: '4-tier resolution: Redis manual override → daily exception → master timetable → base station fallback. Always know where faculty are.',
    icon: Navigation,
    iconBg: 'bg-chronos-teal/10',
    iconColor: 'text-chronos-teal',
  },
  {
    title: '3D Geofenced Attendance',
    desc: 'Haversine surface distance + 4m altitude check prevents cross-floor spoofing. Falls back to Wi-Fi BSSID when GPS accuracy exceeds 30m.',
    icon: MapPin,
    iconBg: 'bg-chronos-emerald/10',
    iconColor: 'text-chronos-emerald',
  },
  {
    title: 'Reverse RSVP Absences',
    desc: 'Presence is the default. Faculty file absence requests; their manager approves. Approved absences auto-cascade ON_LEAVE to the daily ledger.',
    icon: UserCheck,
    iconBg: 'bg-chronos-accent/10',
    iconColor: 'text-chronos-accent',
  },
  {
    title: 'Real-Time WebSocket',
    desc: 'JWT-authenticated persistent connections. Instant guest handshake requests, absence approvals, and campus broadcasts — no polling.',
    icon: Zap,
    iconBg: 'bg-chronos-warning/10',
    iconColor: 'text-chronos-warning',
  },
  {
    title: 'CSV Schedule Import',
    desc: 'Bulk-import the semester timetable from a single student-centric CSV. Upserts students, course offerings, registrations, and master slots atomically.',
    icon: Upload,
    iconBg: 'bg-purple-500/10',
    iconColor: 'text-purple-400',
  },
  {
    title: 'iCalendar Sync',
    desc: 'Live 37-day .ics feed per user. Subscribe directly in Google Calendar, Apple Calendar, or Outlook. Updates reflect approved leaves and proxy swaps.',
    icon: Calendar,
    iconBg: 'bg-sky-500/10',
    iconColor: 'text-sky-400',
  },
  {
    title: 'Guest Kiosk',
    desc: 'No login required. Visitors fill a check-in form; the target faculty receives an instant WebSocket notification with Approve/Decline actions.',
    icon: Users,
    iconBg: 'bg-pink-500/10',
    iconColor: 'text-pink-400',
  },
  {
    title: 'Offline Notifications',
    desc: 'Class reminders fire 15 minutes before start — even offline. Scheduled via JS timers while active and Periodic Background Sync when the app is closed.',
    icon: Bell,
    iconBg: 'bg-chronos-teal/10',
    iconColor: 'text-chronos-teal',
  },
  {
    title: 'Role-Based Access',
    desc: 'SUPER_ADMIN, DEPT_ADMIN, FACULTY, STUDENT. JWT RBAC enforced at every endpoint. Each role sees only their own data.',
    icon: Shield,
    iconBg: 'bg-chronos-danger/10',
    iconColor: 'text-chronos-danger',
  },
]

const ROLES = [
  {
    name: 'Admin / Dept Admin',
    path: '/admin/dashboard',
    icon: BarChart3,
    iconBg: 'bg-chronos-teal/10',
    iconColor: 'text-chronos-teal',
    capabilities: [
      'CSV timetable import and cycle management',
      'Proxy assignment and absence approval',
      'Master ledger view with operational state overrides',
      'User provisioning and department management',
    ],
  },
  {
    name: 'Faculty',
    path: '/faculty/dashboard',
    icon: BookOpen,
    iconBg: 'bg-chronos-emerald/10',
    iconColor: 'text-chronos-emerald',
    capabilities: [
      'Availability status switcher (4 states)',
      'Attendance matrix: mark whole class in one tap',
      'Submit and track absence requests',
      'Guest interaction desk with real-time notifications',
    ],
  },
  {
    name: 'Student',
    path: '/student/dashboard',
    icon: UserCheck,
    iconBg: 'bg-chronos-accent/10',
    iconColor: 'text-chronos-accent',
    capabilities: [
      'Live timeline of today\'s classes with status indicators',
      '3D geofenced attendance marking with GPS/BSSID',
      'Faculty locator with real-time availability',
      'Offline attendance queue with background sync',
    ],
  },
  {
    name: 'Guest (no login)',
    path: '/guest/kiosk',
    icon: Users,
    iconBg: 'bg-chronos-warning/10',
    iconColor: 'text-chronos-warning',
    capabilities: [
      'Search faculty directory by name',
      'Submit check-in request with purpose',
      'Real-time notification to target faculty',
      'Public availability status display',
    ],
  },
]

const INSTALL_STEPS = [
  {
    title: 'Clone and run the setup script',
    code: 'git clone https://github.com/Life-Experimentalist/chronos-ledger.git\ncd chronos-ledger\nchmod +x setup.sh && ./setup.sh',
    note: 'Auto-detects your LAN IP, generates JWT & DB secrets, and starts all services.',
  },
  {
    title: 'Or pull pre-built images from GHCR (fastest)',
    code: 'export JWT_SECRET_SIGNING_KEY=$(openssl rand -hex 32)\nexport DB_PASSWORD=$(openssl rand -base64 24 | tr -d \'/+=\' | head -c 32)\nexport GHCR_OWNER=Life-Experimentalist\ncurl -fsSL https://github.com/Life-Experimentalist/chronos-ledger/releases/latest/download/docker-compose.prod.yml | docker compose -f - up -d',
    note: 'No build required. Pin a version: VERSION=v1.2.0 docker compose -f docker-compose.prod.yml up -d',
  },
  {
    title: 'Generate push notification keys (optional)',
    code: 'npx web-push generate-vapid-keys\n# Add output to .env as VAPID_PUBLIC_KEY / VAPID_PRIVATE_KEY',
    note: 'Skip this step if you do not need browser push notifications.',
  },
  {
    title: 'Open the app and change the default password',
    code: '# App:     http://<your-server-ip>\n# API docs: http://<your-server-ip>/docs\n# Login:    admin@college.internal / ChronosAdmin2026!',
    note: 'The setup script prints the exact URL when it finishes.',
  },
]

const API_GROUPS = [
  {
    group: 'Auth',
    endpoints: ['POST /auth/login', 'GET /auth/me', 'POST /auth/change-password'],
  },
  {
    group: 'Schedule',
    endpoints: ['GET /schedule/ledger/today', 'GET /schedule/faculty/{id}/location', 'POST /schedule/cycles'],
  },
  {
    group: 'Attendance',
    endpoints: ['POST /attendance/mark', 'POST /attendance/batch', 'POST /attendance/absence'],
  },
  {
    group: 'Guest',
    endpoints: ['POST /guest/register-checkin', 'GET /guest/directory', 'PATCH /guest/{id}/decide'],
  },
  {
    group: 'Ingestion',
    endpoints: ['POST /ingestion/upload-csv', 'POST /ingestion/generate-ledger'],
  },
  {
    group: 'Sync',
    endpoints: ['GET /sync/user-feed/{feed_token}.ics', 'WS /ws?token={jwt}', 'GET /ws/stats'],
  },
]
