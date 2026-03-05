"use client";

import { AppShell } from "../../components/AppShell";
import { apiClient } from "@/lib/api";
import { useUser } from "@/contexts/UserContext";
import { canManageRequests } from "@/lib/permissions";
import { useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import type { Equipment, EquipmentCategory, EquipmentComment, User, Department } from "@/types/api";
import { ChevronDown, Filter, MessageSquare, Monitor, Paperclip, Pencil, Plus, Search, Trash2, X, FileSignature } from "lucide-react";

/* ──── form state ──── */
type EquipmentFormState = {
  name: string;
  description: string;
  category: number | null;
  department: number | null;
  assigned_to: number | null;
  serial_number: string;
  purchase_date: string;
  purchase_cost: string;
  location: string;
  attachment: File | null;
};

const emptyForm: EquipmentFormState = {
  name: "",
  description: "",
  category: null,
  department: null,
  assigned_to: null,
  serial_number: "",
  purchase_date: "",
  purchase_cost: "",
  location: "",
  attachment: null,
};

/* ──── status badges ──── */
const statusMeta: Record<string, { label: string; className: string }> = {
  available:   { label: "Доступно",          className: "bg-emerald-50 text-emerald-700 ring-emerald-100" },
  in_use:      { label: "В использовании",   className: "bg-sky-50 text-sky-700 ring-sky-100" },
  maintenance: { label: "На обслуживании",   className: "bg-amber-50 text-amber-700 ring-amber-100" },
  retired:     { label: "Списано",           className: "bg-gray-100 text-gray-700 ring-gray-200" },
  broken:      { label: "Сломано",           className: "bg-rose-50 text-rose-700 ring-rose-100" },
};

const defaultStatusMeta = { label: "—", className: "bg-gray-50 text-gray-700 ring-gray-200" };

function formatDate(value?: string | null): string {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  return date.toLocaleDateString("ru-RU", { day: "2-digit", month: "2-digit", year: "numeric" });
}

/* ──── main page ──── */
export default function EquipmentPage() {
  const { user } = useUser();
  const [items, setItems] = useState<Equipment[]>([]);
  const [employees, setEmployees] = useState<User[]>([]);
  const [departments, setDepartments] = useState<Department[]>([]);
  const [categories, setCategories] = useState<EquipmentCategory[]>([]);
  const [commentsMap, setCommentsMap] = useState<Record<number, EquipmentComment[]>>({});
  const [expandedComments, setExpandedComments] = useState<Record<number, boolean>>({});
  const [commentDrafts, setCommentDrafts] = useState<Record<number, string>>({});

  const [createOpen, setCreateOpen] = useState(false);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [form, setForm] = useState<EquipmentFormState>(emptyForm);

  const [searchQuery, setSearch] = useState("");
  const [employeeFilter, setEmployeeFilter] = useState("");
  const [dateFromFilter, setDateFromFilter] = useState("");
  const [dateToFilter, setDateToFilter] = useState("");
  const [filtersOpen, setFiltersOpen] = useState(false);
  const [attachmentPreview, setAttachmentPreview] = useState<{ url: string; name: string } | null>(null);

  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [actionSuccess, setActionSuccess] = useState<string | null>(null);
  const [busyKey, setBusyKey] = useState<string | null>(null);
  const [nextPage, setNextPage] = useState<number | null>(null);

  const auth = user?.auth;
  const canManage = canManageRequests(user);

  /* ──── helpers ──── */
  const displayUserName = (person?: User | null) => {
    if (!person) return "—";
    const full = `${person.last_name || ""} ${person.first_name || ""}`.trim();
    return full || (person as any)?.full_name || (person as any)?.display_name || person.email || "Пользователь";
  };

  const userProfileLink = (person?: User | null) => {
    if (!person?.id) return "";
    if (user?.id && person.id === user.id) return "/profile";
    return `/users/${person.id}`;
  };

  const extractNextPage = (nextUrl?: string | null): number | null => {
    if (!nextUrl) return null;
    try {
      const parsed = new URL(nextUrl, window.location.origin);
      const num = Number(parsed.searchParams.get("page"));
      return Number.isFinite(num) && num > 0 ? num : null;
    } catch {
      return null;
    }
  };

  const buildParams = (page: number): Record<string, string | number> => {
    const p: Record<string, string | number> = { page };
    if (employeeFilter) p.assigned_to = employeeFilter;
    if (dateFromFilter) p.purchase_date_after = dateFromFilter;
    if (dateToFilter) p.purchase_date_before = dateToFilter;
    return p;
  };

  const getCategoryName = (eq: Equipment): string => {
    if (typeof eq.category === "object" && eq.category?.name) return eq.category.name;
    if (eq.category_name) return eq.category_name;
    const cat = categories.find((c) => c.id === Number(eq.category));
    return cat?.name || "—";
  };

  const getDepartmentName = (eq: Equipment): string => {
    if (eq.department_name) return eq.department_name;
    const dep = departments.find((d) => d.id === Number(eq.department));
    return dep?.name || "—";
  };

  const getAssignedUser = (eq: Equipment): User | null => {
    if (eq.assigned_to_details) return eq.assigned_to_details;
    if (typeof eq.assigned_to === "object" && eq.assigned_to) return eq.assigned_to as User;
    if (typeof eq.assigned_to === "number") {
      return employees.find((e) => e.id === eq.assigned_to) || null;
    }
    return null;
  };

  /* ──── load data ──── */
  useEffect(() => {
    (async () => {
      try {
        setLoading(true);
        setError(null);
        const res = await apiClient.getEquipment(buildParams(1));
        const results = Array.isArray(res) ? res : (res.results || []);
        setItems(results);
        setNextPage(extractNextPage(res.next));
      } catch (e: any) {
        console.error("Ошибка загрузки оборудования:", e);
        setError("Не удалось загрузить оборудование");
      } finally {
        setLoading(false);
      }
    })();
  }, [employeeFilter, dateFromFilter, dateToFilter]);

  useEffect(() => {
    async function loadAllPages<T extends { id: number }>(fetcher: (params: any) => Promise<any>): Promise<T[]> {
      const all: T[] = [];
      let page = 1;
      while (true) {
        const res = await fetcher({ page, limit: 200 });
        const results = Array.isArray(res) ? res : (res.results || []);
        all.push(...results);
        if (Array.isArray(res) || !res.next) break;
        page++;
      }
      return all;
    }

    (async () => {
      try {
        const [allEmployees, allDepartments, allCategories] = await Promise.all([
          loadAllPages<User>((p) => apiClient.getEmployees(p)),
          loadAllPages<Department>((p) => apiClient.getDepartments(p)),
          loadAllPages<EquipmentCategory>((p) => apiClient.getEquipmentCategories(p)),
        ]);
        setEmployees(allEmployees);
        setDepartments(allDepartments);
        setCategories(allCategories);
      } catch (e) {
        console.error("Ошибка загрузки справочников:", e);
      }
    })();
  }, []);

  /* ──── filtered ──── */
  const filteredItems = useMemo(() => {
    const q = searchQuery.trim().toLowerCase();
    const sorted = [...items].sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime());
    if (!q) return sorted;
    return sorted.filter((item) => {
      const name = (item.name || "").toLowerCase();
      const desc = (item.description || "").toLowerCase();
      const sn = (item.serial_number || "").toLowerCase();
      const assigned = displayUserName(getAssignedUser(item)).toLowerCase();
      const cat = getCategoryName(item).toLowerCase();
      return name.includes(q) || desc.includes(q) || sn.includes(q) || assigned.includes(q) || cat.includes(q);
    });
  }, [items, searchQuery, employees, categories, departments]);

  /* ──── form ──── */
  const resetForm = () => setForm(emptyForm);

  const openEdit = (eq: Equipment) => {
    setEditingId(eq.id);
    setCreateOpen(false);
    setActionError(null);
    setActionSuccess(null);
    setForm({
      name: eq.name || "",
      description: eq.description || "",
      category: typeof eq.category === "object" ? eq.category?.id ?? null : eq.category ?? null,
      department: eq.department ?? null,
      assigned_to: typeof eq.assigned_to === "object" ? (eq.assigned_to as User)?.id ?? null : (eq.assigned_to as number) ?? null,
      serial_number: eq.serial_number || "",
      purchase_date: eq.purchase_date || "",
      purchase_cost: String(eq.purchase_cost || ""),
      location: eq.location || "",
      attachment: null,
    });
  };

  const handleSave = async (mode: "create" | "edit") => {
    try {
      setBusyKey(`${mode}-save`);
      setActionError(null);
      setActionSuccess(null);

      if (!form.name.trim()) { setActionError("Укажите название оборудования."); return; }
      if (!form.category) { setActionError("Выберите категорию."); return; }
      if (!form.department) { setActionError("Выберите отдел."); return; }
      if (!form.purchase_date) { setActionError("Укажите дату покупки."); return; }
      if (!form.purchase_cost) { setActionError("Укажите стоимость."); return; }

      const payload: Record<string, any> = {
        name: form.name,
        description: form.description,
        category: form.category,
        department: form.department,
        purchase_date: form.purchase_date,
        purchase_cost: form.purchase_cost,
      };

      if (form.assigned_to) payload.assigned_to = form.assigned_to;
      if (form.serial_number) payload.serial_number = form.serial_number;
      if (form.location) payload.location = form.location;
      if (form.attachment) payload.attachment = form.attachment;

      if (mode === "create") {
        await apiClient.createEquipment(payload);
        setActionSuccess("Оборудование добавлено.");
        setCreateOpen(false);
      } else if (editingId) {
        await apiClient.updateEquipment(editingId, payload);
        setActionSuccess("Оборудование обновлено.");
        setEditingId(null);
      }

      resetForm();
      const res = await apiClient.getEquipment(buildParams(1));
      const results = Array.isArray(res) ? res : (res.results || []);
      setItems(results);
      setNextPage(extractNextPage(res.next));
    } catch (e: any) {
      const raw = String(e?.message || "Не удалось сохранить");
      let readable = raw;
      try {
        const parsed = JSON.parse(raw);
        readable = Object.entries(parsed).map(([key, val]) => `${key}: ${Array.isArray(val) ? val.join(", ") : val}`).join(". ");
      } catch {}
      setActionError(readable);
    } finally {
      setBusyKey(null);
    }
  };

  const handleLoadMore = async () => {
    if (!nextPage || loadingMore) return;
    try {
      setLoadingMore(true);
      const res = await apiClient.getEquipment(buildParams(nextPage));
      const chunk = Array.isArray(res) ? res : (res.results || []);
      setItems((prev) => {
        const known = new Set(prev.map((r) => r.id));
        return [...prev, ...chunk.filter((r: Equipment) => !known.has(r.id))];
      });
      setNextPage(extractNextPage(res.next));
    } catch {
      setError("Не удалось загрузить ещё");
    } finally {
      setLoadingMore(false);
    }
  };

  /* ──── actions ──── */
  const handleDelete = async (id: number) => {
    if (!confirm("Удалить это оборудование?")) return;
    try { setBusyKey(`delete-${id}`); await apiClient.deleteEquipment(id); setItems((p) => p.filter((r) => r.id !== id)); } catch { setActionError("Не удалось удалить"); } finally { setBusyKey(null); } };

  const toggleComments = async (eqId: number) => {
    const isOpen = Boolean(expandedComments[eqId]);
    setExpandedComments((p) => ({ ...p, [eqId]: !isOpen }));
    if (!isOpen && !commentsMap[eqId]) {
      try {
        const c = await apiClient.getEquipmentComments(eqId);
        setCommentsMap((p) => ({ ...p, [eqId]: Array.isArray(c) ? c : c.results || [] }));
      } catch {
        setCommentsMap((p) => ({ ...p, [eqId]: [] }));
      }
    }
  };

  const handleAddComment = async (eqId: number) => {
    const text = (commentDrafts[eqId] || "").trim();
    if (!text) return;
    try {
      setBusyKey(`comment-${eqId}`);
      const saved = await apiClient.addEquipmentComment(eqId, text);
      setCommentsMap((p) => ({ ...p, [eqId]: [...(p[eqId] || []), saved] }));
      setCommentDrafts((p) => ({ ...p, [eqId]: "" }));
    } catch {
      setActionError("Не удалось добавить комментарий");
    } finally {
      setBusyKey(null);
    }
  };

  const handleDeleteComment = async (eqId: number, commentId: number) => {
    try {
      setBusyKey(`comment-delete-${commentId}`);
      await apiClient.deleteEquipmentComment(eqId, commentId);
      setCommentsMap((p) => ({ ...p, [eqId]: (p[eqId] || []).filter((c) => c.id !== commentId) }));
    } catch {
      setActionError("Не удалось удалить комментарий");
    } finally {
      setBusyKey(null);
    }
  };

  const fileInputRef = useRef<HTMLInputElement>(null);

  /* ──── SearchableSelect (single) ──── */
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
      const handler = (e: MouseEvent) => {
        if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
      };
      document.addEventListener("mousedown", handler);
      return () => document.removeEventListener("mousedown", handler);
    }, []);

    const filtered = selectItems.filter((i) => i.name.toLowerCase().includes(q.toLowerCase()));
    const selectedName = selectItems.find((i) => i.id === selectedId)?.name;

    return (
      <div ref={ref} className="relative">
        <label className="mb-1 block text-xs font-medium text-gray-500">{label}</label>
        <button
          type="button"
          onClick={() => setOpen((v) => !v)}
          className="flex w-full items-center justify-between rounded-lg border border-gray-300 bg-white px-3 py-2 text-left text-sm text-gray-800"
        >
          <span className="truncate">
            {selectedName ? selectedName : <span className="text-gray-400">{placeholder || "Выбрать..."}</span>}
          </span>
          <ChevronDown size={14} className={`ml-2 shrink-0 text-gray-400 transition ${open ? "rotate-180" : ""}`} />
        </button>
        {open && (
          <div className="absolute z-50 mt-1 max-h-56 w-full overflow-hidden rounded-lg border border-gray-200 bg-white shadow-lg">
            <div className="border-b border-gray-100 p-2">
              <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Поиск..." className="w-full rounded border border-gray-200 px-2 py-1.5 text-sm focus:border-sky-400 focus:outline-none" autoFocus />
            </div>
            <div className="max-h-40 overflow-y-auto p-1">
              {selectedId && (
                <button type="button" onClick={() => { onSelect(null); setOpen(false); }} className="flex w-full items-center gap-2 rounded px-2 py-1.5 text-sm text-gray-400 hover:bg-gray-50">
                  Сбросить
                </button>
              )}
              {filtered.length === 0 ? (
                <p className="px-2 py-1.5 text-xs text-gray-400">Ничего не найдено</p>
              ) : (
                filtered.map((item) => (
                  <button
                    key={item.id}
                    type="button"
                    onClick={() => { onSelect(item.id); setOpen(false); }}
                    className={`flex w-full items-center gap-2 rounded px-2 py-1.5 text-sm hover:bg-gray-50 ${selectedId === item.id ? "bg-sky-50 text-sky-700 font-medium" : ""}`}
                  >
                    {item.name}
                  </button>
                ))
              )}
            </div>
          </div>
        )}
      </div>
    );
  };

  const modalMode: "create" | "edit" = editingId ? "edit" : "create";
  const isModalOpen = createOpen || editingId !== null;

  const closeModal = () => {
    setCreateOpen(false);
    setEditingId(null);
    resetForm();
    setActionError(null);
  };

  const activeFilterCount = [employeeFilter, dateFromFilter, dateToFilter].filter(Boolean).length;

  /* ──── render ──── */
  return (
    <AppShell>
      {loading ? (
        <div className="rounded-2xl bg-white p-8 text-center shadow-sm ring-1 ring-gray-100">
          <div className="mb-4 inline-block h-8 w-8 animate-spin rounded-full border-4 border-sky-400 border-t-transparent" />
          <p className="text-sm text-gray-500">Загрузка оборудования...</p>
        </div>
      ) : error ? (
        <div className="rounded-2xl bg-red-50 p-6 text-center">
          <p className="text-sm text-red-800">{error}</p>
        </div>
      ) : (
        <section className="rounded-2xl bg-white p-4 shadow-sm ring-1 ring-gray-100">
          {/* Header */}
          <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
            <p className="text-sm font-semibold uppercase tracking-wide text-gray-500">Оборудование</p>
            <button
              type="button"
              onClick={() => { setEditingId(null); resetForm(); setActionError(null); setActionSuccess(null); setCreateOpen(true); }}
              className="inline-flex items-center gap-1 rounded-lg bg-sky-500 px-3 py-2 text-sm font-medium text-white hover:bg-sky-600"
            >
              <Plus size={14} /> Добавить оборудование
            </button>
          </div>

          {actionError && <p className="mb-3 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{actionError}</p>}
          {actionSuccess && <p className="mb-3 rounded-lg bg-emerald-50 px-3 py-2 text-sm text-emerald-700">{actionSuccess}</p>}

          {/* Search + filter toggle */}
          <div className="mb-4 flex items-center gap-2">
            <div className="relative flex-1">
              <Search size={16} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
              <input
                value={searchQuery}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Поиск по оборудованию"
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
                <span className="absolute -right-1 -top-1 flex h-4 min-w-4 items-center justify-center rounded-full bg-sky-500 px-1 text-[10px] font-bold text-white">
                  {activeFilterCount}
                </span>
              )}
            </button>
          </div>

          {/* Filters panel */}
          {filtersOpen && (
            <div className="mb-3 flex flex-col gap-2 rounded-xl border border-gray-200 bg-gray-50 p-3">
              <select value={employeeFilter} onChange={(e) => setEmployeeFilter(e.target.value)} className="rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm text-gray-800">
                <option value="">Все сотрудники</option>
                {employees.map((emp) => (
                  <option key={emp.id} value={emp.id}>{displayUserName(emp)}</option>
                ))}
              </select>
              <div className="flex items-center gap-2">
                <input type="date" value={dateFromFilter} onChange={(e) => setDateFromFilter(e.target.value)} className="flex-1 rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm text-gray-800" placeholder="С" />
                <span className="text-xs text-gray-400">—</span>
                <input type="date" value={dateToFilter} onChange={(e) => setDateToFilter(e.target.value)} className="flex-1 rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm text-gray-800" placeholder="По" />
              </div>
              {activeFilterCount > 0 && (
                <button type="button" onClick={() => { setEmployeeFilter(""); setDateFromFilter(""); setDateToFilter(""); }} className="rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm font-medium text-gray-600 hover:bg-gray-100 transition">
                  Очистить фильтры
                </button>
              )}
            </div>
          )}

          {/* Items list */}
          <div className="space-y-3">
            {filteredItems.length === 0 ? (
              <div className="rounded-xl bg-gray-50 p-8 text-center">
                <Monitor size={22} className="mx-auto mb-2 text-gray-400" />
                <p className="text-sm text-gray-500">Записи об оборудовании не найдены</p>
              </div>
            ) : (
              filteredItems.map((item) => {
                const assignedUser = getAssignedUser(item);
                const assignedName = displayUserName(assignedUser);
                const assignedLink = userProfileLink(assignedUser);
                const statusKey = String(item.status || "").toLowerCase();
                const status = statusMeta[statusKey] ?? defaultStatusMeta;
                const isAuthor = Boolean(item.created_by?.id && user?.id && item.created_by.id === user.id);
                const canDeleteThis = isAuthor || canManage;
                const canEditThis = isAuthor || canManage;
                const comments = commentsMap[item.id] || [];
                const commentsOpen = Boolean(expandedComments[item.id]);

                return (
                  <article key={item.id} className="rounded-xl border border-gray-100 bg-white p-4 transition hover:bg-gray-50">
                    {/* Assigned user + purchase date */}
                    <div className="mb-2 flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        {assignedUser ? (
                          assignedLink ? (
                            <Link href={assignedLink} className="flex items-center gap-2 group">
                              {assignedUser.avatar ? (
                                <img src={assignedUser.avatar} alt={assignedName} className="h-8 w-8 rounded-full object-cover ring-1 ring-gray-200" />
                              ) : (
                                <span className="flex h-8 w-8 items-center justify-center rounded-full bg-sky-100 text-xs font-semibold text-sky-700 ring-1 ring-sky-200">
                                  {(assignedUser.first_name?.[0] || assignedUser.last_name?.[0] || "?").toUpperCase()}
                                </span>
                              )}
                              <span className="text-sm font-medium text-gray-800 group-hover:text-sky-700">{assignedName}</span>
                            </Link>
                          ) : (
                            <div className="flex items-center gap-2">
                              <span className="flex h-8 w-8 items-center justify-center rounded-full bg-sky-100 text-xs font-semibold text-sky-700 ring-1 ring-sky-200">
                                {(assignedUser.first_name?.[0] || assignedUser.last_name?.[0] || "?").toUpperCase()}
                              </span>
                              <span className="text-sm font-medium text-gray-800">{assignedName}</span>
                            </div>
                          )
                        ) : (
                          <span className="text-sm text-gray-400">Не назначено</span>
                        )}
                      </div>
                      <span className="text-xs text-gray-500">{formatDate(item.purchase_date)}</span>
                    </div>

                    {/* Name + status */}
                    <div className="flex items-start justify-between gap-3">
                      <p className="min-w-0 truncate text-sm font-semibold text-gray-900">{item.name || "Без названия"}</p>
                      {statusKey && <span className={`inline-flex shrink-0 rounded-full px-2.5 py-1 text-xs ring-1 ${status.className}`}>{status.label}</span>}
                    </div>

                    {/* Description */}
                    {item.description && (
                      <p className="mt-2 text-sm text-gray-700">{item.description}</p>
                    )}

                    {/* Meta */}
                    <div className="mt-3 flex flex-col gap-1.5 text-xs text-gray-500">
                      <p>Категория: {getCategoryName(item)}</p>
                      <p>Отдел: {getDepartmentName(item)}</p>
                      {item.serial_number && <p>Серийный номер: {item.serial_number}</p>}
                      {item.location && <p>Расположение: {item.location}</p>}
                      <p>Стоимость: {item.purchase_cost ? `${Number(item.purchase_cost).toLocaleString("ru-RU")} ₽` : "—"}</p>
                      <p>Добавлено: {formatDate(item.created_at)}</p>

                      {(item.image || item.attachment || item.attachment_url) && (
                        <div className="flex items-center gap-1.5 min-w-0">
                          <button type="button" onClick={() => {
                            const url = item.image || item.attachment_url || item.attachment || "";
                            const name = decodeURIComponent(url.split("/").pop() || "Вложение");
                            setAttachmentPreview({ url, name });
                          }} className="inline-flex items-center gap-1.5 min-w-0 max-w-full text-sky-700 hover:text-sky-800">
                            <Paperclip size={13} className="shrink-0" />
                            <span className="truncate font-medium underline decoration-sky-300 underline-offset-2">
                              {decodeURIComponent((item.image || item.attachment_url || item.attachment || "").split("/").pop() || "Вложение")}
                            </span>
                          </button>
                        </div>
                      )}
                    </div>

                    {/* Action buttons */}
                    <div className="mt-3 flex flex-wrap items-center gap-1.5">
                      <button type="button" title={`Комментарии (${(item as any).comments_count ?? comments.length})`} onClick={() => toggleComments(item.id)} className="relative inline-flex items-center justify-center rounded-lg border border-gray-300 bg-white p-1.5 text-gray-600 hover:bg-gray-50">
                        <MessageSquare size={15} />
                        {((item as any).comments_count ?? comments.length) > 0 && (
                          <span className="absolute -right-1.5 -top-1.5 flex h-4 min-w-4 items-center justify-center rounded-full bg-sky-500 px-1 text-[10px] font-bold text-white">{(item as any).comments_count ?? comments.length}</span>
                        )}
                      </button>
                      {canEditThis && (
                        <button type="button" title="Редактировать" onClick={() => openEdit(item)} className="inline-flex items-center justify-center rounded-lg border border-gray-300 bg-white p-1.5 text-gray-600 hover:bg-gray-50"><Pencil size={15} /></button>
                      )}
                      {canDeleteThis && (
                        <button type="button" title="Удалить" onClick={() => handleDelete(item.id)} disabled={busyKey === `delete-${item.id}`} className="inline-flex items-center justify-center rounded-lg border border-rose-200 bg-rose-50 p-1.5 text-rose-600 hover:bg-rose-100 disabled:opacity-60"><Trash2 size={15} /></button>
                      )}
                    </div>

                    {/* Comments */}
                    {commentsOpen && (
                      <div className="mt-3 rounded-lg border border-gray-200 bg-gray-50 p-3">
                        <div className="space-y-2">
                          {comments.length === 0 ? (
                            <p className="text-xs text-gray-500">Комментариев пока нет</p>
                          ) : (
                            comments.map((c) => {
                              const canDel = Boolean(c.author?.id && (user?.id === c.author.id || auth?.is_staff || auth?.is_superuser));
                              return (
                                <div key={c.id} className="rounded-lg bg-white px-3 py-2 text-xs text-gray-700 ring-1 ring-gray-100">
                                  <div className="mb-1 flex items-center justify-between gap-2">
                                    <span className="font-medium">{displayUserName(c.author)}</span>
                                    <div className="flex items-center gap-2">
                                      <span className="text-gray-500">{formatDate(c.created_at)}</span>
                                      {canDel && <button type="button" onClick={() => handleDeleteComment(item.id, c.id)} className="text-rose-600 hover:text-rose-700">удалить</button>}
                                    </div>
                                  </div>
                                  <p>{c.text}</p>
                                </div>
                              );
                            })
                          )}
                        </div>
                        <div className="mt-2 flex items-center gap-2">
                          <input value={commentDrafts[item.id] || ""} onChange={(e) => setCommentDrafts((p) => ({ ...p, [item.id]: e.target.value }))} placeholder="Добавить комментарий" className="flex-1 rounded-lg border border-gray-300 px-3 py-2 text-xs" />
                          <button type="button" onClick={() => handleAddComment(item.id)} disabled={busyKey === `comment-${item.id}`} className="rounded-lg bg-sky-500 px-3 py-2 text-xs font-medium text-white hover:bg-sky-600 disabled:opacity-60">Отправить</button>
                        </div>
                      </div>
                    )}
                  </article>
                );
              })
            )}
          </div>

          {/* Load more */}
          {nextPage && (
            <div className="mt-4 flex justify-center">
              <button type="button" onClick={handleLoadMore} disabled={loadingMore} className="rounded-lg border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-60">
                {loadingMore ? "Загружаем..." : "Загрузить ещё"}
              </button>
            </div>
          )}
        </section>
      )}

      {/* ===== Modal create/edit ===== */}
      {isModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4" onClick={(e) => { if (e.target === e.currentTarget) closeModal(); }}>
          <div className="relative max-h-[90vh] w-full max-w-lg overflow-y-auto rounded-2xl bg-white p-5 shadow-xl">
            <div className="mb-4 flex items-center justify-between">
              <h2 className="text-base font-semibold text-gray-900">{modalMode === "create" ? "Добавить оборудование" : "Редактировать оборудование"}</h2>
              <button type="button" onClick={closeModal} className="rounded-lg p-1 text-gray-400 hover:bg-gray-100 hover:text-gray-600"><X size={18} /></button>
            </div>

            {actionError && <p className="mb-3 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{actionError}</p>}

            <div className="flex flex-col gap-3">
              {/* Название */}
              <div>
                <label className="mb-1 block text-xs font-medium text-gray-500">Название оборудования *</label>
                <input
                  value={form.name}
                  onChange={(e) => setForm((p) => ({ ...p, name: e.target.value }))}
                  placeholder="Ноутбук Lenovo ThinkPad X1..."
                  className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-sky-400 focus:outline-none focus:ring-2 focus:ring-sky-100"
                />
              </div>

              {/* Категория */}
              <SearchableSelectSingle
                label="Категория *"
                placeholder="Выберите категорию..."
                items={categories.map((c) => ({ id: c.id, name: c.name }))}
                selectedId={form.category}
                onSelect={(id) => setForm((p) => ({ ...p, category: id }))}
              />

              {/* Отдел */}
              <SearchableSelectSingle
                label="Отдел *"
                placeholder="Выберите отдел..."
                items={departments.map((d) => ({ id: d.id, name: d.name }))}
                selectedId={form.department}
                onSelect={(id) => setForm((p) => ({ ...p, department: id }))}
              />

              {/* Кому выдано */}
              <SearchableSelectSingle
                label="Кому выдано"
                placeholder="Выберите сотрудника..."
                items={employees.map((emp) => ({ id: emp.id, name: displayUserName(emp) }))}
                selectedId={form.assigned_to}
                onSelect={(id) => setForm((p) => ({ ...p, assigned_to: id }))}
              />

              {/* Дата покупки + стоимость */}
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="mb-1 block text-xs font-medium text-gray-500">Дата покупки *</label>
                  <input
                    type="date"
                    value={form.purchase_date}
                    onChange={(e) => setForm((p) => ({ ...p, purchase_date: e.target.value }))}
                    className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-sky-400 focus:outline-none focus:ring-2 focus:ring-sky-100"
                  />
                </div>
                <div>
                  <label className="mb-1 block text-xs font-medium text-gray-500">Стоимость (₽) *</label>
                  <input
                    type="number"
                    step="0.01"
                    value={form.purchase_cost}
                    onChange={(e) => setForm((p) => ({ ...p, purchase_cost: e.target.value }))}
                    placeholder="0.00"
                    className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-sky-400 focus:outline-none focus:ring-2 focus:ring-sky-100"
                  />
                </div>
              </div>

              {/* Серийный номер */}
              <div>
                <label className="mb-1 block text-xs font-medium text-gray-500">Серийный номер</label>
                <input
                  value={form.serial_number}
                  onChange={(e) => setForm((p) => ({ ...p, serial_number: e.target.value }))}
                  placeholder="SN-XXXXX"
                  className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-sky-400 focus:outline-none focus:ring-2 focus:ring-sky-100"
                />
              </div>

              {/* Расположение */}
              <div>
                <label className="mb-1 block text-xs font-medium text-gray-500">Расположение</label>
                <input
                  value={form.location}
                  onChange={(e) => setForm((p) => ({ ...p, location: e.target.value }))}
                  placeholder="Офис 305, стол 2..."
                  className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-sky-400 focus:outline-none focus:ring-2 focus:ring-sky-100"
                />
              </div>

              {/* Описание */}
              <div>
                <label className="mb-1 block text-xs font-medium text-gray-500">Описание</label>
                <textarea
                  value={form.description}
                  onChange={(e) => setForm((p) => ({ ...p, description: e.target.value }))}
                  placeholder="Описание оборудования..."
                  rows={3}
                  className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-sky-400 focus:outline-none focus:ring-2 focus:ring-sky-100"
                />
              </div>

              {/* Фото */}
              <div>
                <input ref={fileInputRef} type="file" accept=".pdf,.jpg,.jpeg,.png" className="hidden" onChange={(e) => {
                  const file = e.target.files?.[0] || null;
                  if (file) {
                    const ext = file.name.split(".").pop()?.toLowerCase() || "";
                    if (!["pdf", "jpg", "jpeg", "png"].includes(ext)) { setActionError(`Файл «${file.name}» не поддерживается. Разрешены: PDF, JPG, PNG.`); e.target.value = ""; return; }
                  }
                  setForm((p) => ({ ...p, attachment: file }));
                }} />
                <button type="button" onClick={() => fileInputRef.current?.click()} className="inline-flex items-center gap-1.5 rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm text-gray-600 hover:bg-gray-50">
                  <Paperclip size={14} />
                  {form.attachment ? form.attachment.name : "Прикрепить фото"}
                </button>
              </div>
            </div>

            {/* Buttons */}
            <div className="mt-5 flex flex-wrap items-center justify-end gap-2 border-t border-gray-100 pt-4">
              <button type="button" onClick={closeModal} className="rounded-lg bg-gray-200 px-3 py-2 text-sm font-medium text-gray-700 hover:bg-gray-300">Отмена</button>
              <button type="button" onClick={() => handleSave(modalMode)} disabled={busyKey !== null} className="rounded-lg bg-sky-500 px-3 py-2 text-sm font-medium text-white hover:bg-sky-600 disabled:opacity-60">
                {modalMode === "create" ? "Добавить" : "Сохранить"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ===== Attachment preview ===== */}
      {attachmentPreview && (
        <div className="fixed inset-0 z-[60] flex items-center justify-center bg-black/50 p-4" onClick={(e) => { if (e.target === e.currentTarget) setAttachmentPreview(null); }}>
          <div className="relative flex max-h-[90vh] w-full max-w-3xl flex-col overflow-hidden rounded-2xl bg-white shadow-xl">
            <div className="flex items-center justify-between border-b border-gray-100 px-4 py-3">
              <p className="truncate text-sm font-medium text-gray-800">{attachmentPreview.name}</p>
              <div className="flex items-center gap-2">
                <a href={attachmentPreview.url} download className="rounded-lg border border-gray-300 px-3 py-1.5 text-xs font-medium text-gray-700 hover:bg-gray-50">Скачать</a>
                <button type="button" onClick={() => setAttachmentPreview(null)} className="rounded-lg p-1 text-gray-400 hover:bg-gray-100 hover:text-gray-600"><X size={18} /></button>
              </div>
            </div>
            <div className="flex-1 overflow-auto p-4">
              {(() => {
                const url = attachmentPreview.url;
                const ext = url.split(".").pop()?.toLowerCase() || "";
                const imageExts = ["jpg", "jpeg", "png", "gif", "webp", "svg", "bmp"];
                const fallback = (
                  <div className="flex flex-col items-center gap-3 py-12 text-center">
                    <FileSignature size={40} className="text-gray-300" />
                    <p className="text-sm text-gray-500">{attachmentPreview.name}</p>
                    <a href={url} download className="rounded-lg bg-sky-500 px-4 py-2 text-sm font-medium text-white hover:bg-sky-600">Скачать файл</a>
                  </div>
                );
                if (imageExts.includes(ext)) return <img src={url} alt={attachmentPreview.name} className="mx-auto max-h-[70vh] rounded-lg object-contain" />;
                return fallback;
              })()}
            </div>
          </div>
        </div>
      )}
    </AppShell>
  );
}
