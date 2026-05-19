'use client'
// Copyright 2026 Chronos Ledger Contributors
// Licensed under the Apache License, Version 2.0

import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Bell, CheckCheck, X, AlertCircle, CheckCircle2, Info, AlertTriangle } from 'lucide-react'
import { useNotificationStore } from '@/store/notifications'
import type { NotificationType } from '@/store/notifications'
import { formatDistanceToNow } from 'date-fns'

const iconMap: Record<NotificationType, React.ElementType> = {
  info: Info,
  success: CheckCircle2,
  warning: AlertTriangle,
  error: AlertCircle,
}

const colorMap: Record<NotificationType, string> = {
  info: 'text-chronos-teal',
  success: 'text-chronos-emerald',
  warning: 'text-chronos-warning',
  error: 'text-chronos-danger',
}

export function NotificationPanel() {
  const [open, setOpen] = useState(false)
  const { notifications, unreadCount, markAllRead, dismiss } = useNotificationStore()

  return (
    <div className="relative">
      <button
        onClick={() => setOpen(!open)}
        className="relative p-2 rounded-lg hover:bg-chronos-surface text-chronos-text-dim hover:text-chronos-text transition-colors"
      >
        <Bell className="w-5 h-5" />
        {unreadCount > 0 && (
          <span className="absolute top-0.5 right-0.5 w-4 h-4 bg-chronos-danger rounded-full text-[9px] font-bold text-white flex items-center justify-center">
            {unreadCount > 9 ? '9+' : unreadCount}
          </span>
        )}
      </button>

      <AnimatePresence>
        {open && (
          <>
            <div className="fixed inset-0 z-40" onClick={() => setOpen(false)} />
            <motion.div
              initial={{ opacity: 0, y: 8, scale: 0.97 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: 8, scale: 0.97 }}
              transition={{ duration: 0.15 }}
              className="absolute right-0 top-10 w-80 glass-card z-50 overflow-hidden"
            >
              <div className="flex items-center justify-between px-4 py-3 border-b border-chronos-border/40">
                <span className="text-sm font-semibold text-chronos-text">Notifications</span>
                {unreadCount > 0 && (
                  <button
                    onClick={markAllRead}
                    className="flex items-center gap-1 text-xs text-chronos-teal hover:text-chronos-teal-glow transition-colors"
                  >
                    <CheckCheck className="w-3.5 h-3.5" />
                    Mark all read
                  </button>
                )}
              </div>

              <div className="max-h-96 overflow-y-auto divide-y divide-chronos-border/20">
                {notifications.length === 0 ? (
                  <div className="px-4 py-8 text-center text-chronos-muted text-sm">
                    No notifications
                  </div>
                ) : (
                  notifications.map((n) => {
                    const Icon = iconMap[n.type]
                    return (
                      <div
                        key={n.id}
                        className={`flex gap-3 px-4 py-3 transition-colors ${!n.read ? 'bg-chronos-teal/5' : ''}`}
                      >
                        <Icon className={`w-4 h-4 mt-0.5 shrink-0 ${colorMap[n.type]}`} />
                        <div className="flex-1 min-w-0">
                          <p className="text-sm font-medium text-chronos-text">{n.title}</p>
                          <p className="text-xs text-chronos-text-dim mt-0.5 line-clamp-2">{n.message}</p>
                          <p className="text-[10px] text-chronos-muted mt-1">
                            {formatDistanceToNow(n.timestamp, { addSuffix: true })}
                          </p>
                        </div>
                        <button
                          onClick={() => dismiss(n.id)}
                          className="p-1 text-chronos-muted hover:text-chronos-text transition-colors shrink-0"
                        >
                          <X className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    )
                  })
                )}
              </div>
            </motion.div>
          </>
        )}
      </AnimatePresence>
    </div>
  )
}
