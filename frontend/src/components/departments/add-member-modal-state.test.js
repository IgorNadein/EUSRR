import test from "node:test";
import assert from "node:assert/strict";

import {
  getAddMemberHelperText,
  getAddMemberPlaceholder,
  isAddMemberSelectDisabled,
} from "./add-member-modal-state.ts";

test("add member modal shows loading placeholder while directory loads", () => {
  assert.equal(getAddMemberPlaceholder(true), "Загружаем сотрудников...");
  assert.equal(isAddMemberSelectDisabled(true, 3), true);
  assert.equal(
    getAddMemberHelperText(true, 3),
    "Загружаем доступных сотрудников...",
  );
});

test("add member modal shows empty state when there are no selectable employees", () => {
  assert.equal(getAddMemberPlaceholder(false), "Выберите сотрудника");
  assert.equal(isAddMemberSelectDisabled(false, 0), true);
  assert.equal(
    getAddMemberHelperText(false, 0),
    "В директории нет доступных сотрудников для добавления.",
  );
});

test("add member modal stays enabled when options are ready", () => {
  assert.equal(isAddMemberSelectDisabled(false, 2), false);
  assert.equal(getAddMemberHelperText(false, 2), null);
});
