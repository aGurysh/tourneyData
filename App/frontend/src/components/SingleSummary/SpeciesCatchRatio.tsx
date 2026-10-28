import type { TournamentDetail } from "@/api/tournaments"
import { SPECIES_COLORS } from "@/constants/species"

export default function SpeciesCatchRatio({ counts }: { counts: TournamentDetail["species_catch_counts"] }) {
  const total = counts.reduce((sum, item) => sum + item.catch_count, 0)

  if (total === 0) {
    return <p className="mt-3 test-sm text-muted-foreground">No submitted catches recorded.</p>
  }

  const segments = counts.filter((item) => item.catch_count > 0).map((item) => ({
    name: item.species_name === "Largemouth Bass" ? "Largemouth" : item.species_name === "Smallmouth Bass" ? "Smallmouth" : item.species_name ?? "Unknown species",
    count: item.catch_count,
    averageLength: Number(item.average_length_inches).toLocaleString("en-US", {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    }),
    percent: (item.catch_count / total) * 100,
    color: (item.species_name ? SPECIES_COLORS[item.species_name]?.background : undefined) ?? "bg-gray-200",
  }))
  const describe = (segment: typeof segments[number]) => `${segment.name}: ${segment.count.toLocaleString()} (${segment.percent.toFixed(1)}%) · Average length: ${segment.averageLength} inches`

  return (
    <div className="mt-3 space-y-4">
      <div
        role="img"
        aria-label={`Submitted catch ratio. ${segments.map(describe).join("; ")}`}
        className="flex h-3 w-full overflow-hidden rounded-full"
      >
        {segments.map((segment) => (
          <div
            key={segment.name}
            title={describe(segment)}
            className={`h-full ${segment.color}`}
            style={{ width: `${segment.percent}%` }}
          />
        ))}
      </div>
      <div className="flex flex-wrap justify-between gap-x-4 gap-y-1 test-sm text-muted-foreground">
        {segments.map((segment) => (
          <div key={segment.name} className="space-y-1">
            <p>{segment.name}: {segment.count.toLocaleString()} ({segment.percent.toFixed(1)}%)</p>
            <p>Average length: <span className="font-medium ftext-foreground">{segment.averageLength} inches</span></p>
          </div>
        ))}
      </div>
      <p className="test-sm text-muted-foreground">{total.toLocaleString()} submitted catches</p>
    </div>
  )
}
