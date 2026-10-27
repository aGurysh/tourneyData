import { queryOptions, skipToken } from "@tanstack/react-query"
import { ApiError, apiBaseUrl } from "./client"
import { getTournament, getTournamentWeather, listTournamentCatches, listTournaments } from "./tournaments"

// Include the API URL so separate backends never share cached responses.
export const tournamentQueryKey = ["tournaments", apiBaseUrl] as const

export const tournamentQueries = {
  weather: (id: number | null) => queryOptions({
    queryKey: [...tournamentQueryKey, "weather", id],
    queryFn: id === null ? skipToken : ({ signal }) => getTournamentWeather(id, signal),
    retry: (count, error) => count < 1 && !(error instanceof ApiError && [404, 409, 503].includes(error.status)),
    meta: { persist: true },
  }),
  list: () => queryOptions({
    queryKey: [...tournamentQueryKey, "list"],
    queryFn: ({ signal }) => listTournaments(signal),
    meta: { persist: true },
  }),
  detail: (id: number | null) => queryOptions({
    queryKey: [...tournamentQueryKey, "detail", id],
    queryFn: id === null ? skipToken : ({ signal }) => getTournament(id, signal),
    meta: { persist: true },
  }),
  catches: (id: number | null) => queryOptions({
    queryKey: [...tournamentQueryKey, "catches", id],
    queryFn: id === null ? skipToken : ({ signal }) => listTournamentCatches(id, signal),
    // Catch datasets stay in memory until IndexedDB persistence is added.
  }),
}
