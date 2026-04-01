"use client";

import { Pencil, Reply, Smile, Trash2 } from "lucide-react";

import type { Message } from "@/types/api";

type MessageActionsMenuProps = {
  anchor: { x: number; y: number };
  message: Message;
  canReply: boolean;
  canManage: boolean;
  recentReactions: string[];
  onQuickReact: (emoji: string) => void;
  onOpenReactionPicker: () => void;
  onReply: () => void;
  onEdit: () => void;
  onDelete: () => void;
};

export default function MessageActionsMenu({
  anchor,
  message,
  canReply,
  canManage,
  recentReactions,
  onQuickReact,
  onOpenReactionPicker,
  onReply,
  onEdit,
  onDelete,
}: MessageActionsMenuProps) {
  return (
    <div
      data-actions-menu="true"
      className="fixed z-[60] flex min-w-[176px] flex-col gap-1 rounded-lg border border-gray-200 bg-white p-1 shadow-xl"
      style={{
        left: anchor.x,
        top: anchor.y - 6,
        transform: "translate(-100%, -100%)",
      }}
    >
      {canReply ? (
        <div className="mb-1 flex items-center gap-1 rounded-md bg-gray-50 p-1">
          {recentReactions.map((emoji) => (
            <button
              key={`recent-${message.id}-${emoji}`}
              type="button"
              onClick={() => onQuickReact(emoji)}
              className="inline-flex h-7 w-7 items-center justify-center rounded-md bg-white text-base hover:bg-sky-50"
              title="Быстрая реакция"
            >
              {emoji}
            </button>
          ))}
          <button
            type="button"
            onClick={onOpenReactionPicker}
            className="ml-auto inline-flex h-7 w-7 items-center justify-center rounded-md bg-white text-gray-600 hover:bg-sky-50 hover:text-sky-700"
            title="Все смайлы"
          >
            <Smile size={14} />
          </button>
        </div>
      ) : null}

      {canReply ? (
        <button
          type="button"
          onClick={onReply}
          className="inline-flex w-full items-center gap-1 rounded-md border border-sky-200 bg-sky-50 px-2 py-1 text-xs font-medium text-sky-700 hover:bg-sky-100"
        >
          <Reply size={12} />
          Ответить
        </button>
      ) : null}

      {canManage ? (
        <>
          <button
            type="button"
            onClick={onEdit}
            className="inline-flex w-full items-center gap-1 rounded-md border border-gray-200 bg-white px-2 py-1 text-xs font-medium text-gray-700 hover:bg-gray-50"
          >
            <Pencil size={12} />
            Редактировать
          </button>

          <button
            type="button"
            onClick={onDelete}
            className="inline-flex w-full items-center gap-1 rounded-md border border-red-200 bg-red-50 px-2 py-1 text-xs font-medium text-red-700 hover:bg-red-100"
          >
            <Trash2 size={12} />
            Удалить
          </button>
        </>
      ) : null}
    </div>
  );
}