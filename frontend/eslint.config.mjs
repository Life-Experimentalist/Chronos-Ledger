// Copyright 2026 Chronos Ledger Contributors
// Licensed under the Apache License, Version 2.0

import { defineConfig, globalIgnores } from 'eslint/config'
import nextVitals from 'eslint-config-next/core-web-vitals'

export default defineConfig([
  ...nextVitals,
  {
    rules: {
      'prefer-const': 'warn',
      '@next/next/no-img-element': 'off',
      // eslint-plugin-react-hooks 7 added rules written for code built with
      // the React Compiler, which this app does not use. They flag patterns
      // that work here, such as setting a loading flag before a fetch or
      // reading a value once on mount, so they warn rather than fail CI.
      'react-hooks/set-state-in-effect': 'warn',
      'react-hooks/preserve-manual-memoization': 'warn',
      'react-hooks/immutability': 'warn',
    },
  },
  globalIgnores([
    '.next/**',
    'out/**',
    'build/**',
    'next-env.d.ts',
    // Written by the build: the service worker and its workbox chunks.
    'public/sw.js',
    'public/workbox-*.js',
    'public/worker-*.js',
    'public/fallback-*.js',
  ]),
])
