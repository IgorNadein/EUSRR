"use client";

import Link from "next/link";
import { Bell, X } from "lucide-react";
import { useCallback, useMemo, useState } from "react";

import { useUser } from "@/contexts/UserContext";
import { useWebPush } from "@/hooks/useWebPush";

const PUSH_PROMPT_VERSION = "v1";

function getDismissStorageKey(userId: number) {
  return `push-onboarding-dismissed:${PUSH_PROMPT_VERSION}:${userId}`;
}

export function PushOnboardingPrompt() {
  const { user } = useUser();
  const {
    isSupported,
    isSubscribed,
    isLoading,
    permission,
    subscribe,
  } = useWebPush();
  const [sessionDismissed, setSessionDismissed] = useState(false);
  const userId = user?.id ?? null;

  const persistedDismissed = useMemo(() => {
    if (typeof window === "undefined" || !userId) {
      return false;
    }

    return (
      window.localStorage.getItem(getDismissStorageKey(userId)) === "1"
    );
  }, [userId]);

  const dismissed = sessionDismissed || persistedDismissed;

  const shouldShow = useMemo(() => {
    if (!userId) return false;
    if (dismissed || isLoading) return false;
    if (!isSupported || isSubscribed) return false;
    return permission === "default";
  }, [dismissed, isLoading, isSubscribed, isSupported, permission, userId]);

  const handleDismiss = useCallback(() => {
    if (typeof window !== "undefined" && userId) {
      window.localStorage.setItem(getDismissStorageKey(userId), "1");
    }
    setSessionDismissed(true);
  }, [userId]);

  const handleEnable = useCallback(async () => {
    const success = await subscribe();
    if (success) {
      setSessionDismissed(true);
    }
  }, [subscribe]);

  if (!shouldShow) {
    return null;
  }

  return (
    <section className="app-surface rounded-2xl p-4 sm:p-5">
      <div className="flex items-start gap-3">
        <div className="app-badge app-badge-accent mt-0.5 flex h-10 w-10 shrink-0 items-center justify-center rounded-xl">
          <Bell size={18} />
        </div>

        <div className="min-w-0 flex-1">
          <div className="flex items-start justify-between gap-3">
            <div>
              <p className="app-card-caption">Системные уведомления</p>
              <h2 className="mt-1 text-base font-semibold text-[var(--foreground)]">
                Включить push-уведомления
              </h2>
            </div>
            <button
              type="button"
              onClick={handleDismiss}
              className="app-action-ghost flex h-8 w-8 items-center justify-center rounded-full"
              aria-label="Скрыть предложение включить уведомления"
              title="Скрыть"
            >
              <X size={16} />
            </button>
          </div>

          <p className="app-text-muted mt-2 text-sm">
            Приложение сможет присылать системные уведомления о новых сообщениях,
            заявках и других событиях, даже когда вкладка закрыта.
          </p>

          <div className="mt-4 flex flex-wrap items-center gap-2">
            <button
              type="button"
              onClick={() => void handleEnable()}
              disabled={isLoading}
              className="app-action-primary inline-flex items-center gap-2 rounded-lg px-4 py-2 text-sm font-medium disabled:opacity-50"
            >
              <Bell size={16} />
              {isLoading ? "Подключаем..." : "Включить уведомления"}
            </button>

            <Link
              href="/settings?section=notifications"
              className="app-action-ghost inline-flex items-center rounded-lg px-4 py-2 text-sm"
            >
              Настройки уведомлений
            </Link>
          </div>
        </div>
      </div>
    </section>
  );
}
