import { useId, useMemo, useState } from "react"
import { useQuery } from "@tanstack/react-query"
import { tournamentQueries } from "@/api/queries"
import EstimatedStandingsChart, { standingColor } from "@/components/charts/EstimatedStandingsChart"
import { AnglerCombobox } from "@/components/ui/angler-combobox"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { buildEstimatedStandings } from "@/lib/estimatedStandings"

const ordinalRules = new Intl.PluralRules("en-US", { type: "ordinal" })
const ordinalSuffixes: Record<string, string> = { one: "st", two: "nd", few: "rd", other: "th" }

function formatPlace(place: number) {
  return `${place}${ordinalSuffixes[ordinalRules.select(place)]}`
}

export default function TournamentEstimatedStandings({ tournamentId }: { tournamentId: number | null }) {
  const titleId = useId()
  const detail = useQuery(tournamentQueries.detail(tournamentId))
  const catches = useQuery(tournamentQueries.catches(tournamentId))
  const [selectedIds, setSelectedIds] = useState<number[] | null>(null)
  const { anglers, start, end, excludedCount } = useMemo(() => buildEstimatedStandings(catches.data ?? []), [catches.data])
  const selected = selectedIds === null ? anglers.slice(0, 1) : selectedIds.flatMap((id) => {
    const angler = anglers.find((item) => item.id === id)
    return angler ? [angler] : []
  })
  const options = useMemo(() => [...anglers].sort((a, b) => a.name.localeCompare(b.name) || a.id - b.id), [anglers])
  const ready = !!detail.data && catches.data !== undefined
  const failed = detail.isError || catches.isError
  const fetching = detail.isFetching || catches.isFetching
  const hasTies = new Set(anglers.map((angler) => angler.total)).size < anglers.length

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
            {ready && (anglers.length > 0 ? (
              <>
                <AnglerCombobox anglers={options} value={selected.map((angler) => angler.id)} onValueChange={setSelectedIds} />
                <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-sm" aria-live="polite">
                  {selected.map((angler) => {
                    const place = 1 + anglers.filter((item) => item.total > angler.total).length
                    const tied = anglers.filter((item) => item.total === angler.total).length > 1
                    return (
                      <span key={angler.id} className="inline-flex items-center gap-2">
                        <span aria-hidden="true" className={`h-0.5 w-5 bg-current ${standingColor(anglers.indexOf(angler))}`} />
                        {angler.name} · {angler.total.toFixed(2)}″ · {tied ? "Tied " : ""}{formatPlace(place)}
                      </span>
                    )
                  })}
                  <span className="text-xs text-muted-foreground">{selected.length === 0 ? "Select anglers to highlight their standings. · " : "Final scoring totals · "}{anglers.length} anglers with catches</span>
                </div>
                <EstimatedStandingsChart key={JSON.stringify(selected.map((angler) => angler.id))} anglers={anglers} selected={selected} start={start} end={end} timeZone={detail.data!.timezone} />
                <p className="text-xs text-muted-foreground">Estimated from final scoring catches and photo times. Earlier culled catches are unavailable, so historical totals may be understated.{hasTies ? " Official tie-break results are unavailable; equal totals share a final place." : ""}</p>
              </>
            ) : <p className="text-muted-foreground">No catches with usable times and lengths to display.</p>)}
            {excludedCount > 0 && <p className="text-xs text-muted-foreground">{excludedCount} {excludedCount === 1 ? "catch excluded" : "catches excluded"} because the angler, time, or length is invalid.</p>}
          </>
        )}
      </CardContent>
    </Card>
  )
}
