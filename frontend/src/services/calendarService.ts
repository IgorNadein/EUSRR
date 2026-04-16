/**
 * Сервис для работы с календарными событиями
 * Включает кэширование для оптимизации запросов
 */

import { apiClient } from "@/lib/api";

// Типы
export interface CalendarEvent {
  id: number;
  title: string;
  start?: string | null;
  end?: string | null;
  allDay?: boolean;
  color?: string | null;
  color_event?: string | null;
  rule?: number | null;
  is_recurring?: boolean;
  event_id?: number;
  description?: string;
  calendar?: number;
  can_edit?: boolean;
  can_delete?: boolean;
}

interface EventsCache {
  key: string;
  events: CalendarEvent[];
  timestamp: number;
}

// Константы
const CACHE_TTL = 30000; // 30 секунд

// Глобальный кэш для событий календаря
let eventsCache: EventsCache | null = null;

// Утилиты для работы с датами
const pad = (v: number) => String(v).padStart(2, "0");

export const formatDateKey = (date: Date): string => 
  `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;

export const startOfWeekMonday = (date: Date): Date => {
  const d = new Date(date);
  d.setHours(0, 0, 0, 0);
  const dayIndex = (d.getDay() + 6) % 7; // Пн = 0
  d.setDate(d.getDate() - dayIndex);
  return d;
};

// Сервис для работы с событиями календаря
class CalendarService {
  /**
   * Загружает события календаря с кэшированием
   * @param startDate Начальная дата периода
   * @param endDate Конечная дата периода
   * @param calendarId ID календаря (null - все календари)
   * @param refreshTrigger Триггер для принудительного обновления
   */
  async loadEvents(
    startDate: Date,
    endDate: Date,
    calendarId: number | null,
    calendarScope: "accessible" | "all",
    canUseAllCalendarsMode: boolean,
    refreshTrigger: number
  ): Promise<CalendarEvent[]> {
    const apiScope =
      canUseAllCalendarsMode && calendarScope === "all" ? "all" : undefined;
    const cacheKey = `${formatDateKey(startDate)}_${formatDateKey(endDate)}_${calendarId}_${calendarScope}_${refreshTrigger}`;

    // Проверяем кэш
    if (eventsCache && eventsCache.key === cacheKey && Date.now() - eventsCache.timestamp < CACHE_TTL) {
      return eventsCache.events;
    }

    // Загружаем события
    const [eventsResult, occurrencesResult] = await Promise.all([
      apiClient.getCalendarEvents({
        start: formatDateKey(startDate),
        end: formatDateKey(endDate),
        calendar: calendarId || undefined,
        scope: apiScope,
      }),
      apiClient.getOccurrences({
        start: formatDateKey(startDate),
        end: formatDateKey(endDate),
        calendar: calendarId || undefined,
        scope: apiScope,
      }),
    ]);

    // Обрабатываем результаты
    const eventsList = Array.isArray(eventsResult) ? eventsResult : (eventsResult?.results || []);
    const regularEvents = eventsList.filter((evt: any) => !evt.rule);

    const occurrencesList = Array.isArray(occurrencesResult) ? occurrencesResult : (occurrencesResult?.results || []);
    const recurringOccurrences = occurrencesList.filter((occ: any) => occ.is_recurring);

    // Объединяем оба типа событий
    let allEvents = [...regularEvents, ...recurringOccurrences];

    if (calendarId !== null) {
      allEvents = allEvents.filter((event) => event.calendar === calendarId);
    }

    // Сохраняем в кэш
    eventsCache = {
      key: cacheKey,
      events: allEvents,
      timestamp: Date.now(),
    };

    return allEvents;
  }

  /**
   * Очищает кэш событий
   */
  clearCache(): void {
    eventsCache = null;
  }

  /**
   * Загружает полное событие по ID (для повторяющихся событий)
   */
  async loadFullEvent(eventId: number, occurrenceStart?: string, occurrenceEnd?: string): Promise<CalendarEvent> {
    const fullEvent = await apiClient.getEvent(eventId);
    
    // Если переданы время occurrence, используем их
    if (occurrenceStart && occurrenceEnd) {
      return {
        ...fullEvent,
        start: occurrenceStart,
        end: occurrenceEnd,
      };
    }
    
    return fullEvent;
  }

  /**
   * Импортирует календарь из ICS файла
   */
  async importFromICS(calendarId: number, file: File): Promise<{ imported: number; skipped: number }> {
    return apiClient.importCalendarFromICS(calendarId, file);
  }

  /**
   * Экспортирует календарь в ICS файл
   */
  async exportToICS(calendarId: number): Promise<Blob> {
    return apiClient.exportCalendarToICS(calendarId);
  }

  /**
   * Удаляет событие
   */
  async deleteEvent(eventId: number): Promise<void> {
    await apiClient.deleteEvent(eventId);
    this.clearCache(); // Очищаем кэш после удаления
  }
}

// Экспортируем singleton
export const calendarService = new CalendarService();
