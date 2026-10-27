import { useMemo } from "react"
import { useQuery } from "@tanstack/react-query"
import { tournamentQueries } from "@/api/queries"
import BiteWindowsCard from "@/components/charts/BiteWindowsCard"
import { Button } from "@/components/ui/button"
import { buildBiteWindows } from "@/lib/biteWindows"

export default function TournamentBiteWindows({ tournamentId }: { tournamentId: number | null }) {
  const detailQuery = useQuery(tournamentQueries.detail(tournamentId))
  const catchesQuery = useQuery(tournamentQueries.catches(tournamentId))
  const timeZone = detailQuery.data?.timezone
  const { windows, excludedCount } = useMemo(() => buildBiteWindows(
    timeZone ? (catchesQuery.data ?? []).map((item) => ({
      catchTime: item.catch_time,
      timeZone,
    })) : [],
  ), [catchesQuery.data, timeZone])
  const failed = detailQuery.isError || catchesQuery.isError
  const fetching = detailQuery.isFetching || catchesQuery.isFetching
  const ready = !!timeZone && catchesQuery.data !== undefined
  const loading = tournamentId !== null && !ready && !failed

  return (
    <BiteWindowsCard
      windows={windows}
      timeLabel={timeZone ?? "tournament local time"}
      emptyMessage={tournamentId === null
        ? "Select a tournament to view bite windows."
        : loading || (failed && !ready) ? "" : "No catches with usable times to display."}
      status={tournamentId !== null && (
        <>
          {failed ? (
            <p role="alert" className="text-sm text-muted-foreground">
              {ready ? "Couldn't refresh bite windows. Showing saved data." : "Unable to load bite windows."}{" "}
              <Button
                variant="link" className="h-auto p-0" disabled={fetching}
                onClick={() => {
                  if (detailQuery.isError) void detailQuery.refetch()
                  if (catchesQuery.isError) void catchesQuery.refetch()
                }}
              >Try again</Button>
            </p>
          ) : loading || fetching ? (
            <p role="status" className="text-sm text-muted-foreground">
              {loading ? "Loading bite windows…" : "Refreshing bite windows…"}
            </p>
          ) : null}
          {excludedCount > 0 && (
            <p className="text-xs text-muted-foreground">
              {excludedCount.toLocaleString()} {excludedCount === 1 ? "catch excluded because its time or timezone is invalid." : "catches excluded because their time or timezone is invalid."}
            </p>
          )}
        </>
      )}
    />
  )
}
