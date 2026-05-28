import { useCallback, useEffect, useRef, useState } from "react";
import { apiClient } from "@/lib/api";
import type { Chat, Message } from "@/types/api";
import { getMessageTimestamp, uniqueMessagesById } from "@/lib/messages/chatUtils";
import { getReplyToId } from "@/lib/messages/messageUtils";
import {
  getPendingMessageStorageIdentity,
  loadStoredPendingMessages,
  reconcileStoredPendingMessages,
  saveStoredPendingMessages,
} from "@/lib/messages/pendingMessageStorage";

const PENDING_MESSAGE_DELAY_MS = 8000;

/* ─── public types ─── */

export interface UseChatMessagesOptions {
  chatId: number;
  userId: number | undefined;
  userLoading: boolean;
}

export interface UseChatMessagesReturn {
  chat: Chat | null;
  setChat: React.Dispatch<React.SetStateAction<Chat | null>>;
  messages: Message[];
  setMessages: React.Dispatch<React.SetStateAction<Message[]>>;
  pendingMessages: Message[];
  loading: boolean;
  messagesLoading: boolean;
  error: string | null;
  hasMoreOlder: boolean;
  hasMoreNewer: boolean;
  loadingOlder: boolean;
  loadingNewer: boolean;
  initialAnchorId: number | null;
  initialAnchorIndex: number | null;
  allowOneOlderProbe: boolean;
  anchorRetryTick: number;
  /** Whether we are in "date navigation" (history) mode */
  historyNavigationMode: boolean;
  setHistoryNavigationMode: React.Dispatch<React.SetStateAction<boolean>>;
  /** Number of new (unread) messages that appeared below the viewport */
  newMessagesBelowCount: number;
  /** Ref containing unread-below message ids */
  unreadBelowIdsRef: React.MutableRefObject<Set<number>>;
  /** hasMoreNewer kept in a ref for synchronous access */
  hasMoreNewerRef: React.MutableRefObject<boolean>;
  /** Load older (prepend) */
  loadOlderMessages: () => Promise<void>;
  /** Load newer (append) */
  loadNewerMessages: (opts?: { markRead?: boolean }) => Promise<void>;
  /** Background "fallback sync" of latest messages */
  syncLatestMessages: (opts?: { limit?: number; scrollOnSync?: boolean }) => Promise<void>;
  /** Register incoming messages as "below viewport" */
  registerNewMessagesBelow: (msgs: Message[]) => void;
  /** Reset the "below viewport" counter & set */
  resetNewMessagesBelow: () => void;
  /** Remove a pending message by its local_id */
  removePendingMessage: (localId?: string | null) => void;
  /** Reconcile a server-confirmed message with its pending twin */
  removePendingByServer: (confirmed: Message) => void;
  /** Create an optimistic message for instant UI */
  buildOptimistic: (text: string, files: File[], localId: string, replyToId?: number) => Message;
  /** Append a pending message */
  addPending: (msg: Message) => void;
  /** Start the "delayed" timer for a pending message */
  schedulePendingTimer: (localId: string) => void;
  /** Mark a pending message as failed */
  markPendingFailed: (localId: string) => void;
  /** Mark a failed pending message as sending again */
  markPendingSending: (localId: string) => void;
  /** Jump to a specific date (history navigation) */
  jumpToDate: (dateISO: string) => Promise<void>;
  /** Return to unread boundary (around last_read_message_id) */
  returnToUnread: () => Promise<{
    hasMoreAfter: boolean;
    anchorId: number | null;
    anchorIndex: number | null;
  } | null>;
  /** Jump to a specific message by id and load surrounding context */
  jumpToMessage: (messageId: number) => Promise<{
    hasMoreAfter: boolean;
    anchorId: number | null;
    anchorIndex: number | null;
  } | null>;
  /** Set anchorRetryTick (used to retry anchor scroll) */
  setAnchorRetryTick: React.Dispatch<React.SetStateAction<number>>;
  /** Mark initial scroll as done */
  markInitialScrollDone: () => void;
  /** Whether initial scroll still pending */
  isInitialScrollPending: () => boolean;
  /** Ref to isNearBottom callback (set by scroll hook) */
  isNearBottomRef: React.MutableRefObject<() => boolean>;
  /** Ref to scrollToBottom callback (set by scroll hook) */
  scrollToBottomRef: React.MutableRefObject<(smooth?: boolean) => void>;
}

/* ─── hook ─── */

