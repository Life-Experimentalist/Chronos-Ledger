// Copyright 2026 Chronos Ledger Contributors
// Licensed under the Apache License, Version 2.0

import { useEffect, useRef, useCallback } from 'react'
import { getToken } from '@/lib/auth'
import { useNotificationStore } from '@/store/notifications'
import type { WSEvent } from '@/types'

const WS_URL = process.env.NEXT_PUBLIC_WS_URL || 'ws://localhost/ws'
const RECONNECT_DELAY_MS = 3000

// Published images bake a relative path ('/ws') so one build works on any
// origin, but new WebSocket() only accepts relative URLs in browsers from
// 2024 onward. Resolve against the page origin ourselves; https gets wss.
function resolveWsUrl(): string {
  if (/^wss?:/i.test(WS_URL)) return WS_URL
  const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  return `${proto}//${window.location.host}${WS_URL}`
}

type EventHandler = (payload: unknown) => void

export function useWebSocket() {
  const wsRef = useRef<WebSocket | null>(null)
  const handlersRef = useRef<Map<string, EventHandler[]>>(new Map())
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const mountedRef = useRef(true)
  const pushNotification = useNotificationStore((s) => s.push)

  const connect = useCallback(() => {
    const token = getToken()
    if (!token || !mountedRef.current) return

    // The token goes in the first frame, not the query string: a query string
    // lands in the proxy's access log and the browser's history, and gets sent
    // on as a Referer. The server accepts the socket, waits a few seconds for
    // this frame, and closes if it does not arrive or does not check out.
    const ws = new WebSocket(resolveWsUrl())
    wsRef.current = ws

    ws.onopen = () => {
      if (reconnectTimerRef.current) {
        clearTimeout(reconnectTimerRef.current)
        reconnectTimerRef.current = null
      }
      ws.send(JSON.stringify({ event: 'AUTH', payload: { token } }))
    }

    ws.onmessage = (event) => {
      try {
        const frame: WSEvent = JSON.parse(event.data)
        const handlers = handlersRef.current.get(frame.event) || []
        handlers.forEach((h) => h(frame.payload))

        // Built-in notification routing
        if (frame.event === 'ABSENCE_APPROVAL_REQUIRED') {
          const p = frame.payload as { from: string; date: string }
          pushNotification({
            type: 'warning',
            title: 'Absence Approval Required',
            message: `${p.from} requested absence on ${p.date}`,
            actionUrl: '/staff/dashboard?tab=absences',
          })
        } else if (frame.event === 'GUEST_HANDSHAKE_REQ') {
          const p = frame.payload as { guest_name: string; organization: string }
          pushNotification({
            type: 'info',
            title: 'Guest at Organization Gate',
            message: `${p.guest_name} from ${p.organization} is waiting`,
            actionUrl: '/staff/dashboard?tab=guests',
          })
        } else if (frame.event === 'ABSENCE_DECISION') {
          const p = frame.payload as { decision: string }
          pushNotification({
            type: p.decision === 'VERIFIED_APPROVED' ? 'success' : 'error',
            title: 'Absence Decision',
            message: p.decision === 'VERIFIED_APPROVED' ? 'Your absence was approved' : 'Your absence was denied',
          })
        }
      } catch {
        // Ignore malformed frames
      }
    }

    ws.onclose = () => {
      wsRef.current = null
      if (mountedRef.current) {
        reconnectTimerRef.current = setTimeout(connect, RECONNECT_DELAY_MS)
      }
    }

    ws.onerror = () => ws.close()
  }, [pushNotification])

  useEffect(() => {
    mountedRef.current = true
    connect()
    return () => {
      mountedRef.current = false
      if (reconnectTimerRef.current) clearTimeout(reconnectTimerRef.current)
      wsRef.current?.close()
    }
  }, [connect])

  const on = useCallback((eventType: string, handler: EventHandler) => {
    const existing = handlersRef.current.get(eventType) || []
    handlersRef.current.set(eventType, [...existing, handler])
    return () => {
      const updated = (handlersRef.current.get(eventType) || []).filter((h) => h !== handler)
      handlersRef.current.set(eventType, updated)
    }
  }, [])

  const isConnected = () => wsRef.current?.readyState === WebSocket.OPEN

  return { on, isConnected }
}
