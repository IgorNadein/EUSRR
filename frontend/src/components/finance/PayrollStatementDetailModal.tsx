"use client";

import {
  BadgeCheck,
  BriefcaseBusiness,
  Calculator,
  Check,
  CircleMinus,
  Clock3,
  CreditCard,
  FileCheck2,
  Loader2,
  RefreshCcw,
  RotateCcw,
  ShieldCheck,
  Sparkles,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { Modal } from "@/components/ui";
import { apiClient } from "@/lib/api";
import type {
  PayrollAcknowledgement,
  PayrollStatement,
  PayrollStatementSummary,
} from "@/lib/api/finance";
import {
  formatPayrollDate,
  formatPayrollDateTime,
  formatPayrollMoney,
  getPayrollLineDirection,
  getPayrollPeriodLabel,
  getPayrollPeriodRange,
  groupPayrollLines,
  type PayrollLineGroupKey,
} from "@/lib/payroll";

type PayrollStatementDetailModalProps = {
  isOpen: boolean;
  statement: PayrollStatementSummary | null;
  onClose: () => void;
  onAcknowledged: (publicId: string, acknowledgement: PayrollAcknowledgement) => void;
};

const groupIcons: Record<PayrollLineGroupKey, typeof BriefcaseBusiness> = {
  accruals: BriefcaseBusiness,
  adjustments: RefreshCcw,
  deductions: CircleMinus,
  payments: CreditCard,
};

function errorMessage(error: unknown): string {
  const message = error instanceof Error ? error.message : String(error);
  if (message.includes("404")) {
    return "Листок больше недоступен. Возможно, опубликована новая ревизия.";
  }
  if (message.includes("409")) {
    return "Не удалось подтвердить текущую ревизию. Обновите список и попробуйте ещё раз.";
  }
  return "Не удалось загрузить расчётный листок. Проверьте соединение и повторите попытку.";
}

function StatCard({ label, value, subtle }: { label: string; value: string; subtle?: string }) {
  return (
    <div className="app-surface-muted min-w-0 rounded-xl p-3">
      <p className="app-card-caption text-[0.68rem]">{label}</p>
      <p className="mt-1 truncate text-base font-semibold text-[var(--foreground)]" title={value}>
        {value}
      </p>
      {subtle ? <p className="app-text-muted mt-1 text-xs">{subtle}</p> : null}
    </div>
  );
}

export function PayrollStatementDetailModal({
  isOpen,
  statement,
  onClose,
  onAcknowledged,
}: PayrollStatementDetailModalProps) {
  const [detail, setDetail] = useState<PayrollStatement | null>(null);
  const [loading, setLoading] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [acknowledging, setAcknowledging] = useState(false);
  const [acknowledgeError, setAcknowledgeError] = useState<string | null>(null);
  const [confirmationOpen, setConfirmationOpen] = useState(false);
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    if (!isOpen || !statement) return;

    let cancelled = false;
    setDetail(null);
    setLoadError(null);
    setAcknowledgeError(null);
    setConfirmationOpen(false);
    setLoading(true);

    apiClient
      .getMyPayrollStatement(statement.public_id)
      .then((payload) => {
        if (!cancelled) setDetail(payload);
      })
      .catch((error: unknown) => {
        if (!cancelled) setLoadError(errorMessage(error));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [isOpen, statement, reloadKey]);

  const lineGroups = useMemo(() => groupPayrollLines(detail?.lines || []), [detail?.lines]);
  const acknowledgement = detail?.acknowledgement || statement?.acknowledgement || null;
  const isAcknowledged = Boolean(acknowledgement?.acknowledged_at);

  const handleAcknowledge = async () => {
    if (!detail || acknowledging || isAcknowledged) return;
    setAcknowledging(true);
    setAcknowledgeError(null);
    try {
      const nextAcknowledgement = await apiClient.acknowledgeMyPayrollStatement(detail.public_id);
      setDetail((current) => current ? { ...current, acknowledgement: nextAcknowledgement } : current);
      onAcknowledged(detail.public_id, nextAcknowledgement);
      setConfirmationOpen(false);
    } catch (error: unknown) {
      setAcknowledgeError(errorMessage(error));
    } finally {
      setAcknowledging(false);
    }
  };

  const footer = detail ? (
    <div className="app-divider flex flex-col gap-3 border-t pb-4 pt-4 sm:flex-row sm:items-center sm:justify-between sm:pb-6">
      <div className="min-w-0">
        {isAcknowledged ? (
          <div className="flex items-start gap-2 text-sm text-emerald-600">
            <BadgeCheck className="mt-0.5 shrink-0" size={18} />
            <div>
              <p className="font-semibold">Получение листка подтверждено</p>
              <p className="app-text-muted mt-0.5 text-xs">
                {formatPayrollDateTime(acknowledgement?.acknowledged_at)}
              </p>
            </div>
          </div>
        ) : (
          <div className="flex items-start gap-2">
            <ShieldCheck className="app-accent-text mt-0.5 shrink-0" size={18} />
            <p className="app-text-muted max-w-md text-xs leading-relaxed">
              Подтверждение фиксирует получение расчётного листка, но не является подтверждением банковской выплаты.
            </p>
          </div>
        )}
      </div>

      {!isAcknowledged ? (
        confirmationOpen ? (
          <div className="flex shrink-0 flex-col-reverse gap-2 sm:flex-row">
            <button
              type="button"
              className="app-action-secondary rounded-lg px-4 py-2.5 text-sm font-medium"
              onClick={() => setConfirmationOpen(false)}
              disabled={acknowledging}
            >
              Отмена
            </button>
            <button
              type="button"
              className="app-action-primary inline-flex items-center justify-center gap-2 rounded-lg px-4 py-2.5 text-sm font-semibold disabled:cursor-not-allowed disabled:opacity-60"
              onClick={handleAcknowledge}
              disabled={acknowledging}
            >
              {acknowledging ? <Loader2 className="animate-spin" size={17} /> : <Check size={17} />}
              Да, подтверждаю
            </button>
          </div>
        ) : (
          <button
            type="button"
            className="app-action-primary inline-flex shrink-0 items-center justify-center gap-2 rounded-lg px-4 py-2.5 text-sm font-semibold"
            onClick={() => setConfirmationOpen(true)}
          >
            <FileCheck2 size={17} />
            Подтвердить получение листка
          </button>
        )
      ) : null}
    </div>
  ) : null;

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title={statement ? `Расчётный листок · ${getPayrollPeriodLabel(statement.period)}` : "Расчётный листок"}
      size="lg"
      closeOnEsc={!acknowledging}
      footer={footer}
    >
      {loading ? (
        <div className="flex min-h-80 flex-col items-center justify-center py-12 text-center">
          <Loader2 className="app-accent-text animate-spin" size={30} />
          <p className="app-text-muted mt-4 text-sm">Загружаем защищённые данные листка…</p>
        </div>
      ) : loadError ? (
        <div className="flex min-h-72 flex-col items-center justify-center py-10 text-center">
          <div className="app-feedback-danger max-w-lg rounded-xl px-4 py-3 text-sm">{loadError}</div>
          <button
            type="button"
            className="app-action-secondary mt-4 inline-flex items-center gap-2 rounded-lg px-4 py-2.5 text-sm font-medium"
            onClick={() => setReloadKey((value) => value + 1)}
          >
            <RotateCcw size={16} />
            Повторить
          </button>
        </div>
      ) : detail ? (
        <div className="space-y-5">
          <section className="overflow-hidden rounded-2xl border border-[color:var(--accent-primary)]/20 bg-[color:var(--accent-soft)] p-4 sm:p-5">
            <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
              <div>
                <p className="app-text-muted text-xs">Расчётный период</p>
                <h4 className="mt-1 text-xl font-bold text-[var(--foreground)]">
                  Зарплата за {getPayrollPeriodLabel(detail.period).toLocaleLowerCase("ru-RU")}
                </h4>
                <p className="app-text-muted mt-1 text-sm">{getPayrollPeriodRange(detail.period)}</p>
              </div>
              <div className="sm:text-right">
                <p className="app-card-caption text-[0.7rem]">К выплате</p>
                <p className="app-accent-text mt-1 text-3xl font-bold tracking-tight">
                  {formatPayrollMoney(detail.payable, detail.currency)}
                </p>
                <p className="app-text-muted mt-1 flex items-center gap-1.5 text-xs sm:justify-end">
                  <Clock3 size={13} />
                  Дата выплаты: {formatPayrollDate(detail.period.pay_date)}
                </p>
              </div>
            </div>
          </section>

          <section>
            <div className="mb-3 flex items-center gap-2">
              <Calculator className="app-text-muted" size={17} />
              <h4 className="text-sm font-semibold text-[var(--foreground)]">Итоги расчёта</h4>
            </div>
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
              <StatCard label="До корректировок" value={formatPayrollMoney(detail.gross_before_adjustments, detail.currency)} />
              <StatCard label="Корректировки" value={formatPayrollMoney(detail.adjustment_total, detail.currency)} />
              <StatCard label="Удержания" value={formatPayrollMoney(detail.deduction_total, detail.currency)} />
              <StatCard label="Выплачено ранее" value={formatPayrollMoney(detail.payment_total, detail.currency)} />
            </div>
          </section>

          <section>
            <div className="mb-3 flex items-center gap-2">
              <Sparkles className="app-text-muted" size={17} />
              <h4 className="text-sm font-semibold text-[var(--foreground)]">Состав расчёта</h4>
            </div>
            {lineGroups.length > 0 ? (
              <div className="space-y-3">
                {lineGroups.map((group) => {
                  const Icon = groupIcons[group.key];
                  return (
                    <div key={group.key} className="app-surface-muted overflow-hidden rounded-xl">
                      <div className="app-divider flex items-center gap-2 border-b px-3 py-2.5 sm:px-4">
                        <Icon className="app-text-muted" size={16} />
                        <h5 className="text-xs font-semibold uppercase tracking-wide text-[var(--muted-foreground)]">
                          {group.label}
                        </h5>
                      </div>
                      <div className="divide-y divide-[var(--border-subtle)]">
                        {group.lines.map((line, index) => {
                          const direction = getPayrollLineDirection(line.kind);
                          const sourcePeriod = line.source_period_from && line.source_period_to
                            ? `${formatPayrollDate(line.source_period_from)} — ${formatPayrollDate(line.source_period_to)}`
                            : null;
                          return (
                            <div key={`${line.code}-${index}`} className="flex items-start justify-between gap-4 px-3 py-3 sm:px-4">
                              <div className="min-w-0">
                                <div className="flex flex-wrap items-center gap-1.5">
                                  <p className="text-sm font-medium text-[var(--foreground)]">{line.label}</p>
                                  {line.is_retro ? (
                                    <span className="app-badge app-badge-accent px-2 py-0.5 text-[0.65rem]">Перерасчёт</span>
                                  ) : null}
                                </div>
                                {sourcePeriod ? (
                                  <p className="app-text-muted mt-1 text-xs">За период: {sourcePeriod}</p>
                                ) : null}
                              </div>
                              <p className={`shrink-0 text-sm font-semibold ${direction === "negative" ? "text-amber-600" : "text-[var(--foreground)]"}`}>
                                {direction === "negative" ? "−" : "+"}
                                {formatPayrollMoney(line.amount, detail.currency)}
                              </p>
                            </div>
                          );
                        })}
                      </div>
                    </div>
                  );
                })}
              </div>
            ) : (
              <div className="app-surface-muted rounded-xl px-4 py-6 text-center">
                <p className="app-text-muted text-sm">Детализация начислений отсутствует.</p>
              </div>
            )}
          </section>

          <section className="app-surface-muted rounded-xl px-4 py-3 text-xs leading-relaxed text-[var(--muted-foreground)]">
            Листок опубликован {formatPayrollDateTime(detail.published_at)}.
          </section>

          {confirmationOpen && !isAcknowledged ? (
            <div className="app-feedback-warning rounded-xl px-4 py-3 text-sm">
              Проверьте суммы и состав расчёта. После подтверждения портал зафиксирует дату и время получения этого листка.
            </div>
          ) : null}
          {acknowledgeError ? (
            <div className="app-feedback-danger rounded-xl px-4 py-3 text-sm">{acknowledgeError}</div>
          ) : null}
        </div>
      ) : null}
    </Modal>
  );
}
