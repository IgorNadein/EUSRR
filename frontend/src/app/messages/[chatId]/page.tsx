"use client";

import React, { useEffect, useLayoutEffect, useMemo, useRef, useState, useCallback } from "react";
import { useParams, usePathname, useRouter, useSearchParams } from "next/navigation";
import { MessageCircle, ChevronDown, ChevronLeft, ChevronRight } from "lucide-react";
import { AppShell } from "../../../components/AppShell";
import ChatDialogHeader from "@/components/messages/ChatDialogHeader";
import ChatMediaPreviewModal from "@/components/messages/ChatMediaPreviewModal";
import ChatMessageItem, { MediaPreview } from "@/components/messages/ChatMessageItem";
import ChatSearchPanel from "@/components/messages/ChatSearchPanel";
import MessageActionsMenu from "@/components/messages/MessageActionsMenu";
import MessageReadersModal from "@/components/messages/MessageReadersModal";
import MessageComposer from "@/components/messages/MessageComposer";
import ReactionPickerModal from "@/components/messages/ReactionPickerModal";
import { apiClient } from "@/lib/api";
import type { ChatMessageSearchResponse, ChatMessageSearchResult, Message } from "@/types/api";
import { useUser } from "@/contexts/UserContext";
import { useChatFallbackSync } from "@/hooks/useChatFallbackSync";
import { useSilentChatReloadGuard } from "@/hooks/useSilentChatReloadGuard";
import { useWebSocket } from "@/hooks/useWebSocket";
import { useChatMessages } from "@/hooks/useChatMessages";
import { useMarkRead } from "@/hooks/useMarkRead";
import { useChatScroll, shiftDateInputValue } from "@/hooks/useChatScroll";
import { mergeDisplayMessages, uniqueMessagesById } from "@/lib/messages/chatUtils";
import { formatDayDivider, getMessageDate, getMessagePreviewText, getReplyToId } from "@/lib/messages/messageUtils";
import wsManager from "@/lib/websocketManager";
import ScrollableMessageList, { ScrollableMessageListInner } from "@/components/ScrollableMessageList";

/* ─── types ─── */

type ReplyTarget = { id: number; author: string; preview: string };
type MessageActionsAnchor = { x: number; y: number };

/* ─── constants ─── */

const RECENT_REACTIONS_KEY = "eusrr_recent_reactions";
const MAX_RECENT_REACTIONS = 5;
const ALL_REACTIONS = [
  "👍","❤️","😂","🔥","👏","🎉","😊","😉","😁","🤝",
  "🙏","😮","😢","😡","💯","✅","👀","🤔","😍","😎",
  "🤩","🥳","😴","🫡","👌","💪","🙌","🧠","💡","🚀",
  "🎯","⭐","✨","💩","🫶","🤗","😅","🤯","🥲","🫠",
];

/* ─── utils ─── */

function uniqueEmoji(items: string[]): string[] {
  const seen = new Set<string>();
  return items.filter(e => { if (!e || seen.has(e)) return false; seen.add(e); return true; });
}

function getMessageDayKey(message: Message): string | null {
  const d = getMessageDate(message);
  return d ? `${d.getFullYear()}-${d.getMonth()}-${d.getDate()}` : null;
}

function formatDateInputValue(date: Date): string {
  return `${date.getFullYear()}-${`${date.getMonth()+1}`.padStart(2,"0")}-${`${date.getDate()}`.padStart(2,"0")}`;
}

/* ─── component ─── */

