"use client";

import { CheckCheck, Pencil, Reply, Smile, Trash2 } from "lucide-react";

import type { Message } from "@/types/api";

type MessageActionsMenuProps = {
  anchor: { x: number; y: number };
  currentUserId?: number;
  message: Message;
  canReply: boolean;
  canManage: boolean;
  recentReactions: string[];
  onQuickReact: (emoji: string) => void;
  onOpenReactionPicker: () => void;
  onShowAllReaders?: () => void;
  onReply: () => void;
  onEdit: () => void;
  onDelete: () => void;
};

export default function MessageActionsMenu({
  anchor,
  currentUserId,
  message,
  canReply,
  canManage,
  recentReactions,
  onQuickReact,
  onOpenReactionPicker,
  onShowAllReaders,
  onReply,
  onEdit,
  onDelete,
}: MessageActionsMenuProps) {
  const isMine = Boolean(
    currentUserId &&
      (message.author_id === currentUserId || message.author?.id === currentUserId || message.sender?.id === currentUserId)
  );
  const readers = message.read_by || [];

  return (
    <div
      data-actions-menu="true"
      className="app-menu fixed z-[60] min-w-[208px] max-w-[232px] rounded-xl py-1.5"
      style={{
        left: anchor.x,
        top: anchor.y - 8,
        transform: "translate(-100%, -100%)",
      }}
    >
      {canReply ? (
        <div className="app-divider border-b px-2.5 pb-2 pt-1">
          <div className="app-text-muted mb-1.5 px-0.5 text-[10px] font-semibold uppercase tracking-[0.08em]">Реакции</div>
          <div className="flex items-center gap-1">
          {recentReactions.map((emoji) => (
            <button
              key={`recent-${message.id}-${emoji}`}
              type="button"
              onClick={() => onQuickReact(emoji)}
              className="inline-flex h-8 w-8 items-center justify-center rounded-md text-base transition hover:bg-[var(--surface-secondary)]"
              title="Быстрая реакция"
            >
              {emoji}
            </button>
          ))}
          <button
            type="button"
            onClick={onOpenReactionPicker}
            className="app-text-muted ml-auto inline-flex h-8 w-8 items-center justify-center rounded-md transition hover:bg-[var(--surface-secondary)] hover:text-[var(--accent-primary-strong)]"
            title="Все смайлы"
          >
            <Smile size={14} />
          </button>
          </div>
        </div>
      ) : null}

      <div className="py-1">
        {isMine && onShowAllReaders ? (
          <>
            <button
              type="button"
              onClick={onShowAllReaders}
              className="flex w-full items-center justify-between gap-2 px-3 py-2 text-left text-sm text-[var(--foreground)] transition hover:bg-[var(--surface-secondary)]"
            >
              <span className="flex items-center gap-2">
                <CheckCheck size={13} className="app-text-muted" />
                Кто прочитал
              </span>
              <span className="app-text-muted text-xs">{readers.length}</span>
            </button>
            <div className="app-divider my-1 border-t" />
          </>
        ) : null}

        {canReply ? (
          <button
            type="button"
            onClick={onReply}
            className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm text-[var(--foreground)] transition hover:bg-[var(--surface-secondary)]"
          >
            <Reply size={13} className="app-text-muted" />
            Ответить
          </button>
        ) : null}

        {canManage ? (
          <button
            type="button"
            onClick={onEdit}
            className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm text-[var(--foreground)] transition hover:bg-[var(--surface-secondary)]"
          >
            <Pencil size={13} className="app-text-muted" />
            Редактировать
          </button>
        ) : null}

        {canManage ? (
          <button
            type="button"
            onClick={onDelete}
            className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm text-[var(--danger-foreground)] transition hover:bg-[var(--danger-soft)]"
          >
            <Trash2 size={13} className="text-[var(--danger-foreground)]" />
            Удалить
          </button>
        ) : null}
      </div>
    </div>
  );
}
