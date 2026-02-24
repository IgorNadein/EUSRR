"use client";

import { createContext, useContext, useEffect, useState, ReactNode, useCallback, useRef } from "react";
import { apiClient } from "@/lib/api";

type Calendar = {
  id: number;
  name: string;
  slug: string;
  events_count?: number;
};

type CalendarContextType = {
  calendars: Calendar[];
  selectedCalendarId: number | null;
  setSelectedCalendarId: (id: number | null) => void;
  loading: boolean;
  error: string | null;
  reloadCalendars: () => Promise<void>;
};

const CalendarContext = createContext<CalendarContextType | undefined>(undefined);

export function CalendarProvider({ children }: { children: ReactNode }) {
  const [calendars, setCalendars] = useState<Calendar[]>([]);
  const [selectedCalendarId, setSelectedCalendarId] = useState<number | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const initialLoadDone = useRef(false);

  const loadCalendars = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      
      const result = await apiClient.getCalendars();
      // API возвращает пагинированный ответ: {count, results}
      const cals = Array.isArray(result) ? result : (result?.results || []);
      console.log("Загружено календарей:", cals.length, cals);
      setCalendars(cals);
      
      // Автоматически выбираем первый календарь только при первой загрузке
      if (!initialLoadDone.current && cals.length > 0 && selectedCalendarId === null) {
        setSelectedCalendarId(cals[0].id);
      }
      
      initialLoadDone.current = true;
    } catch (err) {
      console.error("Ошибка загрузки календарей:", err);
      setError("Не удалось загрузить календари");
    } finally {
      setLoading(false);
    }
  }, [selectedCalendarId]);

  useEffect(() => {
    loadCalendars();
  }, []);

  return (
    <CalendarContext.Provider
      value={{
        calendars,
        selectedCalendarId,
        setSelectedCalendarId,
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
