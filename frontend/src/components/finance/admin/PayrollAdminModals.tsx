"use client";

import { AlertTriangle, Check, Loader2, Search } from "lucide-react";
import { useMemo, useState, type FormEvent } from "react";

import { Modal } from "@/components/ui";
import type {
  PayrollAdminEmployee,
  PayrollAdminInputLine,
  PayrollAdminPayRate,
  PayrollAdminPeriod,
  PayrollAdminWorkRecord,
  PayrollBulkPayRateResult,
  PayrollBulkPayRateWrite,
  PayrollBulkPointRateMode,
  PayrollBulkPointRateResult,
  PayrollBulkPointRateWrite,
  PayrollComponent,
  PayrollInputLineWrite,
  PayrollPayRateWrite,
  PayrollPeriodWrite,
  PayrollWorkRecordWrite,
} from "@/lib/api/finance";
import {
  getDefaultPayrollPeriodForm,
  getPayrollAdminError,
  isPayrollAdminStaleConflict,
} from "@/lib/payroll-admin";

const inputClass = "app-input w-full rounded-lg px-3 py-2.5 text-sm";
const selectClass = "app-select w-full rounded-lg px-3 py-2.5 text-sm";

function ModalActions({
  busy,
  disabled = false,
  onClose,
  submitLabel,
}: {
  busy: boolean;
  disabled?: boolean;
  onClose: () => void;
  submitLabel: string;
}) {
  return (
    <div className="mt-5 flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
      <button
        type="button"
        className="app-action-secondary rounded-lg px-4 py-2.5 text-sm font-medium"
        disabled={busy}
        onClick={onClose}
      >
        Отмена
      </button>
      <button
        type="submit"
        className="app-action-primary inline-flex items-center justify-center gap-2 rounded-lg px-4 py-2.5 text-sm font-semibold disabled:opacity-60"
        disabled={busy || disabled}
      >
        {busy ? <Loader2 className="animate-spin" size={16} /> : <Check size={16} />}
        {submitLabel}
      </button>
    </div>
  );
}

function FormError({ message }: { message: string | null }) {
  if (!message) return null;
  return <div className="app-feedback-danger mt-4 rounded-lg px-3 py-2.5 text-sm">{message}</div>;
}

async function submitModalForm(
  operation: () => Promise<unknown>,
  options: {
    fallback: string;
    setBusy: (busy: boolean) => void;
    setError: (message: string | null) => void;
    onSaved: () => void | Promise<void>;
    onStale?: () => void | Promise<void>;
  },
) {
  options.setBusy(true);
  options.setError(null);
  try {
    await operation();
    await options.onSaved();
  } catch (error) {
    if (isPayrollAdminStaleConflict(error) && options.onStale) {
      await options.onStale();
      return;
    }
    options.setError(getPayrollAdminError(error, options.fallback));
  } finally {
    options.setBusy(false);
  }
}

export function PayrollPeriodFormModal({
  isOpen,
  period,
  periods,
  onClose,
  onSubmit,
  onSaved,
  onStale,
}: {
  isOpen: boolean;
  period?: PayrollAdminPeriod | null;
  periods: PayrollAdminPeriod[];
  onClose: () => void;
  onSubmit: (payload: PayrollPeriodWrite) => Promise<unknown>;
  onSaved: () => void | Promise<void>;
  onStale?: () => void | Promise<void>;
}) {
  const [form, setForm] = useState<PayrollPeriodWrite>(() => period ? {
    code: period.code,
    name: period.name,
    date_from: period.date_from,
    date_to: period.date_to,
    pay_date: period.pay_date,
    currency: period.currency,
  } : getDefaultPayrollPeriodForm(periods));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = (event: FormEvent) => {
    event.preventDefault();
    void submitModalForm(() => onSubmit(form), {
      fallback: "Не удалось сохранить расчётный период.",
      setBusy,
      setError,
      onSaved,
      onStale,
    });
  };

  return (
    <Modal isOpen={isOpen} onClose={onClose} title={period ? "Параметры периода" : "Новый расчётный период"} size="md">
      <form onSubmit={submit}>
        <p className="app-text-muted mb-4 text-sm leading-relaxed">
          Период задаёт границы расчёта и дату, которую сотрудники увидят в листке.
        </p>
        <div className="grid gap-4 sm:grid-cols-2">
          <label>
            <span className="app-field-label">Название</span>
            <input className={inputClass} value={form.name} placeholder="Июль 2026" required onChange={(event) => setForm({ ...form, name: event.target.value })} />
          </label>
          <label>
            <span className="app-field-label">Код периода</span>
            <input className={inputClass} value={form.code} placeholder="2026-07" required disabled={Boolean(period)} onChange={(event) => setForm({ ...form, code: event.target.value })} />
          </label>
          <label>
            <span className="app-field-label">Начало</span>
            <input type="date" className={inputClass} value={form.date_from} required onChange={(event) => setForm({ ...form, date_from: event.target.value })} />
          </label>
          <label>
            <span className="app-field-label">Окончание</span>
            <input type="date" className={inputClass} value={form.date_to} required onChange={(event) => setForm({ ...form, date_to: event.target.value })} />
          </label>
          <label>
            <span className="app-field-label">Дата выплаты</span>
            <input type="date" className={inputClass} value={form.pay_date || ""} onChange={(event) => setForm({ ...form, pay_date: event.target.value || null })} />
          </label>
          <label>
            <span className="app-field-label">Валюта</span>
            <select className={selectClass} value={form.currency} onChange={(event) => setForm({ ...form, currency: event.target.value })}>
              <option value="RUB">RUB — российский рубль</option>
            </select>
          </label>
        </div>
        <FormError message={error} />
        <ModalActions busy={busy} onClose={onClose} submitLabel={period ? "Сохранить" : "Создать период"} />
      </form>
    </Modal>
  );
}

