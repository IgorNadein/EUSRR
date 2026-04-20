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
  recipient_ids: number[];
  cc_user_ids: number[];
  attachment: File | null;
};

export type RequestAttachmentPreview = {
  url: string;
  name: string;
};

export const createEmptyForm = (): RequestFormState => ({
  type: "",
  title: "",
  date_from: "",
  date_to: "",
  comment: "",
  recipient_ids: [],
  cc_user_ids: [],
  attachment: null,
});

export const statusMeta: Record<string, { label: string; className: string }> = {
  draft:       { label: "Черновик",          className: "app-badge" },
  pending:     { label: "На рассмотрении",   className: "app-feedback-warning" },
  approved:    { label: "Одобрено",          className: "app-feedback-success" },
  rejected:    { label: "Отклонено",         className: "app-feedback-danger" },
  cancelled:   { label: "Отменено",          className: "app-badge" },
  in_progress: { label: "В работе",          className: "app-selected" },
  completed:   { label: "Завершено",         className: "app-badge-accent" },
};

export const defaultStatusMeta = { label: "Неизвестный статус", className: "app-badge" };

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

export function getRequestDateMode(type: string): "range" | "single" | "optional" {
  switch (String(type || "").toLowerCase()) {
    case "vacation":
    case "sick_leave":
      return "range";
    case "transfer":
    case "dismissal":
      return "single";
    default:
      return "optional";
  }
}

function getRequestSubmitError(form: RequestFormState): string | null {
  if (form.recipient_ids.length === 0) {
    return "Укажите хотя бы одного получателя.";
  }

  if (!form.type) {
    return "Выберите тип заявления.";
  }

  const dateMode = getRequestDateMode(form.type);
  if (dateMode === "range") {
    if (!form.date_from || !form.date_to) {
      return "Укажите обе даты периода.";
    }
    if (form.date_to < form.date_from) {
      return "Дата окончания не может быть раньше даты начала.";
    }
  }

  if (dateMode === "single" && !form.date_from) {
    return "Укажите дату начала.";
  }

  return null;
}

