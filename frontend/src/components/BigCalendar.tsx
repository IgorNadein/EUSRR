"use client";

import { Calendar, dateFnsLocalizer, View, ToolbarProps, NavigateAction } from "react-big-calendar";
import { format, parse, startOfWeek, getDay } from "date-fns";
import { ru } from "date-fns/locale";
import { useState, useEffect, useCallback } from "react";
import { apiClient } from "@/lib/api";
import { useCalendar } from "@/contexts/CalendarContext";
import { X, Plus, Trash2, Settings, ChevronLeft, ChevronRight } from "lucide-react";
import { CalendarModal } from "@/components/CalendarModal";
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

  // Загрузка событий
  const loadEvents = useCallback(async () => {
    if (!selectedCalendarId) {
      setEvents([]);
      return;
    }

    try {
      setLoading(true);

      // Вычисляем диапазон для загрузки (месяц ±1 неделя)
      const start = new Date(currentDate);
      start.setDate(1);
      start.setDate(start.getDate() - 7);

      const end = new Date(currentDate);
      end.setMonth(end.getMonth() + 1);
      end.setDate(7);

      const result = await apiClient.getCalendarEvents({
        calendar: selectedCalendarId,
        start: start.toISOString().split("T")[0],
        end: end.toISOString().split("T")[0],
      });

      // Обработка пагинированного ответа
      const eventsList = Array.isArray(result) ? result : (result?.results || []);
      const parsedEvents = eventsList.map((evt: any) => ({
        ...evt,
        start: new Date(evt.start),
        end: new Date(evt.end),
      }));

      setEvents(parsedEvents);
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
    ({ start, end }: { start: Date; end: Date }) => {
      if (!selectedCalendarId) {
        alert("Сначала выберите календарь");
        return;
      }

      setEditingEvent({
        title: "",
        description: "",
        start,
        end,
        calendar: selectedCalendarId,
        color_event: "#3498db",
      });
      setShowEventModal(true);
    },
    [selectedCalendarId]
  );

  const handleSelectEvent = useCallback((event: CalendarEvent) => {
    setEditingEvent(event);
    setShowEventModal(true);
  }, []);

  const handleSaveEvent = async () => {
    if (!editingEvent || !editingEvent.title?.trim()) return;

    try {
      const eventData = {
        title: editingEvent.title!,
        description: editingEvent.description,
        start: editingEvent.start!.toISOString(),
        end: editingEvent.end!.toISOString(),
        calendar: editingEvent.calendar!,
        color_event: editingEvent.color_event || "#3498db",
      };

      if (editingEvent.id) {
        await apiClient.updateEvent(editingEvent.id, eventData);
      } else {
        await apiClient.createEvent(eventData);
      }

      await loadEvents();
      setShowEventModal(false);
      setEditingEvent(null);
    } catch (err) {
      console.error("Ошибка сохранения события:", err);
      alert("Не удалось сохранить событие");
    }
  };

  const handleDeleteEvent = async () => {
    if (!editingEvent?.id || !confirm(`Удалить событие "${editingEvent.title}"?`)) return;

    try {
      await apiClient.deleteEvent(editingEvent.id);
      await loadEvents();
      setShowEventModal(false);
      setEditingEvent(null);
    } catch (err) {
      console.error("Ошибка удаления события:", err);
      alert("Не удалось удалить событие");
    }
  };

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
                value={selectedCalendarId || ""}
                onChange={(e) => setSelectedCalendarId(Number(e.target.value))}
                className="flex-1 max-w-xs rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm text-gray-800 outline-none transition focus:border-sky-500 focus:ring-2 focus:ring-sky-100"
              >
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
      {showEventModal && editingEvent && (
        <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/50 p-4">
          <div className="w-full max-w-md rounded-2xl bg-white p-6 shadow-xl">
            <div className="mb-4 flex items-center justify-between">
              <h3 className="text-lg font-semibold text-gray-900">
                {editingEvent.id ? "Редактировать событие" : "Создать событие"}
              </h3>
              <button
                onClick={() => {
                  setShowEventModal(false);
                  setEditingEvent(null);
                }}
                className="rounded-full p-1 hover:bg-gray-100"
              >
                <X size={20} className="text-gray-600" />
              </button>
            </div>

            <div className="space-y-4">
              <div>
                <label className="mb-1 block text-sm font-medium text-gray-700">Название</label>
                <input
                  type="text"
                  value={editingEvent.title || ""}
                  onChange={(e) => setEditingEvent({ ...editingEvent, title: e.target.value })}
                  className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm outline-none focus:border-sky-500 focus:ring-2 focus:ring-sky-100"
                  placeholder="Название события"
                  autoFocus
                />
              </div>

              <div>
                <label className="mb-1 block text-sm font-medium text-gray-700">Описание</label>
                <textarea
                  value={editingEvent.description || ""}
                  onChange={(e) => setEditingEvent({ ...editingEvent, description: e.target.value })}
                  className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm outline-none focus:border-sky-500 focus:ring-2 focus:ring-sky-100"
                  placeholder="Описание (необязательно)"
                  rows={3}
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="mb-1 block text-sm font-medium text-gray-700">Начало</label>
                  <input
                    type="datetime-local"
                    value={
                      editingEvent.start
                        ? format(editingEvent.start, "yyyy-MM-dd'T'HH:mm")
                        : ""
                    }
                    onChange={(e) =>
                      setEditingEvent({ ...editingEvent, start: new Date(e.target.value) })
                    }
                    className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm outline-none focus:border-sky-500 focus:ring-2 focus:ring-sky-100"
                  />
                </div>

                <div>
                  <label className="mb-1 block text-sm font-medium text-gray-700">Конец</label>
                  <input
                    type="datetime-local"
                    value={
                      editingEvent.end ? format(editingEvent.end, "yyyy-MM-dd'T'HH:mm") : ""
                    }
                    onChange={(e) =>
                      setEditingEvent({ ...editingEvent, end: new Date(e.target.value) })
                    }
                    className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm outline-none focus:border-sky-500 focus:ring-2 focus:ring-sky-100"
                  />
                </div>
              </div>

              <div>
                <label className="mb-1 block text-sm font-medium text-gray-700">Цвет</label>
                <div className="flex items-center gap-2">
                  <input
                    type="color"
                    value={editingEvent.color_event || "#3498db"}
                    onChange={(e) =>
                      setEditingEvent({ ...editingEvent, color_event: e.target.value })
                    }
                    className="h-10 w-20 cursor-pointer rounded-lg border border-gray-300"
                  />
                  <span className="text-xs text-gray-500">
                    {editingEvent.color_event || "#3498db"}
                  </span>
                </div>
              </div>

              <div className="flex gap-2">
                <button
                  onClick={handleSaveEvent}
                  disabled={!editingEvent.title?.trim()}
                  className="flex-1 rounded-lg bg-sky-500 px-4 py-2.5 text-sm font-medium text-white transition hover:bg-sky-600 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {editingEvent.id ? "Сохранить" : "Создать"}
                </button>

                {editingEvent.id && (
                  <button
                    onClick={handleDeleteEvent}
                    className="rounded-lg border border-red-200 bg-red-50 px-4 py-2.5 text-sm font-medium text-red-600 transition hover:bg-red-100"
                    title="Удалить событие"
                  >
                    <Trash2 size={16} />
                  </button>
                )}
              </div>
            </div>
          </div>
        </div>
      )}

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
