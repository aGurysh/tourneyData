export function buildScoringBreakdown(
  catches: readonly { angler_id: number; length_inches: string }[],
  anglerCount: number,
) {
  const totals = new Map<number, number>()
  for (const item of catches) {
    // Sum integer hundredths so scores on a bin boundary stay in that bin.
    totals.set(item.angler_id, (totals.get(item.angler_id) ?? 0) + Math.round(Number(item.length_inches) * 100))
  }

  const highest = Math.max(0, ...totals.values())
  const bins = Array.from({ length: Math.floor(highest / 500) + 1 }, (_, index) => ({
    lower: index * 5,
    upper: (index + 1) * 5,
    count: 0,
  }))
  for (const total of totals.values()) bins[Math.floor(total / 500)].count++
  bins[0].count += Math.max(0, anglerCount - totals.size)
  const count = Math.max(anglerCount, totals.size)
  const average = count > 0 ? [...totals.values()].reduce((sum, total) => sum + total, 0) / 100 / count : null
  return { bins: bins.reverse(), average }
}
