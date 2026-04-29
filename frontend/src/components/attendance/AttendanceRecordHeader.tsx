"use client";

import type { ReactNode } from "react";

export type AttendanceRecordHeaderData = {
  employeeName: string;
  date: string;
  statusLabel: string;
  displayText: string;
  detailLines?: string[];
  issues?: string[];
  isManuallyEdited?: boolean;
  commentsCount?: number;
};

type AttendanceRecordHeaderProps = {
  actions?: ReactNode;
  record: AttendanceRecordHeaderData;
};

function visibleDetailLines(lines?: string[]) {
  return (lines || []).filter(
    (line) => !String(line).trim().toLowerCase().startsWith("комментари"),
  );
}

export function AttendanceRecordHeader({
  actions,
  record,
}: AttendanceRecordHeaderProps) {
  const details = visibleDetailLines(record.detailLines);

  return (
    <section className="app-surface-muted rounded-xl p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="app-card-caption">Запись посещения</p>
          <h3 className="app-text-wrap mt-3 text-base font-semibold text-[var(--foreground)]">
            {record.employeeName}
          </h3>
          <p className="app-text-muted mt-1 text-sm">
            {record.date} · {record.displayText || "Нет записи"}
          </p>
        </div>
        <span className="app-status-pill bg-[var(--surface-primary)] text-[var(--foreground)]">
          {record.statusLabel}
        </span>
      </div>

      {details.length ? (
        <div className="mt-3 grid gap-x-8 gap-y-1 text-xs text-[var(--muted-foreground)] sm:grid-cols-2">
          {details.slice(0, 8).map((line) => (
            <p key={line}>{line}</p>
          ))}
        </div>
      ) : null}

      <div className="mt-3 flex flex-wrap items-center gap-2">
        {record.commentsCount !== undefined ? (
          <span className="app-status-pill bg-[var(--surface-primary)] text-[var(--muted-foreground)]">
            Комментариев: {record.commentsCount}
          </span>
        ) : null}
        {record.issues?.map((issue) => (
          <span key={issue} className="app-status-pill bg-amber-500/15 text-amber-300">
            {issue}
          </span>
        ))}
        {record.isManuallyEdited ? (
          <span className="app-status-pill border border-violet-400/30 bg-violet-500/10 text-violet-200">
            Ручная корректировка EUSRR
          </span>
        ) : null}
      </div>

      {actions ? (
        <div className="mt-4 flex flex-wrap gap-2">
          {actions}
        </div>
      ) : null}
    </section>
  );
}
