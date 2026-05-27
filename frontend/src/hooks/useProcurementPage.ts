"use client";

import { useCallback, useDeferredValue, useEffect, useMemo, useRef, useState } from "react";
import { apiClient } from "@/lib/api";
import { canManageRequests, canManageSupplier } from "@/lib/permissions";
import { cleanLinkRows, toLinkRows, validateLinkRows } from "@/lib/procurementLinks";
import { displayUserName, extractNextPage, loadAllPages } from "@/lib/shared";
import type {
  Department,
  ProcurementComment,
  ProcurementItem,
  ProcurementItemComment,
  ProcurementRequest,
  ProcurementStatus,
  UrgencyLevel,
  User,
} from "@/types/api";

type ItemDraft = {
  id?: number;
  name: string;
  description: string;
  quantity: string;
  unit: string;
  estimated_unit_price: string;
  supplier_info: string;
  links: string[];
  initial_comment: string;
};

const emptyItem: ItemDraft = {
  name: "",
  description: "",
  quantity: "1",
  unit: "шт",
  estimated_unit_price: "",
  supplier_info: "",
  links: [],
  initial_comment: "",
};

type FormState = {
  title: string;
  description: string;
  department: number | null;
  requireApproval: boolean;
  processing_department: number | null;
  urgency: UrgencyLevel;
  items: ItemDraft[];
};

const emptyForm: FormState = {
  title: "",
  description: "",
  department: null,
  requireApproval: false,
  processing_department: null,
  urgency: "medium",
  items: [{ ...emptyItem }],
};

type ScopeTab = "all" | "mine" | "department" | "pending_approvals" | "my_work" | "available";
type ProcurementSection = "requests" | "stats" | "suppliers";

type PaginatedLike<T> = {
  results?: T[];
  next?: string | null;
  count?: number;
};

const getPaginatedResults = <T,>(response: unknown): T[] => {
  if (Array.isArray(response)) {
    return response as T[];
  }

  if (response && typeof response === "object") {
    const results = (response as PaginatedLike<T>).results;
    if (Array.isArray(results)) {
      return results;
    }
  }

  return [];
};

const getPaginatedNext = (response: unknown): number | null => {
  if (!response || typeof response !== "object" || Array.isArray(response)) {
    return null;
  }

  return extractNextPage((response as PaginatedLike<unknown>).next ?? null);
};

const getPaginatedCount = (response: unknown): number => {
  if (!response || typeof response !== "object" || Array.isArray(response)) {
    return 0;
  }

  const count = (response as PaginatedLike<unknown>).count;
  return typeof count === "number" && Number.isFinite(count)
    ? count
    : getPaginatedResults(response).length;
};

const getReadableError = (error: unknown, fallback: string): string => {
  const raw = String((error as Error)?.message || fallback);
  const jsonStart = raw.indexOf("{");
  const payload = jsonStart >= 0 ? raw.slice(jsonStart) : raw;

  try {
    const parsed = JSON.parse(payload) as Record<string, unknown>;
    if (typeof parsed === "object" && parsed !== null) {
      if (typeof parsed.error === "string" && parsed.error.trim()) {
        return parsed.error;
      }
      if (typeof parsed.detail === "string" && parsed.detail.trim()) {
        return parsed.detail;
      }
      return Object.entries(parsed)
        .map(([key, value]) => {
          if (Array.isArray(value)) {
            return `${key}: ${value.join(", ")}`;
          }
          return `${key}: ${String(value)}`;
        })
        .join(". ");
    }
  } catch {
    return raw;
  }

  return raw;
};