export function PayrollRateFormModal({
  isOpen,
  period,
  employees,
  rate,
  onClose,
  onSubmit,
  onSaved,
  onStale,
}: {
  isOpen: boolean;
  period: PayrollAdminPeriod;
  employees: PayrollAdminEmployee[];
  rate?: PayrollAdminPayRate | null;
  onClose: () => void;
  onSubmit: (payload: PayrollPayRateWrite) => Promise<unknown>;
  onSaved: () => void | Promise<void>;
  onStale?: () => void | Promise<void>;
}) {
  const [employeeId, setEmployeeId] = useState(() => rate ? String(rate.employee.id) : "");
  const [amount, setAmount] = useState(() => rate?.amount || "");
  const [pointRate, setPointRate] = useState(() => rate?.point_rate || "0");
  const [effectiveFrom, setEffectiveFrom] = useState(() => rate?.effective_from || period.date_from);
  const [reason, setReason] = useState(() => rate?.reason || "");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = (event: FormEvent) => {
    event.preventDefault();
    void submitModalForm(() => onSubmit({
      employee_id: Number(employeeId),
      rate_code: "BASE",
      amount,
      point_rate: pointRate || "0",
      currency: period.currency,
      effective_from: effectiveFrom,
      reason,
    }), {
      fallback: "Не удалось сохранить ставку.",
      setBusy,
      setError,
      onSaved,
      onStale,
    });
  };

  return (
    <Modal isOpen={isOpen} onClose={onClose} title={rate ? "Изменить черновик ставки" : "Новая ставка"} size="md">
      <form onSubmit={submit}>
        <div className="grid gap-4 sm:grid-cols-2">
          <label className="sm:col-span-2">
            <span className="app-field-label">Сотрудник</span>
            <select className={selectClass} required value={employeeId} disabled={Boolean(rate)} onChange={(event) => setEmployeeId(event.target.value)}>
              <option value="">Выберите сотрудника</option>
              {employees.map((employee) => <option value={employee.id} key={employee.id}>{employee.display_name}{employee.position ? ` — ${employee.position}` : ""}</option>)}
            </select>
          </label>
          <label>
            <span className="app-field-label">Оклад за период</span>
            <input type="number" className={inputClass} inputMode="decimal" min="0.01" step="0.01" value={amount} required onChange={(event) => setAmount(event.target.value)} />
          </label>
          <label>
            <span className="app-field-label">Цена балла сверх нормы</span>
            <input type="number" className={inputClass} inputMode="decimal" min="0" step="0.01" value={pointRate} placeholder="0" onChange={(event) => setPointRate(event.target.value)} />
            <span className="app-text-muted mt-1 block text-xs">Если оставить пустым, сверх нормы доплата не начисляется.</span>
          </label>
          <label>
            <span className="app-field-label">Действует с</span>
            <input type="date" className={inputClass} value={effectiveFrom} required onChange={(event) => setEffectiveFrom(event.target.value)} />
          </label>
          <label>
            <span className="app-field-label">Валюта</span>
            <input className={inputClass} value={period.currency} disabled />
          </label>
          <label className="sm:col-span-2">
            <span className="app-field-label">Основание</span>
            <textarea className={`${inputClass} min-h-20 resize-y`} value={reason} placeholder="Приказ, договор или пояснение к изменению" onChange={(event) => setReason(event.target.value)} />
          </label>
        </div>
        <FormError message={error} />
        <ModalActions busy={busy} onClose={onClose} submitLabel="Сохранить черновик" />
      </form>
    </Modal>
  );
}

