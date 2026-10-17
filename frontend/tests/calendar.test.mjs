import assert from "node:assert/strict";
import test from "node:test";
import { JSDOM } from "jsdom";
import { sourceUrl } from "./loadSource.mjs";

// Install the DOM before loading React DOM so its event system detects a browser.
const dom = new JSDOM("<!doctype html><body></body>", { url: "http://localhost" });
Object.assign(globalThis, {
  window: dom.window, document: dom.window.document,
  HTMLElement: dom.window.HTMLElement, FormData: dom.window.FormData,
  IS_REACT_ACT_ENVIRONMENT: true,
});
const { act, createElement } = await import("react");
const { createRoot } = await import("react-dom/client");
const { default: App } = await import(sourceUrl("../src/App.tsx"));

function dateString(date) {
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;
}
const monday = new Date();
monday.setDate(monday.getDate() - (monday.getDay() + 6) % 7);
const firstDay = dateString(monday);
const saved = {
  id: 7, day: firstDay, activity: "gym", status: "completed", duration_min: null,
  effort: 8, hr_zone_min: null, hr_zone_max: null, notes: "Original workout",
};

async function setup(t, initial = [saved]) {
  document.body.replaceChildren();
  const host = document.createElement("div");
  document.body.append(host);
  const root = createRoot(host);
  const state = { sessions: structuredClone(initial), requests: [], fail: "", pause: null };
  t.mock.method(globalThis, "fetch", async (path, options) => {
    const url = new URL(path, "http://localhost");
    const method = options.method;
    if (method === "GET") {
      return Response.json(state.sessions.filter((item) =>
        item.day >= url.searchParams.get("start") && item.day <= url.searchParams.get("end")));
    }
    const body = options.body ? JSON.parse(options.body) : undefined;
    state.requests.push({ method, path: url.pathname, body });
    if (state.pause) await state.pause;
    if (state.fail === method) return Response.json({ detail: "Cannot save right now" }, { status: 503 });
    if (url.pathname === "/api/proposals") {
      return Response.json([{ ...saved, id: null, status: "planned", notes: "Suggested workout" }]);
    }
    if (method === "POST") {
      const session = { ...body, id: 20 };
      state.sessions.push(session);
      return Response.json(session, { status: 201 });
    }
    const id = Number(url.pathname.split("/")[3]);
    if (method === "PATCH") {
      state.sessions = state.sessions.map((item) => item.id === id ? { ...item, status: body.status } : item);
      return Response.json(state.sessions.find((item) => item.id === id));
    }
    if (method === "PUT") {
      const session = { ...body, id };
      state.sessions = state.sessions.map((item) => item.id === id ? session : item);
      return Response.json(session);
    }
    state.sessions = state.sessions.filter((item) => item.id !== id);
    return new Response(null, { status: 204 });
  });
  t.after(async () => { await act(async () => root.unmount()); });
  await act(async () => root.render(createElement(App)));
  return state;
}

function button(text) {
  const found = [...document.querySelectorAll("button")].find((item) => item.textContent === text);
  assert.ok(found, `Missing button ${text}`);
  return found;
}
async function click(element) {
  await act(async () => element.click());
}
async function change(element, value) {
  assert.ok(element);
  // Use the native setter to emulate user input without updating React's tracker.
  const setter = Object.getOwnPropertyDescriptor(Object.getPrototypeOf(element), "value").set;
  await act(async () => {
    setter.call(element, value);
    element.dispatchEvent(new window.Event(element.tagName === "SELECT" ? "change" : "input", { bubbles: true }));
  });
}
function form() { return document.querySelector(".calendar-editor"); }
async function submit() {
  await act(async () => form().dispatchEvent(new window.Event("submit", { bubbles: true, cancelable: true })));
}

// Add on a later calendar week and discard the preview only after persistence.
test("add training inline on the selected day across a multiweek horizon", async (t) => {
  const state = await setup(t, []);
  const horizon = [...document.querySelectorAll("select")][0];
  await change(horizon, "2");
  await click(button("Generate suggestions"));
  assert.match(document.body.textContent, /Suggested workout/);
  const add = document.querySelectorAll('button[aria-label^="Add training on"]')[10];
  const day = add.getAttribute("aria-label").slice("Add training on ".length);
  await click(add);
  assert.equal(form().closest(".calendar-day").querySelector("time").dateTime, day);
  assert.equal(form().elements.day.value, day);
  await change(form().elements.activity, "gym");
  await change(form().elements.duration, "45");
  await change(form().elements.effort, "6");
  await change(form().elements.notes, "Added inline");
  await submit();
  const request = state.requests.at(-1);
  assert.equal(request.method, "POST");
  assert.deepEqual(request.body, {
    day, activity: "gym", status: "planned", duration_min: 45, effort: 6,
    hr_zone_min: null, hr_zone_max: null, notes: "Added inline",
  });
  assert.equal(form(), null);
  assert.match(document.body.textContent, /Added inline/);
  assert.doesNotMatch(document.body.textContent, /Suggested workout/);
  assert.equal(document.querySelector('[aria-labelledby="log-heading"]'), null);
});

