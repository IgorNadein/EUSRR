"use client";

import { useCallback, useEffect, useState } from "react";
import { ChevronRight, History, Loader2 } from "lucide-react";

import { apiClient } from "@/lib/api";
import { formatDateTime } from "@/lib/shared";
import type { ProcurementRequest, ProcurementRequestActivity, User } from "@/types/api";

interface ProcurementRequestHistoryProps {
  request: ProcurementRequest;
  displayUserName: (
    person?: User | number | null,
    fallbackName?: string | null,
    fallbackEmail?: string | null,
  ) => string;
}

const fieldLabels: Record<string, string> = {
  title: "название",
  description: "описание",
  department_id: "отдел-заказчик",
  processing_department_id: "отдел-исполнитель",
  urgency: "срочность",
  actual_cost: "фактическую стоимость",
  execution_status: "статус исполнения",
  ordered_quantity: "заказанное количество",
  received_quantity: "полученное количество",
  expected_delivery_dates: "ожидаемые даты",
  actual_unit_price: "фактическую цену",
  executor_comment: "комментарий исполнителя",
  links: "ссылки",
};

function textMetadata(metadata: Record<string, unknown>, key: string): string {
  return typeof metadata[key] === "string" ? String(metadata[key]) : "";
}

function getActivityDetail(activity: ProcurementRequestActivity): string {
  const metadata = activity.metadata || {};
  if (activity.action === "updated" || activity.action === "item_updated") {
    const fields = Array.isArray(metadata.fields) ? metadata.fields : [];
    const labels = fields.map((field) => fieldLabels[String(field)] || String(field));
    const itemName = textMetadata(metadata, "item_name");
    const prefix = itemName ? `${itemName}. ` : "";
    return labels.length > 0 ? `${prefix}Изменено: ${labels.join(", ")}` : itemName;
  }
  if (activity.action === "executor_reassigned") {
    const previous = textMetadata(metadata, "previous_executor");
    const next = textMetadata(metadata, "new_executor");
    return previous && next ? `${previous} -> ${next}` : next;
  }
  if (activity.action === "stage_approved" || activity.action === "stage_rejected") {
    const step = textMetadata(metadata, "step_name");
    const comment = textMetadata(metadata, "comment");
    return [step, comment].filter(Boolean).join(". ");
  }
  if (activity.action === "attachment_added" || activity.action === "attachment_removed") {
    const fileName = textMetadata(metadata, "file_name");
    const itemName = textMetadata(metadata, "item_name");
    return [itemName, fileName].filter(Boolean).join(": ");
  }
  if (activity.action === "comment_added" || activity.action === "comment_removed") {
    const itemName = textMetadata(metadata, "item_name");
    const comment = textMetadata(metadata, "comment_text");
    return [itemName, comment].filter(Boolean).join(": ");
  }
  if (activity.action === "cancelled") {
    return textMetadata(metadata, "reason");
  }
  return "";
}

function ActivityCard({
  activity,
  displayUserName,
}: {
  activity: ProcurementRequestActivity;
  displayUserName: ProcurementRequestHistoryProps["displayUserName"];
}) {
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
            <span className="app-text-muted text-xs">{formatDateTime(activity.created_at)}</span>
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

export function ProcurementRequestHistory({ request, displayUserName }: ProcurementRequestHistoryProps) {
  const [open, setOpen] = useState(false);
  const [activities, setActivities] = useState<ProcurementRequestActivity[]>([]);
  const [loading, setLoading] = useState(false);
  const [loaded, setLoaded] = useState(false);
  const [error, setError] = useState("");

  const loadActivity = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const result = await apiClient.getProcurementRequestActivity(request.id);
      setActivities(Array.isArray(result) ? result : []);
      setLoaded(true);
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : "Не удалось загрузить историю");
    } finally {
      setLoading(false);
    }
  }, [request.id]);

  useEffect(() => {
    if (open) void loadActivity();
  }, [open, request.updated_at, loadActivity]);

  const toggle = () => {
    setOpen((current) => !current);
  };
  const count = loaded ? activities.length : request.activity_count || 0;

  return (
    <div className="rounded-xl border border-[var(--border-subtle)]">
      <button
        type="button"
        onClick={toggle}
        className="flex w-full items-center justify-between gap-3 px-3 py-2.5 text-left"
        aria-expanded={open}
      >
        <span className="flex min-w-0 items-center gap-2">
          <History size={15} className="app-text-muted shrink-0" />
          <span className="text-sm font-medium text-[var(--foreground)]">История</span>
          {count > 0 ? (
            <span className="app-badge rounded-full px-2 py-0.5 text-[11px]">{count}</span>
          ) : null}
        </span>
        <ChevronRight
          size={16}
          className={`app-text-muted shrink-0 transition-transform ${open ? "rotate-90" : ""}`}
        />
      </button>

      {open ? (
        <div className="space-y-2 border-t border-[var(--border-subtle)] p-3">
          {loading && !loaded ? (
            <div className="app-surface-muted rounded-xl border border-[var(--border-subtle)] p-4 text-center">
              <Loader2 size={18} className="mx-auto animate-spin text-sky-500" />
            </div>
          ) : error ? (
            <div className="app-feedback-danger rounded-xl px-3 py-3 text-xs">{error}</div>
          ) : activities.length > 0 ? (
            activities.map((activity) => (
              <ActivityCard key={activity.id} activity={activity} displayUserName={displayUserName} />
            ))
          ) : (
            <div className="app-surface-muted rounded-xl border border-dashed border-[var(--border-subtle)] px-3 py-4 text-center">
              <p className="app-text-muted text-xs">Истории действий пока нет</p>
            </div>
          )}
        </div>
      ) : null}
    </div>
  );
}
