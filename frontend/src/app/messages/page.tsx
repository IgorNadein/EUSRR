"use client";

import { useEffect, useMemo, useState } from "react";
import { AppShell } from "../../components/AppShell";
import { apiClient } from "@/lib/api";
import type { Chat } from "@/types/api";
import { Search, MessageCircle } from "lucide-react";
import Link from "next/link";
import { useUser } from "@/contexts/UserContext";

const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || "";

function getChatTitle(chat: Chat): string {
  return chat.name?.trim() || "Диалог";
}

function getChatInitials(chat: Chat): string {
  const title = getChatTitle(chat);
  return title
    .split(" ")
    .filter(Boolean)
    .slice(0, 2)
    .map((p) => p[0]?.toUpperCase() || "")
    .join("") || "Ч";
}

function resolveAvatarUrl(url?: string | null): string {
  if (!url) return "";
  if (/^https?:\/\//i.test(url)) return encodeURI(url);
  if (url.startsWith("//")) return encodeURI(`https:${url}`);
  if (url.startsWith("/") && BACKEND_URL) {
    return encodeURI(`${BACKEND_URL.replace(/\/$/, "")}${url}`);
  }
  return encodeURI(url);
}

function formatTime(date?: string): string {
  if (!date) return "";
  const d = new Date(date);
  if (Number.isNaN(d.getTime())) return "";
  const now = new Date();
  const isToday = d.toDateString() === now.toDateString();
  if (isToday) {
    return d.toLocaleTimeString("ru-RU", { hour: "2-digit", minute: "2-digit" });
  }
  return d.toLocaleDateString("ru-RU", { day: "2-digit", month: "2-digit" });
}

function isChatOnline(chat: Chat, currentUserId?: number): boolean {
  const chatKind = chat.chat_type || chat.type;
  if (chatKind !== "direct" && chatKind !== "private") return false;
  const otherParticipant = (chat.participants || []).find((p) => p.id !== currentUserId);
  return Boolean(otherParticipant?.is_active);
}

export default function MessagesPage() {
  const { user } = useUser();
  const [chats, setChats] = useState<Chat[]>([]);
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function loadChats() {
      try {
        setLoading(true);
        setError(null);
        const response = await apiClient.getChats();
        const items = response.results || [];
        setChats(items);
      } catch (e: any) {
        console.error("Ошибка загрузки чатов:", e);
        setError("Не удалось загрузить чаты");
      } finally {
        setLoading(false);
      }
    }

    loadChats();
  }, []);

  const filteredChats = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return chats;

    return chats.filter((chat) => {
      const title = getChatTitle(chat).toLowerCase();
      const lastMessage = chat.last_message?.content?.toLowerCase() || "";
      return title.includes(q) || lastMessage.includes(q);
    });
  }, [chats, search]);

  return (
    <AppShell>
      {loading ? (
        <div className="rounded-2xl bg-white p-8 text-center shadow-sm ring-1 ring-gray-100">
          <div className="mb-4 inline-block h-8 w-8 animate-spin rounded-full border-4 border-sky-400 border-t-transparent" />
          <p className="text-sm text-gray-500">Загрузка чатов...</p>
        </div>
      ) : error ? (
        <div className="rounded-2xl bg-red-50 p-6 text-center">
          <p className="text-sm text-red-800">{error}</p>
        </div>
      ) : (
        <section className="rounded-2xl bg-white p-4 shadow-sm ring-1 ring-gray-100">
          <div className="relative mb-4">
            <Search size={16} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Поиск по чатам"
              className="w-full rounded-lg border border-gray-200 bg-gray-50 py-2.5 pl-9 pr-3 text-sm text-gray-800 transition focus:border-sky-500 focus:bg-white focus:outline-none focus:ring-2 focus:ring-sky-100"
            />
          </div>

          <div className="space-y-2">
            {filteredChats.length === 0 ? (
              <div className="rounded-xl bg-gray-50 p-6 text-center">
                <p className="text-sm text-gray-500">Чаты не найдены</p>
              </div>
            ) : (
              filteredChats.map((chat) => (
                <Link
                  key={chat.id}
                  href={`/messages/${chat.id}`}
                  className="block w-full rounded-xl border border-transparent p-3 text-left transition hover:border-gray-200 hover:bg-gray-50"
                >
                  <div className="flex items-start gap-3">
                    <div className="relative h-10 w-10">
                      <div className="flex h-10 w-10 items-center justify-center overflow-hidden rounded-full bg-sky-400 text-xs font-semibold text-white">
                        {chat.avatar ? (
                          <img
                            src={resolveAvatarUrl(chat.avatar)}
                            alt={getChatTitle(chat)}
                            className="h-full w-full object-cover"
                          />
                        ) : (
                          getChatInitials(chat)
                        )}
                      </div>
                      {isChatOnline(chat, user?.id) ? (
                        <span className="absolute -bottom-0.5 -right-0.5 z-10 h-3 w-3 rounded-full bg-sky-400 ring-2 ring-white" />
                      ) : null}
                    </div>
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center justify-between gap-2">
                        <p className="truncate text-sm font-semibold text-gray-900">{getChatTitle(chat)}</p>
                        <span className="shrink-0 text-xs text-gray-500">{formatTime(chat.last_message?.created_at)}</span>
                      </div>
                      <p className="mt-1 truncate text-xs text-gray-500">
                        {chat.last_message?.content || "Нет сообщений"}
                      </p>
                    </div>
                  </div>
                </Link>
              ))
            )}
          </div>

          {filteredChats.length === 0 ? (
            <div className="mt-4 flex min-h-[120px] items-center justify-center rounded-xl bg-gray-50 text-center">
              <div>
                <MessageCircle size={20} className="mx-auto mb-2 text-gray-400" />
                <p className="text-sm text-gray-500">Создайте или найдите диалог</p>
              </div>
            </div>
          ) : null}
        </section>
      )}
    </AppShell>
  );
}
