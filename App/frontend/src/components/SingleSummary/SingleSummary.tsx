import { useEffect } from "react"
import { useIsFetching, useQuery, useQueryClient } from "@tanstack/react-query"

import { tournamentQueries, tournamentQueryKey } from "@/api/queries"
import { Button } from "@/components/ui/button"
import { usePersistentState } from "@/hooks/usePersistentState"
import TournamentSummaryCard from "./TournamentSummaryCard"
import TournamentBiteWindows from "./TournamentBiteWindows"
import TournamentWeatherCard from "./TournamentWeatherCard"
import TournamentEstimatedStandings from "./TournamentEstimatedStandings"

function isTournamentId(value: string): value is string {
  return value === "" || (/^[1-9]\d*$/.test(value) && Number.isSafeInteger(Number(value)))
}

export default function SingleSummary() {
  const queryClient = useQueryClient()
  const tournamentsQuery = useQuery(tournamentQueries.list())
  const tournaments = tournamentsQuery.data
  const loading = tournaments === undefined && !tournamentsQuery.isError
  const error = tournamentsQuery.isError
  const fetching = useIsFetching({ queryKey: tournamentQueryKey }) > 0
  const [selectedTournamentId, setSelectedTournamentId] = usePersistentState(
    "tournament-analytics:selected-tournament-id",
    "",
    isTournamentId,
  )
  useEffect(() => {
    // Only replace a missing selection after a successful list fetch, never
    // while restoring the cache or when a background refresh has failed.
    if (tournamentsQuery.isSuccess && tournamentsQuery.isFetchedAfterMount) {
      setSelectedTournamentId((id) =>
        tournaments?.some((item) => String(item.id) === id)
          ? id
          : tournaments?.[0] ? String(tournaments[0].id) : "",
      )
    }
  }, [tournaments, tournamentsQuery.isSuccess, tournamentsQuery.isFetchedAfterMount, setSelectedTournamentId])

  const availableTournamentId = tournaments?.some(
    (tournament) => String(tournament.id) === selectedTournamentId,
  ) ? selectedTournamentId : tournaments?.[0] ? String(tournaments[0].id) : ""

  const placeholder = loading
    ? "Loading tournaments…"
    : error && !tournaments
      ? "Tournaments unavailable"
      : tournaments?.length === 0
        ? "No tournaments available"
        : "Select a tournament"

  return (
    <section aria-label="Single tournament summary" className="space-y-6">
      <div className="flex items-center justify-between gap-4">
        <p className="mt-2 text-sm text-muted-foreground">
          Analyze the results of a single tournament
        </p>
        <Button
          variant="outline"
          disabled={loading || fetching}
          onClick={() => void queryClient.invalidateQueries({ queryKey: tournamentQueryKey })}
        >
          {fetching ? "Refreshing…" : "Refresh"}
        </Button>
      </div>
      <div className="max-w-xl space-y-2">
        <label htmlFor="tournament" className="block text-sm font-medium">
          Tournament
        </label>
        <select
          id="tournament"
          value={availableTournamentId}
          onChange={(event) => setSelectedTournamentId(event.target.value)}
          disabled={!tournaments?.length}
          aria-describedby={error ? "tournament-error" : "tournament-status"}
          className="w-full rounded-md border bg-card px-3 py-2 text-sm focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring disabled:opacity-60"
        >
          <option value="" disabled>{placeholder}</option>
          {tournaments?.map((tournament) => (
            <option key={tournament.id} value={tournament.id}>
              {tournament.name} — {tournament.date}
            </option>
          ))}
        </select>
        {error ? (
          <p id="tournament-error" role="alert" className="text-sm text-muted-foreground">
            {tournaments ? "Couldn't refresh tournaments. Showing the saved list." : "Unable to load tournaments."}{" "}
            <Button variant="link" disabled={fetching} onClick={() => void tournamentsQuery.refetch()} className="h-auto p-0">
              Try again
            </Button>
          </p>
        ) : (
          <p id="tournament-status" role="status" className="text-sm text-muted-foreground">
            {loading ? "Loading available tournaments…" : tournaments?.length === 0 ? "Imported tournaments will appear here." : availableTournamentId ? "Showing the selected tournament." : "Choose a tournament to get started."}
          </p>
        )}
      </div>
      <div className="grid grid-cols-1 items-start gap-6 lg:grid-cols-2 lg:items-stretch">
        <TournamentSummaryCard
          key={availableTournamentId}
          tournamentId={availableTournamentId ? Number(availableTournamentId) : null}
        />
        <TournamentBiteWindows
          key={`bite-windows-${availableTournamentId}`}
          tournamentId={availableTournamentId ? Number(availableTournamentId) : null}
        />
        <TournamentEstimatedStandings
          key={`estimated-standings-${availableTournamentId}`}
          tournamentId={availableTournamentId ? Number(availableTournamentId) : null}
        />
        <TournamentWeatherCard
          key={`weather-${availableTournamentId}`}
          tournamentId={availableTournamentId ? Number(availableTournamentId) : null}
        />
      </div>
    </section>
  )
}
