"use client";

import { AppShell } from "../../components/AppShell";
import { apiClient } from "@/lib/api";
import { useEffect, useMemo, useState } from "react";
import type { Request } from "@/types/api";
import { Search, FileSignature } from "lucide-react";

const statusMeta: Record<Request["status"], { label: string; className: string }> = {
  pending: {
    label: "На рассмотрении",
    className: "bg-amber-50 text-amber-700 ring-amber-100",
  },
  approved: {
    label: "Одобрено",
    className: "bg-emerald-50 text-emerald-700 ring-emerald-100",
  },
  rejected: {
    label: "Отклонено",
    className: "bg-rose-50 text-rose-700 ring-rose-100",
  },
  in_progress: {
    label: "В работе",
    className: "bg-sky-50 text-sky-700 ring-sky-100",
  },
  completed: {
    label: "Завершено",
    className: "bg-violet-50 text-violet-700 ring-violet-100",
  },
};

const defaultStatusMeta = {
  label: "Неизвестный статус",
  className: "bg-gray-50 text-gray-700 ring-gray-200",
};

function formatDate(value?: string): string {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  return date.toLocaleDateString("ru-RU", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
  });
}

export default function RequestsPage() {
  const [requests, setRequests] = useState<Request[]>([]);
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function loadRequests() {
      try {
        setLoading(true);
        setError(null);
        const response = await apiClient.getRequests();
        setRequests(response.results || []);
      } catch (err) {
        console.error("Ошибка загрузки заявлений:", err);
        setError("Не удалось загрузить заявления");
      } finally {
        setLoading(false);
      }
    }

    loadRequests();
  }, []);

  const filteredRequests = useMemo(() => {
    const q = search.trim().toLowerCase();
    const sorted = [...requests].sort((a, b) => {
      const aTime = new Date(a.created_at).getTime() || 0;
      const bTime = new Date(b.created_at).getTime() || 0;
      return bTime - aTime;
    });

    if (!q) return sorted;

    return sorted.filter((item) => {
      const title = item.title.toLowerCase();
      const description = item.description.toLowerCase();
      const type = item.request_type.toLowerCase();
      const author = `${item.created_by?.last_name || ""} ${item.created_by?.first_name || ""}`.toLowerCase();
      return title.includes(q) || description.includes(q) || type.includes(q) || author.includes(q);
    });
  }, [requests, search]);

  return (
    <AppShell>
      {loading ? (
        <div className="rounded-2xl bg-white p-8 text-center shadow-sm ring-1 ring-gray-100">
          <div className="mb-4 inline-block h-8 w-8 animate-spin rounded-full border-4 border-sky-400 border-t-transparent" />
          <p className="text-sm text-gray-500">Загрузка заявлений...</p>
        </div>
      ) : error ? (
        <div className="rounded-2xl bg-red-50 p-6 text-center">
          <p className="text-sm text-red-800">{error}</p>
        </div>
      ) : (
        <section className="rounded-2xl bg-white p-4 shadow-sm ring-1 ring-gray-100">
          <div className="relative mb-4">
            <Search size={16} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Поиск по заявлениям"
              className="w-full rounded-lg border border-gray-200 bg-gray-50 py-2.5 pl-9 pr-3 text-sm text-gray-800 transition focus:border-sky-500 focus:bg-white focus:outline-none focus:ring-2 focus:ring-sky-100"
            />
          </div>

          <div className="space-y-3">
            {filteredRequests.length === 0 ? (
              <div className="rounded-xl bg-gray-50 p-8 text-center">
                <FileSignature size={22} className="mx-auto mb-2 text-gray-400" />
                <p className="text-sm text-gray-500">Заявления не найдены</p>
              </div>
            ) : (
              filteredRequests.map((item) => {
                const authorName = `${item.created_by?.last_name || ""} ${item.created_by?.first_name || ""}`.trim() || "Неизвестно";
                const assigneeName = item.assigned_to
                  ? `${item.assigned_to.last_name} ${item.assigned_to.first_name}`.trim()
                  : "Не назначен";
                const statusKey = String(item.status || "").toLowerCase() as Request["status"];
                const status = statusMeta[statusKey] ?? defaultStatusMeta;

                return (
                  <article key={item.id} className="rounded-xl border border-gray-100 bg-white p-4 transition hover:bg-gray-50">
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0">
                        <p className="truncate text-sm font-semibold text-gray-900">{item.title}</p>
                        <p className="mt-1 text-xs text-gray-500">Тип: {item.request_type}</p>
                      </div>

                      <span className={`inline-flex shrink-0 rounded-full px-2.5 py-1 text-xs ring-1 ${status.className}`}>
                        {status.label}
                      </span>
                    </div>

                    <p className="mt-3 text-sm text-gray-700">{item.description}</p>

                    <div className="mt-3 grid grid-cols-1 gap-2 text-xs text-gray-500 sm:grid-cols-2">
                      <p>Автор: {authorName}</p>
                      <p>Исполнитель: {assigneeName}</p>
                      <p>Создано: {formatDate(item.created_at)}</p>
                      <p>Обновлено: {formatDate(item.updated_at)}</p>
                    </div>
                  </article>
                );
              })
            )}
          </div>
        </section>
      )}
    </AppShell>
  );
}
