export function getDepartmentMemberModalItems(
  mode,
  selectableEmployees,
  assignableEmployees,
) {
  return mode === "add" ? selectableEmployees : assignableEmployees;
}

export function getDepartmentMemberModalSubmitLabel(mode) {
  return mode === "add" ? "Добавить" : "Выдать роль";
}

export function getDepartmentMemberModalTitle(mode) {
  return mode === "add" ? "Добавить участника" : "Выдать роль сотруднику";
}

export function getDepartmentMemberModalEmployeeLabel(mode) {
  return mode === "add" ? "Сотрудник" : "Сотрудник *";
}

export function getDepartmentMemberModalPlaceholder(mode, optionsLoading) {
  if (optionsLoading) return "Загружаем сотрудников...";
  return mode === "add" ? "Выберите сотрудника" : "Выберите сотрудника для роли";
}

export function getDepartmentMemberModalHelperText(
  mode,
  optionsLoading,
  itemsCount,
) {
  if (optionsLoading) {
    return mode === "add"
      ? "Загружаем доступных сотрудников..."
      : "Загружаем сотрудников, которым можно выдать роль...";
  }

  if (itemsCount === 0) {
    return mode === "add"
      ? "В директории нет доступных сотрудников для добавления."
      : "Нет активных сотрудников, которым можно выдать роль.";
  }

  return mode === "add"
    ? "При добавлении можно сразу назначить роль, если она нужна."
    : "Роль в отделе можно выдать любому активному сотруднику, даже если он ещё не состоит в отделе.";
}

export function isDepartmentMemberModalSubmitDisabled({
  loading,
  mode,
  selectedEmployeeId,
  selectedRoleId,
}) {
  if (loading || !selectedEmployeeId) return true;
  if (mode === "assignRole" && !selectedRoleId) return true;
  return false;
}
