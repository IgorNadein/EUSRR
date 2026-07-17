"use client";

import { CalendarCheck2, Check, Loader2, Pencil, RotateCcw } from "lucide-react";

import type {
  PayrollAdminInputLine,
  PayrollAdminPayRate,
  PayrollAdminWorkRecord,
  PayrollApprovalStatus,
} from "@/lib/api/finance";
import { formatPayrollDate, formatPayrollMoney } from "@/lib/payroll";
import { formatPayrollWorkMetric, isAttendancePayrollWorkRecord } from "@/lib/payroll-attendance";
import {
  approvalStatusMeta,
  canApprovePayrollDraft,
} from "@/lib/payroll-admin";

function RecordStatus({ status }: { status: PayrollApprovalStatus }) {
  const meta = approvalStatusMeta[status];
  return <span className={`app-status-pill ${meta.className}`}>{meta.label}</span>;
}

function ListState({ loading, error, empty }: { loading: boolean; error: string | null; empty: boolean }) {
  if (loading) {
    return (
      <div className="flex min-h-40 items-center justify-center gap-2 text-sm text-[var(--muted-foreground)]">
        <Loader2 className="animate-spin" size={18} /> Загрузка данных…
      </div>
    );
  }
  if (error) return <div className="app-feedback-danger rounded-xl px-4 py-3 text-sm">{error}</div>;
  if (empty) return <div className="app-surface-muted rounded-xl px-4 py-8 text-center text-sm text-[var(--muted-foreground)]">По выбранным условиям записей нет.</div>;
  return null;
}

function ActionButton({
  label,
  icon,
  onClick,
  tone = "secondary",
  disabled = false,
  tooltip,
}: {
  label: string;
  icon: React.ReactNode;
  onClick: () => void;
  tone?: "secondary" | "success";
  disabled?: boolean;
  tooltip?: string;
}) {
  return (
    <button
      type="button"
      className={`${tone === "success" ? "app-action-success" : "app-action-secondary"} inline-flex h-8 items-center justify-center gap-1.5 rounded-lg px-2.5 text-xs font-medium disabled:cursor-not-allowed disabled:opacity-50`}
      onClick={onClick}
      disabled={disabled}
      title={tooltip || label}
    >
      {icon}
      {label}
    </button>
  );
}

function RecordActions({
  status,
  isAuthor,
  canManage,
  canApprove,
  canOverrideApproval,
  fullAccess,
  onEdit,
  onApprove,
  onRevise,
}: {
  status: PayrollApprovalStatus;
  isAuthor: boolean;
  canManage: boolean;
  canApprove: boolean;
  canOverrideApproval: boolean;
  fullAccess: boolean;
  onEdit?: () => void;
  onApprove?: () => void;
  onRevise?: () => void;
}) {
  if (status === "draft") {
    const approvalAllowed = canApprovePayrollDraft(isAuthor, canApprove, canOverrideApproval);
    return (
      <div className="flex flex-wrap justify-end gap-1.5">
        {canManage && (isAuthor || fullAccess) && onEdit ? <ActionButton label="Изменить" icon={<Pencil size={13} />} onClick={onEdit} /> : null}
        {canApprove && onApprove ? <ActionButton label="Утвердить" icon={<Check size={13} />} onClick={onApprove} tone="success" disabled={!approvalAllowed} tooltip={approvalAllowed ? "Утвердить" : "Недостаточно прав для утверждения этой записи."} /> : null}
      </div>
    );
  }
  if (status === "approved" && canManage && onRevise) {
    return <ActionButton label="Новая версия" icon={<RotateCcw size={13} />} onClick={onRevise} />;
  }
  return null;
}

