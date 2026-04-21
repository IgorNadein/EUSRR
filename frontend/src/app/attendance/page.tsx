"use client";

import { useEffect, useMemo, useState } from "react";
import { AlertTriangle, CalendarCheck, Check, Loader2, Search } from "lucide-react";

import { AppShell } from "@/components/AppShell";
import { apiClient } from "@/lib/api";
import { loadAllPages } from "@/lib/shared";
import type {
  LogStormAttendanceRecord,
  LogStormAttendanceResponse,
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

function toDateInputValue(date: Date) {
  return date.toISOString().slice(0, 10);
}

function getDefaultPeriodStart() {
  const date = new Date();
  date.setDate(date.getDate() - 6);
  return toDateInputValue(date);
}

function getFullName(employee: User) {
  return `${employee.last_name || ""} ${employee.first_name || ""} ${employee.patronymic || ""}`.trim() || employee.email || `#${employee.id}`;
}

function getInitials(employee: User) {
  const first = employee.first_name?.[0] || "";
  const last = employee.last_name?.[0] || "";
  const fallback = employee.email?.[0] || String(employee.id)[0] || "";
  return `${last}${first}` || fallback;
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

function issueLabels(record: LogStormAttendanceRecord) {
  const labels = [
    ...(record.statuses || []),
    ...(record.employee_issues || []),
    ...(record.technical_issues || []),
  ];

  if (labels.length > 0) return labels.map(String);

  const fallback = [];
  if (record.is_absent) fallback.push("absence");
  if (record.is_late) fallback.push("late");
  if (record.is_early_leave) fallback.push("early_leave");
  if (record.is_underwork) fallback.push("underwork");
  if (record.is_overtime) fallback.push("overtime");
  return fallback;
}

function getErrorMessage(error: unknown, fallback: string) {
  return String((error as Error)?.message || fallback);
}

export default function AttendancePage() {
  const [employees, setEmployees] = useState<User[]>([]);
  const [employeeSearch, setEmployeeSearch] = useState("");
  const [employeeId, setEmployeeId] = useState("");
  const [periodStart, setPeriodStart] = useState(getDefaultPeriodStart);
  const [periodEnd, setPeriodEnd] = useState(() => toDateInputValue(new Date()));
  const [useManualSchedule, setUseManualSchedule] = useState(false);
  const [scheduleStart, setScheduleStart] = useState("09:00");
  const [scheduleEnd, setScheduleEnd] = useState("18:00");
  const [expectedHours, setExpectedHours] = useState("9");
  const [workdays, setWorkdays] = useState<string[]>(defaultWorkdays);
  const [loadingEmployees, setLoadingEmployees] = useState(true);
  const [loadingAnalysis, setLoadingAnalysis] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<LogStormAttendanceResponse | null>(null);

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

  const filteredEmployees = useMemo(() => {
    const query = employeeSearch.trim().toLowerCase();
    if (!query) return employees;
    return employees.filter((employee) => {
      const fullName = getFullName(employee).toLowerCase();
      const position = (employee.position?.name || "").toLowerCase();
      return fullName.includes(query) || position.includes(query) || String(employee.id).includes(query);
    });
  }, [employees, employeeSearch]);

  const records = useMemo(() => {
    if (!result?.records || !Array.isArray(result.records)) return [];
    return result.records;
  }, [result]);

  const summary = useMemo(() => {
    const issueDays = records.filter((record) => issueLabels(record).length > 0).length;
    return {
      total: records.length,
      workdays: records.filter((record) => record.is_workday).length,
      overtime: records.filter((record) => record.is_overtime).length,
      issueDays,
    };
  }, [records]);

  const selectedEmployee = employees.find((employee) => String(employee.id) === employeeId);

  function toggleWorkday(day: string) {
    setWorkdays((current) =>
      current.includes(day)
        ? current.filter((currentDay) => currentDay !== day)
        : [...current, day],
    );
  }

  async function analyzeAttendance(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setResult(null);

    if (!employeeId) {
      setError("Выберите сотрудника");
      return;
    }

    if (!periodStart || !periodEnd || periodStart > periodEnd) {
      setError("Проверьте период анализа");
      return;
    }

    try {
      setLoadingAnalysis(true);
      const payload: {
        employee_id: number;
        period_start: string;
        period_end: string;
        schedule?: LogStormSchedulePayload;
      } = {
        employee_id: Number(employeeId),
        period_start: periodStart,
        period_end: periodEnd,
      };

      if (useManualSchedule) {
        payload.schedule = {
          start_time: scheduleStart,
          end_time: scheduleEnd,
          expected_hours: Number(expectedHours),
          workdays,
          // TODO: Send date_overrides from EUSRR when schedule UI can store working/weekend days.
          date_overrides: [],
        };
      }

      const response = await apiClient.analyzeLogStormAttendance(payload);
      setResult(response);
    } catch (analysisError) {
      setError(getErrorMessage(analysisError, "Не удалось выполнить анализ"));
    } finally {
      setLoadingAnalysis(false);
    }
  }

  return (
    <AppShell>
      <div className="mx-auto flex max-w-6xl flex-col gap-4">
        <section className="app-surface rounded-2xl p-4 sm:p-5">
          <div className="mb-4 flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <h1 className="text-lg font-semibold text-[var(--foreground)]">Посещаемость</h1>
              <p className="app-text-muted text-sm">Анализ проходов LogStorm</p>
            </div>
            {selectedEmployee ? (
              <div className="app-surface-muted rounded-lg px-3 py-2 text-sm text-[var(--foreground)]">
                {getFullName(selectedEmployee)}
              </div>
            ) : null}
          </div>

          <form onSubmit={(event) => void analyzeAttendance(event)} className="grid gap-4 xl:grid-cols-[20rem_minmax(0,1fr)]">
            <div className="app-surface-muted rounded-xl p-3 xl:sticky xl:top-20 xl:self-start">
                <div className="relative">
                  <Search size={18} className="app-text-muted pointer-events-none absolute left-4 top-1/2 -translate-y-1/2" />
                  <input
                    value={employeeSearch}
                    onChange={(event) => setEmployeeSearch(event.target.value)}
                    className="app-input w-full rounded-xl py-3 pl-11 pr-4 text-sm"
                    placeholder="Выберите сотрудника для анализа"
                  />
                </div>

                <div className="mt-3 flex items-center justify-between gap-3 px-1 text-xs">
                  <span className="app-text-muted">
                    Найдено: {loadingEmployees ? "..." : filteredEmployees.length}
                  </span>
                  <span className="text-[var(--accent-primary)]">
                    Выбрано: {employeeId ? 1 : 0}
                  </span>
                </div>

                <div className="mt-3 max-h-[21rem] space-y-2 overflow-y-auto pr-1">
                  {loadingEmployees ? (
                    <div className="app-surface flex items-center justify-center gap-2 rounded-xl p-5 text-sm text-[var(--muted-foreground)]">
                      <Loader2 size={16} className="animate-spin" />
                      Загрузка сотрудников
                    </div>
                  ) : null}

                  {!loadingEmployees && filteredEmployees.length === 0 ? (
                    <div className="app-surface rounded-xl p-5 text-center text-sm text-[var(--muted-foreground)]">
                      Сотрудники не найдены
                    </div>
                  ) : null}

                  {!loadingEmployees && filteredEmployees.map((employee) => {
                    const active = String(employee.id) === employeeId;
                    const fullName = getFullName(employee);
                    const subtitle = employee.email || employee.position?.name || `ID ${employee.id}`;

                    return (
                      <button
                        key={employee.id}
                        type="button"
                        onClick={() => setEmployeeId(String(employee.id))}
                        className={`flex w-full items-center gap-3 rounded-xl border px-3 py-3 text-left transition ${
                          active
                            ? "border-[var(--accent-primary)] bg-[var(--accent-soft)]"
                            : "border-[var(--border-subtle)] bg-[var(--surface-primary)] hover:border-[var(--border-strong)] hover:bg-[var(--surface-elevated)]"
                        }`}
                      >
                        <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full border border-[var(--accent-primary)] bg-[var(--accent-soft)] text-sm font-semibold text-[var(--accent-primary)]">
                          {getInitials(employee).toUpperCase()}
                        </span>
                        <span className="min-w-0 flex-1">
                          <span className="block truncate text-sm font-semibold text-[var(--foreground)]">{fullName}</span>
                          <span className="app-text-muted block truncate text-xs">{subtitle}</span>
                        </span>
                        <span className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-full border ${
                          active
                            ? "border-[var(--accent-primary)] bg-[var(--accent-primary)] text-white"
                            : "border-[var(--border-strong)]"
                        }`}>
                          {active ? <Check size={15} /> : null}
                        </span>
                      </button>
                    );
                  })}
                </div>
            </div>

            <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_17rem]">
              <div className="space-y-4">
              <div className="grid gap-3 md:grid-cols-2">
                <label className="block">
                  <span className="app-card-caption mb-2 block">Начало периода</span>
                  <input
                    type="date"
                    value={periodStart}
                    onChange={(event) => setPeriodStart(event.target.value)}
                    className="app-input w-full rounded-lg px-3 py-2.5 text-sm"
                  />
                </label>

                <label className="block">
                  <span className="app-card-caption mb-2 block">Конец периода</span>
                  <input
                    type="date"
                    value={periodEnd}
                    onChange={(event) => setPeriodEnd(event.target.value)}
                    className="app-input w-full rounded-lg px-3 py-2.5 text-sm"
                  />
                </label>
              </div>

              <div className="app-surface-muted rounded-xl p-3">
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
            </div>

            <div className="app-surface-muted flex flex-col justify-between gap-4 rounded-xl p-4 lg:self-start">
              <div className="space-y-3">
                <div className="flex items-center gap-2 text-sm font-semibold text-[var(--foreground)]">
                  <CalendarCheck size={18} />
                  LogStorm
                </div>
                <div className="grid grid-cols-2 gap-2 lg:grid-cols-1">
                  <div className="app-surface rounded-lg px-3 py-2">
                    <p className="app-card-caption">Записей</p>
                    <p className="text-lg font-semibold text-[var(--foreground)]">{summary.total}</p>
                  </div>
                  <div className="app-surface rounded-lg px-3 py-2">
                    <p className="app-card-caption">Рабочих</p>
                    <p className="text-lg font-semibold text-[var(--foreground)]">{summary.workdays}</p>
                  </div>
                  <div className="app-surface rounded-lg px-3 py-2">
                    <p className="app-card-caption">Проблем</p>
                    <p className="text-lg font-semibold text-[var(--foreground)]">{summary.issueDays}</p>
                  </div>
                  <div className="app-surface rounded-lg px-3 py-2">
                    <p className="app-card-caption">Переработок</p>
                    <p className="text-lg font-semibold text-[var(--foreground)]">{summary.overtime}</p>
                  </div>
                </div>
              </div>

              <button
                type="submit"
                disabled={loadingAnalysis || loadingEmployees}
                className="inline-flex h-10 items-center justify-center gap-2 rounded-lg bg-[var(--accent-primary)] px-4 text-sm font-semibold text-white transition hover:bg-[var(--accent-hover)] disabled:cursor-not-allowed disabled:opacity-60"
              >
                {loadingAnalysis ? <Loader2 size={16} className="animate-spin" /> : <CalendarCheck size={16} />}
                Анализировать
              </button>
            </div>
            </div>
          </form>

          {error ? (
            <div className="mt-4 flex items-start gap-2 rounded-lg border border-red-500/30 bg-red-500/10 px-3 py-2 text-sm text-red-300">
              <AlertTriangle size={16} className="mt-0.5 shrink-0" />
              <span>{error}</span>
            </div>
          ) : null}
        </section>

        <section className="app-surface rounded-2xl p-4 sm:p-5">
          {result && records.length === 0 ? (
            <div className="app-surface-muted rounded-xl p-8 text-center">
              <p className="app-text-muted text-sm">Записей за период нет</p>
            </div>
          ) : null}

          {!result ? (
            <div className="app-surface-muted rounded-xl p-8 text-center">
              <p className="app-text-muted text-sm">Выберите сотрудника и период</p>
            </div>
          ) : null}

          {records.length > 0 ? (
            <div className="overflow-x-auto">
              <table className="min-w-full text-left text-sm">
                <thead>
                  <tr className="border-b border-[var(--border-subtle)] text-xs uppercase text-[var(--muted-foreground)]">
                    <th className="whitespace-nowrap px-3 py-3 font-semibold">Дата</th>
                    <th className="whitespace-nowrap px-3 py-3 font-semibold">День</th>
                    <th className="whitespace-nowrap px-3 py-3 font-semibold">Приход</th>
                    <th className="whitespace-nowrap px-3 py-3 font-semibold">Уход</th>
                    <th className="whitespace-nowrap px-3 py-3 font-semibold">Часы</th>
                    <th className="min-w-48 px-3 py-3 font-semibold">Статусы</th>
                  </tr>
                </thead>
                <tbody>
                  {records.map((record, index) => {
                    const labels = issueLabels(record);
                    return (
                      <tr key={`${record.date || "record"}-${index}`} className="border-b border-[var(--border-subtle)] last:border-0">
                        <td className="whitespace-nowrap px-3 py-3 text-[var(--foreground)]">{record.date || "Нет даты"}</td>
                        <td className="whitespace-nowrap px-3 py-3">
                          <span className={`rounded-lg px-2 py-1 text-xs font-medium ${
                            record.is_workday
                              ? "bg-emerald-500/10 text-emerald-300"
                              : "bg-slate-500/10 text-slate-300"
                          }`}>
                            {record.is_workday ? "Рабочий" : "Нерабочий"}
                          </span>
                        </td>
                        <td className="whitespace-nowrap px-3 py-3 text-[var(--foreground)]">{formatTime(record.arrival_time)}</td>
                        <td className="whitespace-nowrap px-3 py-3 text-[var(--foreground)]">{formatTime(record.departure_time)}</td>
                        <td className="whitespace-nowrap px-3 py-3 text-[var(--foreground)]">
                          {formatHours(record.work_hours)}
                          {record.expected_hours !== undefined ? (
                            <span className="app-text-muted"> / {formatHours(record.expected_hours)}</span>
                          ) : null}
                        </td>
                        <td className="px-3 py-3">
                          {labels.length > 0 ? (
                            <div className="flex flex-wrap gap-1.5">
                              {labels.map((label) => (
                                <span key={label} className="rounded-lg bg-amber-500/10 px-2 py-1 text-xs font-medium text-amber-300">
                                  {label}
                                </span>
                              ))}
                            </div>
                          ) : (
                            <span className="app-text-muted text-xs">Нет</span>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          ) : null}
        </section>
      </div>
    </AppShell>
  );
}
