"use client";

import { X, Plus, Clock, Calendar } from "lucide-react";
import { format } from "date-fns";
import { ru } from "date-fns/locale";

interface ViewDayEventsModalProps {
  isOpen: boolean;
  onClose: () => void;
  date: Date | null;
  events: any[];
  onEventClick: (event: any) => void;
  onCreateEvent: () => void;
}

export function ViewDayEventsModal({
  isOpen,
  onClose,
  date,
  events,
  onEventClick,
  onCreateEvent,
}: ViewDayEventsModalProps) {
  if (!isOpen || !date) return null;

  const formattedDate = format(date, "d MMMM yyyy, EEEE", { locale: ru });
  const capitalizedDate = formattedDate.charAt(0).toUpperCase() + formattedDate.slice(1);

  const dayEvents = events.filter(event => {
    const eventStart = new Date(event.start);
    const eventEnd = new Date(event.end);
    const selectedDay = new Date(date);

    // Сбрасываем время для корректного сравнения дат
    eventStart.setHours(0, 0, 0, 0);
    eventEnd.setHours(0, 0, 0, 0);
    selectedDay.setHours(0, 0, 0, 0);

    // Проверяем, попадает ли selectedDay в диапазон [eventStart, eventEnd]
    return selectedDay >= eventStart && selectedDay <= eventEnd;
  });

  // Сортируем события по времени начала
  const sortedEvents = [...dayEvents].sort((a, b) => {
    return new Date(a.start).getTime() - new Date(b.start).getTime();
  });

  const formatTime = (dateStr: string) => {
    const date = new Date(dateStr);
    return format(date, "HH:mm", { locale: ru });
  };

  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/50 backdrop-blur-sm p-2 sm:p-4">
      <div className="w-full max-w-[95vw] sm:max-w-md rounded-xl sm:rounded-2xl bg-white p-4 sm:p-6 shadow-xl max-h-[95vh] sm:max-h-[90vh] overflow-y-auto">
        <div className="mb-3 sm:mb-4 flex items-center justify-between">
          <div>
            <h3 className="text-base sm:text-lg font-semibold text-gray-900">События на {capitalizedDate}</h3>
            <p className="text-xs text-gray-500 mt-1">
              {sortedEvents.length === 0
                ? "Нет событий"
                : `${sortedEvents.length} ${sortedEvents.length === 1 ? "событие" : "событий"}`}
            </p>
          </div>
          <button
            onClick={onClose}
            className="rounded-full p-1 hover:bg-gray-100"
          >
            <X size={20} className="text-gray-600" />
          </button>
        </div>

        <div className="space-y-4">
          {sortedEvents.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-8 text-center">
              <Calendar size={40} className="text-gray-300 mb-2" />
              <p className="text-gray-500 text-sm mb-1">Нет событий в этот день</p>
              <p className="text-gray-400 text-xs">Создайте новое событие</p>
            </div>
          ) : (
            <div className="space-y-2">
              {sortedEvents.map((event) => (
                <button
                  key={event.id}
                  onClick={() => onEventClick(event)}
                  className="w-full text-left rounded-lg border border-gray-200 bg-white p-3 transition hover:border-sky-300 hover:bg-sky-50"
                >
                  <div className="flex items-start gap-2">
                    {/* Color Indicator */}
                    <div
                      className="mt-1 h-8 w-1 rounded-full flex-shrink-0"
                      style={{ backgroundColor: event.color_event || "#3498db" }}
                    />

                    <div className="flex-1 min-w-0">
                      {/* Title with recurring indicator */}
                      <div className="flex items-center gap-1.5 mb-1">
                        <h4 className="text-sm font-medium text-gray-900 truncate">
                          {event.title}
                        </h4>
                        {event.rule && (
                          <span className="text-xs bg-blue-100 text-blue-700 px-1.5 py-0.5 rounded flex-shrink-0">
                            ⟲
                          </span>
                        )}
                      </div>

                      {/* Time */}
                      <div className="flex items-center gap-1 text-xs text-gray-600">
                        <Clock size={12} />
                        <span>
                          {formatTime(event.start)} - {formatTime(event.end)}
                        </span>
                      </div>

                      {/* Description preview */}
                      {event.description && (
                        <p className="text-xs text-gray-500 mt-1.5 line-clamp-2">
                          {event.description}
                        </p>
                      )}
                    </div>
                  </div>
                </button>
              ))}
            </div>
          )}

          <div className="mt-4">
            <button
              onClick={onCreateEvent}
              className="w-full flex items-center justify-center gap-2 rounded-lg bg-sky-500 px-4 py-2.5 text-sm font-medium text-white transition hover:bg-sky-600"
            >
              <Plus size={16} />
              Создать событие
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
