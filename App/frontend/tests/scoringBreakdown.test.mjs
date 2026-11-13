import assert from "node:assert/strict"
import { test } from "node:test"
import { buildScoringBreakdown } from "../src/lib/scoringBreakdown.ts"

test("groups total scores into exclusive 5-inch ranges and includes anglers without catches", () => {
  const { bins, average } = buildScoringBreakdown([
    { angler_id: 1, length_inches: "10.10" },
    { angler_id: 1, length_inches: "4.90" },
    { angler_id: 2, length_inches: "14.99" },
    { angler_id: 3, length_inches: "5.00" },
    { angler_id: 4, length_inches: "4.99" },
  ], 6)
  assert.deepEqual(bins, [
    { lower: 15, upper: 20, count: 1 },
    { lower: 10, upper: 15, count: 1 },
    { lower: 5, upper: 10, count: 1 },
    { lower: 0, upper: 5, count: 3 },
  ])
  assert.equal(bins.reduce((sum, bin) => sum + bin.count, 0), 6)
  assert.equal(average, 39.98 / 6)
})

test("preserves empty ranges and handles tournaments with no scoring catches", () => {
  assert.deepEqual(buildScoringBreakdown([], 3), { bins: [{ lower: 0, upper: 5, count: 3 }], average: 0 })
  assert.deepEqual(buildScoringBreakdown([], 0), { bins: [{ lower: 0, upper: 5, count: 0 }], average: null })
  assert.deepEqual(buildScoringBreakdown([{ angler_id: 1, length_inches: "10" }], 1).bins, [
    { lower: 10, upper: 15, count: 1 },
    { lower: 5, upper: 10, count: 0 },
    { lower: 0, upper: 5, count: 0 },
  ])
})
