export function buildScoringBreakdown(
  catches: readonly { angler_id: number; length_inches: string }[],
  anglerCount: number,
  fishRange: { minimum: number; maximum: number } = { minimum: 0, maximum: Infinity },
) {
  const totals = new Map<number, number>()
  const catchCounts = new Map<number, number>()
  for (const item of catches) {
    catchCounts.set(item.angler_id, (catchCounts.get(item.angler_id) ?? 0) + 1)
    // Sum integer hundredths so scores on a bin boundary stay in that bin.
    totals.set(item.angler_id, (totals.get(item.angler_id) ?? 0) + Math.round(Number(item.length_inches) * 100))
  }

  const selectedTotals = [...totals.entries()]
    .filter(([anglerId]) => {
      const count = catchCounts.get(anglerId)!
      return count >= fishRange.minimum && count <= fishRange.maximum
    })
    .map(([, total]) => total)
  const zeroCatchCount = fishRange.minimum <= 0 && fishRange.maximum >= 0
    ? Math.max(0, anglerCount - totals.size)
    : 0
  const highest = Math.max(0, ...selectedTotals)
  const bins = Array.from({ length: Math.floor(highest / 500) + 1 }, (_, index) => ({
    lower: index * 5,
    upper: (index + 1) * 5,
    count: 0,
  }))
  for (const total of selectedTotals) bins[Math.floor(total / 500)].count++
  bins[0].count += zeroCatchCount
  const count = selectedTotals.length + zeroCatchCount
  const average = count > 0 ? selectedTotals.reduce((sum, total) => sum + total, 0) / 100 / count : null
  return { bins: bins.reverse(), average }
}
