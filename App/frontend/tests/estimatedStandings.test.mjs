import assert from "node:assert/strict"
import { test } from "node:test"
import { buildEstimatedStandings } from "../src/lib/estimatedStandings.ts"

const sample = (angler_name, catch_time, length_inches) => ({ angler_name, catch_time, length_inches })

test("sorts catches chronologically, accumulates final scoring lengths, and defaults to the highest total", () => {
  const result = buildEstimatedStandings([
    sample("Alex", "2026-07-01T13:00:00Z", "18.25"),
    sample("Blair", "2026-07-01T12:00:00Z", "20.00"),
    sample("Alex", "2026-07-01T11:00:00Z", "15.50"),
  ])
  assert.deepEqual(result.anglers.map(({ name, total }) => ({ name, total })), [
    { name: "Alex", total: 33.75 }, { name: "Blair", total: 20 },
  ])
  assert.deepEqual(result.anglers[0].points, [
    { time: Date.parse("2026-07-01T11:00:00Z"), total: 15.5 },
    { time: Date.parse("2026-07-01T13:00:00Z"), total: 33.75 },
  ])
  assert.equal(result.start, Date.parse("2026-07-01T10:50:00Z"))
  assert.equal(result.end, Date.parse("2026-07-01T13:10:00Z"))
})

test("combines simultaneous catches per angler and sorts tied leaders deterministically without floating point drift", () => {
  const { anglers } = buildEstimatedStandings([
    sample("Blair", "2026-07-01T07:00:00-04:00", "10.10"),
    sample("Blair", "2026-07-01T11:00:00Z", "10.20"),
    sample("Alex", "2026-07-01T11:00:00Z", "20.30"),
  ])
  assert.deepEqual(anglers.map(({ name, total }) => ({ name, total })), [
    { name: "Alex", total: 20.3 }, { name: "Blair", total: 20.3 },
  ])
  assert.deepEqual(anglers[1].points, [{ time: Date.parse("2026-07-01T11:00:00Z"), total: 20.3 }])
})

test("rejects invalid times, ambiguous local times, missing anglers, and nonpositive lengths", () => {
  const result = buildEstimatedStandings([
    sample("Alex", "invalid", "10"),
    sample("Alex", "2026-07-01T11:00:00", "10"),
    sample(" ", "2026-07-01T11:00:00Z", "10"),
    ...["0", "-1", "", "NaN", "Infinity"].map((length) => sample("Alex", "2026-07-01T11:00:00Z", length)),
  ])
  assert.deepEqual(result, { anglers: [], start: 0, end: 0, excludedCount: 8 })
  assert.deepEqual(buildEstimatedStandings([]), { anglers: [], start: 0, end: 0, excludedCount: 0 })
})
