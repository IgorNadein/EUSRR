"use client";

import { Edit2, Trash2, Clock, Calendar, FileText, Users, Link2, Loader2 } from "lucide-react";
import { Modal } from "@/components/ui";
import { resolveEventColor } from "@/lib/calendar-event-colors";
import { format } from "date-fns";
import { ru } from "date-fns/locale";
import { useState, useEffect, useCallback } from "react";
import { apiClient } from "@/lib/api";
import type { TaskBoard, TaskCard } from "@/types/api";

type EventRuleData = {
  frequency?: string;
  params?: {
    byweekday?: unknown;
    count?: number | string;
  };
};

type EventDetails = Record<string, unknown> & {
  id?: number;
  title?: string;
  description?: string;
  start?: string | Date | null;
  end?: string | Date | null;
  calendar?: number | null;
  color_event?: string | null;
  can_edit?: boolean;
  can_delete?: boolean;
  rule?: number | null;
  rule_data?: EventRuleData | null;
  end_recurring_period?: string | Date | null;
};

type EventParticipant = {
  id: number | string;
  user_name?: string;
  distinction?: string;
};

interface ViewEventDetailsModalProps {
  isOpen: boolean;
  onClose: () => void;
  event: EventDetails | null;
  onEdit: () => void;
  onDelete: () => void;
  showParticipants?: boolean;
}

// Маппинг частот на русский
const FREQUENCY_LABELS: Record<string, string> = {
  YEARLY: "Каждый год",
  MONTHLY: "Каждый месяц",
  WEEKLY: "Каждую неделю",
  DAILY: "Каждый день",
  HOURLY: "Каждый час",
  MINUTELY: "Каждую минуту",
  SECONDLY: "Каждую секунду",
};

// Маппинг дней недели (0 = Monday в dateutil.rrule)
const WEEKDAY_LABELS: Record<number, string> = {
  0: "ПН",
  1: "ВТ",
  2: "СР",
  3: "ЧТ",
  4: "ПТ",
  5: "СБ",
  6: "ВС",
};

// Нормализация byweekday в массив чисел
function normalizeByweekday(byweekday: unknown): number[] {
  if (!byweekday) return [];
  if (Array.isArray(byweekday)) {
    return byweekday
      .map((day) => Number(day))
      .filter((day) => Number.isFinite(day));
  }
  if (typeof byweekday === 'string') {
    return byweekday.split(',').map(d => parseInt(d.trim(), 10)).filter(n => !isNaN(n));
  }
  if (typeof byweekday === 'number') return [byweekday];
  return [];
}

