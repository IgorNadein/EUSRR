"use client";

import { useEffect, useMemo, useState } from "react";
import { AppShell } from "../../components/AppShell";
import { apiClient } from "@/lib/api";
import type { Chat } from "@/types/api";
import { Search, MessageCircle } from "lucide-react";
import Link from "next/link";
import Image from "next/image";
import { useUser } from "@/contexts/UserContext";

const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || "https://corp.robotail.pro";

function getUserFullName(lastName?: string, firstName?: string): string {
  return `${lastName || ""} ${firstName || ""}`.trim();
}

function normalizeName(value?: string | null): string {
  return (value || "").replace(/\s+/g, " ").trim().toLowerCase();
}

function isLikelyCurrentUserName(candidate: string, user?: { first_name?: string; last_name?: string; patronymic?: string; email?: string } | null): boolean {
  if (!user) return false;

  const c = normalizeName(candidate);
  if (!c) return false;

  const fn = normalizeName(user.first_name);
  const ln = normalizeName(user.last_name);
  const pn = normalizeName(user.patronymic);
  const email = normalizeName(user.email);

  if (email && c === email) return true;

  const variants = new Set<string>([
    normalizeName(`${ln} ${fn}`),
    normalizeName(`${fn} ${ln}`),
    normalizeName(`${ln} ${fn} ${pn}`),
    normalizeName(`${fn} ${pn} ${ln}`),
    normalizeName(`${fn} ${pn}`),
  ]);

  if (variants.has(c)) return true;

  if (fn && ln && c.includes(fn) && c.includes(ln)) return true;

  return false;
}

function getInterlocutorFromParticipants(chat: Chat, currentUserId?: number) {
  const participants = (chat.participants || []).filter(
    (p): p is Exclude<typeof p, number> => typeof p === "object" && p !== null
  );
  return participants.find((p) => p.id !== currentUserId);
}

function getInterlocutorFromParticipantDetails(chat: Chat, currentUserId?: number) {
  return (chat.participant_details || []).find((p) => p.id !== currentUserId);
}

function getInterlocutorNameFromParticipantNames(chat: Chat, currentUser?: { first_name?: string; last_name?: string; patronymic?: string; email?: string } | null): string {
  const names = (chat.participant_names || []).map((n) => (n || "").trim()).filter(Boolean);
  if (!names.length) return "";
  const other = names.find((n) => !isLikelyCurrentUserName(n, currentUser));
  return other || names[0] || "";
}

function getChatTitle(chat: Chat, currentUserId?: number, currentUser?: { first_name?: string; last_name?: string; patronymic?: string; email?: string } | null): string {
  const chatKind = chat.chat_type || chat.type;
  const rawName = (chat.name || "").trim();

  if (chatKind === "direct" || chatKind === "private" || !rawName || rawName.toLowerCase() === "диалог") {
    const detailsOther = getInterlocutorFromParticipantDetails(chat, currentUserId);
    if (detailsOther?.name?.trim()) {
      return detailsOther.name.trim();
    }

    const other = getInterlocutorFromParticipants(chat, currentUserId);
    if (other && typeof other === "object") {
      const name = getUserFullName(other.last_name, other.first_name);
      if (name) return name;
      if (other.email) return other.email;
    }

    const namesFallback = getInterlocutorNameFromParticipantNames(chat, currentUser);
    if (namesFallback) return namesFallback;
  }

  return rawName || "Диалог";
}

function getChatAvatar(chat: Chat, currentUserId?: number): string {
  const chatKind = chat.chat_type || chat.type;
  if (chatKind === "direct" || chatKind === "private" || (chat.name || "").trim().toLowerCase() === "диалог") {
    const detailsOther = getInterlocutorFromParticipantDetails(chat, currentUserId);
    if (detailsOther?.avatar) return detailsOther.avatar;

    const other = getInterlocutorFromParticipants(chat, currentUserId);
    if (other?.avatar) return other.avatar;
  }
  return chat.avatar || "";
}

function getChatInitials(chat: Chat, currentUserId?: number, currentUser?: { first_name?: string; last_name?: string; patronymic?: string; email?: string } | null): string {
  const title = getChatTitle(chat, currentUserId, currentUser);
  return title
    .split(" ")
    .filter(Boolean)
    .slice(0, 2)
    .map((p) => p[0]?.toUpperCase() || "")
    .join("") || "Ч";
}

