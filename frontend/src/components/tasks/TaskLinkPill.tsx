import { Kanban } from "lucide-react";
import Link from "next/link";
import type { CSSProperties } from "react";

import type { MessageLinkedTask, TaskPriority } from "@/types/api";

type TaskLinkPillTask = Pick<
  MessageLinkedTask,
  | "id"
  | "title"
  | "board_id"
  | "board_name"
  | "column_color"
  | "priority"
  | "priority_display"
>;

type TaskLinkPillProps = {
  task: TaskLinkPillTask;
  tone?: "default" | "onAccent";
  maxTitleClassName?: string;
  className?: string;
};

const fallbackColumnColor = "#38bdf8";

const priorityColors: Record<TaskPriority, string> = {
  low: "#22c55e",
  medium: "#38bdf8",
  high: "#f59e0b",
  critical: "#ef4444",
};

function normalizeHexColor(value?: string | null): string {
  const color = String(value || "").trim();
  if (/^#[0-9a-f]{6}$/i.test(color)) return color;
  if (/^#[0-9a-f]{3}$/i.test(color)) {
    const [, r, g, b] = color;
    return `#${r}${r}${g}${g}${b}${b}`;
  }
  return fallbackColumnColor;
}

function hexToRgb(color: string): { red: number; green: number; blue: number } {
  const normalized = normalizeHexColor(color).slice(1);
  return {
    red: parseInt(normalized.slice(0, 2), 16),
    green: parseInt(normalized.slice(2, 4), 16),
    blue: parseInt(normalized.slice(4, 6), 16),
  };
}

function getReadableTextColor(color: string): string {
  const { red, green, blue } = hexToRgb(color);
  const luminance = (0.299 * red + 0.587 * green + 0.114 * blue) / 255;
  return luminance > 0.62 ? "#07111f" : "#ffffff";
}

export default function TaskLinkPill({
  task,
  tone = "default",
  maxTitleClassName = "max-w-44",
  className = "",
}: TaskLinkPillProps) {
  const columnColor = normalizeHexColor(task.column_color);
  const priorityColor = task.priority ? priorityColors[task.priority] : priorityColors.medium;
  const textColor = getReadableTextColor(columnColor);
  const isLightColumn = textColor !== "#ffffff";
  const isOnAccent = tone === "onAccent";
  const title = `${task.board_name ? `${task.board_name}: ` : ""}${task.title}${
    task.priority_display ? `, ${task.priority_display}` : ""
  }`;
  const style: CSSProperties = {
    backgroundColor: columnColor,
    borderColor: priorityColor,
    boxShadow: isOnAccent ? "inset 0 1px 0 rgba(255, 255, 255, 0.18)" : undefined,
    color: textColor,
  };
  const iconWrapStyle: CSSProperties = {
    backgroundColor: isLightColumn ? "rgba(255, 255, 255, 0.72)" : "rgba(255, 255, 255, 0.18)",
  };
  const href = `/tasks?board=${task.board_id}&task=${task.id}`;

  return (
    <Link
      href={href}
      className={`inline-flex max-w-full items-center gap-1 rounded-full border px-2 py-0.5 text-[11px] font-medium shadow-sm transition hover:brightness-110 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/45 ${className}`}
      style={style}
      title={title}
    >
      <span
        className="inline-flex h-3.5 w-3.5 shrink-0 items-center justify-center rounded-full"
        style={iconWrapStyle}
      >
        <Kanban
          size={10}
          style={{ color: textColor }}
          aria-hidden="true"
        />
      </span>
      <span className={`${maxTitleClassName} truncate`}>{task.title}</span>
    </Link>
  );
}
