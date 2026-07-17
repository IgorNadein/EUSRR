"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import {
  DndContext,
  DragOverlay,
  PointerSensor,
  closestCorners,
  useDraggable,
  useDroppable,
  useSensor,
  useSensors,
  type DragEndEvent,
  type DragStartEvent,
} from "@dnd-kit/core";
import { CSS } from "@dnd-kit/utilities";
import {
  CalendarDays,
  Check,
  ChevronDown,
  ChevronRight,
  Download,
  ExternalLink as ExternalLinkIcon,
  FileSignature,
  FileText,
  History,
  Kanban,
  Link2,
  ListChecks,
  Loader2,
  Maximize2,
  MessageSquare,
  Minimize2,
  Newspaper,
  Paperclip,
  Pencil,
  Play,
  Plus,
  RefreshCw,
  Search,
  ShoppingCart,
  Star,
  Tag,
  Trash2,
  UserRound,
  X,
  type LucideIcon,
} from "lucide-react";
import { Suspense, useCallback, useEffect, useMemo, useRef, useState, type RefObject } from "react";

import { AppShell } from "@/components/AppShell";
import { RequestAvatar } from "@/components/requests/RequestAvatar";
import { CommentComposer, CommentDeleteButton } from "@/components/shared/CommentControls";
import { Modal } from "@/components/ui";
import { useUser } from "@/contexts/UserContext";
import { apiClient } from "@/lib/api";
import { displayUserName, formatDate, formatDateTime, formatMoney } from "@/lib/shared";
import { resolveMediaUrl } from "@/lib/url";
import wsManager from "@/lib/websocketManager";
import type {
  CalendarEvent,
  Department,
  Document,
  Message,
  TaskActivity,
  TaskAttachment,
  TaskBoard,
  TaskCard,
  TaskChecklistItem,
  TaskColumn,
  TaskComment,
  TaskExternalLink,
  TaskLinkedAttendanceRecord,
  TaskLinkedDocument,
  TaskLinkedEmployee,
  TaskLinkedCalendarEvent,
  TaskLinkedGuest,
  TaskLinkedGuestVisit,
  TaskLinkedMessage,
  TaskLinkedPost,
  TaskLinkedProcurementRequest,
  TaskLinkedRequest,
  TaskPriority,
  User,
} from "@/types/api";

type TaskFormState = {
  id: number | null;
  title: string;
  description: string;
  column: number | "";
  assignee_id: number | "";
  priority: TaskPriority;
  due_date: string;
  label_ids: number[];
};

type BoardFormState = {
  id: number | null;
  name: string;
  description: string;
  access: "all" | "private" | "restricted";
  member_ids: number[];
  department_ids: number[];
};

type ColumnFormState = {
  name: string;
  color: string;
  is_done: boolean;
};

type LinkedItemMode = "document" | "calendar_event" | "external_link";
type LinkedItemTarget = "view" | "form";

type TaskFormExternalLinkDraft = {
  key: string;
  url: string;
  title: string;
};

type TaskFormChecklistItemDraft = {
  key: string;
  title: string;
  position: number;
  is_completed: boolean;
};

type TaskBoardSocketEvent = {
  type: string;
  data?: {
    board_id?: number;
    event?: string;
    model?: string;
    object_id?: number | null;
    task_id?: number;
  };
};

const DESKTOP_WIDE_MODE_STORAGE_PREFIX = "tasks.desktop-wide-mode";

const emptyForm: TaskFormState = {
  id: null,
  title: "",
  description: "",
  column: "",
  assignee_id: "",
  priority: "medium",
  due_date: "",
  label_ids: [],
};

const emptyBoardForm: BoardFormState = {
  id: null,
  name: "",
  description: "",
  access: "all",
  member_ids: [],
  department_ids: [],
};

const taskDescriptionPreviewClass =
  "app-text-muted mt-1 block max-h-8 w-full max-w-[13rem] overflow-hidden whitespace-normal break-all text-xs leading-4";

function TaskDescriptionPreview({ description }: { description: string }) {
  return (
    <p
      className={taskDescriptionPreviewClass}
      style={{ overflowWrap: "anywhere", wordBreak: "break-all" }}
    >
      {description}
    </p>
  );
}

function getEmployeeInitials(employee: User): string {
  const initials = [employee.first_name, employee.last_name]
    .map((part) => part?.trim().charAt(0) || "")
    .join("")
    .slice(0, 2)
    .toUpperCase();
  return initials || displayUserName(employee).slice(0, 2).toUpperCase();
}

const emptyColumnForm: ColumnFormState = {
  name: "",
  color: "#38bdf8",
  is_done: false,
};

const priorityOptions: {
  value: TaskPriority;
  label: string;
  urgencyLabel: string;
  className: string;
  textClassName: string;
}[] = [
  {
    value: "low",
    label: "Низкий",
    urgencyLabel: "Низкая",
    className: "app-badge",
    textClassName: "app-text-muted",
  },
  {
    value: "medium",
    label: "Средний",
    urgencyLabel: "Средняя",
    className: "app-selected",
    textClassName: "text-[var(--accent-primary-strong)]",
  },
  {
    value: "high",
    label: "Высокий",
    urgencyLabel: "Высокая",
    className: "app-feedback-warning",
    textClassName: "text-[var(--warning-foreground)]",
  },
  {
    value: "critical",
    label: "Критический",
    urgencyLabel: "Критическая",
    className: "app-feedback-danger",
    textClassName: "text-[var(--danger-foreground)]",
  },
];

const priorityMeta = Object.fromEntries(priorityOptions.map((item) => [item.value, item])) as Record<TaskPriority, typeof priorityOptions[number]>;

function getTaskError(error: unknown, fallback: string) {
  const raw = String((error as Error)?.message || fallback);
  const jsonStart = raw.indexOf("{");
  if (jsonStart < 0) return raw;
  try {
    const parsed = JSON.parse(raw.slice(jsonStart)) as Record<string, unknown>;
    if (typeof parsed.detail === "string") return parsed.detail;
    if (typeof parsed.error === "string") return parsed.error;
    const firstValue = Object.values(parsed)[0];
    if (Array.isArray(firstValue) && firstValue.length > 0) return String(firstValue[0]);
  } catch {
    return raw;
  }
  return raw;
}

function extractApiResults<T>(response: T[] | { results?: T[] } | null | undefined): T[] {
  if (Array.isArray(response)) return response;
  return response?.results || [];
}

function normalizeExternalUrl(value: string): string {
  const trimmed = value.trim();
  if (!trimmed) return "";
  return /^[a-z][a-z\d+.-]*:\/\//i.test(trimmed) ? trimmed : `https://${trimmed}`;
}

function getExternalLinkHost(url: string): string {
  try {
    return new URL(url).host;
  } catch {
    return url;
  }
}

function toDateOnlyTime(value?: string | null) {
  if (!value) return null;
  const match = String(value).match(/^(\d{4})-(\d{2})-(\d{2})/);
  if (!match) return null;

  const year = Number(match[1]);
  const month = Number(match[2]);
  const day = Number(match[3]);
  if (!Number.isFinite(year) || !Number.isFinite(month) || !Number.isFinite(day)) {
    return null;
  }

  const date = new Date(year, month - 1, day);
  date.setHours(0, 0, 0, 0);
  return date.getTime();
}

function getTaskDueDateBadgeClass(task: TaskCard, defaultClass = "app-badge") {
  if (!task.due_date || task.completed_at) return defaultClass;

  const dueTime = toDateOnlyTime(task.due_date);
  if (dueTime === null) return defaultClass;

  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const todayTime = today.getTime();

  if (dueTime < todayTime) return "app-feedback-danger";
  if (dueTime === todayTime) return "app-feedback-warning";
  return defaultClass;
}

function formatFileSize(size: number): string {
  if (size < 1024) return `${size} Б`;
  if (size < 1024 * 1024) return `${Math.ceil(size / 1024)} КБ`;
  return `${(size / (1024 * 1024)).toLocaleString("ru-RU", {
    maximumFractionDigits: 1,
  })} МБ`;
}

function getMessageCreatedLabel(message?: Message | null) {
  if (!message) return "";
  return message.created || (message.created_at ? formatDate(message.created_at) : "");
}

function TaskCardView({
  task,
  onOpen,
  onEdit,
  onDelete,
  currentUserId,
  claiming,
  onClaim,
  completing,
  onComplete,
  menuOpen,
  menuRef,
  onToggleMenu,
}: {
  task: TaskCard;
  onOpen: (task: TaskCard) => void;
  onEdit: (task: TaskCard) => void;
  onDelete: (task: TaskCard) => void;
  currentUserId?: number;
  claiming: boolean;
  onClaim: (task: TaskCard) => void;
  completing: boolean;
  onComplete: (task: TaskCard) => void;
  menuOpen: boolean;
  menuRef: RefObject<HTMLDivElement | null>;
  onToggleMenu: () => void;
}) {
  const { attributes, listeners, setNodeRef, transform, isDragging } = useDraggable({
    id: `task-${task.id}`,
    data: { taskId: task.id },
  });
  const style = transform && !isDragging ? { transform: CSS.Translate.toString(transform) } : undefined;
  const priority = priorityMeta[task.priority] ?? priorityMeta.medium;
  const dueDateClass = getTaskDueDateBadgeClass(task);
  const canClaim = !task.assignee && !task.completed_at;
  const canComplete = task.assignee?.id === currentUserId && !task.completed_at;

  return (
    <article
      ref={setNodeRef}
      style={style}
      className={`app-surface-elevated cursor-grab select-none rounded-xl border border-[var(--border-subtle)] p-3 shadow-sm transition active:cursor-grabbing ${
        isDragging ? "opacity-30" : "hover:border-[var(--border-strong)]"
      }`}
      title="Перетащите задачу в нужную колонку"
      onClick={() => onOpen(task)}
      {...attributes}
      {...listeners}
    >
      <div className="mb-2 flex items-start gap-2">
        <div className="min-w-0 flex-1 overflow-hidden whitespace-normal text-left">
          <div className="flex min-w-0 items-center gap-2">
            <span className="app-badge shrink-0 rounded-full px-1.5 py-0.5 text-[10px] font-semibold">
              #{task.id}
            </span>
            <h3 className="min-w-0 max-w-[9rem] truncate text-sm font-semibold text-[var(--foreground)]">
              {task.title}
            </h3>
          </div>
          {task.description ? <TaskDescriptionPreview description={task.description} /> : null}
        </div>
        <div className="flex shrink-0 flex-col items-end gap-1">
          <div
            ref={menuOpen ? menuRef : null}
            className="relative"
            onPointerDown={(event) => event.stopPropagation()}
            onClick={(event) => event.stopPropagation()}
          >
            <button
              type="button"
              onClick={onToggleMenu}
              className="app-icon-button flex h-7 w-7 items-center justify-center rounded-md"
              title="Действия"
              aria-label="Действия с задачей"
              aria-expanded={menuOpen}
              aria-haspopup="menu"
            >
              <ChevronDown
                size={14}
                className={`transition-transform ${menuOpen ? "" : "-rotate-90"}`}
              />
            </button>
            {menuOpen ? (
              <div className="app-menu absolute right-0 top-full z-30 mt-2 w-44 rounded-lg p-1.5">
                <button
                  type="button"
                  onClick={() => onEdit(task)}
                  className="flex w-full items-center gap-2 rounded-md px-3 py-2 text-left text-sm transition hover:bg-[var(--surface-secondary)]"
                >
                  <Pencil size={14} className="app-text-muted" />
                  Редактировать
                </button>
                <button
                  type="button"
                  onClick={() => onDelete(task)}
                  className="flex w-full items-center gap-2 rounded-md px-3 py-2 text-left text-sm text-[var(--danger-foreground)] transition hover:bg-[var(--danger-soft)]"
                >
                  <Trash2 size={14} />
                  Удалить
                </button>
              </div>
            ) : null}
          </div>
          <span className={`whitespace-nowrap text-right text-[11px] font-medium ${priority.textClassName}`}>
            {priority.urgencyLabel} срочность
          </span>
        </div>
      </div>

      {task.labels && task.labels.length > 0 ? (
        <div className="mb-2 flex flex-wrap gap-1.5">
          {task.labels.map((label) => (
            <span
              key={label.id}
              className="inline-flex max-w-full items-center rounded-full px-2 py-0.5 text-[11px] font-medium text-white"
              style={{ backgroundColor: label.color || "#38bdf8" }}
            >
              {label.name}
            </span>
          ))}
        </div>
      ) : null}

      <div className="flex flex-wrap items-center gap-1.5">
        {canClaim ? (
          <button
            type="button"
            onPointerDown={(event) => event.stopPropagation()}
            onClick={(event) => {
              event.stopPropagation();
              onClaim(task);
            }}
            disabled={claiming}
            className="app-action-primary inline-flex h-7 w-7 shrink-0 items-center justify-center rounded-full disabled:cursor-wait disabled:opacity-60"
            title="Взять задачу в работу"
            aria-label={`Взять задачу в работу ${task.title}`}
          >
            {claiming ? (
              <Loader2 size={13} className="animate-spin" />
            ) : (
              <Play size={14} />
            )}
          </button>
        ) : null}
        {canComplete ? (
          <button
            type="button"
            onPointerDown={(event) => event.stopPropagation()}
            onClick={(event) => {
              event.stopPropagation();
              onComplete(task);
            }}
            disabled={completing}
            className="app-action-success inline-flex h-7 w-7 shrink-0 items-center justify-center rounded-full disabled:cursor-wait disabled:opacity-60"
            title="Завершить задачу"
            aria-label={`Завершить задачу ${task.title}`}
          >
            {completing ? (
              <Loader2 size={13} className="animate-spin" />
            ) : (
              <Check size={14} strokeWidth={2.5} />
            )}
          </button>
        ) : null}
        {task.assignee ? (
          <span className="app-badge inline-flex items-center gap-1 rounded-full px-2 py-1 text-[11px]">
            <UserRound size={11} />
            {displayUserName(task.assignee)}
          </span>
        ) : null}
        {task.due_date ? (
          <span className={`${dueDateClass} inline-flex items-center gap-1 rounded-full px-2 py-1 text-[11px]`}>
            <CalendarDays size={11} />
            {formatDate(task.due_date)}
          </span>
        ) : null}
        {(task.checklist_total || 0) > 0 ? (
          <span className="app-badge inline-flex items-center gap-1 rounded-full px-2 py-1 text-[11px]">
            <ListChecks size={11} />
            {task.checklist_completed || 0}/{task.checklist_total}
          </span>
        ) : null}
        {(task.attachments_count || 0) > 0 ? (
          <span className="app-badge inline-flex items-center gap-1 rounded-full px-2 py-1 text-[11px]">
            <Paperclip size={11} />
            {task.attachments_count}
          </span>
        ) : null}
        {(task.linked_objects_count || task.linked_messages_count || 0) > 0 ? (
          <span className="app-badge inline-flex items-center gap-1 rounded-full px-2 py-1 text-[11px]">
            <Link2 size={11} />
            {task.linked_objects_count || task.linked_messages_count}
          </span>
        ) : null}
        {(task.comments_count || 0) > 0 ? (
          <span className="app-badge inline-flex items-center gap-1 rounded-full px-2 py-1 text-[11px]">
            <MessageSquare size={11} />
            {task.comments_count}
          </span>
        ) : null}
      </div>
    </article>
  );
}

function TaskDragOverlayCard({ task }: { task: TaskCard }) {
  const priority = priorityMeta[task.priority] ?? priorityMeta.medium;
  const dueDateClass = getTaskDueDateBadgeClass(task);

  return (
    <article className="app-surface-elevated w-[17rem] cursor-grabbing rounded-xl border border-[var(--accent-primary)] p-3 shadow-2xl ring-1 ring-[color:var(--accent-primary)]/20">
      <div className="mb-2 flex items-start gap-2">
        <div className="min-w-0 flex-1 overflow-hidden whitespace-normal text-left">
          <div className="flex min-w-0 items-center gap-2">
            <span className="app-badge shrink-0 rounded-full px-1.5 py-0.5 text-[10px] font-semibold">
              #{task.id}
            </span>
            <h3 className="min-w-0 max-w-[9rem] truncate text-sm font-semibold text-[var(--foreground)]">
              {task.title}
            </h3>
          </div>
          {task.description ? <TaskDescriptionPreview description={task.description} /> : null}
        </div>
        <span className={`shrink-0 whitespace-nowrap text-right text-[11px] font-medium ${priority.textClassName}`}>
          {priority.urgencyLabel} срочность
        </span>
      </div>

      {task.labels && task.labels.length > 0 ? (
        <div className="mb-2 flex flex-wrap gap-1.5">
          {task.labels.map((label) => (
            <span
              key={label.id}
              className="inline-flex max-w-full items-center rounded-full px-2 py-0.5 text-[11px] font-medium text-white"
              style={{ backgroundColor: label.color || "#38bdf8" }}
            >
              {label.name}
            </span>
          ))}
        </div>
      ) : null}

      <div className="flex flex-wrap items-center gap-1.5">
        {task.assignee ? (
          <span className="app-badge inline-flex items-center gap-1 rounded-full px-2 py-1 text-[11px]">
            <UserRound size={11} />
            {displayUserName(task.assignee)}
          </span>
        ) : null}
        {task.due_date ? (
          <span className={`${dueDateClass} inline-flex items-center gap-1 rounded-full px-2 py-1 text-[11px]`}>
            <CalendarDays size={11} />
            {formatDate(task.due_date)}
          </span>
        ) : null}
        {(task.checklist_total || 0) > 0 ? (
          <span className="app-badge inline-flex items-center gap-1 rounded-full px-2 py-1 text-[11px]">
            <ListChecks size={11} />
            {task.checklist_completed || 0}/{task.checklist_total}
          </span>
        ) : null}
        {(task.attachments_count || 0) > 0 ? (
          <span className="app-badge inline-flex items-center gap-1 rounded-full px-2 py-1 text-[11px]">
            <Paperclip size={11} />
            {task.attachments_count}
          </span>
        ) : null}
        {(task.linked_objects_count || task.linked_messages_count || 0) > 0 ? (
          <span className="app-badge inline-flex items-center gap-1 rounded-full px-2 py-1 text-[11px]">
            <Link2 size={11} />
            {task.linked_objects_count || task.linked_messages_count}
          </span>
        ) : null}
        {(task.comments_count || 0) > 0 ? (
          <span className="app-badge inline-flex items-center gap-1 rounded-full px-2 py-1 text-[11px]">
            <MessageSquare size={11} />
            {task.comments_count}
          </span>
        ) : null}
      </div>
    </article>
  );
}

function BoardColumn({
  column,
  tasks,
  onCreateTask,
  onOpenTask,
  onEditTask,
  onDeleteTask,
  currentUserId,
  claimingTaskId,
  onClaimTask,
  completingTaskId,
  onCompleteTask,
  openMenuTaskId,
  menuRef,
  onToggleTaskMenu,
  onColumnMount,
  fillAvailableHeight = false,
}: {
  column: TaskColumn;
  tasks: TaskCard[];
  onCreateTask: (columnId: number) => void;
  onOpenTask: (task: TaskCard) => void;
  onEditTask: (task: TaskCard) => void;
  onDeleteTask: (task: TaskCard) => void;
  currentUserId?: number;
  claimingTaskId: number | null;
  onClaimTask: (task: TaskCard) => void;
  completingTaskId: number | null;
  onCompleteTask: (task: TaskCard) => void;
  openMenuTaskId: number | null;
  menuRef: RefObject<HTMLDivElement | null>;
  onToggleTaskMenu: (taskId: number) => void;
  onColumnMount: (columnId: number, node: HTMLElement | null) => void;
  fillAvailableHeight?: boolean;
}) {
  const { setNodeRef, isOver } = useDroppable({
    id: `column-${column.id}`,
    data: { columnId: column.id },
  });
  const setColumnNodeRef = useCallback((node: HTMLElement | null) => {
    setNodeRef(node);
    onColumnMount(column.id, node);
  }, [column.id, onColumnMount, setNodeRef]);

  return (
    <section
      ref={setColumnNodeRef}
      className={`flex max-h-[calc(100vh-14rem)] min-h-[28rem] min-w-[18rem] flex-col rounded-xl border bg-[var(--surface-muted)] transition ${fillAvailableHeight ? "lg:h-full lg:min-h-0 lg:max-h-none" : ""} ${
        isOver ? "border-[var(--accent-primary)]" : "border-[var(--border-subtle)]"
      }`}
    >
      <div className="flex items-center justify-between gap-3 border-b border-[var(--border-subtle)] px-3 py-3">
        <div className="min-w-0 flex-1 overflow-hidden">
          <div className="flex items-center gap-2">
            <span
              className="h-2.5 w-2.5 shrink-0 rounded-full"
              style={{ backgroundColor: column.color || "#38bdf8" }}
            />
            <h2 className="min-w-0 truncate text-sm font-semibold text-[var(--foreground)]">
              {column.name}
            </h2>
          </div>
          <p className="app-text-muted mt-0.5 text-xs">{tasks.length} задач</p>
        </div>
        <button
          type="button"
          onClick={() => onCreateTask(column.id)}
          className="app-icon-button flex h-8 w-8 shrink-0 items-center justify-center rounded-lg"
          title="Создать задачу"
          aria-label="Создать задачу"
        >
          <Plus size={16} />
        </button>
      </div>
      <div className="tasks-column-scroll min-h-0 flex-1 space-y-2 overflow-y-auto p-3">
        {tasks.length > 0 ? (
          tasks.map((task) => (
            <TaskCardView
              key={task.id}
              task={task}
              onOpen={onOpenTask}
              onEdit={onEditTask}
              onDelete={onDeleteTask}
              currentUserId={currentUserId}
              claiming={claimingTaskId === task.id}
              onClaim={onClaimTask}
              completing={completingTaskId === task.id}
              onComplete={onCompleteTask}
              menuOpen={openMenuTaskId === task.id}
              menuRef={menuRef}
              onToggleMenu={() => onToggleTaskMenu(task.id)}
            />
          ))
        ) : (
          <div className="app-surface rounded-xl border border-dashed border-[var(--border-subtle)] px-3 py-5 text-center">
            <p className="app-text-muted text-xs">Нет задач</p>
          </div>
        )}
      </div>
    </section>
  );
}

function AddColumnCard({
  onClick,
  fillAvailableHeight = false,
}: {
  onClick: () => void;
  fillAvailableHeight?: boolean;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`group flex max-h-[calc(100vh-14rem)] min-h-[28rem] min-w-[18rem] flex-col items-center justify-center rounded-xl border border-dashed border-[var(--border-subtle)] bg-[var(--surface-muted)] p-4 text-center transition hover:border-[var(--accent-primary)] hover:bg-[var(--surface-elevated)] ${fillAvailableHeight ? "lg:h-full lg:min-h-0 lg:max-h-none" : ""}`}
    >
      <span className="app-selected mb-3 flex h-10 w-10 items-center justify-center rounded-xl transition group-hover:scale-105">
        <Plus size={18} />
      </span>
      <span className="text-sm font-semibold text-[var(--foreground)]">
        Добавить колонку
      </span>
    </button>
  );
}

function getLinkedPostOriginLabel(post: TaskLinkedPost["post"]) {
  if (!post) return "";
  if (post.type === "department") {
    return post.department_name ? `Отдел: ${post.department_name}` : "Отдел";
  }
  return "Компания";
}

function LinkedPostCard({
  link,
  onUnlink,
  disabled,
}: {
  link: TaskLinkedPost;
  onUnlink: (linkId: number) => void;
  disabled?: boolean;
}) {
  const post = link.post;
  const canOpen = Boolean(link.can_open && link.object_url);
  const postText = (post?.body || post?.content || "").trim();
  const originLabel = getLinkedPostOriginLabel(post);
  const mainContent = (
    <>
      <div className="mb-2 min-w-0">
        <div className="flex flex-wrap items-center gap-2">
          <span className="app-pill inline-flex items-center gap-1.5 rounded-full px-2 py-1 text-xs font-medium">
            <Newspaper size={12} />
            Новость
          </span>
          {originLabel ? (
            <span className="app-badge rounded-full px-2 py-1 text-[11px]">
              {originLabel}
            </span>
          ) : null}
          {canOpen ? (
            <span className="app-badge rounded-full px-2 py-1 text-[11px]">
              Открыть
            </span>
          ) : null}
        </div>
        <p className="mt-2 text-sm font-semibold text-[var(--foreground)]">
          {post?.title || "Новость не найдена"}
        </p>
        {post?.created_at ? (
          <p className="app-text-muted mt-0.5 text-xs">
            {formatDateTime(post.created_at)}
          </p>
        ) : null}
      </div>

      {postText ? (
        <p className="app-text-wrap line-clamp-4 whitespace-pre-wrap text-sm leading-5 text-[var(--foreground)]">
          {postText}
        </p>
      ) : null}

      <div className="mt-2 flex flex-wrap items-center gap-2">
        {post?.author ? (
          <span className="app-badge inline-flex max-w-full items-center gap-1 rounded-full px-2 py-1 text-[11px]">
            <span className="truncate">{displayUserName(post.author)}</span>
          </span>
        ) : null}
        {typeof post?.likes_count === "number" ? (
          <span className="app-badge rounded-full px-2 py-1 text-[11px]">
            {post.likes_count} лайк.
          </span>
        ) : null}
        {typeof post?.comments_count === "number" ? (
          <span className="app-badge rounded-full px-2 py-1 text-[11px]">
            {post.comments_count} комм.
          </span>
        ) : null}
        <span className="app-text-muted text-[11px]">
          Связал: {link.created_by ? displayUserName(link.created_by) : "не указано"}
        </span>
      </div>
    </>
  );

  return (
    <article className="app-surface-muted rounded-xl border border-[var(--border-subtle)] p-3">
      <div className="relative">
        {canOpen && link.object_url ? (
          <Link
            href={link.object_url}
            className="block rounded-lg pr-10 transition hover:bg-[var(--surface-elevated)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent-primary)]"
            title="Открыть связанную новость"
          >
            {mainContent}
          </Link>
        ) : (
          <div className="pr-10">
            {mainContent}
          </div>
        )}

        <button
          type="button"
          onClick={() => onUnlink(link.id)}
          disabled={disabled}
          className="app-icon-button absolute right-0 top-0 z-10 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg disabled:opacity-50"
          title="Убрать связь"
          aria-label="Убрать связь с новостью"
        >
          <Trash2 size={14} />
        </button>
      </div>
    </article>
  );
}

