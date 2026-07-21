"use client";

import { CalendarDays, Loader2, RefreshCw } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";

import { Modal } from "@/components/ui";
import { apiClient } from "@/lib/api";
import type {
  PayrollPointBreakdown,
  PayrollPointBreakdownDay,
} from "@/lib/api/finance";
import { getPayrollAdminError } from "@/lib/payroll-admin";
import {
  compareDailyPayrollProjection,
  type PayrollProjectionDifference,
} from "@/lib/payroll-projection";

type PayrollPointBreakdownModalProps = {
  periodId: number;
  employeeId: number;
  employeeName: string;
  onClose: () => void;
};

type PointRow = {
  id: "attendance_points" | "personnel_points" | "work_points";
  label: string;
};

const pointRows: PointRow[] = [
  { id: "attendance_points", label: "Баллы по посещаемости" },
  { id: "personnel_points", label: "Баллы по кадровым событиям" },
  { id: "work_points", label: "Баллы по выработке" },
];

const differenceClasses: Record<PayrollProjectionDifference["color"], string> = {
  green: "bg-emerald-500/15 text-emerald-300",
  orange: "bg-orange-500/15 text-orange-300",
  red: "bg-red-500/15 text-red-300",
};

function formatPoints(value: string | null): string {
  if (value == null || value === "") return "—";
  const numeric = Number(value);
  return Number.isFinite(numeric)
    ? numeric.toLocaleString("ru-RU", { maximumFractionDigits: 4 })
    : value;
}

function dateParts(value: string): { date: string; weekday: string } {
  const parsed = new Date(`${value}T00:00:00`);
  return {
    date: parsed.toLocaleDateString("ru-RU", { day: "2-digit", month: "2-digit" }),
    weekday: parsed.toLocaleDateString("ru-RU", { weekday: "short" }),
  };
}

function differenceTitle(
  row: PointRow,
  day: PayrollPointBreakdownDay,
  difference: PayrollProjectionDifference | null,
): string {
  if (!difference) return `${row.label}: ${formatPoints(day[row.id])}`;
  const direction = difference.direction === "higher" ? "выше" : "ниже";
  const amount = difference.percentage == null
    ? "выработка равна нулю"
    : `на ${difference.percentage.toLocaleString("ru-RU", { maximumFractionDigits: 1 })}%`;
  return `${row.label}: ${direction} выработки ${amount}`;
}

