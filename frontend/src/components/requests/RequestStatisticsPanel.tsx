"use client";

import { apiClient } from "@/lib/api";
import { displayUserName } from "@/lib/shared";
import { resolveMediaUrl } from "@/lib/url";
import type { RequestEmployeeStatistics, User } from "@/types/api";
import { ChevronDown, Search } from "lucide-react";
import { useEffect, useState } from "react";

const statsPeriods = [
  { value: "all", label: "За всё время" },
  { value: "year", label: "За год" },
  { value: "month", label: "За месяц" },
] as const;

type StatsPeriod = (typeof statsPeriods)[number]["value"];

type RequestStatisticsPanelProps = {
  canView: boolean;
  employees: User[];
};

export function RequestStatisticsPanel({
  canView,
  employees,
}: RequestStatisticsPanelProps) {
  const [open, setOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [employeeId, setEmployeeId] = useState<number | null>(null);
  const [period, setPeriod] = useState<StatsPeriod>("all");
  const [stats, setStats] = useState<RequestEmployeeStatistics | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!canView || !open || !employeeId) {
      return;
    }

    let cancelled = false;
    setLoading(true);
    setError(null);

    apiClient.request<RequestEmployeeStatistics>(
      `/api/v1/requests/statistics/?employee_id=${employeeId}&period=${period}`
    )
      .then((response) => {
        if (!cancelled) {
          setStats(response);
        }
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Не удалось загрузить статистику.");
        }
      })
      .finally(() => {
        if (!cancelled) {
          setLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [canView, employeeId, open, period]);

  if (!canView) return null;

  const filteredEmployees = employees.filter((employee) => {
    const normalizedQuery = searchQuery.trim().toLowerCase();
    if (!normalizedQuery) return true;

    const haystack = [
      displayUserName(employee),
      employee.email || "",
    ]
      .join(" ")
      .toLowerCase();

    return haystack.includes(normalizedQuery);
  });

  const statsItems = stats ? [
    { label: "Всего заявлений", value: stats.total_submitted_requests },
    { label: "Больничных", value: stats.sick_leave_requests_count },
    { label: "Отгулов", value: stats.day_off_requests_count },
    { label: "Дней на больничном", value: stats.sick_leave_days },
    { label: "Дней на отгулах", value: stats.day_off_days },
    { label: "Оплачиваемый отпуск, дней", value: stats.paid_vacation_days },
    { label: "За свой счёт, дней", value: stats.unpaid_vacation_days },
  ] : [];

  return (
    <div className="app-surface overflow-hidden rounded-2xl">
      <button
        type="button"
        onClick={() => setOpen((current) => !current)}
        className="flex w-full items-center justify-between gap-3 px-4 py-3 text-left transition hover:bg-[var(--surface-secondary)]"
        aria-expanded={open}
      >
        <div className="min-w-0">
          <p className="text-sm font-semibold text-[var(--foreground)]">Статистика по заявлениям</p>
          <p className="app-text-muted mt-1 text-xs">
            Выбор сотрудника и периода для сводной статистики
          </p>
        </div>
        <ChevronDown
          size={18}
          className={`shrink-0 text-[var(--foreground-muted)] transition-transform ${open ? "rotate-180" : ""}`}
        />
      </button>

      {open ? (
        <div className="border-t border-[var(--border-subtle)] px-4 py-4">
          <div className="app-surface-muted rounded-2xl p-4">
            <div className="relative">
              <Search
                size={16}
                className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 app-text-muted"
              />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Выберите сотрудника для статистики"
                className="app-input w-full rounded-xl py-2.5 pl-10 pr-3 text-sm"
              />
            </div>

            <div className="mt-3 flex items-center justify-between px-1 text-xs">
              <span className="app-text-muted">Найдено: {filteredEmployees.length}</span>
              <span className="app-accent-text font-medium">Выбрано: {employeeId ? 1 : 0}</span>
            </div>

            <div className="app-surface mt-3 max-h-72 space-y-2 overflow-y-auto rounded-2xl p-2">
              {filteredEmployees.length > 0 ? (
                filteredEmployees.map((employee) => {
                  const isSelected = employee.id === employeeId;
                  const employeeName = displayUserName(employee);
                  return (
                    <button
                      key={employee.id}
                      type="button"
                      onClick={() => {
                        setEmployeeId((current) => current === employee.id ? null : employee.id);
                        setStats(null);
                        setError(null);
                      }}
                      className={`flex w-full items-center gap-3 rounded-xl px-3 py-3 text-left transition ${
                        isSelected
                          ? "app-selected"
                          : "app-surface-muted hover:bg-[var(--surface-tertiary)]"
                      }`}
                    >
                      {employee.avatar ? (
                        <img
                          src={resolveMediaUrl(employee.avatar)}
                          alt={employeeName}
                          className="app-avatar-frame h-10 w-10 shrink-0 rounded-full object-cover"
                        />
                      ) : (
                        <div className="app-avatar-fallback flex h-10 w-10 shrink-0 items-center justify-center rounded-full">
                          <span className="text-sm font-semibold">
                            {employee.first_name?.[0] || employee.last_name?.[0] || "?"}
                          </span>
                        </div>
                      )}

                      <div className="min-w-0 flex-1">
                        <div className="truncate text-sm font-medium text-[var(--foreground)]">
                          {employeeName}
                        </div>
                        <div className="truncate text-xs text-[var(--muted-foreground)]">
                          {employee.email || "Почта не указана"}
                        </div>
                      </div>

                      <div
                        className={`flex h-6 w-6 shrink-0 items-center justify-center rounded-full border transition ${
                          isSelected
                            ? "border-[color:var(--accent-primary)] bg-[var(--accent-primary)] text-white"
                            : "border-[var(--border-strong)] text-transparent"
                        }`}
                      >
                        <div className="h-2.5 w-2.5 rounded-full bg-current" />
                      </div>
                    </button>
                  );
                })
              ) : (
                <p className="app-text-muted px-2 py-3 text-sm">Сотрудники не найдены</p>
              )}
            </div>

            <div className="mt-4 flex flex-wrap gap-2">
              {statsPeriods.map((periodOption) => {
                const isActive = period === periodOption.value;
                return (
                  <button
                    key={periodOption.value}
                    type="button"
                    onClick={() => {
                      if (period === periodOption.value) return;
                      setPeriod(periodOption.value);
                      setStats(null);
                      setError(null);
                    }}
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
          </div>

          {!employeeId ? (
            <p className="app-text-muted mt-4 text-sm">
              Выберите сотрудника, чтобы посмотреть статистику.
            </p>
          ) : loading || (!stats && !error) ? (
            <div className="app-text-muted mt-4 flex items-center gap-2 text-sm">
              <div className="h-4 w-4 animate-spin rounded-full border-2 border-[var(--border-strong)] border-t-[var(--accent-primary)]" />
              <span>Загрузка статистики...</span>
            </div>
          ) : error ? (
            <div className="app-feedback-danger mt-4 rounded-xl px-3 py-2 text-sm">
              {error}
            </div>
          ) : (
            <div className="mt-4">
              <p className="app-text-muted mb-3 text-xs">
                {period === "all"
                  ? "Период: за всё время"
                  : period === "year"
                    ? "Период: текущий календарный год"
                    : "Период: текущий календарный месяц"}
              </p>
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4">
                {statsItems.map((item) => (
                  <div
                    key={item.label}
                    className="rounded-xl border border-[var(--border-subtle)] bg-[var(--surface-primary)] px-3 py-3"
                  >
                    <p className="app-text-muted text-xs">{item.label}</p>
                    <p className="mt-2 text-2xl font-semibold text-[var(--foreground)]">{item.value}</p>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      ) : null}
    </div>
  );
}
