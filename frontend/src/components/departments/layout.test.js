import test from "node:test";
import assert from "node:assert/strict";

import {
  DEPARTMENT_MEMBERS_EMPTY_STATE_CLASSNAME,
  getDepartmentMembersListClassName,
} from "./layout.js";

test("showcase members layout keeps bubble flow", () => {
  assert.equal(
    getDepartmentMembersListClassName(false),
    "flex flex-wrap items-center gap-2",
  );
});

test("management members layout keeps stacked editing rows", () => {
  assert.equal(getDepartmentMembersListClassName(true), "space-y-3");
});

test("department empty state spans full section width", () => {
  assert.match(DEPARTMENT_MEMBERS_EMPTY_STATE_CLASSNAME, /\bw-full\b/);
});
