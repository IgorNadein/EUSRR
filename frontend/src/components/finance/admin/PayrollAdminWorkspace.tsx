"use client";

import {
  AlertCircle,
  ArrowLeft,
  Banknote,
  CalendarCheck2,
  Calculator,
  Check,
  CheckCircle2,
  ChevronRight,
  Clock3,
  FileCheck2,
  Loader2,
  Maximize2,
  Minimize2,
  Pencil,
  Plus,
  Search,
  Send,
  ShieldCheck,
  UsersRound,
} from "lucide-react";
import Link from "next/link";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";

import {
  PayrollConfirmModal,
  PayrollBulkPayRateModal,
  PayrollBulkPointRateModal,
  PayrollInputLineFormModal,
  PayrollPeriodFormModal,
  PayrollRateFormModal,
  PayrollWorkRecordFormModal,
} from "@/components/finance/admin/PayrollAdminModals";
import { PayrollAttendanceWorkModal } from "@/components/finance/admin/PayrollAttendanceWorkModal";
import {
  PayrollApprovalQueue,
  PayrollInputLinesTable,
  PayrollRatesTable,
  PayrollWorkRecordsTable,
} from "@/components/finance/admin/PayrollAdminTables";
import { PayrollPeriodTableView } from "@/components/finance/admin/PayrollPeriodTable";
import { useUser } from "@/contexts/UserContext";
import { usePayrollAdminTab } from "@/hooks/usePayrollTabs";
import { apiClient } from "@/lib/api";
import type {
  PayrollAdminInputLine,
  PayrollAdminPayRate,
  PayrollAdminPeriod,
  PayrollAdminRun,
  PayrollAdminWorkspace as WorkspacePayload,
  PayrollAdminWorkRecord,
  PayrollApprovalStatus,
  PayrollBulkPayRateResult,
  PayrollBulkPointRateResult,
  PayrollInputLineWrite,
  PayrollPayRateWrite,
  PayrollPeriodTable,
  PayrollPeriodTableRow,
  PayrollPeriodWrite,
  PayrollWorkRecordWrite,
} from "@/lib/api/finance";
import {
  getPayrollAdminError,
  getPrimaryPayrollRunAction,
  normalizePayrollAdminList,
  PAYROLL_ADMIN_TABS,
  PAYROLL_SELECTED_PERIOD_STORAGE_PREFIX,
  payrollRunActionLabels,
  periodStatusMeta,
  runStatusMeta,
  type PayrollRunAction,
} from "@/lib/payroll-admin";
import { buildPayrollAttendanceApplyNotice } from "@/lib/payroll-attendance";
import { formatPayrollDate, formatPayrollDateTime, formatPayrollMoney, getPayrollPeriodRange } from "@/lib/payroll";

type PendingAction = {
  title: string;
  description: string;
  confirmLabel: string;
  reasonLabel?: string;
  reasonRequired?: boolean;
  warning?: string;
  successMessage: string;
  execute: (reason: string) => Promise<unknown>;
};

function StatusPill({ period }: { period: PayrollAdminPeriod }) {
  const meta = periodStatusMeta[period.status];
  return <span className={`app-status-pill ${meta.className}`}>{meta.label}</span>;
}

function SummaryCards({ workspace }: { workspace: WorkspacePayload }) {
  const summary = workspace.summary;
  const hiddenValue = workspace.current_run ? "Скрыто" : "—";
  const values = [
    { label: "Сотрудников", value: summary ? String(summary.employee_count) : String(workspace.current_run?.employee_count ?? workspace.readiness.work_records.total), icon: UsersRound },
    { label: "Начислено", value: summary?.gross_total != null ? formatPayrollMoney(summary.gross_total, workspace.selected_period?.currency) : hiddenValue, icon: Banknote },
    { label: "Удержано", value: summary?.deduction_total != null ? formatPayrollMoney(summary.deduction_total, workspace.selected_period?.currency) : hiddenValue, icon: FileCheck2 },
    { label: "К выплате", value: summary?.payable_total != null ? formatPayrollMoney(summary.payable_total, workspace.selected_period?.currency) : hiddenValue, icon: Calculator },
  ];
  return (
    <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
      {values.map(({ label, value, icon: Icon }) => (
        <div key={label} className="app-surface-muted rounded-xl p-3.5">
          <div className="flex items-center gap-2 text-[var(--muted-foreground)]"><Icon size={15} /><span className="text-xs">{label}</span></div>
          <p className="mt-2 truncate text-lg font-semibold text-[var(--foreground)]" title={value}>{value}</p>
        </div>
      ))}
    </div>
  );
}

