import { get } from "./client"

export interface Tournament {
  id: number
  name: string
  date: string
}

export interface TournamentDetail extends Tournament {
  timezone: string
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

export interface TournamentCatch {
  angler_id: number
  id: number
  tournament_id: number
  angler_name: string
  catch_time: string
  species_id: number | null
  species_name: string | null
  length_inches: string
  external_id: string | null
}

export function getTournament(id: number, signal?: AbortSignal) {
  return get<TournamentDetail>(`/tournaments/${id}`, signal)
}

export interface WeatherHour {
  time: string
  temperature_f: number | null
  pressure_hpa: number | null
  cloud_cover_percent: number | null
  wind_speed_mph: number | null
  wind_direction_degrees: number | null
}

export interface TournamentWeather {
  tournament_id: number
  source: string
  source_url: string
  attribution: string
  license_url: string
  modifications: string
  data_kind: "historical_reanalysis"
  timezone: string
  starts_at: string
  ends_at: string
  requested_coordinates: { latitude: number; longitude: number }
  grid_coordinates: { latitude: number; longitude: number }
  fetched_at: string
  coverage: "complete" | "partial"
  hourly: WeatherHour[]
}

export function getTournamentWeather(id: number, signal?: AbortSignal) {
  return get<TournamentWeather>(`/tournaments/${id}/weather`, signal)
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

export async function listTournamentCatches(id: number, signal?: AbortSignal): Promise<TournamentCatch[]> {
  const catches: TournamentCatch[] = []
  let offset = 0

  while (true) {
    const page = await get<Page<TournamentCatch>>(
      `/tournaments/${id}/catches?limit=200&offset=${offset}`,
      signal,
    )
    catches.push(...page.items)
    offset += page.items.length

    if (offset >= page.total) return catches
    if (page.items.length === 0) throw new Error("Incomplete catch response")
  }
}
