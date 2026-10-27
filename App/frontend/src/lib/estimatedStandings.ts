export interface StandingPoint {
  time: number
  total: number
}

export interface AnglerStanding {
  name: string
  total: number
  points: StandingPoint[]
}

// These are final scoring catches, not a reconstruction of culled fish.
export function buildEstimatedStandings(catches: readonly {
  angler_name: string
  catch_time: string
  length_inches: string
}[]) {
  const anglers = new Map<string, AnglerStanding>()
  let excludedCount = 0
  const valid = catches.flatMap((item) => {
    const time = Date.parse(item.catch_time)
    const length = Number(item.length_inches)
    if (!item.angler_name.trim() || !Number.isFinite(time) || !/(?:Z|[+-]\d{2}:\d{2})$/i.test(item.catch_time)
      || !Number.isFinite(length) || length <= 0) {
      excludedCount++
      return []
    }
    return [{ name: item.angler_name, time, length: Math.round(length * 100) }]
  }).sort((a, b) => a.time - b.time)

  for (const item of valid) {
    let angler = anglers.get(item.name)
    if (!angler) {
      angler = { name: item.name, total: 0, points: [] }
      anglers.set(item.name, angler)
    }
    // Integer hundredths avoid floating point errors changing the leader.
    angler.total = (Math.round(angler.total * 100) + item.length) / 100
    const previous = angler.points.at(-1)
    if (previous?.time === item.time) previous.total = angler.total
    else angler.points.push({ time: item.time, total: angler.total })
  }

  return {
    anglers: [...anglers.values()].sort((a, b) => b.total - a.total || a.name.localeCompare(b.name)),
    start: valid.length ? valid[0].time - 600_000 : 0,
    end: valid.length ? valid[valid.length - 1].time + 600_000 : 0,
    excludedCount,
  }
}
