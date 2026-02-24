"use client";

import { Calendar, dateFnsLocalizer, View, ToolbarProps, NavigateAction } from "react-big-calendar";
import { format, parse, startOfWeek, getDay } from "date-fns";
import { ru } from "date-fns/locale";
import { useState, useEffect, useCallback } from "react";
import { apiClient } from "@/lib/api";
import { useCalendar } from "@/contexts/CalendarContext";
import { X, Plus, Trash2, Settings, ChevronLeft, ChevronRight } from "lucide-react";
import { CalendarModal } from "@/components/CalendarModal";
import { EventModal } from "@/components/EventModal";
import { ViewDayEventsModal } from "@/components/ViewDayEventsModal";
import { ViewEventDetailsModal } from "@/components/ViewEventDetailsModal";
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
            className="rounded-lg border border-gray-300 px-3 py-2 text-sm font-medium text-gray-700 transition hover:bg-gray-50"
          >
            Сегодня
          </button>
          <button
            onClick={() => onNavigate("PREV")}
            className="flex h-9 w-9 items-center justify-center rounded-lg border border-gray-300 text-gray-700 transition hover:bg-gray-50"
            title="Назад"
          >
            <ChevronLeft size={18} />
          </button>
          <button
            onClick={() => onNavigate("NEXT")}
            className="flex h-9 w-9 items-center justify-center rounded-lg border border-gray-300 text-gray-700 transition hover:bg-gray-50"
            title="Вперёд"
          >
            <ChevronRight size={18} />
          </button>
        </div>

        {/* Текущая дата */}
        <span className="text-lg font-semibold text-gray-800">{capitalizedLabel}</span>
      </div>

      {/* Выбор вида */}
      <div>
        <select
          value={view}
          onChange={(e) => onView(e.target.value as View)}
          className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm text-gray-700 outline-none transition focus:border-sky-500 focus:ring-2 focus:ring-sky-100"
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

      // Если календарь не выбран (null) - загружаем все события пользователя
      if (!selectedCalendarId) {
        const myEventsResult = await apiClient.getMyEvents({
          start: startStr,
          end: endStr,
        });

        const eventsList = Array.isArray(myEventsResult) ? myEventsResult : (myEventsResult?.results || []);
        const allEvents = eventsList.map((evt: any) => ({
          ...evt,
          start: new Date(evt.start),
          end: new Date(evt.end),
          allDay: false,
          title: evt.rule ? `⟲ ${evt.title}` : evt.title,
        }));

        setEvents(allEvents);
        setLoading(false);
        return;
      }

      // Загружаем обычные события и occurrences параллельно для выбранного календаря
      const [eventsResult, occurrencesResult] = await Promise.all([
        apiClient.getCalendarEvents({
          calendar: selectedCalendarId,
          start: startStr,
          end: endStr,
        }),
        apiClient.getOccurrences({
          calendar: selectedCalendarId,
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
        .filter((occ: any) => occ && occ.is_recurring) // Только повторяющиеся (избегаем дубликатов)
        .map((occ: any) => ({
          id: occ.id,
          title: `⟲ ${occ.title}`, // Добавляем индикатор повторения
          description: occ.description,
          start: new Date(occ.start),
          end: new Date(occ.end),
          allDay: false, // Явно указываем что событие с временем
          calendar: selectedCalendarId, // Календарь уже известен из запроса
          color_event: occ.color_event || '#3498db',
          event_id: occ.event_id,
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
      color_event: "#3498db",
    });

    // Закрываем модал просмотра дня и открываем модал создания
    setShowDayEventsModal(false);
    setShowEventModal(true);
  }, [selectedCalendarId, selectedDate]);

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
    const backgroundColor = event.color_event || "#3498db";
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
      <div className="rounded-2xl bg-white shadow-sm ring-1 ring-gray-100">
        {/* Панель выбора календаря */}
        <div className="flex items-center justify-between px-6 py-4">
          <div className="flex items-center gap-3 flex-1">
            <label className="text-sm font-medium text-gray-700">Календарь:</label>
            {calendars.length === 0 ? (
              <div className="flex items-center gap-2">
                <p className="text-sm text-gray-500">Календарей нет.</p>
                <button
                  onClick={() => {
                    setEditingCalendar({ name: "" });
                    setShowCalendarModal(true);
                  }}
                  className="text-sm text-sky-500 hover:text-sky-600 font-medium transition-colors"
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
                  className="flex-1 max-w-xs rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm text-gray-800 outline-none transition focus:border-sky-500 focus:ring-2 focus:ring-sky-100"
                >
                  <option value="">📅 Все события</option>
                  {calendars.map((cal) => (
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
                  className="flex h-9 w-9 items-center justify-center rounded-lg border border-gray-300 text-gray-700 transition hover:bg-gray-50"
                  title="Создать календарь"
                >
                  <Plus size={16} />
                </button>

                {selectedCalendarId && (
                  <button
                    onClick={() => {
                      const cal = calendars.find((c) => c.id === selectedCalendarId);
                      if (cal) {
                        setEditingCalendar({ id: cal.id, name: cal.name });
                        setShowCalendarModal(true);
                      }
                    }}
                    className="flex h-9 w-9 items-center justify-center rounded-lg border border-gray-300 text-gray-700 transition hover:bg-gray-50"
                    title="Настройки календаря"
                  >
                    <Settings size={16} />
                  </button>
                )}
              </div>
            )}
          </div>

          {loading && (
            <div className="flex items-center gap-2 text-sm text-gray-500">
              <div className="h-4 w-4 animate-spin rounded-full border-2 border-gray-300 border-t-sky-500"></div>
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
