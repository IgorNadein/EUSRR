"use client";

import { useState } from "react";
import Link from "next/link";
import { AlertTriangle, Check, CheckCircle2, CircleDot, ExternalLink, MessageSquare, Minus, Plus, RotateCcw, Save, SlidersHorizontal, X } from "lucide-react";
import { RequestAvatar } from "@/components/requests/RequestAvatar";
import { CommentComposer, CommentDeleteButton } from "@/components/shared/CommentControls";

import { cleanLinkRows, linkHref, toLinkRows } from "@/lib/procurementLinks";
import { formatDate, formatMoney, userProfileLink } from "@/lib/shared";
import type { ProcurementItem, ProcurementItemComment, ProcurementItemExecutionStatus, ProcurementRequest, User } from "@/types/api";

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
  canDeleteAnyComment?: boolean;
  onUpdateItem?: (requestId: number, itemId: number, patch: Record<string, unknown>) => void | Promise<unknown>;
  onReportItemIssue?: (requestId: number, itemId: number, text?: string) => void | Promise<unknown>;
  onMarkAllReceived?: (requestId: number) => void | Promise<unknown>;
  itemCommentsMap?: Record<number, ProcurementItemComment[]>;
  itemCommentDrafts?: Record<number, string>;
  expandedItemComments?: Record<number, boolean>;
  onToggleItemComments?: (itemId: number) => void | Promise<void>;
  onItemCommentDraftChange?: (itemId: number, value: string) => void;
  onAddItemComment?: (requestId: number, itemId: number) => void | Promise<void>;
  onDeleteItemComment?: (requestId: number, itemId: number, commentId: number) => void | Promise<void>;
  footer?: React.ReactNode;
}

type ItemProcessingDraft = {
  execution_status: ProcurementItemExecutionStatus;
  expected_delivery_date: string;
  actual_unit_price: string;
  links: string[];
  ordered_quantity: string;
  received_quantity: string;
};

const executionStatusOptions: { value: ProcurementItemExecutionStatus; label: string }[] = [
  { value: "pending", label: "Не выполнено" },
  { value: "ordered", label: "Заказано" },
  { value: "rejected", label: "Отказано" },
  { value: "received", label: "Получено" },
  { value: "completed_with_issue", label: "Выполнено с замечанием" },
  { value: "edited", label: "Отредактировано" },
  { value: "defective", label: "Брак / перезаказ" },
];

const problemExecutionStatuses = new Set<ProcurementItemExecutionStatus>([
  "completed_with_issue",
  "edited",
  "defective",
]);

const executionStatusBadgeClass = (status?: ProcurementItemExecutionStatus) => {
  if (status === "ordered" || status === "received") return "app-feedback-success";
  if (status === "rejected") return "app-feedback-danger";
  if (status && problemExecutionStatuses.has(status)) return "app-feedback-warning";
  return "app-badge";
};

const toNumber = (value?: string | number | null): number => {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : 0;
};

const toOptionalInteger = (value: string): number | null => {
  if (value.trim() === "") return null;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? Math.max(0, Math.trunc(parsed)) : null;
};

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
  links: toLinkRows(item.links),
  ordered_quantity: item.ordered_quantity === null || item.ordered_quantity === undefined ? "" : String(item.ordered_quantity),
  received_quantity: item.received_quantity === null || item.received_quantity === undefined ? "" : String(item.received_quantity),
});

interface ProcurementItemCardProps {
  item: ProcurementItem;
  requestId: number;
  displayUserName: (
    person?: User | number | null,
    fallbackName?: string | null,
    fallbackEmail?: string | null,
  ) => string;
  canEditItemProcessing: boolean;
  canReportIssue: boolean;
  currentUserId?: number | null;
  canDeleteAnyComment?: boolean;
  busyKey?: string | null;
  onUpdateItem?: (requestId: number, itemId: number, patch: Record<string, unknown>) => void | Promise<unknown>;
  onReportItemIssue?: (requestId: number, itemId: number, text?: string) => void | Promise<unknown>;
  comments?: ProcurementItemComment[];
  commentDraft?: string;
  commentsOpen?: boolean;
  onToggleComments?: (itemId: number) => void | Promise<void>;
  onCommentDraftChange?: (itemId: number, value: string) => void;
  onAddComment?: (requestId: number, itemId: number) => void | Promise<void>;
  onDeleteComment?: (requestId: number, itemId: number, commentId: number) => void | Promise<void>;
}

