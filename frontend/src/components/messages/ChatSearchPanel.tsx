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
    <div className="app-divider app-surface shrink-0 border-b px-4 py-3 lg:px-0">
      <div className="flex items-center gap-2">
        <div className="relative min-w-0 flex-1">
          <Search size={15} className="app-text-muted pointer-events-none absolute left-3 top-1/2 -translate-y-1/2" />
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
            className="app-input h-10 w-full rounded-full pl-10 pr-4 text-sm"
          />
        </div>

        <div className="app-surface-elevated app-text-muted flex items-center gap-1 rounded-full px-2 py-1 text-xs">
          <button
            type="button"
            onClick={onPrevious}
            disabled={!canNavigate}
            className="app-action-ghost inline-flex h-7 w-7 items-center justify-center rounded-full disabled:cursor-not-allowed disabled:opacity-40"
            aria-label="Предыдущее совпадение"
            title="Предыдущее совпадение"
          >
            <ChevronUp size={14} />
          </button>
          <span className="min-w-10 text-center font-medium text-[var(--foreground)]">{selectedLabel}</span>
          <button
            type="button"
            onClick={onNext}
            disabled={!canNavigate}
            className="app-action-ghost inline-flex h-7 w-7 items-center justify-center rounded-full disabled:cursor-not-allowed disabled:opacity-40"
            aria-label="Следующее совпадение"
            title="Следующее совпадение"
          >
            <ChevronDown size={14} />
          </button>
        </div>

        <button
          type="button"
          onClick={onClose}
          className="app-action-secondary app-text-muted inline-flex h-10 w-10 items-center justify-center rounded-full hover:text-[var(--accent-primary-strong)]"
          aria-label="Закрыть поиск"
          title="Закрыть поиск"
        >
          <X size={16} />
        </button>
      </div>

      <div className="mt-3">
        {query.trim().length < 2 ? (
          <p className="app-text-muted text-xs">Введите минимум 2 символа для поиска по истории чата.</p>
        ) : loading && results.length === 0 ? (
          <div className="app-text-muted flex items-center gap-2 text-sm">
            <Loader2 size={14} className="animate-spin" />
            <span>Ищем совпадения...</span>
          </div>
        ) : error ? (
          <p className="app-feedback-danger rounded-lg px-3 py-2 text-sm">{error}</p>
        ) : results.length === 0 ? (
          <p className="app-text-muted text-sm">Совпадений не найдено.</p>
        ) : (
          <div className="space-y-2">
            <div className="app-text-muted flex items-center justify-between text-xs">
              <span>Найдено: {totalCount}</span>
              <span>Можно перейти Enter или кликом</span>
            </div>

            <div className="app-surface-muted max-h-56 overflow-y-auto rounded-2xl p-2">
              <div className="space-y-1.5">
                {results.map((result, index) => (
                  <button
                    key={result.message_id}
                    type="button"
                    onClick={() => onSelect(index)}
                    className={`block w-full rounded-xl px-3 py-2 text-left transition ${index === selectedIndex ? "app-selected" : "app-surface-elevated hover:bg-[var(--surface-secondary)]"}`}
                  >
                    <div className="flex items-center justify-between gap-3">
                      <p className="truncate text-xs font-semibold text-[var(--foreground)]">{result.author_name}</p>
                      <span className="app-text-muted shrink-0 text-[11px]">{formatSearchDate(result.created_at)}</span>
                    </div>
                    <p className="mt-1 line-clamp-2 text-sm text-[var(--foreground)]">{result.snippet}</p>
                    {result.has_attachments ? (
                      <div className="app-text-muted mt-1 flex items-center gap-1 text-[11px]">
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
                className="app-action-secondary inline-flex items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium disabled:cursor-not-allowed disabled:opacity-50"
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
