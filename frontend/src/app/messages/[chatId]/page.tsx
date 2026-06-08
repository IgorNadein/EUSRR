"use client";

import React, { Suspense, useEffect, useLayoutEffect, useMemo, useRef, useState, useCallback } from "react";
import { useParams, usePathname, useRouter, useSearchParams } from "next/navigation";
import { MessageCircle, ChevronDown, ChevronLeft, ChevronRight } from "lucide-react";
import { AppShell } from "../../../components/AppShell";
import ChatDialogHeader from "@/components/messages/ChatDialogHeader";
import ChatMediaPreviewModal from "@/components/messages/ChatMediaPreviewModal";
import ChatMessageItem, { MediaPreview } from "@/components/messages/ChatMessageItem";
import ChatSearchPanel from "@/components/messages/ChatSearchPanel";
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
type TypingUser = { id: number; name: string };
/* ─── constants ─── */

const RECENT_REACTIONS_KEY = "eusrr_recent_reactions";
const MAX_RECENT_REACTIONS = 5;
const TYPING_INDICATOR_TIMEOUT_MS = 3000;
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

function formatTypingIndicatorText(users: TypingUser[]): string {
  if (users.length === 0) return "";
  if (users.length === 1) return `${users[0].name} печатает...`;

  const additionalCount = users.length - 1;
  const additionalLabel = additionalCount === 1 ? "человек" : "человека";
  return `${users[0].name} и ещё ${additionalCount} ${additionalLabel} печатают...`;
}

/* ─── component ─── */

export default function MessageDialogPage() {
  return (
    <Suspense fallback={<MessageDialogPageFallback />}>
      <MessageDialogPageContent />
    </Suspense>
  );
}

function MessageDialogPageFallback() {
  return (
    <AppShell>
      <section className="app-surface rounded-2xl p-6 text-center">
        <div className="inline-block h-5 w-5 animate-spin rounded-full border-2 border-[var(--border-subtle)] border-t-[var(--accent-primary)]"></div>
        <p className="app-text-muted mt-3 text-sm">Загрузка чата...</p>
      </section>
    </AppShell>
  );
}

