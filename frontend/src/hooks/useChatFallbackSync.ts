import { useEffect } from "react";

type SyncLatestMessagesOptions = {
  limit?: number;
  scrollOnSync?: boolean;
};

type UseChatFallbackSyncOptions = {
  chatId: number | null;
  isConnected: boolean;
  userLoading: boolean;
  hasUser: boolean;
  messagesLoading: boolean;
  hasMessages: boolean;
  isNearBottom: () => boolean;
  syncLatestMessages: (options?: SyncLatestMessagesOptions) => Promise<void>;
  intervalMs?: number;
};

export function useChatFallbackSync({
  chatId,
  isConnected,
  userLoading,
  hasUser,
  messagesLoading,
  hasMessages,
  isNearBottom,
  syncLatestMessages,
  intervalMs = 10000,
}: UseChatFallbackSyncOptions) {
  useEffect(() => {
    if (
      typeof window === "undefined" ||
      isConnected ||
      !chatId ||
      Number.isNaN(chatId) ||
      userLoading ||
      !hasUser ||
      messagesLoading ||
      !hasMessages
    ) {
      return;
    }

    const sync = () => {
      void syncLatestMessages({
        limit: 20,
        scrollOnSync: isNearBottom(),
      });
    };

    sync();

    const intervalId = window.setInterval(sync, intervalMs);
    const handleFocus = () => sync();
    const handleVisibilityChange = () => {
      if (document.visibilityState === "visible") {
        sync();
      }
    };

    window.addEventListener("focus", handleFocus);
    document.addEventListener("visibilitychange", handleVisibilityChange);

    return () => {
      window.clearInterval(intervalId);
      window.removeEventListener("focus", handleFocus);
      document.removeEventListener("visibilitychange", handleVisibilityChange);
    };
  }, [chatId, hasMessages, hasUser, intervalMs, isConnected, isNearBottom, messagesLoading, syncLatestMessages, userLoading]);
}