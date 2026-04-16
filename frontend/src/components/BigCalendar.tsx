"use client";

import { Calendar, dateFnsLocalizer, View, ToolbarProps, NavigateAction } from "react-big-calendar";
import { format, parse, startOfWeek, getDay } from "date-fns";
import { ru } from "date-fns/locale";
import { useState, useEffect, useCallback, useMemo } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { apiClient } from "@/lib/api";
import { useCalendar } from "@/contexts/CalendarContext";
import { X, Plus, Trash2, Settings, ChevronLeft, ChevronRight } from "lucide-react";
import { CalendarModal } from "@/components/CalendarModal";
import { EventModal } from "@/components/EventModal";
import { ViewDayEventsModal } from "@/components/ViewDayEventsModal";
import { ViewEventDetailsModal } from "@/components/ViewEventDetailsModal";
import { DEFAULT_EVENT_COLOR, resolveEventColor } from "@/lib/calendar-event-colors";
import "react-big-calendar/lib/css/react-big-calendar.css";
import "../app/calendar/calendar.css";

// Настройка локализации для react-big-calendar
const locales = {
  ru: ru,
};

const localizer = dateFnsLocalizer({
  format,
  parse,
  startOfWeek: () => startOfWeek(new Date(), { locale: ru }),
  getDay,
  locales,
});

// Типы для событий
type CalendarEvent = {
  id: number;
  title: string;
  description?: string;
  start: Date;
  end: Date;
  calendar: number;
  color_event?: string;
  rule?: number;
  rule_description?: string;
  isOccurrence?: boolean; // Флаг для повторяющихся событий
  event_id?: number; // ID базового события для occurrence
  allDay?: boolean; // Флаг целодневного события
  can_edit?: boolean;
  can_delete?: boolean;
};

// Кастомные сообщения на русском
const messages = {
  allDay: "Весь день",
  previous: "Назад",
  next: "Вперёд",
  today: "Сегодня",
  month: "Месяц",
  week: "Неделя",
  day: "День",
  agenda: "Список",
  date: "Дата",
  time: "Время",
  event: "Событие",
  noEventsInRange: "В этом диапазоне нет событий",
  showMore: (total: number) => `+${total} ещё`,
};

