"use client";

import { AppShell } from "../../components/AppShell";
import { apiClient } from "@/lib/api";
import { useUser } from "@/contexts/UserContext";
import { canManageRequests, canProcessRequests } from "@/lib/permissions";
import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import type { Request, RequestComment, User, Department } from "@/types/api";
import { Check, FileSignature, MessageSquare, Plus, Search, X } from "lucide-react";

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
  const [dateFromFilter, setDateFromFilter] = useState("");
  const [dateToFilter, setDateToFilter] = useState("");

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
    if (dateFromFilter) params.date_from = dateFromFilter;
    if (dateToFilter) params.date_to = dateToFilter;
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
  }, [view, typeFilter, statusFilter, employeeFilter, dateFromFilter, dateToFilter]);

  useEffect(() => {
    async function loadLookups() {
      try {
        const [employeesResponse, departmentsResponse] = await Promise.all([
          apiClient.getEmployees({ limit: 200 }),
          apiClient.getDepartments({ limit: 200 }),
        ]);
        setEmployees(employeesResponse.results || []);
        setDepartments(departmentsResponse.results || []);
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
      const aTime = new Date(a.created_at).getTime() || 0;
      const bTime = new Date(b.created_at).getTime() || 0;
      return bTime - aTime;
    });

    if (!q) return sorted;

    return sorted.filter((item) => {
      const title = (item.display_title || item.title || "").toLowerCase();
      const description = (item.comment || item.description || "").toLowerCase();
      const type = String(item.type || item.request_type || "").toLowerCase();
      const author = displayUserName(item.employee || item.created_by).toLowerCase();
      return title.includes(q) || description.includes(q) || type.includes(q) || author.includes(q);
    });
  }, [requests, search]);

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

      const payload = {
        type: form.type,
        title: form.title,
        date_from: form.date_from || null,
        date_to: form.date_to || null,
        comment: form.comment,
        department_ids: form.department_ids,
        recipient_ids: form.recipient_ids,
        cc_user_ids: form.cc_user_ids,
        sent_to_all_department: form.sent_to_all_department,
        attachment: form.attachment,
      };

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
      setActionError(String(e?.message || "Не удалось сохранить заявление"));
    } finally {
      setBusyKey(null);
    }
  };

  const handleLoadMore = async () => {
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
  };

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

  const RequestEditor = ({ mode }: { mode: "create" | "edit" }) => (
    <div className="mt-3 rounded-xl border border-gray-200 bg-gray-50 p-3">
      <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
        <select
          value={form.type}
          onChange={(e) => setForm((p) => ({ ...p, type: e.target.value }))}
          className="rounded-lg border border-gray-300 px-3 py-2 text-sm"
        >
          <option value="">Выберите тип</option>
          {Object.entries(requestTypeLabels).map(([value, label]) => (
            <option key={value} value={value}>
              {label}
            </option>
          ))}
        </select>

        <input
          value={form.title}
          onChange={(e) => setForm((p) => ({ ...p, title: e.target.value }))}
          placeholder="Тема"
          className="rounded-lg border border-gray-300 px-3 py-2 text-sm"
        />

        <input
          type="date"
          value={form.date_from}
          onChange={(e) => setForm((p) => ({ ...p, date_from: e.target.value }))}
          className="rounded-lg border border-gray-300 px-3 py-2 text-sm"
        />

        <input
          type="date"
          value={form.date_to}
          onChange={(e) => setForm((p) => ({ ...p, date_to: e.target.value }))}
          className="rounded-lg border border-gray-300 px-3 py-2 text-sm"
        />

        <select
          multiple
          value={form.department_ids.map(String)}
          onChange={(e) => {
            const values = Array.from(e.target.selectedOptions).map((o) => Number(o.value));
            setForm((p) => ({ ...p, department_ids: values }));
          }}
          className="h-28 rounded-lg border border-gray-300 px-3 py-2 text-sm"
        >
          {departments.map((d) => (
            <option key={d.id} value={d.id}>
              {d.name}
            </option>
          ))}
        </select>

        <select
          multiple
          value={form.recipient_ids.map(String)}
          onChange={(e) => {
            const values = Array.from(e.target.selectedOptions).map((o) => Number(o.value));
            setForm((p) => ({ ...p, recipient_ids: values }));
          }}
          className="h-28 rounded-lg border border-gray-300 px-3 py-2 text-sm"
        >
          {employees
            .filter((emp) => !user?.id || emp.id !== user.id)
            .map((emp) => (
              <option key={emp.id} value={emp.id}>
                {displayUserName(emp)}
              </option>
            ))}
        </select>

        <select
          multiple
          value={form.cc_user_ids.map(String)}
          onChange={(e) => {
            const values = Array.from(e.target.selectedOptions).map((o) => Number(o.value));
            setForm((p) => ({ ...p, cc_user_ids: values }));
          }}
          className="h-28 rounded-lg border border-gray-300 px-3 py-2 text-sm"
        >
          {employees
            .filter((emp) => !user?.id || emp.id !== user.id)
            .map((emp) => (
              <option key={emp.id} value={emp.id}>
                {displayUserName(emp)}
              </option>
            ))}
        </select>

        <textarea
          value={form.comment}
          onChange={(e) => setForm((p) => ({ ...p, comment: e.target.value }))}
          placeholder="Комментарий"
          className="rounded-lg border border-gray-300 px-3 py-2 text-sm sm:col-span-2"
          rows={3}
        />

        <input
          type="file"
          onChange={(e) => setForm((p) => ({ ...p, attachment: e.target.files?.[0] || null }))}
          className="rounded-lg border border-gray-300 px-3 py-2 text-sm sm:col-span-2"
        />
      </div>

      <label className="mt-2 flex items-center gap-2 text-sm text-gray-700">
        <input
          type="checkbox"
          checked={form.sent_to_all_department}
          onChange={(e) => setForm((p) => ({ ...p, sent_to_all_department: e.target.checked }))}
        />
        Отправить всем сотрудникам выбранных отделов
      </label>

      <div className="mt-3 flex flex-wrap items-center justify-end gap-2">
        <button
          type="button"
          onClick={() => {
            if (mode === "create") {
              setCreateOpen(false);
            } else {
              setEditingRequestId(null);
            }
            resetForm();
          }}
          className="rounded-lg bg-gray-200 px-3 py-2 text-sm font-medium text-gray-700 hover:bg-gray-300"
        >
          Отмена
        </button>

        <button
          type="button"
          onClick={() => handleCreateOrUpdate(mode, "draft")}
          disabled={busyKey !== null}
          className="rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-60"
        >
          Сохранить как черновик
        </button>

        <button
          type="button"
          onClick={() => handleCreateOrUpdate(mode, "submitted")}
          disabled={busyKey !== null}
          className="rounded-lg bg-sky-500 px-3 py-2 text-sm font-medium text-white hover:bg-sky-600 disabled:opacity-60"
        >
          {mode === "create" ? "Создать" : "Сохранить"}
        </button>
      </div>
    </div>
  );

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
          <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
            <p className="text-sm font-semibold uppercase tracking-wide text-gray-500">Заявления</p>
            <button
              type="button"
              onClick={() => {
                setCreateOpen((v) => !v);
                setEditingRequestId(null);
                setActionError(null);
                setActionSuccess(null);
                resetForm();
              }}
              className="inline-flex items-center gap-1 rounded-lg bg-sky-500 px-3 py-2 text-sm font-medium text-white hover:bg-sky-600"
            >
              <Plus size={14} /> Создать заявление
            </button>
          </div>

          {actionError ? <p className="mb-3 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{actionError}</p> : null}
          {actionSuccess ? <p className="mb-3 rounded-lg bg-emerald-50 px-3 py-2 text-sm text-emerald-700">{actionSuccess}</p> : null}

          {createOpen ? <RequestEditor mode="create" /> : null}

          <div className="mb-3 grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-4">
            <select value={view} onChange={(e) => setView(e.target.value as "" | "mine" | "addressed")} className="rounded-lg border border-gray-200 bg-gray-50 px-3 py-2 text-sm text-gray-800">
              <option value="">Все доступные</option>
              <option value="mine">Мои заявления</option>
              <option value="addressed">Адресованные мне</option>
            </select>

            <select value={typeFilter} onChange={(e) => setTypeFilter(e.target.value)} className="rounded-lg border border-gray-200 bg-gray-50 px-3 py-2 text-sm text-gray-800">
              <option value="">Любой тип</option>
              {Object.entries(requestTypeLabels).map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </select>

            <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)} className="rounded-lg border border-gray-200 bg-gray-50 px-3 py-2 text-sm text-gray-800">
              <option value="">Любой статус</option>
              {Object.entries(statusMeta).map(([value, meta]) => (
                <option key={value} value={value}>
                  {meta.label}
                </option>
              ))}
            </select>

            <select value={employeeFilter} onChange={(e) => setEmployeeFilter(e.target.value)} className="rounded-lg border border-gray-200 bg-gray-50 px-3 py-2 text-sm text-gray-800">
              <option value="">Любой сотрудник</option>
              {employees.map((emp) => (
                <option key={emp.id} value={emp.id}>
                  {displayUserName(emp)}
                </option>
              ))}
            </select>

            <input type="date" value={dateFromFilter} onChange={(e) => setDateFromFilter(e.target.value)} className="rounded-lg border border-gray-200 bg-gray-50 px-3 py-2 text-sm text-gray-800" />
            <input type="date" value={dateToFilter} onChange={(e) => setDateToFilter(e.target.value)} className="rounded-lg border border-gray-200 bg-gray-50 px-3 py-2 text-sm text-gray-800" />
          </div>

          <div className="relative mb-4">
            <Search size={16} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Поиск по заявлениям"
              className="w-full rounded-lg border border-gray-200 bg-gray-50 py-2.5 pl-9 pr-3 text-sm text-gray-800 transition focus:border-sky-500 focus:bg-white focus:outline-none focus:ring-2 focus:ring-sky-100"
            />
          </div>

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
                const status = statusMeta[statusKey] ?? defaultStatusMeta;
                const authorLink = userProfileLink(requestAuthor);
                const approverLink = userProfileLink(item.approver || item.assigned_to);
                const requestTypeLabel = requestTypeLabels[String(item.type || item.request_type || "")] || String(item.type || item.request_type || "Другое");
                const canProcessThis = Boolean(
                  canProcess &&
                    statusKey === "pending" &&
                    item.is_recipient &&
                    requestAuthor?.id &&
                    user?.id &&
                    requestAuthor.id !== user.id
                );
                const isAuthor = Boolean(requestAuthor?.id && user?.id && requestAuthor.id === user.id);
                const canEditThis = isAuthor && !isFinal(statusKey);
                const canCancelThis = isAuthor && !isFinal(statusKey);
                const canDeleteThis = (isAuthor && !isFinal(statusKey)) || canManage;
                const comments = commentsMap[item.id] || [];
                const commentsOpen = Boolean(expandedComments[item.id]);
                const departmentLabels = (item.departments || [])
                  .map((id) => departmentNameMap.get(Number(id)) || `Отдел #${id}`)
                  .join(", ");

                return (
                  <article key={item.id} className="rounded-xl border border-gray-100 bg-white p-4 transition hover:bg-gray-50">
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0">
                        <p className="truncate text-sm font-semibold text-gray-900">{item.display_title || item.title || "Без заголовка"}</p>
                        <p className="mt-1 text-xs text-gray-500">Тип: {requestTypeLabel}</p>
                      </div>

                      <span className={`inline-flex shrink-0 rounded-full px-2.5 py-1 text-xs ring-1 ${status.className}`}>
                        {status.label}
                      </span>
                    </div>

                    <p className="mt-3 text-sm text-gray-700">{item.comment || item.description || "—"}</p>

                    <div className="mt-3 grid grid-cols-1 gap-2 text-xs text-gray-500 sm:grid-cols-2 lg:grid-cols-3">
                      <p>
                        Автор:{" "}
                        {authorLink ? (
                          <Link href={authorLink} className="text-sky-700 underline decoration-sky-300 underline-offset-2 hover:text-sky-800">
                            {authorName}
                          </Link>
                        ) : (
                          <span>{authorName}</span>
                        )}
                      </p>
                      <p>
                        Решение:{" "}
                        {approverLink && item.approver ? (
                          <Link href={approverLink} className="text-sky-700 underline decoration-sky-300 underline-offset-2 hover:text-sky-800">
                            {approverName}
                          </Link>
                        ) : (
                          <span>{item.approver ? approverName : "—"}</span>
                        )}
                      </p>
                      <p>Получатели: {item.recipient_count ?? item.recipients?.length ?? 0}</p>
                      <p>В копии: {item.cc_count ?? item.cc_users?.length ?? 0}</p>
                      <p>Период: {item.date_from ? formatDate(item.date_from) : "—"}{item.date_to ? ` — ${formatDate(item.date_to)}` : ""}</p>
                      <p>Создано: {formatDate(item.created_at)}</p>
                      <p>Обновлено: {formatDate(item.updated_at)}</p>
                      {departmentLabels ? <p className="sm:col-span-2 lg:col-span-3">Отделы: {departmentLabels}</p> : null}
                    </div>

                    <div className="mt-3 flex flex-wrap gap-2">
                      {canProcessThis ? (
                        <>
                          <button type="button" onClick={() => handleApprove(item.id)} disabled={busyKey === `approve-${item.id}`} className="inline-flex items-center gap-1 rounded-lg bg-emerald-500 px-3 py-1.5 text-xs font-medium text-white hover:bg-emerald-600 disabled:opacity-60">
                            <Check size={14} /> Одобрить
                          </button>
                          <button type="button" onClick={() => handleReject(item.id)} disabled={busyKey === `reject-${item.id}`} className="inline-flex items-center gap-1 rounded-lg bg-rose-500 px-3 py-1.5 text-xs font-medium text-white hover:bg-rose-600 disabled:opacity-60">
                            <X size={14} /> Отклонить
                          </button>
                        </>
                      ) : null}

                      {canEditThis ? (
                        <button type="button" onClick={() => openEdit(item)} className="rounded-lg border border-gray-300 bg-white px-3 py-1.5 text-xs font-medium text-gray-700 hover:bg-gray-50">
                          Редактировать
                        </button>
                      ) : null}

                      {canCancelThis ? (
                        <button type="button" onClick={() => handleCancel(item.id)} disabled={busyKey === `cancel-${item.id}`} className="rounded-lg border border-gray-300 bg-white px-3 py-1.5 text-xs font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-60">
                          Отменить
                        </button>
                      ) : null}

                      {canDeleteThis ? (
                        <button type="button" onClick={() => handleDelete(item.id)} disabled={busyKey === `delete-${item.id}`} className="rounded-lg border border-rose-200 bg-rose-50 px-3 py-1.5 text-xs font-medium text-rose-700 hover:bg-rose-100 disabled:opacity-60">
                          Удалить
                        </button>
                      ) : null}

                      <button
                        type="button"
                        onClick={() => toggleComments(item.id)}
                        className="inline-flex items-center gap-1 rounded-lg border border-gray-300 bg-white px-3 py-1.5 text-xs font-medium text-gray-700 hover:bg-gray-50"
                      >
                        <MessageSquare size={14} /> Комментарии ({item.comments_count ?? comments.length})
                      </button>
                    </div>

                    {editingRequestId === item.id ? <RequestEditor mode="edit" /> : null}

                    {commentsOpen ? (
                      <div className="mt-3 rounded-lg border border-gray-200 bg-gray-50 p-3">
                        <div className="space-y-2">
                          {(commentsMap[item.id] || []).length === 0 ? (
                            <p className="text-xs text-gray-500">Комментариев пока нет</p>
                          ) : (
                            (commentsMap[item.id] || []).map((c) => {
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
                  </article>
                );
              })
            )}
          </div>

          {nextPage ? (
            <div className="mt-4 flex justify-center">
              <button
                type="button"
                onClick={handleLoadMore}
                disabled={loadingMore}
                className="rounded-lg border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-60"
              >
                {loadingMore ? "Загружаем..." : "Загрузить ещё"}
              </button>
            </div>
          ) : null}
        </section>
      )}
    </AppShell>
  );
}
