"use client";

import { useMemo, useState } from "react";
import { Pencil, Plus, Trash2 } from "lucide-react";
import {
  getEmployeeActionTone,
  truncateText,
} from "@/lib/users/userDetailUtils";
import type { EmployeeAction, EmployeePersonnelState } from "@/types/api";

type EmployeeActionsTimelineProps = {
  actionLoading: string | null;
  canManageActions: boolean;
  canViewActions: boolean;
  latestActionId: number | null;
  onAddAction?: () => void;
  onDeleteAction?: (actionId: number) => void;
  onEditAction?: (action: EmployeeAction) => void;
  personnelState?: EmployeePersonnelState | null;
  sortedActions: EmployeeAction[];
  initialVisibleCount?: number;
  showCountLabel?: boolean;
  truncateCommentLength?: number;
  expandedCommentLength?: number;
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

function formatStateDate(value?: string | null) {
  if (!value) return "";
  return formatActionDate(value);
}

export default function EmployeeActionsTimeline({
  actionLoading,
  canManageActions,
  canViewActions,
  latestActionId,
  onAddAction,
  onDeleteAction,
  onEditAction,
  personnelState,
  sortedActions,
  initialVisibleCount,
  showCountLabel = true,
  truncateCommentLength,
  expandedCommentLength = truncateCommentLength,
}: EmployeeActionsTimelineProps) {
  const [showAll, setShowAll] = useState(false);
  const currentActionId = personnelState ? personnelState.action_id : latestActionId;
  const showCurrentStateCard = Boolean(
    personnelState
    && personnelState.status
    && personnelState.status !== "normal"
  );
  const canCollapse = Boolean(
    initialVisibleCount && sortedActions.length > initialVisibleCount,
  );
  const visibleActions = useMemo(
    () =>
      canCollapse && !showAll
        ? sortedActions.slice(0, initialVisibleCount)
        : sortedActions,
    [canCollapse, initialVisibleCount, showAll, sortedActions],
  );

  if (!canViewActions || (sortedActions.length === 0 && !showCurrentStateCard)) {
    return null;
  }

  return (
    <section className="app-surface rounded-2xl p-5">
      <div className="mb-4 flex items-start justify-between gap-4">
        <h2 className="app-card-caption">Кадровые события</h2>
        <div className="flex items-center gap-2">
          {showCountLabel ? (
            <span className="app-text-muted text-sm">
              {sortedActions.length}{" "}
              {sortedActions.length === 1
                ? "событие"
                : sortedActions.length < 5
                  ? "события"
                  : "событий"}
            </span>
          ) : null}
          {canCollapse ? (
            <button
              type="button"
              onClick={() => setShowAll((current) => !current)}
              className="app-action-secondary rounded-xl px-3 py-2 text-sm font-medium"
            >
              {showAll ? "Свернуть" : `Показать все (${sortedActions.length})`}
            </button>
          ) : null}
          {canManageActions && onAddAction ? (
            <button
              onClick={onAddAction}
              className="app-action-secondary inline-flex items-center gap-2 rounded-xl px-3 py-2 text-sm font-medium"
            >
              <Plus size={14} />
              Добавить
            </button>
          ) : null}
        </div>
      </div>

      {!showAll && canCollapse ? (
        <p className="app-text-muted mb-3 text-sm">
          Последние {visibleActions.length} из {sortedActions.length}
        </p>
      ) : null}

      {showCurrentStateCard && personnelState ? (
        <div className="mb-4 rounded-xl border border-[var(--accent-primary)]/30 bg-[var(--accent-primary)]/10 px-4 py-3">
          {(() => {
            const tone = getEmployeeActionTone(personnelState.status);
            const dateFrom = formatStateDate(personnelState.date_from);
            const dateTo = formatStateDate(personnelState.date_to);
            return (
              <div className="flex flex-col gap-2 md:flex-row md:items-start md:justify-between">
                <div className="min-w-0">
                  <p className="app-card-caption mb-2">Текущее состояние</p>
                  <div className="flex flex-wrap items-center gap-2">
                    <span className={`app-status-pill ${tone.badgeClass}`}>
                      {personnelState.label || personnelState.status}
                    </span>
                    <span className="app-text-muted text-xs font-medium">
                      активно сейчас
                    </span>
                  </div>
                </div>
                {dateFrom ? (
                  <time className="app-text-muted shrink-0 pt-1 text-sm">
                    {dateFrom}
                    {dateTo ? ` - ${dateTo}` : ""}
                  </time>
                ) : null}
              </div>
            );
          })()}
        </div>
      ) : null}

      <div className="space-y-3">
        {visibleActions.map((action) => {
          const isCurrent = currentActionId === action.id;
          const deleteKey = `delete-${action.id}`;
          const tone = getEmployeeActionTone(action.action);
          const commentText = truncateCommentLength
            ? truncateText(action.comment, showAll ? expandedCommentLength : truncateCommentLength)
            : action.comment;

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
              <div className="app-surface-muted rounded-xl px-4 py-3">
                <div className="flex flex-col gap-2 md:flex-row md:items-start md:justify-between">
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className={`app-status-pill ${tone.badgeClass}`}>
                        {action.action_display || action.action}
                      </span>
                      {isCurrent ? (
                        <span className="app-text-muted text-xs font-medium">
                          текущий
                        </span>
                      ) : null}
                    </div>
                    {commentText ? (
                      <p className="app-text-wrap app-text-muted mt-2 text-sm leading-6">
                        {commentText}
                      </p>
                    ) : null}
                  </div>
                  <div className="flex shrink-0 items-start gap-2">
                    <time className="app-text-muted pt-1 text-sm">
                      {formatActionDate(action.date)}
                      {action.date_to ? ` - ${formatActionDate(action.date_to)}` : ""}
                    </time>
                    {canManageActions && onEditAction && onDeleteAction ? (
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
