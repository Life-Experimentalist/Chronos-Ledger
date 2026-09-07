// Copyright 2026 Chronos Ledger Contributors — Apache 2.0
// Server Component layout — owns all SEO metadata for /landing.
// The page itself is 'use client' so metadata must live here.

import type { Metadata } from 'next'

const SITE_URL = 'https://chronos.vkrishna04.me'

export const metadata: Metadata = {
  metadataBase: new URL(SITE_URL),

  title: 'Chronos Ledger — Organization Schedule & Attendance Management',
  description:
    'Self-hosted PWA for universities and organizations. Geofenced attendance, real-time staff locator, offline-first architecture, and smart absence management. Deploy on your organization intranet in under 5 minutes with Docker.',

  keywords: [
    'organization management system',
    'attendance tracking software',
    'university schedule management',
    'organization timetable system',
    'geofenced attendance',
    'staff locator',
    'offline PWA education',
    'self-hosted organization software',
    'planning management system',
    'chronos ledger',
  ],

  authors: [{ name: 'Life-Experimentalist', url: 'https://github.com/Life-Experimentalist' }],
  creator: 'Life-Experimentalist',
  publisher: 'Life-Experimentalist',

  alternates: {
    canonical: SITE_URL,
  },

  openGraph: {
    type: 'website',
    url: SITE_URL,
    siteName: 'Chronos Ledger',
    title: 'Chronos Ledger — Organization Schedule & Attendance Management',
    description:
      'Self-hosted PWA for universities. Geofenced attendance, staff tracking, offline-first. Deploy in 5 minutes with Docker.',
    images: [
      {
        url: `${SITE_URL}/icons/og-image.png`,
        width: 1200,
        height: 630,
        alt: 'Chronos Ledger — Organization Management PWA',
      },
    ],
    locale: 'en_US',
  },

  twitter: {
    card: 'summary_large_image',
    title: 'Chronos Ledger — Organization Schedule & Attendance Management',
    description:
      'Self-hosted PWA for universities. Geofenced attendance, staff tracking, offline-first.',
    images: [`${SITE_URL}/icons/og-image.png`],
    creator: '@Life-Experimentalist',
  },

  robots: {
    index: true,
    follow: true,
    googleBot: {
      index: true,
      follow: true,
      'max-video-preview': -1,
      'max-image-preview': 'large',
      'max-snippet': -1,
    },
  },

  icons: {
    icon: '/icons/icon-72x72.png',
    apple: '/icons/icon-192x192.png',
  },
}

export default function LandingLayout({ children }: { children: React.ReactNode }) {
  return (
    <>
      {/* JSON-LD structured data for search engines */}
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{
          __html: JSON.stringify({
            '@context': 'https://schema.org',
            '@type': 'SoftwareApplication',
            name: 'Chronos Ledger',
            url: SITE_URL,
            description:
              'Self-hosted organization schedule and attendance management PWA for universities and organizations.',
            applicationCategory: 'EducationApplication',
            operatingSystem: 'Any (PWA)',
            offers: {
              '@type': 'Offer',
              price: '0',
              priceCurrency: 'USD',
            },
            author: {
              '@type': 'Organization',
              name: 'Life-Experimentalist',
              url: 'https://github.com/Life-Experimentalist',
            },
            license: 'https://www.apache.org/licenses/LICENSE-2.0',
            codeRepository: 'https://github.com/Life-Experimentalist/chronos-ledger',
            keywords:
              'organization management, attendance tracking, university software, self-hosted, PWA, geofence',
            featureList: [
              'Geofenced attendance marking with 3D validation',
              '4-tier real-time staff location resolver',
              'Reverse RSVP absence management',
              'Offline-first with service worker sync',
              'CSV bulk schedule import',
              'iCalendar feed per user',
              'WebSocket real-time notifications',
              'Guest visitor kiosk (no login required)',
              'Role-based access: Admin, Staff, Member, Guest',
            ],
          }),
        }}
      />
      {children}
    </>
  )
}