export function PayrollBulkPointRateModal({
  isOpen,
  period,
  rates,
  onClose,
  onSubmit,
  onSaved,
  onStale,
}: {
  isOpen: boolean;
  period: PayrollAdminPeriod;
  rates: PayrollAdminPayRate[];
  onClose: () => void;
  onSubmit: (payload: PayrollBulkPointRateWrite) => Promise<PayrollBulkPointRateResult>;
  onSaved: (result: PayrollBulkPointRateResult) => void | Promise<void>;
  onStale?: () => void | Promise<void>;
}) {
  const employeeOptions = useMemo(() => {
    const grouped = new Map<number, PayrollAdminPayRate[]>();
    for (const rate of rates) {
      if (rate.status === "voided") continue;
      const records = grouped.get(rate.employee.id) || [];
      records.push(rate);
      grouped.set(rate.employee.id, records);
    }
    return Array.from(grouped.values()).map((records) => {
      const current = [...records].sort((left, right) => {
        const dateOrder = right.effective_from.localeCompare(left.effective_from);
        return dateOrder || right.revision - left.revision || right.id - left.id;
      })[0];
      const pointRates = new Set(records.map((record) => record.point_rate));
      return {
        employee: current.employee,
        pointRate: pointRates.size === 1 ? current.point_rate : null,
        hasDraft: records.some((record) => record.status === "draft"),
        rateCount: new Set(records.map((record) => record.effective_from)).size,
      };
    }).sort((left, right) => (
      left.employee.display_name.localeCompare(right.employee.display_name, "ru")
    ));
  }, [rates]);
  const [selectedEmployeeIds, setSelectedEmployeeIds] = useState<Set<number>>(
    () => new Set(employeeOptions.map((option) => option.employee.id)),
  );
  const [search, setSearch] = useState("");
  const [mode, setMode] = useState<PayrollBulkPointRateMode>("fixed");
  const [pointRate, setPointRate] = useState("");
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const filteredOptions = useMemo(() => {
    const needle = search.trim().toLocaleLowerCase("ru-RU");
    if (!needle) return employeeOptions;
    return employeeOptions.filter(({ employee }) => (
      `${employee.display_name} ${employee.position || ""} ${employee.department || ""}`
        .toLocaleLowerCase("ru-RU")
        .includes(needle)
    ));
  }, [employeeOptions, search]);
  const allSelected = employeeOptions.length > 0
    && employeeOptions.every(({ employee }) => selectedEmployeeIds.has(employee.id));
  const numericPointRate = Number(pointRate);
  const fixedValueValid = pointRate.trim() === ""
    || (Number.isFinite(numericPointRate) && numericPointRate >= 0);
  const canSubmit = selectedEmployeeIds.size > 0
    && (mode === "in_norm" || fixedValueValid)
    && reason.trim().length > 0;

  const toggleEmployee = (employeeId: number) => {
    setSelectedEmployeeIds((current) => {
      const next = new Set(current);
      if (next.has(employeeId)) next.delete(employeeId);
      else next.add(employeeId);
      return next;
    });
  };

  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (!canSubmit) return;
    let result: PayrollBulkPointRateResult | null = null;
    void submitModalForm(async () => {
      result = await onSubmit({
        employee_ids: Array.from(selectedEmployeeIds),
        mode,
        point_rate: mode === "fixed" ? pointRate.trim() || "0" : null,
        reason: reason.trim(),
      });
    }, {
      fallback: "Не удалось массово задать цену балла.",
      setBusy,
      setError,
      onSaved: async () => {
        if (result) await onSaved(result);
      },
      onStale,
    });
  };

  return (
    <Modal isOpen={isOpen} onClose={onClose} title="Цена балла сверх нормы" size="lg">
      <form onSubmit={submit}>
        <div className="app-selected rounded-xl px-4 py-3">
          <p className="text-sm font-semibold text-[var(--foreground)]">{period.name || period.code}</p>
          <p className="app-text-muted mt-1 text-xs leading-relaxed">
            Черновики будут обновлены. Для утверждённых ставок система создаст новые черновые версии.
          </p>
        </div>

        <fieldset className="mt-4">
          <legend className="app-field-label">Как заполнить цену сверх нормы</legend>
          <div className="grid gap-2 sm:grid-cols-2">
            <label className={`cursor-pointer rounded-xl border px-4 py-3 ${mode === "fixed" ? "app-selected" : "app-surface-muted border-[var(--border-subtle)]"}`}>
              <span className="flex items-start gap-2.5">
                <input type="radio" name="point-rate-mode" value="fixed" checked={mode === "fixed"} onChange={() => setMode("fixed")} />
                <span>
                  <span className="block text-sm font-semibold text-[var(--foreground)]">Указать одну цену</span>
                  <span className="app-text-muted mt-1 block text-xs">Одинаковое значение для всех выбранных сотрудников.</span>
                </span>
              </span>
            </label>
            <label className={`cursor-pointer rounded-xl border px-4 py-3 ${mode === "in_norm" ? "app-selected" : "app-surface-muted border-[var(--border-subtle)]"}`}>
              <span className="flex items-start gap-2.5">
                <input type="radio" name="point-rate-mode" value="in_norm" checked={mode === "in_norm"} onChange={() => setMode("in_norm")} />
                <span>
                  <span className="block text-sm font-semibold text-[var(--foreground)]">Как в пределах нормы</span>
                  <span className="app-text-muted mt-1 block text-xs">Для каждого сотрудника: его оклад ÷ его норма баллов.</span>
                </span>
              </span>
            </label>
          </div>
        </fieldset>

        <div className="mt-4 grid gap-4 sm:grid-cols-2">
          <label>
            <span className="app-field-label">Цена сверх нормы</span>
            <input
              type="number"
              className={inputClass}
              inputMode="decimal"
              min="0"
              step="0.01"
              value={pointRate}
              disabled={mode === "in_norm"}
              placeholder={mode === "in_norm" ? "Рассчитается отдельно" : "0"}
              onChange={(event) => setPointRate(event.target.value)}
            />
            {mode === "fixed" ? <span className="app-text-muted mt-1 block text-xs">Пустое поле будет сохранено как 0.</span> : null}
          </label>
          <label>
            <span className="app-field-label">Выбрано сотрудников</span>
            <div className="app-input flex min-h-10 items-center rounded-lg px-3 text-sm font-medium">
              {selectedEmployeeIds.size} из {employeeOptions.length}
            </div>
          </label>
        </div>

        <div className="mt-4">
          <div className="mb-2 flex items-center justify-between gap-3">
            <span className="app-field-label mb-0">Сотрудники</span>
            <button
              type="button"
              className="app-action-ghost rounded-md px-2 py-1 text-xs"
              onClick={() => setSelectedEmployeeIds(
                allSelected ? new Set() : new Set(employeeOptions.map((option) => option.employee.id)),
              )}
            >
              {allSelected ? "Снять выбор" : "Выбрать всех"}
            </button>
          </div>
          <label className="relative block">
            <Search className="app-text-muted pointer-events-none absolute left-3 top-1/2 -translate-y-1/2" size={15} />
            <input
              className="app-input w-full rounded-lg py-2.5 pl-9 pr-3 text-sm"
              value={search}
              placeholder="Поиск по сотрудникам"
              onChange={(event) => setSearch(event.target.value)}
            />
          </label>
          <div className="app-surface-muted mt-2 max-h-64 overflow-y-auto rounded-xl border border-[var(--border-subtle)]">
            {filteredOptions.length ? filteredOptions.map((option) => (
              <label
                key={option.employee.id}
                className="flex cursor-pointer items-center gap-3 border-b border-[var(--border-subtle)] px-3 py-2.5 last:border-b-0 hover:bg-[var(--surface-secondary)]"
              >
                <input
                  type="checkbox"
                  checked={selectedEmployeeIds.has(option.employee.id)}
                  onChange={() => toggleEmployee(option.employee.id)}
                />
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-sm font-medium text-[var(--foreground)]">
                    {option.employee.display_name}
                  </span>
                  <span className="app-text-muted mt-0.5 block truncate text-xs">
                    {option.employee.position || option.employee.department || "Сотрудник"}
                  </span>
                </span>
                <span className="shrink-0 text-right">
                  <span className="block text-xs font-medium text-[var(--foreground)]">
                    {option.pointRate === null ? `${option.rateCount} ставки` : `${option.pointRate} ${period.currency}`}
                  </span>
                  <span className="app-text-muted mt-0.5 block text-[11px]">
                    {mode === "in_norm" ? "Станет как цена в норме" : option.hasDraft ? "Обновится черновик" : "Новая версия"}
                  </span>
                </span>
              </label>
            )) : (
              <p className="app-text-muted px-4 py-8 text-center text-sm">Сотрудники не найдены.</p>
            )}
          </div>
        </div>

        <label className="mt-4 block">
          <span className="app-field-label">Основание изменения *</span>
          <textarea
            className={`${inputClass} min-h-20 resize-y`}
            value={reason}
            required
            placeholder="Укажите основание для массового изменения"
            onChange={(event) => setReason(event.target.value)}
          />
        </label>
        <FormError message={error} />
        <ModalActions
          busy={busy}
          disabled={!canSubmit}
          onClose={onClose}
          submitLabel={`Применить к ${selectedEmployeeIds.size}`}
        />
      </form>
    </Modal>
  );
}

