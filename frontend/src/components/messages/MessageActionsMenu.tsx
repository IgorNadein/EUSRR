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
      className="fixed z-[60] min-w-[208px] max-w-[232px] rounded-xl border border-gray-200 bg-white py-1.5 shadow-lg ring-1 ring-slate-100"
      style={{
        left: anchor.x,
        top: anchor.y - 8,
        transform: "translate(-100%, -100%)",
      }}
    >
      {canReply ? (
        <div className="border-b border-slate-100 px-2.5 pb-2 pt-1">
          <div className="mb-1.5 px-0.5 text-[10px] font-semibold uppercase tracking-[0.08em] text-gray-400">Реакции</div>
          <div className="flex items-center gap-1">
          {recentReactions.map((emoji) => (
            <button
              key={`recent-${message.id}-${emoji}`}
              type="button"
              onClick={() => onQuickReact(emoji)}
              className="inline-flex h-8 w-8 items-center justify-center rounded-md text-base transition hover:bg-sky-50"
              title="Быстрая реакция"
            >
              {emoji}
            </button>
          ))}
          <button
            type="button"
            onClick={onOpenReactionPicker}
            className="ml-auto inline-flex h-8 w-8 items-center justify-center rounded-md text-gray-500 transition hover:bg-sky-50 hover:text-sky-700"
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
              className="flex w-full items-center justify-between gap-2 px-3 py-2 text-left text-sm text-gray-700 transition hover:bg-gray-50"
            >
              <span className="flex items-center gap-2">
                <CheckCheck size={13} className="text-gray-400" />
                Кто прочитал
              </span>
              <span className="text-xs text-gray-400">{readers.length}</span>
            </button>
            <div className="my-1 border-t border-slate-100" />
          </>
        ) : null}

        {canReply ? (
          <button
            type="button"
            onClick={onReply}
            className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm text-gray-700 transition hover:bg-sky-50"
          >
            <Reply size={13} className="text-gray-400" />
            Ответить
          </button>
        ) : null}

        {canManage ? (
          <button
            type="button"
            onClick={onEdit}
            className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm text-gray-700 transition hover:bg-gray-50"
          >
            <Pencil size={13} className="text-gray-400" />
            Редактировать
          </button>
        ) : null}

        {canManage ? (
          <button
            type="button"
            onClick={onDelete}
            className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm text-red-600 transition hover:bg-red-50"
          >
            <Trash2 size={13} className="text-red-400" />
            Удалить
          </button>
        ) : null}
      </div>
    </div>
  );
}