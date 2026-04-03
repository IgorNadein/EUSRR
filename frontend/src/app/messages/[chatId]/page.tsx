"use client";

import React, { useEffect, useLayoutEffect, useMemo, useRef, useState, useCallback } from "react";
import { useParams } from "next/navigation";
import { MessageCircle, ChevronDown } from "lucide-react";
import { AppShell } from "../../../components/AppShell";
import ChatDialogHeader from "@/components/messages/ChatDialogHeader";
import ChatMediaPreviewModal from "@/components/messages/ChatMediaPreviewModal";
import ChatMessageItem, { MediaPreview } from "@/components/messages/ChatMessageItem";
import MessageActionsMenu from "@/components/messages/MessageActionsMenu";
import MessageReadersModal from "@/components/messages/MessageReadersModal";
import MessageComposer from "@/components/messages/MessageComposer";
import ReactionPickerModal from "@/components/messages/ReactionPickerModal";
import { apiClient } from "@/lib/api";
import type { Chat, Message } from "@/types/api";
import { useUser } from "@/contexts/UserContext";
import { useChatFallbackSync } from "@/hooks/useChatFallbackSync";
import { useSilentChatReloadGuard } from "@/hooks/useSilentChatReloadGuard";
import { useWebSocket } from "@/hooks/useWebSocket";
import { getMessageTimestamp, mergeDisplayMessages, uniqueMessagesById } from "@/lib/messages/chatUtils";
import { formatDayDivider, getMessagePreviewText, getReplyToId } from "@/lib/messages/messageUtils";
import wsManager from "@/lib/websocketManager";
import ScrollableMessageList, { ScrollableMessageListInner } from "@/components/ScrollableMessageList";

type ReplyTarget = {
  id: number;
  author: string;
  preview: string;
};

type MessageActionsAnchor = {
  x: number;
  y: number;
};

