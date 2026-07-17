import test from "node:test";
import assert from "node:assert/strict";

import {
  formatPayrollDate,
  formatPayrollMoney,
  getPayrollLineDirection,
  getPayrollPeriodLabel,
  groupPayrollLines,
  normalizePayrollStatements,
} from "./payroll.ts";

const period = {
  code: "2026-06",
  name: "",
  date_from: "2026-06-01",
  date_to: "2026-06-30",
  pay_date: "2026-07-05",
};

test("payroll list payload is normalized for paginated and plain responses", () => {
  const statement = { public_id: "id", period };
  assert.deepEqual(normalizePayrollStatements([statement]), [statement]);
  assert.deepEqual(
    normalizePayrollStatements({ count: 1, next: null, previous: null, results: [statement] }),
    [statement],
  );
});

test("payroll formatters keep date-only values in their calendar day", () => {
  assert.match(getPayrollPeriodLabel(period), /Июнь 2026/);
  assert.match(formatPayrollDate("2026-07-05"), /05 июля 2026/);
  assert.match(formatPayrollMoney("115000.00", "RUB"), /115.{0,2}000/);
  assert.equal(formatPayrollMoney("not-a-number", "RUB"), "—");
});

test("payroll lines are grouped and debit-like lines have a negative direction", () => {
  const base = {
    code: "BASE",
    label: "Оклад",
    amount: "80000.00",
    source_period_from: null,
    source_period_to: null,
    is_retro: false,
    calculated: false,
  };
  const groups = groupPayrollLines([
    { ...base, kind: "earning" },
    { ...base, code: "BONUS", label: "Премия", kind: "adjustment_credit" },
    { ...base, code: "ADVANCE", label: "Аванс", kind: "payment" },
  ]);

  assert.deepEqual(groups.map((group) => group.key), ["accruals", "adjustments", "payments"]);
  assert.equal(getPayrollLineDirection("adjustment_credit"), "positive");
  assert.equal(getPayrollLineDirection("deduction"), "negative");
  assert.equal(getPayrollLineDirection("payment"), "negative");
});
