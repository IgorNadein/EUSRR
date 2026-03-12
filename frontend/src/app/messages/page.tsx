"use client";

import { useEffect, useMemo, useState } from "react";
import { AppShell } from "../../components/AppShell";
import { apiClient } from "@/lib/api";
import { resolveMediaUrl } from "@/lib/url";
import type { Chat } from "@/types/api";
import { Search, MessageCircle, Pin, BellOff, Filter, Plus, X, Users, Globe, Radio, Upload, Image as ImageIcon } from "lucide-react";
import Link from "next/link";
import Image from "next/image";
import { useUser } from "@/contexts/UserContext";
import { useRouter } from "next/navigation";

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
  const router = useRouter();
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
  const [chatTypeFilter, setChatTypeFilter] = useState<string>("all");
  const [filterUnread, setFilterUnread] = useState<'all' | 'unread' | 'read'>('all');
  const [filterPinned, setFilterPinned] = useState<'all' | 'pinned' | 'unpinned'>('all');
  const [filtersOpen, setFiltersOpen] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  
  // Состояния для создания чата
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [newChatType, setNewChatType] = useState<'group' | 'channel' | 'global'>('group');
  const [newChatName, setNewChatName] = useState("");
  const [newChatDescription, setNewChatDescription] = useState("");
  const [newChatAvatar, setNewChatAvatar] = useState<File | null>(null);
  const [avatarPreview, setAvatarPreview] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);

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
    
    // Сортировка: закрепленные сверху, потом по времени последнего сообщения
    const sorted = [...chats].sort((a, b) => {
      // Сначала сортируем по закрепленности
      const aPinned = a.is_pinned ? 1 : 0;
      const bPinned = b.is_pinned ? 1 : 0;
      if (aPinned !== bPinned) return bPinned - aPinned;
      
      // Затем по времени последнего сообщения
      return getChatSortTimestamp(b) - getChatSortTimestamp(a);
    });

    // Фильтруем по типу и поисковому запросу
    return sorted.filter((chat: Chat) => {
      // Фильтр по типу чата
      if (chatTypeFilter !== "all") {
        const chatType = chat.chat_type || chat.type;
        if (chatType !== chatTypeFilter) return false;
      }

      // Фильтр по прочитанности
      if (filterUnread === 'unread' && (chat.unread_count || 0) === 0) return false;
      if (filterUnread === 'read' && (chat.unread_count || 0) > 0) return false;

      // Фильтр по закрепленности
      if (filterPinned === 'pinned' && !chat.is_pinned) return false;
      if (filterPinned === 'unpinned' && chat.is_pinned) return false;

      // Фильтр по поисковому запросу
      if (q) {
        const title = getChatTitle(chat, currentUserId, currentUserForMatch).toLowerCase();
        const lastMessage = chat.last_message?.content?.toLowerCase() || "";
        if (!title.includes(q) && !lastMessage.includes(q)) return false;
      }

      return true;
    });
  }, [chats, currentUserForMatch, currentUserId, search, chatTypeFilter, filterUnread, filterPinned]);

  // Подсчет чатов по типам
  const chatTypeCounts = useMemo(() => {
    const counts: Record<string, { total: number; unread: number }> = {
      all: { total: chats.length, unread: 0 },
      global: { total: 0, unread: 0 },
      channel: { total: 0, unread: 0 },
      private: { total: 0, unread: 0 },
      group: { total: 0, unread: 0 },
      announcement: { total: 0, unread: 0 },
    };

    chats.forEach((chat: Chat) => {
      const chatType = chat.chat_type || chat.type;
      const unreadCount = chat.unread_count || 0;

      if (unreadCount > 0) {
        counts.all.unread += unreadCount;
      }

      if (chatType && counts[chatType] !== undefined) {
        counts[chatType].total++;
        if (unreadCount > 0) {
          counts[chatType].unread += unreadCount;
        }
      }
    });

    return counts;
  }, [chats]);

  const handleCreateChat = async () => {
    if (creating) return;
    
    // Валидация: все типы кроме comments требуют название
    if (!newChatName.trim()) {
      alert('Введите название чата');
      return;
    }
    
    setCreating(true);
    try {
      const chatData: any = {
        type: newChatType,
        name: newChatName.trim(),
      };
      
      if (newChatDescription.trim()) {
        chatData.description = newChatDescription.trim();
      }
      
      if (newChatAvatar) {
        chatData.avatar = newChatAvatar;
      }
      
      const newChat = await apiClient.createChat(chatData);
      
      // Закрываем модалку и сбрасываем форму
      setShowCreateModal(false);
      setNewChatType('group');
      setNewChatName('');
      setNewChatDescription('');
      setNewChatAvatar(null);
      setAvatarPreview(null);
      
      // Перенаправляем на страницу настроек созданного чата
      router.push(`/messages/${newChat.id}/settings`);
    } catch (e: unknown) {
      console.error('Ошибка создания чата:', e);
      const errorMessage = e instanceof Error ? e.message : String(e);
      alert(`Не удалось создать чат: ${errorMessage}`);
    } finally {
      setCreating(false);
    }
  };

  const handleAvatarChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      if (file.size > 5 * 1024 * 1024) { // 5MB
        alert('Файл слишком большой. Максимум 5MB');
        return;
      }
      if (!file.type.startsWith('image/')) {
        alert('Можно загружать только изображения');
        return;
      }
      setNewChatAvatar(file);
      
      // Создаем превью
      const reader = new FileReader();
      reader.onloadend = () => {
        setAvatarPreview(reader.result as string);
      };
      reader.readAsDataURL(file);
    }
  };

  const handleRemoveAvatar = () => {
    setNewChatAvatar(null);
    setAvatarPreview(null);
  };

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
          {/* Поиск и кнопка фильтров */}
          <div className="mb-4 flex gap-2">
            <div className="relative flex-1">
              <Search size={16} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
              <input
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Поиск по чатам"
                className="w-full rounded-lg border border-gray-200 bg-gray-50 py-2.5 pl-9 pr-3 text-sm text-gray-800 transition focus:border-sky-500 focus:bg-white focus:outline-none focus:ring-2 focus:ring-sky-100"
              />
            </div>
            <button
              type="button"
              onClick={() => setShowCreateModal(true)}
              className="inline-flex items-center justify-center rounded-lg border border-sky-200 bg-sky-500 p-2.5 text-white transition hover:bg-sky-600"
              title="Создать чат"
            >
              <Plus size={16} />
            </button>
            <button
              type="button"
              onClick={() => setFiltersOpen((v) => !v)}
              className={`relative inline-flex items-center justify-center rounded-lg border p-2.5 transition ${
                filtersOpen
                  ? "border-sky-400 bg-sky-50 text-sky-600"
                  : "border-gray-200 bg-gray-50 text-gray-500 hover:bg-gray-100"
              }`}
            >
              <Filter size={16} />
              {(filterUnread !== 'all' || filterPinned !== 'all') && (
                <span className="absolute -right-1 -top-1 flex h-4 min-w-4 items-center justify-center rounded-full bg-sky-500 px-1 text-[10px] font-bold text-white">
                  {[filterUnread !== 'all', filterPinned !== 'all'].filter(Boolean).length}
                </span>
              )}
            </button>
          </div>

          {/* Панель дополнительных фильтров */}
          {filtersOpen && (
            <div className="mb-4 flex flex-col gap-2 rounded-xl border border-gray-200 bg-gray-50 p-3">
              <select
                value={filterUnread}
                onChange={(e) => setFilterUnread(e.target.value as any)}
                className="rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm text-gray-800"
              >
                <option value="all">Все чаты</option>
                <option value="unread">Только с непрочитанными</option>
                <option value="read">Только прочитанные</option>
              </select>

              <select
                value={filterPinned}
                onChange={(e) => setFilterPinned(e.target.value as any)}
                className="rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm text-gray-800"
              >
                <option value="all">Все чаты</option>
                <option value="pinned">Только закрепленные</option>
                <option value="unpinned">Только незакрепленные</option>
              </select>

              {(filterUnread !== 'all' || filterPinned !== 'all') && (
                <button
                  type="button"
                  onClick={() => {
                    setFilterUnread('all');
                    setFilterPinned('all');
                  }}
                  className="rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm font-medium text-gray-600 hover:bg-gray-100 transition"
                >
                  Очистить фильтры
                </button>
              )}
            </div>
          )}

          {/* Фильтры по типу чата с бэйджами */}
          <div className="mb-4 flex flex-wrap gap-2">
            <button
              onClick={() => setChatTypeFilter("all")}
              className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1.5 text-xs font-medium transition ${
                chatTypeFilter === "all"
                  ? "bg-sky-600 text-white"
                  : "bg-gray-100 text-gray-700 hover:bg-gray-200"
              }`}
            >
              <span>Все</span>
              <span className={`inline-flex items-center gap-1 rounded-full px-1.5 py-0.5 text-[10px] font-bold ${
                chatTypeFilter === "all"
                  ? "bg-sky-500 text-white"
                  : "bg-gray-200 text-gray-600"
              }`}>
                <span>{chatTypeCounts.all.total}</span>
                {chatTypeCounts.all.unread > 0 && (
                  <>
                    <span className={chatTypeFilter === "all" ? "text-sky-300" : "text-gray-400"}>•</span>
                    <span className={chatTypeFilter === "all" ? "text-sky-100" : "text-sky-600"}>
                      {chatTypeCounts.all.unread}
                    </span>
                  </>
                )}
              </span>
            </button>

            {chatTypeCounts.global.total > 0 && (
              <button
                onClick={() => setChatTypeFilter("global")}
                className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1.5 text-xs font-medium transition ${
                  chatTypeFilter === "global"
                    ? "bg-sky-600 text-white"
                    : "bg-gray-100 text-gray-700 hover:bg-gray-200"
                }`}
              >
                <span>Глобальный</span>
                <span className={`inline-flex items-center gap-1 rounded-full px-1.5 py-0.5 text-[10px] font-bold ${
                  chatTypeFilter === "global"
                    ? "bg-sky-500 text-white"
                    : "bg-gray-200 text-gray-600"
                }`}>
                  <span>{chatTypeCounts.global.total}</span>
                  {chatTypeCounts.global.unread > 0 && (
                    <>
                      <span className={chatTypeFilter === "global" ? "text-sky-300" : "text-gray-400"}>•</span>
                      <span className={chatTypeFilter === "global" ? "text-sky-100" : "text-sky-600"}>
                        {chatTypeCounts.global.unread}
                      </span>
                    </>
                  )}
                </span>
              </button>
            )}

            {chatTypeCounts.channel.total > 0 && (
              <button
                onClick={() => setChatTypeFilter("channel")}
                className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1.5 text-xs font-medium transition ${
                  chatTypeFilter === "channel"
                    ? "bg-sky-600 text-white"
                    : "bg-gray-100 text-gray-700 hover:bg-gray-200"
                }`}
              >
                <span>Каналы</span>
                <span className={`inline-flex items-center gap-1 rounded-full px-1.5 py-0.5 text-[10px] font-bold ${
                  chatTypeFilter === "channel"
                    ? "bg-sky-500 text-white"
                    : "bg-gray-200 text-gray-600"
                }`}>
                  <span>{chatTypeCounts.channel.total}</span>
                  {chatTypeCounts.channel.unread > 0 && (
                    <>
                      <span className={chatTypeFilter === "channel" ? "text-sky-300" : "text-gray-400"}>•</span>
                      <span className={chatTypeFilter === "channel" ? "text-sky-100" : "text-sky-600"}>
                        {chatTypeCounts.channel.unread}
                      </span>
                    </>
                  )}
                </span>
              </button>
            )}

            {chatTypeCounts.private.total > 0 && (
              <button
                onClick={() => setChatTypeFilter("private")}
                className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1.5 text-xs font-medium transition ${
                  chatTypeFilter === "private"
                    ? "bg-sky-600 text-white"
                    : "bg-gray-100 text-gray-700 hover:bg-gray-200"
                }`}
              >
                <span>Личные</span>
                <span className={`inline-flex items-center gap-1 rounded-full px-1.5 py-0.5 text-[10px] font-bold ${
                  chatTypeFilter === "private"
                    ? "bg-sky-500 text-white"
                    : "bg-gray-200 text-gray-600"
                }`}>
                  <span>{chatTypeCounts.private.total}</span>
                  {chatTypeCounts.private.unread > 0 && (
                    <>
                      <span className={chatTypeFilter === "private" ? "text-sky-300" : "text-gray-400"}>•</span>
                      <span className={chatTypeFilter === "private" ? "text-sky-100" : "text-sky-600"}>
                        {chatTypeCounts.private.unread}
                      </span>
                    </>
                  )}
                </span>
              </button>
            )}

            {chatTypeCounts.group.total > 0 && (
              <button
                onClick={() => setChatTypeFilter("group")}
                className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1.5 text-xs font-medium transition ${
                  chatTypeFilter === "group"
                    ? "bg-sky-600 text-white"
                    : "bg-gray-100 text-gray-700 hover:bg-gray-200"
                }`}
              >
                <span>Группы</span>
                <span className={`inline-flex items-center gap-1 rounded-full px-1.5 py-0.5 text-[10px] font-bold ${
                  chatTypeFilter === "group"
                    ? "bg-sky-500 text-white"
                    : "bg-gray-200 text-gray-600"
                }`}>
                  <span>{chatTypeCounts.group.total}</span>
                  {chatTypeCounts.group.unread > 0 && (
                    <>
                      <span className={chatTypeFilter === "group" ? "text-sky-300" : "text-gray-400"}>•</span>
                      <span className={chatTypeFilter === "group" ? "text-sky-100" : "text-sky-600"}>
                        {chatTypeCounts.group.unread}
                      </span>
                    </>
                  )}
                </span>
              </button>
            )}

            {chatTypeCounts.announcement.total > 0 && (
              <button
                onClick={() => setChatTypeFilter("announcement")}
                className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1.5 text-xs font-medium transition ${
                  chatTypeFilter === "announcement"
                    ? "bg-sky-600 text-white"
                    : "bg-gray-100 text-gray-700 hover:bg-gray-200"
                }`}
              >
                <span>Объявления</span>
                <span className={`inline-flex items-center gap-1 rounded-full px-1.5 py-0.5 text-[10px] font-bold ${
                  chatTypeFilter === "announcement"
                    ? "bg-sky-500 text-white"
                    : "bg-gray-200 text-gray-600"
                }`}>
                  <span>{chatTypeCounts.announcement.total}</span>
                  {chatTypeCounts.announcement.unread > 0 && (
                    <>
                      <span className={chatTypeFilter === "announcement" ? "text-sky-300" : "text-gray-400"}>•</span>
                      <span className={chatTypeFilter === "announcement" ? "text-sky-100" : "text-sky-600"}>
                        {chatTypeCounts.announcement.unread}
                      </span>
                    </>
                  )}
                </span>
              </button>
            )}
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
                  className={`block w-full rounded-xl border p-3 text-left transition hover:border-gray-300 hover:bg-gray-50 ${
                    (chat.unread_count ?? 0) > 0
                      ? "border-sky-100 bg-sky-50/30"
                      : "border-transparent"
                  }`}
                >
                  <div className="flex items-start gap-3">
                    <div className="relative h-10 w-10">
                      <div className="flex h-10 w-10 items-center justify-center overflow-hidden rounded-full bg-sky-400 text-xs font-semibold text-white">
                        {chatAvatar ? (
                          <Image
                            src={resolveMediaUrl(chatAvatar)}
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
                      {(chat.unread_count ?? 0) > 0 ? (
                        <span className="absolute -top-1 -right-1 z-10 flex h-5 min-w-[20px] items-center justify-center rounded-full bg-red-500 px-1.5 text-[10px] font-bold text-white ring-2 ring-white">
                          {chat.unread_count! > 99 ? '99+' : chat.unread_count}
                        </span>
                      ) : null}
                    </div>
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center justify-between gap-2">
                        <div className="flex items-center gap-1.5 min-w-0">
                          <p className={`truncate text-sm ${
                            (chat.unread_count ?? 0) > 0 ? "font-bold text-gray-900" : "font-semibold text-gray-900"
                          }`}>{chatTitle}</p>
                          {chat.is_pinned ? (
                            <Pin size={12} className="shrink-0 text-sky-600 fill-current" />
                          ) : null}
                          {chat.notifications_enabled === false ? (
                            <BellOff size={12} className="shrink-0 text-gray-400" />
                          ) : null}
                        </div>
                        <span className="shrink-0 text-xs text-gray-500">{formatTime(chat.last_message?.created_at)}</span>
                      </div>
                      <p className={`mt-1 truncate text-xs ${
                        (chat.unread_count ?? 0) > 0 ? "font-medium text-gray-700" : "text-gray-500"
                      }`}>
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
      
      {/* Модальное окно создания чата */}
      {showCreateModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
          <div className="w-full max-w-md rounded-2xl bg-white p-6 shadow-xl">
            <div className="mb-4 flex items-center justify-between">
              <h2 className="text-lg font-bold text-gray-900">Создать чат</h2>
              <button
                onClick={() => setShowCreateModal(false)}
                className="rounded-lg p-1 text-gray-400 transition hover:bg-gray-100 hover:text-gray-600"
              >
                <X size={20} />
              </button>
            </div>

            <div className="space-y-4">
              {/* Тип чата */}
              <div>
                <label className="mb-2 block text-sm font-medium text-gray-700">
                  Тип чата
                </label>
                <div className="flex gap-2">
                  <button
                    type="button"
                    onClick={() => setNewChatType('group')}
                    className={`flex flex-1 items-center justify-center gap-2 rounded-lg border p-3 transition ${
                      newChatType === 'group'
                        ? 'border-sky-500 bg-sky-50 text-sky-700'
                        : 'border-gray-200 bg-white text-gray-700 hover:bg-gray-50'
                    }`}
                  >
                    <Users size={18} />
                    <span className="text-sm font-medium">Групповой</span>
                  </button>
                  <button
                    type="button"
                    onClick={() => setNewChatType('channel')}
                    className={`flex flex-1 items-center justify-center gap-2 rounded-lg border p-3 transition ${
                      newChatType === 'channel'
                        ? 'border-sky-500 bg-sky-50 text-sky-700'
                        : 'border-gray-200 bg-white text-gray-700 hover:bg-gray-50'
                    }`}
                  >
                    <Radio size={18} />
                    <span className="text-sm font-medium">Канал</span>
                  </button>
                  <button
                    type="button"
                    onClick={() => setNewChatType('global')}
                    className={`flex flex-1 items-center justify-center gap-2 rounded-lg border p-3 transition ${
                      newChatType === 'global'
                        ? 'border-sky-500 bg-sky-50 text-sky-700'
                        : 'border-gray-200 bg-white text-gray-700 hover:bg-gray-50'
                    }`}
                  >
                    <Globe size={18} />
                    <span className="text-sm font-medium">Глобальный</span>
                  </button>
                </div>
              </div>

              {/* Название и описание */}
              <div>
                <label className="mb-2 block text-sm font-medium text-gray-700">
                  Название *
                </label>
                <input
                  type="text"
                  value={newChatName}
                  onChange={(e) => setNewChatName(e.target.value)}
                  placeholder="Введите название чата..."
                  className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-sky-500 focus:outline-none focus:ring-2 focus:ring-sky-100"
                />
              </div>
              <div>
                <label className="mb-2 block text-sm font-medium text-gray-700">
                  Описание (необязательно)
                </label>
                <textarea
                  value={newChatDescription}
                  onChange={(e) => setNewChatDescription(e.target.value)}
                  placeholder="Краткое описание чата..."
                  rows={3}
                  className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-sky-500 focus:outline-none focus:ring-2 focus:ring-sky-100"
                />
              </div>

              {/* Аватар */}
              <div>
                <label className="mb-2 block text-sm font-medium text-gray-700">
                  Аватар (необязательно)
                </label>
                {avatarPreview ? (
                  <div className="flex items-center gap-3">
                    <div className="relative h-20 w-20">
                      <Image
                        src={avatarPreview}
                        alt="Preview"
                        width={80}
                        height={80}
                        className="h-20 w-20 rounded-full object-cover"
                        unoptimized
                      />
                    </div>
                    <div className="flex-1">
                      <p className="text-sm text-gray-600 mb-2">{newChatAvatar?.name}</p>
                      <button
                        type="button"
                        onClick={handleRemoveAvatar}
                        className="inline-flex items-center gap-1 rounded-lg border border-red-200 bg-red-50 px-3 py-1.5 text-sm font-medium text-red-700 transition hover:bg-red-100"
                      >
                        <X size={14} />
                        Удалить
                      </button>
                    </div>
                  </div>
                ) : (
                  <label className="flex cursor-pointer flex-col items-center justify-center rounded-lg border-2 border-dashed border-gray-300 bg-gray-50 p-6 transition hover:border-sky-400 hover:bg-sky-50">
                    <input
                      type="file"
                      accept="image/*"
                      onChange={handleAvatarChange}
                      className="hidden"
                    />
                    <div className="flex flex-col items-center gap-2">
                      <div className="rounded-full bg-sky-100 p-3">
                        <ImageIcon size={24} className="text-sky-600" />
                      </div>
                      <div className="text-center">
                        <p className="text-sm font-medium text-gray-700">
                          Загрузить изображение
                        </p>
                        <p className="text-xs text-gray-500 mt-1">
                          PNG, JPG до 5MB
                        </p>
                      </div>
                    </div>
                  </label>
                )}
              </div>

              {/* Кнопки */}
              <div className="flex gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setShowCreateModal(false)}
                  className="flex-1 rounded-lg border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-gray-700 transition hover:bg-gray-50"
                >
                  Отмена
                </button>
                <button
                  type="button"
                  onClick={handleCreateChat}
                  disabled={creating}
                  className="flex-1 rounded-lg bg-sky-500 px-4 py-2 text-sm font-medium text-white transition hover:bg-sky-600 disabled:opacity-50"
                >
                  {creating ? 'Создание...' : 'Создать'}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </AppShell>
  );
}
