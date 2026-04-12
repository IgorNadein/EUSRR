"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { AppShell } from "../../components/AppShell";
import { useUser } from "@/contexts/UserContext";
import Link from "next/link";
import { ProcurementRequestDetailContent } from "@/components/procurement/ProcurementRequestDetailContent";
import ProcurementStatsPanel from "@/components/procurement/ProcurementStatsPanel";
import ProcurementSuppliersPanel from "@/components/procurement/ProcurementSuppliersPanel";
import type { ProcurementRequest, UrgencyLevel } from "@/types/api";
import {
  ArrowUpDown,
  Check,
  ChevronDown,
  ChevronRight,
  ClipboardCheck,
  Filter,
  Loader2,
  MessageSquare,
  Package,
  Pencil,
  Play,
  Plus,
  Search,
  Send,
  ShoppingCart,
  ThumbsDown,
  ThumbsUp,
  Trash2,
  X,
  XCircle,
} from "lucide-react";
import { SearchableSelectSingle } from "@/components/shared/SearchableSelect";
import { formatDate, formatMoney } from "@/lib/shared";
import { useProcurementPage } from "@/hooks/useProcurementPage";
import { Modal } from "@/components/ui";

/* ══════════════════════════════════════════════════════
   Constants & helpers
   ══════════════════════════════════════════════════════ */

const statusMeta: Record<string, { label: string; cls: string }> = {
  draft:       { label: "Черновик",        cls: "app-badge" },
  pending:     { label: "На согласовании", cls: "app-feedback-warning" },
  approved:    { label: "Одобрено",        cls: "app-feedback-success" },
  in_progress: { label: "В работе",        cls: "app-selected" },
  completed:   { label: "Завершено",       cls: "app-selected" },
  rejected:    { label: "Отклонено",       cls: "app-feedback-danger" },
  cancelled:   { label: "Отменено",        cls: "app-badge" },
};
const defaultStatusMeta = { label: "—", cls: "app-badge" };

const urgencyMeta: Record<string, { label: string; cls: string }> = {
  low:      { label: "Низкая",      cls: "text-gray-500" },
  medium:   { label: "Средняя",     cls: "text-sky-600" },
  high:     { label: "Высокая",     cls: "text-amber-600" },
  critical: { label: "Критическая", cls: "text-rose-600" },
};

const orderingOptions = [
  { value: "-created_at", label: "Сначала новые" },
  { value: "created_at", label: "Сначала старые" },
  { value: "title", label: "По названию" },
  { value: "urgency", label: "По срочности ↑" },
  { value: "-urgency", label: "По срочности ↓" },
];

type ScopeTab = "all" | "mine" | "department" | "pending_approvals" | "my_work" | "available";
const scopeTabs: { value: ScopeTab; label: string }[] = [
  { value: "all",               label: "Все" },
  { value: "mine",              label: "Мои" },
  { value: "department",        label: "Мой отдел" },
  { value: "pending_approvals", label: "На согласование" },
  { value: "my_work",           label: "В работе у меня" },
  { value: "available",         label: "Доступные" },
];

const periodOptions = [
  { value: "", label: "Любой период" },
  { value: "today", label: "Сегодня" },
  { value: "week", label: "7 дней" },
  { value: "month", label: "30 дней" },
  { value: "quarter", label: "90 дней" },
];

const fmt = formatDate;
const money = formatMoney;
type RequestActionDialogKind = "approve" | "reject" | "cancel" | "delete";

const getReadableError = (error: unknown, fallback: string): string => {
  const raw = String((error as Error)?.message || fallback);
  const jsonStart = raw.indexOf("{");
  const payload = jsonStart >= 0 ? raw.slice(jsonStart) : raw;

  try {
    const parsed = JSON.parse(payload) as Record<string, unknown>;
    if (typeof parsed.error === "string" && parsed.error.trim()) {
      return parsed.error;
    }
    if (typeof parsed.detail === "string" && parsed.detail.trim()) {
      return parsed.detail;
    }
  } catch {
    return raw;
  }

  return raw;
};

