"use client";

import { Calendar, dateFnsLocalizer, View, ToolbarProps } from "react-big-calendar";
import { format, parse, startOfWeek, getDay } from "date-fns";
import { ru } from "date-fns/locale";
import { useState, useEffect, useCallback, useMemo, useRef } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { apiClient } from "@/lib/api";
import { useCalendar } from "@/contexts/CalendarContext";
import { Plus, ChevronDown, ChevronLeft, ChevronRight, Users, Pencil, Trash2 } from "lucide-react";
import { CalendarModal } from "@/components/CalendarModal";
import CalendarParticipantsModal from "@/components/CalendarParticipantsModal";
import { EventModal } from "@/components/EventModal";
import { ViewDayEventsModal } from "@/components/ViewDayEventsModal";
import { ViewEventDetailsModal } from "@/components/ViewEventDetailsModal";
import { DEFAULT_EVENT_COLOR, resolveEventColor } from "@/lib/calendar-event-colors";
import {
  buildCalendarOptions,
  canOpenParticipantsModal,
  isDepartmentCalendar,
  readLinkedCalendarState,
  resolveSelectedCalendar,
} from "@/lib/calendar/ui";
import {
  calendarService,
  type CalendarEvent as CalendarEventData,
  type CalendarEventDraft,
} from "@/services/calendarService";
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

type CalendarDisplayEvent = CalendarEventData & {
  start: Date;
  end: Date;
  allDay: boolean;
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
const CustomToolbar = ({ onNavigate, onView, view, date }: ToolbarProps<CalendarDisplayEvent, object>) => {
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
            className="app-action-secondary rounded-xl px-4 py-2"
          >
            Сегодня
          </button>
          <button
            onClick={() => onNavigate("PREV")}
            className="app-action-secondary flex h-10 w-10 items-center justify-center rounded-xl p-0"
            title="Назад"
          >
            <ChevronLeft size={18} />
          </button>
          <button
            onClick={() => onNavigate("NEXT")}
            className="app-action-secondary flex h-10 w-10 items-center justify-center rounded-xl p-0"
            title="Вперёд"
          >
            <ChevronRight size={18} />
          </button>
        </div>

        {/* Текущая дата */}
        <span className="text-lg font-semibold text-[var(--foreground)]">{capitalizedLabel}</span>
      </div>

      {/* Выбор вида */}
      <div className="relative">
        <select
          value={view}
          onChange={(e) => onView(e.target.value as View)}
          className="app-select w-full appearance-none rounded-xl py-2.5 pl-3 pr-10 text-sm"
        >
          <option value="month">{viewLabels.month}</option>
          <option value="week">{viewLabels.week}</option>
          <option value="day">{viewLabels.day}</option>
          <option value="agenda">{viewLabels.agenda}</option>
        </select>
        <ChevronDown size={16} className="app-text-muted pointer-events-none absolute right-3 top-1/2 -translate-y-1/2" />
      </div>
    </div>
  );
};

