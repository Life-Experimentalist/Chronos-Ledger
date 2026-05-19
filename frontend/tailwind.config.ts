// Copyright 2026 Chronos Ledger Contributors
// Licensed under the Apache License, Version 2.0

import type { Config } from 'tailwindcss'

const config: Config = {
  content: [
    './src/pages/**/*.{js,ts,jsx,tsx,mdx}',
    './src/components/**/*.{js,ts,jsx,tsx,mdx}',
    './src/app/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      colors: {
        chronos: {
          dark: '#060d1a',
          surface: '#0a1628',
          card: '#0f1f38',
          border: '#1a2f50',
          teal: '#14b8a6',
          'teal-dim': '#0d9488',
          'teal-glow': '#5eead4',
          emerald: '#10b981',
          'emerald-dim': '#059669',
          accent: '#818cf8',
          muted: '#64748b',
          text: '#e2e8f0',
          'text-dim': '#94a3b8',
          danger: '#f43f5e',
          warning: '#f59e0b',
          success: '#22c55e',
        },
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'monospace'],
      },
      backgroundImage: {
        'grid-pattern': "url(\"data:image/svg+xml,%3Csvg width='40' height='40' viewBox='0 0 40 40' xmlns='http://www.w3.org/2000/svg'%3E%3Cg fill='none' fill-rule='evenodd'%3E%3Cg fill='%2314b8a6' fill-opacity='0.04'%3E%3Cpath d='M0 40L40 0H20L0 20M40 40V20L20 40'/%3E%3C/g%3E%3C/g%3E%3C/svg%3E\")",
        'chronos-gradient': 'linear-gradient(135deg, #060d1a 0%, #0a1628 50%, #060d1a 100%)',
      },
      boxShadow: {
        'teal-glow': '0 0 20px rgba(20, 184, 166, 0.15)',
        'teal-strong': '0 0 40px rgba(20, 184, 166, 0.3)',
        'card': '0 4px 24px rgba(0, 0, 0, 0.4)',
      },
      animation: {
        'pulse-teal': 'pulse-teal 2s cubic-bezier(0.4, 0, 0.6, 1) infinite',
        'fade-in': 'fadeIn 0.3s ease-out',
        'slide-up': 'slideUp 0.4s ease-out',
      },
      keyframes: {
        'pulse-teal': {
          '0%, 100%': { boxShadow: '0 0 0 0 rgba(20, 184, 166, 0.4)' },
          '50%': { boxShadow: '0 0 0 12px rgba(20, 184, 166, 0)' },
        },
        fadeIn: {
          from: { opacity: '0' },
          to: { opacity: '1' },
        },
        slideUp: {
          from: { transform: 'translateY(16px)', opacity: '0' },
          to: { transform: 'translateY(0)', opacity: '1' },
        },
      },
      backdropBlur: {
        xs: '2px',
      },
    },
  },
  plugins: [],
}

export default config
