"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { AppShell } from "../../components/AppShell";
import { apiClient } from "@/lib/api";
import { resolveMediaUrl } from "@/lib/url";
import { ChatIdentity, getChatAvatar, getChatInitials, getChatTitle } from "@/lib/messages/chatUtils";
import type { Chat } from "@/types/api";
import { Search, MessageCircle, Pin, BellOff, Filter, Plus, X, Users, Globe, Radio, Image as ImageIcon, Megaphone, MessageSquare } from "lucide-react";
import Link from "next/link";
import Image from "next/image";
import { useUser } from "@/contexts/UserContext";
import { useRouter } from "next/navigation";
import { Modal } from "@/components/ui";
import wsManager from "@/lib/websocketManager";

type UnreadFilter = "all" | "unread" | "read";
type PinnedFilter = "all" | "pinned" | "unpinned";
type CreateChatPayload = {
  type: string;
  name: string;
  description?: string;
  avatar?: File;
};

type RealtimeChatEvent = {
  type: "notification" | "list_update" | "message_edited" | string;
  chat_id?: number;
  notification?: {
    verb?: string;
  } | null;
};

const chatTypeOptions = [
  { key: "all", label: "Все" },
  { key: "global", label: "Глобальный" },
  { key: "channel", label: "Каналы" },
  { key: "private", label: "Личные" },
  { key: "group", label: "Группы" },
  { key: "announcement", label: "Объявления" },
] as const;

