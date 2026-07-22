"use client";

import { useRef, type ReactNode } from "react";
import { ChevronRight, FileText, Loader2, Paperclip, Plus, Trash2 } from "lucide-react";

interface DocumentFilePanelProps {
  title: string;
  count: number;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onFilesSelected: (files: File[]) => void;
  children?: ReactNode;
  multiple?: boolean;
  disabled?: boolean;
  busy?: boolean;
  addLabel?: string;
  emptyText?: string;
}

interface DocumentFileRowProps {
  name: string;
  meta?: string;
  pending?: boolean;
  error?: string;
  onRemove?: () => void;
  disabled?: boolean;
}

export function DocumentFilePanel({
  title,
  count,
  open,
  onOpenChange,
  onFilesSelected,
  children,
  multiple = false,
  disabled = false,
  busy = false,
  addLabel = multiple ? "Добавить файлы" : "Добавить файл",
  emptyText = multiple ? "Файлов пока нет" : "Файл пока не выбран",
}: DocumentFilePanelProps) {
  const inputRef = useRef<HTMLInputElement>(null);

  return (
    <div className="rounded-xl border border-[var(--border-subtle)]">
      <div className="flex items-center px-1 py-1">
        <button
          type="button"
          onClick={() => onOpenChange(!open)}
          className="flex min-w-0 flex-1 items-center gap-2 rounded-lg px-2 py-1.5 text-left"
          aria-expanded={open}
        >
          <Paperclip size={15} className="app-text-muted shrink-0" />
          <span className="truncate text-sm font-medium text-[var(--foreground)]">{title}</span>
          <span className="app-badge rounded-full px-2 py-0.5 text-[11px]">{count}</span>
        </button>

        <input
          ref={inputRef}
          type="file"
          multiple={multiple}
          className="sr-only"
          disabled={disabled || busy}
          onChange={(event) => {
            const files = Array.from(event.currentTarget.files || []);
            event.currentTarget.value = "";
            if (files.length === 0) return;
            onOpenChange(true);
            onFilesSelected(files);
          }}
        />
        <button
          type="button"
          onClick={() => inputRef.current?.click()}
          disabled={disabled || busy}
          className="app-icon-button flex h-8 w-8 shrink-0 items-center justify-center rounded-lg disabled:opacity-50"
          title={addLabel}
          aria-label={addLabel}
        >
          {busy ? <Loader2 size={15} className="animate-spin" /> : <Plus size={15} />}
        </button>
        <button
          type="button"
          onClick={() => onOpenChange(!open)}
          className="app-icon-button flex h-8 w-8 shrink-0 items-center justify-center rounded-lg"
          title={open ? "Скрыть файлы" : "Показать файлы"}
          aria-label={open ? "Скрыть файлы" : "Показать файлы"}
          aria-expanded={open}
        >
          <ChevronRight
            size={16}
            className={`transition-transform ${open ? "rotate-90" : ""}`}
          />
        </button>
      </div>

      {open ? (
        <div className="space-y-3 border-t border-[var(--border-subtle)] p-3">
          {children ?? (
            <div className="app-surface-muted rounded-xl border border-dashed border-[var(--border-subtle)] px-3 py-4 text-center">
              <p className="app-text-muted text-xs">{emptyText}</p>
            </div>
          )}
        </div>
      ) : null}
    </div>
  );
}

export function DocumentFileRow({
  name,
  meta,
  pending = false,
  error,
  onRemove,
  disabled = false,
}: DocumentFileRowProps) {
  return (
    <div className="flex min-w-0 items-center gap-2 border-b border-[var(--border-subtle)] px-3 py-2.5 last:border-b-0">
      <span className="app-selected flex h-8 w-8 shrink-0 items-center justify-center rounded-lg">
        <FileText size={15} />
      </span>
      <span className="min-w-0 flex-1">
        <span className="block truncate text-sm font-medium text-[var(--foreground)]">{name}</span>
        {meta || error ? (
          <span className={`mt-0.5 block truncate text-[11px] ${error ? "text-red-500" : "app-text-muted"}`}>
            {error || meta}
          </span>
        ) : null}
      </span>
      {pending ? (
        <span className="app-badge shrink-0 rounded-full px-2 py-0.5 text-[10px]">новое</span>
      ) : null}
      {onRemove ? (
        <button
          type="button"
          onClick={onRemove}
          disabled={disabled}
          className="app-icon-button flex h-8 w-8 shrink-0 items-center justify-center rounded-lg disabled:opacity-50"
          title="Убрать"
          aria-label={`Убрать ${name}`}
        >
          <Trash2 size={14} />
        </button>
      ) : null}
    </div>
  );
}