export function PayrollRatesTable({
  records,
  loading,
  error,
  currentUserId,
  canManage,
  canApprove,
  canOverrideApproval,
  fullAccess,
  onEdit,
  onApprove,
  onRevise,
}: {
  records: PayrollAdminPayRate[];
  loading: boolean;
  error: string | null;
  currentUserId?: number;
  canManage: boolean;
  canApprove: boolean;
  canOverrideApproval: boolean;
  fullAccess: boolean;
  onEdit: (record: PayrollAdminPayRate) => void;
  onApprove: (record: PayrollAdminPayRate) => void;
  onRevise: (record: PayrollAdminPayRate) => void;
}) {
  const state = <ListState loading={loading} error={error} empty={records.length === 0} />;
  if (loading || error || records.length === 0) return state;

  return (
    <div className="overflow-hidden rounded-xl border border-[var(--border-subtle)] md:overflow-x-auto">
      <div className="md:min-w-[900px]">
      <div className="app-surface-muted hidden grid-cols-[minmax(180px,1.5fr)_minmax(100px,.8fr)_minmax(105px,.8fr)_120px_115px_minmax(150px,1fr)] gap-3 border-0 border-b border-[var(--border-subtle)] px-4 py-2.5 text-xs font-medium text-[var(--muted-foreground)] md:grid">
        <span>Сотрудник</span><span>Оклад</span><span>Цена балла</span><span>Действует с</span><span>Статус</span><span className="text-right">Действия</span>
      </div>
      <div className="divide-y divide-[var(--border-subtle)]">
        {records.map((record) => (
          <div key={record.id} className="grid gap-3 bg-[var(--surface-primary)] px-4 py-3 md:grid-cols-[minmax(180px,1.5fr)_minmax(100px,.8fr)_minmax(105px,.8fr)_120px_115px_minmax(150px,1fr)] md:items-center">
            <div className="min-w-0"><p className="truncate text-sm font-semibold text-[var(--foreground)]">{record.employee.display_name}</p><p className="app-text-muted mt-0.5 truncate text-xs">{record.employee.position || record.employee.department || "Сотрудник"}</p></div>
            <div><span className="app-text-muted mr-2 text-xs md:hidden">Оклад</span><span className="text-sm font-medium text-[var(--foreground)]">{formatPayrollMoney(record.amount, record.currency)}</span></div>
            <div><span className="app-text-muted mr-2 text-xs md:hidden">Цена балла</span><span className="text-sm text-[var(--foreground)]">{formatPayrollMoney(record.point_rate, record.currency)}</span></div>
            <div><span className="app-text-muted mr-2 text-xs md:hidden">С</span><span className="text-sm text-[var(--foreground)]">{formatPayrollDate(record.effective_from)}</span></div>
            <RecordStatus status={record.status} />
            <RecordActions status={record.status} isAuthor={record.created_by.id === currentUserId} canManage={canManage} canApprove={canApprove} canOverrideApproval={canOverrideApproval} fullAccess={fullAccess} onEdit={() => onEdit(record)} onApprove={() => onApprove(record)} onRevise={() => onRevise(record)} />
          </div>
        ))}
      </div>
      </div>
    </div>
  );
}

