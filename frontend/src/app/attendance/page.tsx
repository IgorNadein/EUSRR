"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import {
  AlertTriangle,
  CalendarCheck,
  Check,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  Download,
  Loader2,
  MessageSquare,
  RefreshCw,
  Save,
  Search,
} from "lucide-react";

import { AppShell } from "@/components/AppShell";
import {
  AttendanceDayEventsModal,
  type AttendanceDayEventsPreview,
} from "@/components/attendance/AttendanceDayEventsModal";
import {
  AttendanceRecordCommentsModal,
  type AttendanceRecordCommentsPreview,
} from "@/components/attendance/AttendanceRecordCommentsModal";
import { Modal } from "@/components/ui";
import { useUser } from "@/contexts/UserContext";
import { apiClient } from "@/lib/api";
import { loadAllPages, displayUserName, formatDateTime } from "@/lib/shared";
import { resolveMediaUrl } from "@/lib/url";
import type {
  MonthlyAttendanceMatrix,
  MonthlyAttendanceMatrixCell,
  MonthlyAttendanceMatrixEmployee,
  MonthlyAttendanceMatrixRow,
  AttendanceRecord,
  AttendanceAutoSyncSettings,
} from "@/lib/api/attendance";
import type { User } from "@/types/api";

const weekdays = [
  { value: "Monday", label: "Пн" },
  { value: "Tuesday", label: "Вт" },
  { value: "Wednesday", label: "Ср" },
  { value: "Thursday", label: "Чт" },
  { value: "Friday", label: "Пт" },
  { value: "Saturday", label: "Сб" },
  { value: "Sunday", label: "Вс" },
];

const defaultWorkdays = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"];
const matrixDateColumnWidth = 140;
const matrixEmployeeColumnWidth = 160;
const matrixModalHorizontalPadding = 96;

type AttendancePeriodPreset = "month" | "custom";

const periodPresets: Array<{ value: AttendancePeriodPreset; label: string }> = [
  { value: "month", label: "За месяц" },
  { value: "custom", label: "Свой период" },
];

const autoSyncFrequencyOptions = [
  { value: 5, label: "5 минут" },
  { value: 15, label: "15 минут" },
  { value: 30, label: "30 минут" },
  { value: 60, label: "1 час" },
  { value: 1440, label: "1 сутки" },
];

const autoSyncLookbackOptions = [
  { value: 1, label: "1 день" },
  { value: 3, label: "3 дня" },
  { value: 7, label: "7 дней" },
];

function toDateInputValue(date: Date) {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function toTimeInputValue(value: string | undefined) {
  return (value || "").slice(0, 5);
}

function getCurrentMonthKey() {
  const date = new Date();
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}`;
}

function getMonthRange(monthKey: string) {
  const [year, month] = monthKey.split("-").map(Number);
  const start = new Date(year, month - 1, 1);
  const end = new Date(year, month, 0);
  return {
    start: toDateInputValue(start),
    end: toDateInputValue(end),
  };
}

function shiftMonthKey(monthKey: string, delta: number) {
  const [year, month] = monthKey.split("-").map(Number);
  const date = new Date(year, month - 1 + delta, 1);
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}`;
}

function formatMonthKeyLabel(monthKey: string) {
  const [year, month] = monthKey.split("-").map(Number);
  const date = new Date(year, month - 1, 1);
  return new Intl.DateTimeFormat("ru-RU", {
    month: "long",
    year: "numeric",
  }).format(date);
}

function getInitials(employee: User) {
  const first = employee.first_name?.[0] || "";
  const last = employee.last_name?.[0] || "";
  const fallback = employee.email?.[0] || String(employee.id)[0] || "";
  return `${last}${first}` || fallback;
}

function formatTime(value: unknown) {
  if (!value) return "-";
  return String(value);
}

function formatMatrixTime(value: unknown) {
  const text = formatTime(value);
  if (text === "-") return text;
  const timeText = text.includes("T") ? text.split("T", 2)[1] : text;
  return timeText.length >= 5 && timeText[2] === ":" ? timeText.slice(0, 5) : timeText;
}

function formatHours(value: unknown) {
  if (value === null || value === undefined || value === "") return "0";
  const numeric = Number(value);
  if (Number.isFinite(numeric)) {
    return numeric.toLocaleString("ru-RU", { maximumFractionDigits: 2 });
  }
  return String(value);
}

function getErrorMessage(error: unknown, fallback: string) {
  return String((error as Error)?.message || fallback);
}

function formatOptionalDateTime(value?: string | null) {
  return value ? formatDateTime(value) : "-";
}

function autoSyncStatusText(settings: AttendanceAutoSyncSettings | null) {
  if (!settings) return "Не загружено";
  return settings.last_status_label || settings.last_status || "Ожидание";
}

function monthKeyFromDate(value: string) {
  return value.slice(0, 7);
}

function getMonthKeysBetween(start: string, end: string) {
  const result: string[] = [];
  const [startYear, startMonth] = monthKeyFromDate(start).split("-").map(Number);
  const [endYear, endMonth] = monthKeyFromDate(end).split("-").map(Number);
  let year = startYear;
  let month = startMonth;

  while (year < endYear || (year === endYear && month <= endMonth)) {
    result.push(`${year}-${String(month).padStart(2, "0")}`);
    month += 1;
    if (month > 12) {
      month = 1;
      year += 1;
    }
  }

  return result;
}

function matrixCellTone(status: string) {
  if (status === "technical") return "bg-red-500/15 text-red-200 hover:bg-red-500/20";
  if (status === "underwork" || status === "late" || status === "absent") {
    return "bg-amber-500/15 text-amber-100 hover:bg-amber-500/20";
  }
  if (status === "overtime") return "bg-emerald-500/15 text-emerald-100 hover:bg-emerald-500/20";
  if (status === "non_working") return "bg-slate-500/15 text-slate-300 hover:bg-slate-500/20";
  if (status === "normal") return "bg-[var(--surface-primary)] text-[var(--foreground)] hover:bg-[var(--surface-tertiary)]";
  return "bg-transparent text-[var(--muted-foreground)] hover:bg-[var(--surface-secondary)]";
}

function matrixCellSourceTone(cell: MonthlyAttendanceMatrixCell) {
  if (!cell.is_manually_edited) return "";
  return "ring-1 ring-inset ring-violet-400/70 shadow-[inset_0_0_0_9999px_rgba(139,92,246,0.10)]";
}

function matrixStatusLabel(status: string) {
  const labels: Record<string, string> = {
    empty: "Нет записи",
    technical: "Техсбой",
    underwork: "Недоработка",
    late: "Опоздание",
    overtime: "Переработка",
    absent: "Отсутствие",
    non_working: "Нерабочий",
    normal: "Норма",
  };
  return labels[status] || status;
}

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

function matrixCellIssueLabels(cell: MonthlyAttendanceMatrixCell) {
  if (cell.status === "absent") return ["absence"];
  const result = [...cell.issues.map(String)];
  if (cell.effective_is_workday !== false && cell.is_workday !== false) {
    if (cell.is_absent) result.push("absence");
    if (cell.is_late) result.push("late");
    if (cell.is_early_leave) result.push("early_leave");
    if (cell.is_underwork) result.push("underwork");
  }
  if (cell.is_overtime) result.push("overtime");
  return Array.from(new Set(result));
}

function attendanceRecordIssueLabels(record: AttendanceRecord) {
  const result = [
    ...(record.employee_issues || []),
    ...(record.technical_issues || []),
  ].map(String);
  if (record.is_absent) result.push("absence");
  if (record.is_late) result.push("late");
  if (record.is_early_leave) result.push("early_leave");
  if (record.is_underwork) result.push("underwork");
  if (record.is_overtime) result.push("overtime");
  return Array.from(new Set(result)).map(formatAttendanceIssueLabel);
}

