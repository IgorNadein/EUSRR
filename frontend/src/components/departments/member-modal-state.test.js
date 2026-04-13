import test from "node:test";
import assert from "node:assert/strict";

import {
  getDepartmentMemberModalEmployeeLabel,
  getDepartmentMemberModalHelperText,
  getDepartmentMemberModalItems,
  getDepartmentMemberModalPlaceholder,
  getDepartmentMemberModalSubmitLabel,
  getDepartmentMemberModalTitle,
  isDepartmentMemberModalSubmitDisabled,
} from "./member-modal-state.js";

test("member modal uses selectable employees in add mode", () => {
  const selectable = [{ id: 1, name: "A" }];
  const assignable = [{ id: 2, name: "B" }];

  assert.deepEqual(
    getDepartmentMemberModalItems("add", selectable, assignable),
    selectable,
  );
  assert.equal(getDepartmentMemberModalSubmitLabel("add"), "Добавить");
  assert.equal(getDepartmentMemberModalTitle("add"), "Добавить участника");
  assert.equal(getDepartmentMemberModalEmployeeLabel("add"), "Сотрудник");
});

test("member modal uses full assignable directory in role mode", () => {
  const selectable = [{ id: 1, name: "A" }];
  const assignable = [{ id: 2, name: "B" }];

  assert.deepEqual(
    getDepartmentMemberModalItems("assignRole", selectable, assignable),
    assignable,
  );
  assert.equal(
    getDepartmentMemberModalSubmitLabel("assignRole"),
    "Выдать роль",
  );
  assert.equal(
    getDepartmentMemberModalTitle("assignRole"),
    "Выдать роль сотруднику",
  );
  assert.equal(
    getDepartmentMemberModalEmployeeLabel("assignRole"),
    "Сотрудник *",
  );
});

test("member modal submit stays disabled until required fields are selected", () => {
  assert.equal(
    isDepartmentMemberModalSubmitDisabled({
      loading: false,
      mode: "add",
      selectedEmployeeId: null,
      selectedRoleId: null,
    }),
    true,
  );

  assert.equal(
    isDepartmentMemberModalSubmitDisabled({
      loading: false,
      mode: "assignRole",
      selectedEmployeeId: 1,
      selectedRoleId: null,
    }),
    true,
  );

  assert.equal(
    isDepartmentMemberModalSubmitDisabled({
      loading: false,
      mode: "assignRole",
      selectedEmployeeId: 1,
      selectedRoleId: 2,
    }),
    false,
  );
});

test("member modal helper texts reflect mode and loading state", () => {
  assert.equal(
    getDepartmentMemberModalPlaceholder("add", true),
    "Загружаем сотрудников...",
  );
  assert.equal(
    getDepartmentMemberModalPlaceholder("assignRole", false),
    "Выберите сотрудника для роли",
  );
  assert.match(
    getDepartmentMemberModalHelperText("assignRole", false, 1) || "",
    /любому активному сотруднику/i,
  );
});
