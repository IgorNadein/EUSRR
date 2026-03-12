"use client";

import React, { useEffect, useLayoutEffect, useMemo, useRef, useState, useCallback } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { MessageCircle, Send, ArrowLeft, Paperclip, X, FileText, ChevronRight, ChevronDown, Reply, Pencil, Trash2, Smile, Pin, Bell, BellOff } from "lucide-react";
import { AppShell } from "../../../components/AppShell";
import { apiClient } from "@/lib/api";
import type { Chat, Message, MessageAttachment } from "@/types/api";
import { useUser } from "@/contexts/UserContext";
import { useWebSocket } from "@/hooks/useWebSocket";
import ScrollableMessageList, { ScrollableMessageListInner } from "@/components/ScrollableMessageList";
import { resolveMediaUrl } from "@/lib/url";

function getUserFullName(lastName?: string, firstName?: string): string {
  return `${lastName || ""} ${firstName || ""}`.trim();
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

function getChatTitle(chat: Chat, currentUserId?: number): string {
  const chatKind = chat.chat_type || chat.type;
  const rawName = (chat.name || "").trim();

  if (chatKind === "direct" || chatKind === "private" || !rawName || rawName.toLowerCase() === "диалог") {
    if (chat.interlocutor?.name?.trim()) {
      return chat.interlocutor.name.trim();
    }

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
  }

  return rawName || "Диалог";
}

function getChatAvatar(chat: Chat, currentUserId?: number): string {
  const chatKind = chat.chat_type || chat.type;
  if (chatKind === "direct" || chatKind === "private" || (chat.name || "").trim().toLowerCase() === "диалог") {
    if (chat.interlocutor?.avatar) return chat.interlocutor.avatar;

    const detailsOther = getInterlocutorFromParticipantDetails(chat, currentUserId);
    if (detailsOther?.avatar) return detailsOther.avatar;

    const other = getInterlocutorFromParticipants(chat, currentUserId);
    if (other?.avatar) return other.avatar;
  }
  return chat.avatar || "";
}

function getChatInitials(chat: Chat, currentUserId?: number): string {
  const title = getChatTitle(chat, currentUserId);
  return (
    title
      .split(" ")
      .filter(Boolean)
      .slice(0, 2)
      .map((p) => p[0]?.toUpperCase() || "")
      .join("") || "Ч"
  );
}

function getMessageInitials(message: Message): string {
  const name = (message.author_name || "").trim();
  if (!name) return "С";
  const parts = name.split(" ").filter(Boolean);
  if (parts.length === 1) {
    return parts[0].slice(0, 2).toUpperCase();
  }
  return `${parts[0][0] || ""}${parts[1][0] || ""}`.toUpperCase();
}

function formatTime(date?: string): string {
  if (!date) return "";
  const d = new Date(date);
  if (Number.isNaN(d.getTime())) return "";
  return d.toLocaleTimeString("ru-RU", { hour: "2-digit", minute: "2-digit" });
}

function getMessageDate(message: Message): Date | null {
  if (message.created_at) {
    const d = new Date(message.created_at);
    return Number.isNaN(d.getTime()) ? null : d;
  }

  if (message.created_ts) {
    const d = new Date(message.created_ts);
    return Number.isNaN(d.getTime()) ? null : d;
  }

  return null;
}

function formatDayDivider(date: Date): string {
  return date.toLocaleDateString("ru-RU", {
    day: "2-digit",
    month: "long",
    year: "numeric",
  });
}

function messageTime(message: Message): string {
  const d = getMessageDate(message);
  if (!d) return "";

  const now = new Date();
  const isToday = d.toDateString() === now.toDateString();
  if (isToday) {
    return d.toLocaleTimeString("ru-RU", { hour: "2-digit", minute: "2-digit" });
  }

  return d.toLocaleString("ru-RU", {
    day: "2-digit",
    month: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function isSameDay(a: Date | null, b: Date | null): boolean {
  if (!a || !b) return false;
  return (
    a.getFullYear() === b.getFullYear() &&
    a.getMonth() === b.getMonth() &&
    a.getDate() === b.getDate()
  );
}

function formatFileSize(size?: number): string {
  if (!size || size <= 0) return "";
  const kb = size / 1024;
  if (kb < 1024) return `${Math.round(kb)} КБ`;
  const mb = kb / 1024;
  return `${mb.toFixed(1)} МБ`;
}

function isImageAttachment(att: MessageAttachment): boolean {
  const mime = (att.mime_type || "").toLowerCase();
  const type = (att.file_type || "").toLowerCase();
  const name = (att.file_name || "").toLowerCase();
  const byExt = /\.(png|jpe?g|gif|webp|bmp|svg|avif)$/i.test(name);
  return mime.startsWith("image/") || type === "image" || byExt;
}

function isVideoAttachment(att: MessageAttachment): boolean {
  const mime = (att.mime_type || "").toLowerCase();
  const type = (att.file_type || "").toLowerCase();
  const name = (att.file_name || "").toLowerCase();
  const byExt = /\.(mp4|webm|mov|m4v|avi|mkv|3gp|mpeg|mpg)$/i.test(name);
  return mime.startsWith("video/") || type === "video" || byExt;
}

function isAudioAttachment(att: MessageAttachment): boolean {
  const mime = (att.mime_type || "").toLowerCase();
  const type = (att.file_type || "").toLowerCase();
  return mime.startsWith("audio/") || type === "audio";
}

function normalizePossiblyEncodedUrl(value: string): string {
  const input = (value || "").trim();
  if (!input) return "";

  try {
    // В API URL может приходить уже закодированным (%D0...).
    // Декодируем один раз и кодируем обратно, чтобы избежать %25D0... (double-encoding).
    return encodeURI(decodeURI(input));
  } catch {
    return encodeURI(input);
  }
}

function uniqueMessagesById(items: Message[]): Message[] {
  const map = new Map<number, Message>();
  items.forEach((msg) => {
    map.set(msg.id, msg);
  });
  return Array.from(map.values());
}

function getMessagePreviewText(message: Message): string {
  if (message.content?.trim()) return message.content.trim();
  if (message.attachments?.length) return "[Вложение]";
  return "[Сообщение]";
}

function getReplyToId(message: Message): number | null {
  if (typeof message.reply_to_id === "number") return message.reply_to_id;
  if (typeof message.reply_to === "number") return message.reply_to;
  if (message.reply_to && typeof message.reply_to === "object" && typeof message.reply_to.id === "number") {
    return message.reply_to.id;
  }
  if (message.reply_to_message && typeof message.reply_to_message.id === "number") {
    return message.reply_to_message.id;
  }
  return null;
}

type ReplyTarget = {
  id: number;
  author: string;
  preview: string;
};

const RECENT_REACTIONS_KEY = "eusrr_recent_reactions";
const MAX_RECENT_REACTIONS = 5;
const ALL_REACTIONS = [
  "👍", "❤️", "😂", "🔥", "👏", "🎉", "😊", "😉", "😁", "🤝",
  "🙏", "😮", "😢", "😡", "💯", "✅", "👀", "🤔", "😍", "😎",
  "🤩", "🥳", "😴", "🫡", "👌", "💪", "🙌", "🧠", "💡", "🚀",
  "🎯", "⭐", "✨", "🌟", "🫶", "🤗", "😅", "🤯", "🥲", "🫠",
];

function uniqueEmoji(items: string[]): string[] {
  const seen = new Set<string>();
  const out: string[] = [];

  items.forEach((item) => {
    if (!item || seen.has(item)) return;
    seen.add(item);
    out.push(item);
  });

  return out;
}

export default function MessageDialogPage() {
  const params = useParams<{ chatId: string }>();
  const chatId = Number(params.chatId);
  const { user, loading: userLoading } = useUser();

  const [chat, setChat] = useState<Chat | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [loading, setLoading] = useState(true);
  const [messagesLoading, setMessagesLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [messageText, setMessageText] = useState("");
  const [sending, setSending] = useState(false);
  const [editingMessageId, setEditingMessageId] = useState<number | null>(null);
  const [replyTo, setReplyTo] = useState<ReplyTarget | null>(null);
  const [expandedReplyActionForId, setExpandedReplyActionForId] = useState<number | null>(null);
  const [actionsMenuAnchor, setActionsMenuAnchor] = useState<{ x: number; y: number } | null>(null);
  const [reactionPickerForMessageId, setReactionPickerForMessageId] = useState<number | null>(null);
  const [showComposerEmojiPicker, setShowComposerEmojiPicker] = useState(false);
  const [recentReactions, setRecentReactions] = useState<string[]>(ALL_REACTIONS.slice(0, MAX_RECENT_REACTIONS));
  const [attachedFiles, setAttachedFiles] = useState<File[]>([]);
  const [brokenMedia, setBrokenMedia] = useState<Record<number, boolean>>({});
  const [useOriginalImage, setUseOriginalImage] = useState<Record<number, boolean>>({});
  const [mediaPreview, setMediaPreview] = useState<{ type: "image" | "video"; src: string; name: string } | null>(null);
  const [floatingDate, setFloatingDate] = useState<string | null>(null);
  const [showFloatingDate, setShowFloatingDate] = useState(false);
  const [showScrollToBottom, setShowScrollToBottom] = useState(false);
  const floatingDateTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const messageInputRef = useRef<HTMLTextAreaElement | null>(null);
  const messagesViewportRef = useRef<ScrollableMessageListInner | null>(null);
  const [hasMoreOlder, setHasMoreOlder] = useState(false);
  const [hasMoreNewer, setHasMoreNewer] = useState(false);
  const [loadingOlder, setLoadingOlder] = useState(false);
  const [loadingNewer, setLoadingNewer] = useState(false);
  const [initialAnchorId, setInitialAnchorId] = useState<number | null>(null);
  const [isTyping, setIsTyping] = useState(false);
  const typingTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const [initialAnchorIndex, setInitialAnchorIndex] = useState<number | null>(null);
  const [allowOneOlderProbe, setAllowOneOlderProbe] = useState(false);
  const initialScrolledRef = useRef(false);
  const anchorScrollAttemptsRef = useRef(0);
  const anchorOlderLoadAttemptsRef = useRef(0);
  const [anchorRetryTick, setAnchorRetryTick] = useState(0);
  const hasMoreNewerRef = useRef(false);
  
  // Локальное состояние для настроек чата
  const [isPinned, setIsPinned] = useState(false);
  const [notificationsEnabled, setNotificationsEnabled] = useState(true);
  
  // Синхронизируем ref с state
  useEffect(() => {
    hasMoreNewerRef.current = hasMoreNewer;
  }, [hasMoreNewer]);
  
  // Синхронизация настроек чата
  useEffect(() => {
    if (chat) {
      setIsPinned(chat.is_pinned ?? false);
      setNotificationsEnabled(chat.notifications_enabled ?? true);
    }
  }, [chat]);
  
  const messagesById = useMemo(() => new Map(messages.map((m) => [m.id, m])), [messages]);
  
  // Определяем текущий membership и права на отправку сообщений
  const myMembership = useMemo(() => {
    if (!chat?.memberships || !user?.id) return null;
    return chat.memberships.find(m => m.user === user.id) || null;
  }, [chat?.memberships, user?.id]);
  
  const canSendMessages = useMemo(() => {
    // Если нет membership - разрешаем (обычные чаты без ролей)
    if (!myMembership) return true;
    
    // Проверяем флаг can_send_messages (гости имеют false)
    return myMembership.can_send_messages;
  }, [myMembership]);
  
  const selectedActionMessage = expandedReplyActionForId ? messagesById.get(expandedReplyActionForId) || null : null;
  const selectedActionCanManage = Boolean(
    selectedActionMessage &&
    user?.id &&
    !selectedActionMessage.is_deleted &&
    (selectedActionMessage.author_id === user.id ||
      selectedActionMessage.author?.id === user.id ||
      selectedActionMessage.sender?.id === user.id)
  );
  const selectedActionCanReply = Boolean(selectedActionMessage && !selectedActionMessage.is_deleted);
  const selectedActionRecentReactions = useMemo(
    () => uniqueEmoji(recentReactions).slice(0, MAX_RECENT_REACTIONS),
    [recentReactions]
  );

  // WebSocket для real-time обновлений
  const { isConnected, sendTyping, handlers, reconnectAttempts } = useWebSocket({ 
    chatId: chatId || null,
    autoConnect: true 
  });

  // Проверка, находится ли пользователь внизу списка
  const isNearBottom = useCallback(() => {
    const component = messagesViewportRef.current;
    if (!component || !component.containerRef?.current) return false;
    
    const viewport = component.containerRef.current;
    const threshold = 150; // px от низа
    const { scrollHeight, scrollTop, clientHeight } = viewport;
    return scrollHeight - scrollTop - clientHeight <= threshold;
  }, []);

  // Автопрокрутка вниз
  const scrollToBottom = useCallback((smooth = false) => {
    const component = messagesViewportRef.current;
    if (!component) return;
    
    component.scrollToBottom(smooth ? 'smooth' : 'auto');
  }, []);

  // Обновление reactions_summary для конкретного сообщения
  const updateMessageReactionsSummary = useCallback((
    messageId: number,
    summary?: Record<string, { count: number; users?: number[]; user_names?: string[] }>
  ) => {
    if (!summary) return;
    setMessages((prev) => prev.map((m) => (m.id === messageId ? { ...m, reactions_summary: summary } : m)));
  }, []);

  // Настройка обработчиков WebSocket событий
  useEffect(() => {
    handlers.current.onMessage = (data) => {
      if (data.type === 'new_message') {
        // Новое сообщение
        const newMsg = data.message;
        const isMyMessage = newMsg.author_id === user?.id;
        const wasNearBottom = isNearBottom();
        
        setMessages(prev => {
          // Проверяем, нет ли уже такого сообщения (дедупликация)
          if (prev.some(m => m.id === newMsg.id)) {
            return prev;
          }
          
          // ВАЖНО: Добавляем сообщение только если:
          // 1. Это МОЕ сообщение (я только что отправил) - всегда добавляем
          // 2. ИЛИ у нас загружены все сообщения (hasMoreNewerRef.current = false)
          // 3. ИЛИ новое сообщение идет сразу после последнего (непрерывная последовательность)
          
          if (prev.length > 0 && !isMyMessage) {
            const lastMessage = prev[prev.length - 1];
            const hasGap = newMsg.id - lastMessage.id > 1; // Есть пропущенные сообщения
            
            // Если есть разрыв И есть непрочитанные - НЕ добавляем
            if (hasGap && hasMoreNewerRef.current) {
              console.warn(`⚠️ WebSocket: пропуск сообщения ${newMsg.id} - есть незагруженные между ${lastMessage.id} и ${newMsg.id}`);
              // Оставляем hasMoreNewer = true
              return prev;
            }
          }
          
          // Добавляем сообщение
          const updated = [...prev, newMsg];
          
          // Сбрасываем флаг "есть еще новые сообщения"
          setTimeout(() => {
            setHasMoreNewer(false);
            
            // Автоотметка как прочитанное ТОЛЬКО если:
            // 1. Это НЕ мое сообщение
            // 2. И я был внизу (активно читал)
            // Прагматичный подход: загружено = прочитано (для сообщений в области видимости)
            if (!isMyMessage && wasNearBottom && chatId) {
              apiClient.markChatAsRead(chatId, newMsg.id).catch(err => {
                console.error('Ошибка автоотметки WebSocket сообщения:', err);
              });
            }
            
            // Автопрокрутка вниз если:
            // 1. Сообщение отправил я сам
            // 2. Или я был внизу списка (читал последние сообщения)
            if (isMyMessage || wasNearBottom) {
              requestAnimationFrame(() => {
                requestAnimationFrame(() => {
                  scrollToBottom(true);
                });
              });
            }
          }, 0);
          
          return updated;
        });
      } 
      else if (data.type === 'message_edited') {
        // Редактирование сообщения
        const editedMsg = data.message;
        setMessages(prev => prev.map(m => 
          m.id === editedMsg.id ? { ...m, ...editedMsg } : m
        ));
      } 
      else if (data.type === 'message_deleted') {
        // Удаление сообщения
        setMessages(prev => prev.filter(m => m.id !== data.message_id));
      } 
      else if (data.type === 'typing_start') {
        // Индикатор "печатает..."
        if (data.user_id !== user?.id) {
          setIsTyping(true);
          
          if (typingTimeoutRef.current) {
            clearTimeout(typingTimeoutRef.current);
          }
          
          typingTimeoutRef.current = setTimeout(() => {
            setIsTyping(false);
          }, 3000);
        }
      }
      else if (data.type === 'typing_stop') {
        // Остановка печати
        if (data.user_id !== user?.id) {
          setIsTyping(false);
          if (typingTimeoutRef.current) {
            clearTimeout(typingTimeoutRef.current);
          }
        }
      }
      else if (data.type === 'reaction_added') {
        // Реакция добавлена
        if (data.reactions_summary && data.message_id) {
          updateMessageReactionsSummary(data.message_id, data.reactions_summary);
        }
      }
      else if (data.type === 'reaction_removed') {
        // Реакция удалена
        if (data.reactions_summary && data.message_id) {
          updateMessageReactionsSummary(data.message_id, data.reactions_summary);
        }
      }
    };

    handlers.current.onConnect = () => {
      // WebSocket подключен
    };

    handlers.current.onDisconnect = () => {
      // WebSocket отключен
    };

    handlers.current.onError = (error) => {
      console.error('❌ WebSocket error:', error);
    };
  }, [user?.id, chatId, isNearBottom, scrollToBottom, updateMessageReactionsSummary]);

  // Очистка таймаута при размонтировании
  useEffect(() => {
    return () => {
      if (typingTimeoutRef.current) {
        clearTimeout(typingTimeoutRef.current);
      }
      if (floatingDateTimeoutRef.current) {
        clearTimeout(floatingDateTimeoutRef.current);
      }
    };
  }, []);

  useLayoutEffect(() => {
    if (typeof window === "undefined" || !window.history) return;
    const prev = window.history.scrollRestoration;
    window.history.scrollRestoration = "manual";
    return () => {
      window.history.scrollRestoration = prev;
    };
  }, []);

  useEffect(() => {
    if (typeof window === "undefined") return;
    try {
      const raw = localStorage.getItem(RECENT_REACTIONS_KEY);
      if (!raw) return;
      const parsed = JSON.parse(raw);
      if (!Array.isArray(parsed)) return;
      const normalized = uniqueEmoji(parsed.filter((v): v is string => typeof v === "string")).slice(0, MAX_RECENT_REACTIONS);
      if (normalized.length > 0) {
        setRecentReactions(normalized);
      }
    } catch {
      // ignore
    }
  }, []);

  const pushRecentReaction = (emoji: string) => {
    const next = uniqueEmoji([emoji, ...recentReactions]).slice(0, MAX_RECENT_REACTIONS);
    setRecentReactions(next);
    if (typeof window !== "undefined") {
      localStorage.setItem(RECENT_REACTIONS_KEY, JSON.stringify(next));
    }
  };

  const appendEmojiToComposer = (emoji: string) => {
    setMessageText((prev) => `${prev}${emoji}`);
    requestAnimationFrame(() => {
      const input = messageInputRef.current;
      if (!input) return;
      input.focus();
      const len = input.value.length;
      input.setSelectionRange(len, len);
    });
  };

  const hasMyReaction = (message: Message, emoji: string): boolean => {
    if (!user?.id) return false;
    const users = message.reactions_summary?.[emoji]?.users || [];
    return users.includes(user.id);
  };

  const handleReact = async (message: Message, emoji: string) => {
    try {
      const response = hasMyReaction(message, emoji)
        ? await apiClient.unreactToMessage(message.id, emoji)
        : await apiClient.reactToMessage(message.id, emoji);

      pushRecentReaction(emoji);
      updateMessageReactionsSummary(message.id, response.reactions_summary);
    } catch (e) {
      console.error("Ошибка реакции:", e);
    }
  };

  useEffect(() => {
    async function loadChats() {
      if (!chatId || Number.isNaN(chatId)) {
        setChat(null);
        setLoading(false);
        return;
      }

      // На full reload дожидаемся восстановления auth-состояния,
      // иначе возможен первый 401 и «залипание» без повторной загрузки.
      if (userLoading) {
        setLoading(true);
        return;
      }

      if (!user) {
        setChat(null);
        setLoading(false);
        return;
      }

      try {
        setLoading(true);
        setError(null);
        const loadedChat = await apiClient.getChat(chatId);
        setChat(loadedChat);
      } catch (e: any) {
        setChat(null);
        setError("Не удалось загрузить чат. Проверьте подключение и попробуйте снова.");
      } finally {
        setLoading(false);
      }
    }

    loadChats();
  }, [chatId, userLoading, user?.id]);

  useEffect(() => {
    async function loadMessages() {
      if (!chatId || Number.isNaN(chatId)) {
        setMessages([]);
        setHasMoreOlder(false);
        setHasMoreNewer(false);
        setInitialAnchorId(null);
        setInitialAnchorIndex(null);
        setAllowOneOlderProbe(false);
        initialScrolledRef.current = false;
        return;
      }

      // Ключевой фикс для полного reload: грузим сообщения только
      // после завершения инициализации пользователя.
      if (userLoading || !user) {
        return;
      }

      try {
        setMessagesLoading(true);
        
        // 1. Получаем детали чата с last_read_message_id
        const chatDetails = await apiClient.getChat(chatId);
        const lastReadId = chatDetails.last_read_message_id;
        
        // 2. Загружаем сообщения вокруг last_read_message_id
        //    Асимметричные лимиты: 24 контекста + 6 новых = 30 сообщений
        //    Автоотметка последнего загруженного как прочитанного
        const around = await apiClient.getChatMessagesAround(chatId, { 
          limit: 30,  // 24 до + 6 после
          around_id: lastReadId || undefined
        });
        
        const aroundMessages = around.messages || [];

        if (aroundMessages.length > 0) {
          const normalized = uniqueMessagesById(aroundMessages);
          setMessages(normalized);
          // fallback на случай, если API не вернул флаг has_more_before
          setHasMoreOlder(
            typeof around.has_more_before === "boolean" ? around.has_more_before : normalized.length >= 50
          );
          setHasMoreNewer(Boolean(around.has_more_after));
          setInitialAnchorId(around.anchor_id ?? null);
          setInitialAnchorIndex(typeof around.anchor_index === "number" ? around.anchor_index : null);
          setAllowOneOlderProbe(Boolean(around.anchor_id));
        } else {
          const response = await apiClient.getChatMessages(chatId, { limit: 50 });
          setMessages(uniqueMessagesById(response.messages || []));
          setHasMoreOlder(Boolean(response.has_more));
          setHasMoreNewer(false);
          setInitialAnchorId(null);
          setInitialAnchorIndex(null);
          setAllowOneOlderProbe(false);
        }

        initialScrolledRef.current = false;
        anchorScrollAttemptsRef.current = 0;
        anchorOlderLoadAttemptsRef.current = 0;
        setAnchorRetryTick(0);
      } catch (e: any) {
        if (String(e?.message || "").includes("403")) {
          setError("Нет доступа к этому чату");
          setMessages([]);
        } else {
          console.error("Ошибка загрузки сообщений:", e);
        }
        setHasMoreOlder(false);
        setHasMoreNewer(false);
        setInitialAnchorId(null);
        setInitialAnchorIndex(null);
        setAllowOneOlderProbe(false);
        initialScrolledRef.current = false;
        anchorScrollAttemptsRef.current = 0;
        anchorOlderLoadAttemptsRef.current = 0;
        setAnchorRetryTick(0);
      } finally {
        setMessagesLoading(false);
      }
    }

    loadMessages();
  }, [chatId, userLoading, user?.id]);

  // Скролл к якорю или вниз после загрузки сообщений
  // Anchor scroll используется при переходе по прямой ссылке на сообщение (например, из уведомления)
  useEffect(() => {
    const component = messagesViewportRef.current;
    if (messagesLoading || !component || !component.containerRef?.current || messages.length === 0 || initialScrolledRef.current) return;

    const viewport = component.containerRef.current;

    // Если есть якорь - пытаемся к нему прокрутиться
    if (initialAnchorId) {
      const el = viewport.querySelector(`[data-message-id="${initialAnchorId}"]`) as HTMLElement | null;
      if (el) {
        // Ручной scrollTop вместо scrollIntoView (iOS Safari не поддерживает scrollIntoView в overflow контейнерах)
        const containerRect = viewport.getBoundingClientRect();
        const elRect = el.getBoundingClientRect();
        const offset = elRect.top - containerRect.top + viewport.scrollTop - viewport.clientHeight / 2 + elRect.height / 2;
        viewport.scrollTop = Math.max(0, offset);
        initialScrolledRef.current = true;
        anchorScrollAttemptsRef.current = 0;
        setInitialAnchorId(null);
        setInitialAnchorIndex(null);
        return;
      }

      // Пробуем по индексу
      if (typeof initialAnchorIndex === "number" && initialAnchorIndex >= 0) {
        const children = viewport.querySelectorAll("[data-message-id]");
        const byIndex = children.item(initialAnchorIndex) as HTMLElement | null;
        if (byIndex) {
          const containerRect = viewport.getBoundingClientRect();
          const elRect = byIndex.getBoundingClientRect();
          const offset = elRect.top - containerRect.top + viewport.scrollTop - viewport.clientHeight / 2 + elRect.height / 2;
          viewport.scrollTop = Math.max(0, offset);
          initialScrolledRef.current = true;
          anchorScrollAttemptsRef.current = 0;
          setInitialAnchorId(null);
          setInitialAnchorIndex(null);
          return;
        }
      }

      // Даем DOM время на отрисовку (максимум 5 попыток, iOS рендерит медленнее)
      if (anchorScrollAttemptsRef.current < 5) {
        anchorScrollAttemptsRef.current += 1;
        setTimeout(() => setAnchorRetryTick((v) => v + 1), 100);
        return;
      }
      
      // Якорь не найден после 5 попыток - скроллим вниз
      console.warn('Anchor not found after 5 attempts, scrolling to bottom');
      setInitialAnchorId(null);
      setInitialAnchorIndex(null);
    }

    // Обычная прокрутка вниз без анимации (автоматический скролл при первой загрузке чата)
    component.scrollToBottom('auto');
    initialScrolledRef.current = true;
    anchorScrollAttemptsRef.current = 0;
    anchorOlderLoadAttemptsRef.current = 0;
  }, [
    messagesLoading,
    messages,
    initialAnchorId,
    initialAnchorIndex,
    anchorRetryTick,
  ]);

  // Удалено: prependAdjustRef useLayoutEffect
  // ScrollableMessageList уже корректирует позицию автоматически через getSnapshotBeforeUpdate
  // Дублирующая корректировка вызывала "подергивание" при загрузке старых сообщений

  const loadOlderMessages = async () => {
    if (!chatId || Number.isNaN(chatId) || loadingOlder || messagesLoading || messages.length === 0) {
      return;
    }

    if (!hasMoreOlder && !allowOneOlderProbe) {
      return;
    }

    const oldestMessage = messages[0];

    try {
      setLoadingOlder(true);
      const response = await apiClient.getChatMessages(chatId, {
        limit: 40,
        before_id: oldestMessage.id,
      });

      const olderMessages = response.messages || [];
      if (olderMessages.length > 0) {
        // ScrollableMessageList автоматически сохранит позицию через getSnapshotBeforeUpdate
        setMessages((prev) => uniqueMessagesById([...olderMessages, ...prev]));
      }

      setHasMoreOlder(Boolean(response.has_more));
      setAllowOneOlderProbe(false);
      if (!response.has_more && (!response.messages || response.messages.length === 0)) {
        anchorOlderLoadAttemptsRef.current = 3;
      }
    } catch (e) {
      console.error("Ошибка подгрузки старых сообщений:", e);
    } finally {
      setLoadingOlder(false);
    }
  };

  const loadNewerMessages = async () => {
    if (!chatId || Number.isNaN(chatId) || loadingNewer || messagesLoading || !hasMoreNewer || messages.length === 0) {
      return;
    }

    const newestMessage = messages[messages.length - 1];

    try {
      setLoadingNewer(true);
      const response = await apiClient.getChatMessages(chatId, {
        limit: 10,  // Ограничено для минимальной погрешности автоотметки (было 40)
        after_id: newestMessage.id,
      });

      const newerMessages = response.messages || [];
      if (newerMessages.length > 0) {
        setMessages((prev) => uniqueMessagesById([...prev, ...newerMessages]));
        
        // НЕ делаем автоскролл - ScrollableMessageList сам решит:
        // - Если был внизу (sticky) → автоматически проскроллит вниз
        // - Если был НЕ внизу → сохранит текущую позицию
        // Это правильное поведение для дозагрузки истории
      }

      setHasMoreNewer(Boolean(response.has_more));
    } catch (e) {
      console.error("Ошибка подгрузки новых сообщений:", e);
    } finally {
      setLoadingNewer(false);
    }
  };

  useEffect(() => {
    const component = messagesViewportRef.current;
    if (!component || !component.containerRef?.current) return;
    
    const viewport = component.containerRef.current;

    const onScroll = () => {
      // Загрузка старых сообщений при приближении к верху
      if (!loadingOlder && !messagesLoading && hasMoreOlder && viewport.scrollTop <= 120) {
        loadOlderMessages();
      }

      // Загрузка новых сообщений при приближении к низу
      const distanceFromBottom = viewport.scrollHeight - viewport.scrollTop - viewport.clientHeight;
      if (!loadingNewer && !messagesLoading && hasMoreNewer && distanceFromBottom <= 120) {
        loadNewerMessages();
      }

      // Обновление плавающей даты
      const messageEls = viewport.querySelectorAll<HTMLElement>('[data-message-date]');
      let topDate: string | null = null;
      const viewportTop = viewport.getBoundingClientRect().top;

      for (let i = 0; i < messageEls.length; i++) {
        const el = messageEls[i];
        const rect = el.getBoundingClientRect();
        if (rect.bottom > viewportTop) {
          const isoDate = el.getAttribute('data-message-date');
          if (isoDate) {
            const d = new Date(isoDate);
            if (!Number.isNaN(d.getTime())) {
              topDate = formatDayDivider(d);
            }
          }
          break;
        }
      }

      if (topDate) {
        setFloatingDate(topDate);
        setShowFloatingDate(true);

        if (floatingDateTimeoutRef.current) clearTimeout(floatingDateTimeoutRef.current);
        floatingDateTimeoutRef.current = setTimeout(() => {
          setShowFloatingDate(false);
        }, 1500);
      }

      // Показ кнопки scroll-to-bottom когда не внизу
      const isAtBottom = isNearBottom();
      setShowScrollToBottom(!isAtBottom);
    };

    viewport.addEventListener("scroll", onScroll, { passive: true });
    return () => viewport.removeEventListener("scroll", onScroll);
  }, [chatId, hasMoreOlder, hasMoreNewer, loadingOlder, loadingNewer, messagesLoading, messages]);

  const handleSend = async () => {
    const text = messageText.trim();
    if (!chatId || sending) return;
    if (editingMessageId) {
      if (!text) return;
    } else if (!text && attachedFiles.length === 0) {
      return;
    }

    // Запоминаем позицию ДО отправки
    const wasNearBottom = isNearBottom();

    try {
      setSending(true);
      if (editingMessageId) {
        const updated = await apiClient.updateMessage(editingMessageId, text);
        setMessages((prev) => prev.map((m) => (m.id === editingMessageId ? { ...m, ...updated } : m)));
      } else {
        const sent = attachedFiles.length
          ? await apiClient.sendMessageWithFiles(chatId, text, attachedFiles, replyTo?.id)
          : await apiClient.sendMessage(chatId, text, replyTo?.id);
        setMessages((prev) => uniqueMessagesById([...prev, sent]));
      }

      setEditingMessageId(null);
      setMessageText("");
      setReplyTo(null);
      setExpandedReplyActionForId(null);
      setAttachedFiles([]);
      if (fileInputRef.current) {
        fileInputRef.current.value = "";
      }

      // Автоскролл вниз ТОЛЬКО если был внизу при отправке
      // Если читал историю вверху - не скроллим, оставляем там где был
      if (wasNearBottom) {
        requestAnimationFrame(() => {
          scrollToBottom(false);
        });
      }
    } catch (e) {
      console.error("Ошибка отправки сообщения:", e);
    } finally {
      setSending(false);
    }
  };

  const handlePickFiles = () => {
    if (editingMessageId) return;
    fileInputRef.current?.click();
  };

  const handleFilesChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(e.target.files || []);
    if (!files.length) return;
    setAttachedFiles((prev) => [...prev, ...files]);
  };

  const removeAttachedFile = (index: number) => {
    setAttachedFiles((prev) => prev.filter((_, i) => i !== index));
  };

  const focusMessageInput = () => {
    const input = messageInputRef.current;
    if (!input) return;
    input.focus();
    const len = input.value.length;
    input.setSelectionRange(len, len);
  };

  const handleReplyToMessage = (message: Message) => {
    const author = message.author_name || message.author?.last_name || message.sender?.last_name || "Сотрудник";
    const preview = getMessagePreviewText(message);
    setEditingMessageId(null);
    setReplyTo({ id: message.id, author, preview });
    setExpandedReplyActionForId(null);
    setActionsMenuAnchor(null);
    requestAnimationFrame(focusMessageInput);
  };

  const canManageMessage = (message: Message): boolean => {
    if (!user?.id || message.is_deleted) return false;
    return message.author_id === user.id || message.author?.id === user.id || message.sender?.id === user.id;
  };

  const handleStartEditMessage = (message: Message) => {
    if (!canManageMessage(message)) return;

    setEditingMessageId(message.id);
    setReplyTo(null);
    setExpandedReplyActionForId(null);
    setMessageText(message.content || "");
    setAttachedFiles([]);
    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }

    requestAnimationFrame(focusMessageInput);
  };

  const handleCancelEdit = () => {
    setEditingMessageId(null);
    setMessageText("");
  };

  const handleDeleteMessage = async (message: Message) => {
    if (!canManageMessage(message)) return;

    try {
      await apiClient.deleteMessage(message.id);

      setMessages((prev) =>
        prev.map((m) =>
          m.id === message.id
            ? {
                ...m,
                content: "",
                attachments: [],
                has_attachments: false,
                is_deleted: true,
              }
            : m
        )
      );

      if (replyTo?.id === message.id) {
        setReplyTo(null);
      }
      if (editingMessageId === message.id) {
        setEditingMessageId(null);
        setMessageText("");
      }

      setExpandedReplyActionForId(null);
      setActionsMenuAnchor(null);
    } catch (e) {
      console.error("Ошибка удаления сообщения:", e);
    }
  };

  const handleTogglePin = async () => {
    if (!chatId) return;
    
    try {
      const response = await apiClient.togglePinChat(chatId);
      const newIsPinned = response.is_pinned ?? !isPinned;
      setIsPinned(newIsPinned);
      
      // Обновляем chat объект
      if (chat) {
        setChat({ ...chat, is_pinned: newIsPinned });
      }
    } catch (e) {
      console.error("Ошибка переключения закрепления:", e);
    }
  };

  const handleToggleNotifications = async () => {
    if (!chatId) return;
    
    try {
      const response = await apiClient.toggleChatNotifications(chatId);
      const newNotificationsEnabled = response.notifications_enabled ?? !notificationsEnabled;
      setNotificationsEnabled(newNotificationsEnabled);
      
      // Обновляем chat объект
      if (chat) {
        setChat({ ...chat, notifications_enabled: newNotificationsEnabled });
      }
    } catch (e) {
      console.error("Ошибка переключения уведомлений:", e);
    }
  };

  useEffect(() => {
    const onWindowClick = (e: MouseEvent) => {
      const target = e.target as HTMLElement | null;
      if (!target) return;
      if (target.closest("[data-actions-menu='true']")) return;
      if (target.closest("[data-actions-trigger='true']")) return;
      if (target.closest("[data-reaction-picker='true']")) return;
      if (target.closest("[data-composer-emoji='true']")) return;

      setExpandedReplyActionForId(null);
      setActionsMenuAnchor(null);
      setReactionPickerForMessageId(null);
      setShowComposerEmojiPicker(false);
    };

    window.addEventListener("mousedown", onWindowClick);
    return () => window.removeEventListener("mousedown", onWindowClick);
  }, []);

  const isInteractiveArea = (target: HTMLElement): boolean =>
    Boolean(target.closest("textarea, input, button, a, video, audio, [contenteditable='true']"));

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        setMediaPreview(null);
        setExpandedReplyActionForId(null);
        setActionsMenuAnchor(null);
        setReactionPickerForMessageId(null);
        setShowComposerEmojiPicker(false);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  // При открытии мобильной клавиатуры прокручиваем чат вниз
  useEffect(() => {
    const vv = window.visualViewport;
    if (!vv) return;

    let prevHeight = vv.height;

    const onResize = () => {
      const newHeight = vv.height;
      if (newHeight < prevHeight) {
        requestAnimationFrame(() => {
          messagesViewportRef.current?.scrollToBottom('auto');
        });
      }
      prevHeight = newHeight;
    };

    vv.addEventListener('resize', onResize);
    return () => vv.removeEventListener('resize', onResize);
  }, []);

  useEffect(() => {
    const onGlobalWheel = (e: WheelEvent) => {
      if (e.defaultPrevented || mediaPreview) return;

      const component = messagesViewportRef.current;
      if (!component || !component.containerRef?.current) return;
      const viewport = component.containerRef.current;

      const target = e.target as HTMLElement | null;
      if (!target) return;

      if (viewport.contains(target)) return;
      if (isInteractiveArea(target)) return;

      e.preventDefault();
      viewport.scrollTop += e.deltaY;
    };

    window.addEventListener("wheel", onGlobalWheel, { passive: false });
    return () => window.removeEventListener("wheel", onGlobalWheel);
  }, [mediaPreview]);

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
        <div className="min-h-0 h-full lg:sticky lg:top-22 lg:h-[calc(100dvh-7.5rem)]">
        {/* Предупреждение о WebSocket */}
        {!isConnected && reconnectAttempts > 2 && (
          <div className="mb-4 rounded-2xl bg-amber-50 border border-amber-200 p-4 shadow-sm">
            <div className="flex items-start gap-3">
              <div className="flex-1">
                <p className="text-sm font-semibold text-amber-900">⚠️ Real-time обновления отключены</p>
                <p className="mt-1 text-xs text-amber-800">
                  Backend не поддерживает WebSocket. Запустите через Daphne:
                </p>
                <code className="mt-2 block rounded bg-amber-100 px-2 py-1 text-xs text-amber-900">
                  cd backend && ..\\.venv\\Scripts\\daphne -p 9000 eusrr_backend.asgi:application
                </code>
              </div>
              <button
                onClick={() => window.location.reload()}
                className="text-xs text-amber-700 hover:text-amber-900 underline"
              >
                Обновить
              </button>
            </div>
          </div>
        )}
        
        <section className="flex h-full min-h-0 flex-col overflow-hidden lg:bg-white lg:rounded-2xl lg:p-5 lg:shadow-sm lg:ring-1 lg:ring-gray-100">
          {chat ? (
            <>
              <header className="flex shrink-0 items-center justify-between gap-3 border-b border-gray-100 pb-3">
                <div className="flex items-center gap-3">
                  <div className="flex h-11 w-11 items-center justify-center overflow-hidden rounded-full bg-sky-400 text-sm font-semibold text-white">
                    {getChatAvatar(chat, user?.id) ? (
                      <img src={resolveMediaUrl(getChatAvatar(chat, user?.id))} alt={getChatTitle(chat, user?.id)} className="h-full w-full object-cover" />
                    ) : (
                      getChatInitials(chat, user?.id)
                    )}
                  </div>
                  <Link href={`/messages/${chatId}/settings`} className="hover:opacity-80 transition">
                    <div className="flex items-center gap-2">
                      <p className="text-sm font-semibold text-gray-900">{getChatTitle(chat, user?.id)}</p>
                      {/* Индикатор WebSocket соединения */}
                      {isConnected && (
                        <span className="inline-flex h-2 w-2 rounded-full bg-green-500" title="Real-time подключен"></span>
                      )}
                    </div>
                    <p className="text-xs text-gray-500">{(chat.type || chat.chat_type) === "group" ? "Групповой чат" : "Диалог"}</p>
                  </Link>
                </div>

                <div className="flex items-center gap-2">
                  {/* Кнопка закрепления чата */}
                  <button
                    type="button"
                    onClick={handleTogglePin}
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
                  
                  {/* Кнопка управления уведомлениями */}
                  <button
                    type="button"
                    onClick={handleToggleNotifications}
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
                  
                  {/* Кнопка возврата к списку */}
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

              <div className="relative flex min-h-0 flex-1 flex-col overflow-hidden">
                {/* Плавающая дата */}
                {floatingDate && (
                  <div
                    className={`pointer-events-none absolute left-0 right-0 top-2 z-20 text-center transition-opacity duration-300 ${showFloatingDate ? 'opacity-100' : 'opacity-0'}`}
                  >
                    <span className="inline-block rounded-full bg-white/95 px-3 py-1 text-xs text-gray-500 shadow-sm ring-1 ring-gray-200 backdrop-blur">
                      {floatingDate}
                    </span>
                  </div>
                )}

                <ScrollableMessageList
                  ref={messagesViewportRef}
                  autoScrollToBottom={true}
                  autoScrollToBottomOnMount={true}
                  scrollBehavior="smooth"
                  className="min-h-0 flex-1 bg-gray-50 p-3"
                >
                  {messagesLoading ? (
                    <p className="text-center text-sm text-gray-500">Загрузка сообщений...</p>
                  ) : messages.length === 0 ? (
                    <p className="text-center text-sm text-gray-500">Пока нет сообщений. Напишите первым.</p>
                  ) : (
                    <div className="flex min-h-full flex-col justify-end">
                      {loadingOlder ? (
                        <p className="mb-3 text-center text-xs text-gray-500">Подгружаем старые сообщения...</p>
                      ) : null}
                      {messages.map((message, index) => {
                        const currentDate = getMessageDate(message);
                        const prevDate = index > 0 ? getMessageDate(messages[index - 1]) : null;
                        const showDayDivider = index === 0 || !isSameDay(currentDate, prevDate);
                        const replyToId = getReplyToId(message);
                        const repliedMessage = replyToId ? messagesById.get(replyToId) : null;
                        const isReplyMenuOpen = expandedReplyActionForId === message.id;

                        const isMine =
                          user?.id &&
                          (message.author_id === user.id || message.author?.id === user.id || message.sender?.id === user.id);
                        const canManage = canManageMessage(message);
                        const canReply = !message.is_deleted;
                        const hasActions = canReply || canManage;

                        return (
                          <React.Fragment key={message.id}>
                          <div data-message-id={message.id} data-message-date={currentDate?.toISOString() || ''} className="mb-3 last:mb-0">
                            <div className={`flex ${isMine ? "justify-end" : "justify-start"}`}>
                              {!isMine ? (
                                <div className="relative mr-2 mt-1 h-8 w-8 shrink-0">
                                  <div className="flex h-8 w-8 items-center justify-center overflow-hidden rounded-full bg-sky-400 text-[10px] font-semibold text-white">
                                    {message.avatar || message.author?.avatar ? (
                                      <img
                                        src={resolveMediaUrl(message.avatar || message.author?.avatar || "")}
                                        alt={message.author_name || "Автор"}
                                        className="h-full w-full object-cover"
                                      />
                                    ) : (
                                      getMessageInitials(message)
                                    )}
                                  </div>
                                  {message.author?.is_active ? (
                                    <span className="absolute -bottom-0.5 -right-0.5 z-10 h-2.5 w-2.5 rounded-full bg-sky-400 ring-2 ring-white" />
                                  ) : null}
                                </div>
                              ) : null}

                              <div
                                className={`flex min-w-0 items-start gap-1 ${
                                  isMine ? "max-w-[88%] flex-row-reverse" : "max-w-[calc(100%-2.5rem)]"
                                }`}
                              >
                                <div
                                  className={`relative min-w-0 rounded-2xl px-3 py-2 pr-9 ${
                                    isMine ? "bg-sky-500 text-white" : "bg-white text-gray-900 ring-1 ring-gray-100"
                                  }`}
                                >
                                  {hasActions ? (
                                    <div className="absolute right-1 top-1 z-20">
                                      <button
                                        type="button"
                                        data-actions-trigger="true"
                                        onClick={(e) => {
                                          const rect = (e.currentTarget as HTMLButtonElement).getBoundingClientRect();
                                          setExpandedReplyActionForId((prev) => {
                                            if (prev === message.id) {
                                              setActionsMenuAnchor(null);
                                              return null;
                                            }

                                            setReactionPickerForMessageId(null);
                                            setShowComposerEmojiPicker(false);
                                            setActionsMenuAnchor({ x: rect.right, y: rect.top });
                                            return message.id;
                                          });
                                        }}
                                        className={`inline-flex h-6 w-6 items-center justify-center rounded-full border border-transparent bg-transparent text-gray-500 transition hover:text-sky-600 ${
                                          isReplyMenuOpen ? "rotate-90" : ""
                                        }`}
                                        title="Действия"
                                        aria-label="Действия сообщения"
                                      >
                                        <ChevronRight size={14} />
                                      </button>
                                    </div>
                                  ) : null}

                                  {!isMine ? (
                                    <p className="mb-1 text-[11px] font-medium text-gray-500">
                                      {message.author_name || message.author?.last_name || message.sender?.last_name || "Сотрудник"}
                                    </p>
                                  ) : null}

                                  {replyToId ? (
                                    <div
                                      className={`mb-2 rounded-lg border-l-2 px-2 py-1 text-xs ${
                                        isMine
                                          ? "border-sky-200 bg-sky-400/30 text-sky-50"
                                          : "border-gray-300 bg-gray-100 text-gray-600"
                                      }`}
                                    >
                                      <p className="font-medium">{repliedMessage?.author_name || "Ответ на сообщение"}</p>
                                      <p className="truncate">{repliedMessage ? getMessagePreviewText(repliedMessage) : `Сообщение #${replyToId}`}</p>
                                    </div>
                                  ) : null}

                                  {message.is_deleted ? (
                                    <p className={`italic text-sm ${isMine ? "text-sky-100" : "text-gray-500"}`}>Сообщение удалено</p>
                                  ) : message.content ? (
                                    <p className="whitespace-pre-wrap break-words text-sm leading-5">{message.content}</p>
                                  ) : null}

                                  {message.attachments && message.attachments.length > 0 ? (
                                    <div className="mt-2 space-y-2">
                                      {message.attachments.map((att) => (
                                        <div key={att.id}>
                                          {isImageAttachment(att) ? (
                                            brokenMedia[att.id] ? (
                                              <a
                                                href={resolveMediaUrl(att.file_url)}
                                                target="_blank"
                                                rel="noreferrer"
                                                className="flex items-center gap-2 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800"
                                              >
                                                <FileText size={16} className="shrink-0" />
                                                <span className="min-w-0 flex-1 truncate">Предпросмотр недоступен — открыть файл</span>
                                              </a>
                                            ) : (
                                              <button
                                                type="button"
                                                onClick={() => setMediaPreview({ type: "image", src: resolveMediaUrl(att.file_url), name: att.file_name })}
                                                className="block w-full overflow-hidden rounded-lg"
                                              >
                                                {(() => {
                                                  const hasThumbnail = Boolean(att.thumbnail);
                                                  const src = useOriginalImage[att.id]
                                                    ? resolveMediaUrl(att.file_url)
                                                    : resolveMediaUrl(att.thumbnail || att.file_url);

                                                  return (
                                                <img
                                                  src={src}
                                                  alt={att.file_name}
                                                  width={att.width || undefined}
                                                  height={att.height || undefined}
                                                  className="max-h-64 w-full rounded-lg object-cover"
                                                  onError={() => {
                                                    if (hasThumbnail && !useOriginalImage[att.id]) {
                                                      setUseOriginalImage((prev) => ({ ...prev, [att.id]: true }));
                                                      return;
                                                    }
                                                    setBrokenMedia((prev) => ({ ...prev, [att.id]: true }));
                                                  }}
                                                  onLoad={() => {
                                                    setBrokenMedia((prev) => ({ ...prev, [att.id]: false }));
                                                    // Корректируем позицию скролла после загрузки изображения
                                                    messagesViewportRef.current?.updateScrollPosition();
                                                  }}
                                                />
                                                  );
                                                })()}
                                              </button>
                                            )
                                          ) : isVideoAttachment(att) ? (
                                            brokenMedia[att.id] ? (
                                              <a
                                                href={resolveMediaUrl(att.file_url)}
                                                target="_blank"
                                                rel="noreferrer"
                                                className="flex items-center gap-2 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800"
                                              >
                                                <FileText size={16} className="shrink-0" />
                                                <span className="min-w-0 flex-1 truncate">
                                                  Видео не поддерживается в браузере — открыть файл
                                                </span>
                                              </a>
                                            ) : (
                                              <button
                                                type="button"
                                                onClick={() => setMediaPreview({ type: "video", src: resolveMediaUrl(att.file_url), name: att.file_name })}
                                                className="block w-full overflow-hidden rounded-lg"
                                              >
                                                <video
                                                  preload="metadata"
                                                  playsInline
                                                  muted
                                                  src={resolveMediaUrl(att.file_url)}
                                                  width={att.width || undefined}
                                                  height={att.height || undefined}
                                                  className="max-h-64 w-full rounded-lg bg-black"
                                                  onError={() => setBrokenMedia((prev) => ({ ...prev, [att.id]: true }))}
                                                  onLoadedData={() => {
                                                    setBrokenMedia((prev) => ({ ...prev, [att.id]: false }));
                                                    // Корректируем позицию скролла после загрузки видео
                                                    messagesViewportRef.current?.updateScrollPosition();
                                                  }}
                                                />
                                              </button>
                                            )
                                          ) : isAudioAttachment(att) ? (
                                            brokenMedia[att.id] ? (
                                              <a
                                                href={resolveMediaUrl(att.file_url)}
                                                target="_blank"
                                                rel="noreferrer"
                                                className="flex items-center gap-2 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800"
                                              >
                                                <FileText size={16} className="shrink-0" />
                                                <span className="min-w-0 flex-1 truncate">Аудио не поддерживается — открыть файл</span>
                                              </a>
                                            ) : (
                                              <audio
                                                controls
                                                preload="metadata"
                                                className="w-full"
                                                onError={() => setBrokenMedia((prev) => ({ ...prev, [att.id]: true }))}
                                                onCanPlay={() => {
                                                  setBrokenMedia((prev) => ({ ...prev, [att.id]: false }));
                                                  // Корректируем позицию скролла после загрузки аудио
                                                  messagesViewportRef.current?.updateScrollPosition();
                                                }}
                                              >
                                                <source src={resolveMediaUrl(att.file_url)} type={att.mime_type || "audio/mpeg"} />
                                              </audio>
                                            )
                                          ) : (
                                            <a
                                              href={resolveMediaUrl(att.file_url)}
                                              target="_blank"
                                              rel="noreferrer"
                                              className="flex items-center gap-2 rounded-lg border border-gray-200 bg-white/80 px-3 py-2 text-sm text-sky-700 hover:bg-white"
                                            >
                                              <FileText size={16} className="shrink-0" />
                                              <span className="min-w-0 flex-1 truncate">{att.file_name}</span>
                                              <span className="shrink-0 text-xs text-gray-500">{formatFileSize(att.file_size)}</span>
                                            </a>
                                          )}
                                        </div>
                                      ))}
                                    </div>
                                  ) : null}

                                  <p className={`mt-1 text-right text-[11px] ${isMine ? "text-sky-100" : "text-gray-400"}`}>
                                    {messageTime(message)}
                                  </p>

                                  {Object.keys(message.reactions_summary || {}).length > 0 ? (
                                    <div className="mt-2 flex flex-wrap gap-1">
                                      {Object.entries(message.reactions_summary || {}).map(([emoji, meta]) => {
                                        const mine = hasMyReaction(message, emoji);
                                        return (
                                          <button
                                            key={`${message.id}-${emoji}`}
                                            type="button"
                                            onClick={() => handleReact(message, emoji)}
                                            className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs transition ${
                                              mine
                                                ? "bg-sky-100 text-sky-700 ring-1 ring-sky-300"
                                                : "bg-white/80 text-gray-700 ring-1 ring-gray-200 hover:bg-white"
                                            }`}
                                            title="Реакция"
                                          >
                                            <span>{emoji}</span>
                                            <span>{meta.count}</span>
                                          </button>
                                        );
                                      })}
                                    </div>
                                  ) : null}
                                </div>

                              </div>
                            </div>
                          </div>
                          </React.Fragment>
                        );
                      })}
                    </div>
                  )}
                </ScrollableMessageList>

                {/* Кнопка прокрутки вниз */}
                {showScrollToBottom && (
                  <div className="pointer-events-auto absolute bottom-25 right-3 z-20 transition-opacity duration-300">
                    <button
                      type="button"
                      onClick={() => {
                        const container = messagesViewportRef.current?.containerRef?.current;
                        if (container) {
                          container.scrollTop = container.scrollHeight;
                        }
                      }}
                      className="inline-flex h-10 w-10 items-center justify-center rounded-full bg-sky-500 text-white shadow-lg transition hover:bg-sky-600 active:scale-95"
                      title="Вернуться к новым сообщениям"
                      aria-label="Вернуться к новым сообщениям"
                    >
                      <ChevronDown size={18} />
                    </button>
                  </div>
                )}

                <div className="shrink-0 border-t border-gray-100 bg-white pt-3">
                  {/* Индикатор "печатает..." */}
                  {isTyping && (
                    <div className="mb-2 flex items-center gap-2 text-xs text-gray-500 italic">
                      <div className="flex gap-1">
                        <span className="inline-block h-1.5 w-1.5 animate-bounce rounded-full bg-gray-400" style={{ animationDelay: '0ms' }}></span>
                        <span className="inline-block h-1.5 w-1.5 animate-bounce rounded-full bg-gray-400" style={{ animationDelay: '150ms' }}></span>
                        <span className="inline-block h-1.5 w-1.5 animate-bounce rounded-full bg-gray-400" style={{ animationDelay: '300ms' }}></span>
                      </div>
                      <span>Собеседник печатает...</span>
                    </div>
                  )}

                  {editingMessageId ? (
                    <div className="mb-2 flex items-start justify-between gap-2 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800">
                      <div className="min-w-0">
                        <p className="font-semibold">Режим редактирования</p>
                        <p className="truncate">Измените текст сообщения и отправьте</p>
                      </div>
                      <button
                        type="button"
                        onClick={handleCancelEdit}
                        className="rounded-full p-0.5 text-amber-700 hover:bg-amber-100"
                        aria-label="Отменить редактирование"
                      >
                        <X size={12} />
                      </button>
                    </div>
                  ) : null}

                  {replyTo ? (
                    <div className="mb-2 flex items-start justify-between gap-2 rounded-lg border border-sky-100 bg-sky-50 px-3 py-2 text-xs text-sky-800">
                      <div className="min-w-0">
                        <p className="font-semibold">Ответ: {replyTo.author}</p>
                        <p className="truncate">{replyTo.preview}</p>
                      </div>
                      <button
                        type="button"
                        onClick={() => setReplyTo(null)}
                        className="rounded-full p-0.5 text-sky-700 hover:bg-sky-100"
                        aria-label="Отменить ответ"
                      >
                        <X size={12} />
                      </button>
                    </div>
                  ) : null}

                  {attachedFiles.length > 0 ? (
                    <div className="mb-2 flex flex-wrap gap-2">
                      {attachedFiles.map((file, index) => (
                        <span
                          key={`${file.name}-${file.size}-${index}`}
                          className="inline-flex max-w-full items-center gap-1 rounded-full bg-sky-50 px-3 py-1 text-xs text-sky-700 ring-1 ring-sky-100"
                        >
                          <span className="truncate max-w-[180px]">{file.name}</span>
                          <button
                            type="button"
                            onClick={() => removeAttachedFile(index)}
                            className="rounded-full p-0.5 hover:bg-sky-100"
                            aria-label="Удалить файл"
                          >
                            <X size={12} />
                          </button>
                        </span>
                      ))}
                    </div>
                  ) : null}

                  {canSendMessages ? (
                    <div className="flex items-start gap-2">
                      <input
                        ref={fileInputRef}
                        multiple
                        type="file"
                        className="hidden"
                        onChange={handleFilesChange}
                      />
                      <button
                        type="button"
                        onClick={handlePickFiles}
                        disabled={Boolean(editingMessageId)}
                        className="inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-gray-200 bg-white text-gray-600 leading-none transition hover:bg-gray-50 hover:text-sky-700 disabled:cursor-not-allowed disabled:opacity-50"
                        title={editingMessageId ? "При редактировании вложения недоступны" : "Добавить файлы"}
                      >
                        <Paperclip size={15} />
                      </button>

                      <div className="relative w-full" data-composer-emoji="true">
                        <button
                          type="button"
                          onClick={() => {
                            setShowComposerEmojiPicker((prev) => !prev);
                            setExpandedReplyActionForId(null);
                            setActionsMenuAnchor(null);
                            setReactionPickerForMessageId(null);
                          }}
                          className="absolute right-2 top-1/2 -translate-y-1/2 z-10 inline-flex h-6 w-6 items-center justify-center rounded-md text-gray-400 hover:bg-gray-100 hover:text-sky-600"
                          title="Смайлы"
                        >
                          <Smile size={14} />
                        </button>

                        {showComposerEmojiPicker ? (
                          <div className="absolute bottom-full right-0 z-20 mb-2 w-[260px] rounded-lg border border-gray-200 bg-white p-2 shadow-xl">
                            <div className="grid max-h-48 grid-cols-8 gap-1 overflow-y-auto">
                              {ALL_REACTIONS.map((emoji) => (
                                <button
                                  key={`composer-${emoji}`}
                                  type="button"
                                  onClick={() => {
                                    appendEmojiToComposer(emoji);
                                    setShowComposerEmojiPicker(false);
                                  }}
                                  className="inline-flex h-8 w-8 items-center justify-center rounded-md text-base hover:bg-sky-50"
                                >
                                  {emoji}
                                </button>
                              ))}
                            </div>
                          </div>
                        ) : null}

                        <textarea
                          ref={messageInputRef}
                          value={messageText}
                          onChange={(e) => {
                            setMessageText(e.target.value);
                            // Отправляем индикатор "печатает..."
                            sendTyping();
                          }}
                          onClick={() => setShowComposerEmojiPicker(false)}
                          onKeyDown={(e) => {
                            if (e.key === "Enter" && !e.shiftKey) {
                              e.preventDefault();
                              handleSend();
                            }
                          }}
                          rows={1}
                          placeholder={editingMessageId ? "Редактируйте сообщение..." : "Введите сообщение..."}
                          className="w-full resize-none rounded-lg border border-gray-200 bg-white h-9 px-3 py-2 pr-10 text-sm text-gray-900 outline-none ring-0 transition focus:border-sky-500 focus:ring-2 focus:ring-sky-100"
                        />
                      </div>
                      <button
                        type="button"
                        onClick={handleSend}
                        disabled={sending || (editingMessageId ? !messageText.trim() : (!messageText.trim() && attachedFiles.length === 0))}
                        className="inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-sky-500 text-white leading-none transition hover:bg-sky-600 disabled:cursor-not-allowed disabled:opacity-50"
                        title={editingMessageId ? "Сохранить" : "Отправить"}
                      >
                        <Send size={15} />
                      </button>
                    </div>
                  ) : (
                    <div className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-center text-sm text-amber-800">
                      <p className="font-medium">У вас нет прав на отправку сообщений</p>
                      <p className="mt-1 text-xs text-amber-700">
                        {myMembership?.role === 'guest' 
                          ? 'Гости могут только просматривать сообщения и отправлять реакции' 
                          : 'Обратитесь к администратору чата для получения прав'}
                      </p>
                    </div>
                  )}
                </div>
              </div>
            </>
          ) : (
            <div className="flex h-full min-h-[280px] items-center justify-center rounded-xl bg-gray-50 text-center">
              <div>
                <MessageCircle size={20} className="mx-auto mb-2 text-gray-400" />
                <p className="text-sm text-gray-500">Диалог не найден</p>
              </div>
            </div>
          )}
        </section>
        </div>
      )}

      {mediaPreview ? (
        <div
          className="fixed inset-0 z-[100] flex items-center justify-center bg-black/80 p-4"
          onClick={() => setMediaPreview(null)}
        >
          <button
            type="button"
            onClick={() => setMediaPreview(null)}
            className="absolute right-4 top-4 inline-flex h-10 w-10 items-center justify-center rounded-full bg-white/10 text-white hover:bg-white/20"
            aria-label="Закрыть предпросмотр"
          >
            <X size={18} />
          </button>

          <div className="max-h-full max-w-[92vw]" onClick={(e) => e.stopPropagation()}>
            {mediaPreview.type === "image" ? (
              <img src={mediaPreview.src} alt={mediaPreview.name} className="max-h-[88vh] max-w-[92vw] rounded-lg object-contain" />
            ) : (
              <video controls autoPlay className="max-h-[88vh] max-w-[92vw] rounded-lg bg-black" src={mediaPreview.src} />
            )}
          </div>
        </div>
      ) : null}

      {expandedReplyActionForId && actionsMenuAnchor && selectedActionMessage ? (
        <div
          data-actions-menu="true"
          className="fixed z-[60] flex min-w-[176px] flex-col gap-1 rounded-lg border border-gray-200 bg-white p-1 shadow-xl"
          style={{
            left: actionsMenuAnchor.x,
            top: actionsMenuAnchor.y - 6,
            transform: "translate(-100%, -100%)",
          }}
        >
          {selectedActionCanReply ? (
            <div className="mb-1 flex items-center gap-1 rounded-md bg-gray-50 p-1">
              {selectedActionRecentReactions.map((emoji) => (
                <button
                  key={`recent-${emoji}`}
                  type="button"
                  onClick={() => {
                    handleReact(selectedActionMessage, emoji);
                    setExpandedReplyActionForId(null);
                    setActionsMenuAnchor(null);
                  }}
                  className="inline-flex h-7 w-7 items-center justify-center rounded-md bg-white text-base hover:bg-sky-50"
                  title="Быстрая реакция"
                >
                  {emoji}
                </button>
              ))}
              <button
                type="button"
                onClick={() => setReactionPickerForMessageId(selectedActionMessage.id)}
                className="ml-auto inline-flex h-7 w-7 items-center justify-center rounded-md bg-white text-gray-600 hover:bg-sky-50 hover:text-sky-700"
                title="Все смайлы"
              >
                <Smile size={14} />
              </button>
            </div>
          ) : null}

          {selectedActionCanReply ? (
            <button
              type="button"
              onClick={() => handleReplyToMessage(selectedActionMessage)}
              className="inline-flex w-full items-center gap-1 rounded-md border border-sky-200 bg-sky-50 px-2 py-1 text-xs font-medium text-sky-700 hover:bg-sky-100"
            >
              <Reply size={12} />
              Ответить
            </button>
          ) : null}

          {selectedActionCanManage ? (
            <>
              <button
                type="button"
                onClick={() => handleStartEditMessage(selectedActionMessage)}
                className="inline-flex w-full items-center gap-1 rounded-md border border-gray-200 bg-white px-2 py-1 text-xs font-medium text-gray-700 hover:bg-gray-50"
              >
                <Pencil size={12} />
                Редактировать
              </button>

              <button
                type="button"
                onClick={() => handleDeleteMessage(selectedActionMessage)}
                className="inline-flex w-full items-center gap-1 rounded-md border border-red-200 bg-red-50 px-2 py-1 text-xs font-medium text-red-700 hover:bg-red-100"
              >
                <Trash2 size={12} />
                Удалить
              </button>
            </>
          ) : null}
        </div>
      ) : null}

      {reactionPickerForMessageId ? (
        <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/50 p-2 sm:p-4" data-reaction-picker="true">
          <div className="w-full max-w-[95vw] sm:max-w-md rounded-xl sm:rounded-2xl bg-white p-4 sm:p-6 shadow-xl">
            <div className="mb-3 sm:mb-4 flex items-center justify-between">
              <h3 className="text-base sm:text-lg font-semibold text-gray-900">Выберите реакцию</h3>
              <button
                type="button"
                onClick={() => setReactionPickerForMessageId(null)}
                className="rounded-full p-1 hover:bg-gray-100"
                aria-label="Закрыть"
              >
                <X size={18} className="text-gray-600 sm:w-5 sm:h-5" />
              </button>
            </div>
            <div className="grid max-h-[60vh] sm:max-h-[55vh] grid-cols-6 sm:grid-cols-8 gap-1.5 sm:gap-2 overflow-y-auto">
              {ALL_REACTIONS.map((emoji) => (
                <button
                  key={`picker-${emoji}`}
                  type="button"
                  onClick={() => {
                    const msg = messagesById.get(reactionPickerForMessageId);
                    if (msg) {
                      handleReact(msg, emoji);
                    }
                    setReactionPickerForMessageId(null);
                    setExpandedReplyActionForId(null);
                    setActionsMenuAnchor(null);
                  }}
                  className="inline-flex h-9 w-9 items-center justify-center rounded-md text-lg hover:bg-sky-50"
                >
                  {emoji}
                </button>
              ))}
            </div>
          </div>
        </div>
      ) : null}
    </AppShell>
  );
}