// Editing must prefill stored values rather than replacing null metrics with presets.
test("edit preserves identity, supports moving dates and clearing fields", async (t) => {
  const state = await setup(t);
  await click(button("Edit"));
  assert.equal(form().elements.duration.value, "");
  assert.equal(form().elements.status.value, "completed");
  assert.equal(form().elements.effort.value, "8");
  const next = new Date(`${firstDay}T12:00:00`);
  next.setDate(next.getDate() + 1);
  await change(form().elements.day, dateString(next));
  await change(form().elements.status, "skipped");
  await change(form().elements.effort, "");
  await change(form().elements.notes, "Moved inline");
  await submit();
  assert.equal(state.requests[0].method, "PUT");
  assert.equal(state.requests[0].path, "/api/sessions/7");
  assert.equal(state.sessions.length, 1);
  assert.equal(state.sessions[0].id, 7);
  assert.equal(state.sessions[0].effort, null);
  assert.equal(state.sessions[0].duration_min, null);
  assert.equal(state.sessions[0].status, "skipped");
  const card = document.querySelector(".calendar-card");
  assert.equal(card.closest(".calendar-day").querySelector("time").dateTime, dateString(next));
  assert.match(card.textContent, /Moved inline/);
});

// Cancel never persists a draft or removes a previously generated proposal preview.
test("cancel discards inline edits without changing saved training or proposals", async (t) => {
  const state = await setup(t);
  await click(button("Generate suggestions"));
  const before = state.requests.length;
  await click(button("Edit"));
  await change(form().elements.notes, "Discard me");
  await click(button("Cancel"));
  assert.equal(state.requests.length, before);
  assert.equal(state.sessions[0].notes, saved.notes);
  assert.match(document.body.textContent, /Suggested workout/);
  await click(button("Edit"));
  assert.equal(form().elements.notes.value, saved.notes);
});

// A rejected update retains the draft and preview; retry saves and clears both.
test("failed edits retain drafts and proposals for retry", async (t) => {
  const state = await setup(t);
  await click(button("Generate suggestions"));
  await click(button("Edit"));
  await change(form().elements.notes, "Retry this draft");
  state.fail = "PUT";
  await submit();
  assert.equal(form().elements.notes.value, "Retry this draft");
  assert.match(form().textContent, /Cannot save right now/);
  assert.equal(state.sessions[0].notes, saved.notes);
  assert.match(document.body.textContent, /Suggested workout/);
  state.fail = "";
  await submit();
  assert.equal(form(), null);
  assert.match(document.body.textContent, /Retry this draft/);
  assert.doesNotMatch(document.body.textContent, /Suggested workout/);
});

// Failed creation also retains values, allowing a retry without re-entering fields.
test("failed additions keep the inline draft", async (t) => {
  const state = await setup(t, []);
  await click(document.querySelector('button[aria-label^="Add training on"]'));
  await change(form().elements.notes, "New draft");
  state.fail = "POST";
  await submit();
  assert.equal(form().elements.notes.value, "New draft");
  assert.equal(state.sessions.length, 0);
  state.fail = "";
  await submit();
  assert.equal(state.sessions[0].notes, "New draft");
});

// Exercise the full delete workflow as well as its independent component/client tests.
test("calendar deletion preserves state on cancellation and failure, then clears previews", async (t) => {
  const state = await setup(t);
  await click(button("Generate suggestions"));
  const confirm = t.mock.method(window, "confirm", () => false);
  const before = state.requests.length;
  await click(button("Delete"));
  assert.equal(state.requests.length, before);
  confirm.mock.mockImplementation(() => true);
  state.fail = "DELETE";
  await click(button("Delete"));
  assert.match(document.body.textContent, /Original workout/);
  assert.match(document.body.textContent, /Suggested workout/);
  state.fail = "";
  await click(button("Delete"));
  assert.equal(state.sessions.length, 0);
  assert.doesNotMatch(document.body.textContent, /Original workout|Suggested workout/);
});