export function PayrollWorkRecordsTable({
  records,
  loading,
  error,
  currentUserId,
  canManage,
  canApprove,
  canOverrideApproval,
  fullAccess,
  onEdit,
  onApprove,
  onRevise,
}: {
  records: PayrollAdminWorkRecord[];
  loading: boolean;
  error: string | null;
  currentUserId?: number;
  canManage: boolean;
  canApprove: boolean;
  canOverrideApproval: boolean;
  fullAccess: boolean;
  onEdit: (record: PayrollAdminWorkRecord) => void;
  onApprove: (record: PayrollAdminWorkRecord) => void;
  onRevise: (record: PayrollAdminWorkRecord) => void;
}) {
  const state = <ListState loading={loading} error={error} empty={records.length === 0} />;
  if (loading || error || records.length === 0) return state;

  return (
    <div className="overflow-hidden rounded-xl border border-[var(--border-subtle)] md:overflow-x-auto">
      <div className="md:min-w-[880px]">
      <div className="app-surface-muted hidden grid-cols-[minmax(190px,1.5fr)_110px_110px_120px_115px_minmax(150px,1fr)] gap-3 border-0 border-b border-[var(--border-subtle)] px-4 py-2.5 text-xs font-medium text-[var(--muted-foreground)] md:grid">
        <span>Сотрудник</span><span>Норма</span><span>Факт</span><span>Контроль</span><span>Статус</span><span className="text-right">Действия</span>
      </div>
      <div className="divide-y divide-[var(--border-subtle)]">
        {records.map((record) => {
          const fromAttendance = isAttendancePayrollWorkRecord(record.source);
          return (
            <div key={record.id} className="grid gap-3 bg-[var(--surface-primary)] px-4 py-3 md:grid-cols-[minmax(190px,1.5fr)_110px_110px_120px_115px_minmax(150px,1fr)] md:items-center">
              <div className="min-w-0">
                <p className="truncate text-sm font-semibold text-[var(--foreground)]">{record.employee.display_name}</p>
                <p className="app-text-muted mt-0.5 truncate text-xs">{record.employee.position || record.employee.department || "Сотрудник"}</p>
                {fromAttendance ? (
                  <span className="app-selected mt-1.5 inline-flex items-center gap-1 rounded-full px-2 py-1 text-[10px] font-semibold leading-none">
                    <CalendarCheck2 size={11} /> Из посещаемости
                  </span>
                ) : null}
              </div>
              <div><span className="app-text-muted mr-2 text-xs md:hidden">Норма</span><span className="text-sm font-medium text-[var(--foreground)]">{formatPayrollWorkMetric(record.target_points, record.source)}</span></div>
              <div><span className="app-text-muted mr-2 text-xs md:hidden">Факт</span><span className="text-sm font-medium text-[var(--foreground)]">{formatPayrollWorkMetric(record.actual_points, record.source)}</span></div>
              <div><span className="app-text-muted mr-2 text-xs md:hidden">Контроль</span><span className="text-sm text-[var(--foreground)]">{record.expected_payable ? formatPayrollMoney(record.expected_payable) : "—"}</span></div>
              <RecordStatus status={record.status} />
              <RecordActions status={record.status} isAuthor={record.created_by.id === currentUserId} canManage={canManage} canApprove={canApprove} canOverrideApproval={canOverrideApproval} fullAccess={fullAccess} onEdit={() => onEdit(record)} onApprove={() => onApprove(record)} onRevise={() => onRevise(record)} />
            </div>
          );
        })}
      </div>
      </div>
    </div>
  );
}

export function PayrollInputLinesTable({
  records,
  loading,
  error,
  currentUserId,
  canManage,
  canApprove,
  canOverrideApproval,
  fullAccess,
  onEdit,
  onApprove,
}: {
  records: PayrollAdminInputLine[];
  loading: boolean;
  error: string | null;
  currentUserId?: number;
  canManage: boolean;
  canApprove: boolean;
  canOverrideApproval: boolean;
  fullAccess: boolean;
  onEdit: (record: PayrollAdminInputLine) => void;
  onApprove: (record: PayrollAdminInputLine) => void;
}) {
  const state = <ListState loading={loading} error={error} empty={records.length === 0} />;
  if (loading || error || records.length === 0) return state;

  return (
    <div className="overflow-hidden rounded-xl border border-[var(--border-subtle)] md:overflow-x-auto">
      <div className="md:min-w-[800px]">
      <div className="app-surface-muted hidden grid-cols-[minmax(170px,1.35fr)_minmax(150px,1.2fr)_120px_115px_minmax(150px,1fr)] gap-3 border-0 border-b border-[var(--border-subtle)] px-4 py-2.5 text-xs font-medium text-[var(--muted-foreground)] md:grid">
        <span>Сотрудник</span><span>Операция</span><span>Сумма</span><span>Статус</span><span className="text-right">Действия</span>
      </div>
      <div className="divide-y divide-[var(--border-subtle)]">
        {records.map((record) => (
          <div key={record.id} className="grid gap-3 bg-[var(--surface-primary)] px-4 py-3 md:grid-cols-[minmax(170px,1.35fr)_minmax(150px,1.2fr)_120px_115px_minmax(150px,1fr)] md:items-center">
            <div className="min-w-0"><p className="truncate text-sm font-semibold text-[var(--foreground)]">{record.employee.display_name}</p><p className="app-text-muted mt-0.5 truncate text-xs">{record.employee.position || record.employee.department || "Сотрудник"}</p></div>
            <div className="min-w-0"><p className="truncate text-sm text-[var(--foreground)]">{record.component.name}</p>{record.reason ? <p className="app-text-muted mt-0.5 truncate text-xs" title={record.reason}>{record.reason}</p> : null}</div>
            <div><span className="app-text-muted mr-2 text-xs md:hidden">Сумма</span><span className="text-sm font-medium text-[var(--foreground)]">{formatPayrollMoney(record.amount)}</span></div>
            <RecordStatus status={record.status} />
            <RecordActions status={record.status} isAuthor={record.created_by.id === currentUserId} canManage={canManage} canApprove={canApprove} canOverrideApproval={canOverrideApproval} fullAccess={fullAccess} onEdit={() => onEdit(record)} onApprove={() => onApprove(record)} />
          </div>
        ))}
      </div>
      </div>
    </div>
  );
}

