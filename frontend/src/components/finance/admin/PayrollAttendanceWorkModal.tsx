"use client";

import {
  AlertTriangle,
  CalendarCheck2,
  Check,
  Clock3,
  Loader2,
  RefreshCw,
} from "lucide-react";
import { useCallback, useEffect, useId, useMemo, useState, type FormEvent } from "react";

import { Modal } from "@/components/ui";
import { apiClient } from "@/lib/api";
import type {
  PayrollAdminPeriod,
  PayrollAttendanceWorkAction,
  PayrollAttendanceWorkApplyResult,
  PayrollAttendanceWorkIssue,
  PayrollAttendanceWorkMode,
  PayrollAttendanceWorkPreview,
  PayrollAttendanceWorkPreviewItem,
} from "@/lib/api/finance";
import {
  getPayrollAdminError,
  isPayrollAdminStaleConflict,
  approvalStatusMeta,
} from "@/lib/payroll-admin";
import {
  formatPayrollAttendanceEmployeeCount,
  getPayrollAttendanceIssueMessage,
  getPayrollAttendanceModeSummary,
  payrollAttendanceActionMeta,
} from "@/lib/payroll-attendance";
import { formatPayrollDateTime, getPayrollPeriodRange } from "@/lib/payroll";

type PayrollAttendanceWorkModalProps = {
  isOpen: boolean;
  period: PayrollAdminPeriod;
  onClose: () => void;
  onApplied: (result: PayrollAttendanceWorkApplyResult) => void | Promise<void>;
  onStale?: () => void | Promise<void>;
};

function issueMessage(issue: PayrollAttendanceWorkIssue): string {
  return getPayrollAttendanceIssueMessage(issue);
}

function ActionBadge({ action }: { action: PayrollAttendanceWorkAction }) {
  const meta = payrollAttendanceActionMeta[action];
  return (
    <span className={`${meta.className} inline-flex w-fit rounded-full px-2 py-1 text-[10px] font-semibold leading-none`}>
      {meta.label}
    </span>
  );
}

function ExistingRecord({ item }: { item: PayrollAttendanceWorkPreviewItem }) {
  const record = item.existing_record;
  if (!record) return <span className="app-text-muted text-xs">Нет записи</span>;
  const status = approvalStatusMeta[record.status];
  return (
    <div className="flex min-w-0 flex-col items-start gap-1">
      <span className={`${status.className} inline-flex rounded-full px-2 py-1 text-[10px] font-semibold leading-none`}>
        {status.label}
      </span>
      <span className="app-text-muted text-[11px]">Ревизия {record.revision}</span>
    </div>
  );
}

function ItemIssues({ item }: { item: PayrollAttendanceWorkPreviewItem }) {
  const issues = [...item.blockers, ...item.warnings];
  if (!issues.length) return null;
  return (
    <div className="mt-2 space-y-1">
      {issues.map((issue, index) => (
        <p
          key={`${issue.code}-${index}`}
          className={`${index < item.blockers.length ? "text-[var(--danger-foreground)]" : "app-text-muted"} flex items-start gap-1.5 text-[11px] leading-relaxed`}
        >
          <AlertTriangle className="mt-0.5 shrink-0" size={12} />
          <span>{issueMessage(issue)}</span>
        </p>
      ))}
    </div>
  );
}

