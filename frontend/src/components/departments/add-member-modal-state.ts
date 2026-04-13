export function getAddMemberPlaceholder(optionsLoading: boolean) {
  return optionsLoading ? "Загружаем сотрудников..." : "Выберите сотрудника";
}

export function isAddMemberSelectDisabled(
  optionsLoading: boolean,
  itemsCount: number,
) {
  return optionsLoading || itemsCount === 0;
}

export function getAddMemberHelperText(
  optionsLoading: boolean,
  itemsCount: number,
) {
  if (optionsLoading) {
    return "Загружаем доступных сотрудников...";
  }
  if (itemsCount === 0) {
    return "В директории нет доступных сотрудников для добавления.";
  }
  return null;
}
