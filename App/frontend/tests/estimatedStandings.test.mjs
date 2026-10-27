import assert from "node:assert/strict"
import { test } from "node:test"
import { buildEstimatedStandings } from "../src/lib/estimatedStandings.ts"

const ids = new Map()
const sample = (angler_name, catch_time, length_inches) => {
  if (!ids.has(angler_name)) ids.set(angler_name, ids.size + 1)
  return { angler_id: ids.get(angler_name), angler_name, catch_time, length_inches }
}

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
    { time: Date.parse("2026-07-01T11:00:00Z"), total: 15.5, lengths: [15.5], place: 1, tied: false },
    { time: Date.parse("2026-07-01T13:00:00Z"), total: 33.75, lengths: [18.25], place: 1, tied: false },
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
  assert.deepEqual(anglers[1].points, [{ time: Date.parse("2026-07-01T11:00:00Z"), total: 20.3, lengths: [10.1, 10.2], place: 1, tied: true }])
})

test("ranks each catch against every angler's total at that time with shared places for ties", () => {
  const { anglers } = buildEstimatedStandings([
    sample("Alex", "2026-07-01T11:00:00Z", "20"),
    sample("Blair", "2026-07-01T11:00:00Z", "20"),
    sample("Casey", "2026-07-01T12:00:00Z", "15"),
    sample("Casey", "2026-07-01T13:00:00Z", "10"),
    sample("Blair", "2026-07-01T14:00:00Z", "10"),
    sample("Alex", "2026-07-01T15:00:00Z", "5"),
  ])
  const casey = anglers.find((angler) => angler.name === "Casey")
  assert.deepEqual(casey.points.map(({ lengths, place, tied }) => ({ lengths, place, tied })), [
    { lengths: [15], place: 3, tied: false },
    { lengths: [10], place: 1, tied: false },
  ])
  assert.deepEqual(anglers.find((angler) => angler.name === "Alex").points.map(({ place, tied }) => ({ place, tied })), [
    { place: 1, tied: true }, { place: 2, tied: true },
  ])
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


test("keeps two anglers with the same name separate using their database IDs", () => {
  const catches = [1, 2].map((angler_id) => ({ ...sample("Alex", "2026-07-01T11:00:00Z", "20"), angler_id }))
  const { anglers } = buildEstimatedStandings(catches)
  assert.equal(anglers.length, 2)
  assert.deepEqual(anglers.map(({ id, total }) => ({ id, total })), [{ id: 1, total: 20 }, { id: 2, total: 20 }])
  assert.ok(anglers.every((angler) => angler.points[0].tied))
})