function PreviewTable({
  items,
  mode,
}: {
  items: PayrollAttendanceWorkPreviewItem[];
  mode: PayrollAttendanceWorkMode;
}) {
  if (!items.length) {
    return (
      <div className="app-surface-muted rounded-xl px-4 py-8 text-center text-sm text-[var(--muted-foreground)]">
        За этот период данных посещаемости нет.
      </div>
    );
  }

  return (
    <div className="overflow-hidden rounded-xl border border-[var(--border-subtle)] md:overflow-x-auto">
      <div className="md:min-w-[980px]">
        <div className="app-surface-muted hidden grid-cols-[minmax(190px,1.4fr)_150px_150px_115px_150px] gap-3 border-0 border-b border-[var(--border-subtle)] px-4 py-2.5 text-xs font-medium text-[var(--muted-foreground)] md:grid">
          <span>Сотрудник</span>
          <span>Посещаемость</span>
          <span>Выработка</span>
          <span>Текущая запись</span>
          <span>Результат</span>
        </div>
        <div className="divide-y divide-[var(--border-subtle)]">
          {items.map((item) => {
            const action = item.actions[mode];
            return (
              <div
                key={item.employee.id}
                className="grid gap-3 bg-[var(--surface-primary)] px-4 py-3 md:grid-cols-[minmax(190px,1.4fr)_150px_150px_115px_150px] md:items-start"
              >
                <div className="min-w-0">
                  <p className="truncate text-sm font-semibold text-[var(--foreground)]">
                    {item.employee.display_name}
                  </p>
                  <p className="app-text-muted mt-0.5 truncate text-xs">
                    {item.employee.position || item.employee.department || "Сотрудник"}
                  </p>
                  <ItemIssues item={item} />
                </div>
                <div className="text-xs text-[var(--foreground)]">
                  <span className="app-text-muted mr-1 md:hidden">Посещаемость:</span>
                  <p>Норма: <b>{item.expected_hours} ч</b></p>
                  <p className="mt-1">Отработано: <b>{item.worked_hours} ч</b></p>
                  <p className="app-text-muted mt-1 text-[11px]">
                    Записей: {item.attendance_days} · рабочих дней: {item.effective_workdays}
                  </p>
                  {item.technical_issue_days ? (
                    <p className="mt-1 text-[11px] text-[var(--danger-foreground)]">
                      Тех. проблем: {item.technical_issue_days}
                    </p>
                  ) : null}
                </div>
                <div className="text-xs text-[var(--foreground)]">
                  <span className="app-text-muted mr-1 md:hidden">Выработка:</span>
                  <p>Норма: <b>{item.target_points} ч</b></p>
                  <p className="mt-1">Факт: <b>{item.actual_points} ч</b></p>
                  <span className="app-selected mt-2 inline-flex rounded-full px-2 py-1 text-[10px] font-semibold leading-none">
                    Из посещаемости
                  </span>
                </div>
                <div>
                  <span className="app-text-muted mr-1 text-xs md:hidden">Текущая запись:</span>
                  <ExistingRecord item={item} />
                </div>
                <div>
                  <span className="app-text-muted mr-1 text-xs md:hidden">Результат:</span>
                  <ActionBadge action={action} />
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

export function PayrollAttendanceWorkModal({
  isOpen,
  period,
  onClose,
  onApplied,
  onStale,
}: PayrollAttendanceWorkModalProps) {
  const formId = useId();
  const [preview, setPreview] = useState<PayrollAttendanceWorkPreview | null>(null);
  const [mode, setMode] = useState<PayrollAttendanceWorkMode>("missing_only");
  const [reason, setReason] = useState("");
  const [loading, setLoading] = useState(true);
  const [applying, setApplying] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadPreview = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const payload = await apiClient.getPayrollAdminAttendanceWorkPreview(period.id);
      setPreview(payload);
      setMode("missing_only");
      setReason("");
    } catch (loadError) {
      setError(getPayrollAdminError(loadError, "Не удалось подготовить выработку по посещаемости."));
    } finally {
      setLoading(false);
    }
  }, [period.id]);

  useEffect(() => {
    if (isOpen) void loadPreview();
  }, [isOpen, loadPreview]);

  const modeSummary = useMemo(
    () => preview ? getPayrollAttendanceModeSummary(preview, mode) : null,
    [mode, preview],
  );
  const reasonRequired = mode === "replace_existing";
  const canApply = Boolean(
    preview
      && modeSummary
      && modeSummary.changes > 0
      && (!reasonRequired || reason.trim()),
  );

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (!preview || !canApply) return;
    setApplying(true);
    setError(null);
    try {
      const result = await apiClient.applyPayrollAdminAttendanceWork(period.id, {
        mode,
        preview_token: preview.preview_token,
        expected_period_lock_version: period.lock_version,
        reason: mode === "replace_existing" ? reason.trim() : "",
      });
      await onApplied(result);
    } catch (applyError) {
      if (isPayrollAdminStaleConflict(applyError) && onStale) {
        await onStale();
        return;
      }
      setError(getPayrollAdminError(applyError, "Не удалось сохранить выработку по посещаемости."));
    } finally {
      setApplying(false);
    }
  };

  const footer = (
    <div className="flex flex-col-reverse gap-2 border-t border-[var(--border-subtle)] pb-1 pt-4 sm:flex-row sm:justify-end">
      <button
        type="button"
        className="app-action-secondary rounded-lg px-4 py-2.5 text-sm font-medium"
        disabled={applying}
        onClick={onClose}
      >
        Отмена
      </button>
      <button
        type="submit"
        form={formId}
        className="app-action-primary inline-flex items-center justify-center gap-2 rounded-lg px-4 py-2.5 text-sm font-semibold disabled:cursor-not-allowed disabled:opacity-60"
        disabled={applying || loading || !canApply}
      >
        {applying ? <Loader2 className="animate-spin" size={16} /> : <Check size={16} />}
        {modeSummary?.changes ? `Сохранить изменения (${modeSummary.changes})` : "Нет изменений"}
      </button>
    </div>
  );

  return (
    <Modal
      isOpen={isOpen}
      onClose={applying ? () => undefined : onClose}
      title="Расчёт выработки по посещаемости"
      size="xl"
      showCloseButton={!applying}
      closeOnEsc={!applying}
      footer={footer}
    >
      <form id={formId} onSubmit={(event) => void submit(event)}>
        {loading ? (
          <div className="flex min-h-72 items-center justify-center gap-2 text-sm text-[var(--muted-foreground)]">
            <Loader2 className="app-accent-text animate-spin" size={20} />
            Подготавливаем предпросмотр…
          </div>
        ) : !preview ? (
          <div className="py-5">
            <div className="app-feedback-danger rounded-xl px-4 py-3 text-sm">
              {error || "Предпросмотр недоступен."}
            </div>
            <button
              type="button"
              className="app-action-secondary mt-3 inline-flex items-center gap-2 rounded-lg px-4 py-2.5 text-sm font-medium"
              onClick={() => void loadPreview()}
            >
              <RefreshCw size={15} /> Повторить
            </button>
          </div>
        ) : (
          <div className="space-y-4">
            <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
              <div>
                <p className="text-sm font-semibold text-[var(--foreground)]">{period.name || period.code}</p>
                <p className="app-text-muted mt-1 text-xs">{getPayrollPeriodRange(period)}</p>
              </div>
              <p className="app-text-muted text-xs">Предпросмотр: {formatPayrollDateTime(preview.generated_at)}</p>
            </div>

            <div className="app-selected flex items-start gap-3 rounded-xl p-4">
              <CalendarCheck2 className="app-accent-text mt-0.5 shrink-0" size={19} />
              <div>
                <p className="text-sm font-semibold text-[var(--foreground)]">
                  1 час = 1 единица выработки
                </p>
                <p className="app-text-muted mt-1 text-xs leading-relaxed">
                  {preview.policy.description || preview.policy.label}
                </p>
                <p className="mt-2 text-xs font-medium text-[var(--foreground)]">
                  Часы попадут в норму и факт выработки, но при текущей политике не изменяют начисление по баллам.
                </p>
              </div>
            </div>

            {preview.summary.existing > 0 ? (
              <fieldset>
                <legend className="app-field-label">Что делать с существующими записями</legend>
                <div className="grid gap-2 sm:grid-cols-2">
                  <label className={`${mode === "missing_only" ? "app-selected" : "app-surface-muted"} flex cursor-pointer items-start gap-3 rounded-xl p-3.5`}>
                    <input
                      type="radio"
                      className="app-radio mt-0.5"
                      name="attendance-work-mode"
                      value="missing_only"
                      checked={mode === "missing_only"}
                      onChange={() => setMode("missing_only")}
                    />
                    <span>
                      <span className="block text-sm font-semibold text-[var(--foreground)]">Только отсутствующие</span>
                      <span className="app-text-muted mt-1 block text-xs leading-relaxed">
                        Рекомендуется. Существующие записи останутся без изменений.
                      </span>
                    </span>
                  </label>
                  <label className={`${mode === "replace_existing" ? "app-selected" : "app-surface-muted"} flex cursor-pointer items-start gap-3 rounded-xl p-3.5`}>
                    <input
                      type="radio"
                      className="app-radio mt-0.5"
                      name="attendance-work-mode"
                      value="replace_existing"
                      checked={mode === "replace_existing"}
                      onChange={() => setMode("replace_existing")}
                    />
                    <span>
                      <span className="block text-sm font-semibold text-[var(--foreground)]">Пересчитать существующие</span>
                      <span className="app-text-muted mt-1 block text-xs leading-relaxed">
                        Обновит доступные черновики, для утверждённых создаст новые ревизии.
                      </span>
                    </span>
                  </label>
                </div>
              </fieldset>
            ) : null}

            {mode === "replace_existing" ? (
              <div className="app-feedback-warning rounded-xl p-3.5 text-sm">
                <div className="flex items-start gap-2">
                  <AlertTriangle className="mt-0.5 shrink-0" size={16} />
                  <p className="leading-relaxed">
                    Утверждённые показатели не перезаписываются. Для них будут созданы новые черновики-ревизии, которые потребуется отдельно проверить и утвердить.
                  </p>
                </div>
                <label className="mt-3 block">
                  <span className="app-field-label">Причина перерасчёта *</span>
                  <textarea
                    className="app-input min-h-20 w-full resize-y rounded-lg px-3 py-2.5 text-sm"
                    value={reason}
                    required
                    placeholder={`Перерасчёт по посещаемости за ${period.name || period.code}`}
                    onChange={(event) => setReason(event.target.value)}
                  />
                </label>
              </div>
            ) : null}

            {modeSummary ? (
              <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
                {[
                  { label: "В посещаемости", value: preview.summary.attendance_employees },
                  { label: "Новых черновиков", value: modeSummary.create },
                  { label: "Обновлений и ревизий", value: modeSummary.update + modeSummary.revise },
                  { label: "Требует внимания", value: modeSummary.skip + modeSummary.blocked },
                ].map((item) => (
                  <div key={item.label} className="app-surface-muted rounded-xl p-3">
                    <p className="app-text-muted text-xs">{item.label}</p>
                    <p className="mt-1 text-lg font-semibold text-[var(--foreground)]">{item.value}</p>
                  </div>
                ))}
              </div>
            ) : null}

            {preview.summary.blocked ? (
              <div className="app-feedback-warning flex items-start gap-2 rounded-xl px-3 py-2.5 text-sm">
                <Clock3 className="mt-0.5 shrink-0" size={16} />
                <span>
                  Для {formatPayrollAttendanceEmployeeCount(preview.summary.blocked)} есть незавершённые или технически проблемные дни. Эти строки не будут сохранены, пока посещаемость не исправлена.
                </span>
              </div>
            ) : null}

            <PreviewTable items={preview.items} mode={mode} />

            <div className="app-surface-muted rounded-xl px-3 py-2.5 text-xs leading-relaxed text-[var(--muted-foreground)]">
              Система создаёт только черновики и не утверждает их автоматически. После импорта проверьте строки во вкладке «Выработка» и передайте их на согласование.
            </div>

            {error ? (
              <div className="app-feedback-danger flex items-start justify-between gap-3 rounded-xl px-4 py-3 text-sm">
                <span>{error}</span>
                <button type="button" className="shrink-0 underline" onClick={() => void loadPreview()}>
                  Обновить предпросмотр
                </button>
              </div>
            ) : null}
          </div>
        )}
      </form>
    </Modal>
  );
}
