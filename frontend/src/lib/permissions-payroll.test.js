import test from "node:test";
import assert from "node:assert/strict";

import { canOpenPayrollAdmin } from "./permissions.ts";

test("staff administrators can open payroll management without extra roles", () => {
  assert.equal(canOpenPayrollAdmin(null), false);
  assert.equal(canOpenPayrollAdmin({ auth: { is_staff: true, permissions: [] } }), true);
  assert.equal(
    canOpenPayrollAdmin({
      auth: {
        is_staff: true,
        permissions: ["finance.manage_payroll_inputs"],
      },
    }),
    true,
  );
  assert.equal(
    canOpenPayrollAdmin({
      auth: {
        is_staff: true,
        permissions_by_app: { finance: ["view_all_payroll"] },
      },
    }),
    true,
  );
});

test("custom payroll roles do not need Django staff access", () => {
  assert.equal(
    canOpenPayrollAdmin({
      auth: {
        is_staff: false,
        permissions: ["finance.view_all_payroll"],
      },
    }),
    true,
  );
  assert.equal(canOpenPayrollAdmin({ auth: { is_superuser: true } }), true);
  assert.equal(
    canOpenPayrollAdmin({ auth: { permissions: ["finance.audit_payroll"] } }),
    false,
  );
  assert.equal(
    canOpenPayrollAdmin({ auth: { permissions: ["finance.override_payroll_approval"] } }),
    false,
  );
  assert.equal(
    canOpenPayrollAdmin({ auth: { permissions_by_app: { finance: ["override_payroll_approval"] } } }),
    false,
  );
});