export function ViewEventDetailsModal({
  isOpen,
  onClose,
  event,
  onEdit,
  onDelete,
  showParticipants = false,
}: ViewEventDetailsModalProps) {
  const [participants, setParticipants] = useState<EventParticipant[]>([]);
  const [loadingParticipants, setLoadingParticipants] = useState(false);
  const [taskLinkOpen, setTaskLinkOpen] = useState(false);
  const [taskLinkBoards, setTaskLinkBoards] = useState<TaskBoard[]>([]);
  const [taskLinkBoardId, setTaskLinkBoardId] = useState<number | "">("");
  const [taskLinkTaskId, setTaskLinkTaskId] = useState<number | "">("");
  const [taskLinkMode, setTaskLinkMode] = useState<"existing" | "create">("existing");
  const [taskLinkTitle, setTaskLinkTitle] = useState("");
  const [taskLinkDescription, setTaskLinkDescription] = useState("");
  const [taskLinkLoading, setTaskLinkLoading] = useState(false);
  const [taskLinkError, setTaskLinkError] = useState<string | null>(null);

  const loadParticipants = useCallback(async () => {
    if (!event?.id) return;

    try {
      setLoadingParticipants(true);
      const result = await apiClient.getEventParticipants(event.id);
      const participantsList = (Array.isArray(result) ? result : (result?.results || [])) as EventParticipant[];
      setParticipants(participantsList);
    } catch (error) {
      console.error("Failed to load participants:", error);
    } finally {
      setLoadingParticipants(false);
    }
  }, [event?.id]);

  useEffect(() => {
    if (isOpen && event?.id && showParticipants) {
      void loadParticipants();
    } else {
      setParticipants([]);
    }
  }, [isOpen, event?.id, showParticipants, loadParticipants]);

  if (!isOpen || !event) return null;

  const formatDateTime = (dateStr?: string | Date | null) => {
    if (!dateStr) return "";
    const date = new Date(dateStr);
    return format(date, "d MMMM yyyy, HH:mm", { locale: ru });
  };

  const formatDate = (dateStr?: string | Date | null) => {
    if (!dateStr) return "";
    const date = new Date(dateStr);
    return format(date, "d MMMM yyyy", { locale: ru });
  };

  const formattedStart = formatDateTime(event.start);
  const formattedEnd = formatDateTime(event.end);
  const capitalizedStart = formattedStart.charAt(0).toUpperCase() + formattedStart.slice(1);
  const capitalizedEnd = formattedEnd.charAt(0).toUpperCase() + formattedEnd.slice(1);
  const canEdit = event.can_edit !== false;
  const canDelete = event.can_delete !== false;
  const ruleFrequency = typeof event.rule_data?.frequency === "string"
    ? event.rule_data.frequency
    : "";
  const ruleFrequencyLabel = ruleFrequency
    ? FREQUENCY_LABELS[ruleFrequency] || ruleFrequency
    : "";
  const ruleParams = event.rule_data?.params;
  const selectedTaskLinkBoard = taskLinkBoards.find((board) => board.id === taskLinkBoardId) || null;
  const selectedTaskLinkTask = (selectedTaskLinkBoard?.tasks || []).find((task) => task.id === taskLinkTaskId) || null;
  const selectedTaskLinkColumn = (selectedTaskLinkBoard?.columns || []).find((column) => !column.is_archived) || null;

  const openTaskLinkModal = async () => {
    if (!event?.id) return;
    setTaskLinkOpen(true);
    setTaskLinkError(null);
    setTaskLinkLoading(true);
    setTaskLinkTitle(event.title || "Задача по событию");
    setTaskLinkDescription(event.description || "");
    try {
      const response = await apiClient.getTaskBoards();
      const boards = (response.results || response || []) as TaskBoard[];
      setTaskLinkBoards(boards);
      const firstBoardWithTasks = boards.find((board) => (board.tasks || []).length > 0) || boards[0] || null;
      setTaskLinkBoardId(firstBoardWithTasks?.id || "");
      setTaskLinkTaskId(firstBoardWithTasks?.tasks?.[0]?.id || "");
      setTaskLinkMode(firstBoardWithTasks?.tasks?.length ? "existing" : "create");
    } catch (error) {
      setTaskLinkError(error instanceof Error ? error.message : "Не удалось загрузить задачи");
    } finally {
      setTaskLinkLoading(false);
    }
  };

  const closeTaskLinkModal = () => {
    if (taskLinkLoading) return;
    setTaskLinkOpen(false);
    setTaskLinkError(null);
    setTaskLinkBoardId("");
    setTaskLinkTaskId("");
    setTaskLinkMode("existing");
    setTaskLinkTitle("");
    setTaskLinkDescription("");
  };

  const handleTaskLinkBoardChange = (boardId: number | "") => {
    setTaskLinkBoardId(boardId);
    const nextBoard = taskLinkBoards.find((board) => board.id === boardId) || null;
    setTaskLinkTaskId(nextBoard?.tasks?.[0]?.id || "");
    if (!nextBoard?.tasks?.length) {
      setTaskLinkMode("create");
    }
  };

  const saveTaskLink = async () => {
    if (!event?.id || !selectedTaskLinkBoard) return;
    if (taskLinkMode === "existing" && !selectedTaskLinkTask) return;
    if (taskLinkMode === "create" && !taskLinkTitle.trim()) return;

    setTaskLinkLoading(true);
    setTaskLinkError(null);
    try {
      let taskToLink = selectedTaskLinkTask;
      if (taskLinkMode === "create") {
        if (!selectedTaskLinkColumn) {
          setTaskLinkError("На выбранной доске нет колонки для новой задачи");
          return;
        }
        taskToLink = await apiClient.createTask({
          board: selectedTaskLinkBoard.id,
          column: selectedTaskLinkColumn.id,
          title: taskLinkTitle.trim(),
          description: taskLinkDescription.trim(),
          priority: "medium",
        });
      }

      if (!taskToLink) return;
      await apiClient.linkTaskCalendarEvent(taskToLink.id, event.id);
      closeTaskLinkModal();
    } catch (error) {
      setTaskLinkError(error instanceof Error ? error.message : "Не удалось связать событие с задачей");
    } finally {
      setTaskLinkLoading(false);
    }
  };

  return (
    <>
      <Modal
        isOpen={isOpen}
        onClose={onClose}
        title={event.title}
        size="sm"
        footer={canEdit || canDelete || event.id ? (
          <div className="flex flex-wrap gap-2">
            {event.id ? (
              <button
                onClick={() => void openTaskLinkModal()}
                className="app-action-secondary flex flex-1 items-center justify-center gap-2 rounded-lg px-4 py-2.5 text-sm font-medium"
              >
                <Link2 size={16} />
                Связать с задачей
              </button>
            ) : null}
            {canEdit ? (
              <button
                onClick={onEdit}
                className="app-action-primary flex flex-1 items-center justify-center gap-2 rounded-lg px-4 py-2.5 text-sm font-medium"
              >
                <Edit2 size={16} />
                Редактировать
              </button>
            ) : null}
            {canDelete ? (
              <button
                onClick={onDelete}
                className="app-action-danger rounded-lg px-4 py-2.5 text-sm font-medium"
                title="Удалить событие"
              >
                <Trash2 size={16} />
              </button>
            ) : null}
          </div>
        ) : undefined}
      >
      <div className="space-y-4">
        {/* Event meta */}
        <div className="flex items-center gap-2">
          {event.rule && (
            <span className="app-badge app-badge-accent shrink-0 rounded px-1.5 py-0.5 text-xs">
              ⟲
            </span>
          )}
          <div className="app-text-muted flex items-center gap-1.5 text-xs">
            <div
              className="h-2.5 w-2.5 rounded-full flex-shrink-0"
              style={{ backgroundColor: resolveEventColor(event.color_event) }}
            />
            <span className="truncate">Календарь #{event.calendar}</span>
          </div>
        </div>
          {/* Time */}
          <div className="flex items-start gap-2.5">
            <Clock size={18} className="app-text-muted mt-0.5 flex-shrink-0" />
            <div className="flex-1">
              <p className="mb-1 text-sm font-medium text-[var(--foreground)]">Время</p>
              <p className="app-text-muted text-xs">
                <span className="font-medium">Начало:</span> {capitalizedStart}
              </p>
              <p className="app-text-muted mt-0.5 text-xs">
                <span className="font-medium">Конец:</span> {capitalizedEnd}
              </p>
            </div>
          </div>

          {/* Recurring Info */}
          {event.rule && event.rule_data && (
            <div className="app-selected space-y-2 rounded-lg p-4">
              <div className="app-accent-text flex items-center gap-2 text-sm font-medium">
                <Calendar size={16} />
                <span>Повторяющееся событие</span>
              </div>
              <div className="app-accent-text space-y-1 text-sm">
                <div>
                  Частота: <span className="font-medium">{ruleFrequencyLabel}</span>
                </div>
                {Boolean(ruleParams?.byweekday) && (
                  <div>
                    Дни недели: <span className="font-medium">
                      {normalizeByweekday(ruleParams?.byweekday).map((day: number) => WEEKDAY_LABELS[day]).join(", ")}
                    </span>
                  </div>
                )}
                {Boolean(ruleParams?.count) && (
                  <div>
                    Повторений: <span className="font-medium">{String(ruleParams?.count)}</span>
                  </div>
                )}
                {event.end_recurring_period && (
                  <div>
                    До: <span className="font-medium">{formatDate(event.end_recurring_period)}</span>
                  </div>
                )}
              </div>

            </div>
          )}

          {/* Description */}
          {event.description && (
            <div className="flex items-start gap-2.5">
              <FileText size={18} className="app-text-muted mt-0.5 flex-shrink-0" />
              <div className="flex-1">
                <p className="mb-1 text-sm font-medium text-[var(--foreground)]">Описание</p>
                <p className="app-text-wrap app-text-muted whitespace-pre-wrap text-xs">
                  {event.description}
                </p>
              </div>
            </div>
          )}

          {/* Participants */}
          {showParticipants && (
            <div className="flex items-start gap-2.5">
              <Users size={18} className="app-text-muted mt-0.5 flex-shrink-0" />
              <div className="flex-1">
                <p className="mb-1.5 text-sm font-medium text-[var(--foreground)]">
                  Участники {participants.length > 0 && `(${participants.length})`}
                </p>
                {loadingParticipants ? (
                  <p className="app-text-muted text-xs">Загрузка...</p>
                ) : participants.length > 0 ? (
                  <div className="space-y-1.5">
                    {participants.map((participant) => (
                      <div
                        key={participant.id}
                        className="app-surface-muted flex items-center gap-2 rounded-lg px-2.5 py-2"
                      >
                        <div className="app-avatar-fallback flex h-6 w-6 flex-shrink-0 items-center justify-center rounded-full">
                          <span className="text-xs font-medium">
                            {participant.user_name?.[0] || "?"}
                          </span>
                        </div>
                        <div className="text-xs flex-1 min-w-0">
                          <div className="truncate font-medium text-[var(--foreground)]">
                            {participant.user_name}
                          </div>
                          <div className="app-text-muted">
                            {participant.distinction || "attendee"}
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="app-text-muted text-xs">Нет участников</p>
                )}
              </div>
            </div>
          )}

      </div>
      </Modal>

      <Modal
        isOpen={taskLinkOpen}
        onClose={closeTaskLinkModal}
        title="Связать с задачей"
        size="md"
        closeOnClickOutside
        footer={(
          <div className="flex justify-end gap-2">
            <button
              type="button"
              onClick={closeTaskLinkModal}
              className="app-action-secondary rounded-xl px-4 py-2 text-sm font-medium"
              disabled={taskLinkLoading}
            >
              Отмена
            </button>
            <button
              type="button"
              onClick={() => void saveTaskLink()}
              className="app-action-primary inline-flex items-center gap-2 rounded-xl px-4 py-2 text-sm font-medium disabled:opacity-60"
              disabled={
                taskLinkLoading ||
                (taskLinkMode === "existing"
                  ? !selectedTaskLinkTask
                  : !taskLinkTitle.trim() || !selectedTaskLinkColumn)
              }
            >
              {taskLinkLoading ? <Loader2 size={16} className="animate-spin" /> : <Link2 size={16} />}
              {taskLinkMode === "create" ? "Создать и связать" : "Связать"}
            </button>
          </div>
        )}
      >
        <div className="space-y-4">
          <div className="app-surface-muted rounded-xl border border-[var(--border-subtle)] p-3">
            <p className="app-card-caption">Событие</p>
            <p className="app-text-wrap mt-1 line-clamp-3 text-sm text-[var(--foreground)]">
              {event.title}
            </p>
          </div>

          <label className="block">
            <span className="app-text-muted mb-1 block text-xs font-medium">Доска</span>
            <select
              value={taskLinkBoardId}
              onChange={(selectEvent) => handleTaskLinkBoardChange(Number(selectEvent.target.value) || "")}
              className="app-select w-full rounded-xl px-3 py-2 text-sm"
              disabled={taskLinkLoading}
            >
              <option value="">Выберите доску</option>
              {taskLinkBoards.map((board) => (
                <option key={board.id} value={board.id}>
                  {board.name}
                </option>
              ))}
            </select>
          </label>

          <div className="grid grid-cols-2 gap-2">
            <button
              type="button"
              onClick={() => setTaskLinkMode("existing")}
              className={`rounded-xl border px-3 py-2 text-sm font-medium transition ${
                taskLinkMode === "existing"
                  ? "app-selected border-[var(--accent-primary)]"
                  : "border-[var(--border-subtle)] text-[var(--muted-foreground)] hover:border-[var(--border-strong)]"
              }`}
              disabled={taskLinkLoading || !selectedTaskLinkBoard || (selectedTaskLinkBoard.tasks || []).length === 0}
            >
              Выбрать задачу
            </button>
            <button
              type="button"
              onClick={() => setTaskLinkMode("create")}
              className={`rounded-xl border px-3 py-2 text-sm font-medium transition ${
                taskLinkMode === "create"
                  ? "app-selected border-[var(--accent-primary)]"
                  : "border-[var(--border-subtle)] text-[var(--muted-foreground)] hover:border-[var(--border-strong)]"
              }`}
              disabled={taskLinkLoading || !selectedTaskLinkBoard}
            >
              Создать задачу
            </button>
          </div>

          {taskLinkMode === "existing" ? (
            <label className="block">
              <span className="app-text-muted mb-1 block text-xs font-medium">Задача</span>
              <select
                value={taskLinkTaskId}
                onChange={(selectEvent) => setTaskLinkTaskId(Number(selectEvent.target.value) || "")}
                className="app-select w-full rounded-xl px-3 py-2 text-sm"
                disabled={taskLinkLoading || !selectedTaskLinkBoard}
              >
                <option value="">Выберите задачу</option>
                {(selectedTaskLinkBoard?.tasks || []).map((task: TaskCard) => (
                  <option key={task.id} value={task.id}>
                    {task.title}
                  </option>
                ))}
              </select>
            </label>
          ) : (
            <div className="space-y-3">
              <label className="block">
                <span className="app-text-muted mb-1 block text-xs font-medium">Название задачи</span>
                <input
                  value={taskLinkTitle}
                  onChange={(inputEvent) => setTaskLinkTitle(inputEvent.target.value)}
                  className="app-input w-full rounded-xl px-3 py-2 text-sm"
                  disabled={taskLinkLoading}
                  placeholder="Название новой задачи"
                />
              </label>
              <label className="block">
                <span className="app-text-muted mb-1 block text-xs font-medium">Описание</span>
                <textarea
                  value={taskLinkDescription}
                  onChange={(inputEvent) => setTaskLinkDescription(inputEvent.target.value)}
                  className="app-input w-full rounded-xl px-3 py-2 text-sm"
                  disabled={taskLinkLoading}
                  rows={3}
                />
              </label>
            </div>
          )}

          {taskLinkError ? (
            <div className="app-feedback-danger rounded-xl px-3 py-2 text-sm">
              {taskLinkError}
            </div>
          ) : null}
        </div>
      </Modal>
    </>
  );
}
