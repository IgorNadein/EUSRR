"use client";

import { createContext, useContext, useEffect, useState, ReactNode, useCallback, useRef } from "react";
import { apiClient } from "@/lib/api";
import { useUser } from "@/contexts/UserContext";
import type { Calendar } from "@/types/api";

export type CalendarScope = "accessible" | "all";

type CalendarContextType = {
  calendars: Calendar[];
  selectedCalendarId: number | null;
  setSelectedCalendarId: (id: number | null) => void;
  calendarScope: CalendarScope;
  setCalendarScope: (scope: CalendarScope) => void;
  canUseAllCalendarsMode: boolean;
  loading: boolean;
  error: string | null;
  reloadCalendars: () => Promise<void>;
};

const CalendarContext = createContext<CalendarContextType | undefined>(undefined);

export function CalendarProvider({ children }: { children: ReactNode }) {
  const { user } = useUser();
  const [calendars, setCalendars] = useState<Calendar[]>([]);
  const [selectedCalendarId, setSelectedCalendarId] = useState<number | null>(null);
  const [calendarScope, setCalendarScope] = useState<CalendarScope>("accessible");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const initialLoadDone = useRef(false);
  const canUseAllCalendarsMode = Boolean(
    user?.auth?.is_staff || user?.auth?.is_superuser
  );

  const loadCalendars = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);

      const result = await apiClient.getCalendars({
        scope:
          canUseAllCalendarsMode && calendarScope === "all"
            ? "all"
            : undefined,
      });
      // API возвращает пагинированный ответ: {count, results}
      const cals = Array.isArray(result) ? result : (result?.results || []);
      setCalendars(cals);

      initialLoadDone.current = true;
    } catch (err) {
      console.error("Ошибка загрузки календарей:", err);
      setError("Не удалось загрузить календари");
    } finally {
      setLoading(false);
    }
  }, [
    calendarScope,
    canUseAllCalendarsMode,
  ]);

  useEffect(() => {
    if (user) {
      loadCalendars();
    } else {
      setCalendars([]);
      setSelectedCalendarId(null);
      setCalendarScope("accessible");
      initialLoadDone.current = false;
    }
  }, [user, loadCalendars]);

  return (
    <CalendarContext.Provider
      value={{
        calendars,
        selectedCalendarId,
        setSelectedCalendarId,
        calendarScope,
        setCalendarScope,
        canUseAllCalendarsMode,
        loading,
        error,
        reloadCalendars: loadCalendars,
      }}
    >
      {children}
    </CalendarContext.Provider>
  );
}

export function useCalendar() {
  const context = useContext(CalendarContext);
  if (context === undefined) {
    throw new Error("useCalendar must be used within CalendarProvider");
  }
  return context;
}