export function PayrollBulkPayRateModal({
  isOpen,
  period,
  employees,
  rates,
  onClose,
  onSubmit,
  onSaved,
  onStale,
}: {
  isOpen: boolean;
  period: PayrollAdminPeriod;
  employees: PayrollAdminEmployee[];
  rates: PayrollAdminPayRate[];
  onClose: () => void;
  onSubmit: (payload: PayrollBulkPayRateWrite) => Promise<PayrollBulkPayRateResult>;
  onSaved: (result: PayrollBulkPayRateResult) => void | Promise<void>;
  onStale?: () => void | Promise<void>;
}) {
  const employeeOptions = useMemo(() => employees.map((employee) => {
    const relevantRates = rates
      .filter((rate) => (
        rate.employee.id === employee.id
        && rate.status !== "voided"
        && rate.effective_from <= period.date_to
      ))
      .sort((left, right) => {
        const dateOrder = right.effective_from.localeCompare(left.effective_from);
        return dateOrder || right.revision - left.revision || right.id - left.id;
      });
    return { employee, rates: relevantRates };
  }).sort((left, right) => (
    left.employee.display_name.localeCompare(right.employee.display_name, "ru")
  )), [employees, period.date_to, rates]);
  const [selectedEmployeeIds, setSelectedEmployeeIds] = useState<Set<number>>(
    () => new Set(employeeOptions.map((option) => option.employee.id)),
  );
  const [search, setSearch] = useState("");
  const [amount, setAmount] = useState("");
  const [effectiveFrom, setEffectiveFrom] = useState(period.date_from);
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const filteredOptions = useMemo(() => {
    const needle = search.trim().toLocaleLowerCase("ru-RU");
    if (!needle) return employeeOptions;
    return employeeOptions.filter(({ employee }) => (
      `${employee.display_name} ${employee.position || ""} ${employee.department || ""}`
        .toLocaleLowerCase("ru-RU")
        .includes(needle)
    ));
  }, [employeeOptions, search]);
  const allSelected = employeeOptions.length > 0
    && employeeOptions.every(({ employee }) => selectedEmployeeIds.has(employee.id));
  const numericAmount = Number(amount);
  const canSubmit = selectedEmployeeIds.size > 0
    && amount.trim() !== ""
    && Number.isFinite(numericAmount)
    && numericAmount > 0
    && effectiveFrom >= period.date_from
    && effectiveFrom <= period.date_to
    && reason.trim().length > 0;

  const toggleEmployee = (employeeId: number) => {
    setSelectedEmployeeIds((current) => {
      const next = new Set(current);
      if (next.has(employeeId)) next.delete(employeeId);
      else next.add(employeeId);
      return next;
    });
  };

  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (!canSubmit) return;
    let result: PayrollBulkPayRateResult | null = null;
    void submitModalForm(async () => {
      result = await onSubmit({
        employee_ids: Array.from(selectedEmployeeIds),
        amount,
        effective_from: effectiveFrom,
        reason: reason.trim(),
      });
    }, {
      fallback: "Не удалось массово добавить ставку.",
      setBusy,
      setError,
      onSaved: async () => {
        if (result) await onSaved(result);
      },
      onStale,
    });
  };

  return (
    <Modal isOpen={isOpen} onClose={onClose} title="Массовое добавление ставки" size="lg">
      <form onSubmit={submit}>
        <div className="app-selected rounded-xl px-4 py-3">
          <p className="text-sm font-semibold text-[var(--foreground)]">{period.name || period.code}</p>
          <p className="app-text-muted mt-1 text-xs leading-relaxed">
            Новые ставки сохранятся черновиками. Для утверждённой ставки на выбранную дату будет создана новая версия.
          </p>
        </div>

        <div className="mt-4 grid gap-4 sm:grid-cols-2">
          <label>
            <span className="app-field-label">Ставка / оклад *</span>
            <input
              type="number"
              className={inputClass}
              inputMode="decimal"
              min="0.01"
              step="0.01"
              value={amount}
              required
              onChange={(event) => setAmount(event.target.value)}
            />
          </label>
          <label>
            <span className="app-field-label">Действует с *</span>
            <input
              type="date"
              className={inputClass}
              min={period.date_from}
              max={period.date_to}
              value={effectiveFrom}
              required
              onChange={(event) => setEffectiveFrom(event.target.value)}
            />
          </label>
        </div>

        <div className="mt-4">
          <div className="mb-2 flex items-center justify-between gap-3">
            <span className="app-field-label mb-0">
              Сотрудники · {selectedEmployeeIds.size} из {employeeOptions.length}
            </span>
            <button
              type="button"
              className="app-action-ghost rounded-md px-2 py-1 text-xs"
              onClick={() => setSelectedEmployeeIds(
                allSelected ? new Set() : new Set(employeeOptions.map((option) => option.employee.id)),
              )}
            >
              {allSelected ? "Снять выбор" : "Выбрать всех"}
            </button>
          </div>
          <label className="relative block">
            <Search className="app-text-muted pointer-events-none absolute left-3 top-1/2 -translate-y-1/2" size={15} />
            <input
              className="app-input w-full rounded-lg py-2.5 pl-9 pr-3 text-sm"
              value={search}
              placeholder="Поиск по сотрудникам"
              onChange={(event) => setSearch(event.target.value)}
            />
          </label>
          <div className="app-surface-muted mt-2 max-h-64 overflow-y-auto rounded-xl border border-[var(--border-subtle)]">
            {filteredOptions.length ? filteredOptions.map((option) => {
              const relevant = option.rates.filter((rate) => rate.effective_from <= effectiveFrom);
              const exact = relevant.find((rate) => rate.effective_from === effectiveFrom);
              const inherited = relevant[0];
              const action = exact?.status === "draft"
                ? "Обновится черновик"
                : exact?.status === "approved"
                  ? "Новая версия"
                  : "Новая ставка";
              return (
                <label
                  key={option.employee.id}
                  className="flex cursor-pointer items-center gap-3 border-b border-[var(--border-subtle)] px-3 py-2.5 last:border-b-0 hover:bg-[var(--surface-secondary)]"
                >
                  <input
                    type="checkbox"
                    checked={selectedEmployeeIds.has(option.employee.id)}
                    onChange={() => toggleEmployee(option.employee.id)}
                  />
                  <span className="min-w-0 flex-1">
                    <span className="block truncate text-sm font-medium text-[var(--foreground)]">
                      {option.employee.display_name}
                    </span>
                    <span className="app-text-muted mt-0.5 block truncate text-xs">
                      {option.employee.position || option.employee.department || "Сотрудник"}
                    </span>
                  </span>
                  <span className="shrink-0 text-right">
                    <span className="block text-xs font-medium text-[var(--foreground)]">
                      {inherited ? `${inherited.point_rate} ${period.currency} / балл сверх нормы` : "Цена сверх нормы: 0"}
                    </span>
                    <span className="app-text-muted mt-0.5 block text-[11px]">{action}</span>
                  </span>
                </label>
              );
            }) : (
              <p className="app-text-muted px-4 py-8 text-center text-sm">Сотрудники не найдены.</p>
            )}
          </div>
          <p className="app-text-muted mt-2 text-xs">
            Цена балла сверх нормы наследуется из последней ставки сотрудника; если ставки ещё не было, будет установлено 0.
          </p>
        </div>

        <label className="mt-4 block">
          <span className="app-field-label">Основание изменения *</span>
          <textarea
            className={`${inputClass} min-h-20 resize-y`}
            value={reason}
            required
            placeholder="Укажите основание для массового добавления"
            onChange={(event) => setReason(event.target.value)}
          />
        </label>
        <FormError message={error} />
        <ModalActions
          busy={busy}
          disabled={!canSubmit}
          onClose={onClose}
          submitLabel={`Применить к ${selectedEmployeeIds.size}`}
        />
      </form>
    </Modal>
  );
}

