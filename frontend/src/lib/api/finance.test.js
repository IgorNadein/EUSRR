import test from "node:test";
import assert from "node:assert/strict";

import { createFinanceApi } from "./finance.ts";

test("finance API uses own published payroll endpoints", async () => {
  const calls = [];
  const request = async (endpoint, options) => {
    calls.push({ endpoint, options });
    return { ok: true };
  };
  const finance = createFinanceApi(request);

  await finance.getMyPayrollStatements();
  await finance.getMyPayrollStatement("3f845e30-4ae1-4dd7-a474-66c90f9ef013");
  await finance.acknowledgeMyPayrollStatement("3f845e30-4ae1-4dd7-a474-66c90f9ef013");

  assert.deepEqual(calls, [
    {
      endpoint: "/api/v1/finance/payroll/me/statements/?page_size=100",
      options: undefined,
    },
    {
      endpoint: "/api/v1/finance/payroll/me/statements/3f845e30-4ae1-4dd7-a474-66c90f9ef013/",
      options: undefined,
    },
    {
      endpoint: "/api/v1/finance/payroll/me/statements/3f845e30-4ae1-4dd7-a474-66c90f9ef013/acknowledge/",
      options: { method: "POST" },
    },
  ]);
});

test("finance API encodes statement identifiers before adding them to a path", async () => {
  const endpoints = [];
  const finance = createFinanceApi(async (endpoint) => {
    endpoints.push(endpoint);
    return {};
  });

  await finance.getMyPayrollStatement("id/with spaces");

  assert.equal(
    endpoints[0],
    "/api/v1/finance/payroll/me/statements/id%2Fwith%20spaces/",
  );
});

test("finance API keeps payroll management inside the native admin REST namespace", async () => {
  const calls = [];
  const finance = createFinanceApi(async (endpoint, options) => {
    calls.push({ endpoint, options });
    return {};
  });

  await finance.getPayrollAdminWorkspace(17);
  await finance.getPayrollAdminPayRates({ period_id: 17, status: "draft" });
  await finance.updatePayrollAdminPayRate(21, {
    amount: "115000.00",
    expected_lock_version: 3,
  });
  await finance.approvePayrollAdminPayRate(21, 4);
  await finance.revisePayrollAdminPayRate(21, "Приказ № 42");
  await finance.calculatePayrollAdminPeriod(17, {
    idempotency_key: "2bdb6c92-b263-42de-963f-121491b95f54",
    recalculation_reason: "Исправлена премия",
    expected_lock_version: 7,
  });
  await finance.publishPayrollAdminRun(33);

  assert.deepEqual(calls, [
    {
      endpoint: "/api/v1/finance/payroll/admin/workspace/?period_id=17",
      options: undefined,
    },
    {
      endpoint: "/api/v1/finance/payroll/admin/pay-rates/?period_id=17&status=draft&page_size=200",
      options: undefined,
    },
    {
      endpoint: "/api/v1/finance/payroll/admin/pay-rates/21/",
      options: {
        method: "PATCH",
        body: JSON.stringify({ amount: "115000.00", expected_lock_version: 3 }),
      },
    },
    {
      endpoint: "/api/v1/finance/payroll/admin/pay-rates/21/approve/",
      options: {
        method: "POST",
        body: JSON.stringify({ expected_lock_version: 4 }),
      },
    },
    {
      endpoint: "/api/v1/finance/payroll/admin/pay-rates/21/revise/",
      options: {
        method: "POST",
        body: JSON.stringify({ reason: "Приказ № 42" }),
      },
    },
    {
      endpoint: "/api/v1/finance/payroll/admin/periods/17/calculate/",
      options: {
        method: "POST",
        body: JSON.stringify({
          idempotency_key: "2bdb6c92-b263-42de-963f-121491b95f54",
          recalculation_reason: "Исправлена премия",
          expected_lock_version: 7,
        }),
      },
    },
    {
      endpoint: "/api/v1/finance/payroll/admin/runs/33/publish/",
      options: { method: "POST", body: "{}" },
    },
  ]);
});

test("finance API previews and applies attendance work records through one period command", async () => {
  const calls = [];
  const finance = createFinanceApi(async (endpoint, options) => {
    calls.push({ endpoint, options });
    return {};
  });

  await finance.getPayrollAdminAttendanceWorkPreview(17);
  await finance.applyPayrollAdminAttendanceWork(17, {
    mode: "replace_existing",
    preview_token: "attendance-preview-token",
    expected_period_lock_version: 8,
    reason: "Перерасчёт по посещаемости за июль 2026",
  });

  assert.deepEqual(calls, [
    {
      endpoint: "/api/v1/finance/payroll/admin/periods/17/attendance-work-records/",
      options: undefined,
    },
    {
      endpoint: "/api/v1/finance/payroll/admin/periods/17/attendance-work-records/",
      options: {
        method: "POST",
        body: JSON.stringify({
          mode: "replace_existing",
          preview_token: "attendance-preview-token",
          expected_period_lock_version: 8,
          reason: "Перерасчёт по посещаемости за июль 2026",
        }),
      },
    },
  ]);
});
