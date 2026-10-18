import assert from "node:assert/strict";
import test from "node:test";
import { JSDOM } from "jsdom";
import { sourceUrl } from "./loadSource.mjs";

const dom = new JSDOM("<!doctype html><body></body>", { url: "http://localhost" });
Object.assign(globalThis, {
  window: dom.window, document: dom.window.document,
  HTMLElement: dom.window.HTMLElement, FormData: dom.window.FormData,
  IS_REACT_ACT_ENVIRONMENT: true,
});
const { act, createElement } = await import("react");
const { createRoot } = await import("react-dom/client");
const { averagePace, sessionOverview } = await import(sourceUrl("../src/sessionStats.ts"));
const { default: SessionForm } = await import(sourceUrl("../src/components/SessionForm.tsx"));
const { default: SessionDetails } = await import(sourceUrl("../src/components/SessionDetails.tsx"));
const session = {
  id: 1, day: "2026-10-06", activity: "easy_run", status: "completed",
  duration_min: 45, actual_duration_min: 32, distance_km: 5.2,
  average_hr_bpm: 142, elevation_gain_m: 120, active_calories_kcal: 340,
  hr_zone_min: 2, hr_zone_max: 2, effort: 5, notes: "First line\nSecond line",
};

async function render(t, Component, props) {
  const host = document.createElement("div");
  document.body.append(host);
  const root = createRoot(host);
  t.after(async () => { await act(async () => root.unmount()); host.remove(); });
  await act(async () => root.render(createElement(Component, props)));
  return host;
}

async function change(input, value) {
  const prototype = input.tagName === "SELECT" ? window.HTMLSelectElement.prototype
    : input.tagName === "TEXTAREA" ? window.HTMLTextAreaElement.prototype : window.HTMLInputElement.prototype;
  await act(async () => {
    Object.getOwnPropertyDescriptor(prototype, "value").set.call(input, value);
    input.dispatchEvent(new window.Event(input.tagName === "SELECT" ? "change" : "input", { bubbles: true }));
  });
}

// Pace handles rounding across a minute boundary and never invents missing results.
test("pace derives from actual time and rejects missing or zero inputs", () => {
  assert.equal(averagePace(5.2, 32), "6:09 /km");
  assert.equal(averagePace(1, 5.999), "6:00 /km");
  for (const [distance, duration] of [[0, 30], [5, 0], [null, 30], [5, null], [-1, 30], [5, Infinity]]) {
    assert.equal(averagePace(distance, duration), null);
  }
  assert.equal(sessionOverview(session), "5.2 km · 32 min · 6:09 /km");
  assert.equal(sessionOverview({ ...session, status: "planned" }), "45 min planned · Target Z2");
});

// The status changes the task presented by the editor while keeping identity fields visible.
test("each status exposes only its relevant editable fields", async (t) => {
  for (const status of ["planned", "confirmed", "completed", "skipped"]) {
    const host = await render(t, SessionForm, {
      day: session.day, session: { ...session, status }, disabled: false, error: "",
      onSave: async () => {}, onCancel: () => {},
    });
    for (const name of ["day", "activity", "status"]) {
      assert.ok(host.querySelector(`[name="${name}"]`));
    }
    const planning = status === "planned" || status === "confirmed";
    assert.equal(Boolean(host.querySelector('[name="duration"]')), planning);
    assert.equal(Boolean(host.querySelector('select:not([name])')), planning);
    for (const name of ["actual_duration_min", "distance_km", "average_hr_bpm", "active_calories_kcal", "effort"]) {
      assert.equal(Boolean(host.querySelector(`[name="${name}"]`)), status === "completed");
    }
    assert.equal(Boolean(host.querySelector('[name="notes"]')), status !== "skipped");
    if (status === "completed") {
      const original = host.querySelector(".session-original-plan");
      assert.equal(original.open, false);
      assert.ok(original.textContent.includes("45 min"));
      assert.ok(original.textContent.includes("Target Z2"));
      assert.equal(original.querySelector("input, select, textarea"), null);
    }
    if (status === "skipped") {
      assert.equal(host.querySelectorAll("input, select, textarea").length, 3);
      assert.equal(host.querySelector(".session-original-plan"), null);
      assert.ok(!host.textContent.includes("Z2, comfortable"));
    }
  }
});

// Values typed in one mode must survive unmounting fields, saving skipped, and returning.
test("status changes retain target, result and notes drafts", async (t) => {
  let submitted;
  const host = await render(t, SessionForm, {
    day: session.day, session: { ...session, status: "planned" }, disabled: false, error: "",
    onSave: async (value) => { submitted = value; }, onCancel: () => {},
  });
  const field = (name) => host.querySelector(`[name="${name}"]`);
  await change(field("duration"), "50");
  await change(host.querySelector('select:not([name])'), "3-4");
  await change(field("notes"), "Draft notes\nSecond line");
  await change(field("status"), "confirmed");
  assert.equal(field("duration").value, "50");
  await change(field("status"), "completed");
  await change(field("actual_duration_min"), "42.5");
  await change(field("distance_km"), "7");
  await change(field("average_hr_bpm"), "150");
  await change(field("active_calories_kcal"), "400");
  await change(field("effort"), "6");
  await change(field("status"), "skipped");
  await act(async () => host.querySelector("form").dispatchEvent(new window.Event("submit", { bubbles: true, cancelable: true })));
  assert.equal(submitted.status, "skipped");
  assert.equal(submitted.duration_min, 50);
  assert.equal(submitted.actual_duration_min, 42.5);
  assert.equal(submitted.distance_km, 7);
  assert.equal(submitted.average_hr_bpm, 150);
  assert.equal(submitted.active_calories_kcal, 400);
  assert.equal(submitted.effort, 6);
  assert.equal(submitted.hr_zone_min, 3);
  assert.equal(submitted.hr_zone_max, 4);
  assert.equal(submitted.notes, "Draft notes\nSecond line");
  await change(field("status"), "planned");
  assert.equal(field("duration").value, "50");
  assert.equal(host.querySelector('select:not([name])').value, "3-4");
  await change(field("status"), "completed");
  assert.equal(field("actual_duration_min").value, "42.5");
  assert.equal(field("distance_km").value, "7");
  assert.equal(field("notes").value, "Draft notes\nSecond line");
});

