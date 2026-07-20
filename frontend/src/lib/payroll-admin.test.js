import test from "node:test";
import assert from "node:assert/strict";

import {
  canApprovePayrollDraft,
  getDefaultPayrollPeriodForm,
  getPayrollAdminError,
  getPrimaryPayrollRunAction,
  isPayrollAdminStaleConflict,
  normalizePayrollAdminList,
} from "./payroll-admin.ts";

const permissions = {
  full_access: false,
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

test("new payroll period defaults cover the current month and next payment date", () => {
  assert.deepEqual(
    getDefaultPayrollPeriodForm([], new Date(2026, 6, 20, 12)),
    {
      code: "2026-07",
      name: "Июль 2026",
      date_from: "2026-07-01",
      date_to: "2026-07-31",
      pay_date: "2026-08-05",
      currency: "RUB",
    },
  );
});

test("new payroll period skips occupied months and handles a year boundary", () => {
  const periods = [
    {
      code: "2026-12",
      name: "Декабрь 2026",
      date_from: "2026-12-01",
      date_to: "2026-12-31",
      pay_date: "2027-01-05",
    },
    {
      code: "2027-01",
      name: "Январь 2027",
      date_from: "2027-01-01",
      date_to: "2027-01-31",
      pay_date: "2027-02-05",
    },
  ];

  assert.deepEqual(
    getDefaultPayrollPeriodForm(periods, new Date(2026, 11, 15, 12)),
    {
      code: "2027-02",
      name: "Февраль 2027",
      date_from: "2027-02-01",
      date_to: "2027-02-28",
      pay_date: "2027-03-05",
      currency: "RUB",
    },
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
