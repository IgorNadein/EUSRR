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
      className="fixed z-[60] flex min-w-[240px] max-w-[280px] flex-col gap-2 rounded-2xl border border-gray-200/80 bg-white/98 p-2 text-gray-900 shadow-[0_18px_50px_-18px_rgba(15,23,42,0.35)] backdrop-blur"
      style={{
        left: anchor.x,
        top: anchor.y - 8,
        transform: "translate(-100%, -100%)",
      }}
    >
      {canReply ? (
        <div className="rounded-xl border border-gray-200 bg-gray-50/80 p-1.5">
          <div className="mb-1 flex items-center justify-between px-1">
            <span className="text-[11px] font-semibold uppercase tracking-[0.08em] text-gray-400">Быстрые реакции</span>
          </div>

          <div className="flex items-center gap-1">
          {recentReactions.map((emoji) => (
            <button
              key={`recent-${message.id}-${emoji}`}
              type="button"
              onClick={() => onQuickReact(emoji)}
              className="inline-flex h-8 w-8 items-center justify-center rounded-lg border border-white bg-white text-base shadow-sm transition hover:-translate-y-0.5 hover:border-sky-200 hover:bg-sky-50"
              title="Быстрая реакция"
            >
              {emoji}
            </button>
          ))}
          <button
            type="button"
            onClick={onOpenReactionPicker}
            className="ml-auto inline-flex h-8 w-8 items-center justify-center rounded-lg border border-white bg-white text-gray-600 shadow-sm transition hover:border-sky-200 hover:bg-sky-50 hover:text-sky-700"
            title="Все смайлы"
          >
            <Smile size={14} />
          </button>
          </div>
        </div>
      ) : null}

      {isMine ? (
        <div className="rounded-xl border border-emerald-200/80 bg-emerald-50/70 p-2.5">
          <div className="mb-1.5 flex items-center gap-1.5 text-emerald-800">
            <CheckCheck size={13} />
            <span className="text-[11px] font-semibold uppercase tracking-[0.08em]">Прочитали</span>
          </div>

          {readers.length > 0 ? (
            <>
              <div className="flex flex-col gap-1.5">
              {previewReaders.map((reader) => (
                <div
                  key={`reader-${message.id}-${reader.id}`}
                  className="rounded-lg bg-white/85 px-2 py-1.5 text-xs font-medium leading-4 text-gray-700 ring-1 ring-emerald-100 break-words"
                >
                  {reader.name}
                </div>
              ))}
              </div>

              {onShowAllReaders ? (
                <button
                  type="button"
                  onClick={onShowAllReaders}
                  className="mt-2 inline-flex w-full items-center justify-between rounded-lg border border-emerald-200 bg-white/90 px-2.5 py-2 text-left text-xs font-semibold text-emerald-800 transition hover:bg-white"
                >
                  <span>{hasMoreReaders ? "Показать весь список" : "Открыть список"}</span>
                  <span className="rounded-full bg-emerald-100 px-2 py-0.5 text-[11px] font-semibold text-emerald-900">
                    {readers.length}
                  </span>
                </button>
              ) : null}
            </>
          ) : (
            <p className="text-xs text-gray-500">Пока никто не дочитал это сообщение.</p>
          )}
        </div>
      ) : null}

      <div className="flex flex-col gap-1">
        {canReply ? (
          <button
            type="button"
            onClick={onReply}
            className="inline-flex w-full items-center gap-2 rounded-xl border border-sky-200 bg-sky-50 px-3 py-2 text-xs font-medium text-sky-700 transition hover:bg-sky-100"
          >
            <Reply size={13} />
            Ответить
          </button>
        ) : null}

        {canManage ? (
          <button
            type="button"
            onClick={onEdit}
            className="inline-flex w-full items-center gap-2 rounded-xl border border-gray-200 bg-white px-3 py-2 text-xs font-medium text-gray-700 transition hover:bg-gray-50"
          >
            <Pencil size={13} />
            Редактировать
          </button>
        ) : null}

        {canManage ? (
          <button
            type="button"
            onClick={onDelete}
            className="inline-flex w-full items-center gap-2 rounded-xl border border-red-200 bg-red-50 px-3 py-2 text-xs font-medium text-red-700 transition hover:bg-red-100"
          >
            <Trash2 size={13} />
            Удалить
          </button>
        ) : null}
      </div>
    </div>
  );
}