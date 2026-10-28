export interface CatchTimeSample {
  catchTime: string
  timeZone: string
}

export interface BiteWindow {
  startMinute: number
  count: number
}

export interface BiteWindowFilters {
  species: string | null
  minimumLength: number
}

export function matchesBiteWindowFilters(
  sample: { species: string | null; length: number },
  filters: BiteWindowFilters,
) {
  const speciesMatches = filters.species === null || (sample.species ?? "") === filters.species
  return speciesMatches && Number.isFinite(sample.length) && sample.length >= filters.minimumLength
}

// Group by local time of day, across any number of dates and timezones.
// Callers can filter their catch records before creating these samples.
export function buildBiteWindows(samples: readonly CatchTimeSample[]) {
  const windows: BiteWindow[] = Array.from({ length: 48 }, (_, index) => ({
    startMinute: index * 30,
    count: 0,
  }))
  const formatters = new Map<string, Intl.DateTimeFormat>()
  let excludedCount = 0

  for (const sample of samples) {
    // Reject timestamps without an explicit offset rather than using the
    // browser's timezone to guess when the catch happened.
    const date = new Date(sample.catchTime)
    if (!sample.timeZone || !/(?:Z|[+-]\d{2}:\d{2})$/i.test(sample.catchTime) || !Number.isFinite(date.getTime())) {
      excludedCount++
      continue
    }
    try {
      let formatter = formatters.get(sample.timeZone)
      if (!formatter) {
        formatter = new Intl.DateTimeFormat("en-US", {
          timeZone: sample.timeZone,
          hour: "2-digit",
          minute: "2-digit",
          hourCycle: "h23",
        })
        formatters.set(sample.timeZone, formatter)
      }
      const parts = formatter.formatToParts(date)
      const hour = Number(parts.find((part) => part.type === "hour")?.value)
      const minute = Number(parts.find((part) => part.type === "minute")?.value)
      windows[Math.floor((hour * 60 + minute) / 30)].count++
    } catch {
      excludedCount++
    }
  }

  const first = windows.findIndex((window) => window.count > 0)
  let last = windows.length - 1
  while (last >= 0 && windows[last].count === 0) last--
  return {
    windows: first === -1 ? [] : windows.slice(first, last + 1),
    excludedCount,
  }
}

export function formatWindowTime(minute: number) {
  const hour = Math.floor((minute % 1440) / 60)
  return `${hour % 12 || 12}:${String(minute % 60).padStart(2, "0")} ${hour < 12 ? "AM" : "PM"}`
}

export function describeBiteWindow(window: BiteWindow) {
  return `${formatWindowTime(window.startMinute)}–${formatWindowTime(window.startMinute + 30)}: ${window.count.toLocaleString()} ${window.count === 1 ? "catch" : "catches"}`
}
