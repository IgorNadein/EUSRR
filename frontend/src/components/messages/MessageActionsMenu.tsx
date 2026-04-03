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
  const previewReaders = readers.slice(0, 3);
  const hasMoreReaders = readers.length > previewReaders.length;

  return (
    <div
      data-actions-menu="true"
      className="fixed z-[60] min-w-[220px] max-w-[248px] rounded-xl border border-gray-200 bg-white py-2 shadow-lg ring-1 ring-slate-100"
      style={{
        left: anchor.x,
        top: anchor.y - 8,
        transform: "translate(-100%, -100%)",
      }}
    >
      {canReply ? (
        <div className="px-3 pb-2">
          <div className="mb-2 flex items-center justify-between">
            <span className="text-[10px] font-semibold uppercase tracking-[0.08em] text-gray-400">Быстрые реакции</span>
          </div>

          <div className="flex items-center gap-1.5">
          {recentReactions.map((emoji) => (
            <button
              key={`recent-${message.id}-${emoji}`}
              type="button"
              onClick={() => onQuickReact(emoji)}
              className="inline-flex h-8 w-8 items-center justify-center rounded-lg bg-gray-50 text-base transition hover:bg-sky-50"
              title="Быстрая реакция"
            >
              {emoji}
            </button>
          ))}
          <button
            type="button"
            onClick={onOpenReactionPicker}
            className="ml-auto inline-flex h-8 w-8 items-center justify-center rounded-lg bg-gray-50 text-gray-500 transition hover:bg-sky-50 hover:text-sky-700"
            title="Все смайлы"
          >
            <Smile size={14} />
          </button>
          </div>
        </div>
      ) : null}

      {isMine ? (
        <div className="border-t border-slate-100 px-3 py-2">
          <div className="mb-1.5 flex items-center gap-1.5 text-gray-500">
            <CheckCheck size={13} />
            <span className="text-[10px] font-semibold uppercase tracking-[0.08em]">Прочитали</span>
          </div>

          {readers.length > 0 ? (
            <>
              <div className="flex flex-col gap-1.5">
              {previewReaders.map((reader) => (
                <div
                  key={`reader-${message.id}-${reader.id}`}
                  className="text-xs font-medium leading-4 text-gray-700 break-words"
                >
                  {reader.name}
                </div>
              ))}
              </div>

              {onShowAllReaders ? (
                <button
                  type="button"
                  onClick={onShowAllReaders}
                  className="mt-2 inline-flex items-center gap-1 text-xs font-medium text-sky-700 transition hover:text-sky-800"
                >
                  <span>{hasMoreReaders ? `Показать весь список (${readers.length})` : "Открыть список"}</span>
                </button>
              ) : null}
            </>
          ) : (
            <p className="text-xs text-gray-500">Пока никто не дочитал это сообщение.</p>
          )}
        </div>
      ) : null}

      <div className="border-t border-slate-100 py-1">
        {canReply ? (
          <button
            type="button"
            onClick={onReply}
            className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm text-sky-700 transition hover:bg-sky-50"
          >
            <Reply size={13} />
            Ответить
          </button>
        ) : null}

        {canManage ? (
          <button
            type="button"
            onClick={onEdit}
            className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm text-gray-700 transition hover:bg-gray-50"
          >
            <Pencil size={13} />
            Редактировать
          </button>
        ) : null}

        {canManage ? (
          <button
            type="button"
            onClick={onDelete}
            className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm text-red-600 transition hover:bg-red-50"
          >
            <Trash2 size={13} />
            Удалить
          </button>
        ) : null}
      </div>
    </div>
  );
}