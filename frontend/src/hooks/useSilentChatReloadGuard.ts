import { useCallback } from "react";

const WS_SILENT_RELOAD_COOLDOWN_MS = 60_000;

function getWsReloadGuardKey(chatId: number): string {
  return `messages-ws-silent-reload:${chatId}`;
}

type ReconnectExhaustedDetails = {
  chatId: number | null;
  reconnectAttempts: number;
};

export function useSilentChatReloadGuard(chatId: number | null) {
  const handleReconnectExhausted = useCallback((details: ReconnectExhaustedDetails) => {
    if (typeof window === "undefined" || !chatId || Number.isNaN(chatId)) {
      return;
    }

    const guardKey = getWsReloadGuardKey(chatId);
    const now = Date.now();
    const lastReloadAt = Number(window.sessionStorage.getItem(guardKey) || 0);

    if (Number.isFinite(lastReloadAt) && now - lastReloadAt < WS_SILENT_RELOAD_COOLDOWN_MS) {
      console.warn(
        `Пропускаем тихую перезагрузку чата ${details.chatId}: cooldown еще не истек после ${details.reconnectAttempts} попыток.`
      );
      return;
    }

    window.sessionStorage.setItem(guardKey, String(now));
    console.warn(
      `WebSocket чата ${details.chatId} не восстановлен после ${details.reconnectAttempts} попыток, выполняем тихую перезагрузку.`
    );
    window.location.reload();
  }, [chatId]);

  const resetReloadGuard = useCallback(() => {
    if (typeof window === "undefined" || !chatId || Number.isNaN(chatId)) {
      return;
    }

    window.sessionStorage.removeItem(getWsReloadGuardKey(chatId));
  }, [chatId]);

  return {
    handleReconnectExhausted,
    resetReloadGuard,
  };
}