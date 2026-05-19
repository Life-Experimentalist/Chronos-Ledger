# Copyright 2026 Chronos Ledger Contributors — Apache 2.0
#
# Multi-stage image: builds Next.js static export then bakes it into nginx.
# Used by CI/CD to produce the ghcr.io chronos-ledger-web image.
# Build context must be the repo root so COPY can reach both frontend/ and nginx/.
#
# Example:
#   docker build -f nginx/Dockerfile \
#     --build-arg NEXT_PUBLIC_API_URL=/api/v1 \
#     --build-arg NEXT_PUBLIC_WS_URL=/ws \
#     -t chronos-ledger-web:local .

# ── Stage 1: Build Next.js ────────────────────────────────────────────────────
FROM node:20-alpine AS builder

WORKDIR /app

# Dependency layer — cached unless package files change
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --legacy-peer-deps --ignore-scripts

COPY frontend/ ./

# These default to relative paths so the image works behind any nginx proxy
# without rebuild. The browser always talks to the same origin as the page.
ARG NEXT_PUBLIC_API_URL=/api/v1
ARG NEXT_PUBLIC_WS_URL=/ws
ARG NEXT_PUBLIC_VAPID_PUBLIC_KEY=
ARG NEXT_PUBLIC_TELEMETRY_ENABLED=true
ARG NEXT_PUBLIC_TELEMETRY_ENDPOINT=https://counter.vkrishna04.me

ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL \
    NEXT_PUBLIC_WS_URL=$NEXT_PUBLIC_WS_URL \
    NEXT_PUBLIC_VAPID_PUBLIC_KEY=$NEXT_PUBLIC_VAPID_PUBLIC_KEY \
    NEXT_PUBLIC_TELEMETRY_ENABLED=$NEXT_PUBLIC_TELEMETRY_ENABLED \
    NEXT_PUBLIC_TELEMETRY_ENDPOINT=$NEXT_PUBLIC_TELEMETRY_ENDPOINT \
    NODE_ENV=production

RUN npm run build

# ── Stage 2: Serve with nginx ─────────────────────────────────────────────────
FROM nginx:1.27-alpine AS server

# Copy pre-built static export
COPY --from=builder /app/out /usr/share/nginx/html

# Copy nginx reverse-proxy config
COPY nginx/nginx.conf /etc/nginx/nginx.conf

EXPOSE 80

# Lightweight healthcheck — nginx must respond to /health which it proxies
# to the backend. Use a simple port check here so the container reports
# healthy even before the backend is ready (compose handles sequencing).
HEALTHCHECK --interval=10s --timeout=3s --start-period=5s --retries=3 \
    CMD wget -qO- http://localhost/ > /dev/null || exit 1