function ProcurementRequestActionButtons({
  request,
  busyKey,
  canManage,
  isAuthor,
  isExecutor,
  isFinal,
  showApprovalActions = true,
  showSecondaryActions = true,
  onSubmit,
  onEdit,
  onDelete,
  onApprove,
  onReject,
  onStart,
  onComplete,
  onCancel,
}: {
  request: ProcurementRequest;
  busyKey: string | null;
  canManage: boolean;
  isAuthor: boolean;
  isExecutor: boolean;
  isFinal: (status?: string) => boolean;
  showApprovalActions?: boolean;
  showSecondaryActions?: boolean;
  onSubmit: (id: number) => void | Promise<unknown>;
  onEdit: (request: ProcurementRequest) => void;
  onDelete: (id: number) => void | Promise<unknown>;
  onApprove: (id: number) => void | Promise<unknown>;
  onReject: (id: number) => void | Promise<unknown>;
  onStart: (id: number) => void | Promise<unknown>;
  onComplete: (id: number) => void | Promise<unknown>;
  onCancel: (id: number) => void | Promise<unknown>;
}) {
  const status = String(request.status || "").toLowerCase();
  const isDraft = status === "draft";
  const isPending = status === "pending";
  const isApproved = status === "approved";
  const isInProgress = status === "in_progress";
  const canApproveThis = Boolean(request.can_current_user_approve);

  return (
    <div className="flex flex-wrap items-center gap-1.5 pt-1">
      {isDraft && isAuthor ? (
        <button
          type="button"
          onClick={() => onSubmit(request.id)}
          disabled={busyKey === `submit-${request.id}`}
          title="На согласование"
          className="app-action-primary inline-flex h-9 w-9 items-center justify-center rounded-lg disabled:opacity-60"
        >
          <Send size={14} />
        </button>
      ) : null}
      {showSecondaryActions && isDraft && isAuthor ? (
        <button
          type="button"
          onClick={() => onEdit(request)}
          title="Редактировать"
          className="app-action-secondary inline-flex h-9 w-9 items-center justify-center rounded-lg"
        >
          <Pencil size={14} />
        </button>
      ) : null}
      {showSecondaryActions && isDraft && (isAuthor || canManage) ? (
        <button
          type="button"
          onClick={() => onDelete(request.id)}
          disabled={busyKey === `delete-${request.id}`}
          title="Удалить"
          className="app-action-danger inline-flex h-9 w-9 items-center justify-center rounded-lg disabled:opacity-60"
        >
          <Trash2 size={14} />
        </button>
      ) : null}
      {showApprovalActions && isPending && canApproveThis ? (
        <>
          <button
            type="button"
            onClick={() => onApprove(request.id)}
            disabled={busyKey === `approve-${request.id}`}
            title="Одобрить"
            className="app-feedback-success inline-flex h-9 w-9 items-center justify-center rounded-lg disabled:opacity-60"
          >
            <ThumbsUp size={14} />
          </button>
          <button
            type="button"
            onClick={() => onReject(request.id)}
            disabled={busyKey === `reject-${request.id}`}
            title="Отклонить"
            className="app-action-danger inline-flex h-9 w-9 items-center justify-center rounded-lg disabled:opacity-60"
          >
            <ThumbsDown size={14} />
          </button>
        </>
      ) : null}
      {isApproved && !request.executor ? (
        <button
          type="button"
          onClick={() => onStart(request.id)}
          disabled={busyKey === `start-${request.id}`}
          title="Взять в работу"
          className="app-action-primary inline-flex h-9 w-9 items-center justify-center rounded-lg disabled:opacity-60"
        >
          <Play size={14} />
        </button>
      ) : null}
      {isInProgress && isExecutor ? (
        <button
          type="button"
          onClick={() => onComplete(request.id)}
          disabled={busyKey === `complete-${request.id}`}
          title="Завершить"
          className="app-action-primary inline-flex h-9 w-9 items-center justify-center rounded-lg disabled:opacity-60"
        >
          <ClipboardCheck size={14} />
        </button>
      ) : null}
      {showSecondaryActions && isAuthor && !isFinal(status) && status !== "draft" ? (
        <button
          type="button"
          onClick={() => onCancel(request.id)}
          disabled={busyKey === `cancel-${request.id}`}
          title="Отменить"
          className="app-action-secondary inline-flex h-9 w-9 items-center justify-center rounded-lg disabled:opacity-60"
        >
          <XCircle size={14} />
        </button>
      ) : null}
    </div>
  );
}

/* ══════════════════════════════════════════════════════
   Main page component
   ══════════════════════════════════════════════════════ */

