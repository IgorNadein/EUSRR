"use client";

import {
  CalendarDays,
  Check,
  ClipboardList,
  Loader2,
  Pencil,
  Save,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useState, type FormEvent } from "react";

import { apiClient } from "@/lib/api";
import type {
  PayrollOwnDailyWorkEntry,
  PayrollOwnDailyWorkWorkspace,
  PayrollOwnWorkPeriod,
} from "@/lib/api/finance";
import { approvalStatusMeta, getPayrollAdminError, periodStatusMeta } from "@/lib/payroll-admin";
import { formatPayrollDate, getPayrollPeriodRange } from "@/lib/payroll";

function localDateInput(): string {
  const now = new Date();
  const year = now.getFullYear();
  const month = String(now.getMonth() + 1).padStart(2, "0");
  const day = String(now.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function defaultWorkDate(period: PayrollOwnWorkPeriod): string {
  const today = localDateInput();
  if (today < period.date_from) return period.date_from;
  if (today > period.date_to) return period.date_to;
  return today;
}

function formatPoints(value: string | null | undefined): string {
  if (value == null || value === "") return "0";
  const number = Number(value);
  if (!Number.isFinite(number)) return value;
  return number.toLocaleString("ru-RU", { maximumFractionDigits: 4 });
}

function currentEntryForDate(
  entries: PayrollOwnDailyWorkEntry[],
  workDate: string,
): PayrollOwnDailyWorkEntry | null {
  return entries.find((entry) => entry.work_date === workDate) || null;
}

export function PayrollDailyWorkSection() {
  const [workspace, setWorkspace] = useState<PayrollOwnDailyWorkWorkspace | null>(null);
  const [selectedPeriodId, setSelectedPeriodId] = useState<number | null>(null);
  const [workDate, setWorkDate] = useState("");
  const [actualPoints, setActualPoints] = useState("");
  const [note, setNote] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const fillForm = useCallback((
    payload: PayrollOwnDailyWorkWorkspace,
    preferredDate?: string,
  ) => {
    const period = payload.periods.find((item) => item.id === payload.selected_period_id);
    if (!period) {
      setWorkDate("");
      setActualPoints("");
      setNote("");
      return;
    }
    const nextDate = preferredDate && preferredDate >= period.date_from && preferredDate <= period.date_to
      ? preferredDate
      : defaultWorkDate(period);
    const entry = currentEntryForDate(payload.entries, nextDate);
    setWorkDate(nextDate);
    setActualPoints(entry?.actual_points || "");
    setNote(entry?.note || "");
  }, []);

  const loadWorkspace = useCallback(async (
    periodId?: number,
    preferredDate?: string,
  ) => {
    setLoading(true);
    setError(null);
    try {
      const payload = await apiClient.getMyPayrollDailyWork(periodId);
      setWorkspace(payload);
      setSelectedPeriodId(payload.selected_period_id);
      fillForm(payload, preferredDate);
    } catch (loadError) {
      setError(getPayrollAdminError(loadError, "Не удалось загрузить ежедневную выработку."));
    } finally {
      setLoading(false);
    }
  }, [fillForm]);

  useEffect(() => {
    void loadWorkspace();
  }, [loadWorkspace]);

  const selectedPeriod = useMemo(
    () => workspace?.periods.find((period) => period.id === selectedPeriodId) || null,
    [selectedPeriodId, workspace?.periods],
  );
  const selectedEntry = useMemo(
    () => currentEntryForDate(workspace?.entries || [], workDate),
    [workDate, workspace?.entries],
  );
  const maxWorkDate = selectedPeriod
    ? [selectedPeriod.date_to, localDateInput()].sort()[0]
    : "";
  const numericActual = Number(actualPoints);
  const canSubmit = Boolean(
    selectedPeriod?.editable
    && workDate
    && workDate <= maxWorkDate
    && actualPoints.trim()
    && Number.isFinite(numericActual)
    && numericActual >= 0,
  );

  const selectWorkDate = (date: string) => {
    setWorkDate(date);
    const entry = currentEntryForDate(workspace?.entries || [], date);
    setActualPoints(entry?.actual_points || "");
    setNote(entry?.note || "");
    setError(null);
    setNotice(null);
  };

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (!selectedPeriod || !canSubmit) return;
    setSaving(true);
    setError(null);
    setNotice(null);
    try {
      const result = await apiClient.saveMyPayrollDailyWorkEntry({
        period_id: selectedPeriod.id,
        work_date: workDate,
        actual_points: actualPoints,
        note: note.trim(),
        ...(selectedEntry ? { expected_lock_version: selectedEntry.lock_version } : {}),
      });
      setNotice(result.operation === "created" ? "Выработка за день добавлена." : "Выработка за день обновлена.");
      await loadWorkspace(selectedPeriod.id, workDate);
    } catch (saveError) {
      setError(getPayrollAdminError(saveError, "Не удалось сохранить ежедневную выработку."));
    } finally {
      setSaving(false);
    }
  };

  if (loading && !workspace) {
    return (
      <section className="app-surface flex min-h-64 items-center justify-center rounded-2xl">
        <Loader2 className="app-accent-text animate-spin" size={28} />
      </section>
    );
  }

  if (!workspace?.periods.length) {
    return (
      <section className="app-surface rounded-2xl p-5 sm:p-8">
        <div className="app-surface-muted py-10 text-center">
          <ClipboardList className="app-text-muted mx-auto" size={28} />
          <p className="app-text-muted mt-3 text-sm">Расчётные периоды пока не созданы.</p>
        </div>
      </section>
    );
  }

  const aggregate = selectedPeriod?.record || null;
  const summary = selectedPeriod?.summary || null;
  const aggregateStatus = aggregate ? approvalStatusMeta[aggregate.status] : null;
  const periodStatus = selectedPeriod ? periodStatusMeta[selectedPeriod.status] : null;

  return (
    <div className="space-y-4">
      <section className="app-surface rounded-2xl p-4 sm:p-5">
        <form onSubmit={submit}>
          <div className="flex items-center gap-2">
            <CalendarDays className="app-accent-text" size={18} />
            <h2 className="text-base font-semibold text-[var(--foreground)]">
              {selectedEntry ? "Изменить запись за день" : "Добавить запись за день"}
            </h2>
          </div>
          <div className="mt-4 grid gap-4 sm:grid-cols-3">
            <label>
              <span className="app-field-label">Дата</span>
              <input
                type="date"
                className="app-input w-full rounded-lg px-3 py-2.5 text-sm"
                min={selectedPeriod?.date_from}
                max={maxWorkDate}
                value={workDate}
                disabled={!selectedPeriod?.editable}
                required
                onChange={(event) => selectWorkDate(event.target.value)}
              />
            </label>
            <label>
              <span className="app-field-label">Норма баллов</span>
              <input
                type="text"
                className="app-input w-full rounded-lg px-3 py-2.5 text-sm"
                value={formatPoints(selectedEntry?.target_points || workspace.daily_target_points)}
                disabled
                readOnly
              />
            </label>
            <label>
              <span className="app-field-label">Фактические баллы</span>
              <input
                type="number"
                className="app-input w-full rounded-lg px-3 py-2.5 text-sm"
                inputMode="decimal"
                min="0"
                step="0.0001"
                value={actualPoints}
                disabled={!selectedPeriod?.editable}
                required
                onChange={(event) => setActualPoints(event.target.value)}
              />
            </label>
          </div>
          <label className="mt-4 block">
            <span className="app-field-label">Комментарий</span>
            <textarea
              className="app-input min-h-20 w-full resize-y rounded-lg px-3 py-2.5 text-sm"
              value={note}
              disabled={!selectedPeriod?.editable}
              onChange={(event) => setNote(event.target.value)}
            />
          </label>

          {!selectedPeriod?.editable ? (
            <div className="app-feedback-warning mt-4 rounded-lg px-3 py-2.5 text-sm">
              Период закрыт для изменения выработки.
            </div>
          ) : null}
          {error ? <div className="app-feedback-danger mt-4 rounded-lg px-3 py-2.5 text-sm">{error}</div> : null}
          {notice ? <div className="app-feedback-success mt-4 rounded-lg px-3 py-2.5 text-sm">{notice}</div> : null}

          <div className="mt-4 flex justify-end">
            <button
              type="submit"
              className="app-action-primary inline-flex items-center justify-center gap-2 rounded-lg px-4 py-2.5 text-sm font-semibold disabled:cursor-not-allowed disabled:opacity-50"
              disabled={!canSubmit || saving}
            >
              {saving ? <Loader2 className="animate-spin" size={16} /> : selectedEntry ? <Save size={16} /> : <Check size={16} />}
              {selectedEntry ? "Сохранить изменения" : "Добавить выработку"}
            </button>
          </div>
        </form>
      </section>

      <section className="app-surface rounded-2xl p-4 sm:p-5">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
          <div className="min-w-0">
            <p className="app-card-caption">Выработка</p>
            <h2 className="mt-1 text-lg font-semibold text-[var(--foreground)]">Ежедневные баллы</h2>
          </div>
          <select
            className="app-select min-w-0 rounded-lg px-3 py-2.5 text-sm sm:min-w-56"
            value={selectedPeriodId || ""}
            onChange={(event) => void loadWorkspace(Number(event.target.value))}
            aria-label="Расчётный период выработки"
          >
            {workspace.periods.map((period) => (
              <option key={period.id} value={period.id}>{period.name || period.code}</option>
            ))}
          </select>
        </div>

        {selectedPeriod ? (
          <div className="mt-4 grid gap-3 sm:grid-cols-3">
            <div className="app-surface-muted rounded-xl p-3">
              <p className="app-text-muted text-xs">Период</p>
              <p className="mt-1 text-sm font-medium text-[var(--foreground)]">{getPayrollPeriodRange(selectedPeriod)}</p>
              {periodStatus ? <span className={`app-status-pill mt-2 ${periodStatus.className}`}>{periodStatus.label}</span> : null}
            </div>
            <div className="app-surface-muted rounded-xl p-3">
              <p className="app-text-muted text-xs">Норма за период</p>
              <p className="mt-1 text-lg font-semibold text-[var(--foreground)]">{formatPoints(summary?.target_points)}</p>
              <p className="app-text-muted mt-1 text-[11px]">
                {summary?.target_source === "saved_record" ? "Из сохранённой записи" : `По графику: ${summary?.workdays_count || 0} дн.`}
              </p>
            </div>
            <div className="app-surface-muted rounded-xl p-3">
              <div className="flex items-start justify-between gap-2">
                <div>
                  <p className="app-text-muted text-xs">Фактически за период</p>
                  <p className="mt-1 text-lg font-semibold text-[var(--foreground)]">
                    {formatPoints(summary?.actual_points)} / {formatPoints(summary?.target_points)}
                  </p>
                </div>
                {aggregateStatus ? <span className={`app-status-pill ${aggregateStatus.className}`}>{aggregateStatus.label}</span> : null}
              </div>
            </div>
          </div>
        ) : null}
      </section>

      <section className="app-surface rounded-2xl p-4 sm:p-5">
        <div className="mb-4 flex items-center justify-between gap-3">
          <h2 className="text-base font-semibold text-[var(--foreground)]">Записи за период</h2>
          <span className="app-counter h-6 min-w-6 px-1.5 text-xs">{workspace.entries.length}</span>
        </div>
        {workspace.entries.length ? (
          <div className="space-y-2">
            {workspace.entries.map((entry) => (
              <button
                type="button"
                key={entry.id}
                className={`app-surface-muted grid w-full grid-cols-[minmax(0,1fr)_auto] items-center gap-3 rounded-xl p-3 text-left transition hover:border-[var(--border-strong)] ${entry.work_date === workDate ? "app-selected" : ""}`}
                onClick={() => selectWorkDate(entry.work_date)}
              >
                <span className="min-w-0">
                  <span className="block text-sm font-semibold text-[var(--foreground)]">{formatPayrollDate(entry.work_date)}</span>
                  <span className="app-text-muted mt-1 block truncate text-xs">{entry.note || "Без комментария"}</span>
                </span>
                <span className="flex shrink-0 items-center gap-3">
                  <span className="text-right">
                    <span className="block text-sm font-semibold text-[var(--foreground)]">{formatPoints(entry.actual_points)}</span>
                    <span className="app-text-muted block text-[11px]">из {formatPoints(entry.target_points)}</span>
                  </span>
                  {selectedPeriod?.editable ? <Pencil className="app-text-muted" size={15} /> : null}
                </span>
              </button>
            ))}
          </div>
        ) : (
          <div className="app-surface-muted rounded-xl px-4 py-8 text-center">
            <p className="app-text-muted text-sm">За выбранный период записей пока нет.</p>
          </div>
        )}
      </section>
    </div>
  );
}