type ApprovalQueueItem = {
  key: string;
  group: "rate" | "work" | "input";
  title: string;
  subtitle: string;
  value: string;
  createdById: number;
  raw: PayrollAdminPayRate | PayrollAdminWorkRecord | PayrollAdminInputLine;
};

export function PayrollApprovalQueue({
  rates,
  workRecords,
  inputLines,
  currentUserId,
  canApprove,
  canOverrideApproval,
  onApproveRate,
  onApproveWork,
  onApproveInput,
}: {
  rates: PayrollAdminPayRate[];
  workRecords: PayrollAdminWorkRecord[];
  inputLines: PayrollAdminInputLine[];
  currentUserId?: number;
  canApprove: boolean;
  canOverrideApproval: boolean;
  onApproveRate: (record: PayrollAdminPayRate) => void;
  onApproveWork: (record: PayrollAdminWorkRecord) => void;
  onApproveInput: (record: PayrollAdminInputLine) => void;
}) {
  const items: ApprovalQueueItem[] = [
    ...rates.filter((item) => item.status === "draft").map((item) => ({ key: `rate-${item.id}`, group: "rate" as const, title: item.employee.display_name, subtitle: "Базовая ставка", value: formatPayrollMoney(item.amount, item.currency), createdById: item.created_by.id, raw: item })),
    ...workRecords.filter((item) => item.status === "draft").map((item) => ({ key: `work-${item.id}`, group: "work" as const, title: item.employee.display_name, subtitle: `Выработка: ${item.actual_points} из ${item.target_points} баллов`, value: "", createdById: item.created_by.id, raw: item })),
    ...inputLines.filter((item) => item.status === "draft").map((item) => ({ key: `input-${item.id}`, group: "input" as const, title: item.employee.display_name, subtitle: item.component.name, value: formatPayrollMoney(item.amount), createdById: item.created_by.id, raw: item })),
  ];

  if (items.length === 0) return <div className="app-surface-muted rounded-xl px-4 py-8 text-center text-sm text-[var(--muted-foreground)]">Нет черновиков, ожидающих решения.</div>;
  return (
    <div className="divide-y divide-[var(--border-subtle)] overflow-hidden rounded-xl border border-[var(--border-subtle)]">
      {items.map((item) => {
        const isAuthor = item.createdById === currentUserId;
        const approvalAllowed = canApprovePayrollDraft(isAuthor, canApprove, canOverrideApproval);
        const approvalLabel = canApprove ? "Утвердить" : "Только просмотр";
        const approvalTooltip = approvalAllowed
          ? "Утвердить"
          : "Недостаточно прав для утверждения этой записи.";
        const approve = () => {
          if (item.group === "rate") onApproveRate(item.raw as PayrollAdminPayRate);
          else if (item.group === "work") onApproveWork(item.raw as PayrollAdminWorkRecord);
          else onApproveInput(item.raw as PayrollAdminInputLine);
        };
        return (
          <div key={item.key} className="flex flex-col gap-3 bg-[var(--surface-primary)] px-4 py-3 sm:flex-row sm:items-center">
            <div className="min-w-0 flex-1"><p className="truncate text-sm font-semibold text-[var(--foreground)]">{item.title}</p><p className="app-text-muted mt-0.5 truncate text-xs">{item.subtitle}</p></div>
            {item.value ? <p className="shrink-0 text-sm font-semibold text-[var(--foreground)]">{item.value}</p> : null}
            <ActionButton label={approvalLabel} icon={<Check size={13} />} onClick={approve} tone="success" disabled={!approvalAllowed} tooltip={approvalTooltip} />
          </div>
        );
      })}
    </div>
  );
}
