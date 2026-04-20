"use client";

import { SearchableSelectSingle } from "@/components/shared/SearchableSelect";
import { apiClient } from "@/lib/api";
import { displayUserName } from "@/lib/shared";
import type { RequestEmployeeStatistics, User } from "@/types/api";
import { ChevronDown } from "lucide-react";
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

    apiClient.getEmployeeRequestStatistics(employeeId, period)
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

  const employeeOptions = employees.map((employee) => ({
    id: employee.id,
    name: displayUserName(employee),
  }));

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
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-[minmax(0,1fr)_auto] lg:items-end">
            <SearchableSelectSingle
              label="Сотрудник"
              items={employeeOptions}
              selectedId={employeeId}
              onSelect={(id) => {
                setEmployeeId(id);
                setStats(null);
                setError(null);
              }}
              placeholder="Выберите сотрудника"
            />

            <div className="flex flex-wrap gap-2">
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
