import { useEffect, useRef, useState } from "react"
import type { AnglerStanding, StandingPoint } from "@/lib/estimatedStandings"

const colors = [
  "text-teal-600 dark:text-teal-400",
  "text-violet-600 dark:text-violet-400",
  "text-orange-600 dark:text-orange-400",
  "text-blue-600 dark:text-blue-400",
  "text-rose-600 dark:text-rose-400",
  "text-lime-600 dark:text-lime-400",
  "text-fuchsia-600 dark:text-fuchsia-400",
  "text-cyan-600 dark:text-cyan-400",
]

export const standingColor = (index: number) => colors[index % colors.length]

export default function EstimatedStandingsChart({ anglers, selected, start, end, timeZone }: {
  anglers: AnglerStanding[]
  selected: AnglerStanding[]
  start: number
  end: number
  timeZone: string
}) {
  const ref = useRef<HTMLDivElement>(null)
  const [width, setWidth] = useState(600)
  const [activeCatch, setActiveCatch] = useState<{ name: string; time: number } | null>(null)
  useEffect(() => {
    if (!ref.current) return
    const observer = new ResizeObserver(([entry]) => {
      if (entry.contentRect.width > 0) setWidth(entry.contentRect.width)
    })
    observer.observe(ref.current)
    return () => observer.disconnect()
  }, [])
  const left = 48
  const right = width - 16
  const bottom = 252
  const top = 24
  const max = Math.max(10, Math.ceil(anglers[0].total / 10) * 10)
  const x = (time: number) => left + (time - start) / (end - start) * (right - left)
  const y = (total: number) => bottom - total / max * (bottom - top)
  const formatter = new Intl.DateTimeFormat("en-US", { timeZone, hour: "numeric", minute: "2-digit" })
  const catchDetails = (point: StandingPoint) => `${point.lengths.map((length) => `${length.toFixed(2)}″`).join(" + ")} ${point.lengths.length === 1 ? "fish" : "fish (same time)"} · Estimated place: ${point.tied ? "Tied " : ""}#${point.place}`
  const path = (angler: AnglerStanding) => `M ${left} ${bottom} `
    + angler.points.map((point) => `H ${x(point.time)} V ${y(point.total)}`).join(" ") + ` H ${right}`
  const activeAngler = selected.find((angler) => angler.name === activeCatch?.name)
  const active = activeAngler?.points.find((point) => point.time === activeCatch?.time)
  const tickCount = Math.max(2, Math.floor((right - left) / 90))

  return (
    <div ref={ref} className="min-w-0 space-y-2">
      <svg viewBox={`0 0 ${width} 310`} className="block w-full" role="group" aria-label={`Estimated cumulative scoring lengths. Highlighted anglers: ${selected.map((angler) => angler.name).join(", ") || "none"}`}>
        <text x={left} y={12} className="fill-muted-foreground text-[11px]">Scoring length (inches)</text>
        {Array.from({ length: 5 }, (_, index) => max * index / 4).map((tick) => (
          <g key={tick} aria-hidden="true">
            <line x1={left} x2={right} y1={y(tick)} y2={y(tick)} className="stroke-border" />
            <text x={left - 8} y={y(tick) + 4} textAnchor="end" className="fill-muted-foreground text-[11px]">{tick}</text>
          </g>
        ))}
        {anglers.filter((angler) => !selected.some((item) => item.name === angler.name)).map((angler) => (
          <path key={angler.name} d={path(angler)} fill="none" className="stroke-muted-foreground/25" strokeWidth={1} aria-hidden="true" />
        ))}
        {selected.map((angler) => (
          <g key={angler.name} className={standingColor(anglers.indexOf(angler))}>
            <path d={path(angler)} fill="none" stroke="currentColor" strokeWidth={2.5} aria-hidden="true" />
            {angler.points.map((point) => {
              const description = `${angler.name}: ${catchDetails(point)} at ${formatter.format(point.time)}`
              const activate = () => setActiveCatch({ name: angler.name, time: point.time })
              return (
                <g key={point.time}>
                  <circle cx={x(point.time)} cy={y(point.total)} r={4} fill="currentColor" aria-hidden="true" />
                  <circle cx={x(point.time)} cy={y(point.total)} r={10} tabIndex={0} role="img" aria-label={description}
                    className="fill-transparent stroke-transparent hover:stroke-current focus:stroke-current focus:outline-none"
                    onMouseEnter={activate} onMouseLeave={() => setActiveCatch(null)}
                    onFocus={activate} onBlur={() => setActiveCatch(null)} onClick={activate}>
                    <title>{description}</title>
                  </circle>
                </g>
              )
            })}
          </g>
        ))}
        {Array.from({ length: tickCount }, (_, index) => start + (end - start) * index / (tickCount - 1)).map((time, index) => (
          <text key={time} x={x(time)} y={bottom + 22} textAnchor={index === 0 ? "start" : index === tickCount - 1 ? "end" : "middle"}
            className="fill-muted-foreground text-[11px]" aria-hidden="true">{formatter.format(time)}</text>
        ))}
        <text x={(left + right) / 2} y={302} textAnchor="middle" className="fill-muted-foreground text-[11px]">Time · {timeZone}</text>
      </svg>
      <p className="min-h-5 text-xs text-muted-foreground" aria-live="polite">
        {active ? `${formatter.format(active.time)} · ${activeAngler!.name}: ${catchDetails(active)}` : "Hover, focus, or tap a highlighted catch to see its fish length and estimated place after the catch."}
      </p>
    </div>
  )
}