export function PayrollWorkRecordFormModal({
  isOpen,
  period,
  employees,
  record,
  onClose,
  onSubmit,
  onSaved,
  onStale,
}: {
  isOpen: boolean;
  period: PayrollAdminPeriod;
  employees: PayrollAdminEmployee[];
  record?: PayrollAdminWorkRecord | null;
  onClose: () => void;
  onSubmit: (payload: PayrollWorkRecordWrite) => Promise<unknown>;
  onSaved: () => void | Promise<void>;
  onStale?: () => void | Promise<void>;
}) {
  const fromAttendance = record?.source === "attendance";
  const [form, setForm] = useState(() => ({
    employee_id: record ? String(record.employee.id) : "",
    target_points: record?.target_points_overridden ? record.target_points : "",
    actual_points: record?.actual_points || "",
    expected_point_amount: record?.expected_point_amount || "",
    expected_gross: record?.expected_gross || "",
    expected_recalculated_gross: record?.expected_recalculated_gross || "",
    expected_payable: record?.expected_payable || "",
    reason: record?.reason || "",
  }));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const optionalMoney = (value: string) => value.trim() || null;
  const submit = (event: FormEvent) => {
    event.preventDefault();
    void submitModalForm(() => onSubmit({
      period_id: period.id,
      employee_id: Number(form.employee_id),
      target_points: form.target_points.trim() || null,
      actual_points: form.actual_points,
      expected_point_amount: optionalMoney(form.expected_point_amount),
      expected_gross: optionalMoney(form.expected_gross),
      expected_recalculated_gross: optionalMoney(form.expected_recalculated_gross),
      expected_payable: optionalMoney(form.expected_payable),
      reason: form.reason,
    }), {
      fallback: "Не удалось сохранить выработку.",
      setBusy,
      setError,
      onSaved,
      onStale,
    });
  };

  return (
    <Modal isOpen={isOpen} onClose={onClose} title={record ? "Изменить черновик выработки" : "Добавить выработку"} size="lg">
      <form onSubmit={submit}>
        <div className="grid gap-4 sm:grid-cols-2">
          <label className="sm:col-span-2">
            <span className="app-field-label">Сотрудник</span>
            <select className={selectClass} required value={form.employee_id} disabled={Boolean(record)} onChange={(event) => setForm({ ...form, employee_id: event.target.value })}>
              <option value="">Выберите сотрудника</option>
              {employees.map((employee) => <option value={employee.id} key={employee.id}>{employee.display_name}{employee.position ? ` — ${employee.position}` : ""}</option>)}
            </select>
          </label>
          <label>
            <span className="app-field-label">{fromAttendance ? "Норма, часы" : "Норма баллов"}</span>
            <input type="number" className={inputClass} inputMode="decimal" min="0.0001" step="0.0001" placeholder="Рассчитается автоматически" value={form.target_points} onChange={(event) => setForm({ ...form, target_points: event.target.value })} />
          </label>
          <label>
            <span className="app-field-label">{fromAttendance ? "Отработано, часы" : "Фактические баллы"}</span>
            <input type="number" className={inputClass} inputMode="decimal" min="0" step="0.0001" required value={form.actual_points} onChange={(event) => setForm({ ...form, actual_points: event.target.value })} />
          </label>
        </div>

        <details className="app-surface-muted mt-4 rounded-xl p-3 sm:p-4">
          <summary className="cursor-pointer text-sm font-semibold text-[var(--foreground)]">Контрольные суммы из Excel</summary>
          <p className="app-text-muted mt-2 text-xs leading-relaxed">Не участвуют в формуле, но заблокируют расчёт при расхождении.</p>
          <div className="mt-4 grid gap-4 sm:grid-cols-2">
            <label><span className="app-field-label">Выработка по баллам</span><input type="number" className={inputClass} inputMode="decimal" step="0.01" value={form.expected_point_amount} onChange={(event) => setForm({ ...form, expected_point_amount: event.target.value })} /></label>
            <label><span className="app-field-label">Итого начислено</span><input type="number" className={inputClass} inputMode="decimal" step="0.01" value={form.expected_gross} onChange={(event) => setForm({ ...form, expected_gross: event.target.value })} /></label>
            <label><span className="app-field-label">Перерасчёт</span><input type="number" className={inputClass} inputMode="decimal" step="0.01" value={form.expected_recalculated_gross} onChange={(event) => setForm({ ...form, expected_recalculated_gross: event.target.value })} /></label>
            <label><span className="app-field-label">К выплате</span><input type="number" className={inputClass} inputMode="decimal" step="0.01" value={form.expected_payable} onChange={(event) => setForm({ ...form, expected_payable: event.target.value })} /></label>
          </div>
        </details>

        <label className="mt-4 block">
          <span className="app-field-label">Основание изменения</span>
          <textarea className={`${inputClass} min-h-20 resize-y`} value={form.reason} placeholder="Обязательно для новой ревизии" onChange={(event) => setForm({ ...form, reason: event.target.value })} />
        </label>
        <FormError message={error} />
        <ModalActions busy={busy} onClose={onClose} submitLabel="Сохранить черновик" />
      </form>
    </Modal>
  );
}

