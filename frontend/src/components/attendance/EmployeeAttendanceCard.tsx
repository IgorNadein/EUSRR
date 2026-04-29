"use client";

import { useEffect, useMemo, useState, type FormEvent } from "react";
import {
  AlertTriangle,
  Camera,
  ChevronDown,
  Clock,
  Edit3,
  Loader2,
  LogIn,
  LogOut,
  MessageSquare,
  RefreshCw,
} from "lucide-react";

import {
  AttendanceDayEventsModal,
  type AttendanceDayEventsPreview,
} from "@/components/attendance/AttendanceDayEventsModal";
import { CommentComposer, CommentDeleteButton } from "@/components/shared/CommentControls";
import { Modal } from "@/components/ui";
import { useUser } from "@/contexts/UserContext";
import { apiClient } from "@/lib/api";
import { displayUserName, formatDate } from "@/lib/shared";
import type {
  AttendanceRecordComment,
  AttendanceAnalysisResponse,
  AttendanceRecord,
  AttendanceRecordUpdatePayload,
  PaginatedAttendanceRecords,
} from "@/lib/api/attendance";
import type { EmployeeAction } from "@/types/api";

type EmployeeAttendanceCardProps = {
  employeeId: number;
  employeeActions?: EmployeeAction[] | null;
};

const attendancePeriods = [
  { value: "week", label: "За неделю" },
  { value: "month", label: "За месяц" },
  { value: "year", label: "За год" },
  { value: "custom", label: "Свой период" },
] as const;

type AttendancePeriod = (typeof attendancePeriods)[number]["value"];

function toDateInputValue(date: Date) {
  return date.toISOString().slice(0, 10);
}

function getPeriodRange(period: Exclude<AttendancePeriod, "custom">) {
  const end = new Date();
  const start = new Date(end);

  if (period === "week") {
    start.setDate(start.getDate() - 6);
  } else if (period === "month") {
    start.setMonth(start.getMonth() - 1);
  } else {
    start.setFullYear(start.getFullYear() - 1);
  }

  return {
    start: toDateInputValue(start),
    end: toDateInputValue(end),
  };
}

function formatTime(value: unknown) {
  if (!value) return "Нет";
  return String(value);
}

function formatHours(value: unknown) {
  if (value === null || value === undefined || value === "") return "0";
  const numeric = Number(value);
  if (Number.isFinite(numeric)) {
    return numeric.toLocaleString("ru-RU", { maximumFractionDigits: 2 });
  }
  return String(value);
}

function formatDateLabel(value: unknown) {
  if (!value) return "Нет даты";
  const date = new Date(String(value));
  if (Number.isNaN(date.getTime())) return String(value);
  return date.toLocaleDateString("ru-RU", {
    day: "2-digit",
    month: "short",
    weekday: "short",
  });
}

type PersonnelDayMeta = {
  action: EmployeeAction;
  className: string;
  label: string;
  nonWorking: boolean;
};

type AttendanceRecordEditForm = {
  recordId: number;
  arrival_time: string;
  departure_time: string;
  work_hours: string;
  expected_hours: string;
  is_workday: boolean;
  effective_is_workday: boolean;
  is_late: boolean;
  late_minutes: string;
  is_early_leave: boolean;
  early_leave_minutes: string;
  is_underwork: boolean;
  underwork_hours: string;
  is_overtime: boolean;
  overtime_hours: string;
  is_absent: boolean;
};

type AttendanceRecordBooleanEditField = {
  [Key in keyof AttendanceRecordEditForm]: AttendanceRecordEditForm[Key] extends boolean ? Key : never;
}[keyof AttendanceRecordEditForm];

const attendanceRecordBooleanFields: Array<{
  key: AttendanceRecordBooleanEditField;
  label: string;
}> = [
  { key: "is_workday", label: "Рабочий по календарю" },
  { key: "effective_is_workday", label: "Учитывать как рабочий" },
  { key: "is_absent", label: "Отсутствие" },
  { key: "is_late", label: "Опоздание" },
  { key: "is_early_leave", label: "Ранний уход" },
  { key: "is_underwork", label: "Недоработка" },
  { key: "is_overtime", label: "Переработка" },
];

const suppressedByPersonnelStateMarkers = [
  "absence",
  "absent",
  "late",
  "early",
  "underwork",
  "отсутств",
  "опозд",
  "ранн",
  "недоработ",
];

const attendanceIssueLabelMap: Record<string, string> = {
  absence: "Отсутствие",
  absent: "Отсутствие",
  late: "Опоздание",
  early_leave: "Ранний уход",
  early: "Ранний уход",
  underwork: "Недоработка",
  overtime: "Переработка",
  technical: "Техническая проблема",
  work_outside_personnel_schedule: "Работа вне графика",
};

function formatAttendanceIssueLabel(label: string) {
  const normalized = label.trim().toLowerCase();
  return attendanceIssueLabelMap[normalized] || label;
}

function hasWorked(record: AttendanceRecord) {
  const hours = Number(record.work_hours || 0);
  return Boolean(record.arrival_time || record.departure_time || hours > 0);
}

function getDateEnd(value: unknown) {
  if (!value) return null;
  const date = new Date(String(value));
  if (Number.isNaN(date.getTime())) return null;
  date.setHours(23, 59, 59, 999);
  return date;
}

