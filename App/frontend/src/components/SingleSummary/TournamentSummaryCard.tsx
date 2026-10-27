import { useEffect, useState } from "react"

import { getTournament } from "@/api/tournaments"
import type { TournamentDetail } from "@/api/tournaments"
import { SPECIES_COLORS } from "@/constants/species"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import SpeciesCatchRatio from "./SpeciesCatchRatio"

function formatScore(score: string | null) {
  return score === null ? "Not available" : `${Number(score).toLocaleString("en-US", { maximumFractionDigits: 2 })} inches`
}

export default function TournamentSummaryCard({ tournamentId }: { tournamentId: number | null }) {
  const [tournament, setTournament] = useState<TournamentDetail | null>(null)
  const [error, setError] = useState(false)
  const [attempt, setAttempt] = useState(0)

  useEffect(() => {
    if (tournamentId === null) return

    const controller = new AbortController()
    setError(false)
    setTournament(null)

    getTournament(tournamentId, controller.signal)
      .then((detail) => {
        if (!controller.signal.aborted) setTournament(detail)
      })
      .catch(() => {
        if (!controller.signal.aborted) setError(true)
      })

    return () => controller.abort()
  }, [tournamentId, attempt])

  return (
    <Card role="article" aria-labelledby="tournament-summary-title" className="min-w-0">
      <CardHeader>
        <CardTitle>
          <h2 id="tournament-summary-title">Tournament Summary</h2>
        </CardTitle>
      </CardHeader>
      <CardContent>
        {tournamentId === null ? (
          <p className="text-muted-foreground">Select a tournament to view its summary.</p>
        ) : error ? (
          <p role="alert" className="text-muted-foreground">
            Unable to load the tournament summary.{" "}
            <Button variant="link" onClick={() => setAttempt((value) => value + 1)} className="h-auto p-0">
              Try again
            </Button>
          </p>
        ) : tournament === null ? (
          <p role="status" className="text-muted-foreground">Loading tournament summary…</p>
        ) : (
          <dl className="space-y-5">
            <div>
              <dt className="text-muted-foreground">Tournament Name</dt>
              <dd className="mt-1 break-words font-medium">{tournament.name}</dd>
            </div>
            <div>
              <dt className="text-muted-foreground">Location</dt>
              <dd className="mt-1 font-medium">
                {tournament.locations.length === 0 ? "Not available" : (
                  <ul className="space-y-1">
                    {tournament.locations.map((location) => (
                      <li key={location.id}>{[location.name, location.state].filter(Boolean).join(", ")}</li>
                    ))}
                  </ul>
                )}
              </dd>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <dt className="text-muted-foreground">Winning Score</dt>
                <dd className="mt-1 text-xl font-semibold tabular-nums">{formatScore(tournament.winning_length_inches)}</dd>
              </div>
              <div>
                <dt className="text-muted-foreground">Top 10% Score</dt>
                <dd className="mt-1 text-xl font-semibold tabular-nums">{formatScore(tournament.top_10_percent_length_inches)}</dd>
              </div>
            </div>
            <div>
              <dt className="text-muted-foreground">Species caught</dt>
              <dd className="mt-2 flex flex-wrap gap-2 font-medium">
                {tournament.species_caught.length === 0 ? "Not recorded" : tournament.species_caught.map((species) => (
                  <Badge
                    key={species}
                    variant="secondary"
                    className={`${
                      SPECIES_COLORS[species]?.background ?? "bg-muted"
                    } ${
                      SPECIES_COLORS[species]?.text ?? "text-foreground"
                    }`}
                  >
                    {species === "Largemouth Bass" ? "Largemouth" : species === "Smallmouth Bass" ? "Smallmouth" : species}
                  </Badge>
                ))}
              </dd>
              <dd>
                <SpeciesCatchRatio counts={tournament.species_catch_counts} />
              </dd>
            </div>
          </dl>
        )}
      </CardContent>
    </Card>
  )
}
