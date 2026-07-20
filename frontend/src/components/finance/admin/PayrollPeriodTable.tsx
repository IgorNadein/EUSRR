"use client";

import { CircleHelp, Eye, EyeOff, Loader2, Pencil, Search, X } from "lucide-react";
import { type ReactNode, useCallback, useEffect, useMemo, useRef, useState, useSyncExternalStore } from "react";
import { createPortal } from "react-dom";

import type {
  PayrollPeriodTable,
  PayrollPeriodTableComponent,
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
const HIDDEN_COLUMNS_STORAGE_PREFIX = "finances.payroll.period-table.hidden-columns";
const HIDDEN_COLUMNS_CHANGE_EVENT = "payroll-period-table-hidden-columns-change";

const columnIds = {
  rateAmount: "rate_amount",
  inNormPointRate: "in_norm_point_rate",
  excessPointRate: "point_rate",
  targetPoints: "target_points",
  attendancePoints: "attendance_points",
  personnelPoints: "personnel_points",
  actualPoints: "actual_points",
  pointDelta: "point_delta",
  pointAmount: "point_amount",
  grossBeforeAdjustments: "gross_before_adjustments",
  adjustments: "adjustment_total",
  gross: "gross_total",
  deductions: "deduction_total",
  net: "net_pay",
  payments: "payment_total",
  payable: "payable",
  status: "status",
} as const;

type ColumnDefinition = {
  id: string;
  label: string;
  group: string;
  width: number;
};

const salaryColumns: ColumnDefinition[] = [
  { id: columnIds.rateAmount, label: "Оклад", group: "Оклад и баллы", width: 75 },
  { id: columnIds.inNormPointRate, label: "Цена балла в норме", group: "Оклад и баллы", width: 75 },
  { id: columnIds.excessPointRate, label: "Цена балла сверх нормы", group: "Оклад и баллы", width: 75 },
];

const workColumns: ColumnDefinition[] = [
  { id: columnIds.targetPoints, label: "Норма", group: "Выработка", width: 55 },
  { id: columnIds.attendancePoints, label: "Баллы по посещаемости", group: "Выработка", width: 75 },
  { id: columnIds.personnelPoints, label: "Баллы по кадровым событиям", group: "Выработка", width: 82 },
  { id: columnIds.actualPoints, label: "Баллы", group: "Выработка", width: 55 },
  { id: columnIds.pointDelta, label: "Отклонение", group: "Выработка", width: 55 },
  { id: columnIds.pointAmount, label: "По баллам", group: "Выработка", width: 75 },
];

const calculationColumns: ColumnDefinition[] = [
  { id: columnIds.grossBeforeAdjustments, label: "До корректировок", group: "Расчёт", width: 80 },
  { id: columnIds.adjustments, label: "Корректировки", group: "Расчёт", width: 80 },
  { id: columnIds.gross, label: "Начислено", group: "Расчёт", width: 80 },
  { id: columnIds.deductions, label: "Удержано", group: "Расчёт", width: 80 },
  { id: columnIds.net, label: "После удержаний", group: "Расчёт", width: 80 },
  { id: columnIds.payments, label: "Выплачено", group: "Расчёт", width: 80 },
  { id: columnIds.payable, label: "К выплате", group: "Расчёт", width: 80 },
];

const statusColumn: ColumnDefinition = {
  id: columnIds.status,
  label: "Состояние",
  group: "Состояние",
  width: 90,
};

function componentColumnId(code: string): string {
  return `component:${code}`;
}

function parseHiddenColumns(value: string): Set<string> {
  try {
    const parsed: unknown = JSON.parse(value);
    return new Set(Array.isArray(parsed) ? parsed.filter((item): item is string => typeof item === "string") : []);
  } catch {
    return new Set();
  }
}

function useHiddenPayrollColumns(userId?: number | null) {
  const storageKey = `${HIDDEN_COLUMNS_STORAGE_PREFIX}.${userId || "default"}`;
  const subscribe = useCallback((notify: () => void) => {
    const handleStorage = (event: StorageEvent) => {
      if (event.key === storageKey) notify();
    };
    window.addEventListener("storage", handleStorage);
    window.addEventListener(HIDDEN_COLUMNS_CHANGE_EVENT, notify);
    return () => {
      window.removeEventListener("storage", handleStorage);
      window.removeEventListener(HIDDEN_COLUMNS_CHANGE_EVENT, notify);
    };
  }, [storageKey]);
  const getSnapshot = useCallback(
    () => window.localStorage.getItem(storageKey) || "[]",
    [storageKey],
  );
  const serialized = useSyncExternalStore(subscribe, getSnapshot, () => "[]");
  const hiddenColumns = useMemo(() => parseHiddenColumns(serialized), [serialized]);
  const setHiddenColumns = useCallback((next: Set<string>) => {
    window.localStorage.setItem(storageKey, JSON.stringify([...next].sort()));
    window.dispatchEvent(new Event(HIDDEN_COLUMNS_CHANGE_EVENT));
  }, [storageKey]);
  return [hiddenColumns, setHiddenColumns] as const;
}

type CalculationHelp = {
  title: string;
  logic: string;
  formula: string;
  manual: string;
};

function ColumnHeader({
  children,
  label,
  help,
  onOpen,
  onBulkEdit,
  onHide,
}: {
  children: ReactNode;
  label: string;
  help?: CalculationHelp;
  onOpen: (help: CalculationHelp) => void;
  onBulkEdit?: () => void;
  onHide: () => void;
}) {
  return (
    <span className="min-w-0 whitespace-normal break-words">
      {children}{" "}
      <span className="inline-flex translate-y-0.5 items-center gap-0.5 whitespace-nowrap align-baseline">
        {help ? (
          <button
            type="button"
            className="app-accent-text inline-flex h-4 w-4 items-center justify-center rounded-full transition hover:bg-[var(--surface-tertiary)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent-primary)]"
            onClick={() => onOpen(help)}
            aria-label={`Как рассчитывается «${help.title}»`}
            title="Показать логику расчёта"
          >
            <CircleHelp size={13} strokeWidth={2} />
          </button>
        ) : null}
        {onBulkEdit ? (
          <button
            type="button"
            className="app-text-muted inline-flex h-4 w-4 items-center justify-center rounded transition hover:bg-[var(--surface-tertiary)] hover:text-[var(--foreground)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent-primary)]"
            onClick={onBulkEdit}
            aria-label={`Массово заполнить колонку «${label}»`}
            title="Массовое заполнение"
          >
            <Pencil size={12} strokeWidth={2} />
          </button>
        ) : null}
        <button
          type="button"
          className="app-text-muted inline-flex h-4 w-4 items-center justify-center rounded transition hover:bg-[var(--surface-tertiary)] hover:text-[var(--foreground)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent-primary)]"
          onClick={onHide}
          aria-label={`Скрыть колонку «${label}»`}
          title="Скрыть колонку"
        >
          <Eye size={12} strokeWidth={2} />
        </button>
      </span>
    </span>
  );
}

function CalculationHelpModal({ help, rules, onClose }: { help: CalculationHelp; rules: PayrollPeriodTable["calculation_rules"]; onClose: () => void }) {
  const closeButtonRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    const previouslyFocused = document.activeElement as HTMLElement | null;
    closeButtonRef.current?.focus();
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    document.addEventListener("keydown", closeOnEscape);
    return () => {
      document.removeEventListener("keydown", closeOnEscape);
      previouslyFocused?.focus();
    };
  }, [onClose]);

  if (typeof document === "undefined") return null;
  const roundingLabel = rules.rounding === "ROUND_HALF_UP"
    ? "математическое"
    : rules.rounding === "ROUND_HALF_EVEN"
      ? "банковское"
      : "вниз";

  return createPortal(
    <div className="fixed inset-0 z-[1000] flex items-center justify-center p-4" role="presentation">
      <button type="button" className="absolute inset-0 bg-black/60" onClick={onClose} aria-label="Закрыть пояснение" />
      <section className="app-surface relative z-10 w-full max-w-lg rounded-2xl border border-[var(--border-subtle)] p-5 shadow-2xl" role="dialog" aria-modal="true" aria-labelledby="payroll-formula-title">
        <div className="flex items-start justify-between gap-4">
          <div className="min-w-0">
            <p className="app-text-muted text-xs uppercase tracking-wide">Логика расчёта</p>
            <h3 id="payroll-formula-title" className="mt-1 text-lg font-semibold text-[var(--foreground)]">{help.title}</h3>
          </div>
          <button ref={closeButtonRef} type="button" className="app-action-ghost inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-lg" onClick={onClose} aria-label="Закрыть"><X size={17} /></button>
        </div>
        <div className="mt-5 space-y-4 text-sm">
          <div>
            <p className="font-semibold text-[var(--foreground)]">Как формируется</p>
            <p className="app-text-muted mt-1 leading-relaxed">{help.logic}</p>
          </div>
          <div>
            <p className="font-semibold text-[var(--foreground)]">Формула</p>
            <div className="app-surface-muted mt-2 whitespace-pre-wrap rounded-xl px-3 py-2.5 font-mono text-xs leading-relaxed text-[var(--foreground)]">{help.formula}</div>
          </div>
          <div>
            <p className="font-semibold text-[var(--foreground)]">Можно изменить вручную?</p>
            <p className="app-text-muted mt-1 leading-relaxed">{help.manual}</p>
          </div>
        </div>
        <p className="app-text-muted mt-5 border-t border-[var(--border-subtle)] pt-3 text-xs leading-relaxed">Правила {rules.ruleset_id}, версия {rules.version}. Денежные строки округляются до {rules.money_quantum} ({roundingLabel} округление).</p>
      </section>
    </div>,
    document.body,
  );
}

