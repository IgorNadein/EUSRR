"use client";

import { useEffect, useState } from "react";
import { apiClient } from "@/lib/api";
import type { ProcurementDepartmentStats, ProcurementOverviewStats } from "@/types/api";
import { BarChart3, Building2, CheckCircle2, Clock3, Wallet } from "lucide-react";

function money(value?: string | number) {
  if (value === null || value === undefined || value === "") return "—";
  return `${Number(value).toLocaleString("ru-RU", { minimumFractionDigits: 2, maximumFractionDigits: 2 })} ₽`;
}

const statusLabels: Record<string, string> = {
  draft: "Черновик",
  pending: "На согласовании",
  approved: "Одобрено",
  in_progress: "В работе",
  completed: "Завершено",
  rejected: "Отклонено",
  cancelled: "Отменено",
};

const urgencyLabels: Record<string, string> = {
  low: "Низкая",
  medium: "Средняя",
  high: "Высокая",
  critical: "Критическая",
};

export default function ProcurementStatsPanel() {
  const [overview, setOverview] = useState<ProcurementOverviewStats | null>(null);
  const [byDepartment, setByDepartment] = useState<ProcurementDepartmentStats[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let mounted = true;
    (async () => {
      try {
        setLoading(true);
        setError(null);
        const [overviewData, byDepartmentData] = await Promise.allSettled([
          apiClient.getProcurementOverviewStats(),
          apiClient.getProcurementDepartmentStats(),
        ]);

        if (!mounted) return;

        if (overviewData.status === "fulfilled") {
          setOverview(overviewData.value);
        }
        if (byDepartmentData.status === "fulfilled") {
          setByDepartment(Array.isArray(byDepartmentData.value) ? byDepartmentData.value : []);
        }
      } catch {
        if (mounted) setError("Не удалось загрузить статистику закупок");
      } finally {
        if (mounted) setLoading(false);
      }
    })();
    return () => {
      mounted = false;
    };
  }, []);

  if (loading) {
    return <div className="rounded-xl bg-gray-50 p-8 text-center text-sm text-gray-500">Загрузка статистики...</div>;
  }

  if (error || !overview) {
    return <div className="rounded-xl bg-red-50 p-4 text-sm text-red-700">{error || "Статистика недоступна"}</div>;
  }

  return (
    <div className="space-y-4">
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <div className="rounded-xl border border-gray-200 bg-white p-4 ring-1 ring-gray-100">
          <div className="flex items-center gap-2 text-gray-500"><BarChart3 size={16} /><span className="text-xs font-medium uppercase tracking-wide">Всего заявок</span></div>
          <p className="mt-2 text-2xl font-semibold text-gray-900">{overview.total_requests}</p>
        </div>
        <div className="rounded-xl border border-gray-200 bg-white p-4 ring-1 ring-gray-100">
          <div className="flex items-center gap-2 text-amber-600"><Clock3 size={16} /><span className="text-xs font-medium uppercase tracking-wide">Ожидают</span></div>
          <p className="mt-2 text-2xl font-semibold text-gray-900">{overview.pending_requests}</p>
        </div>
        <div className="rounded-xl border border-gray-200 bg-white p-4 ring-1 ring-gray-100">
          <div className="flex items-center gap-2 text-emerald-600"><CheckCircle2 size={16} /><span className="text-xs font-medium uppercase tracking-wide">Завершено за месяц</span></div>
          <p className="mt-2 text-2xl font-semibold text-gray-900">{overview.completed_this_month}</p>
        </div>
        <div className="rounded-xl border border-gray-200 bg-white p-4 ring-1 ring-gray-100">
          <div className="flex items-center gap-2 text-sky-600"><Wallet size={16} /><span className="text-xs font-medium uppercase tracking-wide">Потрачено за год</span></div>
          <p className="mt-2 text-lg font-semibold text-gray-900">{money(overview.total_spent_this_year)}</p>
        </div>
      </div>

      <div className="grid gap-4 xl:grid-cols-2">
        <div className="rounded-xl border border-gray-200 bg-white p-4 ring-1 ring-gray-100">
          <p className="text-xs font-medium uppercase tracking-wide text-gray-500">По статусам</p>
          <div className="mt-3 space-y-2">
            {Object.entries(overview.by_status || {}).map(([key, count]) => (
              <div key={key} className="flex items-center justify-between rounded-lg bg-gray-50 px-3 py-2 text-sm">
                <span className="text-gray-600">{statusLabels[key] || key}</span>
                <span className="font-semibold text-gray-900">{count}</span>
              </div>
            ))}
          </div>
        </div>

        <div className="rounded-xl border border-gray-200 bg-white p-4 ring-1 ring-gray-100">
          <p className="text-xs font-medium uppercase tracking-wide text-gray-500">По срочности</p>
          <div className="mt-3 space-y-2">
            {Object.entries(overview.by_urgency || {}).map(([key, count]) => (
              <div key={key} className="flex items-center justify-between rounded-lg bg-gray-50 px-3 py-2 text-sm">
                <span className="text-gray-600">{urgencyLabels[key] || key}</span>
                <span className="font-semibold text-gray-900">{count}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      <div className="rounded-xl border border-gray-200 bg-white p-4 ring-1 ring-gray-100">
        <div className="flex items-center gap-2 text-gray-500"><Building2 size={16} /><p className="text-xs font-medium uppercase tracking-wide">По отделам</p></div>
        {byDepartment.length === 0 ? (
          <p className="mt-3 text-sm text-gray-500">Статистика по отделам недоступна для текущего пользователя.</p>
        ) : (
          <div className="mt-3 overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="text-left text-xs uppercase tracking-wide text-gray-400">
                <tr>
                  <th className="pb-2 font-medium">Отдел</th>
                  <th className="pb-2 font-medium text-right">Заявки</th>
                  <th className="pb-2 font-medium text-right">Потрачено</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {byDepartment.map((item) => (
                  <tr key={item.department_id || item.department_name}>
                    <td className="py-2.5 text-gray-700">{item.department_name}</td>
                    <td className="py-2.5 text-right text-gray-700">{item.total_requests}</td>
                    <td className="py-2.5 text-right text-gray-700">{money(item.total_spent)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
