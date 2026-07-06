"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { ChevronRight, Link2, Loader2, Plus } from "lucide-react";
import { toast } from "sonner";

import TaskLinkPill from "@/components/tasks/TaskLinkPill";
import { Modal } from "@/components/ui";
import { apiClient } from "@/lib/api";
import { displayUserName, formatMoney } from "@/lib/shared";
import type {
  ProcurementRequest,
  TaskBoard,
  TaskCard,
  TaskPriority,
  User,
} from "@/types/api";

type ProcurementTaskLinksProps = {
  request: ProcurementRequest;
  variant?: "section" | "dialog";
  open?: boolean;
  onClose?: () => void;
  onLinked?: () => void;
};

const taskPriorityOptions: { value: TaskPriority; label: string }[] = [
  { value: "low", label: "Низкая" },
  { value: "medium", label: "Средняя" },
  { value: "high", label: "Высокая" },
  { value: "critical", label: "Критическая" },
];

function requestTitle(request: ProcurementRequest) {
  return request.title || `Заявка на закупку #${request.id}`;
}

function getTaskOptionLabel(task: TaskCard) {
  return `#${task.id} - ${task.title}`;
}

function taskMatchesSearch(task: TaskCard, query: string) {
  const normalized = query.trim().toLowerCase();
  if (!normalized) return true;
  return [
    String(task.id),
    task.title,
    task.description || "",
    task.assignee ? displayUserName(task.assignee) : "",
  ]
    .join(" ")
    .toLowerCase()
    .includes(normalized);
}