function getPersonnelDayMeta(
  actions: EmployeeAction[] | null | undefined,
  dateValue: unknown,
  record?: AttendanceRecord,
): PersonnelDayMeta | null {
  if (record?.personnel_status && record.personnel_status !== "normal") {
    const personnelStatus = String(record.personnel_status);
    return {
      action: {
        id: Number(record.personnel_action || 0),
        employee: 0,
        action: personnelStatus,
        action_display: record.personnel_status_label || record.personnel_status,
        date: String(dateValue || ""),
      },
      className: personnelStatus === "dismissed"
        ? "text-red-400"
        : personnelStatus === "remote"
          ? "text-sky-400"
          : "text-amber-500",
      label: record.personnel_status_label || record.personnel_status,
      nonWorking: record.effective_is_workday === false,
    };
  }

  if (!actions?.length) return null;

  const dayEnd = getDateEnd(dateValue);
  if (!dayEnd) return null;

  const activeAction = actions
    .filter((action) => {
      const actionDate = new Date(action.date);
      return !Number.isNaN(actionDate.getTime()) && actionDate <= dayEnd;
    })
    .sort((left, right) => new Date(right.date).getTime() - new Date(left.date).getTime())[0];

  if (!activeAction) return null;

  if (activeAction.action === "on_leave") {
    return {
      action: activeAction,
      className: "text-amber-500",
      label: activeAction.action_display || "В отпуске",
      nonWorking: true,
    };
  }

  if (activeAction.action === "on_sick_leave") {
    return {
      action: activeAction,
      className: "text-amber-500",
      label: activeAction.action_display || "На больничном",
      nonWorking: true,
    };
  }

  if (activeAction.action === "on_day_off") {
    return {
      action: activeAction,
      className: "text-amber-500",
      label: activeAction.action_display || "В отгуле",
      nonWorking: true,
    };
  }

  if (activeAction.action === "on_maternity") {
    return {
      action: activeAction,
      className: "text-amber-500",
      label: activeAction.action_display || "В декрете",
      nonWorking: true,
    };
  }

  if (activeAction.action === "dismissed") {
    return {
      action: activeAction,
      className: "text-red-400",
      label: activeAction.action_display || "Уволен",
      nonWorking: true,
    };
  }

  if (activeAction.action === "remote") {
    return {
      action: activeAction,
      className: "text-sky-400",
      label: activeAction.action_display || "На удалёнке",
      nonWorking: false,
    };
  }

  return null;
}

function isRemotePersonnelMeta(personnelMeta?: PersonnelDayMeta | null) {
  return personnelMeta?.action.action === "remote";
}

function isRemoteNonWorkingReason(value?: string) {
  return String(value || "").toLowerCase().replaceAll("ё", "е").includes("удален");
}

function issueLabels(record: AttendanceRecord, personnelMeta?: PersonnelDayMeta | null) {
  const labels = [
    ...(record.statuses || []),
    ...(record.employee_issues || []),
    ...(record.technical_issues || []),
  ].map(String);
  const nonWorking = personnelMeta?.nonWorking || record.effective_is_workday === false || record.is_workday === false;

  const effectiveLabels = nonWorking
    ? labels.filter((label) => {
      const normalized = label.toLowerCase();
      return !suppressedByPersonnelStateMarkers.some((marker) => normalized.includes(marker));
    })
    : labels;

  const result = [...effectiveLabels];
  if (!nonWorking && !isRemotePersonnelMeta(personnelMeta)) {
    if (record.is_absent) result.push("absence");
    if (record.is_late) result.push("late");
    if (record.is_early_leave) result.push("early_leave");
    if (record.is_underwork) result.push("underwork");
    if (record.is_overtime) result.push("overtime");
  }
  return Array.from(new Set(result));
}

function getRecordTone(record: AttendanceRecord, personnelMeta?: PersonnelDayMeta | null) {
  const nonWorking = personnelMeta?.nonWorking || record.effective_is_workday === false || record.is_workday === false;

  if (nonWorking && hasWorked(record)) {
    return {
      dotClassName: "bg-sky-500",
      pillClassName: "app-selected",
      label: "Работа вне графика",
    };
  }

  const labels = issueLabels(record, personnelMeta);

  if (labels.length > 0) {
    return {
      dotClassName: "bg-amber-500",
      pillClassName: "app-feedback-warning",
      label: "Есть замечания",
    };
  }

  if (nonWorking) {
    return {
      dotClassName: "bg-slate-400",
      pillClassName: "app-badge",
      label: "Нерабочий",
    };
  }

  if (isRemotePersonnelMeta(personnelMeta)) {
    return {
      dotClassName: "bg-sky-500",
      pillClassName: "app-selected",
      label: personnelMeta?.label || "На удалёнке",
    };
  }

  return {
    dotClassName: "bg-emerald-500",
    pillClassName: "app-feedback-success",
    label: "Без замечаний",
  };
}

function getWorkdayMeta(record: AttendanceRecord, personnelMeta?: PersonnelDayMeta | null) {
  if (personnelMeta?.nonWorking && isRemotePersonnelMeta(personnelMeta) && !record.is_workday) {
    const reason = !isRemoteNonWorkingReason(record.non_working_reason)
      ? record.non_working_reason
      : "";
    return {
      className: "text-gray-500",
      label: "Нерабочий день",
      reason: reason || "Выходной по графику/календарю",
    };
  }

  if (personnelMeta?.nonWorking) {
    return {
      className: personnelMeta.className,
      label: personnelMeta.label,
      reason: record.non_working_reason || personnelMeta.label,
    };
  }

  if (record.is_workday) {
    return {
      className: "text-amber-600",
      label: "Рабочий день",
      reason: "",
    };
  }

  const nonWorkingReason = isRemotePersonnelMeta(personnelMeta)
    ? ""
    : record.non_working_reason;

  return {
    className: "text-gray-500",
    label: "Нерабочий день",
    reason: nonWorkingReason || "Выходной по графику/календарю",
  };
}

function getIssueBadgeClassName(label: string) {
  const normalized = label.toLowerCase();

  if (normalized.includes("overtime")) return "app-selected";
  if (normalized.includes("technical")) return "app-badge";
  if (normalized.includes("absence") || normalized.includes("late") || normalized.includes("early") || normalized.includes("underwork")) {
    return "app-feedback-warning";
  }

  return "app-badge";
}

function getErrorMessage(error: unknown, fallback: string) {
  return String((error as Error)?.message || fallback);
}

function getRecordId(record: AttendanceRecord) {
  const value = Number(record.id);
  return Number.isFinite(value) && value > 0 ? value : null;
}

