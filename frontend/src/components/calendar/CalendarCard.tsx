"use client";

import { memo, useMemo, useState, useRef, useEffect, useCallback } from "react";
import { ChevronLeft, ChevronRight, Plus, Users } from "lucide-react";
import { useCalendar } from "@/contexts/CalendarContext";
import { useCalendarEvents } from "@/hooks/calendar/useCalendarEvents";
import { calendarService, formatDateKey, type CalendarEvent } from "@/services/calendarService";

// Типы
interface CalendarCardProps {
  onOpenCalendarModal: (calendar?: { id?: number; name: string }) => void;
  onOpenEventModal: (event: any, date?: Date) => void;
  onOpenParticipantsModal: (calendar: { id: number; name: string; user_role?: string }) => void;
  eventsRefreshTrigger: number;
  setEventsRefreshTrigger: (value: number | ((prev: number) => number)) => void;
  setSidebarEvents: (events: CalendarEvent[]) => void;
  onCalendarChange: (calendarId: number | null) => void;
}

// Константы
const weekdays = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"];

// Утилиты
const sameDate = (a: Date, b: Date) =>
  a.getFullYear() === b.getFullYear() && a.getMonth() === b.getMonth() && a.getDate() === b.getDate();

/**
 * Компонент мини-календаря в сайдбаре
 */