function LinkedMessageCard({
  link,
  onUnlink,
  disabled,
}: {
  link: TaskLinkedMessage;
  onUnlink: (linkId: number) => void;
  disabled?: boolean;
}) {
  const message = link.message;
  const attachmentsCount = message?.attachments?.length || 0;
  const canOpen = Boolean(link.can_open && link.object_url);
  const mainContent = (
    <>
      <div className="mb-2 min-w-0">
        <div className="flex flex-wrap items-center gap-2">
          <span className="app-pill inline-flex items-center gap-1.5 rounded-full px-2 py-1 text-xs font-medium">
            <MessageSquare size={12} />
            Сообщение
          </span>
          {message?.is_edited ? (
            <span className="app-badge rounded-full px-2 py-1 text-[11px]">
              Изменено
            </span>
          ) : null}
          {canOpen ? (
            <span className="app-badge rounded-full px-2 py-1 text-[11px]">
              Открыть
            </span>
          ) : null}
        </div>
        <p className="mt-2 text-sm font-semibold text-[var(--foreground)]">
          {message?.author_name || "Автор не указан"}
        </p>
        {getMessageCreatedLabel(message) ? (
          <p className="app-text-muted mt-0.5 text-xs">
            {getMessageCreatedLabel(message)}
          </p>
        ) : null}
      </div>

      {message?.is_deleted ? (
        <p className="app-text-muted text-sm italic">Сообщение удалено</p>
      ) : (
        <p className="app-text-wrap whitespace-pre-wrap text-sm leading-5 text-[var(--foreground)]">
          {message?.content || (attachmentsCount > 0 ? "Сообщение с вложениями" : "Сообщение без текста")}
        </p>
      )}

      <p className="app-text-muted mt-2 text-[11px]">
        Связал: {link.created_by ? displayUserName(link.created_by) : "не указано"}
      </p>
    </>
  );

  return (
    <article className="app-surface-muted rounded-xl border border-[var(--border-subtle)] p-3">
      <div className="relative">
        {canOpen && link.object_url ? (
          <Link
            href={link.object_url}
            className="block rounded-lg pr-10 transition hover:bg-[var(--surface-elevated)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent-primary)]"
            title="Открыть связанное сообщение"
          >
            {mainContent}
          </Link>
        ) : (
          <div className="pr-10">
            {mainContent}
          </div>
        )}

        <button
          type="button"
          onClick={() => onUnlink(link.id)}
          disabled={disabled}
          className="app-icon-button absolute right-0 top-0 z-10 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg disabled:opacity-50"
          title="Убрать связь"
          aria-label="Убрать связь с сообщением"
        >
          <Trash2 size={14} />
        </button>
      </div>

      {attachmentsCount > 0 ? (
        <div className="mt-2 flex flex-wrap gap-1.5">
          {message?.attachments?.map((attachment) => (
            <a
              key={attachment.id}
              href={resolveMediaUrl(attachment.file_url)}
              target="_blank"
              rel="noreferrer"
              className="app-badge inline-flex max-w-full items-center gap-1 rounded-full px-2 py-1 text-[11px]"
            >
              <Paperclip size={11} />
              <span className="truncate">{attachment.file_name}</span>
            </a>
          ))}
        </div>
      ) : null}
    </article>
  );
}

function LinkedCalendarEventCard({
  link,
  onUnlink,
  disabled,
}: {
  link: TaskLinkedCalendarEvent;
  onUnlink: (linkId: number) => void;
  disabled?: boolean;
}) {
  const event = link.event;
  const canOpen = Boolean(link.can_open && link.object_url);
  const timeLabel = event
    ? `${formatDateTime(event.start)} - ${formatDateTime(event.end)}`
    : "";
  const mainContent = (
    <>
      <div className="mb-2 min-w-0">
        <div className="flex flex-wrap items-center gap-2">
          <span className="app-pill inline-flex items-center gap-1.5 rounded-full px-2 py-1 text-xs font-medium">
            <CalendarDays size={12} />
            Событие
          </span>
          {canOpen ? (
            <span className="app-badge rounded-full px-2 py-1 text-[11px]">
              Открыть
            </span>
          ) : null}
        </div>
        <p className="mt-2 text-sm font-semibold text-[var(--foreground)]">
          {event?.title || "Событие не найдено"}
        </p>
        {timeLabel ? (
          <p className="app-text-muted mt-0.5 text-xs">
            {timeLabel}
          </p>
        ) : null}
      </div>

      {event?.description ? (
        <p className="app-text-wrap whitespace-pre-wrap text-sm leading-5 text-[var(--foreground)]">
          {event.description}
        </p>
      ) : null}

      <div className="mt-2 flex flex-wrap items-center gap-2">
        {event?.calendar_name ? (
          <span className="app-badge inline-flex items-center gap-1 rounded-full px-2 py-1 text-[11px]">
            <span
              className="h-2 w-2 rounded-full"
              style={{ backgroundColor: event.color_event || "#38bdf8" }}
            />
            {event.calendar_name}
          </span>
        ) : null}
        <span className="app-text-muted text-[11px]">
          Связал: {link.created_by ? displayUserName(link.created_by) : "не указано"}
        </span>
      </div>
    </>
  );

  return (
    <article className="app-surface-muted rounded-xl border border-[var(--border-subtle)] p-3">
      <div className="relative">
        {canOpen && link.object_url ? (
          <Link
            href={link.object_url}
            className="block rounded-lg pr-10 transition hover:bg-[var(--surface-elevated)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent-primary)]"
            title="Открыть связанное событие"
          >
            {mainContent}
          </Link>
        ) : (
          <div className="pr-10">
            {mainContent}
          </div>
        )}

        <button
          type="button"
          onClick={() => onUnlink(link.id)}
          disabled={disabled}
          className="app-icon-button absolute right-0 top-0 z-10 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg disabled:opacity-50"
          title="Убрать связь"
          aria-label="Убрать связь с событием"
        >
          <Trash2 size={14} />
        </button>
      </div>
    </article>
  );
}

function LinkedDocumentCard({
  link,
  onUnlink,
  disabled,
}: {
  link: TaskLinkedDocument;
  onUnlink: (linkId: number) => void;
  disabled?: boolean;
}) {
  const document = link.document;
  const canOpen = Boolean(link.can_open && link.object_url);
  const mainContent = (
    <>
      <div className="mb-2 min-w-0">
        <div className="flex flex-wrap items-center gap-2">
          <span className="app-pill inline-flex items-center gap-1.5 rounded-full px-2 py-1 text-xs font-medium">
            <FileText size={12} />
            Документ
          </span>
          {document?.is_regulation ? (
            <span className="app-selected app-accent-text inline-flex items-center gap-1.5 rounded-full px-2 py-1 text-[11px] font-medium">
              Регламент
            </span>
          ) : null}
          {canOpen ? (
            <span className="app-badge rounded-full px-2 py-1 text-[11px]">
              Открыть
            </span>
          ) : null}
        </div>
        <p className="mt-2 text-sm font-semibold text-[var(--foreground)]">
          {document?.title || "Документ не найден"}
        </p>
        {document?.uploaded_at || document?.created_at ? (
          <p className="app-text-muted mt-0.5 text-xs">
            {formatDate(document.uploaded_at || document.created_at)}
          </p>
        ) : null}
      </div>

      {document?.description ? (
        <p className="app-text-wrap whitespace-pre-wrap text-sm leading-5 text-[var(--foreground)]">
          {document.description}
        </p>
      ) : null}

      <div className="mt-2 flex flex-wrap items-center gap-2">
        {document?.folder_path ? (
          <span className="app-badge inline-flex max-w-full items-center gap-1 rounded-full px-2 py-1 text-[11px]">
            <span className="truncate">{document.folder_path}</span>
          </span>
        ) : null}
        {document?.file_name ? (
          <span className="app-badge inline-flex max-w-full items-center gap-1 rounded-full px-2 py-1 text-[11px]">
            <Paperclip size={11} />
            <span className="truncate">{document.file_name}</span>
          </span>
        ) : null}
        <span className="app-text-muted text-[11px]">
          Связал: {link.created_by ? displayUserName(link.created_by) : "не указано"}
        </span>
      </div>
    </>
  );

  return (
    <article className="app-surface-muted rounded-xl border border-[var(--border-subtle)] p-3">
      <div className="relative">
        {canOpen && link.object_url ? (
          <Link
            href={link.object_url}
            className="block rounded-lg pr-10 transition hover:bg-[var(--surface-elevated)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent-primary)]"
            title="Открыть связанный документ"
          >
            {mainContent}
          </Link>
        ) : (
          <div className="pr-10">
            {mainContent}
          </div>
        )}

        <button
          type="button"
          onClick={() => onUnlink(link.id)}
          disabled={disabled}
          className="app-icon-button absolute right-0 top-0 z-10 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg disabled:opacity-50"
          title="Убрать связь"
          aria-label="Убрать связь с документом"
        >
          <Trash2 size={14} />
        </button>
      </div>
    </article>
  );
}

function LinkedRequestCard({
  link,
  onUnlink,
  disabled,
}: {
  link: TaskLinkedRequest;
  onUnlink: (linkId: number) => void;
  disabled?: boolean;
}) {
  const request = link.request;
  const canOpen = Boolean(link.can_open && link.object_url);
  const periodLabel = request?.date_from
    ? `${formatDate(request.date_from)}${request.date_to ? ` - ${formatDate(request.date_to)}` : ""}`
    : "";
  const mainContent = (
    <>
      <div className="mb-2 min-w-0">
        <div className="flex flex-wrap items-center gap-2">
          <span className="app-pill inline-flex items-center gap-1.5 rounded-full px-2 py-1 text-xs font-medium">
            <FileSignature size={12} />
            Заявление
          </span>
          {request?.status_display ? (
            <span className="app-badge rounded-full px-2 py-1 text-[11px]">
              {request.status_display}
            </span>
          ) : null}
          {canOpen ? (
            <span className="app-badge rounded-full px-2 py-1 text-[11px]">
              Открыть
            </span>
          ) : null}
        </div>
        <p className="mt-2 text-sm font-semibold text-[var(--foreground)]">
          {request?.display_title || request?.title || "Заявление не найдено"}
        </p>
        {periodLabel ? (
          <p className="app-text-muted mt-0.5 text-xs">
            {periodLabel}
          </p>
        ) : null}
      </div>

      {request?.comment ? (
        <p className="app-text-wrap whitespace-pre-wrap text-sm leading-5 text-[var(--foreground)]">
          {request.comment}
        </p>
      ) : null}

      <div className="mt-2 flex flex-wrap items-center gap-2">
        {request?.type_display ? (
          <span className="app-badge inline-flex max-w-full items-center gap-1 rounded-full px-2 py-1 text-[11px]">
            <span className="truncate">{request.type_display}</span>
          </span>
        ) : null}
        {request?.employee ? (
          <span className="app-badge inline-flex max-w-full items-center gap-1 rounded-full px-2 py-1 text-[11px]">
            <UserRound size={11} />
            <span className="truncate">{displayUserName(request.employee)}</span>
          </span>
        ) : null}
        <span className="app-text-muted text-[11px]">
          Связал: {link.created_by ? displayUserName(link.created_by) : "не указано"}
        </span>
      </div>
    </>
  );

  return (
    <article className="app-surface-muted rounded-xl border border-[var(--border-subtle)] p-3">
      <div className="relative">
        {canOpen && link.object_url ? (
          <Link
            href={link.object_url}
            className="block rounded-lg pr-10 transition hover:bg-[var(--surface-elevated)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent-primary)]"
            title="Открыть связанное заявление"
          >
            {mainContent}
          </Link>
        ) : (
          <div className="pr-10">
            {mainContent}
          </div>
        )}

        <button
          type="button"
          onClick={() => onUnlink(link.id)}
          disabled={disabled}
          className="app-icon-button absolute right-0 top-0 z-10 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg disabled:opacity-50"
          title="Убрать связь"
          aria-label="Убрать связь с заявлением"
        >
          <Trash2 size={14} />
        </button>
      </div>
    </article>
  );
}

function LinkedProcurementRequestCard({
  link,
  onUnlink,
  disabled,
}: {
  link: TaskLinkedProcurementRequest;
  onUnlink: (linkId: number) => void;
  disabled?: boolean;
}) {
  const request = link.procurement_request;
  const canOpen = Boolean(link.can_open && link.object_url);
  const amountLabel = request?.total_cost ? formatMoney(request.total_cost) : "";
  const mainContent = (
    <>
      <div className="mb-2 min-w-0">
        <div className="flex flex-wrap items-center gap-2">
          <span className="app-pill inline-flex items-center gap-1.5 rounded-full px-2 py-1 text-xs font-medium">
            <ShoppingCart size={12} />
            Закупка
          </span>
          {request?.status_display ? (
            <span className="app-badge rounded-full px-2 py-1 text-[11px]">
              {request.status_display}
            </span>
          ) : null}
          {request?.urgency_display ? (
            <span className="app-badge rounded-full px-2 py-1 text-[11px]">
              {request.urgency_display} срочность
            </span>
          ) : null}
          {canOpen ? (
            <span className="app-badge rounded-full px-2 py-1 text-[11px]">
              Открыть
            </span>
          ) : null}
        </div>
        <p className="mt-2 text-sm font-semibold text-[var(--foreground)]">
          {request?.title || "Заявка на закупку не найдена"}
        </p>
        {request?.created_at ? (
          <p className="app-text-muted mt-0.5 text-xs">
            {formatDate(request.created_at)}
          </p>
        ) : null}
      </div>

      {request?.description ? (
        <p className="app-text-wrap whitespace-pre-wrap text-sm leading-5 text-[var(--foreground)]">
          {request.description}
        </p>
      ) : null}

      <div className="mt-2 flex flex-wrap items-center gap-2">
        {request?.department_name ? (
          <span className="app-badge inline-flex max-w-full items-center gap-1 rounded-full px-2 py-1 text-[11px]">
            <span className="truncate">{request.department_name}</span>
          </span>
        ) : null}
        {request?.processing_department_name ? (
          <span className="app-badge inline-flex max-w-full items-center gap-1 rounded-full px-2 py-1 text-[11px]">
            <span className="truncate">{request.processing_department_name}</span>
          </span>
        ) : null}
        {amountLabel ? (
          <span className="app-badge inline-flex max-w-full items-center gap-1 rounded-full px-2 py-1 text-[11px]">
            {amountLabel}
          </span>
        ) : null}
        {request?.items_count ? (
          <span className="app-badge inline-flex max-w-full items-center gap-1 rounded-full px-2 py-1 text-[11px]">
            {request.items_count} поз.
          </span>
        ) : null}
        {request?.requestor ? (
          <span className="app-badge inline-flex max-w-full items-center gap-1 rounded-full px-2 py-1 text-[11px]">
            <UserRound size={11} />
            <span className="truncate">{displayUserName(request.requestor)}</span>
          </span>
        ) : null}
        <span className="app-text-muted text-[11px]">
          Связал: {link.created_by ? displayUserName(link.created_by) : "не указано"}
        </span>
      </div>
    </>
  );

  return (
    <article className="app-surface-muted rounded-xl border border-[var(--border-subtle)] p-3">
      <div className="relative">
        {canOpen && link.object_url ? (
          <Link
            href={link.object_url}
            className="block rounded-lg pr-10 transition hover:bg-[var(--surface-elevated)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent-primary)]"
            title="Открыть связанную закупку"
          >
            {mainContent}
          </Link>
        ) : (
          <div className="pr-10">
            {mainContent}
          </div>
        )}

        <button
          type="button"
          onClick={() => onUnlink(link.id)}
          disabled={disabled}
          className="app-icon-button absolute right-0 top-0 z-10 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg disabled:opacity-50"
          title="Убрать связь"
          aria-label="Убрать связь с закупкой"
        >
          <Trash2 size={14} />
        </button>
      </div>
    </article>
  );
}

function LinkedEmployeeCard({
  link,
  onUnlink,
  disabled,
}: {
  link: TaskLinkedEmployee;
  onUnlink: (linkId: number) => void;
  disabled?: boolean;
}) {
  const employee = link.employee;
  const canOpen = Boolean(link.can_open && link.object_url);
  const fullName = employee
    ? (
        employee.display_name ||
        employee.full_name ||
        `${employee.last_name || ""} ${employee.first_name || ""} ${employee.patronymic || ""}`.trim() ||
        employee.email ||
        `Сотрудник #${employee.id}`
      )
    : "Сотрудник не найден";
  const departmentNames = (employee?.departments || [])
    .map((department) => department.name)
    .filter(Boolean);
  const mainContent = (
    <>
      <div className="mb-2 min-w-0">
        <div className="flex flex-wrap items-center gap-2">
          <span className="app-pill inline-flex items-center gap-1.5 rounded-full px-2 py-1 text-xs font-medium">
            <UserRound size={12} />
            Сотрудник
          </span>
          {employee?.personnel_state ? (
            <span className="app-badge rounded-full px-2 py-1 text-[11px]">
              {employee.personnel_state.label || employee.personnel_state.status}
            </span>
          ) : null}
          {canOpen ? (
            <span className="app-badge rounded-full px-2 py-1 text-[11px]">
              Открыть
            </span>
          ) : null}
        </div>
        <p className="mt-2 text-sm font-semibold text-[var(--foreground)]">
          {fullName}
        </p>
        {employee?.position?.name ? (
          <p className="app-text-muted mt-0.5 text-xs">
            {employee.position.name}
          </p>
        ) : null}
      </div>

      <div className="mt-2 flex flex-wrap items-center gap-2">
        {departmentNames.slice(0, 2).map((department) => (
          <span
            key={department}
            className="app-badge inline-flex max-w-full items-center gap-1 rounded-full px-2 py-1 text-[11px]"
          >
            <span className="truncate">{department}</span>
          </span>
        ))}
        {employee?.email ? (
          <span className="app-badge inline-flex max-w-full items-center gap-1 rounded-full px-2 py-1 text-[11px]">
            <span className="truncate">{employee.email}</span>
          </span>
        ) : null}
        <span className="app-text-muted text-[11px]">
          Связал: {link.created_by ? displayUserName(link.created_by) : "не указано"}
        </span>
      </div>
    </>
  );

  return (
    <article className="app-surface-muted rounded-xl border border-[var(--border-subtle)] p-3">
      <div className="relative">
        {canOpen && link.object_url ? (
          <Link
            href={link.object_url}
            className="block rounded-lg pr-10 transition hover:bg-[var(--surface-elevated)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent-primary)]"
            title="Открыть профиль сотрудника"
          >
            {mainContent}
          </Link>
        ) : (
          <div className="pr-10">
            {mainContent}
          </div>
        )}

        <button
          type="button"
          onClick={() => onUnlink(link.id)}
          disabled={disabled}
          className="app-icon-button absolute right-0 top-0 z-10 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg disabled:opacity-50"
          title="Убрать связь"
          aria-label="Убрать связь с сотрудником"
        >
          <Trash2 size={14} />
        </button>
      </div>
    </article>
  );
}

function getLinkedGuestName(guest: TaskLinkedGuest["guest"] | NonNullable<TaskLinkedGuestVisit["guest_visit"]>["guest"] | null | undefined) {
  return (
    guest?.full_name ||
    `${guest?.last_name || ""} ${guest?.first_name || ""} ${guest?.patronymic || ""}`.trim() ||
    (guest?.id ? `Гость #${guest.id}` : "Гость не найден")
  );
}

function LinkedGuestCard({
  link,
  onUnlink,
  disabled,
}: {
  link: TaskLinkedGuest;
  onUnlink: (linkId: number) => void;
  disabled?: boolean;
}) {
  const guest = link.guest;
  const canOpen = Boolean(link.can_open && link.object_url);
  const mainContent = (
    <>
      <div className="mb-2 min-w-0">
        <div className="flex flex-wrap items-center gap-2">
          <span className="app-pill inline-flex items-center gap-1.5 rounded-full px-2 py-1 text-xs font-medium">
            <UserRound size={12} />
            Гость
          </span>
          {guest?.is_blacklisted ? (
            <span className="app-feedback-danger rounded-full px-2 py-1 text-[11px]">
              Черный список
            </span>
          ) : guest?.is_active ? (
            <span className="app-feedback-success rounded-full px-2 py-1 text-[11px]">
              Доступ активен
            </span>
          ) : null}
          {canOpen ? (
            <span className="app-badge rounded-full px-2 py-1 text-[11px]">
              Открыть
            </span>
          ) : null}
        </div>
        <p className="mt-2 text-sm font-semibold text-[var(--foreground)]">
          {getLinkedGuestName(guest)}
        </p>
        {guest?.organization ? (
          <p className="app-text-muted mt-0.5 text-xs">{guest.organization}</p>
        ) : null}
      </div>

      <div className="mt-2 flex flex-wrap items-center gap-2">
        {guest?.email ? (
          <span className="app-badge inline-flex max-w-full items-center gap-1 rounded-full px-2 py-1 text-[11px]">
            <span className="truncate">{guest.email}</span>
          </span>
        ) : null}
        {guest?.phone ? (
          <span className="app-badge inline-flex max-w-full items-center gap-1 rounded-full px-2 py-1 text-[11px]">
            <span className="truncate">{guest.phone}</span>
          </span>
        ) : null}
        <span className="app-text-muted text-[11px]">
          Связал: {link.created_by ? displayUserName(link.created_by) : "не указано"}
        </span>
      </div>
    </>
  );

  return (
    <article className="app-surface-muted rounded-xl border border-[var(--border-subtle)] p-3">
      <div className="relative">
        {canOpen && link.object_url ? (
          <Link
            href={link.object_url}
            className="block rounded-lg pr-10 transition hover:bg-[var(--surface-elevated)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent-primary)]"
            title="Открыть гостя"
          >
            {mainContent}
          </Link>
        ) : (
          <div className="pr-10">
            {mainContent}
          </div>
        )}

        <button
          type="button"
          onClick={() => onUnlink(link.id)}
          disabled={disabled}
          className="app-icon-button absolute right-0 top-0 z-10 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg disabled:opacity-50"
          title="Убрать связь"
          aria-label="Убрать связь с гостем"
        >
          <Trash2 size={14} />
        </button>
      </div>
    </article>
  );
}

function LinkedGuestVisitCard({
  link,
  onUnlink,
  disabled,
}: {
  link: TaskLinkedGuestVisit;
  onUnlink: (linkId: number) => void;
  disabled?: boolean;
}) {
  const visit = link.guest_visit;
  const canOpen = Boolean(link.can_open && link.object_url);
  const period = visit?.unlimited
    ? "Бессрочно"
    : `${formatDateTime(visit?.access_starts_at) || "—"} - ${formatDateTime(visit?.access_expires_at) || "—"}`;
  const mainContent = (
    <>
      <div className="mb-2 min-w-0">
        <div className="flex flex-wrap items-center gap-2">
          <span className="app-pill inline-flex items-center gap-1.5 rounded-full px-2 py-1 text-xs font-medium">
            <CalendarDays size={12} />
            Гостевой визит
          </span>
          {visit?.status_display ? (
            <span className="app-badge rounded-full px-2 py-1 text-[11px]">
              {visit.status_display}
            </span>
          ) : null}
          {canOpen ? (
            <span className="app-badge rounded-full px-2 py-1 text-[11px]">
              Открыть
            </span>
          ) : null}
        </div>
        <p className="mt-2 text-sm font-semibold text-[var(--foreground)]">
          {getLinkedGuestName(visit?.guest)}
        </p>
        {visit?.purpose ? (
          <p className="app-text-wrap app-text-muted mt-1 line-clamp-2 text-xs">
            {visit.purpose}
          </p>
        ) : null}
      </div>

      <div className="mt-2 flex flex-wrap items-center gap-2">
        <span className="app-badge inline-flex max-w-full items-center gap-1 rounded-full px-2 py-1 text-[11px]">
          <CalendarDays size={11} />
          <span className="truncate">{period}</span>
        </span>
        <span className="app-text-muted text-[11px]">
          Связал: {link.created_by ? displayUserName(link.created_by) : "не указано"}
        </span>
      </div>
    </>
  );

  return (
    <article className="app-surface-muted rounded-xl border border-[var(--border-subtle)] p-3">
      <div className="relative">
        {canOpen && link.object_url ? (
          <Link
            href={link.object_url}
            className="block rounded-lg pr-10 transition hover:bg-[var(--surface-elevated)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent-primary)]"
            title="Открыть заявку на гостевой визит"
          >
            {mainContent}
          </Link>
        ) : (
          <div className="pr-10">
            {mainContent}
          </div>
        )}

        <button
          type="button"
          onClick={() => onUnlink(link.id)}
          disabled={disabled}
          className="app-icon-button absolute right-0 top-0 z-10 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg disabled:opacity-50"
          title="Убрать связь"
          aria-label="Убрать связь с гостевым визитом"
        >
          <Trash2 size={14} />
        </button>
      </div>
    </article>
  );
}

function formatAttendanceHours(value: unknown) {
  const numeric = Number(value || 0);
  if (!Number.isFinite(numeric)) return "0";
  return Number.isInteger(numeric) ? String(numeric) : numeric.toFixed(1);
}

function LinkedAttendanceRecordCard({
  link,
  onUnlink,
  disabled,
}: {
  link: TaskLinkedAttendanceRecord;
  onUnlink: (linkId: number) => void;
  disabled?: boolean;
}) {
  const record = link.attendance_record;
  const canOpen = Boolean(link.can_open && link.object_url);
  const employeeName = record?.display_name
    || (record?.employee ? displayUserName(record.employee) : "")
    || "Сотрудник не указан";
  const issueLabels = [
    record?.is_late ? "Опоздание" : "",
    record?.is_early_leave ? "Ранний уход" : "",
    record?.is_underwork ? "Недоработка" : "",
    record?.is_overtime ? "Переработка" : "",
    record?.is_absent ? "Отсутствие" : "",
  ].filter(Boolean);
  const mainContent = (
    <>
      <div className="mb-2 min-w-0">
        <div className="flex flex-wrap items-center gap-2">
          <span className="app-pill inline-flex items-center gap-1.5 rounded-full px-2 py-1 text-xs font-medium">
            <CalendarDays size={12} />
            Посещаемость
          </span>
          {record?.personnel_status_label ? (
            <span className="app-badge rounded-full px-2 py-1 text-[11px]">
              {record.personnel_status_label}
            </span>
          ) : null}
          {canOpen ? (
            <span className="app-badge rounded-full px-2 py-1 text-[11px]">
              Открыть
            </span>
          ) : null}
        </div>
        <p className="mt-2 text-sm font-semibold text-[var(--foreground)]">
          {employeeName}
        </p>
        {record?.date ? (
          <p className="app-text-muted mt-0.5 text-xs">
            {formatDate(record.date)}
          </p>
        ) : null}
      </div>

      <div className="app-text-muted mt-2 flex flex-wrap items-center gap-2 text-[11px]">
        <span className="app-badge inline-flex max-w-full items-center gap-1 rounded-full px-2 py-1 text-[11px]">
          Приход: {record?.arrival_time || "Нет"}
        </span>
        <span className="app-badge inline-flex max-w-full items-center gap-1 rounded-full px-2 py-1 text-[11px]">
          Уход: {record?.departure_time || "Нет"}
        </span>
        <span className="app-badge inline-flex max-w-full items-center gap-1 rounded-full px-2 py-1 text-[11px]">
          Часы: {formatAttendanceHours(record?.work_hours)}
          {record?.expected_hours !== undefined ? ` / ${formatAttendanceHours(record.expected_hours)}` : ""}
        </span>
      </div>

      {issueLabels.length > 0 ? (
        <div className="mt-2 flex flex-wrap gap-1.5">
          {issueLabels.map((label) => (
            <span key={label} className="app-feedback-warning rounded-full px-2 py-1 text-[11px]">
              {label}
            </span>
          ))}
        </div>
      ) : null}

      <p className="app-text-muted mt-2 text-[11px]">
        Связал: {link.created_by ? displayUserName(link.created_by) : "не указано"}
      </p>
    </>
  );

  return (
    <article className="app-surface-muted rounded-xl border border-[var(--border-subtle)] p-3">
      <div className="relative">
        {canOpen && link.object_url ? (
          <Link
            href={link.object_url}
            className="block rounded-lg pr-10 transition hover:bg-[var(--surface-elevated)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent-primary)]"
            title="Открыть запись посещаемости"
          >
            {mainContent}
          </Link>
        ) : (
          <div className="pr-10">
            {mainContent}
          </div>
        )}

        <button
          type="button"
          onClick={() => onUnlink(link.id)}
          disabled={disabled}
          className="app-icon-button absolute right-0 top-0 z-10 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg disabled:opacity-50"
          title="Убрать связь"
          aria-label="Убрать связь с записью посещаемости"
        >
          <Trash2 size={14} />
        </button>
      </div>
    </article>
  );
}

