import { useId, useMemo, useState } from "react"
import { useQuery } from "@tanstack/react-query"
import { tournamentQueries } from "@/api/queries"
import EstimatedStandingsChart from "@/components/charts/EstimatedStandingsChart"
import { AnglerCombobox } from "@/components/ui/angler-combobox"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { buildEstimatedStandings } from "@/lib/estimatedStandings"

export default function TournamentEstimatedStandings({ tournamentId }: { tournamentId: number | null }) {
  const titleId = useId()
  const detail = useQuery(tournamentQueries.detail(tournamentId))
  const catches = useQuery(tournamentQueries.catches(tournamentId))
  const [selectedName, setSelectedName] = useState<string | null>(null)
  const { anglers, start, end, excludedCount } = useMemo(() => buildEstimatedStandings(catches.data ?? []), [catches.data])
  const selected = anglers.find((angler) => angler.name === selectedName) ?? anglers[0]
  const names = useMemo(() => anglers.map((angler) => angler.name).sort((a, b) => a.localeCompare(b)), [anglers])
  const ready = !!detail.data && catches.data !== undefined
  const failed = detail.isError || catches.isError
  const fetching = detail.isFetching || catches.isFetching
  const tiedLeaders = anglers.filter((angler) => angler.total === anglers[0]?.total).length > 1

  return (
    <Card role="article" aria-labelledby={titleId} className="min-w-0 lg:col-span-2">
      <CardHeader>
        <CardTitle><h2 id={titleId}>Estimated Standings</h2></CardTitle>
        <CardDescription>Cumulative scoring length throughout the tournament</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {tournamentId === null ? <p className="text-muted-foreground">Select a tournament to view estimated standings.</p> : (
          <>
            {failed ? (
              <p role="alert" className="text-sm text-muted-foreground">
                {ready ? "Couldn't refresh estimated standings. Showing saved data." : "Unable to load estimated standings."}{" "}
                <Button variant="link" className="h-auto p-0" disabled={fetching} onClick={() => {
                  if (detail.isError) void detail.refetch()
                  if (catches.isError) void catches.refetch()
                }}>Try again</Button>
              </p>
            ) : !ready || fetching ? <p role="status" className="text-sm text-muted-foreground">{ready ? "Refreshing estimated standings…" : "Loading estimated standings…"}</p> : null}
            {ready && (selected ? (
              <>
                <AnglerCombobox names={names} value={selected.name} onValueChange={setSelectedName} />
                <p className="flex flex-wrap items-center gap-x-4 gap-y-1 text-sm" aria-live="polite">
                  <span className="inline-flex items-center gap-2"><span className="h-0.5 w-5 bg-teal-600 dark:bg-teal-400" />{selected.name} · {selected.total.toFixed(2)}″</span>
                  <span className="text-xs text-muted-foreground">{selected.total === anglers[0].total ? tiedLeaders ? "Tied highest total" : "Tournament winner" : "Final scoring total"} · {anglers.length} anglers with catches</span>
                </p>
                <EstimatedStandingsChart key={selected.name} anglers={anglers} selected={selected} start={start} end={end} timeZone={detail.data!.timezone} />
                <p className="text-xs text-muted-foreground">Estimated from final scoring catches and photo times. Earlier culled catches are unavailable, so historical totals may be understated.{tiedLeaders ? " Official tie-break results are unavailable; tied leaders are listed alphabetically." : ""}</p>
              </>
            ) : <p className="text-muted-foreground">No catches with usable times and lengths to display.</p>)}
            {excludedCount > 0 && <p className="text-xs text-muted-foreground">{excludedCount} {excludedCount === 1 ? "catch excluded" : "catches excluded"} because the angler, time, or length is invalid.</p>}
          </>
        )}
      </CardContent>
    </Card>
  )
}
