"use client";

import { useState, useCallback, useEffect, useMemo } from "react";
import { Search, X, Filter, SlidersHorizontal, Save, Clock, ChevronDown } from "lucide-react";
import Fuse from "fuse.js";

export interface SearchFilters {
  query: string;
  documentTypes?: string[];
  dateFrom?: string;
  dateTo?: string;
  statuses?: string[];
  tags?: string[];
  authors?: string[];
  sortBy?: "relevance" | "date" | "title" | "author";
  sortOrder?: "asc" | "desc";
}

export interface SearchResult {
  id: number;
  title: string;
  description: string;
  content?: string;
  type?: string;
  status?: string;
  uploaded_at: string;
  uploaded_by?: string;
  tags?: string[];
  score?: number;
  highlights?: string[];
}

interface AdvancedSearchProps {
  onSearch: (filters: SearchFilters) => void;
  results?: SearchResult[];
  isLoading?: boolean;
  availableTypes?: Array<{ id: string; name: string }>;
  availableStatuses?: Array<{ id: string; name: string }>;
  availableTags?: Array<{ id: string; name: string }>;
  availableAuthors?: Array<{ id: string; name: string }>;
}

const DEFAULT_FILTERS: SearchFilters = {
  query: "",
  documentTypes: [],
  dateFrom: "",
  dateTo: "",
  statuses: [],
  tags: [],
  authors: [],
  sortBy: "relevance",
  sortOrder: "desc",
};