function matrixCellDisplay(cell: MonthlyAttendanceMatrixCell) {
  if (cell.display_text) return cell.display_text;
  if (cell.short_label) return cell.short_label;
  if (cell.status === "empty") return "";
  return `${formatMatrixTime(cell.arrival_time)}/${formatMatrixTime(cell.departure_time)}`;
}

function attendanceRecordStatusLabel(record: AttendanceRecord) {
  if (record.technical_issues?.length) return "Техсбой";
  if (record.personnel_status_label) return record.personnel_status_label;
  if (record.is_absent) return "Отсутствие";
  if (record.is_underwork) return "Недоработка";
  if (record.is_late) return "Опоздание";
  if (record.is_overtime) return "Переработка";
  if (record.effective_is_workday === false || record.is_workday === false) {
    return "Нерабочий";
  }
  return "Норма";
}

function attendanceRecordDisplay(record: AttendanceRecord) {
  const arrival = formatTime(record.arrival_time);
  const departure = formatTime(record.departure_time);
  if (arrival === "-" && departure === "-") {
    if (record.is_absent) return "Отсутствие";
    return record.non_working_reason || "Нет проходов";
  }
  return `${arrival}/${departure} · ${formatHours(record.work_hours)}ч`;
}

function attendanceRecordDetails(record: AttendanceRecord) {
  const lines = [
    `Статус: ${attendanceRecordStatusLabel(record)}`,
    `Приход: ${formatTime(record.arrival_time)}`,
    `Уход: ${formatTime(record.departure_time)}`,
    `Часы: ${formatHours(record.work_hours)} / ${formatHours(record.expected_hours)}`,
  ];
  if (record.late_minutes) lines.push(`Опоздание: ${record.late_minutes} мин.`);
  if (record.early_leave_minutes) {
    lines.push(`Ранний уход: ${record.early_leave_minutes} мин.`);
  }
  if (record.underwork_hours) {
    lines.push(`Недоработка: ${formatHours(record.underwork_hours)} ч.`);
  }
  if (record.overtime_hours) {
    lines.push(`Переработка: ${formatHours(record.overtime_hours)} ч.`);
  }
  if (record.non_working_reason) {
    lines.push(`Причина: ${record.non_working_reason}`);
  }
  if (record.comments_count) lines.push(`Комментарии: ${record.comments_count}`);
  return lines;
}

function weekdayLabelFromDate(value?: string) {
  if (!value) return "";
  const date = new Date(`${value}T00:00:00`);
  if (Number.isNaN(date.getTime())) return "";
  return DAYS_RU_FROM_INDEX[date.getDay()] || "";
}

const DAYS_RU_FROM_INDEX: Record<number, string> = {
  0: "Вс",
  1: "Пн",
  2: "Вт",
  3: "Ср",
  4: "Чт",
  5: "Пт",
  6: "Сб",
};

function calculateMatrixEmployeesPerPage(width: number) {
  const availableWidth = Math.max(
    0,
    width - matrixModalHorizontalPadding - matrixDateColumnWidth,
  );
  return Math.min(
    8,
    Math.max(1, Math.floor(availableWidth / matrixEmployeeColumnWidth)),
  );
}

