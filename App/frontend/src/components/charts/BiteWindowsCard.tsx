import { useId, useState } from "react"
import type { ReactNode } from "react"
import { Settings2 } from "lucide-react"
import { Card, CardAction, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { NativeSelect, NativeSelectOption } from "@/components/ui/native-select"
import { Popover, PopoverContent, PopoverDescription, PopoverHeader, PopoverTitle, PopoverTrigger } from "@/components/ui/popover"
import { describeBiteWindow, formatWindowTime } from "@/lib/biteWindows"
import type { BiteWindow, BiteWindowFilters } from "@/lib/biteWindows"

interface BiteWindowsCardProps {
  windows: readonly BiteWindow[]
  timeLabel: string
  status?: ReactNode
  emptyMessage?: string
  filters?: BiteWindowFilters
  onFiltersChange?: (filters: BiteWindowFilters) => void
}

// Presentation only: accepts counts from any dataset, including filtered or
// aggregated catches. Data acquisition and binning belong to the caller.
export default function BiteWindowsCard({ windows, timeLabel, status, filters, onFiltersChange, emptyMessage = "No catches to display." }: BiteWindowsCardProps) {
  const titleId = useId()
  const speciesId = useId()
  const lengthId = useId()
  const [activeMinute, setActiveMinute] = useState<number | null>(null)
  const active = windows.find((window) => window.startMinute === activeMinute)
  const total = windows.reduce((sum, window) => sum + window.count, 0)
  const width = Math.max(520, windows.length * 36 + 72)
  const height = 280
  const left = 46
  const top = 16
  const bottom = 220
  const plotWidth = width - left - 16
  const step = Math.max(1, Math.ceil(Math.max(0, ...windows.map((window) => window.count)) / 4))
  const maximum = Math.max(step, Math.ceil(Math.max(0, ...windows.map((window) => window.count)) / step) * step)
  const ticks = Array.from({ length: maximum / step + 1 }, (_, index) => index * step)
  const barWidth = plotWidth / Math.max(1, windows.length)

  return (
    <Card role="article" aria-labelledby={titleId} className="min-w-0">
      <CardHeader>
        <CardTitle><h2 id={titleId}>Bite Windows</h2></CardTitle>
        <CardDescription>Catches in 30-minute windows · {timeLabel}</CardDescription>
        {filters && onFiltersChange && (
          <CardAction>
            <Popover>
              <PopoverTrigger render={<Button variant="outline" size="sm" aria-label="Bite window settings" />}>
                <Settings2 aria-hidden="true" /> Settings
              </PopoverTrigger>
              <PopoverContent align="end" className="max-w-[calc(100vw-2rem)] gap-4 p-4">
                <PopoverHeader>
                  <PopoverTitle>Bite window settings</PopoverTitle>
                  <PopoverDescription>Filters update the chart immediately.</PopoverDescription>
                </PopoverHeader>
                <div className="grid gap-2">
                  <Label htmlFor={speciesId}>Species</Label>
                  <NativeSelect id={speciesId} className="w-full" value={filters.species}
                    onChange={(event) => onFiltersChange({ ...filters, species: event.target.value as BiteWindowFilters["species"] })}>
                    <NativeSelectOption value="both">Both</NativeSelectOption>
                    <NativeSelectOption value="Largemouth Bass">Largemouth</NativeSelectOption>
                    <NativeSelectOption value="Smallmouth Bass">Smallmouth</NativeSelectOption>
                  </NativeSelect>
                </div>
                <div className="grid gap-2">
                  <Label htmlFor={lengthId}>Minimum length (inches)</Label>
                  <Input id={lengthId} type="number" min={0} step="any" placeholder="No minimum"
                    value={filters.minimumLength || ""}
                    onChange={(event) => {
                      const minimumLength = Number(event.target.value)
                      if (Number.isFinite(minimumLength) && minimumLength >= 0) {
                        onFiltersChange({ ...filters, minimumLength })
                      }
                    }} />
                </div>
                <Button variant="outline" size="sm" disabled={filters.species === "both" && filters.minimumLength === 0}
                  onClick={() => onFiltersChange({ species: "both", minimumLength: 0 })}>
                  Reset filters
                </Button>
              </PopoverContent>
            </Popover>
          </CardAction>
        )}
      </CardHeader>
      <CardContent className="space-y-3">
        {filters && (
          <p className="text-xs text-muted-foreground" aria-live="polite">
            {filters.species === "both" ? "Largemouth + Smallmouth" : filters.species.replace(" Bass", "")} · {filters.minimumLength > 0 ? `${filters.minimumLength}″ minimum` : "No minimum length"}
          </p>
        )}
        {status}
        {total === 0 ? (
          emptyMessage && <p className="text-muted-foreground">{emptyMessage}</p>
        ) : (
          <>
            <p className="text-xs text-muted-foreground">{total.toLocaleString()} catches</p>
            <div className="overflow-x-auto" role="region" aria-label="Bite windows chart, scroll horizontally for more times" tabIndex={0}>
              <svg width="100%" viewBox={`0 0 ${width} ${height}`} style={{ minWidth: width }} role="group" aria-label="Catch counts by half-hour window">
                <text x={left} y={10} className="fill-muted-foreground text-[10px]">Catches</text>
                {ticks.map((tick) => {
                  const y = bottom - (tick / maximum) * (bottom - top)
                  return (
                    <g key={tick} aria-hidden="true">
                      <line x1={left} x2={width - 16} y1={y} y2={y} className="stroke-border" />
                      <text x={left - 8} y={y + 4} textAnchor="end" className="fill-muted-foreground text-[11px]">{tick}</text>
                    </g>
                  )
                })}
                {windows.map((window, index) => {
                  const x = left + index * barWidth
                  const barHeight = (window.count / maximum) * (bottom - top)
                  const description = describeBiteWindow(window)
                  return (
                    <g key={window.startMinute}>
                      <rect
                        x={x + 3} y={bottom - barHeight} width={barWidth - 6} height={barHeight}
                        rx={3} className="fill-teal-600 dark:fill-teal-400" aria-hidden="true"
                      />
                      <rect
                        x={x} y={top} width={barWidth} height={bottom - top}
                        className="fill-transparent hover:fill-foreground/5 focus:fill-foreground/5 focus:outline-none"
                        tabIndex={0} role="img" aria-label={description}
                        onMouseEnter={() => setActiveMinute(window.startMinute)}
                        onMouseLeave={() => setActiveMinute(null)}
                        onFocus={() => setActiveMinute(window.startMinute)}
                        onBlur={() => setActiveMinute(null)}
                        onClick={() => setActiveMinute(window.startMinute)}
                      ><title>{description}</title></rect>
                      {(windows.length <= 8 || index % 2 === 0) && (
                        <text x={x + barWidth / 2} y={bottom + 20} textAnchor="middle" className="fill-muted-foreground text-[10px]" aria-hidden="true">
                          {formatWindowTime(window.startMinute)}
                        </text>
                      )}
                    </g>
                  )
                })}
                <text x={left + plotWidth / 2} y={height - 8} textAnchor="middle" className="fill-muted-foreground text-[11px]">Time of day · {timeLabel}</text>
              </svg>
            </div>
            <p className="min-h-4 text-xs text-muted-foreground" aria-live="polite">
              {active ? describeBiteWindow(active) : "Hover, focus, or tap a bar for its window and catch count."}
            </p>
          </>
        )}
      </CardContent>
    </Card>
  )
}
