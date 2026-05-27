"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { AppShell } from "../../components/AppShell";
import { useUser } from "@/contexts/UserContext";
import Link from "next/link";
import { ProcurementRequestDetailContent } from "@/components/procurement/ProcurementRequestDetailContent";
import ProcurementStatsPanel from "@/components/procurement/ProcurementStatsPanel";
import ProcurementSuppliersPanel from "@/components/procurement/ProcurementSuppliersPanel";
import type { ProcurementRequest, ProcurementStatus, UrgencyLevel } from "@/types/api";
import {
  AlertTriangle,
  ArrowUpDown,
  CalendarDays,
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
import { CommentComposer, CommentDeleteButton } from "@/components/shared/CommentControls";
import { SearchableSelectSingle } from "@/components/shared/SearchableSelect";
import { formatDate, formatMoney } from "@/lib/shared";
import { useProcurementPage } from "@/hooks/useProcurementPage";
import { Modal } from "@/components/ui";

/* ══════════════════════════════════════════════════════
   Constants & helpers
   ══════════════════════════════════════════════════════ */

const statusMeta: Record<ProcurementStatus, { label: string; cls: string }> = {
  draft:       { label: "Черновик",        cls: "app-badge" },
  waiting:     { label: "Ожидает",         cls: "app-feedback-warning" },
  pending:     { label: "На согласовании", cls: "app-feedback-warning" },
  approved:    { label: "Одобрено",        cls: "app-feedback-success" },
  in_progress: { label: "В работе",        cls: "app-selected" },
  completed:   { label: "Завершено",       cls: "app-selected" },
  rejected:    { label: "Отклонено",       cls: "app-feedback-danger" },
  cancelled:   { label: "Отменено",        cls: "app-badge" },
};
const statusOptions = Object.entries(statusMeta) as [ProcurementStatus, { label: string; cls: string }][];
const defaultStatusMeta = { label: "—", cls: "app-badge" };
const getStatusMeta = (status?: string | null) => (
  statusMeta[String(status || "").toLowerCase() as ProcurementStatus] ?? defaultStatusMeta
);

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

type ScopeTab = "all" | "mine" | "department" | "processing_department" | "pending_approvals" | "my_work" | "available";
const scopeTabs: { value: ScopeTab; label: string }[] = [
  { value: "all",               label: "Все" },
  { value: "mine",              label: "Мои" },
  { value: "department",        label: "Отдел-заказчик" },
  { value: "processing_department", label: "Отдел-исполнитель" },
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
  showLabels = false,
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
  showLabels?: boolean;
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
  const canStartWork = Boolean(request.can_current_user_start_work);
  const isInProgress = status === "in_progress";
  const canApproveThis = Boolean(request.can_current_user_approve);
  const canSubmitForApproval = Boolean(request.can_current_user_submit_for_approval);
  const buttonClass = (variantClass: string) =>
    `${variantClass} inline-flex h-9 items-center justify-center rounded-lg disabled:opacity-60 ${
      showLabels ? "gap-1.5 px-3 text-xs font-medium" : "w-9"
    }`;
  const label = (text: string) => (showLabels ? <span>{text}</span> : null);

  return (
    <div className="flex flex-wrap items-center gap-1.5 pt-1">
      {canSubmitForApproval ? (
        <button
          type="button"
          onClick={() => onSubmit(request.id)}
          disabled={busyKey === `submit-${request.id}`}
          title="Отправить на согласование"
          className={buttonClass("app-action-primary")}
        >
          <Send size={14} />
          {label("Отправить на согласование")}
        </button>
      ) : null}
      {showSecondaryActions && isDraft && isAuthor ? (
        <button
          type="button"
          onClick={() => onEdit(request)}
          title="Редактировать"
          className={buttonClass("app-action-secondary")}
        >
          <Pencil size={14} />
          {label("Изменить")}
        </button>
      ) : null}
      {showSecondaryActions && isDraft && (isAuthor || canManage) ? (
        <button
          type="button"
          onClick={() => onDelete(request.id)}
          disabled={busyKey === `delete-${request.id}`}
          title="Удалить"
          className={buttonClass("app-action-danger")}
        >
          <Trash2 size={14} />
          {label("Удалить")}
        </button>
      ) : null}
      {showApprovalActions && isPending && canApproveThis ? (
        <>
          <button
            type="button"
            onClick={() => onApprove(request.id)}
            disabled={busyKey === `approve-${request.id}`}
            title="Одобрить"
            className={buttonClass("app-feedback-success")}
          >
            <ThumbsUp size={14} />
            {label("Одобрить")}
          </button>
          <button
            type="button"
            onClick={() => onReject(request.id)}
            disabled={busyKey === `reject-${request.id}`}
            title="Отклонить"
            className={buttonClass("app-action-danger")}
          >
            <ThumbsDown size={14} />
            {label("Отклонить")}
          </button>
        </>
      ) : null}
      {canStartWork ? (
        <button
          type="button"
          onClick={() => onStart(request.id)}
          disabled={busyKey === `start-${request.id}`}
          title="Взять в работу"
          className={buttonClass("app-action-primary")}
        >
          <Play size={14} />
          {label("Взять в работу")}
        </button>
      ) : null}
      {isInProgress && isExecutor ? (
        <button
          type="button"
          onClick={() => onComplete(request.id)}
          disabled={busyKey === `complete-${request.id}`}
          title="Закрыть заявку"
          className={buttonClass("app-action-primary")}
        >
          <ClipboardCheck size={14} />
          {label("Закрыть заявку")}
        </button>
      ) : null}
      {showSecondaryActions && isAuthor && !isFinal(status) && status !== "draft" ? (
        <button
          type="button"
          onClick={() => onCancel(request.id)}
          disabled={busyKey === `cancel-${request.id}`}
          title="Отменить"
          className={buttonClass("app-action-secondary")}
        >
          <XCircle size={14} />
          {label("Отменить")}
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
    defaultProcessingDepartmentId,
    detailsCache,
    displayUserName,
    ensureRequestDetail,
    ensureCommentsLoaded,
    error,
    commentsMap,
    commentDrafts,
    setCommentDrafts,
    expandedItemComments,
    itemCommentsMap,
    itemCommentDrafts,
    setItemCommentDrafts,
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
    handleMarkAllReceived,
    handleReportItemIssue,
    handleUpdateItem,
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
    handleAddItemComment,
    handleDeleteItemComment,
    toggleItemComments,
  } = useProcurementPage(user);

  const toggleStatusFilter = useCallback((status: ProcurementStatus) => {
    setStatusFilter((current) => (
      current.includes(status)
        ? current.filter((item) => item !== status)
        : [...current, status]
    ));
  }, [setStatusFilter]);

  const [detailModalId, setDetailModalId] = useState<number | null>(null);
  const [detailModalLoading, setDetailModalLoading] = useState(false);
  const [detailModalError, setDetailModalError] = useState<string | null>(null);
  const procurementMenuRef = useRef<HTMLDivElement | null>(null);
  const statusFilterRef = useRef<HTMLDivElement | null>(null);
  const [procurementMenuOpenId, setProcurementMenuOpenId] = useState<number | null>(null);
  const [statusFilterOpen, setStatusFilterOpen] = useState(false);
  const [requestActionDialog, setRequestActionDialog] = useState<{ kind: RequestActionDialogKind; requestId: number } | null>(null);
  const [requestActionComment, setRequestActionComment] = useState("");

  const statusFilterSummary = useMemo(() => {
    if (statusFilter.length === 0) return "Все статусы";

    const labels = statusFilter
      .map((status) => statusMeta[status]?.label)
      .filter(Boolean);

    if (labels.length <= 2) return labels.join(", ");
    return `Выбрано статусов: ${labels.length}`;
  }, [statusFilter]);

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

  useEffect(() => {
    if (!statusFilterOpen) return;

    const handlePointerDown = (event: MouseEvent) => {
      if (statusFilterRef.current && !statusFilterRef.current.contains(event.target as Node)) {
        setStatusFilterOpen(false);
      }
    };

    const handleEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setStatusFilterOpen(false);
      }
    };

    document.addEventListener("mousedown", handlePointerDown);
    document.addEventListener("keydown", handleEscape);

    return () => {
      document.removeEventListener("mousedown", handlePointerDown);
      document.removeEventListener("keydown", handleEscape);
    };
  }, [statusFilterOpen]);

  useEffect(() => {
    if (!filtersOpen) {
      setStatusFilterOpen(false);
    }
  }, [filtersOpen]);

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
              <div ref={statusFilterRef} className="relative">
                <button
                  type="button"
                  onClick={() => setStatusFilterOpen((current) => !current)}
                  aria-expanded={statusFilterOpen}
                  className="app-select flex w-full items-center justify-between gap-3 rounded-lg px-3 py-2 text-left text-sm"
                >
                  <span className={statusFilter.length > 0 ? "truncate text-[var(--foreground)]" : "app-text-muted truncate"}>
                    {statusFilterSummary}
                  </span>
                  <span className="flex shrink-0 items-center gap-2">
                    {statusFilter.length > 0 ? (
                      <span className="app-badge rounded-full px-1.5 py-0.5 text-[10px] font-bold">
                        {statusFilter.length}
                      </span>
                    ) : null}
                    <ChevronDown size={14} className={`app-text-muted transition ${statusFilterOpen ? "rotate-180" : ""}`} />
                  </span>
                </button>
                {statusFilterOpen ? (
                  <div className="app-menu absolute inset-x-0 z-50 mt-1 overflow-hidden rounded-lg">
                    <div className="app-divider flex items-center justify-between gap-2 border-b px-3 py-2">
                      <span className="app-text-muted text-xs font-semibold uppercase">Статусы</span>
                      {statusFilter.length > 0 ? (
                        <button
                          type="button"
                          onClick={() => setStatusFilter([])}
                          className="app-link-accent text-xs font-medium"
                        >
                          Сбросить
                        </button>
                      ) : null}
                    </div>
                    <div className="max-h-64 overflow-y-auto p-1">
                      {statusOptions.map(([key, meta]) => (
                        <label
                          key={key}
                          className={`flex cursor-pointer items-center gap-2 rounded-md px-2 py-2 text-sm transition ${
                            statusFilter.includes(key)
                              ? "app-selected app-accent-text font-medium"
                              : "hover:bg-[var(--surface-secondary)]"
                          }`}
                        >
                          <input
                            type="checkbox"
                            checked={statusFilter.includes(key)}
                            onChange={() => toggleStatusFilter(key)}
                            className="h-4 w-4 rounded border-[var(--border-strong)] accent-[var(--accent-primary)]"
                          />
                          <span className="min-w-0 flex-1 truncate">{meta.label}</span>
                        </label>
                      ))}
                    </div>
                  </div>
                ) : null}
              </div>
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
                <button type="button" onClick={() => { setStatusFilter([]); setUrgencyFilter(""); setDepartmentFilter(""); setPeriodFilter(""); }} className="app-action-secondary rounded-lg px-3 py-2 text-sm font-medium transition">
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
              const sMeta = getStatusMeta(st);
              const urg = urgencyMeta[req.urgency] ?? urgencyMeta.medium;
              const isAuthor = Boolean(resolveUserId(req.requestor) && user?.id && resolveUserId(req.requestor) === user.id);
              const isExecutor = Boolean(resolveUserId(req.executor) && user?.id && resolveUserId(req.executor) === user.id);
              const isEditableStatus = (st === "draft" || st === "waiting") && !req.executor;
              const detail = detailsCache[req.id];
              const resolvedDetail = detail || req;
              const canApproveThis = Boolean((resolvedDetail.can_current_user_approve ?? req.can_current_user_approve));
              const canEditThis = Boolean(isEditableStatus && isAuthor);
              const canDeleteThis = Boolean(isEditableStatus && (isAuthor || canManage));
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
              const fulfillmentStatusDisplay = resolvedDetail.fulfillment_status_display ?? req.fulfillment_status_display;
              const itemsCount = resolvedDetail.items?.length ?? resolvedDetail.items_count ?? req.items_count ?? 0;
              const detailItems = resolvedDetail.items || req.items || [];
              const itemsTotalCount = resolvedDetail.items_total_count ?? req.items_total_count ?? itemsCount;
              const itemsReceivedCount = resolvedDetail.items_received_count ?? req.items_received_count ?? detailItems.filter((item) => item.execution_status === "received").length;
              const itemsProblemCount = resolvedDetail.items_problem_count ?? req.items_problem_count ?? detailItems.filter((item) => ["rejected", "completed_with_issue", "edited", "defective"].includes(String(item.execution_status || ""))).length;
              const itemsPendingCount = resolvedDetail.items_pending_count ?? req.items_pending_count ?? detailItems.filter((item) => !item.execution_status || item.execution_status === "pending").length;
              const totalRequestedQuantity = resolvedDetail.total_requested_quantity ?? req.total_requested_quantity ?? detailItems.reduce((sum, item) => sum + Number(item.quantity || 0), 0);
              const totalOrderedQuantity = resolvedDetail.total_ordered_quantity ?? req.total_ordered_quantity ?? detailItems.reduce((sum, item) => sum + Number(item.ordered_quantity || 0), 0);
              const totalReceivedQuantity = resolvedDetail.total_received_quantity ?? req.total_received_quantity ?? detailItems.reduce((sum, item) => sum + Number(item.received_quantity || 0), 0);
              const nextExpectedDeliveryDate = resolvedDetail.next_expected_delivery_date ?? req.next_expected_delivery_date ?? null;
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
                              <span className={`h-2 w-2 shrink-0 rounded-full ${st === "completed" ? "bg-teal-500" : st === "approved" ? "bg-emerald-500" : st === "pending" || st === "waiting" ? "bg-amber-500" : st === "in_progress" ? "bg-sky-500" : st === "rejected" ? "bg-rose-500" : "bg-slate-400"}`} />
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
                              <span>Отдел-заказчик: <span className="font-medium text-[var(--foreground)]">{getDeptName(req)}</span></span>
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
                          {(fulfillmentStatusDisplay || itemsTotalCount > 0 || approvalsCount > 0 || nextExpectedDeliveryDate) && (
                            <div className="col-span-2 flex flex-wrap items-center gap-2 pt-0.5">
                              {fulfillmentStatusDisplay ? (
                                <span className="app-badge inline-flex items-center gap-1 rounded-full px-2 py-1 text-[11px] font-medium">
                                  {fulfillmentStatusDisplay}
                                </span>
                              ) : null}
                              {nextExpectedDeliveryDate ? (
                                <span className="app-badge inline-flex items-center gap-1 rounded-full px-2 py-1 text-[11px] font-medium">
                                  <CalendarDays size={11} /> {fmt(nextExpectedDeliveryDate)}
                                </span>
                              ) : null}
                              {itemsTotalCount > 0 && (
                                <span className="app-badge inline-flex items-center gap-1 rounded-full px-2 py-1 text-[11px] font-medium">
                                  <Package size={11} /> {itemsTotalCount} поз.
                                </span>
                              )}
                              {itemsTotalCount > 0 && (
                                <span className="app-badge inline-flex items-center gap-1 rounded-full px-2 py-1 text-[11px] font-medium">
                                  <Check size={11} /> Получено {itemsReceivedCount}/{itemsTotalCount} поз.
                                </span>
                              )}
                              {itemsProblemCount > 0 && (
                                <span className="app-feedback-warning inline-flex items-center gap-1 rounded-full px-2 py-1 text-[11px] font-medium">
                                  <AlertTriangle size={11} /> Проблемы {itemsProblemCount}/{itemsTotalCount} поз.
                                </span>
                              )}
                              {totalRequestedQuantity > 0 && (
                                <span className="app-badge inline-flex items-center gap-1 rounded-full px-2 py-1 text-[11px] font-medium">
                                  Заказано {totalOrderedQuantity}/{totalRequestedQuantity} шт.
                                </span>
                              )}
                              {totalRequestedQuantity > 0 && (
                                <span className="app-badge inline-flex items-center gap-1 rounded-full px-2 py-1 text-[11px] font-medium">
                                  Получено {totalReceivedQuantity}/{totalRequestedQuantity} шт.
                                </span>
                              )}
                              {itemsPendingCount > 0 && (
                                <span className="app-badge inline-flex items-center gap-1 rounded-full px-2 py-1 text-[11px] font-medium">
                                  Не обработано {itemsPendingCount}
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
                                          <CommentDeleteButton
                                            onClick={() => handleDeleteComment(req.id, comment.id)}
                                          />
                                        ) : null}
                                      </div>
                                    </div>
                                    <p className="app-text-wrap text-[var(--foreground)]">{comment.text}</p>
                                  </div>
                                );
                              })
                            )}
                          </div>
                          <div className="mt-2">
                            <CommentComposer
                              value={commentDrafts[req.id] || ""}
                              onChange={(value) => setCommentDrafts((previous) => ({ ...previous, [req.id]: value }))}
                              onSubmit={() => handleAddComment(req.id)}
                              disabled={busyKey === `comment-${req.id}`}
                            />
                          </div>
                        </div>
                      ) : null}

                      {expanded ? (
                        <ProcurementRequestDetailContent
                          currentUserId={user?.id}
                          request={resolvedDetail}
                          displayUserName={displayUserName}
                          canProcessItems={Boolean(resolvedDetail.can_current_user_process_items)}
                          busyKey={busyKey}
                          canDeleteAnyComment={Boolean(user?.auth?.is_staff || user?.auth?.is_superuser)}
                          onUpdateItem={handleUpdateItem}
                          onReportItemIssue={handleReportItemIssue}
                          onMarkAllReceived={handleMarkAllReceived}
                          itemCommentsMap={itemCommentsMap}
                          itemCommentDrafts={itemCommentDrafts}
                          expandedItemComments={expandedItemComments}
                          onToggleItemComments={toggleItemComments}
                          onItemCommentDraftChange={(itemId, value) => setItemCommentDrafts((previous) => ({ ...previous, [itemId]: value }))}
                          onAddItemComment={handleAddItemComment}
                          onDeleteItemComment={handleDeleteItemComment}
                          footer={(
                            <ProcurementRequestActionButtons
                              request={resolvedDetail}
                              busyKey={busyKey}
                              canManage={canManage}
                              isAuthor={isAuthor}
                              isExecutor={isExecutor}
                              isFinal={isFinal}
                              showSecondaryActions={false}
                              showLabels
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
                  <span className={`app-status-pill ${getStatusMeta(selectedRequest.status).cls}`}>
                    {getStatusMeta(selectedRequest.status).label}
                  </span>
                  <span className={`text-[11px] font-medium ${urgencyMeta[selectedRequest.urgency]?.cls ?? urgencyMeta.medium.cls}`}>
                    {(urgencyMeta[selectedRequest.urgency]?.label ?? urgencyMeta.medium.label)} срочность
                  </span>
                </div>
                <div className="app-text-muted mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs">
                  <span>Отдел-заказчик: <span className="font-medium text-[var(--foreground)]">{getDeptName(selectedRequest)}</span></span>
                  {selectedRequest.processing_department_name ? (
                    <span>Отдел-исполнитель: <span className="font-medium text-[var(--foreground)]">{selectedRequest.processing_department_name}</span></span>
                  ) : null}
                  <span>{fmt(selectedRequest.created_at)}</span>
                  {getRequestAmount(selectedRequest) ? (
                    <span className="font-medium text-[var(--foreground)]">{money(getRequestAmount(selectedRequest))}</span>
                  ) : null}
                  {selectedRequest.fulfillment_status_display ? (
                    <span className="app-badge rounded-full px-2 py-0.5 text-[11px] font-medium">
                      {selectedRequest.fulfillment_status_display}
                    </span>
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
              currentUserId={user?.id}
              request={selectedRequest}
              displayUserName={displayUserName}
              canProcessItems={Boolean(selectedRequest.can_current_user_process_items)}
              busyKey={busyKey}
              canDeleteAnyComment={Boolean(user?.auth?.is_staff || user?.auth?.is_superuser)}
              onUpdateItem={handleUpdateItem}
              onReportItemIssue={handleReportItemIssue}
              onMarkAllReceived={handleMarkAllReceived}
              itemCommentsMap={itemCommentsMap}
              itemCommentDrafts={itemCommentDrafts}
              expandedItemComments={expandedItemComments}
              onToggleItemComments={toggleItemComments}
              onItemCommentDraftChange={(itemId, value) => setItemCommentDrafts((previous) => ({ ...previous, [itemId]: value }))}
              onAddItemComment={handleAddItemComment}
              onDeleteItemComment={handleDeleteItemComment}
              footer={(
                <ProcurementRequestActionButtons
                  request={selectedRequest}
                  busyKey={busyKey}
                  canManage={canManage}
                  isAuthor={Boolean(resolveUserId(selectedRequest.requestor) && user?.id && resolveUserId(selectedRequest.requestor) === user.id)}
                  isExecutor={Boolean(resolveUserId(selectedRequest.executor) && user?.id && resolveUserId(selectedRequest.executor) === user.id)}
                  isFinal={isFinal}
                  showLabels
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
                              <CommentDeleteButton
                                onClick={() => handleDeleteComment(selectedRequest.id, comment.id)}
                              />
                            ) : null}
                          </div>
                        </div>
                        <p className="app-text-wrap text-[var(--foreground)]">{comment.text}</p>
                      </div>
                    );
                  })
                )}
              </div>
              <div className="mt-3">
                <CommentComposer
                  value={commentDrafts[selectedRequest.id] || ""}
                  onChange={(value) => setCommentDrafts((previous) => ({ ...previous, [selectedRequest.id]: value }))}
                  onSubmit={() => handleAddComment(selectedRequest.id)}
                  disabled={busyKey === `comment-${selectedRequest.id}`}
                />
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
              <button
                type="button"
                onClick={handleSave}
                disabled={busyKey === "save" || busyKey === "save-submit"}
                className="app-action-primary rounded-lg px-3 py-2 text-sm font-medium disabled:opacity-60"
              >
                {modalMode === "create" ? "Создать заявку" : "Сохранить"}
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
                <label className="app-text-muted mb-1 block text-xs font-medium">
                  Описание и обоснование (необязательно)
                </label>
                <textarea
                  value={form.description}
                  onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))}
                  placeholder="Можно оставить пустым и описать детали в позициях..."
                  rows={3}
                  className="app-input w-full rounded-lg px-3 py-2 text-sm"
                />
              </div>

              {/* Отдел + Срочность */}
              <div className="grid grid-cols-2 gap-3">
                <SearchableSelectSingle
                  label="Отдел-заказчик *"
                  placeholder="Выберите отдел, для которого нужна закупка..."
                  items={departments.map((d) => ({ id: d.id, name: d.name }))}
                  selectedId={form.department}
                  onSelect={(id) => setForm((f) => ({ ...f, department: id }))}
                  disabled={modalMode === "edit"}
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

              <SearchableSelectSingle
                label="Отдел-исполнитель *"
                placeholder="Выберите отдел, который обработает заявку..."
                items={departments.map((d) => ({ id: d.id, name: d.name }))}
                selectedId={form.processing_department}
                onSelect={(id) => setForm((f) => ({ ...f, processing_department: id }))}
                disabled={Boolean(defaultProcessingDepartmentId)}
              />

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
                      <div key={idx} className="app-surface-muted rounded-xl p-3">
                        <div className="grid gap-2">
                          <div className="flex items-center gap-2">
                            <input
                              value={it.name}
                              onChange={(e) => updateItemRow(idx, { name: e.target.value })}
                              placeholder="Название позиции *"
                              className="app-input min-w-0 flex-1 rounded-lg px-3 py-2 text-sm"
                            />
                            {form.items.length > 1 && (
                              <button
                                type="button"
                                onClick={() => removeItemRow(idx)}
                                className="app-action-secondary inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-lg"
                                title="Удалить позицию"
                              >
                                <X size={14} />
                              </button>
                            )}
                          </div>
                          <textarea
                            value={it.initial_comment}
                            onChange={(e) => updateItemRow(idx, { initial_comment: e.target.value })}
                            placeholder="Комментарий к позиции"
                            rows={2}
                            className="app-input app-text-wrap w-full rounded-lg px-3 py-2 text-sm"
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
                              placeholder="Цена/ед. (необяз.)"
                              className="app-input rounded-lg px-3 py-2 text-sm"
                            />
                            <div className="flex items-center text-xs text-gray-500">
                              {it.quantity && it.estimated_unit_price ? money(Number(it.quantity) * Number(it.estimated_unit_price)) : "—"}
                            </div>
                          </div>
                          <div className="space-y-2">
                            <div className="flex items-center justify-between gap-2">
                              <span className="app-text-muted text-xs font-medium">Ссылки</span>
                              <button
                                type="button"
                                onClick={() => updateItemRow(idx, { links: ["", ...it.links] })}
                                className="app-link-accent inline-flex items-center gap-1 text-xs font-medium"
                              >
                                <Plus size={12} /> Добавить ссылку
                              </button>
                            </div>
                            {it.links.map((link, linkIndex) => (
                              <div key={linkIndex} className="flex items-center gap-2">
                                <input
                                  value={link}
                                  onChange={(e) => updateItemRow(idx, {
                                    links: it.links.map((currentLink, currentIndex) => (
                                      currentIndex === linkIndex ? e.target.value : currentLink
                                    )),
                                  })}
                                  placeholder="https://example.ru/item"
                                  className="app-input min-w-0 flex-1 rounded-lg px-3 py-2 text-sm"
                                />
                                {it.links.length > 1 ? (
                                  <button
                                    type="button"
                                    onClick={() => updateItemRow(idx, {
                                      links: it.links.filter((_, currentIndex) => currentIndex !== linkIndex),
                                    })}
                                    className="app-action-secondary inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-lg"
                                    title="Удалить ссылку"
                                  >
                                    <X size={13} />
                                  </button>
                                ) : null}
                              </div>
                            ))}
                          </div>
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
