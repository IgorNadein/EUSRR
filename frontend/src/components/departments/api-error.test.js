import test from "node:test";
import assert from "node:assert/strict";

import { extractDepartmentApiErrorMessage } from "./api-error.js";

test("extracts plain API error text after status code", () => {
  const error = new Error(
    "API Error: 400 Employee already belongs to another active department: Бухгалтерия.",
  );

  assert.equal(
    extractDepartmentApiErrorMessage(error, "fallback"),
    "Employee already belongs to another active department: Бухгалтерия.",
  );
});

test("extracts first field error from JSON payload", () => {
  const error = new Error(
    'API Error: 400 {"employee_id":["Employee already belongs to another active department: Бухгалтерия."]}',
  );

  assert.equal(
    extractDepartmentApiErrorMessage(error, "fallback"),
    "Employee already belongs to another active department: Бухгалтерия.",
  );
});

test("falls back for unparsable payload", () => {
  const error = new Error("API Error: 500");

  assert.equal(
    extractDepartmentApiErrorMessage(error, "fallback"),
    "fallback",
  );
});
