"use client";

import { AppShell } from "../../components/AppShell";
import { useUser } from "@/contexts/UserContext";
import Link from "next/link";
import ProcurementStatsPanel from "@/components/procurement/ProcurementStatsPanel";
import ProcurementSuppliersPanel from "@/components/procurement/ProcurementSuppliersPanel";
import type { UrgencyLevel } from "@/types/api";
import {
  ArrowUpDown,
  Check,
  ChevronDown,
  CircleDot,
  ClipboardCheck,
  Filter,
  Loader2,
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
    error,
    expandedIds,
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
    updateItemRow,
    urgencyFilter,
    userLink,
    scope,
    scopeCounts,
  } = useProcurementPage(user);

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
              const isPending = st === "pending";
              const isApproved = st === "approved";
              const isInProgress = st === "in_progress";
              const expanded = expandedIds.has(req.id);
              const detail = detailsCache[req.id];
              const resolvedDetail = detail || req;
              const requestorName = displayUserName(req.requestor, req.requestor_name, req.requestor_email);
              const executorName = req.executor || req.executor_name ? displayUserName(req.executor, req.executor_name || undefined) : "";
              const requestorLink = userLink(req.requestor);
              const executorLink = userLink(req.executor);
              const itemsCount = resolvedDetail.items?.length ?? 0;
              const approvalsCount = resolvedDetail.approvals?.length ?? 0;

              return (
                <article key={req.id} className="app-surface-muted overflow-hidden rounded-xl transition hover:border-[var(--border-strong)]">
                  <div className="px-4 py-3">
                    <div className="flex items-start gap-3">
                      <button
                        type="button"
                        onClick={() => toggleExpand(req.id)}
                        aria-label={expanded ? "Свернуть детали" : "Развернуть детали"}
                        className="app-action-secondary mt-0.5 inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-lg"
                      >
                        <ChevronDown size={15} className={`transition ${expanded ? "rotate-180" : ""}`} />
                      </button>

                      <div className="min-w-0 flex-1">
                        <div className="flex items-start justify-between gap-3">
                          <div className="min-w-0 flex-1">
                            <div className="flex items-center gap-2">
                              <span className={`h-2 w-2 shrink-0 rounded-full ${st === "completed" ? "bg-teal-500" : st === "approved" ? "bg-emerald-500" : st === "pending" ? "bg-amber-500" : st === "in_progress" ? "bg-sky-500" : st === "rejected" ? "bg-rose-500" : "bg-slate-400"}`} />
                              <h3 className="truncate text-sm font-semibold text-[var(--foreground)]">{req.title || "Без названия"}</h3>
                            </div>
                            <div className="app-text-muted mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs">
                              <span className="font-medium text-[var(--foreground)]">{getDeptName(req)}</span>
                              <span>{fmt(req.created_at)}</span>
                              {getRequestAmount(req) && <span className="font-medium text-[var(--foreground)]">{money(getRequestAmount(req))}</span>}
                            </div>
                          </div>

                          <div className="flex shrink-0 flex-col items-end gap-2">
                            <span className={`app-status-pill shrink-0 ${sMeta.cls}`}>{sMeta.label}</span>
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
                      </div>
                    </div>
                  </div>

                  {expanded && (
                    <div className="mt-4 space-y-3 px-4 pb-4">
                      <div className="app-surface rounded-xl p-4">
                        <p className="text-sm font-semibold text-[var(--foreground)]">Описание</p>
                        <p className="app-text-wrap mt-2 whitespace-pre-line text-sm leading-6 text-[var(--foreground)]">{resolvedDetail.description || "—"}</p>
                        <div className="mt-3 grid gap-2 text-xs sm:grid-cols-3">
                          <div className="app-surface-muted rounded-lg px-3 py-2">
                            <p className="app-text-muted text-[11px] uppercase tracking-wide">Отправлена</p>
                            <p className="mt-1 font-medium text-[var(--foreground)]">{fmt(resolvedDetail.submitted_at) || "—"}</p>
                          </div>
                          <div className="app-surface-muted rounded-lg px-3 py-2">
                            <p className="app-text-muted text-[11px] uppercase tracking-wide">Взята в работу</p>
                            <p className="mt-1 font-medium text-[var(--foreground)]">{fmt(resolvedDetail.started_at) || "—"}</p>
                          </div>
                          <div className="app-surface-muted rounded-lg px-3 py-2">
                            <p className="app-text-muted text-[11px] uppercase tracking-wide">Завершена</p>
                            <p className="mt-1 font-medium text-[var(--foreground)]">{fmt(resolvedDetail.completed_at) || "—"}</p>
                          </div>
                        </div>
                        {resolvedDetail.actual_cost ? (
                          <div className="mt-3 inline-flex rounded-full app-badge-accent px-2.5 py-1 text-xs font-medium">
                            Фактическая сумма: {money(resolvedDetail.actual_cost)}
                          </div>
                        ) : null}
                      </div>

                      {detail?.items && detail.items.length > 0 && (
                        <div className="app-surface rounded-xl p-4">
                          <p className="mb-3 text-sm font-semibold text-[var(--foreground)]">Позиции</p>
                          <div className="space-y-2">
                            {detail.items.map((it, idx) => (
                              <div key={idx} className="app-surface-muted rounded-lg px-3 py-3 text-xs">
                                <div className="flex items-start justify-between gap-3">
                                  <div className="min-w-0 flex-1">
                                    <p className="app-text-wrap font-medium text-[var(--foreground)]">{it.name}</p>
                                    {it.description && <p className="app-text-wrap mt-1 text-[var(--muted-foreground)]">{it.description}</p>}
                                    {it.supplier_info && <p className="app-text-wrap mt-1 text-[var(--muted-foreground)]">Поставщик: {it.supplier_info}</p>}
                                  </div>
                                  <div className="text-right">
                                    <p className="font-medium text-[var(--foreground)]">{money(it.total_price)}</p>
                                    <p className="app-text-muted mt-1">{it.quantity} {it.unit}</p>
                                  </div>
                                </div>
                                <div className="app-text-muted mt-2 flex flex-wrap items-center gap-x-3 gap-y-1">
                                  <span>Цена/ед.: {money(it.estimated_unit_price)}</span>
                                </div>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}

                      {detail?.approvals && detail.approvals.length > 0 && (
                        <div className="app-surface rounded-xl p-4">
                          <p className="mb-3 text-sm font-semibold text-[var(--foreground)]">Согласования</p>
                          <div className="space-y-2">
                            {detail.approvals.map((a) => {
                              const aSt = String(a.status).toLowerCase();
                              const icon = aSt === "approved" ? <Check size={13} className="text-emerald-500" /> : aSt === "rejected" ? <X size={13} className="text-rose-500" /> : <CircleDot size={13} className="text-amber-500" />;
                              return (
                                <div key={a.id} className="app-surface-muted flex items-center gap-2 rounded-lg px-3 py-2 text-xs">
                                  {icon}
                                  <span className="font-medium text-[var(--foreground)]">{displayUserName(a.approver, a.approver_name)}</span>
                                  <span className="app-text-muted">({a.step_label || `Этап ${a.priority}`})</span>
                                  {a.comment && <span className="app-text-wrap app-text-muted ml-auto max-w-full italic">«{a.comment}»</span>}
                                </div>
                              );
                            })}
                          </div>
                        </div>
                      )}

                      <div className="flex flex-wrap items-center gap-1.5 pt-1">
                        {isDraft && isAuthor && (
                          <button type="button" onClick={() => handleSubmit(req.id)} disabled={busyKey === `submit-${req.id}`}
                            title="На согласование"
                            className="app-action-primary inline-flex h-9 w-9 items-center justify-center rounded-lg disabled:opacity-60">
                            <Send size={14} />
                          </button>
                        )}
                        {isDraft && isAuthor && (
                          <button type="button" onClick={() => openEdit(req)} title="Редактировать" className="app-action-secondary inline-flex h-9 w-9 items-center justify-center rounded-lg">
                            <Pencil size={14} />
                          </button>
                        )}
                        {isDraft && (isAuthor || canManage) && (
                          <button type="button" onClick={() => handleDelete(req.id)} disabled={busyKey === `delete-${req.id}`}
                            title="Удалить"
                            className="app-action-danger inline-flex h-9 w-9 items-center justify-center rounded-lg disabled:opacity-60">
                            <Trash2 size={14} />
                          </button>
                        )}
                        {isPending && !isAuthor && (
                          <>
                            <button type="button" onClick={() => handleApprove(req.id)} disabled={busyKey === `approve-${req.id}`}
                              title="Одобрить"
                              className="app-feedback-success inline-flex h-9 w-9 items-center justify-center rounded-lg disabled:opacity-60">
                              <ThumbsUp size={14} />
                            </button>
                            <button type="button" onClick={() => handleReject(req.id)} disabled={busyKey === `reject-${req.id}`}
                              title="Отклонить"
                              className="app-action-danger inline-flex h-9 w-9 items-center justify-center rounded-lg disabled:opacity-60">
                              <ThumbsDown size={14} />
                            </button>
                          </>
                        )}
                        {isApproved && !req.executor && (
                          <button type="button" onClick={() => handleStart(req.id)} disabled={busyKey === `start-${req.id}`}
                            title="Взять в работу"
                            className="app-action-primary inline-flex h-9 w-9 items-center justify-center rounded-lg disabled:opacity-60">
                            <Play size={14} />
                          </button>
                        )}
                        {isInProgress && isExecutor && (
                          <button type="button" onClick={() => handleComplete(req.id)} disabled={busyKey === `complete-${req.id}`}
                            title="Завершить"
                            className="app-action-primary inline-flex h-9 w-9 items-center justify-center rounded-lg disabled:opacity-60">
                            <ClipboardCheck size={14} />
                          </button>
                        )}
                        {isAuthor && !isFinal(st) && st !== "draft" && (
                          <button type="button" onClick={() => handleCancel(req.id)} disabled={busyKey === `cancel-${req.id}`}
                            title="Отменить"
                            className="app-action-secondary inline-flex h-9 w-9 items-center justify-center rounded-lg disabled:opacity-60">
                            <XCircle size={14} />
                          </button>
                        )}
                      </div>
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
