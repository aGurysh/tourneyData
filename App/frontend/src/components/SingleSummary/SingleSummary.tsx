import { useEffect, useState } from "react"

import { listTournaments } from "@/api/tournaments"
import type { Tournament } from "@/api/tournaments"
import { Button } from "@/components/ui/button"
import TournamentSummaryCard from "./TournamentSummaryCard"

export default function SingleSummary() {
  const [tournaments, setTournaments] = useState<Tournament[]>([])
  const [selectedTournamentId, setSelectedTournamentId] = useState("")
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(false)
  const [attempt, setAttempt] = useState(0)

  useEffect(() => {
    const controller = new AbortController()
    setLoading(true)
    setError(false)

    listTournaments(controller.signal)
      .then((items) => {
        if (!controller.signal.aborted) setTournaments(items)
      })
      .catch(() => {
        if (!controller.signal.aborted) setError(true)
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false)
      })

    return () => controller.abort()
  }, [attempt])

  const placeholder = loading
    ? "Loading tournaments…"
    : error
      ? "Tournaments unavailable"
      : tournaments.length === 0
        ? "No tournaments available"
        : "Select a tournament"

  return (
    <section aria-label="Single tournament summary" className="space-y-6">
       <p className="mt-2 text-sm text-muted-foreground">
          Analyze the results of a single tournament
        </p>
      <div className="max-w-xl space-y-2">
        <label htmlFor="tournament" className="block text-sm font-medium">
          Tournament
        </label>
        <select
          id="tournament"
          value={selectedTournamentId}
          onChange={(event) => setSelectedTournamentId(event.target.value)}
          disabled={loading || error || tournaments.length === 0}
          aria-describedby={error ? "tournament-error" : "tournament-status"}
          className="w-full rounded-md border bg-card px-3 py-2 text-sm focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring disabled:opacity-60"
        >
          <option value="" disabled>{placeholder}</option>
          {tournaments.map((tournament) => (
            <option key={tournament.id} value={tournament.id}>
              {tournament.name} — {tournament.date}
            </option>
          ))}
        </select>
        {error ? (
          <p id="tournament-error" role="alert" className="text-sm text-muted-foreground">
            Unable to load tournaments.{" "}
            <Button variant="link" onClick={() => setAttempt((value) => value + 1)} className="h-auto p-0">
              Try again
            </Button>
          </p>
        ) : (
          <p id="tournament-status" role="status" className="text-sm text-muted-foreground">
            {loading ? "Loading available tournaments…" : tournaments.length === 0 ? "Imported tournaments will appear here." : "Choose a tournament to get started."}
          </p>
        )}
      </div>
      <div className="grid grid-cols-1 items-start gap-6 lg:grid-cols-2">
        <TournamentSummaryCard
          key={selectedTournamentId}
          tournamentId={selectedTournamentId ? Number(selectedTournamentId) : null}
        />
      </div>
    </section>
  )
}
