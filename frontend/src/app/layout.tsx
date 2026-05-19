// Copyright 2026 Chronos Ledger Contributors
// Licensed under the Apache License, Version 2.0

import type { Metadata, Viewport } from 'next'
import './globals.css'

export const metadata: Metadata = {
  title: {
    default: 'Chronos Ledger',
    template: '%s | Chronos Ledger',
  },
  description: 'Campus Schedule & Attendance Management System — real-time timetables, geofenced attendance, and faculty tracking.',
  manifest: '/manifest.webmanifest',
  appleWebApp: {
    capable: true,
    statusBarStyle: 'black-translucent',
    title: 'Chronos',
  },
  formatDetection: { telephone: false },
  openGraph: {
    type: 'website',
    title: 'Chronos Ledger',
    description: 'Campus Schedule & Attendance Management System',
  },
}

export const viewport: Viewport = {
  themeColor: '#14b8a6',
  width: 'device-width',
  initialScale: 1,
  maximumScale: 1,
  userScalable: false,
  viewportFit: 'cover',
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="dark">
      <head>
        <link rel="icon" href="/icon.png" />
        <link rel="apple-touch-icon" href="/icon.png" />
        <meta name="mobile-web-app-capable" content="yes" />
      </head>
      <body>{children}</body>
    </html>
  )
}
