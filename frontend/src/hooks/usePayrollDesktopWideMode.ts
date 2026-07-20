"use client";

import { useCallback, useSyncExternalStore } from "react";

import { PAYROLL_DESKTOP_WIDE_MODE_STORAGE_PREFIX } from "@/lib/payroll-admin";

const PAYROLL_DESKTOP_WIDE_MODE_EVENT = "payroll-desktop-wide-mode-change";

function storageKey(userId: number): string {
  return `${PAYROLL_DESKTOP_WIDE_MODE_STORAGE_PREFIX}.${userId}`;
}

export function usePayrollDesktopWideMode(userId?: number | null) {
  const subscribe = useCallback((notify: () => void) => {
    if (!userId) return () => undefined;
    const key = storageKey(userId);
    const handleStorage = (event: StorageEvent) => {
      if (event.key === key) notify();
    };
    window.addEventListener("storage", handleStorage);
    window.addEventListener(PAYROLL_DESKTOP_WIDE_MODE_EVENT, notify);
    return () => {
      window.removeEventListener("storage", handleStorage);
      window.removeEventListener(PAYROLL_DESKTOP_WIDE_MODE_EVENT, notify);
    };
  }, [userId]);

  const getSnapshot = useCallback(() => (
    userId ? window.localStorage.getItem(storageKey(userId)) === "1" : false
  ), [userId]);

  const desktopWideMode = useSyncExternalStore(
    subscribe,
    getSnapshot,
    () => false,
  );

  const changeDesktopWideMode = useCallback((enabled: boolean) => {
    if (!userId) return;
    window.localStorage.setItem(storageKey(userId), enabled ? "1" : "0");
    window.dispatchEvent(new Event(PAYROLL_DESKTOP_WIDE_MODE_EVENT));
  }, [userId]);

  return [desktopWideMode, changeDesktopWideMode] as const;
}
