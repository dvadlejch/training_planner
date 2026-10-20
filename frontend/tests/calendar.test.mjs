import assert from "node:assert/strict";
import test from "node:test";
import { JSDOM } from "jsdom";
import { sourceUrl } from "./loadSource.mjs";

// Install the DOM before loading React DOM so its event system detects a browser.
const dom = new JSDOM("<!doctype html><body></body>", { url: "http://localhost" });
Object.assign(globalThis, {
  window: dom.window, document: dom.window.document,
  Node: dom.window.Node, HTMLElement: dom.window.HTMLElement, FormData: dom.window.FormData,
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
  actual_duration_min: null, distance_km: null, average_hr_bpm: null,
  elevation_gain_m: null, active_calories_kcal: null,
};

async function setup(t, initial = [saved]) {
  t.mock.method(window, "confirm", () => true);
  document.body.replaceChildren();
  const host = document.createElement("div");
  document.body.append(host);
  const root = createRoot(host);
  const state = { sessions: structuredClone(initial), requests: [], reads: [], fail: "", pause: null, readPause: null };
  t.mock.method(globalThis, "fetch", async (path, options) => {
    const url = new URL(path, "http://localhost");
    const method = options.method;
    if (method === "GET") {
      state.reads.push({ start: url.searchParams.get("start"), end: url.searchParams.get("end") });
      if (state.readPause) await state.readPause;
      return Response.json(state.sessions.filter((item) =>
        item.day >= url.searchParams.get("start") && item.day <= url.searchParams.get("end")));
    }
    const body = options.body ? JSON.parse(options.body) : undefined;
    state.requests.push({ method, path: url.pathname, body });
    if (state.pause) await state.pause;
    if (state.fail === method) return Response.json({ detail: "Cannot save right now" }, { status: 503 });
    if (url.pathname === "/api/proposals") {
      const pinned = (body.moves ?? []).map((move) => ({ ...move.session, id: null }));
      const generated = { ...saved, id: null, status: "planned", notes: "Suggested workout",
        muscle_groups: ["chest", ...(body.gym_split?.chest ?? ["shoulders", "abs"])],
      };
      return Response.json(body.moves?.length ? pinned : [generated].filter((item) =>
        !(body.excluded ?? []).some((key) => key.day === item.day && key.activity === item.activity) && !body.blocked.includes(item.day)));
    }
    if (url.pathname === "/api/proposals/accept") {
      const accepted = body.proposals.map((item, index) => ({
        ...item, status: body.confirm ? "confirmed" : item.status,
        id: 20 + state.sessions.length + index,
      }));
      state.sessions.push(...accepted);
      return Response.json(accepted, { status: 201 });
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
  // Open workout details before using controls that are hidden in the month view.
  const details = element.closest("details:not([open])");
  if (details && element.tagName !== "SUMMARY") {
    await act(async () => details.querySelector("summary").click());
  }
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

// Save gym muscle targets on a later calendar week and show them on the saved card.
test("add training inline on the selected day across a multiweek horizon", async (t) => {
  const state = await setup(t, []);
  const horizon = document.querySelector(".planning-controls select");
  await change(horizon, "2");
  await click(button("Generate suggestions"));
  assert.match(document.body.textContent, /Suggested workout/);
  const add = document.querySelectorAll('button[aria-label^="Add training on"]')[10];
  const day = add.getAttribute("aria-label").slice("Add training on ".length);
  await click(add);
  assert.equal(document.querySelectorAll(".monthly-calendar .calendar-day").length % 7, 0);
  assert.equal(form().elements.day.value, day);
  await change(form().elements.activity, "gym");
  await change(form().elements.duration, "45");
  await change(form().elements.notes, "Added inline");
  await click(form().querySelector('[name="muscle_groups"][value="chest"]'));
  await click(form().querySelector('[name="muscle_groups"][value="abs"]'));
  await submit();
  const request = state.requests.at(-1);
  assert.equal(request.method, "POST");
  assert.deepEqual(request.body, {
    day, activity: "gym", status: "planned", duration_min: 45, effort: null,
    hr_zone_min: null, hr_zone_max: null, notes: "Added inline", muscle_groups: ["chest", "abs"],
    actual_duration_min: null, distance_km: null, average_hr_bpm: null,
    elevation_gain_m: null, active_calories_kcal: null,
  });
  assert.equal(form(), null);
  assert.match(document.body.textContent, /Added inline/);
  assert.match(document.querySelector(".monthly-calendar").textContent, /Chest, Abs/);
  assert.doesNotMatch(document.body.textContent, /Suggested workout/);
  assert.equal(document.querySelector('[aria-labelledby="log-heading"]'), null);
});

// Editing completed work shows results; switching to skipped preserves the edited values.
test("edit preserves identity, supports moving dates and clearing fields", async (t) => {
  const state = await setup(t);
  await click(button("Edit"));
  assert.equal(form().elements.duration, undefined);
  assert.equal(form().elements.status.value, "completed");
  assert.equal(form().elements.effort.value, "8");
  const next = new Date(`${firstDay}T12:00:00`);
  next.setDate(next.getDate() + 1);
  await change(form().elements.day, dateString(next));
  await change(form().elements.effort, "");
  await change(form().elements.notes, "Moved inline");
  await change(form().elements.status, "skipped");
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

// Logging a completed workout directly must save results and leave planned targets unknown.
test("add completed training saves results without default targets", async (t) => {
  const state = await setup(t, []);
  await click(document.querySelector('button[aria-label^="Add training on"]'));
  await change(form().elements.status, "completed");
  assert.equal(form().elements.duration, undefined);
  assert.equal(form().querySelector(".session-original-plan"), null);
  await change(form().elements.actual_duration_min, "24");
  await change(form().elements.distance_km, "4");
  await change(form().elements.average_hr_bpm, "140");
  await change(form().elements.notes, "Completed directly");
  await submit();
  assert.equal(state.sessions[0].duration_min, null);
  assert.equal(state.sessions[0].hr_zone_min, null);
  assert.equal(state.sessions[0].actual_duration_min, 24);
  assert.equal(state.sessions[0].distance_km, 4);
  assert.equal(state.sessions[0].average_hr_bpm, 140);
  assert.match(document.querySelector(".calendar-card-overview").textContent, /4 km.*24 min.*6:00/);
  await click(button("Edit"));
  assert.equal(form().elements.actual_duration_min.value, "24");
  assert.equal(form().elements.distance_km.value, "4");
  assert.equal(form().querySelector(".session-original-plan"), null);
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
  await change(form().elements.status, "planned");
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
  assert.equal(document.querySelector('.planning-controls select').disabled, true);
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

// Every month row remains present regardless of the independent proposal horizon.
test("month is the primary view and target changes do not truncate it", async (t) => {
  const state = await setup(t, []);
  const calendar = document.querySelector(".monthly-calendar");
  const dates = [...calendar.querySelectorAll("time")].map((item) => item.dateTime);
  const month = dateString(new Date()).slice(0, 7);
  const days = new Date(new Date().getFullYear(), new Date().getMonth() + 1, 0).getDate();
  assert.equal(dates.filter((day) => day.startsWith(month)).length, days);
  assert.equal(dates.length % 7, 0);
  assert.deepEqual(state.reads.at(-1), { start: dates[0], end: dates.at(-1) });
  assert.ok(document.querySelector("main > .planner-layout > section") === calendar.closest("section"));
  for (const horizon of ["4", "1"]) {
    await change(document.querySelector(".planning-controls select"), horizon);
    assert.deepEqual([...calendar.querySelectorAll("time")].map((item) => item.dateTime), dates);
  }
  assert.equal(document.querySelector('.planning-controls input[type="date"]'), null);
  assert.equal(calendar.querySelectorAll("time").length, dates.length);
  assert.equal(button("Generate suggestions").disabled, false);
  await click(button("Generate suggestions"));
  assert.equal(state.requests.at(-1).body.week_start, dateString(new Date()));
});

// Each new generation reads today's date, including after midnight and month rollover.
test("new suggestions start today regardless of the displayed month", async (t) => {
  const RealDate = Date;
  let currentTime = new RealDate(2026, 2, 31, 12).getTime();
  t.mock.method(globalThis, "Date", class extends RealDate {
    constructor(...args) { super(...(args.length ? args : [currentTime])); }
    static now() { return currentTime; }
  });
  const state = await setup(t, []);
  assert.equal(document.querySelector('.planning-controls input[type="date"]'), null);
  await click(document.querySelector('[aria-label="Next month"]'));
  await click(button("Generate suggestions"));
  assert.equal(state.requests.at(-1).body.week_start, "2026-03-31");
  assert.equal(state.requests.at(-1).body.weeks, 4);
  assert.equal(document.querySelector(".monthly-calendar").getAttribute("aria-label"), "Month 2026-03");
  currentTime = new RealDate(2026, 3, 1, 12).getTime();
  await change(document.querySelector(".planning-controls select"), "4");
  await click(button("Generate suggestions"));
  assert.equal(state.requests.at(-1).body.week_start, "2026-04-01");
  assert.equal(state.requests.at(-1).body.weeks, 4);
  assert.equal(document.querySelector(".monthly-calendar").getAttribute("aria-label"), "Month 2026-04");
});

// The full grid is rendered before its sessions resolve; editing does not span cells.
test("navigation retains the month grid during loading and editing", async (t) => {
  const state = await setup(t, []);
  let release;
  state.readPause = new Promise((resolve) => { release = resolve; });
  await click(document.querySelector('[aria-label="Next month"]'));
  const calendar = document.querySelector(".monthly-calendar");
  const count = calendar.children.length;
  assert.ok(count >= 28 && count <= 42);
  assert.equal(document.querySelector(".month-scroll").getAttribute("aria-busy"), "true");
  assert.equal(calendar.querySelector("button").disabled, true);
  await act(async () => release());
  await click(calendar.querySelector("button"));
  assert.ok(form());
  assert.equal(form().closest(".calendar-day"), null);
  assert.equal(calendar.children.length, count);
  assert.equal(document.querySelector('[aria-label="Next month"]').disabled, true);
  await click(button("Cancel"));
  await click(button("Today"));
  assert.equal(calendar.getAttribute("aria-label"), `Month ${dateString(new Date()).slice(0, 7)}`);
});

// Month navigation preserves unsaved drafts and their direct confirmation action.
test("suggestions can be confirmed after browsing into another month and back", async (t) => {
  await setup(t, []);
  await click(button("Generate suggestions"));
  await click(document.querySelector(".calendar-card--proposal summary"));
  assert.ok(document.querySelector('button[aria-label^="Confirm suggestion "]'));
  await click(document.querySelector('[aria-label="Next month"]'));
  assert.ok(button("Dismiss all"));
  await click(document.querySelector('[aria-label="Previous month"]'));
  await click(document.querySelector('button[aria-label^="Confirm suggestion "]'));
  assert.equal(document.querySelector(".calendar-card--proposal"), null);
  assert.ok(document.querySelector(".calendar-card--confirmed"));
});

// Saving a moved workout navigates to its destination without losing its identity.
test("moving a session across months displays its destination month", async (t) => {
  const state = await setup(t);
  await click(button("Edit"));
  await change(form().elements.day, "2027-02-28");
  await submit();
  assert.equal(state.sessions[0].id, saved.id);
  assert.equal(document.querySelector(".monthly-calendar").getAttribute("aria-label"), "Month 2027-02");
  assert.equal(document.querySelector(".calendar-card").closest(".calendar-day").querySelector("time").dateTime, "2027-02-28");
});


function dayCell(day) {
  return document.querySelector(`time[datetime="${day}"]`).closest(".calendar-day");
}
function availability(day) {
  return document.querySelector(`input[aria-label="Unavailable for suggestions on ${day}"]`);
}

// Calendar availability excludes suggestions without changing saved training.
test("toggle unavailable days in the calendar and regenerate suggestions", async (t) => {
  const state = await setup(t);
  assert.equal(document.querySelector('.planning-panel input[aria-label^="Unavailable for suggestions"]'), null);
  await click(button("Generate suggestions"));
  assert.ok(document.querySelector(".calendar-card--proposal"));
  assert.ok(availability(firstDay).closest(".calendar-day"));
  await click(availability(firstDay));
  assert.equal(availability(firstDay).checked, true);
  assert.equal(document.querySelector(".calendar-card--proposal"), null);
  assert.deepEqual(state.sessions, [saved]);
  await click(button("Generate suggestions"));
  assert.deepEqual(state.requests.at(-1).body.blocked, [firstDay]);
  assert.equal(document.querySelector(".calendar-card--proposal"), null);
  assert.match(document.body.textContent, /No eligible dates/);
  await click(availability(firstDay));
  assert.equal(availability(firstDay).checked, false);
  await click(button("Generate suggestions"));
  assert.deepEqual(state.requests.at(-1).body.blocked, []);
  assert.ok(document.querySelector(".calendar-card--proposal"));
  assert.deepEqual(state.sessions, [saved]);
});

// Availability follows calendar dates across navigation and planning-window changes.
test("availability survives browsing months and changing training targets", async (t) => {
  const state = await setup(t, []);
  const nextDate = new Date();
  nextDate.setDate(15);
  nextDate.setMonth(nextDate.getMonth() + 1);
  const otherDay = dateString(nextDate);
  await click(availability(firstDay));
  await click(document.querySelector('[aria-label="Next month"]'));
  await click(availability(otherDay));
  await click(document.querySelector('[aria-label="Previous month"]'));
  assert.equal(availability(firstDay).checked, true);
  const horizon = document.querySelector(".planning-controls select");
  await change(horizon, "4");
  await change(horizon, "1");
  await click(document.querySelector('[aria-label="Next month"]'));
  assert.equal(availability(otherDay).checked, true);
  await click(button("Generate suggestions"));
  assert.deepEqual(state.requests.at(-1).body.blocked, [firstDay, otherDay]);
  await click(button("Dismiss all"));
  await click(document.querySelector('[aria-label="Next month"]'));
  await click(availability(otherDay));
  await click(button("Generate suggestions"));
  assert.deepEqual(state.requests.at(-1).body.blocked, [firstDay]);
});

// In-flight work and editors lock availability to keep the planning context stable.
test("availability is disabled while editing and generating suggestions", async (t) => {
  const state = await setup(t);
  await click(button("Edit"));
  assert.equal(availability(firstDay).disabled, true);
  await click(availability(firstDay));
  assert.equal(availability(firstDay).checked, false);
  await click(button("Cancel"));
  assert.equal(availability(firstDay).disabled, false);
  let release;
  state.pause = new Promise((resolve) => { release = resolve; });
  await click(button("Generate suggestions"));
  assert.equal(availability(firstDay).disabled, true);
  await click(availability(firstDay));
  assert.equal(availability(firstDay).checked, false);
  await act(async () => { release(); });
  assert.equal(availability(firstDay).disabled, false);
});

function moveHandle() { return document.querySelector(".calendar-drag-handle"); }
function transfer() {
  return { effectAllowed: "", dropEffect: "", setData() {}, setDragImage() {} };
}
async function dragEvent(element, type, dataTransfer, relatedTarget = null) {
  const event = new window.Event(type, { bubbles: true, cancelable: true });
  Object.defineProperties(event, {
    dataTransfer: { value: dataTransfer }, relatedTarget: { value: relatedTarget },
  });
  await act(async () => element.dispatchEvent(event));
  return event;
}
async function dropOn(day, data = transfer()) {
  await dragEvent(moveHandle(), "dragstart", data);
  await dragEvent(dayCell(day), "dragover", data);
  await dragEvent(dayCell(day), "drop", data);
}

// Moving onto an occupied date preserves both workouts and saves only the new day.
test("drag a collapsed saved workout onto an occupied date without reloading", async (t) => {
  const next = new Date(`${firstDay}T12:00:00`);
  next.setDate(next.getDate() + 1);
  const target = dateString(next);
  const other = { ...saved, id: 8, day: target, notes: "Other workout" };
  const state = await setup(t, [saved, other]);
  await click(button("Generate suggestions"));
  const reads = state.reads.length;
  const month = document.querySelector(".monthly-calendar").getAttribute("aria-label");
  const handle = moveHandle();
  assert.equal(handle.closest("article").querySelector("details").open, false);
  const data = transfer();
  await dragEvent(handle, "dragstart", data);
  assert.equal(data.effectAllowed, "move");
  await dragEvent(dayCell(target).querySelector("summary"), "dragover", data);
  assert.ok(dayCell(target).classList.contains("calendar-day--drop-target"));
  assert.equal(data.dropEffect, "move");
  await dragEvent(dayCell(target), "drop", data);
  const { id, ...input } = saved;
  assert.deepEqual(state.requests.at(-1), {
    method: "PUT", path: `/api/sessions/${id}`, body: { ...input, day: target },
  });
  assert.deepEqual(state.sessions, [{ ...saved, day: target }, other]);
  assert.equal(dayCell(target).querySelectorAll(".calendar-card").length, 2);
  assert.equal(dayCell(firstDay).querySelectorAll(".calendar-card:not(.calendar-card--proposal)").length, 0);
  assert.equal(document.querySelector(".calendar-day--drop-target"), null);
  assert.ok(document.querySelector(".calendar-card--proposal"));
  assert.ok(document.querySelector("dialog[open]"));
  assert.equal(state.requests.filter((item) => item.path === "/api/proposals").length, 1);
  await click(button("Keep current suggestions"));
  assert.ok(document.querySelector(".calendar-card--proposal"));
  assert.equal(document.querySelector(".monthly-calendar").getAttribute("aria-label"), month);
  assert.equal(state.reads.length, reads);
});

// Padding dates are real destinations, while dropping must retain the displayed month.
test("drag into a shaded adjacent-month date keeps the month stable", async (t) => {
  const workout = { ...saved, day: "2026-10-05" };
  const state = await setup(t, [workout]);
  assert.ok(dayCell("2026-09-28").classList.contains("calendar-day--outside"));
  await dropOn("2026-09-28");
  assert.deepEqual(state.sessions, [{ ...workout, day: "2026-09-28" }]);
  assert.equal(document.querySelector(".monthly-calendar").getAttribute("aria-label"), "Month 2026-10");
  assert.ok(dayCell("2026-09-28").querySelector(".calendar-card"));
});

// A rejected move leaves the saved card and suggestion preview intact for retry.
test("failed drag save preserves the original position and suggestions", async (t) => {
  const state = await setup(t);
  await click(button("Generate suggestions"));
  const target = [...document.querySelectorAll("time")].find((item) => item.dateTime !== firstDay).dateTime;
  state.fail = "PUT";
  await dropOn(target);
  assert.deepEqual(state.sessions, [saved]);
  assert.ok(dayCell(firstDay).querySelector(".calendar-drag-handle"));
  assert.ok(document.querySelector(".calendar-card--proposal"));
  assert.match(document.querySelector('[role="alert"]').textContent, /Cannot save right now/);
  state.fail = "";
  await dropOn(target);
  assert.equal(state.sessions[0].day, target);
});

// External drags, same-day drops and cancelled drags must never persist a move.
test("ignore unrelated drops and cancel drag highlights without saving", async (t) => {
  const state = await setup(t);
  const target = [...document.querySelectorAll("time")].find((item) => item.dateTime !== firstDay).dateTime;
  const data = transfer();
  assert.equal((await dragEvent(dayCell(target), "dragover", data)).defaultPrevented, false);
  await dragEvent(dayCell(target), "drop", data);
  await dropOn(firstDay, data);
  await dragEvent(moveHandle(), "dragstart", data);
  await dragEvent(dayCell(target), "dragover", data);
  await dragEvent(dayCell(target), "dragleave", data, dayCell(target).querySelector("time"));
  assert.ok(document.querySelector(".calendar-day--drop-target"));
  await dragEvent(dayCell(target), "dragleave", data);
  assert.equal(document.querySelector(".calendar-day--drop-target"), null);
  await dragEvent(dayCell(target), "dragover", data);
  await dragEvent(moveHandle(), "dragend", data);
  assert.equal(document.querySelector(".calendar-day--drop-target"), null);
  await dragEvent(dayCell(target), "drop", data);
  assert.deepEqual(state.requests, []);
});

// An active editor or save prevents drag mutations; clicking the handle offers date editing.
test("move handles support editing and block dragging during conflicting work", async (t) => {
  const state = await setup(t);
  await click(button("Generate suggestions"));
  assert.ok(document.querySelector(".calendar-card--proposal .calendar-drag-handle"));
  await click(moveHandle());
  assert.equal(form().elements.day.value, firstDay);
  assert.equal(moveHandle().disabled, true);
  assert.equal(moveHandle().draggable, false);
  const target = [...document.querySelectorAll("time")].find((item) => item.dateTime !== firstDay).dateTime;
  await dropOn(target);
  assert.equal(state.requests.filter((item) => item.method === "PUT").length, 0);
  await click(button("Cancel"));
  let release;
  state.pause = new Promise((resolve) => { release = resolve; });
  await dropOn(target);
  assert.equal(moveHandle().disabled, true);
  assert.equal(moveHandle().draggable, false);
  assert.equal(document.querySelector('[aria-label="Next month"]').disabled, true);
  await dropOn(target);
  assert.equal(state.requests.filter((item) => item.method === "PUT").length, 1);
  assert.ok(dayCell(firstDay).querySelector(".calendar-drag-handle"));
  await act(async () => release());
  assert.ok(document.querySelector("dialog[open]"));
  await click(button("Keep current suggestions"));
  assert.equal(moveHandle().disabled, false);
  assert.equal(state.sessions[0].day, target);
});


// Confirmed and completed date changes require approval, including through the form.
test("protected workout moves can be cancelled without saving or losing previews", async (t) => {
  for (const status of ["confirmed", "completed"]) {
    const workout = { ...saved, status };
    const state = await setup(t, [workout]);
    const prompts = [];
    t.mock.method(window, "confirm", (message) => { prompts.push(message); return false; });
    await click(button("Generate suggestions"));
    const target = [...document.querySelectorAll("time")].find((item) => item.dateTime !== firstDay).dateTime;
    await dropOn(target);
    assert.match(prompts.at(-1), new RegExp(status));
    assert.deepEqual(state.sessions, [workout]);
    assert.equal(state.requests.filter((item) => item.method === "PUT").length, 0);
    assert.ok(document.querySelector(".calendar-card--proposal"));
    await click(button("Edit"));
    await change(form().elements.day, target);
    await submit();
    assert.equal(prompts.length, 2);
    assert.ok(form());
    assert.deepEqual(state.sessions, [workout]);
  }
});


// Navigate by the displayed month, since padding dates may also be present.
async function showMonth(day) {
  const calendar = document.querySelector(".monthly-calendar");
  const current = calendar.getAttribute("aria-label").slice(-7);
  const [currentYear, currentMonth] = current.split("-").map(Number);
  const [targetYear, targetMonth] = day.slice(0, 7).split("-").map(Number);
  const offset = (targetYear - currentYear) * 12 + targetMonth - currentMonth;
  const direction = offset < 0 ? "Previous month" : "Next month";
  for (let step = 0; step < Math.abs(offset); step += 1) {
    await click(document.querySelector(`[aria-label="${direction}"]`));
  }
  assert.equal(calendar.getAttribute("aria-label"), `Month ${day.slice(0, 7)}`);
}

// Fixed Mondays exercise drafts in the same month, the next month and next year.
const draftCalendarCases = [
  { label: "same month", today: "2026-10-05", origin: "2026-10-19" },
  { label: "month rollover", today: "2026-10-19", origin: "2026-11-02" },
  { label: "year rollover", today: "2026-12-21", origin: "2027-01-04" },
];

function freezeDate(t, day) {
  const RealDate = Date;
  const now = new RealDate(`${day}T12:00:00`).getTime();
  t.mock.method(globalThis, "Date", class extends RealDate {
    constructor(...args) { super(...(args.length ? args : [now])); }
    static now() { return now; }
  });
}

async function prepareDraft(t) {
  const state = await setup(t, []);
  const today = new Date();
  today.setHours(12, 0, 0, 0);
  const future = new Date(today);
  future.setDate(future.getDate() + 14);
  future.setDate(future.getDate() - (future.getDay() + 6) % 7);
  const origin = dateString(future);
  // The existing proposal mock uses firstDay; install a future draft for move cases.
  const originalFetch = globalThis.fetch;
  t.mock.method(globalThis, "fetch", async (path, options) => {
    const response = await originalFetch(path, options);
    if (path === "/api/proposals" && !JSON.parse(options.body).moves?.length && response.ok) {
      return Response.json([{ ...saved, id: null, day: origin, status: "planned" }]);
    }
    return response;
  });
  await change(document.querySelector('.planning-controls select'), "4");
  await click(button("Generate suggestions"));
  await showMonth(origin);
  const targetDate = new Date(`${origin}T12:00:00`);
  targetDate.setDate(targetDate.getDate() + 1);
  return { state, origin, target: dateString(targetDate) };
}

// Moving a draft requires no approval or storage write before direct confirmation.
test("moved suggestions remain unsaved and can be accepted at their new dates", async (t) => {
  const { state, origin, target } = await prepareDraft(t);
  let confirmations = 0;
  t.mock.method(window, "confirm", () => { confirmations += 1; return false; });
  await click(document.querySelector(".calendar-card--proposal summary"));
  await dropOn(target);
  assert.equal(confirmations, 0);
  assert.deepEqual(state.sessions, []);
  assert.equal(state.requests.length, 1);
  assert.ok(dayCell(target).querySelector(".calendar-card--proposal"));
  assert.equal(dayCell(origin).querySelector(".calendar-card--proposal"), null);
  assert.ok(document.querySelector("dialog[open]"));
  await click(button("Keep current suggestions"));
  await click(document.querySelector('button[aria-label^="Confirm suggestion "]'));
  assert.equal(state.sessions[0].day, target);
  const request = state.requests.at(-1);
  assert.equal(request.path, "/api/proposals/accept");
  assert.equal(request.body.confirm, true);
  assert.equal(state.sessions[0].status, "confirmed");
  assert.equal(request.body.moves[0].original_day, origin);
  assert.equal(request.body.moves[0].session.day, target);
  assert.equal(request.body.moves[0].session.id, undefined);
});

// Replanning is explicit and retains manually moved positions without storing them.
test("recalculate after a draft move reserves its date without saving it", async (t) => {
  const { state, origin, target } = await prepareDraft(t);
  await dropOn(target);
  assert.equal(state.requests.length, 1);
  await click(button("Recalculate"));
  assert.equal(document.querySelector("dialog"), null);
  assert.equal(state.requests.length, 2);
  assert.equal(state.requests.at(-1).body.moves[0].original_day, origin);
  assert.ok(dayCell(target).querySelector(".calendar-card--proposal"));
  assert.ok(document.querySelector('button[aria-label^="Confirm suggestion "]'));
  assert.deepEqual(state.sessions, []);
  const next = new Date(`${target}T12:00:00`);
  next.setDate(next.getDate() + 1);
  await dropOn(dateString(next));
  await click(button("Recalculate"));
  assert.equal(state.requests.at(-1).body.moves.length, 1);
  assert.equal(state.requests.at(-1).body.moves[0].original_day, origin);
});

// A recalculation error must not undo the completed move or discard the current preview.
test("failed rescheduling retains the move and preview and supports retry", async (t) => {
  const { state, target } = await prepareDraft(t);
  await dropOn(target);
  state.fail = "POST";
  await click(button("Recalculate"));
  assert.match(document.querySelector("dialog").textContent, /Cannot save right now/);
  assert.ok(dayCell(target).querySelector(".calendar-card--proposal"));
  assert.deepEqual(state.sessions, []);
  state.fail = "";
  await click(button("Recalculate"));
  assert.equal(document.querySelector("dialog"), null);
  assert.ok(dayCell(target).querySelector(".calendar-card--proposal"));
});

// A saved planned entry moves without approval, then asks whether to regenerate drafts.
test("planned moves skip approval and recalculate only after the dialog choice", async (t) => {
  const state = await setup(t, [{ ...saved, status: "planned" }]);
  t.mock.method(window, "confirm", () => assert.fail("Planned moves must not ask for approval"));
  const target = [...document.querySelectorAll("time")].find((item) => item.dateTime !== firstDay).dateTime;
  await dropOn(target);
  assert.equal(state.sessions[0].day, target);
  assert.equal(state.requests.length, 1);
  await click(button("Recalculate"));
  assert.equal(state.requests.at(-1).path, "/api/proposals");
  assert.equal(document.querySelector("dialog"), null);
});

for (const scenario of draftCalendarCases) {
  // Draft destinations must remain free and within the planning horizon and availability.
  test(`invalid suggestion drops stay in place without asking to reschedule (${scenario.label})`, async (t) => {
    freezeDate(t, scenario.today);
    const { state, origin, target } = await prepareDraft(t);
    assert.equal(origin, scenario.origin);
    await click(button("Dismiss all"));
    const unavailable = document.querySelector(`input[aria-label="Unavailable for suggestions on ${target}"]`);
    await click(unavailable);
    await click(button("Generate suggestions"));
    await showMonth(origin);
    await dropOn(target);
    assert.match(document.querySelector('[role="alert"]').textContent, /available date within the 28-day horizon/);
    assert.ok(dayCell(origin).querySelector(".calendar-card--proposal"));
    assert.equal(document.querySelector("dialog"), null);
    assert.deepEqual(state.sessions, []);
  });
}

// Keyboard users can reposition a suggestion through the move handle's date form.
test("suggestion handle offers date editing without saving the draft", async (t) => {
  const { state, target } = await prepareDraft(t);
  await click(moveHandle());
  assert.equal(form().getAttribute("aria-label"), "Move suggestion");
  await change(form().elements.day, target);
  await submit();
  assert.ok(dayCell(target).querySelector(".calendar-card--proposal"));
  assert.deepEqual(state.sessions, []);
  const cancel = new window.Event("cancel", { cancelable: true });
  await act(async () => document.querySelector("dialog").dispatchEvent(cancel));
  assert.equal(document.querySelector("dialog"), null);
});


// A failed replan never rolls back a saved move or leaves the modal impossible to dismiss.
test("saved move survives recalculation failure and keeping the old preview", async (t) => {
  const state = await setup(t, [{ ...saved, status: "planned" }]);
  await click(button("Generate suggestions"));
  const target = [...document.querySelectorAll("time")].find((item) => item.dateTime !== firstDay).dateTime;
  await dropOn(target);
  state.fail = "POST";
  await click(button("Recalculate"));
  assert.equal(state.sessions[0].day, target);
  assert.ok(document.querySelector(".calendar-card--proposal"));
  assert.match(document.querySelector("dialog").textContent, /Cannot save right now/);
  await click(button("Keep current suggestions"));
  assert.equal(document.querySelector("dialog"), null);
  assert.equal(state.sessions[0].day, target);
});

// While recalculation is pending the dialog cannot dismiss or launch a duplicate request.
test("rescheduling blocks duplicate requests and Escape during recalculation", async (t) => {
  const { state, target } = await prepareDraft(t);
  await dropOn(target);
  let release;
  state.pause = new Promise((resolve) => { release = resolve; });
  await click(button("Recalculate"));
  assert.equal(button("Recalculating...").disabled, true);
  assert.equal(button("Keep current suggestions").disabled, true);
  const cancel = new window.Event("cancel", { cancelable: true });
  await act(async () => document.querySelector("dialog").dispatchEvent(cancel));
  assert.ok(document.querySelector("dialog"));
  await click(button("Recalculating..."));
  assert.equal(state.requests.length, 2);
  await act(async () => release());
  assert.equal(document.querySelector("dialog"), null);
});


// The visible remove button dismisses an unsaved card without approval or storage changes.
test("remove a collapsed suggestion without touching saved workouts", async (t) => {
  const state = await setup(t);
  await click(button("Generate suggestions"));
  t.mock.method(window, "confirm", () => assert.fail("Draft removal must not ask for approval"));
  const remove = document.querySelector('button[aria-label^="Remove suggestion "]');
  assert.ok(remove);
  assert.equal(remove.closest("details"), null);
  assert.equal(remove.closest("article").querySelector("details").open, false);
  await click(document.querySelector(".calendar-card--proposal summary"));
  assert.ok(document.querySelector('button[aria-label^="Confirm suggestion "]'));
  const requests = state.requests.length;
  await click(remove);
  assert.equal(document.querySelector(".calendar-card--proposal"), null);
  assert.equal(document.querySelector('button[aria-label^="Remove suggestion "]'), null);
  assert.deepEqual(state.sessions, [saved]);
  assert.equal(state.requests.length, requests);
  assert.ok(document.querySelector("dialog[open]"));
  assert.match(document.querySelector("dialog").textContent, /Removed suggestions stay excluded/);
  await click(button("Keep current suggestions"));
  assert.equal(document.querySelector("dialog"), null);
  assert.equal(state.requests.length, requests);
  assert.equal([...document.querySelectorAll("button")].some((item) => item.textContent.startsWith("Accept selected")), false);
  assert.match(document.body.textContent, /No suggestions remain/);
});

// Removal follows the preview through recalculation, while fresh generation starts over.
test("dismissed dates survive recalculation and reset for a fresh plan", async (t) => {
  const state = await setup(t);
  await click(button("Generate suggestions"));
  await click(button("Remove"));
  const requestsBeforeRecalculation = state.requests.length;
  assert.ok(document.querySelector("dialog[open]"));
  assert.equal(requestsBeforeRecalculation, 1);
  await click(button("Recalculate"));
  assert.equal(state.requests.length, requestsBeforeRecalculation + 1);
  assert.deepEqual(state.requests.at(-1).body.excluded, [{ day: firstDay, activity: "gym" }]);
  assert.equal(document.querySelector(".calendar-card--proposal"), null);
  await click(button("Generate suggestions"));
  assert.equal(state.requests.at(-1).body.excluded, undefined);
  assert.ok(document.querySelector(".calendar-card--proposal"));
});

// Confirming a remaining draft carries the removal and no stale move into acceptance.
test("removing one draft keeps other suggestions and excludes its old reservation", async (t) => {
  const { state, origin, target } = await prepareDraft(t);
  await dropOn(target);
  await click(button("Keep current suggestions"));
  // Add a second generated suggestion through a recalculation response.
  const originalFetch = globalThis.fetch;
  const later = new Date(`${origin}T12:00:00`);
  later.setDate(later.getDate() + 2);
  const remainingDay = dateString(later);
  t.mock.method(globalThis, "fetch", async (path, options) => {
    const response = await originalFetch(path, options);
    if (path === "/api/proposals" && response.ok) {
      const items = await response.json();
      return Response.json([...items, { ...saved, id: null, day: remainingDay, status: "planned" }]);
    }
    return response;
  });
  const movedAgain = new Date(`${origin}T12:00:00`);
  movedAgain.setDate(movedAgain.getDate() + 3);
  const removedDay = dateString(movedAgain);
  await dropOn(removedDay);
  await click(button("Recalculate"));
  await click(dayCell(removedDay).querySelector('button[aria-label^="Remove suggestion "]'));
  await click(button("Keep current suggestions"));
  await click(document.querySelector('button[aria-label^="Confirm suggestion "]'));
  const request = state.requests.at(-1);
  assert.deepEqual(request.body.moves, []);
  assert.deepEqual(request.body.excluded, [{ day: removedDay, activity: "gym" }, { day: origin, activity: "gym" }]);
  assert.equal(request.body.proposals.length, 1);
  assert.equal(request.body.proposals[0].day, remainingDay);
});

// Editing locks suggestion actions so an active form cannot lose its draft context.
test("suggestion actions are disabled during editing and a pending save", async (t) => {
  const state = await setup(t);
  await click(button("Generate suggestions"));
  await click(button("Edit"));
  assert.equal(button("Remove").disabled, true);
  assert.equal(button("Dismiss all").disabled, true);
  assert.equal(document.querySelector('button[aria-label^="Confirm suggestion "]').disabled, true);
  await click(button("Remove"));
  assert.ok(document.querySelector(".calendar-card--proposal"));
  await click(button("Cancel"));
  let release;
  state.pause = new Promise((resolve) => { release = resolve; });
  await click(button("Edit"));
  await submit();
  assert.equal(button("Remove").disabled, true);
  await click(button("Remove"));
  assert.ok(document.querySelector(".calendar-card--proposal"));
  await act(async () => release());
});


// A failed recalculation keeps a removal applied and allows retry with the same exclusions.
test("retry rescheduling after removal without restoring the dismissed suggestion", async (t) => {
  const state = await setup(t);
  await click(button("Generate suggestions"));
  await click(button("Remove"));
  state.fail = "POST";
  await click(button("Recalculate"));
  assert.match(document.querySelector("dialog").textContent, /Cannot save right now/);
  assert.equal(document.querySelector(".calendar-card--proposal"), null);
  assert.deepEqual(state.sessions, [saved]);
  assert.deepEqual(state.requests.at(-1).body.excluded, [{ day: firstDay, activity: "gym" }]);
  state.fail = "";
  await click(button("Recalculate"));
  assert.equal(document.querySelector("dialog"), null);
  assert.equal(document.querySelector(".calendar-card--proposal"), null);
  assert.deepEqual(state.requests.at(-1).body.excluded, [{ day: firstDay, activity: "gym" }]);
  assert.deepEqual(state.sessions, [saved]);
});

// The header action must reveal and focus planning controls without requesting a plan.
test("Plan training opens the tools panel without generating suggestions", async (t) => {
  const state = await setup(t);
  const panel = document.querySelector(".planning-panel");
  panel.open = false;
  const action = document.querySelector(".plan-button");
  await click(action);
  assert.equal(panel.open, true);
  assert.equal(document.activeElement, panel.querySelector("summary"));
  assert.deepEqual(state.requests, []);
});

// A collapsed suggestion can be confirmed while the planning panel is hidden.
test("calendar suggestion actions stay usable when the planning panel is collapsed", async (t) => {
  const state = await setup(t, []);
  await click(button("Generate suggestions"));
  const panel = document.querySelector(".planning-panel");
  panel.open = false;
  const toolbar = document.querySelector('[role="group"][aria-label="Suggestion actions"]');
  assert.ok(toolbar.closest(".calendar-section"));
  assert.equal(toolbar.closest("details"), null);
  const confirm = document.querySelector('button[aria-label^="Confirm suggestion "]');
  assert.ok(confirm.closest(".calendar-card--proposal"));
  assert.equal(confirm.closest("details"), null);
  assert.equal(confirm.closest("article").querySelector("details").open, false);
  assert.equal(document.querySelector(".calendar-selection"), null);
  assert.equal(document.body.textContent.includes("Select all"), false);
  assert.equal(document.body.textContent.includes("Accept selected"), false);
  assert.equal(document.querySelector('[aria-label="Suggestion review"]'), null);
  assert.equal(document.querySelector(".preview"), null);
  assert.equal(document.body.textContent.includes("Review your proposal"), false);
  await click(confirm);
  assert.equal(state.requests.at(-1).path, "/api/proposals/accept");
  assert.equal(state.requests.at(-1).body.proposals.length, 1);
  assert.equal(state.requests.at(-1).body.confirm, true);
  assert.equal(state.sessions[0].status, "confirmed");
  assert.equal(document.querySelector('[aria-label="Suggestion actions"]'), null);
});

// Dismissing suggestions without confirming any of them never writes to storage.
test("calendar suggestions can be dismissed without saving", async (t) => {
  const state = await setup(t, []);
  await click(button("Generate suggestions"));
  assert.ok(document.querySelector('button[aria-label^="Confirm suggestion "]'));
  const requests = state.requests.length;
  await click(button("Dismiss all"));
  assert.equal(state.requests.length, requests);
  assert.deepEqual(state.sessions, []);
  assert.equal(document.querySelector(".calendar-card--proposal"), null);
  assert.equal(document.querySelector('[aria-label="Suggestion actions"]'), null);
});

// A rejected confirmation preserves the draft for an explicit retry.
test("calendar confirmation failure retains suggestions for retry", async (t) => {
  const state = await setup(t, []);
  await click(button("Generate suggestions"));
  state.fail = "POST";
  await click(document.querySelector('button[aria-label^="Confirm suggestion "]'));
  assert.match(document.querySelector('[role="alert"]').textContent, /Cannot save right now/);
  assert.ok(document.querySelector(".calendar-card--proposal"));
  assert.equal(document.querySelector('button[aria-label^="Confirm suggestion "]').disabled, false);
  assert.deepEqual(state.sessions, []);
  state.fail = "";
  await click(document.querySelector('button[aria-label^="Confirm suggestion "]'));
  assert.equal(state.sessions.length, 1);
  assert.equal(document.querySelector('[aria-label="Suggestion actions"]'), null);
});

// Confirming one moved draft leaves the other draft usable without stale reservations.
test("confirm suggestions individually and drop accepted move metadata", async (t) => {
  const { state, origin, target } = await prepareDraft(t);
  await dropOn(target);
  const originalFetch = globalThis.fetch;
  const otherDate = new Date(`${target}T12:00:00`);
  otherDate.setDate(otherDate.getDate() + 1);
  const otherDay = dateString(otherDate);
  t.mock.method(globalThis, "fetch", async (path, options) => {
    const response = await originalFetch(path, options);
    if (path === "/api/proposals" && response.ok) {
      return Response.json([
        ...await response.json(),
        { ...saved, id: null, day: otherDay, status: "planned" },
      ]);
    }
    return response;
  });
  await click(button("Recalculate"));
  let release;
  state.pause = new Promise((resolve) => { release = resolve; });
  const confirm = dayCell(target).querySelector('button[aria-label^="Confirm suggestion "]');
  await click(confirm);
  assert.equal(confirm.disabled, true);
  assert.equal(dayCell(otherDay).querySelector('button[aria-label^="Confirm suggestion "]').disabled, true);
  await act(async () => { release(); });
  state.pause = null;
  assert.equal(state.sessions.length, 1);
  assert.equal(state.sessions[0].status, "confirmed");
  assert.ok(dayCell(otherDay).querySelector(".calendar-card--proposal"));
  await click(dayCell(otherDay).querySelector('button[aria-label^="Confirm suggestion "]'));
  assert.equal(state.sessions.length, 2);
  assert.equal(state.requests.at(-1).body.proposals.length, 1);
  assert.deepEqual(state.requests.at(-1).body.moves, []);
  assert.ok(state.requests.at(-1).body.excluded.some((key) => key.day === origin && key.activity === "gym"));
  assert.equal(document.querySelector(".calendar-card--proposal"), null);
});


// Target changes keep intervals within total runs and send a snapshot with every plan.
test("simple training targets replace the horizon selector", async (t) => {
  const state = await setup(t, []);
  const gym = document.querySelector('[aria-label="Gym sessions per week"]');
  const runs = document.querySelector('[aria-label="Runs per week"]');
  const intervals = document.querySelector('[aria-label="Interval runs (included in total)"]');
  assert.equal(gym.value, "3");
  assert.equal(runs.value, "2");
  assert.equal(intervals.value, "0");
  assert.doesNotMatch(document.querySelector(".planning-controls").textContent, /Planning horizon/);
  await change(gym, "2");
  await change(runs, "3");
  await change(intervals, "1");
  await click(button("Generate suggestions"));
  assert.equal(state.requests.at(-1).body.weeks, 4);
  assert.deepEqual(state.requests.at(-1).body.targets, { gym: 2, runs: 3, intervals: 1 });
  await change(runs, "0");
  assert.equal(intervals.value, "0");
  assert.equal(document.querySelector(".calendar-card--proposal"), null);
  await click(button("Generate suggestions"));
  assert.deepEqual(state.requests.at(-1).body.targets, { gym: 2, runs: 0, intervals: 0 });
});

for (const scenario of draftCalendarCases) {
  // Moving, removing and confirming use both activity and date when drafts share a day.
  test(`same-day draft actions preserve separate workout identities (${scenario.label})`, async (t) => {
    freezeDate(t, scenario.today);
    const { state, origin, target } = await prepareDraft(t);
    assert.equal(origin, scenario.origin);
    const originalFetch = globalThis.fetch;
    t.mock.method(globalThis, "fetch", async (path, options) => {
      const response = await originalFetch(path, options);
      if (path === "/api/proposals" && !JSON.parse(options.body).moves?.length && response.ok) {
        return Response.json([
          { ...saved, id: null, day: origin, status: "planned", activity: "gym" },
          { ...saved, id: null, day: origin, status: "planned", activity: "easy_run" },
        ]);
      }
      return response;
    });
    await click(button("Generate suggestions"));
    await showMonth(origin);
    const handles = () => [...dayCell(origin).querySelectorAll(".calendar-drag-handle")];
    await click(handles()[1]);
    await change(document.querySelector('[aria-label="Move suggestion"] input'), target);
    await click(button("Move suggestion"));
    await click(button("Keep current suggestions"));
    await click(handles()[0]);
    await change(document.querySelector('[aria-label="Move suggestion"] input'), target);
    await click(button("Move suggestion"));
    await click(button("Recalculate"));
    const request = state.requests.at(-1).body;
    assert.equal(request.moves.length, 2);
    assert.deepEqual(request.moves.map((move) => move.session.activity), ["easy_run", "gym"]);
    assert.equal(dayCell(target).querySelectorAll(".calendar-card--proposal").length, 2);
    await click(dayCell(target).querySelector('button[aria-label*="Remove suggestion"][aria-label$="Easy run"]'));
    await click(button("Keep current suggestions"));
    await click(dayCell(target).querySelector('button[aria-label^="Confirm suggestion"]'));
    assert.equal(state.requests.at(-1).body.moves.length, 1);
    assert.equal(state.requests.at(-1).body.moves[0].session.activity, "gym");
    assert.equal(state.sessions[0].activity, "gym");
    assert.equal(state.sessions[0].day, target);
    assert.deepEqual(state.requests.at(-1).body.excluded, [
      { day: target, activity: "easy_run" }, { day: origin, activity: "easy_run" },
    ]);
  });
}


// Gym and running weekday settings are independent and included in preview confirmation.
test("allowed weekday controls include weekends and follow the preview", async (t) => {
  const state = await setup(t, []);
  const days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
  for (const activity of ["Gym", "Running"]) {
    for (const day of days) {
      assert.equal(document.querySelector('[aria-label="' + activity + " on " + day + '"]').checked, true);
    }
  }
  for (const day of days.slice(0, 5)) {
    await click(document.querySelector('[aria-label="Gym on ' + day + '"]'));
  }
  await click(document.querySelector('[aria-label="Running on Tue"]'));
  await click(button("Generate suggestions"));
  const expected = { gym: [5, 6], running: [0, 2, 3, 4, 5, 6] };
  assert.deepEqual(state.requests.at(-1).body.weekdays, expected);
  await click(document.querySelector('button[aria-label^="Confirm suggestion "]'));
  assert.deepEqual(state.requests.at(-1).body.weekdays, expected);
});

// Clearing all days is a valid restriction and changing a setting clears only the preview.
test("weekday changes clear unsaved previews without modifying saved workouts", async (t) => {
  const state = await setup(t);
  await click(button("Generate suggestions"));
  await click(document.querySelector('[aria-label="Gym on Mon"]'));
  assert.equal(document.querySelector(".calendar-card--proposal"), null);
  assert.deepEqual(state.sessions, [saved]);
  for (const day of ["Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]) {
    await click(document.querySelector('[aria-label="Gym on ' + day + '"]'));
  }
  assert.match(document.body.textContent, /No gym suggestions while no weekdays are selected/);
  await click(button("Generate suggestions"));
  assert.deepEqual(state.requests.at(-1).body.weekdays.gym, []);
});

for (const scenario of draftCalendarCases) {
  // Date editing cannot place an unsaved workout outside its recurring activity availability.
  test(`draft date edits reject unselected weekdays (${scenario.label})`, async (t) => {
    freezeDate(t, scenario.today);
    const { state, origin, target } = await prepareDraft(t);
    assert.equal(origin, scenario.origin);
    // target is Tuesday; the original draft is Monday.
    await click(document.querySelector('[aria-label="Gym on Tue"]'));
    await click(button("Generate suggestions"));
    await showMonth(origin);
    await click(moveHandle());
    await change(form().elements.day, target);
    await submit();
    assert.match(document.querySelector('[role="alert"]').textContent, /allowed weekday/);
    assert.ok(dayCell(origin).querySelector(".calendar-card--proposal"));
    assert.equal(document.querySelector("dialog"), null);
    assert.deepEqual(state.sessions, []);
  });
}


// Split settings start with the agreed defaults and allow the user's example combinations.
test("custom gym split reaches generation, recalculation and confirmation", async (t) => {
  const state = await setup(t, []);
  const checkbox = (primary, group) => document.querySelector(`[aria-label="${primary} with ${group}"]`);
  assert.ok(checkbox("Chest", "Shoulders").checked);
  assert.ok(checkbox("Back", "Triceps").checked);
  assert.ok(checkbox("Legs", "Biceps").checked);
  for (const primary of ["Chest", "Back", "Legs"]) assert.ok(checkbox(primary, "Abs").checked);
  await click(button("Generate suggestions"));
  assert.deepEqual(state.requests.at(-1).body.gym_split, {
    chest: ["shoulders", "abs"], back: ["triceps", "abs"], legs: ["biceps", "abs"],
  });
  for (const [primary, old, next] of [["Chest", "Shoulders", "Biceps"], ["Back", "Triceps", "Shoulders"], ["Legs", "Biceps", "Triceps"]]) {
    await click(checkbox(primary, old));
    await click(checkbox(primary, "Abs"));
    await click(checkbox(primary, next));
  }
  assert.equal(document.querySelector(".calendar-card--proposal"), null);
  assert.deepEqual(state.sessions, []);
  const expected = { chest: ["biceps"], back: ["shoulders"], legs: ["triceps"] };
  await click(button("Generate suggestions"));
  assert.deepEqual(state.requests.at(-1).body.gym_split, expected);
  assert.match(document.querySelector(".calendar-card--proposal").textContent, /Chest, Biceps/);
  await click(document.querySelector('button[aria-label^="Remove suggestion"]'));
  await click(button("Recalculate"));
  assert.deepEqual(state.requests.at(-1).body.gym_split, expected);
  await click(button("Generate suggestions"));
  await click(document.querySelector('button[aria-label^="Confirm "]'));
  assert.deepEqual(state.requests.at(-1).body.gym_split, expected);
  assert.deepEqual(state.requests.at(-1).body.proposals[0].muscle_groups, ["chest", "biceps"]);
  assert.deepEqual(state.sessions[0].muscle_groups, ["chest", "biceps"]);
});

// Per-session accessory lists support multiple muscles, only a primary, and independent Abs.
test("gym split accessories remain optional and settings lock during editing", async (t) => {
  const state = await setup(t);
  const checkbox = (primary, group) => document.querySelector(`[aria-label="${primary} with ${group}"]`);
  await click(checkbox("Chest", "Shoulders"));
  await click(checkbox("Chest", "Abs"));
  await click(checkbox("Back", "Biceps"));
  await click(checkbox("Back", "Shoulders"));
  await click(button("Generate suggestions"));
  const split = state.requests.at(-1).body.gym_split;
  assert.deepEqual(split.chest, []);
  assert.deepEqual(new Set(split.back), new Set(["triceps", "abs", "biceps", "shoulders"]));
  assert.deepEqual(split.legs, ["biceps", "abs"]);
  await click(button("Edit"));
  for (const box of document.querySelectorAll(".gym-split-settings input")) {
    assert.ok(box.matches(":disabled"));
  }
});
