import assert from "node:assert/strict";
import test from "node:test";
import { addDays, monthRange, shiftMonth } from "../src/calendar.ts";

// Monday-aligned rows include every date for four-, five- and six-row months.
test("month ranges cover leap years and every weekday alignment", () => {
  for (const [month, start, end, days] of [
    ["2021-02", "2021-02-01", "2021-02-28", 28],
    ["2024-02", "2024-01-29", "2024-03-03", 35],
    ["2026-03", "2026-02-23", "2026-04-05", 42],
    ["2026-10", "2026-09-28", "2026-11-01", 35],
    ["2026-11", "2026-10-26", "2026-12-06", 42],
  ]) {
    assert.deepEqual(monthRange(month), { start, end, days });
    assert.equal(new Date(`${start}T12:00:00`).getDay(), 1);
    assert.equal(new Date(`${end}T12:00:00`).getDay(), 0);
    assert.equal(addDays(start, days - 1), end);
  }
});

// Navigating through short months and year boundaries must never skip a month.
test("month navigation handles February and year rollover", () => {
  assert.equal(shiftMonth("2026-01", 1), "2026-02");
  assert.equal(shiftMonth("2026-03", -1), "2026-02");
  assert.equal(shiftMonth("2026-12", 1), "2027-01");
  assert.equal(shiftMonth("2026-01", -1), "2025-12");
});
