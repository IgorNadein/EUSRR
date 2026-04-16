"use client";

import { memo, useMemo, useState, useRef, useEffect, useCallback } from "react";
import { useSearchParams } from "next/navigation";
import { ChevronDown, ChevronLeft, ChevronRight, Pencil, Trash2, Users } from "lucide-react";
import { apiClient } from "@/lib/api";
import { useCalendar } from "@/contexts/CalendarContext";
import { useCalendarEvents } from "@/hooks/calendar/useCalendarEvents";
import { calendarService, formatDateKey, type CalendarEvent } from "@/services/calendarService";
import { DEFAULT_EVENT_COLOR, resolveEventColor } from "@/lib/calendar-event-colors";

// Типы
interface CalendarCardProps {
  onOpenCalendarModal: (calendar?: { id?: number; name: string }) => void;
  onOpenEventModal: (event: any, date?: Date) => void;
  onOpenParticipantsModal: (calendar: {
    id: number;
    name: string;
    user_role?: string;
    can_manage_participants?: boolean;
    type?: string | null;
    context_type?: string | null;
  }) => void;
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
  const {
    calendars,
    selectedCalendarId,
    setSelectedCalendarId,
    calendarScope,
    setCalendarScope,
    canUseAllCalendarsMode,
    reloadCalendars,
  } = useCalendar();
  const searchParams = useSearchParams();
  const linkedCalendarName = searchParams.get("calendarName") || "";
  const linkedCalendarType = searchParams.get("calendarType") || "";
  const linkedContextType = searchParams.get("contextType") || "";

  const [monthDate, setMonthDate] = useState(() => {
    const now = new Date();
    return new Date(now.getFullYear(), now.getMonth(), 1);
  });

  const [showCalendarMenu, setShowCalendarMenu] = useState(false);
  const [selectedDate, setSelectedDate] = useState<Date | null>(null);
  const [eventsViewMode, setEventsViewMode] = useState<"week" | "month">("week");
  const fileInputRef = useRef<HTMLInputElement>(null);

  const selectedCalendar = useMemo(() => {
    const calendar = calendars.find((item) => item.id === selectedCalendarId);
    if (calendar) return calendar;
    if (selectedCalendarId && linkedCalendarName) {
      return {
        id: selectedCalendarId,
        name: linkedCalendarName,
        slug: `linked-calendar-${selectedCalendarId}`,
        type: linkedCalendarType || null,
        context_type: linkedContextType || null,
        can_create_events: true,
        can_edit_calendar: false,
        can_manage_participants: false,
      };
    }
    return null;
  }, [calendars, linkedCalendarName, linkedCalendarType, linkedContextType, selectedCalendarId]);

  const calendarOptions = useMemo(() => {
    if (!selectedCalendar) return calendars;
    if (calendars.some((item) => item.id === selectedCalendar.id)) {
      return calendars;
    }
    return [...calendars, selectedCalendar];
  }, [calendars, selectedCalendar]);

  const canOpenParticipantsModal = Boolean(
    selectedCalendar && (
      selectedCalendar.can_manage_participants ||
      selectedCalendar.type === "department" ||
      selectedCalendar.context_type === "department"
    )
  );
  const isDepartmentCalendar = Boolean(
    selectedCalendar && (
      selectedCalendar.type === "department" ||
      selectedCalendar.context_type === "department"
    )
  );

