import { useCallback, useEffect, useRef, useState } from "react";
import { formatDayDivider } from "@/lib/messages/messageUtils";
import type { ScrollableMessageListInner } from "@/components/ScrollableMessageList";

/* ─── helpers ─── */

function formatDateInputValue(date: Date): string {
  const year = date.getFullYear();
  const month = `${date.getMonth() + 1}`.padStart(2, "0");
  const day = `${date.getDate()}`.padStart(2, "0");
  return `${year}-${month}-${day}`;
}

export function shiftDateInputValue(value: string, deltaDays: number): string {
  const baseDate = value ? new Date(`${value}T00:00:00`) : new Date();
  if (Number.isNaN(baseDate.getTime())) return formatDateInputValue(new Date());
  baseDate.setDate(baseDate.getDate() + deltaDays);
  return formatDateInputValue(baseDate);
}

/* ─── types ─── */

export interface UseChatScrollOptions {
  chatId: number;
  /** Number of rendered messages, used to recalculate floating date after reload/jump */
  messageCount?: number;
  /** Ref to the scroll container component */
  viewportRef: React.RefObject<ScrollableMessageListInner | null>;
  /** Whether there are more newer messages to load */
  hasMoreNewerRef: React.MutableRefObject<boolean>;
  /** Ref to unread-below message ids */
  unreadBelowIdsRef: React.MutableRefObject<Set<number>>;
  /** Whether we are in history navigation mode */
  historyNavigationMode: boolean;
}

export interface UseChatScrollReturn {
  /** Whether the scroll-to-bottom button should be visible */
  showScrollToBottom: boolean;
  setShowScrollToBottom: React.Dispatch<React.SetStateAction<boolean>>;
  /** Floating date display */
  floatingDate: string | null;
  floatingDateValue: string | null;
  showFloatingDate: boolean;
  /** Date navigator state */
  isDateNavigatorOpen: boolean;
  setIsDateNavigatorOpen: React.Dispatch<React.SetStateAction<boolean>>;
  selectedHistoryDate: string;
  setSelectedHistoryDate: React.Dispatch<React.SetStateAction<string>>;
  /** Check if user is near bottom */
  isNearBottom: () => boolean;
  /** Scroll to bottom */
  scrollToBottom: (smooth?: boolean) => void;
  /** Synchronize the scroll-to-bottom button visibility. Returns true if at bottom. */
  syncScrollToBottomState: () => boolean;
  /** Open date navigator, optionally with a preset date */
  openDateNavigator: (dateValue?: string | null) => void;
}

/* ─── hook ─── */

export function useChatScroll({
  chatId,
  messageCount = 0,
  viewportRef,
  hasMoreNewerRef,
  unreadBelowIdsRef,
  historyNavigationMode,
}: UseChatScrollOptions): UseChatScrollReturn {
  const [showScrollToBottom, setShowScrollToBottom] = useState(false);
  const [floatingDate, setFloatingDate] = useState<string | null>(null);
  const [floatingDateValue, setFloatingDateValue] = useState<string | null>(null);
  const [showFloatingDate, setShowFloatingDate] = useState(false);
  const [isDateNavigatorOpen, setIsDateNavigatorOpen] = useState(false);
  const [selectedHistoryDate, setSelectedHistoryDate] = useState("");

  const floatingDateTimeoutRef = useRef<NodeJS.Timeout | null>(null);

  // Sync selected date from floating date when navigator is closed
  useEffect(() => {
    if (floatingDateValue && !isDateNavigatorOpen) {
      setSelectedHistoryDate(floatingDateValue);
    }
  }, [floatingDateValue, isDateNavigatorOpen]);

  // Cleanup
  useEffect(() => () => {
    if (floatingDateTimeoutRef.current) clearTimeout(floatingDateTimeoutRef.current);
  }, []);

  const isNearBottom = useCallback(() => {
    const c = viewportRef.current;
    if (!c?.containerRef?.current) return false;
    const v = c.containerRef.current;
    return v.scrollHeight - v.scrollTop - v.clientHeight <= 150;
  }, [viewportRef]);

  const scrollToBottom = useCallback((smooth = false) => {
    viewportRef.current?.scrollToBottom(smooth ? "smooth" : "auto");
  }, [viewportRef]);

  const syncScrollToBottomState = useCallback(() => {
    const atBottom = isNearBottom();
    const hasBufferedNewer = hasMoreNewerRef.current || unreadBelowIdsRef.current.size > 0;

    if (atBottom && !hasMoreNewerRef.current) {
      setShowScrollToBottom(false);
      return true;
    }

    setShowScrollToBottom(!atBottom || hasBufferedNewer || historyNavigationMode);
    return atBottom;
  }, [hasMoreNewerRef, historyNavigationMode, isNearBottom, unreadBelowIdsRef]);

  const openDateNavigator = useCallback((dateValue?: string | null) => {
    setSelectedHistoryDate(dateValue || floatingDateValue || formatDateInputValue(new Date()));
    setShowFloatingDate(true);
    setIsDateNavigatorOpen(true);
  }, [floatingDateValue]);

  /** Update floating date from scroll position – call inside onScroll handler */
  const updateFloatingDate = useCallback((viewport: HTMLElement) => {
    const messageEls = viewport.querySelectorAll<HTMLElement>("[data-message-date]");
    const viewportTop = viewport.getBoundingClientRect().top;
    let topDate: string | null = null;
    let topDateVal: string | null = null;

    for (let i = 0; i < messageEls.length; i += 1) {
      const el = messageEls[i];
      if (el.getBoundingClientRect().bottom > viewportTop + 8) {
        const iso = el.getAttribute("data-message-date");
        if (iso) {
          const d = new Date(iso);
          if (!Number.isNaN(d.getTime())) {
            topDate = formatDayDivider(d);
            topDateVal = formatDateInputValue(d);
          }
        }
        break;
      }
    }

    if (topDate) {
      setFloatingDate(topDate);
      setFloatingDateValue(topDateVal);
      setShowFloatingDate(true);

      if (floatingDateTimeoutRef.current) clearTimeout(floatingDateTimeoutRef.current);
      floatingDateTimeoutRef.current = setTimeout(() => setShowFloatingDate(false), 1100);
      return;
    }

    setFloatingDate(null);
    setFloatingDateValue(null);
    setShowFloatingDate(false);
  }, []);

  // Expose updateFloatingDate as a stable ref so the scroll handler can call it
  const updateFloatingDateRef = useRef(updateFloatingDate);
  useEffect(() => { updateFloatingDateRef.current = updateFloatingDate; }, [updateFloatingDate]);

  // Attach scroll handler after the message list actually exists in the DOM.
  // `ref.current` changes do not trigger effects, so we re-run when messageCount changes.
  useEffect(() => {
    const c = viewportRef.current;
    if (!c?.containerRef?.current) return;
    const viewport = c.containerRef.current;

    const onScroll = () => updateFloatingDateRef.current(viewport);
    const frameId = window.requestAnimationFrame(onScroll);

    viewport.addEventListener("scroll", onScroll, { passive: true });
    return () => {
      window.cancelAnimationFrame(frameId);
      viewport.removeEventListener("scroll", onScroll);
    };
  }, [chatId, messageCount, viewportRef]);

  return {
    showScrollToBottom,
    setShowScrollToBottom,
    floatingDate,
    floatingDateValue,
    showFloatingDate,
    isDateNavigatorOpen,
    setIsDateNavigatorOpen,
    selectedHistoryDate,
    setSelectedHistoryDate,
    isNearBottom,
    scrollToBottom,
    syncScrollToBottomState,
    openDateNavigator,
  };
}