function TableToolbar({
  search,
  status,
  onSearch,
  onStatus,
  onAdd,
  onFillFromAttendance,
  onBulkPayRate,
  onBulkPointRate,
  addLabel,
}: {
  search: string;
  status: "" | PayrollApprovalStatus;
  onSearch: (value: string) => void;
  onStatus: (value: "" | PayrollApprovalStatus) => void;
  onAdd?: () => void;
  onFillFromAttendance?: () => void;
  onBulkPayRate?: () => void;
  onBulkPointRate?: () => void;
  addLabel: string;
}) {
  const [addMenuOpen, setAddMenuOpen] = useState(false);
  const addMenuRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!addMenuOpen) return;
    const closeOnOutsideClick = (event: MouseEvent) => {
      if (addMenuRef.current && !addMenuRef.current.contains(event.target as Node)) {
        setAddMenuOpen(false);
      }
    };
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") setAddMenuOpen(false);
    };
    document.addEventListener("mousedown", closeOnOutsideClick);
    document.addEventListener("keydown", closeOnEscape);
    return () => {
      document.removeEventListener("mousedown", closeOnOutsideClick);
      document.removeEventListener("keydown", closeOnEscape);
    };
  }, [addMenuOpen]);

  return (
    <div className="mb-4 flex flex-col gap-2 sm:flex-row">
      <label className="relative min-w-0 flex-1">
        <Search className="app-text-muted pointer-events-none absolute left-3 top-1/2 -translate-y-1/2" size={15} />
        <input className="app-input w-full rounded-lg py-2.5 pl-9 pr-3 text-sm" value={search} placeholder="Поиск по сотруднику" onChange={(event) => onSearch(event.target.value)} />
      </label>
      <select className="app-select rounded-lg px-3 py-2.5 text-sm sm:w-44" value={status} onChange={(event) => onStatus(event.target.value as "" | PayrollApprovalStatus)}>
        <option value="">Все статусы</option><option value="draft">Черновики</option><option value="approved">Утверждённые</option><option value="voided">Аннулированные</option>
      </select>
      {onFillFromAttendance ? (
        <button type="button" className="app-action-secondary inline-flex items-center justify-center gap-2 rounded-lg px-3.5 py-2.5 text-sm font-medium" onClick={onFillFromAttendance}>
          <CalendarCheck2 size={16} /> Заполнить из посещаемости
        </button>
      ) : null}
      {onAdd ? (
        <div ref={addMenuRef} className="relative flex shrink-0 items-center gap-1">
          <button type="button" className="app-action-primary inline-flex items-center justify-center gap-2 rounded-lg px-3.5 py-2.5 text-sm font-semibold" onClick={onAdd}>
            <Plus size={16} /> {addLabel}
          </button>
          {onBulkPayRate || onBulkPointRate ? (
            <button
              type="button"
              className="app-action-ghost flex h-10 w-8 items-center justify-center rounded-md"
              onClick={() => setAddMenuOpen((current) => !current)}
              aria-label="Дополнительные действия со ставками"
              aria-expanded={addMenuOpen}
              aria-haspopup="menu"
              title="Дополнительные действия"
            >
              <ChevronRight size={15} className={`transition-transform duration-200 ${addMenuOpen ? "rotate-90" : ""}`} />
            </button>
          ) : null}
          {addMenuOpen && (onBulkPayRate || onBulkPointRate) ? (
            <div className="app-menu absolute right-0 top-full z-30 mt-2 w-64 rounded-xl py-1.5" role="menu">
              {onBulkPayRate ? (
                <button
                  type="button"
                  className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm text-[var(--foreground)] transition hover:bg-[var(--surface-secondary)]"
                  onClick={() => {
                    setAddMenuOpen(false);
                    onBulkPayRate();
                  }}
                >
                  <UsersRound className="app-text-muted" size={15} />
                  Массово добавить ставку
                </button>
              ) : null}
              {onBulkPointRate ? (
                <button
                  type="button"
                  className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm text-[var(--foreground)] transition hover:bg-[var(--surface-secondary)]"
                  onClick={() => {
                    setAddMenuOpen(false);
                    onBulkPointRate();
                  }}
                >
                  <Banknote className="app-text-muted" size={15} />
                  Массово задать цену сверх нормы
                </button>
              ) : null}
            </div>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}

function SectionIntro({ title, description }: { title: string; description: string }) {
  return <div className="mb-4"><h2 className="text-base font-semibold text-[var(--foreground)]">{title}</h2><p className="app-text-muted mt-1 text-sm">{description}</p></div>;
}

function RunCard({ run, current = false }: { run: PayrollAdminRun; current?: boolean }) {
  const meta = runStatusMeta[run.status];
  return (
    <div className="app-surface-muted rounded-xl p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div><p className="text-sm font-semibold text-[var(--foreground)]">Ревизия {run.revision}{current ? " · текущая" : ""}</p><p className="app-text-muted mt-0.5 text-xs">{formatPayrollDateTime(run.requested_at)} · {run.requested_by.display_name}</p></div>
        <span className={`app-status-pill ${meta.className}`}>{meta.label}</span>
      </div>
      {run.payable_total != null ? (
        <div className="mt-3 flex flex-wrap gap-x-6 gap-y-1 text-xs text-[var(--muted-foreground)]">
          <span>Сотрудников: <b className="text-[var(--foreground)]">{run.employee_count}</b></span>
          <span>К выплате: <b className="text-[var(--foreground)]">{formatPayrollMoney(run.payable_total)}</b></span>
        </div>
      ) : null}
      {run.recalculation_reason ? <p className="app-text-muted mt-3 text-xs">Основание: {run.recalculation_reason}</p> : null}
    </div>
  );
}

type PayrollAdminWorkspaceProps = {
  actionsTargetId?: string;
  desktopWideMode?: boolean;
  embedded?: boolean;
  headerTargetId?: string;
  onDesktopWideModeChange?: (enabled: boolean) => void;
};

export function PayrollAdminWorkspace({
  actionsTargetId,
  desktopWideMode = false,
  embedded = false,
  headerTargetId,
  onDesktopWideModeChange,
}: PayrollAdminWorkspaceProps) {
  const { user } = useUser();
  const [workspace, setWorkspace] = useState<WorkspacePayload | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [tab, setTab] = usePayrollAdminTab(user?.id);
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState<"" | PayrollApprovalStatus>("");
  const [rates, setRates] = useState<PayrollAdminPayRate[]>([]);
  const [workRecords, setWorkRecords] = useState<PayrollAdminWorkRecord[]>([]);
  const [inputLines, setInputLines] = useState<PayrollAdminInputLine[]>([]);
  const [periodTable, setPeriodTable] = useState<PayrollPeriodTable | null>(null);
  const [tableLoading, setTableLoading] = useState(false);
  const [tableError, setTableError] = useState<string | null>(null);
  const [tableVersion, setTableVersion] = useState(0);
  const [notice, setNotice] = useState<string | null>(null);

  const [periodModalOpen, setPeriodModalOpen] = useState(false);
  const [editingPeriod, setEditingPeriod] = useState<PayrollAdminPeriod | null>(null);
  const [rateModalOpen, setRateModalOpen] = useState(false);
  const [bulkPayRateModalOpen, setBulkPayRateModalOpen] = useState(false);
  const [bulkPointRateModalOpen, setBulkPointRateModalOpen] = useState(false);
  const [editingRate, setEditingRate] = useState<PayrollAdminPayRate | null>(null);
  const [workModalOpen, setWorkModalOpen] = useState(false);
  const [editingWork, setEditingWork] = useState<PayrollAdminWorkRecord | null>(null);
  const [attendanceWorkModalOpen, setAttendanceWorkModalOpen] = useState(false);
  const [inputModalOpen, setInputModalOpen] = useState(false);
  const [editingInput, setEditingInput] = useState<PayrollAdminInputLine | null>(null);
  const [pendingAction, setPendingAction] = useState<PendingAction | null>(null);
  const createdPeriodIdRef = useRef<number | null>(null);

  const selectedPeriod = workspace?.selected_period || null;

  const loadWorkspace = useCallback(async (
    periodId?: number,
    silent = false,
    fallbackToLatest = false,
  ) => {
    if (!silent) setLoading(true);
    setLoadError(null);
    try {
      const payload = await apiClient.getPayrollAdminWorkspace(periodId);
      setWorkspace(payload);
    } catch (error) {
      if (fallbackToLatest && periodId !== undefined) {
        try {
          const payload = await apiClient.getPayrollAdminWorkspace();
          setWorkspace(payload);
          return;
        } catch (fallbackError) {
          setLoadError(getPayrollAdminError(fallbackError, "Не удалось загрузить управление зарплатой."));
          return;
        }
      }
      setLoadError(getPayrollAdminError(error, "Не удалось загрузить управление зарплатой."));
    } finally {
      if (!silent) setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!user?.id) return;
    const storedValue = window.localStorage.getItem(
      `${PAYROLL_SELECTED_PERIOD_STORAGE_PREFIX}.${user.id}`,
    );
    const storedPeriodId = storedValue ? Number(storedValue) : undefined;
    void loadWorkspace(
      storedPeriodId && Number.isInteger(storedPeriodId) && storedPeriodId > 0
        ? storedPeriodId
        : undefined,
      false,
      true,
    );
  }, [loadWorkspace, user?.id]);

  useEffect(() => {
    if (!user?.id || !selectedPeriod?.id) return;
    window.localStorage.setItem(
      `${PAYROLL_SELECTED_PERIOD_STORAGE_PREFIX}.${user.id}`,
      String(selectedPeriod.id),
    );
  }, [selectedPeriod?.id, user?.id]);

  useEffect(() => {
    if (!selectedPeriod) {
      setRates([]); setWorkRecords([]); setInputLines([]); setPeriodTable(null);
      return;
    }
    if (tab === "readiness") return;
    const canLoadInputs = Boolean(workspace?.permissions.manage_inputs || workspace?.permissions.approve_inputs || workspace?.permissions.view_all);
    if (["rates", "work", "inputs"].includes(tab) && !canLoadInputs) {
      setRates([]); setWorkRecords([]); setInputLines([]); setTableError(null); setTableLoading(false);
      return;
    }
    if (tab === "approval" && !canLoadInputs) {
      setRates([]); setWorkRecords([]); setInputLines([]); setTableError(null); setTableLoading(false);
      return;
    }
    if (tab === "summary" && !workspace?.permissions.view_all) {
      setPeriodTable(null); setTableError(null); setTableLoading(false);
      return;
    }

    let cancelled = false;
    setTableLoading(true);
    setTableError(null);
    const params = { period_id: selectedPeriod.id };
    const load = async () => {
      try {
        if (tab === "summary") {
          setPeriodTable(null);
          const [tablePayload, ratesPayload, workPayload, inputsPayload] = await Promise.all([
            apiClient.getPayrollAdminPeriodTable(selectedPeriod.id),
            apiClient.getPayrollAdminPayRates(params),
            apiClient.getPayrollAdminWorkRecords(params),
            apiClient.getPayrollAdminInputLines(params),
          ]);
          if (!cancelled) {
            setPeriodTable(tablePayload);
            setRates(normalizePayrollAdminList(ratesPayload));
            setWorkRecords(normalizePayrollAdminList(workPayload));
            setInputLines(normalizePayrollAdminList(inputsPayload));
          }
        } else if (tab === "rates") {
          const payload = await apiClient.getPayrollAdminPayRates(params);
          if (!cancelled) setRates(normalizePayrollAdminList(payload));
        } else if (tab === "work") {
          const payload = await apiClient.getPayrollAdminWorkRecords(params);
          if (!cancelled) setWorkRecords(normalizePayrollAdminList(payload));
        } else if (tab === "inputs") {
          const payload = await apiClient.getPayrollAdminInputLines(params);
          if (!cancelled) setInputLines(normalizePayrollAdminList(payload));
        } else {
          const [ratesPayload, workPayload, inputsPayload] = await Promise.all([
            apiClient.getPayrollAdminPayRates({ ...params, status: "draft" }),
            apiClient.getPayrollAdminWorkRecords({ ...params, status: "draft" }),
            apiClient.getPayrollAdminInputLines({ ...params, status: "draft" }),
          ]);
          if (!cancelled) {
            setRates(normalizePayrollAdminList(ratesPayload));
            setWorkRecords(normalizePayrollAdminList(workPayload));
            setInputLines(normalizePayrollAdminList(inputsPayload));
          }
        }
      } catch (error) {
        if (!cancelled) setTableError(getPayrollAdminError(error, "Не удалось загрузить данные раздела."));
      } finally {
        if (!cancelled) setTableLoading(false);
      }
    };
    void load();
    return () => { cancelled = true; };
  }, [
    selectedPeriod,
    tab,
    tableVersion,
    workspace?.permissions.approve_inputs,
    workspace?.permissions.manage_inputs,
    workspace?.permissions.view_all,
  ]);

  const refreshView = useCallback(async (message?: string) => {
    if (message) setNotice(message);
    await loadWorkspace(selectedPeriod?.id, true);
    setTableVersion((value) => value + 1);
  }, [loadWorkspace, selectedPeriod?.id]);

  const handleStale = useCallback(async () => {
    setPeriodModalOpen(false); setRateModalOpen(false); setBulkPayRateModalOpen(false); setBulkPointRateModalOpen(false); setWorkModalOpen(false); setAttendanceWorkModalOpen(false); setInputModalOpen(false); setPendingAction(null);
    await refreshView("Данные изменились в другой сессии. Экран обновлён — повторите действие.");
  }, [refreshView]);

  const filteredRates = useMemo(() => rates.filter((record) => {
    const needle = search.trim().toLocaleLowerCase("ru-RU");
    return (!status || record.status === status) && (!needle || `${record.employee.display_name} ${record.reason}`.toLocaleLowerCase("ru-RU").includes(needle));
  }), [rates, search, status]);
  const filteredWork = useMemo(() => workRecords.filter((record) => {
    const needle = search.trim().toLocaleLowerCase("ru-RU");
    return (!status || record.status === status) && (!needle || `${record.employee.display_name} ${record.reason}`.toLocaleLowerCase("ru-RU").includes(needle));
  }), [workRecords, search, status]);
  const filteredInputs = useMemo(() => inputLines.filter((record) => {
    const needle = search.trim().toLocaleLowerCase("ru-RU");
    return (!status || record.status === status) && (!needle || `${record.employee.display_name} ${record.component.name} ${record.reason}`.toLocaleLowerCase("ru-RU").includes(needle));
  }), [inputLines, search, status]);

  const openApproveRate = (record: PayrollAdminPayRate) => setPendingAction({
    title: "Утвердить ставку", description: `${record.employee.display_name}: ${formatPayrollMoney(record.amount, record.currency)}.`, confirmLabel: "Утвердить", warning: "После утверждения ставку нельзя редактировать — только создать новую версию.", successMessage: "Ставка утверждена.", execute: () => apiClient.approvePayrollAdminPayRate(record.id, record.lock_version),
  });
  const openApproveWork = (record: PayrollAdminWorkRecord) => setPendingAction({
    title: "Утвердить выработку", description: `${record.employee.display_name}: ${record.actual_points} из ${record.target_points} баллов.`, confirmLabel: "Утвердить", warning: "Проверьте норму и фактическую выработку перед утверждением.", successMessage: "Выработка утверждена.", execute: () => apiClient.approvePayrollAdminWorkRecord(record.id, record.lock_version),
  });
  const openApproveInput = (record: PayrollAdminInputLine) => setPendingAction({
    title: "Утвердить операцию", description: `${record.component.name} для ${record.employee.display_name}: ${formatPayrollMoney(record.amount, selectedPeriod?.currency)}.`, confirmLabel: "Утвердить", warning: "Утверждённая операция станет входом следующего расчёта.", successMessage: "Операция утверждена.", execute: () => apiClient.approvePayrollAdminInputLine(record.id, record.lock_version),
  });
  const openReviseRate = (record: PayrollAdminPayRate) => setPendingAction({
    title: "Создать новую версию ставки", description: `Будет создан отдельный черновик ставки для ${record.employee.display_name}.`, confirmLabel: "Создать черновик", reasonLabel: "Основание изменения", reasonRequired: true, successMessage: "Новая версия ставки создана в черновиках.", execute: (reason) => apiClient.revisePayrollAdminPayRate(record.id, reason),
  });
  const openReviseWork = (record: PayrollAdminWorkRecord) => setPendingAction({
    title: "Создать новую версию выработки", description: `Будет создан отдельный черновик выработки для ${record.employee.display_name}.`, confirmLabel: "Создать черновик", reasonLabel: "Причина исправления", reasonRequired: true, successMessage: "Новая версия выработки создана в черновиках.", execute: (reason) => apiClient.revisePayrollAdminWorkRecord(record.id, reason),
  });

  const openRunAction = (action: PayrollRunAction) => {
    if (!action || !selectedPeriod || !workspace) return;
    const run = workspace.current_run;
    const configs: Record<Exclude<PayrollRunAction, null>, Omit<PendingAction, "execute"> & { execute: (reason: string) => Promise<unknown> }> = {
      calculate: {
        title: run ? "Запустить перерасчёт" : "Запустить расчёт",
        description: `Будет рассчитана зарплата за ${selectedPeriod.name || selectedPeriod.code} для всех сотрудников с утверждёнными данными.`,
        confirmLabel: run ? "Пересчитать" : "Рассчитать",
        reasonLabel: run ? "Основание перерасчёта" : undefined,
        reasonRequired: Boolean(run),
        warning: "Результат сохранится как отдельная неизменяемая ревизия.",
        successMessage: run ? "Новая ревизия рассчитана." : "Расчёт выполнен.",
        execute: (reason) => apiClient.calculatePayrollAdminPeriod(selectedPeriod.id, { idempotency_key: globalThis.crypto.randomUUID(), recalculation_reason: reason, expected_lock_version: selectedPeriod.lock_version }),
      },
      submit_review: { title: "Передать расчёт на проверку", description: "Система повторно проверит актуальность входных данных и контрольные суммы.", confirmLabel: "Передать", successMessage: "Расчёт передан на проверку.", execute: () => apiClient.submitPayrollAdminRunForReview(run!.id) },
      approve: { title: "Утвердить расчёт", description: "Проверьте итоговые суммы и состав сотрудников перед решением.", confirmLabel: "Утвердить", successMessage: "Расчёт утверждён.", execute: () => apiClient.approvePayrollAdminRun(run!.id) },
      publish: { title: "Опубликовать расчётные листки", description: "После публикации сотрудники увидят суммы в разделе «Финансы».", confirmLabel: "Опубликовать", warning: "Проверьте дату выплаты и итог к выплате. Публикация сразу открывает листки сотрудникам.", successMessage: "Расчётные листки опубликованы.", execute: () => apiClient.publishPayrollAdminRun(run!.id) },
      close: { title: "Закрыть период", description: "Закрытый период больше нельзя пересчитывать.", confirmLabel: "Закрыть период", warning: "Это финальное действие для расчётного периода.", successMessage: "Период закрыт.", execute: () => apiClient.closePayrollAdminPeriod(selectedPeriod.id) },
    };
    setPendingAction(configs[action]);
  };

  const openReturn = () => {
    const run = workspace?.current_run;
    if (!run) return;
    setPendingAction({ title: "Вернуть расчёт на исправление", description: "Текущая ревизия останется в истории, а данные можно будет исправить и пересчитать.", confirmLabel: "Вернуть", reasonLabel: "Причина возврата", reasonRequired: true, warning: "Для продолжения потребуется новая ревизия расчёта.", successMessage: "Расчёт возвращён на исправление.", execute: (reason) => apiClient.returnPayrollAdminRun(run.id, reason) });
  };

  if (loading) return <section className="app-surface flex min-h-72 items-center justify-center rounded-2xl"><Loader2 className="app-accent-text animate-spin" size={28} /></section>;
  if (loadError || !workspace) {
    return (
      <section className="app-surface rounded-2xl p-5">
        <div className="app-feedback-danger rounded-xl px-4 py-3 text-sm">{loadError || "Раздел управления недоступен."}</div>
        <div className="mt-4 flex gap-2">{!embedded ? <Link href="/finances" className="app-action-secondary rounded-lg px-4 py-2.5 text-sm font-medium">Вернуться</Link> : null}<button type="button" className="app-action-primary rounded-lg px-4 py-2.5 text-sm font-medium" onClick={() => void loadWorkspace()}>Повторить</button></div>
      </section>
    );
  }

  const permissions = workspace.permissions;
  const canOpenInputTabs = permissions.manage_inputs || permissions.approve_inputs || permissions.view_all;
  const visibleTabs = PAYROLL_ADMIN_TABS.filter((item) => (
    (item.value !== "summary" || permissions.view_all)
    && (!["rates", "work", "inputs"].includes(item.value) || canOpenInputTabs)
  ));
  const primaryAction = selectedPeriod ? getPrimaryPayrollRunAction(workspace.current_run, selectedPeriod.status, permissions, workspace.readiness.calculation.ready, user?.id) : null;
  const canReturn = Boolean(workspace.current_run && ["calculated", "review", "approved"].includes(workspace.current_run.status) && (workspace.current_run.status === "calculated" ? permissions.calculate : permissions.approve_run));
  const sourceDataLocked = selectedPeriod?.status === "closed" || Boolean(
    workspace.current_run && ["calculated", "review", "approved"].includes(workspace.current_run.status),
  );
  const canManageSourceData = permissions.manage_inputs && !sourceDataLocked;
  const canApproveSourceData = permissions.approve_inputs && !sourceDataLocked;

  const savePeriod = async (payload: PayrollPeriodWrite) => {
    if (editingPeriod) await apiClient.updatePayrollAdminPeriod(editingPeriod.id, { ...payload, expected_lock_version: editingPeriod.lock_version });
    else {
      const createdPeriod = await apiClient.createPayrollAdminPeriod(payload);
      createdPeriodIdRef.current = createdPeriod.id;
    }
  };
  const saveRate = async (payload: PayrollPayRateWrite) => {
    if (editingRate) await apiClient.updatePayrollAdminPayRate(editingRate.id, { amount: payload.amount, point_rate: payload.point_rate, effective_from: payload.effective_from, reason: payload.reason, expected_lock_version: editingRate.lock_version });
    else await apiClient.createPayrollAdminPayRate(payload);
  };
  const saveWork = async (payload: PayrollWorkRecordWrite) => {
    if (editingWork) await apiClient.updatePayrollAdminWorkRecord(editingWork.id, { target_points: payload.target_points, actual_points: payload.actual_points, expected_point_amount: payload.expected_point_amount, expected_gross: payload.expected_gross, expected_recalculated_gross: payload.expected_recalculated_gross, expected_payable: payload.expected_payable, reason: payload.reason, expected_lock_version: editingWork.lock_version });
    else await apiClient.createPayrollAdminWorkRecord(payload);
  };
  const saveInput = async (payload: PayrollInputLineWrite) => {
    if (editingInput) await apiClient.updatePayrollAdminInputLine(editingInput.id, { amount: payload.amount, relates_to_period_id: payload.relates_to_period_id, reason: payload.reason, expected_lock_version: editingInput.lock_version });
    else await apiClient.createPayrollAdminInputLine(payload);
  };

  const refreshInlineTable = async (source: "rates" | "work" | "inputs") => {
    if (!selectedPeriod) return;
    const params = { period_id: selectedPeriod.id };
    const tableRequest = apiClient.getPayrollAdminPeriodTable(selectedPeriod.id);
    if (source === "rates") {
      const [tablePayload, sourcePayload] = await Promise.all([tableRequest, apiClient.getPayrollAdminPayRates(params)]);
      setPeriodTable(tablePayload);
      setRates(normalizePayrollAdminList(sourcePayload));
    } else if (source === "work") {
      const [tablePayload, sourcePayload] = await Promise.all([tableRequest, apiClient.getPayrollAdminWorkRecords(params)]);
      setPeriodTable(tablePayload);
      setWorkRecords(normalizePayrollAdminList(sourcePayload));
    } else {
      const [tablePayload, sourcePayload] = await Promise.all([tableRequest, apiClient.getPayrollAdminInputLines(params)]);
      setPeriodTable(tablePayload);
      setInputLines(normalizePayrollAdminList(sourcePayload));
    }
  };

  const saveRateCell = async (row: PayrollPeriodTableRow, field: "amount" | "point_rate", value: string) => {
    if (!canManageSourceData || !selectedPeriod) return;
    const rawValue = value.trim().replace(",", ".");
    const normalized = field === "point_rate" && rawValue === "" ? "0" : rawValue;
    const numeric = Number(normalized);
    if (!Number.isFinite(numeric) || numeric < 0 || (field === "amount" && numeric === 0)) {
      throw new Error(field === "amount" ? "Оклад должен быть больше нуля." : "Укажите корректную цену балла сверх нормы.");
    }
    const record = rates
      .filter((item) => item.employee.id === row.employee.id && item.status !== "voided" && item.effective_from <= selectedPeriod.date_from)
      .sort((left, right) => right.effective_from.localeCompare(left.effective_from) || right.revision - left.revision || right.id - left.id)[0];
    let draft = record;
    if (draft?.status === "approved") {
      draft = await apiClient.revisePayrollAdminPayRate(draft.id, "Изменено в итоговой таблице");
    }
    if (draft) {
      await apiClient.updatePayrollAdminPayRate(draft.id, { [field]: normalized, expected_lock_version: draft.lock_version });
    } else {
      const amount = field === "amount" ? normalized : row.rate_amount;
      if (!amount) throw new Error("Сначала заполните оклад.");
      await apiClient.createPayrollAdminPayRate({
        employee_id: row.employee.id,
        rate_code: "BASE",
        amount,
        point_rate: field === "point_rate" ? normalized : row.point_rate || "0",
        currency: selectedPeriod.currency,
        effective_from: selectedPeriod.date_from,
        reason: "Введено в итоговой таблице",
      });
    }
    await refreshInlineTable("rates");
  };

  const saveWorkCell = async (row: PayrollPeriodTableRow, field: "target_points" | "actual_points", value: string) => {
    if (!canManageSourceData || !selectedPeriod) return;
    const normalized = value.trim().replace(",", ".");
    if (field === "actual_points" && (!normalized || !Number.isFinite(Number(normalized)) || Number(normalized) < 0)) {
      throw new Error("Фактические баллы должны быть числом не меньше нуля.");
    }
    if (field === "target_points" && normalized && (!Number.isFinite(Number(normalized)) || Number(normalized) <= 0)) {
      throw new Error("Норма должна быть больше нуля или оставлена пустой для автоматического расчёта.");
    }
    const record = workRecords
      .filter((item) => item.employee.id === row.employee.id && item.status !== "voided")
      .sort((left, right) => right.revision - left.revision || right.id - left.id)[0];
    let draft = record;
    if (draft?.status === "approved") {
      draft = await apiClient.revisePayrollAdminWorkRecord(draft.id, "Изменено в итоговой таблице");
    }
    if (draft) {
      await apiClient.updatePayrollAdminWorkRecord(draft.id, {
        [field]: field === "target_points" ? normalized || null : normalized,
        expected_lock_version: draft.lock_version,
      });
    } else {
      await apiClient.createPayrollAdminWorkRecord({
        period_id: selectedPeriod.id,
        employee_id: row.employee.id,
        target_points: field === "target_points" ? normalized || null : null,
        actual_points: field === "actual_points" ? normalized : "0",
        expected_point_amount: null,
        expected_gross: null,
        expected_recalculated_gross: null,
        expected_payable: null,
        reason: "Введено в итоговой таблице",
      });
    }
    await refreshInlineTable("work");
  };

  const saveComponentCell = async (row: PayrollPeriodTableRow, componentCode: string, value: string) => {
    if (!canManageSourceData || !selectedPeriod) return;
    const normalized = value.trim().replace(",", ".");
    const desiredAmount = Number(normalized);
    if (!Number.isFinite(desiredAmount) || desiredAmount <= 0) {
      throw new Error("Сумма операции должна быть больше нуля.");
    }
    const component = workspace.components.find((item) => item.code === componentCode);
    if (!component) throw new Error("Вид операции не найден.");
    const matchingLines = inputLines.filter((item) => item.employee.id === row.employee.id && item.component.id === component.id && item.status !== "voided");
    const draft = matchingLines
      .filter((item) => item.status === "draft")
      .sort((left, right) => right.id - left.id)[0];
    const currentAmount = Number(row.component_amounts[componentCode] || "0");
    if (draft) {
      const amountWithoutDraft = currentAmount - Number(draft.amount);
      const replacementAmount = desiredAmount - amountWithoutDraft;
      if (replacementAmount <= 0) {
        throw new Error("Значение ниже уже утверждённой суммы. Исправьте её во вкладке «Начисления и выплаты».");
      }
      await apiClient.updatePayrollAdminInputLine(draft.id, { amount: replacementAmount.toFixed(2), expected_lock_version: draft.lock_version });
    } else {
      const addition = desiredAmount - currentAmount;
      if (addition <= 0) {
        throw new Error("Утверждённую сумму можно уменьшить через корректирующую операцию во вкладке «Начисления и выплаты».");
      }
      await apiClient.createPayrollAdminInputLine({
        period_id: selectedPeriod.id,
        employee_id: row.employee.id,
        component_id: component.id,
        amount: addition.toFixed(2),
        relates_to_period_id: null,
        reason: "Введено в итоговой таблице",
      });
    }
    await refreshInlineTable("inputs");
  };

  const managementInfo = (
    <div className="min-w-0">
      {!embedded ? <Link href="/finances" className="app-link-accent inline-flex items-center gap-1.5 text-xs font-medium"><ArrowLeft size={14} /> Финансы</Link> : null}
      <div className={`${embedded ? "" : "mt-2"} flex flex-wrap items-center gap-2`}><h1 className="text-xl font-semibold text-[var(--foreground)] sm:text-2xl">Управление зарплатой</h1>{selectedPeriod ? <StatusPill period={selectedPeriod} /> : null}</div>
      {selectedPeriod ? <p className="app-text-muted mt-1 text-sm">{getPayrollPeriodRange(selectedPeriod)} · выплата {formatPayrollDate(selectedPeriod.pay_date)}</p> : <p className="app-text-muted mt-1 text-sm">Создайте первый расчётный период, чтобы начать подготовку.</p>}
    </div>
  );
  const managementActions = (
    <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
      {onDesktopWideModeChange ? (
        <button
          type="button"
          onClick={() => onDesktopWideModeChange(!desktopWideMode)}
          className="app-action-ghost hidden h-8 w-8 items-center justify-center rounded-md lg:inline-flex"
          title={desktopWideMode ? "Вернуть обычный вид" : "Развернуть финансы"}
          aria-label={desktopWideMode ? "Вернуть обычный вид" : "Развернуть финансы"}
          aria-pressed={desktopWideMode}
        >
          {desktopWideMode ? <Minimize2 size={17} /> : <Maximize2 size={17} />}
        </button>
      ) : null}
      {workspace.periods.length ? (
        <select className="app-select min-w-52 rounded-lg px-3 py-2.5 text-sm" value={selectedPeriod?.id || ""} onChange={(event) => void loadWorkspace(Number(event.target.value), true)} aria-label="Расчётный период">
          {workspace.periods.map((period) => <option value={period.id} key={period.id}>{period.name || period.code}</option>)}
        </select>
      ) : null}
      {permissions.manage_inputs ? <button type="button" className="app-action-primary inline-flex items-center justify-center gap-2 rounded-lg px-3 py-2.5 text-sm font-semibold" onClick={() => { setEditingPeriod(null); setPeriodModalOpen(true); }}><Plus size={16} /> Новый период</button> : null}
    </div>
  );
  const headerTarget = headerTargetId && typeof document !== "undefined"
    ? document.getElementById(headerTargetId)
    : null;
  const actionsTarget = actionsTargetId && typeof document !== "undefined"
    ? document.getElementById(actionsTargetId)
    : null;

  return (
    <div className="space-y-4 lg:min-h-0 lg:flex-1 lg:overflow-y-auto lg:pr-1">
      {headerTargetId ? (
        <>
          {headerTarget ? createPortal(managementInfo, headerTarget) : null}
          {actionsTarget ? createPortal(managementActions, actionsTarget) : null}
        </>
      ) : (
        <section className="app-surface rounded-2xl p-4 sm:p-5">
          <div className="flex flex-col gap-4 xl:flex-row xl:items-center xl:justify-between">{managementInfo}{managementActions}</div>
        </section>
      )}

      {notice ? <div className="app-feedback-success flex items-start justify-between gap-3 rounded-xl px-4 py-3 text-sm"><span>{notice}</span><button type="button" onClick={() => setNotice(null)} aria-label="Скрыть сообщение">×</button></div> : null}

      {!selectedPeriod ? (
        <section className="app-surface rounded-2xl p-8 text-center"><CalendarEmpty /><p className="app-text-muted mx-auto mt-2 max-w-md text-sm">Без периода нельзя ввести ставки, выработку и начисления.</p>{permissions.manage_inputs ? <button type="button" className="app-action-primary mt-5 inline-flex items-center gap-2 rounded-lg px-4 py-2.5 text-sm font-semibold" onClick={() => setPeriodModalOpen(true)}><Plus size={16} /> Создать период</button> : null}</section>
      ) : (
        <>
          <section className="app-surface rounded-2xl p-4 sm:p-5"><SummaryCards workspace={workspace} /></section>

          <section className="app-surface rounded-2xl p-2 sm:p-3">
            <div className="flex gap-1 overflow-x-auto" role="tablist" aria-label="Разделы управления зарплатой">
              {visibleTabs.map((item) => {
                const count = item.value === "summary"
                  ? periodTable?.summary.employee_count ?? workspace.employees.length
                  : item.value === "approval"
                    ? workspace.pending_approvals.rates + workspace.pending_approvals.work_records + workspace.pending_approvals.input_lines
                    : 0;
                return <button type="button" role="tab" aria-selected={tab === item.value} key={item.value} className={`${tab === item.value ? "app-chip-active" : "app-chip"} inline-flex shrink-0 items-center gap-2 rounded-lg px-3 py-2 text-xs font-medium sm:text-sm`} onClick={() => { setTab(item.value); setSearch(""); setStatus(""); }}>{item.label}{count > 0 ? <span className={`${tab === item.value ? "bg-white/20 text-white" : "app-counter"} inline-flex h-5 min-w-5 items-center justify-center rounded-full px-1 text-[10px]`}>{count}</span> : null}</button>;
              })}
            </div>
          </section>

          {tab === "readiness" ? (
            <section className="app-surface rounded-2xl p-4 sm:p-5">
              <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_320px]">
                <div>
                  <SectionIntro title="Готовность к расчёту" description="Система запускает расчёт только по утверждённым данным и показывает, что ещё нужно подготовить." />
                  <div className="space-y-2">
                    {[
                      { label: "Ставки сотрудников", value: `${workspace.readiness.rates.approved} из ${workspace.readiness.rates.total}`, ready: workspace.readiness.rates.ready, tab: "rates" as const },
                      { label: "Выработка и состав", value: `${workspace.readiness.work_records.approved} из ${workspace.readiness.work_records.total}`, ready: workspace.readiness.work_records.ready, tab: "work" as const },
                      { label: "Начисления и выплаты", value: workspace.readiness.input_lines.draft ? `${workspace.readiness.input_lines.draft} черн.` : `${workspace.readiness.input_lines.approved} утвержд.`, ready: workspace.readiness.input_lines.draft === 0, tab: "inputs" as const },
                    ].map((item) => <button type="button" key={item.label} disabled={!canOpenInputTabs} className="app-surface-muted flex w-full items-center gap-3 rounded-xl p-3 text-left disabled:cursor-default" onClick={() => { if (canOpenInputTabs) setTab(item.tab); }}><span className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-full ${item.ready ? "app-feedback-success" : "app-feedback-warning"}`}>{item.ready ? <Check size={15} /> : <Clock3 size={15} />}</span><span className="min-w-0 flex-1"><span className="block truncate text-sm font-medium text-[var(--foreground)]">{item.label}</span><span className="app-text-muted mt-0.5 block text-xs">{item.value}</span></span>{canOpenInputTabs ? <ChevronRight className="app-text-muted" size={17} /> : null}</button>)}
                  </div>
                  {workspace.readiness.calculation.blockers.length ? <div className="app-feedback-warning mt-4 rounded-xl p-3"><p className="text-sm font-semibold">Что мешает расчёту</p><ul className="mt-2 space-y-1.5 text-xs">{workspace.readiness.calculation.blockers.map((blocker) => { const employee = blocker.employee_id ? workspace.employees.find((item) => item.id === blocker.employee_id) : null; return <li key={`${blocker.code}-${blocker.employee_id || "all"}`} className="flex items-start gap-2"><AlertCircle className="mt-0.5 shrink-0" size={14} /><span>{blocker.message}{employee ? ` — ${employee.display_name}` : ""}</span></li>; })}</ul></div> : null}
                </div>
                <aside className="app-surface-muted rounded-xl p-4">
                  <div className="flex items-center gap-2"><ShieldCheck className="app-accent-text" size={18} /><h3 className="text-sm font-semibold text-[var(--foreground)]">Следующий шаг</h3></div>
                  {primaryAction ? <><p className="app-text-muted mt-3 text-sm leading-relaxed">Все необходимые условия для этого этапа выполнены.</p><button type="button" className="app-action-primary mt-4 inline-flex w-full items-center justify-center gap-2 rounded-lg px-4 py-3 text-sm font-semibold" onClick={() => openRunAction(primaryAction)}>{primaryAction === "calculate" ? <Calculator size={16} /> : primaryAction === "submit_review" ? <Send size={16} /> : <CheckCircle2 size={16} />}{payrollRunActionLabels[primaryAction]}</button></> : <p className="app-text-muted mt-3 text-sm leading-relaxed">Завершите отмеченные пункты.</p>}
                  {selectedPeriod.status === "open" && permissions.manage_inputs && !workspace.current_run ? <button type="button" className="app-action-secondary mt-2 inline-flex w-full items-center justify-center gap-2 rounded-lg px-4 py-2.5 text-sm font-medium" onClick={() => { setEditingPeriod(selectedPeriod); setPeriodModalOpen(true); }}><Pencil size={15} /> Параметры периода</button> : null}
                </aside>
              </div>
            </section>
          ) : null}

          {tab === "rates" ? <section className="app-surface rounded-2xl p-4 sm:p-5"><SectionIntro title="Ставки" description="Оклад и цена балла сверх нормы действуют с указанной даты. Цена балла в пределах нормы рассчитывается как оклад, разделённый на норму." />{sourceDataLocked ? <div className="app-feedback-warning mb-4 rounded-lg px-3 py-2.5 text-sm">Исходные данные заблокированы текущим этапом расчёта. Для исправления сначала верните расчёт.</div> : null}<TableToolbar search={search} status={status} onSearch={setSearch} onStatus={setStatus} onAdd={canManageSourceData ? () => { setEditingRate(null); setRateModalOpen(true); } : undefined} onBulkPayRate={canManageSourceData ? () => setBulkPayRateModalOpen(true) : undefined} onBulkPointRate={canManageSourceData && rates.some((record) => record.status !== "voided") ? () => setBulkPointRateModalOpen(true) : undefined} addLabel="Добавить ставку" /><PayrollRatesTable records={filteredRates} loading={tableLoading} error={tableError} currentUserId={user?.id} canManage={canManageSourceData} canApprove={canApproveSourceData} canOverrideApproval={permissions.override_approval} fullAccess={permissions.full_access} onEdit={(record) => { setEditingRate(record); setRateModalOpen(true); }} onApprove={openApproveRate} onRevise={openReviseRate} /></section> : null}
          {tab === "work" ? (
            <section className="app-surface rounded-2xl p-4 sm:p-5">
              <SectionIntro title="Выработка" description="Норму и факт можно ввести вручную в баллах или заполнить рабочими часами из посещаемости." />
              {sourceDataLocked ? <div className="app-feedback-warning mb-4 rounded-lg px-3 py-2.5 text-sm">Исходные данные заблокированы текущим этапом расчёта. Для исправления сначала верните расчёт.</div> : null}
              <TableToolbar
                search={search}
                status={status}
                onSearch={setSearch}
                onStatus={setStatus}
                onFillFromAttendance={canManageSourceData && selectedPeriod.status !== "published" ? () => setAttendanceWorkModalOpen(true) : undefined}
                onAdd={canManageSourceData && selectedPeriod.status !== "published" ? () => { setEditingWork(null); setWorkModalOpen(true); } : undefined}
                addLabel="Добавить выработку"
              />
              <PayrollWorkRecordsTable records={filteredWork} loading={tableLoading} error={tableError} currentUserId={user?.id} canManage={canManageSourceData} canApprove={canApproveSourceData} canOverrideApproval={permissions.override_approval} fullAccess={permissions.full_access} onEdit={(record) => { setEditingWork(record); setWorkModalOpen(true); }} onApprove={openApproveWork} onRevise={openReviseWork} />
            </section>
          ) : null}
          {tab === "inputs" ? <section className="app-surface rounded-2xl p-4 sm:p-5"><SectionIntro title="Начисления и выплаты" description="Премии, корректировки, удержания и авансы вводятся отдельными строками. Утверждённые строки исправляются новой корректировкой." />{sourceDataLocked ? <div className="app-feedback-warning mb-4 rounded-lg px-3 py-2.5 text-sm">Исходные данные заблокированы текущим этапом расчёта. Для исправления сначала верните расчёт.</div> : null}<TableToolbar search={search} status={status} onSearch={setSearch} onStatus={setStatus} onAdd={canManageSourceData ? () => { setEditingInput(null); setInputModalOpen(true); } : undefined} addLabel="Добавить операцию" /><PayrollInputLinesTable records={filteredInputs} loading={tableLoading} error={tableError} currentUserId={user?.id} canManage={canManageSourceData} canApprove={canApproveSourceData} canOverrideApproval={permissions.override_approval} fullAccess={permissions.full_access} onEdit={(record) => { setEditingInput(record); setInputModalOpen(true); }} onApprove={openApproveInput} /></section> : null}
          {tab === "summary" ? (
            <section className="app-surface min-w-0 rounded-2xl p-4 sm:p-5">
              <SectionIntro title="Итоговая таблица" description="Сводные исходные данные, начисления, удержания и выплаты по всем сотрудникам за выбранный период." />
              <PayrollPeriodTableView data={periodTable} loading={tableLoading} error={tableError} search={search} onSearch={setSearch} canEdit={canManageSourceData} onSaveRate={saveRateCell} onSaveWork={saveWorkCell} onSaveComponent={saveComponentCell} />
            </section>
          ) : null}
          {tab === "approval" ? (
            <section className="app-surface rounded-2xl p-4 sm:p-5">
              <SectionIntro title="Проверка данных" description="Здесь можно утвердить подготовленные черновики и продолжить расчёт." />
              {!canOpenInputTabs ? (
                <div className="app-surface-muted rounded-xl p-4 text-sm">
                  <p className="font-semibold text-[var(--foreground)]">Очередь исходных данных недоступна для вашей роли</p>
                  <p className="app-text-muted mt-1 leading-relaxed">Доступные действия с расчётом показаны ниже и на вкладке «Готовность».</p>
                </div>
              ) : (
                <>
                  {!permissions.view_all ? (
                    <div className="app-feedback-warning mb-4 rounded-xl p-4 text-sm">
                      <p className="font-semibold">Общие итоги расчёта скрыты</p>
                      <p className="mt-1 leading-relaxed">Черновики, необходимые для проверки, доступны в очереди согласно вашей роли.</p>
                    </div>
                  ) : null}
                  {tableLoading ? (
                    <div className="flex min-h-32 items-center justify-center"><Loader2 className="app-accent-text animate-spin" size={22} /></div>
                  ) : tableError ? (
                    <div className="app-feedback-danger rounded-xl px-4 py-3 text-sm">{tableError}</div>
                  ) : (
                    <PayrollApprovalQueue rates={rates} workRecords={workRecords} inputLines={inputLines} currentUserId={user?.id} canApprove={canApproveSourceData} canOverrideApproval={permissions.override_approval} onApproveRate={openApproveRate} onApproveWork={openApproveWork} onApproveInput={openApproveInput} />
                  )}
                </>
              )}
              {workspace.current_run ? <div className="mt-5"><div className="mb-3 flex flex-wrap items-center justify-between gap-2"><h3 className="text-sm font-semibold text-[var(--foreground)]">Текущий расчёт</h3><div className="flex gap-2">{canReturn ? <button type="button" className="app-action-warning rounded-lg px-3 py-2 text-xs font-medium" onClick={openReturn}>Вернуть</button> : null}{primaryAction && primaryAction !== "calculate" ? <button type="button" className="app-action-primary rounded-lg px-3 py-2 text-xs font-semibold" onClick={() => openRunAction(primaryAction)}>{payrollRunActionLabels[primaryAction]}</button> : null}</div></div><RunCard run={workspace.current_run} current /></div> : null}
              {workspace.runs.length > 1 ? <details className="mt-4"><summary className="cursor-pointer text-sm font-medium text-[var(--foreground)]">История ревизий ({workspace.runs.length})</summary><div className="mt-3 grid gap-2">{workspace.runs.map((run) => <RunCard run={run} key={run.id} current={run.id === workspace.current_run?.id} />)}</div></details> : null}
            </section>
          ) : null}
        </>
      )}

      {periodModalOpen ? <PayrollPeriodFormModal isOpen period={editingPeriod} periods={workspace.periods} onClose={() => setPeriodModalOpen(false)} onSubmit={savePeriod} onSaved={async () => { setPeriodModalOpen(false); const createdPeriodId = createdPeriodIdRef.current; createdPeriodIdRef.current = null; if (createdPeriodId) { setNotice("Период создан и выбран."); await loadWorkspace(createdPeriodId, true); setTableVersion((value) => value + 1); } else { await refreshView("Параметры периода сохранены."); } }} onStale={handleStale} /> : null}
      {selectedPeriod && rateModalOpen ? <PayrollRateFormModal isOpen period={selectedPeriod} employees={workspace.employees} rate={editingRate} onClose={() => setRateModalOpen(false)} onSubmit={saveRate} onSaved={async () => { setRateModalOpen(false); await refreshView("Черновик ставки сохранён."); }} onStale={handleStale} /> : null}
      {selectedPeriod && bulkPayRateModalOpen ? <PayrollBulkPayRateModal isOpen period={selectedPeriod} employees={workspace.employees} rates={rates} onClose={() => setBulkPayRateModalOpen(false)} onSubmit={(payload) => apiClient.bulkCreatePayrollAdminPayRates(selectedPeriod.id, payload)} onSaved={async (result: PayrollBulkPayRateResult) => { setBulkPayRateModalOpen(false); const changed = result.summary.created_drafts + result.summary.updated_drafts + result.summary.created_revisions; const details = [result.summary.unchanged ? `без изменений: ${result.summary.unchanged}` : "", result.summary.skipped ? `пропущено: ${result.summary.skipped}` : ""].filter(Boolean).join(", "); await refreshView(`Ставка сохранена для ${changed} сотрудников${details ? ` (${details})` : ""}.`); }} onStale={handleStale} /> : null}
      {selectedPeriod && bulkPointRateModalOpen ? <PayrollBulkPointRateModal isOpen period={selectedPeriod} rates={rates} onClose={() => setBulkPointRateModalOpen(false)} onSubmit={(payload) => apiClient.bulkSetPayrollAdminPointRate(selectedPeriod.id, payload)} onSaved={async (result: PayrollBulkPointRateResult) => { setBulkPointRateModalOpen(false); const changed = result.summary.updated_drafts + result.summary.created_revisions; const details = [result.summary.unchanged ? `без изменений: ${result.summary.unchanged}` : "", result.summary.skipped ? `пропущено: ${result.summary.skipped}` : ""].filter(Boolean).join(", "); await refreshView(`Цена балла сверх нормы сохранена для ${changed} ставок${details ? ` (${details})` : ""}.`); }} onStale={handleStale} /> : null}
      {selectedPeriod && workModalOpen ? <PayrollWorkRecordFormModal isOpen period={selectedPeriod} employees={workspace.employees} record={editingWork} onClose={() => setWorkModalOpen(false)} onSubmit={saveWork} onSaved={async () => { setWorkModalOpen(false); await refreshView("Черновик выработки сохранён."); }} onStale={handleStale} /> : null}
      {selectedPeriod && attendanceWorkModalOpen ? (
        <PayrollAttendanceWorkModal
          isOpen
          period={selectedPeriod}
          onClose={() => setAttendanceWorkModalOpen(false)}
          onApplied={async (result) => {
            setAttendanceWorkModalOpen(false);
            setSearch("");
            setStatus("draft");
            await refreshView(buildPayrollAttendanceApplyNotice(result));
          }}
          onStale={handleStale}
        />
      ) : null}
      {selectedPeriod && inputModalOpen ? <PayrollInputLineFormModal isOpen period={selectedPeriod} periods={workspace.periods} employees={workspace.employees} components={workspace.components} line={editingInput} onClose={() => setInputModalOpen(false)} onSubmit={saveInput} onSaved={async () => { setInputModalOpen(false); await refreshView("Черновик операции сохранён."); }} onStale={handleStale} /> : null}
      {pendingAction ? <PayrollConfirmModal isOpen title={pendingAction.title} description={pendingAction.description} confirmLabel={pendingAction.confirmLabel} reasonLabel={pendingAction.reasonLabel} reasonRequired={pendingAction.reasonRequired} warning={pendingAction.warning} onClose={() => setPendingAction(null)} onConfirm={pendingAction.execute} onDone={async () => { const message = pendingAction.successMessage; setPendingAction(null); await refreshView(message); }} onStale={handleStale} /> : null}
    </div>
  );
}

function CalendarEmpty() {
  return <div className="app-badge-accent mx-auto flex h-12 w-12 items-center justify-center rounded-xl"><Calculator size={22} /></div>;
}
