"use client";

import { AppShell } from "../../components/AppShell";
import { apiClient } from "@/lib/api";
import { useEffect, useMemo, useState } from "react";
import type { Document } from "@/types/api";
import { Search, FileText, Download } from "lucide-react";

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

export default function DocumentsPage() {
  const [documents, setDocuments] = useState<Document[]>([]);
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function loadDocuments() {
      try {
        setLoading(true);
        setError(null);
        const response = await apiClient.getDocuments();
        setDocuments(response.results || []);
      } catch (err) {
        console.error("Ошибка загрузки документов:", err);
        setError("Не удалось загрузить документы");
      } finally {
        setLoading(false);
      }
    }

    loadDocuments();
  }, []);

  const filteredDocuments = useMemo(() => {
    const q = search.trim().toLowerCase();
    const sorted = [...documents].sort((a, b) => {
      const aTime = new Date(a.created_at).getTime() || 0;
      const bTime = new Date(b.created_at).getTime() || 0;
      return bTime - aTime;
    });

    if (!q) return sorted;

    return sorted.filter((doc) => {
      const title = doc.title.toLowerCase();
      const description = (doc.description || "").toLowerCase();
      const type = (doc.document_type || "").toLowerCase();
      const author = doc.created_by
        ? `${doc.created_by.last_name} ${doc.created_by.first_name}`.toLowerCase()
        : "";
      return title.includes(q) || description.includes(q) || type.includes(q) || author.includes(q);
    });
  }, [documents, search]);

  return (
    <AppShell>
      {loading ? (
        <div className="rounded-2xl bg-white p-8 text-center shadow-sm ring-1 ring-gray-100">
          <div className="mb-4 inline-block h-8 w-8 animate-spin rounded-full border-4 border-sky-400 border-t-transparent" />
          <p className="text-sm text-gray-500">Загрузка документов...</p>
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
              placeholder="Поиск по документам"
              className="w-full rounded-lg border border-gray-200 bg-gray-50 py-2.5 pl-9 pr-3 text-sm text-gray-800 transition focus:border-sky-500 focus:bg-white focus:outline-none focus:ring-2 focus:ring-sky-100"
            />
          </div>

          <div className="space-y-3">
            {filteredDocuments.length === 0 ? (
              <div className="rounded-xl bg-gray-50 p-8 text-center">
                <FileText size={22} className="mx-auto mb-2 text-gray-400" />
                <p className="text-sm text-gray-500">Документы не найдены</p>
              </div>
            ) : (
              filteredDocuments.map((doc) => {
                const authorName = doc.created_by
                  ? `${doc.created_by.last_name} ${doc.created_by.first_name}`.trim()
                  : "Неизвестно";

                return (
                  <article key={doc.id} className="rounded-xl border border-gray-100 bg-white p-4 transition hover:bg-gray-50">
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0">
                        <p className="truncate text-sm font-semibold text-gray-900">{doc.title}</p>
                        <p className="mt-1 text-xs text-gray-500">Тип: {doc.document_type || "—"}</p>
                      </div>

                      {doc.file ? (
                        <a
                          href={doc.file}
                          target="_blank"
                          rel="noreferrer"
                          className="inline-flex shrink-0 items-center gap-1 rounded-full bg-sky-50 px-2.5 py-1 text-xs text-sky-700 ring-1 ring-sky-100 hover:bg-sky-100"
                        >
                          <Download size={12} />
                          Открыть
                        </a>
                      ) : null}
                    </div>

                    <p className="mt-3 text-sm text-gray-700">{doc.description || "Описание не заполнено"}</p>

                    {doc.tags && doc.tags.length > 0 ? (
                      <div className="mt-3 flex flex-wrap gap-1.5">
                        {doc.tags.map((tag) => (
                          <span key={`${doc.id}-${tag}`} className="rounded-full bg-gray-100 px-2 py-0.5 text-xs text-gray-600">
                            #{tag}
                          </span>
                        ))}
                      </div>
                    ) : null}

                    <div className="mt-3 grid grid-cols-1 gap-2 text-xs text-gray-500 sm:grid-cols-2">
                      <p>Автор: {authorName}</p>
                      <p>Создано: {formatDate(doc.created_at)}</p>
                      <p>Обновлено: {formatDate(doc.updated_at)}</p>
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