  // Загружаем события через хук
  const { events, loading, error } = useCalendarEvents({
    monthDate,
    selectedCalendarId,
    calendarScope,
    canUseAllCalendarsMode,
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
    if (selectedCalendar?.can_create_events === false) {
      return;
    }
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
      color_event: DEFAULT_EVENT_COLOR,
    };
    onOpenEventModal(newEvent, date);
  }, [onOpenEventModal, selectedCalendar?.can_create_events, selectedCalendarId]);

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

  const handleDeleteCalendar = useCallback(async () => {
    if (!selectedCalendar?.id || !selectedCalendar.can_edit_calendar) {
      return;
    }
    if (!confirm(`Удалить календарь "${selectedCalendar.name}"?`)) {
      return;
    }

    try {
      await apiClient.deleteCalendar(selectedCalendar.id);
      calendarService.clearCache();
      setSelectedCalendarId(null);
      setEventsRefreshTrigger((prev) => prev + 1);
      await reloadCalendars();
    } catch (error) {
      console.error("Не удалось удалить календарь:", error);
      alert("Не удалось удалить календарь");
    } finally {
      setShowCalendarMenu(false);
    }
  }, [
    reloadCalendars,
    selectedCalendar,
    setEventsRefreshTrigger,
    setSelectedCalendarId,
  ]);

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

  // События в выбранном месяце (привязано к monthDate мини-календаря)
  const monthEvents = useMemo(() => {
    const monthStart = new Date(monthDate.getFullYear(), monthDate.getMonth(), 1);
    monthStart.setHours(0, 0, 0, 0);

    const monthEnd = new Date(monthDate.getFullYear(), monthDate.getMonth() + 1, 0);
    monthEnd.setHours(23, 59, 59, 999);

    return [...events]
      .filter((ev) => ev.start)
      .filter((ev) => {
        const start = new Date(ev.start || "");
        if (Number.isNaN(start.getTime())) return false;
        return start >= monthStart && start <= monthEnd;
      })
      .sort((a, b) => new Date(a.start || "").getTime() - new Date(b.start || "").getTime())
      .slice(0, 30);
  }, [events, monthDate]);

  return (
    <>
      {/* Селектор календаря */}
      <div className="app-surface rounded-2xl p-4">
        <div className="mb-2 flex items-center justify-between">
          <p className="app-text-muted text-[11px] font-semibold uppercase tracking-wide">Календарь</p>
          <div className="relative">
            <button
              onClick={() => setShowCalendarMenu(!showCalendarMenu)}
              className="app-icon-button flex h-6 w-6 items-center justify-center rounded-full transition"
              title="Меню календаря"
              aria-expanded={showCalendarMenu}
            >
              {showCalendarMenu ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
            </button>

            {showCalendarMenu && (
              <>
                <div
                  className="fixed inset-0 z-[50]"
                  onClick={() => setShowCalendarMenu(false)}
                />
                <div className="app-menu absolute right-0 top-full z-[60] mt-1 w-48 rounded-lg">
                  <div className="py-1">
                    <button
                      onClick={() => {
                        handleCreateCalendar();
                        setShowCalendarMenu(false);
                      }}
                      className="flex w-full items-center gap-2 px-4 py-2 text-sm text-[var(--foreground)] transition hover:bg-[var(--surface-secondary)]"
                    >
                      <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                        <path d="M5 12h14"></path>
                        <path d="M12 5v14"></path>
                      </svg>
                      Создать календарь
                    </button>

                    {selectedCalendar ? (
                      <>
                        <div className="app-divider my-1 border-t"></div>
                        <button
                          onClick={() => {
                            if (canOpenParticipantsModal) {
                              onOpenParticipantsModal({
                                id: selectedCalendar.id,
                                name: selectedCalendar.name,
                                user_role: (selectedCalendar as any).user_role,
                                can_manage_participants: selectedCalendar.can_manage_participants,
                                type: selectedCalendar.type,
                                context_type: selectedCalendar.context_type,
                              });
                            }
                            setShowCalendarMenu(false);
                          }}
                          disabled={!canOpenParticipantsModal}
                          className="flex w-full items-center gap-2 px-4 py-2 text-sm text-[var(--foreground)] transition hover:bg-[var(--surface-secondary)]"
                        >
                          <Users size={16} />
                          Участники
                        </button>
                        <button
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
                          onClick={() => {
                            fileInputRef.current?.click();
                          }}
                          disabled={!selectedCalendar?.can_edit_calendar}
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
                          onChange={(e) => {
                            setShowCalendarMenu(false);
                            handleImportCalendar(e);
                          }}
                          className="hidden"
                        />

                        {!isDepartmentCalendar ? (
                          <>
                            <div className="app-divider my-1 border-t"></div>
                            <button
                              onClick={() => {
                                if (selectedCalendar.can_edit_calendar) {
                                  onOpenCalendarModal(selectedCalendar);
                                }
                                setShowCalendarMenu(false);
                              }}
                              disabled={!selectedCalendar.can_edit_calendar}
                              className="flex w-full items-center gap-2 px-4 py-2 text-sm text-[var(--foreground)] transition hover:bg-[var(--surface-secondary)]"
                            >
                              <Pencil size={16} />
                              Редактировать
                            </button>
                            <button
                              onClick={() => {
                                void handleDeleteCalendar();
                              }}
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
        </div>
        {calendars.length === 0 ? (
          <div className="rounded-lg border border-dashed border-[var(--border-strong)] bg-[var(--surface-secondary)] p-3">
            <p className="mb-2 text-xs font-medium text-[var(--foreground)]">Календарей пока нет</p>
            <button
              onClick={handleCreateCalendar}
              className="app-action-primary w-full rounded-md px-3 py-1.5 text-xs font-medium"
            >
              Создать первый календарь
            </button>
          </div>
        ) : (
          <div className="space-y-2">
            {canUseAllCalendarsMode && (
              <div className="grid w-full grid-cols-2 rounded-xl border border-[var(--border-strong)] bg-[var(--surface-secondary)] p-1">
                <button
                  type="button"
                  onClick={() => setCalendarScope("accessible")}
                  className={`min-w-0 rounded-lg px-2.5 py-1 text-center text-[11px] font-medium transition ${
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
                  className={`min-w-0 rounded-lg px-2.5 py-1 text-center text-[11px] font-medium transition ${
                    calendarScope === "all"
                      ? "bg-[var(--surface-primary)] text-[var(--foreground)] shadow-sm"
                      : "app-text-muted hover:text-[var(--foreground)]"
                  }`}
                >
                  Все
                </button>
              </div>
            )}

            <div className="flex items-center gap-2">
              <select
                value={selectedCalendarId === null ? "" : selectedCalendarId}
                onChange={(e) => {
                  const value = e.target.value;
                  setSelectedCalendarId(value === "" ? null : Number(value));
                }}
                className="app-select flex-1 rounded-lg px-2.5 py-2 text-xs"
              >
                <option value="">📅 Все события</option>
                {calendarOptions.map((cal) => (
                  <option key={cal.id} value={cal.id}>
                    {cal.name}
                  </option>
                ))}
              </select>
            </div>
          </div>
        )}
      </div>

      {/* Мини-календарь */}
      <div className="app-surface rounded-2xl p-5">
        <div className="flex items-center justify-between text-sm font-semibold text-[var(--foreground)]">
          <span>Месяц</span>
          <div className="flex items-center gap-1">
            <button
              type="button"
              onClick={() => setMonthDate((prev) => new Date(prev.getFullYear(), prev.getMonth() - 1, 1))}
              className="app-icon-button flex h-7 w-7 items-center justify-center rounded-full"
              aria-label="Предыдущий месяц"
            >
              <ChevronLeft size={16} />
            </button>
            <span className="app-text-muted min-w-28 text-center text-xs font-normal">{monthLabel}</span>
            <button
              type="button"
              onClick={() => setMonthDate((prev) => new Date(prev.getFullYear(), prev.getMonth() + 1, 1))}
              className="app-icon-button flex h-7 w-7 items-center justify-center rounded-full"
              aria-label="Следующий месяц"
            >
              <ChevronRight size={16} />
            </button>
          </div>
        </div>
        <div className="app-text-muted mt-4 grid grid-cols-7 gap-1 text-center text-xs">
          {weekdays.map((day) => (
            <div key={day} className="py-1 font-medium">
              {day}
            </div>
          ))}
        </div>
        <div className="mt-1 grid grid-cols-7 gap-1 text-sm text-[var(--foreground)]">
          {days.map((day) => (
            <button
              key={day.key}
              type="button"
              onClick={() => day.inCurrentMonth && handleDayClick(day.date)}
              disabled={!day.inCurrentMonth}
              className={`relative flex h-9 items-center justify-center rounded-full transition ${
                day.isToday
                  ? "app-selected app-accent-text font-semibold"
                  : day.inCurrentMonth
                  ? "cursor-pointer hover:bg-[var(--accent-soft)]"
                  : "cursor-default text-[color:color-mix(in_srgb,var(--muted-foreground)_48%,transparent)]"
              }`}
            >
              {day.day}
              {day.hasEvents && day.inCurrentMonth ? (
                <span className="app-dot-accent absolute bottom-1 h-1.5 w-1.5 rounded-full" />
              ) : null}
            </button>
          ))}
        </div>
      </div>

      {/* События — неделя / месяц */}
      <div className="app-surface rounded-2xl p-5">
        <div className="mb-3 grid w-full grid-cols-2 rounded-xl border border-[var(--border-strong)] bg-[var(--surface-secondary)] p-1">
          <button
            type="button"
            onClick={() => setEventsViewMode("week")}
            className={`min-w-0 rounded-lg px-2.5 py-1 text-center text-[11px] font-medium transition ${
              eventsViewMode === "week"
                ? "bg-[var(--surface-primary)] text-[var(--foreground)] shadow-sm"
                : "app-text-muted hover:text-[var(--foreground)]"
            }`}
          >
            Неделя
          </button>
          <button
            type="button"
            onClick={() => setEventsViewMode("month")}
            className={`min-w-0 rounded-lg px-2.5 py-1 text-center text-[11px] font-medium transition ${
              eventsViewMode === "month"
                ? "bg-[var(--surface-primary)] text-[var(--foreground)] shadow-sm"
                : "app-text-muted hover:text-[var(--foreground)]"
            }`}
          >
            Месяц
          </button>
        </div>

        {(() => {
          const displayEvents = eventsViewMode === "week" ? weekEvents : monthEvents;

          if (loading) return <p className="app-text-muted text-xs">Загрузка...</p>;
          if (error) return <p className="app-feedback-danger rounded-lg px-3 py-2 text-xs">{error}</p>;
          if (displayEvents.length === 0) return <p className="app-text-muted text-xs">Событий нет</p>;

          return (
            <div className="space-y-2">
              {displayEvents.map((event) => {
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
                    key={`${eventsViewMode}-${event.id}-${event.start || ""}`}
                    type="button"
                    onClick={() => handleEventClick(event)}
                    className="w-full rounded-lg bg-[var(--surface-secondary)] px-2.5 py-2 text-left transition hover:bg-[var(--surface-tertiary)]"
                  >
                    <div className="flex items-center gap-1">
                      <div
                        className="h-2 w-2 rounded-full flex-shrink-0"
                        style={{ backgroundColor: resolveEventColor(event.color_event || event.color) }}
                      />
                      <p className="truncate text-xs font-medium text-[var(--foreground)]">{event.title}</p>
                      {(event.is_recurring || event.rule) && (
                        <span className="app-accent-text shrink-0 text-[10px]" title="Повторяющееся событие">
                          ⟲
                        </span>
                      )}
                    </div>
                    <p className="app-text-muted mt-0.5 text-[11px]">{dateLabel}</p>
                  </button>
                );
              })}
            </div>
          );
        })()}
      </div>
    </>
  );
});
