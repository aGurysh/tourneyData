import { get } from "./client"

export interface Tournament {
  id: number
  name: string
  date: string
}

export interface TournamentDetail extends Tournament {
  winning_length_inches: string | null
  top_10_percent_length_inches: string | null
  locations: {
    id: number
    name: string
    state: string | null
    boundary_notes: string | null
  }[]
  species_caught: string[]
  species_catch_counts: {
    species_name: string | null
    catch_count: number
    average_length_inches: string
  }[]
}

export function getTournament(id: number, signal?: AbortSignal) {
  return get<TournamentDetail>(`/tournaments/${id}`, signal)
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
