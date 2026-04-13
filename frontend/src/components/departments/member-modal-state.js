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

export function getDepartmentMemberModalError(message, mode) {
  const normalized = String(message || "").trim();
  if (!normalized) return null;

  const anotherDepartmentMatch = normalized.match(
    /Employee already belongs to another active department:\s*(.+?)\.?$/i,
  );
  if (anotherDepartmentMatch) {
    const departmentName = anotherDepartmentMatch[1]?.trim();
    if (mode === "assignRole") {
      return null;
    }
    return departmentName
      ? `Сотрудник уже состоит в другом активном отделе: ${departmentName}.`
      : "Сотрудник уже состоит в другом активном отделе.";
  }

  if (/Employee is inactive\.?$/i.test(normalized)) {
    return "Можно выбрать только активного сотрудника.";
  }

  if (/Employee not found\.?$/i.test(normalized)) {
    return "Сотрудник не найден.";
  }

  return null;
}
