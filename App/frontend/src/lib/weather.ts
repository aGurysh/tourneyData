export function pressureInHg(hpa: number | null) {
  return hpa === null ? null : hpa / 33.8638866667
}

export function formatWeatherValue(value: number | null, unit: string, digits = 0) {
  return value === null || !Number.isFinite(value)
    ? "—"
    : `${value.toLocaleString("en-US", { maximumFractionDigits: digits, useGrouping: false })}${unit}`
}

export function weatherRange(values: readonly (number | null)[], unit: string, digits = 0) {
  const known = values.filter((value): value is number => value !== null && Number.isFinite(value))
  if (known.length === 0) return "—"
  const minimum = Math.min(...known)
  const maximum = Math.max(...known)
  const low = formatWeatherValue(minimum, "", digits)
  const high = formatWeatherValue(maximum, "", digits)
  return low === high ? `${low}${unit}` : `${low} – ${high}${unit}`
}

export function windDirection(degrees: number | null) {
  if (degrees === null || !Number.isFinite(degrees)) return "—"
  const compass = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE", "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"]
  return compass[Math.round(((degrees % 360 + 360) % 360) / 22.5) % 16]
}