export function PayrollPointBreakdownModal({
  periodId,
  employeeId,
  employeeName,
  onClose,
}: PayrollPointBreakdownModalProps) {
  const [data, setData] = useState<PayrollPointBreakdown | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const payload = await apiClient.getPayrollAdminPointBreakdown(periodId, employeeId);
      setData(payload);
    } catch (loadError) {
      setError(getPayrollAdminError(loadError, "Не удалось загрузить дневную детализацию баллов."));
    } finally {
      setLoading(false);
    }
  }, [employeeId, periodId]);

  useEffect(() => {
    let active = true;
    setData(null);
    setLoading(true);
    setError(null);
    apiClient
      .getPayrollAdminPointBreakdown(periodId, employeeId)
      .then((payload) => {
        if (active) setData(payload);
      })
      .catch((loadError: unknown) => {
        if (active) {
          setError(getPayrollAdminError(loadError, "Не удалось загрузить дневную детализацию баллов."));
        }
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [employeeId, periodId]);

  const tableWidth = useMemo(
    () => 190 + ((data?.dates.length || 0) + (data?.undated_work_points ? 1 : 0)) * 68,
    [data?.dates.length, data?.undated_work_points],
  );

  return (
    <Modal
      isOpen
      onClose={onClose}
      title={`Детализация баллов · ${employeeName}`}
      size="full"
      closeOnClickOutside
    >
      {loading ? (
        <div className="flex min-h-72 items-center justify-center gap-2 text-sm text-[var(--muted-foreground)]">
          <Loader2 className="app-accent-text animate-spin" size={20} />
          Загружаем данные по дням…
        </div>
      ) : error || !data ? (
        <div className="py-5">
          <div className="app-feedback-danger rounded-xl px-4 py-3 text-sm">
            {error || "Детализация недоступна."}
          </div>
          <button
            type="button"
            className="app-action-secondary mt-3 inline-flex items-center gap-2 rounded-lg px-4 py-2.5 text-sm font-medium"
            onClick={() => void load()}
          >
            <RefreshCw size={15} /> Повторить
          </button>
        </div>
      ) : (
        <div className="space-y-4">
          <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
            <div className="min-w-0">
              <p className="text-sm font-semibold text-[var(--foreground)]">{data.period.name}</p>
              <p className="app-text-muted mt-1 text-xs">
                {new Date(`${data.period.date_from}T00:00:00`).toLocaleDateString("ru-RU")} — {new Date(`${data.period.date_to}T00:00:00`).toLocaleDateString("ru-RU")}
              </p>
            </div>
            <div className="app-surface-muted flex shrink-0 items-start gap-2 rounded-xl px-3 py-2.5 text-xs">
              <CalendarDays className="app-accent-text mt-0.5 shrink-0" size={15} />
              <div>
                <p className="text-[var(--foreground)]">
                  Норма за период: <b>{formatPoints(data.target_points)}</b> · выработка: <b>{formatPoints(data.actual_points)}</b>
                </p>
                <p className="app-text-muted mt-1">
                  {data.work_points_mode === "daily_entries"
                    ? "Выработка показана по фактическим ежедневным записям."
                    : data.undated_work_points
                      ? "Выработка введена отдельной суммой без привязки к дате."
                      : "Дневных записей выработки нет."}
                </p>
                {data.undated_work_points ? (
                  <p className="app-text-muted mt-1">
                    Не привязанная к дням сумма показана отдельной колонкой и не распределяется по периоду.
                  </p>
                ) : null}
              </div>
            </div>
          </div>

          <div className="app-text-muted flex flex-wrap items-center gap-x-4 gap-y-1 text-xs">
            <span>Подсвечивается любое дневное расхождение с выработкой:</span>
            <span className="inline-flex items-center gap-1.5"><span className="h-2.5 w-2.5 rounded-sm bg-emerald-400" />выше — зелёный</span>
            <span className="inline-flex items-center gap-1.5"><span className="h-2.5 w-2.5 rounded-sm bg-orange-400" />ниже до 25% — оранжевый</span>
            <span className="inline-flex items-center gap-1.5"><span className="h-2.5 w-2.5 rounded-sm bg-red-400" />ниже больше 25% — красный</span>
          </div>

          <div className="app-table-scroll max-h-[min(65vh,620px)] w-full overflow-auto rounded-xl border border-[var(--border-subtle)]">
            <table
              className="table-fixed border-separate border-spacing-0"
              style={{ width: `max(100%, ${tableWidth}px)` }}
              aria-label={`Дневная детализация баллов: ${data.employee.display_name}`}
            >
              <colgroup>
                <col style={{ width: 190 }} />
                {data.dates.map((day) => <col key={day.date} style={{ width: 68 }} />)}
                {data.undated_work_points ? <col style={{ width: 68 }} /> : null}
              </colgroup>
              <thead className="sticky top-0 z-20">
                <tr>
                  <th className="app-surface-muted sticky left-0 z-30 border-b border-r border-[var(--border-subtle)] px-3 py-2.5 text-left text-[10px] font-semibold text-[var(--muted-foreground)]">
                    Источник баллов
                  </th>
                  {data.dates.map((day) => {
                    const parts = dateParts(day.date);
                    return (
                      <th
                        key={day.date}
                        className={`app-surface-muted border-b border-r border-[var(--border-subtle)] px-1 py-2 text-center text-[10px] font-semibold ${day.is_workday ? "text-[var(--muted-foreground)]" : "opacity-55 text-[var(--muted-foreground)]"}`}
                        title={day.is_workday ? "Плановый рабочий день" : "Нерабочий день"}
                      >
                        <span className="block tabular-nums">{parts.date}</span>
                        <span className="mt-0.5 block font-normal uppercase">{parts.weekday}</span>
                      </th>
                    );
                  })}
                  {data.undated_work_points ? (
                    <th
                      className="app-surface-muted border-b border-r border-[var(--border-subtle)] px-1 py-2 text-center text-[10px] font-semibold text-[var(--muted-foreground)]"
                      title="Выработка, введённая общей суммой без дневной записи внутри периода"
                    >
                      <span className="block">Вне</span>
                      <span className="mt-0.5 block font-normal">периода</span>
                    </th>
                  ) : null}
                </tr>
              </thead>
              <tbody>
                {pointRows.map((row) => (
                  <tr key={row.id} className="bg-[var(--surface-primary)]">
                    <th className="sticky left-0 z-10 border-b border-r border-[var(--border-subtle)] bg-[var(--surface-primary)] px-3 py-3 text-left text-xs font-semibold text-[var(--foreground)]">
                      {row.label}
                    </th>
                    {data.dates.map((day) => {
                      const difference = row.id === "work_points"
                        ? null
                        : compareDailyPayrollProjection(day[row.id], day.work_points);
                      return (
                        <td
                          key={day.date}
                          className={`border-b border-r border-[var(--border-subtle)] px-1 py-3 text-center text-[11px] tabular-nums ${difference ? differenceClasses[difference.color] : day.is_workday ? "text-[var(--foreground)]" : "bg-[var(--surface-secondary)] text-[var(--muted-foreground)]"}`}
                          title={differenceTitle(row, day, difference)}
                        >
                          {formatPoints(day[row.id])}
                        </td>
                      );
                    })}
                    {data.undated_work_points ? (
                      <td
                        className="app-surface-muted border-b border-r border-[var(--border-subtle)] px-1 py-3 text-center text-[11px] font-medium text-[var(--foreground)] tabular-nums"
                        title={row.id === "work_points" ? "Выработка без привязки к дате внутри периода" : undefined}
                      >
                        {row.id === "work_points" ? formatPoints(data.undated_work_points) : "—"}
                      </td>
                    ) : null}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </Modal>
  );
}
