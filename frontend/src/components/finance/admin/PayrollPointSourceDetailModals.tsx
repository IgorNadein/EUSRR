"use client";

import { BriefcaseBusiness, CalendarDays, FileText, UserRoundCog } from "lucide-react";

import { Modal } from "@/components/ui";
import type { PayrollPointBreakdownDay } from "@/lib/api/finance";

function formatDate(value: string | null): string {
  if (!value) return "—";
  return new Date(`${value}T00:00:00`).toLocaleDateString("ru-RU");
}

function formatDateTime(value: string): string {
  return new Date(value).toLocaleString("ru-RU", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function formatPoints(value: string | null): string {
  if (value == null || value === "") return "—";
  const number = Number(value);
  return Number.isFinite(number)
    ? number.toLocaleString("ru-RU", { maximumFractionDigits: 4 })
    : value;
}

function requestStatusClass(status: string): string {
  if (status === "approved") return "app-feedback-success";
  if (status === "rejected" || status === "cancelled") return "app-feedback-danger";
  if (status === "pending") return "app-feedback-warning";
  return "app-surface-muted";
}

export function PayrollPersonnelDayModal({
  day,
  employeeName,
  onClose,
}: {
  day: PayrollPointBreakdownDay;
  employeeName: string;
  onClose: () => void;
}) {
  const detail = day.personnel_detail;

  return (
    <Modal
      isOpen
      onClose={onClose}
      title={`Кадровые события · ${employeeName}`}
      size="lg"
      stackLevel={1}
      closeOnClickOutside
    >
      <div className="space-y-4">
        <section className="app-surface-muted rounded-xl p-4">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <p className="app-card-caption">Состояние на {formatDate(day.date)}</p>
              <p className="mt-2 text-base font-semibold text-[var(--foreground)]">
                {detail.state.label}
              </p>
            </div>
            <span className={`app-status-pill ${detail.state.expects_attendance ? "app-feedback-success" : "app-feedback-warning"}`}>
              {detail.state.expects_attendance ? "Явка ожидается" : "Явка не ожидается"}
            </span>
          </div>
        </section>

        <section>
          <div className="mb-2 flex items-center gap-2">
            <UserRoundCog className="app-text-muted" size={16} />
            <h4 className="text-sm font-semibold text-[var(--foreground)]">
              Кадровые события ({detail.actions.length})
            </h4>
          </div>
          {detail.actions.length ? (
            <div className="space-y-2">
              {detail.actions.map((action) => (
                <article key={action.id} className="app-surface rounded-xl border border-[var(--border-subtle)] p-3.5">
                  <div className="flex flex-wrap items-start justify-between gap-2">
                    <p className="text-sm font-semibold text-[var(--foreground)]">{action.label}</p>
                    <span className="app-status-pill app-surface-muted">#{action.id}</span>
                  </div>
                  <p className="app-text-muted mt-2 text-xs">
                    {formatDate(action.date)}{action.date_to ? ` — ${formatDate(action.date_to)}` : ""}
                  </p>
                  {action.comment ? <p className="mt-2 whitespace-pre-wrap text-sm text-[var(--foreground)]">{action.comment}</p> : null}
                  {action.source_request_id ? (
                    <p className="app-accent-text mt-2 text-xs">Создано по заявлению #{action.source_request_id}</p>
                  ) : null}
                </article>
              ))}
            </div>
          ) : (
            <div className="app-surface-muted rounded-xl px-4 py-6 text-center text-sm text-[var(--muted-foreground)]">
              Отдельных кадровых событий для этой даты нет.
            </div>
          )}
        </section>

        <section>
          <div className="mb-2 flex items-center gap-2">
            <FileText className="app-text-muted" size={16} />
            <h4 className="text-sm font-semibold text-[var(--foreground)]">
              Заявления ({detail.requests.length})
            </h4>
          </div>
          {detail.requests.length ? (
            <div className="space-y-2">
              {detail.requests.map((request) => (
                <article key={request.id} className="app-surface rounded-xl border border-[var(--border-subtle)] p-3.5">
                  <div className="flex flex-wrap items-start justify-between gap-2">
                    <div className="min-w-0">
                      <p className="text-sm font-semibold text-[var(--foreground)]">{request.title || request.type_label}</p>
                      <p className="app-text-muted mt-1 text-xs">{request.type_label} · заявление #{request.id}</p>
                    </div>
                    <span className={`app-status-pill ${requestStatusClass(request.status)}`}>{request.status_label}</span>
                  </div>
                  <p className="app-text-muted mt-2 text-xs">
                    {formatDate(request.date_from)}{request.date_to ? ` — ${formatDate(request.date_to)}` : ""}
                  </p>
                  {request.comment ? <p className="mt-2 whitespace-pre-wrap text-sm text-[var(--foreground)]">{request.comment}</p> : null}
                </article>
              ))}
            </div>
          ) : (
            <div className="app-surface-muted rounded-xl px-4 py-6 text-center text-sm text-[var(--muted-foreground)]">
              Заявлений, относящихся к этой дате, нет.
            </div>
          )}
        </section>
      </div>
    </Modal>
  );
}

type WorkEntryDetail = {
  id: number;
  target_points?: string | null;
  actual_points: string | null;
  note: string;
  created_at: string;
  updated_at: string;
};

export function PayrollWorkEntryDayModal({
  entry,
  date,
  employeeName,
  undated = false,
  onClose,
}: {
  entry: WorkEntryDetail;
  date: string | null;
  employeeName: string;
  undated?: boolean;
  onClose: () => void;
}) {
  return (
    <Modal
      isOpen
      onClose={onClose}
      title={`Запись выработки · ${employeeName}`}
      size="md"
      stackLevel={1}
      closeOnClickOutside
    >
      <div className="space-y-4">
        <section className="app-selected flex items-start gap-3 rounded-xl p-4">
          {undated ? <BriefcaseBusiness className="app-accent-text mt-0.5 shrink-0" size={19} /> : <CalendarDays className="app-accent-text mt-0.5 shrink-0" size={19} />}
          <div className="min-w-0">
            <p className="app-card-caption">{undated ? "Без привязки к дате" : formatDate(date)}</p>
            <p className="mt-2 text-xl font-semibold text-[var(--foreground)]">
              {formatPoints(entry.actual_points)} балл.
            </p>
            {entry.target_points != null ? (
              <p className="app-text-muted mt-1 text-xs">Дневная норма: {formatPoints(entry.target_points)}</p>
            ) : null}
          </div>
        </section>

        <section className="app-surface-muted rounded-xl p-4">
          <p className="app-card-caption">Комментарий</p>
          <p className={`mt-2 whitespace-pre-wrap text-sm ${entry.note ? "text-[var(--foreground)]" : "text-[var(--muted-foreground)]"}`}>
            {entry.note || "Комментарий не указан."}
          </p>
        </section>

        <div className="grid gap-2 text-xs text-[var(--muted-foreground)] sm:grid-cols-2">
          <p>Создано: {formatDateTime(entry.created_at)}</p>
          <p>Изменено: {formatDateTime(entry.updated_at)}</p>
        </div>
      </div>
    </Modal>
  );
}
