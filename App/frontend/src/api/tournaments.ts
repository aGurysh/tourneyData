import { get } from "./client"

export interface Tournament {
  id: number
  name: string
  date: string
}

interface Page<T> {
  items: T[]
  total: number
  limit: number
  offset: number
}

export async function listTournaments(signal?: AbortSignal): Promise<Tournament[]> {
  const tournaments: Tournament[] = []
  let offset = 0

  while (true) {
    const page = await get<Page<Tournament>>(
      `/tournaments?limit=200&offset=${offset}`,
      signal,
    )
    tournaments.push(...page.items)
    offset += page.items.length

    if (offset >= page.total || page.items.length === 0) {
      return tournaments
    }
  }
}
