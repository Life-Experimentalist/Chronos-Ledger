// Copyright 2026 Chronos Ledger Contributors
// Licensed under the Apache License, Version 2.0

import { create } from 'zustand'

export type NotificationType = 'info' | 'success' | 'warning' | 'error'

export interface Notification {
  id: string
  type: NotificationType
  title: string
  message: string
  timestamp: number
  read: boolean
  actionUrl?: string
}

interface NotificationState {
  notifications: Notification[]
  unreadCount: number
  push: (n: Omit<Notification, 'id' | 'timestamp' | 'read'>) => void
  markRead: (id: string) => void
  markAllRead: () => void
  dismiss: (id: string) => void
  clear: () => void
}

export const useNotificationStore = create<NotificationState>((set, get) => ({
  notifications: [],
  unreadCount: 0,

  push: (n) => {
    const notification: Notification = {
      ...n,
      id: `${Date.now()}_${Math.random().toString(36).slice(2, 7)}`,
      timestamp: Date.now(),
      read: false,
    }
    set((state) => ({
      notifications: [notification, ...state.notifications].slice(0, 50),
      unreadCount: state.unreadCount + 1,
    }))
  },

  markRead: (id) => {
    set((state) => ({
      notifications: state.notifications.map((n) => (n.id === id ? { ...n, read: true } : n)),
      unreadCount: Math.max(0, state.unreadCount - 1),
    }))
  },

  markAllRead: () => {
    set((state) => ({
      notifications: state.notifications.map((n) => ({ ...n, read: true })),
      unreadCount: 0,
    }))
  },

  dismiss: (id) => {
    set((state) => {
      const notif = state.notifications.find((n) => n.id === id)
      return {
        notifications: state.notifications.filter((n) => n.id !== id),
        unreadCount: notif && !notif.read ? Math.max(0, state.unreadCount - 1) : state.unreadCount,
      }
    })
  },

  clear: () => set({ notifications: [], unreadCount: 0 }),
}))
