import test from "node:test";
import assert from "node:assert/strict";

import { resolveNotificationActionUrl } from "./actionUrl.ts";
import { getRegulationNotificationScopeLabel } from "./regulationScope.ts";

test("regulation notifications open the regulations section", () => {
  assert.equal(
    resolveNotificationActionUrl({
      verb: "regulation_ready",
      data: { document_id: 42, is_regulation: true },
    }),
    "/documents?section=regulations&document=42",
  );
});

test("ordinary document notifications stay in the documents section", () => {
  assert.equal(
    resolveNotificationActionUrl({
      verb: "document_ready",
      data: { document_id: 42 },
    }),
    "/documents?section=folders&document=42",
  );
});

test("regulation notification shows its acknowledgement departments", () => {
  assert.equal(
    getRegulationNotificationScopeLabel({
      verb: "regulation_ready",
      data: {
        regulation_department_names: ["Бухгалтерия", "Разработка"],
      },
    }),
    "Отделы: Бухгалтерия, Разработка",
  );
});

test("company regulation notification shows company scope", () => {
  assert.equal(
    getRegulationNotificationScopeLabel({
      verb: "regulation_ready",
      data: { regulation_scope: "company" },
    }),
    "Вся компания",
  );
});