/* ── hook ── */
// eslint-disable-next-line @typescript-eslint/no-unused-vars
export function useRequestsPage(_userId: number | null | undefined) {
  /* data */
  const [requests, setRequests] = useState<Request[]>([]);
  const [employees, setEmployees] = useState<User[]>([]);
  const [departments, setDepartments] = useState<Department[]>([]);
  const [commentsMap, setCommentsMap] = useState<Record<number, RequestComment[]>>({});
  const [commentsLoadingMap, setCommentsLoadingMap] = useState<Record<number, boolean>>({});
  const [expandedRows, setExpandedRows] = useState<Record<number, boolean>>({});
  const [expandedComments, setExpandedComments] = useState<Record<number, boolean>>({});
  const [commentDrafts, setCommentDrafts] = useState<Record<number, string>>({});

  /* form */
  const [createOpen, setCreateOpen] = useState(false);
  const [editingRequest, setEditingRequest] = useState<Request | null>(null);
  const [form, setForm] = useState<RequestFormState>(createEmptyForm);

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
  const [attachmentPreview, setAttachmentPreview] = useState<RequestAttachmentPreview | null>(null);
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

  const pendingDecisionRequests = useMemo(
    () => filteredRequests.filter((request) => String(request.status || "").toLowerCase() === "pending" && request.can_decide),
    [filteredRequests],
  );
  const pendingDecisionCount = pendingDecisionRequests.length;
  const activeFiltersCount = useMemo(
    () => [
      view,
      typeFilter,
      statusFilter,
      employeeFilter,
      createdFromFilter,
      createdToFilter,
      periodFromFilter,
      periodToFilter,
    ].filter(Boolean).length,
    [
      view,
      typeFilter,
      statusFilter,
      employeeFilter,
      createdFromFilter,
      createdToFilter,
      periodFromFilter,
      periodToFilter,
    ],
  );
  const hasActiveFilters = activeFiltersCount > 0;

  /* ── form ── */
  const resetForm = () => setForm(createEmptyForm());

  const openEdit = (req: Request) => {
    setEditingRequest(req);
    setCreateOpen(false);
    setActionError(null);
    setActionSuccess(null);
    setForm({
      type: req.type || req.request_type || "",
      title: req.title || "",
      date_from: req.date_from || "",
      date_to: req.date_to || "",
      comment: req.comment || req.description || "",
      recipient_ids: (req.recipients || []).map((u: User) => u.id).filter(Boolean),
      cc_user_ids: (req.cc_users || []).map((u: User) => u.id).filter(Boolean),
      attachment: null,
    });
  };

  const openCreate = () => {
    setEditingRequest(null);
    resetForm();
    setActionError(null);
    setActionSuccess(null);
    setCreateOpen(true);
  };

  const openSwipeMode = () => setSwipeMode(true);

  const closeModal = () => {
    setCreateOpen(false);
    setEditingRequest(null);
    resetForm();
    setActionError(null);
  };

  const clearFilters = () => {
    setView("");
    setTypeFilter("");
    setStatusFilter("");
    setEmployeeFilter("");
    setCreatedFromFilter("");
    setCreatedToFilter("");
    setPeriodFromFilter("");
    setPeriodToFilter("");
  };

  const toggleFilters = () => setFiltersOpen((value) => !value);

  /* ── CRUD ── */
  const handleCreateOrUpdate = async (mode: "create" | "edit", saveAs: "draft" | "submit") => {
    try {
      setBusyKey(`${mode}-${saveAs}`);
      setActionError(null);
      setActionSuccess(null);

      if (saveAs === "submit") {
        const submitError = getRequestSubmitError(form);
        if (submitError) {
          setActionError(submitError);
          return;
        }
      }

      const payload: Record<string, string | File | number[] | null> = {
        title: form.title,
        date_from: form.date_from || null,
        date_to: form.date_to || null,
        comment: form.comment,
      };
      if (form.type) payload.type = form.type;
      if (form.recipient_ids.length > 0) payload.recipient_ids = form.recipient_ids;
      if (form.cc_user_ids.length > 0) payload.cc_user_ids = form.cc_user_ids;
      if (form.attachment) payload.attachment = form.attachment;

      if (mode === "create") {
        await apiClient.createRequest(payload, saveAs);
        setActionSuccess(saveAs === "draft" ? "Черновик сохранён." : "Заявление отправлено.");
        setCreateOpen(false);
      } else if (editingRequest) {
        await apiClient.updateRequest(editingRequest.id, payload, saveAs);
        setActionSuccess(saveAs === "draft" ? "Черновик обновлён." : "Заявление отправлено.");
        setEditingRequest(null);
      }

      resetForm();
      const response = await apiClient.getRequests(buildRequestParams(1));
      setRequests(response.results || []);
      setNextPage(extractNextPage(response.next));
    } catch (e: unknown) {
      const raw = String((e as Error)?.message || "Не удалось сохранить заявление");
      let readable = raw;
      try {
        const parsed = JSON.parse(raw) as Record<string, string[] | string>;
        readable = Object.values(parsed).flat().join(". ");
      } catch {
        /* keep raw */
      }
      setActionError(readable);
    } finally {
      setBusyKey(null);
    }
  };

  const applyUpdatedRequest = useCallback((updated: Request) => {
    setRequests((prev) => prev.map((request) => (request.id === updated.id ? { ...request, ...updated } : request)));
    setDetailsRequest((prev) => (prev?.id === updated.id ? { ...prev, ...updated } : prev));
  }, []);

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
    try { setBusyKey(`approve-${id}`); setActionError(null); const updated = await apiClient.approveRequest(id); applyUpdatedRequest(updated); }
    catch (e: unknown) { setActionError(String((e as Error)?.message || "Не удалось одобрить")); }
    finally { setBusyKey(null); }
  };

  const handleReject = async (id: number) => {
    try { setBusyKey(`reject-${id}`); setActionError(null); const updated = await apiClient.rejectRequest(id); applyUpdatedRequest(updated); }
    catch (e: unknown) { setActionError(String((e as Error)?.message || "Не удалось отклонить")); }
    finally { setBusyKey(null); }
  };

  const handleCancel = async (id: number) => {
    try { setBusyKey(`cancel-${id}`); setActionError(null); const updated = await apiClient.cancelRequest(id); applyUpdatedRequest(updated); }
    catch (e: unknown) { setActionError(String((e as Error)?.message || "Не удалось отменить")); }
    finally { setBusyKey(null); }
  };

  const handleDelete = async (id: number) => {
    if (!window.confirm("Удалить заявление? Это действие нельзя отменить.")) {
      return;
    }
    try {
      setBusyKey(`delete-${id}`);
      setActionError(null);
      await apiClient.deleteRequest(id);
      setRequests((p) => p.filter((r) => r.id !== id));
      setDetailsRequest((prev) => (prev?.id === id ? null : prev));
    }
    catch (e: unknown) { setActionError(String((e as Error)?.message || "Не удалось удалить")); }
    finally { setBusyKey(null); }
  };

  /* ── comments ── */
  const ensureCommentsLoaded = useCallback(async (requestId: number) => {
    if (commentsMap[requestId] || commentsLoadingMap[requestId]) return;

    setCommentsLoadingMap((prev) => ({ ...prev, [requestId]: true }));
    try {
      const comments = await apiClient.getRequestComments(requestId);
      setCommentsMap((prev) => ({ ...prev, [requestId]: comments }));
    } catch {
      setCommentsMap((prev) => ({ ...prev, [requestId]: [] }));
    } finally {
      setCommentsLoadingMap((prev) => ({ ...prev, [requestId]: false }));
    }
  }, [commentsLoadingMap, commentsMap]);

  const toggleComments = async (requestId: number) => {
    const isOpen = Boolean(expandedComments[requestId]);
    setExpandedComments((p) => ({ ...p, [requestId]: !isOpen }));
    if (!isOpen && !commentsMap[requestId]) {
      await ensureCommentsLoaded(requestId);
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

  const setCommentDraft = useCallback((requestId: number, value: string) => {
    setCommentDrafts((prev) => ({ ...prev, [requestId]: value }));
  }, []);

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

  useEffect(() => {
    const requestId = detailsRequest?.id;
    if (!requestId) return;
    if (String(detailsRequest.status || "").toLowerCase() === "draft") return;
    void ensureCommentsLoaded(requestId);
  }, [detailsRequest, ensureCommentsLoaded]);

  return {
    /* data */
    requests: filteredRequests,
    pendingDecisionRequests,
    employees,
    departments,
    departmentNameMap,
    commentsMap,
    commentsLoadingMap,
    expandedRows,
    expandedComments,
    commentDrafts,
    setCommentDraft,

    /* form */
    form,
    setForm,
    createOpen,
    editingRequest,
    editingRequestId: editingRequest?.id ?? null,
    modalMode: (editingRequest ? "edit" : "create") as "create" | "edit",
    isModalOpen: createOpen || editingRequest !== null,
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
    activeFiltersCount,
    hasActiveFilters,
    pendingDecisionCount,
    clearFilters,
    toggleFilters,
    openSwipeMode,

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

export type RequestsPageController = ReturnType<typeof useRequestsPage>;