export function useProcurementPage(user: User | null) {
  const canManage = canManageRequests(user);
  const canSupplierManage = canManageSupplier(user);

  const [requests, setRequests] = useState<ProcurementRequest[]>([]);
  const [departments, setDepartments] = useState<Department[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [actionSuccess, setActionSuccess] = useState<string | null>(null);
  const [busyKey, setBusyKey] = useState<string | null>(null);
  const [nextPage, setNextPage] = useState<number | null>(null);
  const [scopeCounts, setScopeCounts] = useState<Record<ScopeTab, number>>({
    all: 0,
    mine: 0,
    department: 0,
    pending_approvals: 0,
    my_work: 0,
    available: 0,
  });

  const [scope, setScope] = useState<ScopeTab>("all");
  const [searchQuery, setSearchQuery] = useState("");
  const deferredSearchQuery = useDeferredValue(searchQuery);
  const [statusFilter, setStatusFilter] = useState<ProcurementStatus[]>([]);
  const [urgencyFilter, setUrgencyFilter] = useState("");
  const [departmentFilter, setDepartmentFilter] = useState("");
  const [periodFilter, setPeriodFilter] = useState("");
  const [filtersOpen, setFiltersOpen] = useState(false);
  const [ordering, setOrdering] = useState("-created_at");
  const [activeSection, setActiveSection] = useState<ProcurementSection>("requests");

  const [createOpen, setCreateOpen] = useState(false);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [form, setForm] = useState<FormState>(emptyForm);

  const [expandedIds, setExpandedIds] = useState<Set<number>>(new Set());
  const [expandedComments, setExpandedComments] = useState<Record<number, boolean>>({});
  const [commentsMap, setCommentsMap] = useState<Record<number, ProcurementComment[]>>({});
  const [commentDrafts, setCommentDrafts] = useState<Record<number, string>>({});
  const [expandedItemComments, setExpandedItemComments] = useState<Record<number, boolean>>({});
  const [itemCommentsMap, setItemCommentsMap] = useState<Record<number, ProcurementItemComment[]>>({});
  const [itemCommentDrafts, setItemCommentDrafts] = useState<Record<number, string>>({});
  const [detailsCache, setDetailsCache] = useState<Record<number, ProcurementRequest>>({});
  const detailsCacheRef = useRef<Record<number, ProcurementRequest>>({});
  const hasLoadedOnceRef = useRef(false);

  useEffect(() => {
    detailsCacheRef.current = detailsCache;
  }, [detailsCache]);

  const resolveUserId = useCallback((person?: User | number | null) => {
    if (!person) return null;
    return typeof person === "number" ? person : person.id;
  }, []);

  const displayProcurementUserName = useCallback(
    (person?: User | number | null, fallbackName?: string | null, fallbackEmail?: string | null) => (
      displayUserName(person, fallbackName, fallbackEmail)
    ),
    [],
  );

  const userLink = useCallback(
    (person?: User | number | null) => {
      const personId = resolveUserId(person);
      if (!personId) return "";
      return user?.id && personId === user.id ? "/profile" : `/users/${personId}`;
    },
    [resolveUserId, user?.id],
  );

  const getDeptName = useCallback(
    (request: ProcurementRequest) => {
      if (request.department_name) return request.department_name;
      if (request.department_details?.name) return request.department_details.name;
      const department = departments.find((item) => item.id === Number(request.department));
      return department?.name || "—";
    },
    [departments],
  );

  const getRequestAmount = useCallback(
    (request: ProcurementRequest) => request.total_cost ?? request.total_estimated_cost,
    [],
  );

  const buildParams = useCallback(
    (page: number): Record<string, string | number> => {
      const params: Record<string, string | number> = { page };
      if (scope === "mine") params.scope = "mine";
      else if (scope === "department") params.scope = "department";
      else if (scope === "my_work") params.scope = "my_work";
      else if (scope === "available") params.scope = "available";
      if (statusFilter.length === 1) params.status = statusFilter[0];
      else if (statusFilter.length > 1) params.status__in = statusFilter.join(",");
      if (urgencyFilter) params.urgency = urgencyFilter;
      if (departmentFilter) params.department = departmentFilter;
      if (periodFilter) params.period = periodFilter;
      if (deferredSearchQuery.trim()) params.search = deferredSearchQuery.trim();
      return params;
    },
    [deferredSearchQuery, departmentFilter, periodFilter, scope, statusFilter, urgencyFilter],
  );

  const buildScopeCountParams = useCallback(
    (targetScope: ScopeTab): Record<string, string | number> => {
      const params: Record<string, string | number> = { page: 1 };
      if (targetScope === "mine") params.scope = "mine";
      else if (targetScope === "department") params.scope = "department";
      else if (targetScope === "my_work") params.scope = "my_work";
      else if (targetScope === "available") params.scope = "available";
      if (statusFilter.length === 1) params.status = statusFilter[0];
      else if (statusFilter.length > 1) params.status__in = statusFilter.join(",");
      if (urgencyFilter) params.urgency = urgencyFilter;
      if (departmentFilter) params.department = departmentFilter;
      if (periodFilter) params.period = periodFilter;
      if (deferredSearchQuery.trim()) params.search = deferredSearchQuery.trim();
      return params;
    },
    [deferredSearchQuery, departmentFilter, periodFilter, statusFilter, urgencyFilter],
  );

  const loadPage1 = useCallback(async () => {
    try {
      if (!hasLoadedOnceRef.current) {
        setLoading(true);
      }
      setError(null);

      const response: unknown = scope === "pending_approvals"
        ? await apiClient.getPendingApprovals(buildParams(1))
        : await apiClient.getProcurementRequests(buildParams(1));

      setRequests(getPaginatedResults<ProcurementRequest>(response));
      setNextPage(getPaginatedNext(response));
    } catch (loadError) {
      console.error("Load procurement error:", loadError);
      setError("Не удалось загрузить заявки на закупку");
    } finally {
      setLoading(false);
      hasLoadedOnceRef.current = true;
    }
  }, [buildParams, scope]);

  useEffect(() => {
    void loadPage1();
  }, [loadPage1]);

  useEffect(() => {
    let cancelled = false;

    void (async () => {
      try {
        const scopes: ScopeTab[] = ["all", "mine", "department", "pending_approvals", "my_work", "available"];
        const results = await Promise.all(
          scopes.map(async (scopeKey) => {
            const response: unknown = scopeKey === "pending_approvals"
              ? await apiClient.getPendingApprovals(buildScopeCountParams(scopeKey))
              : await apiClient.getProcurementRequests(buildScopeCountParams(scopeKey));
            return [scopeKey, getPaginatedCount(response)] as const;
          }),
        );

        if (!cancelled) {
          setScopeCounts(Object.fromEntries(results) as Record<ScopeTab, number>);
        }
      } catch (countsError) {
        console.error("Load procurement scope counts error:", countsError);
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [buildScopeCountParams]);

  useEffect(() => {
    let cancelled = false;

    void (async () => {
      try {
        const allDepartments = await loadAllPages<Department>((page) => apiClient.getDepartments(page));
        if (!cancelled) {
          setDepartments(allDepartments);
        }
      } catch {
        if (!cancelled) {
          setDepartments([]);
        }
      }
    })();

    return () => {
      cancelled = true;
    };
  }, []);

  const defaultProcessingDepartmentId = useMemo(() => {
    const procurementDepartment = departments.find(
      (department) => department.name.trim().toLocaleLowerCase("ru-RU") === "снабжение",
    );
    return procurementDepartment?.id ?? null;
  }, [departments]);

  useEffect(() => {
    if (
      editingId !== null ||
      form.requireApproval ||
      !defaultProcessingDepartmentId
    ) {
      return;
    }

    setForm((previous) => {
      if (
        previous.requireApproval ||
        previous.processing_department === defaultProcessingDepartmentId
      ) {
        return previous;
      }
      return {
        ...previous,
        processing_department: defaultProcessingDepartmentId,
      };
    });
  }, [defaultProcessingDepartmentId, editingId, form.requireApproval]);

  const filteredRequests = useMemo(() => {
    const urgencyRank: Record<string, number> = {
      low: 1,
      medium: 2,
      high: 3,
      critical: 4,
    };

    return [...requests].sort((left, right) => {
      switch (ordering) {
        case "created_at":
          return (new Date(left.created_at).getTime() || 0) - (new Date(right.created_at).getTime() || 0);
        case "title":
          return String(left.title || "").localeCompare(String(right.title || ""), "ru", { sensitivity: "base" });
        case "urgency":
          return (urgencyRank[left.urgency || "medium"] || 0) - (urgencyRank[right.urgency || "medium"] || 0);
        case "-urgency":
          return (urgencyRank[right.urgency || "medium"] || 0) - (urgencyRank[left.urgency || "medium"] || 0);
        case "-created_at":
        default:
          return (new Date(right.created_at).getTime() || 0) - (new Date(left.created_at).getTime() || 0);
      }
    });
  }, [ordering, requests]);

  const resetForm = useCallback(() => {
    setForm({
      ...emptyForm,
      processing_department: defaultProcessingDepartmentId,
      items: [{ ...emptyItem }],
    });
  }, [defaultProcessingDepartmentId]);

  const openCreate = useCallback(() => {
    setEditingId(null);
    resetForm();
    setActionError(null);
    setActionSuccess(null);
    setCreateOpen(true);
  }, [resetForm]);

  const openEdit = useCallback(async (request: ProcurementRequest) => {
    setCreateOpen(false);
    setActionError(null);
    setActionSuccess(null);

    let detail: ProcurementRequest;
    try {
      detail = detailsCacheRef.current[request.id];
      if (!detail) {
        detail = await apiClient.getProcurementRequest(request.id);
        detailsCacheRef.current = {
          ...detailsCacheRef.current,
          [request.id]: detail,
        };
        setDetailsCache((previous) => ({ ...previous, [request.id]: detail }));
        setRequests((previous) => previous.map((currentRequest) => (
          currentRequest.id === request.id
            ? { ...currentRequest, ...detail }
            : currentRequest
        )));
      }
    } catch {
      setActionError("Не удалось загрузить заявку для редактирования.");
      return;
    }

    setEditingId(request.id);
    setForm({
      title: detail.title || "",
      description: detail.description || "",
      department: detail.department ?? null,
      requireApproval: false,
      processing_department: detail.processing_department ?? null,
      urgency: detail.urgency || "medium",
      items: detail.items && detail.items.length > 0
        ? detail.items.map((item) => ({
            id: item.id,
            name: item.name || "",
            description: item.description || "",
            quantity: String(item.quantity || "1"),
            unit: item.unit || "шт",
            estimated_unit_price: String(item.estimated_unit_price || ""),
            supplier_info: item.supplier_info || "",
            links: toLinkRows(item.links),
            initial_comment: "",
          }))
        : [{ ...emptyItem }],
    });
  }, []);

  const closeModal = useCallback(() => {
    setCreateOpen(false);
    setEditingId(null);
    resetForm();
    setActionError(null);
  }, [resetForm]);

  const modalMode: "create" | "edit" = editingId ? "edit" : "create";
  const isModalOpen = createOpen || editingId !== null;

  const refreshOne = useCallback(async (id: number) => {
    try {
      const updated = await apiClient.getProcurementRequest(id);
      setRequests((previous) => previous.map((request) => (request.id === id ? updated : request)));
      setDetailsCache((previous) => ({ ...previous, [id]: updated }));
    } catch {
      await loadPage1();
    }
  }, [loadPage1]);

  const ensureRequestDetail = useCallback(async (id: number) => {
    const cached = detailsCacheRef.current[id];
    if (cached) {
      return cached;
    }

    const detail = await apiClient.getProcurementRequest(id);
    detailsCacheRef.current = { ...detailsCacheRef.current, [id]: detail };
    setDetailsCache((previous) => ({ ...previous, [id]: detail }));
    setRequests((previous) => previous.map((request) => (
      request.id === id ? { ...request, ...detail } : request
    )));
    return detail;
  }, []);

  const saveRequest = useCallback(async () => {
    try {
      setBusyKey("save");
      setActionError(null);

      if (!form.title.trim()) {
        setActionError("Укажите название заявки.");
        return;
      }
      if (!form.department) {
        setActionError("Выберите отдел.");
        return;
      }
      if (!form.processing_department) {
        setActionError("Выберите отдел-исполнитель.");
        return;
      }

      const validItems = form.items.filter((item) => item.name.trim());
      if (validItems.length === 0) {
        setActionError("Добавьте хотя бы одну позицию.");
        return;
      }

      for (const item of validItems) {
        if (!item.quantity || Number(item.quantity) <= 0) {
          setActionError(`Позиция «${item.name}»: укажите количество.`);
          return;
        }
        const linksError = validateLinkRows(item.links, `Позиция «${item.name}», ссылка`);
        if (linksError) {
          setActionError(linksError);
          return;
        }
      }

      const payload: Record<string, unknown> = {
        title: form.title,
        description: form.description.trim(),
        department: form.department,
        processing_department: form.processing_department,
        urgency: form.urgency,
        items: validItems.map((item) => ({
          id: item.id,
          name: item.name,
          description: item.description || undefined,
          quantity: item.quantity,
          unit: item.unit || "шт",
          estimated_unit_price: item.estimated_unit_price || null,
          supplier_info: item.supplier_info || undefined,
          links: cleanLinkRows(item.links),
          initial_comment: item.initial_comment.trim() || undefined,
        })),
      };

      if (modalMode === "create") {
        await apiClient.createProcurementRequest(payload) as ProcurementRequest;
        setActionSuccess("Заявка создана и направлена в отдел.");
        setCreateOpen(false);
      } else if (editingId) {
        await apiClient.updateProcurementRequest(editingId, {
          title: payload.title,
          description: payload.description,
          urgency: payload.urgency,
          processing_department: payload.processing_department,
          items: payload.items,
        });
        setActionSuccess("Заявка обновлена.");
        setEditingId(null);
      }

      resetForm();
      await loadPage1();
    } catch (saveError) {
      setActionError(getReadableError(saveError, "Ошибка сохранения"));
    } finally {
      setBusyKey(null);
    }
  }, [editingId, form, loadPage1, modalMode, resetForm]);

  const handleSave = useCallback(() => saveRequest(), [saveRequest]);

  const doAction = useCallback(async (key: string, action: () => Promise<unknown>, id: number, successMessage: string) => {
    try {
      setBusyKey(key);
      setActionError(null);
      await action();
      setActionSuccess(successMessage);
      await refreshOne(id);
      return true;
    } catch (actionErrorValue) {
      setActionError(getReadableError(actionErrorValue, "Ошибка"));
      return false;
    } finally {
      setBusyKey(null);
    }
  }, [refreshOne]);

  const handleLoadMore = useCallback(async () => {
    if (!nextPage || loadingMore) return;

    try {
      setLoadingMore(true);
      const response: unknown = scope === "pending_approvals"
        ? await apiClient.getPendingApprovals(buildParams(nextPage))
        : await apiClient.getProcurementRequests(buildParams(nextPage));

      const chunk = getPaginatedResults<ProcurementRequest>(response);
      setRequests((previous) => {
        const known = new Set(previous.map((request) => request.id));
        return [...previous, ...chunk.filter((request) => !known.has(request.id))];
      });
      setNextPage(getPaginatedNext(response));
    } catch {
      setError("Не удалось загрузить ещё");
    } finally {
      setLoadingMore(false);
    }
  }, [buildParams, loadingMore, nextPage, scope]);

  const toggleExpand = useCallback(async (id: number) => {
    setExpandedIds((previous) => {
      const next = new Set(previous);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });

    if (!detailsCacheRef.current[id]) {
      try {
        await ensureRequestDetail(id);
      } catch {
        // ignore detail loading failures for collapsed rows
      }
    }
  }, [ensureRequestDetail]);

  const ensureCommentsLoaded = useCallback(async (id: number) => {
    if (commentsMap[id]) {
      return commentsMap[id];
    }

    const comments = await apiClient.getProcurementComments(id);
    const normalized = Array.isArray(comments) ? comments : [];
    setCommentsMap((previous) => ({ ...previous, [id]: normalized }));
    return normalized;
  }, [commentsMap]);

  const toggleComments = useCallback(async (id: number) => {
    const isOpen = Boolean(expandedComments[id]);
    setExpandedComments((previous) => ({ ...previous, [id]: !isOpen }));

    if (!isOpen && !commentsMap[id]) {
      try {
        await ensureCommentsLoaded(id);
      } catch {
        setActionError("Не удалось загрузить комментарии");
      }
    }
  }, [commentsMap, ensureCommentsLoaded, expandedComments]);

  const updateCachedItem = useCallback((
    requestId: number,
    itemId: number,
    updater: (item: ProcurementItem) => ProcurementItem,
  ) => {
    const updateRequest = (request: ProcurementRequest): ProcurementRequest => {
      if (!Array.isArray(request.items)) {
        return request;
      }

      return {
        ...request,
        items: request.items.map((item) => (item.id === itemId ? updater(item) : item)),
      };
    };

    setRequests((previous) => previous.map((request) => (
      request.id === requestId ? updateRequest(request) : request
    )));
    setDetailsCache((previous) => {
      const detail = previous[requestId];
      if (!detail) {
        return previous;
      }

      const updatedDetail = updateRequest(detail);
      const next = { ...previous, [requestId]: updatedDetail };
      detailsCacheRef.current = { ...detailsCacheRef.current, [requestId]: updatedDetail };
      return next;
    });
  }, []);

  const ensureItemCommentsLoaded = useCallback(async (itemId: number) => {
    if (itemCommentsMap[itemId]) {
      return itemCommentsMap[itemId];
    }

    const comments = await apiClient.getProcurementItemComments(itemId);
    const normalized = Array.isArray(comments) ? comments : [];
    setItemCommentsMap((previous) => ({ ...previous, [itemId]: normalized }));
    return normalized;
  }, [itemCommentsMap]);

  const toggleItemComments = useCallback(async (itemId: number) => {
    const isOpen = Boolean(expandedItemComments[itemId]);
    setExpandedItemComments((previous) => ({ ...previous, [itemId]: !isOpen }));

    if (!isOpen && !itemCommentsMap[itemId]) {
      try {
        await ensureItemCommentsLoaded(itemId);
      } catch {
        setActionError("Не удалось загрузить комментарии позиции");
      }
    }
  }, [ensureItemCommentsLoaded, expandedItemComments, itemCommentsMap]);

  const handleAddComment = useCallback(async (id: number) => {
    const text = (commentDrafts[id] || "").trim();
    if (!text) return;

    try {
      setBusyKey(`comment-${id}`);
      const created = await apiClient.addProcurementComment(id, text);
      setCommentsMap((previous) => ({
        ...previous,
        [id]: [...(previous[id] || []), created],
      }));
      setCommentDrafts((previous) => ({ ...previous, [id]: "" }));
      setRequests((previous) => previous.map((request) => (
        request.id === id
          ? { ...request, comments_count: (request.comments_count || 0) + 1 }
          : request
      )));
      setDetailsCache((previous) => {
        const detail = previous[id];
        if (!detail) return previous;
        return {
          ...previous,
          [id]: { ...detail, comments_count: (detail.comments_count || 0) + 1 },
        };
      });
    } catch {
      setActionError("Не удалось добавить комментарий");
    } finally {
      setBusyKey(null);
    }
  }, [commentDrafts]);

  const handleAddItemComment = useCallback(async (requestId: number, itemId: number) => {
    const text = (itemCommentDrafts[itemId] || "").trim();
    if (!text) return;

    try {
      setBusyKey(`item-comment-${itemId}`);
      const created = await apiClient.addProcurementItemComment(itemId, text);
      setItemCommentsMap((previous) => ({
        ...previous,
        [itemId]: [...(previous[itemId] || []), created],
      }));
      setItemCommentDrafts((previous) => ({ ...previous, [itemId]: "" }));
      updateCachedItem(requestId, itemId, (item) => ({
        ...item,
        comments_count: (item.comments_count || 0) + 1,
      }));
    } catch {
      setActionError("Не удалось добавить комментарий к позиции");
    } finally {
      setBusyKey(null);
    }
  }, [itemCommentDrafts, updateCachedItem]);

  const handleDeleteComment = useCallback(async (requestId: number, commentId: number) => {
    try {
      setBusyKey(`comment-delete-${commentId}`);
      await apiClient.deleteProcurementComment(requestId, commentId);
      setCommentsMap((previous) => ({
        ...previous,
        [requestId]: (previous[requestId] || []).filter((comment) => comment.id !== commentId),
      }));
      setRequests((previous) => previous.map((request) => (
        request.id === requestId
          ? { ...request, comments_count: Math.max(0, (request.comments_count || 0) - 1) }
          : request
      )));
      setDetailsCache((previous) => {
        const detail = previous[requestId];
        if (!detail) return previous;
        return {
          ...previous,
          [requestId]: { ...detail, comments_count: Math.max(0, (detail.comments_count || 0) - 1) },
        };
      });
    } catch {
      setActionError("Не удалось удалить комментарий");
    } finally {
      setBusyKey(null);
    }
  }, []);

  const handleDeleteItemComment = useCallback(async (requestId: number, itemId: number, commentId: number) => {
    try {
      setBusyKey(`item-comment-delete-${commentId}`);
      await apiClient.deleteProcurementItemComment(itemId, commentId);
      setItemCommentsMap((previous) => ({
        ...previous,
        [itemId]: (previous[itemId] || []).filter((comment) => comment.id !== commentId),
      }));
      updateCachedItem(requestId, itemId, (item) => ({
        ...item,
        comments_count: Math.max(0, (item.comments_count || 0) - 1),
      }));
    } catch {
      setActionError("Не удалось удалить комментарий позиции");
    } finally {
      setBusyKey(null);
    }
  }, [updateCachedItem]);

  const handleSubmit = useCallback((id: number) => doAction(
    `submit-${id}`,
    () => apiClient.submitProcurementRequest(id),
    id,
    "Заявка отправлена на согласование.",
  ), [doAction]);

  const handleApprove = useCallback((id: number, comment = "") => {
    return doAction(`approve-${id}`, () => apiClient.approveProcurementRequest(id, comment), id, "Заявка одобрена.");
  }, [doAction]);

  const handleReject = useCallback((id: number, comment = "") => {
    return doAction(`reject-${id}`, () => apiClient.rejectProcurementRequest(id, comment), id, "Заявка отклонена.");
  }, [doAction]);

  const handleStart = useCallback((id: number) => doAction(
    `start-${id}`,
    () => apiClient.startWorkProcurementRequest(id),
    id,
    "Вы взяли заявку в работу.",
  ), [doAction]);

  const handleComplete = useCallback((id: number) => doAction(
    `complete-${id}`,
    () => apiClient.completeProcurementRequest(id),
    id,
    "Заявка закрыта.",
  ), [doAction]);

  const handleMarkAllReceived = useCallback((id: number) => doAction(
    `mark-all-${id}`,
    () => apiClient.markAllReceivedProcurementRequest(id),
    id,
    "Все позиции отмечены полученными.",
  ), [doAction]);

  const handleUpdateItem = useCallback(async (requestId: number, itemId: number, patch: Record<string, unknown>) => {
    try {
      setBusyKey(`item-${itemId}`);
      setActionError(null);
      if (Array.isArray(patch.links)) {
        const linksError = validateLinkRows(patch.links.map((link) => String(link || "")));
        if (linksError) {
          setActionError(linksError);
          return false;
        }
      }
      await apiClient.updateProcurementItem(itemId, patch);
      setActionSuccess("Позиция обновлена.");
      await refreshOne(requestId);
      return true;
    } catch (updateError) {
      setActionError(getReadableError(updateError, "Не удалось обновить позицию"));
      return false;
    } finally {
      setBusyKey(null);
    }
  }, [refreshOne]);

  const handleReportItemIssue = useCallback(async (requestId: number, itemId: number, text = "") => {
    try {
      setBusyKey(`item-issue-${itemId}`);
      setActionError(null);
      await apiClient.reportProcurementItemIssue(itemId, text);
      setActionSuccess("Позиция отмечена как проблемная.");
      await refreshOne(requestId);
      return true;
    } catch (issueError) {
      setActionError(getReadableError(issueError, "Не удалось отметить проблему"));
      return false;
    } finally {
      setBusyKey(null);
    }
  }, [refreshOne]);

  const handleCancel = useCallback((id: number, reason = "") => {
    return doAction(`cancel-${id}`, () => apiClient.cancelProcurementRequest(id, reason), id, "Заявка отменена.");
  }, [doAction]);

  const handleDelete = useCallback(async (id: number) => {
    try {
      setBusyKey(`delete-${id}`);
      setActionError(null);
      await apiClient.deleteProcurementRequest(id);
      setRequests((previous) => previous.filter((request) => request.id !== id));
      setDetailsCache((previous) => {
        const next = { ...previous };
        delete next[id];
        detailsCacheRef.current = next;
        return next;
      });
      setActionSuccess("Заявка удалена.");
      return true;
    } catch (deleteError) {
      setActionError(getReadableError(deleteError, "Не удалось удалить"));
      return false;
    } finally {
      setBusyKey(null);
    }
  }, []);

  const addItemRow = useCallback(() => {
    setForm((previous) => ({ ...previous, items: [{ ...emptyItem }, ...previous.items] }));
  }, []);

  const removeItemRow = useCallback((index: number) => {
    setForm((previous) => ({ ...previous, items: previous.items.filter((_, itemIndex) => itemIndex !== index) }));
  }, []);

  const updateItemRow = useCallback((index: number, patch: Partial<ItemDraft>) => {
    setForm((previous) => ({
      ...previous,
      items: previous.items.map((item, itemIndex) => (itemIndex === index ? { ...item, ...patch } : item)),
    }));
  }, []);

  const activeFilterCount = [
    statusFilter.length > 0,
    urgencyFilter,
    departmentFilter,
    periodFilter,
  ].filter(Boolean).length;
  const isFinal = useCallback((status?: string) => ["completed", "rejected", "cancelled"].includes(String(status || "").toLowerCase()), []);

  return {
    canManage,
    canSupplierManage,
    requests,
    departments,
    defaultProcessingDepartmentId,
    loading,
    loadingMore,
    error,
    actionError,
    actionSuccess,
    busyKey,
    nextPage,
    scopeCounts,
    scope,
    setScope,
    searchQuery,
    setSearchQuery,
    statusFilter,
    setStatusFilter,
    urgencyFilter,
    setUrgencyFilter,
    departmentFilter,
    setDepartmentFilter,
    periodFilter,
    setPeriodFilter,
    filtersOpen,
    setFiltersOpen,
    ordering,
    setOrdering,
    activeSection,
    setActiveSection,
    createOpen,
    editingId,
    form,
    setForm,
    expandedIds,
    expandedComments,
    commentsMap,
    commentDrafts,
    expandedItemComments,
    itemCommentsMap,
    itemCommentDrafts,
    setItemCommentDrafts,
    setCommentDrafts,
    detailsCache,
    filteredRequests,
    openCreate,
    openEdit,
    closeModal,
    modalMode,
    isModalOpen,
    handleSave,
    handleLoadMore,
    toggleExpand,
    toggleComments,
    toggleItemComments,
    ensureCommentsLoaded,
    ensureItemCommentsLoaded,
    handleSubmit,
    handleApprove,
    handleReject,
    handleStart,
    handleComplete,
    handleMarkAllReceived,
    handleUpdateItem,
    handleReportItemIssue,
    handleCancel,
    handleDelete,
    handleAddComment,
    handleDeleteComment,
    handleAddItemComment,
    handleDeleteItemComment,
    addItemRow,
    removeItemRow,
    updateItemRow,
    activeFilterCount,
    isFinal,
    resolveUserId,
    displayUserName: displayProcurementUserName,
    userLink,
    getDeptName,
    getRequestAmount,
    loadPage1,
    refreshOne,
    ensureRequestDetail,
  };
}
