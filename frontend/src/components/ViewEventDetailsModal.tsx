"use client";

import { Edit2, Trash2, Clock, Calendar, FileText, Users } from "lucide-react";
import { Modal } from "@/components/ui";
import { resolveEventColor } from "@/lib/calendar-event-colors";
import { format } from "date-fns";
import { ru } from "date-fns/locale";
import { useState, useEffect } from "react";
import { apiClient } from "@/lib/api";

interface ViewEventDetailsModalProps {
  isOpen: boolean;
  onClose: () => void;
  event: any | null;
  onEdit: () => void;
  onDelete: () => void;
  showParticipants?: boolean;
}

// Маппинг частот на русский
const FREQUENCY_LABELS: Record<string, string> = {
  YEARLY: "Каждый год",
  MONTHLY: "Каждый месяц",
  WEEKLY: "Каждую неделю",
  DAILY: "Каждый день",
  HOURLY: "Каждый час",
  MINUTELY: "Каждую минуту",
  SECONDLY: "Каждую секунду",
};

// Маппинг дней недели (0 = Monday в dateutil.rrule)
const WEEKDAY_LABELS: Record<number, string> = {
  0: "ПН",
  1: "ВТ",
  2: "СР",
  3: "ЧТ",
  4: "ПТ",
  5: "СБ",
  6: "ВС",
};

// Нормализация byweekday в массив чисел
function normalizeByweekday(byweekday: any): number[] {
  if (!byweekday) return [];
  if (Array.isArray(byweekday)) return byweekday;
  if (typeof byweekday === 'string') {
    return byweekday.split(',').map(d => parseInt(d.trim(), 10)).filter(n => !isNaN(n));
  }
  if (typeof byweekday === 'number') return [byweekday];
  return [];
}