// Picking an activity before logging completion must not save its planning presets.
test("direct completion and skipping omit untouched default targets", async (t) => {
  for (const status of ["completed", "skipped"]) {
    let submitted;
    const host = await render(t, SessionForm, {
      day: session.day, session: null, disabled: false, error: "",
      onSave: async (value) => { submitted = value; }, onCancel: () => {},
    });
    await change(host.querySelector('[name="activity"]'), "long_run");
    await change(host.querySelector('[name="status"]'), status);
    assert.equal(host.querySelector(".session-original-plan"), null);
    await act(async () => host.querySelector("form").dispatchEvent(new window.Event("submit", { bubbles: true, cancelable: true })));
    assert.equal(submitted.duration_min, null);
    assert.equal(submitted.hr_zone_min, null);
    assert.equal(submitted.hr_zone_max, null);
  }
});

// An intentionally entered plan remains available if the user completes it before saving.
test("newly edited targets survive completion without being required", async (t) => {
  let submitted;
  const host = await render(t, SessionForm, {
    day: session.day, session: null, disabled: false, error: "",
    onSave: async (value) => { submitted = value; }, onCancel: () => {},
  });
  await change(host.querySelector('[name="duration"]'), "40");
  await change(host.querySelector('[name="status"]'), "completed");
  assert.ok(host.querySelector(".session-original-plan").textContent.includes("40 min"));
  await act(async () => host.querySelector("form").dispatchEvent(new window.Event("submit", { bubbles: true, cancelable: true })));
  assert.equal(submitted.duration_min, 40);
  assert.equal(submitted.actual_duration_min, null);
});

// Each activity exposes its own metrics while keeping targets distinct from results.
test("event details show activity-specific results with units", async (t) => {
  for (const [activity, shown, hidden] of [
    ["easy_run", ["Average pace", "Average HR"], ["Elevation gain"]],
    ["cycle", ["Average HR", "Elevation gain"], ["Average pace"]],
    ["hike", ["Average pace", "Elevation gain"], ["Average HR"]],
    ["gym", ["Workout notes", "Actual duration"], ["Average pace", "Distance", "Average HR"]],
  ]) {
    const host = await render(t, SessionDetails, { session: { ...session, activity } });
    for (const label of shown) assert.ok(host.textContent.includes(label));
    for (const label of hidden) assert.ok(!host.textContent.includes(label));
    assert.ok(host.textContent.includes("45 min"));
    assert.ok(host.textContent.includes("32 min"));
    assert.ok(host.textContent.includes("340 kcal"));
    assert.equal(host.querySelector(".calendar-card-notes").textContent, session.notes);
  }
});

// Editing an existing workout preserves all stats, including those hidden for another activity.
test("editor preserves results and notes through activity changes", async (t) => {
  let submitted;
  const host = await render(t, SessionForm, {
    day: session.day, session, disabled: false, error: "",
    onSave: async (value) => { submitted = value; }, onCancel: () => {},
  });
  assert.ok(host.textContent.includes("Average pace: 6:09 /km"));
  await change(host.querySelector('[name="activity"]'), "gym");
  assert.equal(host.querySelector('[name="distance_km"]'), null);
  assert.equal(host.querySelector('[name="notes"]').rows, 5);
  await change(host.querySelector('[name="activity"]'), "easy_run");
  await change(host.querySelector('[name="distance_km"]'), "");
  await change(host.querySelector('[name="actual_duration_min"]'), "30.5");
  await act(async () => host.querySelector("form").dispatchEvent(new window.Event("submit", { bubbles: true, cancelable: true })));
  const { id, ...expected } = session;
  assert.deepEqual(submitted, { ...expected, actual_duration_min: 30.5, distance_km: null });
});

// A quick completion can be saved without collecting any optional workout statistics.
test("blank result fields submit null rather than zero", async (t) => {
  let submitted;
  const host = await render(t, SessionForm, {
    day: session.day, session: null, disabled: false, error: "",
    onSave: async (value) => { submitted = value; }, onCancel: () => {},
  });
  await change(host.querySelector('[name="status"]'), "completed");
  await act(async () => host.querySelector("form").dispatchEvent(new window.Event("submit", { bubbles: true, cancelable: true })));
  for (const name of ["distance_km", "actual_duration_min", "average_hr_bpm", "elevation_gain_m", "active_calories_kcal"]) {
    assert.equal(submitted[name], null);
  }
  assert.equal(submitted.status, "completed");
  assert.equal(submitted.duration_min, null);
  assert.equal(submitted.hr_zone_min, null);
  assert.equal(submitted.hr_zone_max, null);
});