function TaskExternalLinkCard({
  link,
  onDelete,
  disabled,
}: {
  link: TaskExternalLink;
  onDelete: (linkId: number) => void;
  disabled: boolean;
}) {
  return (
    <article className="app-surface-muted rounded-xl border border-[var(--border-subtle)] p-3">
      <div className="relative">
        <a
          href={link.url}
          target="_blank"
          rel="noreferrer"
          className="flex min-w-0 items-start gap-3 rounded-lg pr-10 transition hover:bg-[var(--surface-elevated)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent-primary)]"
          title="Открыть внешнюю ссылку"
        >
          <span className="app-selected flex h-8 w-8 shrink-0 items-center justify-center rounded-lg">
            <ExternalLinkIcon size={15} />
          </span>
          <span className="min-w-0 flex-1">
            <span className="block truncate text-sm font-semibold text-[var(--foreground)]">
              {link.title || getExternalLinkHost(link.url)}
            </span>
            <span className="app-text-muted mt-0.5 block truncate text-xs">
              {link.url}
            </span>
            <span className="app-text-muted mt-2 block text-[11px]">
              Добавил: {link.created_by ? displayUserName(link.created_by) : "не указано"}
            </span>
          </span>
        </a>
        <button
          type="button"
          onClick={() => onDelete(link.id)}
          disabled={disabled}
          className="app-icon-button absolute right-0 top-0 z-10 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg disabled:opacity-50"
          title="Удалить ссылку"
          aria-label={`Удалить ссылку ${link.title || link.url}`}
        >
          <Trash2 size={14} />
        </button>
      </div>
    </article>
  );
}

function TaskFormResourceRow({
  icon: Icon,
  title,
  meta,
  pending = false,
  onRemove,
}: {
  icon: LucideIcon;
  title: string;
  meta?: string;
  pending?: boolean;
  onRemove: () => void;
}) {
  return (
    <div className="flex min-w-0 items-center gap-2 border-b border-[var(--border-subtle)] px-3 py-2.5 last:border-b-0">
      <span className="app-selected flex h-8 w-8 shrink-0 items-center justify-center rounded-lg">
        <Icon size={15} />
      </span>
      <span className="min-w-0 flex-1">
        <span className="block truncate text-sm font-medium text-[var(--foreground)]">
          {title}
        </span>
        {meta ? (
          <span className="app-text-muted mt-0.5 block truncate text-[11px]">
            {meta}
          </span>
        ) : null}
      </span>
      {pending ? (
        <span className="app-badge shrink-0 rounded-full px-2 py-0.5 text-[10px]">
          новое
        </span>
      ) : null}
      <button
        type="button"
        onClick={onRemove}
        className="app-icon-button flex h-8 w-8 shrink-0 items-center justify-center rounded-lg"
        title="Убрать"
        aria-label={`Убрать ${title}`}
      >
        <Trash2 size={14} />
      </button>
    </div>
  );
}


function TaskChecklistFormRow({
  title,
  isCompleted,
  pending,
  disabled,
  onTitleChange,
  onCompletedChange,
  onRemove,
}: {
  title: string;
  isCompleted: boolean;
  pending?: boolean;
  disabled?: boolean;
  onTitleChange: (value: string) => void;
  onCompletedChange: (value: boolean) => void;
  onRemove: () => void;
}) {
  return (
    <div className="flex min-w-0 items-center gap-2 border-b border-[var(--border-subtle)] px-3 py-2 last:border-b-0">
      <input
        type="checkbox"
        checked={isCompleted}
        onChange={(event) => onCompletedChange(event.target.checked)}
        disabled={disabled}
        className="h-4 w-4 shrink-0 accent-sky-500"
        aria-label={isCompleted ? "Вернуть пункт в работу" : "Отметить пункт выполненным"}
      />
      <input
        value={title}
        onChange={(event) => onTitleChange(event.target.value)}
        disabled={disabled}
        className={`app-input min-w-0 flex-1 rounded-lg px-2.5 py-1.5 text-sm ${
          isCompleted ? "line-through opacity-70" : ""
        }`}
        aria-label="Текст пункта чек-листа"
      />
      {pending ? (
        <span className="app-badge shrink-0 rounded-full px-2 py-0.5 text-[10px]">
          новое
        </span>
      ) : null}
      <button
        type="button"
        onClick={onRemove}
        disabled={disabled}
        className="app-icon-button flex h-8 w-8 shrink-0 items-center justify-center rounded-lg text-[var(--danger-foreground)] disabled:opacity-50"
        title="Удалить пункт"
        aria-label={`Удалить пункт ${title}`}
      >
        <Trash2 size={14} />
      </button>
    </div>
  );
}


const activityFieldLabels: Record<string, string> = {
  title: "название",
  description: "описание",
  assignee_id: "исполнителя",
  priority: "срочность",
  due_date: "срок",
  label_ids: "метки",
};

function getActivityDetail(activity: TaskActivity): string {
  const metadata = activity.metadata || {};
  if (activity.action === "moved") {
    const fromColumn = typeof metadata.from_column === "string" ? metadata.from_column : "";
    const toColumn = typeof metadata.to_column === "string" ? metadata.to_column : "";
    if (fromColumn && toColumn) return `${fromColumn} -> ${toColumn}`;
  }
  if (activity.action === "updated") {
    const fields = Array.isArray(metadata.fields) ? metadata.fields : [];
    const labels = fields
      .map((field) => activityFieldLabels[String(field)] || String(field))
      .filter(Boolean);
    return labels.length > 0 ? `Изменено: ${labels.join(", ")}` : "Данные задачи обновлены";
  }
  if (activity.action === "linked" || activity.action === "unlinked") {
    const objectType = typeof metadata.object_type === "string" ? metadata.object_type : "Объект";
    const objectLabel = typeof metadata.object_label === "string" ? metadata.object_label : "";
    return objectLabel ? `${objectType}: ${objectLabel}` : `${objectType} #${activity.object_id || ""}`;
  }
  if (activity.action === "created") {
    const column = typeof metadata.column === "string" ? metadata.column : "";
    return column ? `Колонка: ${column}` : "";
  }
  if (
    activity.action === "attachment_added" ||
    activity.action === "attachment_removed"
  ) {
    return typeof metadata.file_name === "string" ? metadata.file_name : "Файл";
  }
  if (activity.action.startsWith("checklist_item_")) {
    return typeof metadata.item_title === "string"
      ? metadata.item_title
      : "Пункт чек-листа";
  }
  if (activity.action === "comment_edited") {
    const previousText = typeof metadata.previous_text === "string"
      ? metadata.previous_text
      : "";
    const commentText = typeof metadata.comment_text === "string"
      ? metadata.comment_text
      : "";
    if (previousText && commentText) {
      return `Было: ${previousText}\nСтало: ${commentText}`;
    }
  }
  if (activity.action === "comment_added" || activity.action === "comment_removed") {
    return typeof metadata.comment_text === "string"
      ? metadata.comment_text
      : `Комментарий #${activity.object_id || ""}`;
  }
  return "";
}

function TaskActivityCard({ activity }: { activity: TaskActivity }) {
  const detail = getActivityDetail(activity);
  return (
    <article className="app-surface-muted rounded-xl border border-[var(--border-subtle)] px-3 py-2.5">
      <div className="flex items-start gap-3">
        <span className="app-selected mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-lg">
          <History size={14} />
        </span>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
            <p className="text-sm font-semibold text-[var(--foreground)]">
              {activity.action_display || activity.action}
            </p>
            <span className="app-text-muted text-xs">
              {formatDateTime(activity.created_at)}
            </span>
          </div>
          <p className="app-text-muted mt-0.5 text-xs">
            {activity.actor ? displayUserName(activity.actor) : "Система"}
          </p>
          {detail ? (
              <p className="app-text-wrap mt-2 whitespace-pre-wrap text-xs text-[var(--foreground)]">
              {detail}
            </p>
          ) : null}
        </div>
      </div>
    </article>
  );
}

export default function TasksPage() {
  return (
    <Suspense fallback={<AppShell><div className="app-surface rounded-2xl p-8 text-center"><p className="app-text-muted text-sm">Загрузка задач...</p></div></AppShell>}>
      <TasksPageContent />
    </Suspense>
  );
}

