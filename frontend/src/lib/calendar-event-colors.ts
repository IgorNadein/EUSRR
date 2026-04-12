export const DEFAULT_EVENT_COLOR = "#1296ea";

export const EVENT_COLOR_OPTIONS = [
  { value: DEFAULT_EVENT_COLOR, label: "Фирменный голубой" },
  { value: "#0ea5e9", label: "Небесный" },
  { value: "#14b8a6", label: "Бирюзовый" },
  { value: "#22c55e", label: "Зеленый" },
  { value: "#f59e0b", label: "Янтарный" },
  { value: "#f97316", label: "Оранжевый" },
  { value: "#ef4444", label: "Красный" },
  { value: "#8b5cf6", label: "Фиолетовый" },
];

export function resolveEventColor(color?: string | null) {
  return color || DEFAULT_EVENT_COLOR;
}