export function PayrollInputLineFormModal({
  isOpen,
  period,
  periods,
  employees,
  components,
  line,
  onClose,
  onSubmit,
  onSaved,
  onStale,
}: {
  isOpen: boolean;
  period: PayrollAdminPeriod;
  periods: PayrollAdminPeriod[];
  employees: PayrollAdminEmployee[];
  components: PayrollComponent[];
  line?: PayrollAdminInputLine | null;
  onClose: () => void;
  onSubmit: (payload: PayrollInputLineWrite) => Promise<unknown>;
  onSaved: () => void | Promise<void>;
  onStale?: () => void | Promise<void>;
}) {
  const [form, setForm] = useState(() => ({
    employee_id: line ? String(line.employee.id) : "",
    component_id: line ? String(line.component.id) : "",
    amount: line?.amount || "",
    relates_to_period_id: line?.relates_to_period_id ? String(line.relates_to_period_id) : "",
    reason: line?.reason || "",
  }));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const component = useMemo(() => components.find((item) => item.id === Number(form.component_id)), [components, form.component_id]);
  const submit = (event: FormEvent) => {
    event.preventDefault();
    void submitModalForm(() => onSubmit({
      period_id: period.id,
      employee_id: Number(form.employee_id),
      component_id: Number(form.component_id),
      amount: form.amount,
      relates_to_period_id: form.relates_to_period_id ? Number(form.relates_to_period_id) : null,
      reason: form.reason,
    }), {
      fallback: "Не удалось сохранить начисление.",
      setBusy,
      setError,
      onSaved,
      onStale,
    });
  };

  return (
    <Modal isOpen={isOpen} onClose={onClose} title={line ? "Изменить строку" : "Новое начисление или выплата"} size="md">
      <form onSubmit={submit}>
        <div className="grid gap-4 sm:grid-cols-2">
          <label className="sm:col-span-2">
            <span className="app-field-label">Сотрудник</span>
            <select className={selectClass} required disabled={Boolean(line)} value={form.employee_id} onChange={(event) => setForm({ ...form, employee_id: event.target.value })}>
              <option value="">Выберите сотрудника</option>
              {employees.map((employee) => <option value={employee.id} key={employee.id}>{employee.display_name}{employee.position ? ` — ${employee.position}` : ""}</option>)}
            </select>
          </label>
          <label className="sm:col-span-2">
            <span className="app-field-label">Вид операции</span>
            <select className={selectClass} required disabled={Boolean(line)} value={form.component_id} onChange={(event) => setForm({ ...form, component_id: event.target.value })}>
              <option value="">Выберите вид</option>
              {components.filter((item) => item.is_active).map((item) => <option value={item.id} key={item.id}>{item.name}</option>)}
            </select>
          </label>
          <label>
            <span className="app-field-label">Сумма</span>
            <input type="number" className={inputClass} inputMode="decimal" min="0.01" step="0.01" required value={form.amount} onChange={(event) => setForm({ ...form, amount: event.target.value })} />
          </label>
          <label>
            <span className="app-field-label">Относится к периоду</span>
            <select className={selectClass} value={form.relates_to_period_id} onChange={(event) => setForm({ ...form, relates_to_period_id: event.target.value })}>
              <option value="">Текущий период</option>
              {periods.filter((item) => item.id !== period.id).map((item) => <option key={item.id} value={item.id}>{item.name || item.code}</option>)}
            </select>
          </label>
          <label className="sm:col-span-2">
            <span className="app-field-label">Основание{component?.requires_reason || form.relates_to_period_id ? " *" : ""}</span>
            <textarea className={`${inputClass} min-h-20 resize-y`} required={Boolean(component?.requires_reason || form.relates_to_period_id)} value={form.reason} placeholder="Премия, приказ, причина корректировки" onChange={(event) => setForm({ ...form, reason: event.target.value })} />
          </label>
        </div>
        <FormError message={error} />
        <ModalActions busy={busy} onClose={onClose} submitLabel="Сохранить черновик" />
      </form>
    </Modal>
  );
}