export function ProcurementTaskLinks({
  request,
  variant = "section",
  open = false,
  onClose,
  onLinked,
}: ProcurementTaskLinksProps) {
  const [linkedTasks, setLinkedTasks] = useState<TaskCard[]>([]);
  const [loading, setLoading] = useState(true);
  const [linkModalOpen, setLinkModalOpen] = useState(false);
  const [boards, setBoards] = useState<TaskBoard[]>([]);
  const [employees, setEmployees] = useState<User[]>([]);
  const [boardId, setBoardId] = useState<number | "">("");
  const [taskId, setTaskId] = useState<number | "">("");
  const [taskSearch, setTaskSearch] = useState("");
  const [mode, setMode] = useState<"existing" | "create">("existing");
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [detailsOpen, setDetailsOpen] = useState(false);
  const [columnId, setColumnId] = useState<number | "">("");
  const [assigneeId, setAssigneeId] = useState<number | "">("");
  const [priority, setPriority] = useState<TaskPriority>("medium");
  const [dueDate, setDueDate] = useState("");
  const [labelIds, setLabelIds] = useState<number[]>([]);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const selectedBoard = boards.find((board) => board.id === boardId) || null;
  const selectedTask = (selectedBoard?.tasks || []).find((task) => task.id === taskId) || null;
  const selectedColumn = (
    (selectedBoard?.columns || []).find((column) => column.id === columnId) ||
    (selectedBoard?.columns || []).find((column) => !column.is_archived) ||
    null
  );
  const linkedTaskIds = useMemo(
    () => new Set(linkedTasks.map((task) => task.id)),
    [linkedTasks],
  );
  const dialogMode = variant === "dialog";
  const resolvedModalOpen = dialogMode ? open : linkModalOpen;

  const loadLinkedTasks = useCallback(async () => {
    setLoading(true);
    try {
      const tasks = await apiClient.getProcurementRequestLinkedTasks(request.id);
      setLinkedTasks(tasks);
    } catch (loadError) {
      console.error("Ошибка загрузки связанных задач:", loadError);
      toast.error("Не удалось загрузить связанные задачи");
    } finally {
      setLoading(false);
    }
  }, [request.id]);

  useEffect(() => {
    void loadLinkedTasks();
  }, [loadLinkedTasks]);

  const resetForm = () => {
    setBoardId("");
    setTaskId("");
    setTaskSearch("");
    setMode("existing");
    setTitle("");
    setDescription("");
    setDetailsOpen(false);
    setColumnId("");
    setAssigneeId("");
    setPriority("medium");
    setDueDate("");
    setLabelIds([]);
    setError(null);
  };

  const prepareLinkModal = useCallback(async () => {
    setSaving(true);
    setError(null);
    const baseTitle = requestTitle(request);
    const amount = request.total_cost ? `\nСумма: ${formatMoney(request.total_cost)}` : "";
    setTitle(`Задача по закупке: ${baseTitle}`);
    setDescription(`${request.description || ""}${amount}`.trim());
    try {
      const [boardsResponse, employeesResponse] = await Promise.all([
        apiClient.getTaskBoards(),
        apiClient.getEmployees({ limit: 200, is_active: true, ordering: "last_name" }),
      ]);
      const nextBoards = (boardsResponse.results || boardsResponse || []) as TaskBoard[];
      const nextEmployees = (employeesResponse.results || employeesResponse || []) as User[];
      const firstBoard = nextBoards.find((board) => (board.tasks || []).some((task) => !linkedTaskIds.has(task.id))) || nextBoards[0] || null;
      const firstTask = (firstBoard?.tasks || []).find((task) => !linkedTaskIds.has(task.id)) || null;
      const firstColumn = firstBoard?.columns?.find((column) => !column.is_archived) || null;

      setBoards(nextBoards);
      setEmployees(nextEmployees);
      setBoardId(firstBoard?.id || "");
      setTaskId(firstTask?.id || "");
      setTaskSearch("");
      setColumnId(firstColumn?.id || "");
      setMode(firstTask ? "existing" : "create");
      setDetailsOpen(false);
      setAssigneeId("");
      setPriority("medium");
      setDueDate("");
      setLabelIds([]);
    } catch (openError) {
      setError(openError instanceof Error ? openError.message : "Не удалось загрузить задачи");
    } finally {
      setSaving(false);
    }
  }, [linkedTaskIds, request]);

  const openLinkModal = async () => {
    setLinkModalOpen(true);
    await prepareLinkModal();
  };

  const closeLinkModal = () => {
    if (saving) return;
    if (dialogMode) {
      onClose?.();
    } else {
      setLinkModalOpen(false);
    }
    resetForm();
  };

  useEffect(() => {
    if (!dialogMode) return;
    if (open) {
      void prepareLinkModal();
    } else {
      resetForm();
    }
  }, [dialogMode, open, prepareLinkModal]);

  const handleBoardChange = (nextBoardId: number | "") => {
    setBoardId(nextBoardId);
    const nextBoard = boards.find((board) => board.id === nextBoardId) || null;
    const nextTask = (nextBoard?.tasks || []).find((task) => !linkedTaskIds.has(task.id)) || null;
    setTaskId(nextTask?.id || "");
    setTaskSearch("");
    setColumnId(nextBoard?.columns?.find((column) => !column.is_archived)?.id || "");
    setLabelIds([]);
    if (!nextTask) {
      setMode("create");
    }
  };

  const toggleLabel = (labelId: number) => {
    setLabelIds((current) => (
      current.includes(labelId)
        ? current.filter((id) => id !== labelId)
        : [...current, labelId]
    ));
  };

  const handleTaskSearchChange = (value: string) => {
    setTaskSearch(value);
    const nextTask = availableTasks.find((task) => taskMatchesSearch(task, value));
    setTaskId(nextTask?.id || "");
  };

  const saveLink = async () => {
    if (!selectedBoard) return;
    if (mode === "existing" && !selectedTask) return;
    if (mode === "create" && (!title.trim() || !selectedColumn)) return;

    setSaving(true);
    setError(null);
    try {
      let taskToLink = selectedTask;
      if (mode === "create") {
        taskToLink = await apiClient.createTask({
          board: selectedBoard.id,
          column: selectedColumn?.id,
          title: title.trim(),
          description: description.trim(),
          assignee_id: assigneeId || null,
          priority,
          due_date: dueDate || null,
          label_ids: labelIds,
        });
      }

      if (!taskToLink) return;
      await apiClient.linkTaskProcurementRequest(taskToLink.id, request.id);
      await loadLinkedTasks();
      toast.success("Закупка связана с задачей");
      onLinked?.();
      if (dialogMode) {
        onClose?.();
      } else {
        setLinkModalOpen(false);
      }
      resetForm();
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : "Не удалось связать закупку с задачей");
    } finally {
      setSaving(false);
    }
  };

  const availableTasks = (selectedBoard?.tasks || []).filter((task) => !linkedTaskIds.has(task.id));
  const filteredAvailableTasks = availableTasks.filter((task) => taskMatchesSearch(task, taskSearch));

  const modal = (
    <Modal
      isOpen={resolvedModalOpen}
      onClose={closeLinkModal}
      title="Связать с задачей"
      size="md"
      closeOnClickOutside
      footer={(
        <div className="flex justify-end gap-2">
          <button
            type="button"
            onClick={closeLinkModal}
            className="app-action-secondary rounded-xl px-4 py-2 text-sm font-medium"
            disabled={saving}
          >
            Отмена
          </button>
          <button
            type="button"
            onClick={() => void saveLink()}
            className="app-action-primary inline-flex items-center gap-2 rounded-xl px-4 py-2 text-sm font-medium disabled:opacity-60"
            disabled={
              saving ||
              (mode === "existing" ? !selectedTask : !title.trim() || !selectedColumn)
            }
          >
            {saving ? <Loader2 size={16} className="animate-spin" /> : <Link2 size={16} />}
            {mode === "create" ? "Создать и связать" : "Связать"}
          </button>
        </div>
      )}
    >
      <div className="space-y-4">
        <div className="app-surface-muted rounded-xl border border-[var(--border-subtle)] p-3">
          <p className="app-card-caption">Закупка</p>
          <p className="app-text-wrap mt-1 line-clamp-3 text-sm text-[var(--foreground)]">
            {requestTitle(request)}
          </p>
          <p className="app-text-muted mt-1 text-xs">
            {[request.department_name, request.status_display, request.total_cost ? formatMoney(request.total_cost) : ""].filter(Boolean).join(" · ")}
          </p>
        </div>

        <label className="block">
          <span className="app-text-muted mb-1 block text-xs font-medium">Доска</span>
          <select
            value={boardId}
            onChange={(event) => handleBoardChange(Number(event.target.value) || "")}
            className="app-select w-full rounded-xl px-3 py-2 text-sm"
            disabled={saving}
          >
            <option value="">Выберите доску</option>
            {boards.map((board) => (
              <option key={board.id} value={board.id}>
                {board.name}
              </option>
            ))}
          </select>
        </label>

        <div className="grid grid-cols-2 gap-2">
          <button
            type="button"
            onClick={() => setMode("existing")}
            className={`rounded-xl border px-3 py-2 text-sm font-medium transition ${
              mode === "existing"
                ? "app-selected border-[var(--accent-primary)]"
                : "border-[var(--border-subtle)] text-[var(--muted-foreground)] hover:border-[var(--border-strong)]"
            }`}
            disabled={saving || !selectedBoard || availableTasks.length === 0}
          >
            Выбрать задачу
          </button>
          <button
            type="button"
            onClick={() => setMode("create")}
            className={`rounded-xl border px-3 py-2 text-sm font-medium transition ${
              mode === "create"
                ? "app-selected border-[var(--accent-primary)]"
                : "border-[var(--border-subtle)] text-[var(--muted-foreground)] hover:border-[var(--border-strong)]"
            }`}
            disabled={saving || !selectedBoard}
          >
            Создать задачу
          </button>
        </div>

        {mode === "existing" ? (
          <div className="space-y-2">
            <label className="block">
              <span className="app-text-muted mb-1 block text-xs font-medium">Поиск задачи</span>
              <input
                value={taskSearch}
                onChange={(event) => handleTaskSearchChange(event.target.value)}
                className="app-input w-full rounded-xl px-3 py-2 text-sm"
                disabled={saving || !selectedBoard}
                placeholder="ID, название, описание или исполнитель"
              />
            </label>
            <label className="block">
              <span className="app-text-muted mb-1 block text-xs font-medium">Задача</span>
              <select
                value={taskId}
                onChange={(event) => setTaskId(Number(event.target.value) || "")}
                className="app-select w-full rounded-xl px-3 py-2 text-sm"
                disabled={saving || !selectedBoard || filteredAvailableTasks.length === 0}
              >
                <option value="">
                  {filteredAvailableTasks.length === 0 ? "Задачи не найдены" : "Выберите задачу"}
                </option>
                {filteredAvailableTasks.map((task) => (
                  <option key={task.id} value={task.id}>
                    {getTaskOptionLabel(task)}
                  </option>
                ))}
              </select>
            </label>
          </div>
        ) : (
          <div className="space-y-3">
            <label className="block">
              <span className="app-text-muted mb-1 block text-xs font-medium">Название задачи</span>
              <input
                value={title}
                onChange={(event) => setTitle(event.target.value)}
                className="app-input w-full rounded-xl px-3 py-2 text-sm"
                disabled={saving}
                placeholder="Название новой задачи"
              />
            </label>
            <label className="block">
              <span className="app-text-muted mb-1 block text-xs font-medium">Описание</span>
              <textarea
                value={description}
                onChange={(event) => setDescription(event.target.value)}
                className="app-input w-full rounded-xl px-3 py-2 text-sm"
                disabled={saving}
                rows={3}
              />
            </label>

            <div className="rounded-xl border border-[var(--border-subtle)]">
              <button
                type="button"
                onClick={() => setDetailsOpen((current) => !current)}
                className="flex w-full items-center justify-between gap-3 px-3 py-2 text-left"
                disabled={saving}
                aria-expanded={detailsOpen}
              >
                <span>
                  <span className="block text-sm font-medium text-[var(--foreground)]">
                    Дополнительная информация
                  </span>
                  <span className="app-text-muted mt-0.5 block text-xs">
                    Исполнитель, срочность, срок, колонка и метки
                  </span>
                </span>
                <ChevronRight
                  size={16}
                  className={`app-text-muted shrink-0 transition-transform ${detailsOpen ? "rotate-90" : ""}`}
                />
              </button>

              {detailsOpen ? (
                <div className="space-y-3 border-t border-[var(--border-subtle)] px-3 py-3">
                  <label className="block">
                    <span className="app-text-muted mb-1 block text-xs font-medium">Колонка</span>
                    <select
                      value={columnId}
                      onChange={(event) => setColumnId(Number(event.target.value) || "")}
                      className="app-select w-full rounded-xl px-3 py-2 text-sm"
                      disabled={saving || !selectedBoard}
                    >
                      <option value="">Выберите колонку</option>
                      {(selectedBoard?.columns || [])
                        .filter((column) => !column.is_archived)
                        .map((column) => (
                          <option key={column.id} value={column.id}>
                            {column.name}
                          </option>
                        ))}
                    </select>
                  </label>

                  <label className="block">
                    <span className="app-text-muted mb-1 block text-xs font-medium">Исполнитель</span>
                    <select
                      value={assigneeId}
                      onChange={(event) => setAssigneeId(Number(event.target.value) || "")}
                      className="app-select w-full rounded-xl px-3 py-2 text-sm"
                      disabled={saving}
                    >
                      <option value="">Не назначен</option>
                      {employees.map((employee) => (
                        <option key={employee.id} value={employee.id}>
                          {displayUserName(employee)}
                        </option>
                      ))}
                    </select>
                  </label>

                  <div className="grid gap-3 sm:grid-cols-2">
                    <label className="block">
                      <span className="app-text-muted mb-1 block text-xs font-medium">Срочность</span>
                      <select
                        value={priority}
                        onChange={(event) => setPriority(event.target.value as TaskPriority)}
                        className="app-select w-full rounded-xl px-3 py-2 text-sm"
                        disabled={saving}
                      >
                        {taskPriorityOptions.map((option) => (
                          <option key={option.value} value={option.value}>
                            {option.label}
                          </option>
                        ))}
                      </select>
                    </label>
                    <label className="block">
                      <span className="app-text-muted mb-1 block text-xs font-medium">Срок</span>
                      <input
                        type="date"
                        value={dueDate}
                        onChange={(event) => setDueDate(event.target.value)}
                        className="app-input w-full rounded-xl px-3 py-2 text-sm"
                        disabled={saving}
                      />
                    </label>
                  </div>

                  <div>
                    <span className="app-text-muted mb-2 block text-xs font-medium">Метки</span>
                    {(selectedBoard?.labels || []).length > 0 ? (
                      <div className="flex flex-wrap gap-2">
                        {(selectedBoard?.labels || []).map((label) => {
                          const selected = labelIds.includes(label.id);
                          return (
                            <button
                              key={label.id}
                              type="button"
                              onClick={() => toggleLabel(label.id)}
                              className={`inline-flex max-w-full items-center rounded-full border px-2.5 py-1 text-xs font-medium transition ${
                                selected ? "border-transparent text-white" : "border-[var(--border-subtle)] text-[var(--muted-foreground)]"
                              }`}
                              style={selected ? { backgroundColor: label.color || "#38bdf8" } : undefined}
                              disabled={saving}
                            >
                              <span className="truncate">{label.name}</span>
                            </button>
                          );
                        })}
                      </div>
                    ) : (
                      <p className="app-text-muted text-xs">На этой доске меток нет</p>
                    )}
                  </div>
                </div>
              ) : null}
            </div>
          </div>
        )}

        {error ? (
          <div className="app-feedback-danger rounded-xl px-3 py-2 text-sm">
            {error}
          </div>
        ) : null}
      </div>
    </Modal>
  );

  if (dialogMode) {
    return modal;
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between gap-3">
        <div className="flex min-w-0 items-center gap-2">
          <Link2 size={18} className="app-text-muted shrink-0" />
          <h3 className="text-sm font-medium text-[var(--foreground)]">
            Связанные задачи ({linkedTasks.length})
          </h3>
        </div>
        <button
          type="button"
          onClick={() => void openLinkModal()}
          className="app-action-primary inline-flex shrink-0 items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-medium"
        >
          <Plus size={14} />
          Связать
        </button>
      </div>

      {loading ? (
        <div className="flex items-center justify-center py-6">
          <Loader2 size={18} className="animate-spin text-sky-500" />
        </div>
      ) : linkedTasks.length > 0 ? (
        <div className="flex flex-wrap gap-2">
          {linkedTasks.map((task) => (
            <TaskLinkPill
              key={task.id}
              task={{
                id: task.id,
                title: task.title,
                board_id: task.board,
                board_name: task.board_name || "",
                column_color: task.column_color,
                priority: task.priority,
                priority_display: task.priority_display,
              }}
              maxTitleClassName="max-w-56"
            />
          ))}
        </div>
      ) : (
        <div className="app-surface-muted rounded-xl border border-dashed border-[var(--border-subtle)] px-3 py-4 text-center">
          <p className="app-text-muted text-sm">Связанных задач нет</p>
        </div>
      )}

      {modal}
    </div>
  );
}
