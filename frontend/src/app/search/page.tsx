"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { AppShell } from "../../components/AppShell";
import { apiClient } from "@/lib/api";
import type { SearchResponse, SearchResult, SearchModelType } from "@/types/api";
import { Search, User, Building, FileText, MessageSquare, MessageCircle, Calendar, Inbox } from "lucide-react";

// Иконки для разных типов результатов
const modelIcons: Record<SearchModelType, React.ComponentType<{ size?: number; className?: string }>> = {
  employee: User,
  department: Building,
  post: Inbox,
  document: FileText,
  request: FileText,
  chat: MessageSquare,
  message: MessageCircle,
  event: Calendar,
};

// Названия категорий на русском
const modelNames: Record<SearchModelType, string> = {
  employee: "Сотрудники",
  department: "Отделы",
  post: "Посты",
  document: "Документы",
  request: "Заявления",
  chat: "Чаты",
  message: "Сообщения",
  event: "События",
};

export default function SearchPage() {
  const searchParams = useSearchParams();
  const queryRaw = searchParams.get("q") || "";
  const query = queryRaw.trim();

  const [searchResponse, setSearchResponse] = useState<SearchResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!query) {
      setSearchResponse(null);
      setError(null);
      setLoading(false);
      return;
    }

    let cancelled = false;

    async function runSearch() {
      try {
        setLoading(true);
        setError(null);

        const response: SearchResponse = await apiClient.search(queryRaw, 10);

        if (cancelled) return;

        setSearchResponse(response);
      } catch (err) {
        if (!cancelled) {
          console.error("Ошибка поиска:", err);
          setError("Не удалось выполнить поиск");
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    runSearch();

    return () => {
      cancelled = true;
    };
  }, [query, queryRaw]);

  // Группируем результаты по типам
  const resultsByType: Partial<Record<SearchModelType, SearchResult[]>> = {};
  if (searchResponse) {
    searchResponse.results.forEach((result) => {
      if (!resultsByType[result.model_name]) {
        resultsByType[result.model_name] = [];
      }
      resultsByType[result.model_name]!.push(result);
    });
  }

  return (
    <AppShell>
      <section className="rounded-2xl bg-white p-4 shadow-sm ring-1 ring-gray-100">
        <div className="mb-4 flex items-center gap-2">
          <Search size={16} className="text-gray-400" />
          <p className="text-sm text-gray-600">
            {query ? `Результаты по запросу: "${queryRaw}"` : "Введите запрос в поиске сверху"}
          </p>
        </div>

        {query && searchResponse && (
          <div className="mb-4 text-sm text-gray-500">
            Найдено результатов: <span className="font-semibold">{searchResponse.total}</span>
          </div>
        )}

        {loading ? (
          <div className="rounded-xl bg-gray-50 p-6 text-center text-sm text-gray-500">
            <div className="inline-block h-5 w-5 animate-spin rounded-full border-2 border-gray-300 border-t-blue-600"></div>
            <p className="mt-2">Поиск...</p>
          </div>
        ) : error ? (
          <div className="rounded-xl bg-red-50 p-6 text-center text-sm text-red-800">{error}</div>
        ) : !query ? (
          <div className="rounded-xl bg-gray-50 p-6 text-center text-sm text-gray-500">
            Начните вводить запрос в строке поиска
          </div>
        ) : searchResponse?.total === 0 ? (
          <div className="rounded-xl bg-gray-50 p-6 text-center text-sm text-gray-500">
            Ничего не найдено по запросу "{queryRaw}"
          </div>
        ) : (
          <div className="space-y-6">
            {(Object.keys(resultsByType) as SearchModelType[]).map((modelType) => {
              const results = resultsByType[modelType]!;
              const Icon = modelIcons[modelType];
              const categoryName = modelNames[modelType];

              return (
                <div key={modelType}>
                  <div className="mb-3 flex items-center gap-2">
                    <Icon size={16} className="text-gray-400" />
                    <p className="text-xs font-semibold uppercase tracking-wide text-gray-500">
                      {categoryName} <span className="font-normal">({results.length})</span>
                    </p>
                  </div>
                  <div className="space-y-2">
                    {results.map((result) => (
                      <Link
                        key={`${result.model_name}-${result.object_id}`}
                        href={result.url}
                        className="block rounded-lg border border-gray-200 p-3 transition-all hover:border-blue-300 hover:bg-blue-50/50 hover:shadow-sm"
                      >
                        <div className="flex items-start justify-between gap-2">
                          <div className="flex-1 min-w-0">
                            <p className="text-sm font-medium text-gray-900 truncate">{result.title}</p>
                            {result.description && (
                              <p className="mt-1 text-xs text-gray-500 line-clamp-2">{result.description}</p>
                            )}
                            {result.meta && Object.keys(result.meta).length > 0 && (
                              <div className="mt-2 flex flex-wrap gap-2">
                                {Object.entries(result.meta).map(([key, value]) => {
                                  if (!value || key === 'id') return null;
                                  return (
                                    <span
                                      key={key}
                                      className="inline-flex items-center rounded-full bg-gray-100 px-2 py-0.5 text-xs text-gray-600"
                                    >
                                      {String(value)}
                                    </span>
                                  );
                                })}
                              </div>
                            )}
                          </div>
                        </div>
                      </Link>
                    ))}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </section>
    </AppShell>
  );
}