function attendanceRecordDetails(record: AttendanceRecord, workdayMeta: ReturnType<typeof getWorkdayMeta>) {
  return [
    `Приход: ${formatTime(record.arrival_time)}`,
    `Уход: ${formatTime(record.departure_time)}`,
    `Часы: ${formatHours(record.work_hours)} / ${formatHours(record.expected_hours)}`,
    `Рабочий день: ${record.effective_is_workday === false || record.is_workday === false ? "нет" : "да"}`,
    ...(workdayMeta.reason ? [`Причина: ${workdayMeta.reason}`] : []),
    ...(record.comments_count ? [`Комментарии: ${record.comments_count}`] : []),
  ];
}

function valueToEditString(value: unknown) {
  if (value === null || value === undefined) return "";
  return String(value);
}

function recordToEditForm(record: AttendanceRecord): AttendanceRecordEditForm | null {
  const recordId = getRecordId(record);
  if (!recordId) return null;

  return {
    recordId,
    arrival_time: valueToEditString(record.arrival_time),
    departure_time: valueToEditString(record.departure_time),
    work_hours: valueToEditString(record.work_hours),
    expected_hours: valueToEditString(record.expected_hours),
    is_workday: Boolean(record.is_workday),
    effective_is_workday: record.effective_is_workday ?? Boolean(record.is_workday),
    is_late: Boolean(record.is_late),
    late_minutes: valueToEditString(record.late_minutes),
    is_early_leave: Boolean(record.is_early_leave),
    early_leave_minutes: valueToEditString(record.early_leave_minutes),
    is_underwork: Boolean(record.is_underwork),
    underwork_hours: valueToEditString(record.underwork_hours),
    is_overtime: Boolean(record.is_overtime),
    overtime_hours: valueToEditString(record.overtime_hours),
    is_absent: Boolean(record.is_absent),
  };
}

function nullableNumber(value: string) {
  if (value.trim() === "") return null;
  const numeric = Number(value);
  return Number.isFinite(numeric) ? numeric : null;
}

function nullableTime(value: string) {
  const trimmed = value.trim();
  return trimmed || null;
}

type AttendanceCardApiClient = typeof apiClient & {
  request: <T>(endpoint: string, options?: RequestInit) => Promise<T>;
  addAttendanceRecordComment?: unknown;
  analyzeAttendance?: unknown;
  deleteAttendanceRecordComment?: unknown;
  getAttendanceRecordComments?: unknown;
  getAttendanceRecords?: unknown;
  updateAttendanceRecord?: unknown;
};

function buildAttendanceQuery(params?: Record<string, string | number | undefined>) {
  if (!params) return "";
  const query = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== "") query.append(key, String(value));
  });
  const serialized = query.toString();
  return serialized ? `?${serialized}` : "";
}

function attendanceApiClient() {
  return apiClient as AttendanceCardApiClient;
}

function analyzeEmployeeAttendance(data: {
  employee_id: number;
  period_start: string;
  period_end: string;
}) {
  const client = attendanceApiClient();
  if (typeof client.analyzeAttendance === "function") {
    return client.analyzeAttendance(data) as Promise<AttendanceAnalysisResponse>;
  }
  return client.request<AttendanceAnalysisResponse>(
    "/api/v1/attendance/logstorm/analyze/",
    {
      method: "POST",
      body: JSON.stringify(data),
    },
  );
}

function getAttendanceRecords(params: {
  employee_id: number;
  date_from: string;
  date_to: string;
}) {
  const client = attendanceApiClient();
  if (typeof client.getAttendanceRecords === "function") {
    return client.getAttendanceRecords(params) as Promise<PaginatedAttendanceRecords>;
  }
  return client.request<PaginatedAttendanceRecords>(
    `/api/v1/attendance/records/${buildAttendanceQuery(params)}`,
  );
}

function getAttendanceRecordComments(recordId: number) {
  const client = attendanceApiClient();
  if (typeof client.getAttendanceRecordComments === "function") {
    return client.getAttendanceRecordComments(recordId) as Promise<AttendanceRecordComment[]>;
  }
  return client.request<AttendanceRecordComment[]>(
    `/api/v1/attendance/records/${recordId}/comments/`,
  );
}

function addAttendanceRecordComment(recordId: number, text: string) {
  const client = attendanceApiClient();
  if (typeof client.addAttendanceRecordComment === "function") {
    return client.addAttendanceRecordComment(recordId, text) as Promise<AttendanceRecordComment>;
  }
  return client.request<AttendanceRecordComment>(
    `/api/v1/attendance/records/${recordId}/comments/`,
    {
      method: "POST",
      body: JSON.stringify({ text }),
    },
  );
}

function deleteAttendanceRecordComment(recordId: number, commentId: number) {
  const client = attendanceApiClient();
  if (typeof client.deleteAttendanceRecordComment === "function") {
    return client.deleteAttendanceRecordComment(recordId, commentId) as Promise<void>;
  }
  return client.request<void>(
    `/api/v1/attendance/records/${recordId}/comments/${commentId}/`,
    { method: "DELETE" },
  );
}

function updateAttendanceRecord(recordId: number, data: AttendanceRecordUpdatePayload) {
  const client = attendanceApiClient();
  if (typeof client.updateAttendanceRecord === "function") {
    return client.updateAttendanceRecord(recordId, data) as Promise<AttendanceRecord>;
  }
  return client.request<AttendanceRecord>(
    `/api/v1/attendance/records/${recordId}/`,
    {
      method: "PATCH",
      body: JSON.stringify(data),
    },
  );
}