function calculationHelps(pointPolicy: PayrollPeriodTable["calculation_rules"]["point_policy"]): Record<string, CalculationHelp> {
  const pointRecalculationLogic = pointPolicy === "proportional_with_excess"
    ? "Повторяет исходную Excel-таблицу: баллы изменяют общую базу из оклада и премии. Недовыполнение даёт отрицательный перерасчёт, перевыполнение — положительный."
    : pointPolicy === "excess_only"
      ? "Недовыполнение нормы не уменьшает начисление; оплачивается только превышение."
      : "Перерасчёт по баллам отключён текущими правилами.";
  const pointRecalculationFormula = pointPolicy === "proportional_with_excess"
    ? "Если цена сверх нормы пустая:\nПо баллам = ((Оклад + Премия) ÷ Норма × Баллы) − (Оклад + Премия)\n\nЕсли цена задана и Баллы > Норма:\nПо баллам = (Баллы − Норма) × Цена сверх нормы"
    : pointPolicy === "excess_only"
      ? "По баллам = max(Баллы − Норма, 0) × Цена балла сверх нормы"
      : "По баллам = 0";

  return {
    inNormPointRate: {
      title: "Цена балла в норме",
      logic: "Расчётная стоимость одного балла в исходной Excel-формуле. В балльную базу входят оклад и премия.",
      formula: "Цена балла в норме = (Оклад + Премия) ÷ Норма",
      manual: "Нет. Значение меняется через оклад, премию или норму баллов.",
    },
    excessPointRate: {
      title: "Цена балла сверх нормы",
      logic: pointPolicy === "disabled" ? "При текущем правиле балльная доплата отключена, поэтому цена не участвует в расчёте." : "Если отдельная цена не заполнена, система автоматически использует цену балла в норме. Можно задать индивидуальную цену.",
      formula: "Цена сверх нормы = указанная цена\nесли пусто: (Оклад + Премия) ÷ Норма",
      manual: "Да. Пустая ячейка возвращает автоматический расчёт по цене балла в норме.",
    },
    targetPoints: {
      title: "Норма",
      logic: "По умолчанию норма берётся из рабочего графика. Посещаемость определяет фактические рабочие дни, но часы не становятся баллами напрямую.",
      formula: "Норма = Дневная норма баллов × Рабочие дни",
      manual: "Да. Ручное значение заменяет автоматическую норму; очистка ячейки возвращает расчёт по графику.",
    },
    actualPoints: {
      title: "Баллы",
      logic: "Фактическую выработку можно ввести вручную или рассчитать из посещаемости. Полная смена даёт дневную норму баллов; неполная смена и переработка учитываются пропорционально.",
      formula: "Баллы дня = Дневная норма × Отработанные часы ÷ Плановые часы\nБаллы периода = Σ баллов рабочих дней",
      manual: "Да. Значение можно изменить в таблице или пересчитать из посещаемости.",
    },
    attendancePoints: {
      title: "Баллы по посещаемости",
      logic: "Вычисляются на ходу по доступным корректным записям посещаемости и не сохраняются в зарплате. Полная смена даёт дневную норму, неполная смена и переработка учитываются пропорционально. Если данных посещаемости нет, показывается прочерк.",
      formula: "Баллы дня = Дневная норма × Отработанные часы ÷ Плановые часы\nБаллы по посещаемости = Σ баллов доступных рабочих дней",
      manual: "Нет. Для изменения нужно исправить исходные данные посещаемости.",
    },
    personnelPoints: {
      title: "Баллы по кадровым событиям",
      logic: "Вычисляются на ходу по рабочему графику и официальным кадровым событиям. Каждый плановый рабочий день считается отработанным полностью, пока одобренное заявление или кадровое событие не подтверждает отсутствие. Отпуск, больничный, отгул, декрет и увольнение дают 0 баллов за затронутые рабочие дни; удалённая работа считается присутствием.",
      formula: "Баллы по кадровым событиям = Дневная норма × Рабочие дни без подтверждённого отсутствия",
      manual: "Нет. Для изменения нужно исправить заявление, его статус, кадровое событие или рабочий график.",
    },
    pointDelta: {
      title: "Отклонение",
      logic: "Показывает, насколько фактическая выработка выше или ниже нормы.",
      formula: "Отклонение = Баллы − Норма",
      manual: "Нет. Изменяется автоматически после изменения нормы или баллов.",
    },
    pointAmount: {
      title: "Перерасчёт по баллам",
      logic: pointRecalculationLogic,
      formula: pointRecalculationFormula,
      manual: "Нет. Меняется через оклад, премию, норму и баллы; при перевыполнении также через цену сверх нормы.",
    },
    grossBeforeAdjustments: {
      title: "До корректировок",
      logic: "Сумма исходных начислений до положительных, отрицательных и балльной корректировок.",
      formula: "До корректировок = Оклад + Отпускные + Премия + Разовые + Σ прочих начислений",
      manual: "Нет. Итог пересчитывается из исходных ячеек и строк начислений.",
    },
    adjustments: {
      title: "Корректировки",
      logic: "Объединяет ручные корректировки и подписанный перерасчёт по баллам. Положительное значение увеличивает начисление, отрицательное — уменьшает.",
      formula: "Корректировки = Σ ручных положительных − Σ ручных отрицательных + Перерасчёт по баллам",
      manual: "Нет. Итог меняется через соответствующие строки корректировок.",
    },
    gross: {
      title: "Начислено",
      logic: "Общая сумма начисления до удержаний и учёта уже выплаченных сумм.",
      formula: "Начислено = До корректировок + Корректировки",
      manual: "Нет. Пересчитывается автоматически из начислений и корректировок.",
    },
    deductions: {
      title: "Удержано",
      logic: "Сумма всех действующих строк с типом «Удержание» за выбранный период.",
      formula: "Удержано = Σ удержаний",
      manual: "Нет. Итог меняется через строки удержаний.",
    },
    net: {
      title: "После удержаний",
      logic: "Сумма, оставшаяся после вычета удержаний, но до учёта уже записанных выплат.",
      formula: "После удержаний = Начислено − Удержано",
      manual: "Нет. Пересчитывается автоматически.",
    },
    payments: {
      title: "Выплачено",
      logic: "Сумма уже произведённых выплат за период, например авансов.",
      formula: "Выплачено = Σ строк с типом «Выплата»",
      manual: "Нет. Итог меняется через строки выплат.",
    },
    payable: {
      title: "К выплате",
      logic: "Остаток, который ещё нужно выплатить сотруднику.",
      formula: "К выплате = После удержаний − Выплачено",
      manual: "Нет. Пересчитывается автоматически из связанных сумм.",
    },
    status: {
      title: "Состояние",
      logic: "Система показывает готовность строки по наличию ставки, выработки, черновиков и сохранённого результата расчёта.",
      formula: "Нет ставки или выработки → Не заполнено\nЕсть черновики → Есть черновики\nВсе входы утверждены → Готово\nЕсть результат расчёта → Рассчитано",
      manual: "Нет. Состояние меняется автоматически вместе с данными и этапом расчёта.",
    },
  };
}

