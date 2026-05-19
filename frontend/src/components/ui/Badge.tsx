// Copyright 2026 Chronos Ledger Contributors
// Licensed under the Apache License, Version 2.0

import { clsx } from 'clsx'
import type { DynamicState, VerificationMetric, LogVerificationState, AccessReadiness } from '@/types'

type BadgeVariant = 'teal' | 'emerald' | 'warning' | 'danger' | 'muted' | 'accent'

interface BadgeProps {
  variant?: BadgeVariant
  children: React.ReactNode
  className?: string
  dot?: boolean
}

const variantClasses: Record<BadgeVariant, string> = {
  teal: 'bg-chronos-teal/10 text-chronos-teal border-chronos-teal/20',
  emerald: 'bg-chronos-emerald/10 text-chronos-emerald border-chronos-emerald/20',
  warning: 'bg-chronos-warning/10 text-chronos-warning border-chronos-warning/20',
  danger: 'bg-chronos-danger/10 text-chronos-danger border-chronos-danger/20',
  muted: 'bg-chronos-surface text-chronos-muted border-chronos-border/50',
  accent: 'bg-chronos-accent/10 text-chronos-accent border-chronos-accent/20',
}

export function Badge({ variant = 'muted', children, className, dot }: BadgeProps) {
  return (
    <span className={clsx('badge border', variantClasses[variant], className)}>
      {dot && (
        <span
          className={clsx('w-1.5 h-1.5 rounded-full', {
            'bg-chronos-teal': variant === 'teal',
            'bg-chronos-emerald': variant === 'emerald',
            'bg-chronos-warning': variant === 'warning',
            'bg-chronos-danger': variant === 'danger',
            'bg-chronos-muted': variant === 'muted',
            'bg-chronos-accent': variant === 'accent',
          })}
        />
      )}
      {children}
    </span>
  )
}

export function DynamicStateBadge({ state }: { state: DynamicState }) {
  const map: Record<DynamicState, { label: string; variant: BadgeVariant }> = {
    SCHEDULED: { label: 'Scheduled', variant: 'teal' },
    ON_LEAVE: { label: 'On Leave', variant: 'danger' },
    PROXY_SUBSTITUTE: { label: 'Proxy', variant: 'warning' },
    LUNCH: { label: 'Lunch', variant: 'muted' },
    INTERNAL_MEETING: { label: 'Meeting', variant: 'accent' },
    ADHOC_EVENT: { label: 'Ad-Hoc', variant: 'accent' },
  }
  const { label, variant } = map[state] || { label: state, variant: 'muted' as BadgeVariant }
  return <Badge variant={variant} dot>{label}</Badge>
}

export function AttendanceBadge({ status }: { status: VerificationMetric }) {
  const map: Record<VerificationMetric, { label: string; variant: BadgeVariant }> = {
    PRESENT: { label: 'Present', variant: 'emerald' },
    ABSENT: { label: 'Absent', variant: 'danger' },
    LATE: { label: 'Late', variant: 'warning' },
  }
  const { label, variant } = map[status]
  return <Badge variant={variant} dot>{label}</Badge>
}

export function RsvpStateBadge({ state }: { state: LogVerificationState }) {
  const map: Record<LogVerificationState, { label: string; variant: BadgeVariant }> = {
    PENDING_VERIFICATION: { label: 'Pending', variant: 'warning' },
    VERIFIED_APPROVED: { label: 'Approved', variant: 'emerald' },
    VERIFIED_DENIED: { label: 'Denied', variant: 'danger' },
  }
  const { label, variant } = map[state]
  return <Badge variant={variant} dot>{label}</Badge>
}

export function OccupancyBadge({ status }: { status: AccessReadiness }) {
  const map: Record<AccessReadiness, { label: string; variant: BadgeVariant }> = {
    OPEN_AD_HOC: { label: 'Available', variant: 'teal' },
    VERY_FREE: { label: 'Very Free', variant: 'emerald' },
    BUSY: { label: 'Occupied', variant: 'warning' },
    CRITICAL_DO_NOT_DISTURB: { label: 'Do Not Disturb', variant: 'danger' },
  }
  const { label, variant } = map[status]
  return <Badge variant={variant} dot>{label}</Badge>
}
