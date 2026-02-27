"use client";

import { X, Edit2, Trash2, Clock, Calendar, FileText, Users } from "lucide-react";
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
    <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/50 backdrop-blur-sm p-4">
      <div className="w-full max-w-md rounded-2xl bg-white p-6 shadow-xl max-h-[90vh] overflow-y-auto">
        <div className="mb-4 flex items-start justify-between">
          <div className="flex-1 min-w-0 pr-3">
            <div className="flex items-center gap-2 mb-1">
              <h3 className="text-lg font-semibold text-gray-900">
                {event.title}
              </h3>
              {event.rule && (
                <span className="text-xs bg-blue-100 text-blue-700 px-1.5 py-0.5 rounded flex-shrink-0">
                  ⟲
                </span>
              )}
            </div>
            <div className="flex items-center gap-1.5 text-xs text-gray-500">
              <div
                className="h-2.5 w-2.5 rounded-full flex-shrink-0"
                style={{ backgroundColor: event.color_event || "#3498db" }}
              />
              <span className="truncate">Календарь #{event.calendar}</span>
            </div>
          </div>
          <button
            onClick={onClose}
            className="rounded-full p-1 hover:bg-gray-100 flex-shrink-0"
          >
            <X size={20} className="text-gray-600" />
          </button>
        </div>

        <div className="space-y-4">
          {/* Time */}
          <div className="flex items-start gap-2.5">
            <Clock size={18} className="text-gray-400 mt-0.5 flex-shrink-0" />
            <div className="flex-1">
              <p className="text-sm font-medium text-gray-700 mb-1">Время</p>
              <p className="text-xs text-gray-600">
                <span className="font-medium">Начало:</span> {capitalizedStart}
              </p>
              <p className="text-xs text-gray-600 mt-0.5">
                <span className="font-medium">Конец:</span> {capitalizedEnd}
              </p>
            </div>
          </div>

          {/* Recurring Info */}
          {event.rule && event.rule_data && (
            <div className="rounded-lg bg-blue-50 border border-blue-200 p-4 space-y-2">
              <div className="flex items-center gap-2 text-blue-700 font-medium text-sm">
                <Calendar size={16} />
                <span>Повторяющееся событие</span>
              </div>
              <div className="text-sm text-blue-600 space-y-1">
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
              <FileText size={18} className="text-gray-400 mt-0.5 flex-shrink-0" />
              <div className="flex-1">
                <p className="text-sm font-medium text-gray-700 mb-1">Описание</p>
                <p className="text-xs text-gray-600 whitespace-pre-wrap">
                  {event.description}
                </p>
              </div>
            </div>
          )}

          {/* Participants */}
          {showParticipants && (
            <div className="flex items-start gap-2.5">
              <Users size={18} className="text-gray-400 mt-0.5 flex-shrink-0" />
              <div className="flex-1">
                <p className="text-sm font-medium text-gray-700 mb-1.5">
                  Участники {participants.length > 0 && `(${participants.length})`}
                </p>
                {loadingParticipants ? (
                  <p className="text-xs text-gray-500">Загрузка...</p>
                ) : participants.length > 0 ? (
                  <div className="space-y-1.5">
                    {participants.map((participant: any) => (
                      <div
                        key={participant.id}
                        className="flex items-center gap-2 rounded-lg bg-gray-50 px-2.5 py-2"
                      >
                        <div className="h-6 w-6 rounded-full bg-sky-100 flex items-center justify-center flex-shrink-0">
                          <span className="text-xs font-medium text-sky-700">
                            {participant.user_name?.[0] || "?"}
                          </span>
                        </div>
                        <div className="text-xs flex-1 min-w-0">
                          <div className="font-medium text-gray-900 truncate">
                            {participant.user_name}
                          </div>
                          <div className="text-gray-500">
                            {participant.distinction || "attendee"}
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="text-xs text-gray-500">Нет участников</p>
                )}
              </div>
            </div>
          )}

          <div className="mt-4 flex gap-2">
            <button
              onClick={onEdit}
              className="flex-1 flex items-center justify-center gap-2 rounded-lg bg-sky-500 px-4 py-2.5 text-sm font-medium text-white transition hover:bg-sky-600"
            >
              <Edit2 size={16} />
              Редактировать
            </button>
            <button
              onClick={onDelete}
              className="rounded-lg border border-red-200 bg-red-50 px-4 py-2.5 text-sm font-medium text-red-600 transition hover:bg-red-100"
              title="Удалить событие"
            >
              <Trash2 size={16} />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
