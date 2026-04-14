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
  submitDisabled?: boolean;
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
  submitDisabled,
  value,
}: CommentComposerProps) {
  const resolvedSubmitDisabled =
    submitDisabled ?? (disabled || !value.trim());

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
            disabled={resolvedSubmitDisabled}
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
    <div className="flex min-w-0 items-center gap-2">
      <input
        value={value}
        onChange={(event) => onChange(event.target.value)}
        placeholder={placeholder}
        className="app-input h-9 w-0 min-w-0 flex-1 rounded-lg px-3 py-2 text-xs"
      />
      <button
        type="button"
        onClick={() => void onSubmit()}
        disabled={resolvedSubmitDisabled}
        className="app-action-primary inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-lg disabled:opacity-50"
        title="Отправить комментарий"
        aria-label="Отправить комментарий"
      >
        <Send size={14} />
      </button>
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