export function AdvancedSearch({
  onSearch,
  results = [],
  isLoading = false,
  availableTypes = [],
  availableStatuses = [],
  availableTags = [],
  availableAuthors = [],
}: AdvancedSearchProps) {
  const [filters, setFilters] = useState<SearchFilters>(DEFAULT_FILTERS);
  const [showFilters, setShowFilters] = useState(false);
  const [savedSearches, setSavedSearches] = useState<Array<{ name: string; filters: SearchFilters }>>(
    []
  );
  const [showSavedSearches, setShowSavedSearches] = useState(false);
  const [saveSearchName, setSaveSearchName] = useState("");

  // Загрузка сохраненных поисков из localStorage
  useEffect(() => {
    const saved = localStorage.getItem("savedSearches");
    if (saved) {
      try {
        setSavedSearches(JSON.parse(saved));
      } catch (e) {
        console.error("Error loading saved searches:", e);
      }
    }
  }, []);

  // Обновление фильтра
  const updateFilter = useCallback(
    <K extends keyof SearchFilters>(key: K, value: SearchFilters[K]) => {
      setFilters((prev) => ({ ...prev, [key]: value }));
    },
    []
  );

  // Выполнение поиска
  const handleSearch = useCallback(() => {
    onSearch(filters);
  }, [filters, onSearch]);

  // Сброс фильтров
  const resetFilters = useCallback(() => {
    setFilters(DEFAULT_FILTERS);
    onSearch(DEFAULT_FILTERS);
  }, [onSearch]);

  // Сохранение поиска
  const saveSearch = useCallback(() => {
    if (!saveSearchName.trim()) return;

    const newSearch = {
      name: saveSearchName.trim(),
      filters: { ...filters },
    };

    const updated = [...savedSearches, newSearch];
    setSavedSearches(updated);
    localStorage.setItem("savedSearches", JSON.stringify(updated));
    setSaveSearchName("");
    setShowSavedSearches(false);
  }, [saveSearchName, filters, savedSearches]);

  // Загрузка сохраненного поиска
  const loadSearch = useCallback(
    (search: { name: string; filters: SearchFilters }) => {
      setFilters(search.filters);
      onSearch(search.filters);
      setShowSavedSearches(false);
    },
    [onSearch]
  );

  // Удаление сохраненного поиска
  const deleteSavedSearch = useCallback(
    (index: number) => {
      const updated = savedSearches.filter((_, i) => i !== index);
      setSavedSearches(updated);
      localStorage.setItem("savedSearches", JSON.stringify(updated));
    },
    [savedSearches]
  );

  // Fuzzy search для подсветки
  const fuse = useMemo(() => {
    if (!results.length || !filters.query) return null;

    return new Fuse(results, {
      keys: ["title", "description", "content"],
      includeScore: true,
      includeMatches: true,
      threshold: 0.4,
    });
  }, [results, filters.query]);

  // Подсветка совпадений
  const highlightText = (text: string, query: string) => {
    if (!query) return text;

    const regex = new RegExp(`(${query})`, "gi");
    const parts = text.split(regex);

    return parts.map((part, index) =>
      regex.test(part) ? (
        <mark key={index} className="bg-yellow-200 text-gray-900">
          {part}
        </mark>
      ) : (
        <span key={index}>{part}</span>
      )
    );
  };

  // Активные фильтры (для отображения badges)
  const activeFiltersCount = useMemo(() => {
    let count = 0;
    if (filters.documentTypes && filters.documentTypes.length > 0) count++;
    if (filters.dateFrom) count++;
    if (filters.dateTo) count++;
    if (filters.statuses && filters.statuses.length > 0) count++;
    if (filters.tags && filters.tags.length > 0) count++;
    if (filters.authors && filters.authors.length > 0) count++;
    return count;
  }, [filters]);

  return (
    <div className="space-y-4">
      {/* Поисковая строка */}
      <div className="flex gap-2">
        <div className="relative flex-1">
          <Search
            size={20}
            className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400"
          />
          <input
            type="text"
            value={filters.query}
            onChange={(e) => updateFilter("query", e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleSearch()}
            placeholder="Поиск документов..."
            className="w-full rounded-lg border border-gray-300 py-2.5 pl-10 pr-10 text-sm focus:border-sky-500 focus:outline-none focus:ring-2 focus:ring-sky-100"
          />
          {filters.query && (
            <button
              onClick={() => updateFilter("query", "")}
              className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600"
            >
              <X size={16} />
            </button>
          )}
        </div>

        <button
          onClick={() => setShowFilters((prev) => !prev)}
          className={`flex items-center gap-2 rounded-lg border px-4 py-2.5 text-sm font-medium transition ${
            showFilters
              ? "border-sky-500 bg-sky-50 text-sky-700"
              : "border-gray-300 bg-white text-gray-700 hover:bg-gray-50"
          }`}
        >
          <SlidersHorizontal size={16} />
          Фильтры
          {activeFiltersCount > 0 && (
            <span className="flex h-5 w-5 items-center justify-center rounded-full bg-sky-500 text-xs text-white">
              {activeFiltersCount}
            </span>
          )}
        </button>

        <button
          onClick={handleSearch}
          disabled={isLoading}
          className="rounded-lg bg-sky-600 px-6 py-2.5 text-sm font-medium text-white transition hover:bg-sky-700 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {isLoading ? "Поиск..." : "Найти"}
        </button>

        <button
          onClick={() => setShowSavedSearches((prev) => !prev)}
          className="flex items-center gap-2 rounded-lg border border-gray-300 bg-white px-4 py-2.5 text-sm font-medium text-gray-700 transition hover:bg-gray-50"
          title="Сохраненные поиски"
        >
          <Clock size={16} />
        </button>
      </div>

      {/* Сохраненные поиски */}
      {showSavedSearches && (
        <div className="rounded-lg border border-gray-200 bg-white p-4">
          <div className="mb-3 flex items-center justify-between">
            <h3 className="text-sm font-medium text-gray-900">Сохраненные поиски</h3>
            <button
              onClick={() => setShowSavedSearches(false)}
              className="text-gray-400 hover:text-gray-600"
            >
              <X size={16} />
            </button>
          </div>

          {savedSearches.length > 0 ? (
            <div className="space-y-2">
              {savedSearches.map((search, index) => (
                <div
                  key={index}
                  className="flex items-center justify-between rounded border border-gray-200 p-2 hover:bg-gray-50"
                >
                  <button
                    onClick={() => loadSearch(search)}
                    className="flex-1 text-left text-sm font-medium text-gray-900"
                  >
                    {search.name}
                  </button>
                  <button
                    onClick={() => deleteSavedSearch(index)}
                    className="text-gray-400 hover:text-red-600"
                  >
                    <X size={14} />
                  </button>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-sm text-gray-500">Нет сохраненных поисков</p>
          )}

          {/* Сохранить текущий поиск */}
          <div className="mt-3 flex gap-2 border-t border-gray-200 pt-3">
            <input
              type="text"
              value={saveSearchName}
              onChange={(e) => setSaveSearchName(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && saveSearch()}
              placeholder="Название поиска..."
              className="flex-1 rounded border border-gray-300 px-2 py-1 text-sm focus:border-sky-500 focus:outline-none"
            />
            <button
              onClick={saveSearch}
              disabled={!saveSearchName.trim()}
              className="flex items-center gap-1 rounded bg-sky-600 px-3 py-1 text-sm text-white hover:bg-sky-700 disabled:cursor-not-allowed disabled:opacity-50"
            >
              <Save size={14} />
              Сохранить
            </button>
          </div>
        </div>
      )}

      {/* Панель фильтров */}
      {showFilters && (
        <div className="rounded-lg border border-gray-200 bg-white p-4">
          <div className="mb-4 flex items-center justify-between">
            <h3 className="text-sm font-medium text-gray-900">Расширенные фильтры</h3>
            <button
              onClick={resetFilters}
              className="text-sm text-sky-600 hover:text-sky-700"
            >
              Сбросить все
            </button>
          </div>

          <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
            {/* Тип документа */}
            {availableTypes.length > 0 && (
              <div>
                <label className="mb-1 block text-xs font-medium text-gray-700">
                  Тип документа
                </label>
                <select
                  multiple
                  value={filters.documentTypes || []}
                  onChange={(e) =>
                    updateFilter(
                      "documentTypes",
                      Array.from(e.target.selectedOptions, (option) => option.value)
                    )
                  }
                  className="w-full rounded border border-gray-300 px-2 py-1 text-sm focus:border-sky-500 focus:outline-none"
                  size={3}
                >
                  {availableTypes.map((type) => (
                    <option key={type.id} value={type.id}>
                      {type.name}
                    </option>
                  ))}
                </select>
              </div>
            )}

            {/* Статус */}
            {availableStatuses.length > 0 && (
              <div>
                <label className="mb-1 block text-xs font-medium text-gray-700">Статус</label>
                <select
                  multiple
                  value={filters.statuses || []}
                  onChange={(e) =>
                    updateFilter(
                      "statuses",
                      Array.from(e.target.selectedOptions, (option) => option.value)
                    )
                  }
                  className="w-full rounded border border-gray-300 px-2 py-1 text-sm focus:border-sky-500 focus:outline-none"
                  size={3}
                >
                  {availableStatuses.map((status) => (
                    <option key={status.id} value={status.id}>
                      {status.name}
                    </option>
                  ))}
                </select>
              </div>
            )}

            {/* Теги */}
            {availableTags.length > 0 && (
              <div>
                <label className="mb-1 block text-xs font-medium text-gray-700">Теги</label>
                <select
                  multiple
                  value={filters.tags || []}
                  onChange={(e) =>
                    updateFilter(
                      "tags",
                      Array.from(e.target.selectedOptions, (option) => option.value)
                    )
                  }
                  className="w-full rounded border border-gray-300 px-2 py-1 text-sm focus:border-sky-500 focus:outline-none"
                  size={3}
                >
                  {availableTags.map((tag) => (
                    <option key={tag.id} value={tag.id}>
                      {tag.name}
                    </option>
                  ))}
                </select>
              </div>
            )}

            {/* Дата от */}
            <div>
              <label className="mb-1 block text-xs font-medium text-gray-700">Дата от</label>
              <input
                type="date"
                value={filters.dateFrom || ""}
                onChange={(e) => updateFilter("dateFrom", e.target.value)}
                className="w-full rounded border border-gray-300 px-2 py-1 text-sm focus:border-sky-500 focus:outline-none"
              />
            </div>

            {/* Дата до */}
            <div>
              <label className="mb-1 block text-xs font-medium text-gray-700">Дата до</label>
              <input
                type="date"
                value={filters.dateTo || ""}
                onChange={(e) => updateFilter("dateTo", e.target.value)}
                className="w-full rounded border border-gray-300 px-2 py-1 text-sm focus:border-sky-500 focus:outline-none"
              />
            </div>

            {/* Автор */}
            {availableAuthors.length > 0 && (
              <div>
                <label className="mb-1 block text-xs font-medium text-gray-700">Автор</label>
                <select
                  multiple
                  value={filters.authors || []}
                  onChange={(e) =>
                    updateFilter(
                      "authors",
                      Array.from(e.target.selectedOptions, (option) => option.value)
                    )
                  }
                  className="w-full rounded border border-gray-300 px-2 py-1 text-sm focus:border-sky-500 focus:outline-none"
                  size={3}
                >
                  {availableAuthors.map((author) => (
                    <option key={author.id} value={author.id}>
                      {author.name}
                    </option>
                  ))}
                </select>
              </div>
            )}
          </div>

          {/* Сортировка */}
          <div className="mt-4 flex items-center gap-4 border-t border-gray-200 pt-4">
            <label className="text-xs font-medium text-gray-700">Сортировка:</label>
            <select
              value={filters.sortBy || "relevance"}
              onChange={(e) =>
                updateFilter("sortBy", e.target.value as SearchFilters["sortBy"])
              }
              className="rounded border border-gray-300 px-2 py-1 text-sm focus:border-sky-500 focus:outline-none"
            >
              <option value="relevance">По релевантности</option>
              <option value="date">По дате</option>
              <option value="title">По названию</option>
              <option value="author">По автору</option>
            </select>

            <select
              value={filters.sortOrder || "desc"}
              onChange={(e) =>
                updateFilter("sortOrder", e.target.value as SearchFilters["sortOrder"])
              }
              className="rounded border border-gray-300 px-2 py-1 text-sm focus:border-sky-500 focus:outline-none"
            >
              <option value="asc">По возрастанию</option>
              <option value="desc">По убыванию</option>
            </select>
          </div>
        </div>
      )}

      {/* Результаты поиска */}
      {results.length > 0 && (
        <div className="space-y-3">
          <p className="text-sm text-gray-600">
            Найдено результатов: <span className="font-medium text-gray-900">{results.length}</span>
          </p>

          {results.map((result) => (
            <div
              key={result.id}
              className="rounded-lg border border-gray-200 bg-white p-4 hover:border-sky-300 hover:shadow-sm"
            >
              <h4 className="mb-1 text-base font-medium text-gray-900">
                {highlightText(result.title, filters.query)}
              </h4>
              {result.description && (
                <p className="mb-2 text-sm text-gray-600">
                  {highlightText(result.description, filters.query)}
                </p>
              )}
              <div className="flex items-center gap-3 text-xs text-gray-500">
                {result.type && (
                  <span className="rounded bg-gray-100 px-2 py-0.5">{result.type}</span>
                )}
                {result.status && (
                  <span className="rounded bg-sky-100 px-2 py-0.5 text-sky-700">
                    {result.status}
                  </span>
                )}
                {result.uploaded_by && <span>Автор: {result.uploaded_by}</span>}
                {result.uploaded_at && (
                  <span>{new Date(result.uploaded_at).toLocaleDateString("ru-RU")}</span>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Пустое состояние */}
      {!isLoading && results.length === 0 && filters.query && (
        <div className="rounded-lg border border-gray-200 bg-white p-8 text-center">
          <Search size={48} className="mx-auto mb-3 text-gray-300" />
          <p className="text-sm text-gray-600">Ничего не найдено</p>
          <p className="mt-1 text-xs text-gray-500">Попробуйте изменить параметры поиска</p>
        </div>
      )}
    </div>
  );
}
