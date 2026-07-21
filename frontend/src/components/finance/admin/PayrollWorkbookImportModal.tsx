"use client";

import { AlertTriangle, Check, FileSpreadsheet, Loader2, Upload } from "lucide-react";
import { useEffect, useId, useMemo, useState, type FormEvent } from "react";

import { Modal } from "@/components/ui";
import { apiClient } from "@/lib/api";
import type {
  PayrollAdminPeriod,
  PayrollWorkbookImportMode,
  PayrollWorkbookImportPreview,
  PayrollWorkbookImportResult,
} from "@/lib/api/finance";
import { getPayrollAdminError, isPayrollAdminStaleConflict } from "@/lib/payroll-admin";
import { getPayrollPeriodRange } from "@/lib/payroll";

type Props = {
  isOpen: boolean;
  period: PayrollAdminPeriod;
  onClose: () => void;
  onApplied: (result: PayrollWorkbookImportResult) => void | Promise<void>;
  onStale?: () => void | Promise<void>;
};

export function PayrollWorkbookImportModal({ isOpen, period, onClose, onApplied, onStale }: Props) {
  const formId = useId();
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<PayrollWorkbookImportPreview | null>(null);
  const [mappings, setMappings] = useState<Record<string, number | null>>({});
  const [mode, setMode] = useState<PayrollWorkbookImportMode>("skip_existing");
  const [loading, setLoading] = useState(false);
  const [applying, setApplying] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!isOpen) return;
    setFile(null);
    setPreview(null);
    setMappings({});
    setMode("skip_existing");
    setError(null);
  }, [isOpen, period.id]);

  const selectedSummary = useMemo(
    () => preview?.rows.reduce(
      (summary, row) => mappings[row.row_key]
        ? { rows: summary.rows + 1, entries: summary.entries + row.entry_count }
        : summary,
      { rows: 0, entries: 0 },
    ) ?? { rows: 0, entries: 0 },
    [mappings, preview],
  );

  const inspect = async () => {
    if (!file) return;
    setLoading(true);
    setError(null);
    try {
      const result = await apiClient.previewPayrollAdminWorkbookImport(period.id, file);
      setPreview(result);
      setMappings(Object.fromEntries(
        result.rows
          .filter((row) => row.matched_employee_id != null)
          .map((row) => [row.row_key, row.matched_employee_id as number]),
      ));
      setMode("skip_existing");
    } catch (loadError) {
      setPreview(null);
      setError(getPayrollAdminError(loadError, "Не удалось прочитать график из Excel."));
    } finally {
      setLoading(false);
    }
  };

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (!file || !preview || !selectedSummary.rows) return;
    setApplying(true);
    setError(null);
    try {
      const result = await apiClient.applyPayrollAdminWorkbookImport(period.id, {
        file,
        mode,
        mappings,
        expected_file_hash: preview.file_hash,
        expected_period_lock_version: preview.period_lock_version,
      });
      await onApplied(result);
    } catch (applyError) {
      if (isPayrollAdminStaleConflict(applyError) && onStale) {
        await onStale();
        return;
      }
      setError(getPayrollAdminError(applyError, "Не удалось импортировать выработку."));
    } finally {
      setApplying(false);
    }
  };

  const footer = (
    <div className="flex flex-col-reverse gap-2 border-t border-[var(--border-subtle)] pb-1 pt-4 sm:flex-row sm:justify-end">
      <button type="button" className="app-action-secondary rounded-lg px-4 py-2.5 text-sm font-medium" disabled={applying} onClick={onClose}>Отмена</button>
      {preview ? (
        <button type="submit" form={formId} className="app-action-primary inline-flex items-center justify-center gap-2 rounded-lg px-4 py-2.5 text-sm font-semibold disabled:cursor-not-allowed disabled:opacity-60" disabled={applying || !selectedSummary.rows}>
          {applying ? <Loader2 className="animate-spin" size={16} /> : <Check size={16} />}
          Импортировать {selectedSummary.entries} записей
        </button>
      ) : (
        <button type="button" className="app-action-primary inline-flex items-center justify-center gap-2 rounded-lg px-4 py-2.5 text-sm font-semibold disabled:cursor-not-allowed disabled:opacity-60" disabled={!file || loading} onClick={() => void inspect()}>
          {loading ? <Loader2 className="animate-spin" size={16} /> : <Upload size={16} />}
          Проверить файл
        </button>
      )}
    </div>
  );

  return (
    <Modal isOpen={isOpen} onClose={applying ? () => undefined : onClose} title="Импорт выработки из Excel" size="xl" showCloseButton={!applying} closeOnEsc={!applying} footer={footer}>
      <form id={formId} onSubmit={(event) => void submit(event)} className="space-y-4">
        <div>
          <p className="text-sm font-semibold text-[var(--foreground)]">{period.name || period.code}</p>
          <p className="app-text-muted mt-1 text-xs">{getPayrollPeriodRange(period)}. Из файла будет взят только этот период.</p>
        </div>

        <label className="app-surface-muted flex cursor-pointer items-center gap-3 rounded-xl border border-dashed border-[var(--border-strong)] p-4">
          <FileSpreadsheet className="app-accent-text shrink-0" size={24} />
          <span className="min-w-0 flex-1">
            <span className="block truncate text-sm font-semibold text-[var(--foreground)]">{file?.name || "Выберите файл .xlsx"}</span>
            <span className="app-text-muted mt-1 block text-xs">Сотрудники — по строкам, дни — по столбцам, в ячейках — дневные баллы.</span>
          </span>
          <input
            className="sr-only"
            type="file"
            accept=".xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            disabled={loading || applying}
            onChange={(event) => {
              setFile(event.target.files?.[0] || null);
              setPreview(null);
              setMappings({});
              setError(null);
            }}
          />
        </label>

        {preview ? (
          <>
            <div className="grid gap-2 sm:grid-cols-4">
              {[
                ["Строк сотрудников", preview.summary.rows],
                ["Дневных записей", preview.summary.entries],
                ["Найдено автоматически", preview.summary.matched],
                ["Уже существует", preview.summary.existing],
              ].map(([label, value]) => (
                <div key={label} className="app-surface-muted rounded-xl p-3"><p className="app-text-muted text-xs">{label}</p><p className="mt-1 text-lg font-semibold text-[var(--foreground)]">{value}</p></div>
              ))}
            </div>

            {preview.summary.needs_mapping ? (
              <div className="app-feedback-warning flex items-start gap-2 rounded-xl px-3 py-2.5 text-sm">
                <AlertTriangle className="mt-0.5 shrink-0" size={16} />
                <span>Не удалось однозначно определить {preview.summary.needs_mapping} строк. Выберите нужных сотрудников; остальные строки будут пропущены.</span>
              </div>
            ) : null}

            <div className="max-h-[42vh] overflow-y-auto rounded-xl border border-[var(--border-subtle)]">
              <div className="app-surface-muted sticky top-0 z-10 hidden grid-cols-[minmax(180px,1fr)_minmax(250px,1.4fr)_150px] gap-3 border-b border-[var(--border-subtle)] px-4 py-2.5 text-xs font-medium text-[var(--muted-foreground)] md:grid">
                <span>Имя в Excel</span>
                <span>Сотрудник в системе</span>
                <span className="text-right">Данные</span>
              </div>
              <div className="divide-y divide-[var(--border-subtle)]">
                {preview.rows.map((row) => {
                  const candidateIds = new Set(row.candidate_employee_ids);
                  const selectedEmployeeId = mappings[row.row_key];
                  const matchedAutomatically = Boolean(
                    selectedEmployeeId
                      && row.match_status === "matched"
                      && selectedEmployeeId === row.matched_employee_id,
                  );
                  const orderedEmployees = [...preview.employees].sort((left, right) => {
                    const candidateDelta = Number(candidateIds.has(right.id)) - Number(candidateIds.has(left.id));
                    return candidateDelta || left.display_name.localeCompare(right.display_name, "ru");
                  });
                  return (
                    <div key={row.row_key} className="grid gap-3 bg-[var(--surface-primary)] px-4 py-3 md:grid-cols-[minmax(180px,1fr)_minmax(250px,1.4fr)_150px] md:items-center">
                      <div className="min-w-0">
                        <p className="truncate text-sm font-semibold text-[var(--foreground)]" title={row.source_name}>{row.source_name}</p>
                        <p className="app-text-muted mt-1 text-[11px]">{row.sheet_name}, строка {row.row_number}</p>
                        <span className={`${matchedAutomatically ? "app-feedback-success" : selectedEmployeeId ? "app-selected" : "app-surface-muted"} mt-1.5 inline-flex rounded-full px-2 py-1 text-[10px] font-semibold leading-none`}>
                          {matchedAutomatically ? "Найден автоматически" : selectedEmployeeId ? "Выбран вручную" : "Будет пропущен"}
                        </span>
                      </div>
                      <select
                        className={`app-select w-full rounded-lg px-3 py-2 text-sm ${!mappings[row.row_key] ? "border-[var(--warning-border)]" : ""}`}
                        value={selectedEmployeeId || ""}
                        onChange={(event) => setMappings((current) => ({
                          ...current,
                          [row.row_key]: event.target.value ? Number(event.target.value) : null,
                        }))}
                        aria-label={`Сотрудник для строки ${row.source_name}`}
                      >
                        <option value="">Выберите сотрудника…</option>
                        {orderedEmployees.map((employee) => <option key={employee.id} value={employee.id}>{candidateIds.has(employee.id) ? "★ " : ""}{employee.display_name}{employee.is_active ? "" : " (неактивен)"}</option>)}
                      </select>
                      <div className="text-xs text-[var(--muted-foreground)] md:text-right">
                        <p><b className="text-[var(--foreground)]">{row.entry_count}</b> дней · <b className="text-[var(--foreground)]">{row.points_total}</b> балл.</p>
                        {row.existing_count ? <p className="mt-1 text-[var(--warning-foreground)]">{row.existing_period_record ? "Есть итог за период" : `Совпадений по датам: ${row.existing_count}`}</p> : null}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>

            <fieldset>
              <legend className="app-field-label">Если запись сотрудника за дату уже существует</legend>
              <div className="grid gap-2 sm:grid-cols-2">
                <label className={`${mode === "skip_existing" ? "app-selected" : "app-surface-muted"} flex cursor-pointer items-start gap-3 rounded-xl p-3.5`}>
                  <input type="radio" className="app-radio mt-0.5" checked={mode === "skip_existing"} onChange={() => setMode("skip_existing")} />
                  <span><span className="block text-sm font-semibold text-[var(--foreground)]">Пропустить существующие</span><span className="app-text-muted mt-1 block text-xs">Безопасный режим: имеющиеся дневные записи не изменятся.</span></span>
                </label>
                <label className={`${mode === "replace_existing" ? "app-selected" : "app-surface-muted"} flex cursor-pointer items-start gap-3 rounded-xl p-3.5`}>
                  <input type="radio" className="app-radio mt-0.5" checked={mode === "replace_existing"} onChange={() => setMode("replace_existing")} />
                  <span><span className="block text-sm font-semibold text-[var(--foreground)]">Заменить существующие</span><span className="app-text-muted mt-1 block text-xs">Баллы за совпадающие даты будут заменены значениями из файла.</span></span>
                </label>
              </div>
            </fieldset>

            {selectedSummary.rows < preview.summary.rows ? <p className="app-surface-muted rounded-xl px-3 py-2.5 text-sm text-[var(--muted-foreground)]">Будет импортировано строк: {selectedSummary.rows} из {preview.summary.rows}. Строки без выбранного сотрудника будут пропущены.</p> : null}
            {preview.summary.invalid ? <p className="app-feedback-warning rounded-xl px-3 py-2.5 text-sm">Пропущено некорректных числовых ячеек: {preview.summary.invalid}.</p> : null}
          </>
        ) : null}

        {error ? <div className="app-feedback-danger rounded-xl px-4 py-3 text-sm">{error}</div> : null}
      </form>
    </Modal>
  );
}