export function ViewEventDetailsModal({
  isOpen,
  onClose,
  event,
  onEdit,
  onDelete,
  showParticipants = false,
}: ViewEventDetailsModalProps) {
  const [participants, setParticipants] = useState<any[]>([]);
  const [loadingParticipants, setLoadingParticipants] = useState(false);

  useEffect(() => {
    if (isOpen && event?.id && showParticipants) {
      loadParticipants();
    } else {
      setParticipants([]);
    }
  }, [isOpen, event?.id, showParticipants]);

  const loadParticipants = async () => {
    if (!event?.id) return;

    try {
      setLoadingParticipants(true);
      const result = await apiClient.getEventParticipants(event.id);
      const participantsList = Array.isArray(result) ? result : (result?.results || []);
      setParticipants(participantsList);
    } catch (error) {
      console.error("Failed to load participants:", error);
    } finally {
      setLoadingParticipants(false);
    }
  };

  if (!isOpen || !event) return null;

  const formatDateTime = (dateStr: string) => {
    const date = new Date(dateStr);
    return format(date, "d MMMM yyyy, HH:mm", { locale: ru });
  };

  const formatDate = (dateStr: string) => {
    const date = new Date(dateStr);
    return format(date, "d MMMM yyyy", { locale: ru });
  };

  const capitalizedStart = formatDateTime(event.start).charAt(0).toUpperCase() + formatDateTime(event.start).slice(1);
  const capitalizedEnd = formatDateTime(event.end).charAt(0).toUpperCase() + formatDateTime(event.end).slice(1);

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title={event.title}
      size="sm"
      footer={
        <div className="flex gap-2">
          <button
            onClick={onEdit}
            className="app-action-primary flex flex-1 items-center justify-center gap-2 rounded-lg px-4 py-2.5 text-sm font-medium"
          >
            <Edit2 size={16} />
            Редактировать
          </button>
          <button
            onClick={onDelete}
            className="app-action-danger rounded-lg px-4 py-2.5 text-sm font-medium"
            title="Удалить событие"
          >
            <Trash2 size={16} />
          </button>
        </div>
      }
    >
      <div className="space-y-4">
        {/* Event meta */}
        <div className="flex items-center gap-2">
          {event.rule && (
            <span className="app-badge app-badge-accent shrink-0 rounded px-1.5 py-0.5 text-xs">
              ⟲
            </span>
          )}
          <div className="app-text-muted flex items-center gap-1.5 text-xs">
            <div
              className="h-2.5 w-2.5 rounded-full flex-shrink-0"
              style={{ backgroundColor: resolveEventColor(event.color_event) }}
            />
            <span className="truncate">Календарь #{event.calendar}</span>
          </div>
        </div>
          {/* Time */}
          <div className="flex items-start gap-2.5">
            <Clock size={18} className="app-text-muted mt-0.5 flex-shrink-0" />
            <div className="flex-1">
              <p className="mb-1 text-sm font-medium text-[var(--foreground)]">Время</p>
              <p className="app-text-muted text-xs">
                <span className="font-medium">Начало:</span> {capitalizedStart}
              </p>
              <p className="app-text-muted mt-0.5 text-xs">
                <span className="font-medium">Конец:</span> {capitalizedEnd}
              </p>
            </div>
          </div>

          {/* Recurring Info */}
          {event.rule && event.rule_data && (
            <div className="app-selected space-y-2 rounded-lg p-4">
              <div className="app-accent-text flex items-center gap-2 text-sm font-medium">
                <Calendar size={16} />
                <span>Повторяющееся событие</span>
              </div>
              <div className="app-accent-text space-y-1 text-sm">
                <div>
                  Частота: <span className="font-medium">{FREQUENCY_LABELS[event.rule_data.frequency] || event.rule_data.frequency}</span>
                </div>
                {event.rule_data.params?.byweekday && (
                  <div>
                    Дни недели: <span className="font-medium">
                      {normalizeByweekday(event.rule_data.params.byweekday).map((day: number) => WEEKDAY_LABELS[day]).join(", ")}
                    </span>
                  </div>
                )}
                {event.rule_data.params?.count && (
                  <div>
                    Повторений: <span className="font-medium">{event.rule_data.params.count}</span>
                  </div>
                )}
                {event.end_recurring_period && (
                  <div>
                    До: <span className="font-medium">{formatDate(event.end_recurring_period)}</span>
                  </div>
                )}
              </div>

            </div>
          )}

          {/* Description */}
          {event.description && (
            <div className="flex items-start gap-2.5">
              <FileText size={18} className="app-text-muted mt-0.5 flex-shrink-0" />
              <div className="flex-1">
                <p className="mb-1 text-sm font-medium text-[var(--foreground)]">Описание</p>
                <p className="app-text-wrap app-text-muted whitespace-pre-wrap text-xs">
                  {event.description}
                </p>
              </div>
            </div>
          )}

          {/* Participants */}
          {showParticipants && (
            <div className="flex items-start gap-2.5">
              <Users size={18} className="app-text-muted mt-0.5 flex-shrink-0" />
              <div className="flex-1">
                <p className="mb-1.5 text-sm font-medium text-[var(--foreground)]">
                  Участники {participants.length > 0 && `(${participants.length})`}
                </p>
                {loadingParticipants ? (
                  <p className="app-text-muted text-xs">Загрузка...</p>
                ) : participants.length > 0 ? (
                  <div className="space-y-1.5">
                    {participants.map((participant: any) => (
                      <div
                        key={participant.id}
                        className="app-surface-muted flex items-center gap-2 rounded-lg px-2.5 py-2"
                      >
                        <div className="app-avatar-fallback flex h-6 w-6 flex-shrink-0 items-center justify-center rounded-full">
                          <span className="text-xs font-medium">
                            {participant.user_name?.[0] || "?"}
                          </span>
                        </div>
                        <div className="text-xs flex-1 min-w-0">
                          <div className="truncate font-medium text-[var(--foreground)]">
                            {participant.user_name}
                          </div>
                          <div className="app-text-muted">
                            {participant.distinction || "attendee"}
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="app-text-muted text-xs">Нет участников</p>
                )}
              </div>
            </div>
          )}

      </div>
    </Modal>
  );
}