// Stored targets survive opening the editor; a type change applies editable presets.
test("edit preserves HR targets and supports changing activity presets", async (t) => {
  const state = await setup(t, [{
    ...saved, activity: "interval_run", duration_min: 46, hr_zone_min: 4, hr_zone_max: 5,
  }]);
  await click(button("Edit"));
  const zone = form().querySelector("select:not([name])");
  assert.equal(zone.value, "4-5");
  assert.equal(form().elements.duration.value, "46");
  await change(form().elements.activity, "easy_run");
  assert.equal(zone.value, "2-2");
  assert.equal(form().elements.duration.value, "30");
  await change(form().elements.duration, "35");
  await change(zone, "2-3");
  await submit();
  assert.equal(state.sessions[0].activity, "easy_run");
  assert.equal(state.sessions[0].duration_min, 35);
  assert.equal(state.sessions[0].hr_zone_min, 2);
  assert.equal(state.sessions[0].hr_zone_max, 3);
});

// Prevent conflicting mutations and navigation while a draft is being persisted.
test("saving disables editor controls until the request completes", async (t) => {
  const state = await setup(t);
  await click(button("Edit"));
  let release;
  state.pause = new Promise((resolve) => { release = resolve; });
  await submit();
  assert.equal(form().querySelector("fieldset").disabled, true);
  assert.equal(button("Cancel").matches(":disabled"), true);
  assert.equal(button("Delete").disabled, true);
  assert.equal(document.querySelector('input[type="date"]').disabled, true);
  await act(async () => release());
  assert.equal(form(), null);
  assert.equal(state.requests.filter((item) => item.method === "PUT").length, 1);
});


// Confirmation commits to upcoming training without recording it as completed.
test("confirm planned training directly on its calendar card", async (t) => {
  const planned = { ...saved, status: "planned" };
  const state = await setup(t, [planned]);
  await click(button("Generate suggestions"));
  assert.equal(document.querySelectorAll(".calendar-status-control").length, 1);
  await click(button("Confirm"));
  assert.deepEqual(state.requests.at(-1), {
    method: "PATCH", path: "/api/sessions/7/status", body: { status: "confirmed" },
  });
  assert.deepEqual(state.sessions, [{ ...planned, status: "confirmed" }]);
  assert.equal(document.querySelector(".calendar-status-control select").value, "confirmed");
  assert.ok(document.querySelector(".calendar-card--confirmed"));
  assert.equal(document.querySelector('button[aria-label^="Confirm "]'), null);
  assert.equal(form(), null);
  assert.doesNotMatch(document.body.textContent, /Suggested workout/);
});

// All supported transitions are available without opening or saving the detail form.
test("change status directly between confirmed, completed, skipped and planned", async (t) => {
  const state = await setup(t);
  for (const status of ["confirmed", "completed", "skipped", "planned"]) {
    await change(document.querySelector(".calendar-status-control select"), status);
    assert.deepEqual(state.sessions, [{ ...saved, status }]);
    assert.equal(form(), null);
    assert.equal(document.querySelector(".calendar-status-control select").value, status);
  }
  assert.ok(button("Confirm"));
  await click(button("Edit"));
  assert.equal(form().elements.status.value, "planned");
  assert.ok([...form().elements.status.options].some((option) => option.value === "confirmed"));
});

// Rejecting a status mutation must not change the card or discard existing previews.
test("failed confirmation and status changes preserve the card and preview", async (t) => {
  const state = await setup(t, [{ ...saved, status: "planned" }]);
  await click(button("Generate suggestions"));
  state.fail = "PATCH";
  await click(button("Confirm"));
  assert.equal(state.sessions[0].status, "planned");
  assert.match(document.body.textContent, /Cannot save right now/);
  assert.match(document.body.textContent, /Suggested workout/);
  await change(document.querySelector(".calendar-status-control select"), "completed");
  assert.equal(document.querySelector(".calendar-status-control select").value, "planned");
  state.fail = "";
  await click(button("Confirm"));
  assert.equal(state.sessions[0].status, "confirmed");
  assert.doesNotMatch(document.body.textContent, /Suggested workout/);
});

// Block conflicting changes during a status request and while an editor has a draft.
test("status controls are disabled during saves and inline editing", async (t) => {
  const state = await setup(t, [{ ...saved, status: "planned" }]);
  await click(button("Edit"));
  assert.equal(document.querySelector(".calendar-status-control select").disabled, true);
  assert.equal(button("Confirm").disabled, true);
  await click(button("Cancel"));
  let release;
  state.pause = new Promise((resolve) => { release = resolve; });
  await click(button("Confirm"));
  assert.equal(document.querySelector(".calendar-status-control select").disabled, true);
  assert.equal(button("Confirm").disabled, true);
  assert.equal(button("Delete").disabled, true);
  await act(async () => release());
  assert.equal(document.querySelector(".calendar-status-control select").disabled, false);
  assert.equal(state.requests.filter((item) => item.method === "PATCH").length, 1);
});
