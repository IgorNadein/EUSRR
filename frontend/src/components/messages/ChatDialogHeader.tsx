"use client";

import Link from "next/link";
import Image from "next/image";
import { ArrowLeft, Bell, BellOff, Pin } from "lucide-react";

import type { Chat } from "@/types/api";
import { getChatAvatar, getChatInitials, getChatTitle } from "@/lib/messages/chatUtils";
import { resolveMediaUrl } from "@/lib/url";

type ChatDialogHeaderProps = {
  chat: Chat;
  chatId: number;
  currentUserId?: number;
  isPinned: boolean;
  notificationsEnabled: boolean;
  onTogglePin: () => void;
  onToggleNotifications: () => void;
};

function getChatSubtitle(chat: Chat): string {
  const type = chat.chat_type || chat.type;

  switch (type) {
    case "group":
      return "Групповой чат";
    case "channel":
      return "Канал";
    case "announcement":
      return "Канал объявлений";
    case "global":
      return "Глобальный чат";
    case "comments":
      return "Комментарии";
    default:
      return "Диалог";
  }
}

export default function ChatDialogHeader({
  chat,
  chatId,
  currentUserId,
  isPinned,
  notificationsEnabled,
  onTogglePin,
  onToggleNotifications,
}: ChatDialogHeaderProps) {
  const avatar = getChatAvatar(chat, currentUserId);
  const title = getChatTitle(chat, currentUserId);

  return (
    <header className="flex shrink-0 items-center justify-between gap-3 border-b border-gray-100 px-4 pt-3 pb-3 lg:px-0 lg:pt-0">
      <div className="flex items-center gap-3">
        <div className="flex h-11 w-11 items-center justify-center overflow-hidden rounded-full bg-sky-400 text-sm font-semibold text-white">
          {avatar ? (
            <div className="relative h-full w-full">
              <Image src={resolveMediaUrl(avatar)} alt={title} fill unoptimized className="object-cover" sizes="44px" />
            </div>
          ) : (
            getChatInitials(chat, currentUserId)
          )}
        </div>
        <Link href={`/messages/${chatId}/settings`} className="hover:opacity-80 transition">
          <div>
            <p className="text-sm font-semibold text-gray-900">{title}</p>
          </div>
          <p className="text-xs text-gray-500">{getChatSubtitle(chat)}</p>
        </Link>
      </div>

      <div className="flex items-center gap-2">
        <button
          type="button"
          onClick={onTogglePin}
          className={`flex h-10 w-10 items-center justify-center rounded-full border transition ${
            isPinned
              ? "border-sky-500 bg-sky-50 text-sky-700 hover:bg-sky-100"
              : "border-gray-200 bg-white text-gray-600 hover:bg-gray-50 hover:text-sky-700"
          }`}
          title={isPinned ? "Открепить чат" : "Закрепить чат"}
          aria-label={isPinned ? "Открепить чат" : "Закрепить чат"}
        >
          <Pin size={16} className={isPinned ? "fill-current" : ""} />
        </button>

        <button
          type="button"
          onClick={onToggleNotifications}
          className={`flex h-10 w-10 items-center justify-center rounded-full border transition ${
            notificationsEnabled
              ? "border-gray-200 bg-white text-gray-600 hover:bg-gray-50 hover:text-sky-700"
              : "border-amber-500 bg-amber-50 text-amber-700 hover:bg-amber-100"
          }`}
          title={notificationsEnabled ? "Отключить уведомления" : "Включить уведомления"}
          aria-label={notificationsEnabled ? "Отключить уведомления" : "Включить уведомления"}
        >
          {notificationsEnabled ? <Bell size={16} /> : <BellOff size={16} />}
        </button>

        <Link
          href="/messages"
          aria-label="К списку чатов"
          title="К списку чатов"
          className="flex h-10 w-10 items-center justify-center rounded-full border border-gray-200 bg-white text-gray-600 transition hover:bg-gray-50 hover:text-sky-700"
        >
          <ArrowLeft size={16} />
        </Link>
      </div>
    </header>
  );
}