'use client'
// Copyright 2026 Chronos Ledger Contributors
// Licensed under the Apache License, Version 2.0

import { useState } from 'react'
import { motion } from 'framer-motion'
import { CheckCircle2, Clock, Coffee, AlertOctagon, Loader2 } from 'lucide-react'
import { usersApi } from '@/lib/api'
import type { AccessReadiness } from '@/types'

interface StatusOption {
  value: AccessReadiness
  label: string
  icon: React.ElementType
  color: string
  bg: string
  border: string
}

const STATUS_OPTIONS: StatusOption[] = [
  { value: 'OPEN_AD_HOC', label: 'Available', icon: CheckCircle2, color: 'text-chronos-teal', bg: 'bg-chronos-teal/10', border: 'border-chronos-teal/30' },
  { value: 'VERY_FREE', label: 'Very Free', icon: CheckCircle2, color: 'text-chronos-emerald', bg: 'bg-chronos-emerald/10', border: 'border-chronos-emerald/30' },
  { value: 'BUSY', label: 'Busy', icon: Clock, color: 'text-chronos-warning', bg: 'bg-chronos-warning/10', border: 'border-chronos-warning/30' },
  { value: 'CRITICAL_DO_NOT_DISTURB', label: 'Do Not Disturb', icon: AlertOctagon, color: 'text-chronos-danger', bg: 'bg-chronos-danger/10', border: 'border-chronos-danger/30' },
]

interface StatusSwitcherProps {
  userId: string
}

export function StatusSwitcher({ userId }: StatusSwitcherProps) {
  const [current, setCurrent] = useState<AccessReadiness>('OPEN_AD_HOC')
  const [updating, setUpdating] = useState(false)

  const handleSelect = async (value: AccessReadiness) => {
    if (value === current) return
    setUpdating(true)
    try {
      await usersApi.updateStatus(userId, value)
      setCurrent(value)
    } finally {
      setUpdating(false)
    }
  }

  return (
    <div className="glass-card p-4">
      <div className="flex items-center justify-between mb-3">
        <p className="section-title">My Availability Status</p>
        {updating && <Loader2 className="w-4 h-4 animate-spin text-chronos-teal" />}
      </div>
      <div className="flex flex-wrap gap-2">
        {STATUS_OPTIONS.map((opt) => {
          const Icon = opt.icon
          const active = current === opt.value
          return (
            <motion.button
              key={opt.value}
              onClick={() => handleSelect(opt.value)}
              whileTap={{ scale: 0.97 }}
              className={`flex items-center gap-2 px-3 py-2 rounded-lg border text-sm font-medium transition-all duration-200 ${
                active ? `${opt.bg} ${opt.border} ${opt.color} shadow-sm` : 'border-chronos-border/40 text-chronos-text-dim hover:border-chronos-border hover:text-chronos-text'
              }`}
            >
              <Icon className="w-4 h-4" />
              {opt.label}
              {active && <span className="w-1.5 h-1.5 rounded-full bg-current ml-0.5" />}
            </motion.button>
          )
        })}
      </div>
    </div>
  )
}
