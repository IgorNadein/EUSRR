import type { EmployeeAction, User } from "@/types/api";

export type UserProfileTextField =
  | "firstName"
  | "lastName"
  | "patronymic"
  | "email"
  | "phone"
  | "telegram"
  | "whatsapp"
  | "wechat";

export type UserProfileEditForm = {
  firstName: string;
  lastName: string;
  patronymic: string;
  email: string;
  phone: string;
  telegram: string;
  whatsapp: string;
  wechat: string;
  avatarFile: File | null;
  avatarPreview: string | null;
};

export type EmployeeActionField = "type" | "date" | "comment";

export type EmployeeActionForm = {
  type: string;
  date: string;
  comment: string;
  editingId: number | null;
};

export const employeeActionTypes = [
  { value: "hired", label: "Принят" },
  { value: "dismissed", label: "Уволен" },
  { value: "on_leave", label: "В отпуске" },
  { value: "returned_from_leave", label: "Вернулся из отпуска" },
  { value: "on_maternity", label: "В декрете" },
  { value: "returned_from_maternity", label: "Вернулся из декрета" },
  { value: "transferred", label: "Переведен" },
  { value: "rehired", label: "Восстановлен" },
] as const;

export const createEmptyActionForm = (): EmployeeActionForm => ({
  type: "",
  date: new Date().toISOString().split("T")[0],
  comment: "",
  editingId: null,
});

export const createEmptyEditForm = (): UserProfileEditForm => ({
  firstName: "",
  lastName: "",
  patronymic: "",
  email: "",
  phone: "",
  telegram: "",
  whatsapp: "",
  wechat: "",
  avatarFile: null,
  avatarPreview: null,
});

export function getUserFullName(person: User | null): string {
  if (!person) return "";
  return `${person.last_name || ""} ${person.first_name || ""} ${person.patronymic || ""}`.trim() || "Пользователь";
}

export function getUserInitials(person: User | null): string {
  return `${person?.last_name?.[0] || ""}${person?.first_name?.[0] || ""}` || "П";
}

export function getLatestEmployeeAction(actions?: EmployeeAction[] | null): EmployeeAction | null {
  if (!actions || actions.length === 0) return null;

  const now = new Date();
  const pastActions = actions.filter((action) => new Date(action.date) <= now);

  if (pastActions.length === 0) return null;

  return pastActions.reduce((latest, action) => (
    new Date(action.date) > new Date(latest.date) ? action : latest
  ));
}

export function sortEmployeeActions(actions?: EmployeeAction[] | null): EmployeeAction[] {
  if (!actions || actions.length === 0) return [];
  return [...actions].sort((left, right) => (
    new Date(right.date).getTime() - new Date(left.date).getTime()
  ));
}

export function formatPhoneForLink(phone: string): string {
  return phone.replace(/[^0-9+]/g, "");
}

export function getWorkDuration(dateJoined?: string): string | null {
  if (!dateJoined) return null;

  const start = new Date(dateJoined);
  const now = new Date();
  const diffMs = now.getTime() - start.getTime();
  const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));
  const years = Math.floor(diffDays / 365);
  const months = Math.floor((diffDays % 365) / 30);

  const parts: string[] = [];
  if (years > 0) {
    parts.push(`${years} ${years === 1 ? "год" : years < 5 ? "года" : "лет"}`);
  }
  if (months > 0) {
    parts.push(`${months} ${months === 1 ? "месяц" : months < 5 ? "месяца" : "месяцев"}`);
  }

  return parts.join(" ") || "меньше месяца";
}

export function formatBirthday(birthDate?: string): string | null {
  if (!birthDate) return null;
  return new Date(birthDate).toLocaleDateString("ru-RU", { day: "numeric", month: "long" });
}

export function getEmployeeActionTone(actionType?: string): {
  badgeClass: string;
  lineColor: string;
} {
  switch (actionType) {
    case "on_leave":
    case "on_maternity":
      return {
        badgeClass: "app-feedback-warning",
        lineColor: "#f59e0b",
      };
    case "transferred":
      return {
        badgeClass: "app-selected",
        lineColor: "#38bdf8",
      };
    case "dismissed":
      return {
        badgeClass: "app-feedback-danger",
        lineColor: "#ef4444",
      };
    case "returned_from_leave":
    case "returned_from_maternity":
    case "rehired":
    case "hired":
    default:
      return {
        badgeClass: "app-feedback-success",
        lineColor: "#22c55e",
      };
  }
}

export function getEmployeeActionBadgeClass(actionType?: string): string {
  return getEmployeeActionTone(actionType).badgeClass;
}

export function getEmployeeActionBorderColor(actionType?: string): string {
  return getEmployeeActionTone(actionType).lineColor;
}
