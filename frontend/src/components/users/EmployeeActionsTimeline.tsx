"use client";

import { History, Pencil, Trash2 } from "lucide-react";
import { getEmployeeActionBadgeClass, getEmployeeActionBorderColor } from "@/lib/users/userDetailUtils";
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
    <section className="rounded-2xl bg-white p-4 shadow-sm ring-1 ring-gray-100">
      <div className="mb-3 flex items-center justify-between">
        <h2 className="flex items-center gap-2 text-sm font-semibold text-gray-900">
          <History size={16} />
          История кадровых событий
        </h2>
        <div className="flex items-center gap-2">
          <span className="text-xs text-gray-500">
            {sortedActions.length} {sortedActions.length === 1 ? "событие" : sortedActions.length < 5 ? "события" : "событий"}
          </span>
          {canManageActions && (
            <button
              onClick={onAddAction}
              className="rounded-lg bg-sky-100 px-2 py-1 text-xs font-medium text-sky-700 hover:bg-sky-200 transition"
            >
              + Добавить
            </button>
          )}
        </div>
      </div>
      <div className="space-y-3">
        {sortedActions.map((action) => {
          const isCurrent = latestActionId === action.id;
          const deleteKey = `delete-${action.id}`;

          return (
            <div
              key={action.id}
              className="flex gap-3 border-l-2 py-1 pl-3"
              style={{ borderColor: getEmployeeActionBorderColor(action.action) }}
            >
              <div className="min-w-0 flex-1">
                <div className="flex items-start justify-between gap-2">
                  <div className="flex-1">
                    <div className="flex items-center gap-2">
                      <span className={`inline-block rounded-full px-2 py-0.5 text-xs font-medium ${getEmployeeActionBadgeClass(action.action)}`}>
                        {action.action_display || action.action}
                      </span>
                      {isCurrent && (
                        <span className="text-xs text-gray-500">текущий</span>
                      )}
                    </div>
                    {action.comment && (
                      <p className="mt-1 text-sm text-gray-600">{action.comment}</p>
                    )}
                  </div>
                  <div className="flex items-center gap-2">
                    <time className="flex-shrink-0 text-xs text-gray-500">
                      {new Date(action.date).toLocaleDateString("ru-RU", {
                        day: "numeric",
                        month: "short",
                        year: "numeric",
                      })}
                    </time>
                    {canManageActions && (
                      <div className="flex gap-1">
                        <button
                          onClick={() => onEditAction(action)}
                          className="rounded p-1 text-gray-400 transition hover:bg-gray-100 hover:text-sky-600"
                          title="Редактировать"
                          disabled={actionLoading === deleteKey}
                        >
                          <Pencil size={14} />
                        </button>
                        <button
                          onClick={() => onDeleteAction(action.id)}
                          className="rounded p-1 text-gray-400 transition hover:bg-red-50 hover:text-red-600"
                          title="Удалить"
                          disabled={actionLoading === deleteKey}
                        >
                          {actionLoading === deleteKey ? (
                            <div className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-red-600 border-t-transparent" />
                          ) : (
                            <Trash2 size={14} />
                          )}
                        </button>
                      </div>
                    )}
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