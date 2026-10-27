import assert from "node:assert/strict"
import { test } from "node:test"
import { formatWeatherValue, weatherRange, windDirection } from "../src/lib/weather.ts"

test("weather ranges ignore missing data and preserve zero measurements", () => {
  assert.equal(weatherRange([null, 0, 25, null], "%"), "0 – 25%")
  assert.equal(weatherRange([null, null], "°F"), "—")
  assert.equal(weatherRange([1012.1, 1008.9], " hPa", 1), "1008.9 – 1012.1 hPa")
  assert.equal(weatherRange([8, 8], " mph"), "8 mph")
  assert.equal(formatWeatherValue(null, "°F"), "—")
  assert.equal(formatWeatherValue(0, " mph"), "0 mph")
})

test("wind directions wrap around north and retain unavailable direction", () => {
  for (const north of [0, 360, 359, -1]) assert.equal(windDirection(north), "N")
  assert.equal(windDirection(90), "E")
  assert.equal(windDirection(210), "SSW")
  assert.equal(windDirection(270), "W")
  assert.equal(windDirection(null), "—")
})