function getChatTypeIcon(chat: Chat) {
  const chatType = chat.chat_type || chat.type;
  switch (chatType) {
    case 'global':
      return <Globe size={10} className="text-white" />;
    case 'channel':
      return <Radio size={10} className="text-white" />;
    case 'group':
      return <Users size={10} className="text-white" />;
    case 'private':
    case 'direct':
      return <MessageCircle size={10} className="text-white" />;
    case 'announcement':
      return <Megaphone size={10} className="text-white" />;
    case 'comments':
      return <MessageSquare size={10} className="text-white" />;
    default:
      return null;
  }
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

export default function MessagesPage() {
  const { user } = useUser();
  const router = useRouter();
  const currentUserId = user?.id;
  const currentUserFirstName = user?.first_name;
  const currentUserLastName = user?.last_name;
  const currentUserPatronymic = user?.patronymic;
  const currentUserEmail = user?.email;

  const currentUserForMatch = useMemo<ChatIdentity>(
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
  const [filterUnread, setFilterUnread] = useState<UnreadFilter>('all');
  const [filterPinned, setFilterPinned] = useState<PinnedFilter>('all');
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
  const refreshAllChatsInFlightRef = useRef(false);
  const refreshChatInFlightRef = useRef<Set<number>>(new Set());
  const hasCompletedInitialLoadRef = useRef(false);
  const wasWsConnectedRef = useRef(false);

  const loadChats = useCallback(async (options?: { showLoader?: boolean }) => {
    if (refreshAllChatsInFlightRef.current) {
      return;
    }

    const showLoader = options?.showLoader ?? true;
    refreshAllChatsInFlightRef.current = true;

    try {
      if (showLoader) {
        setLoading(true);
      }
      setError(null);
      const items = await apiClient.getAllChats();
      setChats(items);
      hasCompletedInitialLoadRef.current = true;
    } catch (e: unknown) {
      console.error("Ошибка загрузки чатов:", e);
      setError("Не удалось загрузить чаты");
    } finally {
      refreshAllChatsInFlightRef.current = false;
      if (showLoader) {
        setLoading(false);
      }
    }
  }, []);

  const refreshChat = useCallback(async (chatId: number) => {
    if (!Number.isFinite(chatId) || chatId <= 0) {
      return;
    }

    if (refreshAllChatsInFlightRef.current || refreshChatInFlightRef.current.has(chatId)) {
      return;
    }

    refreshChatInFlightRef.current.add(chatId);

    try {
      const chat = await apiClient.getChat(chatId);
      setChats((prev) => {
        const existingIndex = prev.findIndex((item) => item.id === chatId);
        if (existingIndex === -1) {
          return [chat, ...prev];
        }

        const next = [...prev];
        next[existingIndex] = {
          ...prev[existingIndex],
          ...chat,
        };
        return next;
      });
    } catch (e) {
      console.warn(`Не удалось точечно обновить чат ${chatId}, перегружаю список`, e);
      await loadChats({ showLoader: false });
    } finally {
      refreshChatInFlightRef.current.delete(chatId);
    }
  }, [loadChats]);

  useEffect(() => {
    void loadChats();
  }, [loadChats]);

  useEffect(() => {
    if (typeof window === "undefined" || !localStorage.getItem("access_token")) {
      return;
    }

    const unsubscribeMessages = wsManager.subscribe((event) => {
      const data = event as RealtimeChatEvent;

      if ((data.type === "list_update" || data.type === "message_edited") && typeof data.chat_id === "number") {
        void refreshChat(data.chat_id);
        return;
      }

      if (data.type !== "notification" || !data.notification) {
        return;
      }

      if (data.notification.verb === "chat_added_to_chat") {
        void loadChats({ showLoader: false });
        return;
      }
    });

    const unsubscribeStatus = wsManager.subscribeStatus((status) => {
      if (status.isConnected && !wasWsConnectedRef.current && hasCompletedInitialLoadRef.current) {
        void loadChats({ showLoader: false });
      }
      wasWsConnectedRef.current = status.isConnected;
    });

    return () => {
      unsubscribeMessages();
      unsubscribeStatus();
    };
  }, [loadChats, refreshChat]);

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
      const chatData: CreateChatPayload = {
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
        <div className="app-surface rounded-2xl p-8 text-center">
          <div className="mb-4 inline-block h-8 w-8 animate-spin rounded-full border-4 border-sky-400 border-t-transparent" />
          <p className="app-text-muted text-sm">Загрузка чатов...</p>
        </div>
      ) : error ? (
        <div className="rounded-2xl border border-red-500/20 bg-red-500/10 p-6 text-center">
          <p className="text-sm text-red-800">{error}</p>
        </div>
      ) : (
        <section className="app-surface rounded-2xl p-4">
          <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
            <p className="app-text-muted text-sm font-semibold uppercase tracking-wide">Сообщения</p>
            <button
              type="button"
              onClick={() => setShowCreateModal(true)}
              className="app-action-primary inline-flex items-center gap-1 rounded-lg px-3 py-2 text-sm font-medium transition"
            >
              <Plus size={14} /> Создать чат
            </button>
          </div>

          {/* Поиск и кнопка фильтров */}
          <div className="mb-4 flex gap-2">
            <div className="relative flex-1">
              <Search size={16} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 app-text-muted" />
              <input
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Поиск по чатам"
                className="app-input w-full rounded-lg py-2.5 pl-9 pr-3 text-sm"
              />
            </div>
            <button
              type="button"
              onClick={() => setFiltersOpen((v) => !v)}
              className={`relative inline-flex items-center justify-center rounded-lg p-2.5 transition ${
                filtersOpen
                  ? "app-selected app-accent-text"
                  : "app-surface-muted app-text-muted hover:bg-[var(--surface-tertiary)]"
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
            <div className="app-surface-muted mb-4 flex flex-col gap-2 rounded-xl p-3">
              <select
                value={filterUnread}
                onChange={(e) => setFilterUnread(e.target.value as UnreadFilter)}
                className="app-select rounded-lg px-3 py-2 text-sm"
              >
                <option value="all">Все чаты</option>
                <option value="unread">Только с непрочитанными</option>
                <option value="read">Только прочитанные</option>
              </select>

              <select
                value={filterPinned}
                onChange={(e) => setFilterPinned(e.target.value as PinnedFilter)}
                className="app-select rounded-lg px-3 py-2 text-sm"
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
                  className="app-surface-elevated rounded-lg px-3 py-2 text-sm font-medium text-[var(--muted-foreground)] transition hover:bg-[var(--surface-secondary)]"
                >
                  Очистить фильтры
                </button>
              )}
            </div>
          )}

          {/* Фильтры по типу чата с бэйджами */}
          <div className="mb-4 flex flex-wrap gap-2">
            {chatTypeOptions
              .filter(({ key }) => key === "all" || (chatTypeCounts[key]?.total ?? 0) > 0)
              .map(({ key, label }) => {
                const counts = chatTypeCounts[key];
                const active = chatTypeFilter === key;

                return (
                  <button
                    key={key}
                    onClick={() => setChatTypeFilter(key)}
                    className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1.5 text-xs font-medium transition ${
                      active ? "app-pill-active" : "app-pill"
                    }`}
                  >
                    <span>{label}</span>
                    <span className={`app-badge inline-flex items-center gap-1 px-1.5 py-0.5 text-[10px] font-bold ${
                      active ? "app-pill-count-active" : "app-pill-count"
                    }`}>
                      <span>{counts.total}</span>
                      {counts.unread > 0 ? (
                        <>
                          <span className="app-text-muted">•</span>
                          <span className="app-accent-text">{counts.unread}</span>
                        </>
                      ) : null}
                    </span>
                  </button>
                );
              })}
          </div>

          <div className="space-y-2">
            {filteredChats.length === 0 ? (
              <div className="app-surface-muted rounded-xl p-6 text-center">
                <p className="app-text-muted text-sm">Чаты не найдены</p>
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
                  className={`block w-full rounded-xl border p-3 text-left transition ${
                    (chat.unread_count ?? 0) > 0
                      ? "app-selected"
                      : "border-transparent hover:border-[var(--border-subtle)] hover:bg-[var(--surface-secondary)]"
                  }`}
                >
                  <div className="flex items-start gap-3">
                    <div className="relative h-10 w-10">
                      <div className="app-avatar-fallback flex h-10 w-10 items-center justify-center overflow-hidden rounded-full text-xs font-semibold">
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
                      {/* Иконка типа чата */}
                      <span className="absolute -bottom-0.5 -left-0.5 z-10 flex h-4 w-4 items-center justify-center rounded-full bg-sky-600 ring-2 ring-white">
                        {getChatTypeIcon(chat)}
                      </span>
                      {/* Счетчик непрочитанных */}
                      {(chat.unread_count ?? 0) > 0 ? (
                        <span className="absolute -top-1 -right-1 z-10 flex h-5 min-w-[20px] items-center justify-center rounded-full bg-red-500 px-1.5 text-[10px] font-bold text-white ring-2 ring-white">
                          {chat.unread_count! > 99 ? '99+' : chat.unread_count}
                        </span>
                      ) : null}
                    </div>
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center justify-between gap-2">
                        <div className="flex items-center gap-1.5 min-w-0">
                          <p className={`truncate text-sm text-[var(--foreground)] ${
                            (chat.unread_count ?? 0) > 0 ? "font-bold" : "font-semibold"
                          }`}>{chatTitle}</p>
                          {chat.is_pinned ? (
                            <Pin size={12} className="app-accent-text shrink-0 fill-current" />
                          ) : null}
                          {chat.notifications_enabled === false ? (
                            <BellOff size={12} className="app-text-muted shrink-0" />
                          ) : null}
                        </div>
                        <span className="app-text-muted shrink-0 text-xs">{formatTime(chat.last_message?.created_at)}</span>
                      </div>
                      <p className={`mt-1 truncate text-xs ${
                        (chat.unread_count ?? 0) > 0 ? "font-medium text-[var(--foreground)]" : "app-text-muted"
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
            <div className="app-surface-muted mt-4 flex min-h-[120px] items-center justify-center rounded-xl text-center">
              <div>
                <MessageCircle size={20} className="app-text-muted mx-auto mb-2" />
                <p className="app-text-muted text-sm">Создайте или найдите диалог</p>
              </div>
            </div>
          ) : null}
        </section>
      )}
      
      {/* Модальное окно создания чата */}
      <Modal isOpen={showCreateModal} onClose={() => setShowCreateModal(false)} title="Создать чат" size="sm" closeOnEsc={!creating} footer={
            <div className="flex gap-2">
                <button
                  type="button"
                  onClick={() => setShowCreateModal(false)}
                  className="app-action-secondary flex-1 rounded-lg px-4 py-2 text-sm font-medium transition"
                >
                  Отмена
                </button>
                <button
                  type="button"
                  onClick={handleCreateChat}
                  disabled={creating}
                  className="app-action-primary flex-1 rounded-lg px-4 py-2 text-sm font-medium transition disabled:opacity-50"
                >
                  {creating ? 'Создание...' : 'Создать'}
                </button>
            </div>
      }>
            <div className="space-y-4">
              {/* Тип чата */}
              <div>
                <label className="mb-2 block text-sm font-medium text-[var(--foreground)]">
                  Тип чата
                </label>
                <div className="flex gap-2">
                  <button
                    type="button"
                    onClick={() => setNewChatType('group')}
                    className={`flex flex-1 items-center justify-center gap-2 rounded-lg p-3 transition ${
                      newChatType === 'group'
                        ? 'app-selected'
                        : 'app-action-secondary'
                    }`}
                  >
                    <Users size={18} />
                    <span className="text-sm font-medium">Групповой</span>
                  </button>
                  <button
                    type="button"
                    onClick={() => setNewChatType('channel')}
                    className={`flex flex-1 items-center justify-center gap-2 rounded-lg p-3 transition ${
                      newChatType === 'channel'
                        ? 'app-selected'
                        : 'app-action-secondary'
                    }`}
                  >
                    <Radio size={18} />
                    <span className="text-sm font-medium">Канал</span>
                  </button>
                  <button
                    type="button"
                    onClick={() => setNewChatType('global')}
                    className={`flex flex-1 items-center justify-center gap-2 rounded-lg p-3 transition ${
                      newChatType === 'global'
                        ? 'app-selected'
                        : 'app-action-secondary'
                    }`}
                  >
                    <Globe size={18} />
                    <span className="text-sm font-medium">Глобальный</span>
                  </button>
                </div>
              </div>

              {/* Название и описание */}
              <div>
                <label className="mb-2 block text-sm font-medium text-[var(--foreground)]">
                  Название *
                </label>
                <input
                  type="text"
                  value={newChatName}
                  onChange={(e) => setNewChatName(e.target.value)}
                  placeholder="Введите название чата..."
                  className="app-input w-full rounded-lg px-3 py-2 text-sm"
                />
              </div>
              <div>
                <label className="mb-2 block text-sm font-medium text-[var(--foreground)]">
                  Описание (необязательно)
                </label>
                <textarea
                  value={newChatDescription}
                  onChange={(e) => setNewChatDescription(e.target.value)}
                  placeholder="Краткое описание чата..."
                  rows={3}
                  className="app-input w-full rounded-lg px-3 py-2 text-sm"
                />
              </div>

              {/* Аватар */}
              <div>
                <label className="mb-2 block text-sm font-medium text-[var(--foreground)]">
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
                      <p className="app-text-muted mb-2 text-sm">{newChatAvatar?.name}</p>
                      <button
                        type="button"
                        onClick={handleRemoveAvatar}
                        className="app-action-danger inline-flex items-center gap-1 rounded-lg px-3 py-1.5 text-sm font-medium transition"
                      >
                        <X size={14} />
                        Удалить
                      </button>
                    </div>
                  </div>
                ) : (
                  <label className="flex cursor-pointer flex-col items-center justify-center rounded-lg border-2 border-dashed border-[var(--border-strong)] bg-[var(--surface-secondary)] p-6 transition hover:border-[color:color-mix(in_srgb,var(--accent-primary)_30%,var(--border-strong))] hover:bg-[var(--accent-soft)]">
                    <input
                      type="file"
                      accept="image/*"
                      onChange={handleAvatarChange}
                      className="hidden"
                    />
                    <div className="flex flex-col items-center gap-2">
                      <div className="rounded-full bg-[var(--accent-soft)] p-3">
                        <ImageIcon size={24} className="app-accent-text" />
                      </div>
                      <div className="text-center">
                        <p className="text-sm font-medium text-[var(--foreground)]">
                          Загрузить изображение
                        </p>
                        <p className="app-text-muted mt-1 text-xs">
                          PNG, JPG до 5MB
                        </p>
                      </div>
                    </div>
                  </label>
                )}
              </div>
            </div>
      </Modal>
    </AppShell>
  );
}
