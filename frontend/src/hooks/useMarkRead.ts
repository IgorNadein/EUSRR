import { useCallback, useEffect, useRef } from "react";
import { apiClient } from "@/lib/api";

const MARK_READ_DEBOUNCE_MS = 300;

interface UseMarkReadOptions {
  chatId: number;
  /** Callback to update the chat state after a successful read acknowledgment */
  onReadAcknowledged?: (confirmedId: number) => void;
}

/**
 * Debounced mark-as-read logic.
 *
 * Returns helpers to schedule mark-read events, query the last confirmed
 * read position, and clean-up resources.
 */
export function useMarkRead({ chatId, onReadAcknowledged }: UseMarkReadOptions) {
  const timerRef = useRef<NodeJS.Timeout | null>(null);
  const inFlightRef = useRef(false);
  const queuedIdRef = useRef<number | null>(null);
  const lastConfirmedRef = useRef(0);
  const onReadAcknowledgedRef = useRef(onReadAcknowledged);

  useEffect(() => {
    onReadAcknowledgedRef.current = onReadAcknowledged;
  }, [onReadAcknowledged]);

  // Reset all state when chatId changes
  useEffect(() => {
    if (timerRef.current) {
      clearTimeout(timerRef.current);
      timerRef.current = null;
    }
    inFlightRef.current = false;
    queuedIdRef.current = null;
    lastConfirmedRef.current = 0;
  }, [chatId]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (timerRef.current) {
        clearTimeout(timerRef.current);
        timerRef.current = null;
      }
    };
  }, []);

  const flush = useCallback(async () => {
    if (!chatId || Number.isNaN(chatId) || inFlightRef.current) return;

    const targetId = queuedIdRef.current;
    if (typeof targetId !== "number") return;
    if (targetId <= lastConfirmedRef.current) {
      queuedIdRef.current = null;
      return;
    }

    queuedIdRef.current = null;
    inFlightRef.current = true;

    try {
      await apiClient.markChatAsRead(chatId, targetId);
      lastConfirmedRef.current = Math.max(lastConfirmedRef.current, targetId);
      onReadAcknowledgedRef.current?.(targetId);
    } catch (error) {
      console.error("Ошибка отложенной отметки прочтения:", error);
      // Re-queue the failed id so the next flush picks it up
      queuedIdRef.current = Math.max(queuedIdRef.current ?? 0, targetId);
    } finally {
      inFlightRef.current = false;

      // If another id was queued while we were in-flight, schedule another flush
      if (
        queuedIdRef.current !== null &&
        queuedIdRef.current > lastConfirmedRef.current &&
        !timerRef.current
      ) {
        timerRef.current = setTimeout(() => {
          timerRef.current = null;
          void flush();
        }, MARK_READ_DEBOUNCE_MS);
      }
    }
  }, [chatId]);

  /**
   * Schedule a mark-read for the given message id.
   * Debounces calls so multiple rapid updates collapse into one.
   */
  const scheduleMarkRead = useCallback(
    (messageId?: number | null) => {
      if (!chatId || typeof messageId !== "number") return;

      const nextTarget = Math.max(queuedIdRef.current ?? 0, messageId);
      if (nextTarget <= lastConfirmedRef.current) return;

      queuedIdRef.current = nextTarget;

      if (inFlightRef.current) return;

      if (timerRef.current) {
        clearTimeout(timerRef.current);
      }

      timerRef.current = setTimeout(() => {
        timerRef.current = null;
        void flush();
      }, MARK_READ_DEBOUNCE_MS);
    },
    [chatId, flush],
  );

  /** Sync the confirmed watermark from external sources (e.g. chat.last_read_message_id). */
  const syncConfirmed = useCallback((id: number) => {
    lastConfirmedRef.current = Math.max(lastConfirmedRef.current, id);
  }, []);

  /** Read-only accessor – useful for comparisons without triggering re-renders. */
  const getLastConfirmed = useCallback(() => lastConfirmedRef.current, []);

  return { scheduleMarkRead, syncConfirmed, getLastConfirmed } as const;
}
