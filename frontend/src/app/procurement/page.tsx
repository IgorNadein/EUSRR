"use client";

import { AppShell } from "../../components/AppShell";
import { apiClient } from "@/lib/api";
import { useUser } from "@/contexts/UserContext";
import { canManageRequests } from "@/lib/permissions";
import { useEffect, useMemo, useRef, useState, useCallback } from "react";
import Link from "next/link";
import type {
  ProcurementRequest,
  ProcurementItem,
  User,
  Department,
  UrgencyLevel,
  ProcurementStatus,
} from "@/types/api";
import {
  AlertTriangle,
  ArrowUpDown,
  Check,
  ChevronDown,
  ChevronUp,
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

type ScopeTab = "all" | "mine" | "pending_approvals" | "available";
const scopeTabs: { value: ScopeTab; label: string }[] = [
  { value: "all",               label: "Все" },
  { value: "mine",              label: "Мои" },
  { value: "pending_approvals", label: "На согласование" },
  { value: "available",         label: "Доступные" },
];

function fmt(d?: string | null) {
  if (!d) return "";
  const dt = new Date(d);
  return Number.isNaN(dt.getTime()) ? "" : dt.toLocaleDateString("ru-RU", { day: "2-digit", month: "2-digit", year: "numeric" });
}

function money(v?: string | number | null) {
  if (v === null || v === undefined || v === "") return "—";
  return Number(v).toLocaleString("ru-RU", { minimumFractionDigits: 2, maximumFractionDigits: 2 }) + " ₽";
}

/* ══════════════════════════════════════════════════════
   Item row (позиция заявки) — for inline editing
   ══════════════════════════════════════════════════════ */

type ItemDraft = {
  name: string;
  description: string;
  quantity: string;
  unit: string;
  estimated_unit_price: string;
  supplier_info: string;
};

const emptyItem: ItemDraft = { name: "", description: "", quantity: "1", unit: "шт", estimated_unit_price: "", supplier_info: "" };

/* ══════════════════════════════════════════════════════
   Form state
   ══════════════════════════════════════════════════════ */

type FormState = {
  title: string;
  description: string;
  department: number | null;
  urgency: UrgencyLevel;
  items: ItemDraft[];
};

const emptyForm: FormState = {
  title: "",
  description: "",
  department: null,
  urgency: "medium",
  items: [{ ...emptyItem }],
};

/* ══════════════════════════════════════════════════════
   Main page component
   ══════════════════════════════════════════════════════ */

export default function ProcurementPage() {
  const { user } = useUser();
  const canManage = canManageRequests(user);

  /* ── data ── */
  const [requests, setRequests] = useState<ProcurementRequest[]>([]);
  const [departments, setDepartments] = useState<Department[]>([]);

  /* ── UI flags ── */
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [actionSuccess, setActionSuccess] = useState<string | null>(null);
  const [busyKey, setBusyKey] = useState<string | null>(null);
  const [nextPage, setNextPage] = useState<number | null>(null);

  /* ── scope / filters ── */
  const [scope, setScope] = useState<ScopeTab>("all");
  const [searchQuery, setSearchQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [urgencyFilter, setUrgencyFilter] = useState("");
  const [departmentFilter, setDepartmentFilter] = useState("");
  const [filtersOpen, setFiltersOpen] = useState(false);
  const [ordering, setOrdering] = useState("-created_at");

  /* ── form modal ── */
  const [createOpen, setCreateOpen] = useState(false);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [form, setForm] = useState<FormState>(emptyForm);

  /* ── expanded details ── */
  const [expandedIds, setExpandedIds] = useState<Set<number>>(new Set());
  const [detailsCache, setDetailsCache] = useState<Record<number, ProcurementRequest>>({});

  /* ══════════ helpers ══════════ */

  const displayUserName = (person?: User | null) => {
    if (!person) return "—";
    const full = `${person.last_name || ""} ${person.first_name || ""}`.trim();
    return full || (person as any)?.full_name || person.email || "Пользователь";
  };

  const userLink = (person?: User | null) => {
    if (!person?.id) return "";
    return user?.id && person.id === user.id ? "/profile" : `/users/${person.id}`;
  };

  const extractNextPage = (nextUrl?: string | null): number | null => {
    if (!nextUrl) return null;
    try {
      const u = new URL(nextUrl, window.location.origin);
      const n = Number(u.searchParams.get("page"));
      return Number.isFinite(n) && n > 0 ? n : null;
    } catch { return null; }
  };

  const getDeptName = (req: ProcurementRequest) => {
    if (req.department_name) return req.department_name;
    if (req.department_details?.name) return req.department_details.name;
    const d = departments.find((dep) => dep.id === Number(req.department));
    return d?.name || "—";
  };

  /* ══════════ data loading ══════════ */

  const buildParams = useCallback((page: number): Record<string, string | number> => {
    const p: Record<string, string | number> = { page };
    if (scope === "mine") p.scope = "mine";
    else if (scope === "available") p.scope = "available";
    if (statusFilter) p.status = statusFilter;
    if (urgencyFilter) p.urgency = urgencyFilter;
    if (departmentFilter) p.department = departmentFilter;
    if (searchQuery.trim()) p.search = searchQuery.trim();
    return p;
  }, [scope, statusFilter, urgencyFilter, departmentFilter, searchQuery]);

  const loadPage1 = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);

      let res: any;
      if (scope === "pending_approvals") {
        res = await apiClient.getPendingApprovals(buildParams(1));
      } else {
        res = await apiClient.getProcurementRequests(buildParams(1));
      }
      const results = Array.isArray(res) ? res : (res.results || []);
      setRequests(results);
      setNextPage(extractNextPage(res.next));
    } catch (e: any) {
      console.error("Load procurement error:", e);
      setError("Не удалось загрузить заявки на закупку");
    } finally {
      setLoading(false);
    }
  }, [buildParams, scope]);

  useEffect(() => { loadPage1(); }, [loadPage1]);

  // Load departments once
  useEffect(() => {
    (async () => {
      try {
        const all: Department[] = [];
        let pg = 1;
        while (true) {
          const res = await apiClient.getDepartments({ page: pg, limit: 200 });
          const chunk = Array.isArray(res) ? res : (res.results || []);
          all.push(...chunk);
          if (Array.isArray(res) || !res.next) break;
          pg++;
        }
        setDepartments(all);
      } catch { /* silent */ }
    })();
  }, []);

  /* ══════════ load more ══════════ */

  const handleLoadMore = async () => {
    if (!nextPage || loadingMore) return;
    try {
      setLoadingMore(true);
      let res: any;
      if (scope === "pending_approvals") {
        res = await apiClient.getPendingApprovals(buildParams(nextPage));
      } else {
        res = await apiClient.getProcurementRequests(buildParams(nextPage));
      }
      const chunk = Array.isArray(res) ? res : (res.results || []);
      setRequests((prev) => {
        const known = new Set(prev.map((r) => r.id));
        return [...prev, ...chunk.filter((r: ProcurementRequest) => !known.has(r.id))];
      });
      setNextPage(extractNextPage(res.next));
    } catch {
      setError("Не удалось загрузить ещё");
    } finally {
      setLoadingMore(false);
    }
  };

  /* ══════════ expand detail ══════════ */

  const toggleExpand = async (id: number) => {
    setExpandedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) { next.delete(id); } else { next.add(id); }
      return next;
    });
    if (!detailsCache[id]) {
      try {
        const detail = await apiClient.getProcurementRequest(id);
        setDetailsCache((p) => ({ ...p, [id]: detail }));
      } catch { /* silent */ }
    }
  };

  /* ══════════ client-side filter ══════════ */

  const filteredRequests = useMemo(() => {
    const urgencyRank: Record<string, number> = {
      low: 1,
      medium: 2,
      high: 3,
      critical: 4,
    };

    return [...requests].sort((a, b) => {
      switch (ordering) {
        case "created_at":
          return (new Date(a.created_at).getTime() || 0) - (new Date(b.created_at).getTime() || 0);
        case "title":
          return String(a.title || "").localeCompare(String(b.title || ""), "ru", { sensitivity: "base" });
        case "urgency":
          return (urgencyRank[a.urgency || "medium"] || 0) - (urgencyRank[b.urgency || "medium"] || 0);
        case "-urgency":
          return (urgencyRank[b.urgency || "medium"] || 0) - (urgencyRank[a.urgency || "medium"] || 0);
        case "-created_at":
        default:
          return (new Date(b.created_at).getTime() || 0) - (new Date(a.created_at).getTime() || 0);
      }
    });
  }, [ordering, requests]);

  /* ══════════ form ══════════ */

  const resetForm = () => setForm({ ...emptyForm, items: [{ ...emptyItem }] });

  const openCreate = () => {
    setEditingId(null);
    resetForm();
    setActionError(null);
    setActionSuccess(null);
    setCreateOpen(true);
  };

  const openEdit = (req: ProcurementRequest) => {
    setCreateOpen(false);
    setEditingId(req.id);
    setActionError(null);
    setActionSuccess(null);
    const detail = detailsCache[req.id] || req;
    setForm({
      title: detail.title || "",
      description: detail.description || "",
      department: detail.department ?? null,
      urgency: detail.urgency || "medium",
      items: (detail.items && detail.items.length > 0)
        ? detail.items.map((it) => ({
            name: it.name || "",
            description: it.description || "",
            quantity: String(it.quantity || "1"),
            unit: it.unit || "шт",
            estimated_unit_price: String(it.estimated_unit_price || ""),
            supplier_info: it.supplier_info || "",
          }))
        : [{ ...emptyItem }],
    });
  };

  const closeModal = () => {
    setCreateOpen(false);
    setEditingId(null);
    resetForm();
    setActionError(null);
  };

  const modalMode: "create" | "edit" = editingId ? "edit" : "create";
  const isModalOpen = createOpen || editingId !== null;

  /* ── save ── */
  const handleSave = async () => {
    try {
      setBusyKey("save");
      setActionError(null);

      if (!form.title.trim()) { setActionError("Укажите название заявки."); return; }
      if (!form.description.trim()) { setActionError("Укажите описание и обоснование."); return; }
      if (!form.department) { setActionError("Выберите отдел."); return; }

      // Filter out empty item rows
      const validItems = form.items.filter((it) => it.name.trim());
      if (validItems.length === 0) { setActionError("Добавьте хотя бы одну позицию."); return; }
      for (const it of validItems) {
        if (!it.quantity || Number(it.quantity) <= 0) { setActionError(`Позиция «${it.name}»: укажите количество.`); return; }
        if (!it.estimated_unit_price || Number(it.estimated_unit_price) <= 0) { setActionError(`Позиция «${it.name}»: укажите цену за единицу.`); return; }
      }

      const payload: any = {
        title: form.title,
        description: form.description,
        department: form.department,
        urgency: form.urgency,
        items: validItems.map((it) => ({
          name: it.name,
          description: it.description || undefined,
          quantity: it.quantity,
          unit: it.unit || "шт",
          estimated_unit_price: it.estimated_unit_price,
          supplier_info: it.supplier_info || undefined,
        })),
      };

      if (modalMode === "create") {
        await apiClient.createProcurementRequest(payload);
        setActionSuccess("Заявка создана (черновик).");
        setCreateOpen(false);
      } else if (editingId) {
        await apiClient.updateProcurementRequest(editingId, {
          title: payload.title,
          description: payload.description,
          urgency: payload.urgency,
        });
        setActionSuccess("Заявка обновлена.");
        setEditingId(null);
      }

      resetForm();
      await loadPage1();
    } catch (e: any) {
      const raw = String(e?.message || "Ошибка сохранения");
      let readable = raw;
      try {
        const parsed = JSON.parse(raw);
        readable = Object.entries(parsed).map(([k, v]) => `${k}: ${Array.isArray(v) ? v.join(", ") : v}`).join(". ");
      } catch { /* keep raw */ }
      setActionError(readable);
    } finally {
      setBusyKey(null);
    }
  };

  /* ══════════ workflow actions ══════════ */

  const refreshOne = async (id: number) => {
    try {
      const updated = await apiClient.getProcurementRequest(id);
      setRequests((prev) => prev.map((r) => (r.id === id ? updated : r)));
      setDetailsCache((p) => ({ ...p, [id]: updated }));
    } catch { /* reload all */ await loadPage1(); }
  };

  const doAction = async (key: string, fn: () => Promise<any>, id: number, successMsg: string) => {
    try {
      setBusyKey(key);
      setActionError(null);
      await fn();
      setActionSuccess(successMsg);
      await refreshOne(id);
    } catch (e: any) {
      const raw = String(e?.message || "Ошибка");
      let readable = raw;
      try { const p = JSON.parse(raw); readable = typeof p === "object" ? Object.entries(p).map(([k, v]) => `${k}: ${Array.isArray(v) ? v.join(", ") : v}`).join(". ") : raw; } catch {}
      setActionError(readable);
    } finally {
      setBusyKey(null);
    }
  };

  const handleSubmit  = (id: number) => doAction(`submit-${id}`,  () => apiClient.submitProcurementRequest(id),  id, "Заявка отправлена на согласование.");
  const handleApprove = (id: number) => doAction(`approve-${id}`, () => apiClient.approveProcurementRequest(id), id, "Заявка одобрена.");
  const handleReject  = (id: number) => doAction(`reject-${id}`,  () => apiClient.rejectProcurementRequest(id),  id, "Заявка отклонена.");
  const handleStart   = (id: number) => doAction(`start-${id}`,   () => apiClient.startWorkProcurementRequest(id), id, "Вы взяли заявку в работу.");
  const handleComplete= (id: number) => doAction(`complete-${id}`,() => apiClient.completeProcurementRequest(id), id, "Заявка завершена.");
  const handleCancel  = (id: number) => doAction(`cancel-${id}`,  () => apiClient.cancelProcurementRequest(id),  id, "Заявка отменена.");

  const handleDelete = async (id: number) => {
    if (!confirm("Удалить эту заявку? Доступно только для черновиков.")) return;
    try {
      setBusyKey(`delete-${id}`);
      await apiClient.deleteProcurementRequest(id);
      setRequests((p) => p.filter((r) => r.id !== id));
    } catch (e: any) {
      setActionError(String(e?.message || "Не удалось удалить"));
    } finally {
      setBusyKey(null);
    }
  };

  /* ══════════ form helpers ══════════ */

  const addItemRow = () => setForm((f) => ({ ...f, items: [...f.items, { ...emptyItem }] }));
  const removeItemRow = (idx: number) => setForm((f) => ({ ...f, items: f.items.filter((_, i) => i !== idx) }));
  const updateItemRow = (idx: number, patch: Partial<ItemDraft>) =>
    setForm((f) => ({ ...f, items: f.items.map((it, i) => (i === idx ? { ...it, ...patch } : it)) }));

  /* ══════════ SearchableSelect ══════════ */

  const SearchableSelectSingle = ({ label, items: selectItems, selectedId, onSelect, placeholder }: {
    label: string;
    items: { id: number; name: string }[];
    selectedId: number | null;
    onSelect: (id: number | null) => void;
    placeholder?: string;
  }) => {
    const [open, setOpen] = useState(false);
    const [q, setQ] = useState("");
    const ref = useRef<HTMLDivElement>(null);

    useEffect(() => {
      const handler = (e: MouseEvent) => { if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false); };
      document.addEventListener("mousedown", handler);
      return () => document.removeEventListener("mousedown", handler);
    }, []);

    const filtered = selectItems.filter((i) => i.name.toLowerCase().includes(q.toLowerCase()));
    const selectedName = selectItems.find((i) => i.id === selectedId)?.name;

    return (
      <div ref={ref} className="relative">
        <label className="mb-1 block text-xs font-medium text-gray-500">{label}</label>
        <button type="button" onClick={() => setOpen((v) => !v)} className="flex w-full items-center justify-between rounded-lg border border-gray-300 bg-white px-3 py-2 text-left text-sm text-gray-800">
          <span className="truncate">{selectedName || <span className="text-gray-400">{placeholder || "Выбрать..."}</span>}</span>
          <ChevronDown size={14} className={`ml-2 shrink-0 text-gray-400 transition ${open ? "rotate-180" : ""}`} />
        </button>
        {open && (
          <div className="absolute z-50 mt-1 max-h-56 w-full overflow-hidden rounded-lg border border-gray-200 bg-white shadow-lg">
            <div className="border-b border-gray-100 p-2">
              <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Поиск..." className="w-full rounded border border-gray-200 px-2 py-1.5 text-sm focus:border-sky-400 focus:outline-none" autoFocus />
            </div>
            <div className="max-h-40 overflow-y-auto p-1">
              {selectedId && (
                <button type="button" onClick={() => { onSelect(null); setOpen(false); }} className="flex w-full items-center gap-2 rounded px-2 py-1.5 text-sm text-gray-400 hover:bg-gray-50">Сбросить</button>
              )}
              {filtered.length === 0 ? (
                <p className="px-2 py-1.5 text-xs text-gray-400">Ничего не найдено</p>
              ) : filtered.map((item) => (
                <button key={item.id} type="button" onClick={() => { onSelect(item.id); setOpen(false); }} className={`flex w-full items-center gap-2 rounded px-2 py-1.5 text-sm hover:bg-gray-50 ${selectedId === item.id ? "bg-sky-50 text-sky-700 font-medium" : ""}`}>
                  {item.name}
                </button>
              ))}
            </div>
          </div>
        )}
      </div>
    );
  };

  const activeFilterCount = [statusFilter, urgencyFilter, departmentFilter].filter(Boolean).length;
  const isFinal = (s?: string) => ["completed", "rejected", "cancelled"].includes(String(s || "").toLowerCase());

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
            <p className="text-sm font-semibold uppercase tracking-wide text-gray-500">Закупки</p>
            <button type="button" onClick={openCreate} className="inline-flex items-center gap-1 rounded-lg bg-sky-500 px-3 py-2 text-sm font-medium text-white transition hover:bg-sky-600">
              <Plus size={14} /> Создать заявку
            </button>
          </div>

          {/* ── alerts ── */}
          {actionError && <p className="mb-3 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{actionError}</p>}
          {actionSuccess && <p className="mb-3 rounded-lg bg-emerald-50 px-3 py-2 text-sm text-emerald-700">{actionSuccess}</p>}

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
              {activeFilterCount > 0 && (
                <button type="button" onClick={() => { setStatusFilter(""); setUrgencyFilter(""); setDepartmentFilter(""); }} className="rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm font-medium text-gray-600 hover:bg-gray-100 transition">
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
              const isAuthor = Boolean(req.requestor?.id && user?.id && req.requestor.id === user.id);
              const isExecutor = Boolean(req.executor?.id && user?.id && req.executor.id === user.id);
              const isDraft = st === "draft";
              const isPending = st === "pending";
              const isApproved = st === "approved";
              const isInProgress = st === "in_progress";
              const expanded = expandedIds.has(req.id);
              const detail = detailsCache[req.id];
              const resolvedDetail = detail || req;
              const requestorName = displayUserName(req.requestor);
              const executorName = req.executor ? displayUserName(req.executor) : "";
              const requestorLink = userLink(req.requestor);
              const executorLink = userLink(req.executor);
              const itemsCount = detail?.items?.length ?? 0;
              const approvalsCount = detail?.approvals?.length ?? 0;

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
                              {req.total_estimated_cost && <span className="font-medium text-gray-700">{money(req.total_estimated_cost)}</span>}
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
                      <p className="text-sm font-medium text-gray-700">{money(req.total_estimated_cost)}</p>
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
                                  <span className="font-medium text-gray-700">{displayUserName(a.approver)}</span>
                                  <span className="text-gray-400">({a.role === "department_head" ? "Руководитель" : a.role === "finance_manager" ? "Финансист" : "Директор"})</span>
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
        </section>
      )}

      {/* ══════════ Create / Edit modal ══════════ */}
      {isModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4" onClick={(e) => { if (e.target === e.currentTarget) closeModal(); }}>
          <div className="relative max-h-[90vh] w-full max-w-2xl overflow-y-auto rounded-2xl bg-white p-5 shadow-xl">
            <div className="mb-4 flex items-center justify-between">
              <h2 className="text-base font-semibold text-gray-900">{modalMode === "create" ? "Новая заявка на закупку" : "Редактировать заявку"}</h2>
              <button type="button" onClick={closeModal} className="rounded-lg p-1 text-gray-400 hover:bg-gray-100 hover:text-gray-600"><X size={18} /></button>
            </div>

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

            {/* ── modal buttons ── */}
            <div className="mt-5 flex flex-wrap items-center justify-end gap-2 border-t border-gray-100 pt-4">
              <button type="button" onClick={closeModal} className="rounded-lg bg-gray-200 px-3 py-2 text-sm font-medium text-gray-700 hover:bg-gray-300">Отмена</button>
              <button type="button" onClick={handleSave} disabled={busyKey === "save"} className="rounded-lg bg-sky-500 px-3 py-2 text-sm font-medium text-white hover:bg-sky-600 disabled:opacity-60">
                {modalMode === "create" ? "Создать черновик" : "Сохранить"}
              </button>
            </div>
          </div>
        </div>
      )}
    </AppShell>
  );
}