function ProcurementItemCard({
  item,
  requestId,
  displayUserName,
  canEditItemProcessing,
  canReportIssue,
  currentUserId,
  canDeleteAnyComment = false,
  busyKey,
  onUpdateItem,
  onReportItemIssue,
  comments = [],
  commentDraft = "",
  commentsOpen = false,
  onToggleComments,
  onCommentDraftChange,
  onAddComment,
  onDeleteComment,
}: ProcurementItemCardProps) {
  const [draft, setDraft] = useState<ItemProcessingDraft>(() => normalizeItemDraft(item));
  const [processingOpen, setProcessingOpen] = useState(false);
  const links = Array.isArray(item.links) ? item.links.filter(Boolean) : [];
  const commentsTotal = item.comments_count ?? comments.length;
  const requestedQuantity = Math.max(0, Math.trunc(toNumber(item.quantity)));
  const orderedQuantity = item.ordered_quantity ?? 0;
  const receivedQuantity = item.received_quantity ?? 0;
  const status = item.execution_status || "pending";
  const statusLabel = item.execution_status_display || executionStatusOptions.find((option) => option.value === status)?.label || "Не выполнено";
  const canCancelReceived = canEditItemProcessing && status === "received";
  const canMarkIssue = Boolean(
    canReportIssue &&
    onReportItemIssue &&
    status !== "rejected" &&
    status !== "defective" &&
    (canEditItemProcessing || status === "received")
  );

  const updateDraft = (patch: Partial<ItemProcessingDraft>) => {
    setDraft((previous) => ({ ...previous, ...patch }));
  };

  const adjustDraftQuantity = (field: "ordered_quantity" | "received_quantity", delta: number) => {
    setDraft((previous) => {
      const current = toOptionalInteger(previous[field]) ?? 0;
      const next = Math.min(requestedQuantity, Math.max(0, current + delta));
      return { ...previous, [field]: String(next) };
    });
  };

  const saveItemProcessing = () => {
    return onUpdateItem?.(requestId, item.id, {
      execution_status: draft.execution_status,
      expected_delivery_date: draft.expected_delivery_date || null,
      actual_unit_price: draft.actual_unit_price || null,
      ordered_quantity: toOptionalInteger(draft.ordered_quantity),
      received_quantity: toOptionalInteger(draft.received_quantity),
      links: cleanLinkRows(draft.links),
    });
  };

  const cancelReceived = () => {
    const nextStatus: ProcurementItemExecutionStatus = Number(item.ordered_quantity || 0) > 0 ? "ordered" : "pending";
    return onUpdateItem?.(requestId, item.id, {
      execution_status: nextStatus,
      received_quantity: 0,
    });
  };

  return (
    <div className="app-surface-muted rounded-lg px-3 py-3 text-xs">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <p className="app-text-muted text-[11px] font-semibold uppercase tracking-wide">
          Позиция
        </p>
        <span className={`app-status-pill ${executionStatusBadgeClass(status)}`}>{statusLabel}</span>
      </div>
      <div className="grid gap-3 md:grid-cols-2">
        <section className="min-w-0 rounded-lg bg-[var(--surface-primary)] px-3 py-3">
          <div className="mb-2">
            <p className="app-text-muted text-[11px] font-semibold uppercase tracking-wide">
              От заказчика
            </p>
          </div>
          <div className="grid gap-2 sm:grid-cols-[minmax(0,1fr)_auto]">
            <div className="min-w-0">
              <p className="app-text-muted text-[11px]">Название</p>
              <p className="app-text-wrap mt-0.5 font-medium text-[var(--foreground)]">{item.name}</p>
              {item.description ? (
                <p className="app-text-wrap mt-1 text-[var(--muted-foreground)]">{item.description}</p>
              ) : null}
              {item.supplier_info ? (
                <p className="app-text-wrap mt-1 text-[var(--muted-foreground)]">
                  Поставщик: {item.supplier_info}
                </p>
              ) : null}
            </div>
            <div className="shrink-0 sm:text-right">
              <div>
                <p className="app-text-muted text-[11px]">Количество</p>
                <p className="mt-0.5 font-medium text-[var(--foreground)]">
                  {item.quantity} {item.unit}
                </p>
              </div>
              <div className="mt-2">
                <p className="app-text-muted text-[11px]">Цена ориентир</p>
                <p className="mt-0.5 font-medium text-[var(--foreground)]">
                  {formatMoney(item.estimated_unit_price)}
                </p>
              </div>
            </div>
          </div>
          {links.length > 0 ? (
            <div className="mt-2">
              <p className="app-text-muted mb-1 text-[11px] font-medium">Ссылки / варианты</p>
              <div className="flex flex-wrap gap-1.5">
                {links.map((link, linkIndex) => (
                  <a
                    key={`${item.id}-${linkIndex}`}
                    href={linkHref(link)}
                    target="_blank"
                    rel="noreferrer"
                    className="app-badge inline-flex max-w-full items-center gap-1 rounded-full px-2 py-1 text-[11px] font-medium no-underline hover:bg-[var(--surface-tertiary)] hover:no-underline"
                  >
                    <ExternalLink size={11} />
                    <span className="truncate">{link}</span>
                  </a>
                ))}
              </div>
            </div>
          ) : null}
        </section>

        <section className="min-w-0 rounded-lg bg-[var(--surface-primary)] px-3 py-3">
          <div className="mb-2">
            <p className="app-text-muted text-[11px] font-semibold uppercase tracking-wide">
              От закупщика
            </p>
          </div>
          <div className="grid grid-cols-2 gap-2">
            <div>
              <p className="app-text-muted text-[11px]">Дата поступления</p>
              <p className="mt-0.5 font-medium text-[var(--foreground)]">
                {formatDate(item.expected_delivery_date) || "—"}
              </p>
            </div>
            <div>
              <p className="app-text-muted text-[11px]">Цена факт</p>
              <p className="mt-0.5 font-medium text-[var(--foreground)]">
                {item.actual_unit_price ? formatMoney(item.actual_unit_price) : "—"}
              </p>
            </div>
            <div>
              <p className="app-text-muted text-[11px]">Заказано</p>
              <p className="mt-0.5 font-medium text-[var(--foreground)]">
                {orderedQuantity}/{requestedQuantity}
              </p>
            </div>
            <div>
              <p className="app-text-muted text-[11px]">Получено</p>
              <p className="mt-0.5 font-medium text-[var(--foreground)]">
                {receivedQuantity}/{requestedQuantity}
              </p>
            </div>
            <div>
              <p className="app-text-muted text-[11px]">Сумма расчёт</p>
              <p className="mt-0.5 font-medium text-[var(--foreground)]">
                {formatMoney(item.total_price)}
              </p>
            </div>
          </div>
        </section>
      </div>

      <div className="mt-3 flex flex-wrap items-center gap-2">
        <div>
          <button
            type="button"
            onClick={() => void onToggleComments?.(item.id)}
            className="app-action-ghost inline-flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-xs font-medium"
          >
            <MessageSquare size={13} />
            <span>Комментарии</span>
            {commentsTotal > 0 ? (
              <span className="app-counter inline-flex min-w-4 items-center justify-center px-1 py-0.5 text-[10px] font-bold text-white">
                {commentsTotal}
              </span>
            ) : null}
          </button>
        </div>

        {canEditItemProcessing ? (
          <button
            type="button"
            onClick={() => setProcessingOpen((open) => !open)}
            className="app-action-ghost inline-flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-xs font-medium"
          >
            <SlidersHorizontal size={13} />
            <span>Исполнение</span>
          </button>
        ) : null}

        {canCancelReceived ? (
          <button
            type="button"
            onClick={() => void cancelReceived()}
            disabled={busyKey === `item-${item.id}`}
            className="app-action-secondary inline-flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-xs font-medium disabled:opacity-60"
          >
            <RotateCcw size={13} />
            <span>Отменить получение</span>
          </button>
        ) : null}

        {canMarkIssue ? (
          <button
            type="button"
            onClick={() => void onReportItemIssue?.(requestId, item.id)}
            disabled={busyKey === `item-issue-${item.id}`}
            className="app-feedback-warning inline-flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-xs font-medium disabled:opacity-60"
          >
            <AlertTriangle size={13} />
            <span>Брак</span>
          </button>
        ) : null}
      </div>

      {commentsOpen ? (
        <div className="mt-2 space-y-2">
          {comments.length === 0 ? (
            <p className="app-text-muted text-xs">Комментариев по позиции пока нет</p>
          ) : (
            comments.map((comment) => {
              const canDeleteComment = Boolean(
                canDeleteAnyComment || (comment.author?.id && currentUserId === comment.author.id),
              );

              return (
                <div key={comment.id} className="rounded-lg bg-[var(--surface-primary)] px-3 py-2 text-xs">
                  <div className="mb-1 flex items-center justify-between gap-2">
                    <span className="font-medium text-[var(--foreground)]">
                      {displayUserName(comment.author)}
                    </span>
                    <div className="flex items-center gap-2">
                      <span className="app-text-muted">{formatDate(comment.created_at)}</span>
                      {canDeleteComment ? (
                        <CommentDeleteButton
                          disabled={busyKey === `item-comment-delete-${comment.id}`}
                          onClick={() => onDeleteComment?.(requestId, item.id, comment.id)}
                        />
                      ) : null}
                    </div>
                  </div>
                  <p className="app-text-wrap text-[var(--foreground)]">{comment.text}</p>
                </div>
              );
            })
          )}
          <CommentComposer
            value={commentDraft}
            onChange={(value) => onCommentDraftChange?.(item.id, value)}
            onSubmit={() => onAddComment?.(requestId, item.id)}
            disabled={busyKey === `item-comment-${item.id}`}
            placeholder="Комментарий по позиции"
          />
        </div>
      ) : null}

      {canEditItemProcessing && processingOpen ? (
        <div className="mt-3 grid gap-2 rounded-lg bg-[var(--surface-primary)] p-3 sm:grid-cols-2">
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
            <label className="app-text-muted mb-1 block text-[11px] font-medium">Заказано, шт.</label>
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={() => adjustDraftQuantity("ordered_quantity", -1)}
                className="app-action-secondary inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-lg"
              >
                <Minus size={12} />
              </button>
              <input
                type="number"
                min={0}
                max={requestedQuantity}
                value={draft.ordered_quantity}
                onChange={(event) => {
                  const parsed = toOptionalInteger(event.target.value);
                  updateDraft({
                    ordered_quantity: parsed === null ? "" : String(Math.min(requestedQuantity, parsed)),
                  });
                }}
                placeholder={`0-${requestedQuantity}`}
                className="app-input min-w-0 flex-1 rounded-lg px-3 py-2 text-xs"
              />
              <button
                type="button"
                onClick={() => adjustDraftQuantity("ordered_quantity", 1)}
                className="app-action-secondary inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-lg"
              >
                <Plus size={12} />
              </button>
            </div>
          </div>
          <div>
            <label className="app-text-muted mb-1 block text-[11px] font-medium">Получено, шт.</label>
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={() => adjustDraftQuantity("received_quantity", -1)}
                className="app-action-secondary inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-lg"
              >
                <Minus size={12} />
              </button>
              <input
                type="number"
                min={0}
                max={requestedQuantity}
                value={draft.received_quantity}
                onChange={(event) => {
                  const parsed = toOptionalInteger(event.target.value);
                  updateDraft({
                    received_quantity: parsed === null ? "" : String(Math.min(requestedQuantity, parsed)),
                  });
                }}
                placeholder={`0-${requestedQuantity}`}
                className="app-input min-w-0 flex-1 rounded-lg px-3 py-2 text-xs"
              />
              <button
                type="button"
                onClick={() => adjustDraftQuantity("received_quantity", 1)}
                className="app-action-secondary inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-lg"
              >
                <Plus size={12} />
              </button>
            </div>
          </div>
          <div>
            <label className="app-text-muted mb-1 block text-[11px] font-medium">Ссылки</label>
            <div className="space-y-2">
              {draft.links.map((link, linkIndex) => (
                <div key={linkIndex} className="flex items-center gap-2">
                  <input
                    value={link}
                    onChange={(event) => updateDraft({
                      links: draft.links.map((currentLink, currentIndex) => (
                        currentIndex === linkIndex ? event.target.value : currentLink
                      )),
                    })}
                    placeholder="https://example.ru/item"
                    className="app-input min-w-0 flex-1 rounded-lg px-3 py-2 text-xs"
                  />
                  {draft.links.length > 1 ? (
                    <button
                      type="button"
                      onClick={() => updateDraft({
                        links: draft.links.filter((_, currentIndex) => currentIndex !== linkIndex),
                      })}
                      className="app-action-secondary inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-lg"
                      title="Удалить ссылку"
                    >
                      <X size={12} />
                    </button>
                  ) : null}
                </div>
              ))}
              <button
                type="button"
                onClick={() => updateDraft({ links: ["", ...draft.links] })}
                className="app-link-accent inline-flex items-center gap-1 text-xs font-medium"
              >
                <Plus size={12} /> Добавить ссылку
              </button>
            </div>
          </div>
          <div className="sm:col-span-2">
            <button
              type="button"
              onClick={() => void saveItemProcessing()}
              disabled={busyKey === `item-${item.id}`}
              className="app-action-primary inline-flex items-center gap-1 rounded-lg px-3 py-2 text-xs font-medium disabled:opacity-60"
            >
              <Save size={13} /> Сохранить исполнение
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
  canDeleteAnyComment = false,
  onUpdateItem,
  onReportItemIssue,
  onMarkAllReceived,
  itemCommentsMap = {},
  itemCommentDrafts = {},
  expandedItemComments = {},
  onToggleItemComments,
  onItemCommentDraftChange,
  onAddItemComment,
  onDeleteItemComment,
  footer,
}: ProcurementRequestDetailContentProps) {
  const canEditItemProcessing = Boolean(canProcessItems && onUpdateItem);
  const isRequestPending = String(request.status || "").toLowerCase() === "pending";
  const requestorId = typeof request.requestor === "number" ? request.requestor : request.requestor?.id ?? null;
  const executorId = typeof request.executor === "number" ? request.executor : request.executor?.id ?? null;
  const canReportIssues = Boolean(
    !isRequestPending && onReportItemIssue && currentUserId && (
      canEditItemProcessing ||
      currentUserId === requestorId ||
      currentUserId === executorId
    ),
  );

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
                  item.ordered_quantity ?? "",
                  item.received_quantity ?? "",
                  Array.isArray(item.links) ? item.links.join("|") : "",
                ].join(":")}
                item={item}
                requestId={request.id}
                displayUserName={displayUserName}
                canEditItemProcessing={canEditItemProcessing}
                canReportIssue={canReportIssues}
                currentUserId={currentUserId}
                canDeleteAnyComment={canDeleteAnyComment}
                busyKey={busyKey}
                onUpdateItem={onUpdateItem}
                onReportItemIssue={onReportItemIssue}
                comments={itemCommentsMap[item.id] || []}
                commentDraft={itemCommentDrafts[item.id] || ""}
                commentsOpen={Boolean(expandedItemComments[item.id])}
                onToggleComments={onToggleItemComments}
                onCommentDraftChange={onItemCommentDraftChange}
                onAddComment={onAddItemComment}
                onDeleteComment={onDeleteItemComment}
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
