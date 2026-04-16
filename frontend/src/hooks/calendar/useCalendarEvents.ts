/**
 * Хук для загрузки событий календаря
 * Обрабатывает кэширование, загрузку и ошибки
 */

import { useEffect, useState, useRef } from "react";
import { calendarService, type CalendarEvent, startOfWeekMonday } from "@/services/calendarService";

interface UseCalendarEventsOptions {
  monthDate: Date;
  selectedCalendarId: number | null;
  calendarScope: "accessible" | "all";
  canUseAllCalendarsMode: boolean;
  eventsRefreshTrigger: number;
  onEventsLoaded?: (events: CalendarEvent[]) => void;
}

interface UseCalendarEventsResult {
  events: CalendarEvent[];
  loading: boolean;
  error: string | null;
}

export function useCalendarEvents({
  monthDate,
  selectedCalendarId,
  calendarScope,
  canUseAllCalendarsMode,
  eventsRefreshTrigger,
  onEventsLoaded,
}: UseCalendarEventsOptions): UseCalendarEventsResult {
  const [events, setEvents] = useState<CalendarEvent[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const requestIdRef = useRef(0);

  useEffect(() => {
    let cancelled = false;

    // Вычисляем диапазон дат для загрузки
    const start = new Date(monthDate.getFullYear(), monthDate.getMonth(), 1);
    const end = new Date(monthDate.getFullYear(), monthDate.getMonth() + 1, 1);
    const weekStart = startOfWeekMonday(new Date());
    const weekEndExclusive = new Date(weekStart);
    weekEndExclusive.setDate(weekEndExclusive.getDate() + 7);

    // Расширяем диапазон для включения текущей недели
    const fetchStart = weekStart < start ? weekStart : start;
    const fetchEnd = weekEndExclusive > end ? weekEndExclusive : end;

    async function loadEvents() {
      const requestId = ++requestIdRef.current;

      try {
        setLoading(true);
        setError(null);

        const loadedEvents = await calendarService.loadEvents(
          fetchStart,
          fetchEnd,
          selectedCalendarId,
          calendarScope,
          canUseAllCalendarsMode,
          eventsRefreshTrigger
        );

        if (!cancelled) {
          setEvents(loadedEvents);
          onEventsLoaded?.(loadedEvents);
        }
      } catch (err) {
        if (requestId !== requestIdRef.current) {
          return;
        }

        if (!cancelled) {
          const message = err instanceof Error ? err.message : String(err || "");
          const isNetworkLike = message === "NetworkError" || /fetch failed/i.test(message);
          
          if (!isNetworkLike) {
            console.error("Ошибка загрузки событий календаря:", err);
          }
          
          setError("Не удалось загрузить события");
          setEvents([]);
        }
      } finally {
        if (!cancelled && requestId === requestIdRef.current) {
          setLoading(false);
        }
      }
    }

    loadEvents();

    return () => {
      cancelled = true;
    };
  }, [
    monthDate,
    selectedCalendarId,
    calendarScope,
    canUseAllCalendarsMode,
    eventsRefreshTrigger,
    onEventsLoaded,
  ]);

  return { events, loading, error };
}
