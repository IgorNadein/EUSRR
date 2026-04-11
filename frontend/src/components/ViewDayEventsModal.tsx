"use client";

import { Plus, Clock, Calendar } from "lucide-react";
import { Modal } from "@/components/ui";
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
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title={`События на ${capitalizedDate}`}
      size="sm"
      footer={
        <button
          onClick={onCreateEvent}
          className="app-action-primary flex w-full items-center justify-center gap-2 rounded-lg px-4 py-2.5 text-sm font-medium"
        >
          <Plus size={16} />
          Создать событие
        </button>
      }
    >
      <div className="space-y-4">
        <p className="app-text-muted text-xs">
          {sortedEvents.length === 0
            ? "Нет событий"
            : `${sortedEvents.length} ${sortedEvents.length === 1 ? "событие" : "событий"}`}
        </p>
          {sortedEvents.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-8 text-center">
              <Calendar size={40} className="app-text-muted mb-2 opacity-40" />
              <p className="app-text-muted mb-1 text-sm">Нет событий в этот день</p>
              <p className="app-text-muted text-xs">Создайте новое событие</p>
            </div>
          ) : (
            <div className="space-y-2">
              {sortedEvents.map((event) => (
                <button
                  key={event.id}
                  onClick={() => onEventClick(event)}
                  className="app-surface w-full rounded-lg p-3 text-left transition hover:bg-[var(--surface-secondary)]"
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
                        <h4 className="truncate text-sm font-medium text-[var(--foreground)]">
                          {event.title}
                        </h4>
                        {event.rule && (
                          <span className="app-badge app-badge-accent shrink-0 rounded px-1.5 py-0.5 text-xs">
                            ⟲
                          </span>
                        )}
                      </div>

                      {/* Time */}
                      <div className="app-text-muted flex items-center gap-1 text-xs">
                        <Clock size={12} />
                        <span>
                          {formatTime(event.start)} - {formatTime(event.end)}
                        </span>
                      </div>

                      {/* Description preview */}
                      {event.description && (
                        <p className="app-text-muted mt-1.5 line-clamp-2 text-xs">
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
    </Modal>
  );
}
