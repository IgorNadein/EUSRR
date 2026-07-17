import test from "node:test";
import assert from "node:assert/strict";

import {
  canApprovePayrollDraft,
  getPayrollAdminError,
  getPrimaryPayrollRunAction,
  isPayrollAdminStaleConflict,
  normalizePayrollAdminList,
} from "./payroll-admin.ts";

const permissions = {
  manage_inputs: true,
  approve_inputs: true,
  override_approval: false,
  calculate: true,
  approve_run: true,
  publish: true,
  view_all: true,
  audit: false,
};

test("payroll admin normalizes DRF and plain list payloads", () => {
  assert.deepEqual(normalizePayrollAdminList([1, 2]), [1, 2]);
  assert.deepEqual(
    normalizePayrollAdminList({ count: 1, next: null, previous: null, results: [3] }),
    [3],
  );
});

test("payroll workflow exposes only the next permitted primary action", () => {
  assert.equal(getPrimaryPayrollRunAction(null, "open", permissions, true), "calculate");
  assert.equal(
    getPrimaryPayrollRunAction({ status: "calculated" }, "calculated", permissions, true),
    "submit_review",
  );
  assert.equal(
    getPrimaryPayrollRunAction({ status: "review" }, "review", { ...permissions, approve_run: false }, true),
    null,
  );
  assert.equal(
    getPrimaryPayrollRunAction({ status: "approved" }, "approved", permissions, true),
    "publish",
  );
  assert.equal(getPrimaryPayrollRunAction(null, "closed", permissions, true), null);
});

test("self-approval requires both the normal approval permission and the override", () => {
  assert.equal(canApprovePayrollDraft(false, true, false), true);
  assert.equal(canApprovePayrollDraft(true, true, false), false);
  assert.equal(canApprovePayrollDraft(true, true, true), true);
  assert.equal(canApprovePayrollDraft(true, false, true), false);

  const ownRun = { status: "review", requested_by: { id: 17 } };
  assert.equal(getPrimaryPayrollRunAction(ownRun, "review", permissions, true, 17), null);
  assert.equal(
    getPrimaryPayrollRunAction(
      ownRun,
      "review",
      { ...permissions, override_approval: true },
      true,
      17,
    ),
    "approve",
  );
  assert.equal(getPrimaryPayrollRunAction(ownRun, "review", permissions, true, 18), "approve");
  assert.equal(
    getPrimaryPayrollRunAction(
      ownRun,
      "review",
      { ...permissions, approve_run: false, override_approval: true },
      true,
      17,
    ),
    null,
  );
});

test("payroll admin presents backend and conflict errors in plain Russian", () => {
  assert.equal(
    getPayrollAdminError(
      new Error('API Error: 400 {"code":"INVALID","message":"Проверьте период"}'),
      "Ошибка",
    ),
    "Проверьте период",
  );
  assert.equal(
    getPayrollAdminError(new Error("API Error: 409 Conflict"), "Ошибка"),
    "Возник конфликт данных. Проверьте условия и повторите действие.",
  );
  assert.equal(
    getPayrollAdminError(
      new Error('API Error: 409 {"code":"CALCULATION_VALIDATION_FAILED","message":"Расчёт не прошёл проверку","details":{"issues":[]}} trailing context'),
      "Ошибка",
    ),
    "Расчёт не прошёл проверку",
  );
});

test("only explicit stale payroll conflicts trigger an automatic refresh", () => {
  assert.equal(
    isPayrollAdminStaleConflict(
      new Error('API Error: 409 {"code":"STALE_PERIOD","message":"Период уже изменён"}'),
    ),
    true,
  );
  assert.equal(
    isPayrollAdminStaleConflict(
      new Error('API Error: 409 {"detail":{"code":"STALE_DRAFT","message":"Черновик уже изменён"}}'),
    ),
    true,
  );
  assert.equal(
    isPayrollAdminStaleConflict(
      new Error('API Error: 409 {"code":"CONCURRENT_CALCULATION_CONFLICT","message":"Повторите расчёт"}'),
    ),
    true,
  );
  assert.equal(
    isPayrollAdminStaleConflict(
      new Error('API Error: 409 {"code":"CALCULATION_VALIDATION_FAILED","message":"Проверьте данные"}'),
    ),
    false,
  );
  assert.equal(
    isPayrollAdminStaleConflict(
      new Error('API Error: 409 {"code":"RULESET_NOT_EFFECTIVE","message":"Нет действующих правил"}'),
    ),
    false,
  );
  assert.equal(isPayrollAdminStaleConflict(new Error("API Error: 409 Conflict")), false);
});