export default function MessageDialogPage() {
  const params = useParams<{ chatId: string }>();
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const chatId = Number(params.chatId);
  const { user, loading: userLoading } = useUser();
  const { handleReconnectExhausted, resetReloadGuard } = useSilentChatReloadGuard(chatId || null);

  /* ── refs ── */
  const messagesViewportRef = useRef<ScrollableMessageListInner | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const messageInputRef = useRef<HTMLTextAreaElement | null>(null);
  const searchInputRef = useRef<HTMLInputElement | null>(null);
  const highlightTimerRef = useRef<NodeJS.Timeout | null>(null);

  /* ──────────────────────────────────────────────────────
   * HOOK: Chat messages (state, pagination, pending)
   * ────────────────────────────────────────────────────── */
  const cm = useChatMessages({ chatId, userId: user?.id, userLoading });

  /* ──────────────────────────────────────────────────────
   * HOOK: Scroll behavior (floating date, button, etc.)
   * ────────────────────────────────────────────────────── */
  const scroll = useChatScroll({
    chatId,
    messageCount: cm.messages.length + cm.pendingMessages.length,
    viewportRef: messagesViewportRef,
    hasMoreNewerRef: cm.hasMoreNewerRef,
    unreadBelowIdsRef: cm.unreadBelowIdsRef,
    historyNavigationMode: cm.historyNavigationMode,
  });

  // Wire scroll helpers into the messages hook so it can use them
  useEffect(() => {
    cm.isNearBottomRef.current = scroll.isNearBottom;
    cm.scrollToBottomRef.current = scroll.scrollToBottom;
  }, [cm.isNearBottomRef, cm.scrollToBottomRef, scroll.isNearBottom, scroll.scrollToBottom]);

  /* ──────────────────────────────────────────────────────
   * HOOK: Mark-as-read (debounced)
   * ────────────────────────────────────────────────────── */
  const markRead = useMarkRead({
    chatId,
    onReadAcknowledged: useCallback(() => {
      // We intentionally do NOT pull fresh chat/unread_count here.
      // The local newMessagesBelowCount resets only when the user
      // physically scrolls to the bottom (via syncScrollToBottomState).
    }, []),
  });

  // Sync confirmed watermark from chat.last_read_message_id
  useEffect(() => {
    markRead.syncConfirmed(cm.chat?.last_read_message_id ?? 0);
  }, [cm.chat?.last_read_message_id, markRead]);

  /* ── derived state ── */
  const displayMessages = useMemo(() => mergeDisplayMessages(cm.messages, cm.pendingMessages), [cm.messages, cm.pendingMessages]);
  const messagesById = useMemo(() => new Map(displayMessages.map(m => [m.id, m])), [displayMessages]);

  /**
   * Badge count: take the maximum of the server-provided unread_count
   * and locally tracked new-messages-below. This ensures the badge
   * stays visible even after mark-read flushes (until user scrolls down).
   */
  const displayedUnreadCount = Math.max(cm.chat?.unread_count ?? 0, cm.newMessagesBelowCount);

  /* ── UI state ── */
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
  const [isTyping, setIsTyping] = useState(false);
  const typingTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const [isPinned, setIsPinned] = useState(false);
  const [notificationsEnabled, setNotificationsEnabled] = useState(true);
  const [jumpingToDate, setJumpingToDate] = useState(false);
  const [isSearchOpen, setIsSearchOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState<ChatMessageSearchResult[]>([]);
  const [searchTotalCount, setSearchTotalCount] = useState(0);
  const [selectedSearchResultIndex, setSelectedSearchResultIndex] = useState(0);
  const [searchLoading, setSearchLoading] = useState(false);
  const [searchLoadingMore, setSearchLoadingMore] = useState(false);
  const [searchError, setSearchError] = useState<string | null>(null);
  const [nextSearchOffset, setNextSearchOffset] = useState<number | null>(null);
  const [highlightedMessageId, setHighlightedMessageId] = useState<number | null>(null);
  const linkedMessageId = Number(searchParams.get("message") || "");

  // Sync settings from chat
  useEffect(() => {
    if (cm.chat) {
      setIsPinned(cm.chat.is_pinned ?? false);
      setNotificationsEnabled(cm.chat.notifications_enabled ?? true);
    }
  }, [cm.chat]);

  useEffect(() => {
    if (!isSearchOpen) {
      return;
    }

    requestAnimationFrame(() => {
      searchInputRef.current?.focus();
      searchInputRef.current?.select();
    });
  }, [isSearchOpen]);

  /* ── membership & permissions ── */
  const myMembership = useMemo(() => {
    if (!cm.chat?.memberships || !user?.id) return null;
    return cm.chat.memberships.find(m => m.user === user.id) || null;
  }, [cm.chat?.memberships, user?.id]);

  const canSendMessages = useMemo(() => {
    if (!myMembership) return true;
    return myMembership.can_send_messages;
  }, [myMembership]);

  /* ── action menu derived ── */
  const selectedActionMessage = expandedReplyActionForId ? messagesById.get(expandedReplyActionForId) || null : null;
  const selectedActionCanManage = Boolean(
    selectedActionMessage && user?.id && !selectedActionMessage.is_deleted &&
    (selectedActionMessage.author_id === user.id || selectedActionMessage.author?.id === user.id || selectedActionMessage.sender?.id === user.id),
  );
  const selectedActionCanReply = Boolean(selectedActionMessage && !selectedActionMessage.is_deleted);
  const selectedActionRecentReactions = useMemo(() => uniqueEmoji(recentReactions).slice(0, MAX_RECENT_REACTIONS), [recentReactions]);
  const selectedActionReaders = selectedActionMessage?.read_by || [];
  const sendingComposer = Boolean(editingMessageId && sending);

  /* ── reactions ── */
  useEffect(() => {
    try {
      const raw = localStorage.getItem(RECENT_REACTIONS_KEY);
      if (!raw) return;
      const parsed = JSON.parse(raw);
      if (!Array.isArray(parsed)) return;
      const norm = uniqueEmoji(parsed.filter((v): v is string => typeof v === "string")).slice(0, MAX_RECENT_REACTIONS);
      if (norm.length > 0) setRecentReactions(norm);
    } catch { /* ignore */ }
  }, []);

  const pushRecentReaction = (emoji: string) => {
    const next = uniqueEmoji([emoji, ...recentReactions]).slice(0, MAX_RECENT_REACTIONS);
    setRecentReactions(next);
    if (typeof window !== "undefined") localStorage.setItem(RECENT_REACTIONS_KEY, JSON.stringify(next));
  };

  const updateMessageReactionsSummary = useCallback((
    messageId: number,
    summary?: Record<string, { count: number; users?: number[]; user_names?: string[] }>,
  ) => {
    if (!summary) return;
    cm.setMessages(prev => prev.map(m => m.id === messageId ? { ...m, reactions_summary: summary } : m));
  }, [cm]);

  const hasMyReaction = (message: Message, emoji: string): boolean => {
    if (!user?.id) return false;
    return (message.reactions_summary?.[emoji]?.users || []).includes(user.id);
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

  /* ──────────────────────────────────────────────────────
   * WebSocket
   * ────────────────────────────────────────────────────── */
  const { isConnected, sendTyping, handlers } = useWebSocket({
    chatId: chatId || null,
    autoConnect: true,
    onReconnectExhausted: handleReconnectExhausted,
  });

  useEffect(() => {
    if (!chatId || Number.isNaN(chatId)) return;
    wsManager.setActiveChat(chatId);
    return () => { wsManager.clearActiveChat(chatId); };
  }, [chatId]);

  useEffect(() => { if (isConnected) resetReloadGuard(); }, [isConnected, resetReloadGuard]);

  // WS event handler
  useEffect(() => {
    handlers.current.onMessage = (data) => {
      if (data.type === "new_message" && data.message) {
        const newMsg = data.message;
        const isMyMessage = newMsg.author_id === user?.id;
        const wasNearBottom = scroll.isNearBottom();
        cm.removePendingByServer(newMsg);

        if (!isMyMessage && !wasNearBottom) {
          cm.registerNewMessagesBelow([newMsg]);
          scroll.setShowScrollToBottom(true);
        }

        cm.setMessages(prev => {
          if (prev.some(m => m.id === newMsg.id)) return prev;

          if (prev.length > 0 && !isMyMessage) {
            const last = prev[prev.length - 1];
            if (newMsg.id - last.id > 1 && cm.hasMoreNewerRef.current) return prev;
          }

          const updated = [...prev, newMsg];

          setTimeout(() => {
            if (!isMyMessage && wasNearBottom && chatId) markRead.scheduleMarkRead(newMsg.id);
            if (isMyMessage || wasNearBottom) {
              requestAnimationFrame(() => requestAnimationFrame(() => scroll.scrollToBottom(true)));
            }
          }, 0);

          return updated;
        });
      } else if (data.type === "message_edited" && data.message) {
        const edited = data.message;
        cm.setMessages(prev => prev.map(m => m.id === edited.id ? { ...m, ...edited } : m));
      } else if (data.type === "message_deleted") {
        cm.setMessages(prev => prev.filter(m => m.id !== data.message_id));
      } else if (data.type === "typing_start" && data.user_id !== user?.id) {
        setIsTyping(true);
        if (typingTimeoutRef.current) clearTimeout(typingTimeoutRef.current);
        typingTimeoutRef.current = setTimeout(() => setIsTyping(false), 3000);
      } else if (data.type === "typing_stop" && data.user_id !== user?.id) {
        setIsTyping(false);
        if (typingTimeoutRef.current) clearTimeout(typingTimeoutRef.current);
      } else if (data.type === "reaction_added" || data.type === "reaction_removed") {
        if (data.reactions_summary && typeof data.message_id === "number") {
          updateMessageReactionsSummary(data.message_id, data.reactions_summary);
        }
      } else if (data.type === "marked_read" && data.chat_id === chatId && typeof data.last_read_message_id === "number") {
        const lastReadId = data.last_read_message_id;
        const readerId = typeof data.reader_user_id === "number" ? data.reader_user_id : null;

        if (readerId !== null) {
          cm.setMessages(prev =>
            prev.map(m => {
              const aId = m.author_id ?? m.author?.id ?? m.sender?.id;
              if (m.id > lastReadId || aId === readerId || m.is_read) return m;
              return { ...m, is_read: true };
            }),
          );
        }

        if (readerId === null || readerId === user?.id) {
          markRead.syncConfirmed(lastReadId);
          // Refresh chat to get updated unread_count, but do NOT reset local counter
          void apiClient.getChat(chatId).then(fresh => cm.setChat(fresh)).catch(() => {});
        }
      }
    };

    handlers.current.onConnect = () => {
      void cm.syncLatestMessages({ limit: 30, scrollOnSync: scroll.isNearBottom() });
    };
    handlers.current.onDisconnect = () => {};
    handlers.current.onError = (err) => { console.error("❌ WebSocket error:", err); };
  }, [handlers, user?.id, chatId, scroll, cm, markRead, updateMessageReactionsSummary]);

  /* ── cleanup timers ── */
  useEffect(() => () => {
    if (typingTimeoutRef.current) clearTimeout(typingTimeoutRef.current);
    if (highlightTimerRef.current) clearTimeout(highlightTimerRef.current);
  }, []);

  useLayoutEffect(() => {
    if (typeof window === "undefined" || !window.history) return;
    const prev = window.history.scrollRestoration;
    window.history.scrollRestoration = "manual";
    return () => { window.history.scrollRestoration = prev; };
  }, []);

  /* ── anchor scroll ── */
  useEffect(() => {
    const component = messagesViewportRef.current;
    if (cm.messagesLoading || !component?.containerRef?.current || displayMessages.length === 0 || !cm.isInitialScrollPending()) return;

    const viewport = component.containerRef.current;

    if (cm.initialAnchorId) {
      const el = viewport.querySelector(`[data-message-id="${cm.initialAnchorId}"]`) as HTMLElement | null;
      if (el) {
        const cRect = viewport.getBoundingClientRect();
        const eRect = el.getBoundingClientRect();
        viewport.scrollTop = Math.max(0, eRect.top - cRect.top + viewport.scrollTop - viewport.clientHeight / 2 + eRect.height / 2);
        scroll.syncScrollToBottomState();
        cm.markInitialScrollDone();
        return;
      }

      if (typeof cm.initialAnchorIndex === "number" && cm.initialAnchorIndex >= 0) {
        const byIndex = viewport.querySelectorAll("[data-message-id]").item(cm.initialAnchorIndex) as HTMLElement | null;
        if (byIndex) {
          const cRect = viewport.getBoundingClientRect();
          const eRect = byIndex.getBoundingClientRect();
          viewport.scrollTop = Math.max(0, eRect.top - cRect.top + viewport.scrollTop - viewport.clientHeight / 2 + eRect.height / 2);
          scroll.syncScrollToBottomState();
          cm.markInitialScrollDone();
          return;
        }
      }

      // Retry up to 5 times for slow DOM rendering
      if (cm.anchorRetryTick < 5) {
        setTimeout(() => cm.setAnchorRetryTick(v => v + 1), 100);
        return;
      }
    }

    component.scrollToBottom("auto");
    scroll.syncScrollToBottomState();
    cm.markInitialScrollDone();
  }, [cm, displayMessages, scroll]);

  /* ── scroll handler: pagination + mark-read ── */
  useEffect(() => {
    const c = messagesViewportRef.current;
    if (!c?.containerRef?.current) return;
    const viewport = c.containerRef.current;

    const onScroll = () => {
      if (!cm.loadingOlder && !cm.messagesLoading && cm.hasMoreOlder && viewport.scrollTop <= 120) {
        cm.loadOlderMessages();
      }

      const distFromBottom = viewport.scrollHeight - viewport.scrollTop - viewport.clientHeight;
      if (!cm.loadingNewer && !cm.messagesLoading && cm.hasMoreNewer && distFromBottom <= 300) {
        cm.loadNewerMessages();
      }

      const isAtBottom = scroll.syncScrollToBottomState();

      if (isAtBottom && !cm.hasMoreNewer && cm.messages.length > 0) {
        const latest = cm.messages[cm.messages.length - 1];
        markRead.scheduleMarkRead(latest.id);
        cm.resetNewMessagesBelow();
      }
    };

    viewport.addEventListener("scroll", onScroll, { passive: true });
    return () => viewport.removeEventListener("scroll", onScroll);
  }, [cm, markRead, scroll]);

  /* ── fallback sync ── */
  useChatFallbackSync({
    chatId: chatId || null,
    isConnected,
    userLoading,
    hasUser: Boolean(user),
    messagesLoading: cm.messagesLoading,
    hasMessages: cm.messages.length > 0,
    isNearBottom: scroll.isNearBottom,
    syncLatestMessages: cm.syncLatestMessages,
  });

  /* ── composer helpers ── */

  const resetComposerState = useCallback(() => {
    setEditingMessageId(null);
    setMessageText("");
    setReplyTo(null);
    setExpandedReplyActionForId(null);
    setAttachedFiles([]);
    if (fileInputRef.current) fileInputRef.current.value = "";
  }, []);

  const focusMessageInput = () => {
    const input = messageInputRef.current;
    if (!input) return;
    input.focus();
    input.setSelectionRange(input.value.length, input.value.length);
  };

  const appendEmojiToComposer = (emoji: string) => {
    setMessageText(prev => `${prev}${emoji}`);
    requestAnimationFrame(() => focusMessageInput());
  };

  const handleSend = async () => {
    const text = messageText.trim();
    let optimisticLocalId: string | null = null;

    if (!chatId || (editingMessageId && sending)) return;
    if (editingMessageId) { if (!text) return; }
    else if (!text && attachedFiles.length === 0) return;

    const wasNearBottom = scroll.isNearBottom();

    try {
      if (editingMessageId) {
        setSending(true);
        const updated = await apiClient.updateMessage(editingMessageId, text);
        cm.setMessages(prev => prev.map(m => m.id === editingMessageId ? { ...m, ...updated } : m));
        resetComposerState();
      } else {
        const files = [...attachedFiles];
        const replyToId = replyTo?.id;
        const localId = typeof crypto !== "undefined" && typeof crypto.randomUUID === "function"
          ? crypto.randomUUID()
          : `local-${Date.now()}-${Math.random().toString(16).slice(2)}`;
        optimisticLocalId = localId;
        const opt = cm.buildOptimistic(text, files, localId, replyToId);
        cm.addPending(opt);
        cm.schedulePendingTimer(localId);
        resetComposerState();

        const sent = files.length
          ? await apiClient.sendMessageWithFiles(chatId, text, files, replyToId)
          : await apiClient.sendMessage(chatId, text, replyToId);

        cm.removePendingMessage(localId);
        cm.setMessages(prev => uniqueMessagesById([...prev, sent]));

        if (wasNearBottom) requestAnimationFrame(() => scroll.scrollToBottom(false));
        return;
      }

      if (wasNearBottom) requestAnimationFrame(() => scroll.scrollToBottom(false));
    } catch (e) {
      console.error("Ошибка отправки сообщения:", e);
      if (!editingMessageId && optimisticLocalId) cm.markPendingFailed(optimisticLocalId);
    } finally {
      if (editingMessageId) setSending(false);
    }
  };

  /* ── file handling ── */

  const addAttachedFiles = useCallback((files: File[]) => {
    if (editingMessageId || files.length === 0) return;
    setAttachedFiles(prev => [...prev, ...files]);
  }, [editingMessageId]);

  const handleFilesChange = (e: React.ChangeEvent<HTMLInputElement>) => addAttachedFiles(Array.from(e.target.files || []));
  const removeAttachedFile = (index: number) => setAttachedFiles(prev => prev.filter((_, i) => i !== index));
  const handlePickFiles = () => { if (!editingMessageId) fileInputRef.current?.click(); };

  /* ── message actions ── */

  const canManageMessage = (message: Message): boolean => {
    if (!user?.id || message.is_deleted) return false;
    return message.author_id === user.id || message.author?.id === user.id || message.sender?.id === user.id;
  };

  const handleReplyToMessage = (message: Message) => {
    const author = message.author_name || message.author?.last_name || message.sender?.last_name || "Сотрудник";
    setEditingMessageId(null);
    setReplyTo({ id: message.id, author, preview: getMessagePreviewText(message) });
    setExpandedReplyActionForId(null);
    setIsReadersModalOpen(false);
    setActionsMenuAnchor(null);
    requestAnimationFrame(focusMessageInput);
  };

  const handleStartEditMessage = (message: Message) => {
    if (!canManageMessage(message)) return;
    setEditingMessageId(message.id);
    setReplyTo(null);
    setExpandedReplyActionForId(null);
    setMessageText(message.content || "");
    setAttachedFiles([]);
    if (fileInputRef.current) fileInputRef.current.value = "";
    requestAnimationFrame(focusMessageInput);
  };

  const handleCancelEdit = () => { setEditingMessageId(null); setMessageText(""); };

  const handleDeleteMessage = async (message: Message) => {
    if (!canManageMessage(message)) return;
    try {
      await apiClient.deleteMessage(message.id);
      cm.setMessages(prev => prev.map(m => m.id === message.id ? { ...m, content: "", attachments: [], has_attachments: false, is_deleted: true } : m));
      if (replyTo?.id === message.id) setReplyTo(null);
      if (editingMessageId === message.id) { setEditingMessageId(null); setMessageText(""); }
      setExpandedReplyActionForId(null);
      setIsReadersModalOpen(false);
      setActionsMenuAnchor(null);
    } catch (e) {
      console.error("Ошибка удаления сообщения:", e);
    }
  };

  const handleToggleMessageActions = useCallback((messageId: number, anchor: MessageActionsAnchor) => {
    setExpandedReplyActionForId(prev => {
      if (prev === messageId) { setIsReadersModalOpen(false); setActionsMenuAnchor(null); return null; }
      setIsReadersModalOpen(false);
      setReactionPickerForMessageId(null);
      setShowComposerEmojiPicker(false);
      setActionsMenuAnchor(anchor);
      return messageId;
    });
  }, []);

  const handleAttachmentLoad = useCallback((id: number) => {
    setBrokenMedia(prev => ({ ...prev, [id]: false }));
    messagesViewportRef.current?.updateScrollPosition();
  }, []);
  const handleAttachmentError = useCallback((id: number) => { setBrokenMedia(prev => ({ ...prev, [id]: true })); }, []);
  const handleUseOriginalImage = useCallback((id: number) => { setUseOriginalImage(prev => ({ ...prev, [id]: true })); }, []);

  /* ── date navigation ── */

  const handleJumpToDate = useCallback(async (dateValue: string) => {
    if (jumpingToDate) return;
    setJumpingToDate(true);
    scroll.setIsDateNavigatorOpen(false);
    await cm.jumpToDate(dateValue);
    setJumpingToDate(false);
  }, [cm, jumpingToDate, scroll]);

  const handleReturnToNewMessages = useCallback(async () => {
    const c = messagesViewportRef.current?.containerRef?.current;

    if (!cm.hasMoreNewer && !cm.historyNavigationMode) {
      cm.setHistoryNavigationMode(false);
      if (c) c.scrollTop = c.scrollHeight;
      cm.resetNewMessagesBelow();
      return;
    }

    const result = await cm.returnToUnread();
    if (!result) {
      if (c) c.scrollTop = c.scrollHeight;
      cm.setHistoryNavigationMode(false);
      cm.resetNewMessagesBelow();
    } else {
      scroll.setShowScrollToBottom(true);
    }
  }, [cm, scroll]);

  /* ── chat settings toggles ── */

  const handleTogglePin = async () => {
    if (!chatId) return;
    try {
      const resp = await apiClient.togglePinChat(chatId);
      const v = resp.is_pinned ?? !isPinned;
      setIsPinned(v);
      if (cm.chat) cm.setChat({ ...cm.chat, is_pinned: v });
    } catch (e) { console.error("Ошибка переключения закрепления:", e); }
  };

  const handleToggleNotifications = async () => {
    if (!chatId) return;
    try {
      const resp = await apiClient.toggleChatNotifications(chatId);
      const v = resp.notifications_enabled ?? !notificationsEnabled;
      setNotificationsEnabled(v);
      if (cm.chat) cm.setChat({ ...cm.chat, notifications_enabled: v });
    } catch (e) { console.error("Ошибка переключения уведомлений:", e); }
  };

  const openSearchPanel = useCallback(() => {
    setIsSearchOpen(true);
    setExpandedReplyActionForId(null);
    setActionsMenuAnchor(null);
    setReactionPickerForMessageId(null);
    setShowComposerEmojiPicker(false);
    scroll.setIsDateNavigatorOpen(false);
  }, [scroll]);

  const closeSearchPanel = useCallback(() => {
    setIsSearchOpen(false);
    setSearchQuery("");
    setSearchResults([]);
    setSearchTotalCount(0);
    setSelectedSearchResultIndex(0);
    setSearchLoading(false);
    setSearchLoadingMore(false);
    setSearchError(null);
    setNextSearchOffset(null);
  }, []);

  const highlightFoundMessage = useCallback((messageId: number) => {
    if (highlightTimerRef.current) clearTimeout(highlightTimerRef.current);
    setHighlightedMessageId(messageId);
    highlightTimerRef.current = setTimeout(() => {
      setHighlightedMessageId(null);
      highlightTimerRef.current = null;
    }, 2200);
  }, []);

  const clearMessageParam = useCallback(() => {
    if (!searchParams.get("message")) return;
    const nextParams = new URLSearchParams(searchParams.toString());
    nextParams.delete("message");
    router.replace(nextParams.toString() ? `${pathname}?${nextParams.toString()}` : pathname, { scroll: false });
  }, [pathname, router, searchParams]);

  useEffect(() => {
    if (!linkedMessageId) {
      return;
    }

    let cancelled = false;

    void (async () => {
      const jumped = await cm.jumpToMessage(linkedMessageId);
      if (cancelled) {
        return;
      }
      if (jumped) {
        highlightFoundMessage(linkedMessageId);
      }
      clearMessageParam();
    })();

    return () => {
      cancelled = true;
    };
  }, [clearMessageParam, cm.jumpToMessage, highlightFoundMessage, linkedMessageId]);

  const runSearch = useCallback(async (query: string, options?: { append?: boolean; offset?: number }) => {
    const normalizedQuery = query.trim();
    if (!chatId || normalizedQuery.length < 2) {
      setSearchResults([]);
      setSearchTotalCount(0);
      setSelectedSearchResultIndex(0);
      setSearchError(null);
      setNextSearchOffset(null);
      return;
    }

    const append = Boolean(options?.append);
    if (append) {
      setSearchLoadingMore(true);
    } else {
      setSearchLoading(true);
    }
    setSearchError(null);

    try {
      const response: ChatMessageSearchResponse = await apiClient.searchChatMessages(chatId, {
        q: normalizedQuery,
        limit: 20,
        offset: options?.offset ?? 0,
      });

      setSearchTotalCount(response.count);
      setNextSearchOffset(response.next_offset);
      setSearchResults((prev) => {
        if (!append) {
          return response.results;
        }

        const seen = new Set(prev.map((item) => item.message_id));
        const merged = [...prev];
        response.results.forEach((item: ChatMessageSearchResult) => {
          if (!seen.has(item.message_id)) {
            seen.add(item.message_id);
            merged.push(item);
          }
        });
        return merged;
      });

      if (!append) {
        setSelectedSearchResultIndex(0);
      }
    } catch (e) {
      console.error("Ошибка поиска по сообщениям:", e);
      setSearchError("Не удалось выполнить поиск по сообщениям.");
    } finally {
      if (append) {
        setSearchLoadingMore(false);
      } else {
        setSearchLoading(false);
      }
    }
  }, [chatId]);

  useEffect(() => {
    if (!isSearchOpen) {
      return;
    }

    const normalizedQuery = searchQuery.trim();
    if (normalizedQuery.length < 2) {
      setSearchResults([]);
      setSearchTotalCount(0);
      setSelectedSearchResultIndex(0);
      setSearchError(null);
      setNextSearchOffset(null);
      setSearchLoading(false);
      setSearchLoadingMore(false);
      return;
    }

    const timer = setTimeout(() => {
      void runSearch(normalizedQuery, { append: false, offset: 0 });
    }, 250);

    return () => clearTimeout(timer);
  }, [isSearchOpen, runSearch, searchQuery]);

  const handleSelectSearchResult = useCallback(async (index: number) => {
    const result = searchResults[index];
    if (!result) {
      return;
    }

    setSelectedSearchResultIndex(index);
    const jumped = await cm.jumpToMessage(result.message_id);
    if (jumped) {
      highlightFoundMessage(result.message_id);
      setExpandedReplyActionForId(null);
      setActionsMenuAnchor(null);
      setReactionPickerForMessageId(null);
      setIsReadersModalOpen(false);
    }
  }, [cm, highlightFoundMessage, searchResults]);

  const handleJumpToReply = useCallback(async (messageId: number) => {
    if (!messageId) {
      return;
    }

    const jumped = await cm.jumpToMessage(messageId);
    if (jumped) {
      highlightFoundMessage(messageId);
      setExpandedReplyActionForId(null);
      setActionsMenuAnchor(null);
      setReactionPickerForMessageId(null);
      setIsReadersModalOpen(false);
    }
  }, [cm, highlightFoundMessage]);

  const handleSubmitSelectedSearchResult = useCallback(() => {
    if (searchResults.length === 0) {
      return;
    }

    void handleSelectSearchResult(selectedSearchResultIndex);
  }, [handleSelectSearchResult, searchResults.length, selectedSearchResultIndex]);

  const handlePreviousSearchResult = useCallback(() => {
    if (searchResults.length === 0) {
      return;
    }

    const nextIndex = selectedSearchResultIndex <= 0 ? searchResults.length - 1 : selectedSearchResultIndex - 1;
    void handleSelectSearchResult(nextIndex);
  }, [handleSelectSearchResult, searchResults.length, selectedSearchResultIndex]);

  const handleNextSearchResult = useCallback(() => {
    if (searchResults.length === 0) {
      return;
    }

    const nextIndex = selectedSearchResultIndex >= searchResults.length - 1 ? 0 : selectedSearchResultIndex + 1;
    void handleSelectSearchResult(nextIndex);
  }, [handleSelectSearchResult, searchResults.length, selectedSearchResultIndex]);

  const handleLoadMoreSearchResults = useCallback(() => {
    const normalizedQuery = searchQuery.trim();
    if (!normalizedQuery || nextSearchOffset === null || searchLoadingMore) {
      return;
    }

    void runSearch(normalizedQuery, { append: true, offset: nextSearchOffset });
  }, [nextSearchOffset, runSearch, searchLoadingMore, searchQuery]);

  /* ── global click / escape dismissals ── */

  useEffect(() => {
    const onClick = (e: MouseEvent) => {
      const t = e.target as HTMLElement | null;
      if (!t) return;
      if (t.closest("[data-actions-menu='true'],[data-actions-trigger='true'],[data-reaction-picker='true'],.reaction-picker-modal,[data-composer-emoji='true'],[data-date-navigator='true'],[data-date-trigger='true']")) return;
      setExpandedReplyActionForId(null);
      setActionsMenuAnchor(null);
      setReactionPickerForMessageId(null);
      setShowComposerEmojiPicker(false);
      scroll.setIsDateNavigatorOpen(false);
    };
    window.addEventListener("mousedown", onClick);
    return () => window.removeEventListener("mousedown", onClick);
  }, [scroll]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        setMediaPreview(null);
        setExpandedReplyActionForId(null);
        setActionsMenuAnchor(null);
        setReactionPickerForMessageId(null);
        setShowComposerEmojiPicker(false);
        scroll.setIsDateNavigatorOpen(false);
        if (isSearchOpen) closeSearchPanel();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [closeSearchPanel, isSearchOpen, scroll]);

  // Mobile keyboard viewport adjustment
  useEffect(() => {
    const vv = window.visualViewport;
    if (!vv) return;
    let prevH = vv.height;
    const onResize = () => {
      if (vv.height < prevH) requestAnimationFrame(() => messagesViewportRef.current?.scrollToBottom("auto"));
      prevH = vv.height;
    };
    vv.addEventListener("resize", onResize);
    return () => vv.removeEventListener("resize", onResize);
  }, []);

  // Redirect wheel events outside chat container into it
  useEffect(() => {
    const onWheel = (e: WheelEvent) => {
      if (e.defaultPrevented || mediaPreview) return;
      const c = messagesViewportRef.current;
      if (!c?.containerRef?.current) return;
      const v = c.containerRef.current;
      const t = e.target as HTMLElement | null;
      if (
        !t ||
        v.contains(t) ||
        t.closest("[data-overlay-root='true'], [role='dialog'], [aria-modal='true']") ||
        t.closest("textarea,input,button,a,video,audio,[contenteditable='true']")
      ) {
        return;
      }
      e.preventDefault();
      v.scrollTop += e.deltaY;
    };
    window.addEventListener("wheel", onWheel, { passive: false });
    return () => window.removeEventListener("wheel", onWheel);
  }, [mediaPreview]);

  /* ──────────────────────────────────────────────────────
   * RENDER
   * ────────────────────────────────────────────────────── */

  return (
    <AppShell>
      {cm.loading ? (
        <div className="rounded-2xl bg-white p-8 text-center shadow-sm ring-1 ring-gray-100">
          <div className="mb-4 inline-block h-8 w-8 animate-spin rounded-full border-4 border-sky-400 border-t-transparent" />
          <p className="text-sm text-gray-500">Загрузка чатов...</p>
        </div>
      ) : cm.error ? (
        <div className="rounded-2xl bg-red-50 p-6 text-center">
          <p className="text-sm text-red-800">{cm.error}</p>
        </div>
      ) : (
        <div className="min-h-0 h-full lg:sticky lg:top-22 lg:h-[calc(100dvh-7.5rem)]">
        <section className="flex h-full min-h-0 flex-col overflow-hidden lg:bg-white lg:rounded-xl lg:p-4 lg:ring-1 lg:ring-gray-100">
          {cm.chat ? (
            <>
              <ChatDialogHeader
                chat={cm.chat}
                chatId={chatId}
                currentUserId={user?.id}
                isPinned={isPinned}
                notificationsEnabled={notificationsEnabled}
                onTogglePin={handleTogglePin}
                onToggleNotifications={handleToggleNotifications}
                onOpenSearch={openSearchPanel}
              />

              <ChatSearchPanel
                isOpen={isSearchOpen}
                query={searchQuery}
                loading={searchLoading}
                loadingMore={searchLoadingMore}
                error={searchError}
                results={searchResults}
                totalCount={searchTotalCount}
                nextOffset={nextSearchOffset}
                selectedIndex={selectedSearchResultIndex}
                inputRef={searchInputRef}
                onQueryChange={setSearchQuery}
                onClose={closeSearchPanel}
                onPrevious={handlePreviousSearchResult}
                onNext={handleNextSearchResult}
                onSelect={(index) => {
                  void handleSelectSearchResult(index);
                }}
                onLoadMore={handleLoadMoreSearchResults}
                onSubmitSelection={handleSubmitSelectedSearchResult}
              />

              <div className="relative flex min-h-0 flex-1 flex-col overflow-hidden">
                {/* Floating date */}
                {scroll.floatingDate ? (
                  <div className={`absolute left-0 right-0 top-2 z-20 flex justify-center px-3 transition-opacity duration-200 ${scroll.showFloatingDate ? "opacity-100" : "opacity-0"}`}>
                    <button type="button" data-date-trigger="true" onClick={() => scroll.openDateNavigator()} className="inline-block rounded-full bg-white/95 px-3 py-1 text-xs text-gray-500 shadow-sm ring-1 ring-gray-200 backdrop-blur transition hover:bg-white hover:text-gray-700">
                      {scroll.floatingDate}
                    </button>
                  </div>
                ) : null}

                {/* Date navigator panel */}
                {scroll.isDateNavigatorOpen ? (
                  <div data-date-navigator="true" className="absolute left-1/2 top-12 z-30 w-[min(22rem,calc(100%-1.5rem))] -translate-x-1/2 rounded-2xl bg-white p-4 shadow-lg ring-1 ring-gray-200">
                    <p className="text-xs font-semibold uppercase tracking-wide text-gray-400">Перейти к дате</p>
                    <div className="mt-3 flex items-center gap-2">
                      <button type="button" onClick={() => scroll.setSelectedHistoryDate(prev => shiftDateInputValue(prev, -1))} className="inline-flex h-9 w-9 items-center justify-center rounded-lg border border-gray-200 bg-gray-50 text-gray-600 transition hover:bg-gray-100" aria-label="Предыдущий день"><ChevronLeft size={16} /></button>
                      <input type="date" value={scroll.selectedHistoryDate} onChange={e => scroll.setSelectedHistoryDate(e.target.value)} className="h-9 flex-1 rounded-lg border border-gray-200 bg-white px-3 text-sm text-gray-800 outline-none transition focus:border-sky-400 focus:ring-2 focus:ring-sky-100" />
                      <button type="button" onClick={() => scroll.setSelectedHistoryDate(prev => shiftDateInputValue(prev, 1))} className="inline-flex h-9 w-9 items-center justify-center rounded-lg border border-gray-200 bg-gray-50 text-gray-600 transition hover:bg-gray-100" aria-label="Следующий день"><ChevronRight size={16} /></button>
                    </div>
                    <div className="mt-3 flex flex-wrap gap-2">
                      <button type="button" onClick={() => scroll.setSelectedHistoryDate(formatDateInputValue(new Date()))} className="rounded-lg border border-gray-200 bg-gray-50 px-3 py-2 text-sm text-gray-600 transition hover:bg-gray-100">Сегодня</button>
                      <button type="button" onClick={() => scroll.setIsDateNavigatorOpen(false)} className="rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm text-gray-600 transition hover:bg-gray-50">Закрыть</button>
                      <button type="button" onClick={() => void handleJumpToDate(scroll.selectedHistoryDate)} disabled={!scroll.selectedHistoryDate || jumpingToDate} className="ml-auto rounded-lg bg-sky-500 px-3 py-2 text-sm font-medium text-white transition hover:bg-sky-600 disabled:cursor-not-allowed disabled:bg-sky-300">{jumpingToDate ? "Переход..." : "Перейти"}</button>
                    </div>
                  </div>
                ) : null}

                {/* Message list */}
                <ScrollableMessageList
                  ref={messagesViewportRef}
                  autoScrollToBottom={!cm.hasMoreNewer && !cm.historyNavigationMode}
                  autoScrollToBottomOnMount={!cm.hasMoreNewer && !cm.historyNavigationMode}
                  scrollBehavior="smooth"
                  className="min-h-0 flex-1 bg-gray-50 p-3"
                >
                  {cm.messagesLoading ? (
                    <p className="text-center text-sm text-gray-500">Загрузка сообщений...</p>
                  ) : displayMessages.length === 0 ? (
                    <p className="text-center text-sm text-gray-500">Пока нет сообщений. Напишите первым.</p>
                  ) : (
                    <div className="flex min-h-full flex-col justify-end">
                      {cm.loadingOlder ? <p className="mb-3 text-center text-xs text-gray-500">Подгружаем старые сообщения...</p> : null}
                      {displayMessages.map((message, index) => {
                        const replyToId = getReplyToId(message);
                        const repliedMessage = replyToId ? messagesById.get(replyToId) : null;
                        const curDay = getMessageDayKey(message);
                        const prevDay = index > 0 ? getMessageDayKey(displayMessages[index - 1]) : null;
                        const curDate = getMessageDate(message);
                        const showDayDivider = Boolean(curDate && curDay !== prevDay);

                        return (
                          <React.Fragment key={message.id}>
                            {showDayDivider && curDate ? (
                              <div className="mb-3 flex justify-center px-2 pointer-events-none">
                                <button type="button" data-date-trigger="true" onClick={() => scroll.openDateNavigator(formatDateInputValue(curDate))} className="pointer-events-auto inline-block rounded-full bg-white/95 px-3 py-1 text-xs text-gray-500 shadow-sm ring-1 ring-gray-200 backdrop-blur transition hover:bg-white hover:text-gray-700">
                                  {formatDayDivider(curDate)}
                                </button>
                              </div>
                            ) : null}
                            <ChatMessageItem
                              message={message}
                              currentUserId={user?.id}
                              repliedMessage={repliedMessage}
                              isHighlighted={highlightedMessageId === message.id}
                              isActionsOpen={expandedReplyActionForId === message.id}
                              canManage={!message.is_optimistic && canManageMessage(message)}
                              canReply={!message.is_deleted && !message.is_optimistic}
                              brokenMedia={brokenMedia}
                              useOriginalImage={useOriginalImage}
                              onToggleActions={handleToggleMessageActions}
                              onJumpToReply={(messageId) => {
                                void handleJumpToReply(messageId);
                              }}
                              onOpenMediaPreview={setMediaPreview}
                              onAttachmentLoad={handleAttachmentLoad}
                              onAttachmentError={handleAttachmentError}
                              onUseOriginalImage={handleUseOriginalImage}
                              onReact={handleReact}
                              hasMyReaction={hasMyReaction}
                            />
                          </React.Fragment>
                        );
                      })}
                    </div>
                  )}
                </ScrollableMessageList>

                {/* Scroll-to-bottom button */}
                {scroll.showScrollToBottom && (
                  <div className="pointer-events-auto absolute bottom-25 right-3 z-20 transition-opacity duration-300">
                    <button
                      type="button"
                      onClick={() => void handleReturnToNewMessages()}
                      className="relative inline-flex h-10 w-10 items-center justify-center rounded-full bg-sky-500 text-white leading-none shadow-sm shadow-sky-200/70 transition hover:bg-sky-600 active:scale-[0.98] focus:outline-none focus:ring-2 focus:ring-sky-100"
                      title="Вернуться к новым сообщениям"
                      aria-label={displayedUnreadCount > 0 ? `Вернуться к новым сообщениям (${displayedUnreadCount > 99 ? "99+" : displayedUnreadCount})` : "Вернуться к новым сообщениям"}
                    >
                      <ChevronDown size={18} />
                      {displayedUnreadCount > 0 ? (
                        <span className="absolute -right-1 -top-1 inline-flex min-w-5 items-center justify-center rounded-full border border-white bg-rose-500 px-1.5 py-0.5 text-[10px] font-semibold leading-none text-white shadow-sm">
                          {displayedUnreadCount > 99 ? "99+" : displayedUnreadCount}
                        </span>
                      ) : null}
                    </button>
                  </div>
                )}

                {/* Composer area */}
                <div className="shrink-0 border-t border-gray-100 bg-white px-4 pt-3 pb-[calc(env(safe-area-inset-bottom)+0.25rem)] lg:px-0 lg:pb-0">
                  {isTyping && (
                    <div className="mb-2 flex items-center gap-2 text-xs text-gray-500 italic">
                      <div className="flex gap-1">
                        <span className="inline-block h-1.5 w-1.5 animate-bounce rounded-full bg-gray-400" style={{ animationDelay: "0ms" }} />
                        <span className="inline-block h-1.5 w-1.5 animate-bounce rounded-full bg-gray-400" style={{ animationDelay: "150ms" }} />
                        <span className="inline-block h-1.5 w-1.5 animate-bounce rounded-full bg-gray-400" style={{ animationDelay: "300ms" }} />
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
                    onAddFiles={addAttachedFiles}
                    onFilesChange={handleFilesChange}
                    onRemoveFile={removeAttachedFile}
                    onToggleEmojiPicker={() => {
                      setShowComposerEmojiPicker(prev => !prev);
                      setExpandedReplyActionForId(null);
                      setActionsMenuAnchor(null);
                      setReactionPickerForMessageId(null);
                    }}
                    onSelectEmoji={(emoji) => { appendEmojiToComposer(emoji); setShowComposerEmojiPicker(false); }}
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
          onQuickReact={(emoji) => { handleReact(selectedActionMessage, emoji); setExpandedReplyActionForId(null); setIsReadersModalOpen(false); setActionsMenuAnchor(null); }}
          onOpenReactionPicker={() => setReactionPickerForMessageId(selectedActionMessage.id)}
          onShowAllReaders={() => setIsReadersModalOpen(true)}
          onReply={() => handleReplyToMessage(selectedActionMessage)}
          onEdit={() => handleStartEditMessage(selectedActionMessage)}
          onDelete={() => handleDeleteMessage(selectedActionMessage)}
        />
      ) : null}

      {selectedActionMessage ? (
        <MessageReadersModal isOpen={isReadersModalOpen} onClose={() => setIsReadersModalOpen(false)} readers={selectedActionReaders} />
      ) : null}

      {reactionPickerForMessageId ? (
        <ReactionPickerModal
          onClose={() => setReactionPickerForMessageId(null)}
          onSelect={(emoji) => {
            const msg = messagesById.get(reactionPickerForMessageId);
            if (msg) void handleReact(msg, emoji);
            setReactionPickerForMessageId(null);
            setExpandedReplyActionForId(null);
            setActionsMenuAnchor(null);
          }}
        />
      ) : null}
    </AppShell>
  );
}
