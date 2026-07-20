"use client";

import { Loader2, Search } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";

import type {
  PayrollPeriodTable,
  PayrollPeriodTableRow,
  PayrollPeriodTableStatus,
} from "@/lib/api/finance";
import { formatPayrollMoney } from "@/lib/payroll";
import { getPayrollAdminError } from "@/lib/payroll-admin";

const statusMeta: Record<PayrollPeriodTableStatus, { label: string; className: string }> = {
  calculated: { label: "Рассчитано", className: "app-feedback-success" },
  ready: { label: "Готово", className: "app-selected" },
  draft: { label: "Есть черновики", className: "app-feedback-warning" },
  incomplete: { label: "Не заполнено", className: "app-feedback-danger" },
};

const kindLabels = {
  earning: "Начисление",
  adjustment_credit: "Корректировка +",
  adjustment_debit: "Корректировка −",
  deduction: "Удержание",
  payment: "Выплата",
};

const headerCellClass = "app-surface-muted overflow-hidden border-b border-r border-[var(--border-subtle)] px-2 py-2.5 text-left text-[10px] font-semibold text-[var(--muted-foreground)]";
const bodyCellClass = "overflow-hidden whitespace-normal border-b border-r border-[var(--border-subtle)] px-1.5 py-2 text-right text-[11px] leading-tight text-[var(--foreground)] tabular-nums";

function formatPoints(value: string | null): string {
  if (value == null || value === "") return "—";
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) return value;
  return numeric.toLocaleString("ru-RU", { maximumFractionDigits: 4 });
}

function formatMoney(value: string | null, currency: string): string {
  return value == null
    ? "—"
    : formatPayrollMoney(value, currency).replace(/[\u00a0\u202f]/g, " ");
}

function CalculatedMoney({ value, currency, preliminary }: { value: string | null; currency: string; preliminary: boolean }) {
  return (
    <span
      className="inline-block max-w-full"
      title={preliminary ? "Предварительный расчёт по текущим данным" : undefined}
    >
      {formatMoney(value, currency)}
    </span>
  );
}

function editableNumber(value: string | null): string {
  if (value == null || value === "") return "";
  const numeric = Number(value);
  return Number.isFinite(numeric) ? String(numeric) : value;
}

function sameNumber(left: string, right: string): boolean {
  if (!left.trim() && !right.trim()) return true;
  const leftNumber = Number(left.replace(",", "."));
  const rightNumber = Number(right.replace(",", "."));
  return Number.isFinite(leftNumber) && Number.isFinite(rightNumber) && leftNumber === rightNumber;
}

function InlineEditableCell({ value, formattedValue, onSave, label, automatic = false }: { value: string | null; formattedValue: string; onSave?: (value: string) => Promise<void>; label: string; automatic?: boolean }) {
  const original = editableNumber(value);
  const [draft, setDraft] = useState(original);
  const [pending, setPending] = useState(false);
  const [cellError, setCellError] = useState<string | null>(null);
  const cancelledRef = useRef(false);

  useEffect(() => {
    if (!pending) setDraft(editableNumber(value));
  }, [pending, value]);

  if (!onSave) return <td className={`${bodyCellClass} ${automatic ? "text-[var(--muted-foreground)]" : ""}`}>{formattedValue}</td>;

  const commit = async () => {
    if (cancelledRef.current) {
      cancelledRef.current = false;
      return;
    }
    if (sameNumber(draft, original)) return;
    setPending(true);
    setCellError(null);
    try {
      await onSave(draft.trim().replace(",", "."));
    } catch (error) {
      setDraft(original);
      setCellError(getPayrollAdminError(error, "Не удалось сохранить ячейку."));
    } finally {
      setPending(false);
    }
  };

  return (
    <td className={`${bodyCellClass} p-0`}>
      <label className="relative block min-h-10 w-full max-w-full overflow-hidden">
        <input
          className={`min-h-10 w-full min-w-0 max-w-full bg-transparent px-1.5 py-2 text-right text-[11px] tabular-nums outline-none transition-colors placeholder:text-[var(--muted-foreground)] hover:bg-[var(--surface-tertiary)] focus:bg-[var(--surface-tertiary)] focus:text-[var(--foreground)] focus:ring-2 focus:ring-inset ${automatic ? "text-[var(--muted-foreground)]" : "text-[var(--foreground)]"} ${cellError ? "ring-2 ring-inset ring-red-500/70" : "focus:ring-[var(--accent-primary)]"}`}
          inputMode="decimal"
          size={1}
          value={draft}
          placeholder="—"
          disabled={pending}
          aria-label={label}
          aria-invalid={Boolean(cellError)}
          title={cellError || `${label}. Enter или выход из ячейки — сохранить, Esc — отменить.`}
          onChange={(event) => setDraft(event.target.value)}
          onBlur={() => void commit()}
          onKeyDown={(event) => {
            if (event.key === "Enter") event.currentTarget.blur();
            if (event.key === "Escape") {
              cancelledRef.current = true;
              setDraft(original);
              event.currentTarget.blur();
            }
          }}
        />
        {pending ? <Loader2 className="app-accent-text pointer-events-none absolute left-2 top-1/2 -translate-y-1/2 animate-spin" size={11} /> : null}
      </label>
    </td>
  );
}