export default function EmployeeAttendanceCard({
  employeeActions,
  employeeId,
}: EmployeeAttendanceCardProps) {
  const { user: currentUser } = useUser();
  const defaultRange = useMemo(() => getPeriodRange("week"), []);
  const [period, setPeriod] = useState<AttendancePeriod>("week");
  const [periodStart, setPeriodStart] = useState(defaultRange.start);
  const [periodEnd, setPeriodEnd] = useState(defaultRange.end);
  const [loading, setLoading] = useState(false);
  const [loadingMode, setLoadingMode] = useState<"saved" | "analyze" | null>(null);
  const [busyKey, setBusyKey] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<AttendanceAnalysisResponse | null>(null);
  const [expandedRecordKey, setExpandedRecordKey] = useState<string | null>(null);
  const [expandedComments, setExpandedComments] = useState<Record<number, boolean>>({});
  const [commentsMap, setCommentsMap] = useState<Record<number, AttendanceRecordComment[]>>({});
  const [commentsLoadingMap, setCommentsLoadingMap] = useState<Record<number, boolean>>({});
  const [commentDrafts, setCommentDrafts] = useState<Record<number, string>>({});
  const [dayEventsRecordPreview, setDayEventsRecordPreview] =
    useState<AttendanceDayEventsPreview | null>(null);
  const [editModalOpen, setEditModalOpen] = useState(false);
  const [editForm, setEditForm] = useState<AttendanceRecordEditForm | null>(null);

  const canManageAttendance = Boolean(
    currentUser?.auth?.is_staff || currentUser?.auth?.is_superuser,
  );

  const records = useMemo(() => {
    if (!result?.records || !Array.isArray(result.records)) return [];
    return result.records;
  }, [result]);

  const summary = useMemo(() => {
    const issueDays = records.filter((record) => {
      const personnelMeta = getPersonnelDayMeta(employeeActions, record.date, record);
      return issueLabels(record, personnelMeta).length > 0;
    }).length;
    return {
      total: records.length,
      workdays: records.filter((record) => {
        const personnelMeta = getPersonnelDayMeta(employeeActions, record.date, record);
        return (record.effective_is_workday ?? record.is_workday) && !personnelMeta?.nonWorking;
      }).length,
      issueDays,
      overtime: records.filter((record) => record.is_overtime).length,
    };
  }, [employeeActions, records]);

  async function analyzeAttendance() {
    setError(null);

    if (!employeeId) {
      setError("Некорректный сотрудник");
      return;
    }

    if (!periodStart || !periodEnd || periodStart > periodEnd) {
      setError("Проверьте период анализа");
      return;
    }

    try {
      setLoading(true);
      setLoadingMode("analyze");
      await analyzeEmployeeAttendance({
        employee_id: employeeId,
        period_start: periodStart,
        period_end: periodEnd,
      });
      const savedRecords = await getAttendanceRecords({
        employee_id: employeeId,
        date_from: periodStart,
        date_to: periodEnd,
      });
      setResult({ records: savedRecords.results });
      setExpandedRecordKey(null);
      setExpandedComments({});
      setCommentsMap({});
    } catch (analysisError) {
      setError(getErrorMessage(analysisError, "Не удалось выполнить анализ посещаемости"));
    } finally {
      setLoading(false);
      setLoadingMode(null);
    }
  }

  function handlePeriodChange(nextPeriod: AttendancePeriod) {
    setPeriod(nextPeriod);
    setError(null);
    setResult(null);
    setExpandedRecordKey(null);
    setExpandedComments({});

    if (nextPeriod === "custom") return;

    const range = getPeriodRange(nextPeriod);
    setPeriodStart(range.start);
    setPeriodEnd(range.end);
  }

  useEffect(() => {
    let cancelled = false;

    async function loadSavedRecords() {
      if (!employeeId || !periodStart || !periodEnd || periodStart > periodEnd) {
        setResult(null);
        return;
      }

      try {
        setLoading(true);
        setLoadingMode("saved");
        setError(null);
        const response = await getAttendanceRecords({
          employee_id: employeeId,
          date_from: periodStart,
          date_to: periodEnd,
        });
        if (!cancelled) {
          setResult({ records: response.results });
          setExpandedRecordKey(null);
        }
      } catch (loadError) {
        if (!cancelled) {
          setError(getErrorMessage(loadError, "Не удалось загрузить сохраненную посещаемость"));
          setResult(null);
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
          setLoadingMode(null);
        }
      }
    }

    void loadSavedRecords();

    return () => {
      cancelled = true;
    };
  }, [employeeId, periodEnd, periodStart]);

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    void analyzeAttendance();
  }

  function updateRecordCommentCount(recordId: number, count: number) {
    setResult((current) => {
      if (!current?.records) return current;
      return {
        ...current,
        records: current.records.map((record) =>
          getRecordId(record) === recordId
            ? { ...record, comments_count: count }
            : record,
        ),
      };
    });
  }

  async function ensureCommentsLoaded(recordId: number) {
    if (commentsMap[recordId] || commentsLoadingMap[recordId]) return;

    try {
      setCommentsLoadingMap((current) => ({ ...current, [recordId]: true }));
      const comments = await getAttendanceRecordComments(recordId);
      setCommentsMap((current) => ({ ...current, [recordId]: comments }));
      updateRecordCommentCount(recordId, comments.length);
    } catch (commentError) {
      setError(getErrorMessage(commentError, "Не удалось загрузить комментарии"));
    } finally {
      setCommentsLoadingMap((current) => ({ ...current, [recordId]: false }));
    }
  }

  async function toggleComments(recordId: number) {
    const isOpen = Boolean(expandedComments[recordId]);
    setExpandedComments((current) => ({ ...current, [recordId]: !isOpen }));

    if (!isOpen) {
      await ensureCommentsLoaded(recordId);
    }
  }

  async function openCommentsFromDayEvents(record: AttendanceDayEventsPreview) {
    setExpandedComments((current) => ({ ...current, [record.recordId]: true }));
    await ensureCommentsLoaded(record.recordId);
  }

  function openDayEvents(record: AttendanceRecord, recordId: number, key: string) {
    const personnelMeta = getPersonnelDayMeta(employeeActions, record.date, record);
    const tone = getRecordTone(record, personnelMeta);
    const workdayMeta = getWorkdayMeta(record, personnelMeta);
    setExpandedRecordKey(key);
    setDayEventsRecordPreview({
      recordId,
      employeeName: record.display_name || displayUserName(currentUser) || `Сотрудник ${employeeId}`,
      date: `${record.date || "Дата не указана"} · ${formatDateLabel(record.date)}`,
      statusLabel: tone.label,
      displayText: hasWorked(record)
        ? `${formatTime(record.arrival_time)}/${formatTime(record.departure_time)} · ${formatHours(record.work_hours)} ч.`
        : "Нет проходов",
      detailLines: attendanceRecordDetails(record, workdayMeta),
      issues: issueLabels(record, personnelMeta).map(formatAttendanceIssueLabel),
      isManuallyEdited: Boolean(record.is_manually_edited),
      commentsCount: Number(record.comments_count || 0),
    });
  }

  async function addComment(recordId: number) {
    const text = (commentDrafts[recordId] || "").trim();
    if (!text) return;

    try {
      setBusyKey(`comment-${recordId}`);
      const saved = await addAttendanceRecordComment(recordId, text);
      const nextCount = (commentsMap[recordId]?.length || 0) + 1;
      setCommentsMap((current) => {
        return { ...current, [recordId]: [...(current[recordId] || []), saved] };
      });
      updateRecordCommentCount(recordId, nextCount);
      setCommentDrafts((current) => ({ ...current, [recordId]: "" }));
    } catch (commentError) {
      setError(getErrorMessage(commentError, "Не удалось добавить комментарий"));
    } finally {
      setBusyKey(null);
    }
  }

  async function deleteComment(recordId: number, commentId: number) {
    try {
      setBusyKey(`delete-comment-${commentId}`);
      await deleteAttendanceRecordComment(recordId, commentId);
      const nextCount = Math.max((commentsMap[recordId]?.length || 1) - 1, 0);
      setCommentsMap((current) => {
        return {
          ...current,
          [recordId]: (current[recordId] || []).filter((comment) => comment.id !== commentId),
        };
      });
      updateRecordCommentCount(recordId, nextCount);
    } catch (commentError) {
      setError(getErrorMessage(commentError, "Не удалось удалить комментарий"));
    } finally {
      setBusyKey(null);
    }
  }

  function editableRecords() {
    return records.filter((record) => getRecordId(record));
  }

  function openEditModal() {
    const firstRecord = editableRecords()[0];
    const form = firstRecord ? recordToEditForm(firstRecord) : null;

    if (!form) {
      setError("Нет сохраненных записей для редактирования");
      return;
    }

    setEditForm(form);
    setEditModalOpen(true);
  }

  function handleEditRecordSelect(recordId: string) {
    const selectedRecord = records.find((record) => getRecordId(record) === Number(recordId));
    const form = selectedRecord ? recordToEditForm(selectedRecord) : null;
    if (form) setEditForm(form);
  }

  function updateEditForm<K extends keyof AttendanceRecordEditForm>(
    key: K,
    value: AttendanceRecordEditForm[K],
  ) {
    setEditForm((current) => current ? { ...current, [key]: value } : current);
  }

  async function saveEditedRecord() {
    if (!editForm) return;

    const payload: AttendanceRecordUpdatePayload = {
      arrival_time: nullableTime(editForm.arrival_time),
      departure_time: nullableTime(editForm.departure_time),
      work_hours: nullableNumber(editForm.work_hours),
      expected_hours: nullableNumber(editForm.expected_hours),
      is_workday: editForm.is_workday,
      effective_is_workday: editForm.effective_is_workday,
      is_late: editForm.is_late,
      late_minutes: nullableNumber(editForm.late_minutes),
      is_early_leave: editForm.is_early_leave,
      early_leave_minutes: nullableNumber(editForm.early_leave_minutes),
      is_underwork: editForm.is_underwork,
      underwork_hours: nullableNumber(editForm.underwork_hours),
      is_overtime: editForm.is_overtime,
      overtime_hours: nullableNumber(editForm.overtime_hours),
      is_absent: editForm.is_absent,
    };

    try {
      setBusyKey("edit-record");
      const saved = await updateAttendanceRecord(editForm.recordId, payload);
      setResult((current) => {
        if (!current?.records) return current;
        return {
          ...current,
          records: current.records.map((record) =>
            getRecordId(record) === editForm.recordId
              ? { ...record, ...saved }
              : record,
          ),
        };
      });
      setEditModalOpen(false);
    } catch (saveError) {
      setError(getErrorMessage(saveError, "Не удалось сохранить запись посещаемости"));
    } finally {
      setBusyKey(null);
    }
  }

  return (
    <>
      <section className="app-surface rounded-2xl p-4 sm:p-5">
      <form onSubmit={handleSubmit} className="mb-4 space-y-3">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <h2 className="app-card-caption">Посещаемость</h2>
            <p className="app-text-muted mt-2 text-sm">Анализ проходов по сотруднику</p>
          </div>

          <div className="flex items-center gap-2 sm:shrink-0">
            <button
              type="submit"
              disabled={loading}
              className="app-action-primary inline-flex h-10 items-center justify-center gap-2 rounded-lg px-4 text-sm font-semibold disabled:cursor-not-allowed disabled:opacity-60"
            >
              {loading ? <Loader2 size={16} className="animate-spin" /> : <RefreshCw size={16} />}
              Обновить
            </button>

            {canManageAttendance ? (
              <button
                type="button"
                onClick={openEditModal}
                className="app-action-ghost flex h-9 w-9 items-center justify-center rounded-md"
                aria-label="Редактировать записи посещаемости"
                title="Редактировать записи"
              >
                <Edit3 size={15} />
              </button>
            ) : null}
          </div>
        </div>

        <div className="app-surface-muted rounded-xl p-3">
          <div className="flex flex-wrap gap-2">
            {attendancePeriods.map((periodOption) => {
              const active = period === periodOption.value;
              return (
                <button
                  key={periodOption.value}
                  type="button"
                  onClick={() => handlePeriodChange(periodOption.value)}
                  className={active
                    ? "app-action-primary rounded-lg px-3 py-2 text-xs font-medium"
                    : "app-action-secondary rounded-lg px-3 py-2 text-xs font-medium"
                  }
                >
                  {periodOption.label}
                </button>
              );
            })}
          </div>

          {period === "custom" ? (
            <div className="mt-3 grid grid-cols-1 gap-2 sm:grid-cols-2">
              <label className="block">
                <span className="app-card-caption mb-1 block">Начало</span>
                <input
                  type="date"
                  value={periodStart}
                  onChange={(event) => setPeriodStart(event.target.value)}
                  className="app-input w-full rounded-lg px-3 py-2 text-sm sm:w-36"
                />
              </label>
              <label className="block">
                <span className="app-card-caption mb-1 block">Конец</span>
                <input
                  type="date"
                  value={periodEnd}
                  onChange={(event) => setPeriodEnd(event.target.value)}
                  className="app-input w-full rounded-lg px-3 py-2 text-sm sm:w-36"
                />
              </label>
            </div>
          ) : (
            <p className="app-text-muted mt-2 px-1 text-xs">
              {periodStart} — {periodEnd}
            </p>
          )}
        </div>
      </form>

      <div className="grid grid-cols-[repeat(auto-fit,minmax(7.5rem,1fr))] gap-2">
        <div className="app-surface-muted rounded-lg px-3 py-2">
          <p className="app-card-caption break-words leading-tight">Записей</p>
          <p className="text-lg font-semibold text-[var(--foreground)]">{summary.total}</p>
        </div>
        <div className="app-surface-muted rounded-lg px-3 py-2">
          <p className="app-card-caption break-words leading-tight">Рабочих</p>
          <p className="text-lg font-semibold text-[var(--foreground)]">{summary.workdays}</p>
        </div>
        <div className="app-surface-muted rounded-lg px-3 py-2">
          <p className="app-card-caption break-words leading-tight">Проблем</p>
          <p className="text-lg font-semibold text-[var(--foreground)]">{summary.issueDays}</p>
        </div>
        <div className="app-surface-muted rounded-lg px-3 py-2">
          <p className="app-card-caption break-words leading-tight">Переработок</p>
          <p className="text-lg font-semibold text-[var(--foreground)]">{summary.overtime}</p>
        </div>
      </div>

      {error ? (
        <div className="mt-4 flex items-start gap-2 rounded-lg border border-red-500/30 bg-red-500/10 px-3 py-2 text-sm text-red-300">
          <AlertTriangle size={16} className="mt-0.5 shrink-0" />
          <span>{error}</span>
        </div>
      ) : null}

      <div className="mt-4">
        {loading && !result ? (
          <div className="app-surface-muted flex items-center justify-center gap-2 rounded-xl p-6 text-sm text-[var(--muted-foreground)]">
            <Loader2 size={16} className="animate-spin" />
            {loadingMode === "analyze" ? "Выполняем анализ" : "Загружаем сохраненную посещаемость"}
          </div>
        ) : null}

        {!loading && result && records.length === 0 ? (
          <div className="app-surface-muted rounded-xl p-6 text-center">
            <p className="app-text-muted text-sm">
              Сохраненных записей за период нет. Нажмите «Обновить», чтобы выполнить анализ.
            </p>
          </div>
        ) : null}

        {records.length > 0 ? (
          <div className="space-y-2">
            {records.map((record, index) => {
              const recordId = getRecordId(record);
              const key = recordId ? `record-${recordId}` : `${record.date || "record"}-${index}`;
              const personnelMeta = getPersonnelDayMeta(employeeActions, record.date, record);
              const suppressAttendanceIssues = personnelMeta?.nonWorking || isRemotePersonnelMeta(personnelMeta);
              const labels = issueLabels(record, personnelMeta);
              const tone = getRecordTone(record, personnelMeta);
              const workdayMeta = getWorkdayMeta(record, personnelMeta);
              const expanded = expandedRecordKey === key;
              const commentsOpen = recordId ? Boolean(expandedComments[recordId]) : false;
              const comments = recordId ? (commentsMap[recordId] || []) : [];
              const commentsCount = comments.length || Number(record.comments_count || 0);
              const commentsLoading = recordId ? Boolean(commentsLoadingMap[recordId]) : false;
              const commentDraft = recordId ? (commentDrafts[recordId] || "") : "";

              return (
                <article key={key} className="app-surface-muted overflow-hidden rounded-xl transition hover:border-[var(--border-strong)]">
                  <div className="flex items-start gap-3 p-3 sm:p-4">
                    <div className="mt-0.5 flex shrink-0 flex-col items-center gap-2">
                      <button
                        type="button"
                        onClick={() => setExpandedRecordKey((current) => current === key ? null : key)}
                        className="app-action-secondary inline-flex h-8 w-8 items-center justify-center rounded-lg"
                        aria-expanded={expanded}
                        title="Показать детали"
                        aria-label="Показать детали"
                      >
                        <ChevronDown size={15} className={`transition ${expanded ? "rotate-180" : ""}`} />
                      </button>
                      <button
                        type="button"
                        onClick={() => recordId ? void toggleComments(recordId) : undefined}
                        disabled={!recordId}
                        className="app-action-secondary relative inline-flex h-8 w-8 items-center justify-center rounded-lg disabled:cursor-not-allowed disabled:opacity-50"
                        title="Комментарии"
                        aria-label="Комментарии"
                        aria-expanded={commentsOpen}
                      >
                        <MessageSquare size={15} />
                        {commentsCount > 0 ? (
                          <span className="app-counter absolute -right-1.5 -top-1.5 flex h-4 min-w-4 px-1 text-[10px] font-bold">
                            {commentsCount}
                          </span>
                        ) : null}
                      </button>
                    </div>

                    <button
                      type="button"
                      onClick={() => setExpandedRecordKey((current) => current === key ? null : key)}
                      className="min-w-0 flex-1 text-left"
                    >
                      <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
                        <div className="min-w-0">
                          <div className="flex items-center gap-2">
                            <span className={`h-2 w-2 shrink-0 rounded-full ${tone.dotClassName}`} />
                            <p className="text-sm font-semibold text-[var(--foreground)]">
                              {formatDateLabel(record.date)}
                            </p>
                          </div>
                          <p className="app-text-muted mt-0.5 text-xs">
                            {record.date || "Дата не указана"}
                          </p>
                        </div>

                        <div className="flex shrink-0 flex-col items-start gap-1 sm:items-end">
                          <span className={`app-status-pill ${tone.pillClassName}`}>
                            {tone.label}
                          </span>
                          {record.is_manually_edited ? (
                            <span className="app-status-pill app-badge">
                              Изменено вручную
                            </span>
                          ) : null}
                          <span className={`text-[11px] font-medium ${workdayMeta.className}`}>
                            {workdayMeta.reason || workdayMeta.label}
                          </span>
                        </div>
                      </div>

                      <div className="app-text-muted mt-3 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs">
                        <span className="inline-flex items-center gap-1.5">
                          <LogIn size={13} />
                          <span>Приход:</span>
                          <span className="font-medium text-[var(--foreground)]">{formatTime(record.arrival_time)}</span>
                        </span>
                        <span className="inline-flex items-center gap-1.5">
                          <LogOut size={13} />
                          <span>Уход:</span>
                          <span className="font-medium text-[var(--foreground)]">{formatTime(record.departure_time)}</span>
                        </span>
                        <span className="inline-flex items-center gap-1.5">
                          <Clock size={13} />
                          <span>Часы:</span>
                          <span className="font-medium text-[var(--foreground)]">
                            {formatHours(record.work_hours)}
                            {record.expected_hours !== undefined ? (
                              <span className="app-text-muted"> / {formatHours(record.expected_hours)}</span>
                            ) : null}
                          </span>
                        </span>
                      </div>
                    </button>
                  </div>

                  {(expanded || commentsOpen) ? (
                    <div className="border-t border-[var(--border-subtle)] px-3 pb-3 sm:px-4 sm:pb-4">
                      {commentsOpen ? (
                        <div className="app-surface mt-3 rounded-lg p-3">
                          <div className="space-y-2">
                            {commentsLoading ? (
                              <p className="app-text-muted text-xs">Загружаем комментарии</p>
                            ) : comments.length === 0 ? (
                              <p className="app-text-muted text-xs">Комментариев пока нет</p>
                            ) : (
                              comments.map((comment) => (
                                <div
                                  key={comment.id}
                                  className="app-surface-muted rounded-lg px-3 py-2 text-xs text-[var(--foreground)]"
                                >
                                  <div className="mb-1 flex items-center justify-between gap-2">
                                    <span className="font-medium">{displayUserName(comment.author)}</span>
                                    <div className="flex items-center gap-2">
                                      <span className="app-text-muted">{formatDate(comment.created_at)}</span>
                                      {Boolean(comment.author?.id && currentUser?.id === comment.author.id) ? (
                                        <CommentDeleteButton
                                          disabled={busyKey === `delete-comment-${comment.id}`}
                                          onClick={() => recordId ? deleteComment(recordId, comment.id) : undefined}
                                        />
                                      ) : null}
                                    </div>
                                  </div>
                                  <p className="app-text-wrap text-[var(--foreground)]">{comment.text}</p>
                                </div>
                              ))
                            )}
                          </div>
                          {recordId ? (
                            <div className="mt-2">
                              <CommentComposer
                                value={commentDraft}
                                onChange={(value) => setCommentDrafts((current) => ({ ...current, [recordId]: value }))}
                                onSubmit={() => addComment(recordId)}
                                disabled={busyKey === `comment-${recordId}`}
                              />
                            </div>
                          ) : null}
                        </div>
                      ) : null}

                      {expanded ? (
                        <div className="app-surface mt-3 rounded-lg p-3">
                          <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
                            <p className="app-card-caption">Детали</p>
                            {recordId ? (
                              <button
                                type="button"
                                onClick={() => openDayEvents(record, recordId, key)}
                                className="app-action-secondary inline-flex items-center gap-2 rounded-lg px-3 py-2 text-xs font-semibold"
                              >
                                <Camera size={14} />
                                Подробности события
                              </button>
                            ) : null}
                          </div>
                          <div className="grid gap-3 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
                            <div className="grid gap-2 sm:grid-cols-2">
                              {personnelMeta ? (
                                <div className="sm:col-span-2">
                                  <p className="app-text-muted text-xs">Кадровое состояние</p>
                                  <p className={`mt-1 text-sm font-medium ${personnelMeta.className}`}>
                                    {personnelMeta.label}
                                  </p>
                                </div>
                              ) : null}
                              <div>
                                <p className="app-text-muted text-xs">Опоздание</p>
                                <p className="mt-1 text-sm text-[var(--foreground)]">
                                  {record.is_late && !suppressAttendanceIssues ? `${record.late_minutes ?? 0} мин.` : "Нет"}
                                </p>
                              </div>
                              <div>
                                <p className="app-text-muted text-xs">Ранний уход</p>
                                <p className="mt-1 text-sm text-[var(--foreground)]">
                                  {record.is_early_leave && !suppressAttendanceIssues ? `${record.early_leave_minutes ?? 0} мин.` : "Нет"}
                                </p>
                              </div>
                              <div>
                                <p className="app-text-muted text-xs">Недоработка</p>
                                <p className="mt-1 text-sm text-[var(--foreground)]">
                                  {record.is_underwork && !suppressAttendanceIssues ? `${formatHours(record.underwork_hours)} ч.` : "Нет"}
                                </p>
                              </div>
                              <div>
                                <p className="app-text-muted text-xs">Переработка</p>
                                <p className="mt-1 text-sm text-[var(--foreground)]">
                                  {record.is_overtime ? `${formatHours(record.overtime_hours)} ч.` : "Нет"}
                                </p>
                              </div>
                            </div>

                            {labels.length > 0 ? (
                              <div className="flex flex-wrap content-start gap-1.5">
                                {labels.map((label) => (
                                  <span key={label} className={`app-status-pill ${getIssueBadgeClassName(label)}`}>
                                    {formatAttendanceIssueLabel(label)}
                                  </span>
                                ))}
                              </div>
                            ) : (
                              <p className="app-text-muted text-sm">Замечаний нет</p>
                            )}
                          </div>
                        </div>
                      ) : null}
                    </div>
                  ) : null}
                </article>
              );
            })}
          </div>
        ) : null}
      </div>
      </section>

      <AttendanceDayEventsModal
        isOpen={Boolean(dayEventsRecordPreview)}
        onClose={() => setDayEventsRecordPreview(null)}
        onOpenComments={(record) => void openCommentsFromDayEvents(record)}
        record={dayEventsRecordPreview}
      />

      <Modal
        isOpen={editModalOpen}
        onClose={() => setEditModalOpen(false)}
        title="Редактировать посещаемость"
        size="md"
        footer={(
          <div className="flex flex-wrap justify-end gap-2">
            <button
              type="button"
              onClick={() => setEditModalOpen(false)}
              className="app-action-secondary rounded-lg px-4 py-2 text-sm font-semibold"
            >
              Отмена
            </button>
            <button
              type="button"
              onClick={() => void saveEditedRecord()}
              disabled={!editForm || busyKey === "edit-record"}
              className="app-action-primary inline-flex items-center gap-2 rounded-lg px-4 py-2 text-sm font-semibold disabled:cursor-not-allowed disabled:opacity-60"
            >
              {busyKey === "edit-record" ? <Loader2 size={16} className="animate-spin" /> : <Edit3 size={16} />}
              Сохранить
            </button>
          </div>
        )}
      >
        {!editForm ? (
          <div className="app-surface-muted rounded-xl p-5 text-sm text-[var(--muted-foreground)]">
            Нет сохраненных записей для редактирования.
          </div>
        ) : (
          <div className="space-y-4">
            <label className="block">
              <span className="app-card-caption mb-2 block">Запись</span>
              <select
                value={editForm.recordId}
                onChange={(event) => handleEditRecordSelect(event.target.value)}
                className="app-select w-full rounded-xl px-3 py-2.5 text-sm"
              >
                {editableRecords().map((record) => {
                  const recordId = getRecordId(record);
                  if (!recordId) return null;
                  return (
                    <option key={recordId} value={recordId}>
                      {record.date || "Без даты"} · приход {formatTime(record.arrival_time)} · уход {formatTime(record.departure_time)}
                    </option>
                  );
                })}
              </select>
            </label>

            <div className="grid gap-3 sm:grid-cols-2">
              <label className="block">
                <span className="app-card-caption mb-2 block">Приход</span>
                <input
                  type="time"
                  step="1"
                  value={editForm.arrival_time}
                  onChange={(event) => updateEditForm("arrival_time", event.target.value)}
                  className="app-input w-full rounded-xl px-3 py-2.5 text-sm"
                />
              </label>
              <label className="block">
                <span className="app-card-caption mb-2 block">Уход</span>
                <input
                  type="time"
                  step="1"
                  value={editForm.departure_time}
                  onChange={(event) => updateEditForm("departure_time", event.target.value)}
                  className="app-input w-full rounded-xl px-3 py-2.5 text-sm"
                />
              </label>
              <label className="block">
                <span className="app-card-caption mb-2 block">Часы</span>
                <input
                  type="number"
                  step="0.01"
                  value={editForm.work_hours}
                  onChange={(event) => updateEditForm("work_hours", event.target.value)}
                  className="app-input w-full rounded-xl px-3 py-2.5 text-sm"
                />
              </label>
              <label className="block">
                <span className="app-card-caption mb-2 block">Норма часов</span>
                <input
                  type="number"
                  step="0.01"
                  value={editForm.expected_hours}
                  onChange={(event) => updateEditForm("expected_hours", event.target.value)}
                  className="app-input w-full rounded-xl px-3 py-2.5 text-sm"
                />
              </label>
            </div>

            <div className="app-surface-muted rounded-xl p-3">
              <p className="app-card-caption mb-3">Признаки дня</p>
              <div className="grid gap-2 sm:grid-cols-2">
                {attendanceRecordBooleanFields.map(({ key, label }) => (
                  <label key={key} className="flex items-center gap-2 text-sm text-[var(--foreground)]">
                    <input
                      type="checkbox"
                      checked={editForm[key]}
                      onChange={(event) => updateEditForm(key, event.target.checked)}
                      className="h-4 w-4 rounded border-[var(--border-subtle)]"
                    />
                    {label}
                  </label>
                ))}
              </div>
            </div>

            <div className="grid gap-3 sm:grid-cols-2">
              <label className="block">
                <span className="app-card-caption mb-2 block">Минут опоздания</span>
                <input
                  type="number"
                  step="1"
                  value={editForm.late_minutes}
                  onChange={(event) => updateEditForm("late_minutes", event.target.value)}
                  className="app-input w-full rounded-xl px-3 py-2.5 text-sm"
                />
              </label>
              <label className="block">
                <span className="app-card-caption mb-2 block">Минут раннего ухода</span>
                <input
                  type="number"
                  step="1"
                  value={editForm.early_leave_minutes}
                  onChange={(event) => updateEditForm("early_leave_minutes", event.target.value)}
                  className="app-input w-full rounded-xl px-3 py-2.5 text-sm"
                />
              </label>
              <label className="block">
                <span className="app-card-caption mb-2 block">Часов недоработки</span>
                <input
                  type="number"
                  step="0.01"
                  value={editForm.underwork_hours}
                  onChange={(event) => updateEditForm("underwork_hours", event.target.value)}
                  className="app-input w-full rounded-xl px-3 py-2.5 text-sm"
                />
              </label>
              <label className="block">
                <span className="app-card-caption mb-2 block">Часов переработки</span>
                <input
                  type="number"
                  step="0.01"
                  value={editForm.overtime_hours}
                  onChange={(event) => updateEditForm("overtime_hours", event.target.value)}
                  className="app-input w-full rounded-xl px-3 py-2.5 text-sm"
                />
              </label>
            </div>
          </div>
        )}
      </Modal>

    </>
  );
}
