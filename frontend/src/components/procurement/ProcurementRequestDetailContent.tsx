"use client";

import { useState } from "react";
import Link from "next/link";
import { Check, CheckCircle2, CircleDot, ExternalLink, Save, X } from "lucide-react";
import { RequestAvatar } from "@/components/requests/RequestAvatar";

import { formatDate, formatMoney, userProfileLink } from "@/lib/shared";
import type { ProcurementItem, ProcurementItemExecutionStatus, ProcurementRequest, User } from "@/types/api";

interface ProcurementRequestDetailContentProps {
  currentUserId?: number | null;
  request: ProcurementRequest;
  displayUserName: (
    person?: User | number | null,
    fallbackName?: string | null,
    fallbackEmail?: string | null,
  ) => string;
  canProcessItems?: boolean;
  busyKey?: string | null;
  onUpdateItem?: (requestId: number, itemId: number, patch: Record<string, unknown>) => void | Promise<unknown>;
  onMarkAllReceived?: (requestId: number) => void | Promise<unknown>;
  footer?: React.ReactNode;
}

type ItemProcessingDraft = {
  execution_status: ProcurementItemExecutionStatus;
  expected_delivery_date: string;
  actual_unit_price: string;
  executor_comment: string;
  linksText: string;
};

const executionStatusOptions: { value: ProcurementItemExecutionStatus; label: string }[] = [
  { value: "pending", label: "Не выполнено" },
  { value: "ordered", label: "Заказано" },
  { value: "rejected", label: "Отказано" },
  { value: "received", label: "Получено" },
  { value: "completed_with_issue", label: "Выполнено с замечанием" },
  { value: "edited", label: "Отредактировано" },
];

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

const normalizeItemDraft = (item: ProcurementItem): ItemProcessingDraft => ({
  execution_status: item.execution_status || "pending",
  expected_delivery_date: item.expected_delivery_date || "",
  actual_unit_price: item.actual_unit_price ? String(item.actual_unit_price) : "",
  executor_comment: item.executor_comment || "",
  linksText: Array.isArray(item.links) ? item.links.join("\n") : "",
});

const parseLinks = (value: string): string[] => (
  value
    .split(/[\n,]+/)
    .map((link) => link.trim())
    .filter(Boolean)
);

