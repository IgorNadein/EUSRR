"use client";

import { ChevronDown, ChevronUp, Loader2, Paperclip, Search, X } from "lucide-react";

import type { ChatMessageSearchResult } from "@/types/api";

type ChatSearchPanelProps = {
  isOpen: boolean;
  query: string;
  loading: boolean;
  loadingMore: boolean;
  error: string | null;
  results: ChatMessageSearchResult[];
  totalCount: number;
  nextOffset: number | null;
  selectedIndex: number;
  inputRef: React.RefObject<HTMLInputElement | null>;
  onQueryChange: (value: string) => void;
  onClose: () => void;
  onPrevious: () => void;
  onNext: () => void;
  onSelect: (index: number) => void;
  onLoadMore: () => void;
  onSubmitSelection: () => void;
};

function formatSearchDate(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";

  return date.toLocaleString("ru-RU", {
    day: "2-digit",
    month: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export default function ChatSearchPanel({
  isOpen,
  query,
  loading,
  loadingMore,
  error,
  results,
  totalCount,
  nextOffset,
  selectedIndex,
  inputRef,
  onQueryChange,
  onClose,
  onPrevious,
  onNext,
  onSelect,
  onLoadMore,
  onSubmitSelection,
}: ChatSearchPanelProps) {
  if (!isOpen) {
    return null;
  }

  const canNavigate = results.length > 0;
  const selectedLabel = canNavigate ? `${selectedIndex + 1}/${totalCount}` : totalCount > 0 ? `0/${totalCount}` : "0";

  return (
    <div className="shrink-0 border-b border-gray-100 bg-white px-4 py-3 lg:px-0">
      <div className="flex items-center gap-2">
        <div className="relative min-w-0 flex-1">
          <Search size={15} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
          <input
            ref={inputRef}
            type="text"
            value={query}
            onChange={(event) => onQueryChange(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter") {
                event.preventDefault();
                onSubmitSelection();
              }
              if (event.key === "ArrowUp") {
                event.preventDefault();
                onPrevious();
              }
              if (event.key === "ArrowDown") {
                event.preventDefault();
                onNext();
              }
            }}
            placeholder="Поиск по сообщениям"
            className="h-10 w-full rounded-full border border-gray-200 bg-gray-50 pl-10 pr-4 text-sm text-gray-800 outline-none transition focus:border-sky-500 focus:bg-white focus:ring-2 focus:ring-sky-100"
          />
        </div>

        <div className="flex items-center gap-1 rounded-full border border-gray-200 bg-white px-2 py-1 text-xs text-gray-500">
          <button
            type="button"
            onClick={onPrevious}
            disabled={!canNavigate}
            className="inline-flex h-7 w-7 items-center justify-center rounded-full transition hover:bg-gray-100 disabled:cursor-not-allowed disabled:opacity-40"
            aria-label="Предыдущее совпадение"
            title="Предыдущее совпадение"
          >
            <ChevronUp size={14} />
          </button>
          <span className="min-w-10 text-center font-medium text-gray-600">{selectedLabel}</span>
          <button
            type="button"
            onClick={onNext}
            disabled={!canNavigate}
            className="inline-flex h-7 w-7 items-center justify-center rounded-full transition hover:bg-gray-100 disabled:cursor-not-allowed disabled:opacity-40"
            aria-label="Следующее совпадение"
            title="Следующее совпадение"
          >
            <ChevronDown size={14} />
          </button>
        </div>

        <button
          type="button"
          onClick={onClose}
          className="inline-flex h-10 w-10 items-center justify-center rounded-full border border-gray-200 bg-white text-gray-500 transition hover:bg-gray-50 hover:text-sky-700"
          aria-label="Закрыть поиск"
          title="Закрыть поиск"
        >
          <X size={16} />
        </button>
      </div>

      <div className="mt-3">
        {query.trim().length < 2 ? (
          <p className="text-xs text-gray-500">Введите минимум 2 символа для поиска по истории чата.</p>
        ) : loading && results.length === 0 ? (
          <div className="flex items-center gap-2 text-sm text-gray-500">
            <Loader2 size={14} className="animate-spin" />
            <span>Ищем совпадения...</span>
          </div>
        ) : error ? (
          <p className="text-sm text-red-600">{error}</p>
        ) : results.length === 0 ? (
          <p className="text-sm text-gray-500">Совпадений не найдено.</p>
        ) : (
          <div className="space-y-2">
            <div className="flex items-center justify-between text-xs text-gray-500">
              <span>Найдено: {totalCount}</span>
              <span>Можно перейти Enter или кликом</span>
            </div>

            <div className="max-h-56 overflow-y-auto rounded-2xl border border-gray-100 bg-gray-50 p-2">
              <div className="space-y-1.5">
                {results.map((result, index) => (
                  <button
                    key={result.message_id}
                    type="button"
                    onClick={() => onSelect(index)}
                    className={`block w-full rounded-xl px-3 py-2 text-left transition ${index === selectedIndex ? "bg-sky-50 ring-1 ring-sky-200" : "bg-white hover:bg-gray-100"}`}
                  >
                    <div className="flex items-center justify-between gap-3">
                      <p className="truncate text-xs font-semibold text-gray-700">{result.author_name}</p>
                      <span className="shrink-0 text-[11px] text-gray-400">{formatSearchDate(result.created_at)}</span>
                    </div>
                    <p className="mt-1 line-clamp-2 text-sm text-gray-700">{result.snippet}</p>
                    {result.has_attachments ? (
                      <div className="mt-1 flex items-center gap-1 text-[11px] text-gray-400">
                        <Paperclip size={11} />
                        <span>Вложений: {result.attachments_count}</span>
                      </div>
                    ) : null}
                  </button>
                ))}
              </div>
            </div>

            {nextOffset !== null ? (
              <button
                type="button"
                onClick={onLoadMore}
                disabled={loadingMore}
                className="inline-flex items-center gap-2 rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm font-medium text-gray-700 transition hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {loadingMore ? <Loader2 size={14} className="animate-spin" /> : null}
                <span>{loadingMore ? "Загрузка..." : "Показать еще"}</span>
              </button>
            ) : null}
          </div>
        )}
      </div>
    </div>
  );
}