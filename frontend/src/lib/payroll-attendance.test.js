import test from "node:test";
import assert from "node:assert/strict";

import {
  buildPayrollAttendanceApplyNotice,
  formatPayrollAttendanceEmployeeCount,
  formatPayrollWorkMetric,
  getPayrollAttendanceModeSummary,
  isAttendancePayrollWorkRecord,
} from "./payroll-attendance.ts";

test("attendance warnings use the correct employee form", () => {
  assert.equal(formatPayrollAttendanceEmployeeCount(1), "1 сотрудника");
  assert.equal(formatPayrollAttendanceEmployeeCount(2), "2 сотрудников");
  assert.equal(formatPayrollAttendanceEmployeeCount(11), "11 сотрудников");
});

test("attendance work metrics are explicitly displayed as points", () => {
  assert.equal(isAttendancePayrollWorkRecord("attendance"), true);
  assert.equal(isAttendancePayrollWorkRecord("manual"), false);
  assert.equal(formatPayrollWorkMetric("95.3125", "attendance"), "95.3125 балл.");
  assert.equal(formatPayrollWorkMetric("110.0000", "manual"), "110.0000");
});

test("attendance preview selects the summary for the chosen import mode", () => {
  const missingOnly = {
    create: 2,
    update: 0,
    revise: 0,
    unchanged: 0,
    skip: 3,
    blocked: 1,
    changes: 2,
  };
  const preview = {
    summary: {
      modes: {
        missing_only: missingOnly,
        replace_existing: { ...missingOnly, update: 1, revise: 2, changes: 5 },
      },
    },
  };

  assert.equal(getPayrollAttendanceModeSummary(preview, "missing_only"), missingOnly);
  assert.equal(getPayrollAttendanceModeSummary(preview, "replace_existing").changes, 5);
});

test("attendance apply notice explains drafts, revisions and skipped rows", () => {
  const notice = buildPayrollAttendanceApplyNotice({
    mode: "replace_existing",
    summary: {
      created: 2,
      updated: 1,
      revised: 3,
      unchanged: 4,
      skipped: 2,
      blocked: 1,
    },
    records: [],
  });

  assert.equal(
    notice,
    "Данные посещаемости обработаны: создано 2 черновика, обновлено 1, создано 3 ревизии, без изменений 4, пропущено 2, требует исправления 1. Проверьте и утвердите созданные черновики.",
  );
});
