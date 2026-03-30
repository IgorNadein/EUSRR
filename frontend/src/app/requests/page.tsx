"use client";

import { AppShell } from "../../components/AppShell";
import { apiClient } from "@/lib/api";
import { Modal } from "@/components/ui/Modal";
import { useUser } from "@/contexts/UserContext";
import { canManageRequests, canProcessRequests } from "@/lib/permissions";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import type { Request, RequestComment, User, Department } from "@/types/api";
import { ArrowUpDown, Ban, Check, ChevronDown, FileSignature, Filter, MessageSquare, Paperclip, Pencil, Plus, Search, ThumbsDown, ThumbsUp, Trash2, X, Zap } from "lucide-react";
import dynamic from "next/dynamic";

const SwipeApprovalMode = dynamic(() => import("@/components/requests/SwipeApprovalMode"), { ssr: false });

type RequestFormState = {
  type: string;
  title: string;
  date_from: string;
  date_to: string;
  comment: string;
  department_ids: number[];
  recipient_ids: number[];
  cc_user_ids: number[];
  sent_to_all_department: boolean;
  attachment: File | null;
};

const emptyForm: RequestFormState = {
  type: "",
  title: "",
  date_from: "",
  date_to: "",
  comment: "",
  department_ids: [],
  recipient_ids: [],
  cc_user_ids: [],
  sent_to_all_department: false,
  attachment: null,
};

const statusMeta: Record<string, { label: string; className: string }> = {
  draft: {
    label: "Черновик",
    className: "bg-slate-100 text-slate-700 ring-slate-200",
  },
  pending: {
    label: "На рассмотрении",
    className: "bg-amber-50 text-amber-700 ring-amber-100",
  },
  approved: {
    label: "Одобрено",
    className: "bg-emerald-50 text-emerald-700 ring-emerald-100",
  },
  rejected: {
    label: "Отклонено",
    className: "bg-rose-50 text-rose-700 ring-rose-100",
  },
  cancelled: {
    label: "Отменено",
    className: "bg-gray-100 text-gray-700 ring-gray-200",
  },
  in_progress: {
    label: "В работе",
    className: "bg-sky-50 text-sky-700 ring-sky-100",
  },
  completed: {
    label: "Завершено",
    className: "bg-violet-50 text-violet-700 ring-violet-100",
  },
};

const requestTypeLabels: Record<string, string> = {
  vacation: "Отпуск",
  sick_leave: "Больничный",
  day_off: "Отгул",
  transfer: "Перевод",
  dismissal: "Увольнение",
  other: "Другое",
};

const orderingOptions = [
  { value: "-created_at", label: "Сначала новые" },
  { value: "created_at", label: "Сначала старые" },
  { value: "title", label: "По названию" },
  { value: "date_from", label: "По периоду ↑" },
  { value: "-date_from", label: "По периоду ↓" },
];

const defaultStatusMeta = {
  label: "Неизвестный статус",
  className: "bg-gray-50 text-gray-700 ring-gray-200",
};

function formatDate(value?: string): string {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  return date.toLocaleDateString("ru-RU", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
  });
}