export default function ProcurementPage() {
  const { user } = useUser();
  const {
    activeFilterCount,
    activeSection,
    actionError,
    actionSuccess,
    addItemRow,
    busyKey,
    canManage,
    canSupplierManage,
    closeModal,
    departmentFilter,
    departments,
    detailsCache,
    displayUserName,
    ensureRequestDetail,
    ensureCommentsLoaded,
    error,
    commentsMap,
    commentDrafts,
    setCommentDrafts,
    expandedIds,
    expandedComments,
    filteredRequests,
    filtersOpen,
    form,
    getDeptName,
    getRequestAmount,
    handleApprove,
    handleCancel,
    handleComplete,
    handleDelete,
    handleLoadMore,
    handleReject,
    handleSave,
    handleStart,
    handleSubmit,
    isFinal,
    isModalOpen,
    loadPage1,
    loading,
    loadingMore,
    modalMode,
    nextPage,
    openCreate,
    openEdit,
    ordering,
    periodFilter,
    removeItemRow,
    resolveUserId,
    requests,
    searchQuery,
    setActiveSection,
    setDepartmentFilter,
    setFiltersOpen,
    setForm,
    setOrdering,
    setPeriodFilter,
    setScope,
    setSearchQuery,
    setStatusFilter,
    setUrgencyFilter,
    statusFilter,
    toggleExpand,
    toggleComments,
    updateItemRow,
    urgencyFilter,
    userLink,
    scope,
    scopeCounts,
    handleAddComment,
    handleDeleteComment,
  } = useProcurementPage(user);

  const [detailModalId, setDetailModalId] = useState<number | null>(null);
  const [detailModalLoading, setDetailModalLoading] = useState(false);
  const [detailModalError, setDetailModalError] = useState<string | null>(null);
  const procurementMenuRef = useRef<HTMLDivElement | null>(null);
  const [procurementMenuOpenId, setProcurementMenuOpenId] = useState<number | null>(null);
  const [requestActionDialog, setRequestActionDialog] = useState<{ kind: RequestActionDialogKind; requestId: number } | null>(null);
  const [requestActionComment, setRequestActionComment] = useState("");

  const syncRequestUrl = useCallback((requestId: number | null) => {
    if (typeof window === "undefined") return;

    const url = new URL(window.location.href);
    if (requestId) {
      url.searchParams.set("request", String(requestId));
    } else {
      url.searchParams.delete("request");
    }

    window.history.replaceState({}, "", `${url.pathname}${url.search}${url.hash}`);
  }, []);

  const selectedRequest = useMemo(() => {
    if (!detailModalId) return null;
    return detailsCache[detailModalId] || requests.find((request) => request.id === detailModalId) || null;
  }, [detailModalId, detailsCache, requests]);

  const selectedActionRequest = useMemo(() => {
    if (!requestActionDialog) return null;
    return detailsCache[requestActionDialog.requestId] || requests.find((request) => request.id === requestActionDialog.requestId) || null;
  }, [detailsCache, requestActionDialog, requests]);

  const closeDetailModal = useCallback(() => {
    setDetailModalId(null);
    setDetailModalError(null);
    syncRequestUrl(null);
  }, [syncRequestUrl]);

  const openRequestActionDialog = useCallback((kind: RequestActionDialogKind, requestId: number) => {
    setRequestActionComment("");
    setRequestActionDialog({ kind, requestId });
  }, []);

  const closeRequestActionDialog = useCallback(() => {
    setRequestActionDialog(null);
    setRequestActionComment("");
  }, []);

  const submitRequestActionDialog = useCallback(async () => {
    if (!requestActionDialog) return;

    const { kind, requestId } = requestActionDialog;
    const payload = requestActionComment.trim();
    let success = false;

    if (kind === "approve") {
      success = await handleApprove(requestId, payload);
    } else if (kind === "reject") {
      success = await handleReject(requestId, payload);
    } else if (kind === "cancel") {
      success = await handleCancel(requestId, payload);
    } else if (kind === "delete") {
      success = await handleDelete(requestId);
    }

    if (success) {
      closeRequestActionDialog();
      if (detailModalId === requestId && kind === "delete") {
        closeDetailModal();
      }
    }
  }, [
    closeDetailModal,
    closeRequestActionDialog,
    detailModalId,
    handleApprove,
    handleCancel,
    handleDelete,
    handleReject,
    requestActionComment,
    requestActionDialog,
  ]);

  const openDetailModal = useCallback(async (requestId: number) => {
    setDetailModalLoading(true);
    setDetailModalError(null);

    try {
      await ensureRequestDetail(requestId);
      setDetailModalId(requestId);
      syncRequestUrl(requestId);
    } catch (detailError) {
      setDetailModalError(getReadableError(detailError, "Не удалось открыть заявку"));
    } finally {
      setDetailModalLoading(false);
    }
  }, [ensureRequestDetail, syncRequestUrl]);

  useEffect(() => {
    if (typeof window === "undefined") return;

    const requestParam = new URLSearchParams(window.location.search).get("request");
    if (!requestParam) return;

    const requestId = Number(requestParam);
    if (!Number.isFinite(requestId) || requestId <= 0) {
      syncRequestUrl(null);
      return;
    }

    void openDetailModal(requestId);
  }, [openDetailModal, syncRequestUrl]);

  useEffect(() => {
    if (!detailModalId) return;
    if (selectedRequest) return;
    closeDetailModal();
  }, [closeDetailModal, detailModalId, selectedRequest]);

  useEffect(() => {
    if (!detailModalId) return;
    void ensureCommentsLoaded(detailModalId).catch(() => {});
  }, [detailModalId, ensureCommentsLoaded]);

  useEffect(() => {
    if (procurementMenuOpenId === null) return;

    const handlePointerDown = (event: MouseEvent) => {
      if (procurementMenuRef.current && !procurementMenuRef.current.contains(event.target as Node)) {
        setProcurementMenuOpenId(null);
      }
    };

    const handleEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setProcurementMenuOpenId(null);
      }
    };

    document.addEventListener("mousedown", handlePointerDown);
    document.addEventListener("keydown", handleEscape);

    return () => {
      document.removeEventListener("mousedown", handlePointerDown);
      document.removeEventListener("keydown", handleEscape);
    };
  }, [procurementMenuOpenId]);

  /* ══════════════════════════════════════════════════════
     RENDER
     ══════════════════════════════════════════════════════ */

  return (
    <AppShell>
      {loading ? (
        <div className="app-surface rounded-2xl p-8 text-center">
          <Loader2 size={28} className="mx-auto mb-3 animate-spin text-sky-500" />
          <p className="app-text-muted text-sm">Загрузка заявок на закупку...</p>
        </div>
      ) : error ? (
        <div className="app-feedback-danger rounded-2xl p-6 text-center">
          <p className="text-sm text-red-800">{error}</p>
        </div>
      ) : (
        <section className="app-surface rounded-2xl p-4">
          {/* ── header ── */}
          <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
            <div>
              <p className="app-text-muted text-sm font-semibold uppercase tracking-wide">Закупки</p>
              {/* <div className="mt-2 flex flex-wrap gap-2">
                <button type="button" onClick={() => setActiveSection("requests")} className={`rounded-full px-3 py-1.5 text-xs font-medium transition ${activeSection === "requests" ? "app-pill-active" : "app-pill"}`}>
                  Заявки
                </button>
                <button type="button" onClick={() => setActiveSection("stats")} className={`rounded-full px-3 py-1.5 text-xs font-medium transition ${activeSection === "stats" ? "app-pill-active" : "app-pill"}`}>
                  Статистика
                </button>
                <button type="button" onClick={() => setActiveSection("suppliers")} className={`rounded-full px-3 py-1.5 text-xs font-medium transition ${activeSection === "suppliers" ? "app-pill-active" : "app-pill"}`}>
                  Поставщики
                </button>
              </div> */}
            </div>
            {activeSection === "requests" && (
              <button type="button" onClick={openCreate} className="app-action-primary inline-flex items-center gap-1 rounded-lg px-3 py-2 text-sm font-medium transition">
                <Plus size={14} /> Создать заявку
              </button>
            )}
          </div>

          {/* ── alerts ── */}
          {actionError && <p className="mb-3 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{actionError}</p>}
          {actionSuccess && <p className="app-feedback-success mb-3 rounded-lg px-3 py-2 text-sm">{actionSuccess}</p>}

          {activeSection === "stats" && <ProcurementStatsPanel />}

          {activeSection === "suppliers" && (
            <ProcurementSuppliersPanel canManage={canSupplierManage} />
          )}

          {activeSection === "requests" && (
            <>
          {/* ── search + filter ── */}
          <div className="mb-4 flex items-center gap-2">
            <div className="relative flex-1">
              <Search size={16} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
              <input
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                onKeyDown={(e) => { if (e.key === "Enter") loadPage1(); }}
                placeholder="Поиск по заявкам..."
                className="app-input w-full rounded-lg py-2.5 pl-9 pr-3 text-sm"
              />
            </div>
            <button
              type="button"
              title="Фильтры"
              onClick={() => setFiltersOpen((v) => !v)}
              className={`relative inline-flex items-center justify-center rounded-lg p-2.5 transition ${filtersOpen ? "app-selected app-accent-text" : "app-surface-muted app-text-muted hover:bg-[var(--surface-tertiary)]"}`}
            >
              <Filter size={16} />
              {activeFilterCount > 0 && (
                <span className="absolute -right-1 -top-1 flex h-4 min-w-4 items-center justify-center rounded-full bg-sky-500 px-1 text-[10px] font-bold text-white">{activeFilterCount}</span>
              )}
            </button>
            <div className="relative w-[148px] shrink-0">
              <ArrowUpDown size={15} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-gray-500" />
              <select
                value={ordering}
                onChange={(e) => setOrdering(e.target.value)}
                className="app-select w-full appearance-none rounded-lg py-2.5 pl-9 pr-8 text-xs font-medium"
                aria-label="Сортировка списка закупок"
              >
                {orderingOptions.map((option) => (
                  <option key={option.value} value={option.value}>{option.label}</option>
                ))}
              </select>
              <ChevronDown size={14} className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-gray-400" />
            </div>
          </div>

          {/* ── scope tabs ── */}
          <div className="mb-4 flex flex-wrap gap-2">
            {scopeTabs.map((tab) => (
              <button
                key={tab.value}
                type="button"
                onClick={() => setScope(tab.value)}
                className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1.5 text-xs font-medium transition ${
                  scope === tab.value
                    ? "app-pill-active"
                    : "app-pill"
                }`}
              >
                <span>{tab.label}</span>
                <span className={`app-badge px-1.5 py-0.5 text-[10px] font-bold ${
                  scope === tab.value ? "app-pill-count-active" : "app-pill-count"
                }`}>
                  {scopeCounts[tab.value] ?? 0}
                </span>
              </button>
            ))}
          </div>

          {/* ── filters panel ── */}
          {filtersOpen && (
            <div className="app-surface-muted mb-3 flex flex-col gap-2 rounded-xl p-3">
              <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)} className="app-select rounded-lg px-3 py-2 text-sm">
                <option value="">Все статусы</option>
                {Object.entries(statusMeta).map(([k, v]) => <option key={k} value={k}>{v.label}</option>)}
              </select>
              <select value={urgencyFilter} onChange={(e) => setUrgencyFilter(e.target.value)} className="app-select rounded-lg px-3 py-2 text-sm">
                <option value="">Все уровни срочности</option>
                {Object.entries(urgencyMeta).map(([k, v]) => <option key={k} value={k}>{v.label}</option>)}
              </select>
              <select value={departmentFilter} onChange={(e) => setDepartmentFilter(e.target.value)} className="app-select rounded-lg px-3 py-2 text-sm">
                <option value="">Все отделы</option>
                {departments.map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}
              </select>
              <select value={periodFilter} onChange={(e) => setPeriodFilter(e.target.value)} className="app-select rounded-lg px-3 py-2 text-sm">
                {periodOptions.map((option) => <option key={option.value || "all"} value={option.value}>{option.label}</option>)}
              </select>
              {activeFilterCount > 0 && (
                <button type="button" onClick={() => { setStatusFilter(""); setUrgencyFilter(""); setDepartmentFilter(""); setPeriodFilter(""); }} className="app-action-secondary rounded-lg px-3 py-2 text-sm font-medium transition">
                  Очистить фильтры
                </button>
              )}
            </div>
          )}

          {/* ══════════ Request cards ══════════ */}
          <div className="space-y-3">
            {filteredRequests.length === 0 ? (
              <div className="app-surface-muted rounded-xl p-8 text-center">
                <ShoppingCart size={22} className="app-text-muted mx-auto mb-2" />
                <p className="app-text-muted text-sm">Заявок на закупку не найдено</p>
              </div>
            ) : filteredRequests.map((req) => {
              const st = String(req.status || "").toLowerCase();
              const sMeta = statusMeta[st] ?? defaultStatusMeta;
              const urg = urgencyMeta[req.urgency] ?? urgencyMeta.medium;
              const isAuthor = Boolean(resolveUserId(req.requestor) && user?.id && resolveUserId(req.requestor) === user.id);
              const isExecutor = Boolean(resolveUserId(req.executor) && user?.id && resolveUserId(req.executor) === user.id);
              const isDraft = st === "draft";
              const isApproved = st === "approved";
              const isInProgress = st === "in_progress";
              const detail = detailsCache[req.id];
              const resolvedDetail = detail || req;
              const canApproveThis = Boolean((resolvedDetail.can_current_user_approve ?? req.can_current_user_approve));
              const canEditThis = Boolean(isDraft && isAuthor);
              const canDeleteThis = Boolean(isDraft && (isAuthor || canManage));
              const canCancelThis = Boolean(isAuthor && !isFinal(st) && st !== "draft");
              const hasSecondaryActions = canEditThis || canDeleteThis || canCancelThis;
              const expanded = expandedIds.has(req.id);
              const comments = commentsMap[req.id] || [];
              const commentsOpen = Boolean(expandedComments[req.id]);
              const commentsTotal = resolvedDetail.comments_count ?? req.comments_count ?? comments.length;
              const requestorName = displayUserName(req.requestor, req.requestor_name, req.requestor_email);
              const executorName = req.executor || req.executor_name ? displayUserName(req.executor, req.executor_name || undefined) : "";
              const requestorLink = userLink(req.requestor);
              const executorLink = userLink(req.executor);
              const itemsCount = resolvedDetail.items?.length ?? 0;
              const approvalsCount = resolvedDetail.approvals?.length ?? 0;

              return (
                <article key={req.id} className={`app-surface-muted rounded-xl transition hover:border-[var(--border-strong)] ${procurementMenuOpenId === req.id ? "relative z-20 overflow-visible" : "overflow-hidden"}`}>
                  <div className="px-4 py-3">
                    <div className="flex items-start gap-3">
                      <div className="flex shrink-0 flex-col items-center gap-3 pt-0.5">
                        <button
                          type="button"
                          onClick={() => toggleExpand(req.id)}
                          aria-label={expanded ? "Свернуть детали" : "Развернуть детали"}
                          className="app-action-secondary inline-flex h-8 w-8 items-center justify-center rounded-lg"
                        >
                          <ChevronDown size={15} className={`transition ${expanded ? "rotate-180" : ""}`} />
                        </button>
                        <button
                          type="button"
                          title={`Комментарии (${commentsTotal})`}
                          onClick={() => void toggleComments(req.id)}
                          className="app-action-secondary relative inline-flex h-8 w-8 items-center justify-center rounded-lg"
                        >
                          <MessageSquare size={15} />
                          {commentsTotal > 0 && (
                            <span className="app-counter absolute -right-1 -top-1 inline-flex min-w-4 items-center justify-center px-1 py-0.5 text-[10px] font-bold text-white">{commentsTotal}</span>
                          )}
                        </button>
                      </div>

                      <div className="min-w-0 flex-1">
                        <div className="flex items-start justify-between gap-3">
                          <div className="min-w-0 flex-1">
                            <div className="flex items-center gap-2">
                              <span className={`h-2 w-2 shrink-0 rounded-full ${st === "completed" ? "bg-teal-500" : st === "approved" ? "bg-emerald-500" : st === "pending" ? "bg-amber-500" : st === "in_progress" ? "bg-sky-500" : st === "rejected" ? "bg-rose-500" : "bg-slate-400"}`} />
                              <button
                                type="button"
                                onClick={() => void openDetailModal(req.id)}
                                className="truncate text-left text-sm font-semibold text-[var(--foreground)] transition hover:text-[var(--accent-primary-strong)]"
                                title="Открыть карточку заявки"
                              >
                                {req.title || "Без названия"}
                              </button>
                            </div>
                            <div className="app-text-muted mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs">
                              <span className="font-medium text-[var(--foreground)]">{getDeptName(req)}</span>
                              <span>{fmt(req.created_at)}</span>
                              {getRequestAmount(req) && <span className="font-medium text-[var(--foreground)]">{money(getRequestAmount(req))}</span>}
                            </div>
                          </div>

                          <div
                            ref={procurementMenuOpenId === req.id ? procurementMenuRef : null}
                            className="flex shrink-0 flex-col items-end gap-2"
                          >
                            <div className="flex items-center gap-2">
                              <span className={`app-status-pill shrink-0 ${sMeta.cls}`}>{sMeta.label}</span>
                              {hasSecondaryActions ? (
                                <div className="relative">
                                  <button
                                    type="button"
                                    onClick={() => setProcurementMenuOpenId((prev) => (prev === req.id ? null : req.id))}
                                    className="app-action-ghost flex h-8 w-8 items-center justify-center rounded-md"
                                    title="Действия с заявкой"
                                    aria-label="Действия с заявкой"
                                    aria-expanded={procurementMenuOpenId === req.id}
                                    aria-haspopup="menu"
                                  >
                                    <ChevronRight
                                      size={15}
                                      className={`transition-transform duration-200 ${procurementMenuOpenId === req.id ? "rotate-90" : ""}`}
                                    />
                                  </button>
                                  {procurementMenuOpenId === req.id ? (
                                    <div className="app-menu absolute right-0 top-full z-20 mt-2 w-44 rounded-xl py-1.5">
                                      {canCancelThis ? (
                                        <button
                                          type="button"
                                          disabled={busyKey === `cancel-${req.id}`}
                                          onClick={() => {
                                            setProcurementMenuOpenId(null);
                                            openRequestActionDialog("cancel", req.id);
                                          }}
                                          className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm text-[var(--foreground)] transition hover:bg-[var(--surface-secondary)] disabled:opacity-50"
                                        >
                                          <XCircle size={14} className="app-text-muted" />
                                          Отменить
                                        </button>
                                      ) : null}
                                      {canEditThis ? (
                                        <button
                                          type="button"
                                          onClick={() => {
                                            setProcurementMenuOpenId(null);
                                            openEdit(req);
                                          }}
                                          className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm text-[var(--foreground)] transition hover:bg-[var(--surface-secondary)]"
                                        >
                                          <Pencil size={14} className="app-text-muted" />
                                          Редактировать
                                        </button>
                                      ) : null}
                                      {canDeleteThis ? (
                                        <button
                                          type="button"
                                          disabled={busyKey === `delete-${req.id}`}
                                          onClick={() => {
                                            setProcurementMenuOpenId(null);
                                            openRequestActionDialog("delete", req.id);
                                          }}
                                          className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm text-[var(--danger-foreground)] transition hover:bg-[var(--danger-soft)] disabled:opacity-50"
                                        >
                                          <Trash2 size={13} className="text-[var(--danger-foreground)]" />
                                          Удалить
                                        </button>
                                      ) : null}
                                    </div>
                                  ) : null}
                                </div>
                              ) : null}
                            </div>
                            <span className={`text-[11px] font-medium ${urg.cls}`}>{urg.label} срочность</span>
                          </div>
                        </div>

                        <div className="app-text-muted mt-2 grid grid-cols-1 gap-x-3 gap-y-1 text-xs sm:grid-cols-2">
                          <div className="min-w-0">
                            <span>Заявитель:</span>{" "}
                            {requestorLink
                              ? <Link href={requestorLink} className="font-medium text-[var(--accent-primary-strong)] hover:text-[var(--accent-primary)]">{requestorName}</Link>
                              : <span className="font-medium text-[var(--foreground)]">{requestorName}</span>}
                          </div>
                          <div className="min-w-0">
                            <span>Исполнитель:</span>{" "}
                            {req.executor ? (
                              executorLink
                                ? <Link href={executorLink} className="font-medium text-[var(--accent-primary-strong)] hover:text-[var(--accent-primary)]">{executorName}</Link>
                                : <span className="font-medium text-[var(--foreground)]">{executorName}</span>
                            ) : (
                              <span>не назначен</span>
                            )}
                          </div>
                          {(itemsCount > 0 || approvalsCount > 0) && (
                            <div className="col-span-2 flex flex-wrap items-center gap-2 pt-0.5">
                              {itemsCount > 0 && (
                                <span className="app-badge inline-flex items-center gap-1 rounded-full px-2 py-1 text-[11px] font-medium">
                                  <Package size={11} /> {itemsCount} поз.
                                </span>
                              )}
                              {approvalsCount > 0 && (
                                <span className="app-badge inline-flex items-center gap-1 rounded-full px-2 py-1 text-[11px] font-medium">
                                  <Check size={11} /> {approvalsCount} соглас.
                                </span>
                              )}
                            </div>
                          )}
                        </div>

                        {canApproveThis ? (
                          <div className="mt-3 flex flex-wrap items-center gap-1.5">
                            <span className="ml-auto inline-flex items-center gap-2">
                              <button
                                type="button"
                                title="Одобрить"
                                onClick={() => openRequestActionDialog("approve", req.id)}
                                disabled={busyKey === `approve-${req.id}`}
                                className="app-feedback-success inline-flex items-center justify-center rounded-lg p-2 disabled:opacity-60"
                              >
                                <ThumbsUp size={18} />
                              </button>
                              <button
                                type="button"
                                title="Отклонить"
                                onClick={() => openRequestActionDialog("reject", req.id)}
                                disabled={busyKey === `reject-${req.id}`}
                                className="app-action-danger inline-flex items-center justify-center rounded-lg p-2 disabled:opacity-60"
                              >
                                <ThumbsDown size={18} />
                              </button>
                            </span>
                          </div>
                        ) : null}

                      </div>
                    </div>
                  </div>

                  {(expanded || commentsOpen) && (
                    <div className="mt-4 space-y-3 px-4 pb-4">
                      {expanded ? (
                        <ProcurementRequestDetailContent
                          request={resolvedDetail}
                          displayUserName={displayUserName}
                          footer={(
                            <ProcurementRequestActionButtons
                              request={req}
                              busyKey={busyKey}
                              canManage={canManage}
                              isAuthor={isAuthor}
                              isExecutor={isExecutor}
                              isFinal={isFinal}
                              showApprovalActions={false}
                              showSecondaryActions={false}
                              onSubmit={handleSubmit}
                              onEdit={openEdit}
                              onDelete={handleDelete}
                              onApprove={handleApprove}
                              onReject={handleReject}
                              onStart={handleStart}
                              onComplete={handleComplete}
                              onCancel={handleCancel}
                            />
                          )}
                        />
                      ) : null}

                      {commentsOpen ? (
                        <div className={expanded ? "app-surface rounded-xl p-3" : "app-surface-elevated rounded-xl p-3"}>
                          <div className="space-y-2">
                            {comments.length === 0 ? (
                              <p className="app-text-muted text-xs">Комментариев пока нет</p>
                            ) : (
                              comments.map((comment) => {
                                const canDeleteCommentThis = Boolean(comment.author?.id && (user?.id === comment.author.id || user?.auth?.is_staff || user?.auth?.is_superuser));
                                return (
                                  <div key={comment.id} className="app-surface-muted rounded-lg px-3 py-2 text-xs text-[var(--foreground)]">
                                    <div className="mb-1 flex items-center justify-between gap-2">
                                      <span className="font-medium">{displayUserName(comment.author)}</span>
                                      <div className="flex items-center gap-2">
                                        <span className="app-text-muted">{fmt(comment.created_at)}</span>
                                        {canDeleteCommentThis ? (
                                          <button type="button" onClick={() => void handleDeleteComment(req.id, comment.id)} className="app-action-danger rounded-md px-1.5 py-0.5">
                                            удалить
                                          </button>
                                        ) : null}
                                      </div>
                                    </div>
                                    <p className="app-text-wrap text-[var(--foreground)]">{comment.text}</p>
                                  </div>
                                );
                              })
                            )}
                          </div>
                          <div className="mt-2 flex items-center gap-2">
                            <input value={commentDrafts[req.id] || ""} onChange={(e) => setCommentDrafts((previous) => ({ ...previous, [req.id]: e.target.value }))} placeholder="Добавить комментарий" className="app-input flex-1 rounded-lg px-3 py-2 text-xs" />
                            <button type="button" onClick={() => void handleAddComment(req.id)} disabled={busyKey === `comment-${req.id}`} className="app-action-primary rounded-lg px-3 py-2 text-xs font-medium disabled:opacity-60">Отправить</button>
                          </div>
                        </div>
                      ) : null}
                    </div>
                  )}
                </article>
              );
            })}
          </div>

          {/* ── load more ── */}
          {nextPage && (
            <div className="mt-4 flex justify-center">
              <button type="button" onClick={handleLoadMore} disabled={loadingMore} className="app-action-secondary rounded-lg px-4 py-2 text-sm font-medium disabled:opacity-60">
                {loadingMore ? "Загружаем..." : "Загрузить ещё"}
              </button>
            </div>
          )}
            </>
          )}
        </section>
      )}

      <Modal
        isOpen={detailModalId !== null}
        onClose={closeDetailModal}
        title={selectedRequest?.title || "Карточка заявки"}
        size="lg"
        closeOnClickOutside
      >
        {detailModalLoading ? (
          <div className="py-12 text-center">
            <Loader2 size={24} className="mx-auto mb-3 animate-spin text-sky-500" />
            <p className="app-text-muted text-sm">Загружаем карточку заявки...</p>
          </div>
        ) : detailModalError ? (
          <div className="app-feedback-danger rounded-xl px-4 py-3 text-sm">
            {detailModalError}
          </div>
        ) : selectedRequest ? (
          <div className="space-y-4 pb-1">
            <div className="app-surface-muted rounded-xl px-4 py-4">
              <div className="min-w-0">
                <div className="flex flex-wrap items-center gap-2">
                  <span className={`app-status-pill ${statusMeta[String(selectedRequest.status || "").toLowerCase()]?.cls ?? defaultStatusMeta.cls}`}>
                    {statusMeta[String(selectedRequest.status || "").toLowerCase()]?.label ?? defaultStatusMeta.label}
                  </span>
                  <span className={`text-[11px] font-medium ${urgencyMeta[selectedRequest.urgency]?.cls ?? urgencyMeta.medium.cls}`}>
                    {(urgencyMeta[selectedRequest.urgency]?.label ?? urgencyMeta.medium.label)} срочность
                  </span>
                </div>
                <div className="app-text-muted mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs">
                  <span className="font-medium text-[var(--foreground)]">{getDeptName(selectedRequest)}</span>
                  <span>{fmt(selectedRequest.created_at)}</span>
                  {getRequestAmount(selectedRequest) ? (
                    <span className="font-medium text-[var(--foreground)]">{money(getRequestAmount(selectedRequest))}</span>
                  ) : null}
                </div>
                <div className="app-text-muted mt-2 grid grid-cols-1 gap-x-3 gap-y-1 text-xs sm:grid-cols-2">
                  <div className="min-w-0">
                    <span>Заявитель:</span>{" "}
                    <span className="font-medium text-[var(--foreground)]">
                      {displayUserName(selectedRequest.requestor, selectedRequest.requestor_name, selectedRequest.requestor_email)}
                    </span>
                  </div>
                  <div className="min-w-0">
                    <span>Исполнитель:</span>{" "}
                    <span className="font-medium text-[var(--foreground)]">
                      {selectedRequest.executor || selectedRequest.executor_name
                        ? displayUserName(selectedRequest.executor, selectedRequest.executor_name || undefined)
                        : "не назначен"}
                    </span>
                  </div>
                </div>
              </div>
            </div>

            {actionError ? (
              <div className="app-feedback-danger rounded-xl px-4 py-3 text-sm">
                {actionError}
              </div>
            ) : null}

            <ProcurementRequestDetailContent
              request={selectedRequest}
              displayUserName={displayUserName}
              footer={(
                <ProcurementRequestActionButtons
                  request={selectedRequest}
                  busyKey={busyKey}
                  canManage={canManage}
                  isAuthor={Boolean(resolveUserId(selectedRequest.requestor) && user?.id && resolveUserId(selectedRequest.requestor) === user.id)}
                  isExecutor={Boolean(resolveUserId(selectedRequest.executor) && user?.id && resolveUserId(selectedRequest.executor) === user.id)}
                  isFinal={isFinal}
                  onSubmit={handleSubmit}
                  onEdit={openEdit}
                  onDelete={(id) => openRequestActionDialog("delete", id)}
                  onApprove={(id) => openRequestActionDialog("approve", id)}
                  onReject={(id) => openRequestActionDialog("reject", id)}
                  onStart={handleStart}
                  onComplete={handleComplete}
                  onCancel={(id) => openRequestActionDialog("cancel", id)}
                />
              )}
            />

            <div className="app-surface rounded-xl p-4">
              <p className="app-card-caption">Комментарии</p>
              <div className="mt-3 space-y-2">
                {(commentsMap[selectedRequest.id] || []).length === 0 ? (
                  <p className="app-text-muted text-xs">Комментариев пока нет</p>
                ) : (
                  (commentsMap[selectedRequest.id] || []).map((comment) => {
                    const canDeleteCommentThis = Boolean(comment.author?.id && (user?.id === comment.author.id || user?.auth?.is_staff || user?.auth?.is_superuser));
                    return (
                      <div key={comment.id} className="app-surface-muted rounded-lg px-3 py-2 text-xs text-[var(--foreground)]">
                        <div className="mb-1 flex items-center justify-between gap-2">
                          <span className="font-medium">{displayUserName(comment.author)}</span>
                          <div className="flex items-center gap-2">
                            <span className="app-text-muted">{fmt(comment.created_at)}</span>
                            {canDeleteCommentThis ? (
                              <button type="button" onClick={() => void handleDeleteComment(selectedRequest.id, comment.id)} className="app-action-danger rounded-md px-1.5 py-0.5">
                                удалить
                              </button>
                            ) : null}
                          </div>
                        </div>
                        <p className="app-text-wrap text-[var(--foreground)]">{comment.text}</p>
                      </div>
                    );
                  })
                )}
              </div>
              <div className="mt-3 flex items-center gap-2">
                <input value={commentDrafts[selectedRequest.id] || ""} onChange={(e) => setCommentDrafts((previous) => ({ ...previous, [selectedRequest.id]: e.target.value }))} placeholder="Добавить комментарий" className="app-input flex-1 rounded-lg px-3 py-2 text-xs" />
                <button type="button" onClick={() => void handleAddComment(selectedRequest.id)} disabled={busyKey === `comment-${selectedRequest.id}`} className="app-action-primary rounded-lg px-3 py-2 text-xs font-medium disabled:opacity-60">Отправить</button>
              </div>
            </div>
          </div>
        ) : (
          <div className="app-surface-muted rounded-xl px-4 py-6 text-center">
            <p className="app-text-muted text-sm">Заявка не найдена.</p>
          </div>
        )}
      </Modal>

      <Modal
        isOpen={requestActionDialog !== null}
        onClose={closeRequestActionDialog}
        title={
          requestActionDialog?.kind === "approve" ? "Одобрить заявку"
          : requestActionDialog?.kind === "reject" ? "Отклонить заявку"
          : requestActionDialog?.kind === "cancel" ? "Отменить заявку"
          : "Удалить заявку"
        }
        size="md"
        closeOnClickOutside
      >
        <div className="space-y-4 pb-1">
          {selectedActionRequest ? (
            <div className="app-surface-muted rounded-xl px-4 py-3">
              <p className="text-sm font-semibold text-[var(--foreground)]">{selectedActionRequest.title || "Без названия"}</p>
              <p className="app-text-muted mt-1 text-xs">
                {getDeptName(selectedActionRequest)}{getRequestAmount(selectedActionRequest) ? ` • ${money(getRequestAmount(selectedActionRequest))}` : ""}
              </p>
            </div>
          ) : null}

          {actionError ? (
            <div className="app-feedback-danger rounded-xl px-4 py-3 text-sm">
              {actionError}
            </div>
          ) : null}

          {requestActionDialog?.kind === "delete" ? (
            <p className="app-text-muted text-sm">
              Удалить эту заявку? Действие доступно только для черновиков и будет необратимым.
            </p>
          ) : (
            <div className="space-y-2">
              <label className="app-card-caption">
                {requestActionDialog?.kind === "approve"
                  ? "Комментарий к одобрению"
                  : requestActionDialog?.kind === "reject"
                    ? "Комментарий к отклонению"
                    : "Причина отмены"}
              </label>
              <textarea
                value={requestActionComment}
                onChange={(event) => setRequestActionComment(event.target.value)}
                rows={4}
                placeholder={
                  requestActionDialog?.kind === "approve"
                    ? "Необязательно"
                    : requestActionDialog?.kind === "reject"
                      ? "Необязательно, но желательно"
                      : "Необязательно"
                }
                className="app-input app-text-wrap min-h-28 w-full rounded-xl px-3 py-2.5 text-sm"
              />
            </div>
          )}

          <div className="flex justify-end gap-2">
            <button type="button" onClick={closeRequestActionDialog} className="app-action-secondary rounded-xl px-4 py-2.5 text-sm font-medium">
              Отмена
            </button>
            <button
              type="button"
              onClick={() => void submitRequestActionDialog()}
              disabled={
                requestActionDialog?.kind === "approve" ? busyKey === `approve-${requestActionDialog.requestId}`
                : requestActionDialog?.kind === "reject" ? busyKey === `reject-${requestActionDialog.requestId}`
                : requestActionDialog?.kind === "cancel" ? busyKey === `cancel-${requestActionDialog.requestId}`
                : requestActionDialog?.kind === "delete" ? busyKey === `delete-${requestActionDialog.requestId}`
                : false
              }
              className={`rounded-xl px-4 py-2.5 text-sm font-medium disabled:opacity-60 ${
                requestActionDialog?.kind === "delete" || requestActionDialog?.kind === "reject"
                  ? "app-action-danger"
                  : "app-action-primary"
              }`}
            >
              {requestActionDialog?.kind === "approve"
                ? "Одобрить"
                : requestActionDialog?.kind === "reject"
                  ? "Отклонить"
                  : requestActionDialog?.kind === "cancel"
                    ? "Отменить заявку"
                    : "Удалить"}
            </button>
          </div>
        </div>
      </Modal>

      {/* ══════════ Create / Edit modal ══════════ */}
      <Modal isOpen={isModalOpen} onClose={closeModal} title={modalMode === "create" ? "Новая заявка на закупку" : "Редактировать заявку"} size="lg" footer={
            <div className="flex flex-wrap items-center justify-end gap-2">
              <button type="button" onClick={closeModal} className="app-action-secondary rounded-lg px-3 py-2 text-sm font-medium">Отмена</button>
              <button type="button" onClick={handleSave} disabled={busyKey === "save"} className="app-action-primary rounded-lg px-3 py-2 text-sm font-medium disabled:opacity-60">
                {modalMode === "create" ? "Создать черновик" : "Сохранить"}
              </button>
            </div>
      }>

            {actionError && <p className="mb-3 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{actionError}</p>}

            <div className="flex flex-col gap-3">
              {/* Название */}
              <div>
                <label className="app-text-muted mb-1 block text-xs font-medium">Название заявки *</label>
                <input
                  value={form.title}
                  onChange={(e) => setForm((f) => ({ ...f, title: e.target.value }))}
                  placeholder="Закупка офисной техники..."
                  className="app-input w-full rounded-lg px-3 py-2 text-sm"
                />
              </div>

              {/* Описание */}
              <div>
                <label className="app-text-muted mb-1 block text-xs font-medium">Описание и обоснование *</label>
                <textarea
                  value={form.description}
                  onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))}
                  placeholder="Обоснуйте необходимость закупки..."
                  rows={3}
                  className="app-input w-full rounded-lg px-3 py-2 text-sm"
                />
              </div>

              {/* Отдел + Срочность */}
              <div className="grid grid-cols-2 gap-3">
                <SearchableSelectSingle
                  label="Отдел *"
                  placeholder="Выберите отдел..."
                  items={departments.map((d) => ({ id: d.id, name: d.name }))}
                  selectedId={form.department}
                  onSelect={(id) => setForm((f) => ({ ...f, department: id }))}
                />
                <div>
                  <label className="app-text-muted mb-1 block text-xs font-medium">Срочность</label>
                  <select
                    value={form.urgency}
                    onChange={(e) => setForm((f) => ({ ...f, urgency: e.target.value as UrgencyLevel }))}
                    className="app-select w-full rounded-lg px-3 py-2 text-sm"
                  >
                    <option value="low">Низкая</option>
                    <option value="medium">Средняя</option>
                    <option value="high">Высокая</option>
                    <option value="critical">Критическая</option>
                  </select>
                </div>
              </div>

              {/* ── Items ── */}
              <div>
                <div className="mb-2 flex items-center justify-between">
                  <label className="app-text-muted text-xs font-medium">Позиции *</label>
                  <button type="button" onClick={addItemRow} className="app-link-accent inline-flex items-center gap-1 text-xs font-medium">
                    <Plus size={13} /> Добавить
                  </button>
                </div>

                <div className="space-y-3">
                  {form.items.map((it, idx) => (
                    <div key={idx} className="relative rounded-xl border border-gray-200 bg-gray-50 p-3">
                      {form.items.length > 1 && (
                        <button type="button" onClick={() => removeItemRow(idx)} className="absolute right-2 top-2 rounded p-0.5 text-gray-400 hover:bg-gray-200 hover:text-gray-600">
                          <X size={14} />
                        </button>
                      )}
                      <div className="grid gap-2">
                        <input
                          value={it.name}
                          onChange={(e) => updateItemRow(idx, { name: e.target.value })}
                          placeholder="Название позиции *"
                          className="app-input w-full rounded-lg px-3 py-2 text-sm"
                        />
                        <input
                          value={it.description}
                          onChange={(e) => updateItemRow(idx, { description: e.target.value })}
                          placeholder="Описание (необязательно)"
                          className="app-input w-full rounded-lg px-3 py-2 text-sm"
                        />
                        <div className="grid grid-cols-4 gap-2">
                          <input
                            type="number"
                            value={it.quantity}
                            onChange={(e) => updateItemRow(idx, { quantity: e.target.value })}
                            placeholder="Кол-во"
                            min={1}
                            className="app-input rounded-lg px-3 py-2 text-sm"
                          />
                          <input
                            value={it.unit}
                            onChange={(e) => updateItemRow(idx, { unit: e.target.value })}
                            placeholder="Ед."
                            className="app-input rounded-lg px-3 py-2 text-sm"
                          />
                          <input
                            type="number"
                            step="0.01"
                            value={it.estimated_unit_price}
                            onChange={(e) => updateItemRow(idx, { estimated_unit_price: e.target.value })}
                            placeholder="Цена/ед."
                            className="app-input rounded-lg px-3 py-2 text-sm"
                          />
                          <div className="flex items-center text-xs text-gray-500">
                            {it.quantity && it.estimated_unit_price ? money(Number(it.quantity) * Number(it.estimated_unit_price)) : "—"}
                          </div>
                        </div>
                        <input
                          value={it.supplier_info}
                          onChange={(e) => updateItemRow(idx, { supplier_info: e.target.value })}
                          placeholder="Информация о поставщике (необязательно)"
                          className="app-input w-full rounded-lg px-3 py-2 text-sm"
                        />
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
      </Modal>
    </AppShell>
  );
}
