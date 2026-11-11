import { useId } from "react"
import { useQuery } from "@tanstack/react-query"
import { Cloud, Gauge, Thermometer, Wind } from "lucide-react"

import { ApiError } from "@/api/client"
import { tournamentQueries } from "@/api/queries"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card"
import { formatWeatherValue, pressureInHg, weatherRange, windDirection } from "@/lib/weather"

function weatherError(error: Error | null) {
  if (error instanceof ApiError) {
    if (error.status === 409) return "Historical weather is not available for this tournament yet."
    if (error.status === 503) return "Historical weather is not available for this tournament yet."
    if (error.status === 404) return "This tournament is no longer available."
  }
  return "Unable to load tournament weather."
}

export default function TournamentWeatherCard({ tournamentId }: { tournamentId: number | null }) {
  const titleId = useId()
  const query = useQuery(tournamentQueries.weather(tournamentId))
  const weather = query.data
  const time = weather ? new Intl.DateTimeFormat("en-US", {
    timeZone: weather.timezone, hour: "numeric", minute: "2-digit",
  }) : null
  const zone = weather ? new Intl.DateTimeFormat("en-US", {
    timeZone: weather.timezone, timeZoneName: "short",
  }).formatToParts(new Date(weather.starts_at)).find((part) => part.type === "timeZoneName")?.value : null
  const date = weather ? new Intl.DateTimeFormat("en-US", {
    timeZone: weather.timezone, month: "short", day: "numeric", year: "numeric",
  }).format(new Date(weather.starts_at)) : null
  const summaries = weather ? [
    { label: "Air temperature", icon: Thermometer, value: weatherRange(weather.hourly.map((row) => row.temperature_f), "°F") },
    { label: "Sea-level pressure", icon: Gauge, value: weatherRange(weather.hourly.map((row) => pressureInHg(row.pressure_hpa)), " inHg", 2) },
    { label: "Cloud cover", icon: Cloud, value: weatherRange(weather.hourly.map((row) => row.cloud_cover_percent), "%") },
    { label: "Wind speed", icon: Wind, value: weatherRange(weather.hourly.map((row) => row.wind_speed_mph), " mph", 1) },
  ] : []

  return (
    <Card role="article" aria-labelledby={titleId} className="min-w-0 lg:col-span-2">
      <CardHeader>
        <CardTitle><h2 id={titleId}>Tournament Weather</h2></CardTitle>
        <CardDescription>
          {weather && time
            ? `${date} · ${time.format(new Date(weather.starts_at))}–${time.format(new Date(weather.ends_at))} ${zone}`
            : "Hourly weather during tournament hours"}
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-5">
        {tournamentId === null ? (
          <p className="text-muted-foreground">Select a tournament to view its weather.</p>
        ) : query.isError ? (
          <p role="alert" className="text-sm text-muted-foreground">
            {weather ? "Couldn't refresh weather. Showing saved data." : weatherError(query.error)}{" "}
            {/* <Button variant="link" className="h-auto p-0" disabled={query.isFetching} onClick={() => void query.refetch()}>
              Try again
            </Button> */}
          </p>
        ) : query.isFetching ? (
          <p role="status" className="text-sm text-muted-foreground">
            {weather ? "Refreshing weather…" : "Loading tournament weather…"}
          </p>
        ) : null}
        {weather && (
          <>
            {weather.coverage === "partial" && (
              <p className="flex flex-wrap items-center gap-2 text-sm text-muted-foreground">
                <Badge variant="secondary">Partial data</Badge> Some hours or measurements are unavailable.
              </p>
            )}
            {weather.hourly.length === 0 ? (
              <p className="text-muted-foreground">No hourly weather available during tournament hours.</p>
            ) : (
              <>
                <dl className="grid grid-cols-2 gap-4 xl:grid-cols-4">
                  {summaries.map(({ label, icon: Icon, value }) => (
                    <div key={label} className="space-y-1 rounded-lg bg-muted/50 p-3">
                      <dt className="flex items-center gap-2 test-sm text-muted-foreground"><Icon className="size-4 shrink-0" aria-hidden="true" />{label}</dt>
                      <dd className="text-base font-semibold tabular-nums sm:text-lg">{value}</dd>
                    </div>
                  ))}
                </dl>
                <p className="test-sm text-muted-foreground sm:hidden">Scroll the table sideways to see all weather readings.</p>
                <div role="region" aria-label="Hourly tournament weather" tabIndex={0} className="overflow-x-auto rounded-lg border focus-visible:outline-2 focus-visible:outline-ring">
                  <table className="w-full min-w-[560px] text-left text-sm tabular-nums">
                    <caption className="sr-only">Hourly weather on {date}. Times in {weather.timezone}. Wind directions indicate where the wind comes from. A dash means unavailable.</caption>
                    <thead className="bg-muted/50 test-sm text-muted-foreground">
                      <tr>
                        <th scope="col" className="px-4 py-3 font-medium">Time ({zone})</th>
                        <th scope="col" className="px-4 py-3 font-medium">Temperature</th>
                        <th scope="col" className="px-4 py-3 font-medium">Pressure</th>
                        <th scope="col" className="px-4 py-3 font-medium">Cloud cover</th>
                        <th scope="col" className="px-4 py-3 font-medium">Wind</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y">
                      {weather.hourly.map((row) => (
                        <tr key={row.time} className="hover:bg-muted/30">
                          <th scope="row" className="whitespace-nowrap px-4 py-3 font-medium"><time dateTime={row.time}>{time?.format(new Date(row.time))}</time></th>
                          <td className="whitespace-nowrap px-4 py-3">{formatWeatherValue(row.temperature_f, "°F", 1)}</td>
                          <td className="whitespace-nowrap px-4 py-3">{formatWeatherValue(pressureInHg(row.pressure_hpa), " inHg", 2)}</td>
                          <td className="whitespace-nowrap px-4 py-3">{formatWeatherValue(row.cloud_cover_percent, "%")}</td>
                          <td className="whitespace-nowrap px-4 py-3">
                            {row.wind_speed_mph === 0 ? "Calm" : (
                              <>{formatWeatherValue(row.wind_speed_mph, " mph", 1)} <span className="text-muted-foreground" title={row.wind_direction_degrees === null ? "Direction unavailable" : `From ${row.wind_direction_degrees}°`}>{windDirection(row.wind_direction_degrees)}</span></>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </>
            )}
          </>
        )}
      </CardContent>
      {weather && (
        <CardFooter className="flex-wrap justify-between gap-2 text-sm text-muted-foreground">
          <p>
            Weather data provided by{" "}
            <a href="https://open-meteo.com/" target="_blank" rel="noreferrer" className="underline underline-offset-4 hover:text-foreground">Open-Meteo</a>
            {" · "}
            <a href="https://creativecommons.org/licenses/by/4.0/" target="_blank" rel="noreferrer" className="underline underline-offset-4 hover:text-foreground">CC BY 4.0</a>
          </p>
          <p className="w-full">Adapted: filtered to tournament hours, pressure converted to inHg, ranges calculated, and values rounded.</p>
        </CardFooter>
      )}
    </Card>
  )
}
