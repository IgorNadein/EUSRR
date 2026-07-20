"use client";

import {
  ArrowRight,
  BadgeCheck,
  CalendarDays,
  ChevronRight,
  Clock3,
  History,
  Loader2,
  RefreshCw,
  Wallet,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";

import { AppShell } from "@/components/AppShell";
import { PayrollDailyWorkSection } from "@/components/finance/PayrollDailyWorkSection";
import { PayrollStatementDetailModal } from "@/components/finance/PayrollStatementDetailModal";
import { PayrollAdminWorkspace } from "@/components/finance/admin/PayrollAdminWorkspace";
import { useUser } from "@/contexts/UserContext";
import { usePayrollDesktopWideMode } from "@/hooks/usePayrollDesktopWideMode";
import { usePayrollFinanceTab } from "@/hooks/usePayrollTabs";
import { apiClient } from "@/lib/api";
import type { PayrollAcknowledgement, PayrollStatementSummary } from "@/lib/api/finance";
import { canOpenPayrollAdmin } from "@/lib/permissions";
import {
  formatPayrollDate,
  formatPayrollMoney,
  getPayrollPeriodLabel,
  getPayrollPeriodRange,
  normalizePayrollStatements,
} from "@/lib/payroll";

function listErrorMessage(error: unknown): string {
  const message = error instanceof Error ? error.message : String(error);
  if (message.includes("401")) return "Сессия истекла. Войдите в портал ещё раз.";
  return "Не удалось загрузить расчётные листки. Проверьте соединение и повторите попытку.";
}

function StatementStatus({ statement }: { statement: PayrollStatementSummary }) {
  if (statement.acknowledgement?.disputed_at) {
    return <span className="app-status-pill app-action-warning">Есть обращение</span>;
  }
  if (statement.acknowledgement?.acknowledged_at) {
    return (
      <span className="app-status-pill app-action-success gap-1.5">
        <BadgeCheck size={13} />
        Подтверждён
      </span>
    );
  }
  return (
    <span className="app-status-pill app-badge-accent gap-1.5">
      <Clock3 size={13} />
      Ждёт подтверждения
    </span>
  );
}

function EmptyPayroll() {
  return (
    <section className="app-surface rounded-2xl p-5 sm:p-8">
      <div className="app-surface-muted mx-auto flex max-w-xl flex-col items-center rounded-2xl px-5 py-10 text-center sm:px-8">
        <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-[color:var(--accent-soft)] text-[var(--accent-primary-strong)]">
          <Wallet size={27} />
        </div>
        <h2 className="mt-5 text-lg font-semibold text-[var(--foreground)]">Расчётных листков пока нет</h2>
        <p className="app-text-muted mt-2 max-w-md text-sm leading-relaxed">
          Здесь появятся ваши зарплатные расчёты после проверки и публикации финансовым отделом.
        </p>
      </div>
    </section>
  );
}

export default function FinancesPage() {
  const { user } = useUser();
  const showPayrollAdmin = canOpenPayrollAdmin(user);
  const [activeTab, setActiveTab] = usePayrollFinanceTab(user?.id, showPayrollAdmin);
  const [statements, setStatements] = useState<PayrollStatementSummary[]>([]);
  const [selectedStatement, setSelectedStatement] = useState<PayrollStatementSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [reloadKey, setReloadKey] = useState(0);
  const [desktopWideMode, changeDesktopWideMode] = usePayrollDesktopWideMode(user?.id);

  const loadStatements = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const payload = await apiClient.getMyPayrollStatements();
      setStatements(normalizePayrollStatements(payload));
    } catch (loadError: unknown) {
      setError(listErrorMessage(loadError));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadStatements();
  }, [loadStatements, reloadKey]);

  const latestStatement = statements[0] || null;
  const pendingCount = useMemo(
    () => statements.filter((statement) => !statement.acknowledgement?.acknowledged_at).length,
    [statements],
  );
  const previousStatements = statements.slice(1);
  const handleAcknowledged = (publicId: string, acknowledgement: PayrollAcknowledgement) => {
    setStatements((current) => current.map((statement) => (
      statement.public_id === publicId ? { ...statement, acknowledgement } : statement
    )));
    setSelectedStatement((current) => (
      current?.public_id === publicId ? { ...current, acknowledgement } : current
    ));
  };

  return (
    <AppShell
      desktopWideMode={activeTab === "management" && desktopWideMode}
      onDesktopWideModeChange={changeDesktopWideMode}
    >
      <div className={`min-w-0 space-y-6 ${activeTab === "management" && desktopWideMode ? "lg:min-h-0 lg:flex-1 lg:overflow-y-auto lg:pr-1" : ""}`}>
        <section className="app-surface rounded-2xl p-4 sm:p-5">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <p className="app-card-caption">Финансы</p>
          {activeTab === "management" && showPayrollAdmin ? (
            <div id="finance-management-actions" className="ml-auto max-w-full" />
          ) : null}
        </div>

        {activeTab === "management" && showPayrollAdmin ? (
          <div id="finance-management-header" className="mt-4" />
        ) : null}

        <div className="mt-4 flex flex-wrap items-center gap-2">
          <button
            type="button"
            onClick={() => setActiveTab("statement")}
            className={`inline-flex h-10 items-center rounded-full px-4 text-sm font-medium transition ${activeTab === "statement" ? "app-pill-active" : "app-pill"}`}
          >
            Расчётный лист
          </button>
          <button
            type="button"
            onClick={() => {
              setSelectedStatement(null);
              setActiveTab("work");
            }}
            className={`inline-flex h-10 items-center rounded-full px-4 text-sm font-medium transition ${activeTab === "work" ? "app-pill-active" : "app-pill"}`}
          >
            Выработка
          </button>
          {showPayrollAdmin ? (
            <button
              type="button"
              onClick={() => {
                setSelectedStatement(null);
                setActiveTab("management");
              }}
              className={`inline-flex h-10 items-center rounded-full px-4 text-sm font-medium transition ${activeTab === "management" ? "app-pill-active" : "app-pill"}`}
            >
              Управление
            </button>
          ) : null}
        </div>
        </section>

      {activeTab === "management" && showPayrollAdmin ? (
        <PayrollAdminWorkspace
          embedded
          actionsTargetId="finance-management-actions"
          desktopWideMode={desktopWideMode}
          headerTargetId="finance-management-header"
          onDesktopWideModeChange={changeDesktopWideMode}
        />
      ) : activeTab === "work" ? (
        <PayrollDailyWorkSection />
      ) : (
        <>
      {loading ? (
        <section className="app-surface flex min-h-64 flex-col items-center justify-center rounded-2xl p-8 text-center">
          <Loader2 className="app-accent-text animate-spin" size={30} />
          <p className="app-text-muted mt-4 text-sm">Загружаем ваши расчётные листки…</p>
        </section>
      ) : error ? (
        <section className="app-surface rounded-2xl p-5 sm:p-8">
          <div className="app-feedback-danger mx-auto max-w-xl rounded-xl px-4 py-3 text-center text-sm">{error}</div>
          <div className="mt-4 text-center">
            <button
              type="button"
              className="app-action-secondary inline-flex items-center gap-2 rounded-lg px-4 py-2.5 text-sm font-medium"
              onClick={() => setReloadKey((value) => value + 1)}
            >
              <RefreshCw size={16} />
              Повторить
            </button>
          </div>
        </section>
      ) : statements.length === 0 ? (
        <EmptyPayroll />
      ) : (
        <>
          {latestStatement ? (
            <section className="app-surface rounded-2xl p-4 sm:p-5">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <p className="app-card-caption text-xs">Последний расчёт</p>
                <StatementStatus statement={latestStatement} />
              </div>
              <h2 className="mt-2 text-lg font-semibold text-[var(--foreground)]">
                Зарплата за {getPayrollPeriodLabel(latestStatement.period).toLocaleLowerCase("ru-RU")}
              </h2>

              <div className="mt-5">
                <p className="app-text-muted text-xs">К выплате</p>
                <p className="app-accent-text mt-1 truncate text-4xl font-bold tracking-tight" title={formatPayrollMoney(latestStatement.payable, latestStatement.currency)}>
                  {formatPayrollMoney(latestStatement.payable, latestStatement.currency)}
                </p>
              </div>

              <div className="app-surface-muted mt-5 divide-y divide-[var(--border-subtle)] overflow-hidden rounded-xl">
                <div className="flex items-start gap-3 px-3 py-3.5 sm:px-4">
                  <CalendarDays className="app-text-muted mt-0.5 shrink-0" size={17} />
                  <div className="min-w-0">
                    <p className="app-text-muted text-xs">Расчётный период</p>
                    <p className="mt-0.5 text-sm font-medium text-[var(--foreground)]">{getPayrollPeriodRange(latestStatement.period)}</p>
                  </div>
                </div>
                <div className="flex items-start gap-3 px-3 py-3.5 sm:px-4">
                  <Clock3 className="app-text-muted mt-0.5 shrink-0" size={17} />
                  <div className="min-w-0">
                    <p className="app-text-muted text-xs">Дата выплаты</p>
                    <p className="mt-0.5 text-sm font-medium text-[var(--foreground)]">{formatPayrollDate(latestStatement.period.pay_date)}</p>
                  </div>
                </div>
              </div>

              <button
                type="button"
                className="app-action-primary mt-4 inline-flex w-full items-center justify-center gap-2 rounded-lg px-4 py-3 text-sm font-semibold"
                onClick={() => setSelectedStatement(latestStatement)}
              >
                {latestStatement.acknowledgement?.acknowledged_at
                  ? "Посмотреть расчёт"
                  : "Проверить и подтвердить листок"}
                <ArrowRight size={16} />
              </button>
              {!latestStatement.acknowledgement?.acknowledged_at ? (
                <p className="app-text-muted mt-2 text-center text-xs leading-relaxed">
                  Сначала проверьте начисления. Подтверждается получение листка, а не перевод денег.
                </p>
              ) : null}
            </section>
          ) : null}

          {previousStatements.length > 0 ? (
            <section className="app-surface rounded-2xl p-4 sm:p-5">
              <div className="mb-4 flex items-center justify-between gap-3">
                <div className="flex min-w-0 items-center gap-2">
                  <History className="app-text-muted shrink-0" size={18} />
                  <div className="min-w-0">
                    <h2 className="truncate text-base font-semibold text-[var(--foreground)]">Предыдущие расчёты</h2>
                    <p className="app-text-muted mt-0.5 text-xs">Откройте любой листок, чтобы посмотреть начисления</p>
                  </div>
                </div>
                {pendingCount > 1 ? (
                  <span className="app-counter h-6 min-w-6 shrink-0 px-1.5 text-xs" title="Листки, ожидающие подтверждения">
                    {pendingCount}
                  </span>
                ) : null}
              </div>

              <div className="space-y-2">
              {previousStatements.map((statement) => (
                <button
                  type="button"
                  key={statement.public_id}
                  className="app-surface-muted group grid w-full grid-cols-[minmax(0,1fr)_auto] items-center gap-3 rounded-xl p-3 text-left transition hover:border-[var(--border-strong)] hover:bg-[var(--surface-elevated)] sm:p-4"
                  onClick={() => setSelectedStatement(statement)}
                >
                  <div className="min-w-0">
                    <p className="truncate text-sm font-semibold text-[var(--foreground)]">{getPayrollPeriodLabel(statement.period)}</p>
                    <p className="app-text-muted mt-1 truncate text-xs">Выплата {formatPayrollDate(statement.period.pay_date)}</p>
                    <div className="mt-2"><StatementStatus statement={statement} /></div>
                  </div>

                  <div className="flex items-center justify-end gap-2">
                    <p className="whitespace-nowrap text-right text-sm font-bold text-[var(--foreground)]">
                      {formatPayrollMoney(statement.payable, statement.currency)}
                    </p>
                    <ChevronRight className="app-text-muted shrink-0 transition-transform group-hover:translate-x-0.5" size={18} />
                  </div>
                </button>
              ))}
              </div>
            </section>
          ) : null}
        </>
      )}

        <PayrollStatementDetailModal
          isOpen={Boolean(selectedStatement)}
          statement={selectedStatement}
          onClose={() => setSelectedStatement(null)}
          onAcknowledged={handleAcknowledged}
        />
        </>
      )}
      </div>
    </AppShell>
  );
}
