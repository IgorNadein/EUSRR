type RegulationScopeNotification = {
  verb?: string | null;
  data?: Record<string, unknown> | null;
};

export function getRegulationNotificationScopeLabel(
  notification: RegulationScopeNotification,
): string | null {
  const data = notification.data;
  const isRegulation = data?.is_regulation === true
    || (notification.verb || "").startsWith("regulation_");

  if (!isRegulation) return null;

  const departmentNames = Array.isArray(data?.regulation_department_names)
    ? Array.from(new Set(
        data.regulation_department_names
          .filter((name): name is string => typeof name === "string")
          .map((name) => name.trim())
          .filter(Boolean),
      ))
    : [];

  if (departmentNames.length === 1) {
    return `Отдел: ${departmentNames[0]}`;
  }
  if (departmentNames.length > 1) {
    return `Отделы: ${departmentNames.join(", ")}`;
  }

  if (data?.regulation_scope === "company") return "Вся компания";
  if (data?.regulation_scope === "personal") return "Личное ознакомление";
  return null;
}
