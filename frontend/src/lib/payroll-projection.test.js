import assert from "node:assert/strict";
import test from "node:test";

import {
  compareDailyPayrollProjection,
  comparePayrollProjection,
} from "./payroll-projection.ts";

test("payroll projection keeps small and moderate upward differences neutral", () => {
  assert.equal(comparePayrollProjection("105", "100"), null);
  assert.equal(comparePayrollProjection("95", "100"), null);
  assert.equal(comparePayrollProjection("125", "100"), null);
});

test("payroll projection reports direction and traffic-light color", () => {
  assert.deepEqual(comparePayrollProjection("85", "100"), {
    direction: "lower",
    color: "orange",
    percentage: 15,
  });
  assert.deepEqual(comparePayrollProjection("130", "100"), {
    direction: "higher",
    color: "green",
    percentage: 30,
  });
  assert.deepEqual(comparePayrollProjection("70", "100"), {
    direction: "lower",
    color: "red",
    percentage: 30,
  });
});

test("positive projection against zero work is green", () => {
  assert.deepEqual(comparePayrollProjection("10", "0"), {
    direction: "higher",
    color: "green",
    percentage: null,
  });
  assert.equal(comparePayrollProjection("0", "0"), null);
  assert.equal(comparePayrollProjection(null, "100"), null);
});

test("daily projection highlights every discrepancy", () => {
  assert.deepEqual(compareDailyPayrollProjection("101", "100"), {
    direction: "higher",
    color: "green",
    percentage: 1,
  });
  assert.deepEqual(compareDailyPayrollProjection("80", "100"), {
    direction: "lower",
    color: "orange",
    percentage: 20,
  });
  assert.deepEqual(compareDailyPayrollProjection("50", "100"), {
    direction: "lower",
    color: "red",
    percentage: 50,
  });
  assert.equal(compareDailyPayrollProjection("100", "100"), null);
  assert.equal(compareDailyPayrollProjection(null, "100"), null);
});
