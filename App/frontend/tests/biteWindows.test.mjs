import assert from "node:assert/strict"
import { test } from "node:test"
import { buildBiteWindows, describeBiteWindow, formatWindowTime, matchesBiteWindowFilters } from "../src/lib/biteWindows.ts"

const sample = (catchTime, timeZone = "America/New_York") => ({ catchTime, timeZone })

test("uses half-open half-hour bins in tournament-local time", () => {
  const result = buildBiteWindows([
    sample("2026-07-01T11:00:00Z"),
    sample("2026-07-01T11:29:59.999Z"),
    sample("2026-07-01T11:30:00Z"),
    sample("2026-07-01T12:00:00Z"),
  ])
  assert.deepEqual(result.windows, [
    { startMinute: 420, count: 2 },
    { startMinute: 450, count: 1 },
    { startMinute: 480, count: 1 },
  ])
  assert.equal(result.excludedCount, 0)
})

test("keeps empty windows between catches and sorts unsorted input", () => {
  assert.deepEqual(buildBiteWindows([
    sample("2026-07-01T12:00:00Z"),
    sample("2026-07-01T11:00:00Z"),
  ]).windows, [
    { startMinute: 420, count: 1 },
    { startMinute: 450, count: 0 },
    { startMinute: 480, count: 1 },
  ])
})

test("combines local time of day across dates, offsets, and timezones", () => {
  const result = buildBiteWindows([
    sample("2026-01-01T12:00:00Z"), // 7 AM, winter
    sample("2026-07-01T11:00:00Z"), // 7 AM, summer
    sample("2026-07-02T07:00:00-04:00"),
    sample("2026-07-01T14:00:00Z", "America/Los_Angeles"),
  ])
  assert.deepEqual(result.windows, [{ startMinute: 420, count: 4 }])
})

test("repeated daylight-saving hours share a local time-of-day bin", () => {
  assert.deepEqual(buildBiteWindows([
    sample("2026-11-01T05:15:00Z"),
    sample("2026-11-01T06:15:00Z"),
  ]).windows, [{ startMinute: 60, count: 2 }])
})

test("midnight uses the first bin and the last window ends at midnight", () => {
  assert.deepEqual(buildBiteWindows([sample("2026-07-01T04:00:00Z")]).windows, [{ startMinute: 0, count: 1 }])
  assert.deepEqual(buildBiteWindows([sample("2026-07-02T03:59:59Z")]).windows, [{ startMinute: 1410, count: 1 }])
  assert.equal(formatWindowTime(0), "12:00 AM")
  assert.equal(formatWindowTime(720), "12:00 PM")
  assert.equal(describeBiteWindow({ startMinute: 1410, count: 1 }), "11:30 PM–12:00 AM: 1 catch")
})

test("excludes unusable timestamps and timezones without guessing browser time", () => {
  const result = buildBiteWindows([
    sample("bad timestamp"),
    sample("2026-07-01T07:00:00"),
    sample("2026-07-01T11:00:00Z", "Invalid/Timezone"),
    sample("2026-07-01T11:00:00Z", ""),
    sample("2026-07-01T11:00:00Z"),
  ])
  assert.equal(result.excludedCount, 4)
  assert.deepEqual(result.windows, [{ startMinute: 420, count: 1 }])
})

test("accepts an empty or caller-filtered dataset without tournament metadata", () => {
  assert.deepEqual(buildBiteWindows([]), { windows: [], excludedCount: 0 })
  const records = [
    { catchTime: "2026-07-01T11:00:00Z", timeZone: "UTC", species: "Smallmouth Bass", length: 15 },
    { catchTime: "2026-07-01T12:00:00Z", timeZone: "UTC", species: "Largemouth Bass", length: 10 },
  ]
  assert.deepEqual(buildBiteWindows(records.filter((item) => item.species === "Smallmouth Bass" && item.length >= 12)).windows,
    [{ startMinute: 660, count: 1 }])
})

test("filters species and includes catches exactly at the minimum length before binning", () => {
  const records = [
    { ...sample("2026-07-01T11:00:00Z"), species: "Smallmouth Bass", length: 15.25 },
    { ...sample("2026-07-01T11:10:00Z"), species: "Largemouth Bass", length: 16 },
    { ...sample("2026-07-01T11:20:00Z"), species: "Smallmouth Bass", length: 15 },
    { ...sample("2026-07-01T12:00:00Z"), species: "Smallmouth Bass", length: 18 },
    { ...sample("2026-07-01T12:10:00Z"), species: null, length: 20 },
    { ...sample("2026-07-01T12:20:00Z"), species: "Spotted Bass", length: 20 },
    { ...sample("2026-07-01T12:30:00Z"), species: "Largemouth Bass", length: NaN },
  ]
  const filtered = (species, minimumLength) => records.filter((item) => matchesBiteWindowFilters(item, { species, minimumLength }))
  assert.equal(filtered(null, 0).length, 6)
  assert.equal(filtered(null, 15.25).length, 5)
  assert.equal(filtered("Spotted Bass", 0).length, 1)
  assert.equal(filtered("", 0).length, 1)
  assert.equal(filtered("Largemouth Bass", 15.25).length, 1)
  assert.deepEqual(buildBiteWindows(filtered("Smallmouth Bass", 15.25)).windows, [
    { startMinute: 420, count: 1 },
    { startMinute: 450, count: 0 },
    { startMinute: 480, count: 1 },
  ])
  assert.deepEqual(buildBiteWindows(filtered(null, 25)).windows, [])
})
