"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import Image from "next/image";
import { ArrowLeft, Bell, BellOff, MoreHorizontal, Pin, Search } from "lucide-react";

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
  onOpenSearch: () => void;
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
  onOpenSearch,
}: ChatDialogHeaderProps) {
  const avatar = getChatAvatar(chat, currentUserId);
  const title = getChatTitle(chat, currentUserId);
  const [menuOpen, setMenuOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!menuOpen) {
      return;
    }

    const handlePointerDown = (event: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
        setMenuOpen(false);
      }
    };

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setMenuOpen(false);
      }
    };

    document.addEventListener("mousedown", handlePointerDown);
    document.addEventListener("keydown", handleKeyDown);

    return () => {
      document.removeEventListener("mousedown", handlePointerDown);
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, [menuOpen]);

  const subtitle = getChatSubtitle(chat);

  return (
    <header className="relative z-30 flex shrink-0 items-center gap-3 border-b border-gray-100 bg-white px-4 pt-3 pb-3 lg:px-0 lg:pt-0">
      <Link
        href="/messages"
        aria-label="К списку чатов"
        title="К списку чатов"
        className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full border border-gray-200 bg-white text-gray-600 transition hover:bg-gray-50 hover:text-sky-700"
      >
        <ArrowLeft size={16} />
      </Link>

      <Link href={`/messages/${chatId}/settings`} className="flex min-w-0 flex-1 items-center gap-3 transition hover:opacity-80">
        <div className="flex h-11 w-11 items-center justify-center overflow-hidden rounded-full bg-sky-400 text-sm font-semibold text-white">
          {avatar ? (
            <div className="relative h-full w-full">
              <Image src={resolveMediaUrl(avatar)} alt={title} fill unoptimized className="object-cover" sizes="44px" />
            </div>
          ) : (
            getChatInitials(chat, currentUserId)
          )}
        </div>
        <div className="min-w-0">
          <p className="truncate text-sm font-semibold text-gray-900">{title}</p>
          <p className="truncate text-xs text-gray-500">{subtitle}</p>
        </div>
      </Link>

      <div ref={menuRef} className="relative z-40 shrink-0">
        <button
          type="button"
          onClick={() => setMenuOpen((prev) => !prev)}
          className="flex h-10 w-10 items-center justify-center rounded-full border border-gray-200 bg-white text-gray-600 transition hover:bg-gray-50 hover:text-sky-700"
          aria-label="Дополнительные действия"
          aria-expanded={menuOpen}
          aria-haspopup="menu"
          title="Дополнительные действия"
        >
          <MoreHorizontal size={16} />
        </button>

        {menuOpen ? (
          <div className="absolute right-0 top-full z-[80] mt-2 w-56 overflow-hidden rounded-2xl border border-gray-200 bg-white py-1 shadow-lg shadow-gray-200/70 ring-1 ring-gray-100">
            <button
              type="button"
              onClick={() => {
                setMenuOpen(false);
                onOpenSearch();
              }}
              className="flex w-full items-center gap-3 px-4 py-3 text-left text-sm font-medium text-gray-700 transition hover:bg-gray-50"
            >
              <Search size={16} className="shrink-0 text-gray-500" />
              <span>Поиск по сообщениям</span>
            </button>

            <button
              type="button"
              onClick={() => {
                setMenuOpen(false);
                onTogglePin();
              }}
              className="flex w-full items-center gap-3 px-4 py-3 text-left text-sm font-medium text-gray-700 transition hover:bg-gray-50"
            >
              <Pin size={16} className={`shrink-0 ${isPinned ? "fill-current text-sky-700" : "text-gray-500"}`} />
              <span>{isPinned ? "Открепить чат" : "Закрепить чат"}</span>
            </button>

            <button
              type="button"
              onClick={() => {
                setMenuOpen(false);
                onToggleNotifications();
              }}
              className="flex w-full items-center gap-3 px-4 py-3 text-left text-sm font-medium text-gray-700 transition hover:bg-gray-50"
            >
              {notificationsEnabled ? (
                <Bell size={16} className="shrink-0 text-gray-500" />
              ) : (
                <BellOff size={16} className="shrink-0 text-amber-700" />
              )}
              <span>{notificationsEnabled ? "Отключить уведомления" : "Включить уведомления"}</span>
            </button>
          </div>
        ) : null}
      </div>
    </header>
  );
}