"use client";

import { Check, CircleDot, X } from "lucide-react";

import { formatDate, formatMoney } from "@/lib/shared";
import type { ProcurementRequest, User } from "@/types/api";

interface ProcurementRequestDetailContentProps {
  request: ProcurementRequest;
  displayUserName: (
    person?: User | number | null,
    fallbackName?: string | null,
    fallbackEmail?: string | null,
  ) => string;
  footer?: React.ReactNode;
}

const approvalIconByStatus = (status?: string) => {
  const normalized = String(status || "").toLowerCase();
  if (normalized === "approved") {
    return <Check size={13} className="text-emerald-500" />;
  }
  if (normalized === "rejected") {
    return <X size={13} className="text-rose-500" />;
  }
  return <CircleDot size={13} className="text-amber-500" />;
};

export function ProcurementRequestDetailContent({
  request,
  displayUserName,
  footer,
}: ProcurementRequestDetailContentProps) {
  return (
    <div className="space-y-3">
      <div className="app-surface rounded-xl p-4">
        <p className="text-sm font-semibold text-[var(--foreground)]">Описание</p>
        <p className="app-text-wrap mt-2 whitespace-pre-line text-sm leading-6 text-[var(--foreground)]">
          {request.description || "—"}
        </p>
        <div className="mt-3 grid gap-2 text-xs sm:grid-cols-3">
          <div className="app-surface-muted rounded-lg px-3 py-2">
            <p className="app-text-muted text-[11px] uppercase tracking-wide">Отправлена</p>
            <p className="mt-1 font-medium text-[var(--foreground)]">{formatDate(request.submitted_at) || "—"}</p>
          </div>
          <div className="app-surface-muted rounded-lg px-3 py-2">
            <p className="app-text-muted text-[11px] uppercase tracking-wide">Взята в работу</p>
            <p className="mt-1 font-medium text-[var(--foreground)]">{formatDate(request.started_at) || "—"}</p>
          </div>
          <div className="app-surface-muted rounded-lg px-3 py-2">
            <p className="app-text-muted text-[11px] uppercase tracking-wide">Завершена</p>
            <p className="mt-1 font-medium text-[var(--foreground)]">{formatDate(request.completed_at) || "—"}</p>
          </div>
        </div>
        {request.actual_cost ? (
          <div className="mt-3 inline-flex rounded-full app-badge-accent px-2.5 py-1 text-xs font-medium">
            Фактическая сумма: {formatMoney(request.actual_cost)}
          </div>
        ) : null}
      </div>

      {request.items && request.items.length > 0 ? (
        <div className="app-surface rounded-xl p-4">
          <p className="mb-3 text-sm font-semibold text-[var(--foreground)]">Позиции</p>
          <div className="space-y-2">
            {request.items.map((item, index) => (
              <div key={index} className="app-surface-muted rounded-lg px-3 py-3 text-xs">
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0 flex-1">
                    <p className="app-text-wrap font-medium text-[var(--foreground)]">{item.name}</p>
                    {item.description ? (
                      <p className="app-text-wrap mt-1 text-[var(--muted-foreground)]">{item.description}</p>
                    ) : null}
                    {item.supplier_info ? (
                      <p className="app-text-wrap mt-1 text-[var(--muted-foreground)]">
                        Поставщик: {item.supplier_info}
                      </p>
                    ) : null}
                  </div>
                  <div className="text-right">
                    <p className="font-medium text-[var(--foreground)]">{formatMoney(item.total_price)}</p>
                    <p className="app-text-muted mt-1">
                      {item.quantity} {item.unit}
                    </p>
                  </div>
                </div>
                <div className="app-text-muted mt-2 flex flex-wrap items-center gap-x-3 gap-y-1">
                  <span>Цена/ед.: {formatMoney(item.estimated_unit_price)}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      ) : null}

      {request.approvals && request.approvals.length > 0 ? (
        <div className="app-surface rounded-xl p-4">
          <p className="mb-3 text-sm font-semibold text-[var(--foreground)]">Согласования</p>
          <div className="space-y-2">
            {request.approvals.map((approval) => (
              <div
                key={approval.id}
                className="app-surface-muted flex items-center gap-2 rounded-lg px-3 py-2 text-xs"
              >
                {approvalIconByStatus(approval.status)}
                <span className="font-medium text-[var(--foreground)]">
                  {displayUserName(approval.approver, approval.approver_name)}
                </span>
                <span className="app-text-muted">({approval.step_label || `Этап ${approval.priority}`})</span>
                {approval.comment ? (
                  <span className="app-text-wrap app-text-muted ml-auto max-w-full italic">
                    «{approval.comment}»
                  </span>
                ) : null}
              </div>
            ))}
          </div>
        </div>
      ) : null}

      {footer}
    </div>
  );
}
