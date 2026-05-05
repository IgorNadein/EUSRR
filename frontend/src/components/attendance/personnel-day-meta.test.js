import test from "node:test";
import assert from "node:assert/strict";

import { getPersonnelDayMeta } from "./personnel-day-meta.js";

test("single-day day off does not leak into following attendance days", () => {
  const actions = [
    {
      id: 10,
      employee: 1,
      action: "on_day_off",
      action_display: "В отгуле",
      date: "2026-04-21T00:00:00+03:00",
      date_to: "2026-04-21",
    },
  ];

  assert.equal(
    getPersonnelDayMeta(actions, "2026-04-21", {
      personnel_status: "normal",
      effective_is_workday: true,
    })?.label,
    "В отгуле",
  );

  assert.equal(
    getPersonnelDayMeta(actions, "2026-04-22", {
      personnel_status: "normal",
      effective_is_workday: true,
    }),
    null,
  );
});

test("temporary action without date_to is limited to its own day", () => {
  const actions = [
    {
      id: 11,
      employee: 1,
      action: "on_day_off",
      action_display: "В отгуле",
      date: "2026-04-21T00:00:00+03:00",
      date_to: null,
    },
  ];

  assert.equal(getPersonnelDayMeta(actions, "2026-04-22"), null);
});

test("multi-day leave remains active until date_to inclusively", () => {
  const actions = [
    {
      id: 12,
      employee: 1,
      action: "on_leave",
      action_display: "В отпуске",
      date: "2026-04-20T00:00:00+03:00",
      date_to: "2026-04-25",
    },
  ];

  assert.equal(getPersonnelDayMeta(actions, "2026-04-25")?.label, "В отпуске");
  assert.equal(getPersonnelDayMeta(actions, "2026-04-26"), null);
});

test("activating action after dismissal clears dismissed fallback", () => {
  const actions = [
    {
      id: 20,
      employee: 1,
      action: "dismissed",
      action_display: "Уволен",
      date: "2026-04-20T00:00:00+03:00",
    },
    {
      id: 21,
      employee: 1,
      action: "rehired",
      action_display: "Восстановлен",
      date: "2026-04-22T00:00:00+03:00",
    },
  ];

  assert.equal(getPersonnelDayMeta(actions, "2026-04-21")?.label, "Уволен");
  assert.equal(getPersonnelDayMeta(actions, "2026-04-22"), null);
});
