"use client";
/* eslint-disable react-hooks/refs -- All h.* values come from useState, not useRef. React compiler false positive. */

import { AppShell } from "../../components/AppShell";
import { Modal } from "@/components/ui";
import { apiClient } from "@/lib/api";
import { useUser } from "@/contexts/UserContext";
import { canManageRequests, canProcessRequests } from "@/lib/permissions";
import { useEffect, useRef } from "react";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import type { User } from "@/types/api";
import { ArrowUpDown, Ban, ChevronDown, FileSignature, Filter, MessageSquare, Paperclip, Pencil, Plus, Search, ThumbsDown, ThumbsUp, Trash2, X, Zap } from "lucide-react";
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
  const { user } = useUser();
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const canProcess = canProcessRequests(user);
  const canManage = canManageRequests(user);
  const auth = user?.auth;
  const h = useRequestsPage(user?.id);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const openedLinkedRequestIdRef = useRef<number | null>(null);
  const loadingLinkedRequestIdRef = useRef<number | null>(null);
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
          <img src={person.avatar} alt={personName} className={`${large ? "h-7 w-7" : "h-6 w-6"} shrink-0 rounded-full object-cover ring-1 ring-gray-200`} />
        ) : (
          <span className={`${large ? "h-7 w-7 text-xs" : "h-6 w-6 text-[11px]"} flex shrink-0 items-center justify-center rounded-full bg-sky-100 font-semibold text-sky-700 ring-1 ring-sky-200`}>
            {(person.first_name?.[0] || person.last_name?.[0] || "?").toUpperCase()}
          </span>
        )}
        <span className="break-words">{personName}</span>
      </>
    );
    const cls = `inline-flex max-w-full items-center gap-2 rounded-full bg-gray-100 ${large ? "px-3 py-1.5 text-sm" : "px-2.5 py-1 text-xs"} font-medium text-gray-700 ring-1 ring-gray-200`;
    return personLink
      ? <Link href={personLink} className={`${cls} hover:bg-gray-200`}>{chip}</Link>
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

  return (
    <AppShell>
      {h.loading ? (
        <div className="rounded-2xl bg-white p-8 text-center shadow-sm ring-1 ring-gray-100">
          <div className="mb-4 inline-block h-8 w-8 animate-spin rounded-full border-4 border-sky-400 border-t-transparent" />
          <p className="text-sm text-gray-500">Загрузка заявлений...</p>
        </div>
      ) : h.error ? (
        <div className="rounded-2xl bg-red-50 p-6 text-center"><p className="text-sm text-red-800">{h.error}</p></div>
      ) : (
        <section className="rounded-2xl bg-white p-4 shadow-sm ring-1 ring-gray-100">
          {h.swipeMode && (canManage || canProcess) ? (
            <div>
              <div className="mb-4 flex items-center justify-between">
                <div className="flex items-center gap-2"><Zap size={14} className="text-amber-500" /><p className="text-sm font-semibold uppercase tracking-wide text-gray-500">Быстрый разбор</p></div>
                <button type="button" onClick={() => h.setSwipeMode(false)} className="rounded-lg bg-gray-100 px-3 py-1.5 text-xs font-medium text-gray-600 hover:bg-gray-200">Обычный режим</button>
              </div>
              {h.actionError && <p className="mb-3 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{h.actionError}</p>}
              <SwipeApprovalMode requests={h.requests} onApprove={h.handleApprove} onReject={h.handleReject} onClose={() => h.setSwipeMode(false)} />
            </div>
          ) : (
          <>
          <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
            <div className="flex items-center gap-3">
              <p className="text-sm font-semibold uppercase tracking-wide text-gray-500">Заявления</p>
              {(canManage || canProcess) && (
                <button type="button" onClick={() => h.setSwipeMode(true)} className="group flex items-center gap-1 rounded-full bg-amber-50 px-2.5 py-1 text-[11px] font-medium text-amber-600 ring-1 ring-amber-100 transition hover:bg-amber-100" title="Быстрый разбор">
                  <Zap size={11} className="transition group-hover:text-amber-700" />
                </button>
              )}
            </div>
            <button type="button" onClick={h.openCreate} className="inline-flex items-center gap-1 rounded-lg bg-sky-500 px-3 py-2 text-sm font-medium text-white hover:bg-sky-600"><Plus size={14} /> Создать заявление</button>
          </div>

          {h.actionError && <p className="mb-3 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{h.actionError}</p>}
          {h.actionSuccess && <p className="mb-3 rounded-lg bg-emerald-50 px-3 py-2 text-sm text-emerald-700">{h.actionSuccess}</p>}

          <div className="mb-4 flex items-center gap-2">
            <div className="relative flex-1">
              <Search size={16} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
              <input value={h.search} onChange={(e) => h.setSearch(e.target.value)} placeholder="Поиск по заявлениям" className="w-full rounded-lg border border-gray-200 bg-gray-50 py-2.5 pl-9 pr-3 text-sm text-gray-800 transition focus:border-sky-500 focus:bg-white focus:outline-none focus:ring-2 focus:ring-sky-100" />
            </div>
            <button type="button" title="Фильтры" onClick={() => h.setFiltersOpen((v) => !v)} className={`relative inline-flex items-center justify-center rounded-lg border p-2.5 transition ${h.filtersOpen ? "border-sky-400 bg-sky-50 text-sky-600" : "border-gray-200 bg-gray-50 text-gray-500 hover:bg-gray-100"}`}>
              <Filter size={16} />
              {[h.view, h.typeFilter, h.statusFilter, h.employeeFilter, h.createdFromFilter, h.createdToFilter, h.periodFromFilter, h.periodToFilter].filter(Boolean).length > 0 && (
                <span className="absolute -right-1 -top-1 flex h-4 min-w-4 items-center justify-center rounded-full bg-sky-500 px-1 text-[10px] font-bold text-white">{[h.view, h.typeFilter, h.statusFilter, h.employeeFilter, h.createdFromFilter, h.createdToFilter, h.periodFromFilter, h.periodToFilter].filter(Boolean).length}</span>
              )}
            </button>
            <div className="relative w-[148px] shrink-0">
              <ArrowUpDown size={15} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-gray-500" />
              <select value={h.ordering} onChange={(e) => h.setOrdering(e.target.value)} className="w-full appearance-none rounded-lg border border-gray-200 bg-gray-50 py-2.5 pl-9 pr-8 text-xs font-medium text-gray-700 transition hover:bg-gray-100 focus:border-sky-400 focus:bg-white focus:outline-none focus:ring-2 focus:ring-sky-100" aria-label="Сортировка">
                {orderingOptions.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
              </select>
              <ChevronDown size={14} className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-gray-400" />
            </div>
          </div>

          {h.filtersOpen && (
            <div className="mb-3 flex flex-col gap-2 rounded-xl border border-gray-200 bg-gray-50 p-3">
              <select value={h.view} onChange={(e) => h.setView(e.target.value as "" | "mine" | "addressed")} className="rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm text-gray-800"><option value="">Все заявления</option><option value="mine">Мои заявления</option><option value="addressed">Адресованные мне</option></select>
              <select value={h.typeFilter} onChange={(e) => h.setTypeFilter(e.target.value)} className="rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm text-gray-800"><option value="">Тип заявления</option>{Object.entries(requestTypeLabels).map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select>
              <select value={h.statusFilter} onChange={(e) => h.setStatusFilter(e.target.value)} className="rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm text-gray-800"><option value="">Статус заявления</option>{Object.entries(statusMeta).map(([v, m]) => <option key={v} value={v}>{m.label}</option>)}</select>
              <select value={h.employeeFilter} onChange={(e) => h.setEmployeeFilter(e.target.value)} className="rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm text-gray-800"><option value="">Все сотрудники</option>{h.employees.map((e) => <option key={e.id} value={e.id}>{displayUserName(e)}</option>)}</select>
              <div className="space-y-1.5"><label className="px-1 text-xs font-medium text-gray-600">Дата создания</label><div className="flex gap-2"><input type="date" value={h.createdFromFilter} onChange={(e) => h.setCreatedFromFilter(e.target.value)} className="flex-1 rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm text-gray-800" /><input type="date" value={h.createdToFilter} onChange={(e) => h.setCreatedToFilter(e.target.value)} className="flex-1 rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm text-gray-800" /></div></div>
              <div className="space-y-1.5"><label className="px-1 text-xs font-medium text-gray-600">Период заявления</label><div className="flex gap-2"><input type="date" value={h.periodFromFilter} onChange={(e) => h.setPeriodFromFilter(e.target.value)} className="flex-1 rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm text-gray-800" /><input type="date" value={h.periodToFilter} onChange={(e) => h.setPeriodToFilter(e.target.value)} className="flex-1 rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm text-gray-800" /></div></div>
              {[h.view, h.typeFilter, h.statusFilter, h.employeeFilter, h.createdFromFilter, h.createdToFilter, h.periodFromFilter, h.periodToFilter].some(Boolean) && (
                <button type="button" onClick={() => { h.setView(""); h.setTypeFilter(""); h.setStatusFilter(""); h.setEmployeeFilter(""); h.setCreatedFromFilter(""); h.setCreatedToFilter(""); h.setPeriodFromFilter(""); h.setPeriodToFilter(""); }} className="rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm font-medium text-gray-600 transition hover:bg-gray-100">Очистить фильтры</button>
              )}
            </div>
          )}

          <div className="space-y-3">
            {h.requests.length === 0 ? (
              <div className="rounded-xl bg-gray-50 p-8 text-center"><FileSignature size={22} className="mx-auto mb-2 text-gray-400" /><p className="text-sm text-gray-500">Заявления не найдены</p></div>
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
              const rowOpen = Boolean(h.expandedRows[item.id]);
              const comments = h.commentsMap[item.id] || [];
              const commentsOpen = Boolean(h.expandedComments[item.id]);
              const deptLabels = (item.departments || []).map((id) => h.departmentNameMap.get(Number(id)) || `Отдел #${id}`).join(", ");
              const recs = item.recipients || [];
              const ccs = item.cc_users || [];
              const summary = item.comment || item.description;

              return (
                <article key={item.id} className="overflow-hidden rounded-xl border border-gray-200 bg-white transition hover:border-gray-300">
                  <div className="p-4">
                    <div className="flex items-start gap-3">
                      <button type="button" onClick={() => h.toggleRow(item.id)} className="mt-0.5 inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border border-gray-200 bg-gray-50 text-gray-500 transition hover:bg-gray-100"><ChevronDown size={15} className={`transition ${rowOpen ? "rotate-180" : ""}`} /></button>
                      <div className="min-w-0 flex-1">
                        <div className="flex items-start justify-between gap-3">
                          <div className="min-w-0 flex-1">
                            <div className="mb-2 flex items-center gap-2">
                              {al ? (
                                <Link href={al} className="group flex min-w-0 items-center gap-2">
                                  {requestAuthor?.avatar ? <img src={requestAuthor.avatar} alt={authorName} className="h-8 w-8 shrink-0 rounded-full object-cover ring-1 ring-gray-200" /> : <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-sky-100 text-xs font-semibold text-sky-700 ring-1 ring-sky-200">{(requestAuthor?.first_name?.[0] || requestAuthor?.last_name?.[0] || "?").toUpperCase()}</span>}
                                  <span className="truncate text-sm font-medium text-gray-800 group-hover:text-sky-700">{authorName}</span>
                                </Link>
                              ) : (
                                <div className="flex min-w-0 items-center gap-2"><span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-gray-100 text-xs font-semibold text-gray-500 ring-1 ring-gray-200">?</span><span className="truncate text-sm font-medium text-gray-800">{authorName}</span></div>
                              )}
                            </div>
                            <button type="button" onClick={() => h.setDetailsRequest(item)} className="block w-full text-left">
                              <h3 className={`${rowOpen ? "line-clamp-3 break-words" : "truncate"} text-sm font-semibold text-gray-900 transition hover:text-gray-700`}><span className="text-gray-600">{tl}:</span> <span className="text-gray-900">{tt}</span></h3>
                            </button>
                            <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-gray-500"><span>Период: {item.date_from ? formatDate(item.date_from) : "—"}{item.date_to ? ` — ${formatDate(item.date_to)}` : ""}</span></div>
                          </div>
                          <div className="shrink-0 text-right"><span className={`inline-flex rounded-full px-2.5 py-1 text-xs ring-1 ${st.className}`}>{st.label}</span></div>
                        </div>
                        {summary && <p className={`${rowOpen ? "line-clamp-10 break-words" : "line-clamp-3"} mt-3 text-sm text-gray-700`}>{summary}</p>}
                        <div className={`${summary ? "mt-3" : "mt-2"} flex flex-wrap items-center gap-1.5`}>
                          {isAuth && !h.isFinal(sk) && <button type="button" title="Отменить" onClick={() => h.handleCancel(item.id)} disabled={h.busyKey === `cancel-${item.id}`} className="inline-flex items-center justify-center rounded-lg border border-gray-300 bg-white p-1.5 text-gray-600 hover:bg-gray-50 disabled:opacity-60"><Ban size={15} /></button>}
                          <button type="button" title={`Комментарии (${item.comments_count ?? comments.length})`} onClick={() => h.toggleComments(item.id)} className="relative inline-flex items-center justify-center rounded-lg border border-gray-300 bg-white p-1.5 text-gray-600 hover:bg-gray-50"><MessageSquare size={15} />{(item.comments_count ?? comments.length) > 0 && <span className="absolute -right-1.5 -top-1.5 flex h-4 min-w-4 items-center justify-center rounded-full bg-sky-500 px-1 text-[10px] font-bold text-white">{item.comments_count ?? comments.length}</span>}</button>
                          {isAuth && !h.isFinal(sk) && <button type="button" title="Редактировать" onClick={() => h.openEdit(item)} className="inline-flex items-center justify-center rounded-lg border border-gray-300 bg-white p-1.5 text-gray-600 hover:bg-gray-50"><Pencil size={15} /></button>}
                          {((isAuth && !h.isFinal(sk)) || canManage) && <button type="button" title="Удалить" onClick={() => h.handleDelete(item.id)} disabled={h.busyKey === `delete-${item.id}`} className="inline-flex items-center justify-center rounded-lg border border-rose-200 bg-rose-50 p-1.5 text-rose-600 hover:bg-rose-100 disabled:opacity-60"><Trash2 size={15} /></button>}
                          {canPr && <span className="ml-auto inline-flex items-center gap-2"><button type="button" title="Одобрить" onClick={() => h.handleApprove(item.id)} disabled={h.busyKey === `approve-${item.id}`} className="inline-flex items-center justify-center rounded-lg border border-emerald-200 bg-emerald-50 p-2 text-emerald-600 hover:bg-emerald-100 disabled:opacity-60"><ThumbsUp size={18} /></button><button type="button" title="Отклонить" onClick={() => h.handleReject(item.id)} disabled={h.busyKey === `reject-${item.id}`} className="inline-flex items-center justify-center rounded-lg border border-rose-200 bg-rose-50 p-2 text-rose-600 hover:bg-rose-100 disabled:opacity-60"><ThumbsDown size={18} /></button></span>}
                        </div>
                      </div>
                    </div>

                    {(rowOpen || commentsOpen) && (
                      <div className="mt-4 rounded-xl border border-gray-100 bg-gray-50/80 p-4">
                        {rowOpen && (
                          <div className="space-y-3 text-xs text-gray-500">
                            <div className="grid grid-cols-1 gap-x-4 gap-y-2 sm:grid-cols-2">
                              <div><span className="text-gray-400">Решающий:</span> {(() => { const a = item.approver || item.assigned_to; if (!a) return <span className="text-gray-400">—</span>; const alink = userProfileLink(a as User, user?.id); const aname = displayUserName(a); return alink ? <Link href={alink} className="font-medium text-sky-700 hover:text-sky-800">{aname}</Link> : <span className="font-medium text-gray-700">{aname}</span>; })()}</div>
                              <div><span className="text-gray-400">Создано:</span> <span className="font-medium text-gray-700">{formatDate(item.created_at) || "—"}</span></div>
                              <div><span className="text-gray-400">Обновлено:</span> <span className="font-medium text-gray-700">{formatDate(item.updated_at) || "—"}</span></div>
                              {deptLabels && <div className="sm:col-span-2"><span className="text-gray-400">Отделы:</span> <span className="font-medium text-gray-700">{deptLabels}</span></div>}
                            </div>
                            <div className="space-y-2">
                              <div className="flex flex-wrap items-start gap-2"><span className="pt-1 text-gray-400">Получатели:</span><div className="flex min-w-0 flex-1 flex-wrap gap-1.5">{recs.slice(0,2).map((r) => { const rl = userProfileLink(r, user?.id); const rn = displayUserName(r); const c = <>{r.avatar ? <img src={r.avatar} alt={rn} className="h-5 w-5 shrink-0 rounded-full object-cover ring-1 ring-gray-200" /> : <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-sky-100 text-[10px] font-semibold text-sky-700 ring-1 ring-sky-200">{(r.first_name?.[0] || r.last_name?.[0] || "?").toUpperCase()}</span>}<span className="max-w-[140px] truncate">{rn}</span></>; return rl ? <Link key={r.id} href={rl} className="inline-flex items-center gap-1.5 rounded-full bg-gray-100 px-2 py-1 font-medium text-gray-700 ring-1 ring-gray-200 hover:bg-gray-200">{c}</Link> : <span key={r.id} className="inline-flex items-center gap-1.5 rounded-full bg-gray-100 px-2 py-1 font-medium text-gray-700 ring-1 ring-gray-200">{c}</span>; })}{recs.length === 0 && <span className="pt-1 text-gray-400">{item.recipient_count ?? 0}</span>}{recs.length > 2 && <span className="inline-flex items-center rounded-full bg-gray-100 px-2 py-1 font-medium text-gray-600 ring-1 ring-gray-200">+{recs.length - 2}</span>}</div></div>
                              <div className="flex flex-wrap items-start gap-2"><span className="pt-1 text-gray-400">В копии:</span><div className="flex min-w-0 flex-1 flex-wrap gap-1.5">{ccs.slice(0,2).map((c) => { const cl = userProfileLink(c, user?.id); const cn = displayUserName(c); const ch = <>{c.avatar ? <img src={c.avatar} alt={cn} className="h-5 w-5 shrink-0 rounded-full object-cover ring-1 ring-gray-200" /> : <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-sky-100 text-[10px] font-semibold text-sky-700 ring-1 ring-sky-200">{(c.first_name?.[0] || c.last_name?.[0] || "?").toUpperCase()}</span>}<span className="max-w-[140px] truncate">{cn}</span></>; return cl ? <Link key={c.id} href={cl} className="inline-flex items-center gap-1.5 rounded-full bg-gray-100 px-2 py-1 font-medium text-gray-700 ring-1 ring-gray-200 hover:bg-gray-200">{ch}</Link> : <span key={c.id} className="inline-flex items-center gap-1.5 rounded-full bg-gray-100 px-2 py-1 font-medium text-gray-700 ring-1 ring-gray-200">{ch}</span>; })}{ccs.length === 0 && <span className="pt-1 text-gray-400">—</span>}{ccs.length > 2 && <span className="inline-flex items-center rounded-full bg-gray-100 px-2 py-1 font-medium text-gray-600 ring-1 ring-gray-200">+{ccs.length - 2}</span>}</div></div>
                              {(item.attachment || item.attachment_url) && <div className="flex min-w-0 items-center gap-1.5"><button type="button" onClick={() => { const url = item.attachment_url || item.attachment || ""; h.setAttachmentPreview({ url, name: decodeURIComponent(url.split("/").pop() || "Вложение") }); }} className="inline-flex min-w-0 max-w-full items-center gap-1.5 rounded-full bg-sky-50 px-2.5 py-1 text-sky-700 ring-1 ring-sky-100 hover:bg-sky-100"><Paperclip size={13} className="shrink-0" /><span className="truncate font-medium">{decodeURIComponent((item.attachment_url || item.attachment || "").split("/").pop() || "Вложение")}</span></button></div>}
                            </div>
                          </div>
                        )}
                        {commentsOpen && (
                          <div className={rowOpen ? "mt-3 rounded-lg border border-gray-200 bg-white p-3" : "rounded-lg border border-gray-200 bg-white p-3"}>
                            <div className="space-y-2">{comments.length === 0 ? <p className="text-xs text-gray-500">Комментариев пока нет</p> : comments.map((c) => (<div key={c.id} className="rounded-lg bg-white px-3 py-2 text-xs text-gray-700 ring-1 ring-gray-100"><div className="mb-1 flex items-center justify-between gap-2"><span className="font-medium">{displayUserName(c.author)}</span><div className="flex items-center gap-2"><span className="text-gray-500">{formatDate(c.created_at)}</span>{Boolean(c.author?.id && (user?.id === c.author.id || auth?.is_staff || auth?.is_superuser)) && <button type="button" onClick={() => h.handleDeleteComment(item.id, c.id)} className="text-rose-600 hover:text-rose-700">удалить</button>}</div></div><p>{c.text}</p></div>))}</div>
                            <div className="mt-2 flex items-center gap-2"><input value={h.commentDrafts[item.id] || ""} onChange={(e) => h.setCommentDrafts((p) => ({ ...p, [item.id]: e.target.value }))} placeholder="Добавить комментарий" className="flex-1 rounded-lg border border-gray-300 px-3 py-2 text-xs" /><button type="button" onClick={() => h.handleAddComment(item.id)} disabled={h.busyKey === `comment-${item.id}`} className="rounded-lg bg-sky-500 px-3 py-2 text-xs font-medium text-white hover:bg-sky-600 disabled:opacity-60">Отправить</button></div>
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                </article>
              );
            })}
          </div>

          {h.nextPage && <div ref={h.loadMoreRef} className="mt-4 flex justify-center py-4">{h.loadingMore && <div className="flex items-center gap-2 text-sm text-gray-500"><div className="h-4 w-4 animate-spin rounded-full border-2 border-gray-300 border-t-sky-500" /><span>Загрузка...</span></div>}</div>}
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
            <div className="space-y-5 text-sm text-gray-700">
              <div className="rounded-xl border border-gray-200 bg-gray-50 p-4"><div className="space-y-3"><div className="flex flex-wrap items-center gap-2"><span className="inline-flex rounded-full bg-sky-50 px-2.5 py-1 text-xs font-medium text-sky-700 ring-1 ring-sky-100">{dtl}</span><span className={`inline-flex rounded-full px-2.5 py-1 text-xs ring-1 ${ds.className}`}>{ds.label}</span></div><h2 className="break-words text-lg font-semibold text-gray-900">{dr.display_title || dr.title || "Без заголовка"}</h2>{(dr.comment || dr.description) ? <div className="mt-3 whitespace-pre-wrap break-words text-sm leading-relaxed text-gray-700">{dr.comment || dr.description}</div> : <p className="mt-3 text-sm text-gray-400">Описание отсутствует</p>}</div></div>
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                <div className="rounded-xl border border-gray-200 bg-white p-4"><p className="text-xs font-semibold uppercase tracking-wide text-gray-400">Даты</p><div className="mt-3 space-y-2"><div><p className="text-xs text-gray-400">Период</p><p className="mt-1 text-sm text-gray-900">{dr.date_from ? formatDate(dr.date_from) : "—"}{dr.date_to ? ` — ${formatDate(dr.date_to)}` : ""}</p></div><div><p className="text-xs text-gray-400">Создано</p><p className="mt-1 text-sm text-gray-900">{formatDate(dr.created_at) || "—"}</p></div><div><p className="text-xs text-gray-400">Обновлено</p><p className="mt-1 text-sm text-gray-900">{formatDate(dr.updated_at) || "—"}</p></div></div></div>
                <div className="rounded-xl border border-gray-200 bg-white p-4"><p className="text-xs font-semibold uppercase tracking-wide text-gray-400">Участники</p><div className="mt-3 space-y-3"><div><p className="text-xs text-gray-400">Автор</p><div className="mt-2 flex flex-wrap gap-2">{da ? renderUserBadge(da as User, true) : <span className="text-sm text-gray-400">—</span>}</div></div><div><p className="text-xs text-gray-400">Решающий</p><div className="mt-2 flex flex-wrap gap-2">{dap ? renderUserBadge(dap as User, true) : <span className="text-sm text-gray-400">—</span>}</div></div></div></div>
              </div>
              <div className="rounded-xl border border-gray-200 bg-white p-4"><p className="text-xs font-semibold uppercase tracking-wide text-gray-400">Отделы</p>{(dr.departments || []).length > 0 ? <div className="mt-3 flex flex-wrap gap-2">{(dr.departments || []).map((id) => <span key={id} className="inline-flex items-center rounded-full bg-gray-100 px-3 py-1.5 text-sm font-medium text-gray-700 ring-1 ring-gray-200">{h.departmentNameMap.get(Number(id)) || `Отдел #${id}`}</span>)}</div> : <p className="mt-3 text-sm text-gray-400">Отделы не указаны</p>}</div>
              <div className="rounded-xl border border-gray-200 bg-white p-4"><p className="text-xs font-semibold uppercase tracking-wide text-gray-400">Получатели</p>{(dr.recipients || []).length > 0 ? <div className="mt-3 flex flex-wrap gap-2">{(dr.recipients || []).map((r) => <div key={r.id}>{renderUserBadge(r, true)}</div>)}</div> : <p className="mt-3 text-sm text-gray-400">Получатели не указаны</p>}</div>
              <div className="rounded-xl border border-gray-200 bg-white p-4"><p className="text-xs font-semibold uppercase tracking-wide text-gray-400">В копии</p>{(dr.cc_users || []).length > 0 ? <div className="mt-3 flex flex-wrap gap-2">{(dr.cc_users || []).map((c) => <div key={c.id}>{renderUserBadge(c, true)}</div>)}</div> : <p className="mt-3 text-sm text-gray-400">Копия не указана</p>}</div>
              <div className="rounded-xl border border-gray-200 bg-white p-4"><p className="text-xs font-semibold uppercase tracking-wide text-gray-400">Вложение</p>{dau ? <div className="mt-3 flex flex-wrap items-center gap-3"><button type="button" onClick={() => h.setAttachmentPreview({ url: dau, name: dan })} className="inline-flex items-center gap-2 rounded-lg border border-sky-200 bg-sky-50 px-3 py-2 text-sm font-medium text-sky-700 hover:bg-sky-100"><Paperclip size={15} /><span className="break-all">{dan}</span></button><a href={dau} target="_blank" rel="noreferrer" className="text-sm font-medium text-sky-700 hover:text-sky-800 hover:underline">Открыть в новой вкладке</a></div> : <p className="mt-3 text-sm text-gray-400">Вложение отсутствует</p>}</div>
            </div>
          );
        })()}
      </Modal>

      {/* Create/Edit modal */}
      <Modal isOpen={h.isModalOpen} onClose={h.closeModal} title={h.modalMode === "create" ? "Новое заявление" : "Редактировать заявление"} size="md" footer={
            <div className="flex flex-wrap items-center justify-end gap-2">
              <button type="button" onClick={h.closeModal} className="rounded-lg bg-gray-200 px-3 py-2 text-sm font-medium text-gray-700 hover:bg-gray-300">Отмена</button>
              <button type="button" onClick={() => h.handleCreateOrUpdate(h.modalMode, "draft")} disabled={h.busyKey !== null} className="rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-60">Сохранить как черновик</button>
              <button type="button" onClick={() => h.handleCreateOrUpdate(h.modalMode, "submitted")} disabled={h.busyKey !== null} className="rounded-lg bg-sky-500 px-3 py-2 text-sm font-medium text-white hover:bg-sky-600 disabled:opacity-60">{h.modalMode === "create" ? "Создать" : "Сохранить"}</button>
            </div>
      }>
            {h.actionError && <p className="mb-3 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{h.actionError}</p>}
            <div className="flex flex-col gap-3">
              <div><label className="mb-1 block text-xs font-medium text-gray-500">Тема заявления</label><input value={h.form.title} onChange={(e) => h.setForm((p) => ({ ...p, title: e.target.value }))} placeholder="Тема заявления" className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-sky-400 focus:outline-none focus:ring-2 focus:ring-sky-100" /></div>
              <div><label className="mb-1 block text-xs font-medium text-gray-500">Тип заявления</label><select value={h.form.type} onChange={(e) => h.setForm((p) => ({ ...p, type: e.target.value }))} className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-sky-400 focus:outline-none focus:ring-2 focus:ring-sky-100"><option value="">Выберите тип</option>{Object.entries(requestTypeLabels).map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select></div>
              <div><label className="mb-1 block text-xs font-medium text-gray-500">Период</label><div className="flex items-center gap-2"><input type="date" value={h.form.date_from} onChange={(e) => h.setForm((p) => ({ ...p, date_from: e.target.value }))} className="flex-1 rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-sky-400 focus:outline-none focus:ring-2 focus:ring-sky-100" /><span className="text-xs text-gray-400">—</span><input type="date" value={h.form.date_to} onChange={(e) => h.setForm((p) => ({ ...p, date_to: e.target.value }))} className="flex-1 rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-sky-400 focus:outline-none focus:ring-2 focus:ring-sky-100" /></div></div>
              <SearchableSelectMulti label="Решающий" placeholder="Выберите решающего..." items={h.employees.filter((e) => !user?.id || e.id !== user.id).map((e) => ({ id: e.id, name: displayUserName(e) }))} selectedIds={h.form.recipient_ids} onToggle={(id) => h.setForm((p) => ({ ...p, recipient_ids: p.recipient_ids.includes(id) ? p.recipient_ids.filter((x) => x !== id) : [...p.recipient_ids, id] }))} />
              <SearchableSelectMulti label="В копии" placeholder="Выберите пользователей..." items={h.employees.filter((e) => !user?.id || e.id !== user.id).map((e) => ({ id: e.id, name: displayUserName(e) }))} selectedIds={h.form.cc_user_ids} onToggle={(id) => h.setForm((p) => ({ ...p, cc_user_ids: p.cc_user_ids.includes(id) ? p.cc_user_ids.filter((x) => x !== id) : [...p.cc_user_ids, id] }))} />
              <SearchableSelectMulti label="Отдел" placeholder="Выберите отдел..." items={h.departments.map((d) => ({ id: d.id, name: d.name }))} selectedIds={h.form.department_ids} onToggle={(id) => h.setForm((p) => ({ ...p, department_ids: p.department_ids.includes(id) ? p.department_ids.filter((x) => x !== id) : [...p.department_ids, id] }))} />
              <div><label className="mb-1 block text-xs font-medium text-gray-500">Описание</label><textarea value={h.form.comment} onChange={(e) => h.setForm((p) => ({ ...p, comment: e.target.value }))} placeholder="Описание заявления" rows={3} className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-sky-400 focus:outline-none focus:ring-2 focus:ring-sky-100" /></div>
              <div><input ref={fileInputRef} type="file" accept=".pdf,.jpg,.jpeg,.png" className="hidden" onChange={(e) => { const f = e.target.files?.[0] || null; if (f) { const ext = f.name.split(".").pop()?.toLowerCase() || ""; if (!["pdf","jpg","jpeg","png"].includes(ext)) return; } h.setForm((p) => ({ ...p, attachment: f })); }} /><button type="button" onClick={() => fileInputRef.current?.click()} className="inline-flex items-center gap-1.5 rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm text-gray-600 hover:bg-gray-50"><Paperclip size={14} />{h.form.attachment ? h.form.attachment.name : "Прикрепить файл"}</button></div>
              <label className="flex items-center gap-2 text-sm text-gray-700"><input type="checkbox" checked={h.form.sent_to_all_department} onChange={(e) => h.setForm((p) => ({ ...p, sent_to_all_department: e.target.checked }))} className="rounded border-gray-300" />Отправить всем сотрудникам выбранных отделов</label>
            </div>
      </Modal>

      {/* Attachment preview */}
      {h.attachmentPreview && (() => {
        const apUrl = h.attachmentPreview.url;
        const apName = h.attachmentPreview.name;
        return (
        <Modal isOpen onClose={() => h.setAttachmentPreview(null)} title={apName} size="lg" footer={<a href={apUrl} download className="rounded-lg border border-gray-300 px-3 py-1.5 text-xs font-medium text-gray-700 hover:bg-gray-50">Скачать</a>}>
            <div className="flex-1 overflow-auto">{(() => { const ext = apUrl.split(".").pop()?.toLowerCase() || ""; if (["jpg","jpeg","png","gif","webp","svg","bmp"].includes(ext)) return <img src={apUrl} alt={apName} className="mx-auto max-h-[70vh] rounded-lg object-contain" />; if (["mp4","webm","ogg","mov"].includes(ext)) return <video src={apUrl} controls className="mx-auto max-h-[70vh] rounded-lg" />; if (["mp3","wav","aac"].includes(ext)) return <audio src={apUrl} controls className="mx-auto mt-8" />; return <div className="flex flex-col items-center gap-3 py-12 text-center"><FileSignature size={40} className="text-gray-300" /><p className="text-sm text-gray-500">{apName}</p><a href={apUrl} download className="rounded-lg bg-sky-500 px-4 py-2 text-sm font-medium text-white hover:bg-sky-600">Скачать файл</a></div>; })()}</div>
        </Modal>
        );
      })()}
    </AppShell>
  );
}