export default function AttendancePage() {
  const { user } = useUser();
  const [employees, setEmployees] = useState<User[]>([]);
  const [employeeSearch, setEmployeeSearch] = useState("");
  const [showInactiveEmployees, setShowInactiveEmployees] = useState(false);
  const [selectedEmployeeIds, setSelectedEmployeeIds] = useState<number[]>([]);
  const [periodPreset, setPeriodPreset] = useState<AttendancePeriodPreset>("month");
  const [selectedMonth, setSelectedMonth] = useState(() => getCurrentMonthKey());
  const [periodStart, setPeriodStart] = useState(
    () => getMonthRange(getCurrentMonthKey()).start,
  );
  const [periodEnd, setPeriodEnd] = useState(
    () => getMonthRange(getCurrentMonthKey()).end,
  );
  const [scheduleStart, setScheduleStart] = useState("08:00");
  const [scheduleEnd, setScheduleEnd] = useState("17:00");
  const [expectedHours, setExpectedHours] = useState("9");
  const [workdays, setWorkdays] = useState<string[]>(defaultWorkdays);
  const [loadingEmployees, setLoadingEmployees] = useState(true);
  const [loadingSchedule, setLoadingSchedule] = useState(true);
  const [savingSchedule, setSavingSchedule] = useState(false);
  const [loadingStats, setLoadingStats] = useState(false);
  const [downloadingReport, setDownloadingReport] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [scheduleFeedback, setScheduleFeedback] = useState<string | null>(null);
  const [autoSyncSettings, setAutoSyncSettings] =
    useState<AttendanceAutoSyncSettings | null>(null);
  const [autoSyncOpen, setAutoSyncOpen] = useState(false);
  const [loadingAutoSync, setLoadingAutoSync] = useState(true);
  const [savingAutoSync, setSavingAutoSync] = useState(false);
  const [runningAutoSync, setRunningAutoSync] = useState(false);
  const [autoSyncFeedback, setAutoSyncFeedback] = useState<string | null>(null);
  const [matrices, setMatrices] = useState<MonthlyAttendanceMatrix[]>([]);
  const [activeMonthIndex, setActiveMonthIndex] = useState(0);
  const [visibleEmployeePage, setVisibleEmployeePage] = useState(0);
  const [matrixEmployeesPerPage, setMatrixEmployeesPerPage] = useState(4);
  const [selectedCell, setSelectedCell] = useState<{
    row: MonthlyAttendanceMatrixRow;
    employee: MonthlyAttendanceMatrixEmployee;
    cell: MonthlyAttendanceMatrixCell;
  } | null>(null);
  const [commentsRecordPreview, setCommentsRecordPreview] =
    useState<AttendanceRecordCommentsPreview | null>(null);
  const [dayEventsRecordPreview, setDayEventsRecordPreview] =
    useState<AttendanceDayEventsPreview | null>(null);
  const [openedRecordFromUrl, setOpenedRecordFromUrl] = useState(false);
  const [statsModalOpen, setStatsModalOpen] = useState(false);
  const [actionsMenuOpen, setActionsMenuOpen] = useState(false);
  const actionsMenuRef = useRef<HTMLDivElement>(null);
  const canManageAttendance = Boolean(user?.auth?.is_staff || user?.auth?.is_superuser);

  useEffect(() => {
    let cancelled = false;

    async function loadEmployees() {
      if (!canManageAttendance) {
        setLoadingEmployees(false);
        return;
      }

      try {
        setLoadingEmployees(true);
        setError(null);
        const nextEmployees = await loadAllPages<User>((params) =>
          apiClient.getEmployees({
            ...params,
            is_active: showInactiveEmployees ? undefined : true,
            ordering: "last_name",
          }),
        );
        if (!cancelled) setEmployees(nextEmployees);
      } catch (loadError) {
        if (!cancelled) {
          setError(getErrorMessage(loadError, "Не удалось загрузить сотрудников"));
        }
      } finally {
        if (!cancelled) setLoadingEmployees(false);
      }
    }

    void loadEmployees();

    return () => {
      cancelled = true;
    };
  }, [canManageAttendance, showInactiveEmployees]);

  useEffect(() => {
    const availableIds = new Set(employees.map((employee) => employee.id));
    setSelectedEmployeeIds((current) =>
      current.filter((employeeId) => availableIds.has(employeeId)),
    );
  }, [employees]);

  useEffect(() => {
    if (!actionsMenuOpen) {
      return;
    }

    const handlePointerDown = (event: MouseEvent) => {
      if (actionsMenuRef.current && !actionsMenuRef.current.contains(event.target as Node)) {
        setActionsMenuOpen(false);
      }
    };

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setActionsMenuOpen(false);
      }
    };

    document.addEventListener("mousedown", handlePointerDown);
    document.addEventListener("keydown", handleKeyDown);

    return () => {
      document.removeEventListener("mousedown", handlePointerDown);
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, [actionsMenuOpen]);

  useEffect(() => {
    let cancelled = false;

    async function loadStandardSchedule() {
      if (!canManageAttendance) {
        setLoadingSchedule(false);
        return;
      }

      try {
        setLoadingSchedule(true);
        const schedule = await apiClient.getStandardWorkSchedule();
        if (cancelled) return;
        setScheduleStart(toTimeInputValue(schedule.start_time) || "08:00");
        setScheduleEnd(toTimeInputValue(schedule.end_time) || "17:00");
        setExpectedHours(String(schedule.expected_hours ?? 9));
        setWorkdays(
          Array.isArray(schedule.workdays) && schedule.workdays.length > 0
            ? schedule.workdays
            : defaultWorkdays,
        );
      } catch (scheduleError) {
        if (!cancelled) {
          setError(getErrorMessage(scheduleError, "Не удалось загрузить стандартный график"));
        }
      } finally {
        if (!cancelled) setLoadingSchedule(false);
      }
    }

    void loadStandardSchedule();

    return () => {
      cancelled = true;
    };
  }, [canManageAttendance]);

  useEffect(() => {
    let cancelled = false;

    async function loadAutoSyncSettings() {
      if (!canManageAttendance) {
        setLoadingAutoSync(false);
        return;
      }

      try {
        setLoadingAutoSync(true);
        const settings = await apiClient.getAttendanceAutoSyncSettings();
        if (!cancelled) setAutoSyncSettings(settings);
      } catch (autoSyncError) {
        if (!cancelled) {
          setError(getErrorMessage(autoSyncError, "Не удалось загрузить автообновление"));
        }
      } finally {
        if (!cancelled) setLoadingAutoSync(false);
      }
    }

    void loadAutoSyncSettings();

    return () => {
      cancelled = true;
    };
  }, [canManageAttendance]);

  useEffect(() => {
    function updateMatrixEmployeesPerPage() {
      setMatrixEmployeesPerPage(
        calculateMatrixEmployeesPerPage(window.innerWidth),
      );
    }

    updateMatrixEmployeesPerPage();
    window.addEventListener("resize", updateMatrixEmployeesPerPage);
    return () => window.removeEventListener("resize", updateMatrixEmployeesPerPage);
  }, []);

  useEffect(() => {
    if (openedRecordFromUrl) return;
    const params = new URLSearchParams(window.location.search);
    const shouldOpenEvents = params.get("events") === "1";
    const shouldOpenComments = params.get("comments") === "1";
    if (!shouldOpenEvents && !shouldOpenComments) return;
    const recordId = Number(params.get("record"));
    if (!Number.isInteger(recordId) || recordId <= 0) return;

    let cancelled = false;
    setOpenedRecordFromUrl(true);

    async function openRecordFromUrl() {
      try {
        setError(null);
        const record = await apiClient.getAttendanceRecord(recordId);
        if (cancelled) return;
        const preview = {
          recordId,
          employeeName: record.display_name || `Сотрудник ${record.employee || record.employee_id || recordId}`,
          date: `${record.date || ""}${record.date ? ` · ${weekdayLabelFromDate(record.date)}` : ""}`,
          statusLabel: attendanceRecordStatusLabel(record),
          displayText: attendanceRecordDisplay(record),
          detailLines: attendanceRecordDetails(record),
        };
        if (shouldOpenComments) {
          setCommentsRecordPreview({
            ...preview,
            commentsCount: Number(record.comments_count || 0),
          });
          return;
        }
        setDayEventsRecordPreview({
          ...preview,
          issues: attendanceRecordIssueLabels(record),
          isManuallyEdited: Boolean(record.is_manually_edited),
        });
      } catch (loadError) {
        if (!cancelled) {
          setError(getErrorMessage(loadError, "Не удалось открыть запись посещаемости"));
        }
      }
    }

    void openRecordFromUrl();

    return () => {
      cancelled = true;
    };
  }, [openedRecordFromUrl]);

  const filteredEmployees = useMemo(() => {
    const query = employeeSearch.trim().toLowerCase();
    if (!query) return employees;
    return employees.filter((employee) => {
      const fullName = displayUserName(employee).toLowerCase();
      const position = (employee.position?.name || "").toLowerCase();
      return (
        fullName.includes(query)
        || position.includes(query)
        || (employee.email || "").toLowerCase().includes(query)
        || String(employee.id).includes(query)
      );
    });
  }, [employees, employeeSearch]);

  const selectedEmployees = useMemo(() => {
    const selectedIds = new Set(selectedEmployeeIds);
    return employees.filter((employee) => selectedIds.has(employee.id));
  }, [employees, selectedEmployeeIds]);

  const activeMatrix = matrices[activeMonthIndex] || null;
  const visibleEmployeeStart = visibleEmployeePage * matrixEmployeesPerPage;
  const visibleEmployees = activeMatrix
    ? activeMatrix.employees.slice(
      visibleEmployeeStart,
      visibleEmployeeStart + matrixEmployeesPerPage,
    )
    : [];
  const visibleEmployeeEnd = Math.min(
    visibleEmployeeStart + visibleEmployees.length,
    activeMatrix?.employees.length || 0,
  );
  const matrixTableWidth =
    matrixDateColumnWidth + visibleEmployees.length * matrixEmployeeColumnWidth;
  const hasPreviousEmployeePage = visibleEmployeePage > 0;
  const hasNextEmployeePage = activeMatrix
    ? visibleEmployeeEnd < activeMatrix.employees.length
    : false;

  useEffect(() => {
    if (!activeMatrix) {
      setVisibleEmployeePage(0);
      return;
    }

    const maxPage = Math.max(
      0,
      Math.ceil(activeMatrix.employees.length / matrixEmployeesPerPage) - 1,
    );
    setVisibleEmployeePage((current) => Math.min(current, maxPage));
  }, [activeMatrix, matrixEmployeesPerPage]);

  function toggleEmployee(employeeId: number) {
    setSelectedEmployeeIds((current) =>
      current.includes(employeeId)
        ? current.filter((currentId) => currentId !== employeeId)
        : [...current, employeeId],
    );
  }

  function selectVisibleEmployees() {
    setSelectedEmployeeIds((current) => {
      const next = new Set(current);
      filteredEmployees.forEach((employee) => next.add(employee.id));
      return Array.from(next);
    });
  }

  function clearSelectedEmployees() {
    setSelectedEmployeeIds([]);
    setMatrices([]);
    setSelectedCell(null);
  }

  function toggleWorkday(day: string) {
    setScheduleFeedback(null);
    setWorkdays((current) =>
      current.includes(day)
        ? current.filter((currentDay) => currentDay !== day)
        : [...current, day],
    );
  }

  function selectPeriodPreset(nextPreset: AttendancePeriodPreset) {
    setPeriodPreset(nextPreset);
    setMatrices([]);
    setSelectedCell(null);
    if (nextPreset === "month") {
      const range = getMonthRange(selectedMonth);
      setPeriodStart(range.start);
      setPeriodEnd(range.end);
    }
  }

  function shiftSelectedMonth(delta: number) {
    const nextMonth = shiftMonthKey(selectedMonth, delta);
    const range = getMonthRange(nextMonth);
    setPeriodPreset("month");
    setSelectedMonth(nextMonth);
    setPeriodStart(range.start);
    setPeriodEnd(range.end);
    setMatrices([]);
    setSelectedCell(null);
  }

  async function saveStandardSchedule() {
    const hours = Number(expectedHours);
    if (!scheduleStart || !scheduleEnd || !Number.isFinite(hours) || hours <= 0 || hours > 24) {
      setScheduleFeedback(null);
      setError("Проверьте стандартный график");
      return;
    }
    if (workdays.length === 0) {
      setScheduleFeedback(null);
      setError("Выберите хотя бы один рабочий день");
      return;
    }

    try {
      setSavingSchedule(true);
      setError(null);
      setScheduleFeedback(null);
      const schedule = await apiClient.updateStandardWorkSchedule({
        start_time: scheduleStart,
        end_time: scheduleEnd,
        expected_hours: hours,
        workdays,
        date_overrides: [],
      });
      setScheduleStart(toTimeInputValue(schedule.start_time) || scheduleStart);
      setScheduleEnd(toTimeInputValue(schedule.end_time) || scheduleEnd);
      setExpectedHours(String(schedule.expected_hours ?? hours));
      setWorkdays(schedule.workdays?.length ? schedule.workdays : workdays);
      setScheduleFeedback("Стандартный график сохранен");
    } catch (saveError) {
      setError(getErrorMessage(saveError, "Не удалось сохранить стандартный график"));
    } finally {
      setSavingSchedule(false);
    }
  }

  async function saveAutoSyncSettings(
    patch: Partial<Pick<
      AttendanceAutoSyncSettings,
      "enabled" | "frequency_minutes" | "lookback_days"
    >>,
  ) {
    try {
      setSavingAutoSync(true);
      setError(null);
      setAutoSyncFeedback(null);
      const settings = await apiClient.updateAttendanceAutoSyncSettings(patch);
      setAutoSyncSettings(settings);
      setAutoSyncFeedback("Автообновление сохранено");
    } catch (saveError) {
      setError(getErrorMessage(saveError, "Не удалось сохранить автообновление"));
    } finally {
      setSavingAutoSync(false);
    }
  }

  async function runAutoSyncNow() {
    try {
      setRunningAutoSync(true);
      setError(null);
      setAutoSyncFeedback(null);
      const settings = await apiClient.runAttendanceAutoSyncNow();
      setAutoSyncSettings(settings);
      setAutoSyncFeedback("Автообновление выполнено");
    } catch (runError) {
      setError(getErrorMessage(runError, "Не удалось запустить автообновление"));
    } finally {
      setRunningAutoSync(false);
    }
  }

  function validateSelectionAndPeriod() {
    if (selectedEmployees.length === 0) {
      setError("Выберите хотя бы одного сотрудника");
      return false;
    }

    if (!periodStart || !periodEnd || periodStart > periodEnd) {
      setError("Проверьте период анализа");
      return false;
    }

    return true;
  }

  function validateStatsRequest() {
    if (!validateSelectionAndPeriod()) return false;

    const hours = Number(expectedHours);
    if (!scheduleStart || !scheduleEnd || !Number.isFinite(hours) || hours <= 0 || hours > 24) {
      setError("Проверьте стандартный график");
      return false;
    }

    if (workdays.length === 0) {
      setError("Выберите хотя бы один рабочий день");
      return false;
    }

    return true;
  }

  async function downloadReport() {
    setError(null);
    if (!validateSelectionAndPeriod()) return;

    try {
      setDownloadingReport(true);
      const employeeIds = selectedEmployees.map((employee) => employee.id).join(",");
      const file = await apiClient.downloadMonthlyAttendanceMatrix({
        employee_ids: employeeIds,
        period_start: periodStart,
        period_end: periodEnd,
      });
      const url = URL.createObjectURL(file.blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = file.filename;
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);
    } catch (downloadError) {
      setError(getErrorMessage(downloadError, "Не удалось скачать отчет посещаемости"));
    } finally {
      setDownloadingReport(false);
    }
  }

  async function loadStatistics(options?: { refreshFromAnalyzer?: boolean }) {
    setError(null);
    setMatrices([]);
    setSelectedCell(null);

    if (!validateStatsRequest()) return;

    try {
      setLoadingStats(true);
      const employeeIds = selectedEmployees.map((employee) => employee.id).join(",");

      for (const employee of selectedEmployees) {
        if (options?.refreshFromAnalyzer) {
          await apiClient.analyzeAttendance({
            employee_id: employee.id,
            period_start: periodStart,
            period_end: periodEnd,
          });
        }
      }

      const monthKeys = getMonthKeysBetween(periodStart, periodEnd);
      const nextMatrices = await Promise.all(
        monthKeys.map((month) =>
          apiClient.getMonthlyAttendanceMatrix({
            employee_ids: employeeIds,
            month,
          }),
        ),
      );

      setMatrices(nextMatrices);
      setActiveMonthIndex(Math.max(0, nextMatrices.length - 1));
      setVisibleEmployeePage(0);
      setStatsModalOpen(true);
    } catch (statsError) {
      setError(getErrorMessage(statsError, "Не удалось получить статистику посещаемости"));
    } finally {
      setLoadingStats(false);
    }
  }

  function updateSelectedCellCommentCount(recordId: number, count: number) {
    setSelectedCell((current) => {
      if (!current || current.cell.record_id !== recordId) return current;
      if (current.cell.comments_count === count) return current;
      return {
        ...current,
        cell: {
          ...current.cell,
          comments_count: count,
          detail_lines: [
            ...(current.cell.detail_lines || []).filter(
              (line) => !String(line).startsWith("Комментарии:"),
            ),
            ...(count ? [`Комментарии: ${count}`] : []),
          ],
        },
      };
    });
    setMatrices((current) => {
      let changed = false;
      const nextMatrices = current.map((matrix) => ({
        ...matrix,
        rows: matrix.rows.map((row) => ({
          ...row,
          cells: Object.fromEntries(
            Object.entries(row.cells).map(([employeeId, cell]) => {
              if (cell.record_id !== recordId || cell.comments_count === count) {
                return [employeeId, cell];
              }
              changed = true;
              return [employeeId, { ...cell, comments_count: count }];
            }),
          ),
        })),
      }));
      return changed ? nextMatrices : current;
    });
    setCommentsRecordPreview((current) => (
      current?.recordId === recordId && current.commentsCount !== count
        ? { ...current, commentsCount: count }
        : current
    ));
  }

  function openCellComments(
    row: MonthlyAttendanceMatrixRow,
    employee: MonthlyAttendanceMatrixEmployee,
    cell: MonthlyAttendanceMatrixCell,
  ) {
    if (!cell.record_id) return;
    setCommentsRecordPreview({
      recordId: cell.record_id,
      employeeName: employee.name,
      date: `${row.date} · ${row.weekday}`,
      statusLabel: cell.primary_label || matrixStatusLabel(cell.status),
      displayText: matrixCellDisplay(cell) || "Нет записи",
      detailLines: cell.detail_lines || [],
      commentsCount: cell.comments_count,
    });
  }

  function openSelectedCellComments() {
    if (!selectedCell) return;
    openCellComments(selectedCell.row, selectedCell.employee, selectedCell.cell);
  }

  function openCellDayEvents(
    row: MonthlyAttendanceMatrixRow,
    employee: MonthlyAttendanceMatrixEmployee,
    cell: MonthlyAttendanceMatrixCell,
  ) {
    if (!cell.record_id) return;
    setDayEventsRecordPreview({
      recordId: cell.record_id,
      employeeName: employee.name,
      date: `${row.date} · ${row.weekday}`,
      statusLabel: cell.primary_label || matrixStatusLabel(cell.status),
      displayText: matrixCellDisplay(cell) || "Нет записи",
      detailLines: cell.detail_lines || [],
      issues: matrixCellIssueLabels(cell).map(formatAttendanceIssueLabel),
      isManuallyEdited: Boolean(cell.is_manually_edited),
    });
  }

  const attendanceRecordModals = (
    <>
      <AttendanceRecordCommentsModal
        currentUserId={user?.id}
        isOpen={Boolean(commentsRecordPreview)}
        onClose={() => setCommentsRecordPreview(null)}
        onCommentCountChange={updateSelectedCellCommentCount}
        record={commentsRecordPreview}
      />
      <AttendanceDayEventsModal
        isOpen={Boolean(dayEventsRecordPreview)}
        onClose={() => setDayEventsRecordPreview(null)}
        record={dayEventsRecordPreview}
      />
    </>
  );

  if (!canManageAttendance) {
    return (
      <AppShell>
        <section className="app-surface mx-auto max-w-xl rounded-2xl p-6">
          <div className="flex items-start gap-3">
            <AlertTriangle size={18} className="mt-0.5 shrink-0 text-amber-400" />
            <div>
              <h1 className="text-base font-semibold text-[var(--foreground)]">
                Посещаемость
              </h1>
              <p className="app-text-muted mt-2 text-sm">
                Раздел доступен только сотрудникам с правами администрирования.
                Личную посещаемость можно посмотреть в профиле.
              </p>
            </div>
          </div>
        </section>
        {attendanceRecordModals}
      </AppShell>
    );
  }

  return (
    <AppShell>
      <div className="mx-auto flex max-w-6xl flex-col gap-4">
        <section className="app-surface rounded-2xl p-4">
          <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
            <div>
              <p className="app-text-muted text-sm font-semibold uppercase tracking-wide">Посещаемость</p>
              
            </div>
            <div className="flex flex-wrap gap-2">
              <button
                type="button"
                onClick={() => void loadStatistics()}
                disabled={loadingStats || loadingEmployees || loadingSchedule}
                className="app-action-primary inline-flex min-h-10 items-center justify-center gap-2 rounded-lg px-4 py-2 text-sm font-semibold disabled:cursor-not-allowed disabled:opacity-60"
              >
                {loadingStats ? <Loader2 size={16} className="animate-spin" /> : <CalendarCheck size={16} />}
                Показать
              </button>
              <div ref={actionsMenuRef} className="relative">
                <button
                  type="button"
                  onClick={() => setActionsMenuOpen((current) => !current)}
                  className="app-action-ghost flex h-8 w-8 items-center justify-center rounded-md"
                  aria-label="Дополнительные действия"
                  aria-expanded={actionsMenuOpen}
                  aria-haspopup="menu"
                  title="Дополнительные действия"
                >
                  <ChevronRight
                    size={15}
                    className={`transition-transform duration-200 ${actionsMenuOpen ? "rotate-90" : ""}`}
                  />
                </button>

                {actionsMenuOpen ? (
                  <div className="app-menu absolute right-0 top-full z-20 mt-2 w-48 rounded-xl py-1.5">
                    <button
                      type="button"
                      onClick={() => {
                        setActionsMenuOpen(false);
                        void downloadReport();
                      }}
                      disabled={downloadingReport || loadingEmployees}
                      className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm text-[var(--foreground)] transition hover:bg-[var(--surface-secondary)] disabled:opacity-50"
                    >
                      {downloadingReport ? (
                        <Loader2 size={14} className="app-text-muted shrink-0 animate-spin" />
                      ) : (
                        <Download size={14} className="app-text-muted shrink-0" />
                      )}
                      <span>Скачать</span>
                    </button>
                    <button
                      type="button"
                      onClick={() => {
                        setActionsMenuOpen(false);
                        void loadStatistics({ refreshFromAnalyzer: true });
                      }}
                      disabled={loadingStats || loadingEmployees || loadingSchedule}
                      className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm text-[var(--foreground)] transition hover:bg-[var(--surface-secondary)] disabled:opacity-50"
                    >
                      {loadingStats ? (
                        <Loader2 size={14} className="app-text-muted shrink-0 animate-spin" />
                      ) : (
                        <RefreshCw size={14} className="app-text-muted shrink-0" />
                      )}
                      <span>Обновить</span>
                    </button>
                  </div>
                ) : null}
              </div>
            </div>
          </div>

          <div className="max-w-[34rem]">
                <div className="app-surface-muted rounded-2xl p-3 sm:p-4">
                  <div className="relative">
                    <Search
                      size={16}
                      className="app-text-muted pointer-events-none absolute left-3 top-1/2 -translate-y-1/2"
                    />
                    <input
                      type="text"
                      value={employeeSearch}
                      onChange={(event) => setEmployeeSearch(event.target.value)}
                      placeholder="Выберите сотрудников для статистики"
                      className="app-input w-full rounded-xl py-2.5 pl-10 pr-3 text-sm"
                    />
                  </div>

                  <div className="mt-3 flex flex-wrap items-center justify-between gap-3 px-1 text-xs">
                    <span className="app-text-muted">
                      Найдено: {loadingEmployees ? "..." : filteredEmployees.length}
                    </span>
                    <span className="flex flex-wrap items-center gap-2">
                      <span className="app-accent-text font-medium">
                        Выбрано: {selectedEmployeeIds.length}
                      </span>
                      <button
                        type="button"
                        onClick={selectVisibleEmployees}
                        disabled={loadingEmployees || filteredEmployees.length === 0}
                        className="app-accent-text font-medium disabled:cursor-not-allowed disabled:opacity-40"
                      >
                        Выбрать всех
                      </button>
                      <button
                        type="button"
                        onClick={clearSelectedEmployees}
                        disabled={selectedEmployeeIds.length === 0}
                        className="text-[var(--muted-foreground)] transition hover:text-[var(--foreground)] disabled:cursor-not-allowed disabled:opacity-40"
                      >
                        Снять выбор
                      </button>
                    </span>
                  </div>

                  <label className="app-choice-label mt-3 px-1 text-xs text-[var(--muted-foreground)]">
                    <input
                      type="checkbox"
                      checked={showInactiveEmployees}
                      onChange={(event) => setShowInactiveEmployees(event.target.checked)}
                      className="app-checkbox"
                    />
                    <span>Показывать неактивных сотрудников</span>
                  </label>

                  <div className="app-surface mt-3 max-h-72 space-y-2 overflow-y-auto rounded-2xl p-2">
                    {loadingEmployees ? (
                      <div className="app-surface-muted flex items-center justify-center gap-2 rounded-xl p-5 text-sm text-[var(--muted-foreground)]">
                        <Loader2 size={16} className="animate-spin" />
                        Загрузка сотрудников
                      </div>
                    ) : null}

                    {!loadingEmployees && filteredEmployees.length === 0 ? (
                      <p className="app-text-muted px-2 py-3 text-sm">Сотрудники не найдены</p>
                    ) : null}

                    {!loadingEmployees && filteredEmployees.map((employee) => {
                      const active = selectedEmployeeIds.includes(employee.id);
                      const fullName = displayUserName(employee);
                      const subtitle = employee.email || employee.position?.name || `ID ${employee.id}`;

                      return (
                        <button
                          key={employee.id}
                          type="button"
                          onClick={() => toggleEmployee(employee.id)}
                          className={`flex w-full items-center gap-3 rounded-xl px-3 py-3 text-left transition ${
                            active
                              ? "app-selected"
                              : "app-surface-muted hover:bg-[var(--surface-tertiary)]"
                          }`}
                        >
                          {employee.avatar ? (
                            <>
                              {/* eslint-disable-next-line @next/next/no-img-element */}
                              <img
                                src={resolveMediaUrl(employee.avatar)}
                                alt={fullName}
                                className="app-avatar-frame h-10 w-10 shrink-0 rounded-full object-cover"
                              />
                            </>
                          ) : (
                            <span className="app-avatar-fallback flex h-10 w-10 shrink-0 items-center justify-center rounded-full">
                              <span className="text-sm font-semibold">
                                {getInitials(employee).toUpperCase()}
                              </span>
                            </span>
                          )}
                          <span className="min-w-0 flex-1">
                            <span className="flex items-center gap-2">
                              <span className="block truncate text-sm font-semibold text-[var(--foreground)]">
                                {fullName}
                              </span>
                              
                            </span>
                            <span className="app-text-muted block truncate text-xs">{subtitle}</span>
                          </span>
                          <span
                            className={`flex h-6 w-6 shrink-0 items-center justify-center rounded-full border transition ${
                              active
                                ? "border-[var(--accent-primary)] bg-[var(--accent-primary)] text-white"
                                : "border-[var(--border-strong)] text-transparent"
                            }`}
                          >
                            {active ? <Check size={14} /> : <span className="h-2.5 w-2.5 rounded-full bg-current" />}
                          </span>
                        </button>
                      );
                    })}
                  </div>

                  <div className="mt-4 flex flex-wrap gap-2">
                    {periodPresets.map((periodOption) => {
                      const isActive = periodPreset === periodOption.value;
                      return (
                        <button
                          key={periodOption.value}
                          type="button"
                          onClick={() => selectPeriodPreset(periodOption.value)}
                          className={isActive
                            ? "app-action-primary rounded-lg px-3 py-2 text-xs font-medium"
                            : "app-action-secondary rounded-lg px-3 py-2 text-xs font-medium"
                          }
                        >
                          {periodOption.label}
                        </button>
                      );
                    })}
                  </div>

                  {periodPreset === "month" ? (
                    <div className="mt-3 flex items-center gap-2">
                      <button
                        type="button"
                        onClick={() => shiftSelectedMonth(-1)}
                        className="app-icon-button rounded-lg p-2"
                        aria-label="Предыдущий месяц"
                      >
                        <ChevronLeft size={16} />
                      </button>
                      <span className="min-w-36 text-center text-sm font-semibold capitalize text-[var(--foreground)]">
                        {formatMonthKeyLabel(selectedMonth)}
                      </span>
                      <button
                        type="button"
                        onClick={() => shiftSelectedMonth(1)}
                        className="app-icon-button rounded-lg p-2"
                        aria-label="Следующий месяц"
                      >
                        <ChevronRight size={16} />
                      </button>
                    </div>
                  ) : null}

                  <p className="app-text-muted mt-2 px-1 text-xs">
                    {periodStart} — {periodEnd}
                  </p>

                  {periodPreset === "custom" ? (
                    <div className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-2">
                      <label className="block">
                        <span className="app-card-caption mb-2 block">Начало</span>
                        <input
                          type="date"
                          value={periodStart}
                          onChange={(event) => {
                            setPeriodStart(event.target.value);
                            setMatrices([]);
                            setSelectedCell(null);
                          }}
                          className="app-input w-full rounded-xl px-3 py-2.5 text-sm"
                        />
                      </label>
                      <label className="block">
                        <span className="app-card-caption mb-2 block">Конец</span>
                        <input
                          type="date"
                          value={periodEnd}
                          onChange={(event) => {
                            setPeriodEnd(event.target.value);
                            setMatrices([]);
                            setSelectedCell(null);
                          }}
                          className="app-input w-full rounded-xl px-3 py-2.5 text-sm"
                        />
                      </label>
                    </div>
                  ) : null}
                </div>

                <div className="mt-4 app-surface-muted rounded-2xl p-3 sm:p-4">
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div>
                      <p className="text-sm font-semibold text-[var(--foreground)]">
                        Стандартный график анализа
                      </p>
                      <p className="app-text-muted mt-1 text-xs">
                        Сохраняется на сервере и применяется, если у сотрудника нет индивидуального графика.
                      </p>
                    </div>
                    <button
                      type="button"
                      onClick={() => void saveStandardSchedule()}
                      disabled={loadingSchedule || savingSchedule}
                      className="app-action-secondary inline-flex min-h-9 items-center justify-center gap-2 rounded-lg px-3 py-2 text-xs font-semibold disabled:cursor-not-allowed disabled:opacity-60"
                    >
                      {savingSchedule ? <Loader2 size={14} className="animate-spin" /> : <Save size={14} />}
                      Сохранить
                    </button>
                  </div>

                  {loadingSchedule ? (
                    <p className="app-text-muted mt-3 flex items-center gap-2 text-xs">
                      <Loader2 size={14} className="animate-spin" />
                      Загрузка стандартного графика
                    </p>
                  ) : null}

                  <div className="mt-3 grid gap-3">
                    <div className="grid gap-3 sm:grid-cols-3">
                      <label className="block">
                        <span className="app-card-caption mb-2 block">Начало</span>
                        <input
                          type="time"
                          value={scheduleStart}
                          onChange={(event) => {
                            setScheduleStart(event.target.value);
                            setScheduleFeedback(null);
                          }}
                          className="app-input w-full rounded-lg px-3 py-2 text-sm"
                        />
                      </label>
                      <label className="block">
                        <span className="app-card-caption mb-2 block">Конец</span>
                        <input
                          type="time"
                          value={scheduleEnd}
                          onChange={(event) => {
                            setScheduleEnd(event.target.value);
                            setScheduleFeedback(null);
                          }}
                          className="app-input w-full rounded-lg px-3 py-2 text-sm"
                        />
                      </label>
                      <label className="block">
                        <span className="app-card-caption mb-2 block">Часы</span>
                        <input
                          type="number"
                          min="0"
                          step="0.25"
                          value={expectedHours}
                          onChange={(event) => {
                            setExpectedHours(event.target.value);
                            setScheduleFeedback(null);
                          }}
                          className="app-input w-full rounded-lg px-3 py-2 text-sm"
                        />
                      </label>
                    </div>

                    <div className="flex flex-wrap gap-2">
                      {weekdays.map((day) => {
                        const active = workdays.includes(day.value);
                        return (
                          <button
                            key={day.value}
                            type="button"
                            onClick={() => toggleWorkday(day.value)}
                            className={`h-9 min-w-10 rounded-lg px-3 text-sm font-medium transition ${
                              active
                                ? "app-selected text-[var(--accent-primary)]"
                                : "app-surface text-[var(--muted-foreground)] hover:bg-[var(--surface-tertiary)]"
                            }`}
                          >
                            {day.label}
                          </button>
                        );
                      })}
                    </div>

                    {scheduleFeedback ? (
                      <p className="text-xs font-medium text-emerald-300">
                        {scheduleFeedback}
                      </p>
                    ) : null}
                  </div>
                </div>

                <div className="mt-4 app-surface-muted rounded-2xl p-3 sm:p-4">
                  <button
                    type="button"
                    onClick={() => setAutoSyncOpen((current) => !current)}
                    className="flex w-full items-start justify-between gap-3 text-left"
                  >
                    <span>
                      <span className="text-sm font-semibold text-[var(--foreground)]">
                        Автообновление
                      </span>
                      <span className="app-text-muted mt-1 block text-xs">
                        {loadingAutoSync
                          ? "Загрузка настроек"
                          : autoSyncSettings?.enabled
                            ? `Включено · ${autoSyncStatusText(autoSyncSettings)}`
                            : "Выключено"}
                      </span>
                    </span>
                    <ChevronDown
                      size={16}
                      className={`mt-1 shrink-0 text-[var(--muted-foreground)] transition ${
                        autoSyncOpen ? "rotate-180" : ""
                      }`}
                    />
                  </button>

                  {autoSyncOpen ? (
                    <div className="mt-4 grid gap-3">
                      {loadingAutoSync ? (
                        <p className="app-text-muted flex items-center gap-2 text-xs">
                          <Loader2 size={14} className="animate-spin" />
                          Загрузка автообновления
                        </p>
                      ) : autoSyncSettings ? (
                        <>
                          <div className="flex flex-wrap items-center justify-between gap-3">
                            <label className="inline-flex items-center gap-2 text-sm text-[var(--foreground)]">
                              <input
                                type="checkbox"
                                checked={autoSyncSettings.enabled}
                                onChange={(event) => {
                                  setAutoSyncSettings({
                                    ...autoSyncSettings,
                                    enabled: event.target.checked,
                                  });
                                  void saveAutoSyncSettings({
                                    enabled: event.target.checked,
                                  });
                                }}
                                disabled={savingAutoSync || runningAutoSync}
                                className="h-4 w-4 accent-[var(--accent-primary)]"
                              />
                              Включить автообновление
                            </label>
                            <button
                              type="button"
                              onClick={() => void runAutoSyncNow()}
                              disabled={savingAutoSync || runningAutoSync}
                              className="app-action-secondary inline-flex min-h-9 items-center justify-center gap-2 rounded-lg px-3 py-2 text-xs font-semibold disabled:cursor-not-allowed disabled:opacity-60"
                            >
                              {runningAutoSync ? <Loader2 size={14} className="animate-spin" /> : <RefreshCw size={14} />}
                              Запустить сейчас
                            </button>
                          </div>

                          <div className="grid gap-3 sm:grid-cols-2">
                            <label className="block">
                              <span className="app-card-caption mb-2 block">Частота</span>
                              <select
                                value={autoSyncSettings.frequency_minutes}
                                onChange={(event) => {
                                  const value = Number(event.target.value);
                                  setAutoSyncSettings({
                                    ...autoSyncSettings,
                                    frequency_minutes: value,
                                  });
                                  void saveAutoSyncSettings({
                                    frequency_minutes: value,
                                  });
                                }}
                                disabled={savingAutoSync || runningAutoSync}
                                className="app-input w-full rounded-lg px-3 py-2 text-sm"
                              >
                                {autoSyncFrequencyOptions.map((option) => (
                                  <option key={option.value} value={option.value}>
                                    {option.label}
                                  </option>
                                ))}
                              </select>
                            </label>
                            <label className="block">
                              <span className="app-card-caption mb-2 block">Период</span>
                              <select
                                value={autoSyncSettings.lookback_days}
                                onChange={(event) => {
                                  const value = Number(event.target.value);
                                  setAutoSyncSettings({
                                    ...autoSyncSettings,
                                    lookback_days: value,
                                  });
                                  void saveAutoSyncSettings({
                                    lookback_days: value,
                                  });
                                }}
                                disabled={savingAutoSync || runningAutoSync}
                                className="app-input w-full rounded-lg px-3 py-2 text-sm"
                              >
                                {autoSyncLookbackOptions.map((option) => (
                                  <option key={option.value} value={option.value}>
                                    {option.label}
                                  </option>
                                ))}
                              </select>
                            </label>
                          </div>

                          <div className="grid gap-2 text-xs text-[var(--muted-foreground)] sm:grid-cols-2">
                            <p>Статус: {autoSyncStatusText(autoSyncSettings)}</p>
                            <p>Следующий запуск: {formatOptionalDateTime(autoSyncSettings.next_run_at)}</p>
                            <p>Последний старт: {formatOptionalDateTime(autoSyncSettings.last_started_at)}</p>
                            <p>Завершено: {formatOptionalDateTime(autoSyncSettings.last_finished_at)}</p>
                            <p>Успешно: {autoSyncSettings.last_success_count}</p>
                            <p>Ошибок: {autoSyncSettings.last_error_count}</p>
                          </div>

                          {autoSyncSettings.last_error ? (
                            <p className="rounded-lg border border-amber-400/30 bg-amber-500/10 px-3 py-2 text-xs text-amber-200">
                              {autoSyncSettings.last_error}
                            </p>
                          ) : null}

                          {autoSyncFeedback ? (
                            <p className="text-xs font-medium text-emerald-300">
                              {autoSyncFeedback}
                            </p>
                          ) : null}
                        </>
                      ) : (
                        <p className="app-text-muted text-xs">
                          Настройки автообновления недоступны
                        </p>
                      )}
                    </div>
                  ) : null}
                </div>

              {error ? (
                <div className="mt-4 flex items-start gap-2 rounded-lg border border-red-500/30 bg-red-500/10 px-3 py-2 text-sm text-red-300">
                  <AlertTriangle size={16} className="mt-0.5 shrink-0" />
                  <span>{error}</span>
                </div>
              ) : null}
          </div>
        </section>
      </div>

      <Modal
        isOpen={statsModalOpen}
        onClose={() => {
          setStatsModalOpen(false);
          setSelectedCell(null);
        }}
        title="Статистика посещаемости"
        size="xl"
      >
        <div className="space-y-4">
          {!activeMatrix ? (
            <div className="app-surface-muted rounded-xl p-8 text-center">
              <p className="app-text-muted text-sm">Записей за выбранный период нет</p>
            </div>
          ) : (
            <>
              <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                <p className="app-text-muted text-sm">
                  {periodStart} — {periodEnd}. Сотрудников: {activeMatrix.employees.length}
                </p>
                <div className="flex flex-wrap items-center gap-3">
                  <div className="flex items-center gap-2">
                    <button
                      type="button"
                      onClick={() => {
                        setActiveMonthIndex((current) => Math.max(0, current - 1));
                        setVisibleEmployeePage(0);
                        setSelectedCell(null);
                      }}
                      disabled={activeMonthIndex === 0}
                      className="app-icon-button rounded-lg p-2 disabled:cursor-not-allowed disabled:opacity-40"
                      aria-label="Предыдущий месяц"
                    >
                      <ChevronLeft size={18} />
                    </button>
                    <span className="min-w-36 text-center text-sm font-semibold text-[var(--foreground)]">
                      {activeMatrix.month_label}
                    </span>
                    <button
                      type="button"
                      onClick={() => {
                        setActiveMonthIndex((current) =>
                          Math.min(matrices.length - 1, current + 1),
                        );
                        setVisibleEmployeePage(0);
                        setSelectedCell(null);
                      }}
                      disabled={activeMonthIndex >= matrices.length - 1}
                      className="app-icon-button rounded-lg p-2 disabled:cursor-not-allowed disabled:opacity-40"
                      aria-label="Следующий месяц"
                    >
                      <ChevronRight size={18} />
                    </button>
                  </div>
                  {activeMatrix.employees.length > matrixEmployeesPerPage ? (
                    <div className="flex items-center gap-2">
                      <button
                        type="button"
                        onClick={() => {
                          setVisibleEmployeePage((current) => Math.max(0, current - 1));
                          setSelectedCell(null);
                        }}
                        disabled={!hasPreviousEmployeePage}
                        className="app-icon-button rounded-lg p-2 disabled:cursor-not-allowed disabled:opacity-40"
                        aria-label="Предыдущие сотрудники"
                      >
                        <ChevronLeft size={18} />
                      </button>
                      <span className="app-text-muted min-w-28 text-center text-xs">
                        {visibleEmployeeStart + 1}-{visibleEmployeeEnd} из {activeMatrix.employees.length}
                      </span>
                      <button
                        type="button"
                        onClick={() => {
                          setVisibleEmployeePage((current) => current + 1);
                          setSelectedCell(null);
                        }}
                        disabled={!hasNextEmployeePage}
                        className="app-icon-button rounded-lg p-2 disabled:cursor-not-allowed disabled:opacity-40"
                        aria-label="Следующие сотрудники"
                      >
                        <ChevronRight size={18} />
                      </button>
                    </div>
                  ) : null}
                </div>
              </div>

              <div className="max-w-full overflow-x-auto rounded-xl border border-[var(--border-subtle)]">
                <table
                  className="table-fixed border-separate border-spacing-0 text-left text-xs"
                  style={{ width: matrixTableWidth }}
                >
                  <colgroup>
                    <col style={{ width: matrixDateColumnWidth }} />
                    {visibleEmployees.map((employee) => (
                      <col key={employee.id} style={{ width: matrixEmployeeColumnWidth }} />
                    ))}
                  </colgroup>
                  <thead>
                    <tr className="bg-[var(--surface-secondary)] text-[var(--muted-foreground)]">
                      <th
                        className="sticky left-0 z-20 border-b border-r border-[var(--border-subtle)] bg-[var(--surface-secondary)] px-3 py-3 font-semibold"
                      >
                        Дата
                      </th>
                      {visibleEmployees.map((employee) => (
                        <th
                          key={employee.id}
                          className="border-b border-r border-[var(--border-subtle)] px-3 py-3 text-center font-semibold text-[var(--foreground)]"
                        >
                          <span className="block truncate">{employee.name}</span>
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {activeMatrix.rows.map((row) => (
                      <tr key={row.date}>
                        <th className={`sticky left-0 z-10 border-b border-r border-[var(--border-subtle)] px-3 py-2 text-left font-medium ${
                          row.is_weekend
                            ? "bg-slate-500/10 text-slate-300"
                            : "bg-[var(--surface-secondary)] text-[var(--foreground)]"
                        }`}>
                          {row.label}
                        </th>
                        {visibleEmployees.map((employee) => {
                          const cell = row.cells[String(employee.id)];
                          const active = selectedCell?.row.date === row.date
                            && selectedCell.employee.id === employee.id;
                          return (
                            <td
                              key={`${row.date}-${employee.id}`}
                              className="border-b border-r border-[var(--border-subtle)] p-0"
                            >
                              <div className="relative h-10">
                                <button
                                  type="button"
                                  onClick={() => {
                                    setSelectedCell({ row, employee, cell });
                                    openCellDayEvents(row, employee, cell);
                                  }}
                                  className={`h-10 w-full overflow-hidden px-2 text-center transition ${matrixCellTone(cell.status)} ${matrixCellSourceTone(cell)} ${
                                    active ? "ring-2 ring-inset ring-[var(--accent-primary)]" : ""
                                  }`}
                                  title={cell.primary_label || matrixStatusLabel(cell.status)}
                                >
                                  <span className="block truncate font-medium">
                                    {matrixCellDisplay(cell)}
                                  </span>
                                </button>
                                {cell.comments_count ? (
                                  <button
                                    type="button"
                                    onClick={(event) => {
                                      event.stopPropagation();
                                      setSelectedCell({ row, employee, cell });
                                      openCellComments(row, employee, cell);
                                    }}
                                    className="absolute right-1 top-1 rounded border border-[var(--border-subtle)] bg-[var(--surface-primary)] px-1 text-[9px] leading-3 text-[var(--muted-foreground)] transition hover:border-[var(--accent-primary)] hover:text-[var(--foreground)]"
                                    aria-label={`Открыть комментарии: ${cell.comments_count}`}
                                    title="Открыть комментарии"
                                  >
                                    К:{cell.comments_count}
                                  </button>
                                ) : cell.record_id ? (
                                  <button
                                    type="button"
                                    onClick={(event) => {
                                      event.stopPropagation();
                                      setSelectedCell({ row, employee, cell });
                                      openCellComments(row, employee, cell);
                                    }}
                                    className="absolute bottom-1 left-1 inline-flex h-4 min-w-4 items-center justify-center rounded border border-[var(--border-subtle)] bg-[var(--surface-primary)] px-1 text-[10px] leading-3 text-[var(--muted-foreground)] transition hover:border-[var(--accent-primary)] hover:text-[var(--foreground)]"
                                    aria-label="Добавить комментарий"
                                    title="Добавить комментарий"
                                  >
                                    +
                                  </button>
                                ) : null}
                                {cell.is_manually_edited ? (
                                  <span className="absolute bottom-1 right-1 h-1.5 w-1.5 rounded-full bg-violet-300" />
                                ) : null}
                              </div>
                            </td>
                          );
                        })}
                      </tr>
                    ))}
                    {activeMatrix.summary.map((summaryRow) => (
                      <tr key={summaryRow.key} className="bg-[var(--surface-secondary)]">
                        <th className="sticky left-0 z-10 border-b border-r border-[var(--border-subtle)] bg-[var(--surface-secondary)] px-3 py-2 text-left font-semibold text-[var(--foreground)]">
                          {summaryRow.label}
                        </th>
                        {visibleEmployees.map((employee) => (
                          <td
                            key={`${summaryRow.key}-${employee.id}`}
                            className="border-b border-r border-[var(--border-subtle)] px-2 py-2 text-center font-semibold text-[var(--foreground)]"
                          >
                            {summaryRow.values[String(employee.id)] ?? 0}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              {selectedCell ? (
                <div className="app-surface-muted rounded-xl p-4">
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div>
                      <p className="text-sm font-semibold text-[var(--foreground)]">
                        {selectedCell.employee.name}
                      </p>
                      <p className="app-text-muted mt-1 text-xs">
                        {selectedCell.row.date} · {selectedCell.row.weekday}
                      </p>
                    </div>
                    <span className={`app-status-pill ${matrixCellTone(selectedCell.cell.status)}`}>
                      {selectedCell.cell.primary_label || matrixStatusLabel(selectedCell.cell.status)}
                    </span>
                  </div>
                  <div className="mt-3 rounded-lg border border-[var(--border-subtle)] bg-[var(--surface-primary)] px-3 py-2">
                    <p className="text-sm font-semibold text-[var(--foreground)]">
                      {matrixCellDisplay(selectedCell.cell) || "Нет записи"}
                    </p>
                    {selectedCell.cell.detail_lines?.length ? (
                      <div className="mt-2 grid gap-1 text-xs text-[var(--muted-foreground)] sm:grid-cols-2">
                        {selectedCell.cell.detail_lines.map((line) => (
                          <p key={line}>{line}</p>
                        ))}
                      </div>
                    ) : null}
                  </div>
                  <div className="mt-4 grid gap-3 text-sm sm:grid-cols-4">
                    <div>
                      <p className="app-card-caption">Приход</p>
                      <p className="mt-1 text-[var(--foreground)]">{formatTime(selectedCell.cell.arrival_time)}</p>
                    </div>
                    <div>
                      <p className="app-card-caption">Уход</p>
                      <p className="mt-1 text-[var(--foreground)]">{formatTime(selectedCell.cell.departure_time)}</p>
                    </div>
                    <div>
                      <p className="app-card-caption">Часы</p>
                      <p className="mt-1 text-[var(--foreground)]">
                        {formatHours(selectedCell.cell.work_hours)} / {formatHours(selectedCell.cell.expected_hours)}
                      </p>
                    </div>
                    <div>
                      <p className="app-card-caption">Комментарии</p>
                      <p className="mt-1 text-[var(--foreground)]">{selectedCell.cell.comments_count}</p>
                    </div>
                  </div>
                  {selectedCell.cell.personnel_status_label ? (
                    <p className="app-text-muted mt-3 text-sm">
                      Кадровое состояние: {selectedCell.cell.personnel_status_label}
                    </p>
                  ) : selectedCell.cell.non_working_reason ? (
                    <p className="app-text-muted mt-3 text-sm">
                      Причина нерабочего дня: {selectedCell.cell.non_working_reason}
                    </p>
                  ) : null}
                  {matrixCellIssueLabels(selectedCell.cell).length > 0 ? (
                    <div className="mt-3 flex flex-wrap gap-1.5">
                      {matrixCellIssueLabels(selectedCell.cell).map((issue) => (
                        <span key={issue} className="app-status-pill bg-amber-500/15 text-amber-300">
                          {formatAttendanceIssueLabel(issue)}
                        </span>
                      ))}
                    </div>
                  ) : null}
                  {selectedCell.cell.is_manually_edited ? (
                    <div className="mt-3 inline-flex rounded-lg border border-violet-400/30 bg-violet-500/10 px-2.5 py-1 text-xs font-medium text-violet-200">
                      Ручная корректировка EUSRR
                    </div>
                  ) : null}
                  {selectedCell.cell.record_id ? (
                    <div className="mt-4 border-t border-[var(--border-subtle)] pt-4">
                      <button
                        type="button"
                        onClick={openSelectedCellComments}
                        className="app-action-secondary inline-flex items-center gap-2 rounded-lg px-3 py-2 text-sm"
                      >
                        <MessageSquare size={16} />
                        Комментарии
                        {selectedCell.cell.comments_count ? (
                          <span className="app-counter min-w-4 px-1 text-[10px] font-bold">
                            {selectedCell.cell.comments_count}
                          </span>
                        ) : null}
                      </button>
                    </div>
                  ) : null}
                </div>
              ) : (
                <p className="app-text-muted text-sm">
                  Нажмите на ячейку месяца, чтобы открыть детали дня.
                </p>
              )}
            </>
          )}
        </div>
      </Modal>
      {attendanceRecordModals}
    </AppShell>
  );
}