export function useChatMessages({
  chatId,
  userId,
  userLoading,
}: UseChatMessagesOptions): UseChatMessagesReturn {
  /* ── core state ── */
  const [chat, setChat] = useState<Chat | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [pendingMessages, setPendingMessages] = useState<Message[]>([]);
  const [loading, setLoading] = useState(true);
  const [messagesLoading, setMessagesLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  /* ── pagination ── */
  const [hasMoreOlder, setHasMoreOlder] = useState(false);
  const [hasMoreNewer, setHasMoreNewer] = useState(false);
  const [loadingOlder, setLoadingOlder] = useState(false);
  const [loadingNewer, setLoadingNewer] = useState(false);

  /* ── anchor / history ── */
  const [initialAnchorId, setInitialAnchorId] = useState<number | null>(null);
  const [initialAnchorIndex, setInitialAnchorIndex] = useState<number | null>(null);
  const [allowOneOlderProbe, setAllowOneOlderProbe] = useState(false);
  const [anchorRetryTick, setAnchorRetryTick] = useState(0);
  const [historyNavigationMode, setHistoryNavigationMode] = useState(false);

  /* ── unread tracking ── */
  const [newMessagesBelowCount, setNewMessagesBelowCount] = useState(0);
  const unreadBelowIdsRef = useRef<Set<number>>(new Set());

  /* ── refs ── */
  const hasMoreNewerRef = useRef(false);
  const initialScrolledRef = useRef(false);
  const pendingMessagesRef = useRef<Message[]>([]);
  const pendingStorageIdentityRef = useRef<string | null>(null);
  const localSeqRef = useRef(0);
  const pendingTimersRef = useRef<Map<string, NodeJS.Timeout>>(new Map());
  const fallbackInFlightRef = useRef(false);

  /** Injected by scroll hook */
  const isNearBottomRef = useRef<() => boolean>(() => false);
  const scrollToBottomRef = useRef<(smooth?: boolean) => void>(() => {});

  /* keep refs in sync */
  useEffect(() => { hasMoreNewerRef.current = hasMoreNewer; }, [hasMoreNewer]);
  useEffect(() => { pendingMessagesRef.current = pendingMessages; }, [pendingMessages]);
  useEffect(() => {
    if (!chatId || Number.isNaN(chatId) || !userId) return;
    const identity = getPendingMessageStorageIdentity(chatId, userId);
    if (pendingStorageIdentityRef.current !== identity) return;

    saveStoredPendingMessages(chatId, userId, pendingMessages);
  }, [chatId, pendingMessages, userId]);

  /* ── pending message helpers ── */

  const clearPendingTimer = useCallback((localId?: string | null) => {
    if (!localId) return;
    const t = pendingTimersRef.current.get(localId);
    if (t) { clearTimeout(t); pendingTimersRef.current.delete(localId); }
  }, []);

  const markPendingAsDelayed = useCallback((localId: string) => {
    setPendingMessages(prev =>
      prev.map(m => m.local_id === localId && m.send_state === "pending" ? { ...m, send_state: "delayed" } : m),
    );
  }, []);

  const schedulePendingTimer = useCallback((localId: string) => {
    clearPendingTimer(localId);
    const t = setTimeout(() => { pendingTimersRef.current.delete(localId); markPendingAsDelayed(localId); }, PENDING_MESSAGE_DELAY_MS);
    pendingTimersRef.current.set(localId, t);
  }, [clearPendingTimer, markPendingAsDelayed]);

  const removePendingMessage = useCallback((localId?: string | null) => {
    if (!localId) return;
    clearPendingTimer(localId);
    setPendingMessages(prev => prev.filter(m => m.local_id !== localId));
  }, [clearPendingTimer]);

  const clearAllPendingTimers = useCallback(() => {
    pendingTimersRef.current.forEach(t => clearTimeout(t));
    pendingTimersRef.current.clear();
  }, []);

  const markPendingFailed = useCallback((localId: string) => {
    clearPendingTimer(localId);
    setPendingMessages(prev => prev.map(m => m.local_id === localId ? { ...m, send_state: "failed" } : m));
  }, [clearPendingTimer]);

  const markPendingSending = useCallback((localId: string) => {
    setPendingMessages(prev => prev.map(m => m.local_id === localId ? { ...m, send_state: "pending" } : m));
  }, []);

  /* ── attachment signature matching ── */

  const getAttachmentSig = useCallback((msg: Message) =>
    (msg.attachments || []).map(a => `${a.file_name}|${a.file_size ?? 0}|${a.mime_type ?? ""}`).sort().join("||"),
  []);

  const findMatchingPendingLocalId = useCallback((confirmed: Message) => {
    if (!userId || confirmed.author_id !== userId) return null;
    const confirmedReplyToId = getReplyToId(confirmed) ?? null;
    const confirmedSig = getAttachmentSig(confirmed);
    const confirmedTs = getMessageTimestamp(confirmed);

    const candidates = pendingMessagesRef.current
      .filter(p => p.author_id === userId && p.content === confirmed.content)
      .filter(p => (getReplyToId(p) ?? null) === confirmedReplyToId)
      .filter(p => getAttachmentSig(p) === confirmedSig)
      .map(p => ({ localId: p.local_id ?? null, diff: Math.abs(getMessageTimestamp(p) - confirmedTs) }))
      .filter(c => Boolean(c.localId))
      .sort((a, b) => a.diff - b.diff);

    const best = candidates[0];
    if (!best) return null;
    if (confirmedTs > 0 && best.diff > 10 * 60 * 1000) return null;
    return best.localId;
  }, [getAttachmentSig, userId]);

  const removePendingByServer = useCallback((confirmed: Message) => {
    const localId = findMatchingPendingLocalId(confirmed);
    if (localId) removePendingMessage(localId);
  }, [findMatchingPendingLocalId, removePendingMessage]);

  /* ── unread below ── */

  const resetNewMessagesBelow = useCallback(() => {
    unreadBelowIdsRef.current.clear();
    setNewMessagesBelowCount(0);
  }, []);

  const registerNewMessagesBelow = useCallback((incoming: Message[]) => {
    if (!userId || incoming.length === 0) return;
    let added = 0;
    incoming.forEach(m => {
      const authorId = m.author_id ?? m.author?.id ?? m.sender?.id;
      if (authorId === userId || m.id <= 0 || unreadBelowIdsRef.current.has(m.id)) return;
      unreadBelowIdsRef.current.add(m.id);
      added += 1;
    });
    if (added > 0) {
      setNewMessagesBelowCount(prev => prev + added);
    }
  }, [userId]);

  /* ── optimistic message builder ── */

  const guessType = useCallback((f: File) => {
    const mime = (f.type || "").toLowerCase();
    if (mime.startsWith("image/")) return "image";
    if (mime.startsWith("video/")) return "video";
    if (mime.startsWith("audio/")) return "audio";
    return "file";
  }, []);

  const buildOptimistic = useCallback((text: string, files: File[], localId: string, replyToId?: number): Message => {
    localSeqRef.current += 1;
    const now = Date.now() + localSeqRef.current;
    return {
      id: -now,
      chat: chatId,
      local_id: localId,
      author_id: userId,
      content: text,
      is_read: false,
      send_state: "pending",
      is_optimistic: true,
      created_at: new Date(now).toISOString(),
      created_ts: now,
      has_attachments: files.length > 0,
      attachments: files.map((f, i) => ({
        id: -(now * 100 + i),
        file_name: f.name,
        file_type: guessType(f),
        file_url: "",
        file_size: f.size,
        mime_type: f.type,
        is_local: true,
      })),
      reply_to_id: replyToId,
    };
  }, [chatId, guessType, userId]);

  const addPending = useCallback((msg: Message) => {
    setPendingMessages(prev => [...prev, msg]);
  }, []);

  /* ── load chat ── */

  useEffect(() => {
    if (!chatId || Number.isNaN(chatId)) { setChat(null); setLoading(false); return; }
    if (userLoading) { setLoading(true); return; }
    if (!userId) { setChat(null); setLoading(false); return; }

    let cancelled = false;
    (async () => {
      try {
        setLoading(true);
        setError(null);
        const loaded = await apiClient.getChat(chatId);
        if (!cancelled) setChat(loaded);
      } catch {
        if (!cancelled) { setChat(null); setError("Не удалось загрузить чат. Проверьте подключение и попробуйте снова."); }
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [chatId, userLoading, userId]);

  /* ── load messages ── */

  useEffect(() => {
    if (!chatId || Number.isNaN(chatId)) {
      pendingStorageIdentityRef.current = null;
      clearAllPendingTimers(); setMessages([]); setPendingMessages([]);
      setHasMoreOlder(false); setHasMoreNewer(false);
      setInitialAnchorId(null); setInitialAnchorIndex(null);
      setAllowOneOlderProbe(false);
      initialScrolledRef.current = false;
      resetNewMessagesBelow();
      return;
    }
    if (userLoading || !userId) {
      pendingStorageIdentityRef.current = null;
      return;
    }

    let cancelled = false;
    const storageIdentity = getPendingMessageStorageIdentity(chatId, userId);
    pendingStorageIdentityRef.current = null;

    (async () => {
      try {
        setMessagesLoading(true);
        const chatDetails = await apiClient.getChat(chatId);
        if (cancelled) return;
        setChat(chatDetails);
        const lastReadId = chatDetails.last_read_message_id;

        const around = await apiClient.getChatMessagesAround(chatId, {
          limit: 30,
          around_id: lastReadId || undefined,
        });
        if (cancelled) return;

        const aroundMsgs = around.messages || [];
        if (aroundMsgs.length > 0) {
          clearAllPendingTimers();
          const norm = uniqueMessagesById(aroundMsgs);
          const restoredPending = reconcileStoredPendingMessages(
            loadStoredPendingMessages(chatId, userId),
            norm,
          );
          setMessages(norm);
          setPendingMessages(restoredPending);
          setHasMoreOlder(typeof around.has_more_before === "boolean" ? around.has_more_before : norm.length >= 50);
          setHasMoreNewer(Boolean(around.has_more_after));
          setInitialAnchorId(around.anchor_id ?? null);
          setInitialAnchorIndex(typeof around.anchor_index === "number" ? around.anchor_index : null);
          setAllowOneOlderProbe(Boolean(around.anchor_id));

          // Seed unread-below from loaded messages
          unreadBelowIdsRef.current = new Set(
            norm.filter(m => {
              const aId = m.author_id ?? m.author?.id ?? m.sender?.id;
              return aId !== userId && m.id > (lastReadId ?? 0);
            }).map(m => m.id),
          );
          setNewMessagesBelowCount(Math.max(chatDetails.unread_count ?? 0, unreadBelowIdsRef.current.size));
        } else {
          clearAllPendingTimers();
          const resp = await apiClient.getChatMessages(chatId, { limit: 50 });
          if (cancelled) return;
          const norm = uniqueMessagesById(resp.messages || []);
          const restoredPending = reconcileStoredPendingMessages(
            loadStoredPendingMessages(chatId, userId),
            norm,
          );
          setMessages(norm); setPendingMessages(restoredPending);
          setHasMoreOlder(Boolean(resp.has_more)); setHasMoreNewer(false);
          setInitialAnchorId(null); setInitialAnchorIndex(null); setAllowOneOlderProbe(false);
          unreadBelowIdsRef.current = new Set(
            norm.filter(m => {
              const aId = m.author_id ?? m.author?.id ?? m.sender?.id;
              return aId !== userId && m.id > (lastReadId ?? 0);
            }).map(m => m.id),
          );
          setNewMessagesBelowCount(Math.max(chatDetails.unread_count ?? 0, unreadBelowIdsRef.current.size));
        }

        pendingStorageIdentityRef.current = storageIdentity;
        initialScrolledRef.current = false;
        setAnchorRetryTick(0);
      } catch (err: unknown) {
        if (cancelled) return;
        const msg = err instanceof Error ? err.message : String(err);
        if (msg.includes("403")) {
          setError("Нет доступа к этому чату");
          clearAllPendingTimers(); setMessages([]); setPendingMessages([]);
        } else {
          console.error("Ошибка загрузки сообщений:", err);
        }
        setHasMoreOlder(false); setHasMoreNewer(false);
        setInitialAnchorId(null); setInitialAnchorIndex(null); setAllowOneOlderProbe(false);
        resetNewMessagesBelow();
        initialScrolledRef.current = false;
        setAnchorRetryTick(0);
      } finally {
        if (!cancelled) setMessagesLoading(false);
      }
    })();

    return () => { cancelled = true; };
  }, [chatId, clearAllPendingTimers, resetNewMessagesBelow, userLoading, userId]);

  // Cleanup timers on unmount
  useEffect(() => () => { clearAllPendingTimers(); }, [clearAllPendingTimers]);

  // Reset per-chat state
  useEffect(() => {
    setHistoryNavigationMode(false);
    resetNewMessagesBelow();
  }, [chatId, resetNewMessagesBelow]);

  /* ── pagination ── */

  const loadOlderMessages = useCallback(async () => {
    if (!chatId || Number.isNaN(chatId) || loadingOlder || messagesLoading || messages.length === 0) return;
    if (!hasMoreOlder && !allowOneOlderProbe) return;

    const oldest = messages[0];
    try {
      setLoadingOlder(true);
      const resp = await apiClient.getChatMessages(chatId, { limit: 40, before_id: oldest.id });
      const older = resp.messages || [];
      if (older.length > 0) setMessages(prev => uniqueMessagesById([...older, ...prev]));
      setHasMoreOlder(Boolean(resp.has_more));
      setAllowOneOlderProbe(false);
    } catch (e) {
      console.error("Ошибка подгрузки старых сообщений:", e);
    } finally {
      setLoadingOlder(false);
    }
  }, [allowOneOlderProbe, chatId, hasMoreOlder, loadingOlder, messages, messagesLoading]);

  const loadNewerMessages = useCallback(async (opts?: { markRead?: boolean }) => {
    if (!chatId || Number.isNaN(chatId) || loadingNewer || messagesLoading || !hasMoreNewer || messages.length === 0) return;

    const newest = messages[messages.length - 1];
    try {
      setLoadingNewer(true);
      const resp = await apiClient.getChatMessages(chatId, { limit: 10, after_id: newest.id, mark_read: opts?.markRead ?? false });
      const newer = resp.messages || [];
      if (newer.length > 0) {
        newer.forEach(removePendingByServer);
        setMessages(prev => uniqueMessagesById([...prev, ...newer]));
      }
      setHasMoreNewer(Boolean(resp.has_more));
    } catch (e) {
      console.error("Ошибка подгрузки новых сообщений:", e);
    } finally {
      setLoadingNewer(false);
    }
  }, [chatId, hasMoreNewer, loadingNewer, messages, messagesLoading, removePendingByServer]);

  /* ── fallback sync ── */

  const syncLatestMessages = useCallback(async (options: { limit?: number; scrollOnSync?: boolean } = {}) => {
    if (!chatId || Number.isNaN(chatId) || messagesLoading || messages.length === 0 || fallbackInFlightRef.current) return;

    const newest = messages[messages.length - 1];
    fallbackInFlightRef.current = true;

    try {
      const resp = await apiClient.getChatMessages(chatId, { limit: options.limit ?? 20, after_id: newest.id, mark_read: false });
      const newer = resp.messages || [];
      if (newer.length > 0) {
        newer.forEach(removePendingByServer);
        setMessages(prev => uniqueMessagesById([...prev, ...newer]));

        if (options.scrollOnSync) {
          requestAnimationFrame(() => scrollToBottomRef.current(false));
        }
      }
      setHasMoreNewer(Boolean(resp.has_more));
    } catch (e) {
      console.error("Ошибка тихой синхронизации сообщений:", e);
    } finally {
      fallbackInFlightRef.current = false;
    }
  }, [chatId, messages, messagesLoading, removePendingByServer]);

  /* ── jump to date ── */

  const jumpToDate = useCallback(async (dateValue: string) => {
    if (!chatId || Number.isNaN(chatId) || !dateValue) return;
    const dayStart = new Date(`${dateValue}T00:00:00`);
    if (Number.isNaN(dayStart.getTime())) return;

    try {
      setMessagesLoading(true);
      setHistoryNavigationMode(true);

      const [olderResp, newerResp] = await Promise.all([
        apiClient.getChatMessages(chatId, { limit: 20, before: dayStart.toISOString() }),
        apiClient.getChatMessages(chatId, { limit: 20, after: dayStart.toISOString(), mark_read: false }),
      ]);

      const combined = uniqueMessagesById([...(olderResp.messages || []), ...(newerResp.messages || [])]);
      const anchor = (newerResp.messages || [])[0] || (olderResp.messages || []).at(-1) || combined[0] || null;
      if (!anchor) return;

      setMessages(combined);
      setHasMoreOlder(Boolean(olderResp.has_more));
      setHasMoreNewer(Boolean(newerResp.has_more));
      setInitialAnchorId(anchor.id);
      setInitialAnchorIndex(combined.findIndex(m => m.id === anchor.id));
      setAllowOneOlderProbe(Boolean((newerResp.messages || [])[0]));

      initialScrolledRef.current = false;
      setAnchorRetryTick(0);
    } catch (e) {
      console.error("Ошибка перехода к дате:", e);
    } finally {
      setMessagesLoading(false);
    }
  }, [chatId]);

  /* ── return to unread boundary ── */

  const returnToUnread = useCallback(async () => {
    if (!chatId || Number.isNaN(chatId)) return null;

    const lastReadMessageId = Math.max(chat?.last_read_message_id ?? 0, 0);
    const shouldRestore = (hasMoreNewer || historyNavigationMode) && lastReadMessageId > 0;

    if (!shouldRestore) return null;

    try {
      setMessagesLoading(true);
      const around = await apiClient.getChatMessagesAround(chatId, { limit: 30, around_id: lastReadMessageId });
      const norm = uniqueMessagesById(around.messages || []);
      if (norm.length === 0) return null;

      setMessages(norm);
      setHasMoreOlder(typeof around.has_more_before === "boolean" ? around.has_more_before : norm.length >= 50);
      setHasMoreNewer(Boolean(around.has_more_after));
      setInitialAnchorId(around.anchor_id ?? lastReadMessageId);
      setInitialAnchorIndex(typeof around.anchor_index === "number" ? around.anchor_index : null);
      setAllowOneOlderProbe(Boolean(around.anchor_id ?? lastReadMessageId));
      setHistoryNavigationMode(Boolean(around.has_more_after));

      initialScrolledRef.current = false;
      setAnchorRetryTick(0);

      return {
        hasMoreAfter: Boolean(around.has_more_after),
        anchorId: around.anchor_id ?? lastReadMessageId,
        anchorIndex: typeof around.anchor_index === "number" ? around.anchor_index : null,
      };
    } catch (e) {
      console.error("Ошибка возврата к непрочитанным сообщениям:", e);
      return null;
    } finally {
      setMessagesLoading(false);
    }
  }, [chat?.last_read_message_id, chatId, hasMoreNewer, historyNavigationMode]);

  const jumpToMessage = useCallback(async (messageId: number) => {
    if (!chatId || Number.isNaN(chatId) || !messageId) return null;

    try {
      setMessagesLoading(true);
      setHistoryNavigationMode(true);

      const around = await apiClient.getChatMessagesAround(chatId, { limit: 30, around_id: messageId });
      const norm = uniqueMessagesById(around.messages || []);
      if (norm.length === 0) return null;

      setMessages(norm);
      setHasMoreOlder(typeof around.has_more_before === "boolean" ? around.has_more_before : norm.length >= 50);
      setHasMoreNewer(Boolean(around.has_more_after));
      setInitialAnchorId(around.anchor_id ?? messageId);
      setInitialAnchorIndex(typeof around.anchor_index === "number" ? around.anchor_index : norm.findIndex(m => m.id === (around.anchor_id ?? messageId)));
      setAllowOneOlderProbe(Boolean(around.anchor_id ?? messageId));

      initialScrolledRef.current = false;
      setAnchorRetryTick(0);

      return {
        hasMoreAfter: Boolean(around.has_more_after),
        anchorId: around.anchor_id ?? messageId,
        anchorIndex: typeof around.anchor_index === "number" ? around.anchor_index : norm.findIndex(m => m.id === (around.anchor_id ?? messageId)),
      };
    } catch (e) {
      console.error("Ошибка перехода к найденному сообщению:", e);
      return null;
    } finally {
      setMessagesLoading(false);
    }
  }, [chatId]);

  /* ── scroll tracking helpers ── */

  const markInitialScrollDone = useCallback(() => { initialScrolledRef.current = true; }, []);
  const isInitialScrollPending = useCallback(() => !initialScrolledRef.current, []);

  return {
    chat,
    setChat,
    messages,
    setMessages,
    pendingMessages,
    loading,
    messagesLoading,
    error,
    hasMoreOlder,
    hasMoreNewer,
    loadingOlder,
    loadingNewer,
    initialAnchorId,
    initialAnchorIndex,
    allowOneOlderProbe,
    anchorRetryTick,
    historyNavigationMode,
    setHistoryNavigationMode,
    newMessagesBelowCount,
    unreadBelowIdsRef,
    hasMoreNewerRef,
    loadOlderMessages,
    loadNewerMessages,
    syncLatestMessages,
    registerNewMessagesBelow,
    resetNewMessagesBelow,
    removePendingMessage,
    removePendingByServer,
    buildOptimistic,
    addPending,
    schedulePendingTimer,
    markPendingFailed,
    markPendingSending,
    jumpToDate,
    returnToUnread,
    jumpToMessage,
    setAnchorRetryTick,
    markInitialScrollDone,
    isInitialScrollPending,
    isNearBottomRef,
    scrollToBottomRef,
  };
}
