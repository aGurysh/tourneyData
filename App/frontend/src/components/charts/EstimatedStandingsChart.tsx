import { useEffect, useRef, useState } from "react"
import type { AnglerStanding } from "@/lib/estimatedStandings"

export default function EstimatedStandingsChart({ anglers, selected, start, end, timeZone }: {
  anglers: AnglerStanding[]
  selected: AnglerStanding
  start: number
  end: number
  timeZone: string
}) {
  const ref = useRef<HTMLDivElement>(null)
  const [width, setWidth] = useState(600)
  const [activeTime, setActiveTime] = useState<number | null>(null)
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
  const path = (angler: AnglerStanding) => `M ${left} ${bottom} `
    + angler.points.map((point) => `H ${x(point.time)} V ${y(point.total)}`).join(" ") + ` H ${right}`
  const active = selected.points.find((point) => point.time === activeTime)
  const tickCount = Math.max(2, Math.floor((right - left) / 90))

  return (
    <div ref={ref} className="min-w-0 space-y-2">
      <svg viewBox={`0 0 ${width} 310`} className="block w-full" role="group" aria-label={`Estimated cumulative scoring lengths. Highlighted angler: ${selected.name}`}>
        <text x={left} y={12} className="fill-muted-foreground text-[11px]">Scoring length (inches)</text>
        {Array.from({ length: 5 }, (_, index) => max * index / 4).map((tick) => (
          <g key={tick} aria-hidden="true">
            <line x1={left} x2={right} y1={y(tick)} y2={y(tick)} className="stroke-border" />
            <text x={left - 8} y={y(tick) + 4} textAnchor="end" className="fill-muted-foreground text-[11px]">{tick}</text>
          </g>
        ))}
        {anglers.filter((angler) => angler.name !== selected.name).map((angler) => (
          <path key={angler.name} d={path(angler)} fill="none" className="stroke-muted-foreground/25" strokeWidth={1} aria-hidden="true" />
        ))}
        <path d={path(selected)} fill="none" className="stroke-teal-600 dark:stroke-teal-400" strokeWidth={2.5} aria-hidden="true" />
        {selected.points.map((point) => {
          const description = `${selected.name}: ${point.total.toFixed(2)} inches at ${formatter.format(point.time)}`
          return (
            <g key={point.time}>
              <circle cx={x(point.time)} cy={y(point.total)} r={4} className="fill-teal-600 dark:fill-teal-400" aria-hidden="true" />
              <circle cx={x(point.time)} cy={y(point.total)} r={10} tabIndex={0} role="img" aria-label={description}
                className="fill-transparent stroke-transparent hover:stroke-teal-600 focus:stroke-teal-600 focus:outline-none dark:hover:stroke-teal-400 dark:focus:stroke-teal-400"
                onMouseEnter={() => setActiveTime(point.time)} onMouseLeave={() => setActiveTime(null)}
                onFocus={() => setActiveTime(point.time)} onBlur={() => setActiveTime(null)} onClick={() => setActiveTime(point.time)}>
                <title>{description}</title>
              </circle>
            </g>
          )
        })}
        {Array.from({ length: tickCount }, (_, index) => start + (end - start) * index / (tickCount - 1)).map((time, index) => (
          <text key={time} x={x(time)} y={bottom + 22} textAnchor={index === 0 ? "start" : index === tickCount - 1 ? "end" : "middle"}
            className="fill-muted-foreground text-[11px]" aria-hidden="true">{formatter.format(time)}</text>
        ))}
        <text x={(left + right) / 2} y={302} textAnchor="middle" className="fill-muted-foreground text-[11px]">Time · {timeZone}</text>
      </svg>
      <p className="min-h-5 text-xs text-muted-foreground" aria-live="polite">
        {active ? `${formatter.format(active.time)} · ${selected.name}: ${active.total.toFixed(2)}″` : "Hover, focus, or tap a highlighted catch to see its time and running total."}
      </p>
    </div>
  )
}
