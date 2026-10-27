import { useId, useState } from "react"
import type { ReactNode } from "react"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { describeBiteWindow, formatWindowTime } from "@/lib/biteWindows"
import type { BiteWindow } from "@/lib/biteWindows"

interface BiteWindowsCardProps {
  windows: readonly BiteWindow[]
  timeLabel: string
  status?: ReactNode
  emptyMessage?: string
}

// Presentation only: accepts counts from any dataset, including filtered or
// aggregated catches. Data acquisition and binning belong to the caller.
export default function BiteWindowsCard({ windows, timeLabel, status, emptyMessage = "No catches to display." }: BiteWindowsCardProps) {
  const titleId = useId()
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
      </CardHeader>
      <CardContent className="space-y-3">
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
