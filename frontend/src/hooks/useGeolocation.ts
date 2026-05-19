// Copyright 2026 Chronos Ledger Contributors
// Licensed under the Apache License, Version 2.0

import { useState, useRef, useCallback } from 'react'

export interface GeoPosition {
  lat: number
  lon: number
  alt: number
  accuracy: number
}

interface GeolocationState {
  position: GeoPosition | null
  error: string | null
  isWatching: boolean
}

const GPS_ACCURACY_THRESHOLD = 30 // metres — above this we try BSSID fallback

export function useGeolocation() {
  const [state, setState] = useState<GeolocationState>({
    position: null,
    error: null,
    isWatching: false,
  })

  // Must be useRef so the watch ID survives re-renders and clearWatch gets the right value.
  const watchIdRef = useRef<number>(0)

  const startWatching = useCallback(() => {
    if (!navigator.geolocation) {
      setState((s) => ({ ...s, error: 'Geolocation not supported on this device' }))
      return
    }

    setState((s) => ({ ...s, isWatching: true, error: null }))

    watchIdRef.current = navigator.geolocation.watchPosition(
      (pos) => {
        setState({
          position: {
            lat: pos.coords.latitude,
            lon: pos.coords.longitude,
            alt: pos.coords.altitude ?? 0,
            accuracy: pos.coords.accuracy,
          },
          error: null,
          isWatching: true,
        })
      },
      (err) => {
        setState((s) => ({ ...s, error: err.message, isWatching: false }))
      },
      {
        enableHighAccuracy: true,
        timeout: 10000,
        maximumAge: 5000,
      }
    )
  }, [])

  const stopWatching = useCallback(() => {
    if (watchIdRef.current) {
      navigator.geolocation.clearWatch(watchIdRef.current)
      watchIdRef.current = 0
    }
    setState((s) => ({ ...s, isWatching: false }))
  }, [])

  const hasGoodAccuracy = state.position && state.position.accuracy <= GPS_ACCURACY_THRESHOLD
  const needsBssidFallback = state.position && state.position.accuracy > GPS_ACCURACY_THRESHOLD

  return { ...state, startWatching, stopWatching, hasGoodAccuracy, needsBssidFallback }
}