function MessageDialogPageContent() {
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
  const pendingRetryFilesRef = useRef<Map<string, File[]>>(new Map());

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
  const unreadDividerMessageId = useMemo(() => {
    if (cm.newMessagesBelowCount <= 0) {
      return null;
    }

    const unreadBelowIds = cm.unreadBelowIdsRef.current;
    if (!unreadBelowIds || unreadBelowIds.size === 0) {
      return null;
    }

    const firstUnreadIncoming = displayMessages.find((message) => unreadBelowIds.has(message.id));
    return firstUnreadIncoming?.id ?? null;
  }, [cm.newMessagesBelowCount, cm.unreadBelowIdsRef, displayMessages]);

  /**
   * Badge count: take the maximum of the server-provided unread_count
   * and locally tracked new-messages-below. This ensures the badge
   * stays visible even after mark-read flushes (until user scrolls down).
   */
  const displayedUnreadCount = Math.max(cm.chat?.unread_count ?? 0, cm.newMessagesBelowCount);
  const {
    allowOneOlderProbe: cmAllowOneOlderProbe,
    hasMoreOlder: cmHasMoreOlder,
    jumpToMessage: cmJumpToMessage,
    loadOlderMessages: cmLoadOlderMessages,
    loadingOlder: cmLoadingOlder,
    messagesLoading: cmMessagesLoading,
  } = cm;

  /* ── UI state ── */
  const [messageText, setMessageText] = useState("");
  const [sending, setSending] = useState(false);
  const [retryingLocalIds, setRetryingLocalIds] = useState<Set<string>>(() => new Set());
  const [editingMessageId, setEditingMessageId] = useState<number | null>(null);
  const [replyTo, setReplyTo] = useState<ReplyTarget | null>(null);
  const [expandedReplyActionForId, setExpandedReplyActionForId] = useState<number | null>(null);
  const [isReadersModalOpen, setIsReadersModalOpen] = useState(false);
  const [reactionPickerForMessageId, setReactionPickerForMessageId] = useState<number | null>(null);
  const [showComposerEmojiPicker, setShowComposerEmojiPicker] = useState(false);
  const [recentReactions, setRecentReactions] = useState<string[]>(ALL_REACTIONS.slice(0, MAX_RECENT_REACTIONS));
  const [attachedFiles, setAttachedFiles] = useState<File[]>([]);
  const [brokenMedia, setBrokenMedia] = useState<Record<number, boolean>>({});
  const [useOriginalImage, setUseOriginalImage] = useState<Record<number, boolean>>({});
  const [mediaPreview, setMediaPreview] = useState<MediaPreview | null>(null);
  const [typingUsers, setTypingUsers] = useState<TypingUser[]>([]);
  const typingTimeoutsRef = useRef<Map<number, NodeJS.Timeout>>(new Map());
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
    setTypingUsers([]);
    typingTimeoutsRef.current.forEach(timeout => clearTimeout(timeout));
    typingTimeoutsRef.current.clear();
  }, [chatId]);

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
  const selectedActionRecentReactions = useMemo(() => uniqueEmoji(recentReactions).slice(0, MAX_RECENT_REACTIONS), [recentReactions]);
  const selectedActionReaders = selectedActionMessage?.read_by || [];
  const sendingComposer = Boolean(editingMessageId && sending);
  const typingIndicatorText = useMemo(() => formatTypingIndicatorText(typingUsers), [typingUsers]);

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
      setExpandedReplyActionForId(null);
      setReactionPickerForMessageId(null);
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
      } else if (data.type === "typing_start" && typeof data.user_id === "number" && data.user_id !== user?.id) {
        const typingUserId = data.user_id;
        const userName = typeof data.user_name === "string" && data.user_name.trim()
          ? data.user_name.trim()
          : "Собеседник";

        setTypingUsers(prev => {
          const existing = prev.find(item => item.id === typingUserId);
          if (existing) {
            return prev.map(item => item.id === typingUserId ? { ...item, name: userName } : item);
          }
          return [...prev, { id: typingUserId, name: userName }];
        });

        const existingTimeout = typingTimeoutsRef.current.get(typingUserId);
        if (existingTimeout) clearTimeout(existingTimeout);
        const timeout = setTimeout(() => {
          setTypingUsers(prev => prev.filter(item => item.id !== typingUserId));
          typingTimeoutsRef.current.delete(typingUserId);
        }, TYPING_INDICATOR_TIMEOUT_MS);
        typingTimeoutsRef.current.set(typingUserId, timeout);
      } else if (data.type === "typing_stop" && typeof data.user_id === "number" && data.user_id !== user?.id) {
        const typingUserId = data.user_id;
        setTypingUsers(prev => prev.filter(item => item.id !== typingUserId));
        const existingTimeout = typingTimeoutsRef.current.get(typingUserId);
        if (existingTimeout) {
          clearTimeout(existingTimeout);
          typingTimeoutsRef.current.delete(typingUserId);
        }
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
    typingTimeoutsRef.current.forEach(timeout => clearTimeout(timeout));
    typingTimeoutsRef.current.clear();
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
      if (!cm.loadingOlder && !cm.messagesLoading && (cm.hasMoreOlder || cm.allowOneOlderProbe) && viewport.scrollTop <= 120) {
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

  useEffect(() => {
    if (cmMessagesLoading || cmLoadingOlder || displayMessages.length === 0) {
      return;
    }

    if (!cmHasMoreOlder && !cmAllowOneOlderProbe) {
      return;
    }

    const component = messagesViewportRef.current;
    const viewport = component?.containerRef?.current;
    if (!viewport) {
      return;
    }

    let cancelled = false;

    const frameId = window.requestAnimationFrame(() => {
      if (cancelled) {
        return;
      }

      const hasScrollableOverflow = viewport.scrollHeight > viewport.clientHeight + 8;
      if (!hasScrollableOverflow) {
        void cmLoadOlderMessages();
      }
    });

    return () => {
      cancelled = true;
      window.cancelAnimationFrame(frameId);
    };
  }, [
    cmAllowOneOlderProbe,
    cmHasMoreOlder,
    cmLoadOlderMessages,
    cmLoadingOlder,
    cmMessagesLoading,
    displayMessages.length,
  ]);

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
        if (files.length > 0) pendingRetryFilesRef.current.set(localId, files);
        cm.addPending(opt);
        cm.schedulePendingTimer(localId);
        resetComposerState();

        const sent = files.length
          ? await apiClient.sendMessageWithFiles(chatId, text, files, replyToId)
          : await apiClient.sendMessage(chatId, text, replyToId);

        cm.removePendingMessage(localId);
        pendingRetryFilesRef.current.delete(localId);
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

  const canRetryMessage = useCallback((message: Message): boolean => {
    if (message.send_state !== "failed" || !message.local_id) return false;
    const hasAttachments = Boolean(message.attachments?.length);
    return !hasAttachments || pendingRetryFilesRef.current.has(message.local_id);
  }, []);

  const handleRetryMessage = useCallback(async (message: Message) => {
    const localId = message.local_id;
    if (!chatId || !localId || retryingLocalIds.has(localId) || !canRetryMessage(message)) return;

    const text = (message.content || "").trim();
    const files = pendingRetryFilesRef.current.get(localId) || [];
    const replyToId = getReplyToId(message) ?? undefined;
    const wasNearBottom = scroll.isNearBottom();

    setRetryingLocalIds(prev => new Set(prev).add(localId));
    cm.markPendingSending(localId);
    cm.schedulePendingTimer(localId);

    try {
      const sent = files.length
        ? await apiClient.sendMessageWithFiles(chatId, text, files, replyToId)
        : await apiClient.sendMessage(chatId, text, replyToId);

      cm.removePendingMessage(localId);
      pendingRetryFilesRef.current.delete(localId);
      cm.setMessages(prev => uniqueMessagesById([...prev, sent]));

      if (wasNearBottom) requestAnimationFrame(() => scroll.scrollToBottom(false));
    } catch (e) {
      console.error("Ошибка переотправки сообщения:", e);
      cm.markPendingFailed(localId);
    } finally {
      setRetryingLocalIds(prev => {
        const next = new Set(prev);
        next.delete(localId);
        return next;
      });
    }
  }, [canRetryMessage, chatId, cm, retryingLocalIds, scroll]);

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
    } catch (e) {
      console.error("Ошибка удаления сообщения:", e);
    }
  };

  const handleToggleMessageActions = useCallback((messageId: number) => {
    setExpandedReplyActionForId(prev => {
      if (prev === messageId) { setIsReadersModalOpen(false); return null; }
      setIsReadersModalOpen(false);
      setReactionPickerForMessageId(null);
      setShowComposerEmojiPicker(false);
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
      const jumped = await cmJumpToMessage(linkedMessageId);
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
  }, [clearMessageParam, cmJumpToMessage, highlightFoundMessage, linkedMessageId]);

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
        <div className="app-surface rounded-2xl p-8 text-center">
          <div className="mb-4 inline-block h-8 w-8 animate-spin rounded-full border-4 border-[var(--border-subtle)] border-t-[var(--accent-primary)]" />
          <p className="app-text-muted text-sm">Загрузка чатов...</p>
        </div>
      ) : cm.error ? (
        <div className="app-feedback-danger rounded-2xl p-6 text-center">
          <p className="text-sm">{cm.error}</p>
        </div>
      ) : (
        <div className="min-h-0 h-full">
        <section className="flex h-full min-h-0 flex-col overflow-hidden lg:rounded-xl lg:border lg:border-[var(--border-subtle)] lg:bg-[var(--surface-primary)] lg:p-4 lg:shadow-[var(--shadow-card)]">
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
                    <button type="button" data-date-trigger="true" onClick={() => scroll.openDateNavigator()} className="app-surface-elevated inline-block rounded-full px-3 py-1 text-xs text-[var(--muted-foreground)] backdrop-blur transition hover:text-[var(--foreground)]">
                      {scroll.floatingDate}
                    </button>
                  </div>
                ) : null}

                {/* Date navigator panel */}
                {scroll.isDateNavigatorOpen ? (
                  <div data-date-navigator="true" className="app-menu absolute left-1/2 top-12 z-30 w-[min(22rem,calc(100%-1.5rem))] -translate-x-1/2 rounded-2xl p-4">
                    <p className="app-text-muted text-xs font-semibold uppercase tracking-wide">Перейти к дате</p>
                    <div className="mt-3 flex items-center gap-2">
                      <button type="button" onClick={() => scroll.setSelectedHistoryDate(prev => shiftDateInputValue(prev, -1))} className="app-surface-muted inline-flex h-9 w-9 items-center justify-center rounded-lg text-[var(--muted-foreground)] transition hover:bg-[var(--surface-tertiary)]" aria-label="Предыдущий день"><ChevronLeft size={16} /></button>
                      <input type="date" value={scroll.selectedHistoryDate} onChange={e => scroll.setSelectedHistoryDate(e.target.value)} className="app-input h-9 flex-1 rounded-lg px-3 text-sm" />
                      <button type="button" onClick={() => scroll.setSelectedHistoryDate(prev => shiftDateInputValue(prev, 1))} className="app-surface-muted inline-flex h-9 w-9 items-center justify-center rounded-lg text-[var(--muted-foreground)] transition hover:bg-[var(--surface-tertiary)]" aria-label="Следующий день"><ChevronRight size={16} /></button>
                    </div>
                    <div className="mt-3 flex flex-wrap gap-2">
                      <button type="button" onClick={() => scroll.setSelectedHistoryDate(formatDateInputValue(new Date()))} className="app-surface-muted rounded-lg px-3 py-2 text-sm text-[var(--muted-foreground)] transition hover:bg-[var(--surface-tertiary)]">Сегодня</button>
                      <button type="button" onClick={() => scroll.setIsDateNavigatorOpen(false)} className="app-surface-elevated rounded-lg px-3 py-2 text-sm text-[var(--muted-foreground)] transition hover:bg-[var(--surface-secondary)]">Закрыть</button>
                      <button type="button" onClick={() => void handleJumpToDate(scroll.selectedHistoryDate)} disabled={!scroll.selectedHistoryDate || jumpingToDate} className="app-action-primary ml-auto rounded-lg px-3 py-2 text-sm font-medium disabled:cursor-not-allowed disabled:opacity-50">{jumpingToDate ? "Переход..." : "Перейти"}</button>
                    </div>
                  </div>
                ) : null}

                {/* Message list */}
                <ScrollableMessageList
                  ref={messagesViewportRef}
                  autoScrollToBottom={!cm.hasMoreNewer && !cm.historyNavigationMode}
                  autoScrollToBottomOnMount={!cm.hasMoreNewer && !cm.historyNavigationMode}
                  scrollBehavior="smooth"
                  className="min-h-0 flex-1 bg-transparent p-3 lg:bg-[var(--surface-secondary)]"
                >
                  {cm.messagesLoading ? (
                    <p className="app-text-muted text-center text-sm">Загрузка сообщений...</p>
                  ) : displayMessages.length === 0 ? (
                    <p className="app-text-muted text-center text-sm">Пока нет сообщений. Напишите первым.</p>
                  ) : (
                    <div className="flex min-h-full flex-col justify-end">
                      {cm.loadingOlder ? <p className="app-text-muted mb-3 text-center text-xs">Подгружаем старые сообщения...</p> : null}
                      {displayMessages.map((message, index) => {
                        const replyToId = getReplyToId(message);
                        const repliedMessage = replyToId ? messagesById.get(replyToId) : null;
                        const curDay = getMessageDayKey(message);
                        const prevDay = index > 0 ? getMessageDayKey(displayMessages[index - 1]) : null;
                        const curDate = getMessageDate(message);
                        const showDayDivider = Boolean(curDate && curDay !== prevDay);
                        const showUnreadDivider = unreadDividerMessageId === message.id;

                        return (
                          <React.Fragment key={message.id}>
                            {showDayDivider && curDate ? (
                              <div className="mb-3 flex justify-center px-2 pointer-events-none">
                                <button type="button" data-date-trigger="true" onClick={() => scroll.openDateNavigator(formatDateInputValue(curDate))} className="app-surface-elevated pointer-events-auto inline-block rounded-full px-3 py-1 text-xs text-[var(--muted-foreground)] backdrop-blur transition hover:text-[var(--foreground)]">
                                  {formatDayDivider(curDate)}
                                </button>
                              </div>
                            ) : null}
                            {showUnreadDivider ? (
                              <div className="chat-unread-divider mb-3 mt-1 flex items-center gap-3 px-2" role="separator" aria-label="Непрочитанные сообщения">
                                <span className="h-px flex-1 bg-[color:color-mix(in_srgb,var(--accent-primary)_18%,var(--border-subtle))]" />
                                <span className="chat-unread-divider__label rounded-full px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.08em]">
                                  Непрочитанные сообщения
                                </span>
                                <span className="h-px flex-1 bg-[color:color-mix(in_srgb,var(--accent-primary)_18%,var(--border-subtle))]" />
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
                              recentReactions={selectedActionRecentReactions}
                              onQuickReact={handleReact}
                              onOpenReactionPicker={(msg) => setReactionPickerForMessageId(msg.id)}
                              onShowAllReaders={() => setIsReadersModalOpen(true)}
                              onRetry={handleRetryMessage}
                              isRetrying={Boolean(message.local_id && retryingLocalIds.has(message.local_id))}
                              retryDisabled={!canRetryMessage(message)}
                              onReply={handleReplyToMessage}
                              onEdit={handleStartEditMessage}
                              onDelete={handleDeleteMessage}
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
                      className="relative inline-flex h-10 w-10 items-center justify-center rounded-full border border-[var(--border-subtle)] bg-[var(--surface-primary)] p-0 leading-none text-[var(--muted-foreground)] shadow-[0_10px_30px_rgba(15,23,42,0.22)] transition hover:bg-[var(--surface-secondary)] hover:text-[var(--foreground)] active:scale-[0.98]"
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
                <div className="app-divider shrink-0 border-t bg-transparent px-4 pt-3 pb-[calc(env(safe-area-inset-bottom)+0.25rem)] lg:app-header lg:px-0 lg:pb-0">
                  {typingIndicatorText && (
                    <div className="app-text-muted mb-2 flex items-center gap-2 text-xs italic">
                      <div className="flex gap-1">
                        <span className="app-text-muted inline-block h-1.5 w-1.5 animate-bounce rounded-full bg-current" style={{ animationDelay: "0ms" }} />
                        <span className="app-text-muted inline-block h-1.5 w-1.5 animate-bounce rounded-full bg-current" style={{ animationDelay: "150ms" }} />
                        <span className="app-text-muted inline-block h-1.5 w-1.5 animate-bounce rounded-full bg-current" style={{ animationDelay: "300ms" }} />
                      </div>
                      <span>{typingIndicatorText}</span>
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
            <div className="app-surface-muted flex h-full min-h-[280px] items-center justify-center rounded-xl text-center">
              <div>
                <MessageCircle size={20} className="app-text-muted mx-auto mb-2" />
                <p className="app-text-muted text-sm">Диалог не найден</p>
              </div>
            </div>
          )}
        </section>
        </div>
      )}

      {mediaPreview ? <ChatMediaPreviewModal preview={mediaPreview} onClose={() => setMediaPreview(null)} /> : null}

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
          }}
        />
      ) : null}
    </AppShell>
  );
}
