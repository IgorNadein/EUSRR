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
    const eventDate = new Date(event.start);
    return eventDate.toDateString() === date.toDateString();
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
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm">
      <div className="w-full max-w-2xl rounded-2xl bg-white shadow-xl max-h-[85vh] flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-gray-200 px-6 py-4">
          <div>
            <h3 className="text-lg font-semibold text-gray-900">События на {capitalizedDate}</h3>
            <p className="text-sm text-gray-500 mt-0.5">
              {sortedEvents.length === 0
                ? "Нет событий"
                : `${sortedEvents.length} ${sortedEvents.length === 1 ? "событие" : "событий"}`}
            </p>
          </div>
          <button
            onClick={onClose}
            className="rounded-full p-1 hover:bg-gray-100 transition"
          >
            <X size={20} className="text-gray-600" />
          </button>
        </div>

        {/* Events List */}
        <div className="flex-1 overflow-y-auto px-6 py-4">
          {sortedEvents.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-12 text-center">
              <Calendar size={48} className="text-gray-300 mb-3" />
              <p className="text-gray-500 text-sm mb-1">Нет событий в этот день</p>
              <p className="text-gray-400 text-xs">Создайте новое событие, нажав кнопку ниже</p>
            </div>
          ) : (
            <div className="space-y-2">
              {sortedEvents.map((event) => (
                <button
                  key={event.id}
                  onClick={() => onEventClick(event)}
                  className="w-full text-left rounded-lg border border-gray-200 bg-white p-4 transition hover:border-sky-300 hover:bg-sky-50/50 hover:shadow-sm"
                >
                  <div className="flex items-start gap-3">
                    {/* Color Indicator */}
                    <div
                      className="mt-1 h-10 w-1 rounded-full flex-shrink-0"
                      style={{ backgroundColor: event.color_event || "#3498db" }}
                    />

                    <div className="flex-1 min-w-0">
                      {/* Title with recurring indicator */}
                      <div className="flex items-center gap-2 mb-1">
                        <h4 className="font-medium text-gray-900 truncate">
                          {event.title}
                        </h4>
                        {event.rule && (
                          <span className="text-xs bg-blue-100 text-blue-700 px-1.5 py-0.5 rounded flex-shrink-0">
                            🔁 Повторяется
                          </span>
                        )}
                      </div>

                      {/* Time */}
                      <div className="flex items-center gap-1.5 text-sm text-gray-600">
                        <Clock size={14} />
                        <span>
                          {formatTime(event.start)} - {formatTime(event.end)}
                        </span>
                      </div>

                      {/* Description preview */}
                      {event.description && (
                        <p className="text-xs text-gray-500 mt-2 line-clamp-2">
                          {event.description}
                        </p>
                      )}
                    </div>
                  </div>
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="border-t border-gray-200 px-6 py-4">
          <button
            onClick={onCreateEvent}
            className="w-full flex items-center justify-center gap-2 rounded-lg bg-sky-500 px-4 py-2.5 text-sm font-medium text-white transition hover:bg-sky-600"
          >
            <Plus size={16} />
            Создать событие на этот день
          </button>
        </div>
      </div>
    </div>
  );
}