function TasksPageContent() {
  const { user } = useUser();
  const searchParams = useSearchParams();
  const requestedBoardId = Number(searchParams.get("board") || "");
  const requestedTaskId = Number(searchParams.get("task") || "");
  const [boards, setBoards] = useState<TaskBoard[]>([]);
  const [board, setBoard] = useState<TaskBoard | null>(null);
  const [selectedBoardId, setSelectedBoardId] = useState<number | null>(null);
  const [employees, setEmployees] = useState<User[]>([]);
  const [departments, setDepartments] = useState<Department[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [claimingTaskId, setClaimingTaskId] = useState<number | null>(null);
  const [completingTaskId, setCompletingTaskId] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [onlyMine, setOnlyMine] = useState(false);
  const [desktopWideMode, setDesktopWideMode] = useState(false);
  const [selectedColumnTarget, setSelectedColumnTarget] = useState<number | "all">("all");
  const [activeTaskId, setActiveTaskId] = useState<number | null>(null);
  const [viewTaskId, setViewTaskId] = useState<number | null>(null);
  const [taskModalOpen, setTaskModalOpen] = useState(false);
  const [taskMenuOpen, setTaskMenuOpen] = useState(false);
  const [viewColumnMenuOpen, setViewColumnMenuOpen] = useState(false);
  const [cardMenuTaskId, setCardMenuTaskId] = useState<number | null>(null);
  const [boardModalOpen, setBoardModalOpen] = useState(false);
  const [boardMenuOpen, setBoardMenuOpen] = useState(false);
  const [boardActionsMenuOpen, setBoardActionsMenuOpen] = useState(false);
  const [columnModalOpen, setColumnModalOpen] = useState(false);
  const [form, setForm] = useState<TaskFormState>(emptyForm);
  const [boardForm, setBoardForm] = useState<BoardFormState>(emptyBoardForm);
  const [boardMemberSearch, setBoardMemberSearch] = useState("");
  const [boardDepartmentSearch, setBoardDepartmentSearch] = useState("");
  const [columnForm, setColumnForm] = useState<ColumnFormState>(emptyColumnForm);
  const [labelName, setLabelName] = useState("");
  const [labelColor, setLabelColor] = useState("#38bdf8");
  const [linkedObjectsOpen, setLinkedObjectsOpen] = useState(false);
  const [linkedPosts, setLinkedPosts] = useState<TaskLinkedPost[]>([]);
  const [linkedMessages, setLinkedMessages] = useState<TaskLinkedMessage[]>([]);
  const [linkedEvents, setLinkedEvents] = useState<TaskLinkedCalendarEvent[]>([]);
  const [linkedDocuments, setLinkedDocuments] = useState<TaskLinkedDocument[]>([]);
  const [linkedRequests, setLinkedRequests] = useState<TaskLinkedRequest[]>([]);
  const [linkedProcurementRequests, setLinkedProcurementRequests] = useState<TaskLinkedProcurementRequest[]>([]);
  const [linkedEmployees, setLinkedEmployees] = useState<TaskLinkedEmployee[]>([]);
  const [linkedGuests, setLinkedGuests] = useState<TaskLinkedGuest[]>([]);
  const [linkedGuestVisits, setLinkedGuestVisits] = useState<TaskLinkedGuestVisit[]>([]);
  const [linkedAttendanceRecords, setLinkedAttendanceRecords] = useState<TaskLinkedAttendanceRecord[]>([]);
  const [taskExternalLinks, setTaskExternalLinks] = useState<TaskExternalLink[]>([]);
  const [linkedObjectsLoading, setLinkedObjectsLoading] = useState(false);
  const [linkedItemModalOpen, setLinkedItemModalOpen] = useState(false);
  const [linkedItemMode, setLinkedItemMode] = useState<LinkedItemMode>("document");
  const [linkedItemTarget, setLinkedItemTarget] = useState<LinkedItemTarget>("view");
  const [linkedItemSearch, setLinkedItemSearch] = useState("");
  const [linkedItemCandidatesLoading, setLinkedItemCandidatesLoading] = useState(false);
  const [availableDocuments, setAvailableDocuments] = useState<Document[]>([]);
  const [availableEvents, setAvailableEvents] = useState<CalendarEvent[]>([]);
  const [externalLinkUrl, setExternalLinkUrl] = useState("");
  const [externalLinkTitle, setExternalLinkTitle] = useState("");
  const [taskFormFilesOpen, setTaskFormFilesOpen] = useState(false);
  const [taskFormLinksOpen, setTaskFormLinksOpen] = useState(false);
  const [taskFormChecklistOpen, setTaskFormChecklistOpen] = useState(false);
  const [taskFormChecklistDraft, setTaskFormChecklistDraft] = useState("");
  const [taskFormResourcesLoading, setTaskFormResourcesLoading] = useState(false);
  const [taskFormChecklistItems, setTaskFormChecklistItems] = useState<TaskChecklistItem[]>([]);
  const [taskFormPendingChecklistItems, setTaskFormPendingChecklistItems] = useState<TaskFormChecklistItemDraft[]>([]);
  const [taskFormRemovedChecklistItemIds, setTaskFormRemovedChecklistItemIds] = useState<number[]>([]);
  const [taskFormDirtyChecklistItemIds, setTaskFormDirtyChecklistItemIds] = useState<number[]>([]);
  const [taskFormAttachments, setTaskFormAttachments] = useState<TaskAttachment[]>([]);
  const [taskFormDocuments, setTaskFormDocuments] = useState<TaskLinkedDocument[]>([]);
  const [taskFormEvents, setTaskFormEvents] = useState<TaskLinkedCalendarEvent[]>([]);
  const [taskFormExternalLinks, setTaskFormExternalLinks] = useState<TaskExternalLink[]>([]);
  const [taskFormPendingFiles, setTaskFormPendingFiles] = useState<File[]>([]);
  const [taskFormPendingDocuments, setTaskFormPendingDocuments] = useState<Document[]>([]);
  const [taskFormPendingEvents, setTaskFormPendingEvents] = useState<CalendarEvent[]>([]);
  const [taskFormPendingExternalLinks, setTaskFormPendingExternalLinks] = useState<TaskFormExternalLinkDraft[]>([]);
  const [taskFormRemovedAttachmentIds, setTaskFormRemovedAttachmentIds] = useState<number[]>([]);
  const [taskFormRemovedDocumentLinkIds, setTaskFormRemovedDocumentLinkIds] = useState<number[]>([]);
  const [taskFormRemovedEventLinkIds, setTaskFormRemovedEventLinkIds] = useState<number[]>([]);
  const [taskFormRemovedExternalLinkIds, setTaskFormRemovedExternalLinkIds] = useState<number[]>([]);
  const [commentsOpen, setCommentsOpen] = useState(false);
  const [taskComments, setTaskComments] = useState<TaskComment[]>([]);
  const [editingCommentId, setEditingCommentId] = useState<number | null>(null);
  const [editingCommentDraft, setEditingCommentDraft] = useState("");
  const [taskCommentsLoading, setTaskCommentsLoading] = useState(false);
  const [commentDraft, setCommentDraft] = useState("");
  const [attachmentsOpen, setAttachmentsOpen] = useState(false);
  const [taskAttachments, setTaskAttachments] = useState<TaskAttachment[]>([]);
  const [taskAttachmentsLoading, setTaskAttachmentsLoading] = useState(false);
  const [taskAttachmentsUploading, setTaskAttachmentsUploading] = useState(false);
  const [checklistOpen, setChecklistOpen] = useState(false);
  const [taskChecklist, setTaskChecklist] = useState<TaskChecklistItem[]>([]);
  const [taskChecklistLoaded, setTaskChecklistLoaded] = useState(false);
  const [taskChecklistLoading, setTaskChecklistLoading] = useState(false);
  const [taskChecklistSaving, setTaskChecklistSaving] = useState(false);
  const [taskChecklistDraft, setTaskChecklistDraft] = useState("");
  const [activityOpen, setActivityOpen] = useState(false);
  const [taskActivities, setTaskActivities] = useState<TaskActivity[]>([]);
  const [taskActivityLoading, setTaskActivityLoading] = useState(false);
  const boardMenuRef = useRef<HTMLDivElement | null>(null);
  const boardActionsMenuRef = useRef<HTMLDivElement | null>(null);
  const taskMenuRef = useRef<HTMLDivElement | null>(null);
  const viewColumnMenuRef = useRef<HTMLDivElement | null>(null);
  const cardMenuRef = useRef<HTMLDivElement | null>(null);
  const selectedBoardIdRef = useRef<number | null>(null);
  const taskBoardSyncTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const boardScrollRef = useRef<HTMLDivElement | null>(null);
  const columnNodeRefs = useRef<Map<number, HTMLElement>>(new Map());
  const taskAttachmentInputRef = useRef<HTMLInputElement | null>(null);
  const taskFormAttachmentInputRef = useRef<HTMLInputElement | null>(null);
  const taskChecklistDraftRef = useRef<HTMLInputElement | null>(null);
  const taskFormChecklistDraftRef = useRef<HTMLInputElement | null>(null);
  const taskFormResourcesRequestRef = useRef(0);

  const sensors = useSensors(
    useSensor(PointerSensor, {
      activationConstraint: { distance: 8 },
    }),
  );

  useEffect(() => {
    if (!user?.id) return;
    setDesktopWideMode(
      window.localStorage.getItem(`${DESKTOP_WIDE_MODE_STORAGE_PREFIX}.${user.id}`) === "1",
    );
  }, [user?.id]);

  const changeDesktopWideMode = useCallback((enabled: boolean) => {
    setDesktopWideMode(enabled);
    if (user?.id) {
      window.localStorage.setItem(
        `${DESKTOP_WIDE_MODE_STORAGE_PREFIX}.${user.id}`,
        enabled ? "1" : "0",
      );
    }
  }, [user?.id]);

  const loadBoards = useCallback(async () => {
    const response = await apiClient.getTaskBoards();
    const results = response.results || response || [];
    setBoards(results);
    return results as TaskBoard[];
  }, []);

  const loadBoard = useCallback(async (boardId?: number | null) => {
    setError(null);
    const data = boardId
      ? await apiClient.getTaskBoard(boardId)
      : await apiClient.getDefaultTaskBoard();
    setBoard(data);
    setSelectedBoardId(data.id);
    return data;
  }, []);

  const loadTaskLinkedObjects = useCallback(async (taskId: number) => {
    setLinkedObjectsLoading(true);
    try {
      const [
        posts,
        messages,
        events,
        documents,
        requests,
        procurementRequests,
        employees,
        guests,
        guestVisits,
        attendanceRecords,
        externalLinks,
      ] = await Promise.all([
        apiClient.getTaskLinkedPosts(taskId),
        apiClient.getTaskLinkedMessages(taskId),
        apiClient.getTaskLinkedEvents(taskId),
        apiClient.getTaskLinkedDocuments(taskId),
        apiClient.getTaskLinkedRequests(taskId),
        apiClient.getTaskLinkedProcurementRequests(taskId),
        apiClient.getTaskLinkedEmployees(taskId),
        apiClient.getTaskLinkedGuests(taskId),
        apiClient.getTaskLinkedGuestVisits(taskId),
        apiClient.getTaskLinkedAttendanceRecords(taskId),
        apiClient.getTaskExternalLinks(taskId),
      ]);
      setLinkedPosts(posts);
      setLinkedMessages(messages);
      setLinkedEvents(events);
      setLinkedDocuments(documents);
      setLinkedRequests(requests);
      setLinkedProcurementRequests(procurementRequests);
      setLinkedEmployees(employees);
      setLinkedGuests(guests);
      setLinkedGuestVisits(guestVisits);
      setLinkedAttendanceRecords(attendanceRecords);
      setTaskExternalLinks(externalLinks);
    } catch (linksError) {
      setError(getTaskError(linksError, "Не удалось загрузить связанные объекты"));
    } finally {
      setLinkedObjectsLoading(false);
    }
  }, []);

  const loadTaskActivity = useCallback(async (taskId: number) => {
    setTaskActivityLoading(true);
    try {
      const data = await apiClient.getTaskActivity(taskId);
      setTaskActivities(data);
    } catch (activityError) {
      setError(getTaskError(activityError, "Не удалось загрузить историю задачи"));
    } finally {
      setTaskActivityLoading(false);
    }
  }, []);

  const loadTaskAttachments = useCallback(async (taskId: number) => {
    setTaskAttachmentsLoading(true);
    try {
      const data = await apiClient.getTaskAttachments(taskId);
      setTaskAttachments(data);
    } catch (attachmentsError) {
      setError(getTaskError(attachmentsError, "Не удалось загрузить файлы задачи"));
    } finally {
      setTaskAttachmentsLoading(false);
    }
  }, []);

  const loadTaskChecklist = useCallback(async (taskId: number) => {
    setTaskChecklistLoading(true);
    try {
      const data = await apiClient.getTaskChecklist(taskId);
      setTaskChecklist(data);
      setTaskChecklistLoaded(true);
    } catch (checklistError) {
      setError(getTaskError(checklistError, "Не удалось загрузить чек-лист"));
    } finally {
      setTaskChecklistLoading(false);
    }
  }, []);

  const clearTaskFormResources = useCallback(() => {
    setTaskFormFilesOpen(false);
    setTaskFormLinksOpen(false);
    setTaskFormChecklistOpen(false);
    setTaskFormChecklistDraft("");
    setTaskFormResourcesLoading(false);
    setTaskFormChecklistItems([]);
    setTaskFormPendingChecklistItems([]);
    setTaskFormRemovedChecklistItemIds([]);
    setTaskFormDirtyChecklistItemIds([]);
    setTaskFormAttachments([]);
    setTaskFormDocuments([]);
    setTaskFormEvents([]);
    setTaskFormExternalLinks([]);
    setTaskFormPendingFiles([]);
    setTaskFormPendingDocuments([]);
    setTaskFormPendingEvents([]);
    setTaskFormPendingExternalLinks([]);
    setTaskFormRemovedAttachmentIds([]);
    setTaskFormRemovedDocumentLinkIds([]);
    setTaskFormRemovedEventLinkIds([]);
    setTaskFormRemovedExternalLinkIds([]);
  }, []);

  const loadTaskFormResources = useCallback(async (taskId: number) => {
    const requestId = ++taskFormResourcesRequestRef.current;
    setTaskFormResourcesLoading(true);
    try {
      const [checklist, attachments, documents, events, externalLinks] = await Promise.all([
        apiClient.getTaskChecklist(taskId),
        apiClient.getTaskAttachments(taskId),
        apiClient.getTaskLinkedDocuments(taskId),
        apiClient.getTaskLinkedEvents(taskId),
        apiClient.getTaskExternalLinks(taskId),
      ]);
      if (requestId !== taskFormResourcesRequestRef.current) return;
      setTaskFormChecklistItems(checklist);
      setTaskFormAttachments(attachments);
      setTaskFormDocuments(documents);
      setTaskFormEvents(events);
      setTaskFormExternalLinks(externalLinks);
    } catch (resourcesError) {
      if (requestId === taskFormResourcesRequestRef.current) {
        setError(getTaskError(resourcesError, "Не удалось загрузить файлы и связи задачи"));
      }
    } finally {
      if (requestId === taskFormResourcesRequestRef.current) {
        setTaskFormResourcesLoading(false);
      }
    }
  }, []);

  const loadTaskComments = useCallback(async (taskId: number) => {
    setTaskCommentsLoading(true);
    try {
      const data = await apiClient.getTaskComments(taskId);
      setTaskComments(data);
    } catch (commentsError) {
      setError(getTaskError(commentsError, "Не удалось загрузить комментарии"));
    } finally {
      setTaskCommentsLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!linkedItemModalOpen || linkedItemMode === "external_link") {
      setLinkedItemCandidatesLoading(false);
      return;
    }

    let cancelled = false;
    const timer = window.setTimeout(async () => {
      setLinkedItemCandidatesLoading(true);
      try {
        const searchValue = linkedItemSearch.trim() || undefined;
        if (linkedItemMode === "document") {
          const response = await apiClient.getDocuments({
            search: searchValue,
            page_size: 100,
          });
          if (!cancelled) {
            setAvailableDocuments(extractApiResults<Document>(response));
          }
        } else {
          const response = await apiClient.getCalendarEvents({
            search: searchValue,
            page_size: 100,
          });
          if (!cancelled) {
            setAvailableEvents(extractApiResults<CalendarEvent>(response));
          }
        }
      } catch (candidatesError) {
        if (!cancelled) {
          setError(getTaskError(candidatesError, "Не удалось загрузить доступные объекты"));
        }
      } finally {
        if (!cancelled) setLinkedItemCandidatesLoading(false);
      }
    }, 250);

    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [linkedItemModalOpen, linkedItemMode, linkedItemSearch]);

  useEffect(() => {
    selectedBoardIdRef.current = selectedBoardId;
  }, [selectedBoardId]);

  const registerColumnNode = useCallback((columnId: number, node: HTMLElement | null) => {
    if (node) {
      columnNodeRefs.current.set(columnId, node);
    } else {
      columnNodeRefs.current.delete(columnId);
    }
  }, []);

  const scrollBoardToStart = useCallback(() => {
    boardScrollRef.current?.scrollTo({ left: 0, behavior: "smooth" });
  }, []);

  const scrollToColumn = useCallback((columnId: number) => {
    const container = boardScrollRef.current;
    const node = columnNodeRefs.current.get(columnId);
    if (!container || !node) return;

    const containerRect = container.getBoundingClientRect();
    const nodeRect = node.getBoundingClientRect();
    const targetLeft = container.scrollLeft + nodeRect.left - containerRect.left - 12;

    container.scrollTo({
      left: Math.max(0, targetLeft),
      behavior: "smooth",
    });
  }, []);

  const focusAllColumns = useCallback(() => {
    setSelectedColumnTarget("all");
    scrollBoardToStart();
  }, [scrollBoardToStart]);

  const focusColumn = useCallback((columnId: number) => {
    setSelectedColumnTarget(columnId);
    window.requestAnimationFrame(() => scrollToColumn(columnId));
  }, [scrollToColumn]);

  const syncTaskBoardState = useCallback(async (eventBoardId?: number | null) => {
    const currentBoardId = selectedBoardIdRef.current;
    try {
      const boardList = await loadBoards();

      if (!currentBoardId) {
        const nextBoard = eventBoardId
          ? boardList.find((item) => item.id === eventBoardId)
          : boardList[0];
        if (nextBoard) {
          await loadBoard(nextBoard.id);
        } else {
          await loadBoard(null);
          await loadBoards();
        }
        return;
      }

      const currentBoardAvailable = boardList.some(
        (item) => item.id === currentBoardId,
      );
      if (!currentBoardAvailable) {
        if (boardList[0]) {
          await loadBoard(boardList[0].id);
        } else {
          await loadBoard(null);
          await loadBoards();
        }
        setSearch("");
        setOnlyMine(false);
        setSelectedColumnTarget("all");
        return;
      }

      if (!eventBoardId || eventBoardId === currentBoardId) {
        await loadBoard(currentBoardId);
      }
    } catch (syncError) {
      setError(getTaskError(syncError, "Не удалось синхронизировать доску"));
    }
  }, [loadBoard, loadBoards]);

  useEffect(() => {
    if (typeof window === "undefined") return undefined;

    const unsubscribe = wsManager.subscribe((event) => {
      const data = event as TaskBoardSocketEvent;
      if (data.type !== "task_board_update") return;

      const boardId = Number(data.data?.board_id);
      if (!Number.isFinite(boardId) || boardId <= 0) return;

      const eventTaskId = Number(
        data.data?.task_id ?? (
          data.data?.model === "task" ? data.data?.object_id : undefined
        ),
      );
      if (
        data.data?.model === "checklist_item" &&
        checklistOpen &&
        viewTaskId &&
        eventTaskId === viewTaskId
      ) {
        void loadTaskChecklist(viewTaskId);
      }

      if (
        commentsOpen &&
        viewTaskId &&
        eventTaskId === viewTaskId &&
        (
          data.data?.event === "commented" ||
          data.data?.event === "comment_edited" ||
          data.data?.event === "comment_deleted"
        )
      ) {
        void loadTaskComments(viewTaskId);
      }

      if (activityOpen && viewTaskId && eventTaskId === viewTaskId) {
        void loadTaskActivity(viewTaskId);
      }

      if (taskBoardSyncTimerRef.current) {
        clearTimeout(taskBoardSyncTimerRef.current);
      }
      taskBoardSyncTimerRef.current = setTimeout(() => {
        taskBoardSyncTimerRef.current = null;
        void syncTaskBoardState(boardId);
      }, 250);
    });

    return () => {
      unsubscribe();
      if (taskBoardSyncTimerRef.current) {
        clearTimeout(taskBoardSyncTimerRef.current);
        taskBoardSyncTimerRef.current = null;
      }
    };
  }, [
    activityOpen,
    checklistOpen,
    commentsOpen,
    loadTaskActivity,
    loadTaskChecklist,
    loadTaskComments,
    syncTaskBoardState,
    viewTaskId,
  ]);

  useEffect(() => {
    let mounted = true;
    async function load() {
      setLoading(true);
      try {
        const [boardData, boardsData, employeesData, departmentsData] = await Promise.all([
          requestedBoardId > 0
            ? apiClient.getTaskBoard(requestedBoardId)
            : apiClient.getDefaultTaskBoard(),
          apiClient.getTaskBoards(),
          apiClient.getEmployees({ limit: 200, is_active: true, ordering: "last_name" }),
          apiClient.getDepartments({ limit: 200 }),
        ]);
        if (!mounted) return;
        const boardList = boardsData.results || boardsData || [];
        setBoards(boardList);
        setBoard(boardData);
        setSelectedBoardId(boardData.id);
        setEmployees(employeesData.results || employeesData || []);
        setDepartments(departmentsData.results || departmentsData || []);
        if (
          requestedTaskId > 0 &&
          (boardData.tasks || []).some((task: TaskCard) => task.id === requestedTaskId)
        ) {
          setViewTaskId(requestedTaskId);
          setSelectedColumnTarget("all");
          setOnlyMine(false);
          setSearch("");
        }
      } catch (loadError) {
        if (mounted) setError(getTaskError(loadError, "Не удалось загрузить доску"));
      } finally {
        if (mounted) setLoading(false);
      }
    }

    void load();
    return () => {
      mounted = false;
    };
  }, [requestedBoardId, requestedTaskId]);

  useEffect(() => {
    if (!boardMenuOpen) return undefined;

    function handlePointerDown(event: MouseEvent) {
      if (
        boardMenuRef.current &&
        !boardMenuRef.current.contains(event.target as Node)
      ) {
        setBoardMenuOpen(false);
      }
    }

    document.addEventListener("mousedown", handlePointerDown);
    return () => document.removeEventListener("mousedown", handlePointerDown);
  }, [boardMenuOpen]);

  useEffect(() => {
    if (!boardActionsMenuOpen) return undefined;

    function handlePointerDown(event: MouseEvent) {
      if (
        boardActionsMenuRef.current &&
        !boardActionsMenuRef.current.contains(event.target as Node)
      ) {
        setBoardActionsMenuOpen(false);
      }
    }

    document.addEventListener("mousedown", handlePointerDown);
    return () => document.removeEventListener("mousedown", handlePointerDown);
  }, [boardActionsMenuOpen]);

  useEffect(() => {
    if (!taskMenuOpen) return undefined;

    function handlePointerDown(event: MouseEvent) {
      if (
        taskMenuRef.current &&
        !taskMenuRef.current.contains(event.target as Node)
      ) {
        setTaskMenuOpen(false);
      }
    }

    document.addEventListener("mousedown", handlePointerDown);
    return () => document.removeEventListener("mousedown", handlePointerDown);
  }, [taskMenuOpen]);

  useEffect(() => {
    if (!viewColumnMenuOpen) return undefined;

    function handlePointerDown(event: MouseEvent) {
      if (
        viewColumnMenuRef.current &&
        !viewColumnMenuRef.current.contains(event.target as Node)
      ) {
        setViewColumnMenuOpen(false);
      }
    }

    document.addEventListener("mousedown", handlePointerDown);
    return () => document.removeEventListener("mousedown", handlePointerDown);
  }, [viewColumnMenuOpen]);

  useEffect(() => {
    if (cardMenuTaskId === null) return undefined;

    function handlePointerDown(event: MouseEvent) {
      if (
        cardMenuRef.current &&
        !cardMenuRef.current.contains(event.target as Node)
      ) {
        setCardMenuTaskId(null);
      }
    }

    document.addEventListener("mousedown", handlePointerDown);
    return () => document.removeEventListener("mousedown", handlePointerDown);
  }, [cardMenuTaskId]);

  const filteredBoardMembers = useMemo(() => {
    const query = boardMemberSearch.trim().toLowerCase();
    if (!query) return employees;
    return employees.filter((employee) => {
      const searchable = [
        displayUserName(employee),
        employee.email,
        employee.position?.name,
      ]
        .filter(Boolean)
        .join(" ")
        .toLowerCase();
      return searchable.includes(query);
    });
  }, [boardMemberSearch, employees]);

  const filteredBoardDepartments = useMemo(() => {
    const query = boardDepartmentSearch.trim().toLowerCase();
    if (!query) return departments;
    return departments.filter((department) => (
      department.name.toLowerCase().includes(query)
    ));
  }, [boardDepartmentSearch, departments]);

  const searchedTasks = useMemo(() => {
    const tasks = board?.tasks || [];
    const query = search.trim().toLowerCase();
    return tasks.filter((task) => {
      if (!query) return true;
      const assignee = task.assignee ? displayUserName(task.assignee).toLowerCase() : "";
      const labels = (task.labels || []).map((label) => label.name.toLowerCase()).join(" ");
      return (
        task.title.toLowerCase().includes(query) ||
        (task.description || "").toLowerCase().includes(query) ||
        assignee.includes(query) ||
        labels.includes(query)
      );
    });
  }, [board?.tasks, search]);

  const filteredTasks = useMemo(
    () => searchedTasks.filter((task) => !onlyMine || task.assignee?.id === user?.id),
    [onlyMine, searchedTasks, user?.id],
  );

  const tasksByColumn = useMemo(() => {
    const grouped = new Map<number, TaskCard[]>();
    for (const column of board?.columns || []) grouped.set(column.id, []);
    for (const task of filteredTasks) {
      const list = grouped.get(task.column) || [];
      list.push(task);
      grouped.set(task.column, list);
    }
    for (const list of grouped.values()) {
      list.sort((left, right) => left.position - right.position || left.id - right.id);
    }
    return grouped;
  }, [board?.columns, filteredTasks]);

  const activeColumns = useMemo(
    () => (board?.columns || []).filter((column) => !column.is_archived),
    [board?.columns],
  );

  const columnCounts = useMemo(() => {
    const counts = new Map<number, number>();
    for (const column of activeColumns) counts.set(column.id, 0);
    for (const task of filteredTasks) {
      counts.set(task.column, (counts.get(task.column) || 0) + 1);
    }
    return counts;
  }, [activeColumns, filteredTasks]);

  const mineCount = useMemo(
    () => searchedTasks.filter((task) => task.assignee?.id === user?.id).length,
    [searchedTasks, user?.id],
  );

  const activeDragTask = useMemo(
    () => (board?.tasks || []).find((task) => task.id === activeTaskId) || null,
    [activeTaskId, board?.tasks],
  );

  const viewTask = useMemo(
    () => (board?.tasks || []).find((task) => task.id === viewTaskId) || null,
    [board?.tasks, viewTaskId],
  );

  const viewTaskColumn = useMemo(
    () => activeColumns.find((column) => column.id === viewTask?.column) || null,
    [activeColumns, viewTask?.column],
  );
  const linkedObjectsCount = linkedPosts.length + linkedMessages.length + linkedEvents.length + linkedDocuments.length + linkedRequests.length + linkedProcurementRequests.length + linkedEmployees.length + linkedGuests.length + linkedGuestVisits.length + linkedAttendanceRecords.length + taskExternalLinks.length;
  const linkedObjectsBadgeCount = viewTask?.linked_objects_count ?? linkedObjectsCount;
  const commentsBadgeCount = viewTask?.comments_count ?? taskComments.length;
  const attachmentsBadgeCount = viewTask?.attachments_count ?? taskAttachments.length;
  const checklistBadgeTotal = taskChecklistLoaded
    ? taskChecklist.length
    : (viewTask?.checklist_total || 0);
  const checklistBadgeCompleted = taskChecklistLoaded
    ? taskChecklist.filter((item) => item.is_completed).length
    : (viewTask?.checklist_completed || 0);
  const taskFormChecklistTotal = taskFormChecklistItems.length + taskFormPendingChecklistItems.length;
  const taskFormChecklistCompleted = (
    taskFormChecklistItems.filter((item) => item.is_completed).length +
    taskFormPendingChecklistItems.filter((item) => item.is_completed).length
  );
  const taskFormChecklistHasInvalidTitle = [
    ...taskFormChecklistItems.map((item) => item.title),
    ...taskFormPendingChecklistItems.map((item) => item.title),
  ].some((title) => !title.trim());
  const taskFormAttachmentsCount = taskFormAttachments.length + taskFormPendingFiles.length;
  const taskFormLinksCount = (
    taskFormDocuments.length +
    taskFormEvents.length +
    taskFormExternalLinks.length +
    taskFormPendingDocuments.length +
    taskFormPendingEvents.length +
    taskFormPendingExternalLinks.length
  );

  useEffect(() => {
    if (
      selectedColumnTarget !== "all" &&
      !activeColumns.some((column) => column.id === selectedColumnTarget)
    ) {
      setSelectedColumnTarget("all");
    }
  }, [activeColumns, selectedColumnTarget]);

  useEffect(() => {
    if (!viewTaskId) {
      setLinkedPosts([]);
      setLinkedMessages([]);
      setLinkedEvents([]);
      setLinkedDocuments([]);
      setLinkedRequests([]);
      setLinkedProcurementRequests([]);
      setLinkedEmployees([]);
      setLinkedGuests([]);
      setLinkedGuestVisits([]);
      setLinkedAttendanceRecords([]);
      setTaskExternalLinks([]);
      setTaskActivities([]);
      setTaskComments([]);
      setTaskAttachments([]);
      setTaskChecklist([]);
      setTaskChecklistLoaded(false);
      setTaskChecklistDraft("");
      setCommentDraft("");
      setLinkedObjectsOpen(false);
      setCommentsOpen(false);
      setAttachmentsOpen(false);
      setChecklistOpen(false);
      setActivityOpen(false);
      setLinkedItemModalOpen(false);
      return;
    }

    if (linkedObjectsOpen) {
      void loadTaskLinkedObjects(viewTaskId);
    }
  }, [linkedObjectsOpen, loadTaskLinkedObjects, viewTask?.linked_objects_count, viewTaskId]);

  useEffect(() => {
    if (!viewTaskId || !commentsOpen) return;
    void loadTaskComments(viewTaskId);
  }, [commentsOpen, loadTaskComments, viewTask?.comments_count, viewTaskId]);

  useEffect(() => {
    if (!viewTaskId || !attachmentsOpen) return;
    void loadTaskAttachments(viewTaskId);
  }, [attachmentsOpen, loadTaskAttachments, viewTask?.attachments_count, viewTaskId]);

  useEffect(() => {
    if (!viewTaskId || !checklistOpen) return;
    void loadTaskChecklist(viewTaskId);
  }, [checklistOpen, loadTaskChecklist, viewTaskId]);

  useEffect(() => {
    if (!viewTaskId || !activityOpen) return;
    void loadTaskActivity(viewTaskId);
  }, [activityOpen, loadTaskActivity, viewTask?.updated_at, viewTaskId]);

  const openCreateTask = useCallback((columnId?: number) => {
    const firstColumn = board?.columns.find((column) => !column.is_archived);
    taskFormResourcesRequestRef.current += 1;
    clearTaskFormResources();
    setForm({
      ...emptyForm,
      column: columnId || firstColumn?.id || "",
    });
    setLabelName("");
    setLabelColor("#38bdf8");
    setTaskModalOpen(true);
  }, [board?.columns, clearTaskFormResources]);

  const openTaskView = useCallback((task: TaskCard) => {
    setViewTaskId(task.id);
    setTaskMenuOpen(false);
    setViewColumnMenuOpen(false);
    setLinkedObjectsOpen(false);
    setCommentsOpen(false);
    setAttachmentsOpen(false);
    setChecklistOpen(true);
    setActivityOpen(false);
    setLinkedMessages([]);
    setLinkedEvents([]);
    setLinkedDocuments([]);
    setLinkedRequests([]);
    setLinkedProcurementRequests([]);
    setLinkedEmployees([]);
    setLinkedGuests([]);
    setLinkedGuestVisits([]);
    setLinkedAttendanceRecords([]);
    setTaskComments([]);
    setEditingCommentId(null);
    setEditingCommentDraft("");
    setTaskAttachments([]);
    setTaskChecklist([]);
    setTaskChecklistLoaded(false);
    setTaskChecklistDraft("");
    setTaskActivities([]);
    setCommentDraft("");
    setCardMenuTaskId(null);
  }, []);

  const toggleCardTaskMenu = useCallback((taskId: number) => {
    setCardMenuTaskId((current) => (current === taskId ? null : taskId));
  }, []);

  const closeTaskView = useCallback(() => {
    if (saving || taskAttachmentsUploading || taskChecklistSaving) return;
    setViewTaskId(null);
    setTaskMenuOpen(false);
    setViewColumnMenuOpen(false);
    setLinkedMessages([]);
    setLinkedEvents([]);
    setLinkedDocuments([]);
    setLinkedRequests([]);
    setLinkedProcurementRequests([]);
    setLinkedEmployees([]);
    setLinkedGuests([]);
    setLinkedGuestVisits([]);
    setLinkedAttendanceRecords([]);
    setTaskComments([]);
    setEditingCommentId(null);
    setEditingCommentDraft("");
    setTaskAttachments([]);
    setTaskChecklist([]);
    setTaskChecklistLoaded(false);
    setTaskActivities([]);
    setLinkedObjectsOpen(false);
    setCommentsOpen(false);
    setAttachmentsOpen(false);
    setChecklistOpen(false);
    setActivityOpen(false);
    setCommentDraft("");
    setTaskChecklistDraft("");
  }, [saving, taskAttachmentsUploading, taskChecklistSaving]);

  const openEditTask = useCallback((task: TaskCard) => {
    taskFormResourcesRequestRef.current += 1;
    clearTaskFormResources();
    setForm({
      id: task.id,
      title: task.title,
      description: task.description || "",
      column: task.column,
      assignee_id: task.assignee?.id || "",
      priority: task.priority,
      due_date: task.due_date || "",
      label_ids: (task.labels || []).map((label) => label.id),
    });
    setLabelName("");
    setLabelColor("#38bdf8");
    setViewTaskId(null);
    setTaskMenuOpen(false);
    setViewColumnMenuOpen(false);
    setCardMenuTaskId(null);
    setTaskModalOpen(true);
    void loadTaskFormResources(task.id);
  }, [clearTaskFormResources, loadTaskFormResources]);

  const closeTaskModal = useCallback(() => {
    if (saving) return;
    taskFormResourcesRequestRef.current += 1;
    setTaskModalOpen(false);
    setForm(emptyForm);
    setLabelName("");
    clearTaskFormResources();
  }, [clearTaskFormResources, saving]);

  const openCreateBoard = useCallback(() => {
    setBoardForm(emptyBoardForm);
    setBoardMemberSearch("");
    setBoardDepartmentSearch("");
    setBoardActionsMenuOpen(false);
    setBoardModalOpen(true);
  }, []);

  const openEditBoard = useCallback(() => {
    if (!board) return;
    const memberIds = board.members || [];
    const departmentIds = board.departments || [];
    setBoardForm({
      id: board.id,
      name: board.name || "",
      description: board.description || "",
      access: board.access_scope || (
        memberIds.length > 0 || departmentIds.length > 0 ? "restricted" : "all"
      ),
      member_ids: memberIds,
      department_ids: departmentIds,
    });
    setBoardMemberSearch("");
    setBoardDepartmentSearch("");
    setBoardActionsMenuOpen(false);
    setBoardModalOpen(true);
  }, [board]);

  const closeBoardModal = useCallback(() => {
    if (saving) return;
    setBoardModalOpen(false);
    setBoardForm(emptyBoardForm);
    setBoardMemberSearch("");
    setBoardDepartmentSearch("");
  }, [saving]);

  const openCreateColumn = useCallback(() => {
    setColumnForm(emptyColumnForm);
    setColumnModalOpen(true);
  }, []);

  const closeColumnModal = useCallback(() => {
    if (saving) return;
    setColumnModalOpen(false);
    setColumnForm(emptyColumnForm);
  }, [saving]);

  const toggleBoardMember = useCallback((employeeId: number) => {
    setBoardForm((current) => ({
      ...current,
      member_ids: current.member_ids.includes(employeeId)
        ? current.member_ids.filter((id) => id !== employeeId)
        : [...current.member_ids, employeeId],
    }));
  }, []);

  const toggleBoardDepartment = useCallback((departmentId: number) => {
    setBoardForm((current) => ({
      ...current,
      department_ids: current.department_ids.includes(departmentId)
        ? current.department_ids.filter((id) => id !== departmentId)
        : [...current.department_ids, departmentId],
    }));
  }, []);

  const selectBoard = useCallback(async (boardId: number) => {
    if (!boardId || boardId === selectedBoardId) return;
    setLoading(true);
    setError(null);
    try {
      await loadBoard(boardId);
      setSearch("");
      setOnlyMine(false);
      setSelectedColumnTarget("all");
      setBoardMenuOpen(false);
    } catch (loadError) {
      setError(getTaskError(loadError, "Не удалось загрузить доску"));
    } finally {
      setLoading(false);
    }
  }, [loadBoard, selectedBoardId]);

  const refreshSelectedBoard = useCallback(async () => {
    if (!board) return;
    setBoardActionsMenuOpen(false);
    setLoading(true);
    setError(null);
    try {
      await Promise.all([loadBoards(), loadBoard(board.id)]);
    } catch (refreshError) {
      setError(getTaskError(refreshError, "Не удалось обновить доску"));
    } finally {
      setLoading(false);
    }
  }, [board, loadBoard, loadBoards]);

  const setDefaultSelectedBoard = useCallback(async () => {
    if (!board || saving || board.is_default_for_current_user) return;

    setBoardActionsMenuOpen(false);
    setSaving(true);
    setError(null);
    try {
      const updatedBoard = await apiClient.setDefaultTaskBoard(board.id);
      setBoard((current) => (
        current
          ? {
              ...current,
              is_default_for_current_user: current.id === updatedBoard.id,
            }
          : current
      ));
      setBoards((current) => current.map((item) => ({
        ...item,
        is_default_for_current_user: item.id === updatedBoard.id,
      })));
    } catch (defaultError) {
      setError(getTaskError(defaultError, "Не удалось выбрать доску по умолчанию"));
    } finally {
      setSaving(false);
    }
  }, [board, saving]);

  const deleteSelectedBoard = useCallback(async () => {
    if (!board || saving) return;
    if (!window.confirm(`Удалить доску "${board.name}"? Все задачи этой доски будут удалены.`)) return;

    setBoardActionsMenuOpen(false);
    setSaving(true);
    setError(null);
    try {
      await apiClient.deleteTaskBoard(board.id);
      const nextBoards = await loadBoards();
      const nextBoard = nextBoards.find((item) => item.id !== board.id) || null;
      await loadBoard(nextBoard?.id || null);
      await loadBoards();
      setSearch("");
      setOnlyMine(false);
      setSelectedColumnTarget("all");
    } catch (deleteError) {
      setError(getTaskError(deleteError, "Не удалось удалить доску"));
    } finally {
      setSaving(false);
    }
  }, [board, loadBoard, loadBoards, saving]);

  const saveBoard = useCallback(async () => {
    if (!boardForm.name.trim()) return;
    setSaving(true);
    setError(null);
    try {
      const payload = {
        name: boardForm.name.trim(),
        description: boardForm.description.trim(),
        access_scope: boardForm.access,
        members: boardForm.access === "restricted" ? boardForm.member_ids : [],
        departments: boardForm.access === "restricted" ? boardForm.department_ids : [],
      };
      const saved = boardForm.id
        ? await apiClient.updateTaskBoard(boardForm.id, payload)
        : await apiClient.createTaskBoard(payload);
      await loadBoards();
      await loadBoard(saved.id);
      setBoardModalOpen(false);
      setBoardForm(emptyBoardForm);
      setSearch("");
      setOnlyMine(false);
      setSelectedColumnTarget("all");
    } catch (saveError) {
      setError(getTaskError(saveError, "Не удалось создать доску"));
    } finally {
      setSaving(false);
    }
  }, [
    boardForm.access,
    boardForm.department_ids,
    boardForm.description,
    boardForm.id,
    boardForm.member_ids,
    boardForm.name,
    loadBoard,
    loadBoards,
  ]);

  const saveColumn = useCallback(async () => {
    if (!board || !columnForm.name.trim()) return;
    setSaving(true);
    setError(null);
    try {
      const maxPosition = Math.max(
        0,
        ...(board.columns || []).map((column) => column.position || 0),
      );
      await apiClient.createTaskColumn({
        board: board.id,
        name: columnForm.name.trim(),
        color: columnForm.color,
        is_done: columnForm.is_done,
        position: maxPosition + 1000,
      });
      await loadBoard(board.id);
      setColumnModalOpen(false);
      setColumnForm(emptyColumnForm);
    } catch (saveError) {
      setError(getTaskError(saveError, "Не удалось создать колонку"));
    } finally {
      setSaving(false);
    }
  }, [board, columnForm.color, columnForm.is_done, columnForm.name, loadBoard]);

  const persistTaskFormResources = useCallback(async (taskId: number) => {
    for (const itemId of [...taskFormRemovedChecklistItemIds]) {
      await apiClient.deleteTaskChecklistItem(taskId, itemId);
      setTaskFormRemovedChecklistItemIds((current) => current.filter((id) => id !== itemId));
    }

    for (const itemId of [...taskFormDirtyChecklistItemIds]) {
      const item = taskFormChecklistItems.find((currentItem) => currentItem.id === itemId);
      if (!item) continue;
      const updated = await apiClient.updateTaskChecklistItem(taskId, item.id, {
        title: item.title.trim(),
        is_completed: item.is_completed,
      });
      setTaskFormDirtyChecklistItemIds((current) => current.filter((id) => id !== itemId));
      setTaskFormChecklistItems((current) => current.map((currentItem) => (
        currentItem.id === updated.id ? updated : currentItem
      )));
    }

    for (const item of [...taskFormPendingChecklistItems]) {
      const created = await apiClient.addTaskChecklistItem(taskId, {
        title: item.title.trim(),
        position: item.position,
        is_completed: item.is_completed,
      });
      setTaskFormPendingChecklistItems((current) => (
        current.filter((currentItem) => currentItem.key !== item.key)
      ));
      setTaskFormChecklistItems((current) => [...current, created]);
    }

    for (const attachmentId of [...taskFormRemovedAttachmentIds]) {
      await apiClient.deleteTaskAttachment(taskId, attachmentId);
      setTaskFormRemovedAttachmentIds((current) => (
        current.filter((id) => id !== attachmentId)
      ));
    }

    for (const linkId of [...taskFormRemovedDocumentLinkIds]) {
      await apiClient.unlinkTaskDocument(taskId, linkId);
      setTaskFormRemovedDocumentLinkIds((current) => current.filter((id) => id !== linkId));
    }

    for (const linkId of [...taskFormRemovedEventLinkIds]) {
      await apiClient.unlinkTaskCalendarEvent(taskId, linkId);
      setTaskFormRemovedEventLinkIds((current) => current.filter((id) => id !== linkId));
    }

    for (const linkId of [...taskFormRemovedExternalLinkIds]) {
      await apiClient.deleteTaskExternalLink(taskId, linkId);
      setTaskFormRemovedExternalLinkIds((current) => current.filter((id) => id !== linkId));
    }

    for (const document of [...taskFormPendingDocuments]) {
      const linked = await apiClient.linkTaskDocument(taskId, document.id);
      setTaskFormPendingDocuments((current) => current.filter((item) => item.id !== document.id));
      setTaskFormDocuments((current) => (
        current.some((item) => item.id === linked.id) ? current : [...current, linked]
      ));
    }

    for (const event of [...taskFormPendingEvents]) {
      const linked = await apiClient.linkTaskCalendarEvent(taskId, event.id);
      setTaskFormPendingEvents((current) => current.filter((item) => item.id !== event.id));
      setTaskFormEvents((current) => (
        current.some((item) => item.id === linked.id) ? current : [...current, linked]
      ));
    }

    for (const link of [...taskFormPendingExternalLinks]) {
      const created = await apiClient.addTaskExternalLink(taskId, {
        url: link.url,
        title: link.title || undefined,
      });
      setTaskFormPendingExternalLinks((current) => (
        current.filter((item) => item.key !== link.key)
      ));
      setTaskFormExternalLinks((current) => (
        current.some((item) => item.id === created.id) ? current : [...current, created]
      ));
    }

    for (const file of [...taskFormPendingFiles]) {
      const uploaded = await apiClient.uploadTaskAttachments(taskId, [file]);
      setTaskFormPendingFiles((current) => current.filter((item) => item !== file));
      setTaskFormAttachments((current) => [...current, ...uploaded]);
    }
  }, [
    taskFormChecklistItems,
    taskFormDirtyChecklistItemIds,
    taskFormPendingDocuments,
    taskFormPendingEvents,
    taskFormPendingExternalLinks,
    taskFormPendingFiles,
    taskFormPendingChecklistItems,
    taskFormRemovedAttachmentIds,
    taskFormRemovedChecklistItemIds,
    taskFormRemovedDocumentLinkIds,
    taskFormRemovedEventLinkIds,
    taskFormRemovedExternalLinkIds,
  ]);

  const saveTask = useCallback(async () => {
    if (!board || !form.title.trim() || !form.column || taskFormChecklistHasInvalidTitle) return;
    setSaving(true);
    setError(null);
    const payload = {
      board: board.id,
      column: Number(form.column),
      title: form.title.trim(),
      description: form.description.trim(),
      assignee_id: form.assignee_id || null,
      priority: form.priority,
      due_date: form.due_date || null,
      label_ids: form.label_ids,
    };
    let savedTaskId = form.id || null;
    let primaryDataSaved = false;
    try {
      const savedTask = form.id
        ? await apiClient.updateTask(form.id, payload)
        : await apiClient.createTask(payload);
      savedTaskId = savedTask.id;
      primaryDataSaved = true;
      if (!form.id) {
        setForm((current) => ({ ...current, id: savedTask.id }));
      }

      await persistTaskFormResources(savedTask.id);
      await loadBoard(board.id);
      closeTaskModal();
    } catch (saveError) {
      if (primaryDataSaved && savedTaskId) {
        try {
          await loadBoard(board.id);
        } catch {
          // Исходная ошибка сохранения ресурса важнее ошибки обновления доски.
        }
        setError(getTaskError(
          saveError,
          "Основные данные сохранены, но не удалось сохранить чек-лист, файлы или связи",
        ));
      } else {
        setError(getTaskError(saveError, "Не удалось сохранить задачу"));
      }
    } finally {
      setSaving(false);
    }
  }, [
    board,
    closeTaskModal,
    form,
    loadBoard,
    persistTaskFormResources,
    taskFormChecklistHasInvalidTitle,
  ]);

  const createLabel = useCallback(async () => {
    if (!board || !labelName.trim()) return;
    setSaving(true);
    setError(null);
    try {
      const label = await apiClient.createTaskLabel({
        board: board.id,
        name: labelName.trim(),
        color: labelColor,
      });
      setBoard((current) => current ? {
        ...current,
        labels: [...current.labels, label],
      } : current);
      setForm((current) => ({
        ...current,
        label_ids: [...current.label_ids, label.id],
      }));
      setLabelName("");
    } catch (labelError) {
      setError(getTaskError(labelError, "Не удалось создать метку"));
    } finally {
      setSaving(false);
    }
  }, [board, labelColor, labelName]);

  const toggleLabel = useCallback((labelId: number) => {
    setForm((current) => ({
      ...current,
      label_ids: current.label_ids.includes(labelId)
        ? current.label_ids.filter((id) => id !== labelId)
        : [...current.label_ids, labelId],
    }));
  }, []);

  const deleteTask = useCallback(async (task: TaskCard) => {
    if (!board || saving) return;
    if (!window.confirm(`Удалить задачу "${task.title}"?`)) return;

    setSaving(true);
    setError(null);
    try {
      await apiClient.deleteTask(task.id);
      if (viewTaskId === task.id) setViewTaskId(null);
      setTaskMenuOpen(false);
      setCardMenuTaskId(null);
      await loadBoard(board.id);
    } catch (deleteError) {
      setError(getTaskError(deleteError, "Не удалось удалить задачу"));
    } finally {
      setSaving(false);
    }
  }, [board, loadBoard, saving, viewTaskId]);

  const deleteViewedTask = useCallback(async () => {
    if (!viewTask) return;
    await deleteTask(viewTask);
  }, [deleteTask, viewTask]);

  const uploadViewedTaskAttachments = useCallback(async (files: File[]) => {
    if (!board || !viewTask || taskAttachmentsUploading || files.length === 0) return;

    setTaskAttachmentsUploading(true);
    setError(null);
    try {
      const created = await apiClient.uploadTaskAttachments(viewTask.id, files);
      setTaskAttachments((current) => [...current, ...created]);
      await loadBoard(board.id);
      if (activityOpen) await loadTaskActivity(viewTask.id);
    } catch (attachmentError) {
      setError(getTaskError(attachmentError, "Не удалось загрузить файлы"));
    } finally {
      setTaskAttachmentsUploading(false);
    }
  }, [activityOpen, board, loadBoard, loadTaskActivity, taskAttachmentsUploading, viewTask]);

  const downloadViewedTaskAttachment = useCallback(async (attachment: TaskAttachment) => {
    if (!viewTask) return;
    setError(null);
    try {
      const { blob, filename } = await apiClient.downloadTaskAttachment(
        viewTask.id,
        attachment,
      );
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);
    } catch (attachmentError) {
      setError(getTaskError(attachmentError, "Не удалось скачать файл"));
    }
  }, [viewTask]);

  const deleteViewedTaskAttachment = useCallback(async (attachment: TaskAttachment) => {
    if (!board || !viewTask || taskAttachmentsUploading) return;
    if (!window.confirm(`Удалить файл "${attachment.file_name}"?`)) return;

    setTaskAttachmentsUploading(true);
    setError(null);
    try {
      await apiClient.deleteTaskAttachment(viewTask.id, attachment.id);
      setTaskAttachments((current) => current.filter((item) => item.id !== attachment.id));
      await loadBoard(board.id);
      if (activityOpen) await loadTaskActivity(viewTask.id);
    } catch (attachmentError) {
      setError(getTaskError(attachmentError, "Не удалось удалить файл"));
    } finally {
      setTaskAttachmentsUploading(false);
    }
  }, [activityOpen, board, loadBoard, loadTaskActivity, taskAttachmentsUploading, viewTask]);

  const addViewedTaskChecklistItem = useCallback(async () => {
    const title = taskChecklistDraft.trim();
    if (!board || !viewTask || !title || taskChecklistSaving) return;

    setTaskChecklistSaving(true);
    setError(null);
    try {
      const created = await apiClient.addTaskChecklistItem(viewTask.id, { title });
      setTaskChecklist((current) => [
        ...current.filter((item) => item.id !== created.id),
        created,
      ].sort((left, right) => left.position - right.position || left.id - right.id));
      setTaskChecklistLoaded(true);
      setTaskChecklistDraft("");
      await loadBoard(board.id);
      if (activityOpen) await loadTaskActivity(viewTask.id);
      window.requestAnimationFrame(() => taskChecklistDraftRef.current?.focus());
    } catch (checklistError) {
      setError(getTaskError(checklistError, "Не удалось добавить пункт чек-листа"));
    } finally {
      setTaskChecklistSaving(false);
    }
  }, [
    activityOpen,
    board,
    loadBoard,
    loadTaskActivity,
    taskChecklistDraft,
    taskChecklistSaving,
    viewTask,
  ]);

  const toggleViewedTaskChecklistItem = useCallback(async (item: TaskChecklistItem) => {
    if (!board || !viewTask || taskChecklistSaving) return;

    setTaskChecklistSaving(true);
    setError(null);
    try {
      const updated = await apiClient.updateTaskChecklistItem(viewTask.id, item.id, {
        is_completed: !item.is_completed,
      });
      setTaskChecklist((current) => current.map((currentItem) => (
        currentItem.id === updated.id ? updated : currentItem
      )));
      setTaskChecklistLoaded(true);
      await loadBoard(board.id);
      if (activityOpen) await loadTaskActivity(viewTask.id);
    } catch (checklistError) {
      setError(getTaskError(checklistError, "Не удалось изменить пункт чек-листа"));
    } finally {
      setTaskChecklistSaving(false);
    }
  }, [activityOpen, board, loadBoard, loadTaskActivity, taskChecklistSaving, viewTask]);

  const deleteViewedTaskChecklistItem = useCallback(async (item: TaskChecklistItem) => {
    if (!board || !viewTask || taskChecklistSaving) return;

    setTaskChecklistSaving(true);
    setError(null);
    try {
      await apiClient.deleteTaskChecklistItem(viewTask.id, item.id);
      setTaskChecklist((current) => current.filter((currentItem) => currentItem.id !== item.id));
      setTaskChecklistLoaded(true);
      await loadBoard(board.id);
      if (activityOpen) await loadTaskActivity(viewTask.id);
    } catch (checklistError) {
      setError(getTaskError(checklistError, "Не удалось удалить пункт чек-листа"));
    } finally {
      setTaskChecklistSaving(false);
    }
  }, [activityOpen, board, loadBoard, loadTaskActivity, taskChecklistSaving, viewTask]);

  const addTaskFormChecklistItem = useCallback(() => {
    const title = taskFormChecklistDraft.trim();
    if (!title) return;
    const maxPosition = Math.max(
      0,
      ...taskFormChecklistItems.map((item) => item.position),
      ...taskFormPendingChecklistItems.map((item) => item.position),
    );
    setTaskFormPendingChecklistItems((current) => [
      ...current,
      {
        key: `checklist-${Date.now()}-${Math.random().toString(36).slice(2)}`,
        title,
        position: maxPosition + 1000,
        is_completed: false,
      },
    ]);
    setTaskFormChecklistDraft("");
    setTaskFormChecklistOpen(true);
    window.requestAnimationFrame(() => taskFormChecklistDraftRef.current?.focus());
  }, [taskFormChecklistDraft, taskFormChecklistItems, taskFormPendingChecklistItems]);

  const updateExistingTaskFormChecklistItem = useCallback((
    itemId: number,
    patch: Partial<Pick<TaskChecklistItem, "title" | "is_completed">>,
  ) => {
    setTaskFormChecklistItems((current) => current.map((item) => (
      item.id === itemId ? { ...item, ...patch } : item
    )));
    setTaskFormDirtyChecklistItemIds((current) => (
      current.includes(itemId) ? current : [...current, itemId]
    ));
  }, []);

  const updatePendingTaskFormChecklistItem = useCallback((
    key: string,
    patch: Partial<Pick<TaskFormChecklistItemDraft, "title" | "is_completed">>,
  ) => {
    setTaskFormPendingChecklistItems((current) => current.map((item) => (
      item.key === key ? { ...item, ...patch } : item
    )));
  }, []);

  const removeExistingTaskFormChecklistItem = useCallback((item: TaskChecklistItem) => {
    setTaskFormChecklistItems((current) => current.filter((currentItem) => currentItem.id !== item.id));
    setTaskFormRemovedChecklistItemIds((current) => (
      current.includes(item.id) ? current : [...current, item.id]
    ));
    setTaskFormDirtyChecklistItemIds((current) => current.filter((id) => id !== item.id));
  }, []);

  const addFilesToTaskForm = useCallback((files: File[]) => {
    if (files.length === 0) return;
    setTaskFormFilesOpen(true);
    setTaskFormPendingFiles((current) => {
      const keys = new Set(
        current.map((file) => `${file.name}:${file.size}:${file.lastModified}`),
      );
      return [
        ...current,
        ...files.filter((file) => {
          const key = `${file.name}:${file.size}:${file.lastModified}`;
          if (keys.has(key)) return false;
          keys.add(key);
          return true;
        }),
      ];
    });
  }, []);

  const removeExistingTaskFormAttachment = useCallback((attachment: TaskAttachment) => {
    setTaskFormAttachments((current) => current.filter((item) => item.id !== attachment.id));
    setTaskFormRemovedAttachmentIds((current) => [...current, attachment.id]);
  }, []);

  const removeExistingTaskFormDocument = useCallback((link: TaskLinkedDocument) => {
    setTaskFormDocuments((current) => current.filter((item) => item.id !== link.id));
    setTaskFormRemovedDocumentLinkIds((current) => [...current, link.id]);
  }, []);

  const removeExistingTaskFormEvent = useCallback((link: TaskLinkedCalendarEvent) => {
    setTaskFormEvents((current) => current.filter((item) => item.id !== link.id));
    setTaskFormRemovedEventLinkIds((current) => [...current, link.id]);
  }, []);

  const removeExistingTaskFormExternalLink = useCallback((link: TaskExternalLink) => {
    setTaskFormExternalLinks((current) => current.filter((item) => item.id !== link.id));
    setTaskFormRemovedExternalLinkIds((current) => [...current, link.id]);
  }, []);

  const openLinkedItemModalForView = useCallback(() => {
    if (!viewTask) return;
    setLinkedItemTarget("view");
    setLinkedItemMode("document");
    setLinkedItemSearch("");
    setExternalLinkUrl("");
    setExternalLinkTitle("");
    setLinkedObjectsOpen(true);
    setLinkedItemModalOpen(true);
  }, [viewTask]);

  const openLinkedItemModalForForm = useCallback(() => {
    if (!taskModalOpen) return;
    setLinkedItemTarget("form");
    setLinkedItemMode("document");
    setLinkedItemSearch("");
    setExternalLinkUrl("");
    setExternalLinkTitle("");
    setTaskFormLinksOpen(true);
    setLinkedItemModalOpen(true);
  }, [taskModalOpen]);

  const closeLinkedItemModal = useCallback(() => {
    if (saving) return;
    setLinkedItemModalOpen(false);
    setLinkedItemSearch("");
    setExternalLinkUrl("");
    setExternalLinkTitle("");
  }, [saving]);

  const refreshViewedTaskLinks = useCallback(async () => {
    if (!board || !viewTask) return;
    await Promise.all([
      loadTaskLinkedObjects(viewTask.id),
      loadBoard(board.id),
    ]);
    if (activityOpen) await loadTaskActivity(viewTask.id);
  }, [activityOpen, board, loadBoard, loadTaskActivity, loadTaskLinkedObjects, viewTask]);

  const linkDocumentToViewedTask = useCallback(async (documentId: number) => {
    if (!viewTask || saving) return;
    setSaving(true);
    setError(null);
    try {
      await apiClient.linkTaskDocument(viewTask.id, documentId);
      await refreshViewedTaskLinks();
      setLinkedItemModalOpen(false);
    } catch (linkError) {
      setError(getTaskError(linkError, "Не удалось связать документ с задачей"));
    } finally {
      setSaving(false);
    }
  }, [refreshViewedTaskLinks, saving, viewTask]);

  const linkEventToViewedTask = useCallback(async (eventId: number) => {
    if (!viewTask || saving) return;
    setSaving(true);
    setError(null);
    try {
      await apiClient.linkTaskCalendarEvent(viewTask.id, eventId);
      await refreshViewedTaskLinks();
      setLinkedItemModalOpen(false);
    } catch (linkError) {
      setError(getTaskError(linkError, "Не удалось связать событие с задачей"));
    } finally {
      setSaving(false);
    }
  }, [refreshViewedTaskLinks, saving, viewTask]);

  const addExternalLinkToViewedTask = useCallback(async () => {
    if (!viewTask || saving) return;
    const url = normalizeExternalUrl(externalLinkUrl);
    if (!url) return;

    setSaving(true);
    setError(null);
    try {
      await apiClient.addTaskExternalLink(viewTask.id, {
        url,
        title: externalLinkTitle.trim() || undefined,
      });
      await refreshViewedTaskLinks();
      setLinkedItemModalOpen(false);
      setExternalLinkUrl("");
      setExternalLinkTitle("");
    } catch (linkError) {
      setError(getTaskError(linkError, "Не удалось добавить ссылку"));
    } finally {
      setSaving(false);
    }
  }, [externalLinkTitle, externalLinkUrl, refreshViewedTaskLinks, saving, viewTask]);

  const addDocumentToTaskForm = useCallback((document: Document) => {
    const isExisting = taskFormDocuments.some((link) => link.document_id === document.id);
    const isPending = taskFormPendingDocuments.some((item) => item.id === document.id);
    if (isExisting || isPending) return;
    setTaskFormPendingDocuments((current) => [...current, document]);
    setTaskFormLinksOpen(true);
    setLinkedItemModalOpen(false);
  }, [taskFormDocuments, taskFormPendingDocuments]);

  const addEventToTaskForm = useCallback((event: CalendarEvent) => {
    const isExisting = taskFormEvents.some((link) => link.event_id === event.id);
    const isPending = taskFormPendingEvents.some((item) => item.id === event.id);
    if (isExisting || isPending) return;
    setTaskFormPendingEvents((current) => [...current, event]);
    setTaskFormLinksOpen(true);
    setLinkedItemModalOpen(false);
  }, [taskFormEvents, taskFormPendingEvents]);

  const addExternalLinkToTaskForm = useCallback(() => {
    const url = normalizeExternalUrl(externalLinkUrl);
    if (!url) return;
    const duplicate = (
      taskFormExternalLinks.some((link) => link.url === url) ||
      taskFormPendingExternalLinks.some((link) => link.url === url)
    );
    if (duplicate) {
      setError("Эта ссылка уже добавлена к задаче");
      return;
    }

    setTaskFormPendingExternalLinks((current) => [
      ...current,
      {
        key: `${Date.now()}-${current.length}`,
        url,
        title: externalLinkTitle.trim(),
      },
    ]);
    setTaskFormLinksOpen(true);
    setLinkedItemModalOpen(false);
    setExternalLinkUrl("");
    setExternalLinkTitle("");
  }, [
    externalLinkTitle,
    externalLinkUrl,
    taskFormExternalLinks,
    taskFormPendingExternalLinks,
  ]);

  const deleteExternalLinkFromViewedTask = useCallback(async (linkId: number) => {
    if (!viewTask || saving) return;
    if (!window.confirm("Удалить ссылку из задачи?")) return;

    setSaving(true);
    setError(null);
    try {
      await apiClient.deleteTaskExternalLink(viewTask.id, linkId);
      await refreshViewedTaskLinks();
    } catch (linkError) {
      setError(getTaskError(linkError, "Не удалось удалить ссылку"));
    } finally {
      setSaving(false);
    }
  }, [refreshViewedTaskLinks, saving, viewTask]);

  const addViewedTaskComment = useCallback(async () => {
    if (!board || !viewTask || saving || !commentDraft.trim()) return;

    setSaving(true);
    setError(null);
    try {
      const created = await apiClient.addTaskComment(viewTask.id, commentDraft.trim());
      setTaskComments((current) => [
        ...current.filter((comment) => comment.id !== created.id),
        created,
      ]);
      setCommentDraft("");
      await loadBoard(board.id);
      if (activityOpen) await loadTaskActivity(viewTask.id);
    } catch (commentError) {
      setError(getTaskError(commentError, "Не удалось добавить комментарий"));
    } finally {
      setSaving(false);
    }
  }, [activityOpen, board, commentDraft, loadBoard, loadTaskActivity, saving, viewTask]);

  const beginEditingViewedTaskComment = useCallback((comment: TaskComment) => {
    setEditingCommentId(comment.id);
    setEditingCommentDraft(comment.text);
  }, []);

  const cancelEditingViewedTaskComment = useCallback(() => {
    setEditingCommentId(null);
    setEditingCommentDraft("");
  }, []);

  const updateViewedTaskComment = useCallback(async () => {
    const text = editingCommentDraft.trim();
    if (!viewTask || !editingCommentId || !text || saving) return;

    setSaving(true);
    setError(null);
    try {
      const updated = await apiClient.updateTaskComment(viewTask.id, editingCommentId, text);
      setTaskComments((current) => current.map((comment) => (
        comment.id === updated.id ? updated : comment
      )));
      setEditingCommentId(null);
      setEditingCommentDraft("");
      if (activityOpen) await loadTaskActivity(viewTask.id);
    } catch (commentError) {
      setError(getTaskError(commentError, "Не удалось изменить комментарий"));
    } finally {
      setSaving(false);
    }
  }, [activityOpen, editingCommentDraft, editingCommentId, loadTaskActivity, saving, viewTask]);

  const deleteViewedTaskComment = useCallback(async (commentId: number) => {
    if (!board || !viewTask || saving) return;

    setSaving(true);
    setError(null);
    try {
      await apiClient.deleteTaskComment(viewTask.id, commentId);
      setTaskComments((current) => current.filter((comment) => comment.id !== commentId));
      if (editingCommentId === commentId) {
        setEditingCommentId(null);
        setEditingCommentDraft("");
      }
      await loadBoard(board.id);
      if (activityOpen) await loadTaskActivity(viewTask.id);
    } catch (commentError) {
      setError(getTaskError(commentError, "Не удалось удалить комментарий"));
    } finally {
      setSaving(false);
    }
  }, [activityOpen, board, editingCommentId, loadBoard, loadTaskActivity, saving, viewTask]);

  const unlinkPostFromViewedTask = useCallback(async (linkId: number) => {
    if (!board || !viewTask || saving) return;

    setSaving(true);
    setError(null);
    try {
      await apiClient.unlinkTaskPost(viewTask.id, linkId);
      await loadTaskLinkedObjects(viewTask.id);
      await loadBoard(board.id);
      if (activityOpen) await loadTaskActivity(viewTask.id);
    } catch (unlinkError) {
      setError(getTaskError(unlinkError, "Не удалось убрать связь с новостью"));
    } finally {
      setSaving(false);
    }
  }, [activityOpen, board, loadBoard, loadTaskActivity, loadTaskLinkedObjects, saving, viewTask]);

  const unlinkMessageFromViewedTask = useCallback(async (linkId: number) => {
    if (!board || !viewTask || saving) return;

    setSaving(true);
    setError(null);
    try {
      await apiClient.unlinkTaskMessage(viewTask.id, linkId);
      await loadTaskLinkedObjects(viewTask.id);
      await loadBoard(board.id);
      if (activityOpen) await loadTaskActivity(viewTask.id);
    } catch (unlinkError) {
      setError(getTaskError(unlinkError, "Не удалось убрать связь с сообщением"));
    } finally {
      setSaving(false);
    }
  }, [activityOpen, board, loadBoard, loadTaskActivity, loadTaskLinkedObjects, saving, viewTask]);

  const unlinkEventFromViewedTask = useCallback(async (linkId: number) => {
    if (!board || !viewTask || saving) return;

    setSaving(true);
    setError(null);
    try {
      await apiClient.unlinkTaskCalendarEvent(viewTask.id, linkId);
      await loadTaskLinkedObjects(viewTask.id);
      await loadBoard(board.id);
      if (activityOpen) await loadTaskActivity(viewTask.id);
    } catch (unlinkError) {
      setError(getTaskError(unlinkError, "Не удалось убрать связь с событием"));
    } finally {
      setSaving(false);
    }
  }, [activityOpen, board, loadBoard, loadTaskActivity, loadTaskLinkedObjects, saving, viewTask]);

  const unlinkDocumentFromViewedTask = useCallback(async (linkId: number) => {
    if (!board || !viewTask || saving) return;

    setSaving(true);
    setError(null);
    try {
      await apiClient.unlinkTaskDocument(viewTask.id, linkId);
      await loadTaskLinkedObjects(viewTask.id);
      await loadBoard(board.id);
      if (activityOpen) await loadTaskActivity(viewTask.id);
    } catch (unlinkError) {
      setError(getTaskError(unlinkError, "Не удалось убрать связь с документом"));
    } finally {
      setSaving(false);
    }
  }, [activityOpen, board, loadBoard, loadTaskActivity, loadTaskLinkedObjects, saving, viewTask]);

  const unlinkRequestFromViewedTask = useCallback(async (linkId: number) => {
    if (!board || !viewTask || saving) return;

    setSaving(true);
    setError(null);
    try {
      await apiClient.unlinkTaskRequest(viewTask.id, linkId);
      await loadTaskLinkedObjects(viewTask.id);
      await loadBoard(board.id);
      if (activityOpen) await loadTaskActivity(viewTask.id);
    } catch (unlinkError) {
      setError(getTaskError(unlinkError, "Не удалось убрать связь с заявлением"));
    } finally {
      setSaving(false);
    }
  }, [activityOpen, board, loadBoard, loadTaskActivity, loadTaskLinkedObjects, saving, viewTask]);

  const unlinkProcurementRequestFromViewedTask = useCallback(async (linkId: number) => {
    if (!board || !viewTask || saving) return;

    setSaving(true);
    setError(null);
    try {
      await apiClient.unlinkTaskProcurementRequest(viewTask.id, linkId);
      await loadTaskLinkedObjects(viewTask.id);
      await loadBoard(board.id);
      if (activityOpen) await loadTaskActivity(viewTask.id);
    } catch (unlinkError) {
      setError(getTaskError(unlinkError, "Не удалось убрать связь с закупкой"));
    } finally {
      setSaving(false);
    }
  }, [activityOpen, board, loadBoard, loadTaskActivity, loadTaskLinkedObjects, saving, viewTask]);

  const unlinkEmployeeFromViewedTask = useCallback(async (linkId: number) => {
    if (!board || !viewTask || saving) return;

    setSaving(true);
    setError(null);
    try {
      await apiClient.unlinkTaskEmployee(viewTask.id, linkId);
      await loadTaskLinkedObjects(viewTask.id);
      await loadBoard(board.id);
      if (activityOpen) await loadTaskActivity(viewTask.id);
    } catch (unlinkError) {
      setError(getTaskError(unlinkError, "Не удалось убрать связь с сотрудником"));
    } finally {
      setSaving(false);
    }
  }, [activityOpen, board, loadBoard, loadTaskActivity, loadTaskLinkedObjects, saving, viewTask]);

  const unlinkGuestFromViewedTask = useCallback(async (linkId: number) => {
    if (!board || !viewTask || saving) return;

    setSaving(true);
    setError(null);
    try {
      await apiClient.unlinkTaskGuest(viewTask.id, linkId);
      await loadTaskLinkedObjects(viewTask.id);
      await loadBoard(board.id);
      if (activityOpen) await loadTaskActivity(viewTask.id);
    } catch (unlinkError) {
      setError(getTaskError(unlinkError, "Не удалось убрать связь с гостем"));
    } finally {
      setSaving(false);
    }
  }, [activityOpen, board, loadBoard, loadTaskActivity, loadTaskLinkedObjects, saving, viewTask]);

  const unlinkGuestVisitFromViewedTask = useCallback(async (linkId: number) => {
    if (!board || !viewTask || saving) return;

    setSaving(true);
    setError(null);
    try {
      await apiClient.unlinkTaskGuestVisit(viewTask.id, linkId);
      await loadTaskLinkedObjects(viewTask.id);
      await loadBoard(board.id);
      if (activityOpen) await loadTaskActivity(viewTask.id);
    } catch (unlinkError) {
      setError(getTaskError(unlinkError, "Не удалось убрать связь с гостевым визитом"));
    } finally {
      setSaving(false);
    }
  }, [activityOpen, board, loadBoard, loadTaskActivity, loadTaskLinkedObjects, saving, viewTask]);

  const unlinkAttendanceRecordFromViewedTask = useCallback(async (linkId: number) => {
    if (!board || !viewTask || saving) return;

    setSaving(true);
    setError(null);
    try {
      await apiClient.unlinkTaskAttendanceRecord(viewTask.id, linkId);
      await loadTaskLinkedObjects(viewTask.id);
      await loadBoard(board.id);
      if (activityOpen) await loadTaskActivity(viewTask.id);
    } catch (unlinkError) {
      setError(getTaskError(unlinkError, "Не удалось убрать связь с записью посещаемости"));
    } finally {
      setSaving(false);
    }
  }, [activityOpen, board, loadBoard, loadTaskActivity, loadTaskLinkedObjects, saving, viewTask]);

  const changeViewedTaskColumn = useCallback(async (columnId: number) => {
    if (!board || !viewTask || saving || viewTask.column === columnId) {
      setViewColumnMenuOpen(false);
      return;
    }

    setSaving(true);
    setError(null);
    setViewColumnMenuOpen(false);
    try {
      await apiClient.moveTask(viewTask.id, { column: columnId });
      await loadBoard(board.id);
      if (activityOpen) await loadTaskActivity(viewTask.id);
    } catch (moveError) {
      setError(getTaskError(moveError, "Не удалось изменить колонку задачи"));
      await loadBoard(board.id);
    } finally {
      setSaving(false);
    }
  }, [activityOpen, board, loadBoard, loadTaskActivity, saving, viewTask]);

  const claimTask = useCallback(async (task: TaskCard) => {
    if (
      !board ||
      task.assignee ||
      task.completed_at ||
      claimingTaskId !== null
    ) {
      return;
    }

    setClaimingTaskId(task.id);
    setCardMenuTaskId(null);
    setError(null);
    try {
      await apiClient.claimTask(task.id);
      await loadBoard(board.id);
      if (activityOpen && viewTaskId === task.id) {
        await loadTaskActivity(task.id);
      }
    } catch (claimError) {
      setError(getTaskError(claimError, "Не удалось взять задачу в работу"));
      await loadBoard(board.id);
    } finally {
      setClaimingTaskId(null);
    }
  }, [activityOpen, board, claimingTaskId, loadBoard, loadTaskActivity, viewTaskId]);

  const completeTask = useCallback(async (task: TaskCard) => {
    if (
      !board ||
      !user?.id ||
      task.assignee?.id !== user.id ||
      task.completed_at ||
      completingTaskId !== null
    ) {
      return;
    }

    setCompletingTaskId(task.id);
    setCardMenuTaskId(null);
    setViewColumnMenuOpen(false);
    setError(null);
    try {
      await apiClient.completeTask(task.id);
      await loadBoard(board.id);
      if (activityOpen && viewTaskId === task.id) {
        await loadTaskActivity(task.id);
      }
    } catch (completeError) {
      setError(getTaskError(completeError, "Не удалось завершить задачу"));
      await loadBoard(board.id);
    } finally {
      setCompletingTaskId(null);
    }
  }, [
    activityOpen,
    board,
    completingTaskId,
    loadBoard,
    loadTaskActivity,
    user?.id,
    viewTaskId,
  ]);

  const handleDragStart = useCallback((event: DragStartEvent) => {
    const taskId = Number(String(event.active.id).replace("task-", ""));
    setActiveTaskId(Number.isFinite(taskId) ? taskId : null);
  }, []);

  const handleDragCancel = useCallback(() => {
    setActiveTaskId(null);
  }, []);

  const handleDragEnd = useCallback(async (event: DragEndEvent) => {
    setActiveTaskId(null);
    if (!board || !event.over) return;
    const taskId = Number(String(event.active.id).replace("task-", ""));
    const columnId = Number(String(event.over.id).replace("column-", ""));
    if (!taskId || !columnId) return;
    const task = board.tasks.find((item) => item.id === taskId);
    if (!task || task.column === columnId) return;

    try {
      await apiClient.moveTask(taskId, { column: columnId });
      await loadBoard(board.id);
    } catch (moveError) {
      setError(getTaskError(moveError, "Не удалось переместить задачу"));
      await loadBoard(board.id);
    }
  }, [board, loadBoard]);

  if (loading) {
    return (
      <AppShell
        desktopWideMode={desktopWideMode}
        onDesktopWideModeChange={changeDesktopWideMode}
      >
        <section className="app-surface rounded-2xl p-8 text-center">
          <Loader2 size={28} className="mx-auto mb-3 animate-spin text-sky-500" />
          <p className="app-text-muted text-sm">Загрузка задач...</p>
        </section>
      </AppShell>
    );
  }

  return (
    <AppShell
      desktopWideMode={desktopWideMode}
      onDesktopWideModeChange={changeDesktopWideMode}
    >
      <div className={`${desktopWideMode ? "w-full lg:flex lg:min-h-0 lg:flex-1 lg:flex-col lg:gap-4 lg:space-y-0" : "mx-auto max-w-[1600px]"} space-y-4`}>
        <section className="app-surface rounded-2xl p-4">
          <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
            <div className="min-w-0">
              <p className="app-card-caption">Доска</p>
              <h1 className="truncate text-xl font-semibold text-[var(--foreground)]">
                {board?.name || "Доска задач"}
              </h1>
            </div>
            <div className="flex flex-wrap gap-2">
              <button
                type="button"
                onClick={() => changeDesktopWideMode(!desktopWideMode)}
                className="app-action-ghost hidden h-8 w-8 items-center justify-center rounded-md lg:inline-flex"
                title={desktopWideMode ? "Вернуть обычный вид" : "Развернуть доску"}
                aria-label={desktopWideMode ? "Вернуть обычный вид" : "Развернуть доску"}
                aria-pressed={desktopWideMode}
              >
                {desktopWideMode ? <Minimize2 size={17} /> : <Maximize2 size={17} />}
              </button>
              <button
                type="button"
                onClick={openCreateBoard}
                className="app-action-primary inline-flex min-h-10 items-center justify-center gap-2 rounded-lg px-4 py-2 text-sm font-semibold"
              >
                <Plus size={16} />
                Создать доску
              </button>
              <div ref={boardActionsMenuRef} className="relative">
                <button
                  type="button"
                  onClick={() => setBoardActionsMenuOpen((current) => !current)}
                  className="app-action-ghost flex h-8 w-8 items-center justify-center rounded-md disabled:cursor-not-allowed disabled:opacity-50"
                  title="Дополнительные действия"
                  aria-label="Дополнительные действия"
                  aria-expanded={boardActionsMenuOpen}
                  aria-haspopup="menu"
                  disabled={!board}
                >
                  <ChevronRight
                    size={15}
                    className={`transition-transform duration-200 ${boardActionsMenuOpen ? "rotate-90" : ""}`}
                  />
                </button>

                {boardActionsMenuOpen ? (
                  <div className="app-menu absolute right-0 top-full z-20 mt-2 w-56 rounded-xl py-1.5">
                    <button
                      type="button"
                      onClick={openEditBoard}
                      className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm text-[var(--foreground)] transition hover:bg-[var(--surface-secondary)]"
                    >
                      <Pencil size={14} className="app-text-muted shrink-0" />
                      <span>Редактировать доску</span>
                    </button>
                    <button
                      type="button"
                      onClick={() => void refreshSelectedBoard()}
                      className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm text-[var(--foreground)] transition hover:bg-[var(--surface-secondary)]"
                    >
                      <RefreshCw size={14} className="app-text-muted shrink-0" />
                      <span>Обновить</span>
                    </button>
                    <button
                      type="button"
                      onClick={() => void setDefaultSelectedBoard()}
                      className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm text-[var(--foreground)] transition hover:bg-[var(--surface-secondary)] disabled:cursor-default disabled:opacity-70 disabled:hover:bg-transparent"
                      disabled={saving || Boolean(board?.is_default_for_current_user)}
                    >
                      <Star
                        size={14}
                        className={`shrink-0 ${
                          board?.is_default_for_current_user
                            ? "fill-current app-accent-text"
                            : "app-text-muted"
                        }`}
                      />
                      <span>
                        {board?.is_default_for_current_user
                          ? "Доска по умолчанию"
                          : "Сделать доской по умолчанию"}
                      </span>
                    </button>
                    <button
                      type="button"
                      onClick={() => void deleteSelectedBoard()}
                      className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm text-[var(--danger-foreground)] transition hover:bg-[var(--danger-soft)]"
                      disabled={saving}
                    >
                      <Trash2 size={14} className="shrink-0" />
                      <span>Удалить доску</span>
                    </button>
                  </div>
                ) : null}
              </div>
            </div>
          </div>

          <div className="mt-4">
            <label className="relative block min-w-0">
              <Search size={16} className="app-text-muted pointer-events-none absolute left-3 top-1/2 -translate-y-1/2" />
              <input
                value={search}
                onChange={(event) => setSearch(event.target.value)}
                placeholder="Поиск по задачам"
                className="app-input w-full rounded-xl py-2.5 pl-9 pr-3 text-sm"
              />
            </label>
          </div>

          <div className="mt-4 flex flex-wrap items-center gap-2">
            <div ref={boardMenuRef} className="relative">
              <div className="app-pill inline-flex max-w-full items-center overflow-hidden rounded-full text-xs font-medium transition">
                <button
                  type="button"
                  onClick={() => setBoardMenuOpen(false)}
                  className="inline-flex min-w-0 items-center gap-1.5 py-1.5 pl-3 pr-1.5 transition hover:opacity-85"
                >
                  <Kanban size={14} className="shrink-0" />
                  <span className="max-w-[220px] truncate">
                    {board?.name || "Доска"}
                  </span>
                </button>
                <button
                  type="button"
                  onClick={() => setBoardMenuOpen((prev) => !prev)}
                  className="flex h-7 w-7 shrink-0 items-center justify-center transition hover:bg-[var(--surface-tertiary)]"
                  title="Показать доски"
                  aria-label="Показать список досок"
                  aria-expanded={boardMenuOpen}
                  aria-haspopup="menu"
                >
                  <ChevronDown
                    size={12}
                    className={`opacity-70 transition-transform ${boardMenuOpen ? "rotate-180" : ""}`}
                  />
                </button>
              </div>
              {boardMenuOpen ? (
                <div className="app-menu absolute left-0 top-full z-20 mt-2 w-72 rounded-lg p-2">
                  <div className="tasks-column-scroll max-h-80 overflow-y-auto">
                    {boards.map((item) => {
                      const active = selectedBoardId === item.id;
                      return (
                        <button
                          key={item.id}
                          type="button"
                          onClick={() => void selectBoard(item.id)}
                          className={`flex w-full items-center gap-2 rounded-md px-3 py-2 text-left text-sm transition ${
                            active
                              ? "app-selected app-accent-text font-medium"
                              : "text-[var(--foreground)] hover:bg-[var(--surface-secondary)]"
                          }`}
                        >
                          <Kanban size={15} className="shrink-0" />
                          <span className="min-w-0 flex-1 truncate">{item.name}</span>
                          {item.is_default_for_current_user ? (
                            <Star
                              size={12}
                              className="app-accent-text shrink-0 fill-current"
                              aria-label="Доска по умолчанию"
                            />
                          ) : null}
                        </button>
                      );
                    })}
                  </div>
                </div>
              ) : null}
            </div>

            <button
              type="button"
              onClick={focusAllColumns}
              className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1.5 text-xs font-medium transition ${
                selectedColumnTarget === "all" ? "app-pill-active" : "app-pill"
              }`}
            >
              <span>Все</span>
              <span className={`app-badge px-1.5 py-0.5 text-[10px] font-bold ${
                selectedColumnTarget === "all" ? "app-pill-count-active" : "app-pill-count"
              }`}>
                {filteredTasks.length}
              </span>
            </button>
            {activeColumns.map((column) => {
              const active = selectedColumnTarget === column.id;
              return (
                <button
                  key={column.id}
                  type="button"
                  onClick={() => focusColumn(column.id)}
                  className={`inline-flex max-w-48 items-center gap-1.5 rounded-full px-3 py-1.5 text-xs font-medium transition ${
                    active ? "app-pill-active" : "app-pill"
                  }`}
                >
                  <span
                    className="h-2 w-2 shrink-0 rounded-full"
                    style={{ backgroundColor: column.color || "#38bdf8" }}
                  />
                  <span className="truncate">{column.name}</span>
                  <span className={`app-badge px-1.5 py-0.5 text-[10px] font-bold ${
                    active ? "app-pill-count-active" : "app-pill-count"
                  }`}>
                    {columnCounts.get(column.id) || 0}
                  </span>
                </button>
              );
            })}
            <button
              type="button"
              onClick={() => setOnlyMine((current) => !current)}
              className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1.5 text-xs font-medium transition ${
                onlyMine ? "app-pill-active" : "app-pill"
              }`}
            >
              <UserRound size={14} />
              <span>Мои задачи</span>
              <span className={`app-badge px-1.5 py-0.5 text-[10px] font-bold ${
                onlyMine ? "app-pill-count-active" : "app-pill-count"
              }`}>
                {mineCount}
              </span>
            </button>
            {onlyMine ? (
              <button
                type="button"
                onClick={() => setOnlyMine(false)}
                className="app-action-ghost inline-flex h-7 w-7 items-center justify-center rounded-full"
                title="Сбросить фильтр"
                aria-label="Сбросить фильтр моих задач"
              >
                <X size={13} />
              </button>
            ) : null}
          </div>

          {error ? (
            <div className="app-feedback-danger mt-3 rounded-xl px-4 py-3 text-sm">
              {error}
            </div>
          ) : null}
        </section>

        <DndContext
          sensors={sensors}
          collisionDetection={closestCorners}
          onDragStart={handleDragStart}
          onDragCancel={handleDragCancel}
          onDragEnd={handleDragEnd}
        >
          <div
            ref={boardScrollRef}
            className={`tasks-board-scroll overflow-x-auto pb-3 ${desktopWideMode ? "lg:min-h-0 lg:flex-1" : ""}`}
          >
            <div className={`flex min-w-max gap-3 ${desktopWideMode ? "lg:h-full" : ""}`}>
              {activeColumns.map((column) => (
                <BoardColumn
                  key={column.id}
                  column={column}
                  tasks={tasksByColumn.get(column.id) || []}
                  onCreateTask={openCreateTask}
                  onOpenTask={openTaskView}
                  onEditTask={openEditTask}
                  onDeleteTask={deleteTask}
                  currentUserId={user?.id}
                  claimingTaskId={claimingTaskId}
                  onClaimTask={claimTask}
                  completingTaskId={completingTaskId}
                  onCompleteTask={completeTask}
                  openMenuTaskId={cardMenuTaskId}
                  menuRef={cardMenuRef}
                  onToggleTaskMenu={toggleCardTaskMenu}
                  onColumnMount={registerColumnNode}
                  fillAvailableHeight={desktopWideMode}
                />
              ))}
              <AddColumnCard
                onClick={openCreateColumn}
                fillAvailableHeight={desktopWideMode}
              />
            </div>
          </div>
          <DragOverlay zIndex={1000} dropAnimation={null}>
            {activeDragTask ? <TaskDragOverlayCard task={activeDragTask} /> : null}
          </DragOverlay>
        </DndContext>
      </div>

      <Modal
        isOpen={boardModalOpen}
        onClose={closeBoardModal}
        title={boardForm.id ? "Редактировать доску" : "Новая доска"}
        size="lg"
        closeOnClickOutside
        footer={(
          <div className="flex justify-end gap-2">
            <button
              type="button"
              onClick={closeBoardModal}
              className="app-action-secondary rounded-xl px-4 py-2 text-sm font-medium"
              disabled={saving}
            >
              Отмена
            </button>
            <button
              type="button"
              onClick={() => void saveBoard()}
              disabled={saving || !boardForm.name.trim()}
              className="app-action-primary inline-flex items-center gap-2 rounded-xl px-4 py-2 text-sm font-medium disabled:opacity-60"
            >
              {saving ? <Loader2 size={16} className="animate-spin" /> : null}
              {boardForm.id ? "Сохранить" : "Создать"}
            </button>
          </div>
        )}
      >
        <div className="space-y-4">
          <label className="block">
            <span className="app-text-muted mb-1 block text-xs font-medium">Название доски</span>
            <input
              value={boardForm.name}
              onChange={(event) => setBoardForm((current) => ({ ...current, name: event.target.value }))}
              className="app-input w-full rounded-xl px-3 py-2 text-sm"
              autoFocus
            />
          </label>
          <label className="block">
            <span className="app-text-muted mb-1 block text-xs font-medium">Описание</span>
            <textarea
              value={boardForm.description}
              onChange={(event) => setBoardForm((current) => ({ ...current, description: event.target.value }))}
              rows={3}
              className="app-input w-full rounded-xl px-3 py-2 text-sm"
            />
          </label>

          <div>
            <span className="app-text-muted mb-2 block text-xs font-medium">Доступ</span>
            <div className="grid gap-2 sm:grid-cols-3">
              <button
                type="button"
                onClick={() => setBoardForm((current) => ({ ...current, access: "all" }))}
                className={`rounded-xl border px-3 py-2 text-left text-sm font-medium transition ${
                  boardForm.access === "all"
                    ? "app-selected border-[var(--accent-primary)]"
                    : "border-[var(--border-subtle)] text-[var(--muted-foreground)] hover:border-[var(--border-strong)]"
                }`}
              >
                Для всех
              </button>
              <button
                type="button"
                onClick={() => setBoardForm((current) => ({ ...current, access: "private" }))}
                className={`rounded-xl border px-3 py-2 text-left text-sm font-medium transition ${
                  boardForm.access === "private"
                    ? "app-selected border-[var(--accent-primary)]"
                    : "border-[var(--border-subtle)] text-[var(--muted-foreground)] hover:border-[var(--border-strong)]"
                }`}
              >
                Для себя
              </button>
              <button
                type="button"
                onClick={() => setBoardForm((current) => ({ ...current, access: "restricted" }))}
                className={`rounded-xl border px-3 py-2 text-left text-sm font-medium transition ${
                  boardForm.access === "restricted"
                    ? "app-selected border-[var(--accent-primary)]"
                    : "border-[var(--border-subtle)] text-[var(--muted-foreground)] hover:border-[var(--border-strong)]"
                }`}
              >
                Выборочно
              </button>
            </div>
          </div>

          {boardForm.access === "restricted" ? (
            <div className="grid gap-3 md:grid-cols-2">
              <div>
                <div className="mb-2 flex items-center justify-between gap-2">
                  <span className="app-text-muted text-xs font-medium">Сотрудники</span>
                  <span className="app-badge rounded-full px-2 py-0.5 text-[11px]">
                    {boardForm.member_ids.length}
                  </span>
                </div>
                <div className="relative mb-2">
                  <Search
                    size={14}
                    className="app-text-muted pointer-events-none absolute left-2.5 top-1/2 -translate-y-1/2"
                  />
                  <input
                    value={boardMemberSearch}
                    onChange={(event) => setBoardMemberSearch(event.target.value)}
                    className="app-input w-full rounded-xl py-2 pl-8 pr-3 text-xs"
                    placeholder="Поиск сотрудников"
                    aria-label="Поиск сотрудников"
                  />
                </div>
                <div className="tasks-column-scroll app-surface-muted max-h-52 space-y-1 overflow-y-auto rounded-xl border border-[var(--border-subtle)] p-2">
                  {filteredBoardMembers.length > 0 ? (
                    filteredBoardMembers.map((employee) => {
                      const employeeName = displayUserName(employee);
                      return (
                        <label
                          key={employee.id}
                          className="flex cursor-pointer items-center gap-2 rounded-lg px-2 py-1.5 text-sm transition hover:bg-[var(--surface-elevated)]"
                        >
                          <input
                            type="checkbox"
                            checked={boardForm.member_ids.includes(employee.id)}
                            onChange={() => toggleBoardMember(employee.id)}
                            className="h-4 w-4 shrink-0"
                          />
                          <RequestAvatar
                            alt={employeeName}
                            fallback={getEmployeeInitials(employee)}
                            src={employee.avatar}
                            size="sm"
                          />
                          <span className="min-w-0 flex-1">
                            <span className="block truncate text-xs font-medium text-[var(--foreground)]">
                              {employeeName}
                            </span>
                            {employee.email ? (
                              <span className="app-text-muted block truncate text-[10px]">
                                {employee.email}
                              </span>
                            ) : null}
                          </span>
                        </label>
                      );
                    })
                  ) : (
                    <p className="app-text-muted px-2 py-4 text-center text-xs">
                      Сотрудники не найдены
                    </p>
                  )}
                </div>
              </div>

              <div>
                <div className="mb-2 flex items-center justify-between gap-2">
                  <span className="app-text-muted text-xs font-medium">Отделы</span>
                  <span className="app-badge rounded-full px-2 py-0.5 text-[11px]">
                    {boardForm.department_ids.length}
                  </span>
                </div>
                <div className="relative mb-2">
                  <Search
                    size={14}
                    className="app-text-muted pointer-events-none absolute left-2.5 top-1/2 -translate-y-1/2"
                  />
                  <input
                    value={boardDepartmentSearch}
                    onChange={(event) => setBoardDepartmentSearch(event.target.value)}
                    className="app-input w-full rounded-xl py-2 pl-8 pr-3 text-xs"
                    placeholder="Поиск отделов"
                    aria-label="Поиск отделов"
                  />
                </div>
                <div className="tasks-column-scroll app-surface-muted max-h-52 space-y-1 overflow-y-auto rounded-xl border border-[var(--border-subtle)] p-2">
                  {filteredBoardDepartments.length > 0 ? (
                    filteredBoardDepartments.map((department) => (
                      <label
                        key={department.id}
                        className="flex cursor-pointer items-center gap-2 rounded-lg px-2 py-1.5 text-sm transition hover:bg-[var(--surface-elevated)]"
                      >
                        <input
                          type="checkbox"
                          checked={boardForm.department_ids.includes(department.id)}
                          onChange={() => toggleBoardDepartment(department.id)}
                          className="h-4 w-4"
                        />
                        <span className="min-w-0 truncate text-[var(--foreground)]">
                          {department.name}
                        </span>
                      </label>
                    ))
                  ) : (
                    <p className="app-text-muted px-2 py-4 text-center text-xs">
                      Отделы не найдены
                    </p>
                  )}
                </div>
              </div>
            </div>
          ) : null}
        </div>
      </Modal>

      <Modal
        isOpen={columnModalOpen}
        onClose={closeColumnModal}
        title="Новая колонка"
        size="sm"
        closeOnClickOutside
        footer={(
          <div className="flex justify-end gap-2">
            <button
              type="button"
              onClick={closeColumnModal}
              className="app-action-secondary rounded-xl px-4 py-2 text-sm font-medium"
              disabled={saving}
            >
              Отмена
            </button>
            <button
              type="button"
              onClick={() => void saveColumn()}
              disabled={saving || !columnForm.name.trim()}
              className="app-action-primary inline-flex items-center gap-2 rounded-xl px-4 py-2 text-sm font-medium disabled:opacity-60"
            >
              {saving ? <Loader2 size={16} className="animate-spin" /> : null}
              Создать
            </button>
          </div>
        )}
      >
        <div className="space-y-4">
          <label className="block">
            <span className="app-text-muted mb-1 block text-xs font-medium">Название колонки</span>
            <input
              value={columnForm.name}
              onChange={(event) => setColumnForm((current) => ({ ...current, name: event.target.value }))}
              className="app-input w-full rounded-xl px-3 py-2 text-sm"
              autoFocus
            />
          </label>

          <label className="block">
            <span className="app-text-muted mb-1 block text-xs font-medium">Цвет</span>
            <div className="grid grid-cols-[3.5rem_1fr] gap-2">
              <input
                type="color"
                value={columnForm.color}
                onChange={(event) => setColumnForm((current) => ({ ...current, color: event.target.value }))}
                className="h-10 w-14 rounded-lg border border-[var(--border-subtle)] bg-transparent p-1"
                aria-label="Цвет колонки"
              />
              <input
                value={columnForm.color}
                onChange={(event) => setColumnForm((current) => ({ ...current, color: event.target.value }))}
                className="app-input min-w-0 rounded-xl px-3 py-2 text-sm"
              />
            </div>
          </label>

          <label className="app-surface-muted flex cursor-pointer items-center gap-3 rounded-xl border border-[var(--border-subtle)] px-3 py-2 text-sm">
            <input
              type="checkbox"
              checked={columnForm.is_done}
              onChange={(event) => setColumnForm((current) => ({ ...current, is_done: event.target.checked }))}
              className="h-4 w-4"
            />
            Финальная колонка
          </label>
        </div>
      </Modal>

      <Modal
        isOpen={Boolean(viewTask)}
        onClose={closeTaskView}
        title="Задача"
        size="md"
        closeOnClickOutside
      >
        {viewTask ? (
          <div className="space-y-4">
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0 flex-1">
                <div className="flex min-w-0 flex-wrap items-center gap-x-2 gap-y-1">
                  <span className="app-badge shrink-0 rounded-full px-1.5 py-0.5 text-[10px] font-semibold">
                    #{viewTask.id}
                  </span>
                  <h2 className="app-text-wrap min-w-0 text-lg font-semibold text-[var(--foreground)]">
                    {viewTask.title}
                  </h2>
                </div>
                <div className="mt-2 flex flex-wrap gap-1.5">
                  {!viewTask.assignee && !viewTask.completed_at ? (
                    <button
                      type="button"
                      onClick={() => void claimTask(viewTask)}
                      disabled={claimingTaskId !== null}
                      className="app-action-primary inline-flex h-7 w-7 shrink-0 items-center justify-center rounded-full disabled:cursor-wait disabled:opacity-60"
                      title="Взять задачу в работу"
                      aria-label="Взять задачу в работу"
                    >
                      {claimingTaskId === viewTask.id ? (
                        <Loader2 size={13} className="animate-spin" />
                      ) : (
                        <Play size={14} />
                      )}
                    </button>
                  ) : null}
                  {viewTask.assignee?.id === user?.id && !viewTask.completed_at ? (
                    <button
                      type="button"
                      onClick={() => void completeTask(viewTask)}
                      disabled={completingTaskId !== null}
                      className="app-action-success inline-flex h-7 w-7 shrink-0 items-center justify-center rounded-full disabled:cursor-wait disabled:opacity-60"
                      title="Завершить задачу"
                      aria-label="Завершить задачу"
                    >
                      {completingTaskId === viewTask.id ? (
                        <Loader2 size={13} className="animate-spin" />
                      ) : (
                        <Check size={14} strokeWidth={2.5} />
                      )}
                    </button>
                  ) : null}
                  {viewTaskColumn ? (
                    <div ref={viewColumnMenuRef} className="relative">
                      <button
                        type="button"
                        onClick={() => setViewColumnMenuOpen((current) => !current)}
                        className="app-pill inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium transition hover:border-[var(--border-strong)] disabled:cursor-not-allowed disabled:opacity-60"
                        disabled={saving || activeColumns.length === 0}
                        title="Изменить колонку"
                        aria-label="Изменить колонку задачи"
                        aria-expanded={viewColumnMenuOpen}
                        aria-haspopup="menu"
                      >
                        <span
                          className="h-2 w-2 shrink-0 rounded-full"
                          style={{ backgroundColor: viewTaskColumn.color || "#38bdf8" }}
                        />
                        <span className="max-w-40 truncate">{viewTaskColumn.name}</span>
                        <ChevronDown
                          size={12}
                          className={`transition-transform ${viewColumnMenuOpen ? "rotate-180" : ""}`}
                        />
                      </button>

                      {viewColumnMenuOpen ? (
                        <div className="app-menu absolute left-0 top-full z-30 mt-2 w-56 rounded-xl p-1.5">
                          {activeColumns.map((column) => {
                            const selected = column.id === viewTask.column;
                            return (
                              <button
                                key={column.id}
                                type="button"
                                onClick={() => void changeViewedTaskColumn(column.id)}
                                className={`flex w-full items-center gap-2 rounded-lg px-3 py-2 text-left text-sm transition hover:bg-[var(--surface-secondary)] ${
                                  selected ? "text-[var(--accent-primary)]" : "text-[var(--foreground)]"
                                }`}
                                disabled={saving || selected}
                              >
                                <span
                                  className="h-2.5 w-2.5 shrink-0 rounded-full"
                                  style={{ backgroundColor: column.color || "#38bdf8" }}
                                />
                                <span className="min-w-0 flex-1 truncate">{column.name}</span>
                                {selected ? (
                                  <span className="app-badge rounded-full px-2 py-0.5 text-[10px]">
                                    текущая
                                  </span>
                                ) : null}
                              </button>
                            );
                          })}
                        </div>
                      ) : null}
                    </div>
                  ) : null}
                  <span className={`app-status-pill min-h-0 px-2.5 py-1 text-xs ${priorityMeta[viewTask.priority]?.className || "app-badge"}`}>
                    {viewTask.priority_display || priorityMeta[viewTask.priority]?.label || viewTask.priority}
                  </span>
                  {viewTask.assignee ? (
                    <span className="app-pill inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium">
                      <UserRound size={12} />
                      {displayUserName(viewTask.assignee)}
                    </span>
                  ) : null}
                  {viewTask.due_date ? (
                    <span className={`${getTaskDueDateBadgeClass(viewTask, "app-pill")} inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium`}>
                      <CalendarDays size={12} />
                      {formatDate(viewTask.due_date)}
                    </span>
                  ) : null}
                </div>
              </div>

              <div ref={taskMenuRef} className="relative shrink-0">
                <button
                  type="button"
                  onClick={() => setTaskMenuOpen((current) => !current)}
                  className="app-icon-button flex h-9 w-9 items-center justify-center rounded-lg"
                  title="Действия"
                  aria-label="Действия с задачей"
                  aria-expanded={taskMenuOpen}
                  aria-haspopup="menu"
                >
                  <ChevronDown
                    size={16}
                    className={`transition-transform ${taskMenuOpen ? "" : "-rotate-90"}`}
                  />
                </button>
                {taskMenuOpen ? (
                  <div className="app-menu absolute right-0 top-full z-20 mt-2 w-48 rounded-lg p-1.5">
                    <button
                      type="button"
                      onClick={() => openEditTask(viewTask)}
                      className="flex w-full items-center gap-2 rounded-md px-3 py-2 text-left text-sm transition hover:bg-[var(--surface-secondary)]"
                    >
                      <Pencil size={14} className="app-text-muted" />
                      Редактировать
                    </button>
                    <button
                      type="button"
                      onClick={() => void deleteViewedTask()}
                      className="flex w-full items-center gap-2 rounded-md px-3 py-2 text-left text-sm text-[var(--danger-foreground)] transition hover:bg-[var(--danger-soft)]"
                      disabled={saving}
                    >
                      <Trash2 size={14} />
                      Удалить
                    </button>
                  </div>
                ) : null}
              </div>
            </div>

            {viewTask.description ? (
              <div className="app-surface-muted rounded-xl border border-[var(--border-subtle)] p-3">
                <p className="app-text-wrap whitespace-pre-wrap text-sm text-[var(--foreground)]">
                  {viewTask.description}
                </p>
              </div>
            ) : null}

            <div className="rounded-xl border border-[var(--border-subtle)]">
              <div className="flex items-center px-1 py-1">
                <button
                  type="button"
                  onClick={() => setChecklistOpen((current) => !current)}
                  className="flex min-w-0 flex-1 items-center gap-2 rounded-lg px-2 py-1.5 text-left"
                  aria-expanded={checklistOpen}
                >
                  <ListChecks size={15} className="app-text-muted shrink-0" />
                  <span className="truncate text-sm font-medium text-[var(--foreground)]">
                    Чек-лист
                  </span>
                  <span className="app-badge rounded-full px-2 py-0.5 text-[11px]">
                    {checklistBadgeCompleted}/{checklistBadgeTotal}
                  </span>
                </button>
                <button
                  type="button"
                  onClick={() => setChecklistOpen((current) => !current)}
                  className="app-icon-button flex h-8 w-8 shrink-0 items-center justify-center rounded-lg"
                  title={checklistOpen ? "Скрыть чек-лист" : "Показать чек-лист"}
                  aria-label={checklistOpen ? "Скрыть чек-лист" : "Показать чек-лист"}
                  aria-expanded={checklistOpen}
                >
                  <ChevronRight
                    size={16}
                    className={`transition-transform ${checklistOpen ? "rotate-90" : ""}`}
                  />
                </button>
              </div>

              {checklistOpen ? (
                <div className="space-y-3 border-t border-[var(--border-subtle)] p-3">
                  {taskChecklistLoading && !taskChecklistLoaded ? (
                    <div className="app-surface-muted rounded-xl border border-[var(--border-subtle)] p-4 text-center">
                      <Loader2 size={18} className="mx-auto animate-spin text-sky-500" />
                    </div>
                  ) : taskChecklist.length > 0 ? (
                    <div className="overflow-hidden rounded-lg border border-[var(--border-subtle)]">
                      {taskChecklist.map((item) => (
                        <div
                          key={item.id}
                          className="flex min-w-0 items-center gap-3 border-b border-[var(--border-subtle)] px-3 py-2.5 last:border-b-0"
                        >
                          <input
                            type="checkbox"
                            checked={item.is_completed}
                            onChange={() => void toggleViewedTaskChecklistItem(item)}
                            disabled={taskChecklistSaving}
                            className="h-4 w-4 shrink-0 accent-sky-500"
                            aria-label={item.is_completed ? "Вернуть пункт в работу" : "Отметить пункт выполненным"}
                          />
                          <span className={`app-text-wrap min-w-0 flex-1 text-sm ${
                            item.is_completed
                              ? "app-text-muted line-through"
                              : "text-[var(--foreground)]"
                          }`}>
                            {item.title}
                          </span>
                          <button
                            type="button"
                            onClick={() => void deleteViewedTaskChecklistItem(item)}
                            disabled={taskChecklistSaving}
                            className="app-icon-button flex h-8 w-8 shrink-0 items-center justify-center rounded-lg text-[var(--danger-foreground)] disabled:opacity-50"
                            title="Удалить пункт"
                            aria-label={`Удалить пункт ${item.title}`}
                          >
                            <Trash2 size={14} />
                          </button>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div className="app-surface-muted rounded-xl border border-dashed border-[var(--border-subtle)] px-3 py-4 text-center">
                      <p className="app-text-muted text-xs">Пунктов пока нет</p>
                    </div>
                  )}

                  <div className="flex items-center gap-2">
                    <input
                      ref={taskChecklistDraftRef}
                      value={taskChecklistDraft}
                      onChange={(event) => setTaskChecklistDraft(event.target.value)}
                      onKeyDown={(event) => {
                        if (event.key !== "Enter") return;
                        event.preventDefault();
                        void addViewedTaskChecklistItem();
                      }}
                      disabled={taskChecklistSaving}
                      className="app-input min-w-0 flex-1 rounded-xl px-3 py-2 text-sm"
                      placeholder="Новый пункт"
                    />
                    <button
                      type="button"
                      onClick={() => void addViewedTaskChecklistItem()}
                      disabled={taskChecklistSaving || !taskChecklistDraft.trim()}
                      className="app-icon-button flex h-9 w-9 shrink-0 items-center justify-center rounded-lg disabled:opacity-50"
                      title="Добавить пункт"
                      aria-label="Добавить пункт чек-листа"
                    >
                      {taskChecklistSaving ? (
                        <Loader2 size={15} className="animate-spin" />
                      ) : (
                        <Plus size={15} />
                      )}
                    </button>
                  </div>
                </div>
              ) : null}
            </div>

            {viewTask.labels && viewTask.labels.length > 0 ? (
              <div>
                <div className="mb-2 flex items-center gap-2">
                  <Tag size={15} className="app-text-muted" />
                  <span className="app-text-muted text-xs font-medium">Метки</span>
                </div>
                <div className="flex flex-wrap gap-2">
                  {viewTask.labels.map((label) => (
                    <span
                      key={label.id}
                      className="inline-flex max-w-full items-center rounded-full px-2.5 py-1 text-xs font-medium text-white"
                      style={{ backgroundColor: label.color || "#38bdf8" }}
                    >
                      {label.name}
                    </span>
                  ))}
                </div>
              </div>
            ) : null}

            <div className="rounded-xl border border-[var(--border-subtle)]">
              <div className="flex items-center px-1 py-1">
                <button
                  type="button"
                  onClick={() => setAttachmentsOpen((current) => !current)}
                  className="flex min-w-0 flex-1 items-center gap-2 rounded-lg px-2 py-1.5 text-left"
                  aria-expanded={attachmentsOpen}
                >
                  <Paperclip size={15} className="app-text-muted shrink-0" />
                  <span className="truncate text-sm font-medium text-[var(--foreground)]">
                    Файлы
                  </span>
                  <span className="app-badge rounded-full px-2 py-0.5 text-[11px]">
                    {attachmentsBadgeCount}
                  </span>
                </button>
                <input
                  ref={taskAttachmentInputRef}
                  type="file"
                  multiple
                  className="sr-only"
                  disabled={taskAttachmentsUploading}
                  onChange={(event) => {
                    const files = Array.from(event.currentTarget.files || []);
                    event.currentTarget.value = "";
                    setAttachmentsOpen(true);
                    void uploadViewedTaskAttachments(files);
                  }}
                />
                <button
                  type="button"
                  onClick={() => taskAttachmentInputRef.current?.click()}
                  disabled={taskAttachmentsUploading}
                  className="app-icon-button flex h-8 w-8 shrink-0 items-center justify-center rounded-lg disabled:opacity-50"
                  title="Добавить файлы"
                  aria-label="Добавить файлы"
                >
                  {taskAttachmentsUploading ? (
                    <Loader2 size={15} className="animate-spin" />
                  ) : (
                    <Plus size={15} />
                  )}
                </button>
                <button
                  type="button"
                  onClick={() => setAttachmentsOpen((current) => !current)}
                  className="app-icon-button flex h-8 w-8 shrink-0 items-center justify-center rounded-lg"
                  title={attachmentsOpen ? "Скрыть файлы" : "Показать файлы"}
                  aria-label={attachmentsOpen ? "Скрыть файлы" : "Показать файлы"}
                  aria-expanded={attachmentsOpen}
                >
                  <ChevronRight
                    size={16}
                    className={`transition-transform ${attachmentsOpen ? "rotate-90" : ""}`}
                  />
                </button>
              </div>

              {attachmentsOpen ? (
                <div className="space-y-3 border-t border-[var(--border-subtle)] p-3">
                  {taskAttachmentsLoading ? (
                    <div className="app-surface-muted rounded-xl border border-[var(--border-subtle)] p-4 text-center">
                      <Loader2 size={18} className="mx-auto animate-spin text-sky-500" />
                    </div>
                  ) : taskAttachments.length > 0 ? (
                    <div className="overflow-hidden rounded-lg border border-[var(--border-subtle)]">
                      {taskAttachments.map((attachment) => (
                        <div
                          key={attachment.id}
                          className="flex items-center gap-2 border-b border-[var(--border-subtle)] px-3 py-2.5 last:border-b-0"
                        >
                          <button
                            type="button"
                            onClick={() => void downloadViewedTaskAttachment(attachment)}
                            className="flex min-w-0 flex-1 items-center gap-3 text-left"
                            title={`Скачать ${attachment.file_name}`}
                          >
                            <span className="app-selected flex h-8 w-8 shrink-0 items-center justify-center rounded-lg">
                              <FileText size={15} />
                            </span>
                            <span className="min-w-0 flex-1">
                              <span className="block truncate text-sm font-medium text-[var(--foreground)]">
                                {attachment.file_name}
                              </span>
                              <span className="app-text-muted mt-0.5 block truncate text-[11px]">
                                {formatFileSize(attachment.file_size)}
                                {attachment.uploaded_by
                                  ? ` · ${displayUserName(attachment.uploaded_by)}`
                                  : ""}
                                {` · ${formatDateTime(attachment.created_at)}`}
                              </span>
                            </span>
                            <Download size={14} className="app-text-muted shrink-0" />
                          </button>
                          <button
                            type="button"
                            onClick={() => void deleteViewedTaskAttachment(attachment)}
                            disabled={taskAttachmentsUploading}
                            className="app-icon-button flex h-8 w-8 shrink-0 items-center justify-center rounded-lg text-[var(--danger-foreground)] disabled:opacity-50"
                            title="Удалить файл"
                            aria-label={`Удалить файл ${attachment.file_name}`}
                          >
                            <Trash2 size={14} />
                          </button>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div className="app-surface-muted rounded-xl border border-dashed border-[var(--border-subtle)] px-3 py-4 text-center">
                      <p className="app-text-muted text-xs">Файлов пока нет</p>
                    </div>
                  )}
                </div>
              ) : null}
            </div>

            <div className="rounded-xl border border-[var(--border-subtle)]">
              <button
                type="button"
                onClick={() => setCommentsOpen((current) => !current)}
                className="flex w-full items-center justify-between gap-3 px-3 py-2.5 text-left"
                aria-expanded={commentsOpen}
              >
                <span className="flex min-w-0 items-center gap-2">
                  <MessageSquare size={15} className="app-text-muted shrink-0" />
                  <span className="text-sm font-medium text-[var(--foreground)]">
                    Комментарии
                  </span>
                  <span className="app-badge rounded-full px-2 py-0.5 text-[11px]">
                    {commentsBadgeCount}
                  </span>
                </span>
                <ChevronRight
                  size={16}
                  className={`app-text-muted shrink-0 transition-transform ${commentsOpen ? "rotate-90" : ""}`}
                />
              </button>

              {commentsOpen ? (
                <div className="space-y-3 border-t border-[var(--border-subtle)] p-3">
                  {taskCommentsLoading ? (
                    <div className="app-surface-muted rounded-xl border border-[var(--border-subtle)] p-4 text-center">
                      <Loader2 size={18} className="mx-auto animate-spin text-sky-500" />
                    </div>
                  ) : taskComments.length > 0 ? (
                    <div className="space-y-2">
                      {taskComments.map((comment) => {
                        const canEditComment = comment.author?.id === user?.id;
                        const canDeleteComment = Boolean(
                          user?.auth?.is_staff ||
                          user?.auth?.is_superuser ||
                          comment.author?.id === user?.id,
                        );
                        return (
                          <div
                            key={comment.id}
                            className="app-surface-muted rounded-xl border border-[var(--border-subtle)] px-3 py-2 text-sm"
                          >
                            <div className="mb-1 flex items-start justify-between gap-2">
                              <div className="min-w-0">
                                <p className="truncate text-xs font-semibold text-[var(--foreground)]">
                                  {comment.author ? displayUserName(comment.author) : "Сотрудник"}
                                </p>
                                <p className="app-text-muted mt-0.5 text-[11px]">
                                  {formatDateTime(comment.created_at)}
                                  {comment.is_edited ? " · изменён" : ""}
                                </p>
                              </div>
                              {editingCommentId !== comment.id && (canEditComment || canDeleteComment) ? (
                                <div className="flex shrink-0 items-center gap-1">
                                  {canEditComment ? (
                                    <button
                                      type="button"
                                      onClick={() => beginEditingViewedTaskComment(comment)}
                                      disabled={saving}
                                      className="app-icon-button inline-flex h-7 w-7 items-center justify-center rounded-lg disabled:opacity-50"
                                      title="Редактировать комментарий"
                                      aria-label="Редактировать комментарий"
                                    >
                                      <Pencil size={13} />
                                    </button>
                                  ) : null}
                                  {canDeleteComment ? (
                                    <CommentDeleteButton
                                      disabled={saving}
                                      onClick={() => deleteViewedTaskComment(comment.id)}
                                    />
                                  ) : null}
                                </div>
                              ) : null}
                            </div>
                            {editingCommentId === comment.id ? (
                              <div className="space-y-2">
                                <textarea
                                  autoFocus
                                  value={editingCommentDraft}
                                  onChange={(event) => setEditingCommentDraft(event.target.value)}
                                  onKeyDown={(event) => {
                                    if ((event.ctrlKey || event.metaKey) && event.key === "Enter") {
                                      event.preventDefault();
                                      void updateViewedTaskComment();
                                    }
                                    if (event.key === "Escape") {
                                      event.preventDefault();
                                      cancelEditingViewedTaskComment();
                                    }
                                  }}
                                  disabled={saving}
                                  rows={3}
                                  className="app-input w-full resize-none rounded-lg p-2.5 text-sm"
                                  aria-label="Текст комментария"
                                />
                                <div className="flex justify-end gap-1.5">
                                  <button
                                    type="button"
                                    onClick={cancelEditingViewedTaskComment}
                                    disabled={saving}
                                    className="app-icon-button inline-flex h-8 w-8 items-center justify-center rounded-lg disabled:opacity-50"
                                    title="Отменить редактирование"
                                    aria-label="Отменить редактирование"
                                  >
                                    <X size={14} />
                                  </button>
                                  <button
                                    type="button"
                                    onClick={() => void updateViewedTaskComment()}
                                    disabled={saving || !editingCommentDraft.trim()}
                                    className="app-action-success inline-flex h-8 w-8 items-center justify-center rounded-lg disabled:opacity-50"
                                    title="Сохранить комментарий"
                                    aria-label="Сохранить комментарий"
                                  >
                                    {saving ? <Loader2 size={14} className="animate-spin" /> : <Check size={14} />}
                                  </button>
                                </div>
                              </div>
                            ) : (
                              <p className="app-text-wrap whitespace-pre-wrap text-sm leading-5 text-[var(--foreground)]">
                                {comment.text}
                              </p>
                            )}
                          </div>
                        );
                      })}
                    </div>
                  ) : (
                    <div className="app-surface-muted rounded-xl border border-dashed border-[var(--border-subtle)] px-3 py-4 text-center">
                      <p className="app-text-muted text-xs">Комментариев пока нет</p>
                    </div>
                  )}

                  <CommentComposer
                    value={commentDraft}
                    onChange={setCommentDraft}
                    onSubmit={addViewedTaskComment}
                    disabled={saving}
                    multiline
                    rows={2}
                    placeholder="Комментарий к задаче"
                  />
                </div>
              ) : null}
            </div>

            <div className="rounded-xl border border-[var(--border-subtle)]">
              <div className="flex items-center px-1 py-1">
                <button
                  type="button"
                  onClick={() => setLinkedObjectsOpen((current) => !current)}
                  className="flex min-w-0 flex-1 items-center gap-2 rounded-lg px-2 py-1.5 text-left"
                  aria-expanded={linkedObjectsOpen}
                >
                  <Link2 size={15} className="app-text-muted shrink-0" />
                  <span className="truncate text-sm font-medium text-[var(--foreground)]">
                    Связанные объекты и ссылки
                  </span>
                  <span className="app-badge rounded-full px-2 py-0.5 text-[11px]">
                    {linkedObjectsBadgeCount}
                  </span>
                </button>
                <button
                  type="button"
                  onClick={openLinkedItemModalForView}
                  disabled={saving}
                  className="app-icon-button flex h-8 w-8 shrink-0 items-center justify-center rounded-lg disabled:opacity-50"
                  title="Добавить объект или ссылку"
                  aria-label="Добавить объект или ссылку"
                >
                  <Plus size={15} />
                </button>
                <button
                  type="button"
                  onClick={() => setLinkedObjectsOpen((current) => !current)}
                  className="app-icon-button flex h-8 w-8 shrink-0 items-center justify-center rounded-lg"
                  title={linkedObjectsOpen ? "Скрыть связанные объекты" : "Показать связанные объекты"}
                  aria-label={linkedObjectsOpen ? "Скрыть связанные объекты" : "Показать связанные объекты"}
                  aria-expanded={linkedObjectsOpen}
                >
                  <ChevronRight
                    size={16}
                    className={`transition-transform ${linkedObjectsOpen ? "rotate-90" : ""}`}
                  />
                </button>
              </div>

              {linkedObjectsOpen ? (
                <div className="space-y-2 border-t border-[var(--border-subtle)] p-3">
                  {linkedObjectsLoading ? (
                    <div className="app-surface-muted rounded-xl border border-[var(--border-subtle)] p-4 text-center">
                      <Loader2 size={18} className="mx-auto animate-spin text-sky-500" />
                    </div>
                  ) : linkedObjectsCount > 0 ? (
                    <>
                      {linkedPosts.map((link) => (
                        <LinkedPostCard
                          key={link.id}
                          link={link}
                          onUnlink={unlinkPostFromViewedTask}
                          disabled={saving}
                        />
                      ))}
                      {linkedMessages.map((link) => (
                        <LinkedMessageCard
                          key={link.id}
                          link={link}
                          onUnlink={unlinkMessageFromViewedTask}
                          disabled={saving}
                        />
                      ))}
                      {linkedEvents.map((link) => (
                        <LinkedCalendarEventCard
                          key={link.id}
                          link={link}
                          onUnlink={unlinkEventFromViewedTask}
                          disabled={saving}
                        />
                      ))}
                      {linkedDocuments.map((link) => (
                        <LinkedDocumentCard
                          key={link.id}
                          link={link}
                          onUnlink={unlinkDocumentFromViewedTask}
                          disabled={saving}
                        />
                      ))}
                      {linkedRequests.map((link) => (
                        <LinkedRequestCard
                          key={link.id}
                          link={link}
                          onUnlink={unlinkRequestFromViewedTask}
                          disabled={saving}
                        />
                      ))}
                      {linkedProcurementRequests.map((link) => (
                        <LinkedProcurementRequestCard
                          key={link.id}
                          link={link}
                          onUnlink={unlinkProcurementRequestFromViewedTask}
                          disabled={saving}
                        />
                      ))}
                      {linkedEmployees.map((link) => (
                        <LinkedEmployeeCard
                          key={link.id}
                          link={link}
                          onUnlink={unlinkEmployeeFromViewedTask}
                          disabled={saving}
                        />
                      ))}
                      {linkedGuests.map((link) => (
                        <LinkedGuestCard
                          key={link.id}
                          link={link}
                          onUnlink={unlinkGuestFromViewedTask}
                          disabled={saving}
                        />
                      ))}
                      {linkedGuestVisits.map((link) => (
                        <LinkedGuestVisitCard
                          key={link.id}
                          link={link}
                          onUnlink={unlinkGuestVisitFromViewedTask}
                          disabled={saving}
                        />
                      ))}
                      {linkedAttendanceRecords.map((link) => (
                        <LinkedAttendanceRecordCard
                          key={link.id}
                          link={link}
                          onUnlink={unlinkAttendanceRecordFromViewedTask}
                          disabled={saving}
                        />
                      ))}
                      {taskExternalLinks.map((link) => (
                        <TaskExternalLinkCard
                          key={link.id}
                          link={link}
                          onDelete={deleteExternalLinkFromViewedTask}
                          disabled={saving}
                        />
                      ))}
                    </>
                  ) : (
                    <div className="app-surface-muted rounded-xl border border-dashed border-[var(--border-subtle)] px-3 py-4 text-center">
                      <p className="app-text-muted text-xs">Связанных объектов и ссылок нет</p>
                    </div>
                  )}
                </div>
              ) : null}
            </div>

            <div className="rounded-xl border border-[var(--border-subtle)]">
              <button
                type="button"
                onClick={() => setActivityOpen((current) => !current)}
                className="flex w-full items-center justify-between gap-3 px-3 py-2.5 text-left"
                aria-expanded={activityOpen}
              >
                <span className="flex min-w-0 items-center gap-2">
                  <History size={15} className="app-text-muted shrink-0" />
                  <span className="text-sm font-medium text-[var(--foreground)]">
                    История
                  </span>
                  {taskActivities.length > 0 ? (
                    <span className="app-badge rounded-full px-2 py-0.5 text-[11px]">
                      {taskActivities.length}
                    </span>
                  ) : null}
                </span>
                <ChevronRight
                  size={16}
                  className={`app-text-muted shrink-0 transition-transform ${activityOpen ? "rotate-90" : ""}`}
                />
              </button>

              {activityOpen ? (
                <div className="space-y-2 border-t border-[var(--border-subtle)] p-3">
                  {taskActivityLoading ? (
                    <div className="app-surface-muted rounded-xl border border-[var(--border-subtle)] p-4 text-center">
                      <Loader2 size={18} className="mx-auto animate-spin text-sky-500" />
                    </div>
                  ) : taskActivities.length > 0 ? (
                    taskActivities.map((activity) => (
                      <TaskActivityCard key={activity.id} activity={activity} />
                    ))
                  ) : (
                    <div className="app-surface-muted rounded-xl border border-dashed border-[var(--border-subtle)] px-3 py-4 text-center">
                      <p className="app-text-muted text-xs">Истории действий пока нет</p>
                    </div>
                  )}
                </div>
              ) : null}
            </div>

            <div className="grid gap-3 sm:grid-cols-2">
              <div className="app-surface-muted rounded-xl border border-[var(--border-subtle)] p-3">
                <p className="app-card-caption">Доска</p>
                <p className="mt-1 truncate text-sm font-medium text-[var(--foreground)]">
                  {board?.name || "Не указана"}
                </p>
              </div>
              <div className="app-surface-muted rounded-xl border border-[var(--border-subtle)] p-3">
                <p className="app-card-caption">Создал</p>
                <p className="mt-1 truncate text-sm font-medium text-[var(--foreground)]">
                  {viewTask.created_by ? displayUserName(viewTask.created_by) : "Не указан"}
                </p>
              </div>
              <div className="app-surface-muted rounded-xl border border-[var(--border-subtle)] p-3">
                <p className="app-card-caption">Дата создания</p>
                <p className="mt-1 text-sm font-medium text-[var(--foreground)]">
                  {formatDate(viewTask.created_at)}
                </p>
              </div>
              <div className="app-surface-muted rounded-xl border border-[var(--border-subtle)] p-3">
                <p className="app-card-caption">Колонка</p>
                <p className="mt-1 truncate text-sm font-medium text-[var(--foreground)]">
                  {viewTaskColumn?.name || viewTask.column_name || "Не указана"}
                </p>
              </div>
              <div className="app-surface-muted rounded-xl border border-[var(--border-subtle)] p-3">
                <p className="app-card-caption">Исполнитель</p>
                <p className="mt-1 truncate text-sm font-medium text-[var(--foreground)]">
                  {viewTask.assignee ? displayUserName(viewTask.assignee) : "Не назначен"}
                </p>
              </div>
              {viewTask.completed_at ? (
                <div className="app-surface-muted rounded-xl border border-[var(--border-subtle)] p-3 sm:col-span-2">
                  <p className="app-card-caption">Завершено</p>
                  <p className="mt-1 text-sm font-medium text-[var(--foreground)]">
                    {formatDate(viewTask.completed_at)}
                  </p>
                </div>
              ) : null}
            </div>
          </div>
        ) : null}
      </Modal>

      <Modal
        isOpen={linkedItemModalOpen}
        onClose={closeLinkedItemModal}
        title="Добавить объект или ссылку"
        size="md"
        stackLevel={1}
        closeOnClickOutside
        footer={(
          <div className="flex justify-end gap-2">
            <button
              type="button"
              onClick={closeLinkedItemModal}
              className="app-action-secondary rounded-xl px-4 py-2 text-sm font-medium"
              disabled={saving}
            >
              Отмена
            </button>
            {linkedItemMode === "external_link" ? (
              <button
                type="button"
                onClick={() => {
                  if (linkedItemTarget === "view") {
                    void addExternalLinkToViewedTask();
                  } else {
                    addExternalLinkToTaskForm();
                  }
                }}
                disabled={saving || !externalLinkUrl.trim()}
                className="app-action-primary inline-flex items-center gap-2 rounded-xl px-4 py-2 text-sm font-medium disabled:opacity-60"
              >
                {saving ? <Loader2 size={15} className="animate-spin" /> : <Plus size={15} />}
                Добавить
              </button>
            ) : null}
          </div>
        )}
      >
        <div className="space-y-4">
          <div className="grid grid-cols-3 rounded-xl border border-[var(--border-subtle)] bg-[var(--surface-secondary)] p-1">
            {([
              ["document", "Документ", FileText],
              ["calendar_event", "Событие", CalendarDays],
              ["external_link", "Ссылка", ExternalLinkIcon],
            ] as const).map(([mode, label, Icon]) => (
              <button
                key={mode}
                type="button"
                onClick={() => {
                  setLinkedItemMode(mode);
                  setLinkedItemSearch("");
                }}
                className={`inline-flex min-w-0 items-center justify-center gap-1.5 rounded-lg px-2 py-2 text-xs font-medium transition ${
                  linkedItemMode === mode
                    ? "app-surface text-[var(--foreground)] shadow-sm"
                    : "app-text-muted hover:text-[var(--foreground)]"
                }`}
              >
                <Icon size={14} className="shrink-0" />
                <span className="truncate">{label}</span>
              </button>
            ))}
          </div>

          {linkedItemMode === "external_link" ? (
            <div className="space-y-3">
              <label className="block">
                <span className="app-text-muted mb-1 block text-xs font-medium">Ссылка</span>
                <input
                  type="url"
                  value={externalLinkUrl}
                  onChange={(event) => setExternalLinkUrl(event.target.value)}
                  className="app-input w-full rounded-xl px-3 py-2 text-sm"
                  placeholder="https://service.example/item"
                  autoFocus
                />
              </label>
              <label className="block">
                <span className="app-text-muted mb-1 block text-xs font-medium">Название</span>
                <input
                  value={externalLinkTitle}
                  onChange={(event) => setExternalLinkTitle(event.target.value)}
                  className="app-input w-full rounded-xl px-3 py-2 text-sm"
                  placeholder="Необязательно"
                />
              </label>
            </div>
          ) : (
            <>
              <div className="relative">
                <Search
                  size={15}
                  className="app-text-muted pointer-events-none absolute left-3 top-1/2 -translate-y-1/2"
                />
                <input
                  value={linkedItemSearch}
                  onChange={(event) => setLinkedItemSearch(event.target.value)}
                  className="app-input w-full rounded-xl py-2 pl-9 pr-3 text-sm"
                  placeholder={linkedItemMode === "document" ? "Поиск документов" : "Поиск событий"}
                  autoFocus
                />
              </div>

              <div className="tasks-column-scroll max-h-72 space-y-2 overflow-y-auto pr-1">
                {linkedItemCandidatesLoading ? (
                  <div className="app-surface-muted rounded-xl border border-[var(--border-subtle)] p-5 text-center">
                    <Loader2 size={18} className="mx-auto animate-spin text-sky-500" />
                  </div>
                ) : linkedItemMode === "document" ? (
                  availableDocuments.length > 0 ? (
                    availableDocuments.map((item) => {
                      const alreadyLinked = linkedItemTarget === "view"
                        ? linkedDocuments.some((link) => link.document_id === item.id)
                        : (
                          taskFormDocuments.some((link) => link.document_id === item.id) ||
                          taskFormPendingDocuments.some((document) => document.id === item.id)
                        );
                      return (
                        <button
                          key={item.id}
                          type="button"
                          onClick={() => {
                            if (linkedItemTarget === "view") {
                              void linkDocumentToViewedTask(item.id);
                            } else {
                              addDocumentToTaskForm(item);
                            }
                          }}
                          disabled={saving || alreadyLinked}
                          className="app-surface-muted flex w-full items-start gap-3 rounded-xl border border-[var(--border-subtle)] p-3 text-left transition hover:border-[var(--border-strong)] disabled:cursor-default disabled:opacity-60"
                        >
                          <span className="app-selected flex h-8 w-8 shrink-0 items-center justify-center rounded-lg">
                            <FileText size={15} />
                          </span>
                          <span className="min-w-0 flex-1">
                            <span className="block truncate text-sm font-semibold text-[var(--foreground)]">
                              #{item.id} {item.title}
                            </span>
                            <span className="app-text-muted mt-0.5 block truncate text-xs">
                              {item.folder_path || item.file_name || "Без папки"}
                            </span>
                          </span>
                          {alreadyLinked ? (
                            <span className="app-badge shrink-0 rounded-full px-2 py-0.5 text-[10px]">
                              добавлен
                            </span>
                          ) : (
                            <Plus size={15} className="app-text-muted mt-1 shrink-0" />
                          )}
                        </button>
                      );
                    })
                  ) : (
                    <div className="app-surface-muted rounded-xl border border-dashed border-[var(--border-subtle)] p-5 text-center">
                      <p className="app-text-muted text-xs">Документы не найдены</p>
                    </div>
                  )
                ) : availableEvents.length > 0 ? (
                  availableEvents.map((item) => {
                    const alreadyLinked = linkedItemTarget === "view"
                      ? linkedEvents.some((link) => link.event_id === item.id)
                      : (
                        taskFormEvents.some((link) => link.event_id === item.id) ||
                        taskFormPendingEvents.some((event) => event.id === item.id)
                      );
                    return (
                      <button
                        key={item.id}
                        type="button"
                        onClick={() => {
                          if (linkedItemTarget === "view") {
                            void linkEventToViewedTask(item.id);
                          } else {
                            addEventToTaskForm(item);
                          }
                        }}
                        disabled={saving || alreadyLinked}
                        className="app-surface-muted flex w-full items-start gap-3 rounded-xl border border-[var(--border-subtle)] p-3 text-left transition hover:border-[var(--border-strong)] disabled:cursor-default disabled:opacity-60"
                      >
                        <span className="app-selected flex h-8 w-8 shrink-0 items-center justify-center rounded-lg">
                          <CalendarDays size={15} />
                        </span>
                        <span className="min-w-0 flex-1">
                          <span className="block truncate text-sm font-semibold text-[var(--foreground)]">
                            #{item.id} {item.title}
                          </span>
                          <span className="app-text-muted mt-0.5 block truncate text-xs">
                            {formatDateTime(item.start)}
                            {item.calendar_name ? ` · ${item.calendar_name}` : ""}
                          </span>
                        </span>
                        {alreadyLinked ? (
                          <span className="app-badge shrink-0 rounded-full px-2 py-0.5 text-[10px]">
                            добавлено
                          </span>
                        ) : (
                          <Plus size={15} className="app-text-muted mt-1 shrink-0" />
                        )}
                      </button>
                    );
                  })
                ) : (
                  <div className="app-surface-muted rounded-xl border border-dashed border-[var(--border-subtle)] p-5 text-center">
                    <p className="app-text-muted text-xs">События не найдены</p>
                  </div>
                )}
              </div>
            </>
          )}
        </div>
      </Modal>

      <Modal
        isOpen={taskModalOpen}
        onClose={closeTaskModal}
        title={form.id ? "Редактировать задачу" : "Новая задача"}
        size="lg"
        closeOnClickOutside
        footer={(
          <div className="flex justify-end gap-2">
            <button
              type="button"
              onClick={closeTaskModal}
              className="app-action-secondary rounded-xl px-4 py-2 text-sm font-medium"
              disabled={saving}
            >
              Отмена
            </button>
            <button
              type="button"
              onClick={() => void saveTask()}
              disabled={saving || !form.title.trim() || !form.column || taskFormChecklistHasInvalidTitle}
              className="app-action-primary inline-flex items-center gap-2 rounded-xl px-4 py-2 text-sm font-medium disabled:opacity-60"
            >
              {saving ? <Loader2 size={16} className="animate-spin" /> : null}
              Сохранить
            </button>
          </div>
        )}
      >
        <div className="space-y-4">
          <div className="app-surface-muted flex items-center gap-2 rounded-xl border border-[var(--border-subtle)] px-3 py-2">
            <Kanban size={15} className="app-text-muted shrink-0" />
            <div className="min-w-0">
              <p className="app-card-caption">Доска</p>
              <p className="truncate text-sm font-medium text-[var(--foreground)]">
                {board?.name || "Не указана"}
              </p>
            </div>
          </div>

          <label className="block">
            <span className="app-text-muted mb-1 block text-xs font-medium">Название</span>
            <input
              value={form.title}
              onChange={(event) => setForm((current) => ({ ...current, title: event.target.value }))}
              className="app-input w-full rounded-xl px-3 py-2 text-sm"
              autoFocus
            />
          </label>

          <label className="block">
            <span className="app-text-muted mb-1 block text-xs font-medium">Описание</span>
            <textarea
              value={form.description}
              onChange={(event) => setForm((current) => ({ ...current, description: event.target.value }))}
              rows={4}
              className="app-input w-full rounded-xl px-3 py-2 text-sm"
            />
          </label>

          <div className="rounded-xl border border-[var(--border-subtle)]">
            <div className="flex items-center px-1 py-1">
              <button
                type="button"
                onClick={() => setTaskFormChecklistOpen((current) => !current)}
                className="flex min-w-0 flex-1 items-center gap-2 rounded-lg px-2 py-1.5 text-left"
                aria-expanded={taskFormChecklistOpen}
              >
                <ListChecks size={15} className="app-text-muted shrink-0" />
                <span className="truncate text-sm font-medium text-[var(--foreground)]">
                  Чек-лист
                </span>
                <span className="app-badge rounded-full px-2 py-0.5 text-[11px]">
                  {taskFormChecklistCompleted}/{taskFormChecklistTotal}
                </span>
              </button>
              <button
                type="button"
                onClick={() => setTaskFormChecklistOpen((current) => !current)}
                className="app-icon-button flex h-8 w-8 shrink-0 items-center justify-center rounded-lg"
                title={taskFormChecklistOpen ? "Скрыть чек-лист" : "Показать чек-лист"}
                aria-label={taskFormChecklistOpen ? "Скрыть чек-лист" : "Показать чек-лист"}
                aria-expanded={taskFormChecklistOpen}
              >
                <ChevronRight
                  size={16}
                  className={`transition-transform ${taskFormChecklistOpen ? "rotate-90" : ""}`}
                />
              </button>
            </div>

            {taskFormChecklistOpen ? (
              <div className="space-y-3 border-t border-[var(--border-subtle)] p-3">
                {taskFormResourcesLoading ? (
                  <div className="app-surface-muted rounded-xl border border-[var(--border-subtle)] p-4 text-center">
                    <Loader2 size={18} className="mx-auto animate-spin text-sky-500" />
                  </div>
                ) : taskFormChecklistTotal > 0 ? (
                  <div className="overflow-hidden rounded-lg border border-[var(--border-subtle)]">
                    {taskFormChecklistItems.map((item) => (
                      <TaskChecklistFormRow
                        key={`checklist-${item.id}`}
                        title={item.title}
                        isCompleted={item.is_completed}
                        disabled={saving}
                        onTitleChange={(title) => updateExistingTaskFormChecklistItem(item.id, { title })}
                        onCompletedChange={(is_completed) => updateExistingTaskFormChecklistItem(item.id, { is_completed })}
                        onRemove={() => removeExistingTaskFormChecklistItem(item)}
                      />
                    ))}
                    {taskFormPendingChecklistItems.map((item) => (
                      <TaskChecklistFormRow
                        key={item.key}
                        title={item.title}
                        isCompleted={item.is_completed}
                        pending
                        disabled={saving}
                        onTitleChange={(title) => updatePendingTaskFormChecklistItem(item.key, { title })}
                        onCompletedChange={(is_completed) => updatePendingTaskFormChecklistItem(item.key, { is_completed })}
                        onRemove={() => setTaskFormPendingChecklistItems((current) => (
                          current.filter((currentItem) => currentItem.key !== item.key)
                        ))}
                      />
                    ))}
                  </div>
                ) : (
                  <div className="app-surface-muted rounded-xl border border-dashed border-[var(--border-subtle)] px-3 py-4 text-center">
                    <p className="app-text-muted text-xs">Пунктов пока нет</p>
                  </div>
                )}

                <div className="flex items-center gap-2">
                  <input
                    ref={taskFormChecklistDraftRef}
                    value={taskFormChecklistDraft}
                    onChange={(event) => setTaskFormChecklistDraft(event.target.value)}
                    onKeyDown={(event) => {
                      if (event.key !== "Enter") return;
                      event.preventDefault();
                      addTaskFormChecklistItem();
                    }}
                    disabled={saving}
                    className="app-input min-w-0 flex-1 rounded-xl px-3 py-2 text-sm"
                    placeholder="Новый пункт"
                  />
                  <button
                    type="button"
                    onClick={addTaskFormChecklistItem}
                    disabled={saving || !taskFormChecklistDraft.trim()}
                    className="app-icon-button flex h-9 w-9 shrink-0 items-center justify-center rounded-lg disabled:opacity-50"
                    title="Добавить пункт"
                    aria-label="Добавить пункт чек-листа"
                  >
                    <Plus size={15} />
                  </button>
                </div>
              </div>
            ) : null}
          </div>

          <div className="grid gap-3 md:grid-cols-2">
            <label className="block">
              <span className="app-text-muted mb-1 block text-xs font-medium">Колонка</span>
              <select
                value={form.column}
                onChange={(event) => setForm((current) => ({ ...current, column: Number(event.target.value) || "" }))}
                className="app-select w-full rounded-xl px-3 py-2 text-sm"
              >
                {(board?.columns || []).filter((column) => !column.is_archived).map((column) => (
                  <option key={column.id} value={column.id}>{column.name}</option>
                ))}
              </select>
            </label>

            <label className="block">
              <span className="app-text-muted mb-1 block text-xs font-medium">Исполнитель</span>
              <select
                value={form.assignee_id}
                onChange={(event) => setForm((current) => ({ ...current, assignee_id: Number(event.target.value) || "" }))}
                className="app-select w-full rounded-xl px-3 py-2 text-sm"
              >
                <option value="">Не назначен</option>
                {employees.map((employee) => (
                  <option key={employee.id} value={employee.id}>
                    {displayUserName(employee)}
                  </option>
                ))}
              </select>
            </label>

            <label className="block">
              <span className="app-text-muted mb-1 block text-xs font-medium">Приоритет</span>
              <select
                value={form.priority}
                onChange={(event) => setForm((current) => ({ ...current, priority: event.target.value as TaskPriority }))}
                className="app-select w-full rounded-xl px-3 py-2 text-sm"
              >
                {priorityOptions.map((option) => (
                  <option key={option.value} value={option.value}>{option.label}</option>
                ))}
              </select>
            </label>

            <label className="block">
              <span className="app-text-muted mb-1 block text-xs font-medium">Срок</span>
              <input
                type="date"
                value={form.due_date}
                onChange={(event) => setForm((current) => ({ ...current, due_date: event.target.value }))}
                className="app-input w-full rounded-xl px-3 py-2 text-sm"
              />
            </label>
          </div>

          <div>
            <div className="mb-2 flex items-center gap-2">
              <Tag size={15} className="app-text-muted" />
              <span className="app-text-muted text-xs font-medium">Метки</span>
            </div>
            <div className="flex flex-wrap gap-2">
              {(board?.labels || []).map((label) => {
                const selected = form.label_ids.includes(label.id);
                return (
                  <button
                    key={label.id}
                    type="button"
                    onClick={() => toggleLabel(label.id)}
                    className={`rounded-full border px-3 py-1 text-xs font-medium transition ${
                      selected ? "border-transparent text-white" : "border-[var(--border-subtle)] text-[var(--muted-foreground)]"
                    }`}
                    style={selected ? { backgroundColor: label.color } : undefined}
                  >
                    {label.name}
                  </button>
                );
              })}
            </div>
            <div className="mt-3 grid gap-2 md:grid-cols-[auto_1fr_auto]">
              <input
                type="color"
                value={labelColor}
                onChange={(event) => setLabelColor(event.target.value)}
                className="h-10 w-14 rounded-lg border border-[var(--border-subtle)] bg-transparent p-1"
                aria-label="Цвет метки"
              />
              <input
                value={labelName}
                onChange={(event) => setLabelName(event.target.value)}
                className="app-input min-w-0 rounded-xl px-3 py-2 text-sm"
                placeholder="Новая метка"
              />
              <button
                type="button"
                onClick={() => void createLabel()}
                disabled={saving || !labelName.trim()}
                className="app-action-secondary rounded-xl px-3 py-2 text-sm font-medium disabled:opacity-60"
              >
                Добавить
              </button>
            </div>
          </div>

          <div className="rounded-xl border border-[var(--border-subtle)]">
            <div className="flex items-center px-1 py-1">
              <button
                type="button"
                onClick={() => setTaskFormFilesOpen((current) => !current)}
                className="flex min-w-0 flex-1 items-center gap-2 rounded-lg px-2 py-1.5 text-left"
                aria-expanded={taskFormFilesOpen}
              >
                <Paperclip size={15} className="app-text-muted shrink-0" />
                <span className="truncate text-sm font-medium text-[var(--foreground)]">
                  Файлы
                </span>
                <span className="app-badge rounded-full px-2 py-0.5 text-[11px]">
                  {taskFormAttachmentsCount}
                </span>
              </button>
              <input
                ref={taskFormAttachmentInputRef}
                type="file"
                multiple
                className="sr-only"
                disabled={saving}
                onChange={(event) => {
                  const files = Array.from(event.currentTarget.files || []);
                  event.currentTarget.value = "";
                  addFilesToTaskForm(files);
                }}
              />
              <button
                type="button"
                onClick={() => taskFormAttachmentInputRef.current?.click()}
                disabled={saving}
                className="app-icon-button flex h-8 w-8 shrink-0 items-center justify-center rounded-lg disabled:opacity-50"
                title="Добавить файлы"
                aria-label="Добавить файлы"
              >
                <Plus size={15} />
              </button>
              <button
                type="button"
                onClick={() => setTaskFormFilesOpen((current) => !current)}
                className="app-icon-button flex h-8 w-8 shrink-0 items-center justify-center rounded-lg"
                title={taskFormFilesOpen ? "Скрыть файлы" : "Показать файлы"}
                aria-label={taskFormFilesOpen ? "Скрыть файлы" : "Показать файлы"}
                aria-expanded={taskFormFilesOpen}
              >
                <ChevronRight
                  size={16}
                  className={`transition-transform ${taskFormFilesOpen ? "rotate-90" : ""}`}
                />
              </button>
            </div>

            {taskFormFilesOpen ? (
              <div className="border-t border-[var(--border-subtle)] p-3">
                {taskFormResourcesLoading ? (
                  <div className="app-surface-muted rounded-xl border border-[var(--border-subtle)] p-4 text-center">
                    <Loader2 size={18} className="mx-auto animate-spin text-sky-500" />
                  </div>
                ) : taskFormAttachmentsCount > 0 ? (
                  <div className="overflow-hidden rounded-lg border border-[var(--border-subtle)]">
                    {taskFormAttachments.map((attachment) => (
                      <TaskFormResourceRow
                        key={`attachment-${attachment.id}`}
                        icon={FileText}
                        title={attachment.file_name}
                        meta={formatFileSize(attachment.file_size)}
                        onRemove={() => removeExistingTaskFormAttachment(attachment)}
                      />
                    ))}
                    {taskFormPendingFiles.map((file) => (
                      <TaskFormResourceRow
                        key={`pending-file-${file.name}-${file.size}-${file.lastModified}`}
                        icon={FileText}
                        title={file.name}
                        meta={formatFileSize(file.size)}
                        pending
                        onRemove={() => setTaskFormPendingFiles((current) => (
                          current.filter((item) => item !== file)
                        ))}
                      />
                    ))}
                  </div>
                ) : (
                  <div className="app-surface-muted rounded-xl border border-dashed border-[var(--border-subtle)] p-4 text-center">
                    <p className="app-text-muted text-xs">Файлов пока нет</p>
                  </div>
                )}
              </div>
            ) : null}
          </div>

          <div className="rounded-xl border border-[var(--border-subtle)]">
            <div className="flex items-center px-1 py-1">
              <button
                type="button"
                onClick={() => setTaskFormLinksOpen((current) => !current)}
                className="flex min-w-0 flex-1 items-center gap-2 rounded-lg px-2 py-1.5 text-left"
                aria-expanded={taskFormLinksOpen}
              >
                <Link2 size={15} className="app-text-muted shrink-0" />
                <span className="truncate text-sm font-medium text-[var(--foreground)]">
                  Связанные объекты и ссылки
                </span>
                <span className="app-badge rounded-full px-2 py-0.5 text-[11px]">
                  {taskFormLinksCount}
                </span>
              </button>
              <button
                type="button"
                onClick={openLinkedItemModalForForm}
                disabled={saving}
                className="app-icon-button flex h-8 w-8 shrink-0 items-center justify-center rounded-lg disabled:opacity-50"
                title="Добавить объект или ссылку"
                aria-label="Добавить объект или ссылку"
              >
                <Plus size={15} />
              </button>
              <button
                type="button"
                onClick={() => setTaskFormLinksOpen((current) => !current)}
                className="app-icon-button flex h-8 w-8 shrink-0 items-center justify-center rounded-lg"
                title={taskFormLinksOpen ? "Скрыть связи" : "Показать связи"}
                aria-label={taskFormLinksOpen ? "Скрыть связи" : "Показать связи"}
                aria-expanded={taskFormLinksOpen}
              >
                <ChevronRight
                  size={16}
                  className={`transition-transform ${taskFormLinksOpen ? "rotate-90" : ""}`}
                />
              </button>
            </div>

            {taskFormLinksOpen ? (
              <div className="border-t border-[var(--border-subtle)] p-3">
                {taskFormResourcesLoading ? (
                  <div className="app-surface-muted rounded-xl border border-[var(--border-subtle)] p-4 text-center">
                    <Loader2 size={18} className="mx-auto animate-spin text-sky-500" />
                  </div>
                ) : taskFormLinksCount > 0 ? (
                  <div className="overflow-hidden rounded-lg border border-[var(--border-subtle)]">
                    {taskFormDocuments.map((link) => (
                      <TaskFormResourceRow
                        key={`document-${link.id}`}
                        icon={FileText}
                        title={`#${link.document_id} ${link.document?.title || "Документ"}`}
                        meta="Документ"
                        onRemove={() => removeExistingTaskFormDocument(link)}
                      />
                    ))}
                    {taskFormPendingDocuments.map((document) => (
                      <TaskFormResourceRow
                        key={`pending-document-${document.id}`}
                        icon={FileText}
                        title={`#${document.id} ${document.title}`}
                        meta="Документ"
                        pending
                        onRemove={() => setTaskFormPendingDocuments((current) => (
                          current.filter((item) => item.id !== document.id)
                        ))}
                      />
                    ))}
                    {taskFormEvents.map((link) => (
                      <TaskFormResourceRow
                        key={`event-${link.id}`}
                        icon={CalendarDays}
                        title={`#${link.event_id} ${link.event?.title || "Событие"}`}
                        meta={link.event?.start ? formatDateTime(link.event.start) : "Событие календаря"}
                        onRemove={() => removeExistingTaskFormEvent(link)}
                      />
                    ))}
                    {taskFormPendingEvents.map((event) => (
                      <TaskFormResourceRow
                        key={`pending-event-${event.id}`}
                        icon={CalendarDays}
                        title={`#${event.id} ${event.title}`}
                        meta={formatDateTime(event.start)}
                        pending
                        onRemove={() => setTaskFormPendingEvents((current) => (
                          current.filter((item) => item.id !== event.id)
                        ))}
                      />
                    ))}
                    {taskFormExternalLinks.map((link) => (
                      <TaskFormResourceRow
                        key={`external-link-${link.id}`}
                        icon={ExternalLinkIcon}
                        title={link.title || getExternalLinkHost(link.url)}
                        meta={link.url}
                        onRemove={() => removeExistingTaskFormExternalLink(link)}
                      />
                    ))}
                    {taskFormPendingExternalLinks.map((link) => (
                      <TaskFormResourceRow
                        key={`pending-external-link-${link.key}`}
                        icon={ExternalLinkIcon}
                        title={link.title || getExternalLinkHost(link.url)}
                        meta={link.url}
                        pending
                        onRemove={() => setTaskFormPendingExternalLinks((current) => (
                          current.filter((item) => item.key !== link.key)
                        ))}
                      />
                    ))}
                  </div>
                ) : (
                  <div className="app-surface-muted rounded-xl border border-dashed border-[var(--border-subtle)] p-4 text-center">
                    <p className="app-text-muted text-xs">Связанных объектов и ссылок пока нет</p>
                  </div>
                )}
              </div>
            ) : null}
          </div>
        </div>
      </Modal>
    </AppShell>
  );
}
