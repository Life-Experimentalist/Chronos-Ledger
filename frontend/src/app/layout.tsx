// Copyright 2026 Chronos Ledger Contributors
// Licensed under the Apache License, Version 2.0

import type { Metadata, Viewport } from 'next'
import { Inter, JetBrains_Mono } from 'next/font/google'
import './globals.css'

// Self-hosted at build time: next/font downloads the files during `next build`
// and emits them under /_next/static/media, so a running instance never talks
// to fonts.googleapis.com.
const inter = Inter({
  subsets: ['latin'],
  weight: ['300', '400', '500', '600', '700'],
  display: 'swap',
  variable: '--font-inter',
})

const jetbrainsMono = JetBrains_Mono({
  subsets: ['latin'],
  weight: ['400', '500'],
  display: 'swap',
  variable: '--font-jetbrains-mono',
})

export const metadata: Metadata = {
  title: {
    default: 'Chronos Ledger',
    template: '%s | Chronos Ledger',
  },
  description: 'Organization Schedule & Attendance Management System: real-time timetables, geofenced attendance, and staff tracking.',
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
    description: 'Organization Schedule & Attendance Management System',
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
    <html lang="en" className={`dark ${inter.variable} ${jetbrainsMono.variable}`}>
      <head>
        <link rel="icon" href="/icon.png" />
        <link rel="apple-touch-icon" href="/icon.png" />
        <meta name="mobile-web-app-capable" content="yes" />
      </head>
      <body>{children}</body>
    </html>
  )
}