const linkHref = (link: string) => (/^https?:\/\//i.test(link) ? link : `https://${link}`);

interface ProcurementItemCardProps {
  item: ProcurementItem;
  requestId: number;
  canEditItemProcessing: boolean;
  busyKey?: string | null;
  onUpdateItem?: (requestId: number, itemId: number, patch: Record<string, unknown>) => void | Promise<unknown>;
}

function ProcurementItemCard({
  item,
  requestId,
  canEditItemProcessing,
  busyKey,
  onUpdateItem,
}: ProcurementItemCardProps) {
  const [draft, setDraft] = useState<ItemProcessingDraft>(() => normalizeItemDraft(item));
  const links = Array.isArray(item.links) ? item.links.filter(Boolean) : [];

  const updateDraft = (patch: Partial<ItemProcessingDraft>) => {
    setDraft((previous) => ({ ...previous, ...patch }));
  };

  const saveItemProcessing = () => {
    return onUpdateItem?.(requestId, item.id, {
      execution_status: draft.execution_status,
      expected_delivery_date: draft.expected_delivery_date || null,
      actual_unit_price: draft.actual_unit_price || null,
      executor_comment: draft.executor_comment,
      links: parseLinks(draft.linksText),
    });
  };

  return (
    <div className="app-surface-muted rounded-lg px-3 py-3 text-xs">
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
          {links.length > 0 ? (
            <div className="mt-2 flex flex-wrap gap-1.5">
              {links.map((link, linkIndex) => (
                <a
                  key={`${item.id}-${linkIndex}`}
                  href={linkHref(link)}
                  target="_blank"
                  rel="noreferrer"
                  className="app-badge inline-flex max-w-full items-center gap-1 rounded-full px-2 py-1 text-[11px] font-medium hover:bg-[var(--surface-tertiary)]"
                >
                  <ExternalLink size={11} />
                  <span className="truncate">{link}</span>
                </a>
              ))}
            </div>
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
        {item.actual_unit_price ? <span>Факт/ед.: {formatMoney(item.actual_unit_price)}</span> : null}
        <span>Статус: {item.execution_status_display || "Не выполнено"}</span>
        {item.expected_delivery_date ? <span>Ожидается: {formatDate(item.expected_delivery_date)}</span> : null}
      </div>
      {item.executor_comment ? (
        <p className="app-text-wrap app-text-muted mt-2">
          Комментарий исполнителя: {item.executor_comment}
        </p>
      ) : null}

      {canEditItemProcessing ? (
        <div className="mt-3 grid gap-2 rounded-lg border border-[var(--border)] bg-[var(--surface-primary)] p-3 sm:grid-cols-2">
          <div>
            <label className="app-text-muted mb-1 block text-[11px] font-medium">Статус позиции</label>
            <select
              value={draft.execution_status}
              onChange={(event) => updateDraft({ execution_status: event.target.value as ProcurementItemExecutionStatus })}
              className="app-select w-full rounded-lg px-3 py-2 text-xs"
            >
              {executionStatusOptions.map((option) => (
                <option key={option.value} value={option.value}>{option.label}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="app-text-muted mb-1 block text-[11px] font-medium">Ожидаемая дата</label>
            <input
              type="date"
              value={draft.expected_delivery_date}
              onChange={(event) => updateDraft({ expected_delivery_date: event.target.value })}
              className="app-input w-full rounded-lg px-3 py-2 text-xs"
            />
          </div>
          <div>
            <label className="app-text-muted mb-1 block text-[11px] font-medium">Фактическая цена/ед.</label>
            <input
              type="number"
              step="0.01"
              value={draft.actual_unit_price}
              onChange={(event) => updateDraft({ actual_unit_price: event.target.value })}
              className="app-input w-full rounded-lg px-3 py-2 text-xs"
            />
          </div>
          <div>
            <label className="app-text-muted mb-1 block text-[11px] font-medium">Ссылки</label>
            <textarea
              value={draft.linksText}
              onChange={(event) => updateDraft({ linksText: event.target.value })}
              rows={2}
              className="app-input app-text-wrap min-h-16 w-full rounded-lg px-3 py-2 text-xs"
            />
          </div>
          <div className="sm:col-span-2">
            <label className="app-text-muted mb-1 block text-[11px] font-medium">Комментарий исполнителя</label>
            <textarea
              value={draft.executor_comment}
              onChange={(event) => updateDraft({ executor_comment: event.target.value })}
              rows={2}
              className="app-input app-text-wrap min-h-16 w-full rounded-lg px-3 py-2 text-xs"
            />
          </div>
          <div className="sm:col-span-2">
            <button
              type="button"
              onClick={() => void saveItemProcessing()}
              disabled={busyKey === `item-${item.id}`}
              className="app-action-primary inline-flex items-center gap-1 rounded-lg px-3 py-2 text-xs font-medium disabled:opacity-60"
            >
              <Save size={13} /> Сохранить позицию
            </button>
          </div>
        </div>
      ) : null}
    </div>
  );
}

export function ProcurementRequestDetailContent({
  currentUserId,
  request,
  displayUserName,
  canProcessItems = false,
  busyKey,
  onUpdateItem,
  onMarkAllReceived,
  footer,
}: ProcurementRequestDetailContentProps) {
  const canEditItemProcessing = Boolean(canProcessItems && onUpdateItem);

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
          <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
            <p className="text-sm font-semibold text-[var(--foreground)]">Позиции</p>
            {canEditItemProcessing && onMarkAllReceived ? (
              <button
                type="button"
                onClick={() => onMarkAllReceived(request.id)}
                disabled={busyKey === `mark-all-${request.id}`}
                className="app-action-primary inline-flex items-center gap-1 rounded-lg px-3 py-2 text-xs font-medium disabled:opacity-60"
              >
                <CheckCircle2 size={14} /> Отметить все полученными
              </button>
            ) : null}
          </div>
          <div className="space-y-2">
            {request.items.map((item) => (
              <ProcurementItemCard
                key={[
                  item.id,
                  item.execution_status || "",
                  item.expected_delivery_date || "",
                  item.actual_unit_price || "",
                  item.executor_comment || "",
                  Array.isArray(item.links) ? item.links.join("|") : "",
                ].join(":")}
                item={item}
                requestId={request.id}
                canEditItemProcessing={canEditItemProcessing}
                busyKey={busyKey}
                onUpdateItem={onUpdateItem}
              />
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