export function PayrollConfirmModal({
  isOpen,
  title,
  description,
  confirmLabel,
  reasonLabel,
  reasonRequired = false,
  warning,
  onClose,
  onConfirm,
  onDone,
  onStale,
}: {
  isOpen: boolean;
  title: string;
  description: string;
  confirmLabel: string;
  reasonLabel?: string;
  reasonRequired?: boolean;
  warning?: string;
  onClose: () => void;
  onConfirm: (reason: string) => Promise<unknown>;
  onDone: () => void | Promise<void>;
  onStale?: () => void | Promise<void>;
}) {
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = (event: FormEvent) => {
    event.preventDefault();
    void submitModalForm(() => onConfirm(reason), {
      fallback: "Не удалось выполнить действие.",
      setBusy,
      setError,
      onSaved: onDone,
      onStale,
    });
  };

  return (
    <Modal isOpen={isOpen} onClose={onClose} title={title} size="sm">
      <form onSubmit={submit}>
        <p className="app-text-muted text-sm leading-relaxed">{description}</p>
        {warning ? (
          <div className="app-feedback-warning mt-4 flex items-start gap-2 rounded-lg px-3 py-2.5 text-sm">
            <AlertTriangle className="mt-0.5 shrink-0" size={16} />
            <span>{warning}</span>
          </div>
        ) : null}
        {reasonLabel ? (
          <label className="mt-4 block">
            <span className="app-field-label">{reasonLabel}</span>
            <textarea className={`${inputClass} min-h-24 resize-y`} required={reasonRequired} value={reason} onChange={(event) => setReason(event.target.value)} />
          </label>
        ) : null}
        <FormError message={error} />
        <ModalActions busy={busy} onClose={onClose} submitLabel={confirmLabel} />
      </form>
    </Modal>
  );
}
