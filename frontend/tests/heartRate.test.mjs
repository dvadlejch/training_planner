import assert from "node:assert/strict";
import test from "node:test";
import { calculateHeartRateZones } from "../src/heartRate.ts";

test("180 bpm produces non-overlapping zones including the maximum", () => {
  const zones = calculateHeartRateZones(180);
  assert.deepEqual(zones.map(({ minBpm, maxBpm }) => [minBpm, maxBpm]),
    [[90, 107], [108, 125], [126, 143], [144, 161], [162, 180]]);
});

test("fractional percentage boundaries are rounded without gaps", () => {
  const zones = calculateHeartRateZones(181);
  assert.deepEqual([zones[1].minBpm, zones[1].maxBpm], [109, 126]);
  assert.equal(zones[4].maxBpm, 181);
  for (let i = 1; i < zones.length; i++) {
    assert.equal(zones[i].minBpm, zones[i - 1].maxBpm + 1);
  }
});

test("invalid or fractional maximum heart rates are rejected", () => {
  for (const value of [0, -1, 49, 301, 180.5, NaN, Infinity]) {
    assert.throws(() => calculateHeartRateZones(value), RangeError);
  }
});
