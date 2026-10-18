import assert from "node:assert/strict";
import test from "node:test";
import { JSDOM } from "jsdom";
import { sourceUrl } from "./loadSource.mjs";

const dom = new JSDOM("<!doctype html><body></body>", { url: "http://localhost" });
Object.assign(globalThis, {
  window: dom.window, document: dom.window.document,
  HTMLElement: dom.window.HTMLElement, IS_REACT_ACT_ENVIRONMENT: true,
});
const { act, createElement } = await import("react");
const { createRoot } = await import("react-dom/client");
const { default: WeeklyCalendar } = await import(sourceUrl("../src/components/WeeklyCalendar.tsx"));
const { deleteSession } = await import(sourceUrl("../src/api/client.ts"));
const saved = {
  id: 7, day: "2026-10-06", activity: "gym", status: "planned",
  duration_min: null, effort: null, hr_zone_min: null, hr_zone_max: null, notes: "",
  actual_duration_min: null, distance_km: null, average_hr_bpm: null,
  elevation_gain_m: null, active_calories_kcal: null,
};

async function renderCalendar(t, props) {
  document.body.replaceChildren();
  const host = document.createElement("div");
  document.body.append(host);
  const root = createRoot(host);
  t.after(async () => { await act(async () => root.unmount()); });
  await act(async () => root.render(createElement(WeeklyCalendar, props)));
  return host;
}

// Every persisted status requires approval; cancelling must never call deletion.
test("saved activity deletion requires confirmation and identifies the entry", async (t) => {
  for (const status of ["planned", "confirmed", "completed", "skipped"]) {
    const session = { ...saved, status };
    const deleted = [];
    let approved = false;
    t.mock.method(window, "confirm", (message) => {
      assert.match(message, /gym on 2026-10-06/);
      assert.ok(message.includes(status));
      return approved;
    });
    const host = await renderCalendar(t, {
      weekStart: "2026-10-05", sessions: [session], onDelete: (item) => deleted.push(item),
    });
    const button = host.querySelector("button");
    assert.equal(button.getAttribute("aria-label"), "Delete 2026-10-06 gym");
    await act(async () => button.click());
    assert.deepEqual(deleted, []);
    approved = true;
    await act(async () => button.click());
    assert.deepEqual(deleted, [session]);
  }
});

// Suggestions cannot be deleted as saved records, even if their status is planned.
test("only saved activities have delete controls and busy controls are disabled", async (t) => {
  const host = await renderCalendar(t, {
    weekStart: "2026-10-05", sessions: [saved, { ...saved, id: null }],
    proposals: [{ ...saved, id: null }], onDelete: () => {}, disabled: true,
  });
  const controls = host.querySelectorAll("button");
  assert.equal(controls.length, 1);
  assert.equal(controls[0].disabled, true);
});

// A successful DELETE has an empty body and must not be decoded as JSON.
test("delete client targets the saved identifier and accepts an empty 204", async (t) => {
  t.mock.method(globalThis, "fetch", async (url, options) => {
    assert.equal(url, "/api/sessions/7");
    assert.equal(options.method, "DELETE");
    assert.equal(options.body, undefined);
    return new Response(null, { status: 204 });
  });
  assert.equal(await deleteSession(7), undefined);
});

// Server errors stay visible to the caller instead of being reported as success.
test("delete client propagates server failures", async (t) => {
  t.mock.method(globalThis, "fetch", async () => new Response(
    JSON.stringify({ detail: "Session 7 does not exist" }), { status: 404 },
  ));
  await assert.rejects(deleteSession(7), /Session 7 does not exist/);
});

// Network failures reject too, allowing the app to retain the saved activity.
test("delete client propagates network failures", async (t) => {
  t.mock.method(globalThis, "fetch", async () => { throw new Error("Offline"); });
  await assert.rejects(deleteSession(7), /Offline/);
});
