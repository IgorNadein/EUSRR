"use client";

import { useEffect, useState, Suspense } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { AppShell } from "../../components/AppShell";
import { apiClient } from "@/lib/api";
import type { SearchResponse, SearchResult, SearchModelType } from "@/types/api";
import { Search, User, Building, FileText, MessageSquare, MessageCircle, Calendar, Inbox, ShoppingCart, Package, Bell } from "lucide-react";

function buildSearchHref(result: SearchResult): string {
  switch (result.model_name) {
    case "employee":
      return `/users/${result.object_id}`;
    case "department":
      return `/departments/${result.object_id}`;
    case "post":
      return `/?post=${result.object_id}`;
    case "request":
      return `/requests?request=${result.object_id}`;
    case "chat":
      return `/messages/${result.object_id}`;
    case "message": {
      const chatId = typeof result.meta?.chat_id === "number"
        ? result.meta.chat_id
        : Number(result.meta?.chat_id || 0);
      return chatId ? `/messages/${chatId}?message=${result.object_id}` : "/messages";
    }
    case "event":
      return "/calendar";
    case "schedule_event":
      return `/calendar?event=${result.object_id}`;
    case "procurement_request":
      return "/procurement";
    case "equipment":
      return "/equipment";
    case "document":
      return `/documents?document=${result.object_id}`;
    case "notification":
      return "/notifications";
    default:
      return "/search";
  }
}

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
  schedule_event: Calendar,
  procurement_request: ShoppingCart,
  equipment: Package,
  notification: Bell,
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
  event: "События календаря",
  schedule_event: "Расписание",
  procurement_request: "Заявки на закупку",
  equipment: "Оборудование",
  notification: "Уведомления",
};

export default function SearchPage() {
  return (
    <Suspense fallback={
      <AppShell>
        <section className="app-surface rounded-2xl p-4">
          <div className="app-surface-muted app-text-muted rounded-xl p-6 text-center text-sm">
            <div className="inline-block h-5 w-5 animate-spin rounded-full border-2 border-[var(--border-subtle)] border-t-[var(--accent-primary)]"></div>
            <p className="mt-2">Загрузка...</p>
          </div>
        </section>
      </AppShell>
    }>
      <SearchPageContent />
    </Suspense>
  );
}

function SearchPageContent() {
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
      <section className="app-surface rounded-2xl p-4">
        <div className="mb-4 flex items-center gap-2">
          <Search size={16} className="app-text-muted" />
          <p className="app-text-muted text-sm">
            {query ? `Результаты по запросу: "${queryRaw}"` : "Введите запрос в поиске сверху"}
          </p>
        </div>

        {query && searchResponse && (
          <div className="app-text-muted mb-4 text-sm">
            Найдено результатов: <span className="font-semibold">{searchResponse.total}</span>
          </div>
        )}

        {loading ? (
          <div className="app-surface-muted app-text-muted rounded-xl p-6 text-center text-sm">
            <div className="inline-block h-5 w-5 animate-spin rounded-full border-2 border-[var(--border-subtle)] border-t-[var(--accent-primary)]"></div>
            <p className="mt-2">Поиск...</p>
          </div>
        ) : error ? (
          <div className="app-feedback-danger rounded-xl p-6 text-center text-sm">{error}</div>
        ) : !query ? (
          <div className="app-surface-muted app-text-muted rounded-xl p-6 text-center text-sm">
            Начните вводить запрос в строке поиска
          </div>
        ) : searchResponse?.total === 0 ? (
          <div className="app-surface-muted app-text-muted rounded-xl p-6 text-center text-sm">
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
                    <Icon size={16} className="app-text-muted" />
                    <p className="app-text-muted text-xs font-semibold uppercase tracking-wide">
                      {categoryName} <span className="font-normal">({results.length})</span>
                    </p>
                  </div>
                  <div className="space-y-2">
                    {results.map((result) => (
                      <Link
                        key={`${result.model_name}-${result.object_id}`}
                        href={buildSearchHref(result)}
                        className="app-surface-muted block rounded-lg p-3 transition-all hover:border-[color:var(--accent-primary)] hover:bg-[color:var(--accent-soft)] hover:shadow-[var(--shadow-card)]"
                      >
                        <div className="flex items-start justify-between gap-2">
                          <div className="flex-1 min-w-0">
                            <p className="truncate text-sm font-medium text-[var(--foreground)]">{result.title}</p>
                            {result.description && (
                              <p className="app-text-muted mt-1 line-clamp-2 text-xs">{result.description}</p>
                            )}
                            {result.meta && Object.keys(result.meta).length > 0 && (
                              <div className="mt-2 flex flex-wrap gap-2">
                                {Object.entries(result.meta).map(([key, value]) => {
                                  if (!value || key === 'id') return null;
                                  return (
                                    <span
                                      key={key}
                                      className="app-badge inline-flex items-center px-2 py-0.5 text-xs"
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
