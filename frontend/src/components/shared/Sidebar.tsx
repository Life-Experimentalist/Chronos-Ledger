'use client'
// Copyright 2026 Chronos Ledger Contributors
// Licensed under the Apache License, Version 2.0

import { useState } from 'react'
import Link from 'next/link'
import { usePathname, useRouter } from 'next/navigation'
import { motion, AnimatePresence } from 'framer-motion'
import { clsx } from 'clsx'
import {
  LayoutDashboard, Users, Calendar, CheckSquare,
  LogOut, Bell, ChevronLeft, ChevronRight, Settings,
  FileSpreadsheet, MapPin, UserCheck,
} from 'lucide-react'
import { useAuthStore } from '@/store/auth'
import { useNotificationStore } from '@/store/notifications'
import type { InstitutionalRole } from '@/types'

interface NavItem {
  icon: React.ElementType
  label: string
  href: string
  roles?: InstitutionalRole[]
}

const NAV_ITEMS: NavItem[] = [
  { icon: LayoutDashboard, label: 'Dashboard', href: '/admin/dashboard', roles: ['SUPER_ADMIN', 'UNIT_ADMIN'] },
  { icon: FileSpreadsheet, label: 'Import Data', href: '/admin/dashboard?tab=import', roles: ['SUPER_ADMIN', 'UNIT_ADMIN'] },
  { icon: Users, label: 'Proxy Management', href: '/admin/dashboard?tab=proxy', roles: ['SUPER_ADMIN', 'UNIT_ADMIN'] },
  { icon: LayoutDashboard, label: 'Dashboard', href: '/staff/dashboard', roles: ['STAFF'] },
  { icon: CheckSquare, label: 'Attendance', href: '/staff/dashboard?tab=attendance', roles: ['STAFF'] },
  { icon: UserCheck, label: 'Guests & Requests', href: '/staff/dashboard?tab=guests', roles: ['STAFF'] },
  { icon: LayoutDashboard, label: 'My Schedule', href: '/member/dashboard', roles: ['MEMBER'] },
  { icon: MapPin, label: 'Mark Presence', href: '/member/dashboard?tab=attendance', roles: ['MEMBER'] },
  { icon: Calendar, label: 'Calendar Sync', href: '/member/dashboard?tab=calendar', roles: ['MEMBER'] },
]

interface SidebarProps {
  role: InstitutionalRole
}

export function Sidebar({ role }: SidebarProps) {
  const [collapsed, setCollapsed] = useState(false)
  const pathname = usePathname()
  const router = useRouter()
  const { logout } = useAuthStore()
  const { unreadCount } = useNotificationStore()

  const items = NAV_ITEMS.filter((item) => !item.roles || item.roles.includes(role))

  const handleLogout = () => {
    logout()
    router.push('/')
  }

  return (
    <motion.aside
      animate={{ width: collapsed ? 64 : 240 }}
      transition={{ duration: 0.2, ease: 'easeInOut' }}
      className="flex flex-col h-screen bg-chronos-surface border-r border-chronos-border/40 shrink-0 overflow-hidden"
    >
      {/* Brand */}
      <div className={clsx('flex items-center h-16 px-4 border-b border-chronos-border/40 overflow-hidden', collapsed ? 'justify-center' : 'gap-3')}>
        <img src="/icon.png" alt="Chronos Ledger" className="w-8 h-8 rounded-lg shrink-0" />
        <AnimatePresence>
          {!collapsed && (
            <motion.img
              src="/logo-dark.svg"
              alt="Chronos Ledger"
              initial={{ opacity: 0, x: -8 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: -8 }}
              className="h-8 w-auto object-contain"
              style={{ maxWidth: 140 }}
            />
          )}
        </AnimatePresence>
      </div>

      {/* Nav */}
      <nav className="flex-1 px-2 py-4 space-y-1 overflow-y-auto scrollbar-hide">
        {items.map((item) => {
          const Icon = item.icon
          const active = pathname === item.href.split('?')[0]
          return (
            <Link
              key={item.href}
              href={item.href}
              className={clsx(
                'flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition-all duration-150',
                active
                  ? 'bg-chronos-teal/10 text-chronos-teal border border-chronos-teal/20'
                  : 'text-chronos-text-dim hover:text-chronos-text hover:bg-chronos-card/60',
                collapsed && 'justify-center'
              )}
              title={collapsed ? item.label : undefined}
            >
              <Icon className="w-4 h-4 shrink-0" />
              <AnimatePresence>
                {!collapsed && (
                  <motion.span
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    exit={{ opacity: 0 }}
                    className="whitespace-nowrap"
                  >
                    {item.label}
                  </motion.span>
                )}
              </AnimatePresence>
            </Link>
          )
        })}
      </nav>

      {/* Bottom controls */}
      <div className="px-2 pb-4 space-y-1 border-t border-chronos-border/40 pt-3">
        <button
          onClick={() => {}}
          className={clsx(
            'w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm text-chronos-text-dim hover:text-chronos-text hover:bg-chronos-card/60 transition-all relative',
            collapsed && 'justify-center'
          )}
          title={collapsed ? 'Notifications' : undefined}
        >
          <Bell className="w-4 h-4 shrink-0" />
          {unreadCount > 0 && (
            <span className="absolute top-1.5 left-6 w-4 h-4 bg-chronos-danger rounded-full text-[10px] flex items-center justify-center text-white font-bold">
              {unreadCount > 9 ? '9+' : unreadCount}
            </span>
          )}
          <AnimatePresence>
            {!collapsed && <motion.span initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>Notifications</motion.span>}
          </AnimatePresence>
        </button>

        <button
          onClick={handleLogout}
          className={clsx(
            'w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm text-chronos-text-dim hover:text-chronos-danger hover:bg-chronos-danger/10 transition-all',
            collapsed && 'justify-center'
          )}
          title={collapsed ? 'Sign Out' : undefined}
        >
          <LogOut className="w-4 h-4 shrink-0" />
          <AnimatePresence>
            {!collapsed && <motion.span initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>Sign Out</motion.span>}
          </AnimatePresence>
        </button>

        <button
          onClick={() => setCollapsed(!collapsed)}
          className="w-full flex items-center justify-center p-2 rounded-lg text-chronos-muted hover:text-chronos-text transition-colors"
        >
          {collapsed ? <ChevronRight className="w-4 h-4" /> : <ChevronLeft className="w-4 h-4" />}
        </button>
      </div>
    </motion.aside>
  )
}
