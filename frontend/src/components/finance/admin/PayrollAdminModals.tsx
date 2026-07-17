"use client";

import { AlertTriangle, Check, Loader2 } from "lucide-react";
import { useMemo, useState, type FormEvent } from "react";

import { Modal } from "@/components/ui";
import type {
  PayrollAdminEmployee,
  PayrollAdminInputLine,
  PayrollAdminPayRate,
  PayrollAdminPeriod,
  PayrollAdminWorkRecord,
  PayrollComponent,
  PayrollInputLineWrite,
  PayrollPayRateWrite,
  PayrollPeriodWrite,
  PayrollWorkRecordWrite,
} from "@/lib/api/finance";
import { getPayrollAdminError, isPayrollAdminStaleConflict } from "@/lib/payroll-admin";

const inputClass = "app-input w-full rounded-lg px-3 py-2.5 text-sm";
const selectClass = "app-select w-full rounded-lg px-3 py-2.5 text-sm";

function ModalActions({
  busy,
  onClose,
  submitLabel,
}: {
  busy: boolean;
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
        disabled={busy}
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
  onClose,
  onSubmit,
  onSaved,
  onStale,
}: {
  isOpen: boolean;
  period?: PayrollAdminPeriod | null;
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
  } : {
    code: "",
    name: "",
    date_from: "",
    date_to: "",
    pay_date: null,
    currency: "RUB",
  });
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
            <input type="number" className={inputClass} inputMode="decimal" min="0" step="0.01" value={pointRate} required onChange={(event) => setPointRate(event.target.value)} />
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
    target_points: record?.target_points || "",
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
      target_points: form.target_points,
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
            <input type="number" className={inputClass} inputMode="decimal" min="0.0001" step="0.0001" required value={form.target_points} onChange={(event) => setForm({ ...form, target_points: event.target.value })} />
          </label>
          <label>
            <span className="app-field-label">{fromAttendance ? "Отработано, часы" : "Фактические баллы"}</span>
            <input type="number" className={inputClass} inputMode="decimal" min="0" step="0.0001" required value={form.actual_points} onChange={(event) => setForm({ ...form, actual_points: event.target.value })} />
          </label>
        </div>

        <details className="app-surface-muted mt-4 rounded-xl p-3 sm:p-4">
          <summary className="cursor-pointer text-sm font-semibold text-[var(--foreground)]">Контрольные суммы из Excel</summary>
          <p className="app-text-muted mt-2 text-xs leading-relaxed">Не участвуют в формуле, но остановят согласование при расхождении.</p>
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
