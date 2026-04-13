"use client";

import Link from "next/link";
import { Check, CircleDot, X } from "lucide-react";
import { RequestAvatar } from "@/components/requests/RequestAvatar";

import { formatDate, formatMoney, userProfileLink } from "@/lib/shared";
import type { ProcurementRequest, User } from "@/types/api";

interface ProcurementRequestDetailContentProps {
  currentUserId?: number | null;
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

const initialsFromName = (name: string) =>
  name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase() || "")
    .join("") || "?";

export function ProcurementRequestDetailContent({
  currentUserId,
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
            {request.approvals.map((approval) => {
              const approver =
                typeof approval.approver === "object" && approval.approver
                  ? approval.approver
                  : null;
              const approverName = displayUserName(approval.approver, approval.approver_name);
              const approverLink = approver ? userProfileLink(approver, currentUserId) : "";

              return (
              <div key={approval.id} className="rounded-lg px-1 py-1 text-xs">
                <div className="flex flex-wrap items-center gap-2">
                  {approvalIconByStatus(approval.status)}
                  {approverLink ? (
                    <Link
                      href={approverLink}
                      className="app-badge inline-flex max-w-full items-center gap-2 rounded-full px-2.5 py-1 text-xs font-medium hover:bg-[var(--surface-tertiary)]"
                    >
                      <RequestAvatar
                        alt={approverName}
                        fallback={initialsFromName(approverName)}
                        size="sm"
                        src={approver?.avatar}
                      />
                      <span className="truncate">{approverName}</span>
                    </Link>
                  ) : (
                    <span className="app-badge inline-flex max-w-full items-center gap-2 rounded-full px-2.5 py-1 text-xs font-medium">
                      <RequestAvatar
                        alt={approverName}
                        fallback={initialsFromName(approverName)}
                        size="sm"
                        src={approver?.avatar}
                      />
                      <span className="truncate">{approverName}</span>
                    </span>
                  )}
                  <span className="app-text-muted">
                    ({approval.step_label || `Этап ${approval.priority}`})
                  </span>
                </div>
                {approval.comment ? (
                  <p className="app-text-wrap app-text-muted mt-2 pl-6 italic">
                    «{approval.comment}»
                  </p>
                ) : null}
              </div>
            );
            })}
          </div>
        </div>
      ) : null}

      {footer}
    </div>
  );
}
