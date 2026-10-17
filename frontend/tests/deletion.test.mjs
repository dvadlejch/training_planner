import assert from "node:assert/strict";
import test from "node:test";
import { sourceUrl } from "./loadSource.mjs";

const { default: WeeklyCalendar } = await import(sourceUrl("../src/components/WeeklyCalendar.tsx"));
const { deleteSession } = await import(sourceUrl("../src/api/client.ts"));
const saved = {
  id: 7, day: "2026-10-06", activity: "gym", status: "planned",
  duration_min: null, effort: null, hr_zone_min: null, hr_zone_max: null, notes: "",
};

function buttons(node) {
  if (Array.isArray(node)) return node.flatMap(buttons);
  if (!node || typeof node !== "object") return [];
  return [
    ...(node.type === "button" ? [node] : []),
    ...buttons(node.props?.children),
  ];
}

// Every persisted status requires approval; cancelling must never call deletion.
test("saved activity deletion requires confirmation and identifies the entry", (t) => {
  const originalWindow = globalThis.window;
  t.after(() => { globalThis.window = originalWindow; });
  for (const status of ["planned", "confirmed", "completed", "skipped"]) {
    const session = { ...saved, status };
    const deleted = [];
    let approved = false;
    globalThis.window = { confirm: (message) => {
      assert.match(message, /gym on 2026-10-06/);
      assert.ok(message.includes(status));
      return approved;
    } };
    const [button] = buttons(WeeklyCalendar({
      weekStart: "2026-10-05", sessions: [session], onDelete: (item) => deleted.push(item),
    }));
    assert.equal(button.props["aria-label"], "Delete 2026-10-06 gym");
    button.props.onClick();
    assert.deepEqual(deleted, []);
    approved = true;
    button.props.onClick();
    assert.deepEqual(deleted, [session]);
  }
});

// Suggestions cannot be deleted as saved records, even if their status is planned.
test("only saved activities have delete controls and busy controls are disabled", () => {
  const controls = buttons(WeeklyCalendar({
    weekStart: "2026-10-05", sessions: [saved, { ...saved, id: null }],
    proposals: [{ ...saved, id: null }], onDelete: () => {}, disabled: true,
  }));
  assert.equal(controls.length, 1);
  assert.equal(controls[0].props.disabled, true);
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
