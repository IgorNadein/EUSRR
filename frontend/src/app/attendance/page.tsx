"use client";

import { Fragment, useEffect, useMemo, useState } from "react";
import {
  AlertTriangle,
  CalendarCheck,
  Check,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  Loader2,
  RefreshCw,
  Search,
} from "lucide-react";

import { AppShell } from "@/components/AppShell";
import { Modal } from "@/components/ui";
import { apiClient } from "@/lib/api";
import { loadAllPages, displayUserName } from "@/lib/shared";
import { resolveMediaUrl } from "@/lib/url";
import type {
  MonthlyAttendanceMatrix,
  MonthlyAttendanceMatrixCell,
  MonthlyAttendanceMatrixEmployee,
  MonthlyAttendanceMatrixRow,
  LogStormSchedulePayload,
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

type AttendancePeriodPreset = "week" | "month" | "year" | "custom";

const periodPresets: Array<{ value: AttendancePeriodPreset; label: string }> = [
  { value: "week", label: "За неделю" },
  { value: "month", label: "За месяц" },
  { value: "year", label: "За год" },
  { value: "custom", label: "Свой период" },
];

function toDateInputValue(date: Date) {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function getPeriodStart(preset: Exclude<AttendancePeriodPreset, "custom">) {
  const date = new Date();
  if (preset === "week") date.setDate(date.getDate() - 6);
  if (preset === "month") date.setMonth(date.getMonth() - 1);
  if (preset === "year") date.setFullYear(date.getFullYear() - 1);
  return toDateInputValue(date);
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
  const [employees, setEmployees] = useState<User[]>([]);
  const [employeeSearch, setEmployeeSearch] = useState("");
  const [selectedEmployeeIds, setSelectedEmployeeIds] = useState<number[]>([]);
  const [periodPreset, setPeriodPreset] = useState<AttendancePeriodPreset>("week");
  const [periodStart, setPeriodStart] = useState(() => getPeriodStart("week"));
  const [periodEnd, setPeriodEnd] = useState(() => toDateInputValue(new Date()));
  const [useManualSchedule, setUseManualSchedule] = useState(false);
  const [scheduleStart, setScheduleStart] = useState("09:00");
  const [scheduleEnd, setScheduleEnd] = useState("18:00");
  const [expectedHours, setExpectedHours] = useState("9");
  const [workdays, setWorkdays] = useState<string[]>(defaultWorkdays);
  const [selectorOpen, setSelectorOpen] = useState(true);
  const [loadingEmployees, setLoadingEmployees] = useState(true);
  const [loadingStats, setLoadingStats] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [matrices, setMatrices] = useState<MonthlyAttendanceMatrix[]>([]);
  const [activeMonthIndex, setActiveMonthIndex] = useState(0);
  const [visibleEmployeePage, setVisibleEmployeePage] = useState(0);
  const [matrixEmployeesPerPage, setMatrixEmployeesPerPage] = useState(4);
  const [selectedCell, setSelectedCell] = useState<{
    row: MonthlyAttendanceMatrixRow;
    employee: MonthlyAttendanceMatrixEmployee;
    cell: MonthlyAttendanceMatrixCell;
  } | null>(null);
  const [statsModalOpen, setStatsModalOpen] = useState(false);

  useEffect(() => {
    let cancelled = false;

    async function loadEmployees() {
      try {
        setLoadingEmployees(true);
        setError(null);
        const nextEmployees = await loadAllPages<User>((params) =>
          apiClient.getEmployees({
            ...params,
            is_active: true,
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
  }, []);

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
    if (nextPreset !== "custom") {
      setPeriodStart(getPeriodStart(nextPreset));
      setPeriodEnd(toDateInputValue(new Date()));
    }
  }

  function getSchedulePayload(): LogStormSchedulePayload | undefined {
    if (!useManualSchedule) return undefined;
    return {
      start_time: scheduleStart,
      end_time: scheduleEnd,
      expected_hours: Number(expectedHours),
      workdays,
      // TODO: Send date_overrides from EUSRR when schedule UI can store working/weekend days.
      date_overrides: [],
    };
  }

  function validateStatsRequest() {
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

  async function loadStatistics(options?: { refreshFromLogStorm?: boolean }) {
    setError(null);
    setMatrices([]);
    setSelectedCell(null);

    if (!validateStatsRequest()) return;

    try {
      setLoadingStats(true);
      const schedule = getSchedulePayload();
      const employeeIds = selectedEmployees.map((employee) => employee.id).join(",");

      for (const employee of selectedEmployees) {
        if (options?.refreshFromLogStorm) {
          await apiClient.analyzeLogStormAttendance({
            employee_id: employee.id,
            period_start: periodStart,
            period_end: periodEnd,
            schedule,
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

  return (
    <AppShell>
      <div className="mx-auto flex max-w-6xl flex-col gap-4">
        <section className="app-surface overflow-hidden rounded-2xl">
          <button
            type="button"
            onClick={() => setSelectorOpen((current) => !current)}
            className="flex w-full items-center justify-between gap-3 px-4 py-3 text-left transition hover:bg-[var(--surface-secondary)] sm:px-5"
            aria-expanded={selectorOpen}
          >
            <div className="min-w-0">
              <h1 className="text-base font-semibold text-[var(--foreground)] sm:text-lg">
                Посещаемость
              </h1>
              <p className="app-text-muted mt-1 text-xs sm:text-sm">
                Выбор сотрудников и периода для статистики LogStorm
              </p>
            </div>
            <ChevronDown
              size={18}
              className={`shrink-0 text-[var(--foreground-muted)] transition-transform ${selectorOpen ? "rotate-180" : ""}`}
            />
          </button>

          {selectorOpen ? (
            <div className="border-t border-[var(--border-subtle)] px-4 py-4 sm:px-5">
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
                            <span className="block truncate text-sm font-semibold text-[var(--foreground)]">
                              {fullName}
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
                  <label className="flex items-center gap-3 text-sm font-medium text-[var(--foreground)]">
                    <input
                      type="checkbox"
                      checked={useManualSchedule}
                      onChange={(event) => setUseManualSchedule(event.target.checked)}
                      className="h-4 w-4 rounded border-[var(--border-subtle)]"
                    />
                    Ручной график
                  </label>

                  {useManualSchedule ? (
                    <div className="mt-3 grid gap-3">
                      <div className="grid gap-3 sm:grid-cols-3">
                        <label className="block">
                          <span className="app-card-caption mb-2 block">Начало</span>
                          <input
                            type="time"
                            value={scheduleStart}
                            onChange={(event) => setScheduleStart(event.target.value)}
                            className="app-input w-full rounded-lg px-3 py-2 text-sm"
                          />
                        </label>
                        <label className="block">
                          <span className="app-card-caption mb-2 block">Конец</span>
                          <input
                            type="time"
                            value={scheduleEnd}
                            onChange={(event) => setScheduleEnd(event.target.value)}
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
                            onChange={(event) => setExpectedHours(event.target.value)}
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
                    </div>
                  ) : null}
                </div>

                <div className="mt-4 flex flex-wrap gap-2">
                  <button
                    type="button"
                    onClick={() => void loadStatistics()}
                    disabled={loadingStats || loadingEmployees}
                    className="app-action-secondary inline-flex min-h-10 items-center justify-center gap-2 rounded-lg px-4 py-2 text-sm font-semibold disabled:cursor-not-allowed disabled:opacity-60"
                  >
                    {loadingStats ? <Loader2 size={16} className="animate-spin" /> : <CalendarCheck size={16} />}
                    Показать статистику
                  </button>
                  <button
                    type="button"
                    onClick={() => void loadStatistics({ refreshFromLogStorm: true })}
                    disabled={loadingStats || loadingEmployees}
                    className="app-action-primary inline-flex min-h-10 items-center justify-center gap-2 rounded-lg px-4 py-2 text-sm font-semibold disabled:cursor-not-allowed disabled:opacity-60"
                  >
                    {loadingStats ? <Loader2 size={16} className="animate-spin" /> : <RefreshCw size={16} />}
                    Обновить и открыть
                  </button>
                </div>
              </div>

              {error ? (
                <div className="mt-4 flex max-w-[34rem] items-start gap-2 rounded-lg border border-red-500/30 bg-red-500/10 px-3 py-2 text-sm text-red-300">
                  <AlertTriangle size={16} className="mt-0.5 shrink-0" />
                  <span>{error}</span>
                </div>
              ) : null}
            </div>
          ) : null}
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

              <div className="overflow-x-auto rounded-xl border border-[var(--border-subtle)]">
                <table className="min-w-max border-separate border-spacing-0 text-left text-xs">
                  <thead>
                    <tr className="bg-[var(--surface-secondary)] text-[var(--muted-foreground)]">
                      <th
                        rowSpan={2}
                        className="sticky left-0 z-20 min-w-28 border-b border-r border-[var(--border-subtle)] bg-[var(--surface-secondary)] px-3 py-3 font-semibold"
                      >
                        Дата
                      </th>
                      {visibleEmployees.map((employee) => (
                        <th
                          key={employee.id}
                          colSpan={2}
                          className="min-w-40 border-b border-r border-[var(--border-subtle)] px-3 py-2 text-center font-semibold text-[var(--foreground)]"
                        >
                          <span className="block max-w-44 truncate">{employee.name}</span>
                        </th>
                      ))}
                    </tr>
                    <tr className="bg-[var(--surface-secondary)] text-[var(--muted-foreground)]">
                      {visibleEmployees.map((employee) => (
                        <Fragment key={employee.id}>
                          <th
                            className="min-w-20 border-b border-r border-[var(--border-subtle)] px-2 py-2 text-center font-semibold"
                          >
                            Приход
                          </th>
                          <th
                            className="min-w-20 border-b border-r border-[var(--border-subtle)] px-2 py-2 text-center font-semibold"
                          >
                            Уход
                          </th>
                        </Fragment>
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
                            <Fragment key={`${row.date}-${employee.id}`}>
                              <td
                                className="border-b border-r border-[var(--border-subtle)] p-0"
                              >
                                <button
                                  type="button"
                                  onClick={() => setSelectedCell({ row, employee, cell })}
                                  className={`h-10 w-full px-2 text-center transition ${matrixCellTone(cell.status)} ${
                                    active ? "ring-2 ring-inset ring-[var(--accent-primary)]" : ""
                                  }`}
                                  title={matrixStatusLabel(cell.status)}
                                >
                                  {formatTime(cell.arrival_time)}
                                </button>
                              </td>
                              <td
                                className="border-b border-r border-[var(--border-subtle)] p-0"
                              >
                                <button
                                  type="button"
                                  onClick={() => setSelectedCell({ row, employee, cell })}
                                  className={`h-10 w-full px-2 text-center transition ${matrixCellTone(cell.status)} ${
                                    active ? "ring-2 ring-inset ring-[var(--accent-primary)]" : ""
                                  }`}
                                  title={matrixStatusLabel(cell.status)}
                                >
                                  {formatTime(cell.departure_time)}
                                </button>
                              </td>
                            </Fragment>
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
                            colSpan={2}
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
                      {matrixStatusLabel(selectedCell.cell.status)}
                    </span>
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
    </AppShell>
  );
}