export const CalendarCard = memo(function CalendarCard({
  onOpenCalendarModal,
  onOpenEventModal,
  onOpenParticipantsModal,
  eventsRefreshTrigger,
  setEventsRefreshTrigger,
  setSidebarEvents,
  onCalendarChange,
}: CalendarCardProps) {
  const { calendars, selectedCalendarId, setSelectedCalendarId } = useCalendar();

  const [monthDate, setMonthDate] = useState(() => {
    const now = new Date();
    return new Date(now.getFullYear(), now.getMonth(), 1);
  });

  const [showCalendarMenu, setShowCalendarMenu] = useState(false);
  const [selectedDate, setSelectedDate] = useState<Date | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Загружаем события через хук
  const { events, loading, error } = useCalendarEvents({
    monthDate,
    selectedCalendarId,
    eventsRefreshTrigger,
    onEventsLoaded: setSidebarEvents,
  });

  // Синхронизация selectedCalendarId с родительским компонентом
  const prevSelectedCalendarIdRef = useRef<number | null | undefined>(undefined);
  useEffect(() => {
    if (prevSelectedCalendarIdRef.current !== selectedCalendarId) {
      prevSelectedCalendarIdRef.current = selectedCalendarId;
      onCalendarChange(selectedCalendarId);
    }
  }, [selectedCalendarId, onCalendarChange]);

  // Метка месяца
  const monthLabel = useMemo(() => {
    const label = monthDate.toLocaleDateString("ru-RU", {
      month: "long",
      year: "numeric",
    });
    return label.charAt(0).toUpperCase() + label.slice(1);
  }, [monthDate]);

  // Обработчики
  const handleCreateCalendar = useCallback(() => {
    onOpenCalendarModal({ name: "" });
  }, [onOpenCalendarModal]);

  const handleDayClick = useCallback((date: Date) => {
    setSelectedDate(date);
    const startDate = new Date(date);
    startDate.setHours(10, 0, 0, 0);
    const endDate = new Date(date);
    endDate.setHours(11, 0, 0, 0);

    const newEvent = {
      title: "",
      description: "",
      start: startDate.toISOString(),
      end: endDate.toISOString(),
      calendar: selectedCalendarId,
      color_event: "#3498db",
    };
    onOpenEventModal(newEvent, date);
  }, [selectedCalendarId, onOpenEventModal]);

  const handleEventClick = useCallback(async (event: CalendarEvent) => {
    // Если это occurrence (повторяющееся событие), загружаем базовое событие
    if (event.is_recurring && event.event_id) {
      try {
        const fullEvent = await calendarService.loadFullEvent(event.event_id, event.start || undefined, event.end || undefined);
        onOpenEventModal(fullEvent);
      } catch (err) {
        console.error("Ошибка загрузки базового события:", err);
      }
    } else {
      onOpenEventModal(event);
    }
  }, [onOpenEventModal]);

  const handleImportCalendar = useCallback(async (event: React.ChangeEvent<HTMLInputElement>) => {
    if (!selectedCalendarId || !event.target.files || event.target.files.length === 0) {
      return;
    }

    const file = event.target.files[0];

    try {
      const result = await calendarService.importFromICS(selectedCalendarId, file);
      alert(`Импорт завершен!\nИмпортировано: ${result.imported}\nПропущено: ${result.skipped}`);
      setEventsRefreshTrigger(prev => prev + 1);
    } catch (error: any) {
      console.error('Failed to import calendar:', error);
      alert(`Ошибка импорта: ${error.message}`);
    } finally {
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }
    }
  }, [selectedCalendarId, setEventsRefreshTrigger]);

  const handleExportCalendar = useCallback(async () => {
    if (!selectedCalendarId) return;

    try {
      const blob = await calendarService.exportToICS(selectedCalendarId);
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `calendar-${selectedCalendarId}.ics`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
    } catch (error) {
      console.error('Failed to export calendar:', error);
      alert('Не удалось экспортировать календарь');
    }
    setShowCalendarMenu(false);
  }, [selectedCalendarId]);

  // Дни с событиями
  const eventDays = useMemo(() => {
    const days = new Set<string>();
    events.forEach((ev) => {
      if (!ev.start) return;
      const eventStart = new Date(ev.start);
      if (Number.isNaN(eventStart.getTime())) return;

      const eventEnd = ev.end ? new Date(ev.end) : eventStart;
      eventStart.setHours(0, 0, 0, 0);
      eventEnd.setHours(0, 0, 0, 0);

      const currentDay = new Date(eventStart);
      while (currentDay <= eventEnd) {
        days.add(formatDateKey(currentDay));
        currentDay.setDate(currentDay.getDate() + 1);
      }
    });
    return days;
  }, [events]);

  // Дни месяца для календарной сетки
  const days = useMemo(() => {
    const firstOfMonth = new Date(monthDate.getFullYear(), monthDate.getMonth(), 1);
    const weekDayIndex = (firstOfMonth.getDay() + 6) % 7;
    const gridStart = new Date(firstOfMonth);
    gridStart.setDate(firstOfMonth.getDate() - weekDayIndex);

    const today = new Date();

    return Array.from({ length: 42 }, (_, i) => {
      const date = new Date(gridStart);
      date.setDate(gridStart.getDate() + i);

      const key = formatDateKey(date);
      return {
        key,
        day: date.getDate(),
        date,
        inCurrentMonth: date.getMonth() === monthDate.getMonth(),
        isToday: sameDate(date, today),
        hasEvents: eventDays.has(key),
      };
    });
  }, [monthDate, eventDays]);

  // События на этой неделе
  const weekEvents = useMemo(() => {
    const weekStart = new Date();
    weekStart.setHours(0, 0, 0, 0);
    const dayIndex = (weekStart.getDay() + 6) % 7;
    weekStart.setDate(weekStart.getDate() - dayIndex);

    const weekEndExclusive = new Date(weekStart);
    weekEndExclusive.setDate(weekEndExclusive.getDate() + 7);

    return [...events]
      .filter((ev) => ev.start)
      .filter((ev) => {
        const start = new Date(ev.start || "");
        if (Number.isNaN(start.getTime())) return false;
        return start >= weekStart && start < weekEndExclusive;
      })
      .sort((a, b) => new Date(a.start || "").getTime() - new Date(b.start || "").getTime())
      .slice(0, 12);
  }, [events]);

  return (
    <>
      {/* Селектор календаря */}
      <div className="rounded-2xl bg-white p-4 shadow-sm ring-1 ring-gray-100">
        <div className="mb-2 flex items-center justify-between">
          <p className="text-[11px] font-semibold uppercase tracking-wide text-gray-500">Календарь</p>
          <button
            onClick={handleCreateCalendar}
            className="flex h-6 w-6 items-center justify-center rounded-full hover:bg-gray-100 transition"
            title="Создать календарь"
          >
            <Plus size={14} className="text-gray-600" />
          </button>
        </div>
        {calendars.length === 0 ? (
          <div className="rounded-lg border border-dashed border-gray-300 bg-gray-50 p-3">
            <p className="mb-2 text-xs font-medium text-gray-700">Календарей пока нет</p>
            <button
              onClick={handleCreateCalendar}
              className="w-full rounded-md bg-sky-500 px-3 py-1.5 text-xs font-medium text-white transition hover:bg-sky-600"
            >
              Создать первый календарь
            </button>
          </div>
        ) : (
          <div className="flex items-center gap-2">
            <select
              value={selectedCalendarId === null ? "" : selectedCalendarId}
              onChange={(e) => {
                const value = e.target.value;
                setSelectedCalendarId(value === "" ? null : Number(value));
              }}
              className="flex-1 rounded-lg border border-gray-300 bg-white px-2.5 py-2 text-xs text-gray-800 outline-none transition focus:border-sky-500 focus:ring-2 focus:ring-sky-100"
            >
              <option value="">📅 Все события</option>
              {calendars.map((cal) => (
                <option key={cal.id} value={cal.id}>
                  {cal.name}
                </option>
              ))}
            </select>
            {selectedCalendarId && (
              <div className="relative">
                <button
                  onClick={() => setShowCalendarMenu(!showCalendarMenu)}
                  className="flex h-9 w-9 items-center justify-center rounded-lg hover:bg-gray-100 transition"
                  title="Меню календаря"
                >
                  <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <circle cx="12" cy="12" r="1"></circle>
                    <circle cx="12" cy="5" r="1"></circle>
                    <circle cx="12" cy="19" r="1"></circle>
                  </svg>
                </button>

                {showCalendarMenu && (
                  <>
                    <div
                      className="fixed inset-0 z-[50]"
                      onClick={() => setShowCalendarMenu(false)}
                    />
                    <div className="absolute right-0 top-full mt-1 w-48 rounded-lg bg-white shadow-lg ring-1 ring-black/5 z-[60]">
                      <div className="py-1">
                        <button
                          onClick={() => {
                            const cal = calendars.find(c => c.id === selectedCalendarId);
                            if (cal) {
                              onOpenParticipantsModal({ id: cal.id, name: cal.name, user_role: (cal as any).user_role });
                            }
                            setShowCalendarMenu(false);
                          }}
                          className="flex w-full items-center gap-2 px-4 py-2 text-sm text-gray-700 hover:bg-gray-50 transition"
                        >
                          <Users size={16} />
                          Участники
                        </button>
                        <button
                          onClick={handleExportCalendar}
                          className="flex w-full items-center gap-2 px-4 py-2 text-sm text-gray-700 hover:bg-gray-50 transition"
                        >
                          <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                            <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
                            <polyline points="7 10 12 15 17 10"></polyline>
                            <line x1="12" y1="15" x2="12" y2="3"></line>
                          </svg>
                          Экспорт .ics
                        </button>
                        <button
                          onClick={() => {
                            fileInputRef.current?.click();
                          }}
                          className="flex w-full items-center gap-2 px-4 py-2 text-sm text-gray-700 hover:bg-gray-50 transition"
                        >
                          <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                            <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
                            <polyline points="17 8 12 3 7 8"></polyline>
                            <line x1="12" y1="3" x2="12" y2="15"></line>
                          </svg>
                          Импорт .ics
                        </button>
                        <input
                          ref={fileInputRef}
                          type="file"
                          accept=".ics"
                          onChange={(e) => {
                            setShowCalendarMenu(false);
                            handleImportCalendar(e);
                          }}
                          className="hidden"
                        />

                        <div className="my-1 border-t border-gray-100"></div>
                        <button
                          onClick={() => {
                            const cal = calendars.find(c => c.id === selectedCalendarId);
                            if (cal) {
                              onOpenCalendarModal(cal);
                            }
                            setShowCalendarMenu(false);
                          }}
                          className="flex w-full items-center gap-2 px-4 py-2 text-sm text-gray-700 hover:bg-gray-50 transition"
                        >
                          <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                            <path d="M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.08a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2z"></path>
                            <circle cx="12" cy="12" r="3"></circle>
                          </svg>
                          Настройки
                        </button>
                      </div>
                    </div>
                  </>
                )}
              </div>
            )}
          </div>
        )}
      </div>

      {/* Мини-календарь */}
      <div className="rounded-2xl bg-white p-5 shadow-sm ring-1 ring-gray-100">
        <div className="flex items-center justify-between text-sm font-semibold text-gray-900">
          <span>Месяц</span>
          <div className="flex items-center gap-1">
            <button
              type="button"
              onClick={() => setMonthDate((prev) => new Date(prev.getFullYear(), prev.getMonth() - 1, 1))}
              className="flex h-7 w-7 items-center justify-center rounded-full hover:bg-slate-100"
              aria-label="Предыдущий месяц"
            >
              <ChevronLeft size={16} className="text-gray-600" />
            </button>
            <span className="min-w-28 text-center text-xs font-normal text-gray-500">{monthLabel}</span>
            <button
              type="button"
              onClick={() => setMonthDate((prev) => new Date(prev.getFullYear(), prev.getMonth() + 1, 1))}
              className="flex h-7 w-7 items-center justify-center rounded-full hover:bg-slate-100"
              aria-label="Следующий месяц"
            >
              <ChevronRight size={16} className="text-gray-600" />
            </button>
          </div>
        </div>
        <div className="mt-4 grid grid-cols-7 gap-1 text-center text-xs text-gray-500">
          {weekdays.map((day) => (
            <div key={day} className="py-1 font-medium">
              {day}
            </div>
          ))}
        </div>
        <div className="mt-1 grid grid-cols-7 gap-1 text-sm text-gray-800">
          {days.map((day) => (
            <button
              key={day.key}
              type="button"
              onClick={() => day.inCurrentMonth && handleDayClick(day.date)}
              disabled={!day.inCurrentMonth}
              className={`relative flex h-9 items-center justify-center rounded-full transition ${
                day.isToday
                  ? "bg-sky-100 text-sky-800 font-semibold ring-1 ring-sky-200"
                  : day.inCurrentMonth
                  ? "hover:bg-sky-50 cursor-pointer"
                  : "text-gray-300 cursor-default"
              }`}
            >
              {day.day}
              {day.hasEvents && day.inCurrentMonth ? (
                <span className="absolute bottom-1 h-1.5 w-1.5 rounded-full bg-sky-500" />
              ) : null}
            </button>
          ))}
        </div>
      </div>

      {/* События на этой неделе */}
      <div className="rounded-2xl bg-white p-5 shadow-sm ring-1 ring-gray-100">
        <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-gray-500">На этой неделе</p>
        {loading ? (
          <p className="text-xs text-gray-500">Загрузка...</p>
        ) : error ? (
          <p className="text-xs text-red-600">{error}</p>
        ) : weekEvents.length === 0 ? (
          <p className="text-xs text-gray-500">Событий нет</p>
        ) : (
          <div className="space-y-2">
            {weekEvents.map((event) => {
              const start = event.start ? new Date(event.start) : null;
              const dateLabel =
                start && !Number.isNaN(start.getTime())
                  ? start.toLocaleString("ru-RU", {
                      weekday: "short",
                      day: "2-digit",
                      month: "2-digit",
                      hour: "2-digit",
                      minute: "2-digit",
                    })
                  : "Без даты";

              return (
                <button
                  key={`${event.id}-${event.start || ""}`}
                  type="button"
                  onClick={() => handleEventClick(event)}
                  className="w-full rounded-lg bg-gray-50 px-2.5 py-2 text-left transition hover:bg-gray-100"
                >
                  <div className="flex items-center gap-1">
                    <div
                      className="h-2 w-2 rounded-full flex-shrink-0"
                      style={{ backgroundColor: event.color_event || event.color || "#3498db" }}
                    />
                    <p className="truncate text-xs font-medium text-gray-800">{event.title}</p>
                    {(event.is_recurring || event.rule) && (
                      <span className="text-[10px] text-sky-600 flex-shrink-0" title="Повторяющееся событие">
                        ⟲
                      </span>
                    )}
                  </div>
                  <p className="mt-0.5 text-[11px] text-gray-500">{dateLabel}</p>
                </button>
              );
            })}
          </div>
        )}
      </div>
    </>
  );
});