function resolveAvatarUrl(url?: string | null): string {
  if (!url) return "";
  if (url.startsWith("data:")) return url;
  if (/^https?:\/\//i.test(url)) return encodeURI(url);
  if (url.startsWith("//")) return encodeURI(`https:${url}`);
  if (url.startsWith("/") && BACKEND_URL) {
    return encodeURI(`${BACKEND_URL.replace(/\/$/, "")}${url}`);
  }
  if (BACKEND_URL) {
    return encodeURI(`${BACKEND_URL.replace(/\/$/, "")}/${url.replace(/^\/+/, "")}`);
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

function getChatSortTimestamp(chat: Chat): number {
  const lastMessage = chat.last_message;

  if (typeof lastMessage?.created_ts === "number") {
    return lastMessage.created_ts;
  }

  const lastCreatedRaw = lastMessage?.created_at || lastMessage?.created;
  if (lastCreatedRaw) {
    const ts = new Date(lastCreatedRaw).getTime();
    if (!Number.isNaN(ts)) return ts;
  }

  const chatCreatedTs = new Date(chat.created_at).getTime();
  return Number.isNaN(chatCreatedTs) ? 0 : chatCreatedTs;
}

function isChatOnline(chat: Chat, currentUserId?: number): boolean {
  const chatKind = chat.chat_type || chat.type;
  if (chatKind !== "direct" && chatKind !== "private") return false;
  const otherParticipant = (chat.participants || [])
    .filter((p): p is Exclude<typeof p, number> => typeof p === "object" && p !== null)
    .find((p) => p.id !== currentUserId);
  return Boolean(otherParticipant?.is_active);
}

export default function MessagesPage() {
  const { user } = useUser();
  const currentUserId = user?.id;
  const currentUserFirstName = user?.first_name;
  const currentUserLastName = user?.last_name;
  const currentUserPatronymic = user?.patronymic;
  const currentUserEmail = user?.email;

  const currentUserForMatch = useMemo(
    () => ({
      first_name: currentUserFirstName,
      last_name: currentUserLastName,
      patronymic: currentUserPatronymic,
      email: currentUserEmail,
    }),
    [currentUserEmail, currentUserFirstName, currentUserLastName, currentUserPatronymic]
  );
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

        // FRONTEND-ONLY: добираем детали чатов, чтобы получить имя/аватар собеседника
        // для private/direct в случае, когда list не отдает avatar/participant_details.
        const needDetails = items.filter((chat: Chat) => {
          const kind = chat.chat_type || chat.type;
          if (kind !== "private" && kind !== "direct") return false;

          const hasOtherAvatar = Boolean(getChatAvatar(chat, currentUserId));
          const resolvedTitle = getChatTitle(chat, currentUserId, currentUserForMatch).trim();
          const hasOtherName = Boolean(resolvedTitle && resolvedTitle.toLowerCase() !== "диалог");
          return !(hasOtherAvatar && hasOtherName);
        });

        if (!needDetails.length) {
          setChats(items);
          return;
        }

        const details = await Promise.all(
          needDetails.map(async (chat: Chat) => {
            try {
              return await apiClient.getChat(chat.id);
            } catch {
              return null;
            }
          })
        );

        const detailsMap = new Map<number, Chat>();
        details.forEach((d) => {
          if (d) detailsMap.set(d.id, d);
        });

        const merged = items.map((chat: Chat) => {
          const detail = detailsMap.get(chat.id);
          if (!detail) return chat;
          return {
            ...chat,
            participants: detail.participants ?? chat.participants,
            participant_details: detail.participant_details ?? chat.participant_details,
            avatar: chat.avatar || detail.avatar,
            name: chat.name || detail.name,
          };
        });

        setChats(merged);
      } catch (e: unknown) {
        console.error("Ошибка загрузки чатов:", e);
        setError("Не удалось загрузить чаты");
      } finally {
        setLoading(false);
      }
    }

    loadChats();
  }, [currentUserForMatch, currentUserId]);

  const filteredChats = useMemo(() => {
    const q = search.trim().toLowerCase();
    const sorted = [...chats].sort((a, b) => getChatSortTimestamp(b) - getChatSortTimestamp(a));

    if (!q) return sorted;

    return sorted.filter((chat: Chat) => {
      const title = getChatTitle(chat, currentUserId, currentUserForMatch).toLowerCase();
      const lastMessage = chat.last_message?.content?.toLowerCase() || "";
      return title.includes(q) || lastMessage.includes(q);
    });
  }, [chats, currentUserForMatch, currentUserId, search]);

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
              filteredChats.map((chat: Chat) => (
                (() => {
                  const chatTitle = getChatTitle(chat, currentUserId, currentUserForMatch);
                  const chatAvatar = getChatAvatar(chat, currentUserId);
                  return (
                <Link
                  key={chat.id}
                  href={`/messages/${chat.id}`}
                  className="block w-full rounded-xl border border-transparent p-3 text-left transition hover:border-gray-200 hover:bg-gray-50"
                >
                  <div className="flex items-start gap-3">
                    <div className="relative h-10 w-10">
                      <div className="flex h-10 w-10 items-center justify-center overflow-hidden rounded-full bg-sky-400 text-xs font-semibold text-white">
                        {chatAvatar ? (
                          <Image
                            src={resolveAvatarUrl(chatAvatar)}
                            alt={chatTitle}
                            width={40}
                            height={40}
                            unoptimized
                            className="h-full w-full object-cover"
                          />
                        ) : (
                          getChatInitials(chat, currentUserId, currentUserForMatch)
                        )}
                      </div>
                      {isChatOnline(chat, user?.id) ? (
                        <span className="absolute -bottom-0.5 -right-0.5 z-10 h-3 w-3 rounded-full bg-sky-400 ring-2 ring-white" />
                      ) : null}
                    </div>
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center justify-between gap-2">
                        <p className="truncate text-sm font-semibold text-gray-900">{chatTitle}</p>
                        <span className="shrink-0 text-xs text-gray-500">{formatTime(chat.last_message?.created_at)}</span>
                      </div>
                      <p className="mt-1 truncate text-xs text-gray-500">
                        {chat.last_message?.content || "Нет сообщений"}
                      </p>
                    </div>
                  </div>
                </Link>
                  );
                })()
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
