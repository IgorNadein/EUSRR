"use client";
/* eslint-disable react-hooks/refs -- All h.* values come from useState, not useRef. React compiler false positive. */

import { AppShell } from "../../components/AppShell";
import { Modal } from "@/components/ui";
import { apiClient } from "@/lib/api";
import { useUser } from "@/contexts/UserContext";
import { canManageRequests, canProcessRequests } from "@/lib/permissions";
import { Suspense, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import type { User } from "@/types/api";
import { ArrowUpDown, Ban, ChevronDown, ChevronRight, FileSignature, Filter, MessageSquare, Paperclip, Pencil, Plus, Search, ThumbsDown, ThumbsUp, Trash2, X, Zap } from "lucide-react";
import dynamic from "next/dynamic";
import { SearchableSelectMulti } from "@/components/shared/SearchableSelect";
import { formatDate, displayUserName, userProfileLink } from "@/lib/shared";
import {
  useRequestsPage,
  statusMeta,
  defaultStatusMeta,
  requestTypeLabels,
  orderingOptions,
} from "@/hooks/useRequestsPage";

const SwipeApprovalMode = dynamic(() => import("@/components/requests/SwipeApprovalMode"), { ssr: false });

export default function RequestsPage() {
  return (
    <Suspense fallback={<RequestsPageFallback />}>
      <RequestsPageContent />
    </Suspense>
  );
}

function RequestsPageFallback() {
  return (
    <AppShell>
      <section className="app-surface rounded-2xl p-6 text-center">
        <div className="inline-block h-5 w-5 animate-spin rounded-full border-2 border-[var(--border-strong)] border-t-[var(--accent-primary)]"></div>
        <p className="app-text-muted mt-3 text-sm">Загрузка заявлений...</p>
      </section>
    </AppShell>
  );
}

function RequestsPageContent() {
  const { user } = useUser();
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const canProcess = canProcessRequests(user);
  const canManage = canManageRequests(user);
  const auth = user?.auth;
  const h = useRequestsPage(user?.id);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const requestMenuRef = useRef<HTMLDivElement | null>(null);
  const openedLinkedRequestIdRef = useRef<number | null>(null);
  const loadingLinkedRequestIdRef = useRef<number | null>(null);
  const [requestMenuOpenId, setRequestMenuOpenId] = useState<number | null>(null);
  const linkedRequestId = Number(searchParams.get("request") || "");

  const clearRequestParam = () => {
    if (!searchParams.get("request")) return;
    const nextParams = new URLSearchParams(searchParams.toString());
    nextParams.delete("request");
    router.replace(nextParams.toString() ? `${pathname}?${nextParams.toString()}` : pathname, { scroll: false });
  };

  const closeDetailsRequest = () => {
    h.setDetailsRequest(null);
    clearRequestParam();
  };

  const renderUserBadge = (person: User, large = false) => {
    const personLink = userProfileLink(person, user?.id);
    const personName = displayUserName(person);
    const chip = (
      <>
        {person.avatar ? (
          <img src={person.avatar} alt={personName} className={`app-avatar-frame ${large ? "h-7 w-7" : "h-6 w-6"} shrink-0 rounded-full object-cover`} />
        ) : (
          <span className={`app-avatar-fallback ${large ? "h-7 w-7 text-xs" : "h-6 w-6 text-[11px]"} flex shrink-0 items-center justify-center rounded-full font-semibold`}>
            {(person.first_name?.[0] || person.last_name?.[0] || "?").toUpperCase()}
          </span>
        )}
        <span className="break-words">{personName}</span>
      </>
    );
    const cls = `app-badge inline-flex max-w-full items-center gap-2 rounded-full ${large ? "px-3 py-1.5 text-sm" : "px-2.5 py-1 text-xs"} font-medium`;
    return personLink
      ? <Link href={personLink} className={`${cls} hover:bg-[var(--surface-tertiary)]`}>{chip}</Link>
      : <span className={cls}>{chip}</span>;
  };

  useEffect(() => {
    if (!linkedRequestId) {
      openedLinkedRequestIdRef.current = null;
      loadingLinkedRequestIdRef.current = null;
      return;
    }

    if (h.detailsRequest?.id === linkedRequestId) {
      openedLinkedRequestIdRef.current = linkedRequestId;
      loadingLinkedRequestIdRef.current = null;
      return;
    }

    if (openedLinkedRequestIdRef.current === linkedRequestId) {
      return;
    }

    const existing = h.requests.find((item) => item.id === linkedRequestId);
    if (existing) {
      openedLinkedRequestIdRef.current = linkedRequestId;
      loadingLinkedRequestIdRef.current = null;
      h.setDetailsRequest(existing);
      return;
    }

    if (loadingLinkedRequestIdRef.current === linkedRequestId) {
      return;
    }

    loadingLinkedRequestIdRef.current = linkedRequestId;

    let cancelled = false;

    apiClient.getRequest(linkedRequestId)
      .then((request) => {
        if (!cancelled && openedLinkedRequestIdRef.current !== linkedRequestId) {
          openedLinkedRequestIdRef.current = linkedRequestId;
          loadingLinkedRequestIdRef.current = null;
          h.setDetailsRequest(request);
        }
      })
      .catch((error) => {
        loadingLinkedRequestIdRef.current = null;
        console.error("Ошибка deep-link заявления:", error);
      });

    return () => {
      cancelled = true;
    };
  }, [h.detailsRequest?.id, h.requests, h.setDetailsRequest, linkedRequestId]);

  useEffect(() => {
    if (requestMenuOpenId === null) return;

    const handlePointerDown = (event: MouseEvent) => {
      if (requestMenuRef.current && !requestMenuRef.current.contains(event.target as Node)) {
        setRequestMenuOpenId(null);
      }
    };

    const handleEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setRequestMenuOpenId(null);
      }
    };

    document.addEventListener("mousedown", handlePointerDown);
    document.addEventListener("keydown", handleEscape);

    return () => {
      document.removeEventListener("mousedown", handlePointerDown);
      document.removeEventListener("keydown", handleEscape);
    };
  }, [requestMenuOpenId]);

  return (
    <AppShell>
      {h.loading ? (
        <div className="app-surface rounded-2xl p-8 text-center">
          <div className="mb-4 inline-block h-8 w-8 animate-spin rounded-full border-4 border-[var(--border-strong)] border-t-[var(--accent-primary)]" />
          <p className="app-text-muted text-sm">Загрузка заявлений...</p>
        </div>
      ) : h.error ? (
        <div className="app-feedback-danger rounded-2xl p-6 text-center"><p className="text-sm">{h.error}</p></div>
      ) : (
        <section className="app-surface rounded-2xl p-4">
          {h.swipeMode && (canManage || canProcess) ? (
            <div>
              <div className="mb-4 flex items-center justify-between">
                <div className="flex items-center gap-2"><Zap size={14} className="text-amber-500" /><p className="app-text-muted text-sm font-semibold uppercase tracking-wide">Быстрый разбор</p></div>
                <button type="button" onClick={() => h.setSwipeMode(false)} className="app-action-secondary rounded-lg px-3 py-1.5 text-xs font-medium">Обычный режим</button>
              </div>
              {h.actionError && <p className="app-feedback-danger mb-3 rounded-lg px-3 py-2 text-sm">{h.actionError}</p>}
              <SwipeApprovalMode requests={h.requests} onApprove={h.handleApprove} onReject={h.handleReject} onClose={() => h.setSwipeMode(false)} />
            </div>
          ) : (
          <>
          <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
            <div className="flex items-center gap-3">
              <p className="app-text-muted text-sm font-semibold uppercase tracking-wide">Заявления</p>
              {(canManage || canProcess) && (
                <button type="button" onClick={() => h.setSwipeMode(true)} className="app-feedback-warning group flex items-center gap-1 rounded-full px-2.5 py-1 text-[11px] font-medium transition" title="Быстрый разбор">
                  <Zap size={11} className="transition group-hover:text-amber-700" />
                </button>
              )}
            </div>
            <button type="button" onClick={h.openCreate} className="app-action-primary inline-flex items-center gap-1 rounded-lg px-3 py-2 text-sm font-medium"><Plus size={14} /> Создать заявление</button>
          </div>

          {h.actionError && <p className="app-feedback-danger mb-3 rounded-lg px-3 py-2 text-sm">{h.actionError}</p>}
          {h.actionSuccess && <p className="app-feedback-success mb-3 rounded-lg px-3 py-2 text-sm">{h.actionSuccess}</p>}

          <div className="mb-4 flex items-center gap-2">
            <div className="relative flex-1">
              <Search size={16} className="app-text-muted pointer-events-none absolute left-3 top-1/2 -translate-y-1/2" />
              <input value={h.search} onChange={(e) => h.setSearch(e.target.value)} placeholder="Поиск по заявлениям" className="app-input w-full rounded-lg py-2.5 pl-9 pr-3 text-sm" />
            </div>
            <button type="button" title="Фильтры" onClick={() => h.setFiltersOpen((v) => !v)} className={`relative inline-flex items-center justify-center rounded-lg p-2.5 transition ${h.filtersOpen ? "app-selected app-accent-text" : "app-surface-muted app-text-muted hover:bg-[var(--surface-tertiary)]"}`}>
              <Filter size={16} />
              {[h.view, h.typeFilter, h.statusFilter, h.employeeFilter, h.createdFromFilter, h.createdToFilter, h.periodFromFilter, h.periodToFilter].filter(Boolean).length > 0 && (
                <span className="app-counter absolute -right-1 -top-1 flex h-4 min-w-4 px-1 text-[10px] font-bold">{[h.view, h.typeFilter, h.statusFilter, h.employeeFilter, h.createdFromFilter, h.createdToFilter, h.periodFromFilter, h.periodToFilter].filter(Boolean).length}</span>
              )}
            </button>
            <div className="relative w-[148px] shrink-0">
              <ArrowUpDown size={15} className="app-text-muted pointer-events-none absolute left-3 top-1/2 -translate-y-1/2" />
              <select value={h.ordering} onChange={(e) => h.setOrdering(e.target.value)} className="app-select w-full appearance-none rounded-lg py-2.5 pl-9 pr-8 text-xs font-medium" aria-label="Сортировка">
                {orderingOptions.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
              </select>
              <ChevronDown size={14} className="app-text-muted pointer-events-none absolute right-3 top-1/2 -translate-y-1/2" />
            </div>
          </div>

          {h.filtersOpen && (
            <div className="app-surface-muted mb-3 flex flex-col gap-2 rounded-xl p-3">
              <select value={h.view} onChange={(e) => h.setView(e.target.value as "" | "mine" | "addressed")} className="app-select rounded-lg px-3 py-2 text-sm"><option value="">Все заявления</option><option value="mine">Мои заявления</option><option value="addressed">Адресованные мне</option></select>
              <select value={h.typeFilter} onChange={(e) => h.setTypeFilter(e.target.value)} className="app-select rounded-lg px-3 py-2 text-sm"><option value="">Тип заявления</option>{Object.entries(requestTypeLabels).map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select>
              <select value={h.statusFilter} onChange={(e) => h.setStatusFilter(e.target.value)} className="app-select rounded-lg px-3 py-2 text-sm"><option value="">Статус заявления</option>{Object.entries(statusMeta).map(([v, m]) => <option key={v} value={v}>{m.label}</option>)}</select>
              <select value={h.employeeFilter} onChange={(e) => h.setEmployeeFilter(e.target.value)} className="app-select rounded-lg px-3 py-2 text-sm"><option value="">Все сотрудники</option>{h.employees.map((e) => <option key={e.id} value={e.id}>{displayUserName(e)}</option>)}</select>
              <div className="space-y-1.5"><label className="app-text-muted px-1 text-xs font-medium">Дата создания</label><div className="flex gap-2"><input type="date" value={h.createdFromFilter} onChange={(e) => h.setCreatedFromFilter(e.target.value)} className="app-input flex-1 rounded-lg px-3 py-2 text-sm" /><input type="date" value={h.createdToFilter} onChange={(e) => h.setCreatedToFilter(e.target.value)} className="app-input flex-1 rounded-lg px-3 py-2 text-sm" /></div></div>
              <div className="space-y-1.5"><label className="app-text-muted px-1 text-xs font-medium">Период заявления</label><div className="flex gap-2"><input type="date" value={h.periodFromFilter} onChange={(e) => h.setPeriodFromFilter(e.target.value)} className="app-input flex-1 rounded-lg px-3 py-2 text-sm" /><input type="date" value={h.periodToFilter} onChange={(e) => h.setPeriodToFilter(e.target.value)} className="app-input flex-1 rounded-lg px-3 py-2 text-sm" /></div></div>
              {[h.view, h.typeFilter, h.statusFilter, h.employeeFilter, h.createdFromFilter, h.createdToFilter, h.periodFromFilter, h.periodToFilter].some(Boolean) && (
                <button type="button" onClick={() => { h.setView(""); h.setTypeFilter(""); h.setStatusFilter(""); h.setEmployeeFilter(""); h.setCreatedFromFilter(""); h.setCreatedToFilter(""); h.setPeriodFromFilter(""); h.setPeriodToFilter(""); }} className="app-action-secondary rounded-lg px-3 py-2 text-sm font-medium transition">Очистить фильтры</button>
              )}
            </div>
          )}

          <div className="space-y-3">
            {h.requests.length === 0 ? (
              <div className="app-surface-muted rounded-xl p-8 text-center"><FileSignature size={22} className="app-text-muted mx-auto mb-2" /><p className="app-text-muted text-sm">Заявления не найдены</p></div>
            ) : h.requests.map((item) => {
              const requestAuthor = item.employee || item.created_by;
              const authorName = displayUserName(requestAuthor);
              const sk = String(item.status || "").toLowerCase();
              const tk = String(item.type || item.request_type || "").toLowerCase();
              const st = statusMeta[sk] ?? defaultStatusMeta;
              const al = userProfileLink(requestAuthor as User, user?.id);
              const tl = requestTypeLabels[tk] || String(item.type || item.request_type || "Другое");
              const tt = item.display_title || item.title || "Без заголовка";
              const canPr = Boolean(sk === "pending" && requestAuthor?.id && user?.id && requestAuthor.id !== user.id && (canManage || (canProcess && item.is_recipient)));
              const isAuth = Boolean(requestAuthor?.id && user?.id && requestAuthor.id === user.id);
              const canCancel = Boolean(isAuth && !h.isFinal(sk));
              const canEdit = Boolean(isAuth && !h.isFinal(sk));
              const canDelete = Boolean((isAuth && !h.isFinal(sk)) || canManage);
              const hasSecondaryActions = canCancel || canEdit || canDelete;
              const rowOpen = Boolean(h.expandedRows[item.id]);
              const comments = h.commentsMap[item.id] || [];
              const commentsOpen = Boolean(h.expandedComments[item.id]);
              const deptLabels = (item.departments || []).map((id) => h.departmentNameMap.get(Number(id)) || `Отдел #${id}`).join(", ");
              const recs = item.recipients || [];
              const ccs = item.cc_users || [];
              const summary = item.comment || item.description;

              return (
                <article key={item.id} className={`app-surface-muted rounded-xl transition hover:border-[var(--border-strong)] ${requestMenuOpenId === item.id ? "relative z-20 overflow-visible" : "overflow-hidden"}`}>
                  <div className="p-4">
                    <div className="flex items-start gap-3">
                      <div className="flex shrink-0 flex-col items-center gap-3 pt-0.5">
                        <button type="button" onClick={() => h.toggleRow(item.id)} className="app-action-secondary inline-flex h-8 w-8 items-center justify-center rounded-lg transition"><ChevronDown size={15} className={`transition ${rowOpen ? "rotate-180" : ""}`} /></button>
                        <button type="button" title={`Комментарии (${item.comments_count ?? comments.length})`} onClick={() => h.toggleComments(item.id)} className="app-action-secondary relative inline-flex h-8 w-8 items-center justify-center rounded-lg">
                          <MessageSquare size={15} />
                          {(item.comments_count ?? comments.length) > 0 && <span className="app-counter absolute -right-1.5 -top-1.5 flex h-4 min-w-4 px-1 text-[10px] font-bold">{item.comments_count ?? comments.length}</span>}
                        </button>
                      </div>
                      <div className="min-w-0 flex-1">
                        <div className="flex items-start justify-between gap-3">
                          <div className="min-w-0 flex-1">
                            <div className="mb-2 flex items-center gap-2">
                              {al ? (
                                <Link href={al} className="group flex min-w-0 items-center gap-2">
                                  {requestAuthor?.avatar ? <img src={requestAuthor.avatar} alt={authorName} className="app-avatar-frame h-8 w-8 shrink-0 rounded-full object-cover" /> : <span className="app-avatar-fallback flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-xs font-semibold">{(requestAuthor?.first_name?.[0] || requestAuthor?.last_name?.[0] || "?").toUpperCase()}</span>}
                                  <span className="truncate text-sm font-medium text-[var(--foreground)] group-hover:text-[var(--accent-primary-strong)]">{authorName}</span>
                                </Link>
                              ) : (
                                <div className="flex min-w-0 items-center gap-2"><span className="app-badge flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-xs font-semibold">?</span><span className="truncate text-sm font-medium text-[var(--foreground)]">{authorName}</span></div>
                              )}
                            </div>
                            <button type="button" onClick={() => h.setDetailsRequest(item)} className="block w-full text-left">
                              <h3 className={`${rowOpen ? "app-text-wrap line-clamp-3" : "truncate"} text-sm font-semibold text-[var(--foreground)] transition hover:text-[var(--accent-primary-strong)]`}><span className="app-text-muted">{tl}:</span> <span className="text-[var(--foreground)]">{tt}</span></h3>
                            </button>
                            <div className="app-text-muted mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs"><span>Период: {item.date_from ? formatDate(item.date_from) : "—"}{item.date_to ? ` — ${formatDate(item.date_to)}` : ""}</span></div>
                          </div>
                          <div className="shrink-0">
                            <div
                              ref={requestMenuOpenId === item.id ? requestMenuRef : null}
                              className="flex items-center justify-end gap-2"
                            >
                              <span className={`inline-flex rounded-full px-2.5 py-1 text-xs ring-1 ${st.className}`}>{st.label}</span>
                              {hasSecondaryActions ? (
                                <div className="relative">
                                  <button
                                    type="button"
                                    onClick={() => setRequestMenuOpenId((prev) => (prev === item.id ? null : item.id))}
                                    className="app-action-ghost flex h-8 w-8 items-center justify-center rounded-md"
                                    title="Действия с заявлением"
                                    aria-label="Действия с заявлением"
                                    aria-expanded={requestMenuOpenId === item.id}
                                    aria-haspopup="menu"
                                  >
                                    <ChevronRight
                                      size={15}
                                      className={`transition-transform duration-200 ${requestMenuOpenId === item.id ? "rotate-90" : ""}`}
                                    />
                                  </button>
                                  {requestMenuOpenId === item.id ? (
                                    <div className="app-menu absolute right-0 top-full z-20 mt-2 w-44 rounded-xl py-1.5">
                                      {canCancel ? (
                                        <button
                                          type="button"
                                          disabled={h.busyKey === `cancel-${item.id}`}
                                          onClick={() => {
                                            setRequestMenuOpenId(null);
                                            void h.handleCancel(item.id);
                                          }}
                                          className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm text-[var(--foreground)] transition hover:bg-[var(--surface-secondary)] disabled:opacity-50"
                                        >
                                          <Ban size={14} />
                                          Отменить
                                        </button>
                                      ) : null}
                                      {canEdit ? (
                                        <button
                                          type="button"
                                          onClick={() => {
                                            setRequestMenuOpenId(null);
                                            h.openEdit(item);
                                          }}
                                          className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm text-[var(--foreground)] transition hover:bg-[var(--surface-secondary)]"
                                        >
                                          <Pencil size={14} />
                                          Редактировать
                                        </button>
                                      ) : null}
                                      {canDelete ? (
                                        <button
                                          type="button"
                                          disabled={h.busyKey === `delete-${item.id}`}
                                          onClick={() => {
                                            setRequestMenuOpenId(null);
                                            void h.handleDelete(item.id);
                                          }}
                                          className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm text-[var(--danger-foreground)] transition hover:bg-[var(--danger-soft)] disabled:opacity-50"
                                        >
                                          <Trash2 size={14} />
                                          Удалить
                                        </button>
                                      ) : null}
                                    </div>
                                  ) : null}
                                </div>
                              ) : null}
                            </div>
                          </div>
                        </div>
                        {summary && <p className={`${rowOpen ? "app-text-wrap line-clamp-10" : "app-text-wrap line-clamp-3"} mt-3 text-sm text-[var(--foreground)]`}>{summary}</p>}
                        {canPr && <div className={`${summary ? "mt-3" : "mt-2"} flex flex-wrap items-center gap-1.5`}><span className="ml-auto inline-flex items-center gap-2"><button type="button" title="Одобрить" onClick={() => h.handleApprove(item.id)} disabled={h.busyKey === `approve-${item.id}`} className="app-feedback-success inline-flex items-center justify-center rounded-lg p-2 disabled:opacity-60"><ThumbsUp size={18} /></button><button type="button" title="Отклонить" onClick={() => h.handleReject(item.id)} disabled={h.busyKey === `reject-${item.id}`} className="app-action-danger inline-flex items-center justify-center rounded-lg p-2 disabled:opacity-60"><ThumbsDown size={18} /></button></span></div>}
                      </div>
                    </div>

                    {(rowOpen || commentsOpen) && (
                      <div className="app-surface-elevated mt-4 rounded-xl p-4">
                        {rowOpen && (
                          <div className="space-y-3 text-xs">
                            <div className="grid grid-cols-1 gap-x-4 gap-y-2 sm:grid-cols-2">
                              <div><span className="app-text-muted">Решающий:</span> {(() => { const a = item.approver || item.assigned_to; if (!a) return <span className="app-text-muted">—</span>; const alink = userProfileLink(a as User, user?.id); const aname = displayUserName(a); return alink ? <Link href={alink} className="app-link-accent font-medium">{aname}</Link> : <span className="font-medium text-[var(--foreground)]">{aname}</span>; })()}</div>
                              <div><span className="app-text-muted">Создано:</span> <span className="font-medium text-[var(--foreground)]">{formatDate(item.created_at) || "—"}</span></div>
                              <div><span className="app-text-muted">Обновлено:</span> <span className="font-medium text-[var(--foreground)]">{formatDate(item.updated_at) || "—"}</span></div>
                              {deptLabels && <div className="sm:col-span-2"><span className="app-text-muted">Отделы:</span> <span className="font-medium text-[var(--foreground)]">{deptLabels}</span></div>}
                            </div>
                            <div className="space-y-2">
                              <div className="flex flex-wrap items-start gap-2"><span className="app-text-muted pt-1">Получатели:</span><div className="flex min-w-0 flex-1 flex-wrap gap-1.5">{recs.slice(0,2).map((r) => <div key={r.id}>{renderUserBadge(r)}</div>)}{recs.length === 0 && <span className="app-text-muted pt-1">{item.recipient_count ?? 0}</span>}{recs.length > 2 && <span className="app-badge px-2 py-1 text-xs font-medium">+{recs.length - 2}</span>}</div></div>
                              <div className="flex flex-wrap items-start gap-2"><span className="app-text-muted pt-1">В копии:</span><div className="flex min-w-0 flex-1 flex-wrap gap-1.5">{ccs.slice(0,2).map((c) => <div key={c.id}>{renderUserBadge(c)}</div>)}{ccs.length === 0 && <span className="app-text-muted pt-1">—</span>}{ccs.length > 2 && <span className="app-badge px-2 py-1 text-xs font-medium">+{ccs.length - 2}</span>}</div></div>
                              {(item.attachment || item.attachment_url) && <div className="flex min-w-0 items-center gap-1.5"><button type="button" onClick={() => { const url = item.attachment_url || item.attachment || ""; h.setAttachmentPreview({ url, name: decodeURIComponent(url.split("/").pop() || "Вложение") }); }} className="app-badge app-badge-accent inline-flex min-w-0 max-w-full items-center gap-1.5 px-2.5 py-1 text-xs font-medium"><Paperclip size={13} className="shrink-0" /><span className="truncate">{decodeURIComponent((item.attachment_url || item.attachment || "").split("/").pop() || "Вложение")}</span></button></div>}
                            </div>
                          </div>
                        )}
                        {commentsOpen && (
                          <div className={rowOpen ? "app-surface mt-3 rounded-xl p-3" : "app-surface rounded-xl p-3"}>
                            <div className="space-y-2">{comments.length === 0 ? <p className="app-text-muted text-xs">Комментариев пока нет</p> : comments.map((c) => (<div key={c.id} className="app-surface-muted rounded-lg px-3 py-2 text-xs text-[var(--foreground)]"><div className="mb-1 flex items-center justify-between gap-2"><span className="font-medium">{displayUserName(c.author)}</span><div className="flex items-center gap-2"><span className="app-text-muted">{formatDate(c.created_at)}</span>{Boolean(c.author?.id && (user?.id === c.author.id || auth?.is_staff || auth?.is_superuser)) && <button type="button" onClick={() => h.handleDeleteComment(item.id, c.id)} className="app-action-danger rounded-md px-1.5 py-0.5">удалить</button>}</div></div><p className="app-text-wrap text-[var(--foreground)]">{c.text}</p></div>))}</div>
                            <div className="mt-2 flex items-center gap-2"><input value={h.commentDrafts[item.id] || ""} onChange={(e) => h.setCommentDrafts((p) => ({ ...p, [item.id]: e.target.value }))} placeholder="Добавить комментарий" className="app-input flex-1 rounded-lg px-3 py-2 text-xs" /><button type="button" onClick={() => h.handleAddComment(item.id)} disabled={h.busyKey === `comment-${item.id}`} className="app-action-primary rounded-lg px-3 py-2 text-xs font-medium disabled:opacity-60">Отправить</button></div>
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                </article>
              );
            })}
          </div>

          {h.nextPage && <div ref={h.loadMoreRef} className="mt-4 flex justify-center py-4">{h.loadingMore && <div className="app-text-muted flex items-center gap-2 text-sm"><div className="h-4 w-4 animate-spin rounded-full border-2 border-[var(--border-strong)] border-t-[var(--accent-primary)]" /><span>Загрузка...</span></div>}</div>}
          </>
          )}
        </section>
      )}

      {/* Detail modal */}
      <Modal isOpen={Boolean(h.detailsRequest)} onClose={closeDetailsRequest} title="Полная информация по заявлению" size="lg">
        {h.detailsRequest && (() => {
          const dr = h.detailsRequest; const da = dr.employee || dr.created_by; const dap = dr.approver || dr.assigned_to;
          const ds = statusMeta[String(dr.status || "").toLowerCase()] ?? defaultStatusMeta;
          const dtl = requestTypeLabels[String(dr.type || dr.request_type || "").toLowerCase()] || String(dr.type || dr.request_type || "Другое");
          const dau = dr.attachment_url || dr.attachment || ""; const dan = dau ? decodeURIComponent(dau.split("/").pop() || "Вложение") : "";
          return (
            <div className="space-y-5 text-sm text-[var(--foreground)]">
              <div className="app-surface-muted rounded-xl p-4"><div className="space-y-3"><div className="flex flex-wrap items-center gap-2"><span className="app-badge app-badge-accent px-2.5 py-1 text-xs font-medium">{dtl}</span><span className={`inline-flex rounded-full px-2.5 py-1 text-xs ring-1 ${ds.className}`}>{ds.label}</span></div><h2 className="app-text-wrap text-lg font-semibold text-[var(--foreground)]">{dr.display_title || dr.title || "Без заголовка"}</h2>{(dr.comment || dr.description) ? <div className="app-text-wrap mt-3 whitespace-pre-wrap text-sm leading-relaxed text-[var(--foreground)]">{dr.comment || dr.description}</div> : <p className="app-text-muted mt-3 text-sm">Описание отсутствует</p>}</div></div>
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                <div className="app-surface rounded-xl p-4"><p className="app-text-muted text-xs font-semibold uppercase tracking-wide">Даты</p><div className="mt-3 space-y-2"><div><p className="app-text-muted text-xs">Период</p><p className="mt-1 text-sm text-[var(--foreground)]">{dr.date_from ? formatDate(dr.date_from) : "—"}{dr.date_to ? ` — ${formatDate(dr.date_to)}` : ""}</p></div><div><p className="app-text-muted text-xs">Создано</p><p className="mt-1 text-sm text-[var(--foreground)]">{formatDate(dr.created_at) || "—"}</p></div><div><p className="app-text-muted text-xs">Обновлено</p><p className="mt-1 text-sm text-[var(--foreground)]">{formatDate(dr.updated_at) || "—"}</p></div></div></div>
                <div className="app-surface rounded-xl p-4"><p className="app-text-muted text-xs font-semibold uppercase tracking-wide">Участники</p><div className="mt-3 space-y-3"><div><p className="app-text-muted text-xs">Автор</p><div className="mt-2 flex flex-wrap gap-2">{da ? renderUserBadge(da as User, true) : <span className="app-text-muted text-sm">—</span>}</div></div><div><p className="app-text-muted text-xs">Решающий</p><div className="mt-2 flex flex-wrap gap-2">{dap ? renderUserBadge(dap as User, true) : <span className="app-text-muted text-sm">—</span>}</div></div></div></div>
              </div>
              <div className="app-surface rounded-xl p-4"><p className="app-text-muted text-xs font-semibold uppercase tracking-wide">Отделы</p>{(dr.departments || []).length > 0 ? <div className="mt-3 flex flex-wrap gap-2">{(dr.departments || []).map((id) => <span key={id} className="app-badge px-3 py-1.5 text-sm font-medium">{h.departmentNameMap.get(Number(id)) || `Отдел #${id}`}</span>)}</div> : <p className="app-text-muted mt-3 text-sm">Отделы не указаны</p>}</div>
              <div className="app-surface rounded-xl p-4"><p className="app-text-muted text-xs font-semibold uppercase tracking-wide">Получатели</p>{(dr.recipients || []).length > 0 ? <div className="mt-3 flex flex-wrap gap-2">{(dr.recipients || []).map((r) => <div key={r.id}>{renderUserBadge(r, true)}</div>)}</div> : <p className="app-text-muted mt-3 text-sm">Получатели не указаны</p>}</div>
              <div className="app-surface rounded-xl p-4"><p className="app-text-muted text-xs font-semibold uppercase tracking-wide">В копии</p>{(dr.cc_users || []).length > 0 ? <div className="mt-3 flex flex-wrap gap-2">{(dr.cc_users || []).map((c) => <div key={c.id}>{renderUserBadge(c, true)}</div>)}</div> : <p className="app-text-muted mt-3 text-sm">Копия не указана</p>}</div>
              <div className="app-surface rounded-xl p-4"><p className="app-text-muted text-xs font-semibold uppercase tracking-wide">Вложение</p>{dau ? <div className="mt-3 flex flex-wrap items-center gap-3"><button type="button" onClick={() => h.setAttachmentPreview({ url: dau, name: dan })} className="app-action-secondary inline-flex items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium"><Paperclip size={15} /><span className="app-text-wrap">{dan}</span></button><a href={dau} target="_blank" rel="noreferrer" className="app-link-accent text-sm font-medium hover:underline">Открыть в новой вкладке</a></div> : <p className="app-text-muted mt-3 text-sm">Вложение отсутствует</p>}</div>
            </div>
          );
        })()}
      </Modal>

      {/* Create/Edit modal */}
      <Modal isOpen={h.isModalOpen} onClose={h.closeModal} title={h.modalMode === "create" ? "Новое заявление" : "Редактировать заявление"} size="md" footer={
            <div className="flex flex-wrap items-center justify-end gap-2">
              <button type="button" onClick={h.closeModal} className="app-action-secondary rounded-lg px-3 py-2 text-sm font-medium">Отмена</button>
              <button type="button" onClick={() => h.handleCreateOrUpdate(h.modalMode, "draft")} disabled={h.busyKey !== null} className="app-action-secondary rounded-lg px-3 py-2 text-sm font-medium disabled:opacity-60">Сохранить как черновик</button>
              <button type="button" onClick={() => h.handleCreateOrUpdate(h.modalMode, "submitted")} disabled={h.busyKey !== null} className="app-action-primary rounded-lg px-3 py-2 text-sm font-medium disabled:opacity-60">{h.modalMode === "create" ? "Создать" : "Сохранить"}</button>
            </div>
      }>
            {h.actionError && <p className="app-feedback-danger mb-3 rounded-lg px-3 py-2 text-sm">{h.actionError}</p>}
            <div className="flex flex-col gap-3">
              <div><label className="app-text-muted mb-1 block text-xs font-medium">Тема заявления</label><input value={h.form.title} onChange={(e) => h.setForm((p) => ({ ...p, title: e.target.value }))} placeholder="Тема заявления" className="app-input w-full rounded-lg px-3 py-2 text-sm" /></div>
              <div><label className="app-text-muted mb-1 block text-xs font-medium">Тип заявления</label><select value={h.form.type} onChange={(e) => h.setForm((p) => ({ ...p, type: e.target.value }))} className="app-select w-full rounded-lg px-3 py-2 text-sm"><option value="">Выберите тип</option>{Object.entries(requestTypeLabels).map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select></div>
              <div><label className="app-text-muted mb-1 block text-xs font-medium">Период</label><div className="flex items-center gap-2"><input type="date" value={h.form.date_from} onChange={(e) => h.setForm((p) => ({ ...p, date_from: e.target.value }))} className="app-input flex-1 rounded-lg px-3 py-2 text-sm" /><span className="app-text-muted text-xs">—</span><input type="date" value={h.form.date_to} onChange={(e) => h.setForm((p) => ({ ...p, date_to: e.target.value }))} className="app-input flex-1 rounded-lg px-3 py-2 text-sm" /></div></div>
              <SearchableSelectMulti label="Решающий" placeholder="Выберите решающего..." items={h.employees.filter((e) => !user?.id || e.id !== user.id).map((e) => ({ id: e.id, name: displayUserName(e) }))} selectedIds={h.form.recipient_ids} onToggle={(id) => h.setForm((p) => ({ ...p, recipient_ids: p.recipient_ids.includes(id) ? p.recipient_ids.filter((x) => x !== id) : [...p.recipient_ids, id] }))} />
              <SearchableSelectMulti label="В копии" placeholder="Выберите пользователей..." items={h.employees.filter((e) => !user?.id || e.id !== user.id).map((e) => ({ id: e.id, name: displayUserName(e) }))} selectedIds={h.form.cc_user_ids} onToggle={(id) => h.setForm((p) => ({ ...p, cc_user_ids: p.cc_user_ids.includes(id) ? p.cc_user_ids.filter((x) => x !== id) : [...p.cc_user_ids, id] }))} />
              <SearchableSelectMulti label="Отдел" placeholder="Выберите отдел..." items={h.departments.map((d) => ({ id: d.id, name: d.name }))} selectedIds={h.form.department_ids} onToggle={(id) => h.setForm((p) => ({ ...p, department_ids: p.department_ids.includes(id) ? p.department_ids.filter((x) => x !== id) : [...p.department_ids, id] }))} />
              <div><label className="app-text-muted mb-1 block text-xs font-medium">Описание</label><textarea value={h.form.comment} onChange={(e) => h.setForm((p) => ({ ...p, comment: e.target.value }))} placeholder="Описание заявления" rows={3} className="app-input w-full rounded-lg px-3 py-2 text-sm" /></div>
              <div><input ref={fileInputRef} type="file" accept=".pdf,.jpg,.jpeg,.png" className="hidden" onChange={(e) => { const f = e.target.files?.[0] || null; if (f) { const ext = f.name.split(".").pop()?.toLowerCase() || ""; if (!["pdf","jpg","jpeg","png"].includes(ext)) return; } h.setForm((p) => ({ ...p, attachment: f })); }} /><button type="button" onClick={() => fileInputRef.current?.click()} className="app-action-secondary inline-flex items-center gap-1.5 rounded-lg px-3 py-2 text-sm"><Paperclip size={14} />{h.form.attachment ? h.form.attachment.name : "Прикрепить файл"}</button></div>
              <label className="flex items-center gap-2 text-sm text-[var(--foreground)]"><input type="checkbox" checked={h.form.sent_to_all_department} onChange={(e) => h.setForm((p) => ({ ...p, sent_to_all_department: e.target.checked }))} className="rounded border-[var(--border-strong)]" />Отправить всем сотрудникам выбранных отделов</label>
            </div>
      </Modal>

      {/* Attachment preview */}
      {h.attachmentPreview && (() => {
        const apUrl = h.attachmentPreview.url;
        const apName = h.attachmentPreview.name;
        return (
        <Modal isOpen onClose={() => h.setAttachmentPreview(null)} title={apName} size="lg" footer={<a href={apUrl} download className="app-action-secondary rounded-lg px-3 py-1.5 text-xs font-medium">Скачать</a>}>
            <div className="flex-1 overflow-auto">{(() => { const ext = apUrl.split(".").pop()?.toLowerCase() || ""; if (["jpg","jpeg","png","gif","webp","svg","bmp"].includes(ext)) return <img src={apUrl} alt={apName} className="mx-auto max-h-[70vh] rounded-lg object-contain" />; if (["mp4","webm","ogg","mov"].includes(ext)) return <video src={apUrl} controls className="mx-auto max-h-[70vh] rounded-lg" />; if (["mp3","wav","aac"].includes(ext)) return <audio src={apUrl} controls className="mx-auto mt-8" />; return <div className="flex flex-col items-center gap-3 py-12 text-center"><FileSignature size={40} className="app-text-muted" /><p className="app-text-muted text-sm">{apName}</p><a href={apUrl} download className="app-action-primary rounded-lg px-4 py-2 text-sm font-medium">Скачать файл</a></div>; })()}</div>
        </Modal>
        );
      })()}
    </AppShell>
  );
}
