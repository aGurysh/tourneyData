import { useId, useMemo } from "react"
import { useQuery } from "@tanstack/react-query"

import { tournamentQueries } from "@/api/queries"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { buildScoringBreakdown } from "@/lib/scoringBreakdown"

export default function TournamentScoringBreakdown({ tournamentId }: { tournamentId: number | null }) {
  const titleId = useId()
  const detail = useQuery(tournamentQueries.detail(tournamentId))
  const catches = useQuery(tournamentQueries.catches(tournamentId))
  const ready = detail.data !== undefined && catches.data !== undefined
  const failed = detail.isError || catches.isError
  const fetching = detail.isFetching || catches.isFetching
  const { bins, average } = useMemo(() => buildScoringBreakdown(catches.data ?? [], detail.data?.angler_count ?? 0), [catches.data, detail.data?.angler_count])
  const maximum = Math.max(1, ...bins.map((bin) => bin.count))
  const averageLabel = average === null ? "" : `Average: ${average.toFixed(2)}″`
  const containsAverage = (bin: typeof bins[number]) => average !== null && average >= bin.lower && average < bin.upper

  return (
    <Card role="article" aria-labelledby={titleId} className="min-w-0">
      <CardHeader>
        <CardTitle><h2 id={titleId}>Scoring Breakdown</h2></CardTitle>
        <CardDescription>Anglers by total scoring inches, in 5-inch ranges</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {tournamentId === null ? <p className="text-muted-foreground">Select a tournament to view its scoring breakdown.</p> : (
          <>
            {failed ? (
              <p role="alert" className="text-sm text-muted-foreground">
                {ready ? "Couldn't refresh the scoring breakdown. Showing saved data." : "Unable to load the scoring breakdown."}{" "}
                <Button variant="link" className="h-auto p-0" disabled={fetching} onClick={() => {
                  if (detail.isError) void detail.refetch()
                  if (catches.isError) void catches.refetch()
                }}>Try again</Button>
              </p>
            ) : !ready || fetching ? <p role="status" className="text-sm text-muted-foreground">{ready ? "Refreshing scoring breakdown…" : "Loading scoring breakdown…"}</p> : null}
            {ready && (detail.data!.angler_count > 0 ? (
              <>
                <div role="img" aria-label={`Scoring breakdown. ${averageLabel}, including anglers with no scoring catches. The average range is outlined in amber. ${bins.map((bin) => `${bin.lower} to under ${bin.upper} inches: ${bin.count} anglers`).join("; ")}`}>
                  <div aria-hidden="true" className="space-y-2 text-sm tabular-nums">
                    <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
                      <p className="text-muted-foreground">Total inches</p>
                      <p className="flex items-center gap-2 font-medium text-amber-700 dark:text-amber-400">
                        <span className="h-3 w-5 rounded-sm border border-dashed border-current" />
                        {averageLabel}
                      </p>
                    </div>
                    {bins.map((bin) => (
                      <div key={bin.lower} title={`${bin.lower} to under ${bin.upper} inches: ${bin.count} anglers`} className="grid grid-cols-[5rem_minmax(0,1fr)_2.5rem] items-center gap-3">
                        <span className="text-right whitespace-nowrap text-muted-foreground">{bin.lower}-{bin.upper}</span>
                        <div className={`h-5 rounded-sm bg-muted/40 ${containsAverage(bin) ? "outline outline-2 outline-offset-2 outline-dashed outline-amber-600 dark:outline-amber-400" : ""}`}>
                          <div className="h-full rounded-sm bg-teal-600 dark:bg-teal-400" style={{ width: `${bin.count / maximum * 100}%` }} />
                        </div>
                        <span className="font-medium">{bin.count}</span>
                      </div>
                    ))}
                    <div className="grid grid-cols-[5rem_minmax(0,1fr)_2.5rem] gap-3 text-muted-foreground">
                      <div className="col-start-2 flex justify-between border-t pt-2"><span>0</span><span>{maximum}</span></div>
                      <p className="col-start-2 text-center">Number of anglers</p>
                    </div>
                  </div>
                </div>
              </>
            ) : <p className="text-muted-foreground">No anglers recorded for this tournament.</p>)}
          </>
        )}
      </CardContent>
    </Card>
  )
}