function componentCalculationHelp(component: PayrollPeriodTableComponent): CalculationHelp {
  const effect = {
    earning: "входит в сумму «До корректировок»",
    adjustment_credit: "увеличивает сумму «Корректировки»",
    adjustment_debit: "уменьшает сумму «Корректировки»",
    deduction: "входит в сумму «Удержано»",
    payment: "входит в сумму «Выплачено»",
  }[component.kind];
  return {
    title: component.label,
    logic: `Показана сумма всех действующих операций «${component.label}» сотрудника за период. Этот вид операции ${effect}.`,
    formula: `${component.label} = Σ операций этого вида за период`,
    manual: "Да. Ввод нового итога в ячейку создаёт или обновляет черновик операции на разницу. Утверждённые суммы исправляются новой операцией.",
  };
}

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
  storageUserId,
  canEdit = false,
  onBulkEditRate,
  onBulkEditPointRate,
  onBulkEditTargetPoints,
  onSaveRate,
  onSaveWork,
  onSaveComponent,
}: {
  data: PayrollPeriodTable | null;
  loading: boolean;
  error: string | null;
  search: string;
  onSearch: (value: string) => void;
  storageUserId?: number | null;
  canEdit?: boolean;
  onBulkEditRate?: () => void;
  onBulkEditPointRate?: () => void;
  onBulkEditTargetPoints?: () => void;
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
  const [activeHelp, setActiveHelp] = useState<CalculationHelp | null>(null);
  const [columnsMenuOpen, setColumnsMenuOpen] = useState(false);
  const columnsMenuRef = useRef<HTMLDivElement>(null);
  const [hiddenColumns, setHiddenColumns] = useHiddenPayrollColumns(storageUserId);
  const componentColumns = useMemo(() => data?.component_columns || [], [data?.component_columns]);
  const componentDefinitions = useMemo<ColumnDefinition[]>(() => (
    componentColumns.map((component) => ({
      id: componentColumnId(component.code),
      label: component.label,
      group: "Начисления и выплаты",
      width: 75,
    }))
  ), [componentColumns]);
  const allColumns = useMemo(
    () => [...salaryColumns, ...workColumns, ...componentDefinitions, ...calculationColumns, statusColumn],
    [componentDefinitions],
  );
  const hiddenCurrentColumns = allColumns.filter((column) => hiddenColumns.has(column.id));
  const isVisible = (columnId: string) => !hiddenColumns.has(columnId);
  const visibleSalaryColumns = salaryColumns.filter((column) => isVisible(column.id));
  const visibleWorkColumns = workColumns.filter((column) => isVisible(column.id));
  const visibleComponentColumns = componentColumns.filter((component) => isVisible(componentColumnId(component.code)));
  const visibleCalculationColumns = calculationColumns.filter((column) => isVisible(column.id));
  const visibleColumnCount = 1 + visibleSalaryColumns.length + visibleWorkColumns.length + visibleComponentColumns.length + visibleCalculationColumns.length + (isVisible(columnIds.status) ? 1 : 0);

  const hideColumn = (columnId: string) => {
    const next = new Set(hiddenColumns);
    next.add(columnId);
    setHiddenColumns(next);
  };
  const showColumn = (columnId: string) => {
    const next = new Set(hiddenColumns);
    next.delete(columnId);
    setHiddenColumns(next);
    if (hiddenCurrentColumns.length === 1) setColumnsMenuOpen(false);
  };

  useEffect(() => {
    if (!columnsMenuOpen) return;
    const closeOnOutsideClick = (event: MouseEvent) => {
      if (!columnsMenuRef.current?.contains(event.target as Node)) setColumnsMenuOpen(false);
    };
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") setColumnsMenuOpen(false);
    };
    document.addEventListener("mousedown", closeOnOutsideClick);
    document.addEventListener("keydown", closeOnEscape);
    return () => {
      document.removeEventListener("mousedown", closeOnOutsideClick);
      document.removeEventListener("keydown", closeOnEscape);
    };
  }, [columnsMenuOpen]);

  if (loading && !data) {
    return <div className="flex min-h-56 items-center justify-center"><Loader2 className="app-accent-text animate-spin" size={24} /></div>;
  }
  if (error) return <div className="app-feedback-danger rounded-xl px-4 py-3 text-sm">{error}</div>;
  if (!data) return null;

  const tableWidth = 150 + allColumns.reduce(
    (width, column) => width + (isVisible(column.id) ? column.width : 0),
    0,
  );
  const helps = calculationHelps(data.calculation_rules.point_policy);
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
        <div className="flex min-w-0 flex-col gap-2 sm:flex-row sm:items-center">
          <label className="relative block min-w-0 sm:w-72">
            <Search className="app-text-muted pointer-events-none absolute left-3 top-1/2 -translate-y-1/2" size={15} />
            <input
              className="app-input w-full rounded-lg py-2.5 pl-9 pr-3 text-sm"
              value={search}
              placeholder="Поиск по сотрудникам"
              onChange={(event) => onSearch(event.target.value)}
            />
          </label>
          <div ref={columnsMenuRef} className="relative shrink-0">
            <button
              type="button"
              className="app-action-secondary inline-flex w-full items-center justify-center gap-2 rounded-lg px-3 py-2.5 text-sm font-medium disabled:cursor-default disabled:opacity-60 sm:w-auto"
              onClick={() => setColumnsMenuOpen((open) => !open)}
              disabled={!hiddenCurrentColumns.length}
              aria-expanded={columnsMenuOpen}
              aria-haspopup="menu"
            >
              <Eye size={15} />
              Показать колонки
              {hiddenCurrentColumns.length ? <span className="app-counter inline-flex h-5 min-w-5 px-1 text-[10px]">{hiddenCurrentColumns.length}</span> : null}
            </button>
            {columnsMenuOpen && hiddenCurrentColumns.length ? (
              <div className="app-surface absolute right-0 top-full z-50 mt-2 w-72 overflow-hidden rounded-xl border border-[var(--border-subtle)] p-2 shadow-2xl" role="menu" aria-label="Скрытые колонки">
                <p className="app-text-muted px-2 pb-2 pt-1 text-[10px] font-semibold uppercase tracking-wide">Скрытые колонки</p>
                <div className="max-h-72 overflow-y-auto">
                  {hiddenCurrentColumns.map((column) => (
                    <button
                      key={column.id}
                      type="button"
                      className="app-action-ghost flex w-full items-center gap-2 rounded-lg px-2.5 py-2 text-left"
                      onClick={() => showColumn(column.id)}
                      role="menuitem"
                      title={`Показать колонку «${column.label}»`}
                    >
                      <EyeOff className="app-text-muted shrink-0" size={15} />
                      <span className="min-w-0 flex-1">
                        <span className="block truncate text-xs font-medium text-[var(--foreground)]">{column.label}</span>
                        <span className="app-text-muted block truncate text-[10px]">{column.group}</span>
                      </span>
                      <span className="app-accent-text text-[10px]">Показать</span>
                    </button>
                  ))}
                </div>
                {hiddenCurrentColumns.length > 1 ? (
                  <button
                    type="button"
                    className="app-action-secondary mt-2 inline-flex w-full items-center justify-center gap-2 rounded-lg px-3 py-2 text-xs font-medium"
                    onClick={() => {
                      setHiddenColumns(new Set());
                      setColumnsMenuOpen(false);
                    }}
                  >
                    <Eye size={14} /> Показать все
                  </button>
                ) : null}
              </div>
            ) : null}
          </div>
        </div>
      </div>

      {data.summary.preliminary_count ? (
        <div className="app-feedback-warning mb-3 rounded-lg px-3 py-2.5 text-sm">
          Значения рассчитаны предварительно по текущим данным. Они обновляются после сохранения ячеек и станут официальными после запуска расчёта.
        </div>
      ) : null}

      <div className="app-text-muted mb-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs">
        {canEdit ? <span>Enter или переход в другую ячейку — сохранить, Esc — отменить.</span> : null}
        <span className="inline-flex items-center gap-1.5"><span className="h-2.5 w-2.5 rounded-sm bg-[var(--muted-foreground)]" aria-hidden="true" />Серый текст — заполнено автоматически</span>
        <span className="inline-flex items-center gap-1.5"><CircleHelp className="app-accent-text" size={13} />Знак вопроса — логика и формула расчёта</span>
      </div>

      <div className="app-table-scroll max-h-[min(70vh,760px)] w-full max-w-full overflow-auto overscroll-contain rounded-xl border border-[var(--border-subtle)]">
        <table className="table-fixed border-separate border-spacing-0" style={{ width: `max(100%, ${tableWidth}px)` }} aria-label="Итоговая таблица расчётного периода">
          <colgroup>
            <col style={{ width: 150 }} />
            {[...visibleSalaryColumns, ...visibleWorkColumns].map((column) => <col key={column.id} style={{ width: column.width }} />)}
            {visibleComponentColumns.map((component) => <col key={component.code} style={{ width: 75 }} />)}
            {visibleCalculationColumns.map((column) => <col key={column.id} style={{ width: column.width }} />)}
            {isVisible(columnIds.status) ? <col style={{ width: statusColumn.width }} /> : null}
          </colgroup>
          <thead className="sticky top-0 z-20">
            <tr>
              <th rowSpan={2} className={`${headerCellClass} sticky left-0 z-30 align-middle`}>Сотрудник</th>
              {visibleSalaryColumns.length ? <th colSpan={visibleSalaryColumns.length} className={`${headerCellClass} text-center uppercase tracking-wide`}>Оклад и баллы</th> : null}
              {visibleWorkColumns.length ? <th colSpan={visibleWorkColumns.length} className={`${headerCellClass} text-center uppercase tracking-wide`}>Выработка</th> : null}
              {visibleComponentColumns.length ? <th colSpan={visibleComponentColumns.length} className={`${headerCellClass} text-center uppercase tracking-wide`}>Начисления и выплаты</th> : null}
              {visibleCalculationColumns.length ? <th colSpan={visibleCalculationColumns.length} className={`${headerCellClass} text-center uppercase tracking-wide`}>Расчёт</th> : null}
              {isVisible(columnIds.status) ? (
                <th rowSpan={2} className={`${headerCellClass} align-middle`}>
                  <ColumnHeader label="Состояние" help={helps.status} onOpen={setActiveHelp} onHide={() => hideColumn(columnIds.status)}>Состояние</ColumnHeader>
                </th>
              ) : null}
            </tr>
            <tr>
              {isVisible(columnIds.rateAmount) ? (
                <th className={`${headerCellClass} text-right`}><ColumnHeader label="Оклад" onOpen={setActiveHelp} onBulkEdit={onBulkEditRate} onHide={() => hideColumn(columnIds.rateAmount)}>Оклад</ColumnHeader></th>
              ) : null}
              {isVisible(columnIds.inNormPointRate) ? (
                <th className={`${headerCellClass} whitespace-normal text-right`}>
                  <ColumnHeader label="Цена балла в норме" help={helps.inNormPointRate} onOpen={setActiveHelp} onHide={() => hideColumn(columnIds.inNormPointRate)}>Цена балла в норме</ColumnHeader>
                </th>
              ) : null}
              {isVisible(columnIds.excessPointRate) ? (
                <th className={`${headerCellClass} whitespace-normal text-right`}>
                  <ColumnHeader label="Цена балла сверх нормы" help={helps.excessPointRate} onOpen={setActiveHelp} onBulkEdit={onBulkEditPointRate} onHide={() => hideColumn(columnIds.excessPointRate)}>Цена балла сверх нормы</ColumnHeader>
                </th>
              ) : null}
              {isVisible(columnIds.targetPoints) ? <th className={`${headerCellClass} text-right`}><ColumnHeader label="Норма баллов" help={helps.targetPoints} onOpen={setActiveHelp} onBulkEdit={onBulkEditTargetPoints} onHide={() => hideColumn(columnIds.targetPoints)}>Норма</ColumnHeader></th> : null}
              {isVisible(columnIds.attendancePoints) ? <th className={`${headerCellClass} text-right`}><ColumnHeader label="Баллы по посещаемости" help={helps.attendancePoints} onOpen={setActiveHelp} onHide={() => hideColumn(columnIds.attendancePoints)}>Баллы по посещаемости</ColumnHeader></th> : null}
              {isVisible(columnIds.personnelPoints) ? <th className={`${headerCellClass} text-right`}><ColumnHeader label="Баллы по кадровым событиям" help={helps.personnelPoints} onOpen={setActiveHelp} onHide={() => hideColumn(columnIds.personnelPoints)}>Баллы по кадровым событиям</ColumnHeader></th> : null}
              {isVisible(columnIds.actualPoints) ? <th className={`${headerCellClass} text-right`}><ColumnHeader label="Баллы" help={helps.actualPoints} onOpen={setActiveHelp} onHide={() => hideColumn(columnIds.actualPoints)}>Баллы</ColumnHeader></th> : null}
              {isVisible(columnIds.pointDelta) ? <th className={`${headerCellClass} text-right`}><ColumnHeader label="Отклонение" help={helps.pointDelta} onOpen={setActiveHelp} onHide={() => hideColumn(columnIds.pointDelta)}>Отклонение</ColumnHeader></th> : null}
              {isVisible(columnIds.pointAmount) ? <th className={`${headerCellClass} text-right`}><ColumnHeader label="По баллам" help={helps.pointAmount} onOpen={setActiveHelp} onHide={() => hideColumn(columnIds.pointAmount)}>По баллам</ColumnHeader></th> : null}
              {visibleComponentColumns.map((component) => (
                <th key={component.code} className={`${headerCellClass} text-right whitespace-normal break-words`} title={`${component.label} · ${kindLabels[component.kind]}`}>
                  <ColumnHeader label={component.label} help={componentCalculationHelp(component)} onOpen={setActiveHelp} onHide={() => hideColumn(componentColumnId(component.code))}>{component.label}</ColumnHeader>
                </th>
              ))}
              {isVisible(columnIds.grossBeforeAdjustments) ? <th className={`${headerCellClass} text-right`}><ColumnHeader label="До корректировок" help={helps.grossBeforeAdjustments} onOpen={setActiveHelp} onHide={() => hideColumn(columnIds.grossBeforeAdjustments)}>До коррект.</ColumnHeader></th> : null}
              {isVisible(columnIds.adjustments) ? <th className={`${headerCellClass} text-right`}><ColumnHeader label="Корректировки" help={helps.adjustments} onOpen={setActiveHelp} onHide={() => hideColumn(columnIds.adjustments)}>Корректировки</ColumnHeader></th> : null}
              {isVisible(columnIds.gross) ? <th className={`${headerCellClass} text-right`}><ColumnHeader label="Начислено" help={helps.gross} onOpen={setActiveHelp} onHide={() => hideColumn(columnIds.gross)}>Начислено</ColumnHeader></th> : null}
              {isVisible(columnIds.deductions) ? <th className={`${headerCellClass} text-right`}><ColumnHeader label="Удержано" help={helps.deductions} onOpen={setActiveHelp} onHide={() => hideColumn(columnIds.deductions)}>Удержано</ColumnHeader></th> : null}
              {isVisible(columnIds.net) ? <th className={`${headerCellClass} text-right`}><ColumnHeader label="После удержаний" help={helps.net} onOpen={setActiveHelp} onHide={() => hideColumn(columnIds.net)}>После удерж.</ColumnHeader></th> : null}
              {isVisible(columnIds.payments) ? <th className={`${headerCellClass} text-right`}><ColumnHeader label="Выплачено" help={helps.payments} onOpen={setActiveHelp} onHide={() => hideColumn(columnIds.payments)}>Выплачено</ColumnHeader></th> : null}
              {isVisible(columnIds.payable) ? <th className={`${headerCellClass} text-right`}><ColumnHeader label="К выплате" help={helps.payable} onOpen={setActiveHelp} onHide={() => hideColumn(columnIds.payable)}>К выплате</ColumnHeader></th> : null}
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
                  {isVisible(columnIds.rateAmount) ? <InlineEditableCell value={row.rate_amount} formattedValue={formatMoney(row.rate_amount, data.currency)} onSave={canEdit && onSaveRate ? (value) => onSaveRate(row, "amount", value) : undefined} label={`Оклад: ${row.employee.display_name}`} /> : null}
                  {isVisible(columnIds.inNormPointRate) ? <InlineEditableCell value={row.in_norm_point_rate} formattedValue={formatMoney(row.in_norm_point_rate, data.currency)} label={`Цена балла в пределах нормы: ${row.employee.display_name}`} automatic /> : null}
                  {isVisible(columnIds.excessPointRate) ? <InlineEditableCell value={row.point_rate ?? row.in_norm_point_rate} formattedValue={formatMoney(row.point_rate ?? row.in_norm_point_rate, data.currency)} onSave={canEdit && onSaveRate ? (value) => onSaveRate(row, "point_rate", value) : undefined} label={`Цена балла сверх нормы: ${row.employee.display_name}`} automatic={row.point_rate === null} /> : null}
                  {isVisible(columnIds.targetPoints) ? <InlineEditableCell value={row.target_points} formattedValue={formatPoints(row.target_points)} onSave={canEdit && onSaveWork ? (value) => onSaveWork(row, "target_points", value) : undefined} label={`Норма: ${row.employee.display_name}`} automatic={row.target_points_automatic} /> : null}
                  {isVisible(columnIds.attendancePoints) ? <InlineEditableCell value={row.attendance_points} formattedValue={formatPoints(row.attendance_points)} label={`Баллы по посещаемости: ${row.employee.display_name}`} automatic /> : null}
                  {isVisible(columnIds.personnelPoints) ? <InlineEditableCell value={row.personnel_points} formattedValue={formatPoints(row.personnel_points)} label={`Баллы по кадровым событиям: ${row.employee.display_name}`} automatic /> : null}
                  {isVisible(columnIds.actualPoints) ? <InlineEditableCell value={row.actual_points} formattedValue={formatPoints(row.actual_points)} onSave={canEdit && onSaveWork ? (value) => onSaveWork(row, "actual_points", value) : undefined} label={`Баллы: ${row.employee.display_name}`} /> : null}
                  {isVisible(columnIds.pointDelta) ? <td className={bodyCellClass}>{formatPoints(row.point_delta)}</td> : null}
                  {isVisible(columnIds.pointAmount) ? <td className={bodyCellClass}><CalculatedMoney value={row.point_amount} currency={data.currency} preliminary={row.totals_preliminary} /></td> : null}
                  {visibleComponentColumns.map((component) => (
                    <InlineEditableCell key={component.code} value={row.component_amounts[component.code] || null} formattedValue={formatMoney(row.component_amounts[component.code] || null, data.currency)} onSave={canEdit && onSaveComponent ? (value) => onSaveComponent(row, component.code, value) : undefined} label={`${component.label}: ${row.employee.display_name}`} />
                  ))}
                  {isVisible(columnIds.grossBeforeAdjustments) ? <td className={bodyCellClass}><CalculatedMoney value={row.gross_before_adjustments} currency={data.currency} preliminary={row.totals_preliminary} /></td> : null}
                  {isVisible(columnIds.adjustments) ? <td className={bodyCellClass}><CalculatedMoney value={row.adjustment_total} currency={data.currency} preliminary={row.totals_preliminary} /></td> : null}
                  {isVisible(columnIds.gross) ? <td className={`${bodyCellClass} font-semibold`}><CalculatedMoney value={row.gross_total} currency={data.currency} preliminary={row.totals_preliminary} /></td> : null}
                  {isVisible(columnIds.deductions) ? <td className={bodyCellClass}><CalculatedMoney value={row.deduction_total} currency={data.currency} preliminary={row.totals_preliminary} /></td> : null}
                  {isVisible(columnIds.net) ? <td className={bodyCellClass}><CalculatedMoney value={row.net_pay} currency={data.currency} preliminary={row.totals_preliminary} /></td> : null}
                  {isVisible(columnIds.payments) ? <td className={bodyCellClass}><CalculatedMoney value={row.payment_total} currency={data.currency} preliminary={row.totals_preliminary} /></td> : null}
                  {isVisible(columnIds.payable) ? <td className={`${bodyCellClass} font-semibold`}><CalculatedMoney value={row.payable} currency={data.currency} preliminary={row.totals_preliminary} /></td> : null}
                  {isVisible(columnIds.status) ? <td className="overflow-hidden border-b border-r border-[var(--border-subtle)] px-1 py-2 text-center"><span className={`app-status-pill px-2 text-[10px] ${meta.className}`}>{meta.label}</span></td> : null}
                </tr>
              );
            }) : (
              <tr><td colSpan={visibleColumnCount} className="app-text-muted px-4 py-10 text-center text-sm">Сотрудники не найдены.</td></tr>
            )}
          </tbody>
          {rows.length ? (
            <tfoot>
              <tr className="app-surface-muted font-semibold">
                <td className="sticky left-0 z-10 border-r border-[var(--border-subtle)] bg-[var(--surface-secondary)] px-3 py-3 text-xs text-[var(--foreground)]">Итого · {rows.length}</td>
                {isVisible(columnIds.rateAmount) ? <td className={bodyCellClass}>{formatMoney(total("rate_amount"), data.currency)}</td> : null}
                {isVisible(columnIds.inNormPointRate) ? <td className={bodyCellClass}>—</td> : null}
                {isVisible(columnIds.excessPointRate) ? <td className={bodyCellClass}>—</td> : null}
                {isVisible(columnIds.targetPoints) ? <td className={bodyCellClass}>{formatPoints(total("target_points"))}</td> : null}
                {isVisible(columnIds.attendancePoints) ? <td className={bodyCellClass}>{formatPoints(total("attendance_points"))}</td> : null}
                {isVisible(columnIds.personnelPoints) ? <td className={bodyCellClass}>{formatPoints(total("personnel_points"))}</td> : null}
                {isVisible(columnIds.actualPoints) ? <td className={bodyCellClass}>{formatPoints(total("actual_points"))}</td> : null}
                {isVisible(columnIds.pointDelta) ? <td className={bodyCellClass}>{formatPoints(total("point_delta"))}</td> : null}
                {isVisible(columnIds.pointAmount) ? <td className={bodyCellClass}>{formatMoney(total("point_amount"), data.currency)}</td> : null}
                {visibleComponentColumns.map((component) => (
                  <td key={component.code} className={bodyCellClass}>{formatMoney(sumRows(rows, (row) => row.component_amounts[component.code] || null), data.currency)}</td>
                ))}
                {isVisible(columnIds.grossBeforeAdjustments) ? <td className={bodyCellClass}>{formatMoney(total("gross_before_adjustments"), data.currency)}</td> : null}
                {isVisible(columnIds.adjustments) ? <td className={bodyCellClass}>{formatMoney(total("adjustment_total"), data.currency)}</td> : null}
                {isVisible(columnIds.gross) ? <td className={bodyCellClass}>{formatMoney(total("gross_total"), data.currency)}</td> : null}
                {isVisible(columnIds.deductions) ? <td className={bodyCellClass}>{formatMoney(total("deduction_total"), data.currency)}</td> : null}
                {isVisible(columnIds.net) ? <td className={bodyCellClass}>{formatMoney(total("net_pay"), data.currency)}</td> : null}
                {isVisible(columnIds.payments) ? <td className={bodyCellClass}>{formatMoney(total("payment_total"), data.currency)}</td> : null}
                {isVisible(columnIds.payable) ? <td className={bodyCellClass}>{formatMoney(total("payable"), data.currency)}</td> : null}
                {isVisible(columnIds.status) ? <td className="border-r border-[var(--border-subtle)] px-3 py-3" /> : null}
              </tr>
            </tfoot>
          ) : null}
        </table>
      </div>
      {activeHelp ? <CalculationHelpModal help={activeHelp} rules={data.calculation_rules} onClose={() => setActiveHelp(null)} /> : null}
    </div>
  );
}
