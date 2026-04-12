"use client";

import { History, Pencil, Trash2 } from "lucide-react";
import {
  getEmployeeActionTone,
} from "@/lib/users/userDetailUtils";
import type { EmployeeAction } from "@/types/api";

type EmployeeActionsTimelineProps = {
  actionLoading: string | null;
  canManageActions: boolean;
  canViewActions: boolean;
  latestActionId: number | null;
  onAddAction: () => void;
  onDeleteAction: (actionId: number) => void;
  onEditAction: (action: EmployeeAction) => void;
  sortedActions: EmployeeAction[];
};

function formatActionDate(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleDateString("ru-RU", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
  });
}

export default function EmployeeActionsTimeline({
  actionLoading,
  canManageActions,
  canViewActions,
  latestActionId,
  onAddAction,
  onDeleteAction,
  onEditAction,
  sortedActions,
}: EmployeeActionsTimelineProps) {
  if (!canViewActions || sortedActions.length === 0) {
    return null;
  }

  return (
    <section className="app-surface rounded-[24px] p-5">
      <div className="mb-4 flex items-start justify-between gap-4">
        <div className="flex items-center gap-2">
          <History size={18} className="app-text-muted" />
          <h2 className="app-card-caption">Кадровые события</h2>
        </div>
        <div className="flex items-center gap-2">
          <span className="app-text-muted text-sm">
            {sortedActions.length}{" "}
            {sortedActions.length === 1
              ? "событие"
              : sortedActions.length < 5
                ? "события"
                : "событий"}
          </span>
          {canManageActions ? (
            <button
              onClick={onAddAction}
              className="app-action-secondary rounded-xl px-3 py-2 text-sm font-medium"
            >
              + Добавить
            </button>
          ) : null}
        </div>
      </div>

      <div className="space-y-3">
        {sortedActions.map((action) => {
          const isCurrent = latestActionId === action.id;
          const deleteKey = `delete-${action.id}`;
          const tone = getEmployeeActionTone(action.action);

          return (
            <div key={action.id} className="relative pl-5">
              <span
                className="absolute bottom-0 left-1.5 top-0 w-px"
                style={{ backgroundColor: tone.lineColor }}
              />
              {isCurrent ? (
                <span
                  className="absolute left-0 top-2 h-3.5 w-3.5 rounded-full border-4 border-[var(--surface-primary)]"
                  style={{ backgroundColor: tone.lineColor }}
                />
              ) : null}
              <div className="app-surface-muted rounded-2xl px-4 py-3">
                <div className="flex flex-col gap-2 md:flex-row md:items-start md:justify-between">
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-2">
                      <span
                        className={`app-status-pill ${tone.badgeClass}`}
                      >
                        {action.action_display || action.action}
                      </span>
                      {isCurrent ? (
                        <span className="app-text-muted text-xs font-medium">
                          текущий
                        </span>
                      ) : null}
                    </div>
                    {action.comment ? (
                      <p className="app-text-muted mt-2 text-sm leading-6">
                        {action.comment}
                      </p>
                    ) : null}
                  </div>
                  <div className="flex shrink-0 items-start gap-2">
                    <time className="app-text-muted pt-1 text-sm">
                      {formatActionDate(action.date)}
                    </time>
                    {canManageActions ? (
                      <div className="flex gap-1">
                        <button
                          onClick={() => onEditAction(action)}
                          className="app-action-secondary inline-flex h-9 w-9 items-center justify-center rounded-xl"
                          title="Редактировать"
                          disabled={actionLoading === deleteKey}
                        >
                          <Pencil size={14} />
                        </button>
                        <button
                          onClick={() => onDeleteAction(action.id)}
                          className="app-action-secondary inline-flex h-9 w-9 items-center justify-center rounded-xl text-red-400 hover:border-red-400/40 hover:bg-red-500/10 hover:text-red-300"
                          title="Удалить"
                          disabled={actionLoading === deleteKey}
                        >
                          {actionLoading === deleteKey ? (
                            <div className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-red-400 border-t-transparent" />
                          ) : (
                            <Trash2 size={14} />
                          )}
                        </button>
                      </div>
                    ) : null}
                  </div>
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </section>
  );
}
