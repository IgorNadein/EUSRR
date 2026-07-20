"use client";

import { useCallback, useSyncExternalStore } from "react";

import type { PayrollAdminTab } from "@/lib/payroll-admin";

export type PayrollFinanceTab = "statement" | "work" | "management";

const PAYROLL_TAB_CHANGE_EVENT = "payroll-tab-change";
const FINANCE_TAB_STORAGE_PREFIX = "finances.payroll.active-tab";
const ADMIN_TAB_STORAGE_PREFIX = "finances.payroll.admin.active-tab";
const ALL_FINANCE_TABS: ReadonlySet<string> = new Set(["statement", "work", "management"]);
const EMPLOYEE_FINANCE_TABS: ReadonlySet<string> = new Set(["statement", "work"]);
const ADMIN_TABS: ReadonlySet<string> = new Set([
  "readiness",
  "rates",
  "work",
  "inputs",
  "summary",
  "approval",
]);

function useStoredPayrollTab<T extends string>({
  userId,
  storagePrefix,
  allowedTabs,
  fallback,
}: {
  userId?: number | null;
  storagePrefix: string;
  allowedTabs: ReadonlySet<string>;
  fallback: T;
}) {
  const key = userId ? `${storagePrefix}.${userId}` : null;

  const subscribe = useCallback((notify: () => void) => {
    if (!key) return () => undefined;
    const handleStorage = (event: StorageEvent) => {
      if (event.key === key) notify();
    };
    window.addEventListener("storage", handleStorage);
    window.addEventListener(PAYROLL_TAB_CHANGE_EVENT, notify);
    return () => {
      window.removeEventListener("storage", handleStorage);
      window.removeEventListener(PAYROLL_TAB_CHANGE_EVENT, notify);
    };
  }, [key]);

  const getSnapshot = useCallback(() => {
    if (!key) return fallback;
    const stored = window.localStorage.getItem(key);
    return allowedTabs.has(stored || "") ? stored as T : fallback;
  }, [allowedTabs, fallback, key]);

  const value = useSyncExternalStore(subscribe, getSnapshot, () => fallback);

  const setValue = useCallback((nextValue: T) => {
    if (!key || !allowedTabs.has(nextValue)) return;
    window.localStorage.setItem(key, nextValue);
    window.dispatchEvent(new Event(PAYROLL_TAB_CHANGE_EVENT));
  }, [allowedTabs, key]);

  return [value, setValue] as const;
}

export function usePayrollFinanceTab(
  userId?: number | null,
  canOpenManagement = false,
) {
  return useStoredPayrollTab<PayrollFinanceTab>({
    userId,
    storagePrefix: FINANCE_TAB_STORAGE_PREFIX,
    allowedTabs: canOpenManagement ? ALL_FINANCE_TABS : EMPLOYEE_FINANCE_TABS,
    fallback: "statement",
  });
}

export function usePayrollAdminTab(userId?: number | null) {
  return useStoredPayrollTab<PayrollAdminTab>({
    userId,
    storagePrefix: ADMIN_TAB_STORAGE_PREFIX,
    allowedTabs: ADMIN_TABS,
    fallback: "readiness",
  });
}