function sumRows(rows: PayrollPeriodTableRow[], value: (row: PayrollPeriodTableRow) => string | null): string | null {
  let hasValue = false;
  const total = rows.reduce((sum, row) => {
    const raw = value(row);
    if (raw == null || raw === "") return sum;
    const numeric = Number(raw);
    if (!Number.isFinite(numeric)) return sum;
    hasValue = true;
    return sum + numeric;
  }, 0);
  return hasValue ? String(total) : null;
}

export function PayrollPeriodTableView({
  data,
  loading,
  error,
  search,
  onSearch,
  canEdit = false,
  onSaveRate,
  onSaveWork,
  onSaveComponent,
}: {
  data: PayrollPeriodTable | null;
  loading: boolean;
  error: string | null;
  search: string;
  onSearch: (value: string) => void;
  canEdit?: boolean;
  onSaveRate?: (row: PayrollPeriodTableRow, field: "amount" | "point_rate", value: string) => Promise<void>;
  onSaveWork?: (row: PayrollPeriodTableRow, field: "target_points" | "actual_points", value: string) => Promise<void>;
  onSaveComponent?: (row: PayrollPeriodTableRow, componentCode: string, value: string) => Promise<void>;
}) {
  const rows = useMemo(() => {
    const needle = search.trim().toLocaleLowerCase("ru-RU");
    if (!needle) return data?.rows || [];
    return (data?.rows || []).filter((row) => (
      `${row.employee.display_name} ${row.employee.position || ""} ${row.employee.department || ""}`
        .toLocaleLowerCase("ru-RU")
        .includes(needle)
    ));
  }, [data?.rows, search]);

  if (loading && !data) {
    return <div className="flex min-h-56 items-center justify-center"><Loader2 className="app-accent-text animate-spin" size={24} /></div>;
  }
  if (error) return <div className="app-feedback-danger rounded-xl px-4 py-3 text-sm">{error}</div>;
  if (!data) return null;

  const tableWidth = 1265 + data.component_columns.length * 75;
  const total = (field: keyof PayrollPeriodTableRow) => sumRows(rows, (row) => {
    const value = row[field];
    return typeof value === "string" ? value : null;
  });

  return (
    <div className="min-w-0 max-w-full">
      <div className="mb-3 flex flex-col gap-2 lg:flex-row lg:items-center lg:justify-between">
        <div className="flex flex-wrap gap-2">
          <span className="app-chip inline-flex items-center gap-1.5 rounded-full px-3 py-1.5 text-xs">Сотрудников <span className="app-counter inline-flex h-5 min-w-5 px-1 text-[10px]">{data.summary.employee_count}</span></span>
          <span className="app-chip inline-flex items-center gap-1.5 rounded-full px-3 py-1.5 text-xs">Рассчитано <span className="app-counter inline-flex h-5 min-w-5 px-1 text-[10px]">{data.summary.calculated_count}</span></span>
          <span className="app-chip inline-flex items-center gap-1.5 rounded-full px-3 py-1.5 text-xs">Готово <span className="app-counter inline-flex h-5 min-w-5 px-1 text-[10px]">{data.summary.ready_count}</span></span>
          <span className="app-chip inline-flex items-center gap-1.5 rounded-full px-3 py-1.5 text-xs">Черновики <span className="app-counter inline-flex h-5 min-w-5 px-1 text-[10px]">{data.summary.draft_count}</span></span>
          <span className="app-chip inline-flex items-center gap-1.5 rounded-full px-3 py-1.5 text-xs">Не заполнено <span className="app-counter inline-flex h-5 min-w-5 px-1 text-[10px]">{data.summary.incomplete_count}</span></span>
          {data.summary.preliminary_count ? <span className="app-chip inline-flex items-center gap-1.5 rounded-full px-3 py-1.5 text-xs">Предварительно <span className="app-counter inline-flex h-5 min-w-5 px-1 text-[10px]">{data.summary.preliminary_count}</span></span> : null}
          {data.run ? <span className="app-selected inline-flex items-center rounded-full px-3 py-1.5 text-xs">Ревизия {data.run.revision}</span> : null}
        </div>
        <label className="relative block min-w-0 lg:w-72">
          <Search className="app-text-muted pointer-events-none absolute left-3 top-1/2 -translate-y-1/2" size={15} />
          <input
            className="app-input w-full rounded-lg py-2.5 pl-9 pr-3 text-sm"
            value={search}
            placeholder="Поиск по сотрудникам"
            onChange={(event) => onSearch(event.target.value)}
          />
        </label>
      </div>

      {data.summary.preliminary_count ? (
        <div className="app-feedback-warning mb-3 rounded-lg px-3 py-2.5 text-sm">
          Значения рассчитаны предварительно по текущим данным. Они обновляются после сохранения ячеек и станут официальными после запуска расчёта.
        </div>
      ) : null}

      <div className="app-text-muted mb-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs">
        {canEdit ? <span>Enter или переход в другую ячейку — сохранить, Esc — отменить.</span> : null}
        <span className="inline-flex items-center gap-1.5"><span className="h-2.5 w-2.5 rounded-sm bg-[var(--muted-foreground)]" aria-hidden="true" />Серый текст — заполнено автоматически</span>
      </div>

      <div className="app-table-scroll max-h-[min(70vh,760px)] w-full max-w-full overflow-auto overscroll-contain rounded-xl border border-[var(--border-subtle)]">
        <table className="table-fixed border-separate border-spacing-0" style={{ width: `max(100%, ${tableWidth}px)` }} aria-label="Итоговая таблица расчётного периода">
          <colgroup>
            <col style={{ width: 150 }} />
            <col style={{ width: 75 }} />
            <col style={{ width: 75 }} />
            <col style={{ width: 75 }} />
            <col style={{ width: 55 }} />
            <col style={{ width: 55 }} />
            <col style={{ width: 55 }} />
            <col style={{ width: 75 }} />
            {data.component_columns.map((component) => <col key={component.code} style={{ width: 75 }} />)}
            {Array.from({ length: 7 }, (_, index) => <col key={`total-${index}`} style={{ width: 80 }} />)}
            <col style={{ width: 90 }} />
          </colgroup>
          <thead className="sticky top-0 z-20">
            <tr>
              <th rowSpan={2} className={`${headerCellClass} sticky left-0 z-30 align-middle`}>Сотрудник</th>
              <th colSpan={3} className={`${headerCellClass} text-center uppercase tracking-wide`}>Оклад и баллы</th>
              <th colSpan={4} className={`${headerCellClass} text-center uppercase tracking-wide`}>Выработка</th>
              {data.component_columns.length ? <th colSpan={data.component_columns.length} className={`${headerCellClass} text-center uppercase tracking-wide`}>Начисления и выплаты</th> : null}
              <th colSpan={7} className={`${headerCellClass} text-center uppercase tracking-wide`}>Расчёт</th>
              <th rowSpan={2} className={`${headerCellClass} align-middle`}>Состояние</th>
            </tr>
            <tr>
              <th className={`${headerCellClass} text-right`}>Оклад</th>
              <th className={`${headerCellClass} whitespace-normal text-right`} title="Цена одного балла в пределах нормы: оклад, разделённый на норму баллов">
                <span className="block">Цена балла</span>
                <span className="block">в норме</span>
              </th>
              <th className={`${headerCellClass} whitespace-normal text-right`} title="Цена каждого балла сверх нормы">
                <span className="block">Цена балла</span>
                <span className="block">сверх нормы</span>
              </th>
              <th className={`${headerCellClass} text-right`}>Норма</th>
              <th className={`${headerCellClass} text-right`}>Баллы</th>
              <th className={`${headerCellClass} text-right`}>Отклонение</th>
              <th className={`${headerCellClass} text-right`} title="Доплата за баллы сверх нормы">Доплата</th>
              {data.component_columns.map((component) => (
                <th key={component.code} className={`${headerCellClass} text-right whitespace-normal break-words`} title={`${component.label} · ${kindLabels[component.kind]}`}>
                  {component.label}
                </th>
              ))}
              <th className={`${headerCellClass} text-right`} title="До корректировок">До коррект.</th>
              <th className={`${headerCellClass} text-right`}>Корректировки</th>
              <th className={`${headerCellClass} text-right`}>Начислено</th>
              <th className={`${headerCellClass} text-right`}>Удержано</th>
              <th className={`${headerCellClass} text-right`} title="После удержаний">После удерж.</th>
              <th className={`${headerCellClass} text-right`}>Выплачено</th>
              <th className={`${headerCellClass} text-right`}>К выплате</th>
            </tr>
          </thead>
          <tbody>
            {rows.length ? rows.map((row) => {
              const meta = statusMeta[row.status];
              return (
                <tr key={row.employee.id} className="bg-[var(--surface-primary)] hover:bg-[var(--surface-secondary)]">
                  <td className="sticky left-0 z-10 overflow-hidden border-b border-r border-[var(--border-subtle)] bg-[var(--surface-primary)] px-2 py-2.5">
                    <p className="max-w-full truncate text-xs font-semibold text-[var(--foreground)]" title={row.employee.display_name}>{row.employee.display_name}</p>
                    <p className="app-text-muted mt-0.5 max-w-full truncate text-[10px]">{row.employee.position || row.employee.department || "Сотрудник"}{row.employee.is_active ? "" : " · неактивен"}</p>
                  </td>
                  <InlineEditableCell value={row.rate_amount} formattedValue={formatMoney(row.rate_amount, data.currency)} onSave={canEdit && onSaveRate ? (value) => onSaveRate(row, "amount", value) : undefined} label={`Оклад: ${row.employee.display_name}`} />
                  <InlineEditableCell value={row.in_norm_point_rate} formattedValue={formatMoney(row.in_norm_point_rate, data.currency)} label={`Цена балла в пределах нормы: ${row.employee.display_name}`} automatic />
                  <InlineEditableCell value={row.point_rate} formattedValue={formatMoney(row.point_rate, data.currency)} onSave={canEdit && onSaveRate ? (value) => onSaveRate(row, "point_rate", value) : undefined} label={`Цена балла сверх нормы: ${row.employee.display_name}`} />
                  <InlineEditableCell value={row.target_points} formattedValue={formatPoints(row.target_points)} onSave={canEdit && onSaveWork ? (value) => onSaveWork(row, "target_points", value) : undefined} label={`Норма: ${row.employee.display_name}`} automatic={row.target_points_automatic} />
                  <InlineEditableCell value={row.actual_points} formattedValue={formatPoints(row.actual_points)} onSave={canEdit && onSaveWork ? (value) => onSaveWork(row, "actual_points", value) : undefined} label={`Баллы: ${row.employee.display_name}`} />
                  <td className={bodyCellClass}>{formatPoints(row.point_delta)}</td>
                  <td className={bodyCellClass}><CalculatedMoney value={row.point_amount} currency={data.currency} preliminary={row.totals_preliminary} /></td>
                  {data.component_columns.map((component) => (
                    <InlineEditableCell key={component.code} value={row.component_amounts[component.code] || null} formattedValue={formatMoney(row.component_amounts[component.code] || null, data.currency)} onSave={canEdit && onSaveComponent ? (value) => onSaveComponent(row, component.code, value) : undefined} label={`${component.label}: ${row.employee.display_name}`} />
                  ))}
                  <td className={bodyCellClass}><CalculatedMoney value={row.gross_before_adjustments} currency={data.currency} preliminary={row.totals_preliminary} /></td>
                  <td className={bodyCellClass}><CalculatedMoney value={row.adjustment_total} currency={data.currency} preliminary={row.totals_preliminary} /></td>
                  <td className={`${bodyCellClass} font-semibold`}><CalculatedMoney value={row.gross_total} currency={data.currency} preliminary={row.totals_preliminary} /></td>
                  <td className={bodyCellClass}><CalculatedMoney value={row.deduction_total} currency={data.currency} preliminary={row.totals_preliminary} /></td>
                  <td className={bodyCellClass}><CalculatedMoney value={row.net_pay} currency={data.currency} preliminary={row.totals_preliminary} /></td>
                  <td className={bodyCellClass}><CalculatedMoney value={row.payment_total} currency={data.currency} preliminary={row.totals_preliminary} /></td>
                  <td className={`${bodyCellClass} font-semibold`}><CalculatedMoney value={row.payable} currency={data.currency} preliminary={row.totals_preliminary} /></td>
                  <td className="overflow-hidden border-b border-r border-[var(--border-subtle)] px-1 py-2 text-center"><span className={`app-status-pill px-2 text-[10px] ${meta.className}`}>{meta.label}</span></td>
                </tr>
              );
            }) : (
              <tr><td colSpan={16 + data.component_columns.length} className="app-text-muted px-4 py-10 text-center text-sm">Сотрудники не найдены.</td></tr>
            )}
          </tbody>
          {rows.length ? (
            <tfoot>
              <tr className="app-surface-muted font-semibold">
                <td className="sticky left-0 z-10 border-r border-[var(--border-subtle)] bg-[var(--surface-secondary)] px-3 py-3 text-xs text-[var(--foreground)]">Итого · {rows.length}</td>
                <td className={bodyCellClass}>{formatMoney(total("rate_amount"), data.currency)}</td>
                <td className={bodyCellClass}>—</td>
                <td className={bodyCellClass}>—</td>
                <td className={bodyCellClass}>{formatPoints(total("target_points"))}</td>
                <td className={bodyCellClass}>{formatPoints(total("actual_points"))}</td>
                <td className={bodyCellClass}>{formatPoints(total("point_delta"))}</td>
                <td className={bodyCellClass}>{formatMoney(total("point_amount"), data.currency)}</td>
                {data.component_columns.map((component) => (
                  <td key={component.code} className={bodyCellClass}>{formatMoney(sumRows(rows, (row) => row.component_amounts[component.code] || null), data.currency)}</td>
                ))}
                <td className={bodyCellClass}>{formatMoney(total("gross_before_adjustments"), data.currency)}</td>
                <td className={bodyCellClass}>{formatMoney(total("adjustment_total"), data.currency)}</td>
                <td className={bodyCellClass}>{formatMoney(total("gross_total"), data.currency)}</td>
                <td className={bodyCellClass}>{formatMoney(total("deduction_total"), data.currency)}</td>
                <td className={bodyCellClass}>{formatMoney(total("net_pay"), data.currency)}</td>
                <td className={bodyCellClass}>{formatMoney(total("payment_total"), data.currency)}</td>
                <td className={bodyCellClass}>{formatMoney(total("payable"), data.currency)}</td>
                <td className="border-r border-[var(--border-subtle)] px-3 py-3" />
              </tr>
            </tfoot>
          ) : null}
        </table>
      </div>
    </div>
  );
}