// Кастомный тулбар с улучшенным UI
const CustomToolbar = ({ label, onNavigate, onView, view, date }: ToolbarProps<CalendarEvent, object>) => {
  const viewLabels = {
    month: "Месяц",
    week: "Неделя",
    day: "День",
    agenda: "Список",
  };

  // Форматируем дату в именительном падеже (Февраль 2026 вместо февраля 2026)
  const formattedLabel = format(date, "LLLL yyyy", { locale: ru });
  const capitalizedLabel = formattedLabel.charAt(0).toUpperCase() + formattedLabel.slice(1);

  return (
    <div className="mb-4 space-y-3">
      {/* Навигация */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <button
            onClick={() => onNavigate("TODAY")}
            className="app-action-secondary px-3 py-2"
          >
            Сегодня
          </button>
          <button
            onClick={() => onNavigate("PREV")}
            className="app-action-secondary flex h-9 w-9 items-center justify-center p-0"
            title="Назад"
          >
            <ChevronLeft size={18} />
          </button>
          <button
            onClick={() => onNavigate("NEXT")}
            className="app-action-secondary flex h-9 w-9 items-center justify-center p-0"
            title="Вперёд"
          >
            <ChevronRight size={18} />
          </button>
        </div>

        {/* Текущая дата */}
        <span className="text-lg font-semibold text-[var(--foreground)]">{capitalizedLabel}</span>
      </div>

      {/* Выбор вида */}
      <div>
        <select
          value={view}
          onChange={(e) => onView(e.target.value as View)}
          className="app-select w-full"
        >
          <option value="month">{viewLabels.month}</option>
          <option value="week">{viewLabels.week}</option>
          <option value="day">{viewLabels.day}</option>
          <option value="agenda">{viewLabels.agenda}</option>
        </select>
      </div>
    </div>
  );
};

export function BigCalendar() {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const { calendars, selectedCalendarId, setSelectedCalendarId, reloadCalendars } = useCalendar();
  const [events, setEvents] = useState<CalendarEvent[]>([]);
  const [loading, setLoading] = useState(false);
  const [currentView, setCurrentView] = useState<View>("month");
  const [currentDate, setCurrentDate] = useState(new Date());

  // Модальные окна
  const [showEventModal, setShowEventModal] = useState(false);
  const [editingEvent, setEditingEvent] = useState<Partial<CalendarEvent> | null>(null);
  const [showCalendarModal, setShowCalendarModal] = useState(false);
  const [editingCalendar, setEditingCalendar] = useState<{ id?: number; name: string } | null>(null);

  // Новые модалы для просмотра
  const [showDayEventsModal, setShowDayEventsModal] = useState(false);
  const [selectedDate, setSelectedDate] = useState<Date | null>(null);
  const [showEventDetailsModal, setShowEventDetailsModal] = useState(false);
  const [viewingEvent, setViewingEvent] = useState<CalendarEvent | null>(null);
  const linkedEventId = Number(searchParams.get("event") || "");
  const linkedCalendarId = Number(searchParams.get("calendar") || "");
  const linkedCalendarName = searchParams.get("calendarName") || "";

  const selectedCalendar = useMemo(() => {
    const calendar = calendars.find((item) => item.id === selectedCalendarId);
    if (calendar) return calendar;
    if (selectedCalendarId && linkedCalendarName) {
      return {
        id: selectedCalendarId,
        name: linkedCalendarName,
        slug: `linked-calendar-${selectedCalendarId}`,
        can_create_events: true,
        can_edit_calendar: false,
        can_manage_participants: false,
      };
    }
    return null;
  }, [calendars, linkedCalendarName, selectedCalendarId]);

  const calendarOptions = useMemo(() => {
    if (!selectedCalendar) return calendars;
    if (calendars.some((item) => item.id === selectedCalendar.id)) {
      return calendars;
    }
    return [...calendars, selectedCalendar];
  }, [calendars, selectedCalendar]);

  const clearEventParam = useCallback(() => {
    if (!searchParams.get("event")) return;
    const nextParams = new URLSearchParams(searchParams.toString());
    nextParams.delete("event");
    router.replace(nextParams.toString() ? `${pathname}?${nextParams.toString()}` : pathname, { scroll: false });
  }, [pathname, router, searchParams]);

  useEffect(() => {
    if (!linkedCalendarId) return;
    setSelectedCalendarId(linkedCalendarId);
  }, [linkedCalendarId, setSelectedCalendarId]);

  // Загрузка событий
  const loadEvents = useCallback(async () => {
    try {
      setLoading(true);

      // Вычисляем диапазон для загрузки (месяц ±1 неделя)
      const start = new Date(currentDate);
      start.setDate(1);
      start.setDate(start.getDate() - 7);

      const end = new Date(currentDate);
      end.setMonth(end.getMonth() + 1);
      end.setDate(7);

      const startStr = start.toISOString().split("T")[0];
      const endStr = end.toISOString().split("T")[0];

      // Загружаем обычные события и occurrences параллельно
      // Если selectedCalendarId === null, загружаем все доступные события со всех календарей
      const [eventsResult, occurrencesResult] = await Promise.all([
        apiClient.getCalendarEvents({
          calendar: selectedCalendarId || undefined,
          start: startStr,
          end: endStr,
        }),
        apiClient.getOccurrences({
          calendar: selectedCalendarId || undefined,
          start: startStr,
          end: endStr,
        }),
      ]);

      // Обработка обычных событий (без правил повторения)
      const eventsList = Array.isArray(eventsResult) ? eventsResult : (eventsResult?.results || []);
      const regularEvents = eventsList
        .filter((evt: any) => !evt.rule) // Только события без правил
        .map((evt: any) => {
          const startDate = new Date(evt.start);
          const endDate = new Date(evt.end);

          return {
            ...evt,
            start: startDate,
            end: endDate,
            allDay: false, // Явно указываем что событие с временем
          };
        });

      // Обработка occurrences (повторяющихся событий)
      const occurrencesList = Array.isArray(occurrencesResult) ? occurrencesResult : (occurrencesResult?.results || []);
      
      const occurrenceEvents = occurrencesList
        .filter((occ: any) => occ && occ.is_recurring) // Только повторяющиеся (обычные события уже в regularEvents)
        .map((occ: any) => ({
          id: occ.id,
          title: occ.title.startsWith('⟲') ? occ.title : `⟲ ${occ.title}`, // Добавляем индикатор повторения
          description: occ.description,
          start: new Date(occ.start),
          end: new Date(occ.end),
          allDay: false, // Явно указываем что событие с временем
          calendar: occ.calendar, // Используем calendar из occurrence (важно для "Все события")
          color_event: resolveEventColor(occ.color_event),
          event_id: occ.event_id,
          rule: occ.rule,
          can_edit: occ.can_edit,
          can_delete: occ.can_delete,
          isOccurrence: true, // Помечаем как occurrence для корректного отображения
        }));

      // Объединяем обычные события и occurrences
      setEvents([...regularEvents, ...occurrenceEvents]);
    } catch (err) {
      console.error("Ошибка загрузки событий:", err);
    } finally {
      setLoading(false);
    }
  }, [selectedCalendarId, currentDate]);

  useEffect(() => {
    loadEvents();
  }, [loadEvents]);

  useEffect(() => {
    if (!linkedEventId || viewingEvent?.id === linkedEventId) return;

    let cancelled = false;

    apiClient.getEvent(linkedEventId)
      .then((event) => {
        if (cancelled) return;

        setViewingEvent({
          ...event,
          start: new Date(event.start),
          end: new Date(event.end),
        });
        setCurrentDate(new Date(event.start));
        setShowEventDetailsModal(true);
      })
      .catch((error) => {
        console.error("Ошибка deep-link события календаря:", error);
      });

    return () => {
      cancelled = true;
    };
  }, [linkedEventId, viewingEvent?.id]);

  // Обработчики календаря
  const handleSelectSlot = useCallback(
    ({ start }: { start: Date; end: Date }) => {
      // Открываем модальное окно просмотра событий в этот день
      setSelectedDate(start);
      setShowDayEventsModal(true);
    },
    []
  );

  // Создание события из модала просмотра дня
  const handleCreateEventFromDay = useCallback(() => {
    if (!selectedCalendarId) {
      alert("Сначала выберите календарь");
      return;
    }
    if (selectedCalendar?.can_create_events === false) {
      alert("В выбранный календарь нельзя добавлять события");
      return;
    }

    if (!selectedDate) return;

    // Устанавливаем время по умолчанию 10:00 - 11:00
    const startDate = new Date(selectedDate);
    startDate.setHours(10, 0, 0, 0);

    const endDate = new Date(selectedDate);
    endDate.setHours(11, 0, 0, 0);

    setEditingEvent({
      title: "",
      description: "",
      start: startDate,
      end: endDate,
      calendar: selectedCalendarId,
      color_event: DEFAULT_EVENT_COLOR,
    });

    // Закрываем модал просмотра дня и открываем модал создания
    setShowDayEventsModal(false);
    setShowEventModal(true);
  }, [selectedCalendar?.can_create_events, selectedCalendarId, selectedDate]);

  const handleSelectEvent = useCallback(async (calEvent: CalendarEvent) => {
    // Если это occurrence (повторяющееся событие), загружаем базовое событие
    if (calEvent.isOccurrence && calEvent.event_id) {
      try {
        const fullEvent = await apiClient.getEvent(calEvent.event_id);
        // Устанавливаем время из occurrence, но остальные данные из базового события
        setViewingEvent({
          ...fullEvent,
          start: calEvent.start,
          end: calEvent.end,
        });
        setShowEventDetailsModal(true);
      } catch (err) {
        console.error("Ошибка загрузки базового события:", err);
      }
    } else {
      // Обычное событие - открываем детали
      setViewingEvent(calEvent);
      setShowEventDetailsModal(true);
    }
  }, []);

  // Переход к редактированию из модала просмотра
  const handleEditFromDetails = useCallback(() => {
    setEditingEvent(viewingEvent);
    setShowEventDetailsModal(false);
    setShowEventModal(true);
  }, [viewingEvent]);

  // Клик на событие из модала просмотра дня
  const handleEventClickFromDay = useCallback(async (event: any) => {
    setShowDayEventsModal(false);

    // Если это occurrence, загружаем базовое событие
    if (event.isOccurrence && event.event_id) {
      try {
        const fullEvent = await apiClient.getEvent(event.event_id);
        setViewingEvent({
          ...fullEvent,
          start: event.start,
          end: event.end,
        });
        setShowEventDetailsModal(true);
      } catch (err) {
        console.error("Ошибка загрузки события:", err);
      }
    } else {
      setViewingEvent(event);
      setShowEventDetailsModal(true);
    }
  }, []);


  // Стилизация событий по цвету
  const eventStyleGetter = (event: CalendarEvent) => {
    const backgroundColor = resolveEventColor(event.color_event);
    return {
      style: {
        backgroundColor,
        borderRadius: "6px",
        opacity: 0.9,
        color: "white",
        border: "none",
        display: "block",
      },
    };
  };

  return (
    <>
      <div className="app-surface rounded-2xl">
        {/* Панель выбора календаря */}
        <div className="flex items-center justify-between px-6 py-4">
          <div className="flex items-center gap-3 flex-1">
            <label className="text-sm font-medium text-[var(--foreground)]">Календарь:</label>
            {calendars.length === 0 ? (
              <div className="flex items-center gap-2">
                <p className="app-text-muted text-sm">Календарей нет.</p>
                <button
                  onClick={() => {
                    setEditingCalendar({ name: "" });
                    setShowCalendarModal(true);
                  }}
                  className="app-link-accent text-sm font-medium"
                >
                  Создать календарь
                </button>
              </div>
            ) : (
              <div className="flex items-center gap-2 flex-1">
                <select
                  value={selectedCalendarId === null ? "" : selectedCalendarId}
                  onChange={(e) => {
                    const value = e.target.value;
                    setSelectedCalendarId(value === "" ? null : Number(value));
                  }}
                  className="app-select max-w-xs flex-1"
                >
                  <option value="">📅 Все события</option>
                  {calendarOptions.map((cal) => (
                    <option key={cal.id} value={cal.id}>
                      {cal.name}
                    </option>
                  ))}
                </select>

                <button
                  onClick={() => {
                    setEditingCalendar({ name: "" });
                    setShowCalendarModal(true);
                  }}
                  className="app-action-secondary flex h-9 w-9 items-center justify-center p-0"
                  title="Создать календарь"
                >
                  <Plus size={16} />
                </button>

                {selectedCalendarId && selectedCalendar?.can_edit_calendar && (
                  <button
                    onClick={() => {
                      const cal = selectedCalendar;
                      if (cal) {
                        setEditingCalendar({ id: cal.id, name: cal.name });
                        setShowCalendarModal(true);
                      }
                    }}
                    className="app-action-secondary flex h-9 w-9 items-center justify-center p-0"
                    title="Настройки календаря"
                  >
                    <Settings size={16} />
                  </button>
                )}
              </div>
            )}
          </div>

          {loading && (
            <div className="app-text-muted flex items-center gap-2 text-sm">
              <div className="h-4 w-4 animate-spin rounded-full border-2 border-[var(--border-subtle)] border-t-[var(--accent-primary)]"></div>
              <span>Загрузка...</span>
            </div>
          )}
        </div>

        {/* Календарь */}
        <div className="overflow-hidden px-6 pb-6" style={{ height: "750px" }}>
          <Calendar
            localizer={localizer}
            events={events}
            startAccessor="start"
            endAccessor="end"
            allDayAccessor={(event: CalendarEvent) => event.allDay || false}
            messages={messages}
            culture="ru"
            view={currentView}
            onView={(view: View) => setCurrentView(view)}
            date={currentDate}
            onNavigate={(date: Date) => setCurrentDate(date)}
            onSelectSlot={handleSelectSlot}
            onSelectEvent={handleSelectEvent}
            selectable
            eventPropGetter={eventStyleGetter}
            popup
            components={{
              toolbar: CustomToolbar,
            }}
          />
        </div>
      </div>


      {/* Модальное окно события */}
      <EventModal
        isOpen={showEventModal}
        onClose={() => {
          setShowEventModal(false);
          setEditingEvent(null);
        }}
        event={editingEvent}
        onSave={() => {
          loadEvents(); // ✅ Обновляем список событий
        }}
        showParticipants={true}
      />

      {/* Модальное окно просмотра событий дня */}
      <ViewDayEventsModal
        isOpen={showDayEventsModal}
        onClose={() => {
          setShowDayEventsModal(false);
          setSelectedDate(null);
        }}
        date={selectedDate}
        events={events}
        onEventClick={handleEventClickFromDay}
        onCreateEvent={handleCreateEventFromDay}
      />

      {/* Модальное окно просмотра деталей события */}
      <ViewEventDetailsModal
        isOpen={showEventDetailsModal}
        onClose={() => {
          setShowEventDetailsModal(false);
          setViewingEvent(null);
          clearEventParam();
        }}
        event={viewingEvent}
        onEdit={handleEditFromDetails}
        onDelete={async () => {
          if (!viewingEvent?.id) return;
          if (!confirm("Удалить это событие?")) return;

          try {
            await apiClient.deleteEvent(viewingEvent.id);
            setShowEventDetailsModal(false);
            setViewingEvent(null);
            loadEvents();
          } catch (err) {
            console.error("Ошибка удаления события:", err);
            alert("Не удалось удалить событие");
          }
        }}
        showParticipants={true}
      />

      {/* Модальное окно управления календарем */}
      <CalendarModal
        isOpen={showCalendarModal}
        onClose={() => {
          setShowCalendarModal(false);
          setEditingCalendar(null);
        }}
        calendar={editingCalendar}
      />
    </>
  );
}
