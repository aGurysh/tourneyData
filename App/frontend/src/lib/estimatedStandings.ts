export interface StandingPoint {
  time: number
  total: number
  lengths: number[]
  place: number
  tied: boolean
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
    if (previous?.time === item.time) {
      previous.total = angler.total
      previous.lengths.push(item.length / 100)
    } else angler.points.push({ time: item.time, total: angler.total, lengths: [item.length / 100], place: 0, tied: false })
  }

  const pointsByTime = new Map<number, { name: string; point: StandingPoint }[]>()
  for (const angler of anglers.values()) {
    for (const point of angler.points) {
      const group = pointsByTime.get(point.time) ?? []
      group.push({ name: angler.name, point })
      pointsByTime.set(point.time, group)
    }
  }
  const totals = new Map<string, number>()
  for (const [, group] of [...pointsByTime].sort(([a], [b]) => a - b)) {
    // Equal timestamps share a snapshot; do not invent an order for simultaneous catches.
    for (const { name, point } of group) totals.set(name, Math.round(point.total * 100))
    const scores = [...totals.values()]
    for (const { point } of group) {
      const score = Math.round(point.total * 100)
      point.place = 1 + scores.filter((total) => total > score).length
      point.tied = scores.filter((total) => total === score).length > 1
    }
  }

  return {
    anglers: [...anglers.values()].sort((a, b) => b.total - a.total || a.name.localeCompare(b.name)),
    start: valid.length ? valid[0].time - 600_000 : 0,
    end: valid.length ? valid[valid.length - 1].time + 600_000 : 0,
    excludedCount,
  }
}