const RECENT_REACTIONS_KEY = "eusrr_recent_reactions";
const MAX_RECENT_REACTIONS = 5;
const PENDING_MESSAGE_DELAY_MS = 8000;
const MARK_READ_DEBOUNCE_MS = 300;
const ALL_REACTIONS = [
  "👍", "❤️", "😂", "🔥", "👏", "🎉", "😊", "😉", "😁", "🤝",
  "🙏", "😮", "😢", "😡", "💯", "✅", "👀", "🤔", "😍", "😎",
  "🤩", "🥳", "😴", "🫡", "👌", "💪", "🙌", "🧠", "💡", "🚀",
  "🎯", "⭐", "✨", "💩", "🫶", "🤗", "😅", "🤯", "🥲", "🫠",
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
  const { handleReconnectExhausted, resetReloadGuard } = useSilentChatReloadGuard(chatId || null);

  const [chat, setChat] = useState<Chat | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [pendingMessages, setPendingMessages] = useState<Message[]>([]);
  const [loading, setLoading] = useState(true);
  const [messagesLoading, setMessagesLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [messageText, setMessageText] = useState("");
  const [sending, setSending] = useState(false);
  const [editingMessageId, setEditingMessageId] = useState<number | null>(null);
  const [replyTo, setReplyTo] = useState<ReplyTarget | null>(null);
  const [expandedReplyActionForId, setExpandedReplyActionForId] = useState<number | null>(null);
  const [actionsMenuAnchor, setActionsMenuAnchor] = useState<{ x: number; y: number } | null>(null);
  const [isReadersModalOpen, setIsReadersModalOpen] = useState(false);
  const [reactionPickerForMessageId, setReactionPickerForMessageId] = useState<number | null>(null);
  const [showComposerEmojiPicker, setShowComposerEmojiPicker] = useState(false);
  const [recentReactions, setRecentReactions] = useState<string[]>(ALL_REACTIONS.slice(0, MAX_RECENT_REACTIONS));
  const [attachedFiles, setAttachedFiles] = useState<File[]>([]);
  const [brokenMedia, setBrokenMedia] = useState<Record<number, boolean>>({});
  const [useOriginalImage, setUseOriginalImage] = useState<Record<number, boolean>>({});
  const [mediaPreview, setMediaPreview] = useState<MediaPreview | null>(null);
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
  const fallbackSyncInFlightRef = useRef(false);
  const pendingTimersRef = useRef<Map<string, NodeJS.Timeout>>(new Map());
  const pendingMessagesRef = useRef<Message[]>([]);
  const localMessageSequenceRef = useRef(0);
  const markReadTimerRef = useRef<NodeJS.Timeout | null>(null);
  const markReadInFlightRef = useRef(false);
  const queuedMarkReadIdRef = useRef<number | null>(null);
  const lastConfirmedMarkReadIdRef = useRef(0);
  
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
  
  const displayMessages = useMemo(() => mergeDisplayMessages(messages, pendingMessages), [messages, pendingMessages]);
  const messagesById = useMemo(() => new Map(displayMessages.map((m) => [m.id, m])), [displayMessages]);

  useEffect(() => {
    pendingMessagesRef.current = pendingMessages;
  }, [pendingMessages]);

  useEffect(() => {
    lastConfirmedMarkReadIdRef.current = Math.max(
      lastConfirmedMarkReadIdRef.current,
      chat?.last_read_message_id ?? 0,
    );
  }, [chat?.last_read_message_id]);

  useEffect(() => {
    if (markReadTimerRef.current) {
      clearTimeout(markReadTimerRef.current);
      markReadTimerRef.current = null;
    }

    markReadInFlightRef.current = false;
    queuedMarkReadIdRef.current = null;
    lastConfirmedMarkReadIdRef.current = chat?.last_read_message_id ?? 0;
  }, [chatId, chat?.last_read_message_id]);
  
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
  const selectedActionReaders = selectedActionMessage?.read_by || [];
  const sendingComposer = Boolean(editingMessageId && sending);

  const clearPendingTimer = useCallback((localId?: string | null) => {
    if (!localId) return;

    const timer = pendingTimersRef.current.get(localId);
    if (timer) {
      clearTimeout(timer);
      pendingTimersRef.current.delete(localId);
    }
  }, []);

  const markPendingAsDelayed = useCallback((localId: string) => {
    setPendingMessages((prev) =>
      prev.map((message) =>
        message.local_id === localId && message.send_state === "pending"
          ? { ...message, send_state: "delayed" }
          : message
      )
    );
  }, []);

  const schedulePendingTimer = useCallback((localId: string) => {
    clearPendingTimer(localId);

    const timer = setTimeout(() => {
      pendingTimersRef.current.delete(localId);
      markPendingAsDelayed(localId);
    }, PENDING_MESSAGE_DELAY_MS);

    pendingTimersRef.current.set(localId, timer);
  }, [clearPendingTimer, markPendingAsDelayed]);

  const removePendingMessage = useCallback((localId?: string | null) => {
    if (!localId) return;

    clearPendingTimer(localId);
    setPendingMessages((prev) => prev.filter((message) => message.local_id !== localId));
  }, [clearPendingTimer]);

  const clearAllPendingTimers = useCallback(() => {
    pendingTimersRef.current.forEach((timer) => clearTimeout(timer));
    pendingTimersRef.current.clear();
  }, []);

  const flushMarkRead = useCallback(async () => {
    if (!chatId || Number.isNaN(chatId) || markReadInFlightRef.current) {
      return;
    }

    const targetMessageId = queuedMarkReadIdRef.current;
    if (typeof targetMessageId !== "number") {
      return;
    }

    if (targetMessageId <= lastConfirmedMarkReadIdRef.current) {
      queuedMarkReadIdRef.current = null;
      return;
    }

    queuedMarkReadIdRef.current = null;
    markReadInFlightRef.current = true;

    try {
      await apiClient.markChatAsRead(chatId, targetMessageId);
      lastConfirmedMarkReadIdRef.current = Math.max(
        lastConfirmedMarkReadIdRef.current,
        targetMessageId,
      );
      setChat((prev) =>
        prev
          ? {
              ...prev,
              last_read_message_id: Math.max(prev.last_read_message_id ?? 0, targetMessageId),
            }
          : prev
      );
    } catch (error) {
      console.error("Ошибка отложенной отметки прочтения:", error);
      queuedMarkReadIdRef.current = Math.max(
        queuedMarkReadIdRef.current ?? 0,
        targetMessageId,
      );
    } finally {
      markReadInFlightRef.current = false;

      if (
        queuedMarkReadIdRef.current !== null &&
        queuedMarkReadIdRef.current > lastConfirmedMarkReadIdRef.current &&
        !markReadTimerRef.current
      ) {
        markReadTimerRef.current = setTimeout(() => {
          markReadTimerRef.current = null;
          void flushMarkRead();
        }, MARK_READ_DEBOUNCE_MS);
      }
    }
  }, [chatId]);

  const scheduleMarkRead = useCallback((messageId?: number | null) => {
    if (!chatId || typeof messageId !== "number") {
      return;
    }

    const nextTarget = Math.max(queuedMarkReadIdRef.current ?? 0, messageId);
    if (nextTarget <= lastConfirmedMarkReadIdRef.current) {
      return;
    }

    queuedMarkReadIdRef.current = nextTarget;

    if (markReadInFlightRef.current) {
      return;
    }

    if (markReadTimerRef.current) {
      clearTimeout(markReadTimerRef.current);
    }

    markReadTimerRef.current = setTimeout(() => {
      markReadTimerRef.current = null;
      void flushMarkRead();
    }, MARK_READ_DEBOUNCE_MS);
  }, [chatId, flushMarkRead]);

  const getCurrentUserDisplayName = useCallback(() => {
    if (!user) return "Вы";

    const fullName = [user.last_name, user.first_name, user.patronymic].filter(Boolean).join(" ").trim();
    return fullName || user.email || "Вы";
  }, [user]);

  const guessAttachmentType = useCallback((file: File): string => {
    const mime = (file.type || "").toLowerCase();
    if (mime.startsWith("image/")) return "image";
    if (mime.startsWith("video/")) return "video";
    if (mime.startsWith("audio/")) return "audio";
    return "file";
  }, []);

  const getAttachmentSignature = useCallback((message: Message) => {
    return (message.attachments || [])
      .map((attachment) => `${attachment.file_name}|${attachment.file_size ?? 0}|${attachment.mime_type ?? ""}`)
      .sort()
      .join("||");
  }, []);

  const findMatchingPendingLocalId = useCallback((confirmedMessage: Message) => {
    if (!user?.id || confirmedMessage.author_id !== user.id) {
      return null;
    }

    const confirmedReplyToId = getReplyToId(confirmedMessage) ?? null;
    const confirmedAttachmentSignature = getAttachmentSignature(confirmedMessage);
    const confirmedTimestamp = getMessageTimestamp(confirmedMessage);

    const candidates = pendingMessagesRef.current
      .filter((pending) => pending.author_id === user.id)
      .filter((pending) => pending.content === confirmedMessage.content)
      .filter((pending) => (getReplyToId(pending) ?? null) === confirmedReplyToId)
      .filter((pending) => getAttachmentSignature(pending) === confirmedAttachmentSignature)
      .map((pending) => ({
        localId: pending.local_id ?? null,
        diff: Math.abs(getMessageTimestamp(pending) - confirmedTimestamp),
      }))
      .filter((candidate) => Boolean(candidate.localId))
      .sort((left, right) => left.diff - right.diff);

    const matchedCandidate = candidates[0];
    if (!matchedCandidate) {
      return null;
    }

    if (confirmedTimestamp > 0 && matchedCandidate.diff > 10 * 60 * 1000) {
      return null;
    }

    return matchedCandidate.localId;
  }, [getAttachmentSignature, user?.id]);

  const removePendingMessageByServerMessage = useCallback((confirmedMessage: Message) => {
    const localId = findMatchingPendingLocalId(confirmedMessage);
    if (!localId) {
      return;
    }

    removePendingMessage(localId);
  }, [findMatchingPendingLocalId, removePendingMessage]);

  const buildOptimisticMessage = useCallback((text: string, files: File[], localId: string): Message => {
    localMessageSequenceRef.current += 1;
    const now = Date.now() + localMessageSequenceRef.current;

    return {
      id: -now,
      chat: chatId,
      local_id: localId,
      author_id: user?.id,
      author_name: getCurrentUserDisplayName(),
      avatar: user?.avatar,
      content: text,
      is_read: false,
      send_state: "pending",
      is_optimistic: true,
      created_at: new Date(now).toISOString(),
      created_ts: now,
      has_attachments: files.length > 0,
      attachments: files.map((file, index) => ({
        id: -(now * 100 + index),
        file_name: file.name,
        file_type: guessAttachmentType(file),
        file_url: "",
        file_size: file.size,
        mime_type: file.type,
        is_local: true,
      })),
      reply_to_id: replyTo?.id,
    };
  }, [chatId, getCurrentUserDisplayName, guessAttachmentType, replyTo?.id, user?.avatar, user?.id]);

  const resetComposerState = useCallback(() => {
    setEditingMessageId(null);
    setMessageText("");
    setReplyTo(null);
    setExpandedReplyActionForId(null);
    setAttachedFiles([]);
    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
  }, []);

  // WebSocket для real-time обновлений
  const { isConnected, sendTyping, handlers } = useWebSocket({ 
    chatId: chatId || null,
    autoConnect: true,
    onReconnectExhausted: handleReconnectExhausted,
  });

  useEffect(() => {
    if (!chatId || Number.isNaN(chatId)) {
      return;
    }

    wsManager.setActiveChat(chatId);

    return () => {
      wsManager.clearActiveChat(chatId);
    };
  }, [chatId]);

  useEffect(() => {
    if (!isConnected) {
      return;
    }

    resetReloadGuard();
  }, [isConnected, resetReloadGuard]);

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

  const syncLatestMessages = useCallback(async (
    options: { limit?: number; scrollOnSync?: boolean } = {}
  ) => {
    if (
      !chatId ||
      Number.isNaN(chatId) ||
      messagesLoading ||
      messages.length === 0 ||
      fallbackSyncInFlightRef.current
    ) {
      return;
    }

    const newestMessage = messages[messages.length - 1];
    const shouldMarkRead = isNearBottom();

    fallbackSyncInFlightRef.current = true;

    try {
      const response = await apiClient.getChatMessages(chatId, {
        limit: options.limit ?? 20,
        after_id: newestMessage.id,
        mark_read: false,
      });

      const newerMessages = response.messages || [];
      if (newerMessages.length > 0) {
        newerMessages.forEach(removePendingMessageByServerMessage);
        setMessages((prev) => uniqueMessagesById([...prev, ...newerMessages]));

        if (shouldMarkRead) {
          const lastLoadedMessage = newerMessages[newerMessages.length - 1];
          scheduleMarkRead(lastLoadedMessage.id);
        }

        if (shouldMarkRead && options.scrollOnSync) {
          requestAnimationFrame(() => {
            scrollToBottom(false);
          });
        }
      }

      setHasMoreNewer(Boolean(response.has_more));
    } catch (e) {
      console.error("Ошибка тихой синхронизации сообщений:", e);
    } finally {
      fallbackSyncInFlightRef.current = false;
    }
  }, [chatId, isNearBottom, messages, messagesLoading, removePendingMessageByServerMessage, scheduleMarkRead, scrollToBottom]);

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
        if (!data.message) {
          return;
        }

        const newMsg = data.message;
        const isMyMessage = newMsg.author_id === user?.id;
        const wasNearBottom = isNearBottom();
        removePendingMessageByServerMessage(newMsg);
        
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
              scheduleMarkRead(newMsg.id);
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
        if (!data.message) {
          return;
        }

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
        if (data.reactions_summary && typeof data.message_id === 'number') {
          updateMessageReactionsSummary(data.message_id, data.reactions_summary);
        }
      }
      else if (data.type === 'reaction_removed') {
        // Реакция удалена
        if (data.reactions_summary && typeof data.message_id === 'number') {
          updateMessageReactionsSummary(data.message_id, data.reactions_summary);
        }
      }
      else if (data.type === 'marked_read' && data.chat_id === chatId && typeof data.last_read_message_id === 'number') {
        const lastReadMessageId = data.last_read_message_id;
        const readerUserId = typeof data.reader_user_id === 'number' ? data.reader_user_id : null;

        if (readerUserId !== null) {
          setMessages((prev) =>
            prev.map((message) => {
              const authorId = message.author_id ?? message.author?.id ?? message.sender?.id;
              if (message.id > lastReadMessageId || authorId === readerUserId || message.is_read) {
                return message;
              }

              return {
                ...message,
                is_read: true,
              };
            })
          );
        }

        if (readerUserId === null || readerUserId === user?.id) {
          lastConfirmedMarkReadIdRef.current = Math.max(
            lastConfirmedMarkReadIdRef.current,
            lastReadMessageId,
          );
          setChat((prev) =>
            prev
              ? {
                  ...prev,
                  last_read_message_id: Math.max(prev.last_read_message_id ?? 0, lastReadMessageId),
                }
              : prev
          );
        }
      }
    };

    handlers.current.onConnect = () => {
      void syncLatestMessages({
        limit: 30,
        scrollOnSync: isNearBottom(),
      });
    };

    handlers.current.onDisconnect = () => {
      // WebSocket отключен
    };

    handlers.current.onError = (error) => {
      console.error('❌ WebSocket error:', error);
    };
  }, [handlers, user?.id, chatId, isNearBottom, removePendingMessageByServerMessage, scheduleMarkRead, scrollToBottom, syncLatestMessages, updateMessageReactionsSummary]);

  // Очистка таймаута при размонтировании
  useEffect(() => {
    return () => {
      if (typingTimeoutRef.current) {
        clearTimeout(typingTimeoutRef.current);
      }
      if (floatingDateTimeoutRef.current) {
        clearTimeout(floatingDateTimeoutRef.current);
      }
      if (markReadTimerRef.current) {
        clearTimeout(markReadTimerRef.current);
      }
      clearAllPendingTimers();
    };
  }, [clearAllPendingTimers]);

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
      } catch {
        setChat(null);
        setError("Не удалось загрузить чат. Проверьте подключение и попробуйте снова.");
      } finally {
        setLoading(false);
      }
    }

    loadChats();
  }, [chatId, userLoading, user, user?.id]);

  useEffect(() => {
    async function loadMessages() {
      if (!chatId || Number.isNaN(chatId)) {
        clearAllPendingTimers();
        setMessages([]);
        setPendingMessages([]);
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
          clearAllPendingTimers();
          const normalized = uniqueMessagesById(aroundMessages);
          setMessages(normalized);
          setPendingMessages([]);
          // fallback на случай, если API не вернул флаг has_more_before
          setHasMoreOlder(
            typeof around.has_more_before === "boolean" ? around.has_more_before : normalized.length >= 50
          );
          setHasMoreNewer(Boolean(around.has_more_after));
          setInitialAnchorId(around.anchor_id ?? null);
          setInitialAnchorIndex(typeof around.anchor_index === "number" ? around.anchor_index : null);
          setAllowOneOlderProbe(Boolean(around.anchor_id));
        } else {
          clearAllPendingTimers();
          const response = await apiClient.getChatMessages(chatId, { limit: 50 });
          setMessages(uniqueMessagesById(response.messages || []));
          setPendingMessages([]);
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
      } catch (error: unknown) {
        const errorMessage = error instanceof Error ? error.message : String(error);
        if (errorMessage.includes("403")) {
          setError("Нет доступа к этому чату");
          clearAllPendingTimers();
          setMessages([]);
          setPendingMessages([]);
        } else {
          console.error("Ошибка загрузки сообщений:", error);
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
  }, [chatId, clearAllPendingTimers, userLoading, user, user?.id]);

  // Скролл к якорю или вниз после загрузки сообщений
  // Anchor scroll используется при переходе по прямой ссылке на сообщение (например, из уведомления)
  useEffect(() => {
    const component = messagesViewportRef.current;
    if (messagesLoading || !component || !component.containerRef?.current || displayMessages.length === 0 || initialScrolledRef.current) return;

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
    displayMessages,
    initialAnchorId,
    initialAnchorIndex,
    anchorRetryTick,
  ]);

  // Удалено: prependAdjustRef useLayoutEffect
  // ScrollableMessageList уже корректирует позицию автоматически через getSnapshotBeforeUpdate
  // Дублирующая корректировка вызывала "подергивание" при загрузке старых сообщений

  const loadOlderMessages = useCallback(async () => {
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
  }, [allowOneOlderProbe, chatId, hasMoreOlder, loadingOlder, messages, messagesLoading]);

  const loadNewerMessages = useCallback(async () => {
    if (!chatId || Number.isNaN(chatId) || loadingNewer || messagesLoading || !hasMoreNewer || messages.length === 0) {
      return;
    }

    const newestMessage = messages[messages.length - 1];
    const shouldMarkRead = isNearBottom();

    try {
      setLoadingNewer(true);
      const response = await apiClient.getChatMessages(chatId, {
        limit: 10,  // Ограничено для минимальной погрешности автоотметки (было 40)
        after_id: newestMessage.id,
        mark_read: false,
      });

      const newerMessages = response.messages || [];
      if (newerMessages.length > 0) {
        newerMessages.forEach(removePendingMessageByServerMessage);
        setMessages((prev) => uniqueMessagesById([...prev, ...newerMessages]));

        if (shouldMarkRead) {
          const lastLoadedMessage = newerMessages[newerMessages.length - 1];
          scheduleMarkRead(lastLoadedMessage.id);
        }
        
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
  }, [chatId, hasMoreNewer, isNearBottom, loadingNewer, messages, messagesLoading, removePendingMessageByServerMessage, scheduleMarkRead]);

  useChatFallbackSync({
    chatId: chatId || null,
    isConnected,
    userLoading,
    hasUser: Boolean(user),
    messagesLoading,
    hasMessages: messages.length > 0,
    isNearBottom,
    syncLatestMessages,
  });

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

      if (isAtBottom && !hasMoreNewer && messages.length > 0) {
        const latestLoadedMessage = messages[messages.length - 1];
        scheduleMarkRead(latestLoadedMessage.id);
      }
    };

    viewport.addEventListener("scroll", onScroll, { passive: true });
    return () => viewport.removeEventListener("scroll", onScroll);
  }, [chatId, displayMessages, hasMoreOlder, hasMoreNewer, isNearBottom, loadNewerMessages, loadOlderMessages, loadingOlder, loadingNewer, messages, messagesLoading, scheduleMarkRead]);

  const handleSend = async () => {
    const text = messageText.trim();
    let optimisticLocalId: string | null = null;

    if (!chatId || (editingMessageId && sending)) return;
    if (editingMessageId) {
      if (!text) return;
    } else if (!text && attachedFiles.length === 0) {
      return;
    }

    // Запоминаем позицию ДО отправки
    const wasNearBottom = isNearBottom();

    try {
      if (editingMessageId) {
        setSending(true);
        const updated = await apiClient.updateMessage(editingMessageId, text);
        setMessages((prev) => prev.map((m) => (m.id === editingMessageId ? { ...m, ...updated } : m)));
        resetComposerState();
      } else {
        const files = [...attachedFiles];
        const replyToId = replyTo?.id;
        const localId = typeof crypto !== "undefined" && typeof crypto.randomUUID === "function"
          ? crypto.randomUUID()
          : `local-${Date.now()}-${Math.random().toString(16).slice(2)}`;
        optimisticLocalId = localId;
        const optimisticMessage = buildOptimisticMessage(text, files, localId);

        setPendingMessages((prev) => [...prev, optimisticMessage]);
        schedulePendingTimer(localId);
        resetComposerState();

        const sent = files.length
          ? await apiClient.sendMessageWithFiles(chatId, text, files, replyToId)
          : await apiClient.sendMessage(chatId, text, replyToId);

        removePendingMessage(localId);
        setMessages((prev) => uniqueMessagesById([...prev, sent]));
        setHasMoreNewer(false);

        if (wasNearBottom) {
          requestAnimationFrame(() => {
            scrollToBottom(false);
          });
        }
        return;
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
      if (!editingMessageId && optimisticLocalId) {
        clearPendingTimer(optimisticLocalId);
        setPendingMessages((prev) =>
          prev.map((message) =>
            message.local_id === optimisticLocalId
              ? { ...message, send_state: "failed" }
              : message
          )
        );
      }
    } finally {
      if (editingMessageId) {
        setSending(false);
      }
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
    setIsReadersModalOpen(false);
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
      setIsReadersModalOpen(false);
      setActionsMenuAnchor(null);
    } catch (e) {
      console.error("Ошибка удаления сообщения:", e);
    }
  };

  const handleToggleMessageActions = useCallback((messageId: number, anchor: MessageActionsAnchor) => {
    setExpandedReplyActionForId((prev) => {
      if (prev === messageId) {
        setIsReadersModalOpen(false);
        setActionsMenuAnchor(null);
        return null;
      }

      setIsReadersModalOpen(false);
      setReactionPickerForMessageId(null);
      setShowComposerEmojiPicker(false);
      setActionsMenuAnchor(anchor);
      return messageId;
    });
  }, []);

  const handleAttachmentLoad = useCallback((attachmentId: number) => {
    setBrokenMedia((prev) => ({ ...prev, [attachmentId]: false }));
    messagesViewportRef.current?.updateScrollPosition();
  }, []);

  const handleAttachmentError = useCallback((attachmentId: number) => {
    setBrokenMedia((prev) => ({ ...prev, [attachmentId]: true }));
  }, []);

  const handleUseOriginalImage = useCallback((attachmentId: number) => {
    setUseOriginalImage((prev) => ({ ...prev, [attachmentId]: true }));
  }, []);

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
      if (target.closest(".reaction-picker-modal")) return;
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
        <section className="flex h-full min-h-0 flex-col overflow-hidden lg:bg-white lg:rounded-2xl lg:p-5 lg:shadow-sm lg:ring-1 lg:ring-gray-100">
          {chat ? (
            <>
              <ChatDialogHeader
                chat={chat}
                chatId={chatId}
                currentUserId={user?.id}
                isPinned={isPinned}
                notificationsEnabled={notificationsEnabled}
                onTogglePin={handleTogglePin}
                onToggleNotifications={handleToggleNotifications}
              />

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
                  ) : displayMessages.length === 0 ? (
                    <p className="text-center text-sm text-gray-500">Пока нет сообщений. Напишите первым.</p>
                  ) : (
                    <div className="flex min-h-full flex-col justify-end">
                      {loadingOlder ? (
                        <p className="mb-3 text-center text-xs text-gray-500">Подгружаем старые сообщения...</p>
                      ) : null}
                      {displayMessages.map((message) => {
                        const replyToId = getReplyToId(message);
                        const repliedMessage = replyToId ? messagesById.get(replyToId) : null;

                        return (
                          <ChatMessageItem
                            key={message.id}
                            message={message}
                            currentUserId={user?.id}
                            repliedMessage={repliedMessage}
                            isActionsOpen={expandedReplyActionForId === message.id}
                            canManage={!message.is_optimistic && canManageMessage(message)}
                            canReply={!message.is_deleted && !message.is_optimistic}
                            brokenMedia={brokenMedia}
                            useOriginalImage={useOriginalImage}
                            onToggleActions={handleToggleMessageActions}
                            onOpenMediaPreview={setMediaPreview}
                            onAttachmentLoad={handleAttachmentLoad}
                            onAttachmentError={handleAttachmentError}
                            onUseOriginalImage={handleUseOriginalImage}
                            onReact={handleReact}
                            hasMyReaction={hasMyReaction}
                          />
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

                  <MessageComposer
                    canSendMessages={canSendMessages}
                    membershipRole={myMembership?.role}
                    editingMessageId={editingMessageId}
                    replyTo={replyTo}
                    attachedFiles={attachedFiles}
                    messageText={messageText}
                    sending={sendingComposer}
                    showEmojiPicker={showComposerEmojiPicker}
                    allReactions={ALL_REACTIONS}
                    fileInputRef={fileInputRef}
                    messageInputRef={messageInputRef}
                    onPickFiles={handlePickFiles}
                    onFilesChange={handleFilesChange}
                    onRemoveFile={removeAttachedFile}
                    onToggleEmojiPicker={() => {
                      setShowComposerEmojiPicker((prev) => !prev);
                      setExpandedReplyActionForId(null);
                      setActionsMenuAnchor(null);
                      setReactionPickerForMessageId(null);
                    }}
                    onSelectEmoji={(emoji) => {
                      appendEmojiToComposer(emoji);
                      setShowComposerEmojiPicker(false);
                    }}
                    onInputClick={() => setShowComposerEmojiPicker(false)}
                    onChangeMessage={setMessageText}
                    onTyping={sendTyping}
                    onSend={handleSend}
                    onCancelEdit={handleCancelEdit}
                    onCancelReply={() => setReplyTo(null)}
                  />
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

      {mediaPreview ? <ChatMediaPreviewModal preview={mediaPreview} onClose={() => setMediaPreview(null)} /> : null}

      {expandedReplyActionForId && actionsMenuAnchor && selectedActionMessage ? (
        <MessageActionsMenu
          anchor={actionsMenuAnchor}
          currentUserId={user?.id}
          message={selectedActionMessage}
          canReply={selectedActionCanReply}
          canManage={selectedActionCanManage}
          recentReactions={selectedActionRecentReactions}
          onQuickReact={(emoji) => {
            handleReact(selectedActionMessage, emoji);
            setExpandedReplyActionForId(null);
            setIsReadersModalOpen(false);
            setActionsMenuAnchor(null);
          }}
          onOpenReactionPicker={() => setReactionPickerForMessageId(selectedActionMessage.id)}
          onShowAllReaders={() => setIsReadersModalOpen(true)}
          onReply={() => handleReplyToMessage(selectedActionMessage)}
          onEdit={() => handleStartEditMessage(selectedActionMessage)}
          onDelete={() => handleDeleteMessage(selectedActionMessage)}
        />
      ) : null}

      {selectedActionMessage ? (
        <MessageReadersModal
          isOpen={isReadersModalOpen}
          onClose={() => setIsReadersModalOpen(false)}
          readers={selectedActionReaders}
        />
      ) : null}

      {reactionPickerForMessageId ? (
        <ReactionPickerModal
          onClose={() => setReactionPickerForMessageId(null)}
          onSelect={(emoji) => {
            const message = messagesById.get(reactionPickerForMessageId);
            if (message) {
              void handleReact(message, emoji);
            }
            setReactionPickerForMessageId(null);
            setExpandedReplyActionForId(null);
            setActionsMenuAnchor(null);
          }}
        />
      ) : null}
    </AppShell>
  );
}
