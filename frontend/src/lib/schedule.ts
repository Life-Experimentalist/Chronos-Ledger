// Copyright 2026 Chronos Ledger Contributors
// Licensed under the Apache License, Version 2.0

/**
 * Whether a scheduled window is running, and whether it is over.
 *
 * Two pages worked this out for themselves by comparing the two time strings
 * against a reading of the clock, and both got the same two things wrong.
 *
 * The first is midnight. An end earlier than a start means the window
 * finishes on the day after the one it opened on, which is what a night
 * shift is, so a ward running 22:00 to 06:00 compared string against string
 * reads as already finished at eleven at night. That rule is window_span in
 * the backend, and this is the same rule.
 *
 * The second is padding. The entries carry HH:MM:SS and the reading was
 * built as HH:MM, and "09:00" sorts before "09:00:00", so a nine o'clock
 * class only started looking live at 09:01.
 *
 * Instants rather than strings, because once a window can finish on a
 * different date than it opened on, the two times alone no longer say when
 * it is. They are built in the browser's own zone out of a wall clock
 * reading the organisation keeps in its zone, which is the same mismatch the
 * string comparison had and no better or worse: nothing in an entry says
 * which zone its times mean.
 */

export interface ScheduleWindow {
  target_date?: string | null
  time_window_start?: string | null
  time_window_end?: string | null
}

export interface WindowState {
  active: boolean
  past: boolean
}

const IDLE: WindowState = { active: false, past: false }

/** A YYYY-MM-DD and an HH:MM:SS, as an instant on the local clock. */
function at(day: string, clock: string, dayOffset = 0): Date | null {
  const date = day.split('-').map(Number)
  const time = clock.split(':').map(Number)
  if (date.length !== 3 || time.length < 2 || [...date, ...time].some(Number.isNaN)) return null
  return new Date(date[0], date[1] - 1, date[2] + dayOffset, time[0], time[1], time[2] || 0)
}

export function windowState(entry: ScheduleWindow, now: Date): WindowState {
  const { target_date: day, time_window_start: start, time_window_end: end } = entry
  if (!day || !start || !end) return IDLE

  const starts = at(day, start)
  const ends = at(day, end, end < start ? 1 : 0)
  if (!starts || !ends) return IDLE

  // Half open, the start in and the end out, the same as everywhere in the
  // backend. Two entries meeting on the hour would otherwise both call
  // themselves live for the minute they share.
  return { active: now >= starts && now < ends, past: now >= ends }
}