export default function RequestsPage() {
  const { user } = useUser();
  const [requests, setRequests] = useState<Request[]>([]);
  const [employees, setEmployees] = useState<User[]>([]);
  const [departments, setDepartments] = useState<Department[]>([]);
  const [commentsMap, setCommentsMap] = useState<Record<number, RequestComment[]>>({});
  const [expandedRows, setExpandedRows] = useState<Record<number, boolean>>({});
  const [expandedComments, setExpandedComments] = useState<Record<number, boolean>>({});
  const [commentDrafts, setCommentDrafts] = useState<Record<number, string>>({});

  const [createOpen, setCreateOpen] = useState(false);
  const [editingRequestId, setEditingRequestId] = useState<number | null>(null);
  const [form, setForm] = useState<RequestFormState>(emptyForm);

  const [search, setSearch] = useState("");
  const [view, setView] = useState<"" | "mine" | "addressed">("");
  const [typeFilter, setTypeFilter] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [employeeFilter, setEmployeeFilter] = useState("");
  const [createdFromFilter, setCreatedFromFilter] = useState("");
  const [createdToFilter, setCreatedToFilter] = useState("");
  const [periodFromFilter, setPeriodFromFilter] = useState("");
  const [periodToFilter, setPeriodToFilter] = useState("");
  const [filtersOpen, setFiltersOpen] = useState(false);
  const [ordering, setOrdering] = useState("-created_at");
  const [attachmentPreview, setAttachmentPreview] = useState<{ url: string; name: string } | null>(null);
  const [detailsRequest, setDetailsRequest] = useState<Request | null>(null);
  const [swipeMode, setSwipeMode] = useState(false);

  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [actionSuccess, setActionSuccess] = useState<string | null>(null);
  const [busyKey, setBusyKey] = useState<string | null>(null);
  const [nextPage, setNextPage] = useState<number | null>(null);

  const auth = user?.auth;
  const canProcess = canProcessRequests(user);
  const canManage = canManageRequests(user);

  const departmentNameMap = useMemo(
    () => new Map((departments || []).map((d) => [d.id, d.name])),
    [departments]
  );

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
      const rawPage = parsed.searchParams.get("page");
      const num = Number(rawPage);
      return Number.isFinite(num) && num > 0 ? num : null;
    } catch {
      return null;
    }
  };

  const buildRequestParams = (page: number): Record<string, string | number> => {
    const params: Record<string, string | number> = { page, limit: 20 };
    if (view === "mine") params.view = "mine";
    if (view === "addressed") params.addressed_to_me = "true";
    if (typeFilter) params.type = typeFilter;
    if (statusFilter) params.status = statusFilter;
    if (employeeFilter) params.employee_id = employeeFilter;
    if (createdFromFilter) params.created_from = createdFromFilter;
    if (createdToFilter) params.created_to = createdToFilter;
    if (periodFromFilter) params.date_from = periodFromFilter;
    if (periodToFilter) params.date_to = periodToFilter;
    return params;
  };

  useEffect(() => {
    async function loadRequests() {
      try {
        setLoading(true);
        setError(null);
        const response = await apiClient.getRequests(buildRequestParams(1));
        setRequests(response.results || []);
        setNextPage(extractNextPage(response.next));
      } catch (err) {
        console.error("Ошибка загрузки заявлений:", err);
        setError("Не удалось загрузить заявления");
      } finally {
        setLoading(false);
      }
    }

    loadRequests();
  }, [view, typeFilter, statusFilter, employeeFilter, createdFromFilter, createdToFilter, periodFromFilter, periodToFilter]);

  useEffect(() => {
    async function loadAllPages<T extends { id: number }>(fetcher: (params: any) => Promise<any>): Promise<T[]> {
      const all: T[] = [];
      let page = 1;
      while (true) {
        const response = await fetcher({ page, limit: 200 });
        const results = response.results || [];
        all.push(...results);
        if (!response.next) break;
        page++;
      }
      return all;
    }

    async function loadLookups() {
      try {
        const [allEmployees, allDepartments] = await Promise.all([
          loadAllPages<User>((p) => apiClient.getEmployees(p)),
          loadAllPages<Department>((p) => apiClient.getDepartments(p)),
        ]);
        setEmployees(allEmployees);
        setDepartments(allDepartments);
      } catch {
        setEmployees([]);
        setDepartments([]);
      }
    }
    loadLookups();
  }, []);

  const filteredRequests = useMemo(() => {
    const q = search.trim().toLowerCase();
    const sorted = [...requests].sort((a, b) => {
      switch (ordering) {
        case "created_at":
          return (new Date(a.created_at).getTime() || 0) - (new Date(b.created_at).getTime() || 0);
        case "title": {
          const leftTitle = String(a.display_title || a.title || "").trim();
          const rightTitle = String(b.display_title || b.title || "").trim();
          return leftTitle.localeCompare(rightTitle, "ru", { sensitivity: "base" });
        }
        case "date_from":
          return (new Date(a.date_from || 0).getTime() || 0) - (new Date(b.date_from || 0).getTime() || 0);
        case "-date_from":
          return (new Date(b.date_from || 0).getTime() || 0) - (new Date(a.date_from || 0).getTime() || 0);
        case "-created_at":
        default:
          return (new Date(b.created_at).getTime() || 0) - (new Date(a.created_at).getTime() || 0);
      }
    });

    if (!q) return sorted;

    return sorted.filter((item) => {
      const title = (item.display_title || item.title || "").toLowerCase();
      const description = (item.comment || item.description || "").toLowerCase();
      const type = String(item.type || item.request_type || "").toLowerCase();
      const author = displayUserName(item.employee || item.created_by).toLowerCase();
      return title.includes(q) || description.includes(q) || type.includes(q) || author.includes(q);
    });
  }, [ordering, requests, search]);

  const resetForm = () => {
    setForm(emptyForm);
  };

  const openEdit = (req: Request) => {
    setEditingRequestId(req.id);
    setCreateOpen(false);
    setActionError(null);
    setActionSuccess(null);
    setForm({
      type: req.type || req.request_type || "",
      title: req.title || "",
      date_from: req.date_from || "",
      date_to: req.date_to || "",
      comment: req.comment || req.description || "",
      department_ids: (req.departments || []).map(Number).filter((n) => Number.isFinite(n)),
      recipient_ids: (req.recipients || []).map((u) => u.id).filter(Boolean),
      cc_user_ids: (req.cc_users || []).map((u) => u.id).filter(Boolean),
      sent_to_all_department: Boolean(req.sent_to_all_department),
      attachment: null,
    });
  };

  const handleCreateOrUpdate = async (mode: "create" | "edit", saveAs: "draft" | "submitted") => {
    try {
      setBusyKey(`${mode}-${saveAs}`);
      setActionError(null);
      setActionSuccess(null);

      if (saveAs === "submitted" && !form.sent_to_all_department && form.department_ids.length === 0 && form.recipient_ids.length === 0) {
        setActionError("Укажите получателей или отделы.");
        return;
      }

      const payload: Record<string, any> = {
        type: form.type,
        title: form.title,
        date_from: form.date_from || null,
        date_to: form.date_to || null,
        comment: form.comment,
        sent_to_all_department: form.sent_to_all_department,
      };

      // Arrays need to be sent as separate FormData entries
      if (form.department_ids.length > 0) payload.department_ids = form.department_ids;
      if (form.recipient_ids.length > 0) payload.recipient_ids = form.recipient_ids;
      if (form.cc_user_ids.length > 0) payload.cc_user_ids = form.cc_user_ids;
      if (form.attachment) payload.attachment = form.attachment;

      if (mode === "create") {
        await apiClient.createRequest(payload, saveAs);
        setActionSuccess(saveAs === "draft" ? "Черновик сохранён." : "Заявление создано.");
        setCreateOpen(false);
      } else if (editingRequestId) {
        await apiClient.updateRequest(editingRequestId, payload, saveAs);
        setActionSuccess("Заявление обновлено.");
        setEditingRequestId(null);
      }

      resetForm();

      const response = await apiClient.getRequests(buildRequestParams(1));
      setRequests(response.results || []);
      setNextPage(extractNextPage(response.next));
    } catch (e: any) {
      const raw = String(e?.message || "Не удалось сохранить заявление");
      let readable = raw;
      try {
        const parsed = JSON.parse(raw);
        const messages = Object.values(parsed).flat();
        readable = messages.join(". ");
      } catch {}
      setActionError(readable);
    } finally {
      setBusyKey(null);
    }
  };

  const handleLoadMore = useCallback(async () => {
    if (!nextPage || loadingMore) return;
    try {
      setLoadingMore(true);
      setError(null);
      const response = await apiClient.getRequests(buildRequestParams(nextPage));
      const chunk = response.results || [];
      setRequests((prev) => {
        const known = new Set(prev.map((r: Request) => r.id));
        const uniqueChunk = chunk.filter((r: Request) => !known.has(r.id));
        return [...prev, ...uniqueChunk];
      });
      setNextPage(extractNextPage(response.next));
    } catch (e: any) {
      setError(String(e?.message || "Не удалось загрузить ещё заявления"));
    } finally {
      setLoadingMore(false);
    }
  }, [nextPage, loadingMore, view, typeFilter, statusFilter, employeeFilter, createdFromFilter, createdToFilter, periodFromFilter, periodToFilter]);

  const handleApprove = async (id: number) => {
    try {
      setBusyKey(`approve-${id}`);
      setActionError(null);
      await apiClient.approveRequest(id);
      setRequests((prev) => prev.map((r) => (r.id === id ? { ...r, status: "approved" } : r)));
    } catch (e: any) {
      setActionError(String(e?.message || "Не удалось одобрить заявление"));
    } finally {
      setBusyKey(null);
    }
  };

  const handleReject = async (id: number) => {
    try {
      setBusyKey(`reject-${id}`);
      setActionError(null);
      await apiClient.rejectRequest(id);
      setRequests((prev) => prev.map((r) => (r.id === id ? { ...r, status: "rejected" } : r)));
    } catch (e: any) {
      setActionError(String(e?.message || "Не удалось отклонить заявление"));
    } finally {
      setBusyKey(null);
    }
  };

  const handleCancel = async (id: number) => {
    try {
      setBusyKey(`cancel-${id}`);
      setActionError(null);
      await apiClient.cancelRequest(id);
      setRequests((prev) => prev.map((r) => (r.id === id ? { ...r, status: "cancelled" } : r)));
    } catch (e: any) {
      setActionError(String(e?.message || "Не удалось отменить заявление"));
    } finally {
      setBusyKey(null);
    }
  };

  const handleDelete = async (id: number) => {
    try {
      setBusyKey(`delete-${id}`);
      setActionError(null);
      await apiClient.deleteRequest(id);
      setRequests((prev) => prev.filter((r) => r.id !== id));
    } catch (e: any) {
      setActionError(String(e?.message || "Не удалось удалить заявление"));
    } finally {
      setBusyKey(null);
    }
  };

  const toggleComments = async (requestId: number) => {
    const isOpen = Boolean(expandedComments[requestId]);
    setExpandedComments((prev) => ({ ...prev, [requestId]: !isOpen }));
    if (!isOpen && !commentsMap[requestId]) {
      try {
        const comments = await apiClient.getRequestComments(requestId);
        setCommentsMap((prev) => ({ ...prev, [requestId]: comments }));
      } catch {
        setCommentsMap((prev) => ({ ...prev, [requestId]: [] }));
      }
    }
  };

  const toggleRow = (requestId: number) => {
    setExpandedRows((prev) => ({ ...prev, [requestId]: !prev[requestId] }));
  };

  const handleAddComment = async (requestId: number) => {
    const text = (commentDrafts[requestId] || "").trim();
    if (!text) return;
    try {
      setBusyKey(`comment-${requestId}`);
      const saved = await apiClient.addRequestComment(requestId, text);
      setCommentsMap((prev) => ({ ...prev, [requestId]: [...(prev[requestId] || []), saved] }));
      setCommentDrafts((prev) => ({ ...prev, [requestId]: "" }));
    } catch (e: any) {
      setActionError(String(e?.message || "Не удалось добавить комментарий"));
    } finally {
      setBusyKey(null);
    }
  };

  const handleDeleteComment = async (requestId: number, commentId: number) => {
    try {
      setBusyKey(`comment-delete-${commentId}`);
      await apiClient.deleteRequestComment(requestId, commentId);
      setCommentsMap((prev) => ({
        ...prev,
        [requestId]: (prev[requestId] || []).filter((c) => c.id !== commentId),
      }));
    } catch (e: any) {
      setActionError(String(e?.message || "Не удалось удалить комментарий"));
    } finally {
      setBusyKey(null);
    }
  };

  const isFinal = (status?: string) => ["approved", "rejected", "cancelled"].includes(String(status || "").toLowerCase());

  const fileInputRef = useRef<HTMLInputElement>(null);
  const loadMoreRef = useRef<HTMLDivElement>(null);

  // Автоматическая подгрузка при прокрутке
  useEffect(() => {
    const observer = new IntersectionObserver(
      (entries) => {
        const target = entries[0];
        if (target.isIntersecting && nextPage && !loadingMore && !loading) {
          handleLoadMore();
        }
      },
      {
        rootMargin: '100px', // Начинаем загрузку за 100px до конца
      }
    );

    const currentRef = loadMoreRef.current;
    if (currentRef) {
      observer.observe(currentRef);
    }

    return () => {
      if (currentRef) {
        observer.unobserve(currentRef);
      }
    };
  }, [nextPage, loadingMore, loading, handleLoadMore]);

  /* ---- Searchable multi-select dropdown ---- */
  const SearchableSelect = ({ label, items, selectedIds, onToggle, placeholder }: {
    label: string;
    items: { id: number; name: string }[];
    selectedIds: number[];
    onToggle: (id: number) => void;
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

    const filtered = items.filter((i) => i.name.toLowerCase().includes(q.toLowerCase()));
    const selectedNames = items.filter((i) => selectedIds.includes(i.id)).map((i) => i.name);

    return (
      <div ref={ref} className="relative">
        <label className="mb-1 block text-xs font-medium text-gray-500">{label}</label>
        <button
          type="button"
          onClick={() => setOpen((v) => !v)}
          className="flex w-full items-center justify-between rounded-lg border border-gray-300 bg-white px-3 py-2 text-left text-sm text-gray-800"
        >
          <span className="truncate">
            {selectedNames.length > 0 ? selectedNames.join(", ") : <span className="text-gray-400">{placeholder || "Выбрать..."}</span>}
          </span>
          <ChevronDown size={14} className={`ml-2 shrink-0 text-gray-400 transition ${open ? "rotate-180" : ""}`} />
        </button>
        {open && (
          <div className="absolute z-50 mt-1 max-h-56 w-full overflow-hidden rounded-lg border border-gray-200 bg-white shadow-lg">
            <div className="border-b border-gray-100 p-2">
              <input
                value={q}
                onChange={(e) => setQ(e.target.value)}
                placeholder="Поиск..."
                className="w-full rounded border border-gray-200 px-2 py-1.5 text-sm focus:border-sky-400 focus:outline-none"
                autoFocus
              />
            </div>
            <div className="max-h-40 overflow-y-auto p-1">
              {filtered.length === 0 ? (
                <p className="px-2 py-1.5 text-xs text-gray-400">Ничего не найдено</p>
              ) : (
                filtered.map((item) => (
                  <label key={item.id} className="flex cursor-pointer items-center gap-2 rounded px-2 py-1.5 text-sm hover:bg-gray-50">
                    <input
                      type="checkbox"
                      checked={selectedIds.includes(item.id)}
                      onChange={() => onToggle(item.id)}
                      className="rounded border-gray-300"
                    />
                    <span className="truncate">{item.name}</span>
                  </label>
                ))
              )}
            </div>
          </div>
        )}
      </div>
    );
  };

  const modalMode: "create" | "edit" = editingRequestId ? "edit" : "create";
  const isModalOpen = createOpen || editingRequestId !== null;

  const closeModal = () => {
    setCreateOpen(false);
    setEditingRequestId(null);
    resetForm();
    setActionError(null);
  };

  const renderUserBadge = (person: User, large = false) => {
    const personLink = userProfileLink(person);
    const personName = displayUserName(person);
    const chipContent = (
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

    return personLink ? (
      <Link href={personLink} className={`inline-flex max-w-full items-center gap-2 rounded-full bg-gray-100 ${large ? "px-3 py-1.5 text-sm" : "px-2.5 py-1 text-xs"} font-medium text-gray-700 ring-1 ring-gray-200 hover:bg-gray-200`}>
        {chipContent}
      </Link>
    ) : (
      <span className={`inline-flex max-w-full items-center gap-2 rounded-full bg-gray-100 ${large ? "px-3 py-1.5 text-sm" : "px-2.5 py-1 text-xs"} font-medium text-gray-700 ring-1 ring-gray-200`}>
        {chipContent}
      </span>
    );
  };

  return (
    <AppShell>
      {loading ? (
        <div className="rounded-2xl bg-white p-8 text-center shadow-sm ring-1 ring-gray-100">
          <div className="mb-4 inline-block h-8 w-8 animate-spin rounded-full border-4 border-sky-400 border-t-transparent" />
          <p className="text-sm text-gray-500">Загрузка заявлений...</p>
        </div>
      ) : error ? (
        <div className="rounded-2xl bg-red-50 p-6 text-center">
          <p className="text-sm text-red-800">{error}</p>
        </div>
      ) : (
        <section className="rounded-2xl bg-white p-4 shadow-sm ring-1 ring-gray-100">
          {swipeMode && (canManage || canProcess) ? (
            <div>
              <div className="mb-4 flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Zap size={14} className="text-amber-500" />
                  <p className="text-sm font-semibold uppercase tracking-wide text-gray-500">Быстрый разбор</p>
                </div>
                <button type="button" onClick={() => setSwipeMode(false)} className="rounded-lg bg-gray-100 px-3 py-1.5 text-xs font-medium text-gray-600 hover:bg-gray-200">
                  Обычный режим
                </button>
              </div>
              {actionError ? <p className="mb-3 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{actionError}</p> : null}
              <SwipeApprovalMode
                requests={requests}
                onApprove={handleApprove}
                onReject={handleReject}
                onClose={() => setSwipeMode(false)}
              />
            </div>
          ) : (
          <>
          <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
            <div className="flex items-center gap-3">
              <p className="text-sm font-semibold uppercase tracking-wide text-gray-500">Заявления</p>
              {(canManage || canProcess) && (
                <button type="button" onClick={() => setSwipeMode(true)} className="group flex items-center gap-1 rounded-full bg-amber-50 px-2.5 py-1 text-[11px] font-medium text-amber-600 ring-1 ring-amber-100 transition hover:bg-amber-100" title="Тестовый режим быстрого разбора заявлений">
                  <Zap size={11} className="transition group-hover:text-amber-700" /> Быстрый разбор
                </button>
              )}
            </div>
            <button
              type="button"
              onClick={() => {
                setEditingRequestId(null);
                resetForm();
                setActionError(null);
                setActionSuccess(null);
                setCreateOpen(true);
              }}
              className="inline-flex items-center gap-1 rounded-lg bg-sky-500 px-3 py-2 text-sm font-medium text-white hover:bg-sky-600"
            >
              <Plus size={14} /> Создать заявление
            </button>
          </div>

          {actionError ? <p className="mb-3 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{actionError}</p> : null}
          {actionSuccess ? <p className="mb-3 rounded-lg bg-emerald-50 px-3 py-2 text-sm text-emerald-700">{actionSuccess}</p> : null}

          <div className="mb-4 flex items-center gap-2">
            <div className="relative flex-1">
              <Search size={16} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
              <input
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Поиск по заявлениям"
                className="w-full rounded-lg border border-gray-200 bg-gray-50 py-2.5 pl-9 pr-3 text-sm text-gray-800 transition focus:border-sky-500 focus:bg-white focus:outline-none focus:ring-2 focus:ring-sky-100"
              />
            </div>
            <button
              type="button"
              title="Фильтры"
              onClick={() => setFiltersOpen((v) => !v)}
              className={`relative inline-flex items-center justify-center rounded-lg border p-2.5 transition ${
                filtersOpen
                  ? "border-sky-400 bg-sky-50 text-sky-600"
                  : "border-gray-200 bg-gray-50 text-gray-500 hover:bg-gray-100"
              }`}
            >
              <Filter size={16} />
              {(view || typeFilter || statusFilter || employeeFilter || createdFromFilter || createdToFilter || periodFromFilter || periodToFilter) && (
                <span className="absolute -right-1 -top-1 flex h-4 min-w-4 items-center justify-center rounded-full bg-sky-500 px-1 text-[10px] font-bold text-white">
                  {[view, typeFilter, statusFilter, employeeFilter, createdFromFilter, createdToFilter, periodFromFilter, periodToFilter].filter(Boolean).length}
                </span>
              )}
            </button>
            <div className="relative w-[148px] shrink-0">
              <ArrowUpDown size={15} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-gray-500" />
              <select
                value={ordering}
                onChange={(e) => setOrdering(e.target.value)}
                className="w-full appearance-none rounded-lg border border-gray-200 bg-gray-50 py-2.5 pl-9 pr-8 text-xs font-medium text-gray-700 transition hover:bg-gray-100 focus:border-sky-400 focus:bg-white focus:outline-none focus:ring-2 focus:ring-sky-100"
                aria-label="Сортировка списка заявлений"
              >
                {orderingOptions.map((option) => (
                  <option key={option.value} value={option.value}>{option.label}</option>
                ))}
              </select>
              <ChevronDown size={14} className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-gray-400" />
            </div>
          </div>

          {filtersOpen && (
            <div className="mb-3 flex flex-col gap-2 rounded-xl border border-gray-200 bg-gray-50 p-3">
              <select value={view} onChange={(e) => setView(e.target.value as "" | "mine" | "addressed")} className="rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm text-gray-800">
                <option value="">Все заявления</option>
                <option value="mine">Мои заявления</option>
                <option value="addressed">Адресованные мне</option>
              </select>

              <select value={typeFilter} onChange={(e) => setTypeFilter(e.target.value)} className="rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm text-gray-800">
                <option value="">Тип заявления</option>
                {Object.entries(requestTypeLabels).map(([value, label]) => (
                  <option key={value} value={value}>
                    {label}
                  </option>
                ))}
              </select>

              <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)} className="rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm text-gray-800">
                <option value="">Статус заявления</option>
                {Object.entries(statusMeta).map(([value, meta]) => (
                  <option key={value} value={value}>
                    {meta.label}
                  </option>
                ))}
              </select>

              <select value={employeeFilter} onChange={(e) => setEmployeeFilter(e.target.value)} className="rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm text-gray-800">
                <option value="">Все сотрудники</option>
                {employees.map((emp) => (
                  <option key={emp.id} value={emp.id}>
                    {displayUserName(emp)}
                  </option>
                ))}
              </select>

              <div className="space-y-1.5">
                <label className="text-xs font-medium text-gray-600 px-1">Дата создания заявления</label>
                <div className="flex gap-2">
                  <input
                    type="date"
                    value={createdFromFilter}
                    onChange={(e) => setCreatedFromFilter(e.target.value)}
                    placeholder="от"
                    className="flex-1 rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm text-gray-800"
                  />
                  <input
                    type="date"
                    value={createdToFilter}
                    onChange={(e) => setCreatedToFilter(e.target.value)}
                    placeholder="до"
                    className="flex-1 rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm text-gray-800"
                  />
                </div>
              </div>

              <div className="space-y-1.5">
                <label className="text-xs font-medium text-gray-600 px-1">Период заявления</label>
                <div className="flex gap-2">
                  <input
                    type="date"
                    value={periodFromFilter}
                    onChange={(e) => setPeriodFromFilter(e.target.value)}
                    placeholder="от"
                    className="flex-1 rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm text-gray-800"
                  />
                  <input
                    type="date"
                    value={periodToFilter}
                    onChange={(e) => setPeriodToFilter(e.target.value)}
                    placeholder="до"
                    className="flex-1 rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm text-gray-800"
                  />
                </div>
              </div>

              {(view || typeFilter || statusFilter || employeeFilter || createdFromFilter || createdToFilter || periodFromFilter || periodToFilter) && (
                <button
                  type="button"
                  onClick={() => {
                    setView("");
                    setTypeFilter("");
                    setStatusFilter("");
                    setEmployeeFilter("");
                    setCreatedFromFilter("");
                    setCreatedToFilter("");
                    setPeriodFromFilter("");
                    setPeriodToFilter("");
                  }}
                  className="rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm font-medium text-gray-600 hover:bg-gray-100 transition"
                >
                  Очистить фильтры
                </button>
              )}
            </div>
          )}

          <div className="space-y-3">
            {filteredRequests.length === 0 ? (
              <div className="rounded-xl bg-gray-50 p-8 text-center">
                <FileSignature size={22} className="mx-auto mb-2 text-gray-400" />
                <p className="text-sm text-gray-500">Заявления не найдены</p>
              </div>
            ) : (
              filteredRequests.map((item) => {
                const requestAuthor = item.employee || item.created_by;
                const authorName = displayUserName(requestAuthor);
                const approverName = displayUserName(item.approver || item.assigned_to);
                const statusKey = String(item.status || "").toLowerCase();
                const requestTypeKey = String(item.type || item.request_type || "").toLowerCase();
                const status = statusMeta[statusKey] ?? defaultStatusMeta;
                const authorLink = userProfileLink(requestAuthor);
                const approverLink = userProfileLink(item.approver || item.assigned_to);
                const requestTypeLabel = requestTypeLabels[requestTypeKey] || String(item.type || item.request_type || "Другое");
                const requestTitle = item.display_title || item.title || "Без заголовка";
                const canProcessThis = Boolean(
                  statusKey === "pending" &&
                    requestAuthor?.id &&
                    user?.id &&
                    requestAuthor.id !== user.id &&
                    (canManage || (canProcess && item.is_recipient))
                );
                const isAuthor = Boolean(requestAuthor?.id && user?.id && requestAuthor.id === user.id);
                const canEditThis = isAuthor && !isFinal(statusKey);
                const canCancelThis = isAuthor && !isFinal(statusKey);
                const canDeleteThis = (isAuthor && !isFinal(statusKey)) || canManage;
                const rowOpen = Boolean(expandedRows[item.id]);
                const comments = commentsMap[item.id] || [];
                const commentsOpen = Boolean(expandedComments[item.id]);
                const departmentLabels = (item.departments || [])
                  .map((id) => departmentNameMap.get(Number(id)) || `Отдел #${id}`)
                  .join(", ");
                const recipients = item.recipients || [];
                const ccUsers = item.cc_users || [];
                const visibleRecipients = recipients.slice(0, 2);
                const visibleCcUsers = ccUsers.slice(0, 2);
                const hiddenRecipientsCount = Math.max(0, recipients.length - visibleRecipients.length);
                const hiddenCcCount = Math.max(0, ccUsers.length - visibleCcUsers.length);
                const summaryText = item.comment || item.description;

                return (
                  <article key={item.id} className="overflow-hidden rounded-xl border border-gray-200 bg-white transition hover:border-gray-300">
                    <div className="p-4">
                      <div className="flex items-start gap-3">
                        <button
                          type="button"
                          onClick={() => toggleRow(item.id)}
                          aria-label={rowOpen ? "Свернуть детали" : "Развернуть детали"}
                          className="mt-0.5 inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border border-gray-200 bg-gray-50 text-gray-500 transition hover:bg-gray-100"
                        >
                          <ChevronDown size={15} className={`transition ${rowOpen ? "rotate-180" : ""}`} />
                        </button>

                        <div className="min-w-0 flex-1">
                          <div className="flex items-start justify-between gap-3">
                            <div className="min-w-0 flex-1">
                              <div className="mb-2 flex items-center gap-2">
                                {authorLink ? (
                                  <Link href={authorLink} className="group flex min-w-0 items-center gap-2">
                                    {requestAuthor?.avatar ? (
                                      <img src={requestAuthor.avatar} alt={authorName} className="h-8 w-8 shrink-0 rounded-full object-cover ring-1 ring-gray-200" />
                                    ) : (
                                      <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-sky-100 text-xs font-semibold text-sky-700 ring-1 ring-sky-200">
                                        {(requestAuthor?.first_name?.[0] || requestAuthor?.last_name?.[0] || "?").toUpperCase()}
                                      </span>
                                    )}
                                    <span className="truncate text-sm font-medium text-gray-800 group-hover:text-sky-700">{authorName}</span>
                                  </Link>
                                ) : (
                                  <div className="flex min-w-0 items-center gap-2">
                                    <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-gray-100 text-xs font-semibold text-gray-500 ring-1 ring-gray-200">
                                      ?
                                    </span>
                                    <span className="truncate text-sm font-medium text-gray-800">{authorName}</span>
                                  </div>
                                )}
                              </div>

                              <button
                                type="button"
                                onClick={() => setDetailsRequest(item)}
                                className="block w-full text-left"
                                aria-label={`Открыть полную информацию по заявлению ${requestTitle}`}
                              >
                                <h3 className={`${rowOpen ? "line-clamp-3 break-words" : "truncate"} text-sm font-semibold text-gray-900 transition hover:text-gray-700`}>
                                  <span className="text-gray-600">{requestTypeLabel}:</span>{" "}
                                  <span className="text-gray-900">{requestTitle}</span>
                                </h3>
                              </button>
                              <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-gray-500">
                                <span>Период: {item.date_from ? formatDate(item.date_from) : "—"}{item.date_to ? ` — ${formatDate(item.date_to)}` : ""}</span>
                              </div>
                            </div>

                            <div className="shrink-0 text-right">
                              <span className={`inline-flex rounded-full px-2.5 py-1 text-xs ring-1 ${status.className}`}>
                                {status.label}
                              </span>
                            </div>
                          </div>

                          {summaryText ? (
                            <p className={`${rowOpen ? "line-clamp-10 break-words" : "line-clamp-3"} mt-3 text-sm text-gray-700`}>{summaryText}</p>
                          ) : null}

                          <div className={`${summaryText ? "mt-3" : "mt-2"} flex flex-wrap items-center gap-1.5`}>
                            {canCancelThis ? (
                              <button type="button" title="Отменить" onClick={() => handleCancel(item.id)} disabled={busyKey === `cancel-${item.id}`} className="inline-flex items-center justify-center rounded-lg border border-gray-300 bg-white p-1.5 text-gray-600 hover:bg-gray-50 disabled:opacity-60">
                                <Ban size={15} />
                              </button>
                            ) : null}

                            <button
                              type="button"
                              title={`Комментарии (${item.comments_count ?? comments.length})`}
                              onClick={() => toggleComments(item.id)}
                              className="relative inline-flex items-center justify-center rounded-lg border border-gray-300 bg-white p-1.5 text-gray-600 hover:bg-gray-50"
                            >
                              <MessageSquare size={15} />
                              {(item.comments_count ?? comments.length) > 0 && (
                                <span className="absolute -right-1.5 -top-1.5 flex h-4 min-w-4 items-center justify-center rounded-full bg-sky-500 px-1 text-[10px] font-bold text-white">
                                  {item.comments_count ?? comments.length}
                                </span>
                              )}
                            </button>

                            {canEditThis ? (
                              <button type="button" title="Редактировать" onClick={() => openEdit(item)} className="inline-flex items-center justify-center rounded-lg border border-gray-300 bg-white p-1.5 text-gray-600 hover:bg-gray-50">
                                <Pencil size={15} />
                              </button>
                            ) : null}

                            {canDeleteThis ? (
                              <button type="button" title="Удалить" onClick={() => handleDelete(item.id)} disabled={busyKey === `delete-${item.id}`} className="inline-flex items-center justify-center rounded-lg border border-rose-200 bg-rose-50 p-1.5 text-rose-600 hover:bg-rose-100 disabled:opacity-60">
                                <Trash2 size={15} />
                              </button>
                            ) : null}

                            {canProcessThis && (
                              <span className="ml-auto inline-flex items-center gap-2">
                                <button type="button" title="Одобрить" onClick={() => handleApprove(item.id)} disabled={busyKey === `approve-${item.id}`} className="inline-flex items-center justify-center rounded-lg border border-emerald-200 bg-emerald-50 p-2 text-emerald-600 hover:bg-emerald-100 disabled:opacity-60">
                                  <ThumbsUp size={18} />
                                </button>
                                <button type="button" title="Отклонить" onClick={() => handleReject(item.id)} disabled={busyKey === `reject-${item.id}`} className="inline-flex items-center justify-center rounded-lg border border-rose-200 bg-rose-50 p-2 text-rose-600 hover:bg-rose-100 disabled:opacity-60">
                                  <ThumbsDown size={18} />
                                </button>
                              </span>
                            )}
                          </div>
                        </div>
                      </div>

                      {(rowOpen || commentsOpen) ? (
                        <div className="mt-4 rounded-xl border border-gray-100 bg-gray-50/80 p-4">
                            {rowOpen ? (
                              <div className="space-y-3 text-xs text-gray-500">
                                <div className="grid grid-cols-1 gap-x-4 gap-y-2 sm:grid-cols-2">
                                  <div className="min-w-0">
                                    <span className="text-gray-400">Решающий:</span>{" "}
                                    {(() => {
                                      const approver = item.approver || item.assigned_to;
                                      const aLink = userProfileLink(approver);
                                      const aName = displayUserName(approver);
                                      if (!approver) return <span className="text-gray-400">—</span>;
                                      return aLink ? (
                                        <Link href={aLink} className="font-medium text-sky-700 hover:text-sky-800">{aName}</Link>
                                      ) : (
                                        <span className="font-medium text-gray-700">{aName}</span>
                                      );
                                    })()}
                                  </div>
                                  <div>
                                    <span className="text-gray-400">Создано:</span>{" "}
                                    <span className="font-medium text-gray-700">{formatDate(item.created_at) || "—"}</span>
                                  </div>
                                  <div>
                                    <span className="text-gray-400">Обновлено:</span>{" "}
                                    <span className="font-medium text-gray-700">{formatDate(item.updated_at) || "—"}</span>
                                  </div>
                                  {departmentLabels ? (
                                    <div className="sm:col-span-2">
                                      <span className="text-gray-400">Отделы:</span>{" "}
                                      <span className="font-medium text-gray-700">{departmentLabels}</span>
                                    </div>
                                  ) : null}
                                </div>

                                <div className="space-y-2">
                                  <div className="flex flex-wrap items-start gap-2">
                                    <span className="pt-1 text-gray-400">Получатели:</span>
                                    <div className="flex min-w-0 flex-1 flex-wrap gap-1.5">
                                      {visibleRecipients.length > 0 ? visibleRecipients.map((recipient) => {
                                        const recipientLink = userProfileLink(recipient);
                                        const recipientName = displayUserName(recipient);
                                        const chipContent = (
                                          <>
                                            {recipient.avatar ? (
                                              <img src={recipient.avatar} alt={recipientName} className="h-5 w-5 shrink-0 rounded-full object-cover ring-1 ring-gray-200" />
                                            ) : (
                                              <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-sky-100 text-[10px] font-semibold text-sky-700 ring-1 ring-sky-200">
                                                {(recipient.first_name?.[0] || recipient.last_name?.[0] || "?").toUpperCase()}
                                              </span>
                                            )}
                                            <span className="max-w-[140px] truncate">{recipientName}</span>
                                          </>
                                        );

                                        return recipientLink ? (
                                          <Link key={recipient.id} href={recipientLink} className="inline-flex items-center gap-1.5 rounded-full bg-gray-100 px-2 py-1 font-medium text-gray-700 ring-1 ring-gray-200 hover:bg-gray-200">
                                            {chipContent}
                                          </Link>
                                        ) : (
                                          <span key={recipient.id} className="inline-flex items-center gap-1.5 rounded-full bg-gray-100 px-2 py-1 font-medium text-gray-700 ring-1 ring-gray-200">
                                            {chipContent}
                                          </span>
                                        );
                                      }) : (
                                        <span className="pt-1 text-gray-400">{item.recipient_count ?? 0}</span>
                                      )}
                                      {hiddenRecipientsCount > 0 && (
                                        <span className="inline-flex items-center rounded-full bg-gray-100 px-2 py-1 font-medium text-gray-600 ring-1 ring-gray-200">
                                          +{hiddenRecipientsCount}
                                        </span>
                                      )}
                                    </div>
                                  </div>

                                  <div className="flex flex-wrap items-start gap-2">
                                    <span className="pt-1 text-gray-400">В копии:</span>
                                    <div className="flex min-w-0 flex-1 flex-wrap gap-1.5">
                                      {visibleCcUsers.length > 0 ? visibleCcUsers.map((ccUser) => {
                                        const ccLink = userProfileLink(ccUser);
                                        const ccName = displayUserName(ccUser);
                                        const chipContent = (
                                          <>
                                            {ccUser.avatar ? (
                                              <img src={ccUser.avatar} alt={ccName} className="h-5 w-5 shrink-0 rounded-full object-cover ring-1 ring-gray-200" />
                                            ) : (
                                              <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-sky-100 text-[10px] font-semibold text-sky-700 ring-1 ring-sky-200">
                                                {(ccUser.first_name?.[0] || ccUser.last_name?.[0] || "?").toUpperCase()}
                                              </span>
                                            )}
                                            <span className="max-w-[140px] truncate">{ccName}</span>
                                          </>
                                        );

                                        return ccLink ? (
                                          <Link key={ccUser.id} href={ccLink} className="inline-flex items-center gap-1.5 rounded-full bg-gray-100 px-2 py-1 font-medium text-gray-700 ring-1 ring-gray-200 hover:bg-gray-200">
                                            {chipContent}
                                          </Link>
                                        ) : (
                                          <span key={ccUser.id} className="inline-flex items-center gap-1.5 rounded-full bg-gray-100 px-2 py-1 font-medium text-gray-700 ring-1 ring-gray-200">
                                            {chipContent}
                                          </span>
                                        );
                                      }) : (
                                        <span className="pt-1 text-gray-400">—</span>
                                      )}
                                      {hiddenCcCount > 0 && (
                                        <span className="inline-flex items-center rounded-full bg-gray-100 px-2 py-1 font-medium text-gray-600 ring-1 ring-gray-200">
                                          +{hiddenCcCount}
                                        </span>
                                      )}
                                    </div>
                                  </div>

                                  {(item.attachment || item.attachment_url) && (
                                    <div className="flex min-w-0 items-center gap-1.5">
                                      <button
                                        type="button"
                                        onClick={() => {
                                          const url = item.attachment_url || item.attachment || "";
                                          const name = decodeURIComponent(url.split("/").pop() || "Вложение");
                                          setAttachmentPreview({ url, name });
                                        }}
                                        className="inline-flex min-w-0 max-w-full items-center gap-1.5 rounded-full bg-sky-50 px-2.5 py-1 text-sky-700 ring-1 ring-sky-100 hover:bg-sky-100"
                                      >
                                        <Paperclip size={13} className="shrink-0" />
                                        <span className="truncate font-medium">
                                          {(() => {
                                            const url = item.attachment_url || item.attachment || "";
                                            return decodeURIComponent(url.split("/").pop() || "Вложение");
                                          })()}
                                        </span>
                                      </button>
                                    </div>
                                  )}
                                </div>
                              </div>
                            ) : null}

                            {commentsOpen ? (
                              <div className={rowOpen ? "mt-3 rounded-lg border border-gray-200 bg-white p-3" : "rounded-lg border border-gray-200 bg-white p-3"}>
                                <div className="space-y-2">
                                  {comments.length === 0 ? (
                                    <p className="text-xs text-gray-500">Комментариев пока нет</p>
                                  ) : (
                                    comments.map((c) => {
                                      const canDeleteComment = Boolean(c.author?.id && (user?.id === c.author.id || auth?.is_staff || auth?.is_superuser));
                                      return (
                                        <div key={c.id} className="rounded-lg bg-white px-3 py-2 text-xs text-gray-700 ring-1 ring-gray-100">
                                          <div className="mb-1 flex items-center justify-between gap-2">
                                            <span className="font-medium">{displayUserName(c.author)}</span>
                                            <div className="flex items-center gap-2">
                                              <span className="text-gray-500">{formatDate(c.created_at)}</span>
                                              {canDeleteComment ? (
                                                <button type="button" onClick={() => handleDeleteComment(item.id, c.id)} className="text-rose-600 hover:text-rose-700">
                                                  удалить
                                                </button>
                                              ) : null}
                                            </div>
                                          </div>
                                          <p>{c.text}</p>
                                        </div>
                                      );
                                    })
                                  )}
                                </div>

                                <div className="mt-2 flex items-center gap-2">
                                  <input
                                    value={commentDrafts[item.id] || ""}
                                    onChange={(e) => setCommentDrafts((prev) => ({ ...prev, [item.id]: e.target.value }))}
                                    placeholder="Добавить комментарий"
                                    className="flex-1 rounded-lg border border-gray-300 px-3 py-2 text-xs"
                                  />
                                  <button
                                    type="button"
                                    onClick={() => handleAddComment(item.id)}
                                    disabled={busyKey === `comment-${item.id}`}
                                    className="rounded-lg bg-sky-500 px-3 py-2 text-xs font-medium text-white hover:bg-sky-600 disabled:opacity-60"
                                  >
                                    Отправить
                                  </button>
                                </div>
                              </div>
                            ) : null}
                        </div>
                      ) : null}
                    </div>
                  </article>
                );
              })
            )}
          </div>

          {/* Элемент-наблюдатель для автоматической подгрузки */}
          {nextPage && (
            <div ref={loadMoreRef} className="mt-4 flex justify-center py-4">
              {loadingMore && (
                <div className="flex items-center gap-2 text-sm text-gray-500">
                  <div className="h-4 w-4 animate-spin rounded-full border-2 border-gray-300 border-t-sky-500"></div>
                  <span>Загрузка...</span>
                </div>
              )}
            </div>
          )}
          </>
          )}
        </section>
      )}

      <Modal
        isOpen={Boolean(detailsRequest)}
        onClose={() => setDetailsRequest(null)}
        title="Полная информация по заявлению"
        size="lg"
      >
        {detailsRequest ? (
          (() => {
            const detailAuthor = detailsRequest.employee || detailsRequest.created_by;
            const detailApprover = detailsRequest.approver || detailsRequest.assigned_to;
            const detailStatusKey = String(detailsRequest.status || "").toLowerCase();
            const detailTypeKey = String(detailsRequest.type || detailsRequest.request_type || "").toLowerCase();
            const detailStatus = statusMeta[detailStatusKey] ?? defaultStatusMeta;
            const detailTypeLabel = requestTypeLabels[detailTypeKey] || String(detailsRequest.type || detailsRequest.request_type || "Другое");
            const detailTitle = detailsRequest.display_title || detailsRequest.title || "Без заголовка";
            const detailSummary = detailsRequest.comment || detailsRequest.description;
            const detailDepartments = (detailsRequest.departments || [])
              .map((id) => departmentNameMap.get(Number(id)) || `Отдел #${id}`);
            const detailRecipients = detailsRequest.recipients || [];
            const detailCcUsers = detailsRequest.cc_users || [];
            const detailAttachmentUrl = detailsRequest.attachment_url || detailsRequest.attachment || "";
            const detailAttachmentName = detailAttachmentUrl ? decodeURIComponent(detailAttachmentUrl.split("/").pop() || "Вложение") : "";

            return (
              <div className="space-y-5 text-sm text-gray-700">
                <div className="flex flex-wrap items-start justify-between gap-3 rounded-xl border border-gray-200 bg-gray-50 p-4">
                  <div className="min-w-0 flex-1 space-y-3">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="inline-flex rounded-full bg-sky-50 px-2.5 py-1 text-xs font-medium text-sky-700 ring-1 ring-sky-100">
                        {detailTypeLabel}
                      </span>
                      <span className={`inline-flex rounded-full px-2.5 py-1 text-xs ring-1 ${detailStatus.className}`}>
                        {detailStatus.label}
                      </span>
                    </div>
                    <div>
                      <h2 className="text-lg font-semibold text-gray-900 break-words">{detailTitle}</h2>
                      {detailSummary ? (
                        <div className="mt-3 whitespace-pre-wrap break-words text-sm leading-relaxed text-gray-700">{detailSummary}</div>
                      ) : (
                        <p className="mt-3 text-sm text-gray-400">Описание отсутствует</p>
                      )}
                    </div>
                  </div>
                </div>

                <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                  <div className="rounded-xl border border-gray-200 bg-white p-4">
                    <p className="text-xs font-semibold uppercase tracking-wide text-gray-400">Даты</p>
                    <div className="mt-3 space-y-2">
                      <div>
                        <p className="text-xs text-gray-400">Период</p>
                        <p className="mt-1 break-words text-sm text-gray-900">{detailsRequest.date_from ? formatDate(detailsRequest.date_from) : "—"}{detailsRequest.date_to ? ` — ${formatDate(detailsRequest.date_to)}` : ""}</p>
                      </div>
                      <div>
                        <p className="text-xs text-gray-400">Создано</p>
                        <p className="mt-1 text-sm text-gray-900">{formatDate(detailsRequest.created_at) || "—"}</p>
                      </div>
                      <div>
                        <p className="text-xs text-gray-400">Обновлено</p>
                        <p className="mt-1 text-sm text-gray-900">{formatDate(detailsRequest.updated_at) || "—"}</p>
                      </div>
                    </div>
                  </div>

                  <div className="rounded-xl border border-gray-200 bg-white p-4">
                    <p className="text-xs font-semibold uppercase tracking-wide text-gray-400">Участники</p>
                    <div className="mt-3 space-y-3">
                      <div>
                        <p className="text-xs text-gray-400">Автор</p>
                        <div className="mt-2 flex flex-wrap gap-2">
                          {detailAuthor ? renderUserBadge(detailAuthor, true) : <span className="text-sm text-gray-400">—</span>}
                        </div>
                      </div>
                      <div>
                        <p className="text-xs text-gray-400">Решающий</p>
                        <div className="mt-2 flex flex-wrap gap-2">
                          {detailApprover ? renderUserBadge(detailApprover, true) : <span className="text-sm text-gray-400">—</span>}
                        </div>
                      </div>
                    </div>
                  </div>
                </div>

                <div className="rounded-xl border border-gray-200 bg-white p-4">
                  <p className="text-xs font-semibold uppercase tracking-wide text-gray-400">Отделы</p>
                  {detailDepartments.length > 0 ? (
                    <div className="mt-3 flex flex-wrap gap-2">
                      {detailDepartments.map((department) => (
                        <span key={department} className="inline-flex items-center rounded-full bg-gray-100 px-3 py-1.5 text-sm font-medium text-gray-700 ring-1 ring-gray-200">
                          {department}
                        </span>
                      ))}
                    </div>
                  ) : (
                    <p className="mt-3 text-sm text-gray-400">Отделы не указаны</p>
                  )}
                </div>

                <div className="rounded-xl border border-gray-200 bg-white p-4">
                  <p className="text-xs font-semibold uppercase tracking-wide text-gray-400">Получатели</p>
                  {detailRecipients.length > 0 ? (
                    <div className="mt-3 flex flex-wrap gap-2">
                      {detailRecipients.map((recipient) => (
                        <div key={recipient.id}>{renderUserBadge(recipient, true)}</div>
                      ))}
                    </div>
                  ) : (
                    <p className="mt-3 text-sm text-gray-400">Получатели не указаны</p>
                  )}
                </div>

                <div className="rounded-xl border border-gray-200 bg-white p-4">
                  <p className="text-xs font-semibold uppercase tracking-wide text-gray-400">В копии</p>
                  {detailCcUsers.length > 0 ? (
                    <div className="mt-3 flex flex-wrap gap-2">
                      {detailCcUsers.map((ccUser) => (
                        <div key={ccUser.id}>{renderUserBadge(ccUser, true)}</div>
                      ))}
                    </div>
                  ) : (
                    <p className="mt-3 text-sm text-gray-400">Копия не указана</p>
                  )}
                </div>

                <div className="rounded-xl border border-gray-200 bg-white p-4">
                  <p className="text-xs font-semibold uppercase tracking-wide text-gray-400">Вложение</p>
                  {detailAttachmentUrl ? (
                    <div className="mt-3 flex flex-wrap items-center gap-3">
                      <button
                        type="button"
                        onClick={() => setAttachmentPreview({ url: detailAttachmentUrl, name: detailAttachmentName })}
                        className="inline-flex items-center gap-2 rounded-lg border border-sky-200 bg-sky-50 px-3 py-2 text-sm font-medium text-sky-700 hover:bg-sky-100"
                      >
                        <Paperclip size={15} />
                        <span className="break-all">{detailAttachmentName}</span>
                      </button>
                      <a href={detailAttachmentUrl} target="_blank" rel="noreferrer" className="text-sm font-medium text-sky-700 hover:text-sky-800 hover:underline">
                        Открыть в новой вкладке
                      </a>
                    </div>
                  ) : (
                    <p className="mt-3 text-sm text-gray-400">Вложение отсутствует</p>
                  )}
                </div>
              </div>
            );
          })()
        ) : null}
      </Modal>

      {/* ===== Modal create/edit ===== */}
      {isModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4" onClick={(e) => { if (e.target === e.currentTarget) closeModal(); }}>
          <div className="relative max-h-[90vh] w-full max-w-lg overflow-y-auto rounded-2xl bg-white p-5 shadow-xl">
            <div className="mb-4 flex items-center justify-between">
              <h2 className="text-base font-semibold text-gray-900">
                {modalMode === "create" ? "Новое заявление" : "Редактировать заявление"}
              </h2>
              <button type="button" onClick={closeModal} className="rounded-lg p-1 text-gray-400 hover:bg-gray-100 hover:text-gray-600">
                <X size={18} />
              </button>
            </div>

            {actionError ? <p className="mb-3 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{actionError}</p> : null}

            <div className="flex flex-col gap-3">
              {/* Тема */}
              <div>
                <label className="mb-1 block text-xs font-medium text-gray-500">Тема заявления</label>
                <input
                  value={form.title}
                  onChange={(e) => setForm((p) => ({ ...p, title: e.target.value }))}
                  placeholder="Тема заявления"
                  className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-sky-400 focus:outline-none focus:ring-2 focus:ring-sky-100"
                />
              </div>

              {/* Тип */}
              <div>
                <label className="mb-1 block text-xs font-medium text-gray-500">Тип заявления</label>
                <select
                  value={form.type}
                  onChange={(e) => setForm((p) => ({ ...p, type: e.target.value }))}
                  className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-sky-400 focus:outline-none focus:ring-2 focus:ring-sky-100"
                >
                  <option value="">Выберите тип</option>
                  {Object.entries(requestTypeLabels).map(([value, label]) => (
                    <option key={value} value={value}>{label}</option>
                  ))}
                </select>
              </div>

              {/* Период */}
              <div>
                <label className="mb-1 block text-xs font-medium text-gray-500">Период</label>
                <div className="flex items-center gap-2">
                  <input
                    type="date"
                    value={form.date_from}
                    onChange={(e) => setForm((p) => ({ ...p, date_from: e.target.value }))}
                    className="flex-1 rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-sky-400 focus:outline-none focus:ring-2 focus:ring-sky-100"
                  />
                  <span className="text-xs text-gray-400">—</span>
                  <input
                    type="date"
                    value={form.date_to}
                    onChange={(e) => setForm((p) => ({ ...p, date_to: e.target.value }))}
                    className="flex-1 rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-sky-400 focus:outline-none focus:ring-2 focus:ring-sky-100"
                  />
                </div>
              </div>

              {/* Решающий (recipients) */}
              <SearchableSelect
                label="Решающий"
                placeholder="Выберите решающего..."
                items={employees.filter((emp) => !user?.id || emp.id !== user.id).map((emp) => ({ id: emp.id, name: displayUserName(emp) }))}
                selectedIds={form.recipient_ids}
                onToggle={(id) => setForm((p) => ({
                  ...p,
                  recipient_ids: p.recipient_ids.includes(id) ? p.recipient_ids.filter((x) => x !== id) : [...p.recipient_ids, id],
                }))}
              />

              {/* В копии */}
              <SearchableSelect
                label="В копии"
                placeholder="Выберите пользователей..."
                items={employees.filter((emp) => !user?.id || emp.id !== user.id).map((emp) => ({ id: emp.id, name: displayUserName(emp) }))}
                selectedIds={form.cc_user_ids}
                onToggle={(id) => setForm((p) => ({
                  ...p,
                  cc_user_ids: p.cc_user_ids.includes(id) ? p.cc_user_ids.filter((x) => x !== id) : [...p.cc_user_ids, id],
                }))}
              />

              {/* Отдел */}
              <SearchableSelect
                label="Отдел"
                placeholder="Выберите отдел..."
                items={departments.map((d) => ({ id: d.id, name: d.name }))}
                selectedIds={form.department_ids}
                onToggle={(id) => setForm((p) => ({
                  ...p,
                  department_ids: p.department_ids.includes(id) ? p.department_ids.filter((x) => x !== id) : [...p.department_ids, id],
                }))}
              />

              {/* Описание */}
              <div>
                <label className="mb-1 block text-xs font-medium text-gray-500">Описание</label>
                <textarea
                  value={form.comment}
                  onChange={(e) => setForm((p) => ({ ...p, comment: e.target.value }))}
                  placeholder="Описание заявления"
                  rows={3}
                  className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-sky-400 focus:outline-none focus:ring-2 focus:ring-sky-100"
                />
              </div>

              {/* Прикрепить файл */}
              <div>
                <input
                  ref={fileInputRef}
                  type="file"
                  accept=".pdf,.jpg,.jpeg,.png"
                  className="hidden"
                  onChange={(e) => {
                    const file = e.target.files?.[0] || null;
                    if (file) {
                      const ext = file.name.split(".").pop()?.toLowerCase() || "";
                      if (!["pdf", "jpg", "jpeg", "png"].includes(ext)) {
                        setActionError(`Файл «${file.name}» не поддерживается. Разрешены: PDF, JPG, PNG.`);
                        e.target.value = "";
                        return;
                      }
                    }
                    setForm((p) => ({ ...p, attachment: file }));
                  }}
                />
                <button
                  type="button"
                  onClick={() => fileInputRef.current?.click()}
                  className="inline-flex items-center gap-1.5 rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm text-gray-600 hover:bg-gray-50"
                >
                  <Paperclip size={14} />
                  {form.attachment ? form.attachment.name : "Прикрепить файл"}
                </button>
              </div>

              {/* Чекбокс */}
              <label className="flex items-center gap-2 text-sm text-gray-700">
                <input
                  type="checkbox"
                  checked={form.sent_to_all_department}
                  onChange={(e) => setForm((p) => ({ ...p, sent_to_all_department: e.target.checked }))}
                  className="rounded border-gray-300"
                />
                Отправить всем сотрудникам выбранных отделов
              </label>
            </div>

            {/* Кнопки */}
            <div className="mt-5 flex flex-wrap items-center justify-end gap-2 border-t border-gray-100 pt-4">
              <button
                type="button"
                onClick={closeModal}
                className="rounded-lg bg-gray-200 px-3 py-2 text-sm font-medium text-gray-700 hover:bg-gray-300"
              >
                Отмена
              </button>

              <button
                type="button"
                onClick={() => handleCreateOrUpdate(modalMode, "draft")}
                disabled={busyKey !== null}
                className="rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-60"
              >
                Сохранить как черновик
              </button>

              <button
                type="button"
                onClick={() => handleCreateOrUpdate(modalMode, "submitted")}
                disabled={busyKey !== null}
                className="rounded-lg bg-sky-500 px-3 py-2 text-sm font-medium text-white hover:bg-sky-600 disabled:opacity-60"
              >
                {modalMode === "create" ? "Создать" : "Сохранить"}
              </button>
            </div>
          </div>
        </div>
      )}
      {/* ===== Attachment preview modal ===== */}
      {attachmentPreview && (
        <div className="fixed inset-0 z-[60] flex items-center justify-center bg-black/50 p-4" onClick={(e) => { if (e.target === e.currentTarget) setAttachmentPreview(null); }}>
          <div className="relative flex max-h-[90vh] w-full max-w-3xl flex-col overflow-hidden rounded-2xl bg-white shadow-xl">
            <div className="flex items-center justify-between border-b border-gray-100 px-4 py-3">
              <p className="truncate text-sm font-medium text-gray-800">{attachmentPreview.name}</p>
              <div className="flex items-center gap-2">
                <a
                  href={attachmentPreview.url}
                  download
                  className="rounded-lg border border-gray-300 px-3 py-1.5 text-xs font-medium text-gray-700 hover:bg-gray-50"
                >
                  Скачать
                </a>
                <button type="button" onClick={() => setAttachmentPreview(null)} className="rounded-lg p-1 text-gray-400 hover:bg-gray-100 hover:text-gray-600">
                  <X size={18} />
                </button>
              </div>
            </div>
            <div className="flex-1 overflow-auto p-4">
              {(() => {
                const url = attachmentPreview.url;
                const ext = url.split(".").pop()?.toLowerCase() || "";
                const imageExts = ["jpg", "jpeg", "png", "gif", "webp", "svg", "bmp"];
                const videoExts = ["mp4", "webm", "ogg", "mov"];
                const audioExts = ["mp3", "wav", "ogg", "aac"];
                const pdfExts = ["pdf"];

                const fallback = (
                  <div className="flex flex-col items-center gap-3 py-12 text-center">
                    <FileSignature size={40} className="text-gray-300" />
                    <p className="text-sm text-gray-500">{attachmentPreview.name}</p>
                    <a
                      href={url}
                      download
                      className="rounded-lg bg-sky-500 px-4 py-2 text-sm font-medium text-white hover:bg-sky-600"
                    >
                      Скачать файл
                    </a>
                  </div>
                );

                if (imageExts.includes(ext)) {
                  return <img src={url} alt={attachmentPreview.name} className="mx-auto max-h-[70vh] rounded-lg object-contain" onError={(e) => { (e.target as HTMLImageElement).style.display = "none"; (e.target as HTMLImageElement).parentElement!.querySelector(".fallback")?.classList.remove("hidden"); }} />;
                }
                if (videoExts.includes(ext)) {
                  return <video src={url} controls className="mx-auto max-h-[70vh] rounded-lg" onError={(e) => { (e.target as HTMLVideoElement).style.display = "none"; (e.target as HTMLVideoElement).parentElement!.querySelector(".fallback")?.classList.remove("hidden"); }} />;
                }
                if (audioExts.includes(ext)) {
                  return <audio src={url} controls className="mx-auto mt-8" onError={(e) => { (e.target as HTMLAudioElement).style.display = "none"; (e.target as HTMLAudioElement).parentElement!.querySelector(".fallback")?.classList.remove("hidden"); }} />;
                }
                if (pdfExts.includes(ext)) {
                  return fallback;
                }
                return fallback;
              })()}
              <div className="fallback hidden">
                <div className="flex flex-col items-center gap-3 py-12 text-center">
                  <FileSignature size={40} className="text-gray-300" />
                  <p className="text-sm text-gray-500">{attachmentPreview.name}</p>
                  <a
                    href={attachmentPreview.url}
                    download
                    className="rounded-lg bg-sky-500 px-4 py-2 text-sm font-medium text-white hover:bg-sky-600"
                  >
                    Скачать файл
                  </a>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </AppShell>
  );
}