export function BigCalendar() {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const {
    calendars,
    selectedCalendarId,
    setSelectedCalendarId,
    calendarScope,
    setCalendarScope,
    canUseAllCalendarsMode,
    reloadCalendars,
  } = useCalendar();
  const [events, setEvents] = useState<CalendarEventData[]>([]);
  const [loading, setLoading] = useState(false);
  const [currentView, setCurrentView] = useState<View>("month");
  const [currentDate, setCurrentDate] = useState(new Date());

  // Модальные окна
  const [showEventModal, setShowEventModal] = useState(false);
  const [editingEvent, setEditingEvent] = useState<CalendarEventDraft | null>(null);
  const [showCalendarModal, setShowCalendarModal] = useState(false);
  const [editingCalendar, setEditingCalendar] = useState<{ id?: number; name: string } | null>(null);
  const [showCalendarActions, setShowCalendarActions] = useState(false);
  const [showParticipantsModal, setShowParticipantsModal] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Новые модалы для просмотра
  const [showDayEventsModal, setShowDayEventsModal] = useState(false);
  const [selectedDate, setSelectedDate] = useState<Date | null>(null);
  const [showEventDetailsModal, setShowEventDetailsModal] = useState(false);
  const [viewingEvent, setViewingEvent] = useState<CalendarEventDraft | null>(null);
  const eventsRequestIdRef = useRef(0);
  const linkedEventId = Number(searchParams.get("event") || "");
  const linkedCalendarId = Number(searchParams.get("calendar") || "");
  const linkedCalendarState = useMemo(
    () => readLinkedCalendarState(searchParams),
    [searchParams],
  );

  const selectedCalendar = useMemo(() => {
    return resolveSelectedCalendar(calendars, selectedCalendarId, linkedCalendarState);
  }, [calendars, linkedCalendarState, selectedCalendarId]);

  const calendarOptions = useMemo(() => {
    return buildCalendarOptions(calendars, selectedCalendar);
  }, [calendars, selectedCalendar]);
  const hasCalendarSelection = calendarOptions.length > 0 || selectedCalendar !== null;

  const participantsModalAvailable = canOpenParticipantsModal(selectedCalendar);
  const departmentCalendar = isDepartmentCalendar(selectedCalendar);

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

  const displayEvents = useMemo<CalendarDisplayEvent[]>(() => {
    return events.reduce<CalendarDisplayEvent[]>((result, event) => {
      if (!event.start || !event.end) {
        return result;
      }

      const start = new Date(event.start);
      const end = new Date(event.end);

      if (Number.isNaN(start.getTime()) || Number.isNaN(end.getTime())) {
        return result;
      }

      result.push({
        ...event,
        start,
        end,
        allDay: false,
      });
      return result;
    }, []);
  }, [events]);

  // Загрузка событий
  const loadEvents = useCallback(async () => {
    const requestId = ++eventsRequestIdRef.current;
    const requestedCalendarId = selectedCalendarId;

    try {
      setLoading(true);
      const start = new Date(currentDate.getFullYear(), currentDate.getMonth(), 1);
      start.setDate(start.getDate() - 7);

      const end = new Date(currentDate.getFullYear(), currentDate.getMonth() + 1, 7);
      const nextEvents = await calendarService.loadEvents(
        start,
        end,
        requestedCalendarId,
        calendarScope,
        canUseAllCalendarsMode,
        0,
      );

      // Если параллельно ушёл более новый запрос, его ответ приоритетнее.
      if (requestId !== eventsRequestIdRef.current) {
        return;
      }

      setEvents(nextEvents);
    } catch (err) {
      if (requestId !== eventsRequestIdRef.current) {
        return;
      }
      console.error("Ошибка загрузки событий:", err);
    } finally {
      if (requestId === eventsRequestIdRef.current) {
        setLoading(false);
      }
    }
  }, [calendarScope, canUseAllCalendarsMode, currentDate, selectedCalendarId]);

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
    if (selectedCalendarId === null) {
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

    const nextDraft: CalendarEventDraft = {
      title: "",
      description: "",
      start: startDate,
      end: endDate,
      calendar: selectedCalendarId,
      color_event: DEFAULT_EVENT_COLOR,
    };

    setEditingEvent(nextDraft);

    // Закрываем модал просмотра дня и открываем модал создания
    setShowDayEventsModal(false);
    setShowEventModal(true);
  }, [selectedCalendar?.can_create_events, selectedCalendarId, selectedDate]);

  const handleSelectEvent = useCallback(async (calEvent: CalendarDisplayEvent) => {
    // Если это occurrence (повторяющееся событие), загружаем базовое событие
    if (calEvent.is_recurring && calEvent.event_id) {
      try {
        const fullEvent = await calendarService.loadFullEvent(
          calEvent.event_id,
          calEvent.start.toISOString(),
          calEvent.end.toISOString(),
        );
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

  const handleCreateCalendar = useCallback(() => {
    setEditingCalendar({ name: "" });
    setShowCalendarModal(true);
    setShowCalendarActions(false);
  }, []);

  const handleEditCalendar = useCallback(() => {
    if (!selectedCalendar?.can_edit_calendar || departmentCalendar) {
      return;
    }
    setEditingCalendar({ id: selectedCalendar.id, name: selectedCalendar.name });
    setShowCalendarModal(true);
    setShowCalendarActions(false);
  }, [departmentCalendar, selectedCalendar]);

  const handleDeleteCalendar = useCallback(async () => {
    if (!selectedCalendar?.id || !selectedCalendar.can_edit_calendar || departmentCalendar) {
      return;
    }
    if (!confirm(`Удалить календарь "${selectedCalendar.name}"?`)) {
      return;
    }

    try {
      await apiClient.deleteCalendar(selectedCalendar.id);
      calendarService.clearCache();
      setSelectedCalendarId(null);
      setShowCalendarActions(false);
      await reloadCalendars();
      loadEvents();
    } catch (error) {
      console.error("Не удалось удалить календарь:", error);
      alert("Не удалось удалить календарь");
    }
  }, [departmentCalendar, loadEvents, reloadCalendars, selectedCalendar, setSelectedCalendarId]);

  const handleExportCalendar = useCallback(async () => {
    if (!selectedCalendar?.id) return;

    try {
      const blob = await calendarService.exportToICS(selectedCalendar.id);
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `calendar-${selectedCalendar.id}.ics`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
    } catch (error) {
      console.error("Не удалось экспортировать календарь:", error);
      alert("Не удалось экспортировать календарь");
    } finally {
      setShowCalendarActions(false);
    }
  }, [selectedCalendar]);

  const handleImportCalendar = useCallback(async (event: React.ChangeEvent<HTMLInputElement>) => {
    if (!selectedCalendar?.id || !event.target.files || event.target.files.length === 0) {
      return;
    }

    const file = event.target.files[0];
    try {
      const result = await calendarService.importFromICS(selectedCalendar.id, file);
      alert(`Импорт завершен!\nИмпортировано: ${result.imported}\nПропущено: ${result.skipped}`);
      calendarService.clearCache();
      loadEvents();
    } catch (error: unknown) {
      console.error("Не удалось импортировать календарь:", error);
      alert(`Ошибка импорта: ${error instanceof Error ? error.message : "Не удалось импортировать календарь"}`);
    } finally {
      if (fileInputRef.current) {
        fileInputRef.current.value = "";
      }
      setShowCalendarActions(false);
    }
  }, [loadEvents, selectedCalendar]);

  // Клик на событие из модала просмотра дня
  const handleEventClickFromDay = useCallback(async (event: CalendarEventData) => {
    setShowDayEventsModal(false);

    // Если это occurrence, загружаем базовое событие
    if (event.is_recurring && event.event_id) {
      try {
        const fullEvent = await calendarService.loadFullEvent(
          event.event_id,
          typeof event.start === "string" ? event.start : undefined,
          typeof event.end === "string" ? event.end : undefined,
        );
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
  const eventStyleGetter = (event: CalendarDisplayEvent) => {
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
        <div className="app-divider relative z-20 border-b px-6 py-5">
          <div className="flex flex-col gap-4">
            <div className="flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
              <div className="space-y-1">
                <p className="app-card-caption">Календарь</p>
                <p className="app-text-muted text-sm">
                  {selectedCalendar
                    ? `События календаря «${selectedCalendar.name}»`
                  : "Просмотр всех доступных событий"}
                </p>
              </div>

              <div className="flex items-center gap-2 self-end">
                {loading && (
                  <div className="app-text-muted flex items-center gap-2 text-sm">
                    <div className="h-4 w-4 animate-spin rounded-full border-2 border-[var(--border-subtle)] border-t-[var(--accent-primary)]"></div>
                    <span>Загрузка...</span>
                  </div>
                )}

                {hasCalendarSelection && (
                  <div className="relative z-30">
                    <button
                      type="button"
                      onClick={() => setShowCalendarActions((prev) => !prev)}
                      className="app-action-ghost flex h-8 w-8 items-center justify-center rounded-md"
                      title="Действия с календарем"
                      aria-label="Действия с календарем"
                      aria-expanded={showCalendarActions}
                      aria-haspopup="menu"
                    >
                      <ChevronRight
                        size={15}
                        className={`transition-transform duration-200 ${showCalendarActions ? "rotate-90" : ""}`}
                      />
                    </button>

                    {showCalendarActions && (
                      <>
                        <div
                          className="fixed inset-0 z-[50]"
                          onClick={() => setShowCalendarActions(false)}
                        />
                        <div className="app-menu pointer-events-auto absolute right-0 top-full z-[80] mt-1 w-52 rounded-xl">
                          <div className="py-1">
                            <button
                              type="button"
                              onClick={handleCreateCalendar}
                              className="flex w-full items-center gap-2 px-4 py-2 text-sm text-[var(--foreground)] transition hover:bg-[var(--surface-secondary)]"
                            >
                              <Plus size={16} />
                              Создать календарь
                            </button>

                            {selectedCalendar ? (
                              <>
                                <div className="app-divider my-1 border-t"></div>
                                <button
                                  type="button"
                                  onClick={() => {
                                    if (participantsModalAvailable && selectedCalendar) {
                                      setShowParticipantsModal(true);
                                    }
                                    setShowCalendarActions(false);
                                  }}
                                  disabled={!participantsModalAvailable}
                                  className="flex w-full items-center gap-2 px-4 py-2 text-sm text-[var(--foreground)] transition hover:bg-[var(--surface-secondary)]"
                                >
                                  <Users size={16} />
                                  Участники
                                </button>
                                <button
                                  type="button"
                                  onClick={handleExportCalendar}
                                  className="flex w-full items-center gap-2 px-4 py-2 text-sm text-[var(--foreground)] transition hover:bg-[var(--surface-secondary)]"
                                >
                                  <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                                    <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
                                    <polyline points="7 10 12 15 17 10"></polyline>
                                    <line x1="12" y1="15" x2="12" y2="3"></line>
                                  </svg>
                                  Экспорт .ics
                                </button>
                                <button
                                  type="button"
                                  onClick={() => fileInputRef.current?.click()}
                                  disabled={!selectedCalendar.can_edit_calendar}
                                  className="flex w-full items-center gap-2 px-4 py-2 text-sm text-[var(--foreground)] transition hover:bg-[var(--surface-secondary)]"
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
                                  onChange={handleImportCalendar}
                                  className="hidden"
                                />

                                {!departmentCalendar ? (
                                  <>
                                    <div className="app-divider my-1 border-t"></div>
                                    <button
                                      type="button"
                                      onClick={handleEditCalendar}
                                      disabled={!selectedCalendar.can_edit_calendar}
                                      className="flex w-full items-center gap-2 px-4 py-2 text-sm text-[var(--foreground)] transition hover:bg-[var(--surface-secondary)]"
                                    >
                                      <Pencil size={16} />
                                      Редактировать
                                    </button>
                                    <button
                                      type="button"
                                      onClick={() => void handleDeleteCalendar()}
                                      disabled={!selectedCalendar.can_edit_calendar}
                                      className="flex w-full items-center gap-2 px-4 py-2 text-sm text-[var(--foreground)] transition hover:bg-[var(--surface-secondary)]"
                                    >
                                      <Trash2 size={16} />
                                      Удалить
                                    </button>
                                  </>
                                ) : null}
                              </>
                            ) : null}
                          </div>
                        </div>
                      </>
                    )}
                  </div>
                )}
              </div>
            </div>

            {!hasCalendarSelection ? (
              <div className="flex flex-wrap items-center gap-2">
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
              <div className="flex flex-col gap-3 xl:flex-row xl:items-center xl:justify-between">
                <div className="flex min-w-0 flex-1 flex-col gap-3 lg:flex-row lg:items-center">
                  <label className="app-text-muted shrink-0 text-sm font-medium">Календарь</label>
                  <div className="relative min-w-0 flex-1">
                    <select
                      value={selectedCalendarId === null ? "" : selectedCalendarId}
                      onChange={(e) => {
                        const value = e.target.value;
                        setSelectedCalendarId(value === "" ? null : Number(value));
                      }}
                      className="app-select w-full min-w-0 appearance-none rounded-xl py-2.5 pl-3 pr-10 text-sm"
                    >
                      <option value="">📅 Все события</option>
                      {calendarOptions.map((cal) => (
                        <option key={cal.id} value={cal.id}>
                          {cal.name}
                        </option>
                      ))}
                    </select>
                    <ChevronDown size={16} className="app-text-muted pointer-events-none absolute right-3 top-1/2 -translate-y-1/2" />
                  </div>
                </div>

                <div className="flex flex-wrap items-center gap-2">
                  {canUseAllCalendarsMode && (
                    <div className="grid min-w-[12rem] grid-cols-2 rounded-xl border border-[var(--border-strong)] bg-[var(--surface-secondary)] p-1">
                      <button
                        type="button"
                        onClick={() => setCalendarScope("accessible")}
                        className={`min-w-0 rounded-lg px-3 py-1.5 text-center text-xs font-medium transition ${
                          calendarScope === "accessible"
                            ? "bg-[var(--surface-primary)] text-[var(--foreground)] shadow-sm"
                            : "app-text-muted hover:text-[var(--foreground)]"
                        }`}
                      >
                        Доступные
                      </button>
                      <button
                        type="button"
                        onClick={() => setCalendarScope("all")}
                        className={`min-w-0 rounded-lg px-3 py-1.5 text-center text-xs font-medium transition ${
                          calendarScope === "all"
                            ? "bg-[var(--surface-primary)] text-[var(--foreground)] shadow-sm"
                            : "app-text-muted hover:text-[var(--foreground)]"
                        }`}
                      >
                        Все
                      </button>
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Календарь */}
        <div className="relative z-0 overflow-hidden px-6 pb-6 pt-5" style={{ height: "750px" }}>
          <div className="calendar-shell h-full rounded-[1.4rem]">
            <Calendar
              localizer={localizer}
              events={displayEvents}
              startAccessor="start"
              endAccessor="end"
              allDayAccessor={(event: CalendarDisplayEvent) => event.allDay || false}
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
          calendarService.clearCache();
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
            await calendarService.deleteEvent(viewingEvent.id);
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

      {selectedCalendar && (
        <CalendarParticipantsModal
          isOpen={showParticipantsModal}
          onClose={() => setShowParticipantsModal(false)}
          calendarId={selectedCalendar.id}
          calendarName={selectedCalendar.name}
          canManageParticipants={selectedCalendar.can_manage_participants}
          calendarType={selectedCalendar.type}
          contextType={selectedCalendar.context_type}
        />
      )}
    </>
  );
}
