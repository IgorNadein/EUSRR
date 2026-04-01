"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { apiClient } from "@/lib/api";
import type { Request, RequestComment, User, Department } from "@/types/api";
import { extractNextPage, loadAllPages, displayUserName } from "@/lib/shared";

/* ── constants ── */
export type RequestFormState = {
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

export const emptyForm: RequestFormState = {
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

export const statusMeta: Record<string, { label: string; className: string }> = {
  draft:       { label: "Черновик",          className: "bg-slate-100 text-slate-700 ring-slate-200" },
  pending:     { label: "На рассмотрении",   className: "bg-amber-50 text-amber-700 ring-amber-100" },
  approved:    { label: "Одобрено",          className: "bg-emerald-50 text-emerald-700 ring-emerald-100" },
  rejected:    { label: "Отклонено",         className: "bg-rose-50 text-rose-700 ring-rose-100" },
  cancelled:   { label: "Отменено",          className: "bg-gray-100 text-gray-700 ring-gray-200" },
  in_progress: { label: "В работе",          className: "bg-sky-50 text-sky-700 ring-sky-100" },
  completed:   { label: "Завершено",         className: "bg-violet-50 text-violet-700 ring-violet-100" },
};

export const defaultStatusMeta = { label: "Неизвестный статус", className: "bg-gray-50 text-gray-700 ring-gray-200" };

export const requestTypeLabels: Record<string, string> = {
  vacation: "Отпуск",
  sick_leave: "Больничный",
  day_off: "Отгул",
  transfer: "Перевод",
  dismissal: "Увольнение",
  other: "Другое",
};

export const orderingOptions = [
  { value: "-created_at", label: "Сначала новые" },
  { value: "created_at",  label: "Сначала старые" },
  { value: "title",       label: "По названию" },
  { value: "date_from",   label: "По периоду ↑" },
  { value: "-date_from",  label: "По периоду ↓" },
];

/* ── hook ── */
// eslint-disable-next-line @typescript-eslint/no-unused-vars
export function useRequestsPage(_userId: number | null | undefined) {
  /* data */
  const [requests, setRequests] = useState<Request[]>([]);
  const [employees, setEmployees] = useState<User[]>([]);
  const [departments, setDepartments] = useState<Department[]>([]);
  const [commentsMap, setCommentsMap] = useState<Record<number, RequestComment[]>>({});
  const [expandedRows, setExpandedRows] = useState<Record<number, boolean>>({});
  const [expandedComments, setExpandedComments] = useState<Record<number, boolean>>({});
  const [commentDrafts, setCommentDrafts] = useState<Record<number, string>>({});

  /* form */
  const [createOpen, setCreateOpen] = useState(false);
  const [editingRequestId, setEditingRequestId] = useState<number | null>(null);
  const [form, setForm] = useState<RequestFormState>(emptyForm);

  /* filters */
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
  const [swipeMode, setSwipeMode] = useState(false);

  /* UI */
  const [attachmentPreview, setAttachmentPreview] = useState<{ url: string; name: string } | null>(null);
  const [detailsRequest, setDetailsRequest] = useState<Request | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [actionSuccess, setActionSuccess] = useState<string | null>(null);
  const [busyKey, setBusyKey] = useState<string | null>(null);
  const [nextPage, setNextPage] = useState<number | null>(null);

  const departmentNameMap = useMemo(
    () => new Map((departments || []).map((d) => [d.id, d.name])),
    [departments],
  );

  /* ── params ── */
  const buildRequestParams = useCallback(
    (page: number): Record<string, string | number> => {
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
    },
    [view, typeFilter, statusFilter, employeeFilter, createdFromFilter, createdToFilter, periodFromFilter, periodToFilter],
  );

  /* ── load data ── */
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        setLoading(true);
        setError(null);
        const response = await apiClient.getRequests(buildRequestParams(1));
        if (cancelled) return;
        setRequests(response.results || []);
        setNextPage(extractNextPage(response.next));
      } catch (err) {
        if (!cancelled) {
          console.error("Ошибка загрузки заявлений:", err);
          setError("Не удалось загрузить заявления");
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [buildRequestParams]);

  useEffect(() => {
    (async () => {
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
    })();
  }, []);

  /* ── filtered + sorted ── */
  const filteredRequests = useMemo(() => {
    const q = search.trim().toLowerCase();
    const sorted = [...requests].sort((a, b) => {
      switch (ordering) {
        case "created_at":
          return (new Date(a.created_at).getTime() || 0) - (new Date(b.created_at).getTime() || 0);
        case "title": {
          const l = String(a.display_title || a.title || "").trim();
          const r = String(b.display_title || b.title || "").trim();
          return l.localeCompare(r, "ru", { sensitivity: "base" });
        }
        case "date_from":
          return (new Date(a.date_from || 0).getTime() || 0) - (new Date(b.date_from || 0).getTime() || 0);
        case "-date_from":
          return (new Date(b.date_from || 0).getTime() || 0) - (new Date(a.date_from || 0).getTime() || 0);
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

  /* ── form ── */
  const resetForm = () => setForm(emptyForm);

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
      recipient_ids: (req.recipients || []).map((u: User) => u.id).filter(Boolean),
      cc_user_ids: (req.cc_users || []).map((u: User) => u.id).filter(Boolean),
      sent_to_all_department: Boolean(req.sent_to_all_department),
      attachment: null,
    });
  };

  const openCreate = () => {
    setEditingRequestId(null);
    resetForm();
    setActionError(null);
    setActionSuccess(null);
    setCreateOpen(true);
  };

  const closeModal = () => {
    setCreateOpen(false);
    setEditingRequestId(null);
    resetForm();
    setActionError(null);
  };

  /* ── CRUD ── */
  const handleCreateOrUpdate = async (mode: "create" | "edit", saveAs: "draft" | "submitted") => {
    try {
      setBusyKey(`${mode}-${saveAs}`);
      setActionError(null);
      setActionSuccess(null);

      if (saveAs === "submitted" && !form.sent_to_all_department && form.department_ids.length === 0 && form.recipient_ids.length === 0) {
        setActionError("Укажите получателей или отделы.");
        return;
      }

      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const payload: Record<string, any> = {
        type: form.type,
        title: form.title,
        date_from: form.date_from || null,
        date_to: form.date_to || null,
        comment: form.comment,
        sent_to_all_department: form.sent_to_all_department,
      };
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
    } catch (e: unknown) {
      const raw = String((e as Error)?.message || "Не удалось сохранить заявление");
      let readable = raw;
      try { const parsed = JSON.parse(raw); readable = Object.values(parsed).flat().join(". "); } catch { /* keep raw */ }
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
        return [...prev, ...chunk.filter((r: Request) => !known.has(r.id))];
      });
      setNextPage(extractNextPage(response.next));
    } catch (e: unknown) {
      setError(String((e as Error)?.message || "Не удалось загрузить ещё заявления"));
    } finally {
      setLoadingMore(false);
    }
  }, [nextPage, loadingMore, buildRequestParams]);

  const handleApprove = async (id: number) => {
    try { setBusyKey(`approve-${id}`); setActionError(null); await apiClient.approveRequest(id); setRequests((p) => p.map((r) => (r.id === id ? { ...r, status: "approved" } : r))); }
    catch (e: unknown) { setActionError(String((e as Error)?.message || "Не удалось одобрить")); }
    finally { setBusyKey(null); }
  };

  const handleReject = async (id: number) => {
    try { setBusyKey(`reject-${id}`); setActionError(null); await apiClient.rejectRequest(id); setRequests((p) => p.map((r) => (r.id === id ? { ...r, status: "rejected" } : r))); }
    catch (e: unknown) { setActionError(String((e as Error)?.message || "Не удалось отклонить")); }
    finally { setBusyKey(null); }
  };

  const handleCancel = async (id: number) => {
    try { setBusyKey(`cancel-${id}`); setActionError(null); await apiClient.cancelRequest(id); setRequests((p) => p.map((r) => (r.id === id ? { ...r, status: "cancelled" } : r))); }
    catch (e: unknown) { setActionError(String((e as Error)?.message || "Не удалось отменить")); }
    finally { setBusyKey(null); }
  };

  const handleDelete = async (id: number) => {
    try { setBusyKey(`delete-${id}`); setActionError(null); await apiClient.deleteRequest(id); setRequests((p) => p.filter((r) => r.id !== id)); }
    catch (e: unknown) { setActionError(String((e as Error)?.message || "Не удалось удалить")); }
    finally { setBusyKey(null); }
  };

  /* ── comments ── */
  const toggleComments = async (requestId: number) => {
    const isOpen = Boolean(expandedComments[requestId]);
    setExpandedComments((p) => ({ ...p, [requestId]: !isOpen }));
    if (!isOpen && !commentsMap[requestId]) {
      try { const c = await apiClient.getRequestComments(requestId); setCommentsMap((p) => ({ ...p, [requestId]: c })); }
      catch { setCommentsMap((p) => ({ ...p, [requestId]: [] })); }
    }
  };

  const toggleRow = (requestId: number) => setExpandedRows((p) => ({ ...p, [requestId]: !p[requestId] }));

  const handleAddComment = async (requestId: number) => {
    const text = (commentDrafts[requestId] || "").trim();
    if (!text) return;
    try {
      setBusyKey(`comment-${requestId}`);
      const saved = await apiClient.addRequestComment(requestId, text);
      setCommentsMap((p) => ({ ...p, [requestId]: [...(p[requestId] || []), saved] }));
      setCommentDrafts((p) => ({ ...p, [requestId]: "" }));
    } catch (e: unknown) { setActionError(String((e as Error)?.message || "Не удалось добавить комментарий")); }
    finally { setBusyKey(null); }
  };

  const handleDeleteComment = async (requestId: number, commentId: number) => {
    try {
      setBusyKey(`comment-delete-${commentId}`);
      await apiClient.deleteRequestComment(requestId, commentId);
      setCommentsMap((p) => ({ ...p, [requestId]: (p[requestId] || []).filter((c) => c.id !== commentId) }));
    } catch (e: unknown) { setActionError(String((e as Error)?.message || "Не удалось удалить комментарий")); }
    finally { setBusyKey(null); }
  };

  const isFinal = (status?: string) => ["approved", "rejected", "cancelled"].includes(String(status || "").toLowerCase());

  const loadMoreRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const observer = new IntersectionObserver(
      (entries) => { if (entries[0].isIntersecting && nextPage && !loadingMore && !loading) handleLoadMore(); },
      { rootMargin: "100px" },
    );
    const el = loadMoreRef.current;
    if (el) observer.observe(el);
    return () => { if (el) observer.unobserve(el); };
  }, [nextPage, loadingMore, loading, handleLoadMore]);

  return {
    /* data */
    requests: filteredRequests,
    employees,
    departments,
    departmentNameMap,
    commentsMap,
    expandedRows,
    expandedComments,
    commentDrafts,
    setCommentDrafts,

    /* form */
    form,
    setForm,
    createOpen,
    editingRequestId,
    modalMode: (editingRequestId ? "edit" : "create") as "create" | "edit",
    isModalOpen: createOpen || editingRequestId !== null,
    openCreate,
    openEdit,
    closeModal,
    handleCreateOrUpdate,

    /* filters */
    search, setSearch,
    view, setView,
    typeFilter, setTypeFilter,
    statusFilter, setStatusFilter,
    employeeFilter, setEmployeeFilter,
    createdFromFilter, setCreatedFromFilter,
    createdToFilter, setCreatedToFilter,
    periodFromFilter, setPeriodFromFilter,
    periodToFilter, setPeriodToFilter,
    filtersOpen, setFiltersOpen,
    ordering, setOrdering,
    swipeMode, setSwipeMode,

    /* UI */
    attachmentPreview, setAttachmentPreview,
    detailsRequest, setDetailsRequest,
    loading, loadingMore, error,
    actionError, actionSuccess,
    busyKey, nextPage,
    loadMoreRef,

    /* actions */
    handleApprove, handleReject, handleCancel, handleDelete,
    toggleRow, toggleComments, handleAddComment, handleDeleteComment,
    isFinal,
  };
}
