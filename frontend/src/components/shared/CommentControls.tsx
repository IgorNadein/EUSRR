"use client";

import { Send, Trash2 } from "lucide-react";

type CommentComposerProps = {
  disabled?: boolean;
  multiline?: boolean;
  onCancel?: () => void;
  onChange: (value: string) => void;
  onSubmit: () => void | Promise<void>;
  placeholder?: string;
  rows?: number;
  value: string;
};

export function CommentComposer({
  disabled = false,
  multiline = false,
  onCancel,
  onChange,
  onSubmit,
  placeholder = "Добавить комментарий",
  rows = 2,
  value,
}: CommentComposerProps) {
  const submitDisabled = disabled || !value.trim();

  if (multiline) {
    return (
      <div className="space-y-2">
        <textarea
          value={value}
          onChange={(event) => onChange(event.target.value)}
          placeholder={placeholder}
          className="app-input w-full rounded-lg p-3 text-sm resize-none"
          rows={rows}
        />
        <div className="flex flex-wrap items-center justify-end gap-2">
          {onCancel ? (
            <button
              type="button"
              onClick={onCancel}
              className="app-action-secondary rounded-lg px-3 py-1.5 text-xs font-medium"
            >
              Отмена
            </button>
          ) : null}
          <button
            type="button"
            onClick={() => void onSubmit()}
            disabled={submitDisabled}
            className="app-action-primary inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-lg disabled:opacity-50"
            title="Отправить комментарий"
            aria-label="Отправить комментарий"
          >
            <Send size={14} />
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="grid gap-2 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-center">
      <input
        value={value}
        onChange={(event) => onChange(event.target.value)}
        placeholder={placeholder}
        className="app-input min-w-0 w-full rounded-lg px-3 py-2 text-xs"
      />
      <div className="flex items-center justify-end">
        <button
          type="button"
          onClick={() => void onSubmit()}
          disabled={submitDisabled}
          className="app-action-primary inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-lg disabled:opacity-50"
          title="Отправить комментарий"
          aria-label="Отправить комментарий"
        >
          <Send size={14} />
        </button>
      </div>
    </div>
  );
}

type CommentDeleteButtonProps = {
  disabled?: boolean;
  onClick: () => void | Promise<void>;
};

export function CommentDeleteButton({
  disabled = false,
  onClick,
}: CommentDeleteButtonProps) {
  return (
    <button
      type="button"
      onClick={() => void onClick()}
      disabled={disabled}
      className="app-action-danger inline-flex h-7 w-7 items-center justify-center rounded-lg disabled:opacity-50"
      title="Удалить комментарий"
      aria-label="Удалить комментарий"
    >
      <Trash2 size={14} />
    </button>
  );
}
