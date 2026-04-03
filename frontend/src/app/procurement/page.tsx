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
  draft:       { label: "Черновик",        cls: "bg-slate-100 text-slate-700 ring-slate-200" },
  pending:     { label: "На согласовании", cls: "bg-amber-50 text-amber-700 ring-amber-100" },
  approved:    { label: "Одобрено",        cls: "bg-emerald-50 text-emerald-700 ring-emerald-100" },
  in_progress: { label: "В работе",        cls: "bg-sky-50 text-sky-700 ring-sky-100" },
  completed:   { label: "Завершено",       cls: "bg-teal-50 text-teal-700 ring-teal-100" },
  rejected:    { label: "Отклонено",       cls: "bg-rose-50 text-rose-700 ring-rose-100" },
  cancelled:   { label: "Отменено",        cls: "bg-gray-100 text-gray-600 ring-gray-200" },
};
const defaultStatusMeta = { label: "—", cls: "bg-gray-50 text-gray-700 ring-gray-200" };

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
  } = useProcurementPage(user);

  /* ══════════════════════════════════════════════════════
     RENDER
     ══════════════════════════════════════════════════════ */

  return (
    <AppShell>
      {loading ? (
        <div className="rounded-2xl bg-white p-8 text-center shadow-sm ring-1 ring-gray-100">
          <Loader2 size={28} className="mx-auto mb-3 animate-spin text-sky-500" />
          <p className="text-sm text-gray-500">Загрузка заявок на закупку...</p>
        </div>
      ) : error ? (
        <div className="rounded-2xl bg-red-50 p-6 text-center">
          <p className="text-sm text-red-800">{error}</p>
        </div>
      ) : (
        <section className="rounded-2xl bg-white p-4 shadow-sm ring-1 ring-gray-100">
          {/* ── header ── */}
          <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
            <div>
              <p className="text-sm font-semibold uppercase tracking-wide text-gray-500">Закупки</p>
              <div className="mt-2 flex flex-wrap gap-2">
                <button type="button" onClick={() => setActiveSection("requests")} className={`rounded-full px-3 py-1.5 text-xs font-medium transition ${activeSection === "requests" ? "bg-sky-600 text-white" : "bg-gray-100 text-gray-700 hover:bg-gray-200"}`}>
                  Заявки
                </button>
                <button type="button" onClick={() => setActiveSection("stats")} className={`rounded-full px-3 py-1.5 text-xs font-medium transition ${activeSection === "stats" ? "bg-sky-600 text-white" : "bg-gray-100 text-gray-700 hover:bg-gray-200"}`}>
                  Статистика
                </button>
                <button type="button" onClick={() => setActiveSection("suppliers")} className={`rounded-full px-3 py-1.5 text-xs font-medium transition ${activeSection === "suppliers" ? "bg-sky-600 text-white" : "bg-gray-100 text-gray-700 hover:bg-gray-200"}`}>
                  Поставщики
                </button>
              </div>
            </div>
            {activeSection === "requests" && (
              <button type="button" onClick={openCreate} className="inline-flex items-center gap-1 rounded-lg bg-sky-500 px-3 py-2 text-sm font-medium text-white transition hover:bg-sky-600">
                <Plus size={14} /> Создать заявку
              </button>
            )}
          </div>

          {/* ── alerts ── */}
          {actionError && <p className="mb-3 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{actionError}</p>}
          {actionSuccess && <p className="mb-3 rounded-lg bg-emerald-50 px-3 py-2 text-sm text-emerald-700">{actionSuccess}</p>}

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
                className="w-full rounded-lg border border-gray-200 bg-gray-50 py-2.5 pl-9 pr-3 text-sm text-gray-800 transition focus:border-sky-500 focus:bg-white focus:outline-none focus:ring-2 focus:ring-sky-100"
              />
            </div>
            <button
              type="button"
              title="Фильтры"
              onClick={() => setFiltersOpen((v) => !v)}
              className={`relative inline-flex items-center justify-center rounded-lg border p-2.5 transition ${filtersOpen ? "border-sky-400 bg-sky-50 text-sky-600" : "border-gray-200 bg-gray-50 text-gray-500 hover:bg-gray-100"}`}
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
                className="w-full appearance-none rounded-lg border border-gray-200 bg-gray-50 py-2.5 pl-9 pr-8 text-xs font-medium text-gray-700 transition hover:bg-gray-100 focus:border-sky-400 focus:bg-white focus:outline-none focus:ring-2 focus:ring-sky-100"
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
                    ? "bg-sky-600 text-white"
                    : "bg-gray-100 text-gray-700 hover:bg-gray-200"
                }`}
              >
                {tab.label}
              </button>
            ))}
          </div>

          {/* ── filters panel ── */}
          {filtersOpen && (
            <div className="mb-3 flex flex-col gap-2 rounded-xl border border-gray-200 bg-gray-50 p-3">
              <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)} className="rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm text-gray-800">
                <option value="">Все статусы</option>
                {Object.entries(statusMeta).map(([k, v]) => <option key={k} value={k}>{v.label}</option>)}
              </select>
              <select value={urgencyFilter} onChange={(e) => setUrgencyFilter(e.target.value)} className="rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm text-gray-800">
                <option value="">Все уровни срочности</option>
                {Object.entries(urgencyMeta).map(([k, v]) => <option key={k} value={k}>{v.label}</option>)}
              </select>
              <select value={departmentFilter} onChange={(e) => setDepartmentFilter(e.target.value)} className="rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm text-gray-800">
                <option value="">Все отделы</option>
                {departments.map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}
              </select>
              <select value={periodFilter} onChange={(e) => setPeriodFilter(e.target.value)} className="rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm text-gray-800">
                {periodOptions.map((option) => <option key={option.value || "all"} value={option.value}>{option.label}</option>)}
              </select>
              {activeFilterCount > 0 && (
                <button type="button" onClick={() => { setStatusFilter(""); setUrgencyFilter(""); setDepartmentFilter(""); setPeriodFilter(""); }} className="rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm font-medium text-gray-600 hover:bg-gray-100 transition">
                  Очистить фильтры
                </button>
              )}
            </div>
          )}

          {/* ══════════ Request cards ══════════ */}
          <div className="space-y-3">
            {filteredRequests.length === 0 ? (
              <div className="rounded-xl bg-gray-50 p-8 text-center">
                <ShoppingCart size={22} className="mx-auto mb-2 text-gray-400" />
                <p className="text-sm text-gray-500">Заявок на закупку не найдено</p>
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
                <article key={req.id} className="overflow-hidden rounded-xl border border-gray-200 bg-white transition hover:border-gray-300">
                  <div className="px-4 py-3 xl:hidden">
                    <div className="flex items-start gap-3">
                      <button
                        type="button"
                        onClick={() => toggleExpand(req.id)}
                        aria-label={expanded ? "Свернуть детали" : "Развернуть детали"}
                        className="mt-0.5 inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border border-gray-200 bg-gray-50 text-gray-500 transition hover:bg-gray-100"
                      >
                        <ChevronDown size={15} className={`transition ${expanded ? "rotate-180" : ""}`} />
                      </button>

                      <div className="min-w-0 flex-1">
                        <div className="flex items-start justify-between gap-3">
                          <div className="min-w-0 flex-1">
                            <div className="flex items-center gap-2">
                              <span className={`h-2 w-2 shrink-0 rounded-full ${st === "completed" ? "bg-teal-500" : st === "approved" ? "bg-emerald-500" : st === "pending" ? "bg-amber-500" : st === "in_progress" ? "bg-sky-500" : st === "rejected" ? "bg-rose-500" : "bg-slate-400"}`} />
                              <h3 className="truncate text-sm font-semibold text-gray-900">{req.title || "Без названия"}</h3>
                            </div>
                            <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-gray-500">
                              <span className="font-medium text-gray-700">{getDeptName(req)}</span>
                              <span>{fmt(req.created_at)}</span>
                              {getRequestAmount(req) && <span className="font-medium text-gray-700">{money(getRequestAmount(req))}</span>}
                            </div>
                          </div>

                          <div className="flex shrink-0 flex-col items-end gap-2">
                            <span className={`inline-flex shrink-0 rounded-full px-2.5 py-1 text-[11px] font-medium ring-1 ${sMeta.cls}`}>{sMeta.label}</span>
                            <span className={`text-[11px] font-medium ${urg.cls}`}>{urg.label} срочность</span>
                          </div>
                        </div>

                        <div className="mt-2 grid grid-cols-1 gap-x-3 gap-y-1 text-xs text-gray-500 sm:grid-cols-2">
                          <div className="min-w-0">
                            <span className="text-gray-400">Заявитель:</span>{" "}
                            {requestorLink
                              ? <Link href={requestorLink} className="font-medium text-sky-700 hover:text-sky-800">{requestorName}</Link>
                              : <span className="font-medium text-gray-700">{requestorName}</span>}
                          </div>
                          <div className="min-w-0">
                            <span className="text-gray-400">Исполнитель:</span>{" "}
                            {req.executor ? (
                              executorLink
                                ? <Link href={executorLink} className="font-medium text-sky-700 hover:text-sky-800">{executorName}</Link>
                                : <span className="font-medium text-gray-700">{executorName}</span>
                            ) : (
                              <span className="text-gray-400">не назначен</span>
                            )}
                          </div>
                          {(itemsCount > 0 || approvalsCount > 0) && (
                            <div className="col-span-2 flex flex-wrap items-center gap-2 pt-0.5">
                              {itemsCount > 0 && (
                                <span className="inline-flex items-center gap-1 rounded-full bg-gray-100 px-2 py-1 text-[11px] font-medium text-gray-700 ring-1 ring-gray-200">
                                  <Package size={11} /> {itemsCount} поз.
                                </span>
                              )}
                              {approvalsCount > 0 && (
                                <span className="inline-flex items-center gap-1 rounded-full bg-gray-100 px-2 py-1 text-[11px] font-medium text-gray-700 ring-1 ring-gray-200">
                                  <Check size={11} /> {approvalsCount} соглас.
                                </span>
                              )}
                            </div>
                          )}
                        </div>
                      </div>
                    </div>
                  </div>

                  <div className="hidden grid-cols-[minmax(0,2.2fr)_minmax(0,1.2fr)_minmax(0,1fr)_minmax(0,1fr)_auto] gap-3 px-4 py-3 xl:grid xl:items-center">
                    <div className="min-w-0">
                      <div className="flex items-start gap-3">
                        <button
                          type="button"
                          onClick={() => toggleExpand(req.id)}
                          aria-label={expanded ? "Свернуть детали" : "Развернуть детали"}
                          className="mt-0.5 inline-flex h-7 w-7 shrink-0 items-center justify-center rounded-lg border border-gray-200 bg-gray-50 text-gray-500 transition hover:bg-gray-100"
                        >
                          <ChevronDown size={15} className={`transition ${expanded ? "rotate-180" : ""}`} />
                        </button>
                        <div className="min-w-0 flex-1">
                          <div className="flex items-center gap-2">
                            <span className={`h-2 w-2 shrink-0 rounded-full ${st === "completed" ? "bg-teal-500" : st === "approved" ? "bg-emerald-500" : st === "pending" ? "bg-amber-500" : st === "in_progress" ? "bg-sky-500" : st === "rejected" ? "bg-rose-500" : "bg-slate-400"}`} />
                            <h3 className="truncate text-sm font-semibold text-gray-900">{req.title || "Без названия"}</h3>
                          </div>
                          <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-gray-500">
                            <span className="font-medium text-gray-700">{getDeptName(req)}</span>
                            <span>{fmt(req.created_at)}</span>
                            {itemsCount > 0 && <span>{itemsCount} поз.</span>}
                            {approvalsCount > 0 && <span>{approvalsCount} соглас.</span>}
                          </div>
                        </div>
                      </div>
                    </div>

                    <div className="min-w-0 text-sm">
                      <p className="text-xs text-gray-400">Заявитель</p>
                      {requestorLink
                        ? <Link href={requestorLink} className="truncate font-medium text-sky-700 hover:text-sky-800">{requestorName}</Link>
                        : <p className="truncate font-medium text-gray-700">{requestorName}</p>}
                      <p className="mt-1 text-xs text-gray-400">Исполнитель</p>
                      {req.executor ? (
                        executorLink
                          ? <Link href={executorLink} className="truncate font-medium text-sky-700 hover:text-sky-800">{executorName}</Link>
                          : <p className="truncate font-medium text-gray-700">{executorName}</p>
                      ) : (
                        <p className="truncate text-sm text-gray-400">Не назначен</p>
                      )}
                    </div>

                    <div>
                      <div className="flex flex-wrap items-center gap-1.5">
                        <span className={`inline-flex shrink-0 rounded-full px-2.5 py-1 text-xs font-medium ring-1 ${sMeta.cls}`}>{sMeta.label}</span>
                      </div>
                      <p className={`mt-2 text-sm font-medium ${urg.cls}`}>{urg.label} срочность</p>
                    </div>

                    <div>
                      <p className="text-sm font-medium text-gray-700">{money(getRequestAmount(req))}</p>
                      <p className="mt-1 text-xs text-gray-500">Создано {fmt(req.created_at) || "—"}</p>
                    </div>

                    <div className="flex items-center justify-end lg:justify-self-end">
                      <button
                        type="button"
                        onClick={() => toggleExpand(req.id)}
                        aria-label={expanded ? "Свернуть детали" : "Развернуть детали"}
                        className="inline-flex h-9 w-9 items-center justify-center rounded-lg border border-gray-200 bg-white text-gray-500 transition hover:bg-gray-50"
                      >
                        <ChevronDown size={16} className={`transition ${expanded ? "rotate-180" : ""}`} />
                      </button>
                    </div>
                  </div>

                  {expanded && (
                    <div className="border-t border-gray-100 bg-gray-50/70 px-4 py-4">
                      <div className="mb-3 rounded-xl bg-white px-3 py-2.5 ring-1 ring-gray-100">
                        <p className="text-xs font-medium uppercase tracking-wide text-gray-400">Описание</p>
                        <p className="mt-1 whitespace-pre-line text-sm leading-6 text-gray-700">{resolvedDetail.description || "—"}</p>
                        <div className="mt-3 grid gap-2 text-xs text-gray-500 sm:grid-cols-3">
                          <div className="rounded-lg bg-gray-50 px-3 py-2">
                            <p className="text-[11px] uppercase tracking-wide text-gray-400">Отправлена</p>
                            <p className="mt-1 font-medium text-gray-700">{fmt(resolvedDetail.submitted_at) || "—"}</p>
                          </div>
                          <div className="rounded-lg bg-gray-50 px-3 py-2">
                            <p className="text-[11px] uppercase tracking-wide text-gray-400">Взята в работу</p>
                            <p className="mt-1 font-medium text-gray-700">{fmt(resolvedDetail.started_at) || "—"}</p>
                          </div>
                          <div className="rounded-lg bg-gray-50 px-3 py-2">
                            <p className="text-[11px] uppercase tracking-wide text-gray-400">Завершена</p>
                            <p className="mt-1 font-medium text-gray-700">{fmt(resolvedDetail.completed_at) || "—"}</p>
                          </div>
                        </div>
                        {resolvedDetail.actual_cost ? (
                          <div className="mt-3 inline-flex rounded-full bg-sky-50 px-2.5 py-1 text-xs font-medium text-sky-700">
                            Фактическая сумма: {money(resolvedDetail.actual_cost)}
                          </div>
                        ) : null}
                      </div>

                      {detail?.items && detail.items.length > 0 && (
                        <div className="mb-3 rounded-xl border border-gray-200 bg-white p-3">
                          <p className="mb-2 text-xs font-medium uppercase tracking-wide text-gray-400">Позиции</p>
                          <div className="overflow-x-auto rounded-lg border border-gray-200">
                            <table className="w-full text-xs">
                              <thead className="bg-gray-50 text-gray-500">
                                <tr>
                                  <th className="px-3 py-2 text-left font-medium">Название</th>
                                  <th className="px-3 py-2 text-right font-medium">Кол-во</th>
                                  <th className="px-3 py-2 text-left font-medium">Ед.</th>
                                  <th className="px-3 py-2 text-right font-medium">Цена/ед.</th>
                                  <th className="px-3 py-2 text-right font-medium">Итого</th>
                                </tr>
                              </thead>
                              <tbody className="divide-y divide-gray-100">
                                {detail.items.map((it, idx) => (
                                  <tr key={idx} className="text-gray-700">
                                    <td className="px-3 py-2">
                                      <p className="font-medium">{it.name}</p>
                                      {it.description && <p className="mt-0.5 text-gray-500">{it.description}</p>}
                                      {it.supplier_info && <p className="mt-0.5 text-gray-400">Поставщик: {it.supplier_info}</p>}
                                    </td>
                                    <td className="px-3 py-2 text-right">{it.quantity}</td>
                                    <td className="px-3 py-2">{it.unit}</td>
                                    <td className="px-3 py-2 text-right">{money(it.estimated_unit_price)}</td>
                                    <td className="px-3 py-2 text-right font-medium">{money(it.total_price)}</td>
                                  </tr>
                                ))}
                              </tbody>
                            </table>
                          </div>
                        </div>
                      )}

                      {detail?.approvals && detail.approvals.length > 0 && (
                        <div className="mb-3 rounded-xl border border-gray-200 bg-white p-3">
                          <p className="mb-2 text-xs font-medium uppercase tracking-wide text-gray-400">Согласования</p>
                          <div className="flex flex-col gap-1.5">
                            {detail.approvals.map((a) => {
                              const aSt = String(a.status).toLowerCase();
                              const icon = aSt === "approved" ? <Check size={13} className="text-emerald-500" /> : aSt === "rejected" ? <X size={13} className="text-rose-500" /> : <CircleDot size={13} className="text-amber-500" />;
                              return (
                                <div key={a.id} className="flex items-center gap-2 rounded-lg bg-gray-50 px-3 py-2 text-xs">
                                  {icon}
                                  <span className="font-medium text-gray-700">{displayUserName(a.approver, a.approver_name)}</span>
                                  <span className="text-gray-400">({a.step_label || `Этап ${a.priority}`})</span>
                                  {a.comment && <span className="ml-auto italic text-gray-500">«{a.comment}»</span>}
                                </div>
                              );
                            })}
                          </div>
                        </div>
                      )}

                      <div className="flex flex-wrap items-center gap-1.5">
                        {isDraft && isAuthor && (
                          <button type="button" onClick={() => handleSubmit(req.id)} disabled={busyKey === `submit-${req.id}`}
                            className="inline-flex items-center gap-1 rounded-lg bg-sky-500 px-3 py-1.5 text-xs font-medium text-white hover:bg-sky-600 disabled:opacity-60">
                            <Send size={13} /> На согласование
                          </button>
                        )}
                        {isDraft && isAuthor && (
                          <button type="button" onClick={() => openEdit(req)} className="inline-flex items-center gap-1 rounded-lg border border-gray-300 bg-white px-3 py-1.5 text-xs font-medium text-gray-700 hover:bg-gray-50">
                            <Pencil size={13} /> Редактировать
                          </button>
                        )}
                        {isDraft && (isAuthor || canManage) && (
                          <button type="button" onClick={() => handleDelete(req.id)} disabled={busyKey === `delete-${req.id}`}
                            className="inline-flex items-center gap-1 rounded-lg border border-rose-200 bg-rose-50 px-3 py-1.5 text-xs font-medium text-rose-600 hover:bg-rose-100 disabled:opacity-60">
                            <Trash2 size={13} /> Удалить
                          </button>
                        )}
                        {isPending && !isAuthor && (
                          <>
                            <button type="button" onClick={() => handleApprove(req.id)} disabled={busyKey === `approve-${req.id}`}
                              className="inline-flex items-center gap-1 rounded-lg bg-emerald-500 px-3 py-1.5 text-xs font-medium text-white hover:bg-emerald-600 disabled:opacity-60">
                              <ThumbsUp size={13} /> Одобрить
                            </button>
                            <button type="button" onClick={() => handleReject(req.id)} disabled={busyKey === `reject-${req.id}`}
                              className="inline-flex items-center gap-1 rounded-lg bg-rose-500 px-3 py-1.5 text-xs font-medium text-white hover:bg-rose-600 disabled:opacity-60">
                              <ThumbsDown size={13} /> Отклонить
                            </button>
                          </>
                        )}
                        {isApproved && !req.executor && (
                          <button type="button" onClick={() => handleStart(req.id)} disabled={busyKey === `start-${req.id}`}
                            className="inline-flex items-center gap-1 rounded-lg bg-sky-500 px-3 py-1.5 text-xs font-medium text-white hover:bg-sky-600 disabled:opacity-60">
                            <Play size={13} /> Взять в работу
                          </button>
                        )}
                        {isInProgress && isExecutor && (
                          <button type="button" onClick={() => handleComplete(req.id)} disabled={busyKey === `complete-${req.id}`}
                            className="inline-flex items-center gap-1 rounded-lg bg-teal-500 px-3 py-1.5 text-xs font-medium text-white hover:bg-teal-600 disabled:opacity-60">
                            <ClipboardCheck size={13} /> Завершить
                          </button>
                        )}
                        {isAuthor && !isFinal(st) && st !== "draft" && (
                          <button type="button" onClick={() => handleCancel(req.id)} disabled={busyKey === `cancel-${req.id}`}
                            className="inline-flex items-center gap-1 rounded-lg border border-gray-300 bg-white px-3 py-1.5 text-xs font-medium text-gray-600 hover:bg-gray-50 disabled:opacity-60">
                            <XCircle size={13} /> Отменить
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
              <button type="button" onClick={handleLoadMore} disabled={loadingMore} className="rounded-lg border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-60">
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
              <button type="button" onClick={closeModal} className="rounded-lg bg-gray-200 px-3 py-2 text-sm font-medium text-gray-700 hover:bg-gray-300">Отмена</button>
              <button type="button" onClick={handleSave} disabled={busyKey === "save"} className="rounded-lg bg-sky-500 px-3 py-2 text-sm font-medium text-white hover:bg-sky-600 disabled:opacity-60">
                {modalMode === "create" ? "Создать черновик" : "Сохранить"}
              </button>
            </div>
      }>

            {actionError && <p className="mb-3 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{actionError}</p>}

            <div className="flex flex-col gap-3">
              {/* Название */}
              <div>
                <label className="mb-1 block text-xs font-medium text-gray-500">Название заявки *</label>
                <input
                  value={form.title}
                  onChange={(e) => setForm((f) => ({ ...f, title: e.target.value }))}
                  placeholder="Закупка офисной техники..."
                  className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-sky-400 focus:outline-none focus:ring-2 focus:ring-sky-100"
                />
              </div>

              {/* Описание */}
              <div>
                <label className="mb-1 block text-xs font-medium text-gray-500">Описание и обоснование *</label>
                <textarea
                  value={form.description}
                  onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))}
                  placeholder="Обоснуйте необходимость закупки..."
                  rows={3}
                  className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-sky-400 focus:outline-none focus:ring-2 focus:ring-sky-100"
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
                  <label className="mb-1 block text-xs font-medium text-gray-500">Срочность</label>
                  <select
                    value={form.urgency}
                    onChange={(e) => setForm((f) => ({ ...f, urgency: e.target.value as UrgencyLevel }))}
                    className="w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm focus:border-sky-400 focus:outline-none focus:ring-2 focus:ring-sky-100"
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
                  <label className="text-xs font-medium text-gray-500">Позиции *</label>
                  <button type="button" onClick={addItemRow} className="inline-flex items-center gap-1 text-xs font-medium text-sky-600 hover:text-sky-700">
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
                          className="w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm focus:border-sky-400 focus:outline-none"
                        />
                        <input
                          value={it.description}
                          onChange={(e) => updateItemRow(idx, { description: e.target.value })}
                          placeholder="Описание (необязательно)"
                          className="w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm focus:border-sky-400 focus:outline-none"
                        />
                        <div className="grid grid-cols-4 gap-2">
                          <input
                            type="number"
                            value={it.quantity}
                            onChange={(e) => updateItemRow(idx, { quantity: e.target.value })}
                            placeholder="Кол-во"
                            min={1}
                            className="rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm focus:border-sky-400 focus:outline-none"
                          />
                          <input
                            value={it.unit}
                            onChange={(e) => updateItemRow(idx, { unit: e.target.value })}
                            placeholder="Ед."
                            className="rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm focus:border-sky-400 focus:outline-none"
                          />
                          <input
                            type="number"
                            step="0.01"
                            value={it.estimated_unit_price}
                            onChange={(e) => updateItemRow(idx, { estimated_unit_price: e.target.value })}
                            placeholder="Цена/ед."
                            className="rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm focus:border-sky-400 focus:outline-none"
                          />
                          <div className="flex items-center text-xs text-gray-500">
                            {it.quantity && it.estimated_unit_price ? money(Number(it.quantity) * Number(it.estimated_unit_price)) : "—"}
                          </div>
                        </div>
                        <input
                          value={it.supplier_info}
                          onChange={(e) => updateItemRow(idx, { supplier_info: e.target.value })}
                          placeholder="Информация о поставщике (необязательно)"
                          className="w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm focus:border-sky-400 focus:outline-none"
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
