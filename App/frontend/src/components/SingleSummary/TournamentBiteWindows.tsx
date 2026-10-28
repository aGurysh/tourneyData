import { useMemo, useState } from "react"
import { useQuery } from "@tanstack/react-query"
import { tournamentQueries } from "@/api/queries"
import BiteWindowsCard from "@/components/charts/BiteWindowsCard"
import { Button } from "@/components/ui/button"
import { buildBiteWindows, matchesBiteWindowFilters } from "@/lib/biteWindows"
import type { BiteWindowFilters } from "@/lib/biteWindows"

export default function TournamentBiteWindows({ tournamentId }: { tournamentId: number | null }) {
  const [selectedFilters, setFilters] = useState<BiteWindowFilters>({ species: null, minimumLength: 0 })
  const detailQuery = useQuery(tournamentQueries.detail(tournamentId))
  const catchesQuery = useQuery(tournamentQueries.catches(tournamentId))
  const speciesOptions = useMemo(() => [...new Set(
    (catchesQuery.data ?? []).map((item) => item.species_name ?? ""),
  )].sort((a, b) => a.localeCompare(b)), [catchesQuery.data])
  // A species selected for another tournament may not occur in this one.
  const filters = useMemo(() => selectedFilters.species !== null && !speciesOptions.includes(selectedFilters.species)
    ? { ...selectedFilters, species: null }
    : selectedFilters, [selectedFilters, speciesOptions])
  const timeZone = detailQuery.data?.timezone
  const { windows, excludedCount } = useMemo(() => buildBiteWindows(
    timeZone ? (catchesQuery.data ?? []).filter((item) => matchesBiteWindowFilters({
      species: item.species_name,
      length: Number(item.length_inches),
    }, filters)).map((item) => ({
      catchTime: item.catch_time,
      timeZone,
    })) : [],
  ), [catchesQuery.data, timeZone, filters])
  const failed = detailQuery.isError || catchesQuery.isError
  const fetching = detailQuery.isFetching || catchesQuery.isFetching
  const ready = !!timeZone && catchesQuery.data !== undefined
  const loading = tournamentId !== null && !ready && !failed

  return (
    <BiteWindowsCard
      windows={windows}
      filters={filters}
      speciesOptions={speciesOptions}
      onFiltersChange={setFilters}
      timeLabel={timeZone ?? "tournament local time"}
      emptyMessage={tournamentId === null
        ? "Select a tournament to view bite windows."
        : loading || (failed && !ready) ? "" : "No catches match these filters with usable times. Try All species or a lower minimum length."}
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
